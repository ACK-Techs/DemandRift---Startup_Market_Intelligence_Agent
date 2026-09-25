"""AS-03 — alternatifin orijinalden farkini, limitlerini ve yasini gosterir.

Gorev karti: "Mevcut yol calismiyorsa izinli alternatif yuzey, sorgu veya
kaynak dene. **Kaynak/alan/pazar/tarih ve limit farklarini goster;
metadata/arsiv sonucunu tam veya guncel veri gibi sunma.** Cozulemeyen
durumda kanitli engel ve sonraki secenekleri Batuhan'a ilet."

AS-01 alternatifleri buldu; bu modul **farki** olcer. Bir alternatifin
calismasi, kapananin yerini tuttugu anlamina gelmez: farkli alan kumesi,
farkli pazar, farkli tazelik ve farkli limit tasir.

Arsiv ozel olarak ele alinir. Bir arsiv kopyasinin **iki tarihi** vardir:

* ``warc_timestamp`` — icerigin gercekte cekildigi an (Common Crawl'in)
* bizim dizindeki ``tarih`` — o kopyayi bizim indirdigimiz an

Ikisi karistirilirsa 19 ay onceki bir sayfa bu ayin verisi gorunur. G2'de
tam olarak boyle: dizin 2026-09-03 diyor, icerik 2025-02-12 tarihli.
Bu modul arsiv yasini hesaplar ve tazelik uyarisini her satira yazar.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import glob
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
YEREL_ARSIV = HERE / ".." / ".." / "research" / "source-access-lab"
SURUM = "1.0.0"

# Arsiv icerigi kac gun sonra "eski" sayilir. Evrensel bir esik yok; kanit
# politikasi da "evrensel gun sayisi henuz secilmedi" diyor. Bu deger bir
# KARAR degil, bir ISARET esigidir: uzerindeki her satir uyari tasir.
TAZELIK_UYARI_GUNU = 180


def _oku(ad: str) -> list[dict[str, str]]:
    yol = HERE / ad
    if not yol.exists():
        return []
    with yol.open(encoding="utf-8") as tutamak:
        return list(csv.DictReader(tutamak))


def _yaz(ad: str, satirlar: list[dict[str, Any]]) -> None:
    if not satirlar:
        return
    with (HERE / ad).open("w", newline="", encoding="utf-8") as tutamak:
        yazici = csv.DictWriter(tutamak, fieldnames=list(satirlar[0]))
        yazici.writeheader()
        yazici.writerows(satirlar)


def arsiv_tarihleri() -> dict[str, dict[str, str]]:
    """source_id -> arsivin KENDI tarihi ve indeksi.

    ARTEFAKT-DIZINI.csv yalniz bizim cekme anımızı tutuyor; arsivin kendi
    zaman damgasi kosu JSON'unda duruyor ve oraya bakilmazsa 19 aylik bir
    sayfa bu ayin verisi gorunur.
    """
    sonuc: dict[str, dict[str, str]] = {}
    desenler = [str(YEREL_ARSIV / "results" / "*common-crawl*.json"),
                str(HERE / "results" / "*common-crawl*.json")]
    for desen in desenler:
        for yol in glob.glob(desen):
            try:
                veri = json.loads(Path(yol).read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            for site in veri.get("site_results", []):
                sid = site.get("source_id")
                for yontem in site.get("methods", []):
                    ayrinti = yontem.get("details") or {}
                    damga = ayrinti.get("warc_timestamp")
                    if not (sid and damga):
                        continue
                    try:
                        tarih = datetime.datetime.strptime(damga[:14], "%Y%m%d%H%M%S")
                    except ValueError:
                        continue
                    sonuc[sid] = {
                        "arsiv_tarihi": tarih.strftime("%Y-%m-%d"),
                        "arsiv_indeksi": ayrinti.get("archive_index", ""),
                        "arsiv_url": ayrinti.get("warc_url", ""),
                    }
    return sonuc


def tazelik_notu(arsiv_tarihi: str, bugun: str) -> tuple[int, str]:
    """(gun farki, uyari). Arsiv icerigi guncel veri gibi sunulmaz."""
    if not arsiv_tarihi:
        return 0, ""
    a = datetime.date.fromisoformat(arsiv_tarihi)
    b = datetime.date.fromisoformat(bugun)
    gun = (b - a).days
    if gun >= TAZELIK_UYARI_GUNU:
        return gun, (f"ARŞİV — içerik {arsiv_tarihi} tarihli, {gun} gün eski. "
                     "Güncel veri DEĞİLDİR; bulgu bu tarihle birlikte taşınmalıdır.")
    return gun, (f"arşiv — içerik {arsiv_tarihi} tarihli ({gun} gün). "
                 "Canlı veri değildir.")


# --------------------------------------------------------------------------
# Kapanan yol -> alternatif eslesmesi
# --------------------------------------------------------------------------
# AS-01'de olculen kapali kaynaklar ve onlara aranan alternatifler.
# "alternatif yok" da bir kayittir: aranmis ve bulunamamis oldugunu soyler.
ESLESMELER: list[dict[str, Any]] = [
    {"kapanan": "G2", "kapanan_id": "source-0134", "fikirler": "F02, F09",
     "kapanma_sebebi": "bot koruması (challenge)",
     "kapananin_verdigi": "kullanıcı yorumu, puan, fiyat karşılaştırması",
     "alternatifler": [("Filestage", ""), ("Ziflow", "")],
     "arsiv_var_mi": True},
    {"kapanan": "Capterra", "kapanan_id": "source-0135", "fikirler": "F02, F09, F10",
     "kapanma_sebebi": "bot koruması (challenge) — kayıt çalıştığını söylüyordu",
     "kapananin_verdigi": "kullanıcı yorumu, puan, kategori listesi",
     "alternatifler": [("Filestage", ""), ("Ziflow", "")],
     "arsiv_var_mi": False},
    {"kapanan": "Reddit", "kapanan_id": "source-0075",
     "fikirler": "F01, F02, F04, F06, F07, F08, F09",
     "kapanma_sebebi": "robots.txt Disallow: / — politika",
     "kapananin_verdigi": "kullanıcı problem ifadesi, şikâyet, tartışma",
     "alternatifler": [("Apple App Store — Booksy Biz", "source-0096")],
     "arsiv_var_mi": False},
    {"kapanan": "Trustpilot", "kapanan_id": "source-0148", "fikirler": "F07",
     "kapanma_sebebi": "robots.txt Disallow: / — politika",
     "kapananin_verdigi": "tüketici yorumu ve puanı",
     "alternatifler": [],
     "arsiv_var_mi": False},
    {"kapanan": "Google Play Store", "kapanan_id": "source-0097",
     "fikirler": "F01, F08, F10",
     "kapanma_sebebi": "HTTP 200 ama gövde boş (JS kabuğu)",
     "kapananin_verdigi": "uygulama puanı, yorum, indirme sayısı",
     "alternatifler": [("Apple App Store", "source-0096")],
     "arsiv_var_mi": False},
    {"kapanan": "Capterra Education", "kapanan_id": "source-0466", "fikirler": "F10",
     "kapanma_sebebi": "bot koruması (challenge)",
     "kapananin_verdigi": "eğitim yazılımı yorumu ve fiyatı",
     "alternatifler": [],
     "arsiv_var_mi": False},
]

# Cozulemeyen durumda Batuhan'a iletilecek sonraki secenekler.
SONRAKI_SECENEKLER: dict[str, list[str]] = {
    "politika": [
        "Kaynağın resmî API/araştırma programına başvuru (Reddit: "
        "r/reddit4researchers · Public Content Policy) — hesap ve şartname "
        "onayı gerekir, karar Çağlar'da",
        "Lisanslı veri sağlayıcı — kapsam dışı, ayrı değerlendirme",
    ],
    "bot-korumasi": [
        "Aynı nişte üçüncü taraf kaynak aramak (AS-01'de denendi; F02 için "
        "bulunamadı, F09 için App Store bulundu)",
        "Arşiv kopyası — varsa; yaşıyla birlikte ve 'arşiv' etiketiyle",
        "Kaynağın resmî API'si varsa registry'ye eklenmesi",
    ],
    "js-kabugu": [
        "Aynı ürünün başka mağaza/platformdaki sayfası (Google Play → "
        "Apple App Store; AS-01'de çalıştı)",
        "Kaynağın resmî API ucu",
    ],
}


def fark_matrisi(bugun: str) -> list[dict[str, Any]]:
    """Her kapanan yol icin alternatifin alan/pazar/tarih/limit farki."""
    alternatif = {r["aday"]: r for r in _oku("AS01-ALTERNATIF-KAYNAK.csv")}
    kontrol = {r["source_id"]: r for r in _oku("AS01-KAYNAK-KONTROL.csv")}
    arsiv = arsiv_tarihleri()
    ornekler = {r["source_id"]: r for r in _oku("AS01-ALAN-ORNEKLERI.csv")}

    satirlar: list[dict[str, Any]] = []
    for eslesme in ESLESMELER:
        sebep_anahtari = (
            "politika" if "robots" in eslesme["kapanma_sebebi"] else
            "js-kabugu" if "JS kabuğu" in eslesme["kapanma_sebebi"] else
            "bot-korumasi")
        arsiv_bilgisi = arsiv.get(eslesme["kapanan_id"], {})
        gun, tazelik = tazelik_notu(arsiv_bilgisi.get("arsiv_tarihi", ""), bugun)

        if not eslesme["alternatifler"]:
            satirlar.append({
                "kapanan_kaynak": eslesme["kapanan"],
                "kapanan_id": eslesme["kapanan_id"],
                "etkilenen_fikirler": eslesme["fikirler"],
                "kapanma_sebebi": eslesme["kapanma_sebebi"],
                "kapananin_verdigi": eslesme["kapananin_verdigi"],
                "alternatif": "(bulunamadı)",
                "alternatif_id": "",
                "alternatifin_verdigi": "",
                "alan_farki": "alternatif yok — bu kaynağın verdiği hiçbir alan "
                              "başka yerden alınamıyor",
                "pazar_farki": "", "tazelik": "",
                "limit_farki": "",
                "kalan_eksik": f'{eslesme["kapananin_verdigi"]} — kaynağı yok',
                "arsiv_secenegi": (tazelik if arsiv_bilgisi else
                                   "arşivde de yok (Common Crawl robots'a uyuyor)"),
                "sonraki_secenekler": " | ".join(SONRAKI_SECENEKLER[sebep_anahtari]),
            })
            continue

        for ad, sid in eslesme["alternatifler"]:
            alt = alternatif.get(ad, {})
            ornek = ornekler.get(sid, {})
            satici_mi = alt.get("kaynak_cinsi", "").startswith("satıcı")
            verdigi = []
            if alt.get("bulunan_fiyat"):
                verdigi.append("fiyat")
            if ornek.get("puan"):
                verdigi.append("puan")
            if ornek.get("yazar"):
                verdigi.append("yazar")
            if not satici_mi and sid:
                verdigi.append("kullanıcı yorumu")
            satirlar.append({
                "kapanan_kaynak": eslesme["kapanan"],
                "kapanan_id": eslesme["kapanan_id"],
                "etkilenen_fikirler": eslesme["fikirler"],
                "kapanma_sebebi": eslesme["kapanma_sebebi"],
                "kapananin_verdigi": eslesme["kapananin_verdigi"],
                "alternatif": ad,
                "alternatif_id": sid or "(katalogda yok — registry kararı Batuhan'da)",
                "alternatifin_verdigi": ", ".join(verdigi) or "yüzey kanıtı",
                "alan_farki": (
                    "SATICI SİTESİ — fiyat/ürün verir, kullanıcı şikâyeti VERMEZ"
                    if satici_mi else
                    "üçüncü taraf — kullanıcı yorumu taşıyor"),
                "pazar_farki": alt.get("bulunan_fiyat", "").startswith("TRY")
                               and "TR pazarına yerelleşmiş fiyat" or "global",
                "tazelik": "canlı çekim" if alt.get("erisim") == "ok" else "—",
                "limit_farki": _limit_notu(sid, kontrol),
                "kalan_eksik": (
                    "kullanıcı şikâyeti ve problem ifadesi" if satici_mi else ""),
                "arsiv_secenegi": (tazelik if arsiv_bilgisi else
                                   "arşivde yok"),
                "sonraki_secenekler": " | ".join(SONRAKI_SECENEKLER[sebep_anahtari]),
            })
    return satirlar


def _limit_notu(sid: str, kontrol: dict[str, dict[str, str]]) -> str:
    if not sid:
        return "katalogda olmadığı için limiti ölçülmedi"
    satir = kontrol.get(sid, {})
    if satir.get("bugun_erisim") == "rate_limited":
        return "hız sınırı düşük — istek aralığı artırılmalı"
    if sid == "source-0096":
        return ("AS-01'de aynı koşuda üçüncü istekte rate_limited alındı; "
                "istek aralığı artırılmalı")
    return "ölçülen özel limit yok"


def arsiv_yas_tablosu(bugun: str) -> list[dict[str, Any]]:
    """Her arsiv kopyasinin KENDI tarihi ve yasi.

    ARTEFAKT-DIZINI.csv yalniz bizim cekme anımızı tutuyor; bu tablo
    arsivin kendi zaman damgasini yanina koyar ki 19 aylik bir sayfa bu
    ayin verisi sanilmasin.
    """
    envanter = {r["source_id"]: r for r in _oku("VERI-ENVANTERI.csv")}
    dizin = {r["source_id"]: r for r in _oku("ARTEFAKT-DIZINI.csv")
             if r.get("yontem") == "common_crawl_warc" and r["sonuc"] == "ok"}
    satirlar: list[dict[str, Any]] = []
    for sid, bilgi in sorted(arsiv_tarihleri().items()):
        gun, uyari = tazelik_notu(bilgi["arsiv_tarihi"], bugun)
        satirlar.append({
            "source_id": sid,
            "kaynak_adi": envanter.get(sid, {}).get("ad", "?"),
            "arsiv_icerik_tarihi": bilgi["arsiv_tarihi"],
            "bizim_cekme_tarihimiz": dizin.get(sid, {}).get("tarih", "")[:10],
            "yas_gun": gun,
            "arsiv_indeksi": bilgi["arsiv_indeksi"],
            "tazelik_uyarisi": uyari,
            "guncel_veri_mi": "hayır",
        })
    return sorted(satirlar, key=lambda r: -r["yas_gun"])


def rapor(fark: list[dict[str, Any]], arsiv: list[dict[str, Any]], bugun: str) -> str:
    import collections

    eski = [r for r in arsiv if r["yas_gun"] >= TAZELIK_UYARI_GUNU]
    bulunamayan = [r for r in fark if r["alternatif"] == "(bulunamadı)"]
    satici = [r for r in fark if r["alan_farki"].startswith("SATICI")]
    kova = collections.Counter(
        "0-90" if r["yas_gun"] < 90 else "90-180" if r["yas_gun"] < 180
        else "180-365" if r["yas_gun"] < 365 else "365+" for r in arsiv)

    fark_tablosu = "\n".join(
        f'| {r["kapanan_kaynak"]} | {r["alternatif"]} | {r["alternatifin_verdigi"]} | '
        f'{r["alan_farki"][:54]} | {r["kalan_eksik"] or "—"} |' for r in fark)
    arsiv_tablosu = "\n".join(
        f'| {r["kaynak_adi"][:26]} | {r["arsiv_icerik_tarihi"]} | '
        f'{r["bizim_cekme_tarihimiz"]} | {r["yas_gun"]} |' for r in arsiv[:10])

    return f"""# AS-03 — Alternatifin farkı, limitleri ve kalan eksikleri

