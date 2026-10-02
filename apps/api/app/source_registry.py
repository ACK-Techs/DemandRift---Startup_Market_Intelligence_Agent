"""Immutable, offline source authority; historical observations are not permits."""
from __future__ import annotations

from datetime import date
from functools import lru_cache
import hashlib
import ipaddress
import json
from pathlib import Path
import re
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.contracts import ResearchCategory, SourceFamily

REGISTRY_PATH = Path(__file__).parent / "data" / "source-registry.v1.json"
MAX_REGISTRY_BYTES = 2_000_000
LAB_SCRIPT = "faz-1-fikir-ve-arastirma/veri-laboratuvari/as01_kaynak_kontrol.py"
SEARCH_SCRIPT = "faz-1-fikir-ve-arastirma/veri-laboratuvari/keyword_search_pass.py"
SourceId = Annotated[str, Field(pattern=r"^source-[0-9]{4}$")]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Name = Annotated[str, Field(min_length=1, max_length=160)]
Text = Annotated[str, Field(min_length=1, max_length=4096)]
Health = Literal["eligible", "policy_blocked", "bot_challenged", "content_insufficient", "profile_incomplete"]


class RegistryError(ValueError):
    """Safe configuration error; never echoes input data."""


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def content_digest(value: dict) -> str:
    payload = {key: item for key, item in value.items() if key not in {"registry_version", "content_digest"}}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise RegistryError("invalid source registry")
        result[key] = value
    return result


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def complete_explicit_record(self) -> Frozen:
        # Packaged records are complete snapshots, including fields with defaults.
        # fields_set retains which keys actually appeared; defaults cannot authorize
        # omission. Keep JSON-mode validation so strict tuple fields accept JSON arrays.
        if self.model_fields_set != set(type(self).model_fields):
            raise ValueError("incomplete source registry record")
        return self


class InputHash(Frozen):
    path: Text
    sha256: Hash


class Identity(Frozen):
    source_id: SourceId
    display_name: Text
    official_origin: str | None
    resolution_status: Name
    verification_basis: Name
    disposition: Literal["candidate_only"] = "candidate_only"
    runtime_enabled: Literal[False] = False

    @field_validator("runtime_enabled", mode="before")
    @classmethod
    def actual_boolean(cls, value: object) -> object:
        if type(value) is not bool:
            raise ValueError("invalid source enable flag")
        return value


class Observation(Frozen):
    measured_at: str
    health: Health
    content_surface: Name
    requested_url: Text
    artifact_hash: Hash | None
    reason: Text

    @model_validator(mode="after")
    def valid_date(self) -> Observation:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", self.measured_at):
            raise ValueError("invalid observation date")
        date.fromisoformat(self.measured_at)
        return self


class FieldEvidence(Frozen):
    name: Name
    locator: Text
    query_kind: Name
    permission_snapshot: Name
    input_ref: Text


class HistoricalSurface(Frozen):
    surface_id: Name
    endpoint_url: Text
    provenance_ref: Text


class Parameter(Frozen):
    name: Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")]
    value: str | Annotated[int, Field(ge=0, le=1000)]


class FieldReason(Frozen):
    name: Name
    reason: Text


class PreviewSurface(Frozen):
    """A compiled historical mock preview, never a live execution capability."""

    surface_id: Name
    adapter: Literal["github_issues", "stackexchange_search", "algolia_hn_search"]
    url: Text
    query_parameter: Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")]
    item_limit_parameter: Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")]
    fixed_parameters: tuple[Parameter, ...]
    expected_fields: tuple[Name, ...]
    not_applicable_fields: tuple[FieldReason, ...]
    max_items: Literal[5] = 5
    timeout_seconds: Literal[10] = 10
    max_response_bytes: Literal[1_000_000] = 1_000_000
    allowed_content_types: tuple[Literal["application/json"], ...] = ("application/json",)
    content_role: Literal["unvalidated_preview"] = "unvalidated_preview"

    @field_validator("max_items", "timeout_seconds", "max_response_bytes", mode="before")
    @classmethod
    def actual_integer(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("invalid source limit type")
        return value

    @model_validator(mode="after")
    def restricted_request(self) -> PreviewSurface:
        parsed = urlsplit(self.url)
        host = parsed.hostname or ""
        if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None
                or parsed.port is not None or parsed.query or parsed.fragment
                or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", host)
                or not re.fullmatch(r"/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+", parsed.path)
                or any(segment in {".", ".."} for segment in parsed.path.split("/"))
                or self.url != f"https://{host}{parsed.path}"):
            raise ValueError("invalid preview surface")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError("invalid preview surface")
        names = [self.query_parameter, self.item_limit_parameter, *(p.name for p in self.fixed_parameters)]
        missing = [field.name for field in self.not_applicable_fields]
        if (len(names) != len(set(names)) or not self.expected_fields or not self.allowed_content_types
                or len(set(self.expected_fields)) != len(self.expected_fields)
                or len(set(missing)) != len(missing) or set(missing).intersection(self.expected_fields)):
            raise ValueError("invalid preview surface")
        return self


