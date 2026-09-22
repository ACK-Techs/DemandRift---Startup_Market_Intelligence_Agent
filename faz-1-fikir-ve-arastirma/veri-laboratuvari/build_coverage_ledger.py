"""Her kaynak icin adres ve cekim durumunu tek bir okunabilir defterde toplar.

Girdi olarak manifest ile butun fetch kosularinin sonuclarini okur; kaynak basina
en iyi durumu secer (bir kaynak birden fazla kosuda denenmis olabilir). Cikti hem
Markdown tablosu hem de CSV olarak yazilir; sayilar artefaktlardan turetilir, elle
sayim yapilmaz.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
# Icerik sayilan yuzey, method_id listesiyle degil runner'in kendi sinifiyla
# belirlenir: resmi API yaniti da bir edinim yuzeyidir ve cogu zaman HTML'den
# daha iyi veridir. Sabit liste yuzunden API ile cekilen kaynaklar 'kismi'
# gorunuyordu.
CONTENT_CATEGORY = "acquisition_surface"
RANK = {"cekildi": 3, "kismi": 2, "erisim_yok": 1, "adres_yok": 0}


def fetch_state(site: dict[str, Any]) -> tuple[str, list[str], str]:
    got = [m["method_id"] for m in site["methods"] if (m.get("fetched_artifact_count") or 0) > 0]
    content = [
        m["method_id"] for m in site["methods"]
        if m.get("method_category") == CONTENT_CATEGORY and (m.get("fetched_artifact_count") or 0) > 0
    ]
    if site.get("resolution_status") != "resolved_official_origin":
        return "adres_yok", [], "unresolved_official_origin"
    reason = next(
        (m.get("stop_reason") for m in site["methods"]
         if m["method_id"] == "robots_preflight" and (m.get("fetched_artifact_count") or 0) == 0),
        "",
    ) or next(
        (m.get("stop_reason") for m in site["methods"]
         if m.get("method_category") == CONTENT_CATEGORY and (m.get("fetched_artifact_count") or 0) == 0),
        "",
    )
    if content:
        return "cekildi", content, ""
    return ("kismi", got, reason) if got else ("erisim_yok", [], reason)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=HERE / "source_manifest.json")
    parser.add_argument("--out-md", type=Path, default=HERE / "KAYNAK-DEFTERI.md")
    parser.add_argument("--out-csv", type=Path, default=HERE / "KAYNAK-DEFTERI.csv")
    parser.add_argument("runs", type=Path, nargs="+", help="bulk-site-access-*.json kosulari")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    rows: dict[str, dict[str, Any]] = {
        s["source_id"]: {
            "source_id": s["source_id"], "ad": s["display_name"],
            "adres": s.get("official_origin") or "",
            "dogrulama": s.get("verification_basis", ""), "guven": s.get("confidence", ""),
            "durum": "adres_yok" if not s.get("official_origin") else "erisim_yok",
            "yuzeyler": "", "sebep": "", "kosu": "",
        } for s in manifest["sources"]
    }

    for run in args.runs:
        payload = json.loads(run.read_text(encoding="utf-8"))
        for site in payload.get("site_results", []):
            row = rows.get(site["source_id"])
            if row is None:
                continue
            state, surfaces, reason = fetch_state(site)
            if RANK[state] >= RANK[row["durum"]]:
                row.update({
                    "durum": state, "yuzeyler": ",".join(sorted(surfaces)),
                    "sebep": reason or "", "kosu": run.name,
                })

    ordered = sorted(rows.values(), key=lambda r: (-RANK[r["durum"]], r["ad"].casefold()))
    counts = {k: sum(1 for r in ordered if r["durum"] == k) for k in RANK}

    with args.out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ordered[0]))
        writer.writeheader()
        writer.writerows(ordered)

    label = {"cekildi": "✅ Çekildi", "kismi": "⚠️ Kısmi",
             "erisim_yok": "❌ Adres var, erişilemedi", "adres_yok": "❌ Adres yok"}
    lines = [
        "# DemandRift — Kaynak Defteri", "",
        f"Toplam **{len(ordered)}** kaynak. Sayılar artefaktlardan üretilmiştir; "
        f"bu dosya `build_coverage_ledger.py` ile yeniden üretilebilir.", "",
        "| Durum | Kaynak | Oran |", "|---|---:|---:|",
    ]
    for key in ("cekildi", "kismi", "erisim_yok", "adres_yok"):
        lines.append(f"| {label[key]} | {counts[key]} | %{100 * counts[key] / len(ordered):.1f} |")
    lines += ["", "---", "", "| Durum | Kaynak | Adres | Yüzeyler | Doğrulama | Sebep |",
              "|---|---|---|---|---|---|"]
    for row in ordered:
        lines.append(
            f"| {label[row['durum']]} | {row['ad']} | {row['adres'] or '—'} | "
            f"{row['yuzeyler'] or '—'} | {row['dogrulama'] or '—'} | {row['sebep'] or '—'} |"
        )
    args.out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"markdown": str(args.out_md), "csv": str(args.out_csv), **counts},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
