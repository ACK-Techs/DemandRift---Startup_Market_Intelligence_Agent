"""Reproduce the packaged source bundle from fixed, offline historical inputs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

API_ROOT = Path(__file__).resolve().parents[1]
ROOT = API_ROOT.parent.parent
sys.path.insert(0, str(API_ROOT))
from app.source_registry import REGISTRY_PATH, canonical_json, content_digest, parse_registry  # noqa: E402

LAB = ROOT / "faz-1-fikir-ve-arastirma/veri-laboratuvari"
INPUT_NAMES = ("source_manifest.json", "KAYNAK-SAGLIK.csv", "KAYNAK-ALAN.csv", "KATEGORI-KAYNAK.csv")
HEALTH = {
    "saglikli": "eligible", "politika-kapali": "policy_blocked", "bot-korumasi": "bot_challenged",
    "icerik-yetersiz": "content_insufficient",
}


def rows(name: str) -> list[dict[str, str]]:
    with (LAB / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_bundle(seed: dict) -> dict:
    """Curated request definitions stay explicit; observations never enable them."""
    manifest = json.loads((LAB / "source_manifest.json").read_text(encoding="utf-8"))
    ids = [source["source_id"] for source in manifest["sources"]]
    if len(ids) != 636 or len(set(ids)) != 636:
        raise ValueError("invalid historical inventory")
    observations = rows("KAYNAK-SAGLIK.csv")
    if len({r["source_id"] for r in observations}) != len(observations):
        raise ValueError("ambiguous historical observation")
    health = {row["source_id"]: row for row in observations}
    fields = rows("KAYNAK-ALAN.csv")
    category_rows = rows("KATEGORI-KAYNAK.csv")
    result = {
        "schema_version": "1.0.0",
        "historical_inputs": [{"path": (LAB / name).relative_to(ROOT).as_posix(),
                               "sha256": hashlib.sha256((LAB / name).read_bytes()).hexdigest()}
                              for name in INPUT_NAMES],
        "identities": [{"source_id": source["source_id"], "display_name": source["display_name"],
                        "official_origin": source.get("official_origin") or None,
                        "resolution_status": source["resolution_status"],
                        "verification_basis": source["verification_basis"],
                        "disposition": "candidate_only", "runtime_enabled": False}
                       for source in manifest["sources"]],
        "profiles": [], "categories": seed["categories"], "f03_source_ids": seed["f03_source_ids"],
        "legacy_snapshots_json": seed["legacy_snapshots_json"],
    }
    by_id = {source["source_id"]: source for source in manifest["sources"]}
    categories = {policy["category"] for policy in seed["categories"]}
    for old in seed["profiles"]:
        source_id = old["source_id"]
        source = by_id[source_id]
        row = health[source_id]
        if row["kaynak_adi"] != source["display_name"]:
            raise ValueError("historical identity mismatch")
        surfaces = [{"surface_id": endpoint["method_id"], "endpoint_url": endpoint["url"],
                     "provenance_ref": "source_manifest.json"} for endpoint in source["api_endpoints"]]
        if row["son_denenen_url"] and row["son_denenen_url"] not in {s["endpoint_url"] for s in surfaces}:
            surfaces.append({"surface_id": "measured-2026-09-27", "endpoint_url": row["son_denenen_url"],
                             "provenance_ref": "KAYNAK-SAGLIK.csv"})
        result["profiles"].append({
            "source_id": source_id, "family": old["family"],
            "allowed_categories": sorted({r["hedef"] for r in category_rows
                                          if r["kaynak"] == source["display_name"] and r["hedef"] in categories}),
            "observation": {"measured_at": row["son_olcum"], "health": HEALTH.get(row["saglik"], "profile_incomplete"),
                            "content_surface": row["bugun_icerik"], "requested_url": row["son_denenen_url"],
                            "artifact_hash": row["kanit_artefakti"] or None, "reason": row["sebep"]},
            "trial_expected_fields": old["trial_expected_fields"],
            "catalog_field_evidence": [{"name": r["alan"], "locator": r["dogrulama_izi"],
                                        "query_kind": r["yol"], "permission_snapshot": r["izin_durumu"],
                                        "input_ref": "KAYNAK-ALAN.csv"}
                                       for r in fields if r["source_id"] == source_id and r["guven"] == "dogrulandi"],
            # Field CSV lacks an exact surface URL/date/hash binding. Do not redate or widen it.
            "current_verified_fields": [], "historical_surfaces": surfaces,
            "preview_surface": old["preview_surface"], "runtime_enabled": False,
            "current_health": "deferred", "current_permission": "unknown", "ownership_key": None,
            "license_or_restriction": None, "retention_policy": None, "language_scope": [], "market_scope": None,
        })
    digest = content_digest(result)
    result.update(registry_version=f"source-registry-v1-{digest[:16]}", content_digest=digest)
    # Validate exactly the bytes deployed in app/data, not a permissively coerced Python model.
    parse_registry(canonical_json(result).encode("utf-8"))
    return result


def generated_text(seed: dict) -> str:
    return json.dumps(build_bundle(seed), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    seed = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    expected = generated_text(seed)
    if args.check:
        if REGISTRY_PATH.read_text(encoding="utf-8") != expected:
            raise SystemExit("source registry drift; review dated inputs and regenerate")
        print("source registry: 636 identities, 15 profiles; reproducible offline bundle")
    else:
        REGISTRY_PATH.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
