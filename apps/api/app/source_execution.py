"""Allowlisted, bounded live API execution for the F03 BT-02 trial.

This is deliberately not a general URL fetcher.  It can call only the three
sources that the F03 manifest already permits, with the manifest query and
small fixed response limits.  The response is an ephemeral runner result, not
persisted evidence or a decision.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from app.initial_runs import find_scenario_run_seed


F03_SOURCE_IDS = ("source-0017", "source-0023", "source-0022")
MAX_ITEMS_PER_SOURCE = 5
REQUEST_TIMEOUT_SECONDS = 10.0


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
    source_url: str | None = None
    published_at: str | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)


class SourceFieldEvaluation(BaseModel):
    expected_fields: list[str]
    returned_fields: list[str]
    missing_fields: list[str]


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
    previews: list[SourceItemPreview] = Field(default_factory=list)
    error: str | None = None


class F03LiveRunResponse(BaseModel):
    scenario_id: str
    executed_at: datetime
    execution_notice: str = (
        "Yanıt kalıcı artefakt veya karar değildir. Başarılı sonuçlar, ham artefakt "
        "ve insan etiketi olmadan run-record olarak kaydedilemez."
    )
    results: list[F03SourceExecutionResult]


class SourceDefinition(BaseModel):
    source_id: str
    source_name: str
    url: str
    expected_fields: list[str]


SOURCE_DEFINITIONS = {
    "source-0017": SourceDefinition(
        source_id="source-0017",
        source_name="GitHub",
        url="https://api.github.com/search/issues",
        expected_fields=["baslik", "govde", "kaynak_url", "yayin_tarihi", "surum"],
    ),
    "source-0023": SourceDefinition(
        source_id="source-0023",
        source_name="Stack Overflow",
        url="https://api.stackexchange.com/2.3/search/advanced",
        expected_fields=["baslik", "etiket", "kaynak_url", "yayin_tarihi"],
    ),
    "source-0022": SourceDefinition(
        source_id="source-0022",
        source_name="Hacker News",
        url="https://hn.algolia.com/api/v1/search",
        expected_fields=["baslik", "govde", "kaynak_url", "yayin_tarihi", "yazar"],
    ),
}


def _iso_timestamp(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, int):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    return None


def _source_request(source_id: str, query: str) -> tuple[str, dict[str, str | int]]:
    source = SOURCE_DEFINITIONS[source_id]
    if source_id == "source-0017":
        return source.url, {"q": query, "per_page": MAX_ITEMS_PER_SOURCE}
    if source_id == "source-0023":
        return source.url, {"site": "stackoverflow", "q": query, "pagesize": MAX_ITEMS_PER_SOURCE}
    return source.url, {"query": query, "hitsPerPage": MAX_ITEMS_PER_SOURCE}


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
                title=item.get("title"), source_url=item.get("html_url"),
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
                source_url=item.get("url") or (f"https://news.ycombinator.com/item?id={object_id}" if object_id else None),
                published_at=item.get("created_at"), author=item.get("author"),
            ))
    return previews


def _returned_fields(source_id: str, previews: list[SourceItemPreview]) -> list[str]:
    fields: set[str] = set()
    if any(item.title for item in previews):
        fields.add("baslik")
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
    expected = SOURCE_DEFINITIONS[source_id].expected_fields
    returned = _returned_fields(source_id, previews)
    return SourceFieldEvaluation(
        expected_fields=expected,
        returned_fields=returned,
        missing_fields=[field for field in expected if field not in returned],
    )


async def execute_f03_sources(
    request: F03LiveRunRequest,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> F03LiveRunResponse:
    """Call a small allowlist and return only structured, non-persisted previews."""
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
            source = SOURCE_DEFINITIONS[source_id]
            url, params = _source_request(source_id, query)
            try:
                response = await client.get(url, params=params)
            except httpx.RequestError as error:
                results.append(F03SourceExecutionResult(
                    source_id=source_id, source_name=source.source_name, status=SourceExecutionStatus.SOURCE_UNAVAILABLE,
                    query_text=query, field_evaluation=_field_evaluation(source_id, []), error=str(error),
                ))
                continue
            if response.status_code == 429:
                results.append(F03SourceExecutionResult(
                    source_id=source_id, source_name=source.source_name, status=SourceExecutionStatus.RATE_LIMITED,
                    query_text=query, http_status=response.status_code, field_evaluation=_field_evaluation(source_id, []),
                    error="Source API rate limit returned.",
                ))
                continue
            if response.status_code < 200 or response.status_code >= 300:
                results.append(F03SourceExecutionResult(
                    source_id=source_id, source_name=source.source_name, status=SourceExecutionStatus.SOURCE_UNAVAILABLE,
                    query_text=query, http_status=response.status_code, field_evaluation=_field_evaluation(source_id, []),
                    error="Source API returned a non-success status.",
                ))
                continue
            try:
                payload = response.json()
            except ValueError:
                payload = None
            previews = _previews(source_id, payload) if isinstance(payload, dict) else None
            if previews is None:
                results.append(F03SourceExecutionResult(
                    source_id=source_id, source_name=source.source_name, status=SourceExecutionStatus.INVALID_OUTPUT,
                    query_text=query, http_status=response.status_code, field_evaluation=_field_evaluation(source_id, []),
                    error="Source API response did not contain the expected result collection.",
                ))
                continue
            results.append(F03SourceExecutionResult(
                source_id=source_id, source_name=source.source_name,
                status=SourceExecutionStatus.SUCCESS if previews else SourceExecutionStatus.NO_RESULTS,
                query_text=query, http_status=response.status_code, result_count=len(previews),
                field_evaluation=_field_evaluation(source_id, previews), previews=previews,
            ))

    return F03LiveRunResponse(scenario_id=request.scenario_id, executed_at=datetime.now(timezone.utc), results=results)


router = APIRouter(prefix="/api/v1/research", tags=["research-execution"])


@router.post("/source-runs/f03", response_model=F03LiveRunResponse)
async def run_f03_sources(request: F03LiveRunRequest) -> F03LiveRunResponse:
    """Execute the fixed F03 API allowlist; accepts no URL, query, token, or secret."""
    return await execute_f03_sources(request)
