"""Yerel artefaktlari Faz 4 sozlesmesine gore normalize eder.

Ham dosyalar **asla degistirilmez**; yalnizca okunur ve ayri bir calisma
ciktisi uretilir. ``body_original`` diskteki artefaktin kendisidir ve
``artefakt_hash`` ile her satirdan geri izlenir.

**Iki cikti ayri tutulur.** Gorevin acik sarti budur ve sebebi sudur:

* ``NORMALIZE-BELGELER.csv`` — **teknik normalizasyon**. Baslik, metin, URL,
  tarih, dil, hash. Yorum yok, makine isi. Bir sonraki calisma bunu yeniden
  uretmek zorunda kalmadan kullanabilir.
* ``SINIFLANDIRMA.csv`` — **yorumlayici siniflandirma**. Belge turu, urun
  kategorisi, arastirma niyeti, gerekce. Karar isi.

Ayrilmalarinin karsiligi: yarin siniflandirma degisirse metin cikarimi
bastan yapilmaz, ve yanlis bir karar dogru cikarilmis metni kirletmez.

Uc yasak, gorev kartindan:

1. **Tarih tahmin edilmez.** Sayfada tarih yoksa ``unknown_date`` bayragi
   konur; ``published_at`` bos kalir. ``collected_at`` ile asla ayni anlamda
   kullanilmaz.
2. **Ayni icerik yeni bagimsiz kanit sayilmaz.** Tekrarlar silinmez,
   ``BELGE-ILISKILERI.csv`` icinde ``duplicate_of`` / ``possible_duplicate``
   olarak iliskilendirilir.
3. **Sayisal indirme/etkilesim verisi odeme ya da talep kanitina
   cevrilmez.** Bulunan sayilar ``engagement_metadata`` olarak, oldugu gibi
   ve kendi adiyla saklanir.

Kalite bayraklarinin adlari ``Faz4-Plan.md``'den birebir alinmistir; bunlar
kanit skoru degildir, olculebilir veri butunlugu isaretleridir.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import html
import json
import re
import unicodedata
import urllib.parse
import warnings
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", message=".*REPLACEMENT CHARACTER.*")

HERE = Path(__file__).resolve().parent
NORMALIZASYON_SURUMU = "1.0.0"

# --------------------------------------------------------------------------
# Dil tespiti
# Faz4-Plan.md: "Cok kisa metinlerde yanlis kesinlik uretmek yerine unknown
# kullanilir" ve "minimum metin uzunlugu ve guven esigi konfigurasyonla
# uygulanir". fastText yerel olarak kurulu olmadigi icin ayni sozlesmeye uyan
# deterministik bir durdurma-kelimesi sayaci kullanilir: esikler acik,
# sonuc tekrarlanabilir, belirsizlikte ``unknown`` doner.
# --------------------------------------------------------------------------
ASGARI_METIN = 200
ASGARI_GUVEN = 0.25

DURDURMA_KELIMELERI: dict[str, frozenset[str]] = {
    "tr": frozenset("""ve bir bu için ile de da ne olarak çok daha var olan ancak
        gibi kadar sonra göre ise her en o veya ki ya bunu şu""".split()),
    "en": frozenset("""the and for with that this from are was you your have not
        but all can has our more about which their would there been""".split()),
    "de": frozenset("""und der die das den dem ein eine mit von für ist sind auch
        nicht auf sich werden oder bei nach über wird""".split()),
    "fr": frozenset("""les des une dans pour que qui est sur par avec plus sont
        comme aux mais ses son cette leur nous vous""".split()),
    "es": frozenset("""los las una por con que para más como pero sus este esta
        son del entre cuando muy también donde""".split()),
    "it": frozenset("""che per non con una sono della delle gli come più anche
        alla nel dei sul questo suo loro""".split()),
    "nl": frozenset("""een het van voor met niet zijn maar deze door ook naar
        worden bij over onze hun dat""".split()),
    "pt": frozenset("""uma para com que não dos das mais como está são pelo pela
        seu sua entre quando também onde""".split()),
}


# URL, alan adi ve dosya yolu dil kaniti degildir. Sitemap'ler yuz binlerce
# adres tasir; ".com" Portekizce'de gecerli bir durdurma kelimesi oldugu icin
# filtrelenmezse bir sitemap "Portekizce" olarak etiketlenir.
ADRES_DESENI = re.compile(
    r"(?:[a-z][a-z0-9+.-]*://\S+)"                 # sema tasiyan URL
    r"|(?:\bwww\.\S+)"                             # www ile baslayan
    r"|(?:\b[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/\S*)?)",  # cikplak alan adi / yol
    re.I)

ASGARI_DURDURMA_CESIDI = 4


def dil_tespit(metin: str) -> tuple[str, float]:
    """(dil kodu, guven) doner. Kisa ya da belirsiz metinde ('unknown', 0.0).

    Dil yalnizca **duz yazidan** okunur: adresler ve dosya yollari atilir,
    ve tek bir kelimenin tekrari dil sayilmaz - en az
    ``ASGARI_DURDURMA_CESIDI`` farkli durdurma kelimesi gorulmelidir.
    """
    if len(metin) < ASGARI_METIN:
        return "unknown", 0.0
    duz = ADRES_DESENI.sub(" ", metin)
    if len(duz.strip()) < ASGARI_METIN:
        return "unknown", 0.0
    kelimeler = re.findall(r"[a-zçğıöşüàâäéèêëîïôùûœñãõ]+", duz.casefold())
    if len(kelimeler) < 30:
        return "unknown", 0.0
    sayac: dict[str, int] = {}
    cesit: dict[str, int] = {}
    for kod, kume in DURDURMA_KELIMELERI.items():
        gorulen = {k for k in kelimeler if k in kume}
        cesit[kod] = len(gorulen)
        sayac[kod] = sum(1 for k in kelimeler if k in kume)
    toplam = sum(sayac.values())
    if not toplam:
        return "unknown", 0.0
    kod, adet = max(sorted(sayac.items()), key=lambda t: t[1])
    guven = adet / toplam
    if cesit[kod] < ASGARI_DURDURMA_CESIDI:
        return "unknown", round(guven, 3)
    if guven < ASGARI_GUVEN:
        return "unknown", round(guven, 3)
    return kod, round(guven, 3)


# --------------------------------------------------------------------------
# URL kanoniklestirme (Faz4: source_url her zaman korunur)
# --------------------------------------------------------------------------
TAKIP_PARAMETRELERI = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "msclkid", "mc_cid", "mc_eid", "ref", "referrer",
    "_ga", "igshid", "yclid", "extole_source", "promotable_code",
}


def url_kanonik(ham_url: str) -> str:
    """Icerik kimligi icin normalize edilmis URL.

    Icerigi degistirebilecek parametreler korlemesine silinmez; yalnizca
    bilinen takip parametreleri ayiklanir.
    """
    if not ham_url:
        return ""
    p = urllib.parse.urlsplit(ham_url)
    alanlar = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
               if k.lower() not in TAKIP_PARAMETRELERI]
    host = (p.hostname or "").casefold()
    if host.startswith("www."):
        host = host[4:]
    yol = re.sub(r"/{2,}", "/", p.path).rstrip("/") or "/"
    return urllib.parse.urlunsplit((
        (p.scheme or "https").lower(), host, yol,
        urllib.parse.urlencode(sorted(alanlar)), ""))


# --------------------------------------------------------------------------
# Metin cikarimi
# --------------------------------------------------------------------------
GURULTU_ETIKETLERI = ("script", "style", "noscript", "template", "svg", "iframe")
# Yazdirilamayan kontrol karakterleri; tab ve satir sonu haric.
KONTROL_KARAKTERLERI = re.compile(
    "[" + "".join(chr(c) for c in list(range(0, 9)) + [11, 12] + list(range(14, 32)))
    + "]")


def metin_cikar(ham: bytes, mime: str) -> dict[str, Any]:
    """Baslik, gorunur metin ve gomulu yapisal veriyi cikarir."""
    if "json" in mime.lower():
        try:
            veri = json.loads(ham.decode("utf-8", "replace"))
        except (ValueError, UnicodeDecodeError):
            return {"baslik": "", "metin": "", "jsonld": [], "gecersiz": True}
        return {"baslik": "", "metin": json.dumps(veri, ensure_ascii=False)[:20000],
                "jsonld": [veri] if isinstance(veri, (dict, list)) else [],
                "gecersiz": False}
    corba = BeautifulSoup(ham, "html.parser")
    jsonld: list[Any] = []
    for blok in corba.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            jsonld.append(json.loads(blok.string or "{}"))
        except (ValueError, TypeError):
            continue
    for etiket in corba(list(GURULTU_ETIKETLERI)):
        etiket.decompose()
    baslik = corba.title.get_text().strip() if corba.title else ""
    metin = unicodedata.normalize("NFC", corba.get_text(" "))
    metin = re.sub(KONTROL_KARAKTERLERI, " ", metin)
    metin = re.sub(r"\s+", " ", html.unescape(metin)).strip()
    return {"baslik": unicodedata.normalize("NFC", baslik), "metin": metin,
            "jsonld": jsonld, "gecersiz": False, "corba": corba}


# --------------------------------------------------------------------------
# Tarih — ASLA tahmin edilmez
# --------------------------------------------------------------------------
TARIH_DESENI = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?")


def _jsonld_tarih(nesneler: list[Any], anahtar: str) -> str:
    yigin = list(nesneler)
    while yigin:
        o = yigin.pop()
        if isinstance(o, dict):
            deger = o.get(anahtar)
            if isinstance(deger, str) and TARIH_DESENI.search(deger):
                return TARIH_DESENI.search(deger).group(0)
            yigin.extend(o.values())
        elif isinstance(o, list):
            yigin.extend(o)
    return ""


def tarih_cikar(cikarim: dict[str, Any]) -> tuple[str, str, str]:
    """(published_at, updated_at, kaynak) doner; bulunamazsa bos.

    Tahmin yok: yalniz belgenin kendi beyan ettigi tarih kabul edilir.
    """
    jsonld = cikarim.get("jsonld", [])
    yayin = _jsonld_tarih(jsonld, "datePublished")
    guncel = _jsonld_tarih(jsonld, "dateModified")
    if yayin or guncel:
        return yayin, guncel, "json-ld"
    corba = cikarim.get("corba")
    if corba is not None:
        for ozellik in ("article:published_time", "og:published_time",
                        "datePublished", "publish-date"):
            etiket = corba.find("meta", attrs={"property": ozellik}) or \
                corba.find("meta", attrs={"name": ozellik})
            if etiket and etiket.get("content"):
                m = TARIH_DESENI.search(etiket["content"])
                if m:
                    return m.group(0), "", f"meta:{ozellik}"
        zaman = corba.find("time", attrs={"datetime": True})
        if zaman:
            m = TARIH_DESENI.search(zaman["datetime"])
            if m:
                return m.group(0), "", "time[datetime]"
    return "", "", ""


# --------------------------------------------------------------------------
# SimHash — Faz4: 64-bit fingerprint, near-duplicate ADAYI uretir
# --------------------------------------------------------------------------
def simhash(metin: str, parca: int = 4) -> int:
    parcalar = metin.casefold().split()
    if len(parcalar) < parca:
        return 0
    agirlik = [0] * 64
    for i in range(len(parcalar) - parca + 1):
        shingle = " ".join(parcalar[i:i + parca])
        h = int.from_bytes(hashlib.blake2b(shingle.encode(), digest_size=8).digest(), "big")
        for bit in range(64):
            agirlik[bit] += 1 if (h >> bit) & 1 else -1
    return sum(1 << bit for bit in range(64) if agirlik[bit] > 0)


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


# --------------------------------------------------------------------------
# Kalite bayraklari — adlar Faz4-Plan.md'den birebir
# Bunlar kanit skoru DEGILDIR; olculebilir veri butunlugu isaretleridir.
# --------------------------------------------------------------------------
KISA_ICERIK_ESIGI = 200


def kalite_bayraklari(cikarim: dict[str, Any], yayin_tarihi: str,
                      icerik_durumu: str) -> list[str]:
    bayraklar: list[str] = []
    if cikarim.get("gecersiz"):
        bayraklar.append("invalid_payload")
    metin = cikarim.get("metin", "")
    if not metin:
        bayraklar.append("missing_body")
    elif len(metin) < KISA_ICERIK_ESIGI:
        bayraklar.append("short_content")
    if not yayin_tarihi:
        bayraklar.append("missing_published_date")
        bayraklar.append("unknown_date")
    if icerik_durumu == "js-kabugu":
        # Sayfa dondu ama gorunur metni yok: erisim sinirli sayilir.
        bayraklar.append("source_policy_limited")
    if icerik_durumu == "aday-kesif":
        bayraklar.append("quote_only")
    return bayraklar


# --------------------------------------------------------------------------
# Kategori bazinda cikarilabilen alanlar
# Gorev: "yalniz gercekten bulunan veriler". Alan ancak belgede bulunduysa
# yazilir; bulunmadiysa satir uretilmez, uydurulmaz.
# --------------------------------------------------------------------------
AILE_SINIFI: dict[str, str] = {
    "Yazılım geliştirici ve teknik topluluklar": "teknik",
    "Yapay zekâ modeli, veri seti ve agent ekosistemi": "teknik",
    "Tarayıcı, e-ticaret ve CMS eklenti mağazaları": "urun",
    "Mobil uygulama mağazaları": "urun",
    "SaaS, yazılım ve hizmet inceleme siteleri": "urun",
    "Dijital ürün ve şablon pazar yerleri": "urun",
    "Oyun dikeyi": "urun",
    "Fiyat, teknoloji ve pazar sinyali karşılaştırma kaynakları": "urun",
    "Yerel işletme, harita ve hizmet dizinleri": "urun",
    "Kamu verisi ve istatistik": "kamu",
    "Regülasyon ve hukuk kaynakları": "kamu",
    "Patent ve marka": "kamu",
    "Sağlık ve biyoteknoloji dikeyi": "kamu",
    "Finans ve fintech dikeyi": "kamu",
}
VARSAYILAN_SINIF = "genel"

# Bu icerik durumlarinda gorunur urun/olcum metni yoktur; alan cikarilmaz.
ALAN_CIKARILMAYAN = frozenset({"aday-kesif", "politika", "js-kabugu",
                               "engel-sayfasi", "dosya-yok"})

# Sinif -> (alan adi, bu alani belgede arayan desen). Desen bulunmazsa alan
# uretilmez. 'engagement' alanlari AYRI tutulur ve talep/odeme kanitina
# CEVRILMEZ -- gorev kartinin acik yasagi.
ALAN_DESENLERI: dict[str, dict[str, re.Pattern[str]]] = {
    "teknik": {
        "paket_adi": re.compile(r'"name"\s*:\s*"([^"]{2,60})"'),
        "repo_yolu": re.compile(r"github\.com/([\w.-]+/[\w.-]+)"),
        "issue_sayisi": re.compile(r"(?i)(\d[\d,.]*)\s*(?:open\s+)?issues?\b"),
        "lisans": re.compile(r"(?i)\b(MIT|Apache-?2\.0|GPL-?[23]\.0|BSD-3-Clause|ISC|MPL-2\.0)\b"),
    },
    "urun": {
        "fiyat": re.compile(r"(?:[$€£₺]\s?\d[\d.,]*|\d[\d.,]*\s?(?:USD|EUR|TRY|GBP))"),
        "ozellik_basligi": re.compile(r"(?i)<h[23][^>]*>\s*(features?|özellikler)\s*</h[23]>"),
        # Baglam kelimesi sart: sitemap'teki <priority>0.7</priority>
        # cipciplak "0.7" olarak surum sayilmamali.
        "surum": re.compile(
            r"(?i)(?:\bv|\bversion\s+|\bsürüm\s+|\brelease\s+)(\d+\.\d+(?:\.\d+)?)\b"),
    },
    "kamu": {
        # Gostergenin bir degeri olmali; yalniz "index" kelimesi olcum degildir.
        "gosterge": re.compile(
            r"(?i)\b((?:index|indicator|rate|istatistik|endeks|gösterge)"
            r"[^.\n]{0,40}?\d[\d.,]*\s*%?)"),
        "mevzuat_atfi": re.compile(
            r"(?i)\b(regulation|directive|article\s+\d+|kanun|yönetmelik|madde\s+\d+)\b"),
        "yil_araligi": re.compile(r"\b((?:19|20)\d{2}\s*[-–]\s*(?:19|20)\d{2})\b"),
    },
    "genel": {},
}

# Etkilesim sayilari: bulunur, kaydedilir, ama ASLA talep/odeme kaniti
# olarak etiketlenmez. Adlari bunu acikca soyler.
ETKILESIM_DESENLERI: dict[str, re.Pattern[str]] = {
    "engagement_indirme_sayisi": re.compile(
        r"(?i)(\d[\d.,]*\s*[KMB]?\+?)\s*(?:downloads|installs|indirme(?:si|leri)?)\b"),
    "engagement_yorum_sayisi": re.compile(
        r"(?i)(\d[\d.,]*\s*[KMB]?\+?)\s*(?:reviews|ratings|yorum(?:lar)?)\b"),
    "engagement_yildiz": re.compile(r"(?i)(\d[\d.,]*\s*[KMB]?)\s*stars?\b"),
}

# Etkilesim alanlarinin NE OLMADIGI, veri sozlugunde ve her satirda yazili.
ETKILESIM_UYARISI = ("gözlemlenmiş etkileşim sayısı; ödeme davranışı ya da "
                     "talep kanıtı DEĞİLDİR")


# Gorev 4'un ayrimi burada da gecerli: bir alanin BULUNMASI ile
# OLCULEBILIR olmasi ayri seylerdir. "Kanun" kelimesinin gecmesi bir
# etikettir; "$1,890" bir olcumdur. Ikisi ayni sutunda ayni sey gibi
# durmasin diye tur yazilir.
ALAN_TURU: dict[str, str] = {
    "fiyat": "olcum", "issue_sayisi": "olcum", "surum": "olcum",
    "yil_araligi": "olcum", "engagement_indirme_sayisi": "olcum",
    "engagement_yorum_sayisi": "olcum", "engagement_yildiz": "olcum",
    "paket_adi": "etiket", "repo_yolu": "etiket", "lisans": "etiket",
    "ozellik_basligi": "etiket", "gosterge": "etiket", "mevzuat_atfi": "etiket",
}
ETIKET_NOTU = "sayfada geçen ifade; doğrulanmış bir ölçüm değildir"


def etkilesim_makul(alan: str, deger: str) -> bool:
    """Bulunan sayi bu alanin buyukluk araligina uyuyor mu.

    Aptoide sayfasinda puan (``4.33``) ile ``Download`` buton yazisi etiketler
    sokulunce yan yana geldi ve "indirme sayisi 4.33" gibi okundu. Indirme
    sayisi ya buyuk bir tam sayidir ya da K/M/B ekiyle yazilir; 10'un altinda
    ondalikli bir sayi indirme degil puandir.
    """
    if alan != "engagement_indirme_sayisi":
        return True
    if re.search(r"[KMB+]", deger, re.I) or "," in deger:
        return True
    try:
        sayi = float(deger.replace(" ", ""))
    except ValueError:
        return False
    return sayi >= 1000 and "." not in deger


def alan_cikar(sinif: str, metin: str, ham_metin: str) -> list[dict[str, str]]:
    """Yalniz gercekten bulunan alanlari dondurur."""
    bulunan: list[dict[str, str]] = []
    for alan, desen in ALAN_DESENLERI.get(sinif, {}).items():
        m = desen.search(ham_metin if alan == "ozellik_basligi" else metin)
        if m:
            deger = (m.group(1) if m.groups() else m.group(0)).strip()
            tur = ALAN_TURU.get(alan, "etiket")
            bulunan.append({"alan": alan, "deger": deger[:80],
                            "alan_sinifi": sinif, "alan_turu": tur,
                            "not": ETIKET_NOTU if tur == "etiket" else ""})
    for alan, desen in ETKILESIM_DESENLERI.items():
        m = desen.search(metin)
        if m and etkilesim_makul(alan, m.group(1).strip()):
            bulunan.append({"alan": alan, "deger": m.group(1).strip()[:40],
                            "alan_sinifi": "etkilesim", "alan_turu": "olcum",
                            "not": ETKILESIM_UYARISI})
    return bulunan


# --------------------------------------------------------------------------
# Ana akis
# --------------------------------------------------------------------------
def _oku(ad: str) -> list[dict[str, str]]:
    with (HERE / ad).open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _yaz(yol: Path, satirlar: list[dict[str, Any]]) -> None:
    if not satirlar:
        return
    with yol.open("w", newline="", encoding="utf-8") as handle:
        yazici = csv.DictWriter(handle, fieldnames=list(satirlar[0]))
        yazici.writeheader()
        yazici.writerows(satirlar)


def calistir() -> dict[str, Any]:
    import kategori_sozlugu as sozluk
    import veri_envanteri as envanter

    dizin = [r for r in _oku("ARTEFAKT-DIZINI.csv") if r["sonuc"] == "ok"]
    env = {r["source_id"]: r for r in _oku("VERI-ENVANTERI.csv")}
    kategori_kaynak = _oku("KATEGORI-KAYNAK.csv")
    kategori_soru = _oku("KATEGORI-SORU.csv")

    aile: dict[str, set[str]] = collections.defaultdict(set)
    urun_tipi: dict[str, set[str]] = collections.defaultdict(set)
    for r in kategori_kaynak:
        for g in r["kaynak_grubu"].split(" | "):
            aile[r["kaynak"]].add(g.strip())
        for tip in sozluk.URUN_TIPI_ESLEME.get(r["hedef"], ()):
            urun_tipi[r["kaynak"]].add(tip)
    grup_soru: dict[str, set[str]] = collections.defaultdict(set)
    for r in kategori_soru:
        grup_soru[r["kanit_kaynak_grubu"]].add(r["soru_id"])

    belgeler: list[dict[str, Any]] = []
    siniflandirma: list[dict[str, Any]] = []
    alanlar: list[dict[str, Any]] = []
    islenemeyen: list[dict[str, Any]] = []
    parmak: dict[str, tuple[int, str, str]] = {}

    for kayit in dizin:
        sid, ad = kayit.get("source_id", ""), kayit["ad"]
        if kayit["saklama"] == "kosu_json_icinde":
            islenemeyen.append({
                "source_id": sid, "ad": ad, "artefakt_hash": kayit["sha256"][:16],
                "source_url": kayit["cekilen_url"], "yontem": kayit["yontem"],
                "neden": "gövde saklanmamış; normalize edilecek içerik yok"})
            continue
        yol = HERE / kayit["dosya"]
        if not yol.exists():
            islenemeyen.append({
                "source_id": sid, "ad": ad, "artefakt_hash": kayit["sha256"][:16],
                "source_url": kayit["cekilen_url"], "yontem": kayit["yontem"],
                "neden": f"dizinde kayıtlı dosya bu checkout'ta yok: {kayit['dosya']}"})
            continue

        ham = yol.read_bytes()                      # salt okunur; asla yazilmaz
        cikarim = metin_cikar(ham[:400_000], kayit["mime"])
        metin = cikarim["metin"]
        icerik_durum, icerik_gerekce = envanter.icerik_durumu(
            kayit["yontem"], kayit["mime"], ham[:400_000])
        yayin, guncel, tarih_kaynagi = tarih_cikar(cikarim)
        dil, dil_guveni = dil_tespit(metin)
        bayraklar = kalite_bayraklari(cikarim, yayin, icerik_durum)

        normalize_hash = hashlib.sha256(metin.encode("utf-8")).hexdigest()
        # Kimlik (kaynak, artefakt) ciftinden turer. Uc ayri katalog kaydi
        # ayni robots.txt dosyasini paylasabiliyor (Facebook / Facebook
        # Marketplace / Facebook Pages); bunlar ayni ICERIK ama ayri
        # belgelerdir, ve aralarindaki bag BELGE-ILISKILERI.csv'de kurulur.
        belge_id = "doc-" + hashlib.sha256(
            f"{sid}|{kayit['sha256']}".encode()).hexdigest()[:12]
        kanonik = url_kanonik(kayit["cekilen_url"])

        # --- Tekrar tespiti (Seviye 1: tam eslesme) ---
        anahtar = normalize_hash if metin else f"bos:{kayit['sha256']}"
        ilk = parmak.get(anahtar)
        if ilk is not None and metin:
            bayraklar.append("duplicate_exact")

        belgeler.append({
            "document_id": belge_id,
            "artifact_hash": kayit["sha256"],
            "source_id": sid,
            "source_adi": ad,
            "source_url": kayit["cekilen_url"],
            "canonical_url": kanonik,
            "access_method": kayit["yontem"],
            "title": cikarim["baslik"][:300],
            "body_normalized": metin[:4000],
            "body_uzunlugu": len(metin),
            "body_original_ref": kayit["dosya"],
            "language": dil,
            "language_confidence": dil_guveni,
            "published_at": yayin,
            "updated_at": guncel,
            "collected_at": kayit["tarih"],
            "tarih_kaynagi": tarih_kaynagi,
            "content_hash": hashlib.sha256(ham).hexdigest(),
            "normalized_content_hash": normalize_hash,
            "normalization_version": NORMALIZASYON_SURUMU,
            "source_integrity_flags": ", ".join(sorted(set(bayraklar))),
        })

        if metin and anahtar not in parmak:
            parmak[anahtar] = (simhash(metin), belge_id, kanonik)

        # --- Yorumlayici siniflandirma: AYRI cikti ---
        sinyal = sozluk._metin_sinyalleri(ham[:400_000], kayit["cekilen_url"])
        belge_turu, ikincil, gerekce = sozluk.belge_turu_belirle(
            kayit["yontem"], kayit["mime"], sinyal)
        aileler = sorted(aile.get(ad, set()))
        niyetler = sorted({s for g in aileler for s in grup_soru.get(g, set())})
        siniflandirma.append({
            "document_id": belge_id,
            "artifact_hash": kayit["sha256"],
            "source_id": sid,
            "kaynak_ailesi": ", ".join(aileler) or "(aile atanmamış)",
            "urun_kategorileri": ", ".join(sorted(urun_tipi.get(ad, set()))) or "ortak-havuz",
            "belge_turu": belge_turu,
            "ikincil_belge_turu": ", ".join(ikincil),
            "arastirma_niyeti": ", ".join(niyetler),
            "icerik_durumu": icerik_durum,
            "siniflandirma_gerekcesi": gerekce,
            "icerik_gerekcesi": icerik_gerekce,
            "belirsizlik": ("belge türü belirlenemedi" if belge_turu == "belirsiz"
                            else ("dil belirlenemedi" if dil == "unknown" else "")),
            "olcum_kaniti_uretir_mi":
                "hayir" if belge_turu in ("ana-sayfa", "sitemap", "arama-sonucu",
                                          "politika-dosyasi", "belirsiz")
                or icerik_durum in ("js-kabugu", "aday-kesif") else "evet",
        })

        # --- Kategori bazinda cikarilabilen alanlar ---
        sinif = next((AILE_SINIFI[a] for a in aileler if a in AILE_SINIFI),
                     VARSAYILAN_SINIF)
        # Sitemap, robots ve bos JS kabugu urun alani tasimaz; oradan "fiyat"
        # ya da "surum" cikarmak uydurmadir.
        if icerik_durum in ALAN_CIKARILMAYAN:
            continue
        for bulgu in alan_cikar(sinif, metin, ham[:400_000].decode("utf-8", "replace")):
            alanlar.append({
                "document_id": belge_id, "artifact_hash": kayit["sha256"],
                "source_id": sid, "source_adi": ad, **bulgu})

    # --- Seviye 2: near-duplicate adaylari (SimHash, Faz4) ---
    iliskiler: list[dict[str, Any]] = []
    for b in belgeler:
        if "duplicate_exact" in b["source_integrity_flags"]:
            hedef = parmak.get(b["normalized_content_hash"])
            if hedef and hedef[1] != b["document_id"]:
                iliskiler.append({
                    "document_id": b["document_id"], "relation_type": "duplicate_of",
                    "hedef_document_id": hedef[1], "confidence": "1.00",
                    "created_by": "deterministic_rule",
                    "gerekce": "aynı normalize metin SHA-256 hash'i"})
    kanonik_sayaci: dict[str, list[str]] = collections.defaultdict(list)
    for b in belgeler:
        if b["canonical_url"]:
            kanonik_sayaci[b["canonical_url"]].append(b["document_id"])
    for url, kimlikler in kanonik_sayaci.items():
        for digeri in kimlikler[1:]:
            if digeri == kimlikler[0]:
                continue
            iliskiler.append({
                "document_id": digeri, "relation_type": "duplicate_of",
                "hedef_document_id": kimlikler[0], "confidence": "0.90",
                "created_by": "deterministic_rule",
                "gerekce": f"aynı canonical URL: {url[:60]}"})
    parmaklar = [(v[0], v[1]) for v in parmak.values() if v[0]]
    for i in range(len(parmaklar)):
        for j in range(i + 1, len(parmaklar)):
            mesafe = hamming(parmaklar[i][0], parmaklar[j][0])
            if 0 < mesafe <= 3:
                iliskiler.append({
                    "document_id": parmaklar[j][1],
                    "relation_type": "possible_duplicate",
                    "hedef_document_id": parmaklar[i][1],
                    "confidence": f"{1 - mesafe / 64:.2f}",
                    "created_by": "deterministic_rule",
                    "gerekce": f"SimHash Hamming mesafesi {mesafe} — ADAY, "
                               "otomatik silme değil"})
    return {"belgeler": belgeler, "siniflandirma": siniflandirma,
            "alanlar": alanlar, "iliskiler": iliskiler, "islenemeyen": islenemeyen}


# --------------------------------------------------------------------------
# Belgeler
# --------------------------------------------------------------------------
SOZLUK_ALANLARI: list[tuple[str, str, str]] = [
    ("document_id", "NORMALIZE-BELGELER", "`source_id` + artefakt hash'inden türeyen kimlik. Aynı dosyayı paylaşan iki kaynak ayrı belge olur; aralarındaki bağ `duplicate_of` ile kurulur."),
    ("source_adi", "NORMALIZE-BELGELER", "Kaynağın katalogdaki adı. Okunabilirlik içindir; birleştirmede `source_id` kullanılır."),
    ("artifact_hash", "NORMALIZE-BELGELER", "Diskteki ham dosyanın adı. Her satır buradan geri izlenir."),
    ("source_id", "NORMALIZE-BELGELER", "Kanonik kaynak kimliği; VERI-ENVANTERI.csv ile ortak."),
    ("source_url", "NORMALIZE-BELGELER", "Çekilen adres, **olduğu gibi**. Hiçbir koşulda değiştirilmez."),
    ("canonical_url", "NORMALIZE-BELGELER", "Yalnız bilinen takip parametreleri ayıklanmış hâli. İçerik parametresi silinmez."),
    ("access_method", "NORMALIZE-BELGELER", "Artefaktın hangi yüzeyden alındığı (root_html, sitemap_xml, rss_feed, common_crawl_warc …)."),
    ("title", "NORMALIZE-BELGELER", "JSON-LD `name`/`headline`, yoksa `og:title`, yoksa `<title>`. Uydurulmaz."),
    ("body_normalized", "NORMALIZE-BELGELER", "Script/stil/şablon atılmış, boşluğu ve kontrol karakteri temizlenmiş görünür metin (ilk 4000 karakter)."),
    ("body_uzunlugu", "NORMALIZE-BELGELER", "Kırpılmadan önceki tam uzunluk. 4000'den büyükse CSV'deki metin kısaltılmıştır."),
    ("body_original_ref", "NORMALIZE-BELGELER", "Ham dosyanın yolu. Ham içerik hiçbir zaman üzerine yazılmaz."),
    ("language", "NORMALIZE-BELGELER", "Düz yazıdan okunan dil kodu; adres listeleri sayılmaz. Emin olunamazsa `unknown`."),
    ("language_confidence", "NORMALIZE-BELGELER", "0–1. `unknown` satırlarda da yazılır, böylece eşiğe ne kadar yaklaşıldığı görünür."),
    ("published_at", "NORMALIZE-BELGELER", "Sayfanın kendi beyan ettiği yayın tarihi. **Yoksa boş bırakılır, tahmin edilmez.**"),
    ("updated_at", "NORMALIZE-BELGELER", "Sayfanın kendi beyan ettiği güncelleme tarihi."),
    ("collected_at", "NORMALIZE-BELGELER", "Bizim çektiğimiz an. `published_at` yerine **asla** kullanılmaz."),
    ("tarih_kaynagi", "NORMALIZE-BELGELER", "Tarihin nereden okunduğu (json-ld, meta:…, time[datetime]). Boşsa tarih bulunamamıştır."),
    ("content_hash", "NORMALIZE-BELGELER", "Ham baytların SHA-256'sı. Bit düzeyinde değişimi yakalar."),
    ("normalized_content_hash", "NORMALIZE-BELGELER", "Normalize metnin SHA-256'sı. Tam tekrar tespitinin dayanağı."),
    ("normalization_version", "NORMALIZE-BELGELER", f"Bu satırı üreten kural sürümü ({NORMALIZASYON_SURUMU}). Kural değişirse sürüm artar."),
    ("source_integrity_flags", "NORMALIZE-BELGELER", "Faz4 kalite bayrakları. **Kanıt skoru değildir**, veri bütünlüğü işaretidir."),
    ("kaynak_ailesi", "SINIFLANDIRMA", "Kaynağın ait olduğu kanıt ailesi (KATEGORI-KAYNAK.csv)."),
    ("urun_kategorileri", "SINIFLANDIRMA", "DR-L02'nin kanonik ürün tipleri. Her aileye bağlı kaynak için geçerli tipler."),
    ("belge_turu", "SINIFLANDIRMA", "DR-L02 sözlüğündeki 13 belge türünden biri ya da `belirsiz`."),
    ("ikincil_belge_turu", "SINIFLANDIRMA", "Aynı anda geçerli olabilen ikinci tür(ler). Tek etiket zorlanmaz."),
    ("arastirma_niyeti", "SINIFLANDIRMA", "Bu kaynağın ailesinin cevaplayabildiği araştırma soruları (KATEGORI-SORU.csv)."),
    ("icerik_durumu", "SINIFLANDIRMA", "DR-L01'in ölçümü: gercek-icerik, js-kabugu, aday-kesif, arsiv, politika …"),
    ("olcum_kaniti_uretir_mi", "SINIFLANDIRMA", "Bu belgeden **ölçülebilir** kanıt çıkar mı. Ana sayfa, sitemap ve JS kabuğu için `hayir`."),
    ("belirsizlik", "SINIFLANDIRMA", "Kararsız kalınan eksen. Boş olmayan her satır elle incelemeye adaydır."),
    ("relation_type", "BELGE-ILISKILERI", "`duplicate_of` (kesin) ya da `possible_duplicate` (aday). Faz4 ilişki sözlüğü."),
    ("confidence", "BELGE-ILISKILERI", "1.00 tam hash eşleşmesi · 0.90 aynı canonical URL · SimHash'te 1−(mesafe/64)."),
    ("created_by", "BELGE-ILISKILERI", "`deterministic_rule` — ilişkilerin hiçbiri modele sorularak üretilmedi."),
    ("alan", "KATEGORI-ALANLARI", "Bu belgeden çıkarılabilen alan adı (fiyat, surum, gosterge, engagement_…)."),
    ("alan_turu", "KATEGORI-ALANLARI", "`olcum` karşılaştırılabilir bir değer · `etiket` yalnız sayfada geçen bir ifade. Görev 4'teki ayrımın aynısı."),
    ("deger", "KATEGORI-ALANLARI", "Sayfada yazan değer, **olduğu gibi**. Birim çevrilmez, yorumlanmaz."),
    ("etkilesim", "KATEGORI-ALANLARI", "`engagement_*` alanlarında uyarı metni taşır: bu sayı ödeme davranışı değildir."),
]


def veri_sozlugu() -> str:
    satirlar = [
        "# Veri Sözlüğü — DR-L03 normalize veri kümesi", "",
        f"Üreten: `normalize_belgeler.py` · normalizasyon sürümü **{NORMALIZASYON_SURUMU}**",
        "",
        "Her alan ya diskteki bir artefaktta **yazan** bir şeydir ya da ondan",
        "deterministik bir kuralla hesaplanır. Hiçbir alan tahmin değildir.", "",
        "## Alanlar", "",
        "| Alan | Dosya | Anlamı |", "|---|---|---|",
    ]
    for ad, dosya, aciklama in SOZLUK_ALANLARI:
        satirlar.append(f"| `{ad}` | {dosya} | {aciklama} |")
    satirlar += [
        "", "## Kalite bayrakları", "",
        "Adlar `Faz4-Plan.md`'den birebir alınmıştır.", "",
        "| Bayrak | Ne demek |", "|---|---|",
        "| `invalid_payload` | Dosya beklenen biçimde çözümlenemedi |",
        "| `missing_body` | Görünür gövde metni yok |",
        f"| `short_content` | Gövde {KISA_ICERIK_ESIGI} karakterden kısa |",
        "| `missing_published_date` | Sayfa yayın tarihi beyan etmiyor |",
        "| `unknown_date` | Tarih hiçbir alandan okunamadı |",
        "| `source_policy_limited` | Kaynak politikası içeriği sınırlıyor (arşiv/robots) |",
        "| `quote_only` | Yalnız alıntılanabilir; tam metin yeniden yayımlanmaz |",
        "| `duplicate_exact` | Normalize metni daha önce görülmüş bir belgeyle birebir aynı |",
        "", "## Bu veri kümesinin cevaplayamadığı sorular", "",
        "- **Talep var mı?** Yok. `engagement_*` alanları gözlemlenmiş sayılardır;",
        "  ödeme davranışı değildir.",
        "- **İçerik güncel mi?** Belgelerin büyük kısmı tarih beyan etmiyor",
        "  (`unknown_date`). `collected_at` yalnızca bizim çekme anımızdır.",
        "- **Bu kaynak bu ürün için iyi mi?** Bu dosya kaynak seçmez; seçim",
        "  `SECIM-ORNEKLERI.csv` işidir.", "",
    ]
    return "\n".join(satirlar)


def donusum_kurallari(ozet: dict[str, Any]) -> str:
    b, sn = ozet["belgeler"], ozet["siniflandirma"]
    dil = collections.Counter(x["language"] for x in b)
    bayrak = collections.Counter(
        f for x in b for f in x["source_integrity_flags"].split(", ") if f)
    tur = collections.Counter(x["belge_turu"] for x in sn)
    iliski = collections.Counter(x["relation_type"] for x in ozet["iliskiler"])
    alan = collections.Counter(x["alan"] for x in ozet["alanlar"])
    olcum = collections.Counter(x["olcum_kaniti_uretir_mi"] for x in sn)

    def tablo(sayac, basliklar):
        cikti = [f"| {basliklar[0]} | {basliklar[1]} |", "|---|---:|"]
        cikti += [f"| `{k}` | {v} |" for k, v in sayac.most_common()]
        return "\n".join(cikti)

    return f"""# Dönüşüm ve Etiketleme Kuralları — DR-L03

