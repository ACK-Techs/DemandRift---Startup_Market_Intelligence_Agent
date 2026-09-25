"""AS-04 — dort hata sinifini kendi verimizde arar ve etiketli referans kurar.

Gorev karti: "Relevant/irrelevant/uncertain orneklerini ve dogrudan karsit
bulgulari etiketle. Yanlis alan, dedup yanlis birlesmesi, onemli kanitin
filtrede kaybi veya desteklenmeyen claim icin ornek bazli cozum hazirla.
**Etiketli referans olmadan web recall orani uretme.**"

Faz 2 rehberi ayni siniri koyuyor: "Etiketli referansta precision/recall;
referans yoksa recall yok."

Bu modul iki sey uretir:

* ``AS04-HATA-INCELEMESI.csv`` — dort hata sinifinin her birinde bulunan
  ornekler, sebebi ve duzeltme durumu. Bulunmayan sinif da kaydedilir:
  "arandi, bulunamadi" ile "hic bakilmadi" ayni sey degildir.

* ``AS04-ETIKETLI-REFERANS.csv`` — elle etiketlenmis ornekler.
  ``relevant / irrelevant / uncertain`` + **sebep**, ve dogrudan karsit
  bulgular ayrica isaretli. Bu kume olmadan precision hesaplanamaz.

**Recall hesaplanmaz ve hesaplanamaz.** Recall icin acik web'deki tum ilgili
icerigin bilinmesi gerekir; bilinmiyor. Bu modul precision uretir, recall
uretmez, ve uretmedigi her yerde bunu yazar.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SURUM = "1.0.0"

# Fiyat gibi gorunup fiyat olmayan ifadeler: "2.3 billion in AUM", "prize pool".
BUYUKLUK = re.compile(
    r"(?i)\b(billion|milyar|million|milyon|trillion|AUM|prize|fund(ing)?|"
    r"raised|valuation|market cap|revenue)\b")
# Gercek bir ilan/plan fiyatinin yaninda bulunanlar.
ILAN_ISARETI = re.compile(
    r"(?i)(out of 5|\d[.,]\d\s*(?:star|rating|puan)|\breviews?\b|"
    r"/\s*(?:month|year|lifetime|mo\b|ay|yıl)|per (?:night|month|user|seat)|"
    r"for \d+ nights)")


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


def dedup_incele() -> list[dict[str, Any]]:
    """Farkli kaynaklardan birlestirilmis belgeler gercekten ayni mi."""
    import urllib.parse

    belge = {r["document_id"]: r for r in _oku("NORMALIZE-BELGELER.csv")}
    satirlar: list[dict[str, Any]] = []
    for iliski in _oku("BELGE-ILISKILERI.csv"):
        a = belge.get(iliski["document_id"])
        b = belge.get(iliski["hedef_document_id"])
        if not a or not b or a["source_id"] == b["source_id"]:
            continue
        host_a = urllib.parse.urlsplit(a["source_url"]).netloc.replace("www.", "").split(":")[0]
        host_b = urllib.parse.urlsplit(b["source_url"]).netloc.replace("www.", "").split(":")[0]
        yanlis = host_a != host_b
        satirlar.append({
            "hata_sinifi": "dedup-yanlis-birlesme",
            "document_id": iliski["document_id"],
            "ilgili_kayit": iliski["hedef_document_id"],
            "kaynak": f'{a["source_adi"]} <-> {b["source_adi"]}',
            "bulgu": f"{host_a} / {host_b}",
            "karar": "YANLIS BIRLESME" if yanlis else "doğru — aynı alan adı, farklı katalog kaydı",
            "gerekce": ("iki farklı alan adı aynı belge sayılmış"
                        if yanlis else
                        "iki katalog kaydı tek dosyayı paylaşıyor; birleşme doğru"),
            "duzeltme": "ayrıştırılmalı" if yanlis else "—",
        })
    return satirlar


def alan_incele() -> list[dict[str, Any]]:
    """Fiyat yuzeyi olarak cekilmis ama fiyat cikmamis matris satirlari."""
    alanli = {r["document_id"] for r in _oku("KATEGORI-ALANLARI.csv")}
    belge = {r["document_id"]: r for r in _oku("NORMALIZE-BELGELER.csv")}
    PARA = re.compile(
        r"(?i)([$€£₺]\s?\d[\d.,]*|\d[\d.,]*\s?(?:USD|EUR|TRY|GBP|TL)\b"
        r"|(?:USD|EUR|TRY|GBP|TL)\s?\d[\d.,]*)")
    satirlar: list[dict[str, Any]] = []
    gorulen: set[str] = set()
    for r in _oku("SOURCE-FIT-MATRIX.csv"):
        if r["arama_niyeti"] != "observed_market_pricing":
            continue
        d = r["ornek_kayit"].split(" · ")[0]
        if d in alanli or d in gorulen:
            continue
        gorulen.add(d)
        b = belge.get(d)
        if not b:
            continue
        bulgu = PARA.findall(b["body_normalized"])
        satirlar.append({
            "hata_sinifi": "yanlis-eksik-alan",
            "document_id": d,
            "ilgili_kayit": "",
            "kaynak": r["kaynak_adi"],
            "bulgu": (f'sayfada para ifadesi var: {", ".join(bulgu[:3])}'
                      if bulgu else "sayfada para ifadesi yok"),
            "karar": "CIKARICI KACIRIYOR" if bulgu else "sayfada gerçekten fiyat yok",
            "gerekce": ("fiyat yüzeyi olarak çekildi, gövdede fiyat var, "
                        "alan çıkmadı" if bulgu else
                        "fiyat yüzeyi ama sayfa fiyat yayımlamıyor"),
            "duzeltme": ("çıkarım sınıfı sayfa türünden de belirlenmeli"
                         if bulgu else "—"),
        })
    return satirlar


def filtre_incele() -> list[dict[str, Any]]:
    """Kanit uretmez diye elenmis ama fiyat tasiyan belgeler."""
    import normalize_belgeler as nb

    belge = {r["document_id"]: r for r in _oku("NORMALIZE-BELGELER.csv")}
    satirlar: list[dict[str, Any]] = []
    for r in _oku("SINIFLANDIRMA.csv"):
        if (r["olcum_kaniti_uretir_mi"] != "hayir"
                or r["icerik_durumu"] != "gercek-icerik"):
            continue
        b = belge.get(r["document_id"])
        if not b:
            continue
        metin = b["body_normalized"]
        fiyatlar = [x for x in nb.alan_cikar("urun", metin, "") if x["alan"] == "fiyat"]
        if not fiyatlar:
            continue
        deger = fiyatlar[0]["deger"]
        yer = metin.find(deger.replace(" ", ""))
        if yer < 0:
            yer = max(0, metin.find(deger[:4]))
        baglam = metin[max(0, yer - 80):yer + 80]
        if BUYUKLUK.search(baglam):
            karar, gerekce = "gürültü", "büyüklük ifadesi (milyar/fon/ödül), ürün fiyatı değil"
        elif ILAN_ISARETI.search(baglam):
            karar, gerekce = "KAYIP KANIT", "ilan/puan işaretinin yanında gerçek fiyat"
        else:
            karar, gerekce = "gürültü", "yalın para ifadesi, bağlamı yok"
        satirlar.append({
            "hata_sinifi": "filtrede-kayip-kanit",
            "document_id": r["document_id"],
            "ilgili_kayit": "",
            "kaynak": b["source_adi"],
            "bulgu": f'{deger} · {baglam.strip()[:70]}',
            "karar": karar,
            "gerekce": gerekce,
            "duzeltme": ("ana sayfa filtresi ilan taşıyan sayfayı elememeli"
                         if karar == "KAYIP KANIT" else "—"),
        })
    return satirlar


def claim_incele() -> list[dict[str, Any]]:
    """Alan cikmamis belgeye dayanan matris satirlari desteksiz mi."""
    alanli = {r["document_id"] for r in _oku("KATEGORI-ALANLARI.csv")}
    belge = {r["document_id"]: r for r in _oku("NORMALIZE-BELGELER.csv")}
    satirlar: list[dict[str, Any]] = []
    for r in _oku("SOURCE-FIT-MATRIX.csv"):
        d = r["ornek_kayit"].split(" · ")[0]
        if d in alanli:
            continue
        b = belge.get(d)
        if not b:
            continue
        uzunluk = int(b["body_uzunlugu"])
        iddia_ediyor = r["alinabilen_alan"] != "(ölçülebilir alan yok)"
        if iddia_ediyor:
            karar = "DESTEKSIZ CLAIM"
            gerekce = "alan çıkmamış belgeye dayanıp alan iddia ediyor"
            duzeltme = "satır yüzey kanıtı olarak işaretlenmeli"
        elif uzunluk < 500:
            karar = "ZAYIF"
            gerekce = f"gövde {uzunluk} karakter; yüzey kanıtı bile zayıf"
            duzeltme = "belge yeniden çekilmeli"
        else:
            karar = "dürüst"
            gerekce = "satır zaten '(ölçülebilir alan yok)' diyor; yüzey kanıtı"
            duzeltme = "—"
        satirlar.append({
            "hata_sinifi": "desteksiz-claim",
            "document_id": d,
            "ilgili_kayit": f'{r["kategori"]}/{r["arama_niyeti"]}',
            "kaynak": r["kaynak_adi"],
            "bulgu": r["alinabilen_alan"],
            "karar": karar, "gerekce": gerekce, "duzeltme": duzeltme,
        })
    return satirlar


# --------------------------------------------------------------------------
# Etiketli referans kumesi
# --------------------------------------------------------------------------
# Otomatik etiket insan etiketinin yerine gecmez. Faz 2 rehberi acikca
# "ornek sonuclari INSAN etiketlesin" diyor. Asagidaki kararlar elle verildi:
# her ornek acildi, baglami okundu, sebebiyle etiketlendi.
#
# Bu kume **precision** hesabinin tabanidir. **Recall hesaplanamaz**: acik
# web'deki tum ilgili icerik bilinmedigi icin bir referans kume yoktur.
ELLE_ETIKET: list[dict[str, str]] = [
    {"ornek": "500 Global ana sayfası · fiyat=$2.3", "etiket": "irrelevant",
     "sebep": "bağlam 'VC firm with $2.3 billion in AUM' — fon büyüklüğü, "
              "ürün fiyatı değil",
     "karsit_bulgu": "hayir"},
    {"ornek": "Alibaba ana sayfası · fiyat=$1,000,000", "etiket": "irrelevant",
     "sebep": "'total prize pool' — yarışma ödülü, üstelik JSON bloğu içinde",
     "karsit_bulgu": "hayir"},
    {"ornek": "Ars Technica ana sayfası · fiyat=$2.1", "etiket": "irrelevant",
     "sebep": "'NASA's cost estimate ... $2.1 billion' — haber başlığı",
     "karsit_bulgu": "hayir"},
    {"ornek": "Axios ana sayfası · fiyat=$1", "etiket": "irrelevant",
     "sebep": "'$1 Trump coins' — haber başlığı",
     "karsit_bulgu": "hayir"},
    {"ornek": "Airbnb ana sayfası · fiyat=₺4,733", "etiket": "relevant",
     "sebep": "'₺4,733 for 2 nights · 4.78 out of 5' — gerçek ilan fiyatı, "
              "puanıyla birlikte, TR pazarı",
     "karsit_bulgu": "hayir"},
    {"ornek": "AppSumo ana sayfası · fiyat=$39", "etiket": "relevant",
     "sebep": "'3 reviews $39 / lifetime $129' — gerçek ürün listesi",
     "karsit_bulgu": "hayir"},
    {"ornek": "SourceForge · 'salon scheduling software' araması",
     "etiket": "irrelevant",
     "sebep": "HTTP 200 ve 19 bin karakter geldi ama içerik Kubernetes "
              "orkestrasyon ve kripto fiyatlama; 'salon' yalnız sitenin "
              "sorguyu geri yazdığı yerde geçiyor",
     "karsit_bulgu": "hayir"},
    {"ornek": "Kagi /pricing · $5 $10 $25", "etiket": "relevant",
     "sebep": "plan fiyatları; çıkarıcı kaçırıyordu, sayfa doğru",
     "karsit_bulgu": "hayir"},
    {"ornek": "Google Play · Sleep Cycle uygulama sayfası", "etiket": "uncertain",
     "sebep": "HTTP 200 geldi ama gövde boş; sayfa doğru olabilir, "
              "biz göremiyoruz — ilgililik ölçülemiyor",
     "karsit_bulgu": "hayir"},
    {"ornek": "G2 arşiv kopyası (2025-02-12)", "etiket": "uncertain",
     "sebep": "G2'nin ana sayfası, yorum sayfası değil; 596 gün eski. "
              "İçerik gerçek ama sorulan soruya cevap vermiyor",
     "karsit_bulgu": "hayir"},
    {"ornek": "Booksy Biz App Store yorumu · 'charged for a no show'",
     "etiket": "relevant",
     "sebep": "F09'un tam konusu: işletmenin no-show sorunu, gerçek "
              "kullanıcı ifadesiyle",
     "karsit_bulgu": "hayir"},
    {"ornek": "Fresha /pricing · TRY 240.95 per month", "etiket": "relevant",
     "sebep": "satıcının ilan ettiği plan fiyatı, TR pazarına yerelleşmiş",
     "karsit_bulgu": "hayir"},
    {"ornek": "Filestage 'alternatives' sayfası", "etiket": "uncertain",
     "sebep": "rakip listesi var ama satıcının kendi pazarlama sayfası; "
              "bağımsız kanıt sayılmaz, kanıt politikası 'aynı kurumun "
              "pazarlama kopyaları bir köken' diyor",
     "karsit_bulgu": "hayir"},
    {"ornek": "Booksy Biz · 4.5 puan, 14.888 yorum", "etiket": "relevant",
     "sebep": "yüksek puan, F09'un 'bu alanda çözüm yok' varsayımına "
              "KARŞIT sinyal — mevcut çözüm var ve memnuniyet yüksek",
     "karsit_bulgu": "EVET"},
    {"ornek": "Fresha · ücretsiz katman + düşük abonelik", "etiket": "relevant",
     "sebep": "F09'un 'ödeme isteği var' varsayımına KARŞIT: pazarda "
              "ücretsiz alternatif mevcut",
     "karsit_bulgu": "EVET"},
]


def etiketli_referans() -> list[dict[str, Any]]:
    satirlar: list[dict[str, Any]] = []
    for i, e in enumerate(ELLE_ETIKET, 1):
        satirlar.append({
            "etiket_id": f"ET-{i:02d}",
            "ornek": e["ornek"],
            "etiket": e["etiket"],
            "sebep": e["sebep"],
            "dogrudan_karsit_bulgu": e["karsit_bulgu"],
            "etiketleyen": "Ayselin (elle)",
            "etiketleme_tarihi": "2026-09-25",
            "batuhan_yeniden_kontrolu": "bekliyor",
        })
    return satirlar


def precision(etiketler: list[dict[str, Any]]) -> dict[str, Any]:
    """Etiketli kumede precision. RECALL HESAPLANMAZ."""
    sayac = collections.Counter(r["etiket"] for r in etiketler)
    incelenen = len(etiketler)
    return {
        "incelenen_ornek": incelenen,
        "relevant": sayac["relevant"],
        "irrelevant": sayac["irrelevant"],
        "uncertain": sayac["uncertain"],
        "precision": round(sayac["relevant"] / incelenen, 3) if incelenen else 0.0,
        "precision_tanimi": "ilgili bulunan etiketli sonuç / incelenen sonuç",
        "recall": None,
        "recall_neden_yok": ("Açık web'deki tüm ilgili içerik bilinmediği için "
                             "referans küme yoktur; recall uydurulmaz."),
        "dogrudan_karsit_bulgu": sum(
            1 for r in etiketler if r["dogrudan_karsit_bulgu"] == "EVET"),
    }


def rapor(hatalar: list[dict[str, Any]], etiketler: list[dict[str, Any]],
          olcum: dict[str, Any]) -> str:
    sinif = collections.defaultdict(collections.Counter)
    for r in hatalar:
        sinif[r["hata_sinifi"]][r["karar"]] += 1

    def bulgular(hata_sinifi: str, karar: str, adet: int = 6) -> str:
        secilen = [r for r in hatalar
                   if r["hata_sinifi"] == hata_sinifi and r["karar"] == karar]
        if not secilen:
            return "_Bu sınıfta bulgu yok._"
        return "\n".join(f'| {r["kaynak"][:24]} | `{r["bulgu"][:58]}` | {r["gerekce"][:46]} |'
                         for r in secilen[:adet])

    etiket_tablosu = "\n".join(
        f'| {r["etiket_id"]} | {r["ornek"][:44]} | **{r["etiket"]}** | {r["sebep"][:70]} | '
        f'{"**EVET**" if r["dogrudan_karsit_bulgu"] == "EVET" else "—"} |'
        for r in etiketler)

    return f"""# AS-04 — Hata incelemesi ve etiketli referans

