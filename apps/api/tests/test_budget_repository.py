"""Real PostgreSQL shared accounting, durable state and restricted native writes."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4
import time

from alembic import command
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from app.budget_contract import BudgetCapacity, ResourceAmount
from app.db import budget_models as tables
from app.db.budget_repository import BudgetRepository, BudgetConflict, BudgetExhausted
from app.db.engine import Database
from app.db.preparation_repository import RecordNotFound
from test_budget_contract import approved_limits
from test_postgres_foundation import seed, brief, brief_record
from native_budget_dispatch import dispatch as dispatch_budget_attempt
from app.db.migration_head import REQUIRED_MIGRATION

pytestmark = pytest.mark.postgres
META = {
    "kind": "model",
    "operation_version": "test-v1",
    "provider": "offline",
    "model": "offline",
    "prompt_version": "test-v1",
    "schema_version": "1.0.0",
    "pricing_version": "offline-v1",
}
RECEIPT = {
    "response_id": "offline-receipt",
    "model_version": "offline",
    "usage_version": "test-v1",
}
FINGERPRINT = "a" * 64


def setup_ledger(db, *, capacity=None):
    users, projects, researches = seed(db["admin"])
    # Head008 preparation admission requires real immutable briefs even for
    # these historic offline accounting controls. No native dispatch bypass.
    with db["admin"].transaction() as session:
        for index, research in enumerate(researches):
            session.add(brief_record(brief(users[1] if index == 2 else users[0], projects[index], research)))
    capacity = capacity or BudgetCapacity.from_wire(approved_limits())
    suite = uuid4()
    with db["admin"].transaction() as s:
        s.execute(
            tables.suites.insert().values(
                suite_id=suite,
                ceiling=capacity.ceiling.to_json(),
                soft_cost_picousd=capacity.soft_cost_picousd,
                duration_seconds=capacity.duration_seconds,
                concurrency=capacity.concurrency,
                spent=ResourceAmount().to_json(),
                held=ResourceAmount().to_json(),
            )
        )
    repos = [
        BudgetRepository(
            db["app"],
            suite,
            users[1] if i == 2 else users[0],
            projects[i],
            researches[i],
        )
        for i in range(3)
    ]
    for repo in repos:
        repo.create_account(capacity)
    return suite, repos, capacity


def suite_snapshot(db, suite):
    with db["admin"].transaction() as s:
        return dict(
            s.execute(select(tables.suites).where(tables.suites.c.suite_id == suite))
            .mappings()
            .one()
        )


def reserve(repo, amount=None, *, attempt=None, metadata=None):
    return repo.reserve(
        attempt or uuid4(),
        FINGERPRINT,
        amount or ResourceAmount(requests=1),
        {**META, **(metadata or {})},
    )


def test_live_clock_begins_only_once_at_first_committed_dispatch(postgres_database):
    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    repo = repos[0]
    first = reserve(repo, ResourceAmount(requests=1, tokens=10, cost_picousd=250000))
    assert (
        suite_snapshot(db, suite)["started_at"] is None
        and repo.snapshot()["started_at"] is None
    )
    assert dispatch_budget_attempt(repo, first.attempt_id).dispatch_permitted
    started = suite_snapshot(db, suite)["started_at"]
    assert started is not None
    assert not dispatch_budget_attempt(repo, first.attempt_id).dispatch_permitted
    repo.settle(
        first.attempt_id,
        ResourceAmount(requests=1, tokens=1, cost_picousd=250000),
        RECEIPT,
    )
    second = reserve(repos[2])
    assert dispatch_budget_attempt(repos[2], second.attempt_id).dispatch_permitted
    assert suite_snapshot(db, suite)["started_at"] == started
    row = repo.snapshot()
    assert row["spent"]["requests"] == 1 and row["spent"]["cost_picousd"] == 250000
    assert row["held"] == ResourceAmount().to_json() and row["active"] == 0


def test_mixed_owners_and_source_model_attempts_share_global_concurrency(
    postgres_database,
):
    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    one = reserve(repos[0])
    two = reserve(repos[2], metadata={"kind": "source"})
    with pytest.raises(BudgetExhausted):
        reserve(repos[1])
    assert suite_snapshot(db, suite)["active"] == 2
    assert repos[0].cancel_attempt(one.attempt_id).state == "cancelled"
    three = reserve(repos[1])
    assert suite_snapshot(db, suite)["active"] == 2
    assert repos[2].snapshot()["held"]["requests"] == 1
    assert repos[1].cancel_attempt(three.attempt_id).state == "cancelled"
    assert repos[2].cancel_attempt(two.attempt_id).state == "cancelled"
    assert suite_snapshot(db, suite)["held"] == ResourceAmount().to_json()


@pytest.mark.parametrize(
    "dimension", ["requests", "bytes", "pages", "records", "tokens", "cost_picousd"]
)
def test_global_limit_is_enforced_even_when_other_tenant_usage_is_hidden(
    postgres_database, dimension
):
    db = postgres_database
    suite, repos, capacity = setup_ledger(db)
    first = ResourceAmount(
        **{"requests": 1, dimension: getattr(capacity.ceiling, dimension)}
    )
    if dimension == "requests":
        # Each attempt consumes exactly one request, so a one-request suite probes its edge.
        limits = approved_limits()
        limits.max_requests = 1
        suite, repos, capacity = setup_ledger(
            db, capacity=BudgetCapacity.from_wire(limits)
        )
        first = ResourceAmount(requests=1)
    receipt = reserve(repos[0], first)
    dispatch_budget_attempt(repos[0], receipt.attempt_id)
    repos[0].settle(receipt.attempt_id, first, RECEIPT)
    extra = ResourceAmount(**{"requests": 1, dimension: 1})
    with pytest.raises(BudgetExhausted):
        reserve(repos[2], extra)
    assert repos[2].snapshot()["spent"] == ResourceAmount().to_json()
    assert suite_snapshot(db, suite)["spent"] == first.to_json()


def test_concurrent_duplicate_delivery_reserves_and_dispatches_once(postgres_database):
    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    base = repos[0]
    parallel = Database(
        db["app"].engine.url.render_as_string(hide_password=False), pool_size=6
    )
    repo = BudgetRepository(
        parallel, suite, base.user_id, base.project_id, base.research_id
    )
    attempt = uuid4()
    barrier = Barrier(6)

    def submit(_):
        barrier.wait(timeout=10)
        return reserve(repo, attempt=attempt)

    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(submit, range(6)))
        assert {r.attempt_id for r in results} == {attempt}
        assert suite_snapshot(db, suite)["held"]["requests"] == 1
        barrier = Barrier(6)

        def dispatch(_):
            barrier.wait(timeout=10)
            return dispatch_budget_attempt(repo, attempt)

        with ThreadPoolExecutor(max_workers=6) as pool:
            sent = list(pool.map(dispatch, range(6)))
        assert sum(r.dispatch_permitted for r in sent) == 1
        with db["app"].transaction(base.user_id) as s:
            events = (
                s.execute(
                    select(tables.journal.c.next_state).where(
                        tables.journal.c.attempt_id == attempt
                    )
                )
                .scalars()
                .all()
            )
            assert sorted(events) == ["dispatched", "reserved"]
    finally:
        parallel.close()


def test_concurrent_distinct_attempts_cannot_overbook_a_shared_suite(postgres_database):
    db = postgres_database
    suite, bases, _ = setup_ledger(db)
    parallel = Database(
        db["app"].engine.url.render_as_string(hide_password=False), pool_size=6
    )
    repos = [
        BudgetRepository(parallel, suite, b.user_id, b.project_id, b.research_id)
        for b in bases
    ]
    barrier = Barrier(6)

    def submit(i):
        barrier.wait(timeout=10)
        try:
            return reserve(repos[i % 3]).state
        except BudgetExhausted:
            return "refused"

    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(submit, range(6)))
        assert results.count("reserved") == 2 and results.count("refused") == 4
        assert suite_snapshot(db, suite)["held"]["requests"] == 2
    finally:
        parallel.close()


def test_conflicting_replay_and_unauthorized_scope_do_not_touch_counters(
    postgres_database,
):
    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    repo = repos[0]
    first = reserve(repo)
    with pytest.raises(BudgetConflict):
        repo.reserve(first.attempt_id, "b" * 64, first.reserved, META)
    with pytest.raises(BudgetConflict):
        repo.reserve(
            first.attempt_id, FINGERPRINT, ResourceAmount(requests=1, bytes=1), META
        )
    for other in [
        repos[1],
        repos[2],
        BudgetRepository(
            db["app"], suite, repos[2].user_id, repo.project_id, repo.research_id
        ),
    ]:
        with pytest.raises(RecordNotFound):
            dispatch_budget_attempt(other, first.attempt_id)
    assert suite_snapshot(db, suite)["held"]["requests"] == 1
    with db["app"].transaction(repos[2].user_id) as s:
        assert (
            s.execute(
                select(tables.attempts).where(
                    tables.attempts.c.attempt_id == first.attempt_id
                )
            ).first()
            is None
        )


def test_unknown_outcome_holds_capacity_across_new_connection_and_cancellation(
    postgres_database,
):
    db = postgres_database
    suite, repos, capacity = setup_ledger(db)
    repo = repos[0]
    amount = ResourceAmount(requests=1, tokens=120, cost_picousd=1000000)
    first = reserve(repo, amount)
    dispatch_budget_attempt(repo, first.attempt_id)
    assert repo.mark_unknown(first.attempt_id).state == "held_unknown"
    second = reserve(repos[2])
    dispatch_budget_attempt(repos[2], second.attempt_id)
    repo.cancel_account()
    assert repo.cancel_attempt(first.attempt_id).state == "held_unknown"
    repo.create_account(
        capacity
    )  # Identical replay cannot reset cancellation or held usage.
    db["app"].close()
    fresh = Database(db["app"].engine.url.render_as_string(hide_password=False))
    try:
        recovered = BudgetRepository(
            fresh, suite, repo.user_id, repo.project_id, repo.research_id
        )
        assert not dispatch_budget_attempt(recovered, first.attempt_id).dispatch_permitted
        assert (
            recovered.snapshot()["held"] == amount.to_json()
            and recovered.snapshot()["active"] == 1
        )
        with pytest.raises(BudgetExhausted):
            reserve(repos[1])
        known = recovered.settle(
            first.attempt_id,
            ResourceAmount(requests=1, tokens=12, cost_picousd=500000),
            RECEIPT,
        )
        assert (
            known.state == "settled"
            and recovered.snapshot()["cancelled_at"] is not None
        )
        with pytest.raises(BudgetExhausted):
            reserve(recovered)
    finally:
        fresh.close()


def test_cancel_refunds_only_unsent_attempts_and_is_idempotent(postgres_database):
    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    repo = repos[0]
    sent = reserve(repo)
    pending = reserve(repo)
    dispatch_budget_attempt(repo, sent.attempt_id)
    repo.cancel_account()
    repo.cancel_account()
    assert repo.cancel_attempt(pending.attempt_id).state == "cancelled"
    assert not dispatch_budget_attempt(repo, pending.attempt_id).dispatch_permitted
    assert (
        repo.snapshot()["held"]["requests"] == 1
        and suite_snapshot(db, suite)["active"] == 1
    )
    assert repo.cancel_attempt(sent.attempt_id).state == "dispatched"
    with pytest.raises(BudgetExhausted):
        reserve(repo)
    repo.settle(sent.attempt_id, ResourceAmount(requests=1), RECEIPT)
    assert (
        suite_snapshot(db, suite)["active"] == 0
        and repo.snapshot()["spent"]["requests"] == 1
    )


def test_actual_overrun_is_durable_then_closes_global_admission(postgres_database):
    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    repo = repos[0]
    attempt = reserve(repo, ResourceAmount(requests=1, tokens=1))
    dispatch_budget_attempt(repo, attempt.attempt_id)
    actual = ResourceAmount(requests=1, tokens=2, cost_picousd=1)
    assert repo.settle(attempt.attempt_id, actual, RECEIPT).state == "overrun"
    assert repo.settle(attempt.attempt_id, actual, RECEIPT).state == "overrun"
    assert (
        suite_snapshot(db, suite)["spent"] == actual.to_json()
        and suite_snapshot(db, suite)["closed"]
    )
    assert (
        repo.snapshot()["held"] == ResourceAmount().to_json()
        and repo.snapshot()["active"] == 0
    )
    with pytest.raises(BudgetExhausted):
        reserve(repos[2])
    with pytest.raises(BudgetConflict):
        repo.settle(attempt.attempt_id, ResourceAmount(requests=1), RECEIPT)
    with db["app"].transaction(repo.user_id) as s:
        assert (
            s.execute(
                select(tables.journal.c.actual).where(
                    tables.journal.c.next_state == "overrun"
                )
            ).scalar_one()
            == actual.to_json()
        )


def test_application_cannot_reset_authorization_or_write_journal_directly(
    postgres_database,
):
    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    repo = repos[0]
    reserve(repo)
    forbidden = [
        "UPDATE public.budget_suites SET held=spent",
        "DELETE FROM public.budget_suites",
        "UPDATE public.budget_accounts SET started_at=NULL",
        "DELETE FROM public.budget_accounts",
        "UPDATE public.budget_attempts SET state='cancelled'",
        "DELETE FROM public.budget_attempts",
        "INSERT INTO public.budget_attempts SELECT * FROM public.budget_attempts ON CONFLICT DO NOTHING",
        "UPDATE public.budget_journal SET next_state=previous_state",
        "DELETE FROM public.budget_journal",
        "TRUNCATE public.budget_journal",
    ]
    for sql in forbidden:
        with pytest.raises(DBAPIError), db["app"].transaction(repo.user_id) as s:
            s.execute(text(sql))
    with db["admin"].transaction() as s:
        flags = dict(
            s.execute(
                text(
                    "SELECT relname,relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname IN ('budget_accounts','budget_attempts','budget_journal')"
                )
            ).all()
        )
        assert all(flags.values()) and len(flags) == 3
        fn = s.execute(
            text(
                "SELECT proconfig,prosecdef,EXISTS(SELECT 1 FROM aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) e WHERE e.grantee=0 AND e.privilege_type='EXECUTE') FROM pg_proc p WHERE proname='demandrift_budget_operate'"
            )
        ).one()
        assert fn[0] == ["search_path=pg_catalog, pg_temp"] and fn[1] and not fn[2]
    assert repo.snapshot()["held"]["requests"] == 1


def test_policy_start_and_spent_are_immutable_even_for_accidental_operator_updates(
    postgres_database,
):
    db = postgres_database
    suite, repos, capacity = setup_ledger(db)
    repo = repos[0]
    attempt = reserve(repo)
    dispatch_budget_attempt(repo, attempt.attempt_id)
    repo.settle(attempt.attempt_id, ResourceAmount(requests=1), RECEIPT)
    for sql in [
        "UPDATE public.budget_suites SET concurrency=8",
        "UPDATE public.budget_suites SET started_at=NULL",
        "UPDATE public.budget_suites SET spent=held",
        "UPDATE public.budget_accounts SET spent=held",
        "UPDATE public.budget_accounts SET created_at=clock_timestamp()",
        "DELETE FROM public.budget_journal",
    ]:
        with pytest.raises(DBAPIError), db["admin"].transaction() as s:
            s.execute(text(sql))
    limits = approved_limits()
    limits.max_requests = 299
    with pytest.raises(BudgetConflict):
        repo.create_account(BudgetCapacity.from_wire(limits))
    assert suite_snapshot(db, suite)["spent"]["requests"] == 1


def test_waiting_dispatch_checks_fresh_clock_after_lock_crosses_deadline(
    postgres_database,
):
    db = postgres_database
    limits = approved_limits()
    limits.max_duration_seconds = 1
    suite, repos, _ = setup_ledger(db, capacity=BudgetCapacity.from_wire(limits))
    repo = repos[0]
    first = reserve(repo)
    second = reserve(repos[2])
    dispatch_budget_attempt(repo, first.attempt_id)
    ready = Event()
    release = Event()
    attempted = Event()

    def hold():
        with db["admin"].transaction() as s:
            s.execute(
                select(tables.suites)
                .where(tables.suites.c.suite_id == suite)
                .with_for_update()
            )
            ready.set()
            assert release.wait(timeout=8)

    def dispatch():
        attempted.set()
        return dispatch_budget_attempt(repos[2], second.attempt_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        holding = pool.submit(hold)
        assert ready.wait(timeout=4)
        waiting = pool.submit(dispatch)
        try:
            assert attempted.wait(timeout=4)
            time.sleep(1.1)
            assert not waiting.done()
        finally:
            release.set()
        holding.result(timeout=4)
        with pytest.raises(BudgetExhausted):
            waiting.result(timeout=4)
    assert suite_snapshot(db, suite)["active"] == 2
    assert not dispatch_budget_attempt(repo, first.attempt_id).dispatch_permitted


def test_explicit_database_head_and_disposable_roundtrip_cover_new_tables(
    postgres_database,
):
    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    with db["admin"].transaction() as s:
        assert (
            s.scalar(text("SELECT version_num FROM public.alembic_version"))
            == REQUIRED_MIGRATION
        )
    command.downgrade(db["config"], "20261001_0004")
    with db["admin"].transaction() as s:
        assert s.scalar(text("SELECT to_regclass('public.budget_suites')")) is None
    command.upgrade(db["config"], "head")
    db["app"].assert_application_role()
    with db["admin"].transaction() as s:
        assert (
            s.scalar(text("SELECT to_regclass('public.budget_journal')"))
            == "budget_journal"
        )


@pytest.mark.parametrize(
    "table", ["budget_suites", "budget_accounts", "budget_attempts", "budget_journal"]
)
def test_runtime_rejects_inherited_direct_ledger_write_privileges(
    postgres_database, table
):
    from app.db.engine import DatabaseConfigurationError

    db = postgres_database
    quote = db["admin"].engine.dialect.identifier_preparer.quote
    group = "demandrift_testledger_" + uuid4().hex[:12]
    with db["admin"].transaction() as s:
        s.execute(
            text(
                f"CREATE ROLE {quote(group)} NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"
            )
        )
        s.execute(text(f"GRANT UPDATE ON public.{quote(table)} TO {quote(group)}"))
        s.execute(text(f"GRANT {quote(group)} TO {quote(db['role'])}"))
    try:
        with pytest.raises(DatabaseConfigurationError):
            db["app"].assert_application_role()
    finally:
        with db["admin"].transaction() as s:
            s.execute(text(f"REVOKE {quote(group)} FROM {quote(db['role'])}"))
            s.execute(text(f"REVOKE ALL ON public.{quote(table)} FROM {quote(group)}"))
            s.execute(text(f"DROP ROLE {quote(group)}"))
    db["app"].assert_application_role()


def test_missing_version_or_empty_receipt_does_not_free_a_dispatched_hold(
    postgres_database,
):
    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    repo = repos[0]
    for bad in [{"kind": "model"}, {**META, "pricing_version": ""}]:
        with pytest.raises(BudgetConflict):
            repo.reserve(uuid4(), FINGERPRINT, ResourceAmount(requests=1), bad)
    assert suite_snapshot(db, suite)["active"] == 0
    receipt = reserve(repo)
    dispatch_budget_attempt(repo, receipt.attempt_id)
    with pytest.raises(BudgetConflict):
        repo.settle(
            receipt.attempt_id,
            ResourceAmount(requests=1),
            {**RECEIPT, "usage_version": ""},
        )
    assert (
        repo.snapshot()["held"]["requests"] == 1
        and repo.snapshot()["spent"]["requests"] == 0
    )


def test_unknown_budget_is_recovered_by_a_separate_python_process(postgres_database):
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys

    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    repo = repos[0]
    amount = ResourceAmount(requests=1, tokens=100, cost_picousd=500000)
    attempt = reserve(repo, amount)
    dispatch_budget_attempt(repo, attempt.attempt_id)
    repo.mark_unknown(attempt.attempt_id)
    code = """import json,os,sys
