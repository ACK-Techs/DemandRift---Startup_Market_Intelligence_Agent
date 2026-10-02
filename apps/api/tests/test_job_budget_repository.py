"""Real disposable PostgreSQL coupled admission; no provider or real Suite use."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
import json
from pathlib import Path
from threading import Barrier, Event
import time
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.engine import make_url

from app.budget_contract import BudgetCapacity, ResourceAmount
from app.contracts import HumanBriefPatch, ResearchCreate
from app.db import budget_models as tables
from app.db.budget_repository import BudgetRepository
from app.db.engine import Database
from app.db.job_budget_repository import JobBudgetRepository
from app.db.models import BriefRecord, ProjectRecord, UserRecord
from app.db.preparation_http_repository import PreparationHttpRepository
from app.db.preparation_repository import RecordNotFound, StoredSnapshotError
from app.job_budget_contract import AdmissionConflict, AdmissionContext, AdmissionStorageError, AdmissionUnavailable
from test_budget_contract import approved_limits
from test_job_repository import claim, enqueue

pytestmark = pytest.mark.postgres
META = {"kind": "model", "operation_version": "offline-v1", "provider": "offline",
        "model": "offline", "prompt_version": "v1", "schema_version": "1.0.0", "pricing_version": "v1"}
RECEIPT = {"response_id": "offline", "model_version": "offline", "usage_version": "v1"}
AMOUNT = ResourceAmount(requests=1, bytes=1000, tokens=100, cost_picousd=100)


@pytest.fixture
def admission_database(monkeypatch):
    """Own head008 database; explicitly distinct from Root's head007 runtime gate."""
    if os.environ.get("DEMANDRIFT_DB_TESTS") != "1":
        pytest.skip("Explicit native PostgreSQL gate required")
    raw = os.environ.get("DEMANDRIFT_TEST_ADMIN_URL")
    if not raw:
        pytest.fail("Native PostgreSQL admin URL required")
    url = make_url(raw)
    assert url.drivername == "postgresql+psycopg"
    suffix = uuid4().hex[:12]
    name, role = f"demandrift_admit_{suffix}", f"demandrift_admitapp_{suffix}"
    server = create_engine(url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    quote = server.dialect.identifier_preparer.quote
    admin_url = url.set(database=name)
    app_url = admin_url.set(username=role, password="ephemeral-native-only")
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    admin = app = None
    try:
        with server.connect() as connection:
            connection.exec_driver_sql(f"CREATE ROLE {quote(role)} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD 'ephemeral-native-only'")
            connection.exec_driver_sql(f"CREATE DATABASE {quote(name)}")
        monkeypatch.setenv("DATABASE_URL", admin_url.render_as_string(hide_password=False))
        monkeypatch.setenv("DATABASE_APP_ROLE", role)
        command.upgrade(config, "20261002_0008")
        admin = Database(admin_url.render_as_string(hide_password=False))
        app = Database(app_url.render_as_string(hide_password=False), pool_size=1)
        with app.transaction() as session:
            assert session.scalar(text("SELECT NOT (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb) FROM pg_roles WHERE rolname=current_user"))
            assert not session.scalar(text("SELECT has_table_privilege(current_user,'public.budget_suites','SELECT')"))
            assert not session.scalar(text("SELECT has_table_privilege(current_user,'public.budget_attempts','INSERT,UPDATE,DELETE')"))
        # The shared production startup/head/catalog tests are Root-owned and
        # still head007 at author time; do not call them a production-role gate.
        yield {"admin": admin, "app": app, "config": config, "role": role, "name": name}
    finally:
        if app:
            app.close()
        if admin:
            admin.close()
        with server.connect() as connection:
            connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {quote(name)} WITH (FORCE)")
            connection.exec_driver_sql(f"DROP ROLE IF EXISTS {quote(role)}")
        server.dispose()


def preparation(db, label="A"):
    user = uuid4()
    with db["admin"].transaction() as session:
        session.add(UserRecord(user_id=user, email=f"{user}@fixture.invalid", password_hash="fixture-only"))
    project = PreparationHttpRepository.create_project(db["app"], user, f"Preparation {label}")
    prep = PreparationHttpRepository(db["app"], user, project.project_id)
    receipt, _ = prep.create_preparation(uuid4(), ResearchCreate(original_idea="  Öğrenme 🙂 e\u0301\n  "))
    return prep, receipt.brief


def account(db, user, project, research, *, suite=None, capacity=None):
    capacity = capacity or BudgetCapacity.from_wire(approved_limits())
    if suite is None:
        suite = uuid4()
        with db["admin"].transaction() as session:
            session.execute(tables.suites.insert().values(suite_id=suite,
                ceiling=capacity.ceiling.to_json(), soft_cost_picousd=capacity.soft_cost_picousd,
                duration_seconds=capacity.duration_seconds, concurrency=capacity.concurrency,
                spent=ResourceAmount().to_json(), held=ResourceAmount().to_json()))
    ledger = BudgetRepository(db["app"], suite, user, project, research)
    ledger.create_account(capacity)
    producer = JobBudgetRepository(db["app"], suite, user, project, research)
    return ledger, producer


def preparation_admission(db, label="A", **kwargs):
    prep, brief = preparation(db, label)
    ledger, producer = account(db, prep.user_id, prep.project_id, brief.research_id, **kwargs)
    context = AdmissionContext("preparation", brief.brief_id, brief.brief_version)
    return prep, brief, ledger, producer, context


def job_admission(db, label="A", *, seconds=30, **kwargs):
    jobs, run, _, job, data = enqueue(db, label=label)
    job, token = claim(jobs, job, seconds=seconds)
    ledger, producer = account(db, jobs.user_id, jobs.project_id, run.research_id, **kwargs)
    context = AdmissionContext("job", job.brief_id, job.brief_version, job.job_id, token.owner, token.fence)
    return jobs, run, job, data, ledger, producer, context


def admit(producer, context, attempt=None, **kwargs):
    return producer.admit(context, attempt_id=attempt or uuid4(), fingerprint=kwargs.pop("fingerprint", "a" * 64),
                          reserved=kwargs.pop("reserved", AMOUNT), metadata=kwargs.pop("metadata", META),
                          model_timeout_ms=kwargs.pop("model_timeout_ms", 30000), **kwargs)


def snapshot(db, producer):
    with db["admin"].transaction() as session:
        suite = dict(session.execute(select(tables.suites).where(tables.suites.c.suite_id == producer.suite_id)).mappings().one())
        attempts = [dict(row) for row in session.execute(select(tables.attempts).where(
            tables.attempts.c.research_id == producer.research_id)).mappings()]
        return suite, attempts


def test_prejob_exact_brief_fresh_permit_and_historical_replay(admission_database):
    db = admission_database
    prep, brief, ledger, producer, context = preparation_admission(db)
    deadline = producer.remaining(context, model_timeout_ms=30000)
    assert 0 < deadline.remaining_ms <= 30000
    assert snapshot(db, producer)[0]["started_at"] is None
    with db["app"].transaction(prep.user_id) as session:
        assert session.scalar(text("SELECT count(*) FROM public.research_plans")) == 0
        assert session.scalar(text("SELECT count(*) FROM public.research_runs")) == 0
        assert session.scalar(text("SELECT count(*) FROM public.research_jobs")) == 0
    receipt = admit(producer, context)
    assert receipt.dispatch_permitted and receipt.context == context
    assert receipt.reserved == AMOUNT
    assert snapshot(db, producer)[0]["active"] == 1
    prep.revise(brief.research_id, uuid4(), HumanBriefPatch(expected_brief_version=1, target_user="human"))
    assert not admit(producer, context, receipt.attempt_id).dispatch_permitted
    with pytest.raises(AdmissionConflict):
        admit(producer, context, receipt.attempt_id, fingerprint="b" * 64)
    with pytest.raises(AdmissionConflict):
        admit(producer, context, receipt.attempt_id, model_timeout_ms=29999)
    ledger.mark_unknown(receipt.attempt_id)
    assert not admit(producer, context, receipt.attempt_id).dispatch_permitted
    ledger.settle(receipt.attempt_id, ResourceAmount(requests=1, bytes=50, tokens=5, cost_picousd=50), RECEIPT)
    assert not admit(producer, context, receipt.attempt_id).dispatch_permitted
    suite, _ = snapshot(db, producer)
    assert suite["active"] == 0 and suite["spent"]["requests"] == 1


def test_job_exact_binding_cancel_then_replay_is_read_only(admission_database):
    db = admission_database
    jobs, run, job, _, ledger, producer, context = job_admission(db)
    receipt = admit(producer, context)
    assert receipt.dispatch_permitted and receipt.deadline_at <= job.lease_until
    assert jobs.journal(run.research_id, job.job_id)[-1]["event"] == "dispatch_guard"
    jobs.cancel(run.research_id, job.job_id)
    assert not admit(producer, context, receipt.attempt_id).dispatch_permitted
    ledger.mark_unknown(receipt.attempt_id)
    ledger.cancel_account()
    suite, attempts = snapshot(db, producer)
    assert suite["held"] == AMOUNT.to_json() and suite["active"] == 1
    assert attempts[0]["state"] == "held_unknown"
    with pytest.raises((AdmissionUnavailable, AdmissionConflict)):
        admit(producer, context)
    ledger.settle(receipt.attempt_id, ResourceAmount(requests=1, tokens=7), RECEIPT)
    assert snapshot(db, producer)[0]["spent"]["requests"] == 1
    assert not admit(producer, context, receipt.attempt_id).dispatch_permitted


def test_latest_brief_job_presence_and_archived_mutation_deny(admission_database):
    db = admission_database
    prep, brief, _, producer, context = preparation_admission(db)
    prep.revise(brief.research_id, uuid4(), HumanBriefPatch(expected_brief_version=1, product_type="human"))
    with pytest.raises(AdmissionConflict):
        admit(producer, context)
    with db["admin"].transaction() as session:
        session.execute(update(ProjectRecord).where(ProjectRecord.project_id == prep.project_id)
                        .values(archived_at=datetime.now(timezone.utc)))
    with pytest.raises(RecordNotFound):
        admit(producer, replace(context, brief_version=2))
    _, _, _, _, _, job_producer, job_context = job_admission(db, label="JOB")
    with pytest.raises(AdmissionUnavailable):
        admit(job_producer, AdmissionContext("preparation", job_context.brief_id, job_context.brief_version))
    assert not snapshot(db, producer)[1] and not snapshot(db, job_producer)[1]


def test_newer_awaiting_plan_is_current_and_native_direct_rpc_denies(admission_database):
    db = admission_database
    jobs, run, _, _, _, producer, context = job_admission(db)
    plan = jobs.get_plan(run.research_id, run.research_plan_id, run.plan_version)
    jobs.append_plan(run.research_id, plan.brief_id, plan.brief_version, research_mode=plan.research_mode,
                     intents=plan.intents, source_plan=plan.source_plan, query_plan=plan.query_plan,
                     budget=plan.budget, known_unknowns=plan.known_unknowns)
    with pytest.raises(AdmissionConflict):
        admit(producer, context)
    # Direct scoped RPC bypasses Python selected-snapshot checks, still rejects.
    with pytest.raises(Exception) as caught:
        with db["app"].transaction(producer.user_id) as session:
            producer._call(session, "admit", context, 30000, attempt=uuid4(), fingerprint="a" * 64,
                           reserved=AMOUNT, metadata=META)
    assert getattr(caught.value.orig, "sqlstate", None) == "23514"
    assert not snapshot(db, producer)[1]


def test_stale_fence_cancel_first_and_expiry_no_new_dispatch(admission_database):
    db = admission_database
    jobs, run, job, _, _, producer, context = job_admission(db, seconds=1)
    with pytest.raises(AdmissionUnavailable):
        admit(producer, replace(context, fence=context.fence + 1))
    time.sleep(1.05)
    with pytest.raises(AdmissionUnavailable):
        admit(producer, context)
    job = jobs.recover(run.research_id, job.job_id).job
    job, token = claim(jobs, job)
    current = replace(context, fence=token.fence, lease_owner=token.owner)
    jobs.cancel(run.research_id, job.job_id)
    with pytest.raises(AdmissionUnavailable):
        admit(producer, current)
    assert snapshot(db, producer)[0]["started_at"] is None


def test_reserve_dispatch_failure_rolls_back_clocks_binding_and_job_journal(admission_database):
    db = admission_database
    jobs, run, job, _, _, producer, context = job_admission(db)
    before = len(jobs.journal(run.research_id, job.job_id))
    # Native fixture fault after reserve and binding; not a production bypass.
    with db["admin"].transaction() as session:
        session.execute(text("""CREATE FUNCTION public.fixture_reject_dispatch() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN IF NEW.state='dispatched' THEN RAISE EXCEPTION 'fixture interruption' USING ERRCODE='23514'; END IF; RETURN NEW; END $$"""))
        session.execute(text("CREATE TRIGGER z_fixture_reject BEFORE UPDATE ON public.budget_attempts FOR EACH ROW EXECUTE FUNCTION public.fixture_reject_dispatch()"))
    with pytest.raises(AdmissionConflict):
        admit(producer, context)
    suite, attempts = snapshot(db, producer)
    assert not attempts and suite["started_at"] is None and suite["active"] == 0
    assert suite["held"] == ResourceAmount().to_json()
    assert len(jobs.journal(run.research_id, job.job_id)) == before


def test_canonical_corruption_cannot_return_send_permit(admission_database):
    db = admission_database
    _, brief, _, producer, context = preparation_admission(db)
    with db["admin"].transaction() as session:
        session.execute(text("ALTER TABLE public.idea_briefs DISABLE TRIGGER immutable_snapshot"))
        payload = session.scalar(select(BriefRecord.payload).where(BriefRecord.brief_id == brief.brief_id))
        payload["content"]["clarity_status"] = "corrupt"
        session.execute(update(BriefRecord).where(BriefRecord.brief_id == brief.brief_id).values(payload=payload))
        session.execute(text("ALTER TABLE public.idea_briefs ENABLE TRIGGER immutable_snapshot"))
    with pytest.raises(StoredSnapshotError):
        admit(producer, context)
    assert not snapshot(db, producer)[1]


def test_two_native_connections_one_fresh_permit_and_finite_conflict(admission_database):
    db = admission_database
    _, _, _, producer, context = preparation_admission(db)
    parallel = Database(db["app"].engine.url.render_as_string(hide_password=False), pool_size=2)
    caller = JobBudgetRepository(parallel, producer.suite_id, producer.user_id, producer.project_id, producer.research_id)
    barrier = Barrier(2)
    attempt = uuid4()
    def run():
        barrier.wait(timeout=5)
        return admit(caller, context, attempt)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run) for _ in range(2)]
            receipts = [future.result(timeout=10) for future in futures]
        assert sum(r.dispatch_permitted for r in receipts) == 1
        assert len(snapshot(db, producer)[1]) == 1
    finally:
        parallel.close()


