"""Internal immutable admission contracts; no public or model authority inputs."""

from dataclasses import dataclass
from datetime import datetime
import math
import re
from typing import Literal
from uuid import UUID

from app.budget_contract import ResourceAmount


class AdmissionConflict(ValueError):
    """Sanitized immutable input/current preparation mismatch."""


class AdmissionUnavailable(RuntimeError):
    """Current lease, cancellation, capacity or deadline denies admission."""


class AdmissionStorageError(RuntimeError):
    """Sanitized persistent admission failure."""


def uuid_value(value):
    if type(value) is not UUID:
        raise AdmissionConflict("Resolved server UUID required")
    return value


def timeout_value(value):
    if type(value) is not int or not 1 <= value <= 60000:
        raise AdmissionConflict("Pinned timeout must be 1 through 60000 milliseconds")
    return value


def validate_input(attempt_id, fingerprint, reserved, metadata):
    uuid_value(attempt_id)
    if type(fingerprint) is not str or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
        raise AdmissionConflict("Exact operation fingerprint required")
    if type(reserved) is not ResourceAmount or reserved.requests != 1:
        raise AdmissionConflict("One bounded external request reservation required")
    names = {"kind", "operation_version", "provider", "model", "prompt_version",
             "schema_version", "pricing_version"}
    if type(metadata) is not dict or set(metadata) != names or metadata["kind"] not in ("source", "model"):
        raise AdmissionConflict("Exact versioned reservation metadata required")
    if any(type(value) is not str or re.fullmatch(r"[A-Za-z0-9._:/+=-]{1,256}", value) is None
           for value in metadata.values()):
        raise AdmissionConflict("Bounded reservation metadata required")


@dataclass(frozen=True, slots=True)
class AdmissionContext:
    mode: Literal["preparation", "job"]
    brief_id: UUID
    brief_version: int
    job_id: UUID | None = None
    lease_owner: UUID | None = None
    fence: int | None = None

    def __post_init__(self):
        uuid_value(self.brief_id)
        if type(self.brief_version) is not int or not 1 <= self.brief_version <= 2147483647:
            raise AdmissionConflict("Exact positive brief version required")
        if self.mode == "preparation":
            if any(v is not None for v in (self.job_id, self.lease_owner, self.fence)):
                raise AdmissionConflict("Preparation cannot select a job lease")
        elif self.mode == "job":
            uuid_value(self.job_id)
            uuid_value(self.lease_owner)
            if type(self.fence) is not int or not 1 <= self.fence <= 9223372036854775807:
                raise AdmissionConflict("Exact positive job fence required")
        else:
            raise AdmissionConflict("Explicit admission mode required")

    def to_json(self):
        return {"mode": self.mode, "brief_id": str(self.brief_id),
                "brief_version": self.brief_version,
                "job_id": str(self.job_id) if self.job_id is not None else None,
                "lease_owner": str(self.lease_owner) if self.lease_owner is not None else None,
                "fence": self.fence}


def context_value(value):
    if type(value) is not AdmissionContext:
        raise AdmissionConflict("Resolved admission context required")
    # Revalidate even a frozen instance modified through object.__setattr__.
    return AdmissionContext(value.mode, value.brief_id, value.brief_version,
                            value.job_id, value.lease_owner, value.fence)


def monotonic_deadline(anchor, remaining_ms, outer=None):
    if type(anchor) not in (int, float) or not math.isfinite(anchor) or anchor <= 0:
        raise AdmissionConflict("Earlier monotonic anchor required")
    if type(remaining_ms) is not int or remaining_ms < 0:
        raise AdmissionStorageError("Invalid scoped remaining duration")
    deadline = anchor + remaining_ms / 1000
    if outer is not None:
        if type(outer) not in (int, float) or not math.isfinite(outer) or outer <= 0:
            raise AdmissionConflict("Finite caller monotonic deadline required")
        deadline = min(deadline, outer)
    return deadline


@dataclass(frozen=True, slots=True)
class ScopedDeadline:
    deadline_at: datetime
    remaining_ms: int
    absolute_monotonic_deadline: float

    @classmethod
    def parse(cls, value, anchor, outer=None):
        try:
            deadline = datetime.fromisoformat(value["deadline_at"])
            if deadline.tzinfo is None or deadline.utcoffset() is None:
                raise ValueError
            remaining = value["remaining_ms"]
            return cls(deadline, remaining, monotonic_deadline(anchor, remaining, outer))
        except (KeyError, ValueError, TypeError):
            raise AdmissionStorageError("Invalid scoped deadline receipt") from None


@dataclass(frozen=True, slots=True)
class DispatchReceipt:
    attempt_id: UUID
    state: str
    reserved: ResourceAmount
    actual: ResourceAmount | None
    dispatch_permitted: bool
    context: AdmissionContext
    deadline_at: datetime
    remaining_ms: int
    absolute_monotonic_deadline: float

    @classmethod
    def parse(cls, value, context, anchor, outer=None):
        try:
            actual_context = AdmissionContext(
                value["context"]["mode"], UUID(value["context"]["brief_id"]),
                value["context"]["brief_version"],
                UUID(value["context"]["job_id"]) if value["context"]["job_id"] else None,
                UUID(value["context"]["lease_owner"]) if value["context"]["lease_owner"] else None,
                value["context"]["fence"])
            if actual_context != context or type(value["dispatch_permitted"]) is not bool:
                raise ValueError
            if value["state"] not in {"reserved", "dispatched", "held_unknown", "settled", "cancelled", "overrun"}:
                raise ValueError
            scoped = ScopedDeadline.parse(value, anchor, outer)
            if value["dispatch_permitted"] and (value["state"] != "dispatched" or scoped.remaining_ms <= 0):
                raise ValueError
            return cls(UUID(value["attempt_id"]), value["state"],
                       ResourceAmount.from_json(value["reserved"]),
                       ResourceAmount.from_json(value["actual"]) if value["actual"] is not None else None,
                       value["dispatch_permitted"], actual_context, scoped.deadline_at,
                       scoped.remaining_ms, scoped.absolute_monotonic_deadline)
        except (KeyError, ValueError, TypeError, AttributeError):
            raise AdmissionStorageError("Invalid immutable admission receipt") from None