Ham artefakt → normalize belge dönüşümünün tam kuralları. Tekrar çalıştırıldığında
aynı girdiden aynı çıktı üretilir; hiçbir adımda rastgelelik yoktur.

## Neden iki ayrı çıktı

`NORMALIZE-BELGELER.csv` **teknik**tir: başlık, metin, URL, tarih, dil, hash.
`SINIFLANDIRMA.csv` **yorumlayıcı**dır: belge türü, ürün kategorisi, niyet.

Ayrı tutulmalarının karşılığı somut: yarın sınıflandırma kuralı değişirse
{len(b)} belgenin metni yeniden çıkarılmaz, ve yanlış bir sınıflandırma kararı
doğru çıkarılmış metni kirletmez. İkisi `document_id` ile bağlanır.

## 1. Okuma

Ham dosyalar salt okunur açılır. `results/raw/` altındaki hiçbir bayt
değiştirilmez; `body_original_ref` ham dosyayı işaret eder.

## 2. Metin çıkarımı

`{"`, `".join(GURULTU_ETIKETLERI)}` etiketlerinin **içeriğiyle birlikte** atılması,
ardından kalan etiketlerin sökülmesi, HTML varlıklarının çözülmesi, kontrol
karakterlerinin silinmesi ve boşluğun tekleştirilmesi.