from uuid import UUID
from app.db.engine import Database
from app.db.budget_repository import BudgetRepository
v=json.load(sys.stdin);d=Database(os.environ['BUDGET_FIXTURE_DSN'])
r=BudgetRepository(d,*[UUID(v[k]) for k in ['suite','owner','project','research']])
s=r.snapshot();reply=r.dispatch(UUID(v['attempt']))
print(json.dumps({'pid':os.getpid(),'state':reply.state,'permit':reply.dispatch_permitted,'held':s['held'],'active':s['active']}))
d.close()
"""
    context = {
        "suite": str(suite),
        "owner": str(repo.user_id),
        "project": str(repo.project_id),
        "research": str(repo.research_id),
        "attempt": str(attempt.attempt_id),
    }
    process = subprocess.run(
        [sys.executable, "-c", code],
        input=json.dumps(context),
        text=True,
        capture_output=True,
        timeout=15,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parents[1]),
            "PYTHONDONTWRITEBYTECODE": "1",
            "BUDGET_FIXTURE_DSN": db["app"].engine.url.render_as_string(
                hide_password=False
            ),
        },
    )
    assert process.returncode == 0, "Independent recovery process failed"
    result = json.loads(process.stdout)
    assert (
        result["pid"] != os.getpid()
        and result["state"] == "held_unknown"
        and not result["permit"]
    )
    assert result["held"] == amount.to_json() and result["active"] == 1
    assert suite_snapshot(db, suite)["held"] == amount.to_json()


def test_missing_transaction_owner_cannot_call_the_scoped_rpc(postgres_database):
    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    repo = repos[0]
    with pytest.raises(DBAPIError), db["app"].transaction() as s:
        s.execute(
            text(
                """SELECT public.demandrift_budget_operate('cancel_account',:suite,:owner,:project,:research,NULL,NULL,NULL,NULL,'{}',NULL)"""
            ),
            {
                "suite": suite,
                "owner": repo.user_id,
                "project": repo.project_id,
                "research": repo.research_id,
            },
        )
    assert repo.snapshot()["cancelled_at"] is None


def test_extreme_measured_overrun_preserves_truth_beyond_bigint_aggregate(
    postgres_database,
):
    from app.budget_contract import MAX_COUNTER

    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    repo = repos[0]
    first = reserve(repo)
    second = reserve(repos[1])
    dispatch_budget_attempt(repo, first.attempt_id)
    dispatch_budget_attempt(repos[1], second.attempt_id)
    actual = ResourceAmount(requests=1, tokens=MAX_COUNTER)
    assert repo.settle(first.attempt_id, actual, RECEIPT).state == "overrun"
    assert repos[1].settle(second.attempt_id, actual, RECEIPT).state == "overrun"
    row = suite_snapshot(db, suite)
    assert row["closed"] and row["spent"]["tokens"] == 2 * MAX_COUNTER
    assert row["spent"]["requests"] == 2 and row["active"] == 0
    with pytest.raises(BudgetExhausted):
        reserve(repos[2])


@pytest.mark.parametrize("column_only", [False, True])
def test_noinherit_settable_writer_role_cannot_pass_startup_guard(
    postgres_database, column_only
):
    from app.db.engine import DatabaseConfigurationError

    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    repo = repos[0]
    reserve(repo)
    quote = db["admin"].engine.dialect.identifier_preparer.quote
    group = "demandrift_testwriter_" + uuid4().hex[:12]
    permission = "UPDATE(held,active)" if column_only else "UPDATE"
    with db["admin"].transaction() as s:
        s.execute(
            text(
                f"CREATE ROLE {quote(group)} NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"
            )
        )
        s.execute(text(f"GRANT {permission} ON public.budget_suites TO {quote(group)}"))
        s.execute(
            text(
                f"GRANT {quote(group)} TO {quote(db['role'])} WITH INHERIT FALSE, SET TRUE"
            )
        )
    try:
        with db["app"].transaction(repo.user_id) as s:
            assert tuple(
                s.execute(
                    text(
                        "SELECT pg_has_role(current_user,:writer,'MEMBER'),pg_has_role(current_user,:writer,'USAGE'),pg_has_role(current_user,:writer,'SET')"
                    ),
                    {"writer": group},
                ).one()
            ) == (True, False, True)
        with pytest.raises(DatabaseConfigurationError):
            db["app"].assert_application_role()
        assert suite_snapshot(db, suite)["held"]["requests"] == 1
    finally:
        with db["admin"].transaction() as s:
            s.execute(text(f"REVOKE {quote(group)} FROM {quote(db['role'])}"))
            s.execute(
                text(f"REVOKE {permission} ON public.budget_suites FROM {quote(group)}")
            )
            s.execute(text(f"DROP ROLE {quote(group)}"))
    db["app"].assert_application_role()


def test_column_only_write_grants_are_not_hidden_by_table_privilege_queries(
    postgres_database,
):
    from app.db.engine import DatabaseConfigurationError

    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    repo = repos[0]
    reserve(repo)
    quote = db["admin"].engine.dialect.identifier_preparer.quote
    role = quote(db["role"])
    with db["admin"].transaction() as s:
        s.execute(text(f"GRANT UPDATE(held,active) ON public.budget_suites TO {role}"))
    try:
        with db["app"].transaction(repo.user_id) as s:
            assert tuple(
                s.execute(
                    text(
                        "SELECT has_table_privilege(current_user,'public.budget_suites','UPDATE'),has_any_column_privilege(current_user,'public.budget_suites','UPDATE')"
                    )
                ).one()
            ) == (False, True)
        with pytest.raises(DatabaseConfigurationError):
            db["app"].assert_application_role()
        assert suite_snapshot(db, suite)["held"]["requests"] == 1
    finally:
        with db["admin"].transaction() as s:
            s.execute(
                text(f"REVOKE UPDATE(held,active) ON public.budget_suites FROM {role}")
            )
    db["app"].assert_application_role()


def test_tenant_role_cannot_read_global_suite_or_another_owner_hold(postgres_database):
    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    reserve(repos[2], ResourceAmount(requests=1, cost_picousd=1234567))
    assert repos[0].snapshot()["held"]["cost_picousd"] == 0
    with pytest.raises(DBAPIError), db["app"].transaction(repos[0].user_id) as s:
        s.execute(
            select(tables.suites.c.held).where(tables.suites.c.suite_id == suite)
        ).one()
    with db["app"].transaction(repos[0].user_id) as s:
        assert (
            s.execute(
                select(tables.accounts).where(
                    tables.accounts.c.research_id == repos[2].research_id
                )
            ).first()
            is None
        )


@pytest.mark.parametrize("column_only", [False, True])
def test_membership_cannot_expose_operator_only_global_suite_counters(
    postgres_database, column_only
):
    from app.db.engine import DatabaseConfigurationError

    db = postgres_database
    quote = db["admin"].engine.dialect.identifier_preparer.quote
    group = "demandrift_testreader_" + uuid4().hex[:12]
    permission = "SELECT(held)" if column_only else "SELECT"
    with db["admin"].transaction() as s:
        s.execute(
            text(
                f"CREATE ROLE {quote(group)} NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"
            )
        )
        s.execute(text(f"GRANT {permission} ON public.budget_suites TO {quote(group)}"))
        s.execute(
            text(
                f"GRANT {quote(group)} TO {quote(db['role'])} WITH INHERIT FALSE, SET TRUE"
            )
        )
    try:
        with pytest.raises(DatabaseConfigurationError):
            db["app"].assert_application_role()
    finally:
        with db["admin"].transaction() as s:
            s.execute(text(f"REVOKE {quote(group)} FROM {quote(db['role'])}"))
            s.execute(
                text(f"REVOKE {permission} ON public.budget_suites FROM {quote(group)}")
            )
            s.execute(text(f"DROP ROLE {quote(group)}"))
    db["app"].assert_application_role()


@pytest.mark.parametrize("value", [" \t\r\n", "\u00a0", "\u3000"])
@pytest.mark.parametrize(
    "field",
    [
        "operation_version",
        "provider",
        "model",
        "prompt_version",
        "schema_version",
        "pricing_version",
    ],
)
def test_blank_unicode_or_control_version_metadata_is_rejected(
    postgres_database, field, value
):
    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    with pytest.raises(BudgetConflict):
        repos[0].reserve(
            uuid4(), FINGERPRINT, ResourceAmount(requests=1), {**META, field: value}
        )
    assert suite_snapshot(db, suite)["active"] == 0


@pytest.mark.parametrize("value", [" \t\r\n", "\u00a0", "\u3000"])
@pytest.mark.parametrize("field", ["response_id", "model_version", "usage_version"])
def test_blank_receipt_cannot_settle_or_release_unknown_capacity(
    postgres_database, field, value
):
    db = postgres_database
    suite, repos, _ = setup_ledger(db)
    repo = repos[0]
    attempt = reserve(repo)
    dispatch_budget_attempt(repo, attempt.attempt_id)
    repo.mark_unknown(attempt.attempt_id)
    with pytest.raises(BudgetConflict):
        repo.settle(
            attempt.attempt_id, ResourceAmount(requests=1), {**RECEIPT, field: value}
        )
    assert repo.snapshot()["held"]["requests"] == 1 and repo.snapshot()["active"] == 1
    assert suite_snapshot(db, suite)["spent"]["requests"] == 0
