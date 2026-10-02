"""Readiness must fail closed for stale pulses, dependency faults and real process loss."""

import json
import os
from pathlib import Path
import subprocess
import socket
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
import redis

from app.auth_config import AuthPolicy
from app.main import create_app
from app.db.engine import Database
from app.runtime_health import database_ready, queue_connection, readiness, worker_ready, WORKER_TTL
from app.worker_config import WorkerSettings
from sqlalchemy import text

REVISION = "a" * 40


def pulse(**updates):
    return {"revision": REVISION, "instance": str(uuid4()), "pid": 123,
            "reported_at": 100.0, "database_ready": True, **updates}


class Queue:
    def __init__(self, value=None, ttl=30):
        self.value, self.expiry = value, ttl

    def ttl(self, key):
        return self.expiry

    def get(self, key):
        return self.value

    def ping(self):
        return True

    def pipeline(self, transaction=False):
        queue = self

        class Pipeline:
            def __init__(self):
                self.commands = []

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def ping(self):
                self.commands.append(queue.ping)
                return self

            def ttl(self, key):
                self.commands.append(lambda: queue.ttl(key))
                return self

            def get(self, key):
                self.commands.append(lambda: queue.get(key))
                return self

            def execute(self):
                return [command() for command in self.commands]

        assert transaction is False
        return Pipeline()


@pytest.mark.parametrize("change", [
    {"revision": "b" * 40}, {"database_ready": False}, {"database_ready": 1},
    {"pid": True}, {"pid": 0}, {"pid": 2**31}, {"instance": "invalid"},
    {"instance": True}, {"reported_at": True}, {"reported_at": float("nan")},
    {"reported_at": float("inf")}, {"reported_at": 70}, {"reported_at": 106},
    {"extra": "must not silently drop"},
])
def test_invalid_worker_pulses_never_report_ready(change):
    assert not worker_ready(Queue(json.dumps(pulse(**change)).encode()), REVISION, now=100)


@pytest.mark.parametrize("raw,ttl", [
    (None, 30), (b"{}", 30), (b"[]", 30), (b"x" * 1025, 30),
    (b"\xff", 30), (b'{"revision":"first","revision":"second"}', 30),
    (json.dumps(pulse()).encode(), -1), (json.dumps(pulse()).encode(), -2),
    (json.dumps(pulse()).encode(), 0), (json.dumps(pulse()).encode(), 31),
    (json.dumps(pulse()).encode(), True),
])
def test_missing_corrupt_unbounded_or_nonexpiring_pulse_is_down(raw, ttl):
    assert not worker_ready(Queue(raw, ttl), REVISION, now=100)


def test_fresh_primitive_pulse_is_ready_and_boundary_expires():
    queue = Queue(json.dumps(pulse()).encode())
    assert worker_ready(queue, REVISION, now=100)
    assert worker_ready(queue, REVISION, now=129.999)
    assert not worker_ready(queue, REVISION, now=130)
    assert not worker_ready(queue, REVISION, now=94.999)


def test_dependency_faults_return_safe_degraded_without_exception_values():
    class Broken:
        def ping(self):
            raise RuntimeError("credential-canary-private-value")
    report = readiness(None, Broken(), REVISION)
    assert report == {"status": "degraded", "revision": REVISION,
                      "checks": {"process": "up", "database": "down", "queue": "down", "worker": "down"},
                      "research_execution": "unconfigured"}
    assert "canary" not in json.dumps(report)
    assert not database_ready(None)


def test_process_liveness_does_not_imply_unconfigured_dependencies_or_execution():
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["research_execution"] == "unconfigured"
        assert response.json()["checks"]["database"] == "down"


@pytest.mark.parametrize("value", ["true", "", "2"])
def test_queue_requirement_must_be_explicit(monkeypatch, value):
    monkeypatch.setenv("DEMANDRIFT_REQUIRE_QUEUE", value)
    with pytest.raises(Exception, match="Queue requirement must be explicit"):
        create_app()


def private_file(tmp_path, name, value):
    path = (tmp_path / name).resolve()
    path.write_text(value + "\n")
    path.chmod(0o600)
    return str(path)