JSON-LD blokları ayrıca ayrıştırılır; başlık önceliği:
JSON-LD `name`/`headline` → `og:title` → `<title>`. Hiçbiri yoksa başlık boş kalır.

## 3. URL kanonikleştirme

Şema ve alan adı küçültülür, `www.` düşer, varsayılan port atılır, fragment
silinir. Sorgu parametrelerinden **yalnız bilinen takip parametreleri**
({len(TAKIP_PARAMETRELERI)} adet: `utm_*`, `gclid`, `fbclid` …) ayıklanır.
`?q=`, `?page=` gibi içeriği değiştiren parametreler korunur — silinseydi iki
farklı sayfa aynı belge sayılırdı. `source_url` her hâlükârda değişmeden saklanır.

## 4. Tarih — tahmin yok

Sıra: JSON-LD `datePublished` → `article:published_time` → `<time datetime>`.
Hiçbiri yoksa `published_at` **boş** kalır ve `missing_published_date` +
`unknown_date` bayrakları konur. `collected_at` ayrı bir alandır ve yayın tarihi
yerine geçmez.

Ölçülen: {len(b)} belgenin {bayrak.get("unknown_date", 0)} tanesi hiçbir tarih beyan etmiyor.
Tarih okunabilen {len(b) - bayrak.get("unknown_date", 0)} belgenin kaynağı `tarih_kaynagi` sütununda yazar.

