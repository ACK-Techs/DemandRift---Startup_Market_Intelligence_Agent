"""Actual isolated native009 PostgreSQL receipts, claims and atomic graph operations."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from app.budget_contract import BudgetCapacity, ResourceAmount
from app.contracts import (
    ResearchCreate,
    HumanBriefPatch,
    HumanPlanPatch,
    HumanBriefConfirm,
    PlanDraftCreate,
    PlanApprovalCreate,
    PreparationAnalysisCreate,
    PreparationAnalysis,
    ResearchPlan,
    Usage,
)
from app.db.engine import Database
from app.db.models import UserRecord, PlanRecord
from app.db.phase1_repository import Phase1Repository, Phase1Conflict
from app.db.preparation_repository import RecordNotFound, plan_fingerprint
from app.db.budget_repository import BudgetRepository
from app.db.job_budget_repository import JobBudgetRepository
from app.job_budget_contract import (
    AdmissionContext,
    AdmissionUnavailable,
    AdmissionConflict,
)
from app.db import phase1_models as tables
from test_budget_contract import approved_limits
from test_preparation_repository import content_plan

pytestmark = pytest.mark.postgres
META = {
    "kind": "model",
    "operation_version": "offline-v1",
    "provider": "offline",
    "model": "offline",
    "prompt_version": "v1",
    "schema_version": "1.0.0",
    "pricing_version": "v1",
}
AMOUNT = ResourceAmount(requests=1, bytes=1000, tokens=100, cost_picousd=100)
MEASURED = ResourceAmount(requests=1, bytes=500, tokens=30, cost_picousd=10)


@pytest.fixture
def phase1_database(monkeypatch):
    if os.environ.get("DEMANDRIFT_DB_TESTS") != "1":
        pytest.skip("Explicit actual PostgreSQL gate required")
    raw = os.environ.get("DEMANDRIFT_TEST_ADMIN_URL")
    if not raw:
        pytest.fail("Native admin URL required")
    url = make_url(raw)
    assert url.drivername == "postgresql+psycopg"
    suffix = uuid4().hex[:12]
    name, role = "demandrift_phase1_" + suffix, "demandrift_phase1app_" + suffix
    server = create_engine(url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    quote = server.dialect.identifier_preparer.quote
    admin_url = url.set(database=name)
    app_url = admin_url.set(username=role, password="ephemeral-native-only")
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    admin = app = None
    try:
        with server.connect() as c:
            c.exec_driver_sql(
                f"CREATE ROLE {quote(role)} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD 'ephemeral-native-only'"
            )
            c.exec_driver_sql(f"CREATE DATABASE {quote(name)}")
        monkeypatch.setenv(
            "DATABASE_URL", admin_url.render_as_string(hide_password=False)
        )
        monkeypatch.setenv("DATABASE_APP_ROLE", role)
        command.upgrade(config, "20261002_0009")
        admin = Database(admin_url.render_as_string(hide_password=False))
        app = Database(app_url.render_as_string(hide_password=False), pool_size=2)
        with app.transaction() as s:
            assert s.scalar(
                text(
                    "SELECT NOT (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb) FROM pg_roles WHERE rolname=current_user"
                )
            )
            assert not s.scalar(
                text(
                    "SELECT has_table_privilege(current_user,'public.budget_suites','SELECT')"
                )
            )
        yield {
            "admin": admin,
            "app": app,
            "config": config,
            "role": role,
            "name": name,
            "admin_url": admin_url,
            "app_url": app_url,
        }
    finally:
        if app:
            app.close()
        if admin:
            admin.close()
        with server.connect() as c:
            c.exec_driver_sql(f"DROP DATABASE IF EXISTS {quote(name)} WITH (FORCE)")
            c.exec_driver_sql(f"DROP ROLE IF EXISTS {quote(role)}")
        server.dispose()


def setup(db, *, confirmed=True, user=None, project=None):
    user = user or uuid4()
    if project is None:
        with db["admin"].transaction() as s:
            s.add(
                UserRecord(
                    user_id=user,
                    email=f"{user}@fixture.invalid",
                    password_hash="fixture-only",
                )
            )
        project = Phase1Repository.create_project(
            db["app"], user, "Native phase1 fixture"
        ).project_id
    repo = Phase1Repository(db["app"], user, project)
    receipt, _ = repo.create_preparation(
        uuid4(), ResearchCreate(original_idea="  e\u0301🙂 原 idea\n")
    )
    rid = receipt.research_id
    edited, _ = repo.revise(
        rid,
        uuid4(),
        HumanBriefPatch(
            expected_brief_version=1,
            product_type="tool",
            target_user="developers",
            problem_or_job="search",
            primary_category="gelistirici-araci",
        ),
    )
    brief = edited.brief
    if confirmed:
        confirm, _ = repo.confirm_brief(
            rid,
            uuid4(),
            HumanBriefConfirm(
                expected_brief_id=brief.brief_id,
                expected_brief_version=brief.brief_version,
                category_choice="current",
            ),
        )
        brief = confirm.brief
    suite = uuid4()
    limits = approved_limits()
    capacity = BudgetCapacity.from_wire(limits)
    with db["admin"].transaction() as s:
        from app.db import budget_models as ledger

        s.execute(
            ledger.suites.insert().values(
                suite_id=suite,
                ceiling=capacity.ceiling.to_json(),
                soft_cost_picousd=capacity.soft_cost_picousd,
                duration_seconds=capacity.duration_seconds,
                concurrency=capacity.concurrency,
                spent=ResourceAmount().to_json(),
                held=ResourceAmount().to_json(),
            )
        )
    account = BudgetRepository(db["app"], suite, user, project, rid)
    account.create_account(capacity)
    return repo, rid, brief, suite, account


def qualified(db, source=None, *, expires=None):
    source = source or content_plan()["source_plan"][0]
    from app.contracts import SourcePlanItem

    source = SourcePlanItem.model_validate(source).model_dump(mode="json")
    payload = {
        "sources": [source],
        "registry_version": "synthetic-offline-v1",
        "registry_digest": "a" * 64,
        "grant_digest": "b" * 64,
    }
    now = datetime.now(timezone.utc)
    with db["admin"].transaction() as s:
        digest = s.scalar(
            text(
                "SELECT encode(sha256(convert_to(CAST(:p AS jsonb)::text,'UTF8')),'hex')"
            ),
            dict(p=json.dumps(payload)),
        )
        s.execute(
            tables.qualifications.insert().values(
                qualification_version="offline-v1",
                qualification_digest=digest,
                payload=payload,
                reviewed_at=now - timedelta(seconds=2),
                valid_from=now - timedelta(seconds=1),
                expires_at=expires or now + timedelta(hours=1),
            )
        )
        s.execute(
            tables.qualification_current.insert().values(
                slot=1, qualification_version="offline-v1", qualification_digest=digest
            )
        )
    return "offline-v1:" + digest


def compiled(brief, *, token=None, empty=False, budget=None):
    values = content_plan()
    values["budget"] = budget or values["budget"]
    if empty:
        values.update(source_plan=[], query_plan=[], intents=[])
    else:
        values["query_plan"][0].update(origin="ai_hypothesis", user_confirmed=False)
    dto = ResearchPlan(
        user_id=brief.user_id,
        project_id=brief.project_id,
        research_id=brief.research_id,
        created_at=datetime.now(timezone.utc),
        research_plan_id=uuid4(),
        plan_version=1,
        plan_fingerprint="0" * 64,
        status="awaiting_user",
        brief_id=brief.brief_id,
        brief_version=brief.brief_version,
        brief=brief.content,
        versions={"brief": brief.brief_version, "plan": 1, "source_registry": token},
        **values,
    )
    payload = dto.model_dump(mode="json")
    payload["plan_fingerprint"] = plan_fingerprint(payload)
    return ResearchPlan.model_validate(payload)


def draft(repo, rid, brief, plan, key=None):
    body = PlanDraftCreate(
        expected_brief_id=brief.brief_id,
        expected_brief_version=brief.brief_version,
        research_mode=plan.research_mode,
        budget=plan.budget,
    )
    result, created = repo.draft_plan(rid, key or uuid4(), body, compiled=plan)
    return result, body, created


def approval(plan, brief):
    return PlanApprovalCreate(
        expected_plan_id=plan.research_plan_id,
        expected_plan_version=plan.plan_version,
        expected_plan_fingerprint=plan.plan_fingerprint,
        expected_brief_id=brief.brief_id,
        expected_brief_version=brief.brief_version,
        confirmed_query_ids=[
            q.query_id for q in plan.query_plan if not q.user_confirmed
        ],
    )


def test_native009_upgrade_and_explicit_confirmation_receipt(phase1_database):
    db = phase1_database
    repo, rid, brief, suite, account = setup(db)
    assert (
        brief.status == "confirmed"
        and brief.content.original_idea == "  e\u0301🙂 原 idea\n"
    )
    assert brief.content.product_type.prior_origins == ["user_stated"]
    with db["app"].transaction(brief.user_id) as s:
        assert (
            s.scalar(text("SELECT version_num FROM public.alembic_version"))
            == "20261002_0009"
        )
        assert (
            s.scalar(
                text(
                    "SELECT count(*) FROM public.preparation_mutations WHERE operation='confirm_brief'"
                )
            )
            == 1
        )


def test_exact_confirmation_replay_survives_later_brief_and_archive(phase1_database):
    db = phase1_database
    repo, rid, brief, _, _ = setup(db, confirmed=False)
    key = uuid4()
    body = HumanBriefConfirm(
        expected_brief_id=brief.brief_id,
        expected_brief_version=brief.brief_version,
        category_choice="current",
    )
    first, created = repo.confirm_brief(rid, key, body)
    assert created
    repo.revise(
        rid,
        uuid4(),
        HumanBriefPatch(
            expected_brief_version=first.brief_version, target_user="changed"
        ),
    )
    with db["admin"].transaction() as s:
        s.execute(
            text(
                "UPDATE public.projects SET archived_at=clock_timestamp() WHERE project_id=:p"
            ),
            dict(p=repo.project_id),
        )
    replay, new = repo.confirm_brief(rid, key, body)
    assert replay == first and not new
    with pytest.raises(RecordNotFound):
        repo.confirm_brief(rid, uuid4(), body)
    with pytest.raises(Phase1Conflict):
        repo.confirm_brief(
            rid, key, body.model_copy(update={"category_choice": "unmatched"})
        )


def test_closed_empty_draft_and_qualification_expiry_revocation(phase1_database):
    db = phase1_database
    repo, rid, brief, _, _ = setup(db)
    receipt, _, _ = draft(repo, rid, brief, compiled(brief, empty=True))
    state = repo.latest_plan(rid)
    assert (
        not state.eligibility.can_approve
        and "no_eligible_source" in state.eligibility.blocking_reasons
    )
    with pytest.raises(Phase1Conflict):
        repo.approve_plan(rid, uuid4(), approval(receipt.plan, brief))
    token = qualified(db)
    receipt, _, _ = draft(repo, rid, brief, compiled(brief, token=token))
    assert repo.latest_plan(rid).eligibility.can_approve
    with db["admin"].transaction() as s:
        s.execute(
            text(
                "UPDATE public.source_qualification_snapshots SET revoked_at=clock_timestamp()"
            )
        )
    assert (
        "source_permission_unavailable"
        in repo.latest_plan(rid).eligibility.blocking_reasons
    )
    with pytest.raises(Phase1Conflict):
        repo.approve_plan(rid, uuid4(), approval(receipt.plan, brief))


def test_nonempty_graph_approval_receipt_atomic_historical_and_paging(phase1_database):
    db = phase1_database
    repo, rid, brief, _, _ = setup(db)
    token = qualified(db)
    key = uuid4()
    source = compiled(brief, token=token)
    pending, body, _ = draft(repo, rid, brief, source, key)
    repeated, new = repo.draft_plan(rid, key, body, compiled=source)
    assert repeated == pending and not new
    assert repo.latest_plan(rid).eligibility.can_approve
    approved, created = repo.approve_plan(rid, uuid4(), approval(pending.plan, brief))
    assert created and approved.plan.status == "confirmed"
    assert (
        repo.latest_plan(rid).eligibility.can_start
        and approved.input_plan_fingerprint == pending.plan.plan_fingerprint
    )
    assert (
        repo.get_plan_preparation(
            rid, pending.result_plan_id, pending.result_plan_version
        ).plan
        == pending.plan
    )
    page = repo.list_plans(rid, limit=1)
    assert len(page.items) == 1 and page.page.next_cursor
    assert repo.list_plans(rid, limit=1, cursor=page.page.next_cursor).items == [
        pending.plan
    ]
    with db["app"].transaction(repo.user_id) as s:
        assert (
            s.scalar(
                select(tables.plan_mutations.c.result_plan_version).where(
                    tables.plan_mutations.c.operation == "approve_plan"
                )
            )
            == approved.result_plan_version
        )


def claim(repo, rid, brief, suite, *, key=None, kind="brief"):
    body = PreparationAnalysisCreate(
        kind=kind,
        expected_brief_id=brief.brief_id,
        expected_brief_version=brief.brief_version,
        budget=approved_limits(),
    )
    key = key or uuid4()
    result, created = repo.claim_analysis(
        rid,
        key,
        body,
        suite_id=suite,
        prepared_fingerprint="c" * 64,
        reserved=AMOUNT,
        metadata=META,
    )
    return result, body, key, created


def admit(db, repo, rid, brief, suite, operation):
    gateway = JobBudgetRepository(db["app"], suite, repo.user_id, repo.project_id, rid)
    context = AdmissionContext("preparation", brief.brief_id, brief.brief_version)
    return (
        gateway,
        context,
        gateway.admit(
            context,
            attempt_id=operation.attempt_id,
            fingerprint="c" * 64,
            reserved=AMOUNT,
            metadata=META,
            model_timeout_ms=5000,
        ),
    )


def analysis_for(operation, *, proposals=None):
    return PreparationAnalysis(
        user_id=operation.user_id,
        project_id=operation.project_id,
        research_id=operation.research_id,
        analysis_id=operation.analysis_id,
        analysis_kind="brief" if operation.operation == "analyze_brief" else "plan",
        input_brief_id=operation.input_brief_id,
        input_brief_version=operation.input_brief_version,
        input_plan_id=operation.input_plan_id,
        input_plan_version=operation.input_plan_version,
        input_plan_fingerprint=operation.input_plan_fingerprint,
        created_at=datetime.now(timezone.utc),
        versions={
            "brief": operation.input_brief_version,
            "plan": operation.input_plan_version,
            "model": "offline",
            "prompts": {"phase1": "v1"},
        },
        field_proposals=proposals or [],
    )


def measured_usage():
    return Usage(
        requests=1,
        bytes=500,
        input_tokens=10,
        output_tokens=20,
        cost_usd=MEASURED.cost_usd,
    )


def test_analysis_claim_commit_exact_replay_known_settlement_and_historical_reads(
    phase1_database,
):
    db = phase1_database
    repo, rid, brief, suite, ledger = setup(db, confirmed=False)
    op, body, key, created = claim(repo, rid, brief, suite)
    assert created and op.status == "pending"
    with db["app"].transaction(repo.user_id) as s:
        assert s.scalar(select(tables.analysis_requests.c.attempt_id)) == op.attempt_id
        from app.db import budget_models as budget

        assert s.scalar(select(budget.attempts.c.attempt_id)) is None
    replay, new = repo.claim_analysis(
        rid,
        key,
        body,
        suite_id=suite,
        prepared_fingerprint="c" * 64,
        reserved=AMOUNT,
        metadata=META,
    )
    assert replay == op and not new
    dto = analysis_for(
        op,
        proposals=[
            dict(
                proposal_id="proposal-target",
                field_path="target_user",
                value="maintainers",
                origin="ai_hypothesis",
                assumption_id="assumption-target",
                basis_refs=["original_idea"],
            )
        ],
    )
    with pytest.raises(Phase1Conflict):
        repo.publish_analysis(
            rid,
            key,
            op.operation,
            analysis=dto,
            status="completed",
            output_digest="d" * 64,
            usage=measured_usage(),
        )
    gateway, context, permit = admit(db, repo, rid, brief, suite, op)
    assert permit.dispatch_permitted
    ledger.settle(
        op.attempt_id,
        MEASURED,
        dict(response_id="offline", model_version="offline", usage_version="v1"),
    )
    result = repo.publish_analysis(
        rid,
        key,
        op.operation,
        analysis=dto,
        status="completed",
        output_digest="d" * 64,
        usage=measured_usage(),
    )
    assert result.status == "completed" and result.analysis == dto
    assert (
        repo.publish_analysis(
            rid,
            key,
            op.operation,
            analysis=dto,
            status="completed",
            output_digest="d" * 64,
            usage=measured_usage(),
        )
        == result
    )
    assert not gateway.admit(
        context,
        attempt_id=op.attempt_id,
        fingerprint="c" * 64,
        reserved=AMOUNT,
        metadata=META,
        model_timeout_ms=5000,
    ).dispatch_permitted
    confirmed, _ = repo.confirm_brief(
        rid,
        uuid4(),
        HumanBriefConfirm(
            expected_brief_id=brief.brief_id,
            expected_brief_version=brief.brief_version,
            analysis_id=op.analysis_id,
            accepted_proposal_ids=["proposal-target"],
            category_choice="current",
        ),
    )
    assert confirmed.brief.content.target_user.value == "maintainers"
    assert confirmed.brief.content.target_user.prior_origins == [
        "user_stated",
        "user_confirmed",
        "ai_hypothesis",
    ]
    assert repo.get_analysis(rid, op.analysis_id) == dto
    assert repo.list_analyses(rid, limit=1).items == [dto]
    assert not repo.read_analysis_operation(op.operation, key).current_scope_matches
    with pytest.raises(Phase1Conflict):
        repo.publish_analysis(
            rid,
            key,
            op.operation,
            analysis=dto,
            status="completed",
            output_digest="e" * 64,
            usage=measured_usage(),
        )


def test_unknown_attempt_stays_held_no_result_or_new_permit(phase1_database):
    db = phase1_database
    repo, rid, brief, suite, ledger = setup(db)
    op, body, key, _ = claim(repo, rid, brief, suite)
    gateway, context, _ = admit(db, repo, rid, brief, suite, op)
    ledger.mark_unknown(op.attempt_id)
    state = repo.read_analysis_operation(op.operation, key)
    assert (
        state.status == "provider_unknown"
        and state.usage.provider_result_unknown
        and state.analysis is None
    )
    with pytest.raises(Phase1Conflict):
        repo.publish_analysis(
            rid,
            key,
            op.operation,
            analysis=analysis_for(op),
            status="completed",
            output_digest="d" * 64,
            usage=measured_usage(),
        )
    assert not gateway.admit(
        context,
        attempt_id=op.attempt_id,
        fingerprint="c" * 64,
        reserved=AMOUNT,
        metadata=META,
        model_timeout_ms=5000,
    ).dispatch_permitted
    newer, _, _, _ = claim(repo, rid, brief, suite)
    with pytest.raises(AdmissionConflict):
        gateway.admit(
            context,
            attempt_id=newer.attempt_id,
            fingerprint="c" * 64,
            reserved=AMOUNT,
            metadata=META,
            model_timeout_ms=5000,
        )
    assert ledger.snapshot()["held"]["requests"] == 1


def test_fresh_preparation_dispatch_requires_matching_committed_claim(phase1_database):
    db = phase1_database
    repo, rid, brief, suite, _ = setup(db)
    gateway = JobBudgetRepository(db["app"], suite, repo.user_id, repo.project_id, rid)
    context = AdmissionContext("preparation", brief.brief_id, brief.brief_version)
    with pytest.raises(AdmissionConflict):
        gateway.admit(
            context,
            attempt_id=uuid4(),
            fingerprint="c" * 64,
            reserved=AMOUNT,
            metadata=META,
            model_timeout_ms=5000,
        )
    op, _, _, _ = claim(repo, rid, brief, suite)
    with pytest.raises(AdmissionConflict):
        gateway.admit(
            context,
            attempt_id=op.attempt_id,
            fingerprint="e" * 64,
            reserved=AMOUNT,
            metadata=META,
            model_timeout_ms=5000,
        )


def test_concurrent_same_key_confirmation_and_project_plan_version_serialization(
    phase1_database,
):
    db = phase1_database
    repo, rid, brief, _, _ = setup(db, confirmed=False)
    key = uuid4()
    body = HumanBriefConfirm(
        expected_brief_id=brief.brief_id,
        expected_brief_version=brief.brief_version,
        category_choice="current",
    )
    barrier = Barrier(2)

    def confirm():
        barrier.wait(timeout=5)
        return repo.confirm_brief(rid, key, body)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(confirm) for _ in range(2)]
        outcomes = [f.result(timeout=15) for f in futures]
    assert (
        sorted(created for _, created in outcomes) == [False, True]
        and outcomes[0][0] == outcomes[1][0]
    )
    brief = outcomes[0][0].brief
    token = qualified(db)
    barrier = Barrier(2)

    def create():
        barrier.wait(timeout=5)
        return draft(repo, rid, brief, compiled(brief, token=token))[0]

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(create) for _ in range(2)]
        plans = [f.result(timeout=15).plan for f in futures]
    assert (
        sorted(p.plan_version for p in plans) == [1, 2]
        and len(repo.list_plans(rid).items) == 2
    )


def test_mid_graph_failure_rolls_back_snapshot_graph_and_receipt(
    phase1_database, monkeypatch
):
    db = phase1_database
    repo, rid, brief, _, _ = setup(db)
    token = qualified(db)

    def fail(*args, **kwargs):
        raise RuntimeError("injected after graph write")

    monkeypatch.setattr(repo, "_persist_plan_receipt", fail)
    with pytest.raises(RuntimeError):
        draft(repo, rid, brief, compiled(brief, token=token))
    with db["app"].transaction(repo.user_id) as s:
        assert s.scalar(select(PlanRecord.plan_version)) is None
        assert s.scalar(select(tables.plan_mutations.c.operation)) is None


def job_for(db, repo, rid, brief, plan):
    from app.contracts import ResearchRun
    from app.db.evidence_repository import EvidenceRepository
    from app.db.job_repository import JobRepository
    from app.job_contract import EnqueueJob

    run = ResearchRun(
        user_id=repo.user_id,
        project_id=repo.project_id,
        research_id=rid,
        created_at=datetime.now(timezone.utc),
        versions={"brief": brief.brief_version, "plan": plan.plan_version},
        phase="planning",
        status="queued",
        brief_id=brief.brief_id,
        brief_version=brief.brief_version,
        research_plan_id=plan.research_plan_id,
        plan_version=plan.plan_version,
        plan_fingerprint=plan.plan_fingerprint,
        budget=plan.budget,
        usage=Usage(),
        cancel_requested=False,
        source_executions=[],
    )
    evidence = EvidenceRepository(db["app"], repo.user_id, repo.project_id)
    with evidence.transaction(rid) as writer:
        writer.put_run(run)
    jobs = JobRepository(db["app"], repo.user_id, repo.project_id)
    enqueued = jobs.enqueue(
        rid,
        EnqueueJob(
            request_key=uuid4(),
            request_fingerprint="a" * 64,
            brief_id=brief.brief_id,
            brief_version=brief.brief_version,
            research_plan_id=plan.research_plan_id,
            plan_version=plan.plan_version,
            plan_fingerprint=plan.plan_fingerprint,
        ),
    )
    running = jobs.claim(rid, enqueued.job.job_id, uuid4(), lease_seconds=30).job
    context = AdmissionContext(
        "job",
        brief.brief_id,
        brief.brief_version,
        running.job_id,
        running.lease_owner,
        running.fence,
    )
    return jobs, running, context


def narrow_plan(brief, token, **caps):
    values = compiled(brief, token=token).model_dump(mode="json")
    values["budget"].update(caps)
    mapping = {
        "max_items": "max_records",
        "max_pages": "max_pages",
        "max_requests": "max_requests",
        "max_response_bytes": "max_bytes",
        "max_total_bytes": "max_bytes",
        "max_seconds": "max_duration_seconds",
        "max_llm_tokens": "max_tokens",
    }
    for item in values["source_plan"] + values["query_plan"]:
        for key, budget in mapping.items():
            item["limits"][key] = min(item["limits"][key], values["budget"][budget])
    values = ResearchPlan.model_validate(values).model_dump(mode="json")
    values["plan_fingerprint"] = plan_fingerprint(values)
    return ResearchPlan.model_validate(values)


def test_job_dispatch_uses_plan_spent_caps_and_revoked_qualification(phase1_database):
    db = phase1_database
    repo, rid, brief, suite, ledger = setup(db)
    op, _, _, _ = claim(repo, rid, brief, suite)
    admit(db, repo, rid, brief, suite, op)
    ledger.settle(
        op.attempt_id,
        MEASURED,
        dict(response_id="offline", model_version="offline", usage_version="v1"),
    )
    token = qualified(db)
    pending, _, _ = draft(repo, rid, brief, narrow_plan(brief, token, max_requests=1))
    approved, _ = repo.approve_plan(rid, uuid4(), approval(pending.plan, brief))
    _, job, context = job_for(db, repo, rid, brief, approved.plan)
    gateway = JobBudgetRepository(db["app"], suite, repo.user_id, repo.project_id, rid)
    with pytest.raises(AdmissionUnavailable):
        gateway.admit(
            context,
            attempt_id=uuid4(),
            fingerprint="d" * 64,
            reserved=AMOUNT,
            metadata=META,
            model_timeout_ms=5000,
        )
    assert (
        ledger.snapshot()["spent"]["requests"] == 1
        and ledger.snapshot()["held"]["requests"] == 0
    )
    with db["admin"].transaction() as s:
        s.execute(
            text(
                "UPDATE public.source_qualification_snapshots SET revoked_at=clock_timestamp()"
            )
        )
    with pytest.raises(AdmissionConflict):
        gateway.remaining(context, model_timeout_ms=5000)


def test_job_deadline_shares_preparation_account_clock_and_cancel_blocks_admission(
    phase1_database,
):
    db = phase1_database
    repo, rid, brief, suite, ledger = setup(db)
    op, _, _, _ = claim(repo, rid, brief, suite)
    admit(db, repo, rid, brief, suite, op)
    ledger.settle(
        op.attempt_id,
        MEASURED,
        dict(response_id="offline", model_version="offline", usage_version="v1"),
    )
    started = ledger.snapshot()["started_at"]
    token = qualified(db)
    pending, _, _ = draft(
        repo, rid, brief, narrow_plan(brief, token, max_duration_seconds=10)
    )
    approved, _ = repo.approve_plan(rid, uuid4(), approval(pending.plan, brief))
    jobs, job, context = job_for(db, repo, rid, brief, approved.plan)
    gateway = JobBudgetRepository(db["app"], suite, repo.user_id, repo.project_id, rid)
    permit = gateway.admit(
        context,
        attempt_id=uuid4(),
        fingerprint="d" * 64,
        reserved=AMOUNT,
        metadata=META,
        model_timeout_ms=60000,
    )
    assert permit.deadline_at <= started + timedelta(seconds=10)
    assert ledger.snapshot()["started_at"] == started
    jobs.cancel(rid, job.job_id)
    with pytest.raises(AdmissionUnavailable):
        gateway.admit(
            context,
            attempt_id=uuid4(),
            fingerprint="d" * 64,
            reserved=AMOUNT,
            metadata=META,
            model_timeout_ms=5000,
        )


def test_human_plan_query_revision_and_historical_idempotent_receipt(phase1_database):
    db = phase1_database
    repo, rid, brief, _, _ = setup(db)
    token = qualified(db)
    first, _, _ = draft(repo, rid, brief, compiled(brief, token=token))
    plan = first.plan
    query = plan.query_plan[0]
    body = HumanPlanPatch(
        expected_plan_id=plan.research_plan_id,
        expected_plan_version=plan.plan_version,
        expected_plan_fingerprint=plan.plan_fingerprint,
        expected_brief_id=brief.brief_id,
        expected_brief_version=brief.brief_version,
        query_edits=[dict(query_id=query.query_id, query_text="  precise edit🙂  ")],
    )
    values = plan.model_dump(mode="json")
    values["query_plan"][0].update(
        query_text="  precise edit🙂  ", origin="user_stated", user_confirmed=False
    )
    values["plan_fingerprint"] = plan_fingerprint(values)
    compiled_revision = ResearchPlan.model_validate(values)
    key = uuid4()
    result, created = repo.revise_plan(rid, key, body, compiled=compiled_revision)
    assert created and result.plan.query_plan[0].query_text == "  precise edit🙂  "
    assert (
        result.result_plan_version == 2
        and result.input_plan_fingerprint == plan.plan_fingerprint
    )
    approved, _ = repo.approve_plan(rid, uuid4(), approval(result.plan, brief))
    assert approved.plan.query_plan[0].origin == "user_confirmed"
    replay, new = repo.revise_plan(rid, key, body, compiled=compiled_revision)
    assert replay == result and not new
    assert repo.read_plan_mutation("revise_plan", key) == result


def test_analysis_server_ids_conflict_and_result_binding_corruption_is_safe(
    phase1_database,
):
    db = phase1_database
    repo, rid, brief, suite, ledger = setup(db)
    op, body, key, _ = claim(repo, rid, brief, suite)
    with pytest.raises(Phase1Conflict):
        repo.claim_analysis(
            rid,
            key,
            body,
            suite_id=suite,
            prepared_fingerprint="c" * 64,
            reserved=AMOUNT,
            metadata=META,
            attempt_id=uuid4(),
        )
    admit(db, repo, rid, brief, suite, op)
    ledger.settle(
        op.attempt_id,
        MEASURED,
        dict(response_id="offline", model_version="offline", usage_version="v1"),
    )
    repo.publish_analysis(
        rid,
        key,
        op.operation,
        analysis=analysis_for(op),
        status="completed",
        output_digest="d" * 64,
        usage=measured_usage(),
    )
    with db["admin"].transaction() as s:
        s.execute(
            text("ALTER TABLE public.preparation_analysis_results DISABLE TRIGGER USER")
        )
        s.execute(
            text(
                "UPDATE public.preparation_analysis_results SET usage=jsonb_set(usage,'{bytes}','499'::jsonb)"
            )
        )
        s.execute(
            text("ALTER TABLE public.preparation_analysis_results ENABLE TRIGGER USER")
        )
    from app.db.preparation_repository import StoredSnapshotError

    with pytest.raises(StoredSnapshotError):
        repo.get_analysis(rid, op.analysis_id)
    with pytest.raises(StoredSnapshotError):
        repo.read_analysis_operation(op.operation, key)
