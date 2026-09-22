"""Kaynak defterini urun arastirmasi icin anlamli bir aday kataloga cevirir.

Defter bir **erisim kaydidir**: "bu adrese ulasabildik mi, ne indi". Arastirma
icin gereken ise **aday katalogdur**: "bu kaynak arastirmada ne ise yarar, hangi
rolde, birlikte ele alinmasi gereken baska kaynak var mi".

Iki ayrimi gorunur kilar:

**Ayni host / farkli marka.** Defterde Bing, Bing News ve Bing Webmaster Tools
ayri birer kaynak; ucu de bing.com. Marka olarak ayridirlar -- farkli soruyu
cevaplarlar -- ama teknik olarak tek bir sitedir. Ayrimi gormeden sistem ayni
siteye uc kez sorgu atar, kotayi uc kez yakar ve ayni veriyi uc kez sayar.
Katalog her satirda host'u ve o host'u kac markanin paylastigini tasir.

**Discovery yuzeyi / gercek veri yuzeyi.** Bir sitemap nereye bakilacagini
soyler ama kendisi arastirma verisi tasimaz; urun sayfasi veriyi tasir;
robots.txt ikisi de degildir, erisim politikasidir. Bunlari ayni sutunda
tutmak "veri cekildi" ifadesini yaniltici kilar: yalnizca sitemap indirilmis
bir kaynak, hangi sayfalara bakilacagini bilir ama henuz veri toplamamistir.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import urllib.parse
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

# Yuzeyin arastirmadaki rolu. Karar sudur: yuzey arastirma verisi tasiyor mu,
# yoksa verinin nerede oldugunu mu soyluyor?
YUZEY_ROLU: dict[str, str] = {
    # Gercek veri: icerigin kendisi burada.
    "root_html": "veri",
    "entry_url": "veri",
    "common_crawl_warc": "veri",
    "rel_next_pagination": "veri",
    # Kesif: nereye bakilacagini soyler, kendisi veri tasimaz.
    "sitemap_xml": "kesif",
    "rss_link_discovery": "kesif",
    # Karma: baslik ve ozet tasir, tam icerik icin baglantiya gidilir.
    "rss_feed": "karma",
    # Politika: erisim kurali, arastirma malzemesi degil.
    "robots_preflight": "politika",
}
# API yanitlari veri tasir; yontem adlari kaynaga gore degistigi icin desenle
# taninir (stackexchange_questions, github_repository_search, npm_registry_search...).
API_ROLU = "veri"


def yuzey_rolu(yontem: str) -> str:
    return YUZEY_ROLU.get(yontem, API_ROLU)


def sade_host(adres: str) -> str:
    host = (urllib.parse.urlsplit(adres).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=HERE / "KAYNAK-DEFTERI.csv")
    parser.add_argument("--index", type=Path, default=HERE / "ARTEFAKT-DIZINI.csv")
    parser.add_argument("--surfaces", type=Path, default=HERE / "ARAMA-YUZEYLERI.csv")
    parser.add_argument("--kategori-kaynak", type=Path, default=HERE / "KATEGORI-KAYNAK.csv")
    parser.add_argument("--kategori-soru", type=Path, default=HERE / "KATEGORI-SORU.csv")
    parser.add_argument("--out", type=Path, default=HERE / "ADAY-KATALOG.csv")
    args = parser.parse_args()

    def oku(yol: Path) -> list[dict[str, str]]:
        with yol.open(encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    defter = oku(args.ledger)
    dizin = oku(args.index)
    yuzey = {r["ad"]: r for r in oku(args.surfaces)}
    kategori_kaynak = oku(args.kategori_kaynak)
    kategori_soru = oku(args.kategori_soru)

    # Kaynak basina hangi yuzeylerden BASARIYLA icerik alindi
    alinan: dict[str, set[str]] = collections.defaultdict(set)
    for satir in dizin:
        if satir.get("sonuc", "ok") == "ok" and satir["ad"]:
            alinan[satir["ad"]].add(satir["yontem"])

    # Kaynak -> hangi kategorilerde ve hangi rolde
    kategoriler: dict[str, set[str]] = collections.defaultdict(set)
    roller: dict[str, set[str]] = collections.defaultdict(set)
    for satir in kategori_kaynak:
        kategoriler[satir["kaynak"]].add(satir["hedef"])
        roller[satir["kaynak"]].add(satir["rol"])

    # Kaynak grubu -> kac soruya kanit veriyor
    grup_soru: dict[str, set[str]] = collections.defaultdict(set)
    for satir in kategori_soru:
        grup_soru[satir["kanit_kaynak_grubu"]].add(satir["soru_id"])
    kaynak_soru: dict[str, set[str]] = collections.defaultdict(set)
    for satir in kategori_kaynak:
        for grup in satir["kaynak_grubu"].split(" | "):
            kaynak_soru[satir["kaynak"]] |= grup_soru.get(grup.strip(), set())

    # Host paylasimi: ayni host'ta kac marka var
    host_markalari: dict[str, list[str]] = collections.defaultdict(list)
    for satir in defter:
        if satir["adres"]:
            host_markalari[sade_host(satir["adres"])].append(satir["ad"])

    satirlar: list[dict[str, Any]] = []
    for satir in defter:
        ad = satir["ad"]
        host = sade_host(satir["adres"]) if satir["adres"] else ""
        kardesler = [a for a in host_markalari.get(host, []) if a != ad]
        yuzeyler = alinan.get(ad, set())
        rol_sayaci = collections.Counter(yuzey_rolu(y) for y in yuzeyler)

        # Arastirma degeri: veri yuzeyi varsa kaynak arastirmaya girdi saglar;
        # yalnizca kesif varsa nereye bakilacagi bilinir ama veri henuz yok;
        # yalnizca politika varsa kaynak arastirma icin bos demektir.
        if rol_sayaci["veri"]:
            deger = "veri-var"
        elif rol_sayaci["karma"]:
            deger = "kismi-veri"
        elif rol_sayaci["kesif"]:
            deger = "yalniz-kesif"
        elif rol_sayaci["politika"]:
            deger = "yalniz-politika"
        else:
            deger = "bos"

        satirlar.append({
            "source_id": satir["source_id"], "ad": ad, "adres": satir["adres"],
            "host": host,
            "host_marka_sayisi": len(host_markalari.get(host, [])) if host else 0,
            "host_kardesleri": ", ".join(sorted(kardesler)),
            "arastirma_degeri": deger,
            "veri_yuzeyi": ", ".join(sorted(y for y in yuzeyler if yuzey_rolu(y) == "veri")),
            "kesif_yuzeyi": ", ".join(sorted(y for y in yuzeyler if yuzey_rolu(y) == "kesif")),
            "karma_yuzey": ", ".join(sorted(y for y in yuzeyler if yuzey_rolu(y) == "karma")),
            "kategoriler": ", ".join(sorted(kategoriler.get(ad, set()))),
            "kaynak_rolu": ", ".join(sorted(roller.get(ad, set()))),
            "cevapladigi_soru": len(kaynak_soru.get(ad, set())),
            "durum": satir["durum"], "guven": satir["guven"],
            "dogrulama": satir["dogrulama"],
            "arama_yolu": yuzey.get(ad, {}).get("en_iyi_yol", ""),
            "engel": satir["sebep"],
        })

    satirlar.sort(key=lambda r: (r["arastirma_degeri"], -r["host_marka_sayisi"],
                                 r["ad"].casefold()))
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        yazici = csv.DictWriter(handle, fieldnames=list(satirlar[0]))
        yazici.writeheader()
        yazici.writerows(satirlar)

    paylasimli = [r for r in satirlar if r["host_marka_sayisi"] > 1]
    print(json.dumps({
        "cikti": str(args.out), "kaynak": len(satirlar),
        "arastirma_degeri": collections.Counter(
            r["arastirma_degeri"] for r in satirlar).most_common(),
        "host_paylasan_marka": len(paylasimli),
        "paylasilan_host": len({r["host"] for r in paylasimli}),
        "en_kalabalik_host": collections.Counter(
            r["host"] for r in paylasimli).most_common(3),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
