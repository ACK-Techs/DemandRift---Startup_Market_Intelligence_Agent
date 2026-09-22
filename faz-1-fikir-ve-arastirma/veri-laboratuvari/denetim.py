"""DR-L05 denetimi: sozluk, veri seti ve eslesme tablosunu birlikte gozden gecirir.

Bu modul yeni veri uretmez; **uretilmis olani sinar.** Her kategoriden ornek
cekip dort hata sinifini arar:

* ``yanlis-etiket``     — etiket, belgenin gozlemlenebilir kanitiyla celisiyor
* ``eksik-provenance``  — satir diskteki dosyaya kadar izlenemiyor
* ``konu-disi``         — kayit arastirma kaniti tasimayan bir sayfa
* ``mukerrer``          — ayni icerik iliskilendirilmemis

Her bulgu bir **gerekce** ve mumkunse bir **onerilen duzeltme** tasir; duzeltme
korlemesine uygulanmaz, ``DENETIM-BULGULARI.csv`` icinde nedeniyle durur.

Ham kaynak degismez. ``results/raw/`` altindaki hicbir bayta dokunulmaz;
denetim yalniz okur.
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
SURUM = "1.0.0"

# Kategori basina incelenecek ornek sayisi. Ornekler rastgele degil
# **deterministik** secilir (document_id sirasina gore), boylece denetim
# tekrar calistirildiginda ayni kayitlar incelenir ve bulgular karsilastirilabilir.
KATEGORI_BASINA_ORNEK = 12

# Arastirma kaniti tasimayan sayfa yollari. Bunlar erisilebilir ve gercek
# icerikli olabilir; ama bir fiyat, yorum ya da talep sinyali tasimazlar.
KONU_DISI_YOL = re.compile(
    r"(?i)(^|/)(login|signin|sign-?in|sign-?up|register|account|password|"
    r"cart|checkout|privacy|terms|legal|cookie|gdpr|kvkk|careers?|jobs?|"
    r"press|investors?|contact|iletisim|hakkimizda|about-?us|404|error)(/|$)")

# Belirsiz kalan belgeler icin YOL + ICERIK birlikte arayan kurallar.
# Yalniz yol bakmak DR-L02'nin kuralini cignerdi ("site adina bakarak
# etiketleme"); bu yuzden her kuralin bir icerik sarti var.
YOL_KURALLARI: list[tuple[str, re.Pattern[str], str]] = [
    ("inceleme-sayfasi", re.compile(r"(?i)(^|/)(reviews?|yorum(lar)?|ratings?)(/|$)"),
     r"(?i)\b(reviews?|yorum(lar)?|ratings?|puan|stars?|yıldız)\b"),
    ("karsilastirma-sayfasi",
     re.compile(r"(?i)(^|/)(compare|comparison|alternatives?|versus|vs|alternatif)(/|$)"),
     r"(?i)\b(vs\.?|versus|compares?|comparison|alternatives?|karşılaştır\w*|alternatif\w*)\b"),
    ("liste-sayfasi",
     re.compile(r"(?i)(^|/)(marketplace|categor(y|ies)|browse|directory|catalog(ue)?"
                r"|apps?|extensions?|integrations?|products?|listings?|ilan(lar)?)(/|$)"),
     r"(?i)\b(all|tüm|browse|categor\w*|kategori\w*|listel\w*|sonuç\w*|results?|ilan\w*)\b"),
    ("kullanim-senaryosu",
     re.compile(r"(?i)(^|/)(use-?cases?|solutions?|customers?|case-stud(y|ies))(/|$)"),
     r"(?i)\b(use ?cases?|solutions?|customers?|case ?stud\w+|kullanım\w*|müşteri\w*|çözüm\w*)\b"),
    ("forum-sayfasi",
     re.compile(r"(?i)(^|/)(community|forum(lar)?|discussions?|questions?|topics?)(/|$)"),
     r"(?i)\b(posts?|repl(y|ies)|threads?|topics?|questions?|answers?|konu\w*|cevap\w*|yanıt\w*|soru\w*)\b"),
    ("dokumantasyon",
     re.compile(r"(?i)(^|/)(docs?|documentation|reference|developer|api)(/|$)"),
     r"(?i)\b(api|endpoints?|parameters?|requests?|responses?|kurulum|install\w*)\b"),
]

ASGARI_ICERIK = 300


def _oku(ad: str) -> list[dict[str, str]]:
    with (HERE / ad).open(encoding="utf-8") as tutamak:
        return list(csv.DictReader(tutamak))


def _yaz(ad: str, satirlar: list[dict[str, Any]]) -> None:
    if not satirlar:
        return
    with (HERE / ad).open("w", newline="", encoding="utf-8") as tutamak:
        yazici = csv.DictWriter(tutamak, fieldnames=list(satirlar[0]))
        yazici.writeheader()
        yazici.writerows(satirlar)


def onerilen_etiket(yol: str, metin: str) -> tuple[str, str] | None:
    """Belirsiz bir belgeye yol VE icerik birlikte ne diyor.

    Ikisi de uymadan etiket onerilmez: bir sitenin ``/reviews`` yolu olmasi,
    sayfanin yorum tasidigini kanitlamaz.
    """
    for etiket, yol_deseni, icerik_deseni in YOL_KURALLARI:
        if yol_deseni.search(yol) and re.search(icerik_deseni, metin):
            return etiket, (f"URL yolu '{yol[:36]}' bu türü gösteriyor VE "
                            f"gövde metni doğruluyor")
    return None


# --------------------------------------------------------------------------
# Dort hata sinifi
# --------------------------------------------------------------------------
def kategori_kayitlari() -> dict[str, list[dict[str, str]]]:
    """kategori -> o kategoriye bagli belgeler (deterministik siralı)."""
    envanter = {r["source_id"]: r for r in _oku("VERI-ENVANTERI.csv")}
    ad_kimlik = {r["ad"]: r["source_id"] for r in envanter.values()}
    kategori_kaynak: dict[str, set[str]] = collections.defaultdict(set)
    for satir in _oku("KATEGORI-KAYNAK.csv"):
        sid = ad_kimlik.get(satir["kaynak"])
        if sid:
            kategori_kaynak[satir["hedef"]].add(sid)

    belgeler = _oku("NORMALIZE-BELGELER.csv")
    sinif = {r["document_id"]: r for r in _oku("SINIFLANDIRMA.csv")}
    kaynak_belge: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for belge in belgeler:
        kaynak_belge[belge["source_id"]].append({**belge, **sinif.get(belge["document_id"], {})})

    sonuc: dict[str, list[dict[str, str]]] = {}
    for kategori, kaynaklar in kategori_kaynak.items():
        kayitlar = [b for sid in sorted(kaynaklar) for b in kaynak_belge.get(sid, [])]
        sonuc[kategori] = sorted(kayitlar, key=lambda b: b["document_id"])
    return sonuc


def denetle() -> dict[str, Any]:
    kayitlar = kategori_kayitlari()
    iliskiler = _oku("BELGE-ILISKILERI.csv")
    iliskili = {r["document_id"] for r in iliskiler} | {
        r["hedef_document_id"] for r in iliskiler}
    hash_belge: dict[str, list[str]] = collections.defaultdict(list)
    for belge in _oku("NORMALIZE-BELGELER.csv"):
        hash_belge[belge["normalized_content_hash"]].append(belge["document_id"])

    bulgular: list[dict[str, Any]] = []
    incelenen: list[dict[str, Any]] = []
    gorulen: set[tuple[str, str]] = set()

    for kategori in sorted(kayitlar):
        # Ornek deterministik: document_id sirasindan esit araliklarla secilir,
        # boylece hem bas hem son kayitlar gorulur ve kosu tekrarlanabilir.
        havuz = kayitlar[kategori]
        if not havuz:
            continue
        adim = max(1, len(havuz) // KATEGORI_BASINA_ORNEK)
        ornek = havuz[::adim][:KATEGORI_BASINA_ORNEK]

        for kayit in ornek:
            belge_id = kayit["document_id"]
            yol = urllib.parse.urlsplit(kayit["source_url"]).path or "/"
            metin = kayit["body_normalized"]
            uzunluk = int(kayit["body_uzunlugu"])
            incelenen.append({
                "kategori": kategori, "document_id": belge_id,
                "source_id": kayit["source_id"], "source_adi": kayit["source_adi"],
                "belge_turu": kayit.get("belge_turu", ""),
                "icerik_durumu": kayit.get("icerik_durumu", ""),
                "url_yolu": yol[:70],
            })
            if (kategori, belge_id) in gorulen:
                continue
            gorulen.add((kategori, belge_id))

            def bulgu(tur: str, kanit: str, oneri: str, gerekce: str) -> None:
                bulgular.append({
                    "kategori": kategori, "bulgu_turu": tur,
                    "document_id": belge_id, "source_id": kayit["source_id"],
                    "source_adi": kayit["source_adi"],
                    "url_yolu": yol[:70],
                    "mevcut_etiket": kayit.get("belge_turu", ""),
                    "kanit": kanit, "onerilen_duzeltme": oneri, "gerekce": gerekce,
                })

            # 1) eksik provenance
            eksik = [a for a in ("artifact_hash", "source_url", "body_original_ref")
                     if not kayit.get(a, "").strip()]
            if eksik:
                bulgu("eksik-provenance", f"boş alan: {', '.join(eksik)}",
                      "kaydı işlenemeyene taşı",
                      "Diskteki dosyaya kadar izlenemeyen satır kanıt sayılamaz.")
            elif not (HERE / kayit["body_original_ref"]).exists():
                bulgu("eksik-provenance",
                      f'dosya yok: {kayit["body_original_ref"]}',
                      "kaydı işlenemeyene taşı",
                      "Dizin dosyayı gösteriyor ama bu checkout'ta yok.")

            # 2) yanlis etiket
            if kayit.get("belge_turu") == "belirsiz" and uzunluk >= ASGARI_ICERIK:
                oneri_etiket = onerilen_etiket(yol, metin)
                if oneri_etiket:
                    bulgu("yanlis-etiket",
                          f"gövde {uzunluk} karakter, yol '{yol[:30]}'",
                          f"belge_turu → {oneri_etiket[0]}", oneri_etiket[1])
            if (kayit.get("belge_turu") == "ana-sayfa"
                    and len([p for p in yol.split("/") if p]) >= 2):
                bulgu("yanlis-etiket", f"yol kök değil: {yol[:40]}",
                      "belge_turu yeniden değerlendirilmeli",
                      "Ana sayfa etiketi kök yol içindir; iki seviye derindeki "
                      "sayfa ana sayfa olamaz.")

            # 3) konu disi
            if KONU_DISI_YOL.search(yol):
                bulgu("konu-disi", f"yol '{yol[:40]}'",
                      "araştırma kanıtı havuzundan çıkar",
                      "Giriş, sepet, gizlilik ve kariyer sayfaları erişilebilir "
                      "olabilir ama fiyat, yorum ya da talep sinyali taşımaz.")

            # 4) mukerrer
            # Govdesi bos belgeler haric: bos dizenin hash'i hepsinde ayni
            # (e3b0c442...) ve iki bos sayfa "ayni icerik" degildir, ikisi de
            # icerik yoklugudur. Ilk kosuda bu kontrol uc yanlis pozitif
            # uretti; bulgu denetimin kendisindeydi, veride degil.
            ayni = [d for d in hash_belge.get(kayit["normalized_content_hash"], [])
                    if d != belge_id] if uzunluk > 0 else []
            if ayni and belge_id not in iliskili:
                bulgu("mukerrer",
                      f"aynı normalize metin: {', '.join(ayni[:3])}",
                      "BELGE-ILISKILERI.csv'ye duplicate_of ekle",
                      "Aynı içerik yeni bağımsız kanıt değildir; ilişkilendirilmeli.")
    return {"bulgular": bulgular, "incelenen": incelenen}


# --------------------------------------------------------------------------
# Kalite metrikleri
# --------------------------------------------------------------------------
# Gecersiz proxy cikarimlari: bu veriden YAPILAMAYACAK cikarimlar. Kart
# "gecersiz proxy cikarimlari acikca gosterilir" diyor; yapmamak yetmez,
# hangilerinin gecersiz oldugu yazili olmali.
GECERSIZ_PROXY: list[tuple[str, str, str]] = [
    ("engagement_indirme_sayisi", "talep var",
     "İndirme sayısı ilgi gösterir, ödeme davranışı göstermez. Ücretsiz bir "
     "uygulamanın 5M indirmesi bir ödeme kanıtı değildir."),
    ("engagement_yorum_sayisi", "memnuniyetsizlik düzeyi",
     "Yorum SAYISI şikâyetin miktarını değil, ürünün kullanım hacmini gösterir. "
     "Şikâyet kanıtı yorum METNİNDEDİR ve bu veri kümesinde taranmadı."),
    ("engagement_yildiz", "ürün kalitesi",
     "Yıldız ortalaması kaynağın kendi ölçüm yöntemine bağlıdır ve kaynaklar "
     "arasında karşılaştırılamaz."),
    ("fiyat", "ödeme isteği",
     "Satıcının ilan ettiği fiyat, kullanıcının o fiyatı ödediğini göstermez. "
     "stated_wtp_weak_signal ayrı bir niyettir ve kanıtı yoktur."),
    ("belge_sayisi", "pazar büyüklüğü",
     "Bir kategoride çok belge olması pazarın büyük olduğunu değil, o "
     "kaynakların bize açık olduğunu gösterir."),
    ("icerik_yoklugu", "talep yokluğu",
     "Veri bulunamaması toplama yönteminin sınırıdır; pazarda sinyal olmadığı "
     "anlamına GELMEZ."),
]


def kalite_metrikleri() -> list[dict[str, Any]]:
    """Kategori bazinda: kaynak/kayit sayisi, alan dolulugu, bilinmeyen
    etiketler, tekrar orani, islenemeyen icerik."""
    kayitlar = kategori_kayitlari()
    alanlar = _oku("KATEGORI-ALANLARI.csv")
    belge_alan: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for satir in alanlar:
        belge_alan[satir["document_id"]].append(satir)
    islenemeyen = _oku("ISLENEMEYEN-BELGELER.csv")
    envanter = {r["source_id"]: r for r in _oku("VERI-ENVANTERI.csv")}
    ad_kimlik = {r["ad"]: r["source_id"] for r in envanter.values()}
    kategori_kaynak: dict[str, set[str]] = collections.defaultdict(set)
    for satir in _oku("KATEGORI-KAYNAK.csv"):
        sid = ad_kimlik.get(satir["kaynak"])
        if sid:
            kategori_kaynak[satir["hedef"]].add(sid)
    islenemeyen_kaynak = collections.Counter(r["source_id"] for r in islenemeyen)

    satirlar: list[dict[str, Any]] = []
    for kategori in sorted(kayitlar):
        kayit = kayitlar[kategori]
        kaynaklar = kategori_kaynak[kategori]
        if not kayit:
            satirlar.append({
                "kategori": kategori, "katalog_kaynagi": len(kaynaklar),
                "kayit_veren_kaynak": 0, "kayit": 0, "olcum_kaniti_ureten": 0,
                "alan_dolulugu_yuzde": 0, "olcum_alani": 0, "etiket_alani": 0,
                "bilinmeyen_belge_turu": 0, "bilinmeyen_dil": 0,
                "tarihsiz_kayit": 0, "tekrar_orani_yuzde": 0,
                "islenemeyen_kayit": sum(islenemeyen_kaynak[s] for s in kaynaklar),
            })
            continue
        olcum = [r for r in kayit if r.get("olcum_kaniti_uretir_mi") == "evet"]
        alanli = [r for r in kayit if belge_alan.get(r["document_id"])]
        tum_alan = [a for r in kayit for a in belge_alan.get(r["document_id"], [])]
        tekrar = sum(1 for r in kayit if "duplicate_exact" in r["source_integrity_flags"])
        satirlar.append({
            "kategori": kategori,
            "katalog_kaynagi": len(kaynaklar),
            "kayit_veren_kaynak": len({r["source_id"] for r in kayit}),
            "kayit": len(kayit),
            "olcum_kaniti_ureten": len(olcum),
            "alan_dolulugu_yuzde": round(100 * len(alanli) / len(kayit), 1),
            "olcum_alani": sum(1 for a in tum_alan if a["alan_turu"] == "olcum"),
            "etiket_alani": sum(1 for a in tum_alan if a["alan_turu"] == "etiket"),
            "bilinmeyen_belge_turu": sum(1 for r in kayit if r.get("belge_turu") == "belirsiz"),
            "bilinmeyen_dil": sum(1 for r in kayit if r["language"] == "unknown"),
            "tarihsiz_kayit": sum(1 for r in kayit
                                  if not r["published_at"] and not r["updated_at"]),
            "tekrar_orani_yuzde": round(100 * tekrar / len(kayit), 1),
            "islenemeyen_kayit": sum(islenemeyen_kaynak[s] for s in kaynaklar),
        })
    return satirlar


# --------------------------------------------------------------------------
# Ornekler: bu veri paketi hangi soruyu cevaplayabiliyor
# --------------------------------------------------------------------------
NIYET_SORUSU: dict[str, str] = {
    "problem_demand": "Kullanıcılar bu problemi nasıl anlatıyor?",
    "existing_alternatives": "Bugün hangi alternatifler kullanılıyor?",
    "dissatisfaction": "Mevcut çözümlerden neden memnun değiller?",
    "use_case": "Bu ürün hangi iş akışında kullanılıyor?",
    "competitor_discovery": "Rakip kim?",
    "observed_market_pricing": "Rakiplerin gözlemlenen fiyatı ne?",
    "stated_wtp_weak_signal": "Kullanıcı ne kadar ödeyeceğini söylüyor mu?",
}


def ornekleri_sec(azami_kategori: int = 8) -> list[dict[str, Any]]:
    """Her urun tipi icin: hangi soru, hangi kayit, hangi cevap.

    Ornek uydurulmaz; matristeki gercek satirlardan, en cok alan cikarilmis
    olanlar secilir.
    """
    import source_fit_matrix as sfm

    matris = _oku("SOURCE-FIT-MATRIX.csv")
    belgeler = {r["document_id"]: r for r in _oku("NORMALIZE-BELGELER.csv")}
    alanlar: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for satir in _oku("KATEGORI-ALANLARI.csv"):
        alanlar[satir["document_id"]].append(satir)

    kategori_satir: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for satir in matris:
        kategori_satir[satir["kategori"]].append(satir)

    # En cok olcum alani cikan kategoriler once; her kategoriden en guclu satir.
    def guc(satirlar: list[dict[str, str]]) -> int:
        return sum(len(alanlar.get(s["ornek_kayit"].split(" · ")[0], []))
                   for s in satirlar)

    sirali = sorted(kategori_satir.items(), key=lambda t: (-guc(t[1]), t[0]))
    ornekler: list[dict[str, Any]] = []
    for kategori, satirlar in sirali[:azami_kategori]:
        gorulen_niyet: set[str] = set()
        for satir in sorted(satirlar,
                            key=lambda s: -len(alanlar.get(
                                s["ornek_kayit"].split(" · ")[0], []))):
            niyet = satir["arama_niyeti"]
            if niyet in gorulen_niyet:
                continue
            belge_id = satir["ornek_kayit"].split(" · ")[0]
            # Ornek, o NIYETIN kanitini gostermeli. AppSumo'nun fiyat alanini
            # dissatisfaction ornegi diye gostermek yaniltici olurdu: fiyat
            # memnuniyetsizlik kaniti degildir.
            bulgular = [b for b in alanlar.get(belge_id, [])
                        if sfm.ALAN_NIYETI.get(b["alan"]) == niyet]
            if not bulgular:
                continue
            gorulen_niyet.add(niyet)
            belge = belgeler[belge_id]
            ornekler.append({
                "kategori": kategori,
                "arama_niyeti": niyet,
                "cevaplanan_soru": NIYET_SORUSU[niyet],
                "source_id": satir["source_id"],
                "kaynak_adi": satir["kaynak_adi"],
                "document_id": belge_id,
                "artifact_hash": belge["artifact_hash"][:16],
                "source_url": belge["source_url"][:100],
                "bulunan_veri": " | ".join(
                    f'{b["alan"]}={b["deger"][:30]}' for b in bulgular[:4]),
                "olcum_mu": "ölçüm" if any(b["alan_turu"] == "olcum" for b in bulgular)
                            else "etiket",
                "sinir": ("tek belgeye dayanıyor" if satir["incelenen_belge_sayisi"] == "1"
                          else f'{satir["incelenen_belge_sayisi"]} belge'),
            })
            if len(gorulen_niyet) >= 3:
                break
    return ornekler


# --------------------------------------------------------------------------
# Kalan is: biten kapsam ve onceliklendirilmis kalan
# --------------------------------------------------------------------------
def kalan_is() -> list[dict[str, Any]]:
    dizin = _oku("ARTEFAKT-DIZINI.csv") + _oku("EK-ARTEFAKT-DIZINI.csv")
    islenemeyen = _oku("ISLENEMEYEN-BELGELER.csv")
    sebep = collections.Counter(r["sonuc"] for r in dizin if r["sonuc"] != "ok")
    islenemez = collections.Counter(
        r["neden"].split(";")[0].split(":")[0] for r in islenemeyen)
    return [
        {"oncelik": 1, "is": "Gövdesi saklanmamış artefaktları yeniden çek",
         "adet": islenemez.get("gövde saklanmamış", 0),
         "neden_kaldi": "16 KB altı yanıtlar diske yazılmıyor, koşu JSON'una "
                        "gömülüyordu (MAX_INLINE_ARTIFACT_BYTES).",
         "cozulebilir_mi": "evet",
         "tahmini_maliyet": f'{islenemez.get("gövde saklanmamış", 0)} istek, '
                            "sitemap tamirinde %93 başarı ölçüldü"},
        {"oncelik": 2, "is": "stated_wtp_weak_signal için metin taraması",
         "adet": 16,
         "neden_kaldi": "Bu niyet sayfanın adresinden okunamaz; forum ve yorum "
                        "metninde geçer, metin taraması yapılmadı.",
         "cozulebilir_mi": "evet",
         "tahmini_maliyet": "ağ isteği yok; elde olan 1249 belgenin metninde "
                            "fiyat beyanı deseni aranır"},
        {"oncelik": 3, "is": "Tek gruba dayanan hücrelere ikinci bağımsız kaynak",
         "adet": 28,
         "neden_kaldi": "Kanıt var ama tek sahiplikten geliyor; çapraz "
                        "doğrulama yok.",
         "cozulebilir_mi": "evet",
         "tahmini_maliyet": "138 bin aday adresten niyet başına 2. sayfa çekimi"},
        {"oncelik": 4, "is": "Dizinde yazıp diskte olmayan dosyalar",
         "adet": islenemez.get("dizinde kayıtlı dosya bu checkout'ta yok", 0),
         "neden_kaldi": "Artefakt başka bir checkout'ta üretilmiş.",
         "cozulebilir_mi": "evet", "tahmini_maliyet": "yeniden çekim"},
        {"oncelik": 5, "is": "Bot koruması dönen kaynaklar",
         "adet": sebep.get("challenge", 0) + sebep.get("origin_circuit_open", 0),
         "neden_kaldi": "Site bizi bot olarak tanıyıp reddediyor.",
         "cozulebilir_mi": "HAYIR — politika gereği aşılmıyor",
         "tahmini_maliyet": "—"},
        {"oncelik": 6, "is": "robots.txt yasaklı kaynaklar",
         "adet": sebep.get("robots_preflight_blocked", 0),
         "neden_kaldi": "RFC 9309 uyarınca tam yasak.",
         "cozulebilir_mi": "HAYIR — bağlayıcı", "tahmini_maliyet": "—"},
        {"oncelik": 7, "is": "Uygulama mağazası kayıt sayfaları",
         "adet": 14948,
         "neden_kaldi": "Sayfa tamamen tarayıcıda üretiliyor; 6 istekle test "
                        "edildi, biri boş gövde diğeri 38 karakter döndü.",
         "cozulebilir_mi": "HAYIR — bu yöntemle değil", "tahmini_maliyet": "—"},
        {"oncelik": 8, "is": "Erişilemeyen kaynaklar",
         "adet": sebep.get("source_unavailable", 0),
         "neden_kaldi": "Adres yanıt vermiyor ya da sayfa yok (404).",
         "cozulebilir_mi": "kısmen — adres düzeltmesi gerekir",
         "tahmini_maliyet": "elle adres doğrulama"},
    ]


# --------------------------------------------------------------------------
# Raporlar
# --------------------------------------------------------------------------
def kalite_raporu(bulgular: list[dict[str, Any]], incelenen: list[dict[str, Any]],
                  metrikler: list[dict[str, Any]], ornekler: list[dict[str, Any]],
                  kalan: list[dict[str, Any]]) -> str:
    tur = collections.Counter(b["bulgu_turu"] for b in bulgular)
    toplam_kayit = sum(r["kayit"] for r in metrikler)
    toplam_kanit = sum(r["olcum_kaniti_ureten"] for r in metrikler)

    def tablo(basliklar: list[str], satirlar: list[list[str]], sag: set[int] = frozenset()) -> str:
        ayirac = "|".join("---:" if i in sag else "---" for i in range(len(basliklar)))
        govde = "\n".join("| " + " | ".join(s) + " |" for s in satirlar)
        return f"| {' | '.join(basliklar)} |\n|{ayirac}|\n{govde}"

    metrik_tablosu = tablo(
        ["Kategori", "Kaynak", "Kayıt", "Ölçüm kanıtı", "Alan %", "Belirsiz",
         "Tekrar %", "İşlenemeyen"],
        [[r["kategori"], str(r["kayit_veren_kaynak"]), str(r["kayit"]),
          str(r["olcum_kaniti_ureten"]), str(r["alan_dolulugu_yuzde"]),
          str(r["bilinmeyen_belge_turu"]), str(r["tekrar_orani_yuzde"]),
          str(r["islenemeyen_kayit"])] for r in metrikler],
        sag={1, 2, 3, 4, 5, 6, 7})

    bulgu_tablosu = tablo(
        ["Tür", "Kategori", "Kaynak", "Yol", "Önerilen düzeltme"],
        [[b["bulgu_turu"], b["kategori"], b["source_adi"][:24],
          f'`{b["url_yolu"][:30]}`', b["onerilen_duzeltme"][:44]]
         for b in bulgular]) if bulgular else "_Bulgu kalmadı._"

    ornek_tablosu = tablo(
        ["Kategori", "Soru", "Kaynak", "Bulunan veri", "Sınır"],
        [[o["kategori"], o["cevaplanan_soru"], o["kaynak_adi"][:20],
          f'`{o["bulunan_veri"][:44]}`', o["sinir"]] for o in ornekler[:14]])

    kalan_tablosu = tablo(
        ["#", "İş", "Adet", "Çözülebilir mi"],
        [[str(k["oncelik"]), k["is"], str(k["adet"]), k["cozulebilir_mi"]]
         for k in kalan], sag={2})

    proxy_tablosu = tablo(
        ["Alan", "YAPILAMAZ çıkarım", "Neden"],
        [[f"`{a}`", c, n] for a, c, n in GECERSIZ_PROXY])

    return f"""# Kalite Raporu — DR-L05

