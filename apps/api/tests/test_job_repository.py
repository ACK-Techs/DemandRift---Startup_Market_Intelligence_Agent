"""Actual PostgreSQL job fencing, replay, cancellation, recovery and native grants."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from datetime import datetime, timezone
from uuid import uuid4
import time

from alembic import command
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app import contracts as wire
from app.db import job_models as tables
from app.db.budget_repository import BudgetRepository
from app.db import budget_models
from app.budget_contract import BudgetCapacity, ResourceAmount
from app.db.engine import Database
from app.db.migration_head import REQUIRED_MIGRATION
from app.db.job_repository import JobConflict, JobLeaseLost, JobRepository
from app.db.evidence_repository import EvidenceRepository
from app.db.preparation_repository import RecordNotFound, StoredSnapshotError
from app.job_contract import EnqueueJob, LeaseToken
from native_evidence_fixture import fixture_data, seed_preparation
from test_budget_contract import approved_limits

pytestmark = pytest.mark.postgres


def setup_job(db, label="A", *, max_attempts=3, partial=False):
    data = fixture_data(label)
    scope, _ = seed_preparation(db, data)
    run = wire.ResearchRun.model_validate(data["records"]["ResearchRun"][0])
    evidence = EvidenceRepository(db["app"], scope["user_id"], scope["project_id"])
    with evidence.transaction(scope["research_id"]) as writer:
        if partial:
            executions = [wire.QueryExecution.model_validate(r) for r in data["records"]["QueryExecution"]]
            run = wire.ResearchRun.model_validate({**run.model_dump(mode="json"),
                "source_executions": [e.model_dump(mode="json") for e in executions]})
        writer.put_run(run)
        if partial:
            writer.put_artifact(wire.RawArtifact.model_validate(data["records"]["RawArtifact"][0]))
    repo = JobRepository(db["app"], scope["user_id"], scope["project_id"])
    request = EnqueueJob(request_key=uuid4(), request_fingerprint="a" * 64,
        **{k: getattr(run, k) for k in ["research_plan_id", "plan_version", "plan_fingerprint", "brief_id", "brief_version"]},
        max_attempts=max_attempts)
    return repo, run, request, data


def enqueue(db, **kwargs):
    repo, run, request, data = setup_job(db, **kwargs)
    receipt = repo.enqueue(run.research_id, request)
    return repo, run, request, receipt.job, data


def claim(repo, job, *, seconds=30):
    result = repo.claim(job.research_id, job.job_id, uuid4(), lease_seconds=seconds)
    assert result.permitted
    return result.job, LeaseToken(owner=result.job.lease_owner, fence=result.job.fence)


def test_duplicate_concurrent_enqueue_and_conflict_preserve_one_job(postgres_database):
    db = postgres_database
    repo, run, request, _ = setup_job(db)
    barrier = Barrier(2)

    def start():
        separate = Database(db["app"].engine.url.render_as_string(hide_password=False))
        try:
            worker = JobRepository(separate, repo.user_id, repo.project_id)
            barrier.wait(timeout=5)
            return worker.enqueue(run.research_id, request)
        finally:
            separate.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: start(), range(2)))
    assert len({r.job.job_id for r in receipts}) == 1
    assert sum(r.permitted for r in receipts) == 1
    assert len(repo.journal(run.research_id, receipts[0].job.job_id)) == 1
    assert len(repo.pending_deliveries(run.research_id, receipts[0].job.job_id)) == 1
    replay = request.model_copy(update={"request_key": uuid4()})
    assert not repo.enqueue(run.research_id, replay).permitted
    assert not repo.enqueue(run.research_id, replay).permitted
    assert len(repo.journal(run.research_id, receipts[0].job.job_id)) == 2
    for patch in [{"request_fingerprint": "b" * 64}, {"max_attempts": 8}, {"plan_version": 999}]:
        with pytest.raises(JobConflict):
            repo.enqueue(run.research_id, request.model_copy(update=patch))


def test_expired_worker_cannot_advance_complete_or_pass_dispatch_guard(postgres_database):
    repo, run, _, job, _ = enqueue(postgres_database)
    job, stale = claim(repo, job, seconds=1)
    repo.advance(run.research_id, job.job_id, stale, 7)
    time.sleep(1.05)
    for call in [lambda: repo.advance(run.research_id, job.job_id, stale, 8),
                 lambda: repo.finish(run.research_id, job.job_id, stale, succeeded=True),
                 lambda: repo.dispatch_guard(run.research_id, job.job_id, stale),
                 lambda: repo.heartbeat(run.research_id, job.job_id, stale)]:
        with pytest.raises(JobLeaseLost):
            call()
    recovered = repo.recover(run.research_id, job.job_id).job
    assert recovered.state == "queued" and recovered.checkpoint == 7
    replacement, current = claim(repo, recovered)
    assert replacement.fence == stale.fence + 1
    with pytest.raises(JobLeaseLost):
        repo.advance(run.research_id, job.job_id, stale, 9)
    assert repo.dispatch_guard(run.research_id, job.job_id, current).permitted


def test_cancel_blocks_new_claim_dispatch_and_keeps_partial_evidence(postgres_database):
    db = postgres_database
    repo, run, request, job, data = enqueue(db, partial=True)
    _, token = claim(repo, job)
    repo.advance(run.research_id, job.job_id, token, 2)
    delivery = repo.pending_deliveries(run.research_id, job.job_id)[0]
    cancelled = repo.cancel(run.research_id, job.job_id).job
    assert cancelled.state == "cancelled" and cancelled.checkpoint == 2
    assert not repo.claim(run.research_id, job.job_id, uuid4()).permitted
    assert not repo.claim_delivery(run.research_id, job.job_id, delivery, uuid4()).publish_permitted
    with pytest.raises(JobLeaseLost):
        repo.dispatch_guard(run.research_id, job.job_id, token)
    assert not repo.enqueue(run.research_id, request).permitted
    artifact = wire.RawArtifact.model_validate(data["records"]["RawArtifact"][0])
    assert repo.get(run.research_id, "artifact", artifact.artifact_id) == artifact
    assert not repo.cancel(run.research_id, job.job_id).permitted
    assert not repo.recover(run.research_id, job.job_id).permitted


def test_retry_classification_limit_and_terminal_replay(postgres_database):
    repo, run, request, job, _ = enqueue(postgres_database, max_attempts=1)
    _, token = claim(repo, job)
    for error in ["schema", "auth", "policy", "challenge"]:
        with pytest.raises(JobConflict):
            repo.retry(run.research_id, job.job_id, token, error)
    exhausted = repo.retry(run.research_id, job.job_id, token, "timeout").job
    assert exhausted.state == "failed" and exhausted.attempts == 1
    assert not repo.claim(run.research_id, job.job_id, uuid4()).permitted
    assert not repo.finish(run.research_id, job.job_id, token, succeeded=False).permitted
    assert repo.enqueue(run.research_id, request).job == exhausted


def test_retry_backoff_and_live_claim_are_not_reset_by_duplicate_delivery(postgres_database):
    repo, run, _, job, _ = enqueue(postgres_database, max_attempts=2)
    active, token = claim(repo, job)
    assert not repo.claim(run.research_id, job.job_id, uuid4()).permitted
    assert not repo.recover(run.research_id, job.job_id).permitted
    assert repo.heartbeat(run.research_id, job.job_id, token).job.lease_until >= active.lease_until
    waiting = repo.retry(run.research_id, job.job_id, token, "rate_limited").job
    assert waiting.state == "retry_wait" and waiting.available_at > waiting.updated_at
    assert not repo.claim(run.research_id, job.job_id, uuid4()).permitted
    time.sleep(2.05)
    active, token = claim(repo, waiting)
    assert active.attempts == 2
    complete = repo.finish(run.research_id, job.job_id, token, succeeded=True).job
    assert complete.state == "succeeded"
    assert repo.get(run.research_id, "run", run.research_id).status == "queued"
    assert not repo.finish(run.research_id, job.job_id, token, succeeded=True).permitted


def test_outbox_crash_recovery_fences_old_publisher(postgres_database):
    repo, run, _, job, _ = enqueue(postgres_database)
    delivery = repo.pending_deliveries(run.research_id, job.job_id)[0]
    first = repo.claim_delivery(run.research_id, job.job_id, delivery, uuid4(), lease_seconds=1)
    assert first.publish_permitted
    stale = LeaseToken(owner=first.lease_owner, fence=first.fence)
    assert not repo.claim_delivery(run.research_id, job.job_id, delivery, uuid4()).publish_permitted
    time.sleep(1.05)
    next_ = repo.claim_delivery(run.research_id, job.job_id, delivery, uuid4())
    assert next_.publish_permitted and next_.fence == first.fence + 1
    with pytest.raises(JobLeaseLost):
        repo.acknowledge_delivery(run.research_id, job.job_id, delivery, stale)
    current = LeaseToken(owner=next_.lease_owner, fence=next_.fence)
    assert repo.acknowledge_delivery(run.research_id, job.job_id, delivery, current).state == "sent"
    assert not repo.claim_delivery(run.research_id, job.job_id, delivery, uuid4()).publish_permitted


def test_force_rls_scoped_notfound_and_native_mutation_guards(postgres_database):
    db = postgres_database
    repo, run, _, job, _ = enqueue(db)
    other, other_run, _, other_job, _ = enqueue(db, label="B")
    with pytest.raises(RecordNotFound):
        other.get_job(run.research_id, job.job_id)
    with db["app"].transaction(other.user_id) as s:
        assert s.execute(select(tables.jobs).where(tables.jobs.c.job_id == job.job_id)).first() is None
        assert s.execute(select(tables.journal).where(tables.journal.c.job_id == job.job_id)).first() is None
    forbidden = ["UPDATE public.research_jobs SET attempts=0", "UPDATE public.research_jobs SET state='queued'",
                 "DELETE FROM public.research_jobs", "TRUNCATE public.research_jobs",
                 "UPDATE public.job_outbox SET fence=0", "DELETE FROM public.job_journal",
                 "INSERT INTO public.job_journal SELECT * FROM public.job_journal ON CONFLICT DO NOTHING",
                 "INSERT INTO public.job_outbox SELECT * FROM public.job_outbox ON CONFLICT DO NOTHING"]
    for sql in forbidden:
        with pytest.raises(DBAPIError), db["app"].transaction(repo.user_id) as s:
            s.execute(text(sql))
    with pytest.raises(DBAPIError), db["admin"].transaction() as s:
        s.execute(text("UPDATE public.research_jobs SET state='failed',finished_at=clock_timestamp()"))
    with db["admin"].transaction() as s:
        flags = s.execute(text("SELECT relname,relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname IN ('research_jobs','job_outbox','job_journal')")).all()
        assert len(flags) == 3 and all(flag for _, flag in flags)
        functions = s.execute(text("SELECT proname,prosecdef,proconfig FROM pg_proc WHERE proname IN ('demandrift_job_guard','demandrift_job_append','demandrift_job_outbox_guard','demandrift_job_journal_guard')")).all()
        assert len(functions) == 4 and all(secdef == (name == "demandrift_job_append")
            and config == ["search_path=pg_catalog, pg_temp"] for name, secdef, config in functions)
        assert not s.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_proc p,aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a WHERE p.proname LIKE 'demandrift_job_%' AND a.grantee=0 AND a.privilege_type='EXECUTE')"))
        assert tuple(s.execute(text("SELECT has_column_privilege(:role,'public.research_jobs','command','UPDATE'),has_column_privilege(:role,'public.research_jobs','state','UPDATE'),has_table_privilege(:role,'public.job_journal','UPDATE,DELETE,TRUNCATE')"), {"role": db["role"]}).one()) == (True, False, False)
        assert tuple(s.execute(text("SELECT has_table_privilege(:role,'public.job_journal','INSERT'),has_any_column_privilege(:role,'public.job_journal','INSERT'),has_table_privilege(:role,'public.job_outbox','INSERT'),has_any_column_privilege(:role,'public.job_outbox','INSERT'),has_function_privilege(:role,'public.demandrift_job_append()','EXECUTE')"), {"role": db["role"]}).one()) == (False, False, False, False, False)
    assert other.get_job(other_run.research_id, other_job.job_id).state == "queued"


def test_native_stale_command_and_journal_sequence(postgres_database):
    db = postgres_database
    repo, run, _, job, _ = enqueue(db)
    _, token = claim(repo, job)
    with pytest.raises(DBAPIError), db["app"].transaction(repo.user_id) as s:
        s.execute(tables.jobs.update().where(tables.jobs.c.job_id == job.job_id)
            .values(command={"op": "advance", "owner": str(token.owner), "fence": token.fence + 1, "checkpoint": 9}))
    with pytest.raises(DBAPIError), db["app"].transaction(repo.user_id) as s:
        s.execute(tables.jobs.update().where(tables.jobs.c.job_id == job.job_id)
            .values(command={"op": "retry", "owner": str(token.owner), "fence": token.fence, "error": None}))
    repo.advance(run.research_id, job.job_id, token, 3)
    with pytest.raises(JobConflict):
        repo.advance(run.research_id, job.job_id, token, 2)
    assert not repo.advance(run.research_id, job.job_id, token, 3).permitted
    rows = repo.journal(run.research_id, job.job_id)
    assert [r["sequence"] for r in rows] == [1, 2, 3]
    assert [r["event"] for r in rows] == ["enqueue", "claim", "advance"]


def test_job_migration_frozen_roundtrip(postgres_database):
    db = postgres_database
    enqueue(db)
    with db["admin"].transaction() as s:
        assert s.scalar(text("SELECT version_num FROM public.alembic_version")) == REQUIRED_MIGRATION
    command.downgrade(db["config"], "20261001_0005")
    with db["admin"].transaction() as s:
        assert s.scalar(text("SELECT to_regclass('public.research_jobs')")) is None
    command.upgrade(db["config"], "20261002_0006")
    with db["admin"].transaction() as s:
        assert s.scalar(text("SELECT version_num FROM public.alembic_version")) == "20261002_0006"
        assert s.scalar(text("SELECT to_regclass('public.job_journal')")) == "job_journal"
    # Verify the frozen job migration itself, then restore the accepted release
    # schema before applying its additional production privilege requirements.
    command.upgrade(db["config"], REQUIRED_MIGRATION)
    db["app"].assert_application_role()


def budget_for_job(db, repo, run):
    capacity = BudgetCapacity.from_wire(approved_limits())
    suite = uuid4()
    with db["admin"].transaction() as s:
        s.execute(budget_models.suites.insert().values(suite_id=suite,
            ceiling=capacity.ceiling.to_json(), soft_cost_picousd=capacity.soft_cost_picousd,
            duration_seconds=capacity.duration_seconds, concurrency=capacity.concurrency,
            spent=ResourceAmount().to_json(), held=ResourceAmount().to_json()))
    budget = BudgetRepository(db["app"], suite, repo.user_id, repo.project_id, run.research_id)
    budget.create_account(capacity)
    metadata = dict(kind="model", operation_version="offline-v1", provider="offline",
        model="offline", prompt_version="offline-v1", schema_version="1.0.0", pricing_version="offline-v1")
    attempt = budget.reserve(uuid4(), "b" * 64, ResourceAmount(requests=1, tokens=100), metadata)
    return budget, attempt


def test_unknown_budget_attempt_holds_recovery_until_known_settlement(postgres_database):
    db = postgres_database
    repo, run, _, job, _ = enqueue(db)
    _, token = claim(repo, job, seconds=1)
    repo.advance(run.research_id, job.job_id, token, 4)
    budget, attempt = budget_for_job(db, repo, run)
    assert budget.dispatch(attempt.attempt_id).dispatch_permitted
    budget.mark_unknown(attempt.attempt_id)
    with pytest.raises(JobConflict):
        repo.finish(run.research_id, job.job_id, token, succeeded=True)
    time.sleep(1.05)
    held = repo.recover(run.research_id, job.job_id).job
    assert held.state == "held_unknown" and held.checkpoint == 4 and held.attempts == 1
    assert not repo.claim(run.research_id, job.job_id, uuid4()).permitted
    assert not repo.recover(run.research_id, job.job_id).permitted
    assert not budget.dispatch(attempt.attempt_id).dispatch_permitted
    assert budget.snapshot()["held"]["requests"] == 1
    budget.settle(attempt.attempt_id, ResourceAmount(requests=1, tokens=80),
        dict(response_id="offline-known", model_version="offline", usage_version="offline-v1"))
    recovered = repo.recover(run.research_id, job.job_id).job
    assert recovered.state == "queued" and recovered.checkpoint == 4
    current, _ = claim(repo, recovered)
    assert current.fence == 2 and budget.snapshot()["spent"]["requests"] == 1


def test_cancellation_never_releases_unknown_budget_hold(postgres_database):
    db = postgres_database
    repo, run, _, job, _ = enqueue(db)
    claim(repo, job)
    budget, attempt = budget_for_job(db, repo, run)
    budget.dispatch(attempt.attempt_id)
    budget.mark_unknown(attempt.attempt_id)
    repo.cancel(run.research_id, job.job_id)
    assert repo.get_job(run.research_id, job.job_id).state == "cancelled"
    assert budget.snapshot()["held"]["requests"] == 1
    assert not budget.dispatch(attempt.attempt_id).dispatch_permitted


def test_waiting_worker_checks_fresh_clock_after_job_lock(postgres_database):
    db = postgres_database
    repo, run, _, job, _ = enqueue(db)
    _, token = claim(repo, job, seconds=1)
    ready, release = Event(), Event()

    def hold():
        with db["admin"].transaction() as s:
            s.execute(select(tables.jobs).where(tables.jobs.c.job_id == job.job_id).with_for_update())
            ready.set()
            assert release.wait(timeout=5)

    def advance():
        separate = Database(db["app"].engine.url.render_as_string(hide_password=False))
        try:
            worker = JobRepository(separate, repo.user_id, repo.project_id)
            return worker.advance(run.research_id, job.job_id, token, 10)
        finally:
            separate.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        holding = pool.submit(hold)
        assert ready.wait(timeout=3)
        waiting = pool.submit(advance)
        try:
            time.sleep(1.1)
            assert not waiting.done()
        finally:
            release.set()
        holding.result(timeout=3)
        with pytest.raises(JobLeaseLost):
            waiting.result(timeout=3)
    assert repo.get_job(run.research_id, job.job_id).checkpoint == 0


def test_fresh_process_reads_durable_checkpoint_and_terminal_replay(postgres_database):
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys

    db = postgres_database
    repo, run, request, job, _ = enqueue(db)
    _, token = claim(repo, job)
    repo.advance(run.research_id, job.job_id, token, 11)
    repo.cancel(run.research_id, job.job_id)
    code = """import json,os,sys
