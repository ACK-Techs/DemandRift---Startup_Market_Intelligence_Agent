"""Offline authority-boundary controls. Native JSONB/ACL checks are separate."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.source_qualification import QualificationError, QualificationState, load_current_qualification
from app.source_registry import get_registry

NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)
OWNER, PROJECT = UUID(int=41), UUID(int=42)


def source_template():
    # A synthetic trusted-record fixture, never a live grant/publication.
    return dict(source_id="source-0017", profile_version="reviewed-v1", connector_id="github_issues",
        connector_version="v1", family="technical_community", permission="permitted", health="qualified",
        access_method="api", allowed_origins=["https://api.github.com/"], surface_id="f03-github_issues-v1",
        capabilities=["search", "fetch"], allowed_content_types=["application/json"],
        eligible_categories=["gelistirici-araci"], supported_intents=["problem_demand", "counter_evidence"],
        extract_fields=[dict(name=n, value_type="url" if n == "kaynak_url" else "text", required=True,
                            locator="reviewed-json-path:" + n) for n in ("baslik", "govde", "kaynak_url")],
        access_policy_version="license-robots-reviewed-v1", retention_policy_version="retention-v1",
        rate_limit_policy_version="rate-v1", access_reviewed_at=(NOW - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        fallback_source_ids=[], limits=dict(max_items=100, max_pages=20, max_requests=40,
            max_response_bytes=1000000, max_total_bytes=10000000, max_seconds=600, max_retries=1, max_llm_tokens=5000),
        expected_fields=["baslik", "govde", "kaynak_url"], language_scope=["tr", "en"], market_scope=None,
        ownership_key="github-reviewed", limitations=["Synthetic offline fixture; not current production permission"])


def qualification_row(*, sources=None, **changes):
    registry = get_registry()
    payload = dict(sources=[source_template()] if sources is None else sources,
                   registry_version=registry.registry_version, registry_digest=registry.content_digest, grant_digest="a" * 64)
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return dict(qualification_version="review-20261002-v1", qualification_digest=digest, native_digest=digest,
                payload_text=raw, reviewed_at=NOW - timedelta(minutes=5), valid_from=NOW - timedelta(minutes=4),
                expires_at=NOW + timedelta(hours=1), revoked_at=None) | changes


class ReadConnection:
    def __init__(self, row, *, owner=OWNER, project=PROJECT, resolved_owner=OWNER, archived=False, error=False):
        self.row, self.owner, self.project, self.resolved_owner = row, owner, project, resolved_owner
        self.archived, self.error, self.calls = archived, error, []

    def execute(self, statement, params=None):
        sql = str(statement)
        assert sql.strip().startswith("SELECT")
        assert not any(word in sql.upper().split() for word in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "SET"))
        self.calls.append((sql, params))
        if "public.projects" in sql:
            okay = not self.archived and params == {"user_id": self.owner, "project_id": self.project} and self.resolved_owner == self.owner
            return SimpleNamespace(scalar_one_or_none=lambda: self.project if okay else None)
        assert "s.payload::text" in sql and "c.slot = 1" in sql and "s.qualification_digest" in sql
        assert params is None
        if self.error:
            raise RuntimeError("private fixture must never be echoed")
        return SimpleNamespace(mappings=lambda: SimpleNamespace(one_or_none=lambda: self.row))


def state(row=None, *, owner=OWNER, project=PROJECT):
    return load_current_qualification(ReadConnection(qualification_row() if row is None else row, owner=owner, project=project,
                                     resolved_owner=owner), user_id=owner, project_id=project, checked_at=NOW)


def change_payload(row, callback, *, rehash=True):
    row = deepcopy(row)
    payload = json.loads(row["payload_text"])
    callback(payload)
    row["payload_text"] = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if rehash:
        row["qualification_digest"] = row["native_digest"] = hashlib.sha256(row["payload_text"].encode()).hexdigest()
    return row


def test_actual_loader_selects_only_after_verified_owner_and_binds_current_digest():
    row = qualification_row()
    connection = ReadConnection(row)
    loaded = load_current_qualification(connection, user_id=OWNER, project_id=PROJECT, checked_at=NOW)
    sources, version, digest, expiry, reason = loaded.current(NOW)
    assert len(connection.calls) == 2 and connection.calls[0][1] == {"user_id": OWNER, "project_id": PROJECT}
    assert reason == "qualified" and len(sources) == 1
    assert version == row["qualification_version"] + ":" + row["qualification_digest"]
    assert digest == row["qualification_digest"] and expiry == row["expires_at"]
    assert sources[0].model_dump(mode="json")["expected_fields"] == ["baslik", "govde", "kaynak_url"]
    assert all(not i.runtime_enabled for i in get_registry().identities)


@pytest.mark.parametrize("context", [dict(owner=uuid4()), dict(project=uuid4()), dict(resolved_owner=uuid4()), dict(archived=True)])
def test_foreign_archived_or_wrong_native_context_never_reads_global_authority(context):
    connection = ReadConnection(qualification_row(), **context)
    with pytest.raises(QualificationError, match="scope unavailable"):
        load_current_qualification(connection, user_id=OWNER, project_id=PROJECT, checked_at=NOW)
    assert len(connection.calls) == 1


@pytest.mark.parametrize("field,bad", [("user_id", str(OWNER)), ("project_id", str(PROJECT)), ("checked_at", NOW.replace(tzinfo=None)), ("checked_at", "now")])
def test_resolved_context_is_typed_before_any_read(field, bad):
    connection = ReadConnection(qualification_row())
    with pytest.raises(QualificationError):
        load_current_qualification(connection, **({"user_id": OWNER, "project_id": PROJECT, "checked_at": NOW} | {field: bad}))
    assert connection.calls == []


@pytest.mark.parametrize("row,reason", [(None, "qualification_missing"), (qualification_row(sources=[]), "no_qualified_sources"),
    (qualification_row(expires_at=NOW), "qualification_expired"), (qualification_row(revoked_at=NOW), "qualification_revoked"),
    (qualification_row(valid_from=NOW + timedelta(minutes=1)), "qualification_not_yet_valid"),
    (qualification_row(native_digest="b" * 64), "qualification_invalid"),
    (qualification_row(reviewed_at=NOW + timedelta(minutes=1)), "qualification_invalid"),
    (qualification_row(expires_at=NOW.replace(tzinfo=None)), "qualification_invalid")])
def test_missing_stale_revoked_or_inconsistent_authority_fails_closed(row, reason):
    loaded = load_current_qualification(ReadConnection(row), user_id=OWNER, project_id=PROJECT, checked_at=NOW)
    result = loaded.current(NOW)
    assert result[0] == () and result[-1] == reason


@pytest.mark.parametrize("field,bad", [
    ("permission", "unknown"), ("permission", "blocked"), ("health", "deferred"), ("health", "unavailable"),
    ("family", "social_community"), ("source_id", "source-0636"), ("source_id", "source-9999"),
    ("surface_id", "caller-invented"), ("access_method", "manual_export"), ("capabilities", ["fetch"]),
    ("eligible_categories", ["yerel-hizmet"]), ("eligible_categories", []), ("language_scope", []),
    ("expected_fields", ["surum"]), ("supported_intents", []), ("access_reviewed_at", (NOW + timedelta(minutes=1)).isoformat()),
    ("access_reviewed_at", 1790938800), ("allowed_origins", ["https://github.com/"]),
    ("allowed_origins", ["http://api.github.com/"]), ("allowed_origins", ["https://user:password@api.github.com/"]),
    ("allowed_origins", ["https://api.github.com/private?q=caller"]), ("allowed_origins", ["https://127.0.0.1/"]),
    ("allowed_origins", ["https://localhost/"]), ("allowed_origins", ["https://api.github.com:444/"]),
    ("allowed_origins", ["https://api.github.com/#fragment"]), ("allowed_origins", ["https://аpi.github.com/"]),
    ("allowed_origins", ["https://api%2egithub.com/"]), ("fallback_source_ids", ["source-0017"]),
    ("fallback_source_ids", ["source-9999"]), ("expected_fields", ["baslik", "baslik"]), ("extract_fields", []),
    ("fallback_source_ids", ["source-0022"]), ("allowed_content_types", ["*/*"]),
    ("allowed_content_types", ["Application/JSON"]), ("allowed_content_types", ["application/json; charset=utf-8"]),
])
def test_even_correctly_rehashed_admin_templates_require_structural_and_current_review(field, bad):
    changed = change_payload(qualification_row(), lambda p: p["sources"][0].update({field: bad}))
    assert state(changed).current(NOW)[-1] == "qualification_invalid"


@pytest.mark.parametrize("change", [
    lambda p: p.update(grant_digest="0" * 64), lambda p: p.update(grant_digest="Z" * 64),
    lambda p: p.update(registry_digest="c" * 64), lambda p: p.update(registry_version="unknown"),
    lambda p: p.update(extra="caller"), lambda p: p["sources"].append(p["sources"][0]),
    lambda p: p["sources"][0]["limits"].update(max_retries=1.0),
    lambda p: p["sources"][0]["limits"].update(max_requests=True),
    lambda p: p["sources"][0]["limits"].pop("max_llm_tokens"),
    lambda p: p["sources"][0]["extract_fields"][0].update(required=1),
    lambda p: p["sources"][0].pop("market_scope"),
    lambda p: p["sources"][0].update(language_scope=["tr"] * 65),
    lambda p: p["sources"][0].update(access_reviewed_at=(NOW - timedelta(minutes=10)).isoformat()),
    lambda p: p["sources"][0].update(allowed_origins=["https://api.github.com"]),
    lambda p: p["sources"][0]["limits"].update(max_total_bytes=1),
])
def test_raw_critical_types_and_complete_templates_are_not_normalized_into_permission(change):
    row = change_payload(qualification_row(), change)
    assert state(row).current(NOW)[-1] == "qualification_invalid"


def test_omitted_or_mutated_bytes_cannot_keep_old_digest_and_native_digest_must_also_match():
    row = change_payload(qualification_row(), lambda p: p["sources"][0].update(health="supported"), rehash=False)
    assert state(row).current(NOW)[-1] == "qualification_invalid"
    row["qualification_digest"] = hashlib.sha256(row["payload_text"].encode()).hexdigest()
    assert state(row).current(NOW)[-1] == "qualification_invalid"


def test_duplicate_json_keys_and_oversized_payload_are_denied_before_dto_defaults():
    for raw in ('{"sources":[],"sources":[]}', " " * 2000001):
        digest = hashlib.sha256(raw.encode()).hexdigest()
        row = qualification_row(payload_text=raw, qualification_digest=digest, native_digest=digest)
        assert state(row).current(NOW)[-1] == "qualification_invalid"


def test_snapshot_is_immutable_private_and_expiry_is_rechecked_without_rerequest():
    loaded = state()
    assert "reviewed-json-path" not in repr(loaded) and "github" not in repr(loaded)
    sources = loaded.current(NOW)[0]
    sources[0].permission = "unknown"
    sources[0].language_scope.append("injected")
    assert loaded.current(NOW)[0][0].permission.value == "permitted"
    assert loaded.current(NOW + timedelta(hours=1))[-1] == "qualification_expired"
    with pytest.raises(QualificationError):
        loaded.current(NOW - timedelta(seconds=1))
    with pytest.raises(Exception):
        loaded.reason = "permitted"
    with pytest.raises(QualificationError):
        QualificationState(OWNER, PROJECT, NOW, "qualified", ())


def test_global_authority_is_same_but_read_context_is_separately_bound_to_two_owners():
    a = state()
    b = state(owner=UUID(int=43), project=UUID(int=44))
    assert a.current(NOW)[1:4] == b.current(NOW)[1:4]
    assert (a.user_id, a.project_id) != (b.user_id, b.project_id)


def test_database_metadata_failure_is_safe_unavailable_not_no_results():
    loaded = load_current_qualification(ReadConnection(None, error=True), user_id=OWNER, project_id=PROJECT, checked_at=NOW)
    assert loaded.current(NOW)[-1] == "qualification_unavailable"
    assert "private fixture" not in repr(loaded)
