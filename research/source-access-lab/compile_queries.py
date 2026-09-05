"""Gorev 5'in sectigi her kanit yuvasi icin calistirilabilir bir sorgu derler.

Gorev 5 **kime soracagimizi** soyler: "diyabet uygulamasi icin 'doygun mu'
sorusunu Google Play'e sor". Bu adim **ne diyecegimizi** soyler: Google Play'in
arama kutusuna hangi metin, hangi adrese, hangi parametrelerle gider.

Derleme dort girdiyi birlestirir (``query_templates`` modulu):

    [cekirdek terim] + [kaynak grubunun dili] + [niyet eki] + [pazar profili]

ve kaynagin **yoluna** gore ciktiyi degistirir. Yol iki turlu olur:

* **Uzak sorgu** (``site_search``, ``api``, ``opensearch``) — kaynagin kendi
  arama ucuna gidilir; cikti bir URL'dir.
* **Yerel arama** (``fulltext``, ``local_index``) — kaynagin sayfasi zaten
  indirilmistir; cikti indirilmis metinde aranacak terim listesidir. Bunlar
  cogunluktur (400 kaynak) ve URL uretmek yaniltici olurdu.

Yolu olmayan kaynak (``yok``) icin sorgu uretilmez; satir yine yazilir ve
nedeni belirtilir -- gorev 4'te konulan kural burada da gecerlidir.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any

import query_templates as sablon
import terim_sozlugu as sozluk

HERE = Path(__file__).resolve().parent

# API uclari sorgu terimini farkli parametrede bekler. 13 API kaynagi icin
# parametre adi elle yazilir; API dokumaninda tanimli, tahmin degil.
API_SORGU_PARAMETRESI: dict[str, str] = {
    "api.stackexchange.com": "q",
    "api.github.com": "q",
    "api.figshare.com": "search_for",
    "registry.npmjs.org": "text",
    "packagist.org": "q",
    "api.biorxiv.org": "",           # tarih/DOI ile calisir, serbest metin almaz
    "archive.org": "url",
    "hacker-news.firebaseio.com": "",  # serbest metin aramasi yok
    "lemmy.ml": "",                  # kesfedilen uc /api/v3/site: ornek
                                     # bilgisi doner, arama ucu degildir
}

# Bir kaynagin sorgu ucu baska bir alan adinda olabilir; Lemmy'nin defterdeki
# adresi join-lemmy.org (proje sitesi) iken API'si lemmy.ml (ornek sunucu)
# uzerindedir. Bu mesru bir durumdur ama gorunur kalmali: bir kaynagin
# sayfasindan baskasinin arama ucunu devralmak sessizce olmamali.
def _farkli_alan(kaynak_adresi: str, sorgu: str) -> str:
    def kok(adres: str) -> str:
        parcalar = [p for p in
                    (urllib.parse.urlsplit(adres).hostname or "").split(".") if p]
        return ".".join(parcalar[-2:]) if len(parcalar) >= 2 else ""
    hedef, kaynak = kok(sorgu), kok(kaynak_adresi)
    if hedef and kaynak and hedef != kaynak:
        return f"sorgu ucu farklı alanda: {hedef} (kaynak {kaynak})"
    return ""

# Pazar parametresi eklenebilen kaynak ucu kaliplari. Her uc dil/bolge
# parametresi kabul etmez; kabul etmeyene eklemek sorguyu bozar.
PAZAR_PARAMETRESI: dict[str, tuple[str, str]] = {
    "play.google.com": ("hl", "gl"),
    "apps.apple.com": ("l", "cc"),
    "www.google.com": ("hl", "gl"),
    "duckduckgo.com": ("kl", ""),
}


def _pazar_ekle(url: str, pazar: str) -> str:
    """Uc kabul ediyorsa dil/bolge parametresini ekler."""
    host = (urllib.parse.urlsplit(url).hostname or "").casefold()
    anahtarlar = PAZAR_PARAMETRESI.get(host)
    if not anahtarlar:
        return url
    profil = sablon.PAZAR[pazar]
    ek = {}
    dil_anahtari, bolge_anahtari = anahtarlar
    if dil_anahtari:
        ek[dil_anahtari] = profil["dil"]
    if bolge_anahtari:
        ek[bolge_anahtari] = profil["bolge"]
    ayrik = urllib.parse.urlsplit(url)
    mevcut = dict(urllib.parse.parse_qsl(ayrik.query))
    mevcut.update(ek)
    return urllib.parse.urlunsplit(
        ayrik._replace(query=urllib.parse.urlencode(mevcut)))


def derle(metin: str, yol: str, yuzey: dict[str, str], pazar: str,
          opensearch_sablonlari: dict[str, str] | None = None,
          kaynak: str = "") -> tuple[str, str, str]:
    """(sorgu_turu, sorgu, not) uretir.

    Yol uzak bir sorgu ucuysa URL, yerel aramaysa terim listesi doner.
    """
    kodlu = urllib.parse.quote_plus(metin)

    if yol == "site_search" and yuzey.get("site_arama"):
        return "uzak-url", _pazar_ekle(yuzey["site_arama"] + kodlu, pazar), ""

    if yol == "api" and yuzey.get("api_ucu"):
        uc = yuzey["api_ucu"]
        host = (urllib.parse.urlsplit(uc).hostname or "").casefold()
        parametre = API_SORGU_PARAMETRESI.get(host)
        if parametre is None:
            return "", "", f"API parametresi tanımsız: {host}"
        if parametre == "":
            return "", "", f"API serbest metin araması kabul etmiyor: {host}"
        ayirici = "&" if "?" in uc else "?"
        return "uzak-url", f"{uc}{ayirici}{parametre}={kodlu}", ""

    if yol == "opensearch" and yuzey.get("opensearch"):
        # Sablon kaynagin kendi tanim dosyasindan alinmistir; uydurulmaz.
        # Alinamadiysa URL uretmek yerine nedeni yazilir.
        sablon_metni = (opensearch_sablonlari or {}).get(kaynak, "")
        if not sablon_metni:
            return "", "", ("OpenSearch şablonu alınamadı; "
                            f"{yuzey['opensearch']} çekilemedi ya da şablon taşımıyor")
        url = sablon_metni.replace("{searchTerms}", kodlu)
        # Tanim dosyalari kullanilmayan istege bagli alanlar tasiyabilir
        # (ornegin {language} ya da {outputEncoding}); doldurulmayanlar atilir.
        url = re.sub(r"[?&][^?&=]+=\{[^}]+\}", "", url)
        url = re.sub(r"\{[^}]+\}", "", url)
        return "uzak-url", _pazar_ekle(url, pazar), ""

    if yol in ("fulltext", "local_index"):
        return "yerel-arama", metin, ""

    return "", "", f"sorgulanabilir yol yok ({yol or 'yok'})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secim", type=Path, default=HERE / "SECIM-ORNEKLERI.csv",
                        help="Görev 5'in ürettiği kanıt yuvaları")
    parser.add_argument("--surfaces", type=Path, default=HERE / "ARAMA-YUZEYLERI.csv")
    parser.add_argument("--opensearch", type=Path,
                        default=HERE / "OPENSEARCH-SABLONLARI.csv")
    parser.add_argument("--pazar", default="TR", choices=sorted(sablon.PAZAR))
    parser.add_argument("--terim", help="Çekirdek terimi elle verir")
    parser.add_argument("--cevrimici", action="store_true",
                        help="Önbellekte olmayan terim için ağa çıkar")
    parser.add_argument("--out", type=Path, default=HERE / "DERLENMIS-SORGULAR.csv")
    args = parser.parse_args()

    def oku(yol: Path) -> list[dict[str, str]]:
        with yol.open(encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    yuzeyler = {r["ad"]: r for r in oku(args.surfaces)}
    opensearch_sablonlari = {}
    if args.opensearch.exists():
        opensearch_sablonlari = {r["ad"]: r["sablon"]
                                 for r in oku(args.opensearch) if r["sablon"]}
    yuvalar = oku(args.secim)
    kategori_kaynak = oku(HERE / "KATEGORI-KAYNAK.csv")
    onbellek = sozluk.onbellek_yukle()
    onbellek_degisti = False

    satirlar: list[dict[str, Any]] = []
    for yuva in yuvalar:
        kaynak = yuva["birincil_kaynak"]
        y = yuzeyler.get(kaynak, {})
        yol = y.get("en_iyi_yol", "")
        ham_cekirdek = args.terim or sablon.cekirdek_terim(yuva["fikir"])
        cekirdek, ceviri = ham_cekirdek, {}
        # Ceviri yalniz Ingilizce pazar icin ve kullanici terim vermediyse.
        if sablon.PAZAR[args.pazar]["ceviri_gerekir"] == "evet" and not args.terim:
            dil = sozluk.kategori_dili(kategori_kaynak, yuva["kategori"],
                                       sablon.GRUP_DILI)
            ceviri = sozluk.terim_cevir(ham_cekirdek, yuva["kategori"], dil,
                                        onbellek, cevrimdisi=not args.cevrimici)
            if not ceviri.get("onbellekten"):
                anahtar = f'{sozluk.sadelestir(ham_cekirdek)}|{yuva["kategori"]}'
                onbellek[anahtar] = {k: v for k, v in ceviri.items()
                                     if k != "onbellekten"}
                onbellek_degisti = True
            cekirdek = ceviri["kullanilan"]
        metin = sablon.sorgu_metni(cekirdek, yuva["kaynak_grubu"], yuva["soru_id"])
        tur, sorgu, notu = derle(metin, yol, y, args.pazar,
                                 opensearch_sablonlari, kaynak)
        satirlar.append({
            "fikir": yuva["fikir"], "kategori": yuva["kategori"],
            "soru_id": yuva["soru_id"], "yuva": yuva["yuva"],
            "kaynak": kaynak, "kaynak_grubu": yuva["kaynak_grubu"],
            "pazar": args.pazar, "yol": yol or "yok",
            "cekirdek_terim": cekirdek,
            "orijinal_terim": ham_cekirdek,
            "ceviri_guveni": ceviri.get("guven", ""),
            "ceviri_katmani": ceviri.get("cozen_katman", ""),
            "ceviri_izi": ceviri.get("iz", ""),
            "ceviri_uyarisi": ceviri.get("uyari", ""),
            "grup_dili": " ".join(sablon.GRUP_DILI.get(yuva["kaynak_grubu"], ("",))[:1]),
            "niyet_eki": sablon.NIYET_EKI.get(yuva["soru_id"], ("",))[0],
            "sorgu_metni": metin,
            "sorgu_turu": tur,
            "derlenmis_sorgu": sorgu,
            "derlenemedi_nedeni": notu,
            "alan_notu": _farkli_alan(
                yuzeyler.get(kaynak, {}).get("adres", ""), sorgu) if sorgu else "",
            "yedekler": yuva["yedekler"],
        })

    if onbellek_degisti:
        sozluk.onbellek_yaz(onbellek)

    with args.out.open("w", newline="", encoding="utf-8") as handle:
        yazici = csv.DictWriter(handle, fieldnames=list(satirlar[0]))
        yazici.writeheader()
        yazici.writerows(satirlar)

    tur = collections.Counter(r["sorgu_turu"] or "derlenemedi" for r in satirlar)
    print(json.dumps({
        "cikti": str(args.out), "satir": len(satirlar), "pazar": args.pazar,
        "fikir": len({r["fikir"] for r in satirlar}),
        "sorgu_turu": tur.most_common(),
        "derlenemedi_nedeni": collections.Counter(
            r["derlenemedi_nedeni"].split(";")[0]
            for r in satirlar if r["derlenemedi_nedeni"]).most_common(),
        "farkli_sorgu_metni": len({r["sorgu_metni"] for r in satirlar}),
        "ceviri_guveni": collections.Counter(
            r["ceviri_guveni"] for r in satirlar if r["ceviri_guveni"]).most_common(),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
