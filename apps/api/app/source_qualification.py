"""Read-only, owner-bound current source authority. Historical profiles grant nothing."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import ipaddress
import json
import re
from urllib.parse import urlsplit
from uuid import UUID
import warnings

from sqlalchemy import text

from app.contracts import ExtractionField, SourceLimits, SourcePlanItem
from app.source_registry import get_registry

MAX_PAYLOAD_BYTES = 2_000_000
_AUTHORITY = object()
_HEX = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,47}$")


class QualificationError(ValueError):
    """Safe owner/configuration error; input values are never reported."""


def _aware(value: object) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise QualificationError("Invalid source qualification context")
    return value


def _hash(value: object) -> str:
    if type(value) is not str or not _HEX.fullmatch(value) or value == "0" * 64:
        raise QualificationError("Invalid source qualification")
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise QualificationError("Invalid source qualification")
        result[key] = value
    return result


def _origin(value: str) -> str:
    """Structural origin validation only. Actual DNS/TLS lives in source_egress."""
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None
            or parsed.port not in (None, 443) or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", host)
            or host in {"localhost", "localhost.localdomain"} or "." not in host
            or host.endswith((".localhost", ".local", ".internal", ".invalid"))
            or value not in {f"https://{host}", f"https://{host}/", f"https://{host}:443", f"https://{host}:443/"}):
        raise QualificationError("Invalid source qualification")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return "https://" + host
    raise QualificationError("Invalid source qualification")


def _template(raw: object, reviewed_at: datetime) -> SourcePlanItem:
    if type(raw) is not dict or set(raw) != set(SourcePlanItem.model_fields):
        raise QualificationError("Invalid source qualification")
    limits = raw.get("limits")
    if (type(limits) is not dict or set(limits) != set(SourceLimits.model_fields)
            or any(type(v) is not int for v in limits.values())):
        raise QualificationError("Invalid source qualification")
    extracts = raw.get("extract_fields")
    if (type(extracts) is not list or not 1 <= len(extracts) <= 64
            or any(type(e) is not dict or set(e) != set(ExtractionField.model_fields)
                   or type(e.get("required")) is not bool for e in extracts)):
        raise QualificationError("Invalid source qualification")
    if type(raw.get("access_reviewed_at")) is not str:
        raise QualificationError("Invalid source qualification")
    # Full templates are server/admin records. Bound every otherwise unbounded
    # old wire-contract list before validation, without changing that contract.
    for key in ("allowed_origins", "capabilities", "allowed_content_types", "eligible_categories",
                "supported_intents", "expected_fields", "language_scope", "fallback_source_ids", "limitations"):
        values = raw.get(key)
        if (type(values) is not list or len(values) > 64 or any(type(v) is not str for v in values)
                or len(values) != len(set(values))):
            raise QualificationError("Invalid source qualification")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        source = SourcePlanItem.model_validate(raw)
        canonical = source.model_dump(mode="json")
    if (json.dumps(raw, sort_keys=True, ensure_ascii=False, allow_nan=False)
            != json.dumps(canonical, sort_keys=True, ensure_ascii=False, allow_nan=False)):
        raise QualificationError("Invalid source qualification")
    registry = get_registry()
    registry.identity(source.source_id)
    profile = registry.profile(source.source_id)
    origins = {_origin(value) for value in raw["allowed_origins"]}
    # Bind origins to this exact reviewed surface, not to another surface of
    # the same provider or its unrelated official landing page.
    historical = {"https://" + (urlsplit(s.endpoint_url).hostname or "")
                  for s in profile.historical_surfaces if s.surface_id == source.surface_id}
    if profile.preview_surface is not None:
        if profile.preview_surface.surface_id == source.surface_id:
            historical.add("https://" + (urlsplit(profile.preview_surface.url).hostname or ""))
    surfaces = {s.surface_id for s in profile.historical_surfaces}
    if profile.preview_surface is not None:
        surfaces.add(profile.preview_surface.surface_id)
    if (source.family != profile.family or not source.eligible_categories
            or not set(source.eligible_categories).issubset(profile.allowed_categories)
            or source.permission.value != "permitted" or source.health.value not in {"supported", "qualified"}
            or source.access_method.value not in {"api", "permitted_http"}
            or "search" not in source.capabilities or source.surface_id not in surfaces
            or not origins.issubset(historical) or not source.supported_intents
            or not source.expected_fields or not source.language_scope
            or source.access_reviewed_at > reviewed_at):
        raise QualificationError("Invalid source qualification")
    if (any(not re.fullmatch(r"[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*", mime)
            for mime in source.allowed_content_types)
            or source.limits.max_response_bytes > source.limits.max_total_bytes):
        raise QualificationError("Invalid source qualification")
    names = [e.name for e in source.extract_fields]
    # Current reviewed locators are required; trial_expected_fields/catalog CSV
    # labels are not extraction proof and are never copied into this template.
    if len(names) != len(set(names)) or not set(source.expected_fields).issubset(names):
        raise QualificationError("Invalid source qualification")
    if (any(not re.fullmatch(r"source-[0-9]{4}", sid) for sid in source.fallback_source_ids)
            or source.source_id in source.fallback_source_ids):
        raise QualificationError("Invalid source qualification")
    for sid in source.fallback_source_ids:
        registry.identity(sid)
    return source


@dataclass(frozen=True, init=False)
class QualificationState:
    """Immutable trusted loader result, scoped to the resolved owner/project."""
    user_id: UUID
    project_id: UUID
    checked_at: datetime
    reason: str
    _record: tuple = field(repr=False)
    _authority: object = field(repr=False)

    def __init__(self, user_id, project_id, checked_at, reason, record, *, _authority=None):
        if _authority is not _AUTHORITY:
            raise QualificationError("Source qualification requires a trusted read")
        for key, value in (("user_id", user_id), ("project_id", project_id), ("checked_at", checked_at),
                           ("reason", reason), ("_record", record), ("_authority", _authority)):
            object.__setattr__(self, key, value)

    def current(self, checked_at: datetime) -> tuple[tuple[SourcePlanItem, ...], str | None, str | None, datetime | None, str]:
        """Recheck expiry/integrity and return fresh, non-aliased wire templates."""
        checked_at = _aware(checked_at)
        if self._authority is not _AUTHORITY or checked_at < self.checked_at:
            raise QualificationError("Invalid source qualification context")
        if not self._record:
            return (), None, None, None, self.reason
        try:
            version, digest, raw_text, reviewed, valid_from, expires, revoked = self._record
            if (type(version) is not str or not _VERSION.fullmatch(version)
                    or _hash(digest) != hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
                    or not _aware(reviewed) <= _aware(valid_from) < _aware(expires)
                    or type(raw_text) is not str or len(raw_text.encode("utf-8")) > MAX_PAYLOAD_BYTES):
                raise QualificationError("Invalid source qualification")
            payload = json.loads(raw_text, object_pairs_hook=_pairs,
                                 parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if (type(payload) is not dict or set(payload) != {"sources", "registry_version", "registry_digest", "grant_digest"}
                    or payload["registry_version"] != get_registry().registry_version
                    or _hash(payload["registry_digest"]) != get_registry().content_digest
                    or not _hash(payload["grant_digest"]) or type(payload["sources"]) is not list
                    or len(payload["sources"]) > 128):
                raise QualificationError("Invalid source qualification")
            sources = tuple(_template(raw, reviewed) for raw in payload["sources"])
            if len(sources) != len({s.source_id for s in sources}):
                raise QualificationError("Invalid source qualification")
            ids = {s.source_id for s in sources}
            connectors = {}
            for source in sources:
                if (not set(source.fallback_source_ids).issubset(ids)
                        or connectors.setdefault(source.connector_id, source.connector_version) != source.connector_version):
                    raise QualificationError("Invalid source qualification")
            token = version + ":" + digest
            if revoked is not None:
                _aware(revoked)
                return (), token, digest, expires, "qualification_revoked"
            if checked_at < valid_from:
                return (), token, digest, expires, "qualification_not_yet_valid"
            if expires <= checked_at:
                return (), token, digest, expires, "qualification_expired"
            return sources, token, digest, expires, "qualified" if sources else "no_qualified_sources"
        except Exception:
            return (), None, None, None, "qualification_invalid"


_OWNER_SQL = text("""
    SELECT project_id FROM public.projects
    WHERE user_id = :user_id AND project_id = :project_id AND archived_at IS NULL
      AND current_setting('app.user_id', true) = CAST(:user_id AS text)
