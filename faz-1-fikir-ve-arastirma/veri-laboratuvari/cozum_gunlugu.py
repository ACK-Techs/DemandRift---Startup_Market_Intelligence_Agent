"""AS-06 — cozum gunlugu ve kaynak saglik kayitlari.

Gorev karti: "Her bulguda denenen sorgu/yol, tarih, script surumu, once/sonra
veri, cozulemeyen sinir ve FB-ID tut. Cozumu Batuhan'in yeniden uretebilecegi
sekilde teslim et. **Basarili ve basarisiz kaynak orneklerini birlikte koru.**"

Iki kayit uretilir ve ikisi farkli seyi tutar:

* ``COZUM-GUNLUGU.csv`` — **ne yaptik.** Her bulgu icin denenen yol, tarih,
  script surumu, oncesi, sonrasi, kalan sinir, FB-ID ve yeniden uretim komutu.
  Bu kayit elle yazilir cunku tarihsel bir anlatidir; veriden turetilemez.
  Dogrulanabilir olmasi icin her satir bir commit'e ve bir olcume baglanir.

* ``KAYNAK-SAGLIK.csv`` — **kaynak bugun ne durumda.** Bu kayit olculur,
  yazilmaz: artefakt dizinlerinden ve AS-01 yoklamasindan turer.

Son cumle kasitli: **basarisiz kaynaklar silinmez.** Calisan kaynaklari yazip
calismayanlari atmak, ayni siteyi bir sonraki turda yeniden denememize ve
ayni duvara ayni sekilde carpmamiza yol acar. Saglik kaydi ikisini de tutar.

Gunluk bir **basari raporu degildir.** Denenip olmayan yollar, yanlis cikan
tahminler ve geri alinan kararlar da buradadir; bir yolun denenmis ve
calismamis oldugunu bilmek, hic denenmemis olmasindan farklidir.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SURUM = "1.0.0"

# (bulgu_id, baslik, ne_denendi, tarih, script, once, sonra, durum,
#  kalan_sinir, fb_id, yeniden_uretim, commit)
#
# durum: cozuldu | kismen | cozulemedi
# "cozulemedi" bir basarisizlik kaydi degil, bir SINIR kaydidir: o yolun
# denenmis ve yurumemis oldugunu soyler.
BULGULAR: list[dict[str, str]] = [
    {
        "bulgu_id": "CG-01",
        "baslik": "robots_state RFC 9309'un altinda kaliyordu",
        "ne_denendi": "api.stackexchange.com/robots.txt — resmi API host'u robots.txt "
                      "yerine HTTP 400 + JSON hata donduruyor",
        "tarih": "2026-09-24",
        "script": "bulk_site_access_lab.py",
        "once": "robots_preflight_blocked — istek hic atilmadi",
        "sonra": "robots=absent; API calisti, 4980 karakter, 3 gercek sonuc",
        "durum": "cozuldu",
        "kalan_sinir": "stackoverflow.com ayri: HTTP 418 ile GECERLI bir "
                       "'Disallow: /' donduruyor ve bu yasak korunuyor",
        "fb_id": "—",
        "yeniden_uretim": "python3 as01_kaynak_kontrol.py --canli  (F03 satiri)",
        "commit": "bc446ef",
    },
    {
        "bulgu_id": "CG-02",
        "baslik": "iTunes Search API beyan edilen MIME yuzunden reddediliyordu",
        "ne_denendi": "itunes.apple.com/search?term=Booksy&entity=software — "
                      "gecerli JSON'u text/javascript tipiyle servis ediyor",
        "tarih": "2026-09-24",
        "script": "bulk_site_access_lab.py",
        "once": "mime_or_sniff_mismatch — dort terimde de basarisiz",
        "sonra": "Booksy Biz id=725335996, puan 4.52, 14.888 yorum sayisi alindi",
        "durum": "cozuldu",
        "kalan_sinir": "—",
        "fb_id": "—",
        "yeniden_uretim": "python3 alternatif_kaynak.py --canli  (F09 App Store satirlari)",
        "commit": "635ce4b",
    },
    {
        "bulgu_id": "CG-03",
        "baslik": "Fiyat deseni para birimi onde gelen bicimi kaciriyordu",
        "ne_denendi": "fresha.com/pricing — fiyatlar 'TRY 240.95 per month' bicimde",
        "tarih": "2026-09-24",
        "script": "normalize_belgeler.py",
        "once": "fiyat alani bos; 55 fiyat isareti olan sayfadan 0 fiyat cikti",
        "sonra": "TRY 240.95 yakalandi; TL, EUR, GBP onek bicimleri de",
        "durum": "cozuldu",
        "kalan_sinir": "—",
        "fb_id": "—",
        "yeniden_uretim": "python3 -c \"import normalize_belgeler as n; "
                          "print(n.alan_cikar('urun','TRY 240.95 per month',''))\"",
        "commit": "302497e",
    },
    {
        "bulgu_id": "CG-04",
        "baslik": "Reddit kazimayla alinamiyor",
        "ne_denendi": "reddit.com/robots.txt bugun yeniden cekildi; /r/*/.rss, "
                      "/r/*/new.json, /dev/api dahil yedi yol robots'a soruldu",
        "tarih": "2026-09-24",
        "script": "as01_kaynak_kontrol.py",
        "once": "kayitta 'kismi/dosya-yok'; sebep belirsizdi",
        "sonra": "sebep kesin: 'User-agent: * / Disallow: /' — yedi yolun yedisi yasak",
        "durum": "cozulemedi",
        "kalan_sinir": "Politika engeli. Reddit'in kendi robots.txt'i izinli yolu "
                       "gosteriyor: Public Content Policy ve r/reddit4researchers. "
                       "Hesap ve sartname onayi gerekir; karar Cağlar'da. "
                       "10 fikrin 7'sini etkiliyor.",
        "fb_id": "AS01-0075",
        "yeniden_uretim": "python3 as01_kaynak_kontrol.py --canli  (Reddit satirlari)",
        "commit": "bc446ef",
    },
    {
        "bulgu_id": "CG-05",
        "baslik": "Capterra kayitla celisiyor: kayit calisiyor diyor, bugun kapali",
        "ne_denendi": "capterra.com/proofing-software/ ve /salon-software/ — "
                      "robots izin veriyor, istek bot korumasina takiliyor",
        "tarih": "2026-09-24",
        "script": "as01_kaynak_kontrol.py",
        "once": "2 Eylul kaydi: erisim=cekildi, icerik=gercek-icerik",
        "sonra": "bugun challenge; F02, F09 ve F10'u etkiliyor",
        "durum": "cozulemedi",
        "kalan_sinir": "Bot korumasi asilmiyor. Arsiv (Common Crawl) kopyasi var "
                       "ama canli degil ve 'arsiv' etiketiyle tasinmali.",
        "fb_id": "AS01-0135",
        "yeniden_uretim": "python3 as01_kaynak_kontrol.py --canli  (F02/F09 Capterra)",
        "commit": "bc446ef",
    },
    {
        "bulgu_id": "CG-06",
        "baslik": "Google Play HTTP 200 donuyor ama govde bos",
        "ne_denendi": "play.google.com/store/apps/details?id=... — robots izinli, "
                      "istek basarili",
        "tarih": "2026-09-24",
        "script": "as01_kaynak_kontrol.py",
        "once": "erisim listesinde 'ok' gorunuyordu",
        "sonra": "200 OK, 0 karakter gorunur metin; js-kabugu olarak ayrildi",
        "durum": "kismen",
        "kalan_sinir": "Sayfa tamamen tarayicida uretiliyor. Ayni uygulamalar "
                       "Apple App Store'da aliniyor (21-28 bin karakter, puan ve "
                       "fiyatla); Google Play tarafi acik kaliyor.",
        "fb_id": "AS01-0097",
        "yeniden_uretim": "python3 as01_kaynak_kontrol.py --canli  (F01/F10 Google Play)",
        "commit": "bc446ef",
    },
    {
        "bulgu_id": "CG-07",
        "baslik": "Uygulama magazasi kayit sayfalari bos geliyor",
        "ne_denendi": "galaxystore.samsung.com/detail/... ve apps.microsoft.com/"
                      "detail/... — sitemap'lerden 14.948 kayit adresi cikarildi, "
                      "6 tanesi test edildi",
        "tarih": "2026-09-18",
        "script": "ic_sayfa_gecisi.py",
        "once": "14.948 aday adres; mobil-uygulama kategorisi 1/6 hucrede doluydu",
        "sonra": "Microsoft bos govde, Samsung 38 karakter; kategori acik kaldi",
        "durum": "cozulemedi",
        "kalan_sinir": "Istemci tarafinda uretilen magaza sayfalari bu hatla "
                       "alinamiyor. Adres sayisi coklugu ise yaramiyor.",
        "fb_id": "—",
        "yeniden_uretim": "AS01-ALTERNATIF-KAYNAK.csv · kayit sayfasi testi",
        "commit": "298f5c0",
    },
    {
        "bulgu_id": "CG-08",
        "baslik": "Apple musteri yorumu RSS ucu bos donuyor",
        "ne_denendi": "itunes.apple.com/us/rss/customerreviews/page=1/id=725335996/json — "
                      "Booksy Biz ve Fresha for business icin denendi",
        "tarih": "2026-09-24",
        "script": "alternatif_kaynak.py",
        "once": "belgelenmis uc; yorum METNI icin ilk tercih",
        "sonra": "gecerli JSON donuyor ama 'entry' dizisi bos — uc fiilen emekli",
        "durum": "cozuldu",
        "kalan_sinir": "Calisan yol uygulama SAYFASININ kendisi cikti: "
                       "apps.apple.com/.../id725335996 icinde gercek yorum metni var.",
        "fb_id": "—",
        "yeniden_uretim": "python3 alternatif_kaynak.py --canli  (F09 App Store satiri)",
        "commit": "635ce4b",
    },
    {
        "bulgu_id": "CG-09",
        "baslik": "HTTP 200 + gercek icerik, ilgisiz sonuc",
        "ne_denendi": "sourceforge.net/directory/?q=salon+scheduling+software",
        "tarih": "2026-09-24",
        "script": "alternatif_kaynak.py",
        "once": "aday listesinde 'calisiyor' sayiliyordu",
        "sonra": "200 OK, 19 bin karakter; icerik Kubernetes orkestrasyon ve "
                 "kripto fiyatlama — nisle ilgisi yok",
        "durum": "cozuldu",
        "kalan_sinir": "Her adaya ucuncu bir test eklendi: erisim ve icerik "
                       "yetmiyor, nisin kendi kelimeleri govdede aranmali. "
                       "Anahtar kelime eslesmesi ilgililik degildir.",
        "fb_id": "—",
        "yeniden_uretim": "python3 -m unittest test_alternatif_kaynak.IlgililikTests",
        "commit": "302497e",
    },
    {
        "bulgu_id": "CG-10",
        "baslik": "F02 icin kullanici sikayeti kaynagi bulunamadi",
        "ne_denendi": "Filestage/Ziflow (satici sitesi), SourceForge (ilgisiz), "
                      "GetApp (challenge), Hacker News API (0 sonuc), "
                      "iTunes Search (mobil uygulama yok)",
        "tarih": "2026-09-24",
        "script": "alternatif_kaynak.py",
        "once": "F02'nin uc kaynagi da kapaliydi",
        "sonra": "fiyat/urun icin Filestage ve Ziflow bulundu; sikayet icin hicbiri",
        "durum": "kismen",
        "kalan_sinir": "Satici kendi hakkindaki sikayeti yayimlamaz. F02 fiyat ve "
                       "urun iddiasi icin arastirilabilir, memnuniyetsizlik icin "
                       "arastirilamaz. Filestage ve Ziflow katalogda YOK — "
                       "registry karari Batuhan'da.",
        "fb_id": "AS01-0134, AS01-0135",
        "yeniden_uretim": "python3 alternatif_kaynak.py --canli  (F02 satirlari)",
        "commit": "635ce4b",
    },
    {
        "bulgu_id": "CG-11",
        "baslik": "Ham arsiv depo disinda kaldi; iddialar dogrulanamiyordu",
        "ne_denendi": "Uc fazli yapiya tasinma sonrasi artefakt konumu sayildi",
        "tarih": "2026-09-24",
        "script": "as01_kaynak_kontrol.py",
        "once": "1249 normalize belgenin 21'inin ham dosyasi depoda (%1.7)",
        "sonra": "sayi cikarilan 154 dosya depoya alindi; "
                 "KATEGORI-ALANLARI.csv'deki 164 alanin 164'u dogrulanabilir",
        "durum": "kismen",
        "kalan_sinir": "SourceFitMatrix ornek kayitlari 101/346'da; tamamlamak "
                       "~75 MB daha demek, karar Batuhan'da. Kalan 1070 belge "
                       "ana sayfa ve sitemap — dogrulanacak iddia tasimiyorlar.",
        "fb_id": "—",
        "yeniden_uretim": "python3 -m unittest "
                          "test_as01_kaynak_kontrol.CikarilanSayininKaynagiDepodaTests",
        "commit": "474a09c",
    },
]


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


# --------------------------------------------------------------------------
# Kaynak saglik kayitlari
# --------------------------------------------------------------------------
# Saglik "calisiyor mu" degil, **hangi duvara carpiyor** sorusunu cevaplar.
# Ayni sebep ayni cozumu gerektirir; sebebi bilmeden yeniden denemek ayni
# duvara yeniden carpmaktir.
SAGLIK_SINIFI: dict[str, tuple[str, str]] = {
    "ok": ("saglikli", "içerik geliyor"),
    "robots_disallowed": ("politika-kapali", "robots.txt yolu yasaklıyor — aşılmaz"),
    "robots_preflight_blocked": ("politika-kapali", "robots.txt 401/403 — tam yasak"),
    "challenge": ("bot-korumasi", "site bizi bot olarak tanıyıp reddediyor — aşılmaz"),
    "origin_circuit_open": ("bot-korumasi", "aynı origin'de önceki istek reddedildi"),
    "rate_limited": ("hiz-siniri", "istek aralığı artırılmalı; kaynak kapalı değil"),
    "source_unavailable": ("adres-hatasi", "adres yanıt vermiyor ya da sayfa yok"),
    "origin_denied": ("adres-hatasi", "sunucu isteği reddetti"),
    "mime_or_sniff_mismatch": ("bicim-uyusmazligi", "beyan edilen tip beklenenden farklı"),
    "budget_exhausted": ("butce", "koşu bütçesi bitti; kaynak hakkında bilgi vermez"),
}
ICERIK_NOTU: dict[str, str] = {
    "js-kabugu": "HTTP 200 ama görünür metin yok — sayfa tarayıcıda üretiliyor",
    "aday-kesif": "yalnız sitemap/adres listesi — içerik değil",
    "arsiv": "Common Crawl kopyası — canlı değil",
    "dosya-yok": "bu checkout'ta açılabilir dosya yok",
}


def saglik_kayitlari() -> list[dict[str, Any]]:
    """Kaynak basina saglik. Basarili ve basarisiz BIRLIKTE tutulur."""
    envanter = {r["source_id"]: r for r in _oku("VERI-ENVANTERI.csv")}
    kontrol = _oku("AS01-KAYNAK-KONTROL.csv")
    alternatif = _oku("AS01-ALTERNATIF-KAYNAK.csv")
    dizin = _oku("ARTEFAKT-DIZINI.csv") + _oku("EK-ARTEFAKT-DIZINI.csv")

    son_deneme: dict[str, dict[str, str]] = {}
    for satir in kontrol:
        son_deneme.setdefault(satir["source_id"], satir)
    for satir in alternatif:
        sid = satir["source_id"]
        if sid.startswith("source-") and sid not in son_deneme:
            son_deneme[sid] = {"bugun_erisim": satir["erisim"],
                               "bugun_icerik": satir["icerik"],
                               "denenen_url": satir["denenen_url"],
                               "kayitli_icerik": "", "degisti_mi": "",
                               "bugun_artefakt": satir["artefakt"]}

    artefakt_sayisi: dict[str, int] = collections.Counter(
        r["source_id"] for r in dizin if r["sonuc"] == "ok" and r.get("source_id"))
    diskte: dict[str, int] = collections.Counter()
    for r in dizin:
        if r["sonuc"] == "ok" and r.get("source_id") and r["dosya"].strip() \
                and (HERE / r["dosya"]).exists():
            diskte[r["source_id"]] += 1

    satirlar: list[dict[str, Any]] = []
    for sid, deneme in sorted(son_deneme.items()):
        kayit = envanter.get(sid, {})
        erisim = deneme["bugun_erisim"]
        sinif, sebep = SAGLIK_SINIFI.get(erisim, ("bilinmiyor", erisim))
        icerik = deneme.get("bugun_icerik", "")
        if erisim == "ok" and icerik in ICERIK_NOTU:
            sinif, sebep = "icerik-yetersiz", ICERIK_NOTU[icerik]
        satirlar.append({
            "source_id": sid,
            "kaynak_adi": kayit.get("ad", "?"),
            "saglik": sinif,
            "sebep": sebep,
            "son_olcum": "2026-09-24",
            "son_denenen_url": deneme.get("denenen_url", ""),
            "bugun_erisim": erisim,
            "bugun_icerik": icerik,
            "kayitli_icerik": deneme.get("kayitli_icerik", ""),
            "degisim": deneme.get("degisti_mi", ""),
            "kanit_artefakti": deneme.get("bugun_artefakt", ""),
            "arsivdeki_artefakt": artefakt_sayisi.get(sid, 0),
            "artefakt_depoda": diskte.get(sid, 0),
            "yeniden_denenebilir_mi": (
                "hayır — politika" if sinif == "politika-kapali" else
                "hayır — bu yöntemle" if sinif in ("bot-korumasi", "icerik-yetersiz") else
                "evet — aralık artırılarak" if sinif == "hiz-siniri" else
                "evet" if sinif == "saglikli" else "belirsiz"),
        })
    return satirlar


def rapor(bulgular: list[dict[str, str]], saglik: list[dict[str, Any]]) -> str:
    durum = collections.Counter(b["durum"] for b in bulgular)
    sinif = collections.Counter(r["saglik"] for r in saglik)

    def gunluk_bolumu(secilen: list[dict[str, str]]) -> str:
        parcalar = []
        for b in secilen:
            parcalar.append(f"""#### {b["bulgu_id"]} — {b["baslik"]}

