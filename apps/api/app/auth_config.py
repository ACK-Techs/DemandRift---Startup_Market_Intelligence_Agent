"""Versioned backend-only authentication policy."""

from dataclasses import dataclass
import os
from urllib.parse import urlsplit


def exact_origin(value: str) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or any(c in value for c in "\r\n,\\")
    ):
        raise ValueError("An exact HTTP origin is required")
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme in ("http", "https")
            and parsed.hostname
            and parsed.path == ""
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
        )
        if not valid:
            raise ValueError()
        port = parsed.port
        host = parsed.hostname.lower()
        canonical = f"{parsed.scheme}://{host}" + (
            f":{port}" if port is not None else ""
        )
        if canonical != value or (
            parsed.scheme == "http" and host not in ("localhost", "127.0.0.1")
        ):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("An exact HTTPS or loopback HTTP origin is required") from None
    return value


@dataclass(frozen=True)
class AuthPolicy:
    origins: tuple[str, ...]
    cookie_name: str = "demandrift_session"
    cookie_secure: bool = True
    cookie_same_site: str = "lax"
    session_seconds: int = 86400
    rate_window_seconds: int = 600
    account_attempts: int = 10
    peer_attempts: int = 100
    max_body_bytes: int = 16384
    version: str = "auth-2026-10-01.1"

    def __post_init__(self):
        if not self.origins or len(set(self.origins)) != len(self.origins):
            raise ValueError("Exact allowed origins required")
        for origin in self.origins:
            exact_origin(origin)
        if self.cookie_name != "demandrift_session" or self.cookie_secure is not True:
            raise ValueError("Backend cookies require the fixed secure session policy")
        if self.cookie_same_site not in ("lax", "none") or (
            self.cookie_same_site == "none" and not self.cookie_secure
        ):
            raise ValueError("Cross-origin cookies require HTTPS")
        for key in [
            "session_seconds",
            "rate_window_seconds",
            "account_attempts",
            "peer_attempts",
            "max_body_bytes",
        ]:
            if type(getattr(self, key)) is not int or getattr(self, key) <= 0:
                raise ValueError("Positive finite auth policy limits required")
        if self.session_seconds > 86400 or self.max_body_bytes > 16384:
            raise ValueError("Auth policy limits exceed supported bounds")

    @classmethod
    def from_environment(cls):
        value = os.environ.get("CORS_ALLOWED_ORIGINS", "")
        if not value:
            raise ValueError("Explicit local frontend origins are required")
        return cls(
            origins=tuple(value.split(",")),
            cookie_same_site=os.environ.get("AUTH_COOKIE_SAME_SITE", "lax"),
        )
