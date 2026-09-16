"""Dort ekseni ayri tutan kategori sozlugu ve artefakta dayali pilot etiketleme.

Simdiye kadar etiketleme **cikarimla** yapildi: site listesindeki basliklardan
turetildi, kaynagin adina ve grubuna bakildi. Bu adim bunu degistirir: her
etiket **acilmis bir artefakta** ya da **acik bir eksik-veri kaydina** baglanir.
Site adina bakarak etiket verilmez.

Dort eksen ayri tutulur, cunku karistirilmalari sistematik hataya yol acar:

* **Urun tipi** — arastirilan urun ne (B2B SaaS, developer tool, marketplace...).
  Kaynagin ne oldugu degil, arastirmanin konusu.
* **Kaynak ailesi** — kaynak ne tur bir yayin (uygulama magazasi, inceleme
  sitesi, is ilani...). Bir inceleme sitesi B2B SaaS arastirmasinda da
  marketplace arastirmasinda da kullanilir; ailesi degismez.
* **Belge turu** — elimizdeki **dosyanin** ne oldugu: ana sayfa mi, liste
  sayfasi mi, yorum sayfasi mi, sitemap mi. Bu ancak dosya acilarak bilinir.
* **Arastirma niyeti** — o belgeden hangi soruya cevap araniyor.

Ayrimin karsiligi sudur: G2 (kaynak ailesi = inceleme sitesi) hem B2B SaaS hem
data/analytics urunu arastirmasinda kullanilir; elimizdeki G2 dosyasi bir ana
sayfa ise (belge turu) hicbir niyet icin kanit uretmez. Uc eksen ayri olmadan
bu cumle kurulamaz.

Kabul kriterinin geregi: **sitemap ve arama sonucu aday kesiftir**, kanit
degildir; icerik bulunmayan yerde yorum ya da fiyat verisi varsayilmaz.
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

HERE = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# EKSEN 1 — URUN TIPI
# Kanonik gorev metnindeki (tasks/ayselin-task/README.md, T01) aile listesi
# esas alinir. Bizim gorev 1'de urettigimiz kategoriler bu eksene eslenir;
# esleme URUN_TIPI_ESLEME'de acikca yazilidir.
# --------------------------------------------------------------------------
URUN_TIPI: dict[str, dict[str, Any]] = {
    "b2b-saas": {
        "ad": "B2B SaaS",
        "tanim": "İşletmelerin abonelikle kullandığı, kurumsal satın almaya konu web yazılımı",
        "dahil": "CRM, faturalama, İK yazılımı, proje yönetimi",
        "haric": "Bireysel kullanıcıya satılan mobil uygulama; ücretsiz açık kaynak kütüphane",
        "hedef_kullanici": "İşletme; satın alma kararı departman ya da yönetim düzeyinde",
        "satin_alma": "Abonelik, koltuk başına ya da kullanım bazlı",
    },
    "developer-tool": {
        "ad": "Developer tool / API / agent",
        "tanim": "Geliştiricinin kendi ürününe kattığı kütüphane, SDK, API ya da agent",
        "dahil": "npm paketi, ödeme API'si, model/agent altyapısı, CLI aracı",
        "haric": "Son kullanıcıya satılan uygulama; geliştiricilerin kullandığı ama ürüne girmeyen SaaS",
        "hedef_kullanici": "Geliştirici; karar çoğu zaman teknik ekipte",
        "satin_alma": "Ücretsiz/açık kaynak, kullanım bazlı ya da kurumsal lisans",
    },
    "consumer-mobile-web": {
        "ad": "Consumer mobile / web ürünü",
        "tanim": "Son kullanıcıya doğrudan sunulan mobil uygulama ya da web ürünü",
        "dahil": "Sağlık takip uygulaması, bulmaca oyunu, not tutma uygulaması",
        "haric": "İşletmeye satılan panel; geliştirici kütüphanesi",
        "hedef_kullanici": "Birey; karar tek kişide",
        "satin_alma": "Ücretsiz, uygulama içi satın alma ya da bireysel abonelik",
    },
    "marketplace": {
        "ad": "Two-sided marketplace",
        "tanim": "Arz ve talebi buluşturan, iki taraflı ağ etkisi olan platform",
        "dahil": "Freelancer platformu, ikinci el pazar yeri, eklenti mağazası",
        "haric": "Tek taraflı e-ticaret mağazası; yalnız içerik yayınlayan site",
        "hedef_kullanici": "İki ayrı taraf; her biri ayrı araştırma gerektirir",
        "satin_alma": "Komisyon, listeleme ücreti",
    },
    "local-service": {
        "ad": "Local-service platform",
        "tanim": "Belirli bir coğrafyada hizmet arz ve talebini eşleştiren ürün",
        "dahil": "Randevu sistemi, usta bulma, yerel teslimat",
        "haric": "Coğrafyadan bağımsız SaaS; küresel pazar yeri",
        "hedef_kullanici": "Yerel işletme ve o bölgedeki tüketici",
        "satin_alma": "Abonelik ya da işlem başına komisyon",
    },
    "ecommerce-enablement": {
        "ad": "E-commerce enablement",
        "tanim": "E-ticareti mümkün kılan yazılım; ürünü kendisi satmaz",
        "dahil": "Mağaza altyapısı, ödeme/kargo entegrasyonu, stok yönetimi",
        "haric": "Fiziksel ürün satan mağazanın kendisi",
        "hedef_kullanici": "Satıcı işletme",
        "satin_alma": "Abonelik ya da işlem yüzdesi",
    },
    "data-analytics": {
        "ad": "Data / analytics ürünü",
        "tanim": "Veri toplayan, işleyen ya da ölçüm sunan ürün",
        "dahil": "Trafik analitiği, pazar istihbaratı, BI paneli",
        "haric": "Veriyi yalnız kendi işinde kullanan operasyonel yazılım",
        "hedef_kullanici": "Analist, pazarlamacı, yönetim",
        "satin_alma": "Abonelik, veri hacmi bazlı",
    },
    "regulated-vertical": {
        "ad": "Regüle dikey yazılım",
        "tanim": "Yasal düzenlemeye tabi bir alanda çalışan yazılım",
        "dahil": "Sağlık kaydı yazılımı, fintech, hukuk teknolojisi",
        "haric": "Aynı sektöre satılan ama düzenlemeye tabi olmayan araç",
        "hedef_kullanici": "Düzenlemeye tabi kurum",
        "satin_alma": "Kurumsal lisans; uyum maliyeti ayrı kalem",
    },
}

# Gorev 1'de uretilen kategorilerin bu eksene eslenmesi.
#
# Kanonik liste urun tipi eksenini tanimlar; gorev 1'in kategorileri ayni
# ekseni farkli kesen eski bir denemedir. Esleme bir gecis tablosudur, iki
# taksonomiyi uzlastirma cabasi degil: uyusmayan yerde **kanonik liste
# gecerlidir** ve eski kategorinin nasil boluneceği asagida yazilidir.
URUN_TIPI_ESLEME: dict[str, tuple[str, ...]] = {
    "b2b-web-yazilimi": ("b2b-saas",),
    "gelistirici-araci": ("developer-tool",),
    "yapay-zeka-urunu": ("developer-tool",),
    "mobil-uygulama": ("consumer-mobile-web",),
    "yerel-hizmet": ("local-service",),
    # Bir oyun tuketici urunudur. Kanonik listede ayri bir oyun tipi
    # olmamasi bir eksik degil, bilincli bir kesimdir: oyunun arastirma
    # niyeti tuketici uruntununkiyle aynidir (talep, doygunluk, odeme
    # istegi). Kaynak paketinin farkli olmasi urun tipini degil KAYNAK
    # AILESI eksenini ilgilendirir -- oyun dikeyi zaten ayri bir ailedir.
    "oyun": ("consumer-mobile-web",),
    # Eklenti URUNU ile eklenti MAGAZASI farkli seylerdir. Bir WordPress
    # eklentisi gelistirmek pazar yeri kurmak degildir; o pazar yerinde
    # satilan urundur. Tipi, hangi platformda kime satildigina gore
    # belirlenir ve bu bir coklu etiket durumudur.
    "eklenti-entegrasyon": ("b2b-saas", "ecommerce-enablement",
                            "consumer-mobile-web"),
}

# Coklu esleme durumunda hangisinin secilecegini soyleyen kural. Karar
# mentore birakilmaz; olcute baglanir.
ESLEME_KURALI: dict[str, str] = {
    "eklenti-entegrasyon": (
        "Barındıran platformun alıcısına bakılır: işletme yazılımına eklenti "
        "(Atlassian, Slack) → b2b-saas; e-ticaret platformuna eklenti "
        "(Shopify, WooCommerce) → ecommerce-enablement; tarayıcı eklentisi "
        "→ consumer-mobile-web. Platform belirsizse ürün tipi 'belirlenemedi' "
        "yazılır, tahmin edilmez."),
    "oyun": (
        "Tek eşleme; oyunun ayırt ediciliği ürün tipinde değil kaynak "
        "ailesinde taşınır (oyun dikeyi ailesi)."),
}

# --------------------------------------------------------------------------
# EKSEN 3 — BELGE TURU
# Elimizdeki DOSYANIN ne oldugu. Ancak acarak bilinir; kaynagin adindan
# cikarilamaz. Her tur icin hangi sinyalin kanit sayildigi asagida yazili.
# --------------------------------------------------------------------------
BELGE_TURU: dict[str, dict[str, str]] = {
    "ana-sayfa": {
        "tanim": "Kaynağın kök ya da tanıtım sayfası; kayıt listesi taşımaz",
        "kanit": "URL yolu kök, JSON-LD yalnız Organization/WebSite, liste işareti yok",
        "niyet_degeri": "Kaynağın varlığını doğrular; ölçüm kanıtı üretmez",
    },
    "liste-sayfasi": {
        "tanim": "Birden çok kaydı sıralayan dizin ya da kategori sayfası",
        "kanit": ("En az 5 itemListElement girdisi. Tek bir ItemList yeterli "
                  "değildir: gezinme menüleri de ItemList olarak işaretlenir"),
        "niyet_degeri": "Arz yoğunluğu ve rakip listesi için kullanılabilir",
    },
    "kayit-sayfasi": {
        "tanim": "Tek bir ürün, uygulama ya da işletmenin sayfası",
        "kanit": "JSON-LD Product/SoftwareApplication/LocalBusiness tekil nesne",
        "niyet_degeri": "Puan, fiyat ve sağlayıcı alanları buradan gelir",
    },
    "inceleme-sayfasi": {
        "tanim": "Kullanıcı yorumlarının gövdesini taşıyan sayfa",
        "kanit": ("En az 3 Review nesnesi. Tek bir Review pazarlama sayfasındaki "
                  "müşteri görüşü olabilir; yorum gövdesi sayılmaz"),
        "niyet_degeri": "Şikâyet ve memnuniyet kanıtı",
    },
    "fiyatlandirma-sayfasi": {
        "tanim": "Katman ve fiyatların yayımlandığı sayfa",
        "kanit": ("URL yolunda pricing/plans, ya da fiyat DEĞERİ taşıyan en az "
                  "2 Offer. Pazarlama sayfaları tek bir boş Offer gömer"),
        "niyet_degeri": "Ödeme isteği ve fiyat bandı",
    },
    "dokumantasyon": {
        "tanim": "Teknik kullanım belgesi, API referansı",
        "kanit": "URL yolunda docs/documentation/reference/api",
        "niyet_degeri": "Yetenek ve entegrasyon maliyeti",
    },
    "yazi": {
        "tanim": "Haber, blog ya da makale",
        "kanit": "JSON-LD Article/NewsArticle/BlogPosting",
        "niyet_degeri": "Olay ve duyuru kanıtı; ölçüm değil",
    },
    "besleme": {
        "tanim": "RSS/Atom akışı; başlık ve özet taşır, tam içerik taşımaz",
        "kanit": "Yöntem rss_feed; item/entry etiketleri",
        "niyet_degeri": "Tarih ve başlık; içerik için bağlantıya gidilir",
    },
    "arama-sonucu": {
        "tanim": "Sorgu sonucu sayfası",
        "kanit": "URL'de q=/search parametresi",
        "niyet_degeri": "ADAY KEŞİF — kanıt değil; hedef içerik ayrıca çekilir",
    },
    "sitemap": {
        "tanim": "Site haritası; yalnız adres listesi",
        "kanit": "Yöntem sitemap_xml; <loc> etiketleri",
        "niyet_degeri": "ADAY KEŞİF — kanıt değil",
    },
    "politika-dosyasi": {
        "tanim": "robots.txt gibi erişim politikası belgesi",
        "kanit": "Yöntem robots_preflight",
        "niyet_degeri": "Erişim kuralı; araştırma malzemesi değil",
    },
    "api-yaniti": {
        "tanim": "Yapılandırılmış API cevabı",
        "kanit": "MIME application/json ve tanınan anahtarlar",
        "niyet_degeri": "En güvenilir alan kaynağı",
    },
    "belirsiz": {
        "tanim": "Açıldı ama türü belirlenemedi",
        "kanit": "Hiçbir kural eşleşmedi; ham sinyaller kayda geçer",
        "niyet_degeri": "Kullanılmaz; elle incelenmeli",
    },
}

# Coklu etiket kurali: bir belge birden fazla ture uyabilir (fiyat tasiyan bir
# kayit sayfasi gibi). Sira asagidakidir ve ilk eslesen kazanir; digerleri
# 'ikincil_tur' olarak kaydedilir, atilmaz.
BELGE_TURU_SIRASI = (
    "politika-dosyasi", "sitemap", "besleme", "api-yaniti", "arama-sonucu",
    "inceleme-sayfasi", "fiyatlandirma-sayfasi", "kayit-sayfasi",
    "liste-sayfasi", "dokumantasyon", "yazi", "ana-sayfa", "belirsiz",
)

KENDINI_TARIF = {"Organization", "WebSite", "WebPage", "BreadcrumbList",
                 "SiteNavigationElement", "FAQPage", "CollectionPage"}

# Kok yoldaki bir sayfa varsayilan olarak ANA SAYFADIR. Pazarlama ana
# sayfalari kendilerini tarif eden JSON-LD gomer: kendi urununu Product
# olarak, kendi musteri gorusunu Review olarak, kendi haberini Article
# olarak. Bunlari 'kayit sayfasi' ya da 'inceleme sayfasi' saymak,
# kabul kriterinin yasakladigi seydir: icerik bulunmayan yerde yorum ya
# da fiyat verisi varsayilmis olur.
#
# Kok yoldaki bir sayfa ancak **listelenmis kayitlara** dair guclu kanit
# varsa baska bir ture gecer. Asagidaki esikler o kanitin olcusudur.
KOK_YOLU_EZEN_KANIT = {"liste": 5, "yorum": 10}

# Ana sayfa her zaman '/' degildir: 'base.com/en-US/home/' ve 'bigspy.com/en'
# de ana sayfadir. Dil/bolge oneki ve 'home'/'index' segmentleri atildiktan
# sonra yol bossa kok kabul edilir.
_DIL_ONEKI = re.compile(r"^[a-z]{2}([-_][a-z]{2})?$", re.I)
_KOK_SEGMENTI = {"home", "index", "index.html", "intl", "www", "default"}


def kok_yolu_mu(yol: str) -> bool:
    """Yerellestirilmis ana sayfalari da kok sayar."""
    segmentler = [s for s in yol.split("/") if s]
    kalan = [s for s in segmentler
             if not _DIL_ONEKI.match(s) and s.lower() not in _KOK_SEGMENTI]
    return not kalan


def _metin_sinyalleri(ham: bytes, url: str) -> dict[str, Any]:
    """Artefakttan olculebilir sinyalleri cikarir; yorum katmaz."""
    metin = ham.decode("utf-8", "replace")
    yol = urllib.parse.urlsplit(url).path.lower()
    sorgu = urllib.parse.urlsplit(url).query.lower()
    baslik = re.search(r"<title[^>]*>(.*?)</title>", metin, re.S | re.I)
    turler = {t.decode("utf-8", "replace")
              for t in re.findall(rb'"@type"\s*:\s*"([^"]+)"', ham)}
    return {
        "baslik": re.sub(r"\s+", " ", baslik.group(1)).strip()[:120] if baslik else "",
        "jsonld_turleri": sorted(turler),
        "yol": yol,
        "arama_parametresi": bool(re.search(r"\b(q|query|search|searchTerms)=", sorgu)),
        # Sayilar onemli: tek bir ItemList gezinme menusu, tek bir Review
        # musteri gorusu, tek bir bos Offer pazarlama isareti olabilir.
        # Etiket ancak sayilabilir kanit varsa verilir.
        "itemlist_sayisi": metin.count("itemListElement"),
        "aggregate_rating": "aggregateRating" in metin or "AggregateRating" in turler,
        "yorum_sayisi": len(re.findall(r'"@type"\s*:\s*"Review"', metin)),
        "fiyatli_offer_sayisi": len(re.findall(
            r'"@type"\s*:\s*"(?:Offer|AggregateOffer)"[^}]*?"price"\s*:\s*"?[\d.]', metin)),
        "urun_nesnesi": bool(turler & {"Product", "SoftwareApplication",
                                       "MobileApplication", "LocalBusiness"}),
        "makale_nesnesi": bool(turler & {"Article", "NewsArticle", "BlogPosting"}),
        "bayt": len(ham),
    }


def belge_turu_belirle(yontem: str, mime: str, sinyal: dict[str, Any]
                       ) -> tuple[str, list[str], str]:
    """(birincil tur, ikincil turler, kanit) doner.

    Kural sirasi ``BELGE_TURU_SIRASI``; her kural hangi sinyale dayandigini
    dondurur, boylece etiketin gerekcesi kayitta durur.
    """
    uyan: list[tuple[str, str]] = []
    yol = sinyal["yol"]
    if yontem == "robots_preflight":
        uyan.append(("politika-dosyasi", "yöntem robots_preflight"))
    if yontem == "sitemap_xml":
        uyan.append(("sitemap", "yöntem sitemap_xml"))
    if yontem == "rss_feed":
        uyan.append(("besleme", "yöntem rss_feed"))
    if "json" in mime.lower():
        uyan.append(("api-yaniti", f"MIME {mime.split(';')[0]}"))
    if sinyal["arama_parametresi"] or "/search" in yol:
        uyan.append(("arama-sonucu", "URL'de arama parametresi"))
    if sinyal["yorum_sayisi"] >= 3:
        uyan.append(("inceleme-sayfasi",
                     f"{sinyal['yorum_sayisi']} adet JSON-LD Review nesnesi"))
    if re.search(r"/(pricing|plans|fiyat)", yol):
        uyan.append(("fiyatlandirma-sayfasi", "URL yolunda pricing/plans"))
    elif sinyal["fiyatli_offer_sayisi"] >= 2:
        uyan.append(("fiyatlandirma-sayfasi",
                     f"{sinyal['fiyatli_offer_sayisi']} adet fiyat değeri taşıyan Offer"))
    if sinyal["urun_nesnesi"]:
        uyan.append(("kayit-sayfasi",
                     f"JSON-LD {', '.join(t for t in sinyal['jsonld_turleri'] if t not in KENDINI_TARIF)[:40]}"))
    if sinyal["itemlist_sayisi"] >= 5:
        uyan.append(("liste-sayfasi",
                     f"{sinyal['itemlist_sayisi']} adet itemListElement girdisi"))
    if re.search(r"/(docs?|documentation|reference|api)(/|$)", yol):
        uyan.append(("dokumantasyon", "URL yolunda docs/reference"))
    if sinyal["makale_nesnesi"]:
        uyan.append(("yazi", "JSON-LD Article/NewsArticle"))
    if not uyan:
        # Hicbir kural eslesmedi. Kok yoldaysa ana sayfadir; degilse turu
        # bilinmiyordur ve TAHMIN EDILMEZ. 'belirsiz' gecerli bir etikettir.
        if kok_yolu_mu(yol):
            uyan.append(("ana-sayfa",
                         "URL yolu kök ve kayıt/liste/fiyat işareti yok"))
        else:
            uyan.append(("belirsiz",
                         f"URL yolu '{yol[:40]}' kök değil ama kayıt, liste, "
                         "yorum ya da fiyat işareti taşımıyor"))

    # Kok yolda ana sayfa varsayilani: yalnizca listelenmis kayitlara dair
    # guclu kanit bunu ezebilir.
    kok_yolda = kok_yolu_mu(yol)
    if kok_yolda and yontem in ("root_html", "entry_url", "common_crawl_warc"):
        guclu = (sinyal["itemlist_sayisi"] >= KOK_YOLU_EZEN_KANIT["liste"]
                 or sinyal["yorum_sayisi"] >= KOK_YOLU_EZEN_KANIT["yorum"])
        if not guclu:
            zayif = [t for t, _k in uyan
                     if t in ("kayit-sayfasi", "inceleme-sayfasi", "yazi",
                              "liste-sayfasi", "fiyatlandirma-sayfasi")]
            uyan = [(t, k) for t, k in uyan if t not in zayif]
            gerekce = "kök yolda ana sayfa; sayfanın kendini tarif eden işaretleri"
            if zayif:
                gerekce += f" ({', '.join(sorted(set(zayif)))} işareti var ama eşiğin altında)"
            uyan.append(("ana-sayfa", gerekce))

    sirali = sorted(uyan, key=lambda u: BELGE_TURU_SIRASI.index(u[0]))
    birincil, kanit = sirali[0]
    ikincil = [t for t, _k in sirali[1:] if t != birincil]
    return birincil, ikincil, kanit


# --------------------------------------------------------------------------
# EKSEN 4 — ARASTIRMA NIYETI
# Gorev 2'de tanimlanan 14 soru bu eksendir; burada yeniden tanimlanmaz,
# KATEGORI-SORU.csv'den okunur. Ayri eksen olmasinin sebebi: ayni belge
# turu farkli niyetlere farkli deger tasir. Bir inceleme sayfasi
# 'sikayet-ne' icin birincil kanit, 'giris-engeli' icin degersizdir.
# --------------------------------------------------------------------------
NIYET_KAYNAGI = "KATEGORI-SORU.csv"

# --------------------------------------------------------------------------
# COKLU ETIKET VE BELIRSIZLIK KURALLARI (dort eksen icin ayri ayri)
# --------------------------------------------------------------------------
COKLU_ETIKET: dict[str, str] = {
    "urun_tipi": ("Bir fikir birden fazla ürün tipine uyabilir. Ana tip "
                  "araştırmanın ayırt edici sorusunu cevaplayandır; diğeri "
                  "katman olarak eklenir (görev 1'in katman kuralı). "
                  "Örnek: mobil bulmaca oyunu → ana tip consumer, dağıtım "
                  "katmanı app store."),
    "kaynak_ailesi": ("Bir kaynak birden fazla aileye ait olabilir ve bu bir "
                      "hata değildir: G2 hem inceleme sitesi hem fiyat "
                      "karşılaştırma kaynağıdır. Tüm aileler kaydedilir, "
                      "biri seçilmez."),
    "belge_turu": ("Bir belge birden fazla türe uyabilir. Birincil tür "
                   "BELGE_TURU_SIRASI'ndaki ilk eşleşendir; diğerleri "
                   "'ikincil_belge_turu' alanında saklanır, atılmaz."),
    "arastirma_niyeti": ("Bir belge birden fazla niyete hizmet edebilir. "
                         "Niyet belgeye değil, belge × soru çiftine bağlanır."),
}

BELIRSIZ_DURUMU: dict[str, str] = {
    "urun_tipi": ("Fikir hiçbir tipe bağlanamıyorsa 'belirlenemedi' yazılır ve "
                  "iş durur. Sessizce bir varsayılana düşmek bütün seçimi "
                  "yanlış yapar."),
    "kaynak_ailesi": ("Kaynak hiçbir aileye atanamıyorsa 'atanmamis' yazılır; "
                      "kaynak silinmez, envanterde kalır."),
    "belge_turu": ("Dosya açıldı ama hiçbir kural eşleşmediyse 'belirsiz' "
                   "yazılır ve ham sinyaller kayda geçer. Tahmin edilmez."),
    "arastirma_niyeti": ("Belgenin hangi soruya hizmet ettiği belirsizse niyet "
                         "atanmaz; belge kayıtta kalır, kanıt sayılmaz."),
}


def _oku(yol: Path) -> list[dict[str, str]]:
    with yol.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sozluk_belgesi(pilot: list[dict[str, Any]], eksikler: list[dict[str, Any]]) -> str:
    """Kategori sozlugu v1 belgesini modul sabitlerinden uretir.

    Elle yazilmaz ki sozluk ile kod birbirinden ayrilmasin.
    """
    say = collections.Counter(r["belge_turu"] for r in pilot)
    satir: list[str] = [
        "# Kategori Sözlüğü v1",
        "",
        "**Hazırlayan:** Ayselin Aydoğdu  ",
        f"**Üretim:** `kategori_sozlugu.py` — elle yazılmaz, koddan üretilir  ",
        f"**Pilot kayıt:** {len(pilot)} · **Kaynak ailesi:** "
        f"{len({r['kaynak_ailesi'] for r in pilot})} · **Eksik kaydı:** {len(eksikler)}",
        "",
        "Bu sözlük dört ekseni **ayrı** tutar. Karıştırılmaları sistematik hataya",
        "yol açar: bir inceleme sitesi (kaynak ailesi) hem B2B SaaS hem",
        "data/analytics ürünü (ürün tipi) araştırmasında kullanılır; elimizdeki",
        "dosya bir ana sayfaysa (belge türü) hiçbir soru (araştırma niyeti) için",
        "kanıt üretmez. Üç eksen ayrı olmadan bu cümle kurulamaz.",
        "",
        "**Temel kural:** hiçbir etiket site adına bakarak verilmez. Her etiket",
        "ya açılmış bir artefakta ya da açık bir eksik-veri kaydına bağlıdır.",
        "",
        "---",
        "",
        "## Eksen 1 — Ürün tipi",
        "",
        "Kaynak: kanonik görev metni (`tasks/ayselin-task/README.md`, T01).",
        "",
    ]
    for anahtar, bilgi in URUN_TIPI.items():
        satir += [
            f"### `{anahtar}` — {bilgi['ad']}", "",
            f"**Tanım:** {bilgi['tanim']}", "",
            f"- **Dahil:** {bilgi['dahil']}",
            f"- **Hariç:** {bilgi['haric']}",
            f"- **Hedef kullanıcı:** {bilgi['hedef_kullanici']}",
            f"- **Satın alma:** {bilgi['satin_alma']}", "",
        ]
    satir += [
        f"**Çoklu etiket:** {COKLU_ETIKET['urun_tipi']}", "",
        f"**Belirsiz durumu:** {BELIRSIZ_DURUMU['urun_tipi']}", "",
        "### Görev 1 kategorileriyle eşleme", "",
        "Kanonik liste ürün tipi eksenini tanımlar. Görev 1'in kategorileri aynı",
        "ekseni farklı kesen eski bir denemedir; uyuşmayan yerde **kanonik liste",
        "geçerlidir.**",
        "",
        "| Görev 1 kategorisi | Ürün tipi | Karar kuralı |", "|---|---|---|",
    ]
    for eski_ad, yeni_tipler in sorted(URUN_TIPI_ESLEME.items()):
        tipler = ", ".join(f"`{x}`" for x in yeni_tipler)
        satir.append(f"| `{eski_ad}` | {tipler} | {ESLEME_KURALI.get(eski_ad, 'Tek eşleme')} |")
    satir += [
        "",
        "---", "",
        "## Eksen 2 — Kaynak ailesi", "",
        "Kaynağın ne tür bir yayın olduğu. Ürün tipiyle **karıştırılmaz**: bir",
        "aile birden çok ürün tipine hizmet eder ve bu bir hata değildir.",
        "",
        f"Envanterde {len({r['kaynak_ailesi'] for r in pilot})} aile var;",
        "tanımları `KATEGORI-KAYNAK.csv`'nin `kaynak_grubu` sütununda.",
        "",
        f"**Çoklu etiket:** {COKLU_ETIKET['kaynak_ailesi']}", "",
        f"**Belirsiz durumu:** {BELIRSIZ_DURUMU['kaynak_ailesi']}", "",
        "---", "",
        "## Eksen 3 — Belge türü", "",
        "Elimizdeki **dosyanın** ne olduğu. Ancak açarak bilinir.",
        "",
        "| Tür | Tanım | Kanıt kuralı | Araştırma değeri |", "|---|---|---|---|",
    ]
    for anahtar, bilgi in BELGE_TURU.items():
        satir.append(f"| `{anahtar}` | {bilgi['tanim']} | {bilgi['kanit']} "
                     f"| {bilgi['niyet_degeri']} |")
    satir += [
        "",
        "**Kök yolu kuralı.** Kök yoldaki bir sayfa varsayılan olarak ana",
        "sayfadır. Pazarlama ana sayfaları kendilerini tarif eden JSON-LD gömer:",
        "kendi ürününü `Product`, kendi müşteri görüşünü `Review`, kendi haberini",
        "`Article` olarak. Bunları kayıt ya da inceleme sayfası saymak, kabul",
        "kriterinin yasakladığı şeydir. Kök yol ancak listelenmiş kayıtlara dair",
        f"güçlü kanıt varsa ezilir: en az {KOK_YOLU_EZEN_KANIT['liste']} "
        f"`itemListElement` ya da {KOK_YOLU_EZEN_KANIT['yorum']} `Review`.",
        "",
        "Ana sayfa her zaman `/` değildir: `base.com/en-US/home/` ve",
        "`bigspy.com/en` de kök sayılır — dil/bölge öneki ve `home`/`index`",
        "segmentleri atıldıktan sonra yol boşsa kök kabul edilir.",
        "",
        f"**Çoklu etiket:** {COKLU_ETIKET['belge_turu']}", "",
        f"**Belirsiz durumu:** {BELIRSIZ_DURUMU['belge_turu']}", "",
        "---", "",
        "## Eksen 4 — Araştırma niyeti", "",
        f"Görev 2'de tanımlanan 14 soru bu eksendir; `{NIYET_KAYNAGI}`'den okunur,",
        "burada yeniden tanımlanmaz. Ayrı eksen olmasının sebebi: aynı belge türü",
        "farklı niyetlere farklı değer taşır. Bir inceleme sayfası `sikayet-ne`",
        "için birincil kanıt, `giris-engeli` için değersizdir.",
        "",
        f"**Çoklu etiket:** {COKLU_ETIKET['arastirma_niyeti']}", "",
        f"**Belirsiz durumu:** {BELIRSIZ_DURUMU['arastirma_niyeti']}", "",
        "---", "",
        "## Pilot sonucu", "",
        "| Belge türü | Kayıt |", "|---|---:|",
    ]
    for tur, adet in say.most_common():
        satir.append(f"| `{tur}` | {adet} |")
    olcum = sum(1 for r in pilot if r["olcum_kaniti_uretir_mi"] == "evet")
    satir += [
        "",
        f"**{len(pilot)} kayıttan {say.get('ana-sayfa', 0)}'i ana sayfa.** Yalnızca",
        f"**{olcum} kayıt** ölçüm kanıtı üretiyor.",
        "",
        "Bu, kabul kriterinin doğrudan karşılığıdır: içerik bulunmayan yerde",
        "yorum ya da fiyat verisi varsayılmaz. Envanterdeki kaynakların çoğuna",
        "erişildi ama elimizdeki dosya kaynağın ana sayfasıdır; alanı taşıyan iç",
        "sayfa çekilmemiştir.",
        "",
    ]
    if eksikler:
        satir += ["## Eksik kayıtları", "",
                  "| Kaynak ailesi | İstenen | Bulunan | Neden |", "|---|---:|---:|---|"]
        for e in eksikler:
            satir.append(f"| {e['kaynak_ailesi']} | {e['istenen_ornek']} | "
                         f"{e['bulunan_ornek']} | {e['eksik_nedeni']} |")
        satir.append("")
    return "\n".join(satir)


def gunluk_belgesi(pilot: list[dict[str, Any]]) -> str:
    """Ornek inceleme gunlugu: hangi dosya acildi, ne goruldu, ne karar verildi."""
    satir = [
        "# Örnek İnceleme Günlüğü", "",
        "Her satır açılmış bir artefakttır. `artefakt_kimligi` içerik adresli",
        "sha256'nın ilk 16 hanesidir; `dosya` diskteki yoldur.",
        "",
        f"**Açılan artefakt:** {len(pilot)} · "
        f"**Kaynak:** {len({r['kaynak'] for r in pilot})} · "
        f"**Aile:** {len({r['kaynak_ailesi'] for r in pilot})}",
        "",
    ]
    for aile in sorted({r["kaynak_ailesi"] for r in pilot}):
        satir += [f"## {aile}", ""]
        for r in [x for x in pilot if x["kaynak_ailesi"] == aile]:
            satir += [
                f"**{r['kaynak']}** — `{r['source_id']}`  ",
                f"URL: {r['url']}  ",
                f"Artefakt: `{r['artefakt_kimligi']}` ({r['dosya']}, {r['bayt']} bayt, "
                f"yöntem `{r['yontem']}`)  ",
                f"İçerik alanı: {r['icerik_alani']}  ",
                f"JSON-LD: {r['jsonld_turleri'] or '—'} · Kanıt sayıları: "
                f"{r['kanit_sayilari']}  ",
                f"**Belge türü:** `{r['belge_turu']}`"
                + (f" (ikincil: {r['ikincil_belge_turu']})" if r["ikincil_belge_turu"] else "")
                + f" — {r['siniflandirma_gerekcesi']}  ",
                f"Ölçüm kanıtı üretir mi: **{r['olcum_kaniti_uretir_mi']}**"
                + (" · ADAY KEŞİF" if r["aday_kesif_mi"] == "evet" else ""),
                "",
            ]
    return "\n".join(satir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aile-basina", type=int, default=3,
                        help="Her kaynak ailesinden kaç örnek açılır")
    parser.add_argument("--out-pilot", type=Path, default=HERE / "PILOT-KAYITLAR.csv")
    parser.add_argument("--out-eksik", type=Path, default=HERE / "PILOT-EKSIKLER.csv")
    args = parser.parse_args()

    dizin = [r for r in _oku(HERE / "ARTEFAKT-DIZINI.csv") if r["sonuc"] == "ok"]
    kategori_kaynak = _oku(HERE / "KATEGORI-KAYNAK.csv")
    defter = {r["ad"]: r for r in _oku(HERE / "KAYNAK-DEFTERI.csv")}

    # Kaynak -> aile(ler). Aile ile urun tipi AYRI eksen: bir aile birden cok
    # urun tipine hizmet edebilir ve bu bir hata degildir.
    aile_kaynaklari: dict[str, set[str]] = collections.defaultdict(set)
    kaynak_ailesi: dict[str, set[str]] = collections.defaultdict(set)
    kaynak_urun_tipi: dict[str, set[str]] = collections.defaultdict(set)
    for r in kategori_kaynak:
        for g in r["kaynak_grubu"].split(" | "):
            aile_kaynaklari[g.strip()].add(r["kaynak"])
            kaynak_ailesi[r["kaynak"]].add(g.strip())
        for tip in URUN_TIPI_ESLEME.get(r["hedef"], ()):
            kaynak_urun_tipi[r["kaynak"]].add(tip)

    # Kaynak basina acilabilir artefaktlar
    artefakt: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for r in dizin:
        if r["ad"] and r["dosya"].startswith("results/raw/"):
            artefakt[r["ad"]].append(r)

    satirlar: list[dict[str, Any]] = []
    eksikler: list[dict[str, Any]] = []

    for aile in sorted(aile_kaynaklari):
        adaylar = sorted(k for k in aile_kaynaklari[aile] if artefakt.get(k))
        if len(adaylar) < args.aile_basina:
            eksikler.append({
                "kaynak_ailesi": aile,
                "istenen_ornek": args.aile_basina,
                "bulunan_ornek": len(adaylar),
                "aileedeki_kaynak": len(aile_kaynaklari[aile]),
                "eksik_nedeni": ("ailedeki kaynakların açılabilir artefaktı yok; "
                                 "erişilemedi ya da yalnız politika dosyası indi"),
            })
        for kaynak in adaylar[:args.aile_basina]:
            # Kaynak basina en bilgi tasiyan artefakt: politika/sitemap disi
            # olan varsa o, yoksa eldeki.
            sirali = sorted(artefakt[kaynak], key=lambda r: (
                r["yontem"] in ("robots_preflight", "sitemap_xml"), -int(r["bayt"] or 0)))
            kayit = sirali[0]
            yol = Path(kayit["dosya"])
            if not yol.is_absolute():
                yol = HERE / yol
            if not yol.exists():
                eksikler.append({
                    "kaynak_ailesi": aile, "istenen_ornek": 1, "bulunan_ornek": 0,
                    "aileedeki_kaynak": kaynak,
                    "eksik_nedeni": f"dizinde kayıtlı dosya diskte yok: {kayit['dosya']}",
                })
                continue
            ham = yol.read_bytes()[:400_000]
            sinyal = _metin_sinyalleri(ham, kayit["cekilen_url"])
            tur, ikincil, kanit = belge_turu_belirle(
                kayit["yontem"], kayit["mime"], sinyal)
            satirlar.append({
                "ornekleme_gecisi": "kaynak-ailesi",
                "kanit_sayilari": (f"liste={sinyal['itemlist_sayisi']} "
                                   f"yorum={sinyal['yorum_sayisi']} "
                                   f"fiyatli_offer={sinyal['fiyatli_offer_sayisi']}"),
                "source_id": kayit["source_id"] or defter.get(kaynak, {}).get("source_id", ""),
                "kaynak": kaynak,
                "url": kayit["cekilen_url"],
                "artefakt_kimligi": kayit["sha256"][:16],
                "dosya": kayit["dosya"],
                "kaynak_ailesi": aile,
                "kaynagin_diger_aileleri": ", ".join(
                    sorted(kaynak_ailesi[kaynak] - {aile})),
                "urun_tipi": ", ".join(sorted(kaynak_urun_tipi.get(kaynak, set()))) or "ortak-havuz",
                "belge_turu": tur,
                "ikincil_belge_turu": ", ".join(ikincil),
                "icerik_alani": sinyal["baslik"] or "(başlık yok)",
                "jsonld_turleri": ", ".join(sinyal["jsonld_turleri"][:6]),
                "siniflandirma_gerekcesi": kanit,
                "aday_kesif_mi": "evet" if tur in ("sitemap", "arama-sonucu") else "hayir",
                "olcum_kaniti_uretir_mi":
                    "hayir" if tur in ("ana-sayfa", "sitemap", "arama-sonucu",
                                       "politika-dosyasi", "belirsiz") else "evet",
                "bayt": sinyal["bayt"],
                "yontem": kayit["yontem"],
            })

    # --- Ikinci gecis: VERI YUZEYI temsili ---
    # Gorev "her kaynak ailesi VE veri yuzeyini temsil eden ornekleri ac"
    # diyor. Aile bazli ornekleme kaynak basina en bilgilendirici dosyayi
    # sectigi icin root_html'e egilimlidir ve API yanitlari gibi az sayida
    # ama degerli yuzeyler disarida kalir. Bu gecis her yuzey turunden en
    # az bir ornegin acilmasini garanti eder.
    temsil_edilen = {r["yontem"] for r in satirlar}
    yuzey_artefakti: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    govdesiz_yuzey: dict[str, dict[str, str]] = {}
    for r in dizin:
        if not r["ad"]:
            continue
        if r["dosya"].startswith("results/raw/"):
            yuzey_artefakti[r["yontem"]].append(r)
        elif r["yontem"] not in govdesiz_yuzey:
            # Govde saklanmamis: kosu JSON'u yalniz hash ve URL tutuyor.
            # Acilamaz; tahmin edilmez, eksik kaydi yazilir.
            govdesiz_yuzey[r["yontem"]] = r

    for yuzey, kayit in sorted(govdesiz_yuzey.items()):
        if yuzey in temsil_edilen or yuzey in yuzey_artefakti:
            continue
        eksikler.append({
            "kaynak_ailesi": f"(yüzey temsili: {yuzey})",
            "istenen_ornek": 1, "bulunan_ornek": 0,
            "aileedeki_kaynak": kayit["ad"],
            "eksik_nedeni": (
                f"gövde saklanmamış (saklama={kayit['saklama']}, bayt=0); "
                f"elde yalnız sha256 {kayit['sha256'][:16]} ve URL "
                f"{kayit['cekilen_url'][:60]} var — açılacak içerik yok"),
        })

    for yuzey in sorted(set(yuzey_artefakti) - temsil_edilen):
        kayit = sorted(yuzey_artefakti[yuzey], key=lambda r: -int(r["bayt"] or 0))[0]
        yol_dosya = HERE / kayit["dosya"]
        if not yol_dosya.exists():
            eksikler.append({
                "kaynak_ailesi": f"(yüzey temsili: {yuzey})",
                "istenen_ornek": 1, "bulunan_ornek": 0,
                "aileedeki_kaynak": kayit["ad"],
                "eksik_nedeni": f"dizinde kayıtlı dosya diskte yok: {kayit['dosya']}",
            })
            continue
        ham = yol_dosya.read_bytes()[:400_000]
        sinyal = _metin_sinyalleri(ham, kayit["cekilen_url"])
        tur, ikincil, kanit = belge_turu_belirle(yuzey, kayit["mime"], sinyal)
        kaynak = kayit["ad"]
        satirlar.append({
            "ornekleme_gecisi": "veri-yuzeyi",
            "kanit_sayilari": (f"liste={sinyal['itemlist_sayisi']} "
                               f"yorum={sinyal['yorum_sayisi']} "
                               f"fiyatli_offer={sinyal['fiyatli_offer_sayisi']}"),
            "source_id": kayit["source_id"] or defter.get(kaynak, {}).get("source_id", ""),
            "kaynak": kaynak, "url": kayit["cekilen_url"],
            "artefakt_kimligi": kayit["sha256"][:16], "dosya": kayit["dosya"],
            "kaynak_ailesi": ", ".join(sorted(kaynak_ailesi.get(kaynak, {"(aile atanmamış)"}))),
            "kaynagin_diger_aileleri": "",
            "urun_tipi": ", ".join(sorted(kaynak_urun_tipi.get(kaynak, set()))) or "ortak-havuz",
            "belge_turu": tur, "ikincil_belge_turu": ", ".join(ikincil),
            "icerik_alani": sinyal["baslik"] or "(başlık yok)",
            "jsonld_turleri": ", ".join(sinyal["jsonld_turleri"][:6]),
            "siniflandirma_gerekcesi": kanit + " [yüzey temsili örneği]",
            "aday_kesif_mi": "evet" if tur in ("sitemap", "arama-sonucu") else "hayir",
            "olcum_kaniti_uretir_mi":
                "hayir" if tur in ("ana-sayfa", "sitemap", "arama-sonucu",
                                   "politika-dosyasi", "belirsiz") else "evet",
            "bayt": sinyal["bayt"], "yontem": yuzey,
        })

    for yol, veri in ((args.out_pilot, satirlar), (args.out_eksik, eksikler)):
        if not veri:
            continue
        with yol.open("w", newline="", encoding="utf-8") as handle:
            yazici = csv.DictWriter(handle, fieldnames=list(veri[0]))
            yazici.writeheader()
            yazici.writerows(veri)

    (HERE / "KATEGORI-SOZLUGU.md").write_text(
        sozluk_belgesi(satirlar, eksikler) + "\n", encoding="utf-8")
    (HERE / "INCELEME-GUNLUGU.md").write_text(
        gunluk_belgesi(satirlar) + "\n", encoding="utf-8")

    tur_dagilimi = collections.Counter(r["belge_turu"] for r in satirlar)
    print(json.dumps({
        "pilot_kayit": len(satirlar),
        "kaynak_ailesi": len({r["kaynak_ailesi"] for r in satirlar}),
        "ayri_kaynak": len({r["kaynak"] for r in satirlar}),
        "belge_turu_dagilimi": tur_dagilimi.most_common(),
        "olcum_kaniti_ureten": sum(1 for r in satirlar
                                   if r["olcum_kaniti_uretir_mi"] == "evet"),
        "aday_kesif": sum(1 for r in satirlar if r["aday_kesif_mi"] == "evet"),
        "eksik_kaydi": len(eksikler),
        "temsil_edilen_veri_yuzeyi": sorted({r["yontem"] for r in satirlar}),
        "acilabilir_yuzeyin_tamami_temsil_edildi": not (
            {r["yontem"] for r in dizin if r["dosya"].startswith("results/raw/")}
            - {r["yontem"] for r in satirlar}),
        # Yalniz HIC acilabilir kopyasi olmayan yuzeyler. Bir yuzeyin bazi
        # satirlari kosu JSON'unda, bazilari results/raw'da olabilir; ancak
        # ikincisi hic yoksa yuzey acilamaz sayilir.
        "hic_acilamayan_yuzey": sorted(
            {r["yontem"] for r in dizin if r["ad"]}
            - {r["yontem"] for r in dizin
               if r["ad"] and r["dosya"].startswith("results/raw/")}),
        "cikti": [str(args.out_pilot), str(args.out_eksik),
                  "KATEGORI-SOZLUGU.md", "INCELEME-GUNLUGU.md"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