""")
_CURRENT_SQL = text("""
    SELECT s.qualification_version, s.qualification_digest, s.payload::text AS payload_text,
           encode(sha256(convert_to(s.payload::text, 'UTF8')), 'hex') AS native_digest,
           s.reviewed_at, s.valid_from, s.expires_at, s.revoked_at
    FROM public.source_qualification_current c
    JOIN public.source_qualification_snapshots s
      ON (s.qualification_version, s.qualification_digest) =
         (c.qualification_version, c.qualification_digest)
    WHERE c.slot = 1
""")


def load_current_qualification(connection, *, user_id: UUID, project_id: UUID,
                               checked_at: datetime) -> QualificationState:
    """SELECT-only within a caller-owned owner transaction; never mutates its GUC."""
    if type(user_id) is not UUID or type(project_id) is not UUID:
        raise QualificationError("Invalid source qualification context")
    checked_at = _aware(checked_at)
    try:
        owner = connection.execute(_OWNER_SQL, {"user_id": user_id, "project_id": project_id}).scalar_one_or_none()
    except Exception:
        raise QualificationError("Source qualification scope unavailable") from None
    if owner != project_id:
        raise QualificationError("Source qualification scope unavailable")
    try:
        row = connection.execute(_CURRENT_SQL).mappings().one_or_none()
        if row is None:
            reason, record = "qualification_missing", ()
        elif row["qualification_digest"] != row["native_digest"]:
            reason, record = "qualification_invalid", ()
        else:
            reason = "qualified"
            record = tuple(row[k] for k in ("qualification_version", "qualification_digest", "payload_text",
                                           "reviewed_at", "valid_from", "expires_at", "revoked_at"))
        state = QualificationState(user_id, project_id, checked_at, reason, record, _authority=_AUTHORITY)
        sources, version, digest, expiry, reason = state.current(checked_at)
        # Invalid records cannot retain partially parsed data as authority.
        if reason == "qualification_invalid":
            return QualificationState(user_id, project_id, checked_at, reason, (), _authority=_AUTHORITY)
        return state
    except Exception:
        return QualificationState(user_id, project_id, checked_at, "qualification_unavailable", (), _authority=_AUTHORITY)
