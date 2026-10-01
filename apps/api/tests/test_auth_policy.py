"""Request/config bounds do not need a database or provider."""

import asyncio

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.auth_body_guard import AuthBodyGuard
from app.auth_config import AuthPolicy
from app.auth_service import canonical_email, password_text
from app.contracts import AuthCredentials
from app.db.engine import DatabaseConfigurationError
from app.main import create_app


@pytest.mark.parametrize(
    "origin",
    [
        "null",
        "*",
        "http://public.example.invalid",
        "https://site.invalid/path",
        "https://user:pass@site.invalid",
        "https://site.invalid?x=1",
        "https://site.invalid,https://other.invalid",
        " HTTPS://SITE.INVALID",
        "https://site.invalid#fragment",
        "https://site.invalid\\evil",
    ],
)
def test_origin_policy_rejects_ambiguous_or_insecure_values(origin):
    with pytest.raises(ValueError):
        AuthPolicy(origins=(origin,))


def test_backend_cookie_policy_fails_closed_even_for_loopback_origins():
    for origin in ["https://frontend.example.invalid", "http://127.0.0.1:3010"]:
        with pytest.raises(ValueError):
            AuthPolicy(origins=(origin,), cookie_secure=False)
    assert AuthPolicy(
        origins=("http://127.0.0.1:3010",), cookie_same_site="none"
    ).cookie_secure


def test_password_request_is_secret_typed_and_uses_unicode_character_bounds():
    password = "çöğü 🙂 spaces 123456"
    body = AuthCredentials(email="owner@example.invalid", password=password)
    assert password not in repr(body) and password not in body.model_dump_json()
    assert body.password.get_secret_value() == password_text(password)
    for value in ["a" * 14, "a" * 129, 123, [password], {"value": password}]:
        with pytest.raises(ValidationError):
            AuthCredentials(email="owner@example.invalid", password=value)
    assert canonical_email("  OWNER@EXAMPLE.INVALID  ") == "owner@example.invalid"


def test_unconfigured_account_service_is_safe_unavailable_and_production_requires_origins(
    monkeypatch,
):
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/auth/session")
        assert response.status_code == 503
        assert response.json()["code"] == "service_unavailable"
        assert response.headers["cache-control"] == "private, no-store"
        legacy = client.post(
            "/api/v1/research/source-runs/f03", json={"source_ids": ["source-0017"]}
        )
        assert (
            legacy.status_code == 410 and legacy.json()["code"] == "preview_unavailable"
        )
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    with pytest.raises(ValueError):
        create_app()
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://127.0.0.1:3010")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DatabaseConfigurationError), TestClient(create_app()):
        pass


def test_chunked_request_is_bounded_before_parser_hashing_and_root_path_is_supported():
    invoked = []

    async def app(scope, receive, send):
        invoked.append(True)

    events = iter(
        [
            {"type": "http.request", "body": b"a" * 8192, "more_body": True},
            {"type": "http.request", "body": b"b" * 8193, "more_body": False},
        ]
    )
    sent = []

    async def receive():
        return next(events)

    async def send(event):
        sent.append(event)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/demandrift/api/v1/auth/login",
        "root_path": "/demandrift",
        "headers": [(b"content-type", b"application/json")],
    }
    asyncio.run(AuthBodyGuard(app)(scope, receive, send))
    assert not invoked and sent[0]["status"] == 413
    assert b"validation_error" in sent[1]["body"] and b"aaaa" not in sent[1]["body"]


def test_prefix_openapi_and_slash_redirect_preserve_the_backend_root_path(monkeypatch):
    monkeypatch.setenv("API_ROOT_PATH", "/demandrift")
    with TestClient(create_app(), base_url="https://backend.example.invalid") as client:
        schema = client.get("/demandrift/openapi.json").json()
        assert schema["servers"] == [{"url": "/demandrift"}]
        response = client.get("/demandrift/api/v1/projects/", follow_redirects=False)
        assert response.status_code == 307
        assert (
            response.headers["location"]
            == "https://backend.example.invalid/demandrift/api/v1/projects"
        )
