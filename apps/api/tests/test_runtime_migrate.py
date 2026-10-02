"""Operations migrator: release boundaries and real PostgreSQL transactions."""

from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.db.engine import Database
from app.db.migration_head import REQUIRED_MIGRATION
from app.runtime_bootstrap import BootstrapConfig
from app import runtime_migrate as migration


ADMIN = "postgresql+psycopg://demandrift_admin:admin-fixture@postgres/demandrift"
APP = "postgresql+psycopg://demandrift_app:application-fixture-password-1234@postgres/demandrift"


def test_script_is_fixed_release_chain_and_does_not_use_environment_paths(monkeypatch):
    monkeypatch.setenv("ALEMBIC_CONFIG", "/untrusted/alembic.ini")
    monkeypatch.setenv("DATABASE_URL", "untrusted-credential-sentinel")
    config, script = migration._trusted_script()
    root = Path(migration.__file__).resolve().parents[1]
    assert Path(config.config_file_name) == root / "alembic.ini"
    assert Path(script.dir) == root / "migrations"
    assert script.get_heads() == [REQUIRED_MIGRATION] == ["20261002_0009"]
    assert [revision.revision for revision in reversed(list(script.walk_revisions()))] == list(migration._REVISIONS)
    assert not config.get_main_option("sqlalchemy.url")


@pytest.mark.parametrize("alteration", ["head", "branch", "dependency", "parent", "extra", "required"])
def test_release_drift_is_rejected_before_database_access(monkeypatch, alteration):
    _, script = migration._trusted_script()
    if alteration == "head":
        monkeypatch.setattr(script, "get_heads", lambda: ["20261002_0010"])
    elif alteration == "extra":
        monkeypatch.setattr(script, "walk_revisions", lambda: [])
    elif alteration == "required":
        monkeypatch.setattr(migration, "REQUIRED_MIGRATION", "20261002_0007")
    else:
        revision = script.get_revision("20261002_0009")
        monkeypatch.setattr(revision, {"branch": "branch_labels", "dependency": "dependencies", "parent": "down_revision"}[alteration],
                            {"branch": {"other"}, "dependency": "20261001_0001", "parent": "20261001_0005"}[alteration])
    monkeypatch.setattr(migration.ScriptDirectory, "from_config", lambda config: script)
    monkeypatch.setattr(migration, "Database", lambda *args, **kwargs: pytest.fail("release drift reached SQL"))
    with pytest.raises(migration.RuntimeMigrationError, match="^Runtime migration unavailable$"):
        migration.migrate_runtime(BootstrapConfig.from_dsns(ADMIN, APP, role="demandrift_app"))


@pytest.mark.parametrize("kind", ["scope", "role_environment", "credentials"])
def test_forged_or_mismatched_configuration_cannot_reach_sql(monkeypatch, kind):
    config = BootstrapConfig.from_dsns(ADMIN, APP, role="demandrift_app")
    if kind == "scope":
        config = replace(config, application=config.application.set(database="another"))
    elif kind == "credentials":
        config = replace(config, application=config.application.update_query_dict({"user": "demandrift_admin"}))
    else:
        monkeypatch.setenv("DATABASE_APP_ROLE", "another")
    monkeypatch.setattr(migration, "Database", lambda *args, **kwargs: pytest.fail("invalid config reached SQL"))
    with pytest.raises(migration.RuntimeMigrationError) as failure:
        migration.migrate_runtime(config)
    assert str(failure.value) == "Runtime migration unavailable"


def test_configured_migration_uses_public_private_file_loader_once(monkeypatch):
    config = BootstrapConfig.from_dsns(ADMIN, APP, role="demandrift_app")
    seen = []
    monkeypatch.setattr(migration, "configured_bootstrap_config", lambda: seen.append("config") or config)
    monkeypatch.setattr(migration, "migrate_runtime", lambda value: seen.append(value))
    migration.configured_migration()
    assert seen == ["config", config]


@pytest.mark.parametrize("error", [ValueError, KeyboardInterrupt])
def test_cli_success_and_failure_are_generic(monkeypatch, capsys, error):
    monkeypatch.setattr(migration, "configured_migration", lambda: None)
    assert migration.main() == 0
    assert capsys.readouterr().out == "Runtime migration complete\n"

    def failing():
        raise error(ADMIN + APP + "/private/file sentinel")

    monkeypatch.setattr(migration, "configured_migration", failing)
    assert migration.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Runtime migration unavailable\n"


