"""Canli olarak cekilemeyen kaynaklarin icerigini Common Crawl arsivinden alir.

Bot korumasi olan siteler bize sayfa vermiyor ama Common Crawl'in tarayicisina
vermis olabiliyor: olcum, cekilemeyen 167 kaynagin 95'inde arsivde icerik
buldu. Bu yol kural ihlali degildir -- Common Crawl da robots.txt'e uyar, bu
yuzden robots ile yasakli kaynaklar arsivde de yoktur ve burada hic sorgulanmaz.

Akis su: CDX dizini "su WARC dosyasinin su baytindan su kadar bayt" der; o
araliga Range istegi atilir, gelen gzip parcasi cozulur ve WARC kaydinin
icindeki HTTP yanit govdesi ayiklanir. Tam dosya indirilmez.

Onemli ayrim: bu icerik ARSIV ANLIK GORUNTUSUDUR, canli degil. Defterde
``common_crawl_warc`` yontem adiyla durur, boylece canli veriyle karistirilmaz.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from bulk_site_access_lab import (
    MAX_INLINE_ARTIFACT_BYTES,
    RESULTS_DIR,
    USER_AGENT,
    atomic_write_bytes,
    atomic_write_json,
    method_record,
    utc_now,
)

HERE = Path(__file__).resolve().parent
CDX_ORIGIN = "http://index.commoncrawl.org"
DATA_ORIGIN = "https://data.commoncrawl.org"
# En yeni turdan geriye dogru denenir: yeni tur hem guncel icerik verir hem de
# kapsami genis olur. Tek tur sorgulamak 72 kaynagi 'arsivde yok' gosteriyordu;
# her tur farkli sayfalari yakaladigi icin bu bir kapsam sorunudur, kanit degil.
DEFAULT_INDEX = "CC-MAIN-2026-34"
DEFAULT_INDEXES = ("CC-MAIN-2026-34", "CC-MAIN-2026-25", "CC-MAIN-2026-17", "CC-MAIN-2026-04")
CDX_LIMIT = 40
GAP_SECONDS = 1.5
# WARC kaydi = arsiv basligi + HTTP basligi + govde. Aralik istegi bu ucunu birden
# getirir; parca boyutu tipik olarak yuz KB'lar duzeyindedir.
MAX_SLICE_BYTES = 8 * 1024 * 1024
READ_TIMEOUT = 60
# 1 KB altindaki arsiv kaydi sayfa degil koctur (yonlendirme sayfasi, bos govde).
# Bunu icerik saymak deftere yanlis bir 'cekildi' yazardi.
MIN_CONTENT_BYTES = 1024
CDX_ATTEMPTS = 3
CDX_BACKOFF_SECONDS = (2.0, 6.0)


def cdx_url(host: str, index: str = DEFAULT_INDEX) -> str:
    return f"{CDX_ORIGIN}/{index}-index?" + urllib.parse.urlencode({
        "url": f"{host}/*", "output": "json", "limit": CDX_LIMIT,
    })


def parse_cdx(metin: str) -> list[dict[str, Any]]:
    kayitlar = []
    for satir in metin.splitlines():
        satir = satir.strip()
        if not satir.startswith("{"):
            continue
        try:
            kayitlar.append(json.loads(satir))
        except ValueError:
            continue
    return kayitlar


def _yol_derinligi(url: str) -> int:
    yol = urllib.parse.urlsplit(url).path.strip("/")
    return len([p for p in yol.split("/") if p])


def pick_record(kayitlar: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Arsivden hangi kaydi alalim?

    Kaynagi en iyi temsil eden sayfa ana sayfaya en yakin HTML'dir: robots.txt
    bir icerik degil, derin bir makale ise kaynagin tamamini anlatmaz. Sirasiyla
    200 donmus, robots olmayan, HTML turunde ve yolu en sig olan kayit secilir.
    """
    uygun = [
        k for k in kayitlar
        if str(k.get("status")) == "200"
        and not str(k.get("url", "")).rstrip("/").endswith("/robots.txt")
        and str(k.get("filename")) and str(k.get("offset")) and str(k.get("length"))
    ]
    if not uygun:
        return None
    def anahtar(k: dict[str, Any]) -> tuple[int, int, int]:
        html = 0 if "html" in str(k.get("mime", "")).lower() else 1
        return (html, _yol_derinligi(str(k.get("url", ""))), -int(k.get("length", 0)))
    return min(uygun, key=anahtar)


