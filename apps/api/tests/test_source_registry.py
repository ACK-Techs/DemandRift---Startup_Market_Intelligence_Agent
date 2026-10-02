"""Offline source authority, compatibility and typed request boundaries."""
from __future__ import annotations

import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import socket
import subprocess
import sys

import httpx
from pydantic import ValidationError
import pytest

from app.initial_runs import build_initial_run_manifest
from app.research_plan import ResearchCategory
from app.source_plan import build_category_source_plan
from app.source_registry import (
    MAX_REGISTRY_BYTES, REGISTRY_PATH, RegistryError, canonical_json,
    compile_preview_request, content_digest, get_registry, parse_registry,
)

ROOT = Path(__file__).resolve().parents[1].parent.parent
LAB = ROOT / "faz-1-fikir-ve-arastirma/veri-laboratuvari"


@pytest.fixture(autouse=True)
def no_outbound_connections(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("source registry attempted DNS or a TCP connection")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


def bundle() -> dict:
    return json.loads(REGISTRY_PATH.read_bytes())


def rehash(value: dict) -> bytes:
    digest = content_digest(value)
    value.update(content_digest=digest, registry_version=f"source-registry-v1-{digest[:16]}")
    return canonical_json(value).encode("utf-8")


def test_inventory_retains_all_636_identities_and_unresolved_origins():
    registry = get_registry()
    assert len(registry.identities) == len({i.source_id for i in registry.identities}) == 636
    assert all(not i.runtime_enabled and i.disposition == "candidate_only" for i in registry.identities)
    assert len(registry.profiles) == 15
    assert all(not p.runtime_enabled and p.current_health == "deferred" and p.current_permission == "unknown"
               and p.ownership_key is None and p.market_scope is None and p.language_scope == ()
               for p in registry.profiles)
    unresolved = [i for i in registry.identities if i.official_origin is None]
    assert len(unresolved) == 5
    assert not any(i.source_id in registry.f03_source_ids for i in unresolved)


@pytest.mark.skipif(not LAB.exists(), reason="historical lab inputs are not part of the app-only image")
def test_inventory_and_input_hashes_match_actual_fixed_historical_authority():
    registry = get_registry()
    manifest = json.loads((LAB / "source_manifest.json").read_bytes())
    assert [(i.source_id, i.display_name, i.official_origin) for i in registry.identities] == [
        (s["source_id"], s["display_name"], s.get("official_origin") or None) for s in manifest["sources"]]
    for item in registry.historical_inputs:
        assert hashlib.sha256((ROOT / item.path).read_bytes()).hexdigest() == item.sha256


@pytest.mark.skipif(not LAB.exists(), reason="historical lab inputs are not part of the app-only image")
def test_dated_health_is_real_observation_and_reproducible_builder_is_zero_diff():
    with (LAB / "KAYNAK-SAGLIK.csv").open(encoding="utf-8") as handle:
        observations = {r["source_id"]: r for r in csv.DictReader(handle)}
    for profile in get_registry().profiles:
        observation = profile.observation
        assert observation.measured_at == observations[profile.source_id]["son_olcum"] == "2026-09-27"
        assert observation.requested_url == observations[profile.source_id]["son_denenen_url"]
        date.fromisoformat(observation.measured_at)
    builder = runpy.run_path(str(ROOT / "apps/api/scripts/build_source_registry.py"))
    assert builder["generated_text"](bundle()) == REGISTRY_PATH.read_text(encoding="utf-8")


def test_source_views_keep_scenarios_and_expected_fields_but_do_not_claim_fresh_verified_fields():
    registry = get_registry()
    before = json.loads(registry.legacy_snapshots_json)
    after = build_initial_run_manifest().model_dump(mode="json")
    assert len(after["runs"]) == 30
    for old, current in zip(before["initial_runs"]["runs"], after["runs"], strict=True):
        for name in ("idea_id", "idea_name", "scenario_id", "variant", "category", "query_texts",
                     "script_paths", "execution_status", "raw_artifact_refs", "feedback_ids"):
            assert old[name] == current[name]
        for old_source, new_source in zip(old["source_candidates"], current["source_candidates"], strict=True):
            for name in ("source_id", "source_name", "health", "eligible_for_execution", "expected_fields"):
                assert old_source[name] == new_source[name]
    for category in ResearchCategory:
        plan = build_category_source_plan(category)
        assert plan.source_registry_version == registry.registry_version
        assert all(s.last_measured_at == "2026-09-27" and s.verified_fields == []
                   for s in plan.eligible_sources + plan.excluded_sources)
    assert registry.profile("source-0017").catalog_field_evidence
    assert not registry.profile("source-0017").current_verified_fields
    assert registry.profile("source-0017").preview_surface.not_applicable_fields[0].name == "surum"


def test_field_and_endpoint_provenance_stays_on_separate_surfaces():
    registry = get_registry()
    github = registry.profile("source-0017")
    assert any("/search/repositories" in s.endpoint_url for s in github.historical_surfaces)
    assert github.preview_surface.url.endswith("/search/issues")
    assert "lisans" not in github.preview_surface.expected_fields
    hn = registry.profile("source-0022")
    assert any("hacker-news.firebaseio.com" in s.endpoint_url for s in hn.historical_surfaces)
    assert hn.preview_surface.url.startswith("https://hn.algolia.com/")
    assert hn.current_permission == "unknown" and not hn.runtime_enabled


def test_three_preview_definition_projections_keep_original_contract_and_fresh_copies():
    from app.source_execution import _source_definitions

    registry = get_registry()
    before = json.loads(registry.legacy_snapshots_json)
    assert list(registry.f03_source_ids) == before["f03_source_ids"]
    current = _source_definitions()
    assert {source_id: item.model_dump(mode="json") for source_id, item in current.items()} == before["source_definitions"]
    current["source-0017"].expected_fields.append("invented")
    current["source-0017"].url = "https://127.0.0.1/private"
    assert "invented" not in _source_definitions()["source-0017"].expected_fields
    url, _ = compile_preview_request("source-0017", "fixture")
    assert url == before["source_definitions"]["source-0017"]["url"]


def test_returned_consumer_mutation_does_not_change_authority_or_other_requests():
    first = build_category_source_plan(ResearchCategory.MOBILE_APP)
    first.eligible_sources[0].source_name = "modified fixture"
    first.eligible_sources[0].verified_fields.append("invented")
    second = build_category_source_plan(ResearchCategory.MOBILE_APP)
    assert second.eligible_sources[0].source_name == "Apple App Store"
    assert second.eligible_sources[0].verified_fields == []
    manifest = build_initial_run_manifest()
    manifest.runs[0].source_candidates[0].expected_fields.append("invented")
    assert "invented" not in manifest.runs[1].source_candidates[0].expected_fields
    with pytest.raises(ValidationError):
        get_registry().profiles[0].runtime_enabled = True
    assert isinstance(get_registry().profiles, tuple)


@pytest.mark.parametrize("source_id", ["source-0017", "source-0023", "source-0022"])
def test_compilation_keeps_shell_and_url_metacharacters_as_literal_query_data(source_id):
    query = '  Türkçe $(touch /tmp/forbidden) `id` &q=other\nhttps://127.0.0.1/private  '
    url, params = compile_preview_request(source_id, query)
    surface = get_registry().profile(source_id).preview_surface
    assert url == surface.url
    assert params[surface.query_parameter] == query
    assert params[surface.item_limit_parameter] == 5
    request = httpx.Request("GET", url, params=params)
    assert request.url.params[surface.query_parameter] == query
    assert request.url.host == httpx.URL(surface.url).host
    assert request.url.path == httpx.URL(surface.url).path
    assert set(params) == {surface.query_parameter, surface.item_limit_parameter,
                           *(p.name for p in surface.fixed_parameters)}


@pytest.mark.parametrize("limit", [True, False, 0, -1, 6, 5.0, "5", None])
def test_invalid_compilation_limits_are_rejected_before_execution(limit):
    with pytest.raises(RegistryError, match="invalid source limit"):
        compile_preview_request("source-0017", "fixture", max_items=limit)


@pytest.mark.parametrize("query", [None, True, 1, "", " \n ", "a" * 1001, "\ud800"])
def test_invalid_query_and_non_scalar_text_is_rejected(query):
    with pytest.raises(RegistryError):
        compile_preview_request("source-0017", query)


@pytest.mark.parametrize("source_id", ["source-0075", "source-0001", "source-9999", "https://example.org", "SOURCE-0017"])
def test_unknown_or_non_preview_source_cannot_gain_a_compiled_request(source_id):
    with pytest.raises(RegistryError):
        compile_preview_request(source_id, "fixture")


@pytest.mark.parametrize("mutation", ["duplicate_identity", "duplicate_profile", "unknown_category_source", "extra",
                                     "runtime_enabled", "market_default", "date", "query_parameter_collision",
                                     "private_origin", "userinfo", "port", "dot_path", "wrong_digest",
                                     "verified_field", "language_default", "duplicate_expected_field"])
def test_corrupt_and_capability_widening_bundles_fail_closed(mutation):
    value = bundle()
    if mutation == "duplicate_identity":
        value["identities"][1] = value["identities"][0]
    elif mutation == "duplicate_profile":
        value["profiles"][1] = value["profiles"][0]
    elif mutation == "unknown_category_source":
        value["categories"][0]["source_ids"].append("source-9999")
    elif mutation == "extra":
        value["profiles"][0]["extra"] = "unsupported"
    elif mutation == "runtime_enabled":
        value["profiles"][0]["runtime_enabled"] = True
    elif mutation == "market_default":
        value["profiles"][0]["market_scope"] = "TR"
    elif mutation == "date":
        value["profiles"][0]["observation"]["measured_at"] = "2026-09-99"
    elif mutation == "verified_field":
        value["profiles"][0]["current_verified_fields"] = ["lisans"]
    elif mutation == "language_default":
        value["profiles"][0]["language_scope"] = ["tr"]
    elif mutation == "duplicate_expected_field":
        value["profiles"][0]["preview_surface"]["expected_fields"].append("baslik")
    elif mutation == "query_parameter_collision":
        value["profiles"][0]["preview_surface"]["item_limit_parameter"] = "q"
    elif mutation == "private_origin":
        value["profiles"][0]["preview_surface"]["url"] = "https://127.0.0.1/search"
    elif mutation == "userinfo":
        value["profiles"][0]["preview_surface"]["url"] = "https://user@api.github.com/search"
    elif mutation == "port":
        value["profiles"][0]["preview_surface"]["url"] = "https://api.github.com:443/search"
    elif mutation == "dot_path":
        value["profiles"][0]["preview_surface"]["url"] = "https://api.github.com/../search"
    raw = rehash(value)
    if mutation == "wrong_digest":
        raw = raw.replace(value["content_digest"].encode(), b"0" * 64)
    with pytest.raises(RegistryError, match="invalid source registry"):
        parse_registry(raw)


def test_model_copy_update_cannot_bypass_compilation_validation(monkeypatch):
    original = get_registry()
    forged = original.model_copy(update={"f03_source_ids": ("source-0075",)})
    monkeypatch.setattr("app.source_registry.get_registry", lambda: forged)
    with pytest.raises(RegistryError):
        compile_preview_request("source-0075", "fixture")


@pytest.mark.parametrize("digest_mode", ["unchanged", "recomputed"])
@pytest.mark.parametrize("mutation", ["identity_false_as_zero", "profile_false_as_zero", "max_items_float",
                                     "timeout_float", "response_limit_float", "omitted_default_cap"])
def test_raw_integrity_and_actual_types_reject_literal_coercion_and_default_reconstruction(mutation, digest_mode):
    value = bundle()
    original_digest = value["content_digest"]
    surface = value["profiles"][0]["preview_surface"]
    if mutation == "identity_false_as_zero":
        value["identities"][0]["runtime_enabled"] = 0
    elif mutation == "profile_false_as_zero":
        value["profiles"][0]["runtime_enabled"] = 0
    elif mutation == "max_items_float":
        surface["max_items"] = 5.0
    elif mutation == "timeout_float":
        surface["timeout_seconds"] = 10.0
    elif mutation == "response_limit_float":
        surface["max_response_bytes"] = 1_000_000.0
    elif mutation == "omitted_default_cap":
        del surface["max_items"]
    assert content_digest(value) != original_digest
    raw = rehash(value) if digest_mode == "recomputed" else canonical_json(value).encode("utf-8")
    if digest_mode == "recomputed":
        assert value["content_digest"] == content_digest(value)
    with pytest.raises(RegistryError, match="invalid source registry"):
        parse_registry(raw)


@pytest.mark.parametrize("record_name,field", [("identity", "disposition"), ("identity", "runtime_enabled"),
                                             ("profile", "current_permission"), ("profile", "current_verified_fields"),
                                             ("surface", "allowed_content_types"), ("surface", "timeout_seconds")])
def test_recomputed_digest_does_not_authorize_omitting_any_default_metadata(record_name, field):
    value = bundle()
    record = {"identity": value["identities"][0], "profile": value["profiles"][0],
              "surface": value["profiles"][0]["preview_surface"]}[record_name]
    del record[field]
    with pytest.raises(RegistryError):
        parse_registry(rehash(value))


def test_raw_canonical_hash_preserves_values_but_allows_json_whitespace_key_order_and_escaping():
    value = bundle()
    rearranged = dict(reversed(list(value.items())))
    raw = json.dumps(rearranged, ensure_ascii=True, indent=1).encode("utf-8")
    assert raw != REGISTRY_PATH.read_bytes()
    assert parse_registry(raw).content_digest == get_registry().content_digest


def test_valid_explicit_metadata_revision_requires_its_new_complete_payload_digest():
    value = bundle()
    old_version = value["registry_version"]
    value["profiles"][0]["observation"]["reason"] += "; historical fixture revision"
    with pytest.raises(RegistryError):
        parse_registry(canonical_json(value).encode("utf-8"))
    revised = parse_registry(rehash(value))
    assert revised.registry_version != old_version
    assert revised.profiles[0].runtime_enabled is False


def test_valid_historical_http_request_remains_unavailable_without_source_dispatch(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app

    async def forbidden(*args, **kwargs):
        raise AssertionError("historical HTTP route attempted source execution")

    monkeypatch.setattr("app.source_execution.execute_f03_sources", forbidden)
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/research/source-runs/f03", json={"source_ids": ["source-0017"]})
    assert response.status_code == 410
    assert response.json()["code"] == "preview_unavailable"


@pytest.mark.parametrize("raw", [b"", b"{", b'{"schema_version":"1.0.0","schema_version":"2.0.0"}',
                                 b"\xff", b" " * (MAX_REGISTRY_BYTES + 1)])
def test_invalid_or_duplicate_json_and_oversized_bundle_are_rejected(raw):
    with pytest.raises(RegistryError):
        parse_registry(raw)


def test_app_only_snapshot_loads_registry_without_lab_repo_cwd_or_environment(tmp_path):
    snapshot = tmp_path / "snapshot"
    shutil.copytree(REGISTRY_PATH.parents[1], snapshot / "app", ignore=shutil.ignore_patterns("__pycache__"))
    command = "from app.source_registry import get_registry; r=get_registry(); assert len(r.identities)==636; assert len(r.profiles)==15; print(r.registry_version)"
    result = subprocess.run([sys.executable, "-c", command], cwd=tmp_path,
                            env={"PYTHONPATH": str(snapshot), "PYTHONDONTWRITEBYTECODE": "1"},
                            capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    assert get_registry().registry_version in result.stdout
