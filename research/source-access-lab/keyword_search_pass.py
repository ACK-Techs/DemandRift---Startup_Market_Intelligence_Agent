"""Bir anahtar kelimeyi kaynaklara sorar ve sonuclari artefakt olarak saklar.

Gorev 3'un calisan tarafi. Katalog (``ARAMA-YUZEYLERI.csv``) her kaynak icin
hangi yolun kullanilacagini soyler; bu betik o yolu uygular:

* ``opensearch``  — sitenin ilan ettigi sablon indirilir, {searchTerms} yerine
  kelime konur. En saglam yol: adresi biz uydurmayiz, site kendi soyler.
* ``site_search`` — sayfadan cikarilan ``?q=`` kalibina kelime konur.
* ``api``         — resmi API ucundaki sorgu parametresi kelimeyle degistirilir.
* ``local_index`` — ag istegi yok: sitemap'ten toplanan 339 bin URL'de aranir.

Canli sorgular yeni bir ag kodu ile degil, ``bulk_site_access_lab`` uzerinden
atilir: robots kontrolu, cikis guvenligi, istek butcesi ve sha256 artefakt
saklama zaten orada ve tek yerde kalmalidir. Arama URL'i kaynagin ``entry_path``
alanina yazilir, boylece sonuc da ayni deftere ve dizine duser.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any

from bulk_site_access_lab import RESULTS_DIR, atomic_write_json, load_manifest, run_lab

HERE = Path(__file__).resolve().parent
CANLI_YOLLAR = ("opensearch", "site_search", "api")
# OpenSearch sablonunda sorgu yerini bu belirtec tutar (OpenSearch 1.1).
SEARCH_TERMS = "{searchTerms}"
URL_SABLON = re.compile(rb'(?is)<Url[^>]+template=["\']([^"\']+)["\'][^>]*>')
SORGU_ADLARI = ("q", "query", "search", "keyword", "term", "text", "s")


def opensearch_sablonu(xml: bytes) -> str | None:
    """OpenSearch belgesinden HTML sonuc sablonunu secer."""
    adaylar = [m.group(1).decode("utf-8", "replace") for m in URL_SABLON.finditer(xml)]
    # type="text/html" olan sablon kullanici arayuzunun sonucudur; digerleri
    # (suggestion/atom) farkli bicimde doner.
    html_olan = [
        m.group(1).decode("utf-8", "replace")
        for m in URL_SABLON.finditer(xml)
        if b'type="text/html"' in m.group(0) or b"type='text/html'" in m.group(0)
    ]
    for sablon in html_olan or adaylar:
        if SEARCH_TERMS in sablon:
            return sablon
    return None


def sablonu_doldur(sablon: str, kelime: str) -> str:
    """Sablondaki sorgu yerini kelimeyle doldurur, kalan belirtecleri temizler."""
    dolu = sablon.replace(SEARCH_TERMS, urllib.parse.quote(kelime))
    # OpenSearch sablonlari sayfalama/dil belirtecleri de tasiyabilir; doldurulmayan
    # belirtec URL'de kalirsa istek bozulur, bu yuzden bosaltilir.
    return re.sub(r"\{[^}]*\}", "", dolu)


def sorgu_parametresini_degistir(url: str, kelime: str) -> str | None:
    """URL'deki sorgu parametresini kelimeyle degistirir."""
    parcalar = urllib.parse.urlsplit(url)
    alanlar = urllib.parse.parse_qsl(parcalar.query, keep_blank_values=True)
    hedef = next((ad for ad, _ in alanlar if ad.lower() in SORGU_ADLARI), None)
    if hedef is None:
        # Kalip 'https://site/search?q=' gibi bos bitiyorsa kelime dogrudan eklenir.
        if parcalar.query and parcalar.query.rstrip("=").split("=")[-1] == "":
            return url + urllib.parse.quote(kelime)
        return None
    yeni = [(ad, kelime if ad == hedef else deger) for ad, deger in alanlar]
    return urllib.parse.urlunsplit((
        parcalar.scheme, parcalar.netloc, parcalar.path,
        urllib.parse.urlencode(yeni), "",
    ))


def arama_url(satir: dict[str, str], kelime: str, opensearch_govde: bytes | None = None) -> str | None:
    """Katalog satirindan bu kelime icin sorulacak adresi uretir."""
    yol = satir["en_iyi_yol"]
    if yol == "opensearch" and opensearch_govde:
        sablon = opensearch_sablonu(opensearch_govde)
        return sablonu_doldur(sablon, kelime) if sablon else None
    if yol == "site_search":
        kalip = satir["site_arama"]
        if "{kelime}" in kalip:
            return kalip.replace("{kelime}", urllib.parse.quote(kelime))
        return sorgu_parametresini_degistir(kalip, kelime)
    if yol == "api":
        return sorgu_parametresini_degistir(satir["api_ucu"], kelime)
    return None