**Sürüm {SURUM}** · Ölçüm: {bugun} · Üreten: `alternatif_fark.py`
Hazırlayan: Ayselin Aydoğdu · Kontrol eden: Batuhan

AS-01 kapalı kaynaklara alternatif aradı ve buldu. Bu belge **farkı** ölçer:
bir alternatifin çalışması, kapananın yerini tuttuğu anlamına gelmez.

## 1. Arşiv güncel veri değildir — ve dizinimiz bunu göstermiyordu

Bir arşiv kopyasının **iki tarihi** vardır ve ikisi karıştırılırsa eski bir
sayfa bu ayın verisi görünür:

| | Ne demek |
|---|---|
| `arsiv_icerik_tarihi` | Common Crawl'ın sayfayı çektiği an — **içeriğin yaşı** |
| `bizim_cekme_tarihimiz` | O kopyayı bizim indirdiğimiz an |

`ARTEFAKT-DIZINI.csv` yalnız ikincisini tutuyordu. Arşivin kendi zaman
damgası koşu JSON'unda duruyordu ve hiçbir tabloya taşınmamıştı.

Ölçülen sonuç — **{len(arsiv)} arşiv kopyasının yaşı**:

| Yaş | Kaynak |
|---|---:|
| 0-90 gün | {kova['0-90']} |
| 90-180 gün | {kova['90-180']} |
| 180-365 gün | {kova['180-365']} |
| **365+ gün** | **{kova['365+']}** |

