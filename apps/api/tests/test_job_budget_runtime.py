"""Accepted head008 startup rejects reachable private helpers and binding writes."""

from uuid import uuid4

from alembic import command
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from app.auth_config import AuthPolicy
from app.db.engine import DatabaseConfigurationError
from app.db.migration_head import REQUIRED_MIGRATION
from app.main import create_app

pytestmark = pytest.mark.postgres
HELPERS = [
    "public.demandrift_job_budget_guard()",
    "public.demandrift_job_budget_current(uuid,uuid,uuid,jsonb)",
    "public.demandrift_job_budget_receipt(public.budget_attempts,boolean)",
]


def test_head008_startup_accepts_restricted_role_and_rejects_previous_head(postgres_database):
    db = postgres_database
    assert REQUIRED_MIGRATION == "20261002_0008"
    policy = AuthPolicy(origins=("http://127.0.0.1:3100",))
    with TestClient(create_app(database=db["app"], auth_policy=policy)) as client:
        assert client.get("/api/v1/auth/session").status_code == 401
    command.downgrade(db["config"], "20261002_0007")
    with pytest.raises(DatabaseConfigurationError):
        with TestClient(create_app(database=db["app"], auth_policy=policy)):
            pytest.fail("Previous schema must not serve authenticated traffic")
    command.upgrade(db["config"], REQUIRED_MIGRATION)
    db["app"].assert_application_role()


@pytest.mark.parametrize("signature", HELPERS)
@pytest.mark.parametrize("grantee", ["application", "public", "settable_group"])
def test_private_helper_execute_misgrant_rejects_startup(postgres_database, signature, grantee):
    db = postgres_database
    quote = db["admin"].engine.dialect.identifier_preparer.quote
    group = "demandrift_runtime_" + uuid4().hex[:12]
    target = "PUBLIC" if grantee == "public" else quote(group if grantee == "settable_group" else db["role"])
    with db["admin"].transaction() as session:
        if grantee == "settable_group":
            session.execute(text(f"CREATE ROLE {quote(group)} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"))
            session.execute(text(f"GRANT {quote(group)} TO {quote(db['role'])} WITH INHERIT FALSE, SET TRUE"))
        session.execute(text(f"GRANT EXECUTE ON FUNCTION {signature} TO {target}"))
    try:
        with pytest.raises(DatabaseConfigurationError):
            db["app"].assert_application_role()
    finally:
        with db["admin"].transaction() as session:
            session.execute(text(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {target}"))
            if grantee == "settable_group":
                session.execute(text(f"REVOKE {quote(group)} FROM {quote(db['role'])}"))
                session.execute(text(f"DROP ROLE {quote(group)}"))
    db["app"].assert_application_role()


@pytest.mark.parametrize("column", ["admission_kind", "brief_id", "job_fence", "dispatch_deadline_at", "model_timeout_ms"])
def test_reachable_binding_column_write_rejects_startup(postgres_database, column):
    db = postgres_database
    quote = db["admin"].engine.dialect.identifier_preparer.quote
    group = "demandrift_binding_" + uuid4().hex[:12]
    with db["admin"].transaction() as session:
        session.execute(text(f"CREATE ROLE {quote(group)} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"))
        session.execute(text(f"GRANT UPDATE({quote(column)}) ON public.budget_attempts TO {quote(group)}"))
        session.execute(text(f"GRANT {quote(group)} TO {quote(db['role'])} WITH INHERIT FALSE, SET TRUE"))
    try:
        with pytest.raises(DatabaseConfigurationError):
            db["app"].assert_application_role()
    finally:
        with db["admin"].transaction() as session:
            session.execute(text(f"REVOKE {quote(group)} FROM {quote(db['role'])}"))
            session.execute(text(f"REVOKE UPDATE({quote(column)}) ON public.budget_attempts FROM {quote(group)}"))
            session.execute(text(f"DROP ROLE {quote(group)}"))
    db["app"].assert_application_role()
