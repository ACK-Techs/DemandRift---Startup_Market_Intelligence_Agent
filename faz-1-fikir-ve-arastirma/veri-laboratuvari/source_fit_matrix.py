"""SourceFitMatrix v1 — hangi kategorinin hangi sorusunu hangi kaynak cevapliyor.

Bu dosya yeni veri toplamaz. DR-L03'un normalize veri kumesini, Gorev 4'un
alan/izin matrisini ve Gorev 3'un arama yuzeylerini birlestirip **incelenmis
icerige dayanan** eslesmeler uretir.

Uc kural, gorev kartindan, ve uygulanislari:

1. **Her eslesme incelenmis icerikle desteklenir.** Bir satirin var olmasi
   icin o kaynaktan acilmis bir belge ve o belgeden cikarilmis bir sey
   gerekir. ``ornek_kayit`` her satirda o belgenin kimligini ve adresini
   tasir; dogrulanamayan eslesme satir olmaz, ``KATEGORI-YETERLILIK.csv``
   icinde **gap** olur.

2. **Ayni kaynagin kopyalari bagimsiz sayilmaz.** ``bagimsizlik_grubu`` iki
   kaynagi ayni gruba koyar: kayitli alan adlari ayniysa, ya da belgeleri
   ``BELGE-ILISKILERI.csv`` icinde ``duplicate_of`` ile bagliysa. Yeterlilik
   sayimi kaynak degil **grup** sayar.

3. **Beyan edilen odeme istegi gercek odeme davranisindan ayrilir.**
   ``observed_market_pricing`` satici sayfasinda YAZAN fiyattir.
   ``stated_wtp_weak_signal`` kullanicinin "su kadar oderim" demesidir ve
   Faz2-Plan.md'ye gore **gercek odeme davranisi sayilmaz**. Ikisi ayri
   niyettir ve bu veri kumesinde ikincisinin kaniti yoktur; her kategoride
   acik gap olarak durur.

Ayrica: erisim anligi (``cekildi``) **guncel izin garantisi degildir**. Her
satir ``erisim_kisiti`` icinde snapshot tarihini ve robots durumunu tasir,
ve kullanimdan once yeniden kontrol gerektigini soyler.
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

# Faz2-Plan.md'nin yedi arama niyeti. Sira sabittir; ciktilarda bu sira kullanilir.
NIYETLER: tuple[str, ...] = (
    "problem_demand", "existing_alternatives", "dissatisfaction", "use_case",
    "competitor_discovery", "observed_market_pricing", "stated_wtp_weak_signal",
)

NIYET_TANIMI: dict[str, str] = {
    "problem_demand": "Kullanıcıların problemi veya ihtiyacı nasıl anlattığı",
    "existing_alternatives": "Bugün hangi ürün, yöntem veya workaround kullanıldığı",
    "dissatisfaction": "Mevcut çözümlerle ilgili şikâyet ve eksikler",
    "use_case": "Kullanım bağlamı ve gerçek iş akışı",
    "competitor_discovery": "Doğrudan ve dolaylı rakip adayları",
    "observed_market_pricing": "Satıcı sayfasında yayımlanan fiyat, paket ve ticari model",
    "stated_wtp_weak_signal": (
        "Kullanıcının açık fiyat ifadesi. ZAYIF BEYAN SİNYALİDİR; "
        "gerçek ödeme davranışı sayılmaz (Faz2-Plan.md)"),
}

# Bu niyet sayfanin ADRESINDEN okunamaz: forum ve yorum metninde gecer.
# Uydurma desen yazmak yerine yoklugu acikca kaydedilir.
METINDEN_OKUNAN = frozenset({"stated_wtp_weak_signal"})

# Cikarilan alan -> hangi niyetin kaniti sayilir.
ALAN_NIYETI: dict[str, str] = {
    "fiyat": "observed_market_pricing",
    "engagement_yorum_sayisi": "dissatisfaction",
    "engagement_yildiz": "dissatisfaction",
    "engagement_indirme_sayisi": "competitor_discovery",
    "surum": "competitor_discovery",
    "paket_adi": "competitor_discovery",
    "repo_yolu": "existing_alternatives",
    "lisans": "existing_alternatives",
    "issue_sayisi": "dissatisfaction",
    "ozellik_basligi": "use_case",
    "gosterge": "problem_demand",
    "mevzuat_atfi": "use_case",
    "yil_araligi": "problem_demand",
}

# Yeterlilik esikleri: kaynak degil BAGIMSIZ GRUP sayilir.
YETERLI_GRUP = 2
KANIT_ESIGI_METIN = 500


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


def kayitli_alan(url: str) -> str:
    """Alan adinin kayitli kismi: app.ornek.co.uk -> ornek.co.uk.

    Bagimsizlik icin kullanilir; ayni sirketin iki alt alan adi bagimsiz
    kanit degildir.
    """
    host = urllib.parse.urlsplit(url).netloc.lower().split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    parcalar = host.split(".")
    if len(parcalar) >= 3 and parcalar[-2] in {"co", "com", "org", "gov", "net", "ac"}:
        return ".".join(parcalar[-3:])
    return ".".join(parcalar[-2:]) if len(parcalar) >= 2 else host


# --------------------------------------------------------------------------
# Bagimsizlik: ayni kaynagin kopyalari bagimsiz sayilmaz
# --------------------------------------------------------------------------
def bagimsizlik_gruplari(belgeler: list[dict[str, str]],
                         iliskiler: list[dict[str, str]]) -> dict[str, str]:
    """source_id -> grup adi.

    Iki kaynak ayni gruba duser: (a) kayitli alan adlari ayniysa,
    (b) belgeleri ``duplicate_of`` ile bagliysa. Ikincisi Facebook /
    Facebook Marketplace / Facebook Pages gibi ayri katalog kayitlarinin
    ayni dosyayi paylastigi durumu yakalar.
    """
    ebeveyn: dict[str, str] = {}

    def kok(x: str) -> str:
        while ebeveyn.get(x, x) != x:
            ebeveyn[x] = ebeveyn.get(ebeveyn[x], ebeveyn[x])
            x = ebeveyn[x]
        return x

    def birlestir(a: str, b: str) -> None:
        ka, kb = kok(a), kok(b)
        if ka != kb:
            ebeveyn[max(ka, kb)] = min(ka, kb)

    alan_kaynak: dict[str, list[str]] = collections.defaultdict(list)
    belge_kaynak: dict[str, str] = {}
    for satir in belgeler:
        sid = satir["source_id"]
        if not sid:
            continue
        ebeveyn.setdefault(sid, sid)
        belge_kaynak[satir["document_id"]] = sid
        alan_kaynak[kayitli_alan(satir["source_url"])].append(sid)

    for kaynaklar in alan_kaynak.values():
        for digeri in kaynaklar[1:]:
            birlestir(kaynaklar[0], digeri)
    for iliski in iliskiler:
        if iliski["relation_type"] != "duplicate_of":
            continue
        a = belge_kaynak.get(iliski["document_id"])
        b = belge_kaynak.get(iliski["hedef_document_id"])
        if a and b:
            birlestir(a, b)

    return {sid: f"grup-{kok(sid)}" for sid in ebeveyn}


# --------------------------------------------------------------------------
# Kanit toplama
# --------------------------------------------------------------------------
def kanitlari_topla() -> dict[str, Any]:
    """Her (kaynak, niyet) icin incelenmis belgelerden kanit toplar."""
    belgeler = {r["document_id"]: r for r in _oku("NORMALIZE-BELGELER.csv")}
    sinif = {r["document_id"]: r for r in _oku("SINIFLANDIRMA.csv")}
    alanlar = _oku("KATEGORI-ALANLARI.csv")
    iliskiler = _oku("BELGE-ILISKILERI.csv")
    grup = bagimsizlik_gruplari(list(belgeler.values()), iliskiler)

    belge_alanlari: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for satir in alanlar:
        belge_alanlari[satir["document_id"]].append(satir)

    # (source_id, niyet) -> kanit listesi
    kanit: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for belge_id, belge in belgeler.items():
        s = sinif.get(belge_id)
        if not s:
            continue
        sid = belge["source_id"]
        if not sid:
            continue
        uzunluk = int(belge["body_uzunlugu"])
        js_kabugu = s["icerik_durumu"] == "js-kabugu"
        cikarilan = belge_alanlari.get(belge_id, [])

        niyetler: dict[str, str] = {}
        # (a) Sayfa bu niyetin yuzeyi olarak cekildiyse ve gercekten metin
        #     tasiyorsa, niyetin kaniti sayilir.
        cekim = s.get("cekim_niyeti", "")
        if cekim and not js_kabugu and uzunluk >= KANIT_ESIGI_METIN:
            niyetler[cekim] = f"{cekim} yüzeyi olarak çekildi, {uzunluk} karakter metin"
        # (b) Cikarilan alan dogrudan bir niyetin kanitidir.
        for bulgu in cikarilan:
            hedef = ALAN_NIYETI.get(bulgu["alan"])
            if hedef and bulgu["alan_turu"] == "olcum":
                niyetler[hedef] = f"{bulgu['alan']} = {bulgu['deger'][:40]}"

        for niyet, gerekce in niyetler.items():
            kanit[(sid, niyet)].append({
                "document_id": belge_id,
                "source_url": belge["source_url"],
                "title": belge["title"][:80],
                "language": belge["language"],
                "published_at": belge["published_at"],
                "collected_at": belge["collected_at"],
                "flags": belge["source_integrity_flags"],
                "icerik_durumu": s["icerik_durumu"],
                "belge_turu": s["belge_turu"],
                "alanlar": [f"{b['alan']}={b['deger'][:24]}" for b in cikarilan],
                "gerekce": gerekce,
                "uzunluk": uzunluk,
            })
    return {"kanit": kanit, "grup": grup, "belgeler": belgeler}


# --------------------------------------------------------------------------
# Matris satirlari
# --------------------------------------------------------------------------
TR_ISARETI = re.compile(r"(?i)(\.tr$|\.tr/|/tr/|\.com\.tr)")


def dil_pazar(kanitlar: list[dict[str, Any]]) -> str:
    diller = {k["language"] for k in kanitlar if k["language"] != "unknown"}
    pazar = "TR" if any(TR_ISARETI.search(k["source_url"]) for k in kanitlar) else "global"
    if not diller:
        return f"dil belirlenemedi · pazar {pazar}"
    return f"{', '.join(sorted(diller))} · pazar {pazar}"


def tazelik(kanitlar: list[dict[str, Any]]) -> str:
    """Tarih TAHMIN EDILMEZ. Sayfa beyan etmiyorsa oyle yazilir."""
    tarihli = [k["published_at"] for k in kanitlar if k["published_at"]]
    toplandi = sorted(k["collected_at"] for k in kanitlar if k["collected_at"])
    if tarihli:
        return f"sayfa yayın tarihi beyan ediyor (en yeni {max(tarihli)[:10]})"
    son = toplandi[-1][:10] if toplandi else "?"
    return f"yayın tarihi YOK (unknown_date) · yalnızca toplama anı {son}"


def erisim_kisiti(kanitlar: list[dict[str, Any]], envanter: dict[str, str] | None) -> str:
    """Erisim anligi guncel izin garantisi DEGILDIR; bu her satirda yazar."""
    notlar: list[str] = []
    durumlar = {k["icerik_durumu"] for k in kanitlar}
    if "arsiv" in durumlar:
        notlar.append("arşiv kopyası (Common Crawl), canlı değil")
    if "js-kabugu" in durumlar:
        notlar.append("bazı sayfalar JS kabuğu")
    bayraklar = {b for k in kanitlar for b in k["flags"].split(", ") if b}
    if "source_policy_limited" in bayraklar:
        notlar.append("kaynak politikası içeriği sınırlıyor")
    if envanter and envanter.get("erisim_durumu") == "kismi":
        notlar.append("erişim kısmi")
    son = sorted(k["collected_at"] for k in kanitlar if k["collected_at"])
    anlik = son[-1][:10] if son else "?"
    notlar.append(f"erişim anlığı {anlik} — GÜNCEL İZİN GARANTİSİ DEĞİL, "
                  f"kullanımdan önce robots yeniden kontrol edilmeli")
    return " · ".join(notlar)


def benzersiz_katki(alanlar: set[str], aile: str, digerleri: list[set[str]]) -> str:
    """Bu kaynak, ayni hucredeki digerlerinin vermedigi neyi veriyor."""
    baskalarinda = set().union(*digerleri) if digerleri else set()
    sadece_burada = alanlar - baskalarinda
    if sadece_burada:
        return f"bu hücrede yalnız burada: {', '.join(sorted(sadece_burada))}"
    if alanlar:
        return f"{aile or 'aile atanmamış'} · alanları başka kaynakta da var, çapraz doğrulama değeri"
    return f"{aile or 'aile atanmamış'} · ölçülebilir alan çıkmadı, yüzey kanıtı"


def sorgu_yuzeyi(satir: dict[str, str]) -> str:
    """ARAMA-YUZEYLERI.csv'den bu kaynaga sorgu atilabilecek yol.

    Bir arama SONUCU sayfasi DR-L02'de aday kesiftir, kanit degildir: buradaki
    deger "nereden sorulur"u soyler, "kanit burada" demez.
    """
    yol = satir.get("en_iyi_yol") or "yok"
    for anahtar in ("opensearch", "api_ucu", "site_arama"):
        if satir.get(anahtar):
            return f"{yol} · {satir[anahtar][:80]}"
    if yol == "local_index" and satir.get("yerel_url", "0") != "0":
        return f"local_index · yerel dizinde {satir['yerel_url']} adres (ağsız arama)"
    if yol == "fulltext":
        return f"fulltext · tam metin elde ({satir.get('tam_metin_bayt', '0')} bayt)"
    return yol


def matris_kur() -> dict[str, Any]:
    toplanan = kanitlari_topla()
    kanit, grup = toplanan["kanit"], toplanan["grup"]
    envanter = {r["source_id"]: r for r in _oku("VERI-ENVANTERI.csv")}
    ad_kimlik = {r["ad"]: r["source_id"] for r in envanter.values()}
    yuzey = {r["source_id"]: r for r in _oku("ARAMA-YUZEYLERI.csv")}
    sinif = _oku("SINIFLANDIRMA.csv")
    aile = {r["source_id"]: r["kaynak_ailesi"] for r in sinif if r["source_id"]}

    kategori_kaynak: dict[str, set[str]] = collections.defaultdict(set)
    for satir in _oku("KATEGORI-KAYNAK.csv"):
        sid = ad_kimlik.get(satir["kaynak"])
        if sid:
            kategori_kaynak[satir["hedef"]].add(sid)
    kategoriler = sorted(kategori_kaynak)

    # Once hucre bazinda topla ki "benzersiz katki" ve "fallback" hesaplanabilsin
    hucre: dict[tuple[str, str], list[tuple[str, list[dict[str, Any]]]]] = \
        collections.defaultdict(list)
    for kategori in kategoriler:
        for sid in sorted(kategori_kaynak[kategori]):
            for niyet in NIYETLER:
                kanitlar = kanit.get((sid, niyet))
                if kanitlar:
                    hucre[(kategori, niyet)].append((sid, kanitlar))

    satirlar: list[dict[str, Any]] = []
    for (kategori, niyet), girdiler in sorted(hucre.items()):
        alan_kumeleri = {sid: {a.split("=")[0] for k in ks for a in k["alanlar"]}
                         for sid, ks in girdiler}
        for sid, kanitlar in girdiler:
            en_iyi = max(kanitlar, key=lambda k: (len(k["alanlar"]), k["uzunluk"]))
            digerleri = [alan_kumeleri[o] for o, _ in girdiler if o != sid]
            # Fallback FARKLI bir bagimsizlik grubundan secilir; ayni gruptaki
            # kaynak yedek degildir, ayni seyin kopyasidir.
            yedek = [o for o, _ in girdiler
                     if grup.get(o) != grup.get(sid)]
            kaynak_yuzeyi = yuzey.get(sid, {})
            satirlar.append({
                "kategori": kategori,
                "arama_niyeti": niyet,
                "niyet_tanimi": NIYET_TANIMI[niyet],
                "source_id": sid,
                "kaynak_adi": envanter.get(sid, {}).get("ad", ""),
                "ornek_kayit": f'{en_iyi["document_id"]} · {en_iyi["source_url"][:90]}',
                "ornek_kayit_basligi": en_iyi["title"],
                "kanit_gerekcesi": en_iyi["gerekce"],
                "beklenen_benzersiz_katki": benzersiz_katki(
                    alan_kumeleri[sid], aile.get(sid, ""), digerleri),
                "alinabilen_alan": ", ".join(sorted(alan_kumeleri[sid])) or "(ölçülebilir alan yok)",
                "bagimsizlik_grubu": grup.get(sid, f"grup-{sid}"),
                "dil_pazar": dil_pazar(kanitlar),
                "tazelik": tazelik(kanitlar),
                "erisim_kisiti": erisim_kisiti(kanitlar, envanter.get(sid)),
                "fallback": (envanter.get(yedek[0], {}).get("ad", yedek[0])
                             if yedek else "(bağımsız yedek YOK)"),
                "aday_sorgu_yuzeyi": sorgu_yuzeyi(kaynak_yuzeyi),
                "incelenen_belge_sayisi": len(kanitlar),
            })
    return {"satirlar": satirlar, "hucre": hucre, "grup": grup,
            "kategoriler": kategoriler, "kategori_kaynak": kategori_kaynak,
            "envanter": envanter}


# --------------------------------------------------------------------------
# Kategori bazli yeterlilik / eksik matrisi
# --------------------------------------------------------------------------
def gap_sebebi(kategori: str, niyet: str, kaynaklar: set[str],
               envanter: dict[str, dict[str, str]]) -> tuple[str, str]:
    """(sebep kodu, aciklama). Veri yoklugu PAZAR SONUCU olarak yorumlanmaz."""
    if niyet in METINDEN_OKUNAN:
        return ("yontem-disi",
                "Bu niyet sayfanın adresinden okunamaz; forum ve yorum METNİNDE "
                "geçer. Bu veri kümesinde taranmadı — pazarda sinyal olmadığı "
                "anlamına GELMEZ.")
    if not kaynaklar:
        return ("kaynak-yok",
                "Katalogda bu kategoriye bağlı kaynak yok.")
    durum = collections.Counter(
        envanter.get(s, {}).get("icerik_durumu", "dosya-yok") for s in kaynaklar)
    erisim = collections.Counter(
        envanter.get(s, {}).get("erisim_durumu", "erisim_yok") for s in kaynaklar)
    if durum.get("js-kabugu", 0) >= max(1, len(kaynaklar) // 3):
        return ("js-kabugu",
                f"{durum['js-kabugu']}/{len(kaynaklar)} kaynak sayfayı tarayıcıda "
                "üretiyor; indirilen HTML boş. Bot koruması aşılmadığı için "
                "içerik alınamıyor.")
    if erisim.get("erisim_yok", 0) + erisim.get("adres_yok", 0) >= len(kaynaklar) // 2:
        return ("erisilemiyor",
                f"{erisim['erisim_yok'] + erisim['adres_yok']}/{len(kaynaklar)} "
                "kaynağa erişilemiyor (bot koruması ya da adres yok).")
    if durum.get("dosya-yok", 0) >= len(kaynaklar) // 2:
        return ("icerik-yok",
                f"{durum['dosya-yok']}/{len(kaynaklar)} kaynakta bu checkout'ta "
                "açılabilir dosya yok; henüz toplanmadı.")
    return ("yuzey-bulunamadi",
            "Kaynaklara erişiliyor ve içerik var, ama bu niyete karşılık gelen "
            "yüzey (ör. /pricing, /reviews) bulunamadı. Toplama yöntemi "
            "yetersiz — pazar sinyali hakkında bir şey söylemez.")


def yeterlilik_kur(matris: dict[str, Any]) -> list[dict[str, Any]]:
    hucre, grup = matris["hucre"], matris["grup"]
    envanter = matris["envanter"]
    satirlar: list[dict[str, Any]] = []
    for kategori in matris["kategoriler"]:
        for niyet in NIYETLER:
            girdiler = hucre.get((kategori, niyet), [])
            gruplar = {grup.get(sid, sid) for sid, _ in girdiler}
            kaynaklar = matris["kategori_kaynak"][kategori]
            if not girdiler:
                kod, aciklama = gap_sebebi(kategori, niyet, kaynaklar, envanter)
                durum = "bos"
            elif len(gruplar) >= YETERLI_GRUP:
                kod, aciklama, durum = "", "", "yeterli"
            else:
                kod = "tek-grup"
                aciklama = ("Tüm kanıt tek bağımsızlık grubundan geliyor; "
                            "aynı kaynağın kopyaları bağımsız sayılmaz.")
                durum = "zayif"
            satirlar.append({
                "kategori": kategori,
                "arama_niyeti": niyet,
                "durum": durum,
                "kanit_veren_kaynak": len(girdiler),
                "bagimsiz_grup": len(gruplar),
                "incelenen_belge": sum(len(k) for _, k in girdiler),
                "gap_kodu": kod,
                "gap_aciklamasi": aciklama,
                "ornek_kaynaklar": ", ".join(
                    envanter.get(sid, {}).get("ad", sid) for sid, _ in girdiler[:3]),
            })
    return satirlar


# --------------------------------------------------------------------------
# Standard / Deep aday paketleri
# --------------------------------------------------------------------------
# Gorev 7'nin kurali burada da gecerli: Deep "kontrolsuz daha cok site" degildir.
# Standard her niyetten bir bagimsiz grup hedefler; Deep ayni niyetlere ikinci
# bir BAGIMSIZ grup ekleyerek capraz dogrulama saglar.
PAKET_BUTCESI = {"standard": {"niyet_basina_grup": 1, "azami_kaynak": 6},
                 "deep": {"niyet_basina_grup": 2, "azami_kaynak": 14}}


def paketleri_kur(matris: dict[str, Any]) -> list[dict[str, Any]]:
    hucre, grup, envanter = matris["hucre"], matris["grup"], matris["envanter"]
    satirlar: list[dict[str, Any]] = []
    for kategori in matris["kategoriler"]:
        for paket, butce in PAKET_BUTCESI.items():
            secilen: list[tuple[str, str]] = []
            kullanilan_grup: dict[str, set[str]] = collections.defaultdict(set)
            kapsanan: set[str] = set()
            for niyet in NIYETLER:
                girdiler = hucre.get((kategori, niyet), [])
                # Cok belge incelenmis ve cok alan cikmis kaynak once gelir;
                # esitlik source_id ile bozulur, boylece secim tekrarlanabilir.
                sirali = sorted(
                    girdiler,
                    key=lambda t: (-len(t[1]),
                                   -sum(len(k["alanlar"]) for k in t[1]), t[0]))
                for sid, _kanitlar in sirali:
                    g = grup.get(sid, sid)
                    if g in kullanilan_grup[niyet]:
                        continue            # ayni grup ikinci kez sayilmaz
                    if len(kullanilan_grup[niyet]) >= butce["niyet_basina_grup"]:
                        break
                    if len(secilen) >= butce["azami_kaynak"]:
                        break
                    kullanilan_grup[niyet].add(g)
                    secilen.append((sid, niyet))
                    kapsanan.add(niyet)
            eksik = [n for n in NIYETLER if n not in kapsanan]
            satirlar.append({
                "kategori": kategori,
                "paket": paket,
                "kaynak_sayisi": len(secilen),
                "bagimsiz_grup": len({grup.get(s, s) for s, _ in secilen}),
                "kapsanan_niyet": len(kapsanan),
                "kapsanmayan_niyet": ", ".join(eksik) or "(yok)",
                "kaynaklar": " | ".join(
                    f'{envanter.get(s, {}).get("ad", s)}({n.split("_")[0]})'
                    for s, n in secilen),
                "gerekce": paket_gerekcesi(paket, kategori, len(kapsanan), eksik),
            })
    return satirlar


def paket_gerekcesi(paket: str, kategori: str, kapsanan: int,
                    eksik: list[str]) -> str:
    if paket == "standard":
        temel = (f"Her arama niyetinden bir bağımsız grup; {kapsanan}/7 niyet "
                 f"kapsanıyor. Kanıt tek kaynaktan gelir, çapraz doğrulama yok.")
    else:
        temel = (f"Aynı niyetlere ikinci bir BAĞIMSIZ grup eklenir; "
                 f"{kapsanan}/7 niyet kapsanıyor. Fark kaynak sayısı değil, "
                 f"çapraz doğrulama: aynı bulguyu iki farklı sahiplikten görmek.")
    if eksik:
        temel += (f" Kapsanmayan {len(eksik)} niyet için bu paket kanıt "
                  f"ÜRETMEZ; yeterlilik matrisindeki gap sebebine bakılmalı.")
    return temel


# --------------------------------------------------------------------------
# Sema taslagi (Ayse Sena icin)
# --------------------------------------------------------------------------
SEMA_ALANLARI: list[tuple[str, str, str, str]] = [
    # (alan, tip, zorunlu mu, aciklama)
    ("kategori", "string", "zorunlu", "URUN-KATEGORILERI.csv'deki ürün kategorisi"),
    ("arama_niyeti", "enum(7)", "zorunlu",
     "Faz2-Plan.md'nin yedi niyetinden biri. observed_market_pricing ve "
     "stated_wtp_weak_signal AYRI değerlerdir, birleştirilmez."),
    ("source_id", "string", "zorunlu", "Kanonik kaynak kimliği (source_manifest.json)"),
    ("ornek_kayit", "string", "zorunlu",
     "document_id + kaynak URL. Bu satırın dayandığı, GERÇEKTEN AÇILMIŞ belge. "
     "Boş olamaz — dayanağı olmayan eşleşme satır olmaz."),
    ("kanit_gerekcesi", "string", "zorunlu",
     "Bu belgenin neden o niyetin kanıtı sayıldığı (çıkarılan alan ya da yüzey türü)"),
    ("beklenen_benzersiz_katki", "string", "zorunlu",
     "Bu kaynağın aynı hücredeki diğerlerinin vermediği katkı"),
    ("alinabilen_alan", "string[]", "opsiyonel",
     "Belgeden gerçekten çıkarılmış alanlar. Çıkmadıysa '(ölçülebilir alan yok)'"),
    ("bagimsizlik_grubu", "string", "zorunlu",
     "Aynı kayıtlı alan adı ya da duplicate_of ilişkisi olan kaynaklar aynı gruptadır. "
     "Yeterlilik sayımı kaynak değil GRUP sayar."),
    ("dil_pazar", "string", "zorunlu", "Belgelerden okunan dil + TR/global pazar işareti"),
    ("tazelik", "string", "zorunlu",
     "Sayfa yayın tarihi beyan ediyorsa o tarih; etmiyorsa 'yayın tarihi YOK' ve "
     "yalnızca toplama anı. Tarih TAHMİN EDİLMEZ."),
    ("erisim_kisiti", "string", "zorunlu",
     "Arşiv/JS kabuğu/politika kısıtı + erişim anlığının tarihi. Erişim anlığı "
     "GÜNCEL İZİN GARANTİSİ DEĞİLDİR."),
    ("fallback", "string", "zorunlu",
     "FARKLI bir bağımsızlık grubundan yedek kaynak. Aynı gruptaki kaynak yedek değil, kopyadır."),
    ("aday_sorgu_yuzeyi", "string", "zorunlu",
     "ARAMA-YUZEYLERI.csv'den sorgu yolu. Arama SONUCU aday keşiftir, kanıt değildir."),
    ("incelenen_belge_sayisi", "int", "zorunlu", "Bu eşleşmeyi destekleyen belge sayısı"),
]


def sema_taslagi(matris: dict[str, Any], yeterlilik: list[dict[str, Any]]) -> str:
    durum = collections.Counter(r["durum"] for r in yeterlilik)
    alanlar = "\n".join(
        f"| `{ad}` | `{tip}` | {zorunlu} | {aciklama} |"
        for ad, tip, zorunlu, aciklama in SEMA_ALANLARI)
    niyetler = "\n".join(f"| `{n}` | {NIYET_TANIMI[n]} |" for n in NIYETLER)
    return f"""# SourceFitMatrix — şema ve alan taslağı

