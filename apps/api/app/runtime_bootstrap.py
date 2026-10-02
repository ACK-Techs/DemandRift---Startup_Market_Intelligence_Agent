"""Trusted, operations-only application role bootstrap; never imported by API/worker."""

import base64
from dataclasses import dataclass, field
import hashlib
import hmac
import ipaddress
import os
import re
import subprocess
import sys
from urllib.parse import parse_qsl, urlsplit

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url

from app.db.engine import Database
from app.runtime_secrets import runtime_secret


class RuntimeBootstrapError(RuntimeError):
    pass


def _private_url(dsn: str) -> URL:
    if type(dsn) is not str or not 1 <= len(dsn) <= 4096:
        raise ValueError()
    split = urlsplit(dsn)
    if split.fragment:
        raise ValueError()
    # make_url drops blank query values; reject them and duplicate keys before
    # that normalization can erase an invalid credential or route option.
    pairs = parse_qsl(split.query, keep_blank_values=True, strict_parsing=True,
                      max_num_fields=3, encoding="ascii", errors="strict")
    if (len({key for key, _ in pairs}) != len(pairs)
            or any(key not in {"host", "port", "sslmode"} or not value for key, value in pairs)):
        raise ValueError()
    url = make_url(dsn)
    if dict(pairs) != dict(url.query):
        raise ValueError()
    return _explicit_connection_url(url)


def _explicit_connection_url(url: URL) -> URL:
    """Limit libpq kwargs before they can override URL identity or routing."""
    # SQLAlchemy merges query kwargs over URL credentials. A denylist is not a
    # complete identity boundary: service files and future options can add aliases.
    if (not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", url.username or "")
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,62}", url.database or "")
            or any(key not in {"host", "port", "sslmode"} or type(value) is not str
                   for key, value in url.query.items())):
        raise ValueError()
    if "sslmode" in url.query and url.query["sslmode"] not in {
        "disable", "allow", "prefer", "require", "verify-ca", "verify-full"
    }:
        raise ValueError()
    socket = url.query.get("host")
    query_port = url.query.get("port")
    if socket is not None:
        # The native fixture uses one absolute Unix socket directory and port.
        # An authority host/port cannot coexist with query routing overrides.
        if (url.host is not None or url.port is not None or not socket.startswith("/")
                or len(socket) > 4096 or not socket.isascii()
                or any(not 32 <= ord(char) <= 126 for char in socket) or "," in socket
                or "//" in socket or any(part in {".", ".."} for part in socket.split("/"))
                or query_port is None or not re.fullmatch(r"[1-9][0-9]{0,4}", query_port)
                or not 1 <= int(query_port) <= 65535):
            raise ValueError()
    else:
        if type(url.host) is not str or not url.host or len(url.host) > 253 or query_port is not None:
            raise ValueError()
        try:
            ipaddress.ip_address(url.host)
        except ValueError:
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,252}", url.host):
                raise ValueError() from None
        if url.port is not None and (type(url.port) is not int or not 1 <= url.port <= 65535):
            raise ValueError()
        # Resolve the ordinary PostgreSQL default explicitly instead of leaving
        # the authority's missing port to libpq environment fallback.
        if url.port is None:
            url = url.set(port=5432)
    return url


@dataclass(frozen=True)
class BootstrapConfig:
    admin: URL = field(repr=False)
    application: URL = field(repr=False)
    role: str

    @classmethod
    def from_dsns(cls, admin: str, application: str, *, role: str):
        try:
            admin_url, app_url = _private_url(admin), _private_url(application)
            if (type(role) is not str or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", role)
                    or role.startswith("pg_") or role in ("postgres", "public")
                    or admin_url.drivername != "postgresql+psycopg"
                    or app_url.drivername != "postgresql+psycopg"
                    or not admin_url.database or not admin_url.username
                    or app_url.username != role or admin_url.username == role
                    or admin_url._replace(username=None, password=None) != app_url._replace(username=None, password=None)
                    or type(app_url.password) is not str or not 16 <= len(app_url.password) <= 256
                    or not app_url.password.isascii()
                    or any(not 33 <= ord(char) <= 126 for char in app_url.password)):
                raise ValueError()
            return cls(admin_url, app_url, role)
        except Exception:
            raise RuntimeBootstrapError("Explicit same-database private runtime credentials required") from None


def _scram_matches(password: str, verifier: str | None) -> bool:
    try:
        if type(verifier) is not str or len(verifier) > 512:
            return False
        mechanism, work, keys = verifier.split("$")
        iterations, salt = work.split(":")
        stored, server = keys.split(":")
        if mechanism != "SCRAM-SHA-256" or not re.fullmatch(r"[1-9][0-9]{3,6}", iterations):
            return False
        count = int(iterations)
        if not 4096 <= count <= 1_000_000:
            return False
        salt = base64.b64decode(salt, validate=True)
        stored, server = base64.b64decode(stored, validate=True), base64.b64decode(server, validate=True)
        if not 8 <= len(salt) <= 64 or len(stored) != 32 or len(server) != 32:
            return False
        salted = hashlib.pbkdf2_hmac("sha256", password.encode("ascii"), salt, count)
        expected_stored = hashlib.sha256(hmac.digest(salted, b"Client Key", "sha256")).digest()
        expected_server = hmac.digest(salted, b"Server Key", "sha256")
        return hmac.compare_digest(stored, expected_stored) and hmac.compare_digest(server, expected_server)
    except (ValueError, TypeError, UnicodeError):
        return False


