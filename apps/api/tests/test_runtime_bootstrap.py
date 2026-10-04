"""Operations bootstrap is native PostgreSQL, secret-safe and non-destructive."""

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.db.engine import Database
from app.db.migration_head import REQUIRED_MIGRATION
from app.runtime_bootstrap import (
    BootstrapConfig, RuntimeBootstrapError, bootstrap_application_role, configured_bootstrap,
    configured_bootstrap_config,
)

ADMIN = "postgresql+psycopg://demandrift_admin:admin-fixture@postgres/demandrift"
APP = "postgresql+psycopg://demandrift_app:private-fixture-password-123456@postgres/demandrift"


@pytest.mark.parametrize("admin,app,role", [
    (ADMIN, APP.replace("/demandrift", "/another"), "demandrift_app"),
    (ADMIN, APP.replace("@postgres", "@another"), "demandrift_app"),
    (ADMIN, APP.replace("demandrift_app:", "another:"), "demandrift_app"),
    (APP, APP, "demandrift_app"),
    (ADMIN, APP, "pg_superuser"),
    (ADMIN, APP, "public"),
    (ADMIN, APP, "role'; ALTER ROLE postgres SUPERUSER; --"),
    (ADMIN, APP.replace("@postgres", "@first,second"), "demandrift_app"),
    (ADMIN.replace("postgresql+psycopg", "sqlite"), APP, "demandrift_app"),
    (ADMIN, APP.replace("private-fixture-password-123456", "short"), "demandrift_app"),
])
def test_privileged_boundary_rejects_cross_database_unsafe_scope_and_role(admin, app, role):
    with pytest.raises(RuntimeBootstrapError) as failure:
        BootstrapConfig.from_dsns(admin, app, role=role)
    assert "fixture-password" not in str(failure.value)
    assert "ALTER ROLE" not in str(failure.value)


def test_config_repr_never_includes_credentials():
    config = BootstrapConfig.from_dsns(ADMIN, APP, role="demandrift_app")
    assert repr(config) == "BootstrapConfig(role='demandrift_app')"


@pytest.mark.parametrize("key", ["user", "password", "username", "dbname", "database", "service", "servicefile",
                                "passfile", "hostaddr", "sslpassword", "sslkey", "options"])
