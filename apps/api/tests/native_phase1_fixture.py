"""Test-only current-head producer adapter. All authority comes from real receipts.

Synthetic administrator publication exists only in disposable native test DBs.
No production function, privilege, trigger, runtime flag or golden file changes.
"""

from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4
from sqlalchemy import select, text
from app import contracts as wire
from app.budget_contract import BudgetCapacity, ResourceAmount
from app.db import budget_models, phase1_models
from app.db.budget_repository import BudgetRepository
from app.db.phase1_repository import Phase1Repository, Phase1Conflict
from app.db.preparation_repository import (
    RecordNotFound,
    StalePlanError,
    plan_fingerprint,
)
from app.phase1_confirmation import validated
from app.preparation_http_contracts import HUMAN_FIELDS
from app.source_registry import get_registry


def current_head(database):
    with database.transaction() as session:
        return session.scalar(text("SELECT version_num FROM public.alembic_version"))


def _disposable(db):
    if not db.get("name", "").startswith("demandrift_") or "admin" not in db:
        raise ValueError("Explicit disposable native fixture required")


def full_budget():
    from test_budget_contract import approved_limits

    return approved_limits()


def wire_capacity(account):
    ceiling = ResourceAmount.from_json(account["ceiling"])
    return wire.BudgetLimits(
        max_requests=ceiling.requests,
        max_bytes=ceiling.bytes,
        max_pages=ceiling.pages,
        max_records=ceiling.records,
        max_tokens=ceiling.tokens,
        max_duration_seconds=account["duration_seconds"],
        max_concurrency=account["concurrency"],
        max_cost_usd=ceiling.cost_usd,
        soft_cost_usd=ResourceAmount(
            cost_picousd=account["soft_cost_picousd"]
        ).cost_usd,
    )


