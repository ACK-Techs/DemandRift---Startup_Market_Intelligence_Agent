"""Short, transaction-scoped database access with explicit tenant context."""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


class DatabaseConfigurationError(RuntimeError):
    pass


class Database:
    def __init__(self, dsn: str, *, pool_size: int = 5) -> None:
        try:
            url = make_url(dsn)
            if url.drivername != "postgresql+psycopg" or not url.database:
                raise ValueError("unsupported database")
        except Exception:
            # Never include a DSN, password or provider credential in diagnostics.
            raise DatabaseConfigurationError("A valid PostgreSQL psycopg DATABASE_URL is required") from None
        self.engine = create_engine(
            url, pool_size=pool_size, max_overflow=0, pool_timeout=5,
            pool_pre_ping=True, echo=False, hide_parameters=True,
            connect_args={"options": "-c statement_timeout=10000 -c lock_timeout=5000"},
        )

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
            """)).scalar_one()
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