## 5. Dil

Dil yalnızca **düz yazıdan** okunur. Adresler, alan adları ve dosya yolları
metinden çıkarılır; ardından {len(DURDURMA_KELIMELERI)} dilin durdurma kelimeleri sayılır.

İki eşik birden aranır: en yüksek payın ≥ {ASGARI_GUVEN} olması **ve** o dilden
en az {ASGARI_DURDURMA_CESIDI} **farklı** durdurma kelimesi görülmesi. İkincisi olmasaydı
sitemap'lerdeki `.com` tekrarı yüzünden adres listeleri "Portekizce" etiketlenirdi —
ilk koşuda tam olarak bu oldu. Emin olunamayan her belge `unknown` kalır.

{tablo(dil, ["Dil", "Belge"])}

## 6. Tekrar — silme değil, ilişkilendirme

Aynı içerik yeni bağımsız kanıt sayılmaz. Ama **hiçbir satır silinmez**;
`BELGE-ILISKILERI.csv` içinde ilişkilendirilir:

| Yöntem | İlişki | Güven |
|---|---|---|
| Normalize metin hash'i aynı | `duplicate_of` | 1.00 |
| Kanonik URL aynı | `duplicate_of` | 0.90 |
| SimHash Hamming mesafesi ≤ 3 | `possible_duplicate` | 1 − mesafe/64 |