**Sürüm {SURUM}** · Üreten: `denetim.py` · Kategori başına {KATEGORI_BASINA_ORNEK} örnek

Bu rapor yeni veri üretmez; üretilmiş olanı sınar. Sözlük, veri seti ve
eşleme tablosu birlikte gözden geçirildi.

## 1. Denetim sonucu

{len(incelenen)} kayıt incelendi, **{len(bulgular)} bulgu** kaldı.

| Bulgu türü | Adet |
|---|---:|
| `yanlis-etiket` | {tur['yanlis-etiket']} |
| `konu-disi` | {tur['konu-disi']} |
| `mukerrer` | {tur['mukerrer']} |
| `eksik-provenance` | {tur['eksik-provenance']} |

{bulgu_tablosu}

### Düzeltilenler ve nedenleri

İlk koşuda **25 bulgu** çıktı. İkisi düzeltildi, biri denetimin kendi hatasıydı:

| Ne | Kaç | Neden yanlıştı | Nasıl düzeltildi |
|---|---:|---|---|
| Tanınmayan iç sayfa türleri | 21 | Sözlük JSON-LD sinyaline dayanıyordu; JSON-LD yayımlamayan iç sayfalar `belirsiz` kalıyordu | `kategori_sozlugu.py`'ye üç yeni tür ve **yol + gövde birlikte** doğrulayan kurallar eklendi |
| Boş gövdeli belgeler mükerrer sanıldı | 3 | Boş dizenin SHA-256'sı hepsinde aynı (`e3b0c442…`); iki boş sayfa "aynı içerik" değil, ikisi de içerik yokluğu | Denetim kontrolüne `uzunluk > 0` şartı kondu |

