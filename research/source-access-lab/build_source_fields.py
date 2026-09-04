"""Her kaynagin hangi anlamli alani hangi izinli yoldan saglayabilecegini belirler.

Onceki adimlarda kaynak icin soylenen cumle suydu: "bu siteden veri cekilir".
``ADAY-KATALOG.csv`` bunu ``arastirma_degeri = veri-var`` diye yaziyor. Cumle
arastirma icin yetersiz, cunku uc soruyu cevapsiz birakiyor:

* **Hangi alan?** "Veri" bir sey soylemez. Arastirma fiyat, yorum sayisi, puan,
  indirme adedi gibi **adi olan, tabloya konabilen** birimlerle yapilir. Gorev
  2'de kanit tanimlarken bu alanlari zaten ima etmistik ("ilk 20'nin toplam
  yorum hacmi") ama hicbir yerde o alanin o kaynaktan gerçekten alinabildigini
  yazmamistik. Bu dosya o bosluğu kapatir.
* **Hangi yol?** Ayni kaynak API'den, arama ucundan, HTML'den ya da arsiv
  kopyasindan gelebilir. Alan ayni olsa bile yol degisince tazelik, maliyet ve
  izin degisir.
* **Izinli mi?** Kritik kelime budur. Bir yolun **calismasi** ile o yolu
  **kullanma hakkimizin olmasi** ayni sey degildir. robots.txt bir yolu
  kapatmisken sayfanin yine de inmesi mumkundur; inmis olmasi izin vermez.

Alanlar kaynak basina elle yazilmaz, **kaynak grubundan** turetilir -- gorev
2'deki kanit da ayni sekilde gruba baglidir, boylece iki dosya ayni eksende
kalir ve envanter buyudugunde tek yerde guncellenir.

Guven iki degerlidir ve ikisi asla karistirilmaz:

* ``dogrulandi`` — alan, indirilmis artefaktin **icinde goruldu**. Dort kaynaktan
  gelir: API yanitindaki anahtarlar, HTML icindeki schema.org JSON-LD, RSS
  etiketleri ve sitemap'teki ``lastmod``.
* ``beyan`` — alan kaynak grubunun dogasi geregi bekleniyor ama artefakta
  bakilarak gosterilemedi. ``neden_dogrulanmadi`` sutunu **neden**
  gosterilemedigini yazar; cogu durumda elimizde yalnizca anasayfa vardir ve
  alani tasiyan ic sayfa hic cekilmemistir.

Ikinci sinif bir eksiklik itirafidir, gizlenmez: ``beyan`` satirlarinin listesi
dogrudan bir sonraki cekim isinin gorev listesidir.
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

# --------------------------------------------------------------------------
# Kontrollu alan sozlugu. "Anlamli" olmanin ikinci sarti karsilastirilabilir
# olmaktir: bir kaynak 'yorum_sayisi', digeri 'review_count' derse iki kaynak
# birlestirilemez. Alan adi bu sozlukten disari cikamaz.
# --------------------------------------------------------------------------
ALANLAR: dict[str, tuple[str, str]] = {
    # alan -> (tur, ne ise yarar)
    "urun_sayisi": ("sayi", "Kategoride kaç ürün/uygulama listeleniyor — arz yoğunluğu"),
    "yorum_sayisi": ("sayi", "Kullanıcı yorumu adedi — kullanım davranışının izi"),
    "puan": ("sayi", "Ortalama değerlendirme puanı"),
    "fiyat": ("para", "Tekil ürün fiyatı"),
    "fiyat_bandi": ("metin", "Fiyatlandırma katmanları ve aralıkları"),
    "indirme_sayisi": ("sayi", "İndirme ya da kurulum adedi"),
    "siralama": ("sayi", "Kategori içi sıra"),
    "son_guncelleme": ("tarih", "İçeriğin en son değiştiği tarih — canlılık göstergesi"),
    "yayin_tarihi": ("tarih", "Kaydın yayımlandığı tarih"),
    "baslik": ("metin", "Kayıt başlığı"),
    "aciklama_metni": ("metin", "Serbest metin açıklama"),
    "saglayici_adi": ("metin", "Ürünü/hizmeti sunan taraf"),
    "kullanici_sikayeti": ("metin", "Şikâyet ifadeleri — farklılaşmanın kaynağı"),
    "arama_hacmi": ("sayi", "Anahtar kelime arama adedi"),
    "trend_serisi": ("seri", "Zaman içindeki değişim eğrisi"),
    "ilan_sayisi": ("sayi", "İş ilanı adedi — kurumsal talebin dolaylı ölçüsü"),
    "istatistik_serisi": ("seri", "Resmî istatistik zaman serisi"),
    "destekci_sayisi": ("sayi", "Kitle fonlamasında destekleyen kişi adedi"),
    "toplanan_tutar": ("para", "Toplanan/hedeflenen tutar"),
    "lisans": ("metin", "Lisans modeli"),
    "bagimlilik_sayisi": ("sayi", "Pakete bağlı proje adedi — benimsenme ölçüsü"),
    "mevzuat_metni": ("metin", "Bağlayıcı düzenleme metni"),
    "yatirim_olayi": ("olay", "Tarihli yatırım/satın alma olayı"),
    "kayit_sayisi": ("sayi", "Dizindeki kayıt adedi"),
    "konum": ("metin", "Coğrafi konum bilgisi"),
    "etiket": ("metin", "Kategori/etiket bilgisi"),
    "url": ("metin", "Kaydın adresi — daha derin çekim için giriş noktası"),
}

# Kaynak grubu -> o gruptan beklenen alanlar. Grup bazli tutulur cunku gorev
# 2'deki kanit da gruba baglidir; ikisi ayni eksende kalmali.
GRUP_ALANLARI: dict[str, tuple[str, ...]] = {
    "Mobil uygulama mağazaları": (
        "urun_sayisi", "yorum_sayisi", "puan", "fiyat", "indirme_sayisi",
        "siralama", "son_guncelleme", "kullanici_sikayeti", "saglayici_adi"),
    "SaaS, yazılım ve hizmet inceleme siteleri": (
        "urun_sayisi", "yorum_sayisi", "puan", "fiyat_bandi",
        "kullanici_sikayeti", "saglayici_adi", "etiket"),
    "Fiyat, teknoloji ve pazar sinyali karşılaştırma kaynakları": (
        "fiyat", "fiyat_bandi", "urun_sayisi", "trend_serisi", "saglayici_adi"),
    "İş ilanları ve yetenek talebi": (
        "ilan_sayisi", "baslik", "konum", "yayin_tarihi", "saglayici_adi"),
    "Yazılım geliştirici ve teknik topluluklar": (
        "indirme_sayisi", "bagimlilik_sayisi", "lisans", "son_guncelleme",
        "kullanici_sikayeti", "baslik", "url"),
    "Tarayıcı, e-ticaret ve CMS eklenti mağazaları": (
        "urun_sayisi", "indirme_sayisi", "puan", "yorum_sayisi",
        "son_guncelleme", "saglayici_adi"),
    "Yapay zekâ modeli, veri seti ve agent ekosistemi": (
        "urun_sayisi", "indirme_sayisi", "lisans", "son_guncelleme",
        "etiket", "url"),
    "Oyun dikeyi": (
        "urun_sayisi", "puan", "yorum_sayisi", "fiyat", "yayin_tarihi", "etiket"),
    "Yerel işletme, harita ve hizmet dizinleri": (
        "kayit_sayisi", "puan", "yorum_sayisi", "konum", "saglayici_adi", "fiyat_bandi"),
    "Dijital ürün ve şablon pazar yerleri": (
        "urun_sayisi", "fiyat", "puan", "saglayici_adi", "etiket"),
    "Kitle fonlaması platformları": (
        "destekci_sayisi", "toplanan_tutar", "yayin_tarihi", "baslik", "etiket"),

    # Dikeyler
    "Sağlık ve biyoteknoloji dikeyi": (
        "kayit_sayisi", "baslik", "yayin_tarihi", "mevzuat_metni", "istatistik_serisi"),
    "Finans ve fintech dikeyi": (
        "mevzuat_metni", "istatistik_serisi", "saglayici_adi", "yayin_tarihi"),
    "Eğitim dikeyi": ("istatistik_serisi", "kayit_sayisi", "baslik", "konum"),
    "Gayrimenkul ve inşaat dikeyi": (
        "ilan_sayisi", "fiyat", "istatistik_serisi", "konum"),
    "Seyahat, konaklama ve mobilite dikeyi": (
        "fiyat", "puan", "yorum_sayisi", "kayit_sayisi", "konum"),
    "Yeme-içme ve teslimat dikeyi": (
        "kayit_sayisi", "puan", "yorum_sayisi", "fiyat", "konum"),
    "Regülasyon ve hukuk kaynakları": (
        "mevzuat_metni", "yayin_tarihi", "baslik", "url"),
    "Türkiye startup ve teknoloji ekosistemi": (
        "yatirim_olayi", "saglayici_adi", "yayin_tarihi", "baslik"),

    # Ortak havuz
    "Genel web arama ve keşif": ("url", "baslik", "aciklama_metni"),
    "Haber, basın ve sektör yayınları": (
        "yatirim_olayi", "yayin_tarihi", "baslik", "aciklama_metni", "url"),
    "Şirket, yatırım ve startup verisi": (
        "yatirim_olayi", "saglayici_adi", "yayin_tarihi", "kayit_sayisi"),
    "Trafik, SEO, anahtar kelime ve trend": (
        "arama_hacmi", "trend_serisi", "url", "etiket"),
    "Sosyal ağlar ve açık topluluklar": (
        "kullanici_sikayeti", "baslik", "yayin_tarihi", "etiket"),
    "Akademik araştırma ve bilimsel yayınlar": (
        "baslik", "yayin_tarihi", "aciklama_metni", "url"),
    "Patent ve marka": ("kayit_sayisi", "baslik", "yayin_tarihi", "saglayici_adi"),
    "Kamu verisi ve istatistik": ("istatistik_serisi", "trend_serisi", "yayin_tarihi"),
    "Anket, birincil doğrulama ve kullanıcı araştırması platformları": (
        "kullanici_sikayeti", "kayit_sayisi", "fiyat_bandi"),
    "Domain, DNS, sertifika ve web footprint": (
        "kayit_sayisi", "son_guncelleme", "saglayici_adi", "url"),
    "Reklam kütüphaneleri ve pazarlama sinyalleri": (
        "kayit_sayisi", "yayin_tarihi", "saglayici_adi", "aciklama_metni"),
    "Ürün lansmanı ve startup toplulukları": (
        "urun_sayisi", "puan", "yorum_sayisi", "yayin_tarihi", "saglayici_adi"),
}

# Grup adi her zaman icerigini dogru anlatmaz. 'Yazilim gelistirici ve teknik
# topluluklar' basligi uc ayri turu birlikte tutuyor: paket kayitlari (npm,
# PyPI), soru-cevap siteleri (Stack Overflow) ve kod barindirma (GitHub). Grup
# alanlarini oldugu gibi uygulamak Stack Overflow'un 'bagimlilik_sayisi'
# verdigini iddia etmek olurdu -- bu dogrulanmamis degil, yanlistir. Asagidaki
# kaynaklar grup listesi yerine kendi listesini kullanir.
KAYNAK_ALAN_ISTISNASI: dict[str, tuple[str, ...]] = {
    # Soru-cevap ve tartisma: paket indirme/bagimlilik vermezler
    **{ad: ("kullanici_sikayeti", "baslik", "yayin_tarihi", "son_guncelleme",
            "etiket", "url", "kayit_sayisi")
       for ad in ("Stack Overflow", "Ask Ubuntu", "Server Fault", "Super User",
                  "Stack Exchange", "Software Engineering Stack Exchange",
                  "Hacker News", "Lobsters", "Slashdot", "Indie Hackers",
                  "DZone", "Dev.to", "Hashnode", "CodeProject", "InfoQ",
                  "Replit Community")},
    # Kod barindirma: indirme sayisi yayinlamaz, lisans ve guncellik verir
    **{ad: ("lisans", "son_guncelleme", "baslik", "url", "kayit_sayisi",
            "saglayici_adi")
       for ad in ("GitHub", "GitLab", "Bitbucket", "Codeberg")},
}

# --------------------------------------------------------------------------
# Izin siniflari. Sira onemlidir: ustteki daha guclu bir haktir.
# --------------------------------------------------------------------------
IZIN_ACIKLAMA: dict[str, str] = {
    "api-acik": "Belgelenmiş API ucu var; programatik erişim için tasarlanmış yol",
    "robots-izinli": "robots.txt ön kontrolünden geçti ve içerik canlı indirildi",
    "arsiv-kopyasi": "Yalnız Common Crawl kopyası; arşiv robots'a uyar, veri güncel değil",
    "yol-yok": "Sorgulanabilir bir yol bulunamadı",
    "yasak": "robots.txt bu kaynağı kapatıyor — denenmedi",
}

# Artefaktta gorulen kanittan kanonik alana esleme.
JSONLD_ALAN: dict[str, str] = {
    "aggregateRating": "puan", "ratingValue": "puan", "reviewCount": "yorum_sayisi",
    "offers": "fiyat", "price": "fiyat", "priceRange": "fiyat_bandi",
    "datePublished": "yayin_tarihi", "dateModified": "son_guncelleme",
    "itemListElement": "kayit_sayisi", "address": "konum", "name": "baslik",
    "description": "aciklama_metni", "url": "url", "author": "saglayici_adi",
    "downloadUrl": "url", "license": "lisans", "keywords": "etiket",
}
API_ALAN: dict[str, str] = {
    "answer_count": "kayit_sayisi", "score": "puan", "creation_date": "yayin_tarihi",
    "last_activity_date": "son_guncelleme", "title": "baslik", "tags": "etiket",
    "link": "url", "downloads": "indirme_sayisi", "license": "lisans",
    "stargazers_count": "puan", "updated_at": "son_guncelleme",
    "description": "aciklama_metni", "published_date": "yayin_tarihi",
}
RSS_ALAN: dict[str, str] = {
    "pubDate": "yayin_tarihi", "updated": "son_guncelleme", "title": "baslik",
    "link": "url", "category": "etiket", "description": "aciklama_metni",
    "author": "saglayici_adi",
}

# Olcum alanlari: arastirmanin kanitini tasiyanlar. Etiket/kimlik alanlarindan
# ayrilir cunku dogrulama sartlari farklidir (asagida).
OLCUM_ALANLARI: frozenset[str] = frozenset({
    "urun_sayisi", "yorum_sayisi", "puan", "fiyat", "fiyat_bandi",
    "indirme_sayisi", "siralama", "arama_hacmi", "ilan_sayisi",
    "destekci_sayisi", "toplanan_tutar", "bagimlilik_sayisi", "kayit_sayisi",
    "istatistik_serisi", "trend_serisi",
})

# schema.org'da sitenin KENDINI tarif ettigi turler. Booksy'nin anasayfasindaki
# aggregateRating, Booksy uygulamasinin kendi puanidir (4.9 / 840 bin oy) --
# Booksy'de listelenen bir kuaforun puani degil. Ikisini ayirmadan 'Booksy puan
# veriyor' demek arastirma acisindan yanlis olur: bize listelenen kaydin puani
# lazim, sitenin kendi magaza puani degil. Bu yuzden kendini tarif eden bir
# nesneden yalnizca kimlik alanlari (ad, adres) dogrulanir, olcum alani degil.
KENDINI_TARIF: frozenset[str] = frozenset({
    "Organization", "WebSite", "WebPage", "MobileApplication",
    "SoftwareApplication", "NewsMediaOrganization", "Corporation",
    "LocalBusiness", "BreadcrumbList", "FAQPage", "SiteNavigationElement",
})

# Deger nesneleri: kendi @type'lari vardir ama bagimsiz bir varlik degildirler.
# Bir MobileApplication icindeki AggregateRating, hala o uygulamanin puanidir --
# ic nesnenin turu ust baglami ezmemeli, yoksa 'sitenin kendi puani' ayrimi
# ic nesnede kaybolur.
DEGER_NESNESI: frozenset[str] = frozenset({
    "AggregateRating", "Rating", "Offer", "AggregateOffer", "PriceSpecification",
    "QuantitativeValue", "PostalAddress", "ImageObject", "MonetaryAmount",
})

LDJSON = re.compile(
    rb'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)


def izin_durumu(satir: dict[str, str], yuzey: dict[str, str],
                yontemler: set[str]) -> str:
    """Yolun calismasi degil, kullanma hakkimizin olmasi belirleyicidir."""
    if satir.get("sebep") == "robots_disallowed":
        return "yasak"
    if yuzey.get("api_ucu") or any(
            y not in {"root_html", "entry_url", "sitemap_xml", "rss_feed",
                      "rss_link_discovery", "robots_preflight",
                      "common_crawl_warc", "rel_next_pagination"}
            for y in yontemler):
        return "api-acik"
    canli = yontemler - {"common_crawl_warc", "robots_preflight"}
    if canli:
        return "robots-izinli"
    if "common_crawl_warc" in yontemler:
        return "arsiv-kopyasi"
    return "yol-yok"


def artefakt_kanitlari(dizin: list[dict[str, str]],
                       kok: Path) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Indirilmis dosyalarin icine bakip hangi alanin gercekten gorulduugunu toplar.

    Dondurulen ikinci sozluk, alanin **hangi artefaktta** goruldugunu tutar;
    dogrulama iddiasinin izi surulebilir olmali.
    """
    kanit: dict[str, set[str]] = collections.defaultdict(set)
    nereden: dict[str, set[str]] = collections.defaultdict(set)

    def ekle(ad: str, alan: str, kaynak: str) -> None:
        if alan in ALANLAR:
            kanit[ad].add(alan)
            nereden[f"{ad}|{alan}"].add(kaynak)

    for satir in dizin:
        if satir.get("sonuc") != "ok" or not satir["ad"]:
            continue
        yol = Path(satir["dosya"])
        if not yol.is_absolute():
            yol = kok / yol
        if not yol.exists():
            continue
        ad, yontem = satir["ad"], satir["yontem"]
        try:
            ham = yol.read_bytes()[:400_000]
        except OSError:
            continue

        if yontem == "sitemap_xml":
            metin = ham.decode("utf-8", "replace")
            if "<loc" in metin:
                ekle(ad, "url", "sitemap:loc")
            if "<lastmod" in metin:
                ekle(ad, "son_guncelleme", "sitemap:lastmod")
            continue

        if yontem == "rss_feed":
            metin = ham.decode("utf-8", "replace")
            for etiket, alan in RSS_ALAN.items():
                if f"<{etiket}" in metin:
                    ekle(ad, alan, f"rss:{etiket}")
            continue

        if "json" in satir["mime"].lower():
            try:
                veri = json.loads(ham.decode("utf-8", "replace"))
            except (ValueError, UnicodeDecodeError):
                continue
            for anahtar in _json_anahtarlari(veri):
                if anahtar in API_ALAN:
                    ekle(ad, API_ALAN[anahtar], f"api:{anahtar}")
            continue

        # HTML: schema.org JSON-LD gomulu yapisal veri
        for blok in LDJSON.findall(ham)[:4]:
            try:
                veri = json.loads(blok.decode("utf-8", "replace"))
            except (ValueError, UnicodeDecodeError):
                continue
            for tur, anahtar in _jsonld_anahtarlari(veri):
                alan_adi = JSONLD_ALAN.get(anahtar)
                if not alan_adi:
                    continue
                kendini = tur in KENDINI_TARIF
                if kendini and alan_adi in OLCUM_ALANLARI:
                    # Sitenin kendi puani/fiyati arastirma kaniti degildir.
                    continue
                ekle(ad, alan_adi, f"json-ld:{anahtar}" + ("" if not kendini else "(kimlik)"))
    return kanit, nereden