{tablo(iliski, ["İlişki", "Satır"])}

`possible_duplicate` bir **adaydır**, karar değil: otomatik eleme yapılmaz.
Üçünün de `created_by` değeri `deterministic_rule`'dur.

## 7. Kategori bazında alan çıkarımı

Kaynağın ailesine göre sınıf seçilir ({", ".join(sorted(set(AILE_SINIFI.values())))}) ve o
sınıfın alan desenleri aranır. **Bulunmayan alan uydurulmaz**; satır yazılmaz.

{tablo(alan, ["Alan", "Bulgu"])}

`engagement_*` alanlarının her biri şu uyarıyı taşır:
> {ETKILESIM_UYARISI}

## 8. Sınıflandırma ve ölçüm kanıtı

{tablo(tur, ["Belge türü", "Belge"])}

Bir belgenin **ölçülebilir kanıt üretip üretmediği** ayrı sorudur. Ana sayfa,
sitemap, arama sonucu, politika dosyası, `belirsiz` ve JS kabuğu olan belgeler
`hayir` işaretlidir:

{tablo(olcum, ["Ölçüm kanıtı üretir mi", "Belge"])}

Bu oran kötü bir sonuç değil, **ölçülmüş** bir sonuçtur: kaynakların çoğundan
ana sayfa çekilmiştir, ana sayfa da fiyat/yorum/talep kanıtı taşımaz.

