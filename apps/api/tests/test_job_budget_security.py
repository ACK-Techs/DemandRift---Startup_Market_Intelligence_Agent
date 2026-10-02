"""Actual native role, scope, direct RPC and immutable authority negatives."""

from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from app.db.engine import Database
from app.db.budget_repository import BudgetLedgerError
from app.db.job_budget_repository import JobBudgetRepository, SIGNATURE
from app.db import budget_models
from app.db.preparation_repository import RecordNotFound
from test_job_budget_repository import (
    AMOUNT, META, admit, admission_database as _admission_database, job_admission,
    preparation_admission, snapshot,
)

pytestmark = pytest.mark.postgres
admission_database = _admission_database


def test_legacy_unbound_dispatch_denied_preparation_and_job(admission_database):
    db = admission_database
    for ledger, producer in [preparation_admission(db)[2:4], job_admission(db, label="J")[4:6]]:
        attempt = uuid4()
        ledger.reserve(attempt, "a" * 64, AMOUNT, META)
        with pytest.raises(BudgetLedgerError):
            ledger.dispatch(attempt)
        suite, rows = snapshot(db, producer)
        assert rows[0]["state"] == "reserved" and rows[0]["admission_kind"] is None
        assert suite["started_at"] is None
        ledger.cancel_attempt(attempt)
        assert snapshot(db, producer)[0]["active"] == 0


def test_native_scoped_rpc_and_tenant_guard_foreign_missing_identical(admission_database):
    db = admission_database
    _, _, _, first, context = preparation_admission(db)
    _, _, _, foreign, foreign_context = preparation_admission(db, label="F")
    forged = JobBudgetRepository(db["app"], first.suite_id, foreign.user_id, first.project_id, first.research_id)
    missing = JobBudgetRepository(db["app"], first.suite_id, foreign.user_id, uuid4(), uuid4())
    for candidate in (forged, missing):
        with pytest.raises(RecordNotFound, match="Admission scope not found"):
            admit(candidate, context)
    with pytest.raises(DBAPIError) as error:
        with db["app"].transaction(foreign.user_id) as session:
            first._call(session, "admit", context, 30000, attempt=uuid4(), fingerprint="a" * 64, reserved=AMOUNT, metadata=META)
    assert error.value.orig.sqlstate == "P0002"
    with pytest.raises(Exception):
        admit(first, replace(context, brief_id=foreign_context.brief_id))
    assert not snapshot(db, first)[1]


def test_low_role_no_ledger_column_writes_no_suite_select_guard_execute_or_temp_rebinding(admission_database):
    db = admission_database
    _, _, _, producer, context = preparation_admission(db)
    receipt = admit(producer, context)
    with db["app"].transaction(producer.user_id) as session:
        assert session.scalar(text(f"SELECT has_function_privilege(current_user,'{SIGNATURE}','EXECUTE')"))
        for name in ("demandrift_job_budget_guard()", "demandrift_job_budget_current(uuid,uuid,uuid,jsonb)",
                     "demandrift_job_budget_receipt(public.budget_attempts,boolean)"):
            assert not session.scalar(text("SELECT has_function_privilege(current_user,:name,'EXECUTE')"), {"name": "public." + name})
        assert not session.scalar(text("SELECT has_any_column_privilege(current_user,'public.budget_attempts','INSERT,UPDATE,REFERENCES')"))
        assert not session.scalar(text("SELECT has_any_column_privilege(current_user,'public.budget_suites','SELECT')"))
        assert not session.scalar(text("""SELECT EXISTS(SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
           WHERE n.nspname='public' AND p.proname LIKE 'demandrift_job_budget_%'
           AND EXISTS(SELECT 1 FROM aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) x WHERE x.grantee=0 AND x.privilege_type='EXECUTE'))"""))
    for sql in ["SELECT * FROM public.budget_suites",
                "UPDATE public.budget_attempts SET dispatch_deadline_at=clock_timestamp()+interval '1 day'",
                "SELECT public.demandrift_job_budget_guard()"]:
        with pytest.raises(DBAPIError) as error:
            with db["app"].transaction(producer.user_id) as session:
                session.execute(text(sql))
        assert error.value.orig.sqlstate == "42501"
    with pytest.raises(DBAPIError) as error:
        with db["app"].transaction(producer.user_id) as session:
            session.execute(text("CREATE TEMP TABLE forge (LIKE public.budget_attempts)"))
            session.execute(text("CREATE TRIGGER forge_guard BEFORE UPDATE ON forge FOR EACH ROW EXECUTE FUNCTION public.demandrift_job_budget_guard()"))
    assert error.value.orig.sqlstate == "42501"
    assert not admit(producer, context, receipt.attempt_id).dispatch_permitted