class Profile(Frozen):
    source_id: SourceId
    family: SourceFamily
    allowed_categories: tuple[ResearchCategory, ...]
    observation: Observation
    trial_expected_fields: tuple[Name, ...]
    catalog_field_evidence: tuple[FieldEvidence, ...]
    current_verified_fields: tuple[Name, ...] = ()
    historical_surfaces: tuple[HistoricalSurface, ...]
    preview_surface: PreviewSurface | None
    runtime_enabled: Literal[False] = False
    current_health: Literal["deferred"] = "deferred"
    current_permission: Literal["unknown"] = "unknown"
    ownership_key: None = None
    license_or_restriction: None = None
    retention_policy: None = None
    language_scope: tuple[Name, ...] = ()
    market_scope: None = None

    @field_validator("runtime_enabled", mode="before")
    @classmethod
    def actual_boolean(cls, value: object) -> object:
        if type(value) is not bool:
            raise ValueError("invalid source enable flag")
        return value

    @model_validator(mode="after")
    def no_unverified_elevation(self) -> Profile:
        if (self.current_verified_fields or self.language_scope
                or len(set(self.trial_expected_fields)) != len(self.trial_expected_fields)
                or len(set(self.allowed_categories)) != len(self.allowed_categories)):
            raise ValueError("current source qualification unavailable")
        return self

    @property
    def trial_eligible(self) -> bool:
        return self.observation.health == "eligible"


class CategoryPolicy(Frozen):
    category: ResearchCategory
    source_ids: tuple[SourceId, ...]
    limitations: tuple[Text, ...]


class Registry(Frozen):
    schema_version: Literal["1.0.0"]
    registry_version: Name
    content_digest: Hash
    historical_inputs: tuple[InputHash, ...]
    identities: Annotated[tuple[Identity, ...], Field(min_length=636, max_length=636)]
    profiles: Annotated[tuple[Profile, ...], Field(min_length=15, max_length=15)]
    categories: Annotated[tuple[CategoryPolicy, ...], Field(min_length=7, max_length=7)]
    f03_source_ids: Annotated[tuple[SourceId, ...], Field(min_length=3, max_length=3)]
    legacy_snapshots_json: Annotated[str, Field(max_length=500_000)]

    @model_validator(mode="after")
    def references_and_digest(self) -> Registry:
        ids = [item.source_id for item in self.identities]
        profiles = [item.source_id for item in self.profiles]
        if (len(set(ids)) != len(ids) or len(set(profiles)) != len(profiles)
                or not set(profiles).issubset(ids) or len(set(self.f03_source_ids)) != 3
                or len({p.category for p in self.categories}) != 7
                or len({p.path for p in self.historical_inputs}) != len(self.historical_inputs)):
            raise ValueError("invalid registry references")
        for policy in self.categories:
            if len(set(policy.source_ids)) != len(policy.source_ids) or not set(policy.source_ids).issubset(profiles):
                raise ValueError("invalid registry references")
        preview_ids = {p.source_id for p in self.profiles if p.preview_surface is not None}
        if preview_ids != set(self.f03_source_ids):
            raise ValueError("invalid registry references")
        expected = content_digest(self.model_dump(mode="json"))
        if self.content_digest != expected or self.registry_version != f"source-registry-v1-{expected[:16]}":
            raise ValueError("invalid registry digest")
        return self

    def identity(self, source_id: str) -> Identity:
        item = next((i for i in self.identities if i.source_id == source_id), None)
        if item is None:
            raise RegistryError("unknown source")
        return item

    def profile(self, source_id: str) -> Profile:
        item = next((i for i in self.profiles if i.source_id == source_id), None)
        if item is None:
            raise RegistryError("source profile unavailable")
        return item

    def category(self, category: str) -> CategoryPolicy:
        item = next((i for i in self.categories if i.category.value == category), None)
        if item is None:
            raise RegistryError("unknown source category")
        return item


def parse_registry(content: bytes) -> Registry:
    if type(content) is not bytes or not 0 < len(content) <= MAX_REGISTRY_BYTES:
        raise RegistryError("invalid source registry")
    try:
        raw = json.loads(content, object_pairs_hook=_unique_pairs)
        if type(raw) is not dict:
            raise RegistryError("invalid source registry")
        # Hash the complete parsed JSON payload, before defaults or literal-type
        # coercion. Whitespace and object-key layout are intentionally canonicalized.
        expected = content_digest(raw)
        if raw.get("content_digest") != expected or raw.get("registry_version") != f"source-registry-v1-{expected[:16]}":
            raise RegistryError("invalid source registry")
        return Registry.model_validate_json(content)
    except (ValueError, UnicodeError, TypeError, RecursionError):
        raise RegistryError("invalid source registry") from None


@lru_cache(maxsize=1)
def get_registry() -> Registry:
    try:
        with REGISTRY_PATH.open("rb") as handle:
            content = handle.read(MAX_REGISTRY_BYTES + 1)
    except OSError:
        raise RegistryError("source registry unavailable") from None
    return parse_registry(content)


def compile_preview_request(source_id: str, query: str, *, max_items: int = 5) -> tuple[str, dict[str, str | int]]:
    """Compile typed query data only; this function has no execution authority."""
    if type(source_id) is not str:
        raise RegistryError("invalid source identity")
    if type(query) is not str or not 1 <= len(query) <= 1000 or not query.strip():
        raise RegistryError("invalid source query")
    if type(max_items) is not int or not 1 <= max_items <= 5:
        raise RegistryError("invalid source limit")
    try:
        query.encode("utf-8", errors="strict")
        # Revalidation also rejects model_copy/update or object.__setattr__ tampering.
        registry = parse_registry(get_registry().model_dump_json().encode("utf-8"))
    except (UnicodeError, ValueError):
        raise RegistryError("invalid source registry") from None
    surface = registry.profile(source_id).preview_surface
    if surface is None:
        raise RegistryError("source preview unavailable")
    params = {parameter.name: parameter.value for parameter in surface.fixed_parameters}
    params[surface.query_parameter] = query
    params[surface.item_limit_parameter] = max_items
    return surface.url, params
