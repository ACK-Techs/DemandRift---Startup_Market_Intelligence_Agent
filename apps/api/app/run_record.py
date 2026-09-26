"""Validation contract for provenance-bearing BT-02 source-run records."""

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator


class AccessStatus(StrEnum):
    SUCCESS = "success"
    SOURCE_UNAVAILABLE = "source_unavailable"
    RATE_LIMITED = "rate_limited"
    CHALLENGE = "challenge"
    BLOCKED_BY_POLICY = "blocked_by_policy"
    INVALID_OUTPUT = "invalid_output"


class RunCounts(BaseModel):
    discovered: Annotated[int, Field(ge=0)] = 0
    fetched: Annotated[int, Field(ge=0)] = 0
    eligible: Annotated[int, Field(ge=0)] = 0
    unique: Annotated[int, Field(ge=0)] = 0

    @model_validator(mode="after")
    def counts_must_follow_collection_order(self) -> "RunCounts":
        if not self.discovered >= self.fetched >= self.eligible >= self.unique:
            raise ValueError("counts must satisfy discovered >= fetched >= eligible >= unique")
        return self


class HumanLabel(BaseModel):
    artifact_ref: Annotated[str, Field(min_length=1, max_length=512)]
    label: Literal["relevant", "irrelevant", "uncertain"]
    reason: Annotated[str, Field(min_length=1, max_length=1000)]


class SourceRunRecord(BaseModel):
    run_id: UUID
    scenario_id: Annotated[str, Field(pattern=r"^F(?:0[1-9]|10)-(net|eksik|yanlis-etiket)$")]
    source_id: Annotated[str, Field(pattern=r"^source-\d{4}$")]
    query_id: Annotated[str, Field(min_length=1, max_length=128)]
    query_text: Annotated[str, Field(min_length=1, max_length=1000)]
    script: Annotated[str, Field(min_length=1, max_length=512)]
    script_version: Annotated[str, Field(min_length=1, max_length=128)]
    access_method: Literal["api", "permitted_browser", "manual_export"]
    expected_fields: list[Annotated[str, Field(min_length=1, max_length=128)]]
    returned_fields: list[Annotated[str, Field(min_length=1, max_length=128)]] = Field(default_factory=list)
    limits: dict[str, int | float | str] = Field(default_factory=dict)
    counts: RunCounts = Field(default_factory=RunCounts)
    raw_artifact_refs: list[Annotated[str, Field(min_length=1, max_length=512)]] = Field(default_factory=list)
    human_labels: list[HumanLabel] = Field(default_factory=list)
    access_status: AccessStatus
    error: str | None = None
    feedback_id: str | None = None
    retest_result: str | None = None

    @model_validator(mode="after")
    def successful_runs_need_inspectable_provenance(self) -> "SourceRunRecord":
        if self.access_status == AccessStatus.SUCCESS:
            if not self.raw_artifact_refs:
                raise ValueError("successful runs require raw_artifact_refs")
            if not self.returned_fields:
                raise ValueError("successful runs require returned_fields")
            if self.counts.fetched == 0:
                raise ValueError("successful runs require at least one fetched record")
            if not self.human_labels:
                raise ValueError("successful runs require human_labels")
        elif not self.error:
            raise ValueError("unsuccessful runs require an error explanation")
        return self


class ValidatedRunRecord(BaseModel):
    storage: Literal["not_persisted"] = "not_persisted"
    record: SourceRunRecord


router = APIRouter(prefix="/api/v1/research", tags=["research-execution"])


@router.post("/run-records/validate", response_model=ValidatedRunRecord)
def validate_run_record(record: SourceRunRecord) -> ValidatedRunRecord:
    """Validate a manually or runner-produced record without storing or executing it."""
    return ValidatedRunRecord(record=record)