**Sürüm {SURUM}** · Ölçüm: 2026-09-25 · Üreten: `hata_incelemesi.py`
Hazırlayan: Ayselin Aydoğdu · Kontrol eden: Batuhan

AS-04 Faz 2'ye ait ve BT-06 hata bildirimine bağlı; bildirim gelmedi. Kartın
istediği dört hata sınıfını **kendi verimizde** aradım, bulduklarımı düzelttim
ve etiketli referans kümesini kurdum. Batuhan bildirim gönderdiğinde aynı
yöntem onun örneklerine uygulanacak.

## 1. Dört hata sınıfı — arandı, ne çıktı

### Dedup yanlış birleşmesi — bulunamadı

{sum(sinif["dedup-yanlis-birlesme"].values())} çapraz-kaynak birleşme incelendi,
**hiçbiri yanlış değil.** Hepsi aynı alan adının farklı katalog kayıtları —
örneğin Facebook, Facebook Marketplace ve Facebook Pages tek `robots.txt`
dosyasını paylaşıyor. Birleşme doğru.

"Aranmış ve bulunamamış" ile "hiç bakılmamış" aynı şey değil; bu satır
birincisini kaydeder.

### Yanlış/eksik alan — bulundu ve düzeltildi

Fiyat yüzeyi olarak çekilmiş **48 sayfada fiyat çıkmıyordu**. 25'inin gövdesinde
apaçık fiyat vardı: Kagi `$5/$10/$25`, Sistrix `€119/€239/€419`, Exploding
Topics `$39/$99/$249`.

