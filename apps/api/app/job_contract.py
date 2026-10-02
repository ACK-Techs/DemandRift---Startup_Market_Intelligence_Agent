"""Internal durable-job contracts; these are not pipeline result wire DTOs."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from app.contracts import Contract, Hash

BoundedAttempts = Annotated[int, Field(strict=True, ge=1, le=8)]
LeaseSeconds = Annotated[int, Field(strict=True, ge=1, le=300)]
Counter = Annotated[int, Field(strict=True, ge=0)]
JobState = Literal["queued", "running", "retry_wait", "held_unknown", "succeeded", "failed", "cancelled"]
TRANSIENT_ERRORS = frozenset({"timeout", "rate_limited", "provider_5xx"})
TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled"})


class EnqueueJob(Contract):
    request_key: UUID
    request_fingerprint: Hash
    research_plan_id: UUID
    plan_version: Annotated[int, Field(strict=True, gt=0)]
    plan_fingerprint: Hash
    brief_id: UUID
    brief_version: Annotated[int, Field(strict=True, gt=0)]
    max_attempts: BoundedAttempts = 3


class LeaseToken(Contract):
    owner: UUID
    fence: Annotated[int, Field(strict=True, gt=0)]


class JobSnapshot(Contract):
    job_id: UUID
    user_id: UUID
    project_id: UUID
    research_id: UUID
    request_key: UUID
    request_fingerprint: Hash
    research_plan_id: UUID
    plan_version: Annotated[int, Field(strict=True, gt=0)]
    plan_fingerprint: Hash
    brief_id: UUID
    brief_version: Annotated[int, Field(strict=True, gt=0)]
    max_attempts: BoundedAttempts
    state: JobState
    attempts: Counter
    fence: Counter
    checkpoint: Counter
    journal_seq: Annotated[int, Field(strict=True, gt=0)]
    lease_owner: UUID | None
    lease_until: AwareDatetime | None
    available_at: AwareDatetime
    cancelled_at: AwareDatetime | None
    finished_at: AwareDatetime | None
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def lifecycle(self):
        if self.attempts > self.max_attempts or self.fence != self.attempts:
            raise ValueError("job attempts and fence differ")
        if (self.lease_owner is None) != (self.lease_until is None):
            raise ValueError("lease owner and expiry must be paired")
        if (self.state == "running") != (self.lease_owner is not None):
            raise ValueError("only running jobs carry leases")
        if (self.state in TERMINAL_STATES) != (self.finished_at is not None):
            raise ValueError("terminal jobs require finish time")
        if (self.state == "cancelled") != (self.cancelled_at is not None):
            raise ValueError("cancel state and timestamp differ")
        return self


class JobReceipt(Contract):
    job: JobSnapshot
    permitted: bool = False


class OutboxReceipt(Contract):
    delivery_id: UUID
    job_id: UUID
    state: Literal["pending", "leased", "sent", "cancelled", "exhausted"]
    fence: Counter
    lease_owner: UUID | None
    lease_until: AwareDatetime | None
    publish_permitted: bool = False