**{len(eski)} kopya {TAZELIK_UYARI_GUNU} günlük uyarı eşiğini aşıyor.** En eskiler:

| Kaynak | Arşiv içerik tarihi | Bizim çekme tarihimiz | Yaş (gün) |
|---|---|---|---:|
{arsiv_tablosu}

Hepsi dizinde `2026-09-03` görünüyordu. Ayrıntı:
[`AS03-ARSIV-YASI.csv`](AS03-ARSIV-YASI.csv) — her satır `guncel_veri_mi = hayır`.

## 2. Alternatifin farkı

{len(fark)} eşleşme incelendi. **{len(satici)}'i satıcının kendi sitesi**, yani
fiyat verir şikâyet vermez.

| Kapanan | Alternatif | Verdiği | Fark | Kalan eksik |
|---|---|---|---|---|
{fark_tablosu}

### G2 ve Capterra'nın yerini hiçbir şey tutmuyor

İkisi de **kullanıcı yorumu** veriyordu. Bulunan alternatifler (Filestage,
Ziflow) satıcının kendi siteleri: fiyat ve ürün iddiası verirler, kendileri
hakkındaki şikâyeti yayımlamazlar. Kanıt politikası da aynı yere varıyor —
*"aynı kurumun pazarlama kopyaları bir köken"*.