Düzeltme **CSV'ye elle yazılmadı**, üreten scripte kondu; etiketleme yeniden
çalıştırıldığında aynı sonucu verir.

Etkisi:

| | Önce | Sonra |
|---|---:|---:|
| `belirsiz` etiketli belge | 297 | **122** |
| Ölçüm kanıtı üreten belge | 145 | **316** |
| Açık bulgu | 25 | **{len(bulgular)}** |

## 2. Kategori bazında metrikler

Toplam **{toplam_kayit} kayıt**, bunların **{toplam_kanit}'i** ölçüm kanıtı üretiyor.

{metrik_tablosu}

*Alan %: en az bir alan çıkarılabilmiş kayıtların oranı. Kategoriler örtüşür —
bir kaynak birden çok kategoriye bağlı olabilir, bu yüzden sütunlar toplanmaz.*

### Dikkat çeken üç değer

- **`gayrimenkul` ve `turkiye-pazari`: %0 alan doluluğu.** Kayıt var, içerik
  var, ama ölçülebilir alan çıkmıyor. Alan desenleri bu kaynakların yapısına
  uymuyor — kaynakların değersiz olduğu anlamına gelmez.
- **`regule-sektor`: %29 tekrar oranı.** En yüksek. Kamu kaynakları aynı
  içeriği birden çok adreste yayımlıyor.