**Sürüm {SURUM}** · Üreten: `source_fit_matrix.py` · Hazırlayan: Ayselin Aydoğdu

Bu belge `SOURCE-FIT-MATRIX.csv` dosyasının alan sözleşmesidir. Amaç: aynı
şemayı kullanan başka bir çalışmanın satırları aynı anlamda okuyabilmesi.

## Satırın anlamı

Bir satır şu cümledir: **"<kategori> kategorisinde <arama_niyeti> sorusuna,
<source_id> kaynağı cevap verebilir, ve bunun kanıtı <ornek_kayit>."**

Kanıtı olmayan cümle satır olmaz. Kanıtsız kalan (kategori, niyet) çifti
`KATEGORI-YETERLILIK.csv` içinde **gap** olarak, sebebiyle birlikte durur.

## Alanlar

| Alan | Tip | | Anlamı |
|---|---|---|---|
{alanlar}

## Arama niyetleri

Faz2-Plan.md'nin yedi niyeti. Sıra sabittir.

| Niyet | Tanım |
|---|---|
{niyetler}

### İki fiyat niyeti neden ayrı

`observed_market_pricing` satıcının kendi sayfasında **yazan** fiyattır:
gözlemlenebilir, doğrulanabilir bir ticari veridir.

`stated_wtp_weak_signal` kullanıcının "buna şu kadar öderim" demesidir.
Faz2-Plan.md bunu açıkça **zayıf beyan sinyali** sayar ve gerçek ödeme
davranışı kabul etmez. İkisi tek sütunda birleşirse, bir forum yorumu bir
fiyat listesiyle aynı ağırlığa gelir.

