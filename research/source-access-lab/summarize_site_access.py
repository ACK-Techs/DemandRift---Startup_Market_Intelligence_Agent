#!/usr/bin/env python3
"""Render a loss-aware Markdown summary of a bulk source-access report."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "source_manifest.json"
DEFAULT_REPORT = HERE / "results" / "bulk-site-access-live-20260810T203700Z.json"
DEFAULT_OUTPUT = HERE / "SITE-ACCESS-SUMMARY.md"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"object_required:{path}")
    return value


def _short(value: Any, limit: int | None = None) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    text = text.replace("|", "\\|").replace("\n", " ")
    return text if limit is None or len(text) <= limit else text[: limit - 1] + "…"


def _detail_list(records: Iterable[dict[str, Any]], key: str) -> str:
    items: list[dict[str, Any]] = []
    for record in records:
        item = {
            name: record.get(name)
            for name in (
                "result_kind", "url", "canonical_url", "native_id", "candidate_type",
                "content_sha256", "immutable_raw_ref", "source_transaction_id",
            )
            if record.get(name) is not None
        }
        items.append(item)
    return _short(items) if items else "[]"


def build_summary(manifest: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    sources = manifest.get("sources", [])
    if len(sources) != manifest.get("expected_unique_sources", len(sources)):
        raise ValueError("manifest_source_count_mismatch")
    by_id = {site.get("source_id"): site for site in report.get("site_results", [])}
    rows: list[dict[str, Any]] = []
    rates: dict[str, Counter[str]] = defaultdict(Counter)
    for source in sources:
        source_id = source["source_id"]
        site = by_id.get(source_id)
        if site is None:
            methods = [{
                "method_id": "report_coverage", "method_category": "reporting",
                "site_outcome": "not_reported", "stop_reason": "missing_from_input_report",
                "network_transaction_count": 0, "candidate_count": 0,
                "fetched_artifact_count": 0, "candidates": [], "fetched_artifacts": [],
                "details": {},
            }]
            site = {
                "source_id": source_id, "display_name": source["display_name"],
                "official_origin": source.get("official_origin"),
                "resolution_status": source.get("resolution_status"), "methods": methods,
            }
        methods = site.get("methods") or []
        if not methods:
            methods = [{
                "method_id": "report_coverage", "method_category": "reporting",
                "site_outcome": "not_reported", "stop_reason": "no_method_records",
                "network_transaction_count": 0, "candidate_count": 0,
                "fetched_artifact_count": 0, "candidates": [], "fetched_artifacts": [],
                "details": {},
            }]
        normalized: list[dict[str, Any]] = []
        for method in methods:
            row = dict(method)
            row.setdefault("candidates", [])
            row.setdefault("fetched_artifacts", [])
            row.setdefault("details", {})
            row["candidate_count"] = len(row["candidates"])
            row["fetched_artifact_count"] = len(row["fetched_artifacts"])
            normalized.append(row)
            rate = rates[str(row.get("method_id", "unknown"))]
            rate["records"] += 1
            rate[str(row.get("site_outcome", "unknown"))] += 1
            rate["transactions"] += int(row.get("network_transaction_count") or 0)
            rate["candidates"] += row["candidate_count"]
            rate["artifacts"] += row["fetched_artifact_count"]
        rows.append({
            "source_id": source_id,
            "display_name": source["display_name"],
            "official_origin": site.get("official_origin") or source.get("official_origin"),
            "resolution_status": site.get("resolution_status") or source.get("resolution_status"),
            "methods": normalized,
        })
    return {"sources": rows, "rates": rates}


def render_markdown(manifest: dict[str, Any], report: dict[str, Any]) -> str:
    summary = build_summary(manifest, report)
    lines = [
        "# Site Access Summary",
        "",
        "> Bu belge ilk toplu erişim raporundan deterministik olarak üretilmiştir. "
        "Aday URL, fetch edilmiş artefact değildir; erişilemeyen kaynak da sonuç yok anlamına gelmez.",
        "",
        f"- Kaynak sayısı: {len(summary['sources'])}",
        f"- İlk rapor: `{report.get('run_id', 'unknown')}`",
        f"- İşlem: `{report.get('request_accounting', {}).get('used', len(report.get('transactions', [])))}` / "
        f"`{report.get('request_accounting', {}).get('hard_limit', 'unknown')}`",
        "- Global katalog kararı: `retained`",
        "",
        "## Yöntem oranları",
        "",
        "| Yöntem | Kayıt | Başarılı | Başarı oranı | İşlem | Aday | Artefact | Sonuç dağılımı |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for method_id, counts in sorted(summary["rates"].items()):
        total = counts["records"]
        success = counts["succeeded"]
        distribution = ", ".join(
            f"{key}={value}" for key, value in sorted(counts.items())
            if key not in {"records", "transactions", "candidates", "artifacts"}
        )
        lines.append(
            f"| `{method_id}` | {total} | {success} | {success / total:.1%} | "
            f"{counts['transactions']} | {counts['candidates']} | {counts['artifacts']} | {distribution} |"
        )
    lines.extend(["", "## Kaynak ve yöntem ayrıntıları", ""])
    for site in summary["sources"]:
        lines.extend([
            f"### {site['source_id']} — {site['display_name']}",
            "",
            f"Origin: `{site['official_origin'] or 'unresolved'}` · Çözüm: `{site['resolution_status']}` · Katalog: `retained`",
            "",
            "| Yöntem / sınıf | Sonuç | Stop reason | Tx | Aday ayrıntısı | Artefact ayrıntısı | Extractor/details |",
            "| --- | --- | --- | ---: | --- | --- | --- |",
        ])
        for method in site["methods"]:
            lines.append(
                f"| `{method.get('method_id')}` / `{method.get('method_category', 'unknown')}` "
                f"| `{method.get('site_outcome', 'unknown')}` | `{method.get('stop_reason', '')}` "
                f"| {int(method.get('network_transaction_count') or 0)} "
                f"| {_detail_list(method.get('candidates', []), 'candidates')} "
                f"| {_detail_list(method.get('fetched_artifacts', []), 'fetched_artifacts')} "
                f"| {_short(method.get('details', {}))} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    atomic_write_text(args.output, render_markdown(load_json(args.manifest), load_json(args.report)))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
