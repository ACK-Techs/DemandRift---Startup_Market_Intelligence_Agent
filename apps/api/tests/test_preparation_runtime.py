"""Actual main.py startup, auth and preparation middleware on restricted PG."""

from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from app.auth_config import AuthPolicy
from app.contracts import IdeaBrief, PreparationMutationReceipt
from app.db.engine import DatabaseConfigurationError
from app.main import create_app

pytestmark = pytest.mark.postgres
ORIGIN = "http://127.0.0.1:3100"
IDEA = "  İstanbul 🙂\n" + "🙂" * 5000


def client_for(database):
    return TestClient(create_app(database=database, auth_policy=AuthPolicy(origins=(ORIGIN,))),
                      base_url="https://runtime.example.invalid")


def test_main_auth_preparation_body_guard_and_durable_replay(postgres_database):
    db = postgres_database
    with client_for(db["app"]) as client:
        registration = client.post("/api/v1/auth/register", headers={"Origin": ORIGIN},
                                   json={"email": "runtime@example.invalid", "password": "isolated runtime fixture"})
        assert registration.status_code == 201
        session = registration.json()
        headers = {"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"]}
        project = client.post("/api/v1/projects", headers=headers, json={"name": "Runtime"})
        assert project.status_code == 201
        base = "/api/v1/projects/" + project.json()["project_id"]
        key = uuid4()
        headers["Idempotency-Key"] = str(key)
        body = {"original_idea": IDEA}
        first = client.post(base + "/research", headers=headers, json=body)
        assert first.status_code == 201  # >16KiB auth guard must not swallow preparation.
        brief = IdeaBrief.model_validate(first.json())
        assert brief.content.original_idea == IDEA and brief.status == "awaiting_user"
        assert client.post(base + "/research", headers=headers, json=body).json() == first.json()
        receipt = client.get(base + f"/preparation-mutations/create_research/{key}")
        assert PreparationMutationReceipt.model_validate(receipt.json()).brief == brief
        assert receipt.headers["cache-control"] == "private, no-store"
        assert len(client.get(base + "/research").json()["items"]) == 1
        malformed = client.post(base + "/research", headers={**headers, "Content-Type": "application/json"},
                                content=b'{"original_idea":"first","original_idea":"second"}')
        assert malformed.status_code == 422 and malformed.headers["cache-control"] == "private, no-store"
        oversized = client.post(base + "/research", headers={**headers, "Content-Type": "application/json"},
                                content=b"x" * 65537)
        assert oversized.status_code == 413 and oversized.headers["cache-control"] == "private, no-store"
        assert client.post(base + "/research", headers={**headers, "Origin": "https://foreign.example"},
                           json={"original_idea": "forbidden"}).status_code == 403
        assert client.post(base + "/research", headers={"Origin": ORIGIN, "Idempotency-Key": str(uuid4())},
                           json={"original_idea": "forbidden"}).status_code == 403


def test_main_rejects_previous_head_before_accepting_sessions(postgres_database):
    db = postgres_database
    with db["admin"].transaction() as session:
        session.execute(text("UPDATE public.alembic_version SET version_num='20261002_0006'"))
    with pytest.raises(DatabaseConfigurationError), client_for(db["app"]):
        pass


def test_main_rejects_receipt_admin_rights_before_serving_http(postgres_database):
    db = postgres_database
    with db["admin"].transaction() as session:
        session.execute(text(f'GRANT UPDATE(input_payload) ON public.preparation_mutations TO "{db["role"]}"'))
    with pytest.raises(DatabaseConfigurationError), client_for(db["app"]):
        pass