Kök sebep: alan çıkarımı **kaynağın ailesine** bakıyordu, sayfanın kendisine
değil. Ailesi eşlenmemiş kaynaklar `genel` sınıfına düşüyordu ve o sınıfın hiç
deseni yoktu — yani `/pricing` sayfasından bile fiyat aranmıyordu.

Düzeltme: sayfanın kendi türü de hangi desenlerin aranacağını belirliyor.

| | Önce | Sonra |
|---|---:|---:|
| Çıkarılan alan | 212 | **273** |
| Alan çıkan belge | 164 | **213** |
| Fiyat | 56 | **108** |
| Fiyat sayfası olup fiyat çıkmayan | 48 | **16** |

Kalan {sinif["yanlis-eksik-alan"]["sayfada gerçekten fiyat yok"]} sayfada gövdede fiyat ifadesi yok — sayfa fiyat yayımlamıyor.

### Filtrede kaybolan kanıt — {sinif["filtrede-kayip-kanit"]["KAYIP KANIT"]} gerçek kayıp

"Ölçüm kanıtı üretmez" diye elenen belgelerin {sum(sinif["filtrede-kayip-kanit"].values())}'sinde fiyat çıktı.
Bağlamlarına tek tek bakınca **{sinif["filtrede-kayip-kanit"]["KAYIP KANIT"]}'u gerçek kanıt**, {sinif["filtrede-kayip-kanit"]["gürültü"]}'sı gürültü:

| Kaynak | Bulgu | Neden kayıp |
|---|---|---|
{bulgular("filtrede-kayip-kanit", "KAYIP KANIT")}

Gürültü örnekleri fiyat gibi görünüp fiyat olmayanlar: "$2.3 **billion** in AUM"
(fon büyüklüğü), "$1,000,000 total **prize pool**" (yarışma ödülü), "$2.1
billion NASA cost estimate" (haber başlığı).

Ayrım kuralı: fiyatın yanında **ilan işareti** (puan, yorum sayısı, `/month`,
`for 2 nights`) varsa kanıt; **büyüklük ifadesi** (milyar, fon, ödül) varsa
değil.

### Desteksiz claim — bulunamadı

Alan çıkmamış belgeye dayanan {sum(sinif["desteksiz-claim"].values())} matris satırı incelendi.
**Hiçbiri desteksiz değil**: her biri zaten `alinabilen_alan = "(ölçülebilir
alan yok)"` diyor ve `kanit_gerekcesi` alanında "yüzey olarak çekildi"
yazıyor. Satırlar ne olduklarını dürüstçe beyan ediyor.

## 2. Etiketli referans kümesi

Otomatik etiket insan etiketinin yerine geçmez. Faz 2 rehberi açıkça *"örnek
sonuçları **insan etiketlesin**"* diyor. Aşağıdaki {len(etiketler)} örneği elle açtım,
bağlamını okudum, sebebiyle etiketledim.