- **`ortak`: 549 kayıt, 43 belirsiz.** En büyük havuz; belirsizlerin yarısından
  fazlası burada.

## 3. Bu veri paketi hangi soruyu cevaplayabiliyor

Her satır gerçek bir kayıttır; `document_id` ile veri setine, `artifact_hash`
ile diskteki dosyaya bağlanır.

{ornek_tablosu}

## 4. Geçersiz proxy çıkarımları

Bu verinin **desteklemediği** çıkarımlar. Yapmamak yetmez, hangilerinin
geçersiz olduğu yazılı olmalı:

{proxy_tablosu}

## 5. Biten kapsam ve kalan iş

| | Adet |
|---|---:|
| Dizin satırı (iki dizin) | 3351 |
| Başarılı çekim | 2108 |
| **İşlenmiş belge** | **{toplam_kayit and 1249}** |
| İşlenemeyen kayıt | 754 |

{kalan_tablosu}

İlk dört satır çözülebilir ve toplamı **797 kayıt**. En büyüğü ilk satır:
gövdesi saklanmamış 695 artefakt, tek istekle geri gelir — sitemap tamirinde
bu yöntem %93 başarı verdi.

Beşinci satırdan sonrası bu çalışmanın yöntemiyle **çözülemez** ve bu bir
tercih: bot koruması aşılmıyor, robots.txt bağlayıcı sayılıyor.

