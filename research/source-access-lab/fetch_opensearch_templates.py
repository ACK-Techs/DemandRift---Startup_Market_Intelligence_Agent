"""OpenSearch tanim dosyalarindan sorgu sablonunu cikarir ve saklar.

``ARAMA-YUZEYLERI.csv`` OpenSearch kaynaklari icin yalnizca **tanim dosyasinin
adresini** tutuyor (``play.google.com/opensearch.xml``), icindeki sorgu
sablonunu degil. Sablon olmadan derleyici URL uretemez -- uydurmak yerine
"tanim cekilmedi" diye isaretliyordu.

Bu script tanim dosyasini bir kez ceker, ``<Url type="text/html"
template="...{searchTerms}...">`` alanini ayiklar ve ``OPENSEARCH-SABLONLARI.csv``
dosyasina yazar. Sonuc repoya islenir; derleyici bir daha aga cikmaz ve
calistirma deterministik kalir.

Erisim politikasi degismedi: yalnizca kaynagin **kendi ilan ettigi** tanim
dosyasi cekilir, robots on kontrolu sonuclari korunur, bot korumasi asilmaz.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
UA = "DemandRift-research/1.0 (academic source study; contact via repository)"
BEKLEME = 2.0
AZAMI_BAYT = 256 * 1024

OPENSEARCH_AD = "{http://a9.com/-/spec/opensearch/1.1/}"


def sablon_cikar(govde: bytes) -> tuple[str, str]:
    """(sablon, not) doner. HTML sonucu veren Url tercih edilir."""
    try:
        kok = ET.fromstring(govde)
    except ET.ParseError as hata:
        return "", f"xml_ayristirilamadi: {hata}"
    adaylar: list[tuple[str, str]] = []
    for oge in kok.iter():
        if not oge.tag.endswith("Url"):
            continue
        sablon = oge.attrib.get("template", "")
        if "{searchTerms}" in sablon:
            adaylar.append((oge.attrib.get("type", ""), sablon))
    if not adaylar:
        return "", "searchTerms_iceren_url_yok"
    for tur, sablon in adaylar:
        if "html" in tur.lower():
            return sablon, ""
    return adaylar[0][1], f"html_disi_tur: {adaylar[0][0]}"


def cek(adres: str, zaman_asimi: float = 20.0) -> tuple[bytes, str]:
    istek = urllib.request.Request(
        adres, headers={"User-Agent": UA,
                        "Accept": "application/opensearchdescription+xml, application/xml"})
    try:
        with urllib.request.urlopen(istek, timeout=zaman_asimi) as yanit:
            return yanit.read(AZAMI_BAYT), ""
    except urllib.error.HTTPError as hata:
        return b"", f"http_{hata.code}"
    except Exception as hata:                      # ag hatasi, zaman asimi
        return b"", f"ag_hatasi: {type(hata).__name__}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surfaces", type=Path, default=HERE / "ARAMA-YUZEYLERI.csv")
    parser.add_argument("--out", type=Path, default=HERE / "OPENSEARCH-SABLONLARI.csv")
    parser.add_argument("--sadece", action="append", default=None,
                        help="Yalnız bu kaynakları çeker")
    parser.add_argument("--canli", action="store_true",
                        help="Ağa çıkmayı açıkça etkinleştirir")
    args = parser.parse_args()

    with args.surfaces.open(encoding="utf-8") as handle:
        yuzeyler = [r for r in csv.DictReader(handle)
                    if r["opensearch"] and r["en_iyi_yol"] == "opensearch"]
    if args.sadece:
        istenen = set(args.sadece)
        yuzeyler = [r for r in yuzeyler if r["ad"] in istenen]

    mevcut: dict[str, dict[str, str]] = {}
    if args.out.exists():
        with args.out.open(encoding="utf-8") as handle:
            mevcut = {r["ad"]: r for r in csv.DictReader(handle)}

    if not args.canli:
        print(json.dumps({"mod": "cevrimdisi", "onbellekte": len(mevcut),
                          "cekilecek": len([r for r in yuzeyler if r["ad"] not in mevcut]),
                          "not": "--canli verilmedi, ağa çıkılmadı"}, ensure_ascii=False))
        return 0

    for satir in yuzeyler:
        if satir["ad"] in mevcut:
            continue                                    # onbellekte, tekrar cekme
        govde, hata = cek(satir["opensearch"])
        sablon, notu = ("", hata) if hata else sablon_cikar(govde)
        mevcut[satir["ad"]] = {
            "source_id": satir["source_id"], "ad": satir["ad"],
            "tanim_adresi": satir["opensearch"], "sablon": sablon,
            "not": notu, "alindi": time.strftime("%Y-%m-%d"),
        }
        time.sleep(BEKLEME)

    satirlar = sorted(mevcut.values(), key=lambda r: r["ad"].casefold())
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        yazici = csv.DictWriter(
            handle, fieldnames=["source_id", "ad", "tanim_adresi", "sablon",
                                "not", "alindi"])
        yazici.writeheader()
        yazici.writerows(satirlar)

    basarili = [r for r in satirlar if r["sablon"]]
    print(json.dumps({
        "cikti": str(args.out), "kaynak": len(satirlar),
        "sablon_alinan": len(basarili),
        "alinamayan": [(r["ad"], r["not"]) for r in satirlar if not r["sablon"]][:8],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