def yerel_ara(kelime: str, dizin: Path, limit: int = 200) -> list[dict[str, str]]:
    """Sitemap'ten toplanan URL'lerde arar; hicbir ag istegi harcamaz."""
    # Slug'lar ifadeyi bitisik ('fitnessapp'), tireli ('fitness-app') ya da
    # dagitik ('/apps/fitness/tracker') yazabiliyor. Ucu de aranir; cok kelimeli
    # sorguda kelimelerin HEPSI gecmek zorundadir, biri yeterli degildir.
    kelimeler = [k for k in kelime.casefold().split() if k]
    tireli = "-".join(kelimeler)
    bitisik = "".join(kelimeler)
    vurus: list[dict[str, str]] = []
    try:
        with dizin.open(encoding="utf-8") as handle:
            for satir in handle:
                parcalar = satir.rstrip("\n").split("\t")
                if len(parcalar) != 3:
                    continue
                source_id, ad, url = parcalar
                kucuk = url.casefold()
                sade = kucuk.replace("-", "").replace("_", "").replace("/", "")
                if (
                    tireli in kucuk
                    or bitisik in sade
                    or all(k in kucuk for k in kelimeler)
                ):
                    vurus.append({"source_id": source_id, "ad": ad, "url": url})
                    if len(vurus) >= limit:
                        break
    except OSError:
        return []
    return vurus


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kelime", help="Aranacak anahtar kelime")
    parser.add_argument("--catalog", type=Path, default=HERE / "ARAMA-YUZEYLERI.csv")
    parser.add_argument("--url-index", type=Path, default=RESULTS_DIR / "yerel-url-dizini.tsv")
    parser.add_argument("--limit", type=int, default=25, help="Canli sorgulanacak kaynak sayisi")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--live", action="store_true",
                        help="Canli sorgu atar; verilmezse yalnizca yerel dizinde aranir")
    args = parser.parse_args()

    katalog = list(csv.DictReader(args.catalog.open(encoding="utf-8")))
    yerel = yerel_ara(args.kelime, args.url_index)
    kaynak_sayisi = len({v["source_id"] for v in yerel})
    print(json.dumps({
        "kelime": args.kelime, "yerel_vurus": len(yerel), "yerel_kaynak": kaynak_sayisi,
    }, ensure_ascii=False), flush=True)

    hedefler: list[dict[str, Any]] = []
    atlanan = 0
    for satir in katalog:
        if satir["en_iyi_yol"] not in CANLI_YOLLAR or not satir["adres"]:
            continue
        # OpenSearch sablonu ancak belge indirilerek okunur; bu ayri bir istektir
        # ve --live olmadan yapilmaz. Bu kosuda site_search/api ile ilerlenir.
        url = arama_url(satir, args.kelime)
        if url is None:
            atlanan += 1
            continue
        parcalar = urllib.parse.urlsplit(url)
        hedefler.append({
            "source_id": satir["source_id"], "display_name": satir["ad"],
            "official_origin": f"{parcalar.scheme}://{parcalar.hostname}",
            "entry_path": urllib.parse.urlunsplit(("", "", parcalar.path, parcalar.query, "")),
            "resolution_status": "resolved_official_origin", "api_endpoints": [],
        })
        if len(hedefler) >= args.limit:
            break

    print(json.dumps({
        "canli_hedef": len(hedefler), "sablon_cozulemedi": atlanan,
        "canli_kosu": bool(args.live),
    }, ensure_ascii=False), flush=True)

    slug = re.sub(r"[^a-z0-9]+", "-", args.kelime.casefold()).strip("-") or "sorgu"
    cikti = args.output or RESULTS_DIR / f"keyword-search-{slug}.json"
    if args.live and hedefler:
        alt_manifest = RESULTS_DIR / f"manifest-keyword-{slug}.json"
        atomic_write_json(alt_manifest, {
            "schema_version": "1.0.0", "manifest_id": f"keyword-{slug}",
            "policy": {}, "source_list": [], "expected_unique_sources": len(hedefler),
            "resolved_count": len(hedefler), "unresolved_count": 0, "sources": hedefler,
        })
        rapor = run_lab(load_manifest(alt_manifest), live=True, workers=args.workers,
                        global_budget=1500, output=cikti)
        basarili = sum(
            1 for site in rapor["site_results"]
            for yontem in site["methods"]
            if yontem.get("method_category") == "acquisition_surface"
            and (yontem.get("fetched_artifact_count") or 0) > 0
        )
        print(json.dumps({"cikti": str(cikti), "sonuc_alinan_kaynak": basarili},
                         ensure_ascii=False))
    else:
        atomic_write_json(cikti, {
            "kelime": args.kelime, "yerel_sonuclar": yerel,
            "canli_hedefler": [h["display_name"] for h in hedefler],
        })
        print(json.dumps({"cikti": str(cikti)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