def test_scoped_deadlines_min_global_account_model_job_and_lock_wait(admission_database):
    db = admission_database
    _, _, ledger, producer, context = preparation_admission(db)
    with db["admin"].transaction() as session:
        session.execute(update(tables.suites).where(tables.suites.c.suite_id == producer.suite_id)
                        .values(started_at=datetime.now(timezone.utc) - timedelta(seconds=1799)))
    deadline = producer.remaining(context, model_timeout_ms=30000)
    assert 0 < deadline.remaining_ms <= 1000
    anchor = time.monotonic()
    receipt = admit(producer, context, outer_monotonic_deadline=anchor + .2)
    assert receipt.absolute_monotonic_deadline <= anchor + .2
    ledger.mark_unknown(receipt.attempt_id)
    time.sleep(1.05)
    assert not admit(producer, context, receipt.attempt_id).dispatch_permitted
    with pytest.raises(AdmissionUnavailable):
        producer.remaining(context, model_timeout_ms=30000)
    ledger.settle(receipt.attempt_id, ResourceAmount(requests=1), RECEIPT)
    # A second scope with account shorter than suite, and model shorter than both.
    capacity = replace(BudgetCapacity.from_wire(approved_limits()), duration_seconds=2)
    _, _, _, second, second_context = preparation_admission(db, label="SHORT", capacity=capacity)
    assert second.remaining(second_context, model_timeout_ms=100).remaining_ms <= 100
    with db["admin"].transaction() as session:
        session.execute(update(tables.accounts).where(tables.accounts.c.research_id == second.research_id)
                        .values(started_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    assert second.remaining(second_context, model_timeout_ms=30000).remaining_ms <= 1000
    # Wait behind native suite lock until the account deadline expires.
    locked, release = Event(), Event()
    def hold():
        with db["admin"].transaction() as session:
            session.execute(select(tables.suites).where(tables.suites.c.suite_id == second.suite_id).with_for_update())
            locked.set()
            release.wait(timeout=3)
    with ThreadPoolExecutor(max_workers=2) as pool:
        holder = pool.submit(hold)
        assert locked.wait(timeout=3)
        waiter = pool.submit(lambda: admit(second, second_context))
        time.sleep(1.1)
        release.set()
        holder.result(timeout=5)
        with pytest.raises(AdmissionUnavailable):
            waiter.result(timeout=5)
    assert snapshot(db, second)[0]["started_at"] is None and not snapshot(db, second)[1]


def test_shared_suite_concurrency_two_and_unknown_never_ttl_refunds(admission_database):
    db = admission_database
    _, _, first_ledger, first, first_context = preparation_admission(db)
    _, _, second_ledger, second, second_context = preparation_admission(db, label="B", suite=first.suite_id)
    _, _, _, third, third_context = preparation_admission(db, label="C", suite=first.suite_id)
    a, b = admit(first, first_context), admit(second, second_context)
    with pytest.raises(AdmissionUnavailable):
        admit(third, third_context)
    first_ledger.mark_unknown(a.attempt_id)
    first_ledger.cancel_account()
    assert snapshot(db, first)[0]["active"] == 2
    with pytest.raises(AdmissionUnavailable):
        admit(third, third_context)
    second_ledger.settle(b.attempt_id, ResourceAmount(requests=1), RECEIPT)
    assert admit(third, third_context).dispatch_permitted
    assert snapshot(db, first)[1][0]["state"] == "held_unknown"


def test_account_cancel_contention_finishes_without_reverse_lock_deadlock(admission_database, tmp_path):
    db = admission_database
    _, _, ledger, producer, context = preparation_admission(db)
    locked, release = Event(), Event()
    def hold_account():
        with db["admin"].transaction() as session:
            session.execute(select(tables.suites).where(tables.suites.c.suite_id == producer.suite_id).with_for_update())
            locked.set()
            release.wait(timeout=3)
    parallel = Database(db["app"].engine.url.render_as_string(hide_password=False), pool_size=2)
    other_ledger = BudgetRepository(parallel, producer.suite_id, producer.user_id, producer.project_id, producer.research_id)
    caller = JobBudgetRepository(parallel, producer.suite_id, producer.user_id, producer.project_id, producer.research_id)
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            holder = pool.submit(hold_account)
            assert locked.wait(timeout=3)
            admission = pool.submit(lambda: admit(caller, context))
            cancellation = pool.submit(other_ledger.cancel_account)
            time.sleep(.1)
            release.set()
            holder.result(timeout=5)
            time.sleep(.15)
            with db["admin"].transaction() as session:
                locks = [dict(row) for row in session.execute(text("""SELECT l.pid,l.locktype,c.relname,l.mode,l.granted,l.transactionid,
                  a.wait_event,a.query FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid
                  LEFT JOIN pg_class c ON c.oid=l.relation WHERE a.datname=:name AND a.pid<>pg_backend_pid()
                  ORDER BY l.pid,l.locktype,c.relname,l.mode"""), {"name": db["name"]}).mappings()]
            (tmp_path / "contention-locks.json").write_text(json.dumps(locks, indent=2, default=str))
            try:
                result = admission.result(timeout=8)
                assert result.dispatch_permitted
            except AdmissionUnavailable:
                pass
            except AdmissionStorageError as error:
                native = error.__context__.orig
                pytest.fail(f"Native contention failed {native.sqlstate}: {native.diag.message_detail}; {native.diag.context}")
            assert cancellation.result(timeout=8) is None
        assert ledger.snapshot()["cancelled_at"] is not None
    finally:
        parallel.close()


def test_legacy_dispatch_contention_and_reserved_attachment_never_deadlock(admission_database):
    db = admission_database
    _, _, ledger, producer, context = preparation_admission(db)
    attempt = uuid4()
    ledger.reserve(attempt, "a" * 64, AMOUNT, META)
    locked, release = Event(), Event()
    # Use a single native legacy RPC Session instead of a nested public call;
    # the application has no SELECT/lock grant on Suite, and no direct ledger DML.
    def native_legacy():
        with db["admin"].transaction(producer.user_id) as session:
            session.execute(select(tables.suites).where(tables.suites.c.suite_id == producer.suite_id).with_for_update())
            locked.set()
            release.wait(timeout=3)
            return session.scalar(text("""SELECT public.demandrift_budget_operate('dispatch',:suite,:owner,:project,:research,:attempt,
                           NULL,NULL,NULL,NULL,NULL)"""),
                          {"suite": producer.suite_id, "owner": producer.user_id, "project": producer.project_id,
                           "research": producer.research_id, "attempt": attempt})
    with ThreadPoolExecutor(max_workers=2) as pool:
        old = pool.submit(native_legacy)
        assert locked.wait(timeout=3)
        new = pool.submit(lambda: admit(producer, context, attempt))
        time.sleep(.1)
        release.set()
        with pytest.raises(Exception) as error:
            old.result(timeout=5)
        assert getattr(error.value.orig, "sqlstate", None) == "23514"
        assert new.result(timeout=5).dispatch_permitted
    assert not admit(producer, context, attempt).dispatch_permitted
    assert snapshot(db, producer)[0]["active"] == 1


@pytest.mark.parametrize("mutation", ["cancel", "revision", "archive"])
def test_native_scope_mutation_first_serializes_and_denies_admission(admission_database, mutation):
    db = admission_database
    if mutation == "cancel":
        _, _, job, _, _, producer, context = job_admission(db)
    else:
        _, brief, _, producer, context = preparation_admission(db)
    locked, release = Event(), Event()
    def mutate():
        with db["app"].transaction(producer.user_id) as session:
            session.scalar(select(ProjectRecord).where(ProjectRecord.project_id == producer.project_id).with_for_update())
            locked.set()
            release.wait(timeout=3)
            if mutation == "cancel":
                session.execute(text("""UPDATE public.research_jobs SET command='{"op":"cancel"}'::jsonb WHERE job_id=:job"""), {"job": job.job_id})
            elif mutation == "archive":
                session.execute(update(ProjectRecord).where(ProjectRecord.project_id == producer.project_id)
                                .values(archived_at=datetime.now(timezone.utc)))
            else:
                body = brief.model_dump(mode="json")
                body["brief_version"] = 2
                body["versions"]["brief"] = 2
                session.add(BriefRecord(user_id=producer.user_id, project_id=producer.project_id,
                    research_id=producer.research_id, brief_id=brief.brief_id, brief_version=2,
                    created_at=brief.created_at, payload=body))
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(mutate)
        assert locked.wait(timeout=3)
        second = pool.submit(lambda: admit(producer, context))
        time.sleep(.1)
        release.set()
        first.result(timeout=5)
        with pytest.raises((AdmissionConflict, AdmissionUnavailable, RecordNotFound)):
            second.result(timeout=5)
    suite, rows = snapshot(db, producer)
    assert suite["started_at"] is None and not rows