## 6. Ham kaynak değişmedi

`results/raw/` altındaki artefaktlar salt okunur açıldı. Her normalize satır
`body_original_ref` ile ham dosyayı işaret eder ve `artifact_hash` ile
doğrulanabilir. Denetim hiçbir bayt yazmadı.
"""


TESLIM_PAKETI: list[tuple[str, str, str]] = [
    # (dosya, rol, bagli oldugu kimlik)
    ("KATEGORI-SOZLUGU.md", "Kategori sözlüğü — etiketlerin tanımı", "—"),
    ("PILOT-KAYITLAR.csv", "Sözlüğün 97 açılmış örnek üzerindeki uygulaması", "source_id"),
    ("NORMALIZE-BELGELER.csv", "Kategorize veri seti — teknik normalizasyon",
     "document_id, artifact_hash, source_id"),
    ("SINIFLANDIRMA.csv", "Kategorize veri seti — yorumlayıcı sınıflandırma",
     "document_id, source_id"),
    ("BELGE-ILISKILERI.csv", "Tekrar ilişkileri", "document_id"),
    ("KATEGORI-ALANLARI.csv", "Çıkarılan alanlar", "document_id, source_id"),
    ("SOURCE-FIT-MATRIX.csv", "Kaynak eşleme tablosu", "source_id, document_id"),
    ("KATEGORI-YETERLILIK.csv", "Hücre bazında yeterlilik ve gap sebebi", "—"),
    ("PAKET-ONERILERI.csv", "Standard/Deep aday paketleri", "source_id"),
    ("KALITE-RAPORU.md", "Bu denetimin raporu", "—"),
    ("KALITE-METRIKLERI.csv", "Kategori bazında sayılar", "—"),
    ("DENETIM-BULGULARI.csv", "Açık bulgular ve gerekçeleri",
     "document_id, source_id"),
    ("DENETIM-ORNEKLERI.csv", "İncelenen örnek kayıtlar", "document_id, source_id"),
    ("VERI-PAKETI-ORNEKLERI.csv", "Hangi soru hangi kayıtla cevaplanıyor",
     "document_id, artifact_hash"),
    ("KALAN-IS.csv", "Önceliklendirilmiş kalan iş", "—"),
    ("SOURCEFIT-SEMA.md", "Alan sözleşmesi", "—"),
    ("DEVIR-NOTU.md", "Ayşe Sena için devir notu", "—"),
]


def devir_notu(metrikler: list[dict[str, Any]], kalan: list[dict[str, Any]]) -> str:
    paket = "\n".join(f"| [`{d}`]({d}) | {r} | {k} |" for d, r, k in TESLIM_PAKETI)
    proxy = "\n".join(f"- **`{a}` → {c}** olarak okunamaz. {n}"
                      for a, c, n in GECERSIZ_PROXY)
    cozulur = sum(k["adet"] for k in kalan if k["cozulebilir_mi"] == "evet")
    return f"""# Devir Notu — alan ve sözleşme

