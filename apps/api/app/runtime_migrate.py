"""Operations-only, forward-only migration with private credential boundaries."""

import os
from pathlib import Path
import sys

from alembic.config import Config
from alembic.runtime.environment import EnvironmentContext
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db.engine import Database
from app.db.migration_head import REQUIRED_MIGRATION
from app.runtime_bootstrap import (
    BootstrapConfig, bootstrap_application_role, configured_bootstrap_config,
)


class RuntimeMigrationError(RuntimeError):
    pass


_REVISIONS = (
    "20261001_0001", "20261001_0002", "20261001_0003", "20261001_0004",
    "20261001_0005", "20261002_0006", "20261002_0007", "20261002_0008",
    "20261002_0009",
    "20261003_0010",
)


def _trusted_script() -> tuple[Config, ScriptDirectory]:
    # Release-owned paths only: neither alembic.ini search nor env.py URL lookup.
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("version_locations", str(root / "migrations" / "versions"))
    config.set_main_option("recursive_version_locations", "false")
    config.set_main_option("sourceless", "false")
    script = ScriptDirectory.from_config(config)
    revisions = tuple(reversed(tuple(script.walk_revisions())))
    if (REQUIRED_MIGRATION != _REVISIONS[-1]
            or script.get_heads() != [REQUIRED_MIGRATION]
            or tuple(revision.revision for revision in revisions) != _REVISIONS
            or any(revision.down_revision != (None if index == 0 else _REVISIONS[index - 1])
                   or revision.dependencies or revision.branch_labels
                   for index, revision in enumerate(revisions))):
        raise RuntimeMigrationError("Runtime migration unavailable")
    return config, script


def _accepted_current_head(connection) -> tuple[str, ...]:
    heads = MigrationContext.configure(connection, opts={"version_table_schema": "public"}).get_current_heads()
    if heads and (len(heads) != 1 or heads[0] not in _REVISIONS):
        raise RuntimeMigrationError("Runtime migration unavailable")
    return heads


def migrate_runtime(configuration: BootstrapConfig) -> None:
    """Validate, bootstrap, upgrade and check the actual restricted login."""
    admin = application = None
    try:
        # Also reject manually constructed dataclasses before any SQL.
        configuration = BootstrapConfig.from_dsns(
            configuration.admin.render_as_string(hide_password=False),
            configuration.application.render_as_string(hide_password=False),
            role=configuration.role,
        )
        # Canonical release migrations read this public identifier themselves.
        # A dedicated operations process never replaces its parent environment.
        if os.environ.get("DATABASE_APP_ROLE", "demandrift_app") != configuration.role:
            raise RuntimeMigrationError("Runtime migration unavailable")
        config, script = _trusted_script()
        admin = Database(configuration.admin.render_as_string(hide_password=False), pool_size=1)
        with admin.engine.connect() as connection:
            identity = connection.execute(text("SELECT current_user, session_user")).one()
            if tuple(identity) != (configuration.admin.username, configuration.admin.username):
                raise RuntimeMigrationError("Runtime migration unavailable")
            # Unsupported/ahead/multiple heads must fail before role creation.
            _accepted_current_head(connection)

        bootstrap_application_role(configuration)
        with admin.engine.begin() as connection:
            # Serialize cooperating operations against this database, including repeats.
            connection.execute(text("SELECT pg_advisory_xact_lock(1818588276, 8)"))
            _accepted_current_head(connection)
            if os.environ.get("DATABASE_APP_ROLE", "demandrift_app") != configuration.role:
                raise RuntimeMigrationError("Runtime migration unavailable")

            def upgrade(revision, context):
                return script._upgrade_revs(REQUIRED_MIGRATION, revision)

            # env.py creates its own URL from environment credentials. Running the
            # fixed ScriptDirectory on this connection avoids that second boundary.
            with EnvironmentContext(config, script, fn=upgrade, destination_rev=REQUIRED_MIGRATION) as context:
                context.configure(connection=connection, transactional_ddl=True, version_table_schema="public")
                with context.begin_transaction():
                    context.run_migrations()
            if _accepted_current_head(connection) != (REQUIRED_MIGRATION,):
                raise RuntimeMigrationError("Runtime migration unavailable")

        application = Database(configuration.application.render_as_string(hide_password=False), pool_size=1)
        application.assert_application_role()
        with application.engine.connect() as connection:
            row = connection.execute(text("""
                SELECT current_user, session_user, rolcanlogin,
                       rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls OR rolreplication,
                       EXISTS (SELECT 1 FROM pg_auth_members WHERE member=r.oid)
                FROM pg_roles r WHERE rolname=current_user
            """)).one()
            if tuple(row) != (configuration.role, configuration.role, True, False, False):
                raise RuntimeMigrationError("Runtime migration unavailable")
            if _accepted_current_head(connection) != (REQUIRED_MIGRATION,):
                raise RuntimeMigrationError("Runtime migration unavailable")
    except Exception:
        raise RuntimeMigrationError("Runtime migration unavailable") from None
    finally:
        cleanup_failed = False
        for database in (application, admin):
            if database is not None:
                try:
                    database.close()
                except Exception:
                    cleanup_failed = True
        if cleanup_failed:
            raise RuntimeMigrationError("Runtime migration unavailable") from None


def configured_migration() -> None:
    try:
        migrate_runtime(configured_bootstrap_config())
    except Exception:
        raise RuntimeMigrationError("Runtime migration unavailable") from None


def main() -> int:
    try:
        configured_migration()
    except (Exception, KeyboardInterrupt):
        print("Runtime migration unavailable", file=sys.stderr)
        return 1
    print("Runtime migration complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
