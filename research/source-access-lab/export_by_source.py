"""Cekilen icerigi kaynak adiyla okunabilir bir klasor yapisina cikarir.

Arsiv icerik adresli saklanir (``results/raw/<sha256>.bin``): ayni icerik iki kez
inmez, bozulma tespit edilir, dosya adi kaynagin adindaki karakterlerden
etkilenmez. Ama bu yapi teslim edilecek is olarak okunmuyor -- klasore bakan biri
hangi dosyanin hangi siteye ait oldugunu goremiyor.

Bu betik ayni veriyi ikinci bir gorunumle disari verir:

    veriler/
      Forbes/
        _kaynak.json          ad, adres, durum, cekilen yuzeyler
        robots.txt
        news_sitemap.xml
      Y-Combinator-Companies/
        _kaynak.json
        companies.html

Kopyalar orijinali degistirmez; arsiv yine tek dogruluk kaynagidir.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import re
import shutil
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
_kosu_onbellek: dict[Path, dict[str, Any]] = {}

# Uzanti once sunucunun bildirdigi turden secilir; yontem adi yalnizca tur
# bilinmiyorsa devreye girer. API yanitlari JSON'dur ve '.bin' olarak yazilirsa
# klasore bakan biri dosyayi acilamaz saniyor.
MIME_UZANTI = {
    "application/json": ".json", "text/json": ".json",
    "application/xml": ".xml", "text/xml": ".xml",
    "application/rss+xml": ".xml", "application/atom+xml": ".xml",
    "text/html": ".html", "application/xhtml+xml": ".html",
    "text/plain": ".txt",
}
UZANTI = {
    "root_html": ".html", "entry_url": ".html", "rel_next_pagination": ".html",
    "sitemap_xml": ".xml", "rss_feed": ".xml", "robots_preflight": ".txt",
}
TR = str.maketrans({"ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G",
                    "ü": "u", "Ü": "U", "ö": "o", "Ö": "O", "ç": "c", "Ç": "C"})


def klasor_adi(ad: str) -> str:
    """Kaynak adindan dosya sisteminde guvenli ama okunabilir bir ad uretir."""
    duz = unicodedata.normalize("NFKC", ad).translate(TR)
    duz = re.sub(r"[^A-Za-z0-9._-]+", "-", duz).strip("-.")
    return duz[:80] or "adsiz"


def dosya_adi(yontem: str, url: str, mime: str, kullanilan: set[str]) -> str:
    son = url.rstrip("/").rsplit("/", 1)[-1] if "/" in url else ""
    son = re.sub(r"[?#].*$", "", son)
    taban = klasor_adi(son) if son and "." in son else yontem
    uzanti = MIME_UZANTI.get(mime.split(";", 1)[0].strip().lower()) or UZANTI.get(
        yontem, Path(taban).suffix or ".bin"
    )
    if not taban.endswith(uzanti):
        taban = Path(taban).stem + uzanti
    ad, sayac = taban, 2
    while ad in kullanilan:
        ad = f"{Path(taban).stem}-{sayac}{uzanti}"
        sayac += 1
    kullanilan.add(ad)
    return ad


def inline_govde(kosu: Path, sha: str) -> bytes | None:
    """Kosu JSON'una gomulu base64 govdeyi cozer; sha256 ile dogrular."""
    payload = _kosu_onbellek.get(kosu)
    if payload is None:
        try:
            payload = json.loads(kosu.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = {}
        _kosu_onbellek[kosu] = payload
    for islem in payload.get("transactions", []):
        if str(islem.get("sha256")) != sha:
            continue
        gomulu = islem.get("inline_body_base64")
        if not gomulu:
            return None
        try:
            govde = base64.b64decode(gomulu)
        except (ValueError, TypeError):
            return None
        # Ozet tutmuyorsa dosya bozulmustur; sessizce yazmak yanlis olur.
        return govde if hashlib.sha256(govde).hexdigest() == sha else None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=HERE / "ARTEFAKT-DIZINI.csv")
    parser.add_argument("--ledger", type=Path, default=HERE / "KAYNAK-DEFTERI.csv")
    parser.add_argument("--out", type=Path, default=HERE / "veriler")
    parser.add_argument("--only-fetched", action="store_true",
                        help="Yalnizca icerigi olan kaynaklari cikarir (robots.txt tek basina yeterli sayilmaz)")
    parser.add_argument("--max-file-bytes", type=int, default=0,
                        help="Bu boyutu asan dosyalar atlanir (0 = sinir yok)")
    parser.add_argument("--max-total-bytes", type=int, default=0,
                        help="Toplam bu boyuta ulasinca durur (0 = sinir yok)")
    parser.add_argument("--methods", default="",
                        help="Yalnizca bu yontemler cikarilir (virgulle)")
    args = parser.parse_args()
    izinli_yontem = {m.strip() for m in args.methods.split(",") if m.strip()}

    defter = {r["source_id"]: r for r in csv.DictReader(args.ledger.open(encoding="utf-8"))}
    kayitlar: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for satir in csv.DictReader(args.index.open(encoding="utf-8")):
        kayitlar[satir["source_id"]].append(satir)

    yazilan_kaynak = kopyalanan = atlanan = 0
    toplam_bayt = 0
    for source_id, satirlar in sorted(kayitlar.items(), key=lambda kv: kv[1][0]["ad"].casefold()):
        durum = defter.get(source_id, {}).get("durum", "")
        if args.only_fetched and durum != "cekildi":
            continue
        ad = satirlar[0]["ad"]
        hedef = args.out / klasor_adi(ad)
        hedef.mkdir(parents=True, exist_ok=True)
        kullanilan: set[str] = set()
        yuzeyler = []
        for satir in sorted(satirlar, key=lambda s: s["yontem"]):
            # Ornek cikarimda sinirlar: tek dosya ve toplam boyut. Boylece depoya
            # konabilecek kucuk bir kume uretilir, secim rastgele degil kurallidir.
            if izinli_yontem and satir["yontem"] not in izinli_yontem:
                continue
            if satir.get("sonuc", "ok") != "ok":
                continue
            bayt = int(satir["bayt"] or 0)
            if args.max_file_bytes and bayt > args.max_file_bytes:
                continue
            if args.max_total_bytes and toplam_bayt + bayt > args.max_total_bytes:
                continue
            hedef_ad = dosya_adi(satir["yontem"], satir["cekilen_url"], satir.get("mime", ""), kullanilan)
            if satir["saklama"] == "dosya":
                kaynak_yolu = satir["dosya"]
                tam = Path(kaynak_yolu) if Path(kaynak_yolu).is_absolute() else HERE / kaynak_yolu
                if not tam.exists():
                    atlanan += 1
                    continue
                shutil.copy2(tam, hedef / hedef_ad)
            else:
                # 16 KB altindaki artefaktlar kosu JSON'unda base64 duruyor. Bunlari
                # atlamak klasoru eksik gosteriyordu: Y Combinator'in sitemap'i var
                # ama gorunmuyordu. Govde cozulup ayni klasore yazilir.
                govde = inline_govde(RESULTS / satir["kosu"], satir["sha256"])
                if govde is None:
                    atlanan += 1
                    continue
                (hedef / hedef_ad).write_bytes(govde)
            kopyalanan += 1
            toplam_bayt += bayt
            yuzeyler.append({
                "yontem": satir["yontem"], "url": satir["cekilen_url"],
                "dosya": hedef_ad, "bayt": int(satir["bayt"] or 0),
                "sha256": satir["sha256"], "tarih": satir["tarih"],
            })
        if not yuzeyler:
            # Sinirlar yuzunden hicbir dosya kopyalanmadiysa bos klasor birakilmaz.
            for artik in hedef.iterdir():
                artik.unlink()
            hedef.rmdir()
            continue
        (hedef / "_kaynak.json").write_text(json.dumps({
            "ad": ad, "source_id": source_id,
            "adres": satirlar[0]["adres"],
            "durum": durum,
            "dogrulama": defter.get(source_id, {}).get("dogrulama", ""),
            "cekilen_yuzeyler": yuzeyler,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        yazilan_kaynak += 1

    print(json.dumps({
        "klasor": str(args.out), "kaynak": yazilan_kaynak,
        "kopyalanan_dosya": kopyalanan, "atlanan": atlanan,
        "toplam_bayt": toplam_bayt,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
