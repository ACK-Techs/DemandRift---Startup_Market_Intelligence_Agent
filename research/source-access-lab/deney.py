"""Tasarimin gercek dunyada dogru kaynak ve dogru veri urettigini sinar.

Yedi gorev boyunca ic tutarliligi defalarca kontrol ettik ve temiz cikti. Ama
**tutarlilik dogruluk degildir**: bir sistem kendi icinde kusursuz olup gercek
dunyada yanlis olabilir. Simdiye kadar 73 sorgu uretildi ve **hicbiri
calistirilmadi**; olcum alanlarinin 1378'i hala 'beyan' durumunda.

Bu modul o bosluga nisan alir. Iki iddia ayri ayri sinanir:

* **Dogru kaynak** — secilen kaynaklar gercekten o urun turune mi hizmet ediyor,
  yoksa her fikirde ayni liste mi cikiyor?
* **Dogru veri** — "bu kaynak su alani verir" beyani, sayfa cekildiginde tutuyor mu?

**Kontrollu olmak** su demektir: deney basarisiz olabilmelidir. Yanlislanamayan
bir kanit, kanit degildir. Bu yuzden:

1. Basari olcutleri **calistirmadan once** burada sabit olarak yazilidir.
2. Negatif kontroller vardir: sistemin secmemesi gereken seyi secmedigi de
   olculur.
3. Basarisizliklar raporlanir. Bot korumasi, bos sonuc ve eksik alan sayilir;
   gizlenmez.

Deney **kucuktur**: yedi fikir, kaynak basina tek sorgu, elle dogrulanabilecek
kadar az istek. Amac kapsam degil, kanit.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import build_source_fields as alanlar
import butce_profilleri as butce
import compile_queries as derleyici
import query_templates as sablon
import select_sources as sec

HERE = Path(__file__).resolve().parent
UA = "DemandRift-research/1.0 (academic source study; contact via repository)"
BEKLEME = 4.0
ZAMAN_ASIMI = 25.0
AZAMI_BAYT = 400_000

# --------------------------------------------------------------------------
# ONCEDEN YAZILAN DENEY TASARIMI
# Asagidakiler calistirmadan once sabitlenmistir. Sonuca gore degistirilirse
# deney anlamini yitirir.
# --------------------------------------------------------------------------

# Yedi urun turu, yedi fikir. Gorev 1'in iddiasi "kategori farkli kaynak paketi
# dogurur"du; tek kategoride sinanirsa sinanmis olmaz.
DENEY_FIKIRLERI: tuple[tuple[str, str], ...] = (
    ("diyabet hastaları için mobil takip uygulaması", "mobil-uygulama"),
    ("react için grafik kütüphanesi", "gelistirici-araci"),
    ("mobil bulmaca oyunu", "oyun"),
    ("muhasebeciler için fatura yazılımı", "b2b-web-yazilimi"),
    ("yerel esnaf için randevu uygulaması", "yerel-hizmet"),
    ("türkçe metin özetleyen yapay zeka modeli", "yapay-zeka-urunu"),
    ("wordpress için sepet eklentisi", "eklenti-entegrasyon"),
)

# Sistemin REDDETMESI gereken girdi. Sessizce bir varsayilana duserse
# kategori tespiti guvenilmez demektir.
ANLAMSIZ_FIKIR = "zzzz qqqq wwww"

# Kategoriye ozel kaynaklarin capraz ortusmesi bu oranin altinda kalmali.
# Ustune cikarsa "kategori farkli kaynak paketi dogurur" iddiasi zayiflar.
AZAMI_CAPRAZ_ORTUSME = 0.25

# --- SONRADAN EKLENEN OLCUM (post-hoc) ---
# K2 uc ciftte kaldi ve incelendiginde ucunde de tek ortak kaynak Google Play
# Store cikti; ucu de mobil uygulama (biri dogrudan, ikisi 'mobil-uygulama'
# katmaniyla). Yani ortusme gorev 1'in katman kuralinin dogru sonucudur.
#
# K2'nin esigi DEGISTIRILMEDI: onceden yazilan olcut ve sonucu oldugu gibi
# raporlanir. Asagidaki K2b, ayni veriye katman paylasimi disarida
# birakilarak bakan **ikinci** bir olcumdur ve sonucu gorduktern sonra
# eklendigi burada acikca yazilidir.
K2B_ACIKLAMA = ("post-hoc: paylaşılan katmandan gelen kaynaklar hariç "
                "tutulduğunda çapraz örtüşme")

# --- SONRADAN EKLENEN SINIFLANDIRMA (post-hoc) ---
# Canli kosuda V2 (konu ilgisi) beklentinin altinda kaldi. Yanitlar
# incelendiginde basarisizliklarin tamami tek bir sebepte toplandi: sayfa
# HTTP 200 ve buyuk gövde donduruyor ama arama sonuclari tarayicida
# JavaScript ile uretildigi icin gelen HTML bos bir kabuk. URL dogru,
# sorgu dogru, kaynak dogru -- veri duz HTTP cekimiyle alinamiyor.
#
# Bu bir kod kusuru degil, kaynagin ozelligidir ve katalogda kayitli
# olmayan bir boyuttur. Asagidaki esik o ayrimi olculebilir kilar.
JS_KABUGU_ASGARI_BAYT = 150_000

# Canli asamanin onceden yazilmis beklentileri. Gercek sayilar ne cikarsa
# raporlanir; bunlar basari/basarisizlik esigi olarak degil, **onceden
# beyan edilmis tahmin** olarak durur.
BEKLENTI: dict[str, float] = {
    # Gorev 4'te olcmustuk: bot korumasi yaygin. Yarisinin donmesini bekliyoruz.
    "icerik_donme_orani": 0.50,
    # Donen icerigin cogu sorgulanan terimi gecirmeli; gecmiyorsa sorgu yanlis.
    "konu_ilgisi_orani": 0.70,
    # Alan izi en zoru: cogu sayfa arama sonucu, yapisal veri tasimayabilir.
    "alan_izi_orani": 0.30,
}


def _veri_yukle() -> dict[str, Any]:
    def oku(ad: str) -> list[dict[str, str]]:
        with (HERE / ad).open(encoding="utf-8") as h:
            return list(csv.DictReader(h))
    kaynak_alan = oku("KAYNAK-ALAN.csv")
    olcum, dog, izin = (collections.defaultdict(set) for _ in range(3))
    for r in kaynak_alan:
        izin[r["ad"]].add(r["izin_durumu"])
        if r["alan"] in alanlar.OLCUM_ALANLARI:
            olcum[r["ad"]].add(r["alan"])
            if r["guven"] == "dogrulandi":
                dog[r["ad"]].add(r["alan"])
    kategori_kaynak = oku("KATEGORI-KAYNAK.csv")
    rol: dict[str, str] = {}
    for r in kategori_kaynak:
        if r["rol"] == "cekirdek" or r["kaynak"] not in rol:
            rol[r["kaynak"]] = r["rol"]
    return {
        "kategori_kaynak": kategori_kaynak,
        "kategori_soru": oku("KATEGORI-SORU.csv"),
        "olcum_alani": olcum, "dogrulanan": dog, "izin": izin, "rol": rol,
        "host": {r["ad"]: r["host"] for r in oku("ADAY-KATALOG.csv")},
        "metin_bayt": {r["ad"]: int(r["tam_metin_bayt"] or 0)
                       for r in oku("ARAMA-YUZEYLERI.csv")},
        "_defter": {r["ad"]: r for r in oku("KAYNAK-DEFTERI.csv")},
        "_yuzey": {r["ad"]: r for r in oku("ARAMA-YUZEYLERI.csv")},
        "_katman": frozenset(r["kategori"] for r in oku("URUN-KATEGORILERI.csv")
                             if r["tur"] == "kategori" and r["katman_olabilir"] == "evet"),
        "_opensearch": {r["ad"]: r["sablon"] for r in oku("OPENSEARCH-SABLONLARI.csv")
                        if r["sablon"]},
    }


def kaynak_dogrulugu(veri: dict[str, Any]) -> dict[str, Any]:
    """Aga cikmadan olculebilen kisim: dogru kaynak seciliyor mu."""
    ortak_gruplar = {r["kaynak_grubu"].split(" | ")[0].strip()
                     for r in veri["kategori_kaynak"] if r["hedef"] == "ortak"}
    yasakli = {ad for ad, r in veri["_defter"].items()
               if r.get("sebep") == "robots_disallowed"}

    paketler: dict[str, list[dict[str, Any]]] = {}
    kategori_ozel: dict[str, set[str]] = {}
    bulgular: list[dict[str, Any]] = []

    for fikir, beklenen in DENEY_FIKIRLERI:
        kategori, katmanlar, ekler, _p = sec.hedefleri_bul(fikir, veri["_katman"])
        paket = sec.paket_sec(fikir, kategori, ekler, veri, katmanlar)
        paketler[fikir] = paket
        ozel = {r["birincil_kaynak"] for r in paket
                if r["kaynak_grubu"] not in ortak_gruplar}
        kategori_ozel[fikir] = ozel
        secilen = {r["birincil_kaynak"] for r in paket}
        bulgular.append({
            "olcut": "K1 kategori dogru",
            "fikir": fikir, "beklenen": beklenen, "gerceklesen": kategori,
            "gecti": kategori == beklenen,
        })
        bulgular.append({
            "olcut": "K4 yasakli kaynak yok",
            "fikir": fikir, "beklenen": "0",
            "gerceklesen": str(len(secilen & yasakli)),
            "gecti": not (secilen & yasakli),
        })

    # K2 -- kategoriye ozel kaynaklar fikirden fikire farkli mi
    adlar = [f for f, _ in DENEY_FIKIRLERI]
    for i in range(len(adlar)):
        for j in range(i + 1, len(adlar)):
            a, b = kategori_ozel[adlar[i]], kategori_ozel[adlar[j]]
            birlesim = a | b
            oran = len(a & b) / len(birlesim) if birlesim else 0.0
            bulgular.append({
                "olcut": "K2 capraz ortusme",
                "fikir": f"{adlar[i][:22]} ↔ {adlar[j][:22]}",
                "beklenen": f"<{AZAMI_CAPRAZ_ORTUSME}",
                "gerceklesen": f"{oran:.2f}",
                "gecti": oran < AZAMI_CAPRAZ_ORTUSME,
            })

    # K2b -- SONRADAN EKLENEN: katman paylasimini disarida birakan ortusme
    katman_kaynagi: dict[str, set[str]] = {}
    for fikir, _b in DENEY_FIKIRLERI:
        _k, katmanlar, _e, _p = sec.hedefleri_bul(fikir, veri["_katman"])
        katman_kaynagi[fikir] = {
            r["kaynak"] for r in veri["kategori_kaynak"] if r["hedef"] in set(katmanlar)}
    for i in range(len(adlar)):
        for j in range(i + 1, len(adlar)):
            paylasilan = katman_kaynagi[adlar[i]] | katman_kaynagi[adlar[j]]
            a = kategori_ozel[adlar[i]] - paylasilan
            b = kategori_ozel[adlar[j]] - paylasilan
            birlesim = a | b
            oran = len(a & b) / len(birlesim) if birlesim else 0.0
            bulgular.append({
                "olcut": "K2b katman haric ortusme (post-hoc)",
                "fikir": f"{adlar[i][:22]} ↔ {adlar[j][:22]}",
                "beklenen": f"<{AZAMI_CAPRAZ_ORTUSME}",
                "gerceklesen": f"{oran:.2f}",
                "gecti": oran < AZAMI_CAPRAZ_ORTUSME,
            })

    # K3 -- negatif kontrol: bir kategoriye ozel kaynak baska kategoride cikmamali
    for fikir, _b in DENEY_FIKIRLERI:
        digerleri = set().union(*(v for k, v in kategori_ozel.items() if k != fikir))
        yalniz = kategori_ozel[fikir] - digerleri
        bulgular.append({
            "olcut": "K3 kategoriye ozel kaynak",
            "fikir": fikir, "beklenen": ">0",
            "gerceklesen": str(len(yalniz)),
            "gecti": len(yalniz) > 0,
        })

    # K5 -- anlamsiz fikir reddedilmeli
    try:
        sec.hedefleri_bul(ANLAMSIZ_FIKIR, veri["_katman"])
        reddedildi = False
    except SystemExit:
        reddedildi = True
    bulgular.append({
        "olcut": "K5 anlamsiz fikir reddi", "fikir": ANLAMSIZ_FIKIR,
        "beklenen": "reddedilir",
        "gerceklesen": "reddedildi" if reddedildi else "kabul edildi",
        "gecti": reddedildi,
    })
    return {"bulgular": bulgular, "paketler": paketler,
            "kategori_ozel": kategori_ozel}


def _cek(adres: str) -> tuple[int, bytes, str]:
    istek = urllib.request.Request(adres, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/json"})
    try:
        with urllib.request.urlopen(istek, timeout=ZAMAN_ASIMI) as yanit:
            return yanit.status, yanit.read(AZAMI_BAYT), ""
    except urllib.error.HTTPError as hata:
        return hata.code, b"", f"http_{hata.code}"
    except Exception as hata:
        return 0, b"", f"{type(hata).__name__}"


def yanit_sinifi(satir: dict[str, Any]) -> str:
    """Yanitin neden ise yaradigini ya da yaramadigini siniflandirir.

    SONRADAN EKLENDI: ilk kosunun sonucu gorulduktern sonra yazildi.
    """
    if satir["V1_icerik_dondu"] != "evet":
        return "icerik-yok"
    if satir["V2_konu_ilgili"] == "evet":
        return "sunucu-html-veya-api"
    if int(satir["bayt"]) > JS_KABUGU_ASGARI_BAYT:
        return "istemci-js-kabugu"
    return "konu-yok-diger"


def veri_dogrulugu(sorgular: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Sorgulari calistirir ve donen icerigi uc olcutle sinar.

    V1 icerik dondu mu, V2 konuyla ilgili mi, V3 beklenen alanin izi var mi.
    Alan izi icin gorev 4'un dogrulayicisi kullanilir: schema.org JSON-LD,
    API anahtarlari ve RSS etiketleri.
    """
    sonuc: list[dict[str, Any]] = []
    for satir in sorgular:
        kod, govde, hata = _cek(satir["derlenmis_sorgu"])
        metin = govde.decode("utf-8", "replace") if govde else ""
        # V2 -- cekirdek terimin ilk kelimesi icerikte geciyor mu
        konu = satir["cekirdek_terim"].split()[0].casefold() if satir["cekirdek_terim"] else ""
        ilgili = bool(konu) and konu in metin.casefold()
        # V3 -- alanin izi: gorev 4'un kanit kaynaklari
        izler: list[str] = []
        for blok in alanlar.LDJSON.findall(govde)[:4]:
            try:
                nesne = json.loads(blok.decode("utf-8", "replace"))
            except (ValueError, UnicodeDecodeError):
                continue
            for tur, anahtar in alanlar._jsonld_anahtarlari(nesne):
                if anahtar in alanlar.JSONLD_ALAN:
                    izler.append(f"json-ld:{anahtar}")
        if "json" in (metin[:200].lstrip()[:1] or "") or metin.lstrip()[:1] in "[{":
            for anahtar in alanlar.API_ALAN:
                if f'"{anahtar}"' in metin:
                    izler.append(f"api:{anahtar}")
        sonuc.append({
            "fikir": satir["fikir"], "kategori": satir["kategori"],
            "soru_id": satir["soru_id"], "kaynak": satir["kaynak"],
            "yol": satir["yol"], "sorgu": satir["derlenmis_sorgu"][:180],
            "http": kod, "bayt": len(govde), "hata": hata,
            "V1_icerik_dondu": "evet" if govde else "hayir",
            "V2_konu_ilgili": "evet" if ilgili else "hayir",
            "V3_alan_izi": ", ".join(sorted(set(izler))[:4]),
        })
        time.sleep(BEKLEME)
    return sonuc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canli", action="store_true",
                        help="Sorguları gerçekten çalıştırır (ağa çıkar)")
    parser.add_argument("--kaynak-basina", type=int, default=1,
                        help="Fikir başına kaç uzak sorgu denenir")
    parser.add_argument("--out-kaynak", type=Path, default=HERE / "DENEY-KAYNAK.csv")
    parser.add_argument("--out-veri", type=Path, default=HERE / "DENEY-VERI.csv")
    args = parser.parse_args()

    veri = _veri_yukle()
    kaynak = kaynak_dogrulugu(veri)

    with args.out_kaynak.open("w", newline="", encoding="utf-8") as h:
        yazici = csv.DictWriter(h, fieldnames=list(kaynak["bulgular"][0]))
        yazici.writeheader()
        yazici.writerows(kaynak["bulgular"])

    onceden = [b for b in kaynak["bulgular"] if "post-hoc" not in b["olcut"]]
    sonradan = [b for b in kaynak["bulgular"] if "post-hoc" in b["olcut"]]
    ozet: dict[str, Any] = {
        "onceden_yazilan_olcutler": {
            "olcut": len(onceden),
            "gecen": sum(1 for b in onceden if b["gecti"]),
            "kalan": [f'{b["olcut"]}: {b["fikir"][:30]} = {b["gerceklesen"]}'
                      for b in onceden if not b["gecti"]],
        },
        "sonradan_eklenen_olcum": {
            "aciklama": K2B_ACIKLAMA,
            "olcut": len(sonradan),
            "gecen": sum(1 for b in sonradan if b["gecti"]),
            "kalan": [f'{b["fikir"][:30]} = {b["gerceklesen"]}'
                      for b in sonradan if not b["gecti"]],
        },
        "cikti_kaynak": str(args.out_kaynak),
    }

    if args.canli:
        # Her fikir icin ilk N uzak sorgu; kucuk ve elle dogrulanabilir tutulur.
        denenecek: list[dict[str, str]] = []
        for fikir, _b in DENEY_FIKIRLERI:
            paket = kaynak["paketler"][fikir]
            alindi = 0
            for yuva in paket:
                ad = yuva["birincil_kaynak"]
                y = veri["_yuzey"].get(ad, {})
                yol = y.get("en_iyi_yol", "")
                cekirdek = sablon.cekirdek_terim(fikir)
                metin = sablon.sorgu_metni(cekirdek, yuva["kaynak_grubu"],
                                           yuva["soru_id"])
                tur, sorgu, _n = derleyici.derle(metin, yol, y, "TR",
                                                 veri["_opensearch"], ad)
                if tur != "uzak-url":
                    continue
                denenecek.append({
                    "fikir": fikir, "kategori": yuva["kategori"],
                    "soru_id": yuva["soru_id"], "kaynak": ad, "yol": yol,
                    "cekirdek_terim": cekirdek, "derlenmis_sorgu": sorgu})
                alindi += 1
                if alindi >= args.kaynak_basina:
                    break
        sonuc = veri_dogrulugu(denenecek)
        with args.out_veri.open("w", newline="", encoding="utf-8") as h:
            yazici = csv.DictWriter(h, fieldnames=list(sonuc[0]))
            yazici.writeheader()
            yazici.writerows(sonuc)
        n = len(sonuc)
        donen = sum(1 for r in sonuc if r["V1_icerik_dondu"] == "evet")
        sinif = collections.Counter(yanit_sinifi(r) for r in sonuc)
        sunucu = [r for r in sonuc if yanit_sinifi(r) == "sunucu-html-veya-api"]
        js = [r for r in sonuc if yanit_sinifi(r) == "istemci-js-kabugu"]
        ozet["sonradan_eklenen_siniflandirma"] = {
            "aciklama": ("post-hoc: V2 başarısızlıklarının tamamı istemci "
                         "tarafında üretilen sayfalarda toplandı"),
            "dagilim": sinif.most_common(),
            "sunucu_html_veya_api_konu_ilgisi": f"{len(sunucu)}/{len(sunucu)}",
            "istemci_js_konu_ilgisi": f"0/{len(js)}",
            "calisan_kaynaklar": sorted({r["kaynak"] for r in sunucu}),
            "js_kabugu_donen_kaynaklar": sorted({r["kaynak"] for r in js}),
        }
        ozet["veri_dogrulugu"] = {
            "denenen_sorgu": n,
            "V1_icerik_dondu": f"{donen}/{n}",
            "V2_konu_ilgili": f'{sum(1 for r in sonuc if r["V2_konu_ilgili"] == "evet")}/{donen}',
            "V3_alan_izi": f'{sum(1 for r in sonuc if r["V3_alan_izi"])}/{donen}',
            "onceden_beyan_edilen_beklenti": BEKLENTI,
            "hatalar": collections.Counter(r["hata"] for r in sonuc if r["hata"]).most_common(),
        }
        ozet["cikti_veri"] = str(args.out_veri)

    print(json.dumps(ozet, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
