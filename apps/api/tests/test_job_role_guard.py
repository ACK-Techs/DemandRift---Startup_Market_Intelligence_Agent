"""Real restricted-role startup protection for native job fencing columns."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import DatabaseConfigurationError

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("grant", [
    "UPDATE ON public.research_jobs", "UPDATE(fence) ON public.research_jobs",
    "UPDATE(state) ON public.research_jobs", "UPDATE(lease_until) ON public.research_jobs",
    "UPDATE(checkpoint) ON public.research_jobs", "DELETE ON public.research_jobs",
    "TRUNCATE ON public.research_jobs", "TRIGGER ON public.research_jobs",
    "REFERENCES(fence) ON public.research_jobs", "UPDATE(fence) ON public.job_outbox",
    "UPDATE(state) ON public.job_outbox", "UPDATE(lease_until) ON public.job_outbox",
    "UPDATE(sequence) ON public.job_journal", "UPDATE(detail) ON public.job_journal",
    "INSERT ON public.job_outbox", "INSERT(delivery_id) ON public.job_outbox",
    "INSERT ON public.job_journal", "INSERT(detail) ON public.job_journal",
])
def test_direct_table_or_protected_column_rights_rejected(postgres_database, grant):
    db = postgres_database
    with db["admin"].transaction() as session:
        session.execute(text(f'GRANT {grant} TO "{db["role"]}"'))
    with pytest.raises(DatabaseConfigurationError):
        db["app"].assert_application_role()


def test_transitive_noinherit_set_role_and_public_column_rights_rejected(postgres_database):
    db = postgres_database
    inherited = "demandrift_jobgrant_" + uuid4().hex[:12]
    try:
        with db["admin"].transaction() as session:
            session.execute(text(f'CREATE ROLE "{inherited}" NOLOGIN'))
            session.execute(text(f'GRANT UPDATE(fence) ON public.research_jobs TO "{inherited}"'))
            session.execute(text(f'GRANT "{inherited}" TO "{db["role"]}" WITH INHERIT FALSE, SET TRUE'))
        with pytest.raises(DatabaseConfigurationError):
            db["app"].assert_application_role()
        with db["admin"].transaction() as session:
            session.execute(text(f'REVOKE "{inherited}" FROM "{db["role"]}"'))
            session.execute(text('GRANT UPDATE(state) ON public.job_outbox TO PUBLIC'))
        with pytest.raises(DatabaseConfigurationError):
            db["app"].assert_application_role()
    finally:
        with db["admin"].transaction() as session:
            session.execute(text('REVOKE UPDATE(state) ON public.job_outbox FROM PUBLIC'))
            session.execute(text(f'DROP OWNED BY "{inherited}"'))
            session.execute(text(f'DROP ROLE "{inherited}"'))


def test_command_column_only_and_trigger_function_policy_are_safe(postgres_database):
    db = postgres_database
    db["app"].assert_application_role()
    with db["admin"].transaction() as session:
        rows = session.execute(text("""
            SELECT p.proname,p.prosecdef,p.proconfig,
                   has_function_privilege('public',p.oid,'EXECUTE')
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='public' AND p.proname IN
                ('demandrift_job_guard','demandrift_job_append',
                 'demandrift_job_journal_guard','demandrift_job_outbox_guard')
        """)).all()
        assert len(rows) == 4
        for name, definer, config, public_execute in rows:
            assert definer == (name == 'demandrift_job_append') and not public_execute
            assert any(value.startswith('search_path=pg_catalog, pg_temp') for value in config)
    # Restricted application credentials legitimately hold UPDATE(command),
    # while state/fence/checkpoint changes go through the native command guard.
    with db["app"].transaction() as session:
        assert session.scalar(text("SELECT has_column_privilege(current_user,'public.research_jobs','command','UPDATE')"))
        assert not session.scalar(text("SELECT has_column_privilege(current_user,'public.research_jobs','fence','UPDATE')"))
        assert not session.scalar(text("SELECT has_function_privilege(current_user,'public.demandrift_job_append()','EXECUTE')"))


def test_app_privileged_trigger_execute_right_rejected(postgres_database):
    db = postgres_database
    with db['admin'].transaction() as session:
        session.execute(text(f'GRANT EXECUTE ON FUNCTION public.demandrift_job_append() TO "{db["role"]}"'))
    with pytest.raises(DatabaseConfigurationError):
        db['app'].assert_application_role()
