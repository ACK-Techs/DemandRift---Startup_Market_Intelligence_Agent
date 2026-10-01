"""Actual account HTTP boundaries and persistent throttling on isolated PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import base64
import json
import threading
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select, text, update

from app.auth_config import AuthPolicy
from app.auth_service import AuthService, AuthRateLimited, AuthenticationError, digest
from app.db.auth_models import AUTH_RATE_LIMITS
from app.db.engine import Database, DatabaseConfigurationError
from app.db.models import SessionRecord, UserRecord
from app.main import create_app

pytestmark = pytest.mark.postgres
ORIGIN = "http://127.0.0.1:3010"
PASSWORD = "synthetic password for fixture only"


@contextmanager
def client_for(db, **options):
    policy = AuthPolicy(origins=(ORIGIN,), **options)
    with TestClient(
        create_app(database=db["app"], auth_policy=policy),
        base_url="https://backend.example.invalid",
    ) as client:
        yield client


def register(client, email="owner@example.invalid"):
    response = client.post(
        "/api/v1/auth/register",
        headers={"Origin": ORIGIN},
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 201
    return response.json()


def mutation_headers(session):
    return {"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"]}


def test_registration_session_project_and_hash_only_storage(postgres_database):
    db = postgres_database
    with client_for(db) as client:
        session = register(client, "  OWNER@EXAMPLE.INVALID  ")
        token = client.cookies.get("demandrift_session")
        cookie = next(c for c in client.cookies.jar if c.name == "demandrift_session")
        assert cookie.secure and cookie.path == "/" and "HttpOnly" in cookie._rest
        assert cookie._rest["SameSite"] == "lax"
        assert session["user"]["email"] == "owner@example.invalid"
        assert token not in str(session) and PASSWORD not in str(session)
        assert client.get("/api/v1/auth/session").json() == session
        response = client.post(
            "/api/v1/projects",
            headers=mutation_headers(session),
            json={"name": "Alpha"},
        )
        assert (
            response.status_code == 201
            and response.json()["user_id"] == session["user"]["user_id"]
        )
        detail = client.get("/api/v1/projects/" + response.json()["project_id"])
        assert detail.json() == response.json()
        assert (
            detail.headers["cache-control"]
            == response.headers["cache-control"]
            == "private, no-store"
        )
        assert client.get("/api/v1/projects").json()["items"] == [response.json()]
        with db["admin"].transaction() as sql:
            stored = sql.scalar(select(SessionRecord))
            owner = sql.scalar(select(UserRecord))
            assert stored.session_hash == digest(token) and stored.csrf_hash == digest(
                session["csrf_token"]
            )
            assert owner.password_hash.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
            assert PASSWORD not in owner.password_hash


def test_rotation_revokes_old_session_old_csrf_and_logout_persists(postgres_database):
    with client_for(postgres_database) as client:
        before = register(client)
        old = client.cookies.get("demandrift_session")
        response = client.post(
            "/api/v1/auth/login",
            headers={"Origin": ORIGIN},
            json={"email": before["user"]["email"], "password": PASSWORD},
        )
        assert response.status_code == 200
        after = response.json()
        assert client.cookies.get("demandrift_session") != old
        assert (
            client.post(
                "/api/v1/projects",
                headers=mutation_headers(before),
                json={"name": "Denied"},
            ).status_code
            == 403
        )
        service = client.app.state.auth_service
        with pytest.raises(AuthenticationError):
            service.resolve(old)
        assert (
            client.post(
                "/api/v1/auth/logout", headers=mutation_headers(after)
            ).status_code
            == 204
        )
        assert client.get("/api/v1/auth/session").status_code == 401
        assert client.cookies.get("demandrift_session") is None


def test_foreign_owner_project_detail_list_cursor_and_body_claims_are_rejected(
    postgres_database,
):
    with client_for(postgres_database) as a, client_for(postgres_database) as b:
        owner = register(a)
        other = register(b, "other@example.invalid")
        projects = [
            a.post(
                "/api/v1/projects",
                headers=mutation_headers(owner),
                json={"name": f"Alpha {i}"},
            ).json()
            for i in range(3)
        ]
        first = a.get("/api/v1/projects?limit=1").json()
        assert len(first["items"]) == 1 and first["page"]["next_cursor"]
        second = a.get(
            "/api/v1/projects",
            params={"limit": 1, "cursor": first["page"]["next_cursor"]},
        ).json()
        assert first["items"][0]["project_id"] != second["items"][0]["project_id"]
        assert b.get("/api/v1/projects").json()["items"] == []
        foreign = b.get("/api/v1/projects/" + projects[0]["project_id"])
        missing = b.get("/api/v1/projects/" + str(uuid4()))
        assert foreign.status_code == missing.status_code == 404
        assert foreign.json()["code"] == missing.json()["code"] == "not_found"
        assert foreign.json()["message"] == missing.json()["message"]
        assert (
            b.get(
                "/api/v1/projects", params={"cursor": first["page"]["next_cursor"]}
            ).status_code
            == 422
        )
        assert (
            b.post(
                "/api/v1/projects",
                headers=mutation_headers(other),
                json={"name": "Injected", "user_id": owner["user"]["user_id"]},
            ).status_code
            == 422
        )
        assert (
            b.post(
                "/api/v1/projects",
                headers=mutation_headers(owner),
                json={"name": "Denied"},
            ).status_code
            == 403
        )


@pytest.mark.parametrize("field", ["u", "i"])
@pytest.mark.parametrize(
    "value", [42, True, [], {}], ids=["integer", "boolean", "array", "object"]
)
def test_structured_cursor_fields_return_private_canonical_error(
    postgres_database, field, value
):
    with client_for(postgres_database) as client:
        session = register(client)
        project = client.post(
            "/api/v1/projects",
            headers=mutation_headers(session),
            json={"name": "Private cursor regression"},
        ).json()
        fields = {
            "u": session["user"]["user_id"],
            "t": project["created_at"],
            "i": project["project_id"],
        }
        fields[field] = value
        cursor = (
            base64.urlsafe_b64encode(
                json.dumps(fields, separators=(",", ":")).encode("utf-8")
            )
            .decode("ascii")
            .rstrip("=")
        )
        response = client.get("/api/v1/projects", params={"cursor": cursor})
        assert response.status_code == 422
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["content-type"] == "application/json"
        error = response.json()
        assert error["code"] == "validation_error"
        assert error["message"] == "Invalid page cursor"
        assert error["retryable"] is False
        assert session["user"]["user_id"] not in response.text
        assert project["project_id"] not in response.text
        assert project["name"] not in response.text
        assert client.get("/api/v1/projects").json()["items"] == [project]


def test_expired_revoked_unknown_and_duplicate_cookies_are_uniformly_denied(
    postgres_database,
):
    with client_for(postgres_database) as client:
        register(client)
        token = client.cookies.get("demandrift_session")
        with postgres_database["admin"].transaction() as sql:
            now = datetime.now(timezone.utc)
            sql.execute(
                update(SessionRecord)
                .where(SessionRecord.session_hash == digest(token))
                .values(
                    created_at=now - timedelta(seconds=3),
                    expires_at=now - timedelta(seconds=1),
                )
            )
        responses = [client.get("/api/v1/auth/session")]
        client.cookies.clear()
        for value in ["x" * 43, "invalid", "", token + "; demandrift_session=" + token]:
            responses.append(
                client.get(
                    "/api/v1/auth/session",
                    headers={"Cookie": "demandrift_session=" + value},
                )
            )
        assert all(
            r.status_code == 401 and r.json()["code"] == "authentication_required"
            for r in responses
        )
        assert all(r.headers["cache-control"] == "private, no-store" for r in responses)


def test_missing_wrong_multiple_origin_and_csrf_values_do_not_create_records(
    postgres_database,
):
    with client_for(postgres_database) as client:
        session = register(client)
        variants = [
            {},
            {"Origin": "null"},
            {"Origin": ORIGIN + "/"},
            {"Origin": "https://attacker.invalid"},
            {"Origin": ORIGIN + "," + ORIGIN},
            [("Origin", ORIGIN), ("Origin", ORIGIN)],
            [
                ("Origin", ORIGIN),
                ("X-CSRF-Token", session["csrf_token"]),
                ("X-CSRF-Token", session["csrf_token"]),
            ],
        ]
        for headers in variants:
            assert (
                client.post(
                    "/api/v1/projects", headers=headers, json={"name": "Denied"}
                ).status_code
                == 403
            )
        assert client.get("/api/v1/projects").json()["items"] == []


def test_cors_preflight_is_exact_with_credentials_and_never_allows_wildcard(
    postgres_database,
):
    with client_for(postgres_database) as client:
        headers = {
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrf-token",
        }
        response = client.options("/api/v1/projects", headers=headers)
        assert (
            response.status_code == 200
            and response.headers["access-control-allow-origin"] == ORIGIN
        )
        assert response.headers["access-control-allow-credentials"] == "true"
        assert "Origin" in response.headers["vary"]
        response = client.options(
            "/api/v1/projects",
            headers={**headers, "Origin": "https://attacker.invalid"},
        )
        assert (
            response.status_code == 400
            and "access-control-allow-origin" not in response.headers
        )


def test_invalid_secret_input_and_database_outage_errors_are_redacted(
    postgres_database,
):
    with client_for(postgres_database) as client:
        submitted = "private credential that must never echo"
        response = client.post(
            "/api/v1/auth/login",
            headers={"Origin": ORIGIN},
            json={"email": "invalid", "password": submitted, "user_id": str(uuid4())},
        )
        assert (
            response.status_code == 422
            and submitted not in response.text
            and "input" not in response.text
        )
        assert (
            client.post(
                "/api/v1/auth/login",
                headers={"Origin": ORIGIN},
                data={"email": submitted},
            ).status_code
            == 415
        )
        assert (
            client.post(
                "/api/v1/auth/login",
                headers={"Origin": ORIGIN, "Content-Type": "application/json"},
                content=b"x" * 16385,
            ).status_code
            == 413
        )
        with postgres_database["admin"].engine.begin() as sql:
            sql.execute(
                text("ALTER TABLE public.users RENAME TO users_temporarily_unavailable")
            )
        try:
            response = client.post(
                "/api/v1/auth/login",
                headers={"Origin": ORIGIN},
                json={"email": "owner@example.invalid", "password": submitted},
            )
            assert (
                response.status_code == 503
                and "users" not in response.text
                and submitted not in response.text
            )
        finally:
            with postgres_database["admin"].engine.begin() as sql:
                sql.execute(
                    text(
                        "ALTER TABLE public.users_temporarily_unavailable RENAME TO users"
                    )
                )


def test_shared_account_rate_limit_has_no_concurrent_or_restart_bypass(
    postgres_database,
):
    policy = AuthPolicy(origins=(ORIGIN,), account_attempts=3, peer_attempts=20)
    # Separate service objects simulate API replicas; the database owns the counters.
    concurrent_database = Database(
        postgres_database["app"].engine.url.render_as_string(hide_password=False),
        pool_size=6,
    )
    concurrent_database.assert_application_role()
    services = [AuthService(concurrent_database, policy) for _ in range(2)]
    barrier = threading.Barrier(6)

    def attempt(index):
        barrier.wait()
        try:
            services[index % 2].rate_limit(
                "login", "owner@example.invalid", "peer" + str(index)
            )
            return "allowed"
        except AuthRateLimited:
            return "denied"

    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            outcomes = list(pool.map(attempt, range(6)))
    finally:
        concurrent_database.close()
    assert outcomes.count("allowed") == 3 and outcomes.count("denied") == 3
    restarted = AuthService(postgres_database["app"], policy)
    with pytest.raises(AuthRateLimited):
        restarted.rate_limit("register", "owner@example.invalid", "newpeer")
    with postgres_database["admin"].transaction() as sql:
        sql.execute(
            update(AUTH_RATE_LIMITS)
            .where(
                AUTH_RATE_LIMITS.c.rate_key == digest("account:owner@example.invalid")
            )
            .values(
                window_started_at=datetime.now(timezone.utc) - timedelta(seconds=601)
            )
        )
    restarted.rate_limit("login", "owner@example.invalid", "newpeer2")
    with postgres_database["admin"].transaction() as sql:
        assert (
            sql.scalar(
                select(AUTH_RATE_LIMITS.c.attempts).where(
                    AUTH_RATE_LIMITS.c.rate_key
                    == digest("account:owner@example.invalid")
                )
            )
            == 1
        )


def test_untrusted_forwarded_ip_headers_do_not_bypass_peer_limit(postgres_database):
    with client_for(postgres_database, peer_attempts=2) as client:
        statuses = []
        for i in range(3):
            response = client.post(
                "/api/v1/auth/login",
                headers={
                    "Origin": ORIGIN,
                    "X-Forwarded-For": f"192.0.2.{i + 1}",
                    "Forwarded": f"for=192.0.2.{i + 1}",
                },
                json={"email": f"unknown{i}@example.invalid", "password": PASSWORD},
            )
            statuses.append(response.status_code)
        assert statuses == [401, 401, 429]


def test_hash_capacity_returns_safe_retry_without_exposing_credentials(
    postgres_database,
):
    with client_for(postgres_database) as client:
        register(client)
        service = client.app.state.auth_service
        with service._hash_capacity(), service._hash_capacity():
            response = client.post(
                "/api/v1/auth/login",
                headers={"Origin": ORIGIN},
                json={"email": "owner@example.invalid", "password": PASSWORD},
            )
        assert response.status_code == 429 and response.headers["retry-after"] == "1"
        assert response.json()["retryable"] is True and PASSWORD not in response.text
        assert client.get("/api/v1/auth/session").status_code == 200


def test_startup_rejects_administrator_and_least_privilege_throttle_has_no_delete(
    postgres_database,
):
    with (
        pytest.raises(DatabaseConfigurationError),
        TestClient(
            create_app(
                database=postgres_database["admin"],
                auth_policy=AuthPolicy(origins=(ORIGIN,)),
            )
        ),
    ):
        pass
    with postgres_database["app"].transaction() as sql:
        privileges = sql.execute(
            text(
                "SELECT has_table_privilege(current_user,'public.auth_rate_limits','SELECT'),"
                "has_table_privilege(current_user,'public.auth_rate_limits','INSERT'),"
                "has_table_privilege(current_user,'public.auth_rate_limits','UPDATE'),"
                "has_table_privilege(current_user,'public.auth_rate_limits','DELETE'),"
                "has_table_privilege(current_user,'public.auth_rate_limits','TRUNCATE')"
            )
        ).one()
        assert privileges == (True, True, True, False, False)