| | |
|---|---|
| **Ne denendi** | {b["ne_denendi"]} |
| **Tarih** | {b["tarih"]} · `{b["script"]}` · commit `{b["commit"]}` |
| **Önce** | {b["once"]} |
| **Sonra** | {b["sonra"]} |
| **Kalan sınır** | {b["kalan_sinir"]} |
| **FB-ID** | {b["fb_id"]} |

```bash
{b["yeniden_uretim"]}
```
""")
        return "\n".join(parcalar)

    saglik_tablosu = "\n".join(
        f'| {r["kaynak_adi"]} | `{r["source_id"]}` | {r["saglik"]} | {r["sebep"]} | '
        f'{r["yeniden_denenebilir_mi"]} |' for r in saglik)

    return f"""# Çözüm Günlüğü ve Kaynak Sağlık Kayıtları — AS-06

**Sürüm {SURUM}** · Hazırlayan: Ayselin Aydoğdu · Kontrol eden: Batuhan
Üreten: `cozum_gunlugu.py` · Son ölçüm: 2026-09-24

Bu belge bir **başarı raporu değildir.** Denenip yürümeyen yollar, yanlış
çıkan tahminler ve geri alınan kararlar da burada. Bir yolun *denenmiş ve
çalışmamış* olduğunu bilmek, *hiç denenmemiş* olmasından farklıdır — ikincisi
tekrar denemeye değer, birincisi aynı duvara yeniden çarpmaktır.

