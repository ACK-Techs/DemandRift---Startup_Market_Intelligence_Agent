"""Actual runtime file hazards and production fixture route isolation."""

import os
import pytest

from app.auth_config import AuthPolicy
from app.main import create_app
from app.runtime_secrets import RuntimeSecretError, runtime_secret
from app.worker_config import WorkerSettings

PRIVATE = "synthetic-private-runtime-only"


@pytest.fixture(autouse=True)
def no_credentials(monkeypatch):
    for name in ("DATABASE_URL", "DEMANDRIFT_BROKER_URL", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name + "_FILE", raising=False)


def secret_file(tmp_path, monkeypatch, raw=PRIVATE.encode()):
    path = (tmp_path / "credential").resolve()
    path.write_bytes(raw)
    path.chmod(0o600)
    monkeypatch.setenv("GEMINI_API_KEY_FILE", str(path))
    return path


@pytest.mark.parametrize("raw", [PRIVATE.encode(), (PRIVATE + "\n").encode()])
@pytest.mark.parametrize("mode", [0o400, 0o600])
def test_private_regular_files_accept_only_one_optional_terminal_lf(tmp_path, monkeypatch, raw, mode):
    path = secret_file(tmp_path, monkeypatch, raw)
    path.chmod(mode)
    assert runtime_secret("GEMINI_API_KEY", allow_environment=False) == PRIVATE


@pytest.mark.parametrize("raw", [b"", b"\n", b"x\n\n", b"x\r\n", b"a b", b"x\x00", b"x\t", b"\xff", b"x" * 4097])
def test_invalid_file_values_fail_without_exposing_value_or_path(tmp_path, monkeypatch, raw):
    path = secret_file(tmp_path, monkeypatch, raw)
    with pytest.raises(RuntimeSecretError) as error:
        runtime_secret("GEMINI_API_KEY")
    assert str(path) not in str(error.value) and PRIVATE not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o660, 0o700, 0o4600])
def test_unsafe_permissions_are_not_runtime_secrets(tmp_path, monkeypatch, mode):
    path = secret_file(tmp_path, monkeypatch)
    path.chmod(mode)
    with pytest.raises(RuntimeSecretError):
        runtime_secret("GEMINI_API_KEY")


@pytest.mark.parametrize("kind", ["leaf_symlink", "parent_symlink", "hardlink", "directory", "fifo", "missing"])
def test_file_hazards_never_become_credentials(tmp_path, monkeypatch, kind):
    path = secret_file(tmp_path, monkeypatch)
    target = tmp_path / "hazard"
    if kind == "leaf_symlink":
        target.symlink_to(path)
    elif kind == "parent_symlink":
        directory = tmp_path / "alias"
        directory.symlink_to(tmp_path.resolve(), target_is_directory=True)
        target = directory / path.name
    elif kind == "hardlink":
        os.link(path, target)
    elif kind == "directory":
        target.mkdir(mode=0o700)
    elif kind == "fifo":
        os.mkfifo(target, 0o600)
    monkeypatch.setenv("GEMINI_API_KEY_FILE", str(target))
    with pytest.raises(RuntimeSecretError):
        runtime_secret("GEMINI_API_KEY")


def test_ambiguous_sources_do_not_read_or_choose_a_credential(tmp_path, monkeypatch):
    secret_file(tmp_path, monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "different-private-value")
    monkeypatch.setattr(os, "open", lambda *args: pytest.fail("Ambiguous sources must be denied before read"))
    with pytest.raises(RuntimeSecretError):
        runtime_secret("GEMINI_API_KEY")


def test_production_requires_private_file_and_never_falls_back_to_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", PRIVATE)
    assert runtime_secret("GEMINI_API_KEY") == PRIVATE
    with pytest.raises(RuntimeSecretError):
        runtime_secret("GEMINI_API_KEY", allow_environment=False)


def test_in_place_file_change_during_read_is_rejected(tmp_path, monkeypatch):
    path = secret_file(tmp_path, monkeypatch)
    read = os.read
    def changed(fd, size):
        result = read(fd, size)
        path.write_bytes(b"changed-private-value")
        return result
    monkeypatch.setattr(os, "read", changed)
    with pytest.raises(RuntimeSecretError):
        runtime_secret("GEMINI_API_KEY")


def test_worker_production_reads_only_private_broker_file(tmp_path, monkeypatch):
    path = (tmp_path / "broker").resolve()
    path.write_text("redis://:synthetic-private@redis:6379/0\n")
    path.chmod(0o600)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEMANDRIFT_BROKER_URL_FILE", str(path))
    settings = WorkerSettings.from_environment()
    assert settings.broker_url == "redis://:synthetic-private@redis:6379/0"
    assert "synthetic-private" not in repr(settings)
    monkeypatch.setenv("DEMANDRIFT_BROKER_URL", "redis://other:6379/0")
    with pytest.raises(ValueError, match="Explicit worker broker"):
        WorkerSettings.from_environment()


def test_offline_fixture_routes_are_absent_from_every_database_backed_app(monkeypatch):
    policy = AuthPolicy(origins=("http://127.0.0.1:3100",))
    expected_removed = {path for path in create_app().openapi()["paths"] if path.startswith("/api/v1/research")}
    assert len(expected_removed) >= 5
    for environment, database in [("production", None), ("development", object())]:
        monkeypatch.setenv("APP_ENV", environment)
        paths = set(create_app(database=database, auth_policy=policy).openapi()["paths"])
        assert paths.isdisjoint(expected_removed)
        assert "/api/v1/auth/session" in paths and "/api/v1/projects" in paths


def test_file_path_must_be_absolute_and_canonical(tmp_path, monkeypatch):
    path = secret_file(tmp_path, monkeypatch)
    for value in ["credential", str(path.parent / ".." / path.parent.name / path.name)]:
        monkeypatch.setenv("GEMINI_API_KEY_FILE", value)
        with pytest.raises(RuntimeSecretError):
            runtime_secret("GEMINI_API_KEY")


@pytest.mark.postgres
def test_actual_production_private_dsn_serves_scoped_auth_only(postgres_database, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    db = postgres_database
    path = (tmp_path / "database-url").resolve()
    path.write_text(db["app"].engine.url.render_as_string(hide_password=False))
    path.chmod(0o600)
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.setenv("DATABASE_URL_FILE", str(path))
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://127.0.0.1:3100")
    application = create_app()
    with TestClient(application, base_url="https://native-runtime.invalid") as client:
        assert client.get("/api/v1/auth/session").status_code == 401
        assert client.get("/api/v1/research/initial-runs").status_code == 404
        assert client.get("/api/v1/projects").status_code == 401
        response = client.post("/api/v1/auth/register",
            headers={"Origin": "http://127.0.0.1:3100"},
            json={"email": "private-runtime@example.invalid", "password": "synthetic private runtime password"})
        assert response.status_code == 201 and "csrf_token" in response.json()
        assert client.get("/api/v1/projects").status_code == 200
    assert application.state.auth_service is None