G2 için arşiv kopyası var ama işe yaramıyor: elimizdeki kopya G2'nin **ana
sayfası**, yorum sayfası değil; 9.965 karakter ve sıfır çıkarılabilir alan.
Üstelik **{[r for r in arsiv if r["source_id"] == "source-0134"][0]["yas_gun"] if any(r["source_id"] == "source-0134" for r in arsiv) else "?"} gün eski.**

### Alternatifi bulunamayanlar

{len(bulunamayan)} kaynak için alternatif **arandı ve bulunamadı**:

{chr(10).join(f'- **{r["kapanan_kaynak"]}** ({r["etkilenen_fikirler"]}) — {r["kalan_eksik"]}' for r in bulunamayan)}

Bu bir eksiklik kaydı değil **sınır** kaydıdır: aranmış, bulunamamış.

## 3. Çözülemeyenler için sonraki seçenekler

| Engel türü | Sonraki seçenek |
|---|---|
| **Politika** (Reddit, Trustpilot) | Kaynağın resmî araştırma programına başvuru — hesap ve şartname onayı gerekir, **karar Çağlar'da** |
| **Bot koruması** (G2, Capterra) | Üçüncü taraf kaynak · arşiv (yaşıyla) · resmî API varsa registry'ye ekleme |
| **JS kabuğu** (Google Play) | Aynı ürünün başka platformdaki sayfası — App Store'da çalıştı |

