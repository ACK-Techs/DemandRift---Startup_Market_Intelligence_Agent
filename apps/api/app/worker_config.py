"""Explicit backend-only queue configuration with bounded native leases."""

from dataclasses import dataclass, field
import os
import re
from urllib.parse import urlsplit
from app.runtime_secrets import RuntimeSecretError, runtime_secret

TASK_NAME = "demandrift.jobs.wake"


@dataclass(frozen=True)
class WorkerSettings:
    broker_url: str = field(repr=False)
    queue: str = "demandrift.jobs"
    key_prefix: str = "demandrift:"
    lease_seconds: int = 30
    visibility_seconds: int = 300
    handler_seconds: int = 300

    def __post_init__(self):
        try:
            parsed = urlsplit(self.broker_url)
            if (
                parsed.scheme not in ("redis", "rediss")
                or not parsed.hostname
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError()
            if parsed.path and not re.fullmatch(r"/(?:[0-9]|1[0-5])", parsed.path):
                raise ValueError()
            if parsed.port is not None and not 1 <= parsed.port <= 65535:
                raise ValueError()
            if not re.fullmatch(
                r"[a-zA-Z0-9_.-]{1,100}", self.queue
            ) or not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,100}", self.key_prefix):
                raise ValueError()
            if (
                type(self.lease_seconds) is not int
                or not 1 <= self.lease_seconds <= 300
            ):
                raise ValueError()
            if (
                type(self.visibility_seconds) is not int
                or not self.lease_seconds <= self.visibility_seconds <= 3600
            ):
                raise ValueError()
            if (
                type(self.handler_seconds) is not int
                or not self.lease_seconds <= self.handler_seconds <= 3600
            ):
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError(
                "Explicit Redis queue settings and bounded leases required"
            ) from None

    @classmethod
    def from_environment(cls):
        try:
            return cls(
                broker_url=runtime_secret("DEMANDRIFT_BROKER_URL",
                    allow_environment=os.environ.get("APP_ENV") != "production"),
                queue=os.environ.get("DEMANDRIFT_WORKER_QUEUE", "demandrift.jobs"),
                handler_seconds=int(os.environ.get("DEMANDRIFT_HANDLER_SECONDS", "1800")),
                visibility_seconds=int(os.environ.get("DEMANDRIFT_VISIBILITY_SECONDS", "1800")),
                key_prefix=os.environ.get(
                    "DEMANDRIFT_WORKER_KEY_PREFIX", "demandrift:"
                ),
            )
        except (KeyError, RuntimeSecretError):
            raise ValueError("Explicit worker broker configuration required") from None
