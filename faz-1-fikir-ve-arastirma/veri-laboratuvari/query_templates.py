"""Sorguyu genel kelime listesi olmaktan cikarip derlenebilir sablona cevirir.

Gorev 1 her kaynak grubuna bir arama kalibi yazmisti: ``{urun}; {urun} clinical``.
620 kaynak icin toplam 30 kalip vardi ve kalip dort seyi goz ardi ediyordu:

* **Kaynak.** PubMed ile Google Play ayni sorgu sozdizimini kullanmaz. Birine
  ``ti:`` alan oneki, digerine ``&c=apps`` parametresi gider.
* **Niyet.** "Talep var mi" ile "sikayet ne" ayni kelimelerle aranamaz; ikincisi
  sorunu anlatan kelimeleri gerektirir.
* **Urun dili.** Kurucunun cumlesi ("diyabet hastalari icin mobil takip
  uygulamasi") ile magaza kullanicisinin yazdigi ("kan sekeri takip") ayni degil.
* **Pazar.** Turkiye ve ABD pazari icin dil, bolge parametresi ve terim farkli.

Bu modul sabloni dort parcaya ayirir:

    [cekirdek terim] + [kaynak grubunun dili] + [niyet eki] + [pazar profili]
      fikirden otomatik    31 grup, sabit        14 soru      TR / US

Fikirden fikre degisen tek sey cekirdek terimdir ve o otomatik cikarilir; geri
kalan uc tablo bir kez yazilir. Boylece yeni bir urun fikri geldiginde elle
terim eklemek gerekmez.
"""
from __future__ import annotations

import re
import unicodedata

# --------------------------------------------------------------------------
# Cekirdek terim: fikirden konuyu tasiyan kelimeleri birakir, dolguyu atar.
# --------------------------------------------------------------------------
# Turkce dolgu kelimeleri. Listenin kisa ve acik olmasi kasitli: uzun bir
# durdurma listesi konu kelimesini de yutabilir.
DOLGU: frozenset[str] = frozenset({
    "icin", "ile", "ve", "veya", "bir", "bu", "su", "o", "da", "de", "ki",
    "gibi", "kadar", "daha", "cok", "az", "her", "hem", "ama", "fakat",
    "yapmak", "yapan", "olan", "olarak", "uzerine", "hakkinda", "dair",
    "yonelik", "ozel", "genel", "yeni", "kullanan", "kullanicilar",
    "tabanli", "yonetim", "amacli",
    "kullanici", "insanlar", "kisiler", "hastalari", "musteriler",
})

# Urun tipini anlatan ama arama terimi olarak ayirt edici olmayan kelimeler.
# Kaynak grubunun dili bunlari zaten uygun bicimde ekler; cekirdekte tutmak
# sorguyu gereksiz daraltir.
URUN_SONEKI: frozenset[str] = frozenset({
    # Urun tipi
    "uygulamasi", "uygulama", "sistemi", "sistem", "yazilimi", "yazilim",
    "platformu", "platform", "araci", "arac", "servisi", "servis",
    "cozumu", "cozum", "kutuphanesi", "kutuphane", "eklentisi", "eklenti",
    "app", "software", "tool", "service", "library", "plugin",
    # Dagitim bicimi. Kaynak secimi bunu zaten ifade ediyor: magazaya
    # soruyorsak urun zaten mobildir, sorguya 'mobil' koymak daraltir.
    "mobil", "web", "online", "dijital", "bulut", "mobile", "cloud",
})


def sadelestir(metin: str) -> str:
    metin = metin.replace("ı", "i").replace("I", "i").replace("İ", "i")
    ayrik = unicodedata.normalize("NFKD", metin.casefold())
    return "".join(k for k in ayrik if not unicodedata.combining(k))


def cekirdek_terim(fikir: str) -> str:
    """Fikirden konuyu tasiyan kelimeleri birakir.

    'diyabet hastalari icin mobil takip uygulamasi' -> 'diyabet takip'

    Urun tipini anlatan sonekler ('uygulamasi') atilir cunku kaynak grubunun
    dili zaten kendi karsiligini ekler: magazada 'app', gelistirici
    toplulugunda 'library'. Ikisini birden koymak sorguyu daraltir.
    """
    kelimeler = re.findall(r"\w+", fikir, flags=re.UNICODE)
    tutulan = [k for k in kelimeler
               if sadelestir(k) not in DOLGU
               and sadelestir(k) not in URUN_SONEKI
               and len(k) > 2]
    return " ".join(tutulan)


