"""Dependency readiness is distinct from process liveness and pipeline capability."""

import json
import math
import os
import re
import time
from uuid import UUID

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry
from sqlalchemy import text

from app.db.engine import Database
from app.db.migration_head import REQUIRED_MIGRATION
from app.runtime_secrets import runtime_secret
from app.worker_config import WorkerSettings

WORKER_KEY = "demandrift:runtime:worker"
WORKER_TTL = 30


def database_ready(database: Database | None) -> bool:
    probe = None
    try:
        if database is None:
            return False
        probe = database.readiness_probe()
        probe.assert_application_role()
        with probe.transaction() as session:
            return session.execute(text(
                "SELECT version_num FROM public.alembic_version"
            )).scalar_one() == REQUIRED_MIGRATION
    except Exception:
        return False
    finally:
        if probe is not None:
            probe.close()


def queue_connection(settings: WorkerSettings):
    return redis.Redis.from_url(settings.broker_url, socket_timeout=2,
                                socket_connect_timeout=2, max_connections=2,
                                retry=Retry(NoBackoff(), 0), retry_on_timeout=False,
                                retry_on_error=[], lib_name=None, lib_version=None)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def _valid_worker_pulse(ttl, raw, revision: str, *, now=None) -> bool:
    try:
        if type(ttl) is not int or not 0 < ttl <= WORKER_TTL:
            return False
        if type(raw) is not bytes or not 1 <= len(raw) <= 1024:
            return False
        pulse = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_object)
        if type(pulse) is not dict or set(pulse) != {
            "revision", "instance", "pid", "reported_at", "database_ready"
        }:
            return False
        if pulse["revision"] != revision or pulse["database_ready"] is not True:
            return False
        if type(pulse["pid"]) is not int or not 1 <= pulse["pid"] <= 2**31 - 1:
            return False
        if type(pulse["instance"]) is not str or str(UUID(pulse["instance"])) != pulse["instance"]:
            return False
        stamp = pulse["reported_at"]
        if type(stamp) not in (int, float) or not math.isfinite(stamp):
            return False
        age = (time.time() if now is None else now) - stamp
        return -5 <= age < WORKER_TTL
    except Exception:
        return False


def worker_ready(connection, revision: str, *, now=None, key=WORKER_KEY) -> bool:
    try:
        with connection.pipeline(transaction=False) as pipeline:
            result = pipeline.ttl(key).get(key).execute()
        if type(result) is not list or len(result) != 2:
            return False
        return _valid_worker_pulse(*result, revision, now=now)
    except Exception:
        return False


def publish_worker_pulse(connection, database, revision: str, instance: str, *, key=WORKER_KEY):
    if not re.fullmatch(r"(?:[0-9a-f]{40}|development)", revision):
        raise ValueError("Explicit application revision required")
    if type(instance) is not str or str(UUID(instance)) != instance:
        raise ValueError("Canonical worker instance required")
    pulse = {"revision": revision, "instance": instance, "pid": os.getpid(),
             "reported_at": time.time(), "database_ready": database_ready(database)}
    connection.set(key, json.dumps(pulse, separators=(",", ":")), ex=WORKER_TTL)


def readiness(database, connection, revision: str, *, key=WORKER_KEY):
    checks = {"process": "up", "database": "down", "queue": "down", "worker": "down"}
    checks["database"] = "up" if database_ready(database) else "down"
    try:
        if connection is None:
            raise ValueError()
        # One round trip, no retries or ancillary CLIENT commands; a broken
        # dependency cannot turn three bounded reads into repeated reconnects.
        with connection.pipeline(transaction=False) as pipeline:
            result = pipeline.ping().ttl(key).get(key).execute()
        if type(result) is list and len(result) == 3 and result[0] is True:
            checks["queue"] = "up"
            checks["worker"] = "up" if _valid_worker_pulse(*result[1:], revision) else "down"
    except Exception:
        pass
    return {"status": "ready" if all(v == "up" for v in checks.values()) else "degraded",
            "revision": revision, "checks": checks, "research_execution": "unconfigured"}


def configured_readiness():
    database = connection = None
    try:
        database = Database(runtime_secret("DATABASE_URL", allow_environment=False))
        settings = WorkerSettings.from_environment()
        connection = queue_connection(settings)
        return readiness(database, connection, os.environ.get("APP_REVISION", "development"),
                         key=settings.key_prefix + "runtime:worker")
    finally:
        if connection is not None:
            connection.close()
        if database is not None:
            database.close()


if __name__ == "__main__":
    try:
        report = configured_readiness()
        raise SystemExit(0 if report["status"] == "ready" else 1)
    except Exception:
        raise SystemExit(1) from None