def _jsonld_anahtarlari(veri: Any, tur: str = "", derinlik: int = 0):
    """(icinde bulundugu @type, anahtar) ciftlerini uretir.

    Ic ice nesnede en yakin @type gecerlidir: bir Organization icindeki ItemList
    listelemedir, Organization'in kendi tarifi degil.
    """
    if derinlik > 6:
        return
    if isinstance(veri, dict):
        kendi = veri.get("@type")
        if isinstance(kendi, list):
            kendi = kendi[0] if kendi else None
        gecerli = tur
        if isinstance(kendi, str) and kendi not in DEGER_NESNESI:
            gecerli = kendi
        for anahtar, deger in veri.items():
            yield gecerli, anahtar
            yield from _jsonld_anahtarlari(deger, gecerli, derinlik + 1)
    elif isinstance(veri, list):
        for oge in veri[:20]:
            yield from _jsonld_anahtarlari(oge, tur, derinlik + 1)


def _json_anahtarlari(veri: Any, derinlik: int = 0) -> set[str]:
    """Ic ice yapida gecen tum anahtar adlarini toplar."""
    if derinlik > 6:
        return set()
    bulunan: set[str] = set()
    if isinstance(veri, dict):
        for anahtar, deger in veri.items():
            bulunan.add(anahtar)
            bulunan |= _json_anahtarlari(deger, derinlik + 1)
    elif isinstance(veri, list):
        for oge in veri[:20]:
            bulunan |= _json_anahtarlari(oge, derinlik + 1)
    return bulunan


