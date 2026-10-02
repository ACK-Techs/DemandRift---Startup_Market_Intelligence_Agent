"""Native startup protection for immutable preparation operation receipts."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import DatabaseConfigurationError

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("grant", [
    "UPDATE ON public.preparation_mutations",
    "DELETE ON public.preparation_mutations",
    "TRUNCATE ON public.preparation_mutations",
    "TRIGGER ON public.preparation_mutations",
    "REFERENCES ON public.preparation_mutations",
    "UPDATE(input_payload) ON public.preparation_mutations",
    "UPDATE(input_fingerprint) ON public.preparation_mutations",
    "REFERENCES(brief_id) ON public.preparation_mutations",
    "EXECUTE ON FUNCTION public.demandrift_preparation_mutation_guard()",
])
def test_receipt_mutation_or_trigger_execute_rejected(postgres_database, grant):
    db = postgres_database
    with db["admin"].transaction() as session:
        session.execute(text(f'GRANT {grant} TO "{db["role"]}"'))
    with pytest.raises(DatabaseConfigurationError):
        db["app"].assert_application_role()


def test_public_and_noinherit_set_role_receipt_rights_rejected(postgres_database):
    db = postgres_database
    inherited = "demandrift_prepgrant_" + uuid4().hex[:12]
    try:
        with db["admin"].transaction() as session:
            session.execute(text(f'CREATE ROLE "{inherited}" NOLOGIN'))
            session.execute(text(f'GRANT UPDATE(input_payload) ON public.preparation_mutations TO "{inherited}"'))
            session.execute(text(f'GRANT "{inherited}" TO "{db["role"]}" WITH INHERIT FALSE, SET TRUE'))
        with pytest.raises(DatabaseConfigurationError):
            db["app"].assert_application_role()
        with db["admin"].transaction() as session:
            session.execute(text(f'REVOKE "{inherited}" FROM "{db["role"]}"'))
            session.execute(text('GRANT REFERENCES(brief_id) ON public.preparation_mutations TO PUBLIC'))
        with pytest.raises(DatabaseConfigurationError):
            db["app"].assert_application_role()
    finally:
        with db["admin"].transaction() as session:
            session.execute(text('REVOKE REFERENCES(brief_id) ON public.preparation_mutations FROM PUBLIC'))
            session.execute(text(f'DROP OWNED BY "{inherited}"'))
            session.execute(text(f'DROP ROLE "{inherited}"'))


@pytest.mark.parametrize("mutation", [
    "ALTER TABLE public.preparation_mutations DISABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.preparation_mutations NO FORCE ROW LEVEL SECURITY",
    "DROP POLICY owner_scope ON public.preparation_mutations",
    "ALTER POLICY owner_scope ON public.preparation_mutations USING(true)",
    "ALTER POLICY owner_scope ON public.preparation_mutations WITH CHECK(true)",
    "CREATE POLICY extra_read ON public.preparation_mutations USING(true)",
])
def test_missing_unforced_or_broadened_owner_policy_rejected(postgres_database, mutation):
    db = postgres_database
    with db["admin"].transaction() as session:
        session.execute(text(mutation))
    with pytest.raises(DatabaseConfigurationError):
        db["app"].assert_application_role()


def test_safe_receipt_insert_and_select_are_intentionally_allowed(postgres_database):
    db = postgres_database
    db["app"].assert_application_role()
    with db["app"].transaction() as session:
        assert session.scalar(text("SELECT has_table_privilege(current_user,'public.preparation_mutations','SELECT')"))
        assert session.scalar(text("SELECT has_table_privilege(current_user,'public.preparation_mutations','INSERT')"))
        assert not session.scalar(text("SELECT has_function_privilege(current_user,'public.demandrift_preparation_mutation_guard()','EXECUTE')"))
        assert list(session.execute(text("SELECT * FROM public.preparation_mutations"))) == []