@pytest.mark.parametrize("dependency", ["postgres", "redis"])
def test_actual_silent_dependency_returns_safe_http503_without_retry_or_orphan(dependency):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(2)
    listener.settimeout(5)
    release = threading.Event()
    accepted = []

    def silent_peer():
        with listener.accept()[0] as peer:
            accepted.append(peer)
            release.wait(8)
        listener.settimeout(0.1)
        try:
            another, _ = listener.accept()
        except TimeoutError:
            return
        accepted.append(another)
        another.close()

    thread = threading.Thread(target=silent_peer)
    thread.start()
    port = listener.getsockname()[1]
    database = connection = None
    try:
        if dependency == "postgres":
            database = Database(f"postgresql+psycopg://probe:private-fixture@127.0.0.1:{port}/probe")
        else:
            connection = queue_connection(WorkerSettings(f"redis://127.0.0.1:{port}/0"))
        with TestClient(create_app()) as client:
            client.app.state.auth_service = SimpleNamespace(database=database) if database else None
            client.app.state.runtime_queue = connection
            start = time.monotonic()
            response = client.get("/ready")
            assert 1.5 <= time.monotonic() - start < 4
            assert response.status_code == 503
            assert response.json()["checks"]["database" if database else "queue"] == "down"
            assert "private-fixture" not in response.text
            assert response.headers["cache-control"] == "no-store"
    finally:
        release.set()
        thread.join(timeout=2)
        listener.close()
        if connection is not None:
            connection.close()
        if database is not None:
            database.close()
    assert len(accepted) == 1 and not thread.is_alive()


@pytest.mark.postgres
def test_native_readiness_ignores_busy_application_pool_and_cancels_schema_lock(postgres_database):
    database = postgres_database["app"]
    with database.transaction():
        start = time.monotonic()
        assert database_ready(database)
        assert time.monotonic() - start < 2
    with postgres_database["admin"].transaction() as session:
        session.execute(text("LOCK TABLE public.alembic_version IN ACCESS EXCLUSIVE MODE"))
        start = time.monotonic()
        assert not database_ready(database)
        assert time.monotonic() - start < 2
    assert database_ready(database)
    assert not database_ready(postgres_database["admin"])


@pytest.mark.postgres
def test_native_worker_pulse_and_api_dependency_readiness(postgres_database, tmp_path, monkeypatch):
    broker = os.environ.get("DEMANDRIFT_TEST_REDIS_URL")
    if not broker:
        pytest.fail("Native runtime readiness requires explicit disposable Redis")
    db = postgres_database["app"]
    prefix = "demandrift:readiness-test:" + uuid4().hex + ":"
    key = prefix + "runtime:worker"
    dsn = db.engine.url.render_as_string(hide_password=False)
    database_file = private_file(tmp_path, "app-database", dsn)
    broker_file = private_file(tmp_path, "broker", broker)
    environment = os.environ.copy()
    environment.pop("DATABASE_URL", None)
    environment.pop("DEMANDRIFT_BROKER_URL", None)
    environment.update(APP_ENV="production", APP_REVISION=REVISION,
                       DATABASE_URL_FILE=database_file, DEMANDRIFT_BROKER_URL_FILE=broker_file,
                       DEMANDRIFT_WORKER_KEY_PREFIX=prefix,
                       PYTHONPATH=str(Path(__file__).parents[1]))
    connection = redis.Redis.from_url(broker, socket_timeout=2, socket_connect_timeout=2)
    process = None
    log = tmp_path / "worker.log"
    try:
        assert database_ready(db)
        with log.open("wb") as output:
            process = subprocess.Popen([
                os.sys.executable, "-m", "celery", "-A", "app.runtime_worker:app", "worker",
                "--pool=solo", "--concurrency=1", "--hostname=demandrift-readiness@%h",
                "--without-gossip", "--without-mingle", "--without-heartbeat", "--loglevel=WARNING",
            ], env=environment, cwd=Path(__file__).parents[1], stdout=output, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 15
            while not worker_ready(connection, REVISION, key=key):
                assert process.poll() is None, "Native worker exited before dependency pulse"
                assert time.monotonic() < deadline, "Native worker did not publish a bounded pulse"
                time.sleep(0.1)
            assert readiness(db, connection, REVISION, key=key)["status"] == "ready"
            monkeypatch.setenv("APP_ENV", "production")
            monkeypatch.setenv("APP_REVISION", REVISION)
            monkeypatch.setenv("DEMANDRIFT_REQUIRE_QUEUE", "1")
            monkeypatch.delenv("DEMANDRIFT_BROKER_URL", raising=False)
            monkeypatch.setenv("DEMANDRIFT_BROKER_URL_FILE", broker_file)
            monkeypatch.setenv("DEMANDRIFT_WORKER_KEY_PREFIX", prefix)
            with TestClient(create_app(database=db, auth_policy=AuthPolicy(origins=("http://127.0.0.1:3100",)))) as client:
                response = client.get("/ready")
                assert response.status_code == 200
                assert set(response.json()["checks"].values()) == {"up"}
                assert response.json()["research_execution"] == "unconfigured"
                process.terminate()
                process.wait(timeout=15)
                connection.expire(key, 1)
                time.sleep(1.1)
                response = client.get("/ready")
                assert response.status_code == 503
                assert response.json()["checks"]["worker"] == "down"
                assert response.json()["checks"]["database"] == "up"
                assert response.json()["checks"]["queue"] == "up"
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
        connection.delete(key)
        connection.close()
    assert dsn not in log.read_text()
    assert postgres_database["app"].engine.url.password not in log.read_text()
    assert WORKER_TTL == 30
