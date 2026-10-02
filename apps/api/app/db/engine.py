"""Short, transaction-scoped database access with explicit tenant context."""

from collections.abc import Iterator
from contextlib import contextmanager
import time
from uuid import UUID

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.db.bounded_connection import bounded_connection


class DatabaseConfigurationError(RuntimeError):
    pass


class Database:
    def __init__(self, dsn: str, *, pool_size: int = 5, probe: bool = False) -> None:
        try:
            url = make_url(dsn)
            if url.drivername != "postgresql+psycopg" or not url.database:
                raise ValueError("unsupported database")
            # libpq applies connect_timeout per host. Runtime uses one project
            # database, so a list must not multiply the connection deadline.
            for host in (url.host, url.query.get("host"), url.query.get("hostaddr")):
                if host is not None and (type(host) is not str or "," in host):
                    raise ValueError("single database host required")
            if type(probe) is not bool:
                raise ValueError("explicit probe mode required")
        except Exception:
            # Never include a DSN, password or provider credential in diagnostics.
            raise DatabaseConfigurationError("A valid PostgreSQL psycopg DATABASE_URL is required") from None
        self.engine = create_engine(
            url, **({"poolclass": NullPool} if probe else {
                "pool_size": pool_size, "max_overflow": 0, "pool_timeout": 5,
                "pool_pre_ping": True,
            }), echo=False, hide_parameters=True,
            connect_args={"connect_timeout": 2, "tcp_user_timeout": 2000,
                          "options": ("-c statement_timeout=500 -c lock_timeout=250" if probe
                                      else "-c statement_timeout=10000 -c lock_timeout=5000")},
        )
        probe_deadline = time.monotonic() + 3 if probe else None

        @event.listens_for(self.engine, "do_connect")
        def connect(dialect, record, args, parameters):
            return bounded_connection(*args, probe_deadline=probe_deadline, **parameters)

    def readiness_probe(self) -> "Database":
        """Fresh bounded connections never queue behind application transactions."""
        return Database(self.engine.url.render_as_string(hide_password=False), probe=True)

    def assert_application_role(self) -> None:
        with self.engine.connect() as connection:
            unsafe = connection.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_roles r WHERE
                    (r.rolsuper OR r.rolbypassrls OR r.rolcreaterole OR r.rolcreatedb)
                    AND (pg_has_role(current_user, r.oid, 'MEMBER')
                         OR pg_has_role(session_user, r.oid, 'MEMBER'))
                ) OR EXISTS (
                    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
                      AND (pg_has_role(current_user, c.relowner, 'MEMBER')
                           OR pg_has_role(session_user, c.relowner, 'MEMBER'))
                ) OR EXISTS (
                    SELECT 1 FROM pg_namespace n WHERE n.nspname='public'
                      AND (pg_has_role(current_user, n.nspowner, 'MEMBER')
                           OR pg_has_role(session_user, n.nspowner, 'MEMBER'))
                ) OR has_schema_privilege(current_user, 'public', 'CREATE')
                  OR has_schema_privilege(session_user, 'public', 'CREATE')
                  OR EXISTS (
                    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    CROSS JOIN pg_roles r
                    WHERE n.nspname='public'
                      AND c.relname IN ('budget_suites','budget_accounts','budget_attempts','budget_journal')
                      AND (pg_has_role(current_user,r.oid,'MEMBER')
                           OR pg_has_role(session_user,r.oid,'MEMBER'))
                      AND (has_table_privilege(r.oid,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                           OR has_any_column_privilege(r.oid,c.oid,'INSERT,UPDATE,REFERENCES')
                           OR (c.relname='budget_suites'
                               AND (has_table_privilege(r.oid,c.oid,'SELECT')
                                    OR has_any_column_privilege(r.oid,c.oid,'SELECT'))))
                  )
                  OR EXISTS (
                    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    CROSS JOIN pg_roles r
                    WHERE n.nspname='public'
                      AND c.relname IN ('research_jobs','job_outbox','job_journal')
                      AND (pg_has_role(current_user,r.oid,'MEMBER')
                           OR pg_has_role(session_user,r.oid,'MEMBER'))
                      AND (has_table_privilege(r.oid,c.oid,'UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                           OR has_any_column_privilege(r.oid,c.oid,'REFERENCES')
                           OR (c.relname IN ('job_outbox','job_journal')
                               AND (has_table_privilege(r.oid,c.oid,'INSERT')
                                    OR has_any_column_privilege(r.oid,c.oid,'INSERT')))
                           OR EXISTS (
                             SELECT 1 FROM pg_attribute a
                             WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
                               AND (a.attname<>'command' OR c.relname='job_journal')
                               AND has_column_privilege(r.oid,c.oid,a.attnum,'UPDATE')
                           ))
                  )
                  OR EXISTS (
                    SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                    CROSS JOIN pg_roles r
                    WHERE n.nspname='public' AND p.proname='demandrift_job_append'
                      AND (pg_has_role(current_user,r.oid,'MEMBER')
                           OR pg_has_role(session_user,r.oid,'MEMBER'))
                      AND has_function_privilege(r.oid,p.oid,'EXECUTE')
                  )
                  OR EXISTS (
                    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    CROSS JOIN pg_roles r
                    WHERE n.nspname='public' AND c.relname='preparation_mutations'
                      AND (pg_has_role(current_user,r.oid,'MEMBER')
                           OR pg_has_role(session_user,r.oid,'MEMBER'))
                      AND (has_table_privilege(r.oid,c.oid,'UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                           OR has_any_column_privilege(r.oid,c.oid,'UPDATE,REFERENCES'))
                  )
                  OR EXISTS (
                    SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                    CROSS JOIN pg_roles r
                    WHERE n.nspname='public' AND p.proname IN (
                        'demandrift_preparation_mutation_guard',
                        'demandrift_job_budget_guard',
                        'demandrift_job_budget_current',
                        'demandrift_job_budget_receipt'
                    )
                      AND (pg_has_role(current_user,r.oid,'MEMBER')
                           OR pg_has_role(session_user,r.oid,'MEMBER'))
                      AND has_function_privilege(r.oid,p.oid,'EXECUTE')
                  )
                  OR NOT EXISTS (
                    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='public' AND c.relname='preparation_mutations'
                      AND c.relrowsecurity AND c.relforcerowsecurity
                      AND (SELECT count(*) FROM pg_policy p WHERE p.polrelid=c.oid)=1
                      AND EXISTS (
                        SELECT 1 FROM pg_policy p WHERE p.polrelid=c.oid
                          AND p.polname='owner_scope' AND p.polcmd='*'
                          AND p.polpermissive AND p.polroles=ARRAY[0]::oid[]
                          AND pg_get_expr(p.polqual,p.polrelid)=:owner_policy
                          AND pg_get_expr(p.polwithcheck,p.polrelid)=:owner_policy
                      )
                  )
            """), {"owner_policy": "(user_id = (NULLIF(current_setting('app.user_id'::text, true), ''::text))::uuid)"}).scalar_one()
            if unsafe:
                raise DatabaseConfigurationError("Application database role must not administer schemas, own tables or bypass RLS")

    @contextmanager
    def transaction(self, user_id: UUID | None = None) -> Iterator[Session]:
        with Session(self.engine, expire_on_commit=False) as session, session.begin():
            # Override even a session-level GUC left on a reused connection.
            session.execute(text("SELECT set_config('app.user_id', :owner, true)"),
                            {"owner": str(user_id) if user_id is not None else ""})
            yield session

    def close(self) -> None:
        self.engine.dispose()