def dogrulanmama_sebebi(yontemler: set[str], izin: str) -> str:
    """Alanin neden gosterilemedigi; 'beyan' etiketini savunmasiz birakmamak icin."""
    if izin == "yasak":
        return "Kaynak robots.txt ile kapalı; hiçbir artefakt alınmadı"
    if izin == "api-acik":
        return ("Elimizdeki API yanıtında bu alan geçmiyor; başka bir uç ya da "
                "parametre gerekebilir")
    if izin == "yol-yok":
        return "Sorgulanabilir yol yok; alanı taşıyan sayfaya ulaşılamıyor"
    if not yontemler - {"robots_preflight"}:
        return "Yalnız robots.txt ön kontrolü yapıldı; içerik indirilmedi"
    if yontemler <= {"sitemap_xml", "robots_preflight", "rss_link_discovery"}:
        return "Elimizde yalnız sitemap var; alanı taşıyan sayfa çekilmedi"
    if "common_crawl_warc" in yontemler and not (
            yontemler - {"common_crawl_warc", "robots_preflight"}):
        return "Yalnız arşiv kopyası var; sayfa yapısı güncel olmayabilir"
    return "Elimizde anasayfa artefaktı var; alanı taşıyan iç sayfa çekilmedi"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=HERE / "KAYNAK-DEFTERI.csv")
    parser.add_argument("--index", type=Path, default=HERE / "ARTEFAKT-DIZINI.csv")
    parser.add_argument("--surfaces", type=Path, default=HERE / "ARAMA-YUZEYLERI.csv")
    parser.add_argument("--kategori-kaynak", type=Path, default=HERE / "KATEGORI-KAYNAK.csv")
    parser.add_argument("--kategori-soru", type=Path, default=HERE / "KATEGORI-SORU.csv")
    parser.add_argument("--out", type=Path, default=HERE / "KAYNAK-ALAN.csv")
    args = parser.parse_args()

    def oku(yol: Path) -> list[dict[str, str]]:
        with yol.open(encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    defter = {r["ad"]: r for r in oku(args.ledger)}
    dizin = oku(args.index)
    yuzey = {r["ad"]: r for r in oku(args.surfaces)}
    kategori_kaynak = oku(args.kategori_kaynak)
    kategori_soru = oku(args.kategori_soru)

    bilinmeyen = {g.strip() for r in kategori_kaynak
                  for g in r["kaynak_grubu"].split(" | ")} - set(GRUP_ALANLARI)
    if bilinmeyen:
        # Alani tanimsiz grup sessizce bos gecilirse o gruptaki kaynaklar
        # katalogda 'alan yok' gorunur -- yanlis olur, karar elle verilmelidir.
        raise SystemExit(f"alani tanimsiz kaynak grubu: {sorted(bilinmeyen)}")

    # Kaynak -> hangi yontemlerle icerik alindi
    yontemler: dict[str, set[str]] = collections.defaultdict(set)
    for satir in dizin:
        if satir.get("sonuc") == "ok" and satir["ad"]:
            yontemler[satir["ad"]].add(satir["yontem"])

    kanit, nereden = artefakt_kanitlari(dizin, args.index.parent)

    # Kaynak -> gruplari ve o gruplarin verdigi alanlar
    kaynak_gruplari: dict[str, set[str]] = collections.defaultdict(set)
    for satir in kategori_kaynak:
        for grup in satir["kaynak_grubu"].split(" | "):
            kaynak_gruplari[satir["kaynak"]].add(grup.strip())

    # Alan -> hangi sorulara hizmet ediyor (grup uzerinden gorev 2'ye baglanir)
    grup_soru: dict[str, set[str]] = collections.defaultdict(set)
    for satir in kategori_soru:
        grup_soru[satir["kanit_kaynak_grubu"]].add(satir["soru_id"])

    satirlar: list[dict[str, Any]] = []
    for ad, gruplar in sorted(kaynak_gruplari.items()):
        d = defter.get(ad, {})
        y = yuzey.get(ad, {})
        yon = yontemler.get(ad, set())
        izin = izin_durumu(d, y, yon)
        yol = y.get("en_iyi_yol") or "yok"
        gorulen = kanit.get(ad, set())
        for grup in sorted(gruplar):
            alanlar = KAYNAK_ALAN_ISTISNASI.get(ad) or GRUP_ALANLARI[grup]
            for alan in alanlar:
                dogru = alan in gorulen
                satirlar.append({
                    "source_id": d.get("source_id", ""), "ad": ad,
                    "alan": alan, "alan_turu": ALANLAR[alan][0],
                    "alan_aciklama": ALANLAR[alan][1],
                    "kaynak_grubu": grup, "yol": yol,
                    "izin_durumu": izin, "izin_aciklama": IZIN_ACIKLAMA[izin],
                    "guven": "dogrulandi" if dogru else "beyan",
                    "dogrulama_izi": ", ".join(sorted(nereden.get(f"{ad}|{alan}", set()))),
                    "neden_dogrulanmadi": "" if dogru else dogrulanmama_sebebi(yon, izin),
                    "hizmet_ettigi_soru": ", ".join(sorted(grup_soru.get(grup, set()))),
                })

    # Ayni kaynak-alan ikilisi iki gruptan gelebilir; dogrulanmis olan kazanir.
    birlesik: dict[tuple[str, str], dict[str, Any]] = {}
    for satir in satirlar:
        anahtar = (satir["ad"], satir["alan"])
        mevcut = birlesik.get(anahtar)
        if mevcut is None:
            birlesik[anahtar] = satir
            continue
        if mevcut["guven"] == "beyan" and satir["guven"] == "dogrulandi":
            satir["kaynak_grubu"] = f"{mevcut['kaynak_grubu']} | {satir['kaynak_grubu']}"
            birlesik[anahtar] = satir
        elif satir["kaynak_grubu"] not in mevcut["kaynak_grubu"]:
            mevcut["kaynak_grubu"] += f" | {satir['kaynak_grubu']}"
            mevcut["hizmet_ettigi_soru"] = ", ".join(sorted(
                set(filter(None, mevcut["hizmet_ettigi_soru"].split(", "))) |
                set(filter(None, satir["hizmet_ettigi_soru"].split(", ")))))
    satirlar = sorted(birlesik.values(),
                      key=lambda r: (r["izin_durumu"], r["ad"].casefold(), r["alan"]))

    with args.out.open("w", newline="", encoding="utf-8") as handle:
        yazici = csv.DictWriter(handle, fieldnames=list(satirlar[0]))
        yazici.writeheader()
        yazici.writerows(satirlar)

    dogrulanan = [r for r in satirlar if r["guven"] == "dogrulandi"]
    print(json.dumps({
        "cikti": str(args.out),
        "satir": len(satirlar),
        "kaynak": len({r["ad"] for r in satirlar}),
        "alan": len({r["alan"] for r in satirlar}),
        "izin_durumu": collections.Counter(r["izin_durumu"] for r in satirlar).most_common(),
        "dogrulandi": len(dogrulanan),
        "dogrulanan_kaynak": len({r["ad"] for r in dogrulanan}),
        "en_cok_dogrulanan_alan": collections.Counter(
            r["alan"] for r in dogrulanan).most_common(5),
        "dogrulanmama_sebebi": collections.Counter(
            r["neden_dogrulanmadi"] for r in satirlar if r["neden_dogrulanmadi"]).most_common(),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