# --------------------------------------------------------------------------
# Kaynak grubunun dili. Ayni konu, kaynaga gore farkli kelimelerle aranir:
# magaza kullanicisi 'app' yazar, akademisyen 'study'. Terimler o kaynak
# turunde fiilen kullanilan kelimelerden secildi.
# --------------------------------------------------------------------------
GRUP_DILI: dict[str, tuple[str, ...]] = {
    "Mobil uygulama mağazaları": ("app", "uygulama", "tracker"),
    "SaaS, yazılım ve hizmet inceleme siteleri": ("software", "platform", "tool"),
    "Fiyat, teknoloji ve pazar sinyali karşılaştırma kaynakları": (
        "pricing", "comparison", "vs"),
    "İş ilanları ve yetenek talebi": ("specialist", "developer", "engineer"),
    "Yazılım geliştirici ve teknik topluluklar": ("library", "sdk", "api"),
    "Tarayıcı, e-ticaret ve CMS eklenti mağazaları": ("plugin", "extension", "addon"),
    "Yapay zekâ modeli, veri seti ve agent ekosistemi": ("model", "agent", "dataset"),
    "Oyun dikeyi": ("game", "oyun"),
    "Yerel işletme, harita ve hizmet dizinleri": (
        "appointment", "booking", "service", "provider", "near me"),
    "Dijital ürün ve şablon pazar yerleri": ("template", "script", "theme"),
    "Kitle fonlaması platformları": ("campaign", "project", "backers"),

    "Sağlık ve biyoteknoloji dikeyi": ("clinical", "patient", "health"),
    "Finans ve fintech dikeyi": ("finance", "payment", "regulation"),
    "Eğitim dikeyi": ("course", "learning", "student"),
    "Gayrimenkul ve inşaat dikeyi": ("estate", "property", "listing"),
    "Seyahat, konaklama ve mobilite dikeyi": ("booking", "travel", "accommodation"),
    "Yeme-içme ve teslimat dikeyi": ("delivery", "restaurant", "order"),
    "Regülasyon ve hukuk kaynakları": ("regulation", "compliance", "mevzuat"),
    "Türkiye startup ve teknoloji ekosistemi": ("Türkiye", "girişim", "yatırım"),

    "Genel web arama ve keşif": ("", ),
    "Haber, basın ve sektör yayınları": ("funding", "launch", "acquisition"),
    "Şirket, yatırım ve startup verisi": ("startup", "company", "funding"),
    "Trafik, SEO, anahtar kelime ve trend": ("keyword", "search volume", "trend"),
    "Sosyal ağlar ve açık topluluklar": ("alternative", "recommendation"),
    "Akademik araştırma ve bilimsel yayınlar": ("study", "systematic review"),
    "Patent ve marka": ("patent", "trademark"),
    "Kamu verisi ve istatistik": ("statistics", "survey", "indicator"),
    "Anket, birincil doğrulama ve kullanıcı araştırması platformları": (
        "survey", "user research"),
    "Domain, DNS, sertifika ve web footprint": ("domain", "website"),
    "Reklam kütüphaneleri ve pazarlama sinyalleri": ("ad", "campaign", "creative"),
    "Ürün lansmanı ve startup toplulukları": ("launch", "product", "maker"),
}

# --------------------------------------------------------------------------
# Niyet ekleri. Gorev 2'nin kanit tanimindan turetildi: kanit ne ariyorsa
# sorgu da onu aramali.
# --------------------------------------------------------------------------
NIYET_EKI: dict[str, tuple[str, ...]] = {
    # soru_id -> sorguya eklenecek terimler ("" = sade terim yeterli)
    "talep-var-mi": ("",),
    "rakip-kim": ("alternative", "vs", "competitors"),
    "doygun-mu": ("",),
    "odeme-istegi": ("pricing", "premium", "subscription"),
    "talep-yonu": ("trend", "growth"),
    "sikayet-ne": ("problem", "issue", "not working", "sorun"),
    "giris-engeli": ("regulation", "requirements", "license"),
    "ulasilabilir-mi": ("community", "forum", "group"),
    "platform-politikasi": ("policy", "guidelines", "rejected"),
    "lisans-modeli": ("license", "open source", "pricing"),
    "platform-kendi-ekler-mi": ("native", "built-in", "roadmap"),
    "birim-maliyet": ("cost", "pricing", "per request"),
    "cografi-yogunluk": ("near me", "city", "local"),
    "kesfedilebilirlik": ("ranking", "top", "best"),
}

# --------------------------------------------------------------------------
# Pazar profilleri. Dil ve bolge parametresi kaynagin sorgu ucuna eklenir.
# --------------------------------------------------------------------------
PAZAR: dict[str, dict[str, str]] = {
    "TR": {"dil": "tr", "bolge": "TR", "ceviri_gerekir": "hayir"},
    "US": {"dil": "en", "bolge": "US", "ceviri_gerekir": "evet"},
}


def sorgu_metni(cekirdek: str, kaynak_grubu: str, soru_id: str,
                niyet_indeksi: int = 0, grup_indeksi: int = 0) -> str:
    """Dort parcayi birlestirip arama metnini kurar.

    Indeksler sabit tutulur; ayni girdi her zaman ayni metni verir.
    """
    parcalar = [cekirdek.strip()]
    grup = GRUP_DILI.get(kaynak_grubu, ("",))
    if grup and grup[min(grup_indeksi, len(grup) - 1)]:
        parcalar.append(grup[min(grup_indeksi, len(grup) - 1)])
    niyet = NIYET_EKI.get(soru_id, ("",))
    ek = niyet[min(niyet_indeksi, len(niyet) - 1)]
    if ek:
        parcalar.append(ek)
    return " ".join(p for p in parcalar if p)