def test_query_identity_credentials_files_and_arbitrary_options_cannot_override_private_urls(key, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid configuration reached the privileged database")

    monkeypatch.setattr("app.runtime_bootstrap.Database", forbidden)
    admin = make_url(ADMIN).update_query_dict({key: "demandrift_admin"})
    application = make_url(APP).update_query_dict({key: "demandrift_admin"})
    with pytest.raises(RuntimeBootstrapError) as failure:
        BootstrapConfig.from_dsns(admin.render_as_string(hide_password=False),
                                  application.render_as_string(hide_password=False), role="demandrift_app")
    assert "fixture" not in str(failure.value)
    forged = BootstrapConfig(admin, application, "demandrift_app")
    with pytest.raises(RuntimeBootstrapError, match="unavailable"):
        bootstrap_application_role(forged)


@pytest.mark.parametrize("query", [
    {"sslmode": ("require", "require")},
    {"sslmode": ("require", "disable")},
    {"host": ("/private/socket", "/private/socket"), "port": "16532"},
    {"host": ("/private/socket", "/another/socket"), "port": "16532"},
    {"host": "/private/socket", "port": ("16532", "16532")},
    {"host": "/private/socket", "port": ("16532", "5432")},
])
def test_repeated_query_values_are_rejected_including_identical_values(query):
    admin = make_url(ADMIN)._replace(host=None, port=None).set(query=query)
    application = make_url(APP)._replace(host=None, port=None).set(query=query)
    with pytest.raises(RuntimeBootstrapError):
        BootstrapConfig.from_dsns(admin.render_as_string(hide_password=False),
                                  application.render_as_string(hide_password=False), role="demandrift_app")


@pytest.mark.parametrize("query", ["user=", "password=", "sslmode=", "sslmode=require&sslmode=",
                                  "sslmode=&sslmode=require", "%75ser=demandrift_admin", "sslmode"])
def test_raw_query_identity_blank_values_and_repeats_cannot_disappear_during_url_parsing(query):
    with pytest.raises(RuntimeBootstrapError):
        BootstrapConfig.from_dsns(ADMIN + "?" + query, APP + "?" + query, role="demandrift_app")


@pytest.mark.parametrize("query", [
    {"host": "/private/socket", "port": "16532"},
    {"port": "16532"},
    {"host": "first,second", "port": "16532"},
    {"host": "/private/socket,/another/socket", "port": "16532"},
    {"sslmode": "invalid"},
    {"sslmode": ""},
])
def test_query_routing_cannot_override_an_authority_host_or_expand_connection_targets(query):
    admin, application = make_url(ADMIN).set(query=query), make_url(APP).set(query=query)
    with pytest.raises(RuntimeBootstrapError):
        BootstrapConfig.from_dsns(admin.render_as_string(hide_password=False),
                                  application.render_as_string(hide_password=False), role="demandrift_app")


@pytest.mark.parametrize("query", [
    {}, {"host": "postgres", "port": "16532"}, {"host": "/private/socket"},
    {"host": "/private/../socket", "port": "16532"},
    {"host": "/private/socket", "port": "0"},
    {"host": "/private/socket", "port": "65536"},
    {"host": "/private/socket", "port": "16532,5432"},
])
def test_unix_socket_requires_one_explicit_absolute_directory_and_bounded_port(query):
    admin = make_url(ADMIN)._replace(host=None, port=None).set(query=query)
    application = make_url(APP)._replace(host=None, port=None).set(query=query)
    with pytest.raises(RuntimeBootstrapError):
        BootstrapConfig.from_dsns(admin.render_as_string(hide_password=False),
                                  application.render_as_string(hide_password=False), role="demandrift_app")


@pytest.mark.parametrize("database", [None, "", "host=another user=demandrift_admin", "postgresql://another/private"])
def test_missing_or_connection_string_database_cannot_expand_libpq_configuration(database):
    admin, application = make_url(ADMIN)._replace(database=database), make_url(APP)._replace(database=database)
    with pytest.raises(RuntimeBootstrapError):
        BootstrapConfig.from_dsns(admin.render_as_string(hide_password=False),
                                  application.render_as_string(hide_password=False), role="demandrift_app")


@pytest.mark.parametrize("password", [None, "x" * 15, "x" * 257, "private-fixture-password\n",
                                     "private-fixture-password\x7f", "private-fixture-passwordé"])
def test_missing_or_weak_application_password_fails_without_disclosing_it(password):
    application = make_url(APP)._replace(password=password)
    with pytest.raises(RuntimeBootstrapError) as failure:
        BootstrapConfig.from_dsns(ADMIN, application.render_as_string(hide_password=False), role="demandrift_app")
    assert "private-fixture" not in str(failure.value)


def test_single_authority_defaults_to_explicit_port_and_accepts_bounded_sslmode():
    config = BootstrapConfig.from_dsns(ADMIN + "?sslmode=require", APP + "?sslmode=require", role="demandrift_app")
    assert config.admin.host == config.application.host == "postgres"
    assert config.admin.port == config.application.port == 5432
    assert config.application.query == {"sslmode": "require"}
    assert config.application.username == "demandrift_app"
    assert config.application.password == make_url(APP).password


def test_missing_application_file_configuration_fails_without_sql_or_credentials(monkeypatch):
    monkeypatch.setattr("app.runtime_bootstrap.runtime_secret", lambda *args, **kwargs: ADMIN)
    monkeypatch.delenv("DEMANDRIFT_APPLICATION_DATABASE_FILE", raising=False)
    with pytest.raises(RuntimeBootstrapError, match="unavailable") as failure:
        configured_bootstrap_config()
    assert "admin-fixture" not in str(failure.value)


def native_config(fixture):
    return BootstrapConfig.from_dsns(fixture["admin"].engine.url.render_as_string(hide_password=False),
                                    fixture["app"].engine.url.render_as_string(hide_password=False), role=fixture["role"])


@pytest.mark.postgres
@pytest.mark.parametrize("key", ["user", "password"])
@pytest.mark.parametrize("state", ["existing", "new"])
def test_native_query_override_is_rejected_before_sql_without_adopting_admin_or_changing_role(postgres_database, monkeypatch, key, state):
    db = postgres_database
    role = db["role"] if state == "existing" else "demandrift_bootstrap_" + uuid4().hex[:12]
    with db["admin"].transaction() as session:
        before = session.execute(text("SELECT rolpassword FROM pg_authid WHERE rolname=:role"), {"role": role}).one_or_none()
    admin = db["admin"].engine.url.update_query_dict({key: db["admin"].engine.url.username})
    application = db["app"].engine.url.set(username=role).update_query_dict({key: db["admin"].engine.url.username})

    def forbidden(*args, **kwargs):
        pytest.fail("query override reached privileged SQL")

    with monkeypatch.context() as guard:
        guard.setattr("app.runtime_bootstrap.Database", forbidden)
        with pytest.raises(RuntimeBootstrapError):
            BootstrapConfig.from_dsns(admin.render_as_string(hide_password=False),
                                      application.render_as_string(hide_password=False), role=role)
        with pytest.raises(RuntimeBootstrapError, match="unavailable"):
            bootstrap_application_role(BootstrapConfig(admin, application, role))
    with db["admin"].transaction() as session:
        after = session.execute(text("SELECT rolpassword FROM pg_authid WHERE rolname=:role"), {"role": role}).one_or_none()
    assert before == after
    assert (before is None) == (state == "new")
    with db["app"].transaction() as session:
        current = session.execute(text("SELECT current_user, session_user, (SELECT rolsuper FROM pg_roles WHERE rolname=current_user)")).one()
    assert tuple(current) == (db["role"], db["role"], False)
    db["app"].assert_application_role()


@pytest.mark.postgres
def test_existing_scram_matches_without_password_rotation_and_bad_password_is_rejected(postgres_database):
    config = native_config(postgres_database)
    with postgres_database["admin"].transaction() as session:
        original = session.execute(text("SELECT rolpassword FROM pg_authid WHERE rolname=:role"), {"role": config.role}).scalar_one()
    assert original.startswith("SCRAM-SHA-256$")
    assert bootstrap_application_role(config) == "existing"
    forged = replace(config, application=config.application.set(password="different-private-fixture-123456"))
    with pytest.raises(RuntimeBootstrapError, match="unavailable"):
        bootstrap_application_role(forged)
    with postgres_database["admin"].transaction() as session:
        assert session.execute(text("SELECT rolpassword FROM pg_authid WHERE rolname=:role"), {"role": config.role}).scalar_one() == original
    postgres_database["app"].assert_application_role()


@pytest.mark.postgres
@pytest.mark.parametrize("unsafe", ["superuser", "bypassrls", "createrole", "createdb", "replication", "nologin", "table_owner"])
def test_existing_unsafe_role_is_not_adopted_or_repaired(postgres_database, unsafe):
    db = postgres_database
    quote = db["admin"].engine.dialect.identifier_preparer.quote
    with db["admin"].transaction() as session:
        if unsafe == "table_owner":
            session.execute(text(f"ALTER TABLE public.projects OWNER TO {quote(db['role'])}"))
        else:
            session.execute(text(f"ALTER ROLE {quote(db['role'])} {unsafe.upper()}"))
    try:
        with pytest.raises(RuntimeBootstrapError, match="unavailable"):
            bootstrap_application_role(native_config(db))
        with db["admin"].transaction() as session:
            if unsafe == "table_owner":
                assert session.execute(text("SELECT relowner::regrole::text FROM pg_class WHERE oid='public.projects'::regclass")).scalar_one() == db["role"]
            elif unsafe != "nologin":
                column = {"superuser":"rolsuper", "bypassrls":"rolbypassrls", "createrole":"rolcreaterole", "createdb":"rolcreatedb", "replication":"rolreplication"}[unsafe]
                assert session.execute(text(f"SELECT {column} FROM pg_roles WHERE rolname=:role"), {"role":db["role"]}).scalar_one() is True
    finally:
        with db["admin"].transaction() as session:
            if unsafe == "table_owner":
                session.execute(text(f"ALTER TABLE public.projects OWNER TO {quote(db['admin'].engine.url.username)}"))
            else:
                session.execute(text(f"ALTER ROLE {quote(db['role'])} {'LOGIN' if unsafe == 'nologin' else 'NO'+unsafe.upper()}"))


@pytest.mark.postgres
def test_restricted_account_cannot_bootstrap_roles(postgres_database):
    config = native_config(postgres_database)
    wrong = replace(config, admin=config.application, application=config.admin, role=config.admin.username)
    with pytest.raises(RuntimeBootstrapError, match="unavailable"):
        bootstrap_application_role(wrong)
    postgres_database["app"].assert_application_role()


@pytest.fixture
def bootstrap_history_database(monkeypatch):
    from native_phase1_fixture import historical_database
    yield from historical_database(monkeypatch, head="20261001_0001")


@pytest.mark.postgres
def test_new_role_precedes_first_migration_and_cannot_administer_afterwards(bootstrap_history_database, monkeypatch):
    db = bootstrap_history_database
    role = "demandrift_bootstrap_" + uuid4().hex[:12]
    password = "bootstrap-fixture-'quote-$-\\-123456789"
    quote = db["admin"].engine.dialect.identifier_preparer.quote
    app_url = db["admin"].engine.url.set(username=role, password=password)
    config = BootstrapConfig.from_dsns(db["admin"].engine.url.render_as_string(hide_password=False), app_url.render_as_string(hide_password=False), role=role)
    application = None
    try:
        command.downgrade(db["config"], "base")
        assert bootstrap_application_role(config) == "created"
        assert bootstrap_application_role(config) == "existing"
        monkeypatch.setenv("DATABASE_APP_ROLE", role)
        command.upgrade(db["config"], "head")
        application = Database(app_url.render_as_string(hide_password=False))
        application.assert_application_role()
        with application.transaction() as session:
            assert session.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one() == REQUIRED_MIGRATION
            assert session.execute(text("SELECT count(*) FROM public.projects")).scalar_one() == 0
            flags = session.execute(text("SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls,rolreplication,rolinherit,rolconnlimit FROM pg_roles WHERE rolname=current_user")).one()
            assert tuple(flags) == (False,False,False,False,False,False,20)
    finally:
        if application is not None:
            application.close()
        with db["admin"].transaction() as session:
            session.execute(text(f"DROP OWNED BY {quote(role)}"))
            session.execute(text(f"DROP ROLE IF EXISTS {quote(role)}"))


@pytest.mark.postgres
def test_configured_files_use_isolated_child_loader_and_preserve_parent_environment(postgres_database, monkeypatch, tmp_path):
    db = postgres_database
    for name, value in [("admin", db["admin"].engine.url.render_as_string(hide_password=False)),
                        ("app", db["app"].engine.url.render_as_string(hide_password=False))]:
        path = (tmp_path / name).resolve()
        path.write_text(value + "\n")
        path.chmod(0o600)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL_FILE", str((tmp_path / "admin").resolve()))
    monkeypatch.setenv("DEMANDRIFT_APPLICATION_DATABASE_FILE", str((tmp_path / "app").resolve()))
    monkeypatch.setenv("DATABASE_APP_ROLE", db["role"])
    original = (tmp_path / "admin").resolve()
    with monkeypatch.context() as guard:
        def forbidden(*args, **kwargs):
            pytest.fail("configuration loader attempted privileged SQL")

        guard.setattr("app.runtime_bootstrap.Database", forbidden)
        config = configured_bootstrap_config()
    assert config.role == config.application.username == db["role"]
    assert config.admin.username == db["admin"].engine.url.username
    assert "ephemeral-only" not in repr(config)
    assert configured_bootstrap() == "existing"
    import os
    assert Path(os.environ["DATABASE_URL_FILE"]) == original
    assert not (tmp_path / "admin").is_symlink()
    (tmp_path / "app").chmod(0o644)
    with pytest.raises(RuntimeBootstrapError, match="unavailable"):
        configured_bootstrap()


@pytest.mark.postgres
@pytest.mark.parametrize("boundary", ["membership", "expired"])
def test_existing_privilege_membership_or_expired_login_is_rejected_without_repair(postgres_database, boundary):
    db = postgres_database
    quote = db["admin"].engine.dialect.identifier_preparer.quote
    other = "demandrift_bootstrap_member_" + uuid4().hex[:10]
    with db["admin"].transaction() as session:
        if boundary == "membership":
            session.execute(text(f"CREATE ROLE {quote(other)} NOLOGIN"))
            session.execute(text(f"GRANT {quote(other)} TO {quote(db['role'])} WITH INHERIT FALSE"))
        else:
            session.execute(text(f"ALTER ROLE {quote(db['role'])} VALID UNTIL '2000-01-01'"))
    try:
        with pytest.raises(RuntimeBootstrapError, match="unavailable"):
            bootstrap_application_role(native_config(db))
    finally:
        with db["admin"].transaction() as session:
            if boundary == "membership":
                session.execute(text(f"REVOKE {quote(other)} FROM {quote(db['role'])}"))
                session.execute(text(f"DROP ROLE {quote(other)}"))
            else:
                session.execute(text(f"ALTER ROLE {quote(db['role'])} VALID UNTIL 'infinity'"))
