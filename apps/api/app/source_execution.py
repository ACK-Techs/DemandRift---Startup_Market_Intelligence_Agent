"""Allowlisted, bounded live API execution for the F03 BT-02 trial.

This is deliberately not a general URL fetcher.  It can call only the three
sources that the F03 manifest already permits, with the manifest query and
small fixed response limits.  The response is an ephemeral runner result, not
persisted evidence or a decision.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from app.initial_runs import find_scenario_run_seed
from app.source_registry import compile_preview_request, get_registry


F03_SOURCE_IDS = get_registry().f03_source_ids
MAX_ITEMS_PER_SOURCE = 5
REQUEST_TIMEOUT_SECONDS = 10.0
MAX_RESPONSE_BYTES = 1_000_000


class SourceExecutionStatus(StrEnum):
    SUCCESS = "success"
    NO_RESULTS = "no_results"
    SOURCE_UNAVAILABLE = "source_unavailable"
    RATE_LIMITED = "rate_limited"
    INVALID_OUTPUT = "invalid_output"


class F03LiveRunRequest(BaseModel):
    """An allowlisted F03 source subset; query text and URLs are not client input."""

    scenario_id: Literal["F03-net", "F03-eksik", "F03-yanlis-etiket"] = "F03-net"
    source_ids: list[Literal["source-0017", "source-0023", "source-0022"]] = Field(
        default_factory=lambda: list(F03_SOURCE_IDS), min_length=1, max_length=len(F03_SOURCE_IDS)
    )

    @model_validator(mode="after")
    def source_ids_must_be_unique(self) -> "F03LiveRunRequest":
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("source_ids must not contain duplicates")
        return self


class SourceItemPreview(BaseModel):
    title: str | None = None
    body: str | None = None
    source_url: str | None = None
    published_at: str | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)


class SourceFieldEvaluation(BaseModel):
    expected_fields: list[str]
    returned_fields: list[str]
    missing_fields: list[str]
    not_applicable_fields: list[str] = Field(default_factory=list)
    not_applicable_reasons: dict[str, str] = Field(default_factory=dict)


class RawArtifactReference(BaseModel):
    ref: str
    sha256: str
    byte_count: Annotated[int, Field(ge=1)]
    collected_at: datetime


class F03SourceExecutionResult(BaseModel):
    source_id: str
    source_name: str
    access_method: Literal["api"] = "api"
    artifact_origin: Literal["live_capture"] = "live_capture"
    status: SourceExecutionStatus
    query_text: str
    http_status: int | None = None
    result_count: Annotated[int, Field(ge=0)] = 0
    field_evaluation: SourceFieldEvaluation
    raw_artifact: RawArtifactReference | None = None
    previews: list[SourceItemPreview] = Field(default_factory=list)
    error: str | None = None


class F03LiveRunResponse(BaseModel):
    scenario_id: str
    executed_at: datetime
    execution_notice: str = (
        "Yanıtın ham API gövdesi proje-izole artefakt volume'unda saklanır; bu yine "
        "karar değildir. Başarılı sonuçlar insan etiketi olmadan run-record olarak kabul edilemez."
    )
    results: list[F03SourceExecutionResult]


class SourceDefinition(BaseModel):
    source_id: str
    source_name: str
    url: str
    expected_fields: list[str]
    not_applicable_fields: dict[str, str] = Field(default_factory=dict)


def _source_definitions() -> dict[str, SourceDefinition]:
    registry = get_registry()
    definitions = {}
    for source_id in registry.f03_source_ids:
        surface = registry.profile(source_id).preview_surface
        if surface is None:
            raise ValueError("source preview unavailable")
        definitions[source_id] = SourceDefinition(
            source_id=source_id,
            source_name=registry.identity(source_id).display_name,
            url=surface.url,
            expected_fields=list(surface.expected_fields),
            not_applicable_fields={field.name: field.reason for field in surface.not_applicable_fields},
        )
    return definitions


SOURCE_DEFINITIONS = _source_definitions()

class ArtifactStore:
    """Content-addressed raw artefacts rooted only in the DemandRift volume."""

    def __init__(self, root: Path):
        if not root.is_absolute():
            raise ValueError("artifact root must be absolute")
        self.root = root

    def save(self, source_id: str, content: bytes, collected_at: datetime) -> RawArtifactReference:
        digest = hashlib.sha256(content).hexdigest()
        relative = Path("f03") / source_id / f"{digest}.json"
        target = self.root / relative
        target.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(content)
        return RawArtifactReference(
            ref=relative.as_posix(), sha256=digest, byte_count=len(content), collected_at=collected_at
        )


def artifact_store_from_environment() -> ArtifactStore:
    root = os.environ.get("ARTIFACT_ROOT")
    if not root:
        raise RuntimeError("ARTIFACT_ROOT is not configured")
    return ArtifactStore(Path(root))


def _iso_timestamp(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, int):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    return None


def _source_request(source_id: str, query: str) -> tuple[str, dict[str, str | int]]:
    return compile_preview_request(source_id, query, max_items=MAX_ITEMS_PER_SOURCE)


def _previews(source_id: str, payload: dict[str, Any]) -> list[SourceItemPreview] | None:
    items = payload.get("items") if source_id in {"source-0017", "source-0023"} else payload.get("hits")
    if not isinstance(items, list):
        return None
    previews: list[SourceItemPreview] = []
    for item in items[:MAX_ITEMS_PER_SOURCE]:
        if not isinstance(item, dict):
            continue
        if source_id == "source-0017":
            previews.append(SourceItemPreview(
                title=item.get("title"), body=item.get("body"), source_url=item.get("html_url"),
                published_at=item.get("created_at"), tags=[label.get("name", "") for label in item.get("labels", []) if isinstance(label, dict)],
            ))
        elif source_id == "source-0023":
            previews.append(SourceItemPreview(
                title=item.get("title"), source_url=item.get("link"),
                published_at=_iso_timestamp(item.get("creation_date")), tags=item.get("tags", []),
            ))
        else:
            object_id = item.get("objectID")
            previews.append(SourceItemPreview(
                title=item.get("title") or item.get("story_title"),
                body=item.get("comment_text"),
                source_url=f"https://news.ycombinator.com/item?id={object_id}" if object_id else None,
                published_at=item.get("created_at"), author=item.get("author"),
            ))
    return previews


def _returned_fields(source_id: str, previews: list[SourceItemPreview]) -> list[str]:
    fields: set[str] = set()
    if any(item.title for item in previews):
        fields.add("baslik")
    if any(item.body for item in previews):
        fields.add("govde")
    if any(item.source_url for item in previews):
        fields.add("kaynak_url")
    if any(item.published_at for item in previews):
        fields.add("yayin_tarihi")
    if any(item.tags for item in previews):
        fields.add("etiket")
    if source_id == "source-0022" and any(item.author for item in previews):
        fields.add("yazar")
    return sorted(fields)


def _field_evaluation(source_id: str, previews: list[SourceItemPreview]) -> SourceFieldEvaluation:
    source = _source_definitions()[source_id]
    expected = source.expected_fields
    returned = _returned_fields(source_id, previews)
    return SourceFieldEvaluation(
        expected_fields=expected,
        returned_fields=returned,
        missing_fields=[field for field in expected if field not in returned],
        not_applicable_fields=list(source.not_applicable_fields),
        not_applicable_reasons=source.not_applicable_fields,
    )


async def execute_f03_sources(
    request: F03LiveRunRequest,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    artifact_store: ArtifactStore | None = None,
) -> F03LiveRunResponse:
    """Call the allowlist and persist bounded raw responses when a store is configured."""
    seed = find_scenario_run_seed(request.scenario_id)
    if seed is None or seed.idea_id != "F03":  # Defensive guard against future model drift.
        raise ValueError("scenario_id is not a planned F03 scenario")
    query = seed.query_texts[0]
    results: list[F03SourceExecutionResult] = []
    client_args: dict[str, Any] = {
        "timeout": httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
        "follow_redirects": False,
        "headers": {"User-Agent": "DemandRift-F03-Research-Runner/1.0", "Accept": "application/json"},
    }
    if transport is not None:
        client_args["transport"] = transport

    async with httpx.AsyncClient(**client_args) as client:
        for source_id in request.source_ids:
            source = _source_definitions()[source_id]
            url, params = _source_request(source_id, query)
            response_content: bytes | None = None
            response_status: int | None = None
            try:
                async with client.stream("GET", url, params=params) as response:
                    content_length = response.headers.get("content-length")
                    if content_length and content_length.isdigit() and int(content_length) > MAX_RESPONSE_BYTES:
                        results.append(F03SourceExecutionResult(
                            source_id=source_id, source_name=source.source_name,
                            status=SourceExecutionStatus.INVALID_OUTPUT, query_text=query,
                            http_status=response.status_code, field_evaluation=_field_evaluation(source_id, []),
                            error="Source API response exceeded the allowed size.",
                        ))
                        continue
                    raw_content = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw_content.extend(chunk)
                        if len(raw_content) > MAX_RESPONSE_BYTES:
                            results.append(F03SourceExecutionResult(
                                source_id=source_id, source_name=source.source_name,
                                status=SourceExecutionStatus.INVALID_OUTPUT, query_text=query,
                                http_status=response.status_code, field_evaluation=_field_evaluation(source_id, []),
                                error="Source API response exceeded the allowed size.",
                            ))
                            break
                    else:
                        response_content = bytes(raw_content)
                        response_status = response.status_code
                        # The complete response has been read; continue with status/JSON handling below.
                        pass
            except httpx.RequestError as error:
                results.append(F03SourceExecutionResult(
                    source_id=source_id, source_name=source.source_name, status=SourceExecutionStatus.SOURCE_UNAVAILABLE,
                    query_text=query, field_evaluation=_field_evaluation(source_id, []), error=str(error),
                ))
                continue
            if response_content is None or response_status is None:
                # Size-limit branch has already recorded a structured result.
                continue
            if response_status == 429:
                results.append(F03SourceExecutionResult(
                    source_id=source_id, source_name=source.source_name, status=SourceExecutionStatus.RATE_LIMITED,
                    query_text=query, http_status=response_status, field_evaluation=_field_evaluation(source_id, []),
                    error="Source API rate limit returned.",
                ))
                continue
            if response_status < 200 or response_status >= 300:
                results.append(F03SourceExecutionResult(
                    source_id=source_id, source_name=source.source_name, status=SourceExecutionStatus.SOURCE_UNAVAILABLE,
                    query_text=query, http_status=response_status, field_evaluation=_field_evaluation(source_id, []),
                    error="Source API returned a non-success status.",
                ))
                continue
            try:
                payload = json.loads(response_content)
            except (TypeError, ValueError):
                payload = None
            try:
                previews = _previews(source_id, payload) if isinstance(payload, dict) else None
            except (TypeError, ValueError, OverflowError):
                # Upstream fields are untrusted. Conversion failures belong to
                # this source and must not expose its body or abort the batch.
                previews = None
            if previews is None:
                results.append(F03SourceExecutionResult(
                    source_id=source_id, source_name=source.source_name, status=SourceExecutionStatus.INVALID_OUTPUT,
                    query_text=query, http_status=response_status, field_evaluation=_field_evaluation(source_id, []),
                    error="Source API response did not match the expected result format.",
                ))
                continue
            collected_at = datetime.now(timezone.utc)
            artifact = artifact_store.save(source_id, response_content, collected_at) if artifact_store else None
            results.append(F03SourceExecutionResult(
                source_id=source_id, source_name=source.source_name,
                status=SourceExecutionStatus.SUCCESS if previews else SourceExecutionStatus.NO_RESULTS,
                query_text=query, http_status=response_status, result_count=len(previews),
                field_evaluation=_field_evaluation(source_id, previews), raw_artifact=artifact, previews=previews,
            ))

    return F03LiveRunResponse(scenario_id=request.scenario_id, executed_at=datetime.now(timezone.utc), results=results)


router = APIRouter(prefix="/api/v1/research", tags=["research-execution"])


@router.post("/source-runs/f03", response_model=F03LiveRunResponse)
async def run_f03_sources(request: F03LiveRunRequest) -> F03LiveRunResponse:
    """Historical preview cannot bypass account or shared-budget authorization."""
    from app.auth_routes import ApiProblem
    raise ApiProblem(410, "preview_unavailable", "Live sources require an authenticated research run")
