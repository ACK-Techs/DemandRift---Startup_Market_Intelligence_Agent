"""Real PostgreSQL tests own a fresh database and restricted role per test."""
import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.db.engine import Database


@pytest.fixture
def postgres_database(monkeypatch):
    if os.environ.get("DEMANDRIFT_DB_TESTS") != "1":
        pytest.skip("PostgreSQL gate is separate: explicitly enable a disposable test server")
    raw = os.environ.get("DEMANDRIFT_TEST_ADMIN_URL")
    if not raw:
        pytest.fail("Enabled PostgreSQL tests require DEMANDRIFT_TEST_ADMIN_URL")
    url = make_url(raw)
    if url.drivername != "postgresql+psycopg":
        pytest.fail("PostgreSQL psycopg is required; SQLite does not verify this gate")
    suffix = uuid4().hex[:12]
    database_name, role = f"demandrift_test_{suffix}", f"demandrift_testapp_{suffix}"
    admin_engine = create_engine(url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    quote = admin_engine.dialect.identifier_preparer.quote
    admin_url = url.set(database=database_name)
    app_url = admin_url.set(username=role, password="ephemeral-only-db-test")
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    admin_db = app_db = None
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f"CREATE ROLE {quote(role)} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD 'ephemeral-only-db-test'")
            connection.exec_driver_sql(f"CREATE DATABASE {quote(database_name)}")
        monkeypatch.setenv("DATABASE_URL", admin_url.render_as_string(hide_password=False))
        monkeypatch.setenv("DATABASE_APP_ROLE", role)
        command.upgrade(config, "head")
        admin_db = Database(admin_url.render_as_string(hide_password=False))
        app_db = Database(app_url.render_as_string(hide_password=False), pool_size=1)
        app_db.assert_application_role()
        yield {"admin": admin_db, "app": app_db, "config": config, "role": role, "name": database_name}
    finally:
        if app_db: app_db.close()
        if admin_db: admin_db.close()
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {quote(database_name)} WITH (FORCE)")
            connection.exec_driver_sql(f"DROP ROLE IF EXISTS {quote(role)}")
        admin_engine.dispose()
