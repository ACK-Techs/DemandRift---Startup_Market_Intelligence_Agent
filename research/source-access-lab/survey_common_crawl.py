"""Cekilemeyen kaynaklarin Common Crawl arsivinde kaydi var mi diye tarar.

Kod yazmadan once kapsami olcer: hangi kaynak icin kac sayfa arsivlenmis ve
hangi dizin turunde. Yalnizca CDX dizinini sorgular, icerik indirmez.

robots_disallowed kaynaklar kasten haric tutulur: Common Crawl da robots.txt'e
uydugu icin onlar arsivde zaten yok, sorgulamak bos istek olur.
"""
from __future__ import annotations

import argparse
import csv
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = "http://index.commoncrawl.org/{index}-index"
UA = "DemandRiftBulkSourceAccessLab/1.0 (+research contact via repository)"
GAP_SECONDS = 1.5


def sorgula(host: str, index: str) -> dict[str, object]:
    url = INDEX.format(index=index) + "?" + urllib.parse.urlencode({
        "url": f"{host}/*", "output": "json", "limit": 40,
    })
    istek = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(istek, timeout=40, context=ssl.create_default_context()) as yanit:
            govde = yanit.read(400_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as hata:
        return {"kayit": 0, "not": f"http_{hata.code}"}
    except Exception as hata:
        return {"kayit": 0, "not": type(hata).__name__}
    satirlar = []
    for satir in govde.splitlines():
        satir = satir.strip()
        if not satir.startswith("{"):
            continue
        try:
            satirlar.append(json.loads(satir))
        except ValueError:
            continue
    basarili = [s for s in satirlar if str(s.get("status")) == "200"]
    # robots.txt disinda gercek sayfa var mi? Yalnizca robots arsivlenmisse bu
    # kaynak icin Common Crawl bir sey kazandirmaz.
    icerik = [s for s in basarili if not str(s.get("url", "")).endswith("/robots.txt")]
    return {
        "kayit": len(satirlar), "basarili": len(basarili), "icerik": len(icerik),
        "ornek": icerik[0].get("url") if icerik else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="CC-MAIN-2025-08")
    parser.add_argument("--out", type=Path, default=HERE / "results" / "commoncrawl-survey.json")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    rows = list(csv.DictReader(open(HERE / "KAYNAK-DEFTERI.csv", encoding="utf-8")))
    hedef = [
        r for r in rows
        if r["durum"] in ("kismi", "erisim_yok") and r["adres"]
        and r["sebep"] != "robots_disallowed"
    ]
    if args.limit:
        hedef = hedef[: args.limit]
    print(f"taranacak kaynak: {len(hedef)}", flush=True)

    sonuc = []
    for sira, r in enumerate(hedef, 1):
        host = urllib.parse.urlsplit(r["adres"]).hostname or ""
        veri = sorgula(host, args.index)
        sonuc.append({"source_id": r["source_id"], "ad": r["ad"], "host": host,
                      "sebep": r["sebep"], **veri})
        if sira % 20 == 0 or sira == len(hedef):
            var = sum(1 for s in sonuc if s.get("icerik"))
            print(f"  {sira}/{len(hedef)} | arsivde icerigi olan: {var}", flush=True)
            args.out.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(GAP_SECONDS)

    args.out.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    var = [s for s in sonuc if s.get("icerik")]
    print(json.dumps({
        "taranan": len(sonuc), "arsivde_icerigi_olan": len(var),
        "oran": f"%{100 * len(var) / len(sonuc):.1f}" if sonuc else "-",
        "cikti": str(args.out),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