## Özet

| Bulgu durumu | Adet |
|---|---:|
| Çözüldü | {durum['cozuldu']} |
| Kısmen çözüldü | {durum['kismen']} |
| Çözülemedi (sınır kaydı) | {durum['cozulemedi']} |
| **Toplam** | **{len(bulgular)}** |

Her bulgu bir tarihe, bir script sürümüne ve bir commit'e bağlı; her satırın
altında Batuhan'ın çalıştırabileceği komut var.

## 1. Çözülen bulgular

Bunların hepsinde **öncesi ve sonrası ölçüldü**; iddia değil, ölçüm.

{gunluk_bolumu([b for b in bulgular if b["durum"] == "cozuldu"])}
## 2. Kısmen çözülenler

Bir tarafı açıldı, bir tarafı açık kaldı. Açık kalan taraf gizlenmiyor.

{gunluk_bolumu([b for b in bulgular if b["durum"] == "kismen"])}
## 3. Çözülemeyenler — sınır kayıtları

Bunlar başarısızlık değil **sınır** kaydıdır. Yol denendi, yürümedi, sebebi
ölçüldü. Aynı yolu tekrar denemek yerine sebebe bakılmalı.

{gunluk_bolumu([b for b in bulgular if b["durum"] == "cozulemedi"])}
## 4. Kaynak sağlık kayıtları