def warc_govde(parca: bytes) -> tuple[bytes, str | None, int | None]:
    """gzip'li WARC parcasindan HTTP yanit govdesini, turunu ve durumunu ayiklar."""
    try:
        cozulmus = gzip.GzipFile(fileobj=io.BytesIO(parca)).read(MAX_SLICE_BYTES)
    except OSError:
        return b"", None, None
    # WARC kaydi ile HTTP yaniti bos satirla ayrilir; ikinci ayrimdan sonrasi govde.
    parcalar = cozulmus.split(b"\r\n\r\n", 2)
    if len(parcalar) < 3:
        return b"", None, None
    http_basligi, govde = parcalar[1], parcalar[2]
    satirlar = http_basligi.split(b"\r\n")
    durum = None
    if satirlar and satirlar[0].startswith(b"HTTP/"):
        parcali = satirlar[0].split()
        if len(parcali) >= 2 and parcali[1].isdigit():
            durum = int(parcali[1])
    mime = None
    for satir in satirlar[1:]:
        if satir.lower().startswith(b"content-type:"):
            mime = satir.split(b":", 1)[1].decode("utf-8", "replace").split(";")[0].strip()
            break
    return govde, mime, durum


def _iste(url: str, *, aralik: str | None = None) -> tuple[bytes, int | None]:
    basliklar = {"User-Agent": USER_AGENT}
    if aralik:
        basliklar["Range"] = aralik
    istek = urllib.request.Request(url, headers=basliklar)
    try:
        with urllib.request.urlopen(istek, timeout=READ_TIMEOUT,
                                    context=ssl.create_default_context()) as yanit:
            return yanit.read(MAX_SLICE_BYTES), yanit.status
    except urllib.error.HTTPError as hata:
        return b"", hata.code
    except Exception:
        return b"", None