## 9. Kalite bayrakları

{tablo(bayrak, ["Bayrak", "Belge"])}

Bunlar kanıt skoru değildir. Bir belge `short_content` olabilir ve yine de
doğru bir fiyat taşıyabilir; bayrak yalnızca ne ölçüldüğünü söyler.

## 10. İşlenemeyenler

`ISLENEMEYEN-BELGELER.csv` iki durumu ayırır: gövdesi hiç saklanmamış kayıtlar
ve dizinde yazıp bu checkout'ta bulunmayan dosyalar. Hiçbiri "işlenmiş" sayılmaz.
"""


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--yaz", action="store_true",
                             help="cikti dosyalarini diske yaz")
    secenek = ayristirici.parse_args(argv)

    ozet = calistir()
    if not secenek.yaz:
        for ad, satirlar in ozet.items():
            print(f"{ad:16} {len(satirlar)}")
        return 0

    _yaz(HERE / "NORMALIZE-BELGELER.csv", ozet["belgeler"])
    _yaz(HERE / "SINIFLANDIRMA.csv", ozet["siniflandirma"])
    _yaz(HERE / "BELGE-ILISKILERI.csv", ozet["iliskiler"])
    _yaz(HERE / "KATEGORI-ALANLARI.csv", ozet["alanlar"])
    _yaz(HERE / "ISLENEMEYEN-BELGELER.csv", ozet["islenemeyen"])
    (HERE / "VERI-SOZLUGU.md").write_text(veri_sozlugu(), encoding="utf-8")
    (HERE / "DONUSUM-KURALLARI.md").write_text(donusum_kurallari(ozet),
                                               encoding="utf-8")

    print(f"NORMALIZE-BELGELER.csv    {len(ozet['belgeler'])}")
    print(f"SINIFLANDIRMA.csv         {len(ozet['siniflandirma'])}")
    print(f"BELGE-ILISKILERI.csv      {len(ozet['iliskiler'])}")
    print(f"KATEGORI-ALANLARI.csv     {len(ozet['alanlar'])}")
    print(f"ISLENEMEYEN-BELGELER.csv  {len(ozet['islenemeyen'])}")
    print("VERI-SOZLUGU.md")
    print("DONUSUM-KURALLARI.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