def test_binding_immutable_even_native_owner_and_app_misgrant(admission_database):
    db = admission_database
    _, _, _, producer, context = preparation_admission(db)
    receipt = admit(producer, context)
    for changes in ["dispatch_deadline_at=dispatch_deadline_at+interval '1 second'",
                    "brief_version=brief_version+1", "admission_kind=NULL",
                    "model_timeout_ms=model_timeout_ms+1", "input_fingerprint='" + "b" * 64 + "'"]:
        with pytest.raises(DBAPIError) as error:
            with db["admin"].transaction(producer.user_id) as session:
                session.execute(text(f"UPDATE public.budget_attempts SET {changes} WHERE attempt_id=:attempt"), {"attempt": receipt.attempt_id})
        assert error.value.orig.sqlstate == "23514"
    with db["admin"].transaction() as session:
        quote = db["admin"].engine.dialect.identifier_preparer.quote
        session.execute(text(f"GRANT UPDATE(dispatch_deadline_at) ON public.budget_attempts TO {quote(db['role'])}"))
    with pytest.raises(DBAPIError) as error:
        with db["app"].transaction(producer.user_id) as session:
            session.execute(text("UPDATE public.budget_attempts SET dispatch_deadline_at=clock_timestamp()+interval '1 day' WHERE attempt_id=:attempt"), {"attempt": receipt.attempt_id})
    assert error.value.orig.sqlstate == "42501"


def test_static_metadata_and_exact_privileged_rpc_catalog(admission_database):
    db = admission_database
    with db["admin"].engine.connect() as connection:
        native = inspect(connection)
        columns = {column["name"]: column for column in native.get_columns("budget_attempts", schema="public")}
        assert set(columns) == set(budget_models.attempts.c.keys())
        for column in budget_models.attempts.c:
            assert str(column.type.compile(dialect=connection.dialect)) == str(columns[column.name]["type"].compile(dialect=connection.dialect))
            assert column.nullable == columns[column.name]["nullable"]
        foreign = {item["name"]: item for item in native.get_foreign_keys("budget_attempts", schema="public")}
        for constraint in budget_models.attempts.foreign_key_constraints:
            item = foreign[constraint.name]
            assert item["constrained_columns"] == list(constraint.column_keys)
            assert item["referred_columns"] == [element.column.name for element in constraint.elements]
            assert item["referred_table"] == constraint.referred_table.name
        names = connection.execute(text("""SELECT proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
          WHERE n.nspname='public' AND proname LIKE 'demandrift_%' AND prosecdef ORDER BY proname""")).scalars().all()
        assert names == ["demandrift_budget_operate", "demandrift_job_append", "demandrift_job_budget_operate"]
        rows = connection.execute(text("""SELECT proname,proconfig FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
          WHERE n.nspname='public' AND proname LIKE 'demandrift_job_budget_%'""")).all()
        assert all("search_path=pg_catalog, pg_temp" in row.proconfig or "search_path=pg_catalog,pg_temp" in row.proconfig for row in rows)
    # Only this disposable app instance. Root still owns required-head008 and
    # the shared startup/catalog policy integration; no production-role claim.
    separate = Database(db["app"].engine.url.render_as_string(hide_password=False))
    separate.close()
