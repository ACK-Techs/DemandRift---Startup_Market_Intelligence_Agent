"""Indirilen her dosyanin hangi kaynaga ve hangi adrese ait oldugunu tek dizinde toplar.

Ham icerik ``results/raw/<sha256>.bin`` olarak saklanir; ad icerigin ozetidir,
sitenin adi degil. Bu kasitlidir (ayni icerik iki kez inmez, bozulma tespit
edilir, dosya adi Turkce karakterden etkilenmez) ama arsivi tek basina okunmaz
kilar. Bu dizin o baglantiyi disari cikarir: hangi dosya, hangi kaynagin, hangi
adresinden, hangi kosuda, ne zaman alindi.

Cikti ``ARTEFAKT-DIZINI.csv``. Ham icerik depoya girmese bile bu dosya girer;
boylece arsivi gormeyen biri de neyin cekildigini gorebilir.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def kosu_dosyalari(runs: Iterable[Path]) -> list[Path]:
    return sorted({p for p in runs if p.is_file()}, key=lambda p: p.name)


def satirlar(runs: list[Path]) -> list[dict[str, Any]]:
    gorulen: set[tuple[str, str, str]] = set()
    cikti: list[dict[str, Any]] = []
    for run in runs:
        try:
            payload = json.loads(run.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        tarih = str(payload.get("completed_at") or payload.get("started_at") or "")[:19]
        # Uzanti yontem adindan degil sunucunun bildirdigi turden tureme olmali:
        # API yanitlari JSON'dur, '.bin' olarak yazmak dosyayi okunmaz gosterir.
        mime_by_sha = {
            str(t.get("sha256")): str(t.get("mime") or "")
            for t in payload.get("transactions", []) if t.get("sha256")
        }
        for site in payload.get("site_results", []):
            for method in site.get("methods", []):
                for artifact in method.get("fetched_artifacts", []):
                    sha = str(artifact.get("content_sha256") or "")
                    url = str(artifact.get("url") or "")
                    anahtar = (site["source_id"], sha, url)
                    if not sha or anahtar in gorulen:
                        continue
                    gorulen.add(anahtar)
                    ref = str(artifact.get("immutable_raw_ref") or "")
                    if ref.startswith("sha256-file:"):
                        yol = ref.removeprefix("sha256-file:")
                        tam = HERE / yol if not Path(yol).is_absolute() else Path(yol)
                        bayt = tam.stat().st_size if tam.exists() else 0
                        saklama = "dosya"
                    else:
                        # 16 KB altindaki artefaktlar kosu JSON'unun icinde base64 durur.
                        yol, bayt, saklama = run.name, 0, "kosu_json_icinde"
                    cikti.append({
                        "source_id": site["source_id"], "ad": site["display_name"],
                        "adres": site.get("official_origin") or "", "yontem": method["method_id"],
                        "cekilen_url": url, "mime": mime_by_sha.get(sha, ""), "sha256": sha,
                        "saklama": saklama, "dosya": yol, "bayt": bayt,
                        "kosu": run.name, "tarih": tarih,
                    })
    cikti.sort(key=lambda r: (r["ad"].casefold(), r["yontem"], r["cekilen_url"]))
    return cikti


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "ARTEFAKT-DIZINI.csv")
    parser.add_argument("runs", type=Path, nargs="*", help="bulk-site-access-*.json kosulari")
    args = parser.parse_args()

    runs = kosu_dosyalari(args.runs or RESULTS.glob("bulk-site-access-*.json"))
    rows = satirlar(runs)
    if not rows:
        print(json.dumps({"satir": 0, "not": "artefakt bulunamadi"}, ensure_ascii=False))
        return 1
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    kaynak = len({r["source_id"] for r in rows})
    dosyada = sum(1 for r in rows if r["saklama"] == "dosya")
    print(json.dumps({
        "cikti": str(args.out), "satir": len(rows), "kaynak": kaynak,
        "ayri_dosyada": dosyada, "kosu_json_icinde": len(rows) - dosyada,
        "toplam_bayt": sum(r["bayt"] for r in rows),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