Hiçbiri **zorlama** içermiyor: bot koruması aşılmıyor, robots yasağına
uyuluyor.

## 4. Bu belge ne söylemez

- Bir alternatifin bulunması kanıt yeterliliği sağlamaz; 3/2 eşiği Faz 3'e ait.
- **Arşiv sonucu tam ya da güncel veri gibi sunulamaz.** Her arşiv satırı
  kendi tarihini ve yaşını taşır.
- Alternatif bulunamaması o pazarda talep olmadığını göstermez.
- Ölçüm {bugun} tarihlidir.

## 5. Yeniden üretim

```bash
python3 alternatif_fark.py --yaz
python3 -m unittest test_alternatif_fark
```
"""


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--yaz", action="store_true")
    secenek = ayristirici.parse_args(argv)

    bugun = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    fark = fark_matrisi(bugun)
    arsiv = arsiv_yas_tablosu(bugun)
    eski = [r for r in arsiv if r["yas_gun"] >= TAZELIK_UYARI_GUNU]
    print(json.dumps({
        "surum": SURUM, "olcum": bugun,
        "fark_satiri": len(fark),
        "alternatifi_bulunamayan": sum(1 for r in fark if r["alternatif"] == "(bulunamadı)"),
        "satici_sitesi_alternatif": sum(1 for r in fark if r["alan_farki"].startswith("SATICI")),
        "arsiv_kopyasi": len(arsiv),
        "tazelik_uyarisi_asan": len(eski),
        "en_eski_gun": max((r["yas_gun"] for r in arsiv), default=0),
    }, ensure_ascii=False, indent=2))
    if not secenek.yaz:
        return 0
    _yaz("AS03-FARK-MATRISI.csv", fark)
    _yaz("AS03-ARSIV-YASI.csv", arsiv)
    (HERE / "AS03-ALTERNATIF-FARKI.md").write_text(
        rapor(fark, arsiv, bugun), encoding="utf-8")
    print("AS03-FARK-MATRISI.csv · AS03-ARSIV-YASI.csv · AS03-ALTERNATIF-FARKI.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