from uuid import UUID
from app.db.engine import Database
from app.db.job_repository import JobRepository
v=json.load(sys.stdin);d=Database(os.environ['JOB_FIXTURE_DSN'])
r=JobRepository(d,UUID(v['user']),UUID(v['project']))
j=r.get_job(UUID(v['research']),UUID(v['job']))
reply=r.claim(j.research_id,j.job_id,UUID(v['owner']))
print(json.dumps({'pid':os.getpid(),'state':j.state,'checkpoint':j.checkpoint,'permit':reply.permitted}))
d.close()
"""
    process = subprocess.run([sys.executable, "-c", code], text=True, capture_output=True,
        timeout=15, input=json.dumps(dict(user=str(repo.user_id), project=str(repo.project_id),
            research=str(run.research_id), job=str(job.job_id), owner=str(uuid4()))),
        env={"PATH": os.environ["PATH"], "PYTHONPATH": str(Path(__file__).parents[1]),
            "PYTHONDONTWRITEBYTECODE": "1", "JOB_FIXTURE_DSN": db["app"].engine.url.render_as_string(hide_password=False)})
    assert process.returncode == 0, "Independent recovery process failed"
    result = json.loads(process.stdout)
    assert result["pid"] != os.getpid() and result["state"] == "cancelled"
    assert result["checkpoint"] == 11 and not result["permit"]


def test_new_enqueue_refuses_stale_brief_and_native_unapproved_tuple(postgres_database):
    db = postgres_database
    repo, run, request, _ = setup_job(db)
    brief = repo.get_brief(run.research_id, run.brief_id, run.brief_version)
    repo.append_brief(run.research_id, brief.content, status="confirmed")
    with pytest.raises(JobConflict):
        repo.enqueue(run.research_id, request)
    values = request.model_dump()
    values.update(user_id=repo.user_id, project_id=repo.project_id,
        research_id=run.research_id, job_id=uuid4(), plan_fingerprint="c" * 64)
    with pytest.raises(DBAPIError), db["app"].transaction(repo.user_id) as s:
        s.execute(tables.jobs.insert().values(**values))
    with pytest.raises(DBAPIError), db["app"].transaction() as s:
        s.execute(tables.jobs.insert().values(**values))


def test_replayed_alias_key_cannot_be_reused_for_another_run(postgres_database):
    repo, run, request, job, _ = enqueue(postgres_database)
    alias = request.model_copy(update={"request_key": uuid4()})
    repo.enqueue(run.research_id, alias)
    plan = repo.get_plan(run.research_id, run.research_plan_id, run.plan_version)
    research = repo.create_research(plan.brief.original_idea)
    brief = repo.append_brief(research, plan.brief, status="confirmed")
    drafted = repo.append_plan(research, brief.brief_id, brief.brief_version,
        research_mode=plan.research_mode, intents=plan.intents, source_plan=plan.source_plan,
        query_plan=plan.query_plan, budget=plan.budget, known_unknowns=plan.known_unknowns)
    approved = repo.approve_plan(research, drafted.research_plan_id, drafted.plan_version, drafted.plan_fingerprint)
    body = run.model_dump(mode="json")
    body.update(research_id=str(research), brief_id=str(brief.brief_id), brief_version=brief.brief_version,
        research_plan_id=str(approved.research_plan_id), plan_version=approved.plan_version,
        plan_fingerprint=approved.plan_fingerprint, created_at=datetime.now(timezone.utc).isoformat())
    body["versions"].update(brief=brief.brief_version, plan=approved.plan_version)
    new_run = wire.ResearchRun.model_validate(body)
    with repo.transaction(research) as writer:
        writer.put_run(new_run)
    changed = alias.model_copy(update={k: getattr(new_run, k) for k in (
        "research_plan_id", "plan_version", "plan_fingerprint", "brief_id", "brief_version")})
    with pytest.raises(JobConflict):
        repo.enqueue(research, changed)
    with pytest.raises(RecordNotFound):
        repo.get_job(research)
    assert repo.get_job(run.research_id, job.job_id).state == "queued"


def test_cancel_and_claim_race_serializes_with_no_post_cancel_lease(postgres_database):
    db = postgres_database
    repo, run, _, job, _ = enqueue(db)
    barrier = Barrier(2)

    def perform(cancel):
        separate = Database(db["app"].engine.url.render_as_string(hide_password=False))
        try:
            worker = JobRepository(separate, repo.user_id, repo.project_id)
            barrier.wait(timeout=4)
            return worker.cancel(run.research_id, job.job_id) if cancel else worker.claim(run.research_id, job.job_id, uuid4())
        finally:
            separate.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(perform, [False, True]))
    final = repo.get_job(run.research_id, job.job_id)
    assert final.state == "cancelled" and final.lease_owner is None
    assert not repo.claim(run.research_id, job.job_id, uuid4()).permitted
    assert repo.pending_deliveries(run.research_id, job.job_id) == []
    if replies[0].permitted:
        stale = LeaseToken(owner=replies[0].job.lease_owner, fence=replies[0].job.fence)
        with pytest.raises(JobLeaseLost):
            repo.dispatch_guard(run.research_id, job.job_id, stale)


def test_corrupted_restored_job_selection_is_rejected_on_read_and_replay(postgres_database):
    db = postgres_database
    repo, run, request, job, _ = enqueue(db)
    plan = repo.get_plan(run.research_id, run.research_plan_id, run.plan_version)
    drafted = repo.append_plan(run.research_id, plan.brief_id, plan.brief_version,
        research_mode=plan.research_mode, intents=plan.intents, source_plan=plan.source_plan,
        query_plan=plan.query_plan, budget=plan.budget, known_unknowns=plan.known_unknowns)
    approved = repo.approve_plan(run.research_id, drafted.research_plan_id, drafted.plan_version, drafted.plan_fingerprint)
    # Model a bad privileged restore using this test's disposable database only.
    # Both tuples independently satisfy relational FKs; the run selection differs.
    with db["admin"].transaction() as s:
        s.execute(text("ALTER TABLE public.research_jobs DISABLE TRIGGER job_guard"))
        s.execute(text("ALTER TABLE public.research_jobs DISABLE TRIGGER job_append"))
        s.execute(tables.jobs.update().where(tables.jobs.c.job_id == job.job_id)
            .values(plan_version=approved.plan_version, plan_fingerprint=approved.plan_fingerprint))
        s.execute(text("ALTER TABLE public.research_jobs ENABLE TRIGGER job_guard"))
        s.execute(text("ALTER TABLE public.research_jobs ENABLE TRIGGER job_append"))
    with pytest.raises(StoredSnapshotError, match="selected run"):
        repo.get_job(run.research_id, job.job_id)
    with pytest.raises(StoredSnapshotError, match="selected run"):
        repo.enqueue(run.research_id, request)


@pytest.mark.parametrize("target", ["outbox", "journal"])
@pytest.mark.parametrize("grant_insert", [False, True], ids=["least-privilege", "misgranted-columns"])
def test_application_temp_trigger_cannot_forge_protected_inserts(postgres_database, target, grant_insert):
    db = postgres_database
    repo, run, request, job, _ = enqueue(db)
    repo.enqueue(run.research_id, request.model_copy(update={"request_key": uuid4()}))
    before_job = repo.get_job(run.research_id, job.job_id)
    before_deliveries = repo.pending_deliveries(run.research_id, job.job_id)
    before_journal = repo.journal(run.research_id, job.job_id)
    db["app"].assert_application_role()
    if target == "outbox":
        columns = "delivery_id,user_id,project_id,research_id,job_id,generation,available_at"
        insert = """INSERT INTO public.job_outbox(delivery_id,user_id,project_id,research_id,job_id,generation,available_at)
            SELECT gen_random_uuid(),user_id,project_id,research_id,job_id,journal_seq,available_at
            FROM public.research_jobs WHERE job_id=TG_ARGV[0]::uuid"""
    else:
        columns = "user_id,project_id,research_id,job_id,sequence,event,state,fence,checkpoint,detail"
        insert = """INSERT INTO public.job_journal(user_id,project_id,research_id,job_id,sequence,event,state,fence,checkpoint,detail)
            SELECT user_id,project_id,research_id,job_id,journal_seq+100,'forged',state,fence,checkpoint,'{}'::jsonb
            FROM public.research_jobs WHERE job_id=TG_ARGV[0]::uuid"""
    if grant_insert:
        # A privileged misconfiguration after startup must not turn nesting
        # depth into writer authority. Root separately owns startup role checks.
        quote = db["admin"].engine.dialect.identifier_preparer.quote
        with db["admin"].transaction() as s:
            s.execute(text(f"GRANT INSERT({columns}) ON public.job_{target} TO {quote(db['role'])}"))
    with pytest.raises(DBAPIError) as denied, db["app"].transaction(repo.user_id) as s:
        s.execute(text("CREATE TEMP TABLE forged_trigger_parent(id integer) ON COMMIT DROP"))
        s.execute(text("CREATE FUNCTION pg_temp.forge_job_rows() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            + insert + ";RETURN NEW;END $$"))
        s.execute(text("CREATE TRIGGER forge_outer AFTER INSERT ON forged_trigger_parent FOR EACH ROW EXECUTE FUNCTION pg_temp.forge_job_rows('" + str(job.job_id) + "')"))
        s.execute(text("INSERT INTO forged_trigger_parent VALUES(1)"))
    assert getattr(denied.value.orig, "sqlstate", None) == ("23514" if grant_insert else "42501")
    assert repo.get_job(run.research_id, job.job_id) == before_job
    assert repo.pending_deliveries(run.research_id, job.job_id) == before_deliveries
    assert repo.journal(run.research_id, job.job_id) == before_journal


def test_application_cannot_bind_privileged_append_trigger_to_temp_table(postgres_database):
    db = postgres_database
    repo, run, _, job, _ = enqueue(db)
    with pytest.raises(DBAPIError) as denied, db["app"].transaction(repo.user_id) as s:
        s.execute(text("CREATE TEMP TABLE forged_append_parent(id integer) ON COMMIT DROP"))
        s.execute(text("CREATE TRIGGER forged_append AFTER INSERT ON forged_append_parent FOR EACH ROW EXECUTE FUNCTION public.demandrift_job_append()"))
    assert getattr(denied.value.orig, "sqlstate", None) == "42501"
    assert len(repo.journal(run.research_id, job.job_id)) == 1


def test_journal_failure_rolls_back_lease_and_generated_outbox(postgres_database):
    db = postgres_database
    repo, run, _, job, _ = enqueue(db)
    before = repo.get_job(run.research_id, job.job_id)
    deliveries = repo.pending_deliveries(run.research_id, job.job_id)
    with db["admin"].transaction() as s:
        s.execute(text("ALTER TABLE public.job_journal ADD CONSTRAINT reject_test_claim CHECK(event<>'claim')"))
    with pytest.raises(JobConflict):
        repo.claim(run.research_id, job.job_id, uuid4())
    assert repo.get_job(run.research_id, job.job_id) == before
    assert len(repo.journal(run.research_id, job.job_id)) == 1
    assert repo.pending_deliveries(run.research_id, job.job_id) == deliveries