Bu veri kümesinde `stated_wtp_weak_signal` için **hiç kanıt yoktur** ve her
kategoride açık gap taşır. Sebebi ölçülmüştür: o sinyal sayfanın adresinden
değil metninden okunur, bu çalışmada metin taraması yapılmadı.

## Üç sayım kuralı

1. **Bağımsızlık kaynak değil grup sayar.** Aynı kayıtlı alan adına sahip ya da
   belgeleri `duplicate_of` ile bağlı kaynaklar tek gruptur. `{len(set(matris["grup"].values()))}` grup,
   `{len(matris["grup"])}` kaynaktan türedi.
2. **Yeterlilik eşiği {YETERLI_GRUP} bağımsız gruptur.** Altında kalan hücre `zayif`
   işaretlenir: kanıt var ama tek sahiplikten geliyor.
3. **Boş hücre pazar sonucu değildir.** Her gap bir sebep kodu taşır:
   `yontem-disi`, `yuzey-bulunamadi`, `js-kabugu`, `erisilemiyor`,
   `icerik-yok`, `kaynak-yok`. Hiçbiri "bu pazarda talep yok" demez.

## Bu sürümün durumu

| | Hücre |
|---|---:|
| Yeterli ({YETERLI_GRUP}+ bağımsız grup) | {durum['yeterli']} |
| Zayıf (tek grup) | {durum['zayif']} |
| Boş (gap) | {durum['bos']} |
| **Toplam** | **{sum(durum.values())}** |

