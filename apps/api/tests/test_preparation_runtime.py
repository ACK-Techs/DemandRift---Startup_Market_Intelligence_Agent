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


def test_missing_budget_authority_is_runtime_error_and_foreign_research_remains_hidden(postgres_database, monkeypatch):
    from app.research_runtime import AUTHORIZED_LIMITS
    monkeypatch.delenv("DEMANDRIFT_BUDGET_SUITE_ID", raising=False)
    monkeypatch.delenv("DEMANDRIFT_BUDGET_SUITE_ID_FILE", raising=False)
    with client_for(postgres_database["app"]) as client:
        account = client.post("/api/v1/auth/register", headers={"Origin": ORIGIN},
            json={"email": "budget-missing@example.invalid", "password": "isolated runtime fixture"}).json()
        headers = {"Origin": ORIGIN, "X-CSRF-Token": account["csrf_token"]}
        project = client.post("/api/v1/projects", headers=headers, json={"name": "Missing budget"}).json()
        base = "/api/v1/projects/" + project["project_id"]
        brief = client.post(base + "/research", headers={**headers, "Idempotency-Key": str(uuid4())},
            json={"original_idea": "A shift worker sleep research hypothesis"}).json()
        path = base + "/research/" + brief["research_id"] + "/plans"
        body = {"expected_brief_id": brief["brief_id"], "expected_brief_version": brief["brief_version"],
            "research_mode": "standard", "budget": AUTHORIZED_LIMITS.model_dump(mode="json")}
        result = client.post(path, headers={**headers, "Idempotency-Key": str(uuid4())}, json=body)
        assert result.status_code == 503
        assert result.json()["code"] == "budget_authority_unavailable"
        assert result.json()["message"] == "Authorized persistent budget suite is not configured"
        assert result.headers["cache-control"] == "private, no-store"
        foreign = client.post(f"/api/v1/projects/{uuid4()}/research/{brief['research_id']}/plans",
            headers={**headers, "Idempotency-Key": str(uuid4())}, json=body)
        assert foreign.status_code == 404 and foreign.json()["code"] == "not_found"
    with postgres_database["admin"].transaction() as session:
        assert session.execute(text("SELECT count(*) FROM public.budget_suites")).scalar_one() == 0
        assert session.execute(text("SELECT count(*) FROM public.research_plans")).scalar_one() == 0