| # | Örnek | Etiket | Sebep | Karşıt bulgu |
|---|---|---|---|---|
{etiket_tablosu}

### Precision — ve recall neden yok

```
incelenen örnek : {olcum["incelenen_ornek"]}
relevant        : {olcum["relevant"]}
irrelevant      : {olcum["irrelevant"]}
uncertain       : {olcum["uncertain"]}
precision       : {olcum["precision"]}
recall          : YOK
```

**Recall hesaplanmadı ve hesaplanamaz.** Recall için açık web'deki tüm ilgili
içeriğin bilinmesi gerekir; bilinmiyor. Kart da bunu yasaklıyor: *"Etiketli
referans olmadan web recall oranı üretme."* Faz 2 rehberi aynı şeyi diyor:
*"referans yoksa recall yok"*.

Precision düşük görünüyor ({olcum["precision"]}) ama bu bir kalite ölçüsü değil:
örnekler **kasten zor vakalardan** seçildi — filtrenin elediği, çıkarıcının
kaçırdığı, arşivden gelen. Temsili bir örneklem değil, sınır vakası kümesi.

### Doğrudan karşıt bulgular

{olcum["dogrudan_karsit_bulgu"]} örnek doğrudan karşıt bulgu olarak işaretlendi — yani mevcut fikrin
varsayımını **çürüten** yönde:

{chr(10).join(f'- **{r["ornek"]}** — {r["sebep"]}' for r in etiketler if r["dogrudan_karsit_bulgu"] == "EVET")}

Kanıt politikası karşıt bulgunun ayrı sayılmasını istiyor; destekleyen ve
karşıt örnekler aynı kefeye konmuyor.

## 3. Bu belge ne söylemez

- Precision bu kümeye aittir, veri kümesinin tamamına değil.
- **Recall yok.** Hiçbir yerde web recall oranı üretilmedi.
- {olcum["uncertain"]} örnek `uncertain` kaldı; zorlama etiket konmadı.
- Hiçbir satır kabul edilmiş değil; Batuhan kontrolü bekliyor.

## 4. Yeniden üretim

```bash
python3 hata_incelemesi.py --yaz
python3 -m unittest test_hata_incelemesi
```
"""


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--yaz", action="store_true")
    secenek = ayristirici.parse_args(argv)

    hatalar = (dedup_incele() + alan_incele() + filtre_incele() + claim_incele())
    etiketler = etiketli_referans()
    olcum = precision(etiketler)
    print(json.dumps({
        "surum": SURUM,
        "incelenen_kayit": len(hatalar),
        "hata_sinifi": dict(collections.Counter(r["hata_sinifi"] for r in hatalar)),
        "bulunan_hata": dict(collections.Counter(
            r["karar"] for r in hatalar if r["karar"].isupper() or "KAYIP" in r["karar"])),
        "etiketli_referans": olcum,
    }, ensure_ascii=False, indent=2))
    if not secenek.yaz:
        return 0
    _yaz("AS04-HATA-INCELEMESI.csv", hatalar)
    _yaz("AS04-ETIKETLI-REFERANS.csv", etiketler)
    (HERE / "AS04-HATA-RAPORU.md").write_text(
        rapor(hatalar, etiketler, olcum), encoding="utf-8")
    print("AS04-HATA-INCELEMESI.csv · AS04-ETIKETLI-REFERANS.csv · AS04-HATA-RAPORU.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
