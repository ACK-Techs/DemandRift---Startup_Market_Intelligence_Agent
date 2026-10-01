"""Password/session primitives backed by PostgreSQL; no HTTP/provider calls."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
from uuid import uuid4
from threading import BoundedSemaphore
from contextlib import contextmanager

from argon2 import PasswordHasher, profiles
from argon2.exceptions import VerificationError, InvalidHashError
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.auth_config import AuthPolicy
from app.contracts import User, Session as WireSession
from app.db.engine import Database
from app.db.models import UserRecord, SessionRecord
from app.db.auth_models import AUTH_RATE_LIMITS


class AuthenticationError(ValueError):
    pass


class RegistrationError(ValueError):
    pass


class AuthRateLimited(RuntimeError):
    def __init__(self, retry_after):
        super().__init__("Authentication requests are temporarily limited")
        self.retry_after = retry_after


@dataclass(frozen=True)
class Authenticated:
    user: User
    session_hash: str
    csrf_hash: str
    expires_at: datetime

    def wire(self, token):
        return WireSession(
            user=self.user, expires_at=self.expires_at, csrf_token=csrf_token(token)
        )


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def csrf_token(token):
    return digest("demandrift/csrf/v1:" + token)


def canonical_email(value):
    if not isinstance(value, str):
        raise ValueError("A valid email is required")
    email = value.strip().lower()
    # Explicit supported email syntax; no unbounded regex or implicit coercion.
    if len(email) > 254 or not re.fullmatch(
        r"[a-z0-9.!#$%&*+/=?^_`{|}~-]{1,64}@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+",
        email,
    ):
        raise ValueError("A valid email is required")
    return email


def password_text(value):
    if (
        not isinstance(value, str)
        or not 15 <= len(value) <= 128
        or len(value.encode("utf-8")) > 1024
    ):
        raise ValueError("Password must contain 15 to 128 characters")
    return value


class AuthService:
    def __init__(self, database: Database, policy: AuthPolicy):
        self.database, self.policy = database, policy
        self.hasher = PasswordHasher.from_parameters(profiles.RFC_9106_LOW_MEMORY)
        self._dummy_hash = self.hasher.hash(secrets.token_urlsafe(32))
        self._hash_slots = BoundedSemaphore(2)

    @contextmanager
    def _hash_capacity(self):
        if not self._hash_slots.acquire(timeout=0.1):
            raise AuthRateLimited(1)
        try:
            yield
        finally:
            self._hash_slots.release()

    def rate_limit(self, action, email, peer):
        if action not in ("register", "login"):
            raise ValueError("Known authentication action required")
        # Aggregate per account across peers and per peer across accounts/actions.
        limits = sorted(
            [
                (digest("account:" + email), self.policy.account_attempts),
                (digest("peer:" + peer), self.policy.peer_attempts),
            ]
        )
        now = datetime.now(timezone.utc)
        denied = 0
        with self.database.transaction() as session:
            for key, limit in limits:
                inserted = (
                    session.execute(
                        insert(AUTH_RATE_LIMITS)
                        .values(rate_key=key, window_started_at=now, attempts=1)
                        .on_conflict_do_nothing(index_elements=["rate_key"])
                        .returning(AUTH_RATE_LIMITS.c.rate_key)
                    ).scalar_one_or_none()
                    is not None
                )
                row = (
                    session.execute(
                        select(AUTH_RATE_LIMITS)
                        .where(AUTH_RATE_LIMITS.c.rate_key == key)
                        .with_for_update()
                    )
                    .mappings()
                    .one()
                )
                elapsed = (now - row["window_started_at"]).total_seconds()
                if elapsed >= self.policy.rate_window_seconds:
                    session.execute(
                        update(AUTH_RATE_LIMITS)
                        .where(AUTH_RATE_LIMITS.c.rate_key == key)
                        .values(window_started_at=now, attempts=1)
                    )
                elif not inserted and row["attempts"] >= limit:
                    denied = max(
                        denied,
                        max(1, int(self.policy.rate_window_seconds - elapsed) + 1),
                    )
                else:
                    # First insert already consumed its attempt; avoid counting it twice.
                    if not inserted:
                        session.execute(
                            update(AUTH_RATE_LIMITS)
                            .where(AUTH_RATE_LIMITS.c.rate_key == key)
                            .values(attempts=row["attempts"] + 1)
                        )
        if denied:
            raise AuthRateLimited(denied)

    @staticmethod
    def _user(row):
        return User(
            user_id=row.user_id,
            email=row.email,
            created_at=row.created_at.astimezone(timezone.utc),
        )

    def resolve(self, token):
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise AuthenticationError("Authentication required")
        with self.database.transaction() as session:
            row = session.scalar(
                select(SessionRecord).where(
                    SessionRecord.session_hash == digest(token),
                    SessionRecord.revoked_at.is_(None),
                    SessionRecord.expires_at > datetime.now(timezone.utc),
                )
            )
            if row is None:
                raise AuthenticationError("Authentication required")
            owner = session.get(UserRecord, row.user_id)
            if owner is None:
                raise AuthenticationError("Authentication required")
            return Authenticated(
                self._user(owner),
                row.session_hash,
                row.csrf_hash,
                row.expires_at.astimezone(timezone.utc),
            )

    def require_csrf(self, authenticated, provided):
        if (
            not isinstance(provided, str)
            or not re.fullmatch(r"[0-9a-f]{64}", provided)
            or not secrets.compare_digest(authenticated.csrf_hash, digest(provided))
        ):
            raise AuthenticationError("Request verification failed")

    def _new_session(self, session, owner, prior_token=None):
        now = datetime.now(timezone.utc)
        token = secrets.token_urlsafe(32)
        expires = now + timedelta(seconds=self.policy.session_seconds)
        if isinstance(prior_token, str) and re.fullmatch(
            r"[A-Za-z0-9_-]{43}", prior_token
        ):
            session.execute(
                update(SessionRecord)
                .where(
                    SessionRecord.session_hash == digest(prior_token),
                    SessionRecord.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
        row = SessionRecord(
            session_hash=digest(token),
            csrf_hash=digest(csrf_token(token)),
            user_id=owner.user_id,
            created_at=now,
            expires_at=expires,
        )
        session.add(row)
        session.flush()
        return token, Authenticated(
            self._user(owner), row.session_hash, row.csrf_hash, expires
        )

    def register(self, email, password, peer, prior_token=None):
        email = canonical_email(email)
        password = password_text(password)
        self.rate_limit("register", email, peer)
        with self._hash_capacity():
            hashed = self.hasher.hash(password)
        try:
            with self.database.transaction() as session:
                owner = UserRecord(
                    user_id=uuid4(),
                    email=email,
                    password_hash=hashed,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(owner)
                session.flush()
                return self._new_session(session, owner, prior_token)
        except IntegrityError:
            raise RegistrationError("Registration could not be completed") from None

    def login(self, email, password, peer, prior_token=None):
        email = canonical_email(email)
        password = password_text(password)
        self.rate_limit("login", email, peer)
        with self.database.transaction() as session:
            owner = session.scalar(select(UserRecord).where(UserRecord.email == email))
            selected = owner.password_hash if owner is not None else self._dummy_hash
        try:
            with self._hash_capacity():
                verified = self.hasher.verify(selected, password)
        except (VerificationError, InvalidHashError):
            verified = False
        if owner is None or not verified:
            raise AuthenticationError("Email or password is invalid")
        replacement = None
        if self.hasher.check_needs_rehash(selected):
            with self._hash_capacity():
                replacement = self.hasher.hash(password)
        with self.database.transaction() as session:
            # Password could change during the expensive check; verify stored hash has not changed.
            locked = session.scalar(
                select(UserRecord)
                .where(UserRecord.user_id == owner.user_id)
                .with_for_update()
            )
            if locked is None or locked.password_hash != selected:
                raise AuthenticationError("Email or password is invalid")
            if replacement is not None:
                locked.password_hash = replacement
            return self._new_session(session, locked, prior_token)

    def logout(self, authenticated):
        with self.database.transaction() as session:
            session.execute(
                update(SessionRecord)
                .where(
                    SessionRecord.session_hash == authenticated.session_hash,
                    SessionRecord.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(timezone.utc))
            )