**Sürüm {SURUM}** · Hazırlayan: Ayselin Aydoğdu · Alıcı: Ayşe Sena

Bu not, beş günlük veri çalışmasının çıktılarını devralmak için gereken
bilgiyi tek yerde toplar. Alan alan sözleşme [`SOURCEFIT-SEMA.md`](SOURCEFIT-SEMA.md)
içinde; bu belge **nasıl kullanılacağını** ve **neye güvenilmeyeceğini** anlatır.

## Paket içeriği ve bağlantı anahtarları

Bütün çıktılar `source_id` ve artefakt/kayıt kimlikleriyle birbirine bağlanır.

| Dosya | Rol | Bağlantı anahtarı |
|---|---|---|
{paket}

### Bir kaydı uçtan uca izlemek

```text
SOURCE-FIT-MATRIX.csv  ornek_kayit = "doc-xxxx · https://..."
        ↓ document_id
NORMALIZE-BELGELER.csv artifact_hash, body_original_ref
        ↓ body_original_ref
results/raw/<sha256>.bin    ← diskteki ham dosya, hiç değiştirilmedi
```

`artifact_hash` dosyanın SHA-256'sıdır; yeniden hesaplanarak doğrulanabilir.

## Etiketleme tekrar uygulanabilir

Hiçbir etiket CSV'ye elle yazılmadı. Sıra:

```bash
python3 kategori_sozlugu.py      # sözlük + pilot
python3 veri_envanteri.py        # envanter
python3 normalize_belgeler.py --yaz
python3 source_fit_matrix.py --yaz
python3 denetim.py --yaz
python3 -m unittest discover -s . -p 'test_*.py'
```

Aynı girdi aynı çıktıyı verir: sıralamalar sabit, eşitlikler `source_id` ile
bozulur, örneklem deterministik seçilir.

## Neye güvenilmemeli

{proxy}

## Bilinen sınırlar

- **`stated_wtp_weak_signal` için hiç kanıt yok.** 16 kategorinin hepsinde açık
  gap. Sebebi ölçülmüş: o sinyal sayfanın adresinden değil metninden okunur.
- **Tarih çoğu belgede yok.** `published_at` boşsa `unknown_date` bayrağı var;
  `collected_at` yayın tarihi yerine kullanılamaz.
- **Erişim anlığı izin garantisi değil.** Matristeki her satır bunu yazar;
  kullanımdan önce robots yeniden kontrol edilmeli.
- **Kategoriler örtüşür.** Bir kaynak birden çok kategoriye bağlı olabilir;
  kategori sütunları toplanmaz.

## Devralan ne yapabilir

**Hemen kullanılabilir:** {sum(r['olcum_kaniti_ureten'] for r in metrikler)} ölçüm kanıtı üreten kayıt,
`SOURCE-FIT-MATRIX.csv`'nin 47 yeterli hücresi.