def fetch_from_any_index(
    host: str, *, indexes: tuple[str, ...] = DEFAULT_INDEXES,
    isteyici: Callable[..., tuple[bytes, int | None]] = _iste,
    uyuyucu: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Turlari sirayla dener; ilk icerik bulunanda durur.

    Kaynak bir turda yakalanmamis olabilir; bu onun arsivde olmadigini degil o
    turda taranmadigini gosterir. Icerik bulununca kalan turlar sorgulanmaz.
    """
    toplam_istek = 0
    son: dict[str, Any] = {"ok": False, "stop_reason": "tur_denenmedi", "istek": 0}
    for sira, index in enumerate(indexes, 1):
        son = fetch_from_archive(host, index=index, isteyici=isteyici, uyuyucu=uyuyucu)
        toplam_istek += son.get("istek", 0)
        son["index"], son["denenen_tur"] = index, sira
        if son["ok"]:
            break
        uyuyucu(GAP_SECONDS)
    son["istek"] = toplam_istek
    return son


def fetch_from_archive(
    host: str, *, index: str = DEFAULT_INDEX,
    isteyici: Callable[..., tuple[bytes, int | None]] = _iste,
    uyuyucu: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Bir host icin arsivden tek sayfa getirir; her adimin sonucunu dondurur."""
    # CDX servisi yogunlukta 502/503 donuyor; bu gecici bir saglayici hatasidir ve
    # kaynagi arsivde yok saymak icin sebep degildir.
    istek_sayisi = 0
    metin, durum = b"", None
    for deneme in range(CDX_ATTEMPTS):
        metin, durum = isteyici(cdx_url(host, index))
        istek_sayisi += 1
        if metin or (durum is not None and durum < 500):
            break
        if deneme < CDX_ATTEMPTS - 1:
            uyuyucu(CDX_BACKOFF_SECONDS[min(deneme, len(CDX_BACKOFF_SECONDS) - 1)])
    if not metin:
        return {"ok": False, "stop_reason": f"cdx_bos:{durum}", "istek": istek_sayisi}
    kayit = pick_record(parse_cdx(metin.decode("utf-8", "replace")))
    if kayit is None:
        return {"ok": False, "stop_reason": "arsivde_icerik_yok", "istek": istek_sayisi}
    ofset, uzunluk = int(kayit["offset"]), int(kayit["length"])
    parca, durum = isteyici(
        f"{DATA_ORIGIN}/{kayit['filename']}",
        aralik=f"bytes={ofset}-{ofset + uzunluk - 1}",
    )
    if not parca:
        return {"ok": False, "stop_reason": f"warc_alinamadi:{durum}",
                "istek": istek_sayisi + 1, "kayit": kayit}
    govde, mime, http_durum = warc_govde(parca)
    if not govde:
        return {"ok": False, "stop_reason": "warc_cozulemedi",
                "istek": istek_sayisi + 1, "kayit": kayit}
    if len(govde) < MIN_CONTENT_BYTES:
        return {"ok": False, "stop_reason": "arsiv_kaydi_cok_kucuk",
                "istek": istek_sayisi + 1, "kayit": kayit}
    return {"ok": True, "stop_reason": "ok", "istek": istek_sayisi + 1, "kayit": kayit,
            "govde": govde, "mime": mime, "http_durum": http_durum,
            "url": kayit.get("url"), "zaman": kayit.get("timestamp")}


def _artefakt(source_id: str, sonuc: dict[str, Any], raw_dir: Path) -> tuple[dict, dict]:
    govde = sonuc["govde"]
    ozet = hashlib.sha256(govde).hexdigest()
    if len(govde) <= MAX_INLINE_ARTIFACT_BYTES:
        ref, gomulu = f"inline:{ozet}", __import__("base64").b64encode(govde).decode()
    else:
        hedef = raw_dir / f"{ozet}.bin"
        atomic_write_bytes(hedef, govde, ozet)
        ref, gomulu = f"sha256-file:{hedef}", None
    artefakt = {
        "canonical_url": sonuc["url"], "content_sha256": ozet, "immutable_raw_ref": ref,
        "result_kind": "fetched_artifact", "source_transaction_id": f"cc-{source_id}",
        "url": sonuc["url"],
    }
    islem = {
        "transaction_id": f"cc-{source_id}", "source_id": source_id,
        "method_id": "common_crawl_warc", "started_at": utc_now(), "completed_at": utc_now(),
        "requested_url": sonuc["url"], "final_url": sonuc["url"],
        "canonical_url": sonuc["url"], "redirect_chain": [],
        "status": sonuc.get("http_durum"), "mime": sonuc.get("mime"),
        "content_encoding": None, "decoded_bytes": len(govde), "truncated": False,
        "sha256": ozet, "immutable_raw_ref": ref, "inline_body_base64": gomulu,
        "resolved_ip": None, "peer_ip": None, "robots_decision": "archive_snapshot",
        "error_class": None, "stop_reason": None,
        "archive": {"index": sonuc.get("index"), "warc_timestamp": sonuc.get("zaman")},
    }
    return artefakt, islem


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=HERE / "KAYNAK-DEFTERI.csv")
    parser.add_argument("--survey", type=Path, default=RESULTS_DIR / "commoncrawl-survey.json")
    parser.add_argument("--index", default=DEFAULT_INDEX)
    parser.add_argument("--indexes", default=",".join(DEFAULT_INDEXES),
                        help="Sirayla denenecek tur listesi (virgulle)")
    parser.add_argument("--from-ledger", action="store_true",
                        help="Hedefi taramadan degil defterden alir: cekilemeyen ve robots ile yasakli olmayan kaynaklar")
    parser.add_argument("--output", type=Path, default=RESULTS_DIR / "common-crawl-fetch.json")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--live", action="store_true", required=True)
    args = parser.parse_args()

    defter = {r["source_id"]: r for r in csv.DictReader(args.ledger.open(encoding="utf-8"))}
    # Yalnizca taramada icerigi gorulen kaynaklar denenir: digerlerinde arsiv bos
    # ya da sadece robots.txt var, istek harcamak anlamsiz.
    if args.from_ledger:
        # robots ile yasakli kaynaklar haric: Common Crawl da onlari taramaz,
        # sorgulamak bos istek olur.
        hedef = [
            {"source_id": r["source_id"], "ad": r["ad"],
             "host": urllib.parse.urlsplit(r["adres"]).hostname or ""}
            for r in defter.values()
            if r["durum"] in ("kismi", "erisim_yok") and r["adres"]
            and r["sebep"] != "robots_disallowed"
        ]
    else:
        tarama = json.loads(args.survey.read_text(encoding="utf-8"))
        hedef = [t for t in tarama if t.get("icerik") and defter.get(t["source_id"], {}).get("durum") != "cekildi"]
    if args.limit:
        hedef = hedef[: args.limit]
    print(f"arsivden denenecek kaynak: {len(hedef)}", flush=True)

    raw_dir = args.output.parent / "raw"
    site_results, transactions = [], []
    basarili = 0
    for sira, t in enumerate(hedef, 1):
        turlar = tuple(x.strip() for x in args.indexes.split(",") if x.strip())
        sonuc = fetch_from_any_index(t["host"], indexes=turlar)
        yontemler = []
        if sonuc["ok"]:
            artefakt, islem = _artefakt(t["source_id"], sonuc, raw_dir)
            transactions.append(islem)
            basarili += 1
            yontemler.append(method_record(
                {"source_id": t["source_id"], "display_name": t["ad"],
                 "official_origin": defter.get(t["source_id"], {}).get("adres", ""),
                 "resolution_status": "resolved_official_origin"},
                "common_crawl_warc", "acquisition_surface", "succeeded", "ok",
                sonuc["istek"], artifacts=[artefakt],
                details={"archive_index": sonuc.get("index"), "warc_url": sonuc.get("url"),
                         "warc_timestamp": sonuc.get("zaman"),
                         "denenen_tur": sonuc.get("denenen_tur")},
            ))
        else:
            yontemler.append(method_record(
                {"source_id": t["source_id"], "display_name": t["ad"],
                 "official_origin": defter.get(t["source_id"], {}).get("adres", ""),
                 "resolution_status": "resolved_official_origin"},
                "common_crawl_warc", "acquisition_surface", "no_results",
                sonuc["stop_reason"], sonuc["istek"],
                details={"archive_index": sonuc.get("index"),
                         "denenen_tur": sonuc.get("denenen_tur")},
            ))
        site_results.append({
            "source_id": t["source_id"], "display_name": t["ad"],
            "official_origin": defter.get(t["source_id"], {}).get("adres", ""),
            "resolution_status": "resolved_official_origin",
            "global_catalog_disposition": "retained", "worker_pids": [], "methods": yontemler,
        })
        if sira % 10 == 0 or sira == len(hedef):
            print(f"  {sira}/{len(hedef)} | arsivden alinan: {basarili}", flush=True)
        time.sleep(GAP_SECONDS)

    atomic_write_json(args.output, {
        "schema_version": "1.0.0", "runner_version": "common-crawl-pass-1.0.0",
        "mode": "archive", "manifest_id": "common-crawl", "run_id": args.index,
        "started_at": utc_now(), "completed_at": utc_now(),
        "source_count": len(site_results), "site_results": site_results,
        "transactions": transactions, "worker_results": [], "workers_requested": 1,
        "origin_pid_map": {}, "global_catalog_disposition": "retained",
        "request_accounting": {"used": sum(s["methods"][0]["network_transaction_count"] for s in site_results)},
    })
    print(json.dumps({"cikti": str(args.output), "denenen": len(hedef),
                      "arsivden_alinan": basarili}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