**Başarılı ve başarısız kaynaklar birlikte tutulur.** Çalışmayanı silmek, bir
sonraki turda aynı siteyi yeniden deneyip aynı duvara çarpmak demektir.

| Sağlık | Kaynak |
|---|---:|
| `saglikli` — içerik geliyor | {sinif['saglikli']} |
| `bot-korumasi` — site reddediyor | {sinif['bot-korumasi']} |
| `politika-kapali` — robots yasağı | {sinif['politika-kapali']} |
| `icerik-yetersiz` — 200 ama gövde boş | {sinif['icerik-yetersiz']} |

| Kaynak | source_id | Sağlık | Sebep | Yeniden denenebilir mi |
|---|---|---|---|---|
{saglik_tablosu}

Sağlık "çalışıyor mu" değil **hangi duvara çarpıyor** sorusunu cevaplar.
`politika-kapali` ve `bot-korumasi` farklı şeylerdir: birincisi sitenin açık
kararı, ikincisi teknik reddi. İkisi de aşılmıyor ama çözümleri farklı —
birincisi izin, ikincisi başka yüzey gerektirir.

## 5. Bu günlük ne söylemez

- Bir kaynağın kapalı olması o pazarda talep olmadığını göstermez.
- `cozulemedi` satırları kapatılmış değildir; koşul değişirse yeniden açılır.
- Ölçümler 2026-09-24 tarihlidir. Kaynak durumu değişir — CG-05 tam olarak
  bunun örneği: üç hafta önce çalışan Capterra bugün kapalı.

## 6. Yeniden üretim

```bash
python3 cozum_gunlugu.py --yaz
python3 -m unittest test_cozum_gunlugu
```
"""


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--yaz", action="store_true")
    secenek = ayristirici.parse_args(argv)

    saglik = saglik_kayitlari()
    ozet = {
        "surum": SURUM,
        "bulgu": len(BULGULAR),
        "durum": dict(collections.Counter(b["durum"] for b in BULGULAR)),
        "saglik_kaydi": len(saglik),
        "saglik": dict(collections.Counter(r["saglik"] for r in saglik)),
    }
    print(json.dumps(ozet, ensure_ascii=False, indent=2))
    if not secenek.yaz:
        return 0
    _yaz("COZUM-GUNLUGU.csv", BULGULAR)
    _yaz("KAYNAK-SAGLIK.csv", saglik)
    (HERE / "COZUM-GUNLUGU.md").write_text(rapor(BULGULAR, saglik), encoding="utf-8")
    print("COZUM-GUNLUGU.csv · KAYNAK-SAGLIK.csv · COZUM-GUNLUGU.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