def bootstrap_application_role(config: BootstrapConfig) -> str:
    """Create once or validate existing role; never rotate/reset an existing password."""
    database = None
    try:
        # Revalidate even a forged dataclass; this operation is privileged.
        config = BootstrapConfig.from_dsns(config.admin.render_as_string(hide_password=False),
                                           config.application.render_as_string(hide_password=False), role=config.role)
        database = Database(config.admin.render_as_string(hide_password=False), pool_size=1)
        with database.transaction() as session:
            session.execute(text("SET LOCAL log_statement = 'none'"))
            session.execute(text("SET LOCAL log_min_duration_statement = -1"))
            session.execute(text("SET LOCAL log_min_duration_sample = -1"))
            session.execute(text("SET LOCAL log_statement_sample_rate = 0"))
            session.execute(text("SET LOCAL log_transaction_sample_rate = 0"))
            session.execute(text("SET LOCAL log_parameter_max_length = 0"))
            session.execute(text("SET LOCAL log_min_error_statement = 'panic'"))
            session.execute(text("SET LOCAL log_parameter_max_length_on_error = 0"))
            session.execute(text("SET LOCAL log_error_verbosity = 'terse'"))
            session.execute(text("SET LOCAL password_encryption = 'scram-sha-256'"))
            if session.execute(text("SELECT current_user = :expected AND session_user = :expected AND "
                                    "(SELECT rolsuper FROM pg_roles WHERE rolname=current_user)"),
                               {"expected": config.admin.username}).scalar_one() is not True:
                raise ValueError()
            # Serialize this fixed role without mutating another bootstrap attempt.
            session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:role, 0))"), {"role": config.role})
            existing = session.execute(text("""
                SELECT r.rolcanlogin AND (r.rolvaliduntil IS NULL OR r.rolvaliduntil > now()),
                       r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
                       OR r.rolbypassrls OR r.rolreplication
                       OR EXISTS (SELECT 1 FROM pg_auth_members m WHERE m.member=r.oid)
                       OR EXISTS (SELECT 1 FROM pg_shdepend d WHERE d.refclassid='pg_authid'::regclass
                                  AND d.refobjid=r.oid AND d.deptype='o'), r.rolpassword
                FROM pg_authid r WHERE r.rolname=:role
            """), {"role": config.role}).one_or_none()
            if existing is not None:
                if existing[0] is not True or existing[1] is not False or not _scram_matches(config.application.password, existing[2]):
                    raise ValueError()
                return "existing"
            session.execute(text("SELECT set_config('demandrift.bootstrap_role', :role, true), "
                                 "set_config('demandrift.bootstrap_password', :password, true)"),
                            {"role": config.role, "password": config.application.password})
            # Bound parameters never become a command argument or literal SQL in
            # the client. Server utility DDL is formatted only inside this transaction.
            session.execute(text("""
                DO $bootstrap$ BEGIN
                    EXECUTE format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                                   'NOBYPASSRLS NOREPLICATION NOINHERIT CONNECTION LIMIT 20 PASSWORD %L',
                                   current_setting('demandrift.bootstrap_role'),
                                   current_setting('demandrift.bootstrap_password'));
                END $bootstrap$;
            """))
            return "created"
    except Exception:
        raise RuntimeBootstrapError("Application role bootstrap unavailable") from None
    finally:
        if database is not None:
            database.close()


def configured_bootstrap_config() -> BootstrapConfig:
    """Load operations-only private FILEs without SQL or environment mutation."""
    try:
        admin = runtime_secret("DATABASE_URL", allow_environment=False)
        app_file = os.environ["DEMANDRIFT_APPLICATION_DATABASE_FILE"]
        # An isolated bounded child reuses the complete no-follow private FILE
        # loader without changing the parent's environment or duplicating policy.
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("DATABASE_URL", "GEMINI_API_KEY", "GEMINI_API_KEY_FILE",
                                      "DEMANDRIFT_BROKER_URL", "DEMANDRIFT_BROKER_URL_FILE")}
        environment["DATABASE_URL_FILE"] = app_file
        child = subprocess.run([sys.executable, "-c", "import sys; from app.runtime_secrets import runtime_secret; "
                                "sys.stdout.write(runtime_secret('DATABASE_URL', allow_environment=False))"],
                               env=environment, capture_output=True, check=False, timeout=5)
        if child.returncode != 0 or not 1 <= len(child.stdout) <= 4096:
            raise ValueError()
        return BootstrapConfig.from_dsns(admin, child.stdout.decode("ascii"),
                                         role=os.environ.get("DATABASE_APP_ROLE", "demandrift_app"))
    except Exception:
        raise RuntimeBootstrapError("Application role bootstrap unavailable") from None


def configured_bootstrap() -> str:
    return bootstrap_application_role(configured_bootstrap_config())


if __name__ == "__main__":
    try:
        configured_bootstrap()
    except RuntimeBootstrapError:
        raise SystemExit(1) from None
