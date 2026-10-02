"""Real libpq faults and native role checks bound isolated dependency probes."""

import socket
import struct
import threading
import time
from contextlib import contextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.engine import Database, DatabaseConfigurationError
from app.db.migration_head import REQUIRED_MIGRATION
from app.runtime_health import database_ready


@contextmanager
def authenticated_unanswered_peer(*, trickle=False):
    """A real PostgreSQL wire handshake, then ACKed query without a result."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(5)
    authenticated, query, closed = (threading.Event() for _ in range(3))

    def message(kind, body):
        return kind + struct.pack("!I", len(body) + 4) + body

    def peer():
        try:
            with listener.accept()[0] as connection:
                connection.settimeout(5)

                def exact(size):
                    result = b""
                    while len(result) < size:
                        chunk = connection.recv(size - len(result))
                        if not chunk:
                            raise EOFError()
                        result += chunk
                    return result

                size = struct.unpack("!I", exact(4))[0]
                body = exact(size - 4)
                if size == 8 and body == struct.pack("!I", 80877103):
                    connection.sendall(b"N")
                    size = struct.unpack("!I", exact(4))[0]
                    exact(size - 4)
                connection.sendall(message(b"R", struct.pack("!I", 0))
                                   + message(b"S", b"server_version\x0016.15\x00")
                                   + message(b"S", b"client_encoding\x00UTF8\x00")
                                   + message(b"K", struct.pack("!II", 42, 43))
                                   + message(b"Z", b"I"))
                authenticated.set()
                if not connection.recv(65536):
                    closed.set()
                    return
                query.set()
                # An incomplete result with continuing readable bytes must not
                # renew the deadline or evade the native wait timeout.
                if trickle:
                    connection.sendall(b"T" + struct.pack("!I", 100000))
                connection.settimeout(0.05)
                end = time.monotonic() + 4.5
                while time.monotonic() < end:
                    try:
                        if connection.recv(65536) == b"":
                            closed.set()
                            return
                    except TimeoutError:
                        if trickle:
                            connection.sendall(b"\x00")
                    except ConnectionResetError:
                        closed.set()
                        return
        except (EOFError, BrokenPipeError, ConnectionResetError):
            closed.set()

    thread = threading.Thread(target=peer)
    thread.start()
    try:
        yield listener.getsockname()[1], authenticated, query, closed
    finally:
        thread.join(timeout=5)
        listener.close()
        assert not thread.is_alive()


@pytest.mark.parametrize("trickle", [False, True])
def test_authenticated_acknowledged_unanswered_query_closes_under_shared_probe_deadline(trickle):
    with authenticated_unanswered_peer(trickle=trickle) as (port, authenticated, query, closed):
        db = Database(f"postgresql+psycopg://probe:fixture-canary@127.0.0.1:{port}/probe", probe=True)
        start = time.monotonic()
        try:
            with pytest.raises(DBAPIError) as failure:
                with db.engine.connect():
                    pytest.fail("Authenticated unanswered initialization cannot become ready")
            assert 2.5 <= time.monotonic() - start < 3.8
            assert authenticated.is_set() and query.is_set()
            assert closed.wait(0.5), "Held exception must not keep the native socket alive"
            assert failure.value is not None
        finally:
            db.close()


def test_readiness_returns_false_for_authenticated_unanswered_query():
    with authenticated_unanswered_peer() as (port, authenticated, query, closed):
        db = Database(f"postgresql+psycopg://probe:fixture-canary@127.0.0.1:{port}/probe")
        start = time.monotonic()
        try:
            assert database_ready(db) is False
            assert 2.5 <= time.monotonic() - start < 3.8
            assert authenticated.is_set() and query.is_set() and closed.wait(0.5)
        finally:
            db.close()


@pytest.mark.postgres
def test_probe_deadline_is_shared_across_successful_connections(postgres_database):
    probe = postgres_database["app"].readiness_probe()
    try:
        with probe.transaction() as session:
            assert session.execute(text("SELECT 1")).scalar_one() == 1
        time.sleep(3.05)
        start = time.monotonic()
        with pytest.raises(DBAPIError):
            with probe.transaction():
                pytest.fail("A new connection cannot refresh an expired probe deadline")
        assert time.monotonic() - start < 0.5
    finally:
        probe.close()


@pytest.mark.parametrize("query", ["", "?connect_timeout=0&tcp_user_timeout=0"])
def test_real_silent_handshake_closes_connection_without_background_probe(query):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(5)
    accepted, release, ended, peer_closed = (threading.Event() for _ in range(4))

    def silent_peer():
        try:
            with listener.accept()[0] as connection:
                accepted.set()
                connection.settimeout(4)
                while True:
                    try:
                        data = connection.recv(65536)
                    except ConnectionResetError:
                        peer_closed.set()
                        break
                    if data == b"":
                        peer_closed.set()
                        break
        finally:
            ended.set()

    thread = threading.Thread(target=silent_peer)
    thread.start()
    db = Database(f"postgresql+psycopg://probe:fixture-canary@127.0.0.1:{listener.getsockname()[1]}/probe{query}")
    start = time.monotonic()
    try:
        with pytest.raises(DBAPIError):
            with db.engine.connect():
                pytest.fail("A silent native peer cannot establish a database connection")
        elapsed = time.monotonic() - start
        assert accepted.is_set()
        assert 1.5 <= elapsed < 4
        assert db.engine.pool.checkedout() == 0
        assert peer_closed.wait(0.5), "Failed handshake socket must close immediately without GC"
    finally:
        release.set()
        thread.join(timeout=2)
        listener.close()
        db.close()
    assert ended.is_set() and not thread.is_alive()


@pytest.mark.parametrize("dsn", [
    "postgresql+psycopg://probe@first,second/probe",
    "postgresql+psycopg://probe@/probe?host=first,second",
    "postgresql+psycopg://probe@/probe?hostaddr=127.0.0.1,127.0.0.2",
    "postgresql+psycopg://probe@/probe?host=first&host=second",
])
def test_native_connection_timeout_cannot_be_multiplied_by_host_list(dsn):
    with pytest.raises(DatabaseConfigurationError, match="valid PostgreSQL"):
        Database(dsn)


@pytest.mark.postgres
def test_fresh_probe_does_not_wait_for_application_pool_and_retains_restricted_role(postgres_database):
    db = postgres_database["app"]
    with db.transaction() as application:
        assert application.execute(text("SELECT 1")).scalar_one() == 1
        start = time.monotonic()
        probe = db.readiness_probe()
        try:
            probe.assert_application_role()
            with probe.transaction() as session:
                assert session.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one() == REQUIRED_MIGRATION
                assert session.execute(text("SELECT current_setting('app.user_id')")).scalar_one() == ""
                assert session.execute(text("SHOW statement_timeout")).scalar_one() == "500ms"
                assert session.execute(text("SHOW lock_timeout")).scalar_one() == "250ms"
            assert time.monotonic() - start < 2
        finally:
            probe.close()
        assert application.execute(text("SELECT 2")).scalar_one() == 2


@pytest.mark.postgres
def test_native_probe_cancels_stalled_statement_and_disposes_transaction(postgres_database):
    probe = postgres_database["app"].readiness_probe()
    try:
        start = time.monotonic()
        with pytest.raises(DBAPIError):
            with probe.transaction() as session:
                session.execute(text("SELECT pg_sleep(4)"))
        assert 0.35 <= time.monotonic() - start < 2
        with probe.transaction() as session:
            assert session.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        probe.close()


@pytest.mark.postgres
def test_native_probe_keeps_admin_role_rejection(postgres_database):
    probe = postgres_database["admin"].readiness_probe()
    try:
        with pytest.raises(DatabaseConfigurationError, match="must not administer"):
            probe.assert_application_role()
    finally:
        probe.close()