## Bağlı dosyalar

| Dosya | Rol |
|---|---|
| `SOURCE-FIT-MATRIX.csv` | Eşleşmeler — bu şemanın uygulandığı yer |
| `KATEGORI-YETERLILIK.csv` | Hücre bazında yeterlilik ve gap sebebi |
| `PAKET-ONERILERI.csv` | Kategori başına Standard/Deep aday paketi |
| `NORMALIZE-BELGELER.csv` | `ornek_kayit`ın işaret ettiği belgeler |
| `KAYNAK-ALAN.csv` | Alan × izin matrisi (Görev 4) |
| `ARAMA-YUZEYLERI.csv` | `aday_sorgu_yuzeyi`nin kaynağı |
"""


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--yaz", action="store_true", help="çıktıları diske yaz")
    secenek = ayristirici.parse_args(argv)

    matris = matris_kur()
    yeterlilik = yeterlilik_kur(matris)
    paketler = paketleri_kur(matris)
    durum = collections.Counter(r["durum"] for r in yeterlilik)
    ozet = {
        "surum": SURUM,
        "matris_satiri": len(matris["satirlar"]),
        "kategori": len(matris["kategoriler"]),
        "hucre": len(yeterlilik),
        "yeterli": durum["yeterli"], "zayif": durum["zayif"], "bos": durum["bos"],
        "bagimsizlik_grubu": len(set(matris["grup"].values())),
        "paket": len(paketler),
    }
    print(json.dumps(ozet, ensure_ascii=False, indent=2))
    if not secenek.yaz:
        return 0
    _yaz("SOURCE-FIT-MATRIX.csv", matris["satirlar"])
    _yaz("KATEGORI-YETERLILIK.csv", yeterlilik)
    _yaz("PAKET-ONERILERI.csv", paketler)
    (HERE / "SOURCEFIT-SEMA.md").write_text(
        sema_taslagi(matris, yeterlilik), encoding="utf-8")
    print("SOURCE-FIT-MATRIX.csv · KATEGORI-YETERLILIK.csv · "
          "PAKET-ONERILERI.csv · SOURCEFIT-SEMA.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