def test_cli_rejects_environment_credentials_without_files(monkeypatch):
    environment = dict(os.environ)
    for key in ("DATABASE_URL_FILE", "DEMANDRIFT_APPLICATION_DATABASE_FILE"):
        environment.pop(key, None)
    environment.update(DATABASE_URL=ADMIN, APP_ENV="development")
    result = subprocess.run([sys.executable, "-m", "app.runtime_migrate"], env=environment,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "Runtime migration unavailable\n"


@pytest.fixture
def fresh_database(monkeypatch):
    if os.environ.get("DEMANDRIFT_DB_TESTS") != "1":
        pytest.skip("native PostgreSQL checks require DEMANDRIFT_DB_TESTS=1")
    value = os.environ.get("DEMANDRIFT_TEST_ADMIN_URL")
    if not value:
        pytest.fail("explicit disposable local admin fixture required")
    url = make_url(value)
    if url.drivername != "postgresql+psycopg":
        pytest.fail("PostgreSQL psycopg fixture required")
    suffix = uuid4().hex[:12]
    name, role = "demandrift_migrate_" + suffix, "demandrift_migrateapp_" + suffix
    engine = create_engine(url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    quote = engine.dialect.identifier_preparer.quote
    target = url.set(database=name)
    application = target.set(username=role, password="migration-fixture-password-1234")
    config = BootstrapConfig.from_dsns(target.render_as_string(hide_password=False),
                                      application.render_as_string(hide_password=False), role=role)
    admin = Database(target.render_as_string(hide_password=False), pool_size=1)
    with engine.connect() as connection:
        connection.execute(text(f"CREATE DATABASE {quote(name)}"))
    monkeypatch.setenv("DATABASE_APP_ROLE", role)
    try:
        yield {"configuration": config, "admin": admin, "role": role, "name": name, "engine": engine}
    finally:
        admin.close()
        with engine.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS {quote(name)} WITH (FORCE)"))
            connection.execute(text(f"DROP ROLE IF EXISTS {quote(role)}"))
        engine.dispose()


def _role_state(db):
    with db["admin"].engine.connect() as connection:
        return connection.execute(text("SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolbypassrls,rolreplication,rolpassword FROM pg_authid WHERE rolname=:role"),
                                  {"role": db["role"]}).one_or_none()


def _revision_state(db):
    with db["admin"].engine.connect() as connection:
        return migration.MigrationContext.configure(connection).get_current_heads()


def _prepare_revision(db, monkeypatch, revision):
    from app.runtime_bootstrap import bootstrap_application_role
    bootstrap_application_role(db["configuration"])
    monkeypatch.setenv("DATABASE_URL", db["configuration"].admin.render_as_string(hide_password=False))
    monkeypatch.delenv("DATABASE_URL_FILE", raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), revision)


@pytest.mark.postgres
def test_fresh_database_bootstraps_before_full_migration_and_repeat_preserves_role(fresh_database, monkeypatch):
    db = fresh_database
    assert _role_state(db) is None and _revision_state(db) == ()
    # The operations runner must ignore the legacy env.py credential boundary.
    monkeypatch.setenv("DATABASE_URL", "private-sentinel-invalid-admin-url")
    original = dict(os.environ)
    migration.migrate_runtime(db["configuration"])
    assert dict(os.environ) == original
    role_before = _role_state(db)
    assert tuple(role_before[:6]) == (True, False, False, False, False, False)
    assert _revision_state(db) == (REQUIRED_MIGRATION,)
    migration.migrate_runtime(db["configuration"])
    assert _role_state(db) == role_before and _revision_state(db) == (REQUIRED_MIGRATION,)


@pytest.mark.postgres
@pytest.mark.parametrize('previous_revision', ['20261002_0007', '20261002_0008'])
def test_current_database_forward_upgrade_preserves_rows(fresh_database, monkeypatch, previous_revision):
    db = fresh_database
    _prepare_revision(db, monkeypatch, previous_revision)
    owner = uuid4()
    with db["admin"].transaction() as session:
        session.execute(text("INSERT INTO public.users(user_id,email,password_hash) VALUES (:owner,:email,'fixture-hash')"),
                        {"owner": owner, "email": "migration-fixture@example.test"})
    migration.migrate_runtime(db["configuration"])
    assert _revision_state(db) == (REQUIRED_MIGRATION,)
    with db["admin"].transaction() as session:
        assert session.execute(text("SELECT count(*) FROM public.users WHERE user_id=:owner"), {"owner": owner}).scalar_one() == 1


@pytest.mark.postgres
def test_restricted_role_native_grants_and_rls_remain_effective(fresh_database):
    db = fresh_database
    migration.migrate_runtime(db["configuration"])
    owner, other, project = uuid4(), uuid4(), uuid4()
    with db["admin"].transaction() as session:
        for user in (owner, other):
            session.execute(text("INSERT INTO public.users(user_id,email,password_hash) VALUES (:owner,:email,'fixture-hash')"),
                            {"owner": user, "email": f"{user}@fixture.test"})
        session.execute(text("INSERT INTO public.projects(project_id,user_id,name) VALUES (:project,:owner,'Fixture')"),
                        {"project": project, "owner": owner})
    application = Database(db["configuration"].application.render_as_string(hide_password=False))
    try:
        application.assert_application_role()
        with application.transaction(owner) as session:
            assert session.execute(text("SELECT count(*) FROM public.projects")).scalar_one() == 1
        with application.transaction(other) as session:
            assert session.execute(text("SELECT count(*) FROM public.projects")).scalar_one() == 0
        with application.transaction() as session:
            assert session.execute(text("SELECT count(*) FROM public.projects")).scalar_one() == 0
        for sql in (f"CREATE ROLE forbidden_{uuid4().hex[:12]} LOGIN", "CREATE TABLE public.forbidden_fixture(id int)",
                    "UPDATE public.alembic_version SET version_num='20261002_0007'", "DELETE FROM public.preparation_mutations"):
            with pytest.raises(DBAPIError) as denied:
                with application.transaction(owner) as session:
                    session.execute(text(sql))
            assert denied.value.orig.sqlstate == "42501"
        with pytest.raises(DBAPIError) as denied:
            with application.transaction(other) as session:
                session.execute(text("INSERT INTO public.projects(project_id,user_id,name) VALUES (:project,:owner,'Foreign')"),
                                {"project": uuid4(), "owner": owner})
        assert denied.value.orig.sqlstate == "42501"
    finally:
        application.close()


@pytest.mark.postgres
@pytest.mark.parametrize("heads", [("20261002_0010",), ("unknown",), ("20261001_0001", "20261002_0007")])
def test_unknown_ahead_multiple_database_heads_fail_before_role_creation(fresh_database, heads):
    db = fresh_database
    with db["admin"].transaction() as session:
        session.execute(text("CREATE TABLE public.alembic_version(version_num varchar(32) PRIMARY KEY)"))
        for head in heads:
            session.execute(text("INSERT INTO public.alembic_version VALUES (:head)"), {"head": head})
    with pytest.raises(migration.RuntimeMigrationError):
        migration.migrate_runtime(db["configuration"])
    assert _role_state(db) is None and set(_revision_state(db)) == set(heads)


@pytest.mark.postgres
def test_version_table_is_public_even_with_shadowing_database_search_path(fresh_database):
    db = fresh_database
    quote = db["admin"].engine.dialect.identifier_preparer.quote
    with db["admin"].transaction() as session:
        session.execute(text("CREATE SCHEMA shadow"))
        session.execute(text("CREATE TABLE shadow.alembic_version(version_num varchar(32) PRIMARY KEY)"))
        session.execute(text("INSERT INTO shadow.alembic_version VALUES ('20261002_0010')"))
        session.execute(text(f"ALTER DATABASE {quote(db['name'])} SET search_path TO shadow, public"))
    migration.migrate_runtime(db["configuration"])
    with db["admin"].transaction() as session:
        assert session.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one() == REQUIRED_MIGRATION
        assert session.execute(text("SELECT version_num FROM shadow.alembic_version")).scalar_one() == "20261002_0010"


@pytest.mark.postgres
@pytest.mark.parametrize("start", ["base", "20261002_0007"])
def test_failed_migration_rolls_back_ddl_and_head_keeps_restricted_role(fresh_database, monkeypatch, start):
    db = fresh_database
    if start != "base":
        _prepare_revision(db, monkeypatch, start)
    config, script = migration._trusted_script()
    revision = script.get_revision(REQUIRED_MIGRATION)
    real_upgrade = revision.module.upgrade

    def failing_upgrade():
        real_upgrade()
        from alembic import op
        op.execute("CREATE TABLE public.failed_migration_sentinel(id int)")
        raise RuntimeError("private-DSN-password-sentinel")

    monkeypatch.setattr(revision.module, "upgrade", failing_upgrade)
    monkeypatch.setattr(migration, "_trusted_script", lambda: (config, script))
    with pytest.raises(migration.RuntimeMigrationError) as failure:
        migration.migrate_runtime(db["configuration"])
    assert str(failure.value) == "Runtime migration unavailable"
    assert _revision_state(db) == (() if start == "base" else (start,))
    assert tuple(_role_state(db)[:6]) == (True, False, False, False, False, False)
    with db["admin"].engine.connect() as connection:
        assert connection.execute(text("SELECT to_regclass('public.failed_migration_sentinel')")).scalar_one() is None
        if start == "base":
            assert connection.execute(text("SELECT to_regclass('public.projects')")).scalar_one() is None


@pytest.mark.postgres
@pytest.mark.parametrize("unsafe", ["SUPERUSER", "BYPASSRLS", "REPLICATION"])
def test_unsafe_existing_role_is_not_adopted_or_repaired(fresh_database, unsafe):
    db = fresh_database
    quote = db["admin"].engine.dialect.identifier_preparer.quote
    with db["admin"].transaction() as session:
        session.execute(text(f"CREATE ROLE {quote(db['role'])} LOGIN {unsafe} PASSWORD 'migration-fixture-password-1234'"))
    before = _role_state(db)
    with pytest.raises(migration.RuntimeMigrationError):
        migration.migrate_runtime(db["configuration"])
    assert _role_state(db) == before and _revision_state(db) == ()


@pytest.mark.postgres
@pytest.mark.parametrize("alteration", ["head_privilege", "schema_create", "receipt_rls"])
def test_post_upgrade_application_checks_fail_closed_for_drift(fresh_database, monkeypatch, alteration):
    db = fresh_database
    migration.migrate_runtime(db["configuration"])
    quote = db["admin"].engine.dialect.identifier_preparer.quote
    with db["admin"].transaction() as session:
        if alteration == "head_privilege":
            session.execute(text(f"REVOKE SELECT ON public.alembic_version FROM {quote(db['role'])}"))
        elif alteration == "schema_create":
            session.execute(text(f"GRANT CREATE ON SCHEMA public TO {quote(db['role'])}"))
        else:
            session.execute(text("ALTER TABLE public.preparation_mutations NO FORCE ROW LEVEL SECURITY"))
    with pytest.raises(migration.RuntimeMigrationError, match="^Runtime migration unavailable$"):
        migration.migrate_runtime(db["configuration"])
    assert _revision_state(db) == (REQUIRED_MIGRATION,)


@pytest.mark.postgres
@pytest.mark.parametrize("failure", ["check", "close"])
def test_application_check_or_cleanup_failure_closes_both_owned_databases(fresh_database, monkeypatch, failure):
    db = fresh_database
    closed = []

    def tracking_database(dsn, **kwargs):
        database = Database(dsn, **kwargs)
        is_application = database.engine.url.username == db["role"]
        real_close = database.close

        def close():
            real_close()
            closed.append("application" if is_application else "admin")
            if is_application and failure == "close":
                raise RuntimeError("private-credential-sentinel")

        database.close = close
        if is_application and failure == "check":
            def unsafe():
                raise RuntimeError("private-credential-sentinel")
            database.assert_application_role = unsafe
        return database

    monkeypatch.setattr(migration, "Database", tracking_database)
    with pytest.raises(migration.RuntimeMigrationError, match="^Runtime migration unavailable$"):
        migration.migrate_runtime(db["configuration"])
    assert closed == ["application", "admin"]
    assert _revision_state(db) == (REQUIRED_MIGRATION,)


@pytest.mark.postgres
@pytest.mark.parametrize("change", ["head", "role_environment"])
def test_preflight_change_is_rechecked_before_schema_writes(fresh_database, monkeypatch, change):
    db = fresh_database
    from app.runtime_bootstrap import bootstrap_application_role

    def changed_after_preflight(config):
        result = bootstrap_application_role(config)
        if change == "head":
            with db["admin"].transaction() as session:
                session.execute(text("CREATE TABLE public.alembic_version(version_num varchar(32) PRIMARY KEY)"))
                session.execute(text("INSERT INTO public.alembic_version VALUES ('20261002_0010')"))
        else:
            monkeypatch.setenv("DATABASE_APP_ROLE", "unrelated")
        return result

    monkeypatch.setattr(migration, "bootstrap_application_role", changed_after_preflight)
    with pytest.raises(migration.RuntimeMigrationError):
        migration.migrate_runtime(db["configuration"])
    assert _revision_state(db) == (("20261002_0010",) if change == "head" else ())
    with db["admin"].engine.connect() as connection:
        assert connection.execute(text("SELECT to_regclass('public.projects')")).scalar_one() is None


@pytest.mark.postgres
def test_real_private_files_cli_and_owner_permission_failure(fresh_database, monkeypatch, tmp_path):
    db = fresh_database
    for name, url in (("admin", db["configuration"].admin), ("application", db["configuration"].application)):
        path = (tmp_path / name).resolve()
        path.write_text(url.render_as_string(hide_password=False) + "\n")
        path.chmod(0o600)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL_FILE", str((tmp_path / "admin").resolve()))
    monkeypatch.setenv("DEMANDRIFT_APPLICATION_DATABASE_FILE", str((tmp_path / "application").resolve()))
    result = subprocess.run([sys.executable, "-m", "app.runtime_migrate"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and result.stdout == "Runtime migration complete\n" and result.stderr == ""
    assert _revision_state(db) == (REQUIRED_MIGRATION,)
    (tmp_path / "application").chmod(0o644)
    result = subprocess.run([sys.executable, "-m", "app.runtime_migrate"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and result.stdout == "" and result.stderr == "Runtime migration unavailable\n"
    assert _revision_state(db) == (REQUIRED_MIGRATION,)
