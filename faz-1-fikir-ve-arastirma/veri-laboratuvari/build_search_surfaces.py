"""Her kaynaga anahtar kelimeyle nasil sorulacagini cikarir.

Gorev 3 ("anahtar kelimeler ile arama yapabilmenin yollarini bulmak") bir arama
motoru secmek degildir: olcum, genel web aramasinin bize kapali oldugunu gosterdi
(DuckDuckGo 12 sorguda kesiyor, Mojeek ve Marginalia robots'ta /search'u
yasakliyor, Brave API ucretli). Bunun yerine her kaynagin KENDI arama yuzeyi
kataloglanir; boylece sorgu, kaynaga kendi diliyle sorulur.

Dort yuzey aranir, hepsi elimizdeki artefaktlardan turer -- ag istegi harcanmaz:

* ``opensearch``   — site arama ucunu makine okunur bicimde ilan ediyor (en guclu).
* ``site_search``  — HTML'de arama formu ya da /search?q= kalibi var.
* ``api``          — manifestte anahtarsiz resmi API ucu tanimli.
* ``local_index``  — sitemap/RSS'ten toplanan URL'ler; slug'lar anahtar kelime tasir.
* ``fulltext``     — sayfanin tam metni diskte; govdede arama yapilabilir.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import urllib.parse
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"

OPENSEARCH = re.compile(
    rb'(?is)<link[^>]+type=["\']application/opensearchdescription\+xml["\'][^>]*>'
)
HREF = re.compile(rb'(?is)href=["\']([^"\']+)["\']')
# Arama formu: action'i /search'e giden ya da bilinen sorgu adini tasiyan form.
FORM = re.compile(rb'(?is)<form[^>]*>')
FORM_ACTION = re.compile(rb'(?is)action=["\']([^"\']*search[^"\']*)["\']')
FORM_ROLE = re.compile(rb'(?is)role=["\']search["\']')
QUERY_INPUT = re.compile(rb'(?is)<input[^>]+name=["\'](q|query|s|search|keyword|term|k)["\']')
SEARCH_URL = re.compile(rb'(?is)["\']([^"\']*/search[^"\']*\?[^"\']*\b(q|query|s|keyword|term)=)')


def _kosu_govdesi(kosu: Path, sha: str, onbellek: dict[Path, dict]) -> bytes:
    if kosu not in onbellek:
        try:
            onbellek[kosu] = json.loads(kosu.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            onbellek[kosu] = {}
    for islem in onbellek[kosu].get("transactions", []):
        if str(islem.get("sha256")) == sha and islem.get("inline_body_base64"):
            try:
                return base64.b64decode(islem["inline_body_base64"])
            except (ValueError, TypeError):
                return b""
    return b""


def govde(satir: dict[str, str], onbellek: dict[Path, dict]) -> bytes:
    if satir["saklama"] == "dosya":
        yol = Path(satir["dosya"])
        tam = yol if yol.is_absolute() else HERE / yol
        try:
            return tam.read_bytes()
        except OSError:
            return b""
    return _kosu_govdesi(RESULTS / satir["kosu"], satir["sha256"], onbellek)


def opensearch_adresi(html: bytes, taban: str) -> str | None:
    eslesme = OPENSEARCH.search(html)
    if eslesme is None:
        return None
    href = HREF.search(eslesme.group(0))
    return urllib.parse.urljoin(taban, href.group(1).decode("utf-8", "replace")) if href else None


def _ayni_site(url: str, adres: str) -> bool:
    """Bulunan arama ucu KAYNAGIN KENDI sitesinde mi?

    Sayfalar baska sitelere de arama baglantisi tasiyor; 'BigSpy' sayfasindan
    capterra.com'un arama ucu cikmisti. Kaynagin adresi disindaki bir uc, o
    kaynaga sorgu sormaz -- baska bir siteye sorar ve katalogda yanlis kayit olur.
    """
    kaynak = urllib.parse.urlsplit(adres).hostname or ""
    hedef = urllib.parse.urlsplit(url).hostname or ""
    if not kaynak or not hedef:
        return False
    sade = lambda h: h[4:] if h.startswith("www.") else h
    kaynak, hedef = sade(kaynak.casefold()), sade(hedef.casefold())
    return hedef == kaynak or hedef.endswith("." + kaynak) or kaynak.endswith("." + hedef)


def site_arama_kalibi(html: bytes, taban: str, adres: str) -> str | None:
    """Sayfada, KAYNAGIN KENDI sitesine ait bir arama ucu gorunuyor mu?

    Once dogrudan bir arama URL'i aranir (en kesin kanit), sonra arama formu:
    action'i /search'e giden ya da role="search" tasiyip sorgu alani olan form.
    Her aday ayni-site sartindan gecer.
    """
    for dogrudan in SEARCH_URL.finditer(html):
        aday = urllib.parse.urljoin(taban, dogrudan.group(1).decode("utf-8", "replace"))
        if _ayni_site(aday, adres):
            return aday
    for form in re.finditer(rb"(?is)<form[^>]*>.{0,1200}?</form>", html):
        blok = form.group(0)
        aksiyon = FORM_ACTION.search(blok)
        alan_eslesme = QUERY_INPUT.search(blok)
        if not aksiyon or not alan_eslesme:
            continue
        hedef = urllib.parse.urljoin(taban, aksiyon.group(1).decode("utf-8", "replace"))
        if not _ayni_site(hedef, adres):
            continue
        return f"{hedef}?{alan_eslesme.group(1).decode()}=" + "{kelime}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=HERE / "ARTEFAKT-DIZINI.csv")
    parser.add_argument("--ledger", type=Path, default=HERE / "KAYNAK-DEFTERI.csv")
    parser.add_argument("--manifest", type=Path, default=HERE / "source_manifest.json")
    parser.add_argument("--out", type=Path, default=HERE / "ARAMA-YUZEYLERI.csv")
    parser.add_argument("--urls-out", type=Path, default=HERE / "results" / "yerel-url-dizini.tsv")
    args = parser.parse_args()

    defter = {r["source_id"]: r for r in csv.DictReader(args.ledger.open(encoding="utf-8"))}
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    api_ucu = {
        s["source_id"]: (s.get("api_endpoints") or [{}])[0].get("url", "")
        for s in manifest["sources"] if s.get("api_endpoints")
    }

    satirlar = defaultdict(list)
    for satir in csv.DictReader(args.index.open(encoding="utf-8")):
        satirlar[satir["source_id"]].append(satir)

    onbellek: dict[Path, dict] = {}
    url_dizini: list[tuple[str, str, str]] = []
    cikti: list[dict[str, Any]] = []
    for source_id, kayitlar in satirlar.items():
        bilgi = defter.get(source_id, {})
        ad, adres = kayitlar[0]["ad"], kayitlar[0]["adres"]
        opensearch = arama_kalibi = None
        yerel_url = tam_metin = 0
        for kayit in kayitlar:
            icerik = govde(kayit, onbellek)
            if not icerik:
                continue
            if kayit["yontem"] in ("root_html", "entry_url", "common_crawl_warc"):
                tam_metin += len(icerik)
                taban = kayit["cekilen_url"] or adres
                aday = opensearch_adresi(icerik, taban)
                if aday and _ayni_site(aday, adres):
                    opensearch = opensearch or aday
                arama_kalibi = arama_kalibi or site_arama_kalibi(icerik, taban, adres)
            elif kayit["yontem"] in ("sitemap_xml", "rss_feed"):
                bulunan = re.findall(rb"<loc>(.*?)</loc>", icerik) or re.findall(
                    rb"<link>(.*?)</link>", icerik
                )
                yerel_url += len(bulunan)
                url_dizini.extend(
                    (source_id, ad, u.decode("utf-8", "replace").strip()) for u in bulunan
                )
        # En iyi yol, kanit gucune gore secilir: makine okunur ilan > API >
        # sayfadan cikarilan kalip > yerel dizin > yalnizca tam metin.
        en_iyi = (
            "opensearch" if opensearch else
            "api" if source_id in api_ucu else
            "site_search" if arama_kalibi else
            "local_index" if yerel_url else
            "fulltext" if tam_metin else "yok"
        )
        cikti.append({
            "source_id": source_id, "ad": ad, "adres": adres,
            "durum": bilgi.get("durum", ""), "en_iyi_yol": en_iyi,
            "opensearch": opensearch or "", "api_ucu": api_ucu.get(source_id, ""),
            "site_arama": arama_kalibi or "", "yerel_url": yerel_url,
            "tam_metin_bayt": tam_metin,
        })

    cikti.sort(key=lambda r: (r["en_iyi_yol"], r["ad"].casefold()))
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        yazici = csv.DictWriter(handle, fieldnames=list(cikti[0]))
        yazici.writeheader()
        yazici.writerows(cikti)

    args.urls_out.parent.mkdir(parents=True, exist_ok=True)
    with args.urls_out.open("w", encoding="utf-8") as handle:
        for source_id, ad, url in url_dizini:
            handle.write(f"{source_id}\t{ad}\t{url}\n")

    from collections import Counter
    print(json.dumps({
        "katalog": str(args.out), "kaynak": len(cikti),
        "url_dizini": str(args.urls_out), "url": len(url_dizini),
        "yol_dagilimi": Counter(r["en_iyi_yol"] for r in cikti).most_common(),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