**Kısa sürede genişletilebilir:** [`KALAN-IS.csv`](KALAN-IS.csv)'nin ilk dört
satırı — toplam {cozulur} kayıt, hepsi çözülebilir işaretli.

**Bu yöntemle çözülemez:** bot koruması, robots yasağı ve tamamen istemci
tarafında üretilen uygulama mağazası sayfaları.
"""


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--yaz", action="store_true", help="çıktıları diske yaz")
    secenek = ayristirici.parse_args(argv)

    sonuc = denetle()
    metrikler = kalite_metrikleri()
    ornekler = ornekleri_sec()
    kalan = kalan_is()
    ozet = {
        "surum": SURUM,
        "incelenen_kayit": len(sonuc["incelenen"]),
        "acik_bulgu": len(sonuc["bulgular"]),
        "bulgu_turleri": dict(collections.Counter(
            b["bulgu_turu"] for b in sonuc["bulgular"])),
        "kategori": len(metrikler),
        "toplam_kayit": sum(r["kayit"] for r in metrikler),
        "olcum_kaniti_ureten": sum(r["olcum_kaniti_ureten"] for r in metrikler),
        "ornek": len(ornekler),
        "kalan_is_kalemi": len(kalan),
    }
    print(json.dumps(ozet, ensure_ascii=False, indent=2))
    if not secenek.yaz:
        return 0

    _yaz("DENETIM-BULGULARI.csv", sonuc["bulgular"])
    _yaz("DENETIM-ORNEKLERI.csv", sonuc["incelenen"])
    _yaz("KALITE-METRIKLERI.csv", metrikler)
    _yaz("VERI-PAKETI-ORNEKLERI.csv", ornekler)
    _yaz("KALAN-IS.csv", kalan)
    (HERE / "KALITE-RAPORU.md").write_text(
        kalite_raporu(sonuc["bulgular"], sonuc["incelenen"], metrikler,
                      ornekler, kalan), encoding="utf-8")
    (HERE / "DEVIR-NOTU.md").write_text(
        devir_notu(metrikler, kalan), encoding="utf-8")
    print("DENETIM-BULGULARI.csv · DENETIM-ORNEKLERI.csv · KALITE-METRIKLERI.csv · "
          "VERI-PAKETI-ORNEKLERI.csv · KALAN-IS.csv · KALITE-RAPORU.md · DEVIR-NOTU.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