def budget_for_research(db, user_id, project_id, research_id):
    with db["app"].transaction(user_id) as session:
        row = (
            session.execute(
                select(budget_models.accounts).where(
                    budget_models.accounts.c.user_id == user_id,
                    budget_models.accounts.c.project_id == project_id,
                    budget_models.accounts.c.research_id == research_id,
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise RecordNotFound("Fixture account not found")
    return BudgetRepository(
        db["app"], row["suite_id"], user_id, project_id, research_id
    )


def ensure_account(db, repo, research_id, budget=None):
    _disposable(db)
    try:
        return budget_for_research(db, repo.user_id, repo.project_id, research_id)
    except RecordNotFound:
        pass
    capacity = BudgetCapacity.from_wire(budget or full_budget())
    suite = uuid4()
    with db["admin"].transaction() as session:
        session.execute(
            budget_models.suites.insert().values(
                suite_id=suite,
                ceiling=capacity.ceiling.to_json(),
                soft_cost_picousd=capacity.soft_cost_picousd,
                duration_seconds=capacity.duration_seconds,
                concurrency=capacity.concurrency,
                spent=ResourceAmount().to_json(),
                held=ResourceAmount().to_json(),
            )
        )
    ledger = BudgetRepository(
        db["app"], suite, repo.user_id, repo.project_id, research_id
    )
    ledger.create_account(capacity)
    return ledger


def publish_qualification(db, sources):
    """Canonical synthetic templates with exact packaged registry metadata.

    Synthetic graph source IDs may deliberately be outside the packaged registry;
    this publication proves native graph controls, not loader/connector permission.
    """
    _disposable(db)
    templates = [
        wire.SourcePlanItem.model_validate(
            source.model_dump(mode="json")
            if isinstance(source, wire.SourcePlanItem)
            else source
        ).model_dump(mode="json")
        for source in sources
    ]
    if not templates:
        raise ValueError("Synthetic qualification requires sources")
    registry = get_registry()
    now = datetime.now(timezone.utc)
    with db["admin"].transaction() as session:
        current = (
            session.execute(
                select(phase1_models.qualifications).join(
                    phase1_models.qualification_current,
                    (
                        phase1_models.qualifications.c.qualification_version
                        == phase1_models.qualification_current.c.qualification_version
                    )
                    & (
                        phase1_models.qualifications.c.qualification_digest
                        == phase1_models.qualification_current.c.qualification_digest
                    ),
                )
            )
            .mappings()
            .one_or_none()
        )
        merged = (
            {s["source_id"]: s for s in current["payload"]["sources"]}
            if current
            else {}
        )
        merged.update({s["source_id"]: s for s in templates})
        payload = dict(
            sources=[merged[k] for k in sorted(merged)],
            registry_version=registry.registry_version,
            registry_digest=registry.content_digest,
            grant_digest="e" * 64,
        )
        if (
            current
            and current["payload"] == payload
            and current["revoked_at"] is None
            and current["expires_at"] > now
        ):
            return (
                current["qualification_version"] + ":" + current["qualification_digest"]
            )
        digest = session.scalar(
            text(
                "SELECT encode(sha256(convert_to(CAST(:p AS jsonb)::text,'UTF8')),'hex')"
            ),
            dict(p=json.dumps(payload)),
        )
        version = "synthetic-" + uuid4().hex[:24]
        session.execute(
            phase1_models.qualifications.insert().values(
                qualification_version=version,
                qualification_digest=digest,
                payload=payload,
                reviewed_at=now,
                valid_from=now,
                expires_at=now + timedelta(hours=1),
            )
        )
        session.execute(phase1_models.qualification_current.delete())
        session.execute(
            phase1_models.qualification_current.insert().values(
                slot=1, qualification_version=version, qualification_digest=digest
            )
        )
        return version + ":" + digest


class NativePhase1Fixture(Phase1Repository):
    """Legacy-shaped test methods using actual current-head human events."""

    def __init__(self, db, user_id, project_id):
        _disposable(db)
        self.fixture_db = db
        super().__init__(db["app"], user_id, project_id)

    def create_research(self, original_idea):
        receipt, _ = self.create_preparation(
            uuid4(), wire.ResearchCreate(original_idea=original_idea)
        )
        return receipt.research_id

    def append_brief(self, research_id, content, *, status="awaiting_user"):
        content = validated(wire.BriefContent, content)
        fields = [getattr(content, name) for name in HUMAN_FIELDS] + list(
            content.constraints.values()
        )
        if content.category_origin in ("ai_inferred", "ai_hypothesis") or any(
            field.origin in ("ai_inferred", "ai_hypothesis") for field in fields
        ):
            raise ValueError(
                "Model hypotheses require an explicit immutable analysis fixture"
            )
        current = self.latest_brief(research_id)
        if content.original_idea != current.content.original_idea:
            raise ValueError("Original idea must remain exact")
        if status not in ("awaiting_user", "confirmed"):
            raise ValueError("Explicit fixture human event required")
        patch = dict(
            expected_brief_version=current.brief_version,
            **{name: getattr(content, name).value for name in HUMAN_FIELDS},
            constraints={
                name: field.value for name, field in content.constraints.items()
            },
            language_scope=content.language_scope,
            primary_category=content.primary_category,
            modifiers=content.modifiers,
            skipped_clarification=content.skipped_clarification,
            continue_with_unknowns=content.continue_with_unknowns
            or content.clarity_status == "broad_but_continue",
        )
        revision, _ = self.revise(research_id, uuid4(), wire.HumanBriefPatch(**patch))
        if status == "awaiting_user":
            return revision.brief
        confirmed, _ = self.confirm_brief(
            research_id,
            uuid4(),
            wire.HumanBriefConfirm(
                expected_brief_id=revision.brief_id,
                expected_brief_version=revision.brief_version,
                category_choice="current" if content.primary_category else "unmatched",
                skipped_clarification=content.skipped_clarification,
                continue_with_unknowns=patch["continue_with_unknowns"],
            ),
        )
        return confirmed.brief

    def append_plan(self, research_id, brief_id, brief_version, **values):
        brief = self.get_brief(research_id, brief_id, brief_version)
        values = dict(values)
        queries = [
            wire.QueryPlanItem.model_validate(
                q.model_dump(mode="json") if isinstance(q, wire.QueryPlanItem) else q
            ).model_dump(mode="json")
            for q in values["query_plan"]
        ]
        for q in queries:
            q["user_confirmed"] = False
            if q["origin"] == "user_confirmed":
                q["origin"] = "user_stated"
        values["query_plan"] = queries
        ensure_account(self.fixture_db, self, research_id)
        token = (
            publish_qualification(self.fixture_db, values["source_plan"])
            if values["source_plan"]
            else None
        )
        selected = wire.ResearchPlan(
            user_id=self.user_id,
            project_id=self.project_id,
            research_id=research_id,
            research_plan_id=uuid4(),
            plan_version=1,
            plan_fingerprint="0" * 64,
            status="awaiting_user",
            brief_id=brief_id,
            brief_version=brief_version,
            brief=brief.content,
            created_at=datetime.now(timezone.utc),
            versions={"brief": brief_version, "plan": 1, "source_registry": token},
            **values,
        )
        payload = selected.model_dump(mode="json")
        payload["plan_fingerprint"] = plan_fingerprint(payload)
        body = wire.PlanDraftCreate(
            expected_brief_id=brief_id,
            expected_brief_version=brief_version,
            research_mode=selected.research_mode,
            budget=selected.budget,
        )
        receipt, _ = self.draft_plan(
            research_id,
            uuid4(),
            body,
            compiled=wire.ResearchPlan.model_validate(payload),
        )
        return receipt.plan

    def approve_plan(self, research_id, plan_id, version, fingerprint):
        selected = self.get_plan(research_id, plan_id, version)
        if selected.plan_fingerprint != fingerprint:
            raise StalePlanError("Plan fingerprint changed")
        if selected.status == "confirmed":
            return selected
        current = self.latest_brief(research_id)
        if (current.brief_id, current.brief_version) != (
            selected.brief_id,
            selected.brief_version,
        ):
            raise StalePlanError("Brief changed; regenerate the plan")
        eligibility = self.get_plan_preparation(
            research_id, plan_id, version
        ).eligibility
        body = wire.PlanApprovalCreate(
            expected_plan_id=plan_id,
            expected_plan_version=version,
            expected_plan_fingerprint=fingerprint,
            expected_brief_id=selected.brief_id,
            expected_brief_version=selected.brief_version,
            confirmed_query_ids=[
                q.query_id for q in selected.query_plan if not q.user_confirmed
            ],
            acknowledged_gap_ids=[
                g.gap_id for g in eligibility.coverage_gaps if g.required
            ],
        )
        try:
            receipt, _ = Phase1Repository.approve_plan(self, research_id, uuid4(), body)
        except Phase1Conflict:
            raise StalePlanError(
                "Current plan selection or eligibility changed"
            ) from None
        return receipt.plan


def seed_phase1_graph(db, data):
    """Derive current-head graph in memory; never rewrite golden fixture bytes."""
    from app.db.models import UserRecord, ProjectRecord

    source_ids = {
        "synthetic-community-A": "source-0017",
        "synthetic-reviews-B": "source-0134",
    }

    def native_source_ids(value):
        if isinstance(value, dict):
            return {
                source_ids.get(key, key): native_source_ids(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [native_source_ids(item) for item in value]
        if isinstance(value, str):
            return source_ids.get(value, value)
        return value

    rebound = native_source_ids(data)
    data.clear()
    data.update(rebound)
    original_brief = wire.IdeaBrief.model_validate(data["records"]["IdeaBrief"][0])
    original_plan = wire.ResearchPlan.model_validate(data["records"]["ResearchPlan"][0])
    with db["admin"].transaction() as session:
        session.add(
            UserRecord(
                user_id=original_brief.user_id,
                email=str(original_brief.user_id) + "@fixture.invalid",
                password_hash="synthetic-only",
            )
        )
        session.flush()
        session.add(
            ProjectRecord(
                user_id=original_brief.user_id,
                project_id=original_brief.project_id,
                name="Synthetic current-head graph",
            )
        )
    repo = NativePhase1Fixture(db, original_brief.user_id, original_brief.project_id)
    rid = repo.create_research(original_brief.content.original_idea)
    brief = repo.append_brief(rid, original_brief.content, status="confirmed")
    values = {
        name: getattr(original_plan, name)
        for name in (
            "research_mode",
            "intents",
            "source_plan",
            "query_plan",
            "budget",
            "known_unknowns",
        )
    }
    pending = repo.append_plan(rid, brief.brief_id, brief.brief_version, **values)
    approved = repo.approve_plan(
        rid, pending.research_plan_id, pending.plan_version, pending.plan_fingerprint
    )
    replacements = {
        str(original_brief.research_id): str(rid),
        str(original_brief.brief_id): str(brief.brief_id),
        str(original_plan.research_plan_id): str(approved.research_plan_id),
    }

    def rebind(value):
        if isinstance(value, dict):
            updated = {
                replacements.get(key, key): rebind(item) for key, item in value.items()
            }
            if "schema_version" in updated and "versions" in updated:
                if updated["versions"].get("brief") is not None:
                    updated["versions"]["brief"] = brief.brief_version
                if updated["versions"].get("plan") is not None:
                    updated["versions"]["plan"] = approved.plan_version
                updated["versions"]["source_registry"] = (
                    approved.versions.source_registry
                )
            if "brief_version" in updated:
                updated["brief_version"] = brief.brief_version
            if "plan_version" in updated:
                updated["plan_version"] = approved.plan_version
            if "research_plan_version" in updated:
                updated["research_plan_version"] = approved.plan_version
            if "plan_fingerprint" in updated:
                updated["plan_fingerprint"] = approved.plan_fingerprint
            return updated
        if isinstance(value, list):
            return [rebind(item) for item in value]
        if isinstance(value, str):
            return replacements.get(value, value)
        return value

    derived = rebind(data)
    derived["records"]["IdeaBrief"] = [brief.model_dump(mode="json")]
    derived["records"]["ResearchPlan"] = [
        pending.model_dump(mode="json"),
        approved.model_dump(mode="json"),
    ]
    data.clear()
    data.update(derived)
    for name, bodies in data["records"].items():
        for body in bodies:
            getattr(wire, name).model_validate(body)
    return dict(
        user_id=brief.user_id, project_id=brief.project_id, research_id=rid
    ), repo


def historical_database(monkeypatch, *, head="20261002_0008"):
    """Own explicit historical database; never downgrade or replace current009.

    The old role is checked for native restriction, not falsely validated against the
    current production head/catalog. Every database/role is cleaned in finally.
    """
    import os
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from app.db.engine import Database

    allowed = {
        "20261001_0001",
        "20261001_0002",
        "20261001_0003",
        "20261001_0004",
        "20261001_0005",
        "20261002_0006",
        "20261002_0007",
        "20261002_0008",
    }
    if head not in allowed:
        raise ValueError("Exact immutable historical head required")
    if os.environ.get("DEMANDRIFT_DB_TESTS") != "1":
        raise RuntimeError("Explicit native fixture gate required")
    raw = os.environ.get("DEMANDRIFT_TEST_ADMIN_URL")
    if not raw:
        raise RuntimeError("Native fixture admin URL required")
    url = make_url(raw)
    if url.drivername != "postgresql+psycopg":
        raise ValueError("Native PostgreSQL fixture required")
    suffix = uuid4().hex[:12]
    name = "demandrift_history_" + suffix
    role = "demandrift_historyapp_" + suffix
    server = create_engine(url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    quote = server.dialect.identifier_preparer.quote
    admin_url = url.set(database=name)
    app_url = admin_url.set(username=role, password="ephemeral-history-only")
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    admin = app = None
    try:
        with server.connect() as connection:
            connection.exec_driver_sql(
                f"CREATE ROLE {quote(role)} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD 'ephemeral-history-only'"
            )
            connection.exec_driver_sql(f"CREATE DATABASE {quote(name)}")
        monkeypatch.setenv(
            "DATABASE_URL", admin_url.render_as_string(hide_password=False)
        )
        monkeypatch.setenv("DATABASE_APP_ROLE", role)
        command.upgrade(config, head)
        admin = Database(admin_url.render_as_string(hide_password=False))
        app = Database(app_url.render_as_string(hide_password=False), pool_size=1)
        with app.transaction() as session:
            assert session.scalar(
                text(
                    "SELECT NOT (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb) FROM pg_roles WHERE rolname=current_user"
                )
            )
            assert (
                session.scalar(text("SELECT version_num FROM public.alembic_version"))
                == head
            )
        yield dict(admin=admin, app=app, config=config, role=role, name=name)
    finally:
        if app:
            app.close()
        if admin:
            admin.close()
        with server.connect() as connection:
            connection.exec_driver_sql(
                f"DROP DATABASE IF EXISTS {quote(name)} WITH (FORCE)"
            )
            connection.exec_driver_sql(f"DROP ROLE IF EXISTS {quote(role)}")
        server.dispose()
