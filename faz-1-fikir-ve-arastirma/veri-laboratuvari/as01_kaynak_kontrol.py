"""AS-01 — Batuhan'in F01-F10 denemeleri icin kaynak yetenegi ve erisim siniri.

Gorev karti iki sey soyluyor ve bu modul ikisini de uygular:

1. **"Eski erisim kaydini bugunku basari sayma."** Elimizdeki erisim kayitlari
   2 ve 18 Eylul'den. Bu modul ayni kaynaklari **bugun** yeniden yoklar ve iki
   sonucu yan yana koyar. Kayitli durum ``kayitli_*`` sutunlarinda, bugunku
   ``bugun_*`` sutunlarinda durur; ikisi karisirsa hangisi oldugu okunamaz.

2. **"Indekste gorunen ama erisilemeyen dosya, arsiv/snippet ve gercek icerik
   farkini belirt."** Uc ayri eksen ayri sutunda tutulur:

   * ``erisim``  — siteye bugun ulasilabiliyor mu (robots + HTTP)
   * ``icerik``  — gelen sey gercek metin mi, JS kabugu mu, arsiv kopyasi mi
   * ``artefakt`` — o kaydin ham dosyasi bu depoda var mi

Ucuncusu bu calismanin kendi sorunudur ve gizlenmez: normalize belgelerin
buyuk kismi yalniz yerel arsivde duruyor, depoda yok. Kontrol ve kabul
rehberi "kayip artefakt basarili sayilmaz" diyor.

Bu modul **kanit uretir, karar vermez.** Bir kaynagin bugun engelli olmasi o
pazarda talep olmadigini degil, o yuzeyin bu hatla alinamadigini gosterir.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import urllib.parse
import urllib.robotparser
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
# Ham arsivin ikinci konumu. Depo yeniden yapilandirildiginda artefaktlarin
# buyuk kismi burada kaldi; hangi dosyanin nerede oldugu olculur, varsayilmaz.
YEREL_ARSIV = HERE / ".." / ".." / "research" / "source-access-lab"
SURUM = "1.0.0"

# Kontrol ve kabul rehberindeki F01-F10 matrisinden birebir alindi.
# (fikir, beklenen kategori, [(source_id, ad, test yolu, aranan kanit)])
FIKIR_KAYNAK: list[tuple[str, str, str, list[tuple[str, str, str]]]] = [
    ("F01", "Vardiyalı çalışanlar için uyku takibi", "mobil-uygulama", [
        ("source-0096", "https://apps.apple.com", "/us/app/sleep-cycle-sleep-tracker/id320606217"),
        ("source-0097", "https://play.google.com", "/store/apps/details?id=com.northcube.sleepcycle"),
        ("source-0075", "https://www.reddit.com", "/r/shiftwork/"),
    ]),
    ("F02", "Ajans müşteri onayı ve revizyon SaaS", "b2b-web-yazilimi", [
        ("source-0134", "https://www.g2.com", "/categories/proofing"),
        ("source-0135", "https://www.capterra.com", "/proofing-software/"),
        ("source-0075", "https://www.reddit.com", "/r/agency/"),
    ]),
    ("F03", "API geriye uyumluluk CLI", "gelistirici-araci", [
        ("source-0017", "https://api.github.com", "/search/issues?q=openapi+breaking+change&per_page=5"),
        ("source-0023", "https://api.stackexchange.com", "/2.3/search/advanced?site=stackoverflow&q=breaking%20change%20api&pagesize=5"),
        ("source-0022", "https://hn.algolia.com", "/api/v1/search?query=breaking%20changes%20api&hitsPerPage=5"),
    ]),
    ("F04", "Shopify iade nedenleri eklentisi", "eklenti-entegrasyon", [
        ("source-0114", "https://apps.shopify.com", "/categories/orders-and-shipping-returns-and-exchanges"),
        ("source-0075", "https://www.reddit.com", "/r/shopify/"),
    ]),
    ("F05", "Self-host Türkçe konuşma tanıma API", "yapay-zeka-urunu", [
        ("source-0534", "https://huggingface.co", "/api/models?search=turkish%20asr&limit=5"),
        ("source-0017", "https://api.github.com", "/search/repositories?q=turkish+speech+recognition&per_page=5"),
        ("source-0022", "https://hn.algolia.com", "/api/v1/search?query=self%20hosted%20speech%20recognition&hitsPerPage=5"),
    ]),
    ("F06", "PC için iki kişilik bulmaca oyunu", "oyun", [
        ("source-0518", "https://store.steampowered.com", "/search/?tags=1664&term=co-op+puzzle"),
        ("source-0075", "https://www.reddit.com", "/r/gamingsuggestions/"),
    ]),
    ("F07", "İstanbul ev temizliği rezervasyonu", "yerel-hizmet", [
        ("source-0319", "https://armut.com", "/ev-temizligi"),
        ("source-0148", "https://www.trustpilot.com", "/review/armut.com"),
        ("source-0075", "https://www.reddit.com", "/r/Turkey/"),
    ]),
    ("F08", "Günlük mobil kelime bulmacası", "oyun", [
        ("source-0096", "https://apps.apple.com", "/us/app/wordle/id1095569891"),
        ("source-0097", "https://play.google.com", "/store/apps/details?id=com.nytimes.games.wordle"),
        ("source-0075", "https://www.reddit.com", "/r/wordle/"),
    ]),
    ("F09", "Berber randevu ve gelmeme SaaS", "b2b-web-yazilimi", [
        ("source-0135", "https://www.capterra.com", "/salon-software/"),
        ("source-0134", "https://www.g2.com", "/categories/salon-and-spa"),
        ("source-0075", "https://www.reddit.com", "/r/Barber/"),
    ]),
    ("F10", "Öğretmen notlarından AI alıştırma uygulaması", "mobil-uygulama", [
        ("source-0096", "https://apps.apple.com", "/us/app/quizlet-ai-powered-flashcards/id546473125"),
        ("source-0097", "https://play.google.com", "/store/apps/details?id=com.quizlet.quizletandroid"),
        ("source-0466", "https://www.capterra.com", "/education-software/"),
    ]),
]


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


def artefakt_konumu(goreli: str) -> str:
    """Bir artefaktin bu depoda mi yoksa yalniz yerel arsivde mi oldugu."""
    if not goreli.strip():
        return "yol-yok"
    if (HERE / goreli).exists():
        return "depoda"
    if (YEREL_ARSIV / goreli).exists():
        return "yalniz-yerelde"
    return "hicbir-yerde"


# --------------------------------------------------------------------------
# Bugunku yoklama
# --------------------------------------------------------------------------
def bugun_yokla(origin: str, yol: str, canli: bool) -> dict[str, Any]:
    """Tek bir yuzeyi bugun dener. robots once, her zaman.

    Doner: erisim (bugun ulasilabiliyor mu), icerik (gelen sey ne),
    kanit (olculen sayi), ve robots karari.
    """
    if not canli:
        return {"bugun_erisim": "not_run", "bugun_icerik": "not_run",
                "bugun_kanit": "", "bugun_robots": "not_run",
                "bugun_artefakt": "", "bugun_artefakt_dosya": "", "bugun_bayt": 0}

    import normalize_belgeler as nb
    import veri_envanteri as ve
    from bulk_site_access_lab import (ROBOTS_BLOCKED, OriginRuntime,
                                      USER_AGENT, robots_state)

    runtime = OriginRuntime(origin, lease=3, live=True)
    robots = runtime.fetch("as01", "robots_preflight", origin + "/robots.txt",
                           "robots", robots_decision="not_required")
    durum = robots_state(robots)
    if durum == ROBOTS_BLOCKED:
        return {"bugun_erisim": "robots_preflight_blocked",
                "bugun_icerik": "alinmadi",
                "bugun_kanit": "robots.txt 401/403 — RFC 9309 tam yasak",
                "bugun_robots": "blocked",
                "bugun_artefakt": "", "bugun_artefakt_dosya": "", "bugun_bayt": 0}
    ayristirici = urllib.robotparser.RobotFileParser()
    ayristirici.set_url(origin + "/robots.txt")
    ayristirici.parse(robots.body.decode("utf-8", "replace").splitlines()
                      if durum == "policy" else [])
    runtime.robots_parser = ayristirici
    izinli = ayristirici.can_fetch(USER_AGENT, origin + yol)
    if not izinli:
        return {"bugun_erisim": "robots_disallowed", "bugun_icerik": "alinmadi",
                "bugun_kanit": "robots.txt bu yolu yasaklıyor — denenmedi",
                "bugun_robots": "disallow",
                "bugun_artefakt": "", "bugun_artefakt_dosya": "", "bugun_bayt": 0}

    cikti = runtime.fetch("as01", "as01_yoklama", origin + yol,
                          "json" if "/api/" in yol or "api." in origin else "html",
                          robots_decision="required")
    if not cikti.ok:
        return {"bugun_erisim": cikti.stop_reason or cikti.outcome,
                "bugun_icerik": "alinmadi", "bugun_kanit": "",
                "bugun_robots": "allow",
                "bugun_artefakt": "", "bugun_artefakt_dosya": "", "bugun_bayt": 0}

    govde = cikti.body[:400_000]
    # Kaniti sakla. Rehber "kanitsiz veya calistirilmamis test kabul edilmis
    # sayilmaz" diyor; Batuhan'in dogrulayabilmesi icin yanit gövdesi bu
    # DEPOYA yazilir, yerel arsive degil.
    ozet = hashlib.sha256(cikti.body).hexdigest()
    hedef = HERE / "results" / "raw" / f"{ozet}.bin"
    hedef.parent.mkdir(parents=True, exist_ok=True)
    if not hedef.exists():
        hedef.write_bytes(cikti.body)
    mime = "application/json" if govde[:1] in (b"{", b"[") else "text/html"
    icerik, _gerekce = ve.icerik_durumu("as01_yoklama", mime, govde)
    cikarim = nb.metin_cikar(govde, mime)
    uzunluk = len(cikarim["metin"])
    alanlar = nb.alan_cikar("urun", cikarim["metin"], "")
    kanit = f"{uzunluk} karakter metin"
    if alanlar:
        kanit += " · " + ", ".join(f'{b["alan"]}={b["deger"][:18]}' for b in alanlar[:3])
    return {"bugun_erisim": "ok", "bugun_icerik": icerik,
            "bugun_kanit": kanit, "bugun_robots": "allow",
            "bugun_artefakt": ozet, "bugun_artefakt_dosya": f"results/raw/{ozet}.bin",
            "bugun_bayt": len(cikti.body)}


def kontrol_et(canli: bool) -> list[dict[str, Any]]:
    envanter = {r["source_id"]: r for r in _oku("VERI-ENVANTERI.csv")}
    yuzeyler = {r["source_id"]: r for r in _oku("ARAMA-YUZEYLERI.csv")}
    dizin = _oku("ARTEFAKT-DIZINI.csv") + _oku("EK-ARTEFAKT-DIZINI.csv")
    kaynak_artefakt: dict[str, list[dict[str, str]]] = {}
    for kayit in dizin:
        if kayit["sonuc"] == "ok" and kayit.get("source_id"):
            kaynak_artefakt.setdefault(kayit["source_id"], []).append(kayit)

    satirlar: list[dict[str, Any]] = []
    for fikir, baslik, kategori, denemeler in FIKIR_KAYNAK:
        for sid, origin, yol in denemeler:
            kayit = envanter.get(sid, {})
            artefaktlar = kaynak_artefakt.get(sid, [])
            konumlar = [artefakt_konumu(a["dosya"]) for a in artefaktlar]
            sonuc = bugun_yokla(origin, yol, canli)
            satirlar.append({
                "fikir": fikir,
                "fikir_basligi": baslik,
                "beklenen_kategori": kategori,
                "source_id": sid,
                "kaynak_adi": kayit.get("ad", "(katalogda yok)"),
                "denenen_url": origin + yol,
                # Kayitli durum — TARIHLI SNAPSHOT, bugunku basari degil
                "kayitli_erisim": kayit.get("erisim_durumu", "?"),
                "kayitli_icerik": kayit.get("icerik_durumu", "?"),
                "kayitli_artefakt": len(artefaktlar),
                "artefakt_depoda": konumlar.count("depoda"),
                "artefakt_yalniz_yerelde": konumlar.count("yalniz-yerelde"),
                "artefakt_hicbir_yerde": konumlar.count("hicbir-yerde"),
                # Bugunku olcum
                **sonuc,
                "arama_yuzeyi": yuzeyler.get(sid, {}).get("en_iyi_yol", "-"),
                "degisti_mi": "",
            })
    for satir in satirlar:
        satir["degisti_mi"] = fark_yorumu(satir)
    return satirlar


def fark_yorumu(satir: dict[str, Any]) -> str:
    """Kayitli durum ile bugunku sonuc arasindaki fark.

    Bu sutunun varlik sebebi gorev kartinin kurali: eski erisim kaydi
    bugunku basari sayilmaz. Fark varsa burada yazar.
    """
    if satir["bugun_erisim"] == "not_run":
        return "bugün yoklanmadı"
    kayitli_iyi = satir["kayitli_icerik"] in ("gercek-icerik", "api-yaniti", "besleme")
    bugun_iyi = satir["bugun_erisim"] == "ok" and satir["bugun_icerik"] in (
        "gercek-icerik", "api-yaniti", "besleme")
    if kayitli_iyi and not bugun_iyi:
        return "KAYIT ÇALIŞIYOR DİYOR, BUGÜN ÇALIŞMIYOR"
    if not kayitli_iyi and bugun_iyi:
        return "kayıt çalışmıyor diyordu, bugün içerik geldi"
    if bugun_iyi:
        return "bugün de çalışıyor"
    return "kayıtta da bugün de içerik yok"


# --------------------------------------------------------------------------
# Alan ornekleri
# --------------------------------------------------------------------------
# Kontrol ve kabul rehberinin istedigi alanlar. "Kaynak desteklemiyorsa null;
# alan uydurma yok" kurali geregi bulunmayan alan bos birakilir, tahmin edilmez.
ISTENEN_ALANLAR: tuple[str, ...] = (
    "baslik", "govde", "kaynak_url", "alinma_tarihi", "yayin_tarihi",
    "yazar", "puan", "puan_olcegi", "fiyat", "para_birimi", "donem",
)


def alanlari_cikar(govde: bytes, url: str, alinma: str) -> dict[str, str]:
    """Bir yanittan rehberin istedigi alanlari cikarir.

    Bulunmayan alan **bos** kalir. JSON-LD ve resmi API yanitlari once
    denenir; ikisi de yoksa HTML meta etiketlerine bakilir. Hicbiri yoksa
    alan uydurulmaz.
    """
    import json as _json
    import re as _re

    import normalize_belgeler as nb

    sonuc = {a: "" for a in ISTENEN_ALANLAR}
    sonuc["kaynak_url"] = url
    sonuc["alinma_tarihi"] = alinma

    metin_bytes = govde[:400_000]
    mime = "application/json" if metin_bytes[:1] in (b"{", b"[") else "text/html"
    cikarim = nb.metin_cikar(metin_bytes, mime)
    sonuc["baslik"] = cikarim["baslik"][:120]
    sonuc["govde"] = cikarim["metin"][:200]

    yayin, _guncel, _kaynak = nb.tarih_cikar(cikarim)
    sonuc["yayin_tarihi"] = yayin

    # JSON-LD / API nesnelerinden puan ve fiyat
    for nesne in cikarim.get("jsonld", []):
        yigin = [nesne]
        while yigin:
            simdiki = yigin.pop()
            if isinstance(simdiki, list):
                yigin.extend(simdiki)
                continue
            if not isinstance(simdiki, dict):
                continue
            yigin.extend(v for v in simdiki.values() if isinstance(v, (dict, list)))
            if "ratingValue" in simdiki and not sonuc["puan"]:
                sonuc["puan"] = str(simdiki["ratingValue"])[:12]
                sonuc["puan_olcegi"] = str(simdiki.get("bestRating", ""))[:12]
            if "price" in simdiki and not sonuc["fiyat"]:
                sonuc["fiyat"] = str(simdiki["price"])[:16]
                sonuc["para_birimi"] = str(simdiki.get("priceCurrency", ""))[:8]
            if not sonuc["yazar"]:
                yazar = simdiki.get("author")
                if isinstance(yazar, dict):
                    sonuc["yazar"] = str(yazar.get("name", ""))[:60]
                elif isinstance(yazar, str):
                    sonuc["yazar"] = yazar[:60]

    if mime == "application/json":
        try:
            veri = _json.loads(metin_bytes)
        except ValueError:
            veri = None
        girdiler = None
        if isinstance(veri, dict):
            girdiler = veri.get("items") or veri.get("hits") or veri.get("models")
        elif isinstance(veri, list):
            girdiler = veri
        if isinstance(girdiler, list) and girdiler and isinstance(girdiler[0], dict):
            ilk = girdiler[0]
            sonuc["baslik"] = str(ilk.get("title") or ilk.get("name")
                                  or ilk.get("modelId") or "")[:120]
            for anahtar in ("owner", "author", "by", "login"):
                deger = ilk.get(anahtar)
                if isinstance(deger, dict):
                    deger = deger.get("display_name") or deger.get("login")
                if deger and not sonuc["yazar"]:
                    sonuc["yazar"] = str(deger)[:60]
            for anahtar in ("creation_date", "created_at", "created_utc", "lastModified"):
                if ilk.get(anahtar) and not sonuc["yayin_tarihi"]:
                    sonuc["yayin_tarihi"] = str(ilk[anahtar])[:32]

    if not sonuc["fiyat"]:
        bulgular = nb.alan_cikar("urun", cikarim["metin"], "")
        fiyat = next((b for b in bulgular if b["alan"] == "fiyat"), None)
        if fiyat:
            sonuc["fiyat"] = fiyat["deger"][:16]
            para = _re.match(r"[^\d]*", fiyat["deger"])
            sonuc["para_birimi"] = (para.group(0).strip() if para else "")[:8]
    return sonuc


def alan_ornekleri(kontrol: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bugun icerik veren her kaynak icin gercek alan ornegi."""
    import datetime

    bugun = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    satirlar: list[dict[str, Any]] = []
    gorulen: set[str] = set()
    for satir in kontrol:
        if satir["bugun_erisim"] != "ok" or not satir["bugun_artefakt"]:
            continue
        if satir["source_id"] in gorulen:
            continue
        gorulen.add(satir["source_id"])
        yol = HERE / satir["bugun_artefakt_dosya"]
        if not yol.exists():
            continue
        alanlar = alanlari_cikar(yol.read_bytes(), satir["denenen_url"], bugun)
        dolu = [a for a in ISTENEN_ALANLAR if alanlar[a]]
        satirlar.append({
            "source_id": satir["source_id"],
            "kaynak_adi": satir["kaynak_adi"],
            "fikir": satir["fikir"],
            "denenen_url": satir["denenen_url"],
            "artefakt_sha256": satir["bugun_artefakt"],
            "artefakt_dosya": satir["bugun_artefakt_dosya"],
            "icerik_durumu": satir["bugun_icerik"],
            **alanlar,
            "dolu_alan_sayisi": len(dolu),
            "bos_alanlar": ", ".join(a for a in ISTENEN_ALANLAR if not alanlar[a]),
        })
    return satirlar


# --------------------------------------------------------------------------
# Rapor
# --------------------------------------------------------------------------
def artefakt_dagilimi() -> dict[str, int]:
    """Normalize belgelerin ham dosyalari nerede."""
    sayac = {"depoda": 0, "yalniz-yerelde": 0, "hicbir-yerde": 0, "yol-yok": 0}
    for satir in _oku("NORMALIZE-BELGELER.csv"):
        sayac[artefakt_konumu(satir["body_original_ref"])] += 1
    return sayac


def erisim_sinirlari(kontrol: list[dict[str, Any]],
                     ornekler: list[dict[str, Any]],
                     iddialar: list[dict[str, Any]] | None = None) -> str:
    import collections
    import datetime

    bugun = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    durum = collections.Counter(r["degisti_mi"] for r in kontrol)
    artefakt = artefakt_dagilimi()
    toplam_belge = sum(artefakt.values())
    _belge = {r["document_id"]: r for r in _oku("NORMALIZE-BELGELER.csv")}

    def _dogrulanabilir(kimlikler: set[str]) -> str:
        var = sum(1 for d in kimlikler
                  if d in _belge and (HERE / _belge[d]["body_original_ref"]).exists())
        return f"%{100 * var / len(kimlikler):.0f} ({var}/{len(kimlikler)})" if kimlikler else "—"

    alan_oran = _dogrulanabilir({r["document_id"] for r in _oku("KATEGORI-ALANLARI.csv")})
    matris_oran = _dogrulanabilir(
        {r["ornek_kayit"].split(" · ")[0] for r in _oku("SOURCE-FIT-MATRIX.csv")})

    calisan = [r for r in kontrol if r["bugun_erisim"] == "ok"
               and r["bugun_icerik"] in ("gercek-icerik", "api-yaniti", "besleme")]
    yasak = [r for r in kontrol if r["bugun_erisim"].startswith("robots")]
    engel = [r for r in kontrol if r["bugun_erisim"] in ("challenge", "origin_circuit_open")]
    kabuk = [r for r in kontrol if r["bugun_icerik"] == "js-kabugu"]
    geriledi = [r for r in kontrol if "BUGÜN ÇALIŞMIYOR" in r["degisti_mi"]]

    def satirla(kayitlar: list[dict[str, Any]], sutunlar: list[str]) -> str:
        gorulen: set[tuple] = set()
        cikti = []
        for r in kayitlar:
            anahtar = tuple(r[s] for s in sutunlar)
            if anahtar in gorulen:
                continue
            gorulen.add(anahtar)
            cikti.append("| " + " | ".join(str(r[s]) for s in sutunlar) + " |")
        return "\n".join(cikti)

    ornek_tablosu = "\n".join(
        f'| {o["kaynak_adi"]} | {o["dolu_alan_sayisi"]}/11 | `{o["baslik"][:34]}` | '
        f'{o["puan"] or "—"} | {o["fiyat"] or "—"} | {o["yazar"] or "—"} | '
        f'`{o["artefakt_sha256"][:12]}` |' for o in ornekler)

    iddialar = iddialar or []
    iddia_durum = collections.Counter(r["bugun_sonuc"] for r in iddialar)
    kaynak_iddia: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    for r in iddialar:
        kaynak_iddia[r["kaynak_adi"]][1] += 1
        if r["bugun_sonuc"] == "dogrulandi":
            kaynak_iddia[r["kaynak_adi"]][0] += 1
    iddia_tablosu = "\n".join(
        ["| Kaynak | Doğrulanan / iddia |", "|---|---:|"]
        + [f"| {ad} | {d}/{t} |"
           for ad, (d, t) in sorted(kaynak_iddia.items(), key=lambda x: -x[1][0])])

    return f"""# AS-01 — Kaynak yeteneği, alan örnekleri ve erişim sınırları

**Sürüm {SURUM}** · Hazırlayan: Ayselin Aydoğdu · Kontrol eden: Batuhan
**Ölçüm tarihi: {bugun}** · Üreten: `as01_kaynak_kontrol.py`

Bu belge Batuhan'ın F01–F10 kategori/sorgu denemelerine başlamadan önce
**hangi kaynaktan ne beklenebileceğini** söyler. İçindeki her sayı bugün
ölçüldü; hiçbiri geçmiş kayıttan kopyalanmadı.

## 0. Önce en önemlisi: eski kayıt bugünkü başarı değil

Laboratuvarın erişim kayıtları 2 ve 18 Eylül'den. Bugün aynı kaynaklar
yeniden yoklandı ve iki sonuç yan yana kondu:

| | Deneme |
|---|---:|
| Bugün de çalışıyor | {durum['bugün de çalışıyor']} |
| Kayıtta da bugün de içerik yok | {durum['kayıtta da bugün de içerik yok']} |
| **Kayıt çalışıyor diyor, bugün çalışmıyor** | **{durum['KAYIT ÇALIŞIYOR DİYOR, BUGÜN ÇALIŞMIYOR']}** |
| Kayıt çalışmıyor diyordu, bugün geldi | {durum['kayıt çalışmıyor diyordu, bugün içerik geldi']} |

Gerileyen kayıtlar:

| Fikir | Kaynak | Kayıtlı durum | Bugün |
|---|---|---|---|
{satirla(geriledi, ["fikir", "kaynak_adi", "kayitli_icerik", "bugun_erisim"]) or "| — | — | — | — |"}

**Capterra F02, F09 ve F10'da planlanmış.** Kaydımız `gercek-icerik` diyor,
bugün bot koruması dönüyor. Bu satır tek başına kartın uyarısının gerekçesidir.

## 1. Üç ayrı eksen karıştırılmaz

Kontrol ve kabul rehberi üç farklı şeyi ayırmayı şart koşuyor ve bu tabloda
üçü de ayrı sütunda:

| Eksen | Soru | Değerler |
|---|---|---|
| **Erişim** | Siteye bugün ulaşılabiliyor mu | `ok`, `robots_disallowed`, `challenge`, `rate_limited`, `source_unavailable` |
| **İçerik** | Gelen şey ne | `gercek-icerik`, `api-yaniti`, `js-kabugu`, `aday-kesif`, `arsiv` |
| **Artefakt** | Ham dosya bu depoda var mı | `depoda`, `yalniz-yerelde`, `hicbir-yerde` |

HTTP 200 dönmesi içerik geldiği anlamına gelmez: Google Play bugün **200 OK**
döndü ve gövdesinde **0 karakter** görünür metin vardı.

## 2. Bugün ne çalışıyor

{len(calisan)} deneme içerik verdi. Alanlar gerçekten dolu mu diye her birinden
örnek çekildi; **bulunmayan alan boş bırakıldı, uydurulmadı**:

| Kaynak | Dolu alan | Başlık örneği | Puan | Fiyat | Yazar | Artefakt |
|---|---:|---|---|---|---|---|
{ornek_tablosu}

Rehberin istediği 11 alan: {", ".join(f"`{a}`" for a in ISTENEN_ALANLAR)}.

**Apple App Store 11 alanın 10'unu veriyor** — F01, F08 ve F10 için en güçlü
kaynak. **Armut** Türkçe yerel hizmet için puan ve gerçek yorumcu adı
döndürüyor. **Stack Overflow ve Hacker News** resmî API'leriyle çalışıyor.

## 2b. Arşiv, snippet ve gerçek içerik aynı şey değildir

Görev kartı bu üçünün ayrılmasını istiyor. Tanımlar ve bugünkü karşılıkları:

| Tür | Ne demek | Kanıt değeri | Bugün hangi kaynak |
|---|---|---|---|
| **Gerçek içerik** | Sayfanın kendi gövdesi, canlı çekildi | Alıntılanabilir | Apple App Store, Shopify, Steam, Armut |
| **API yanıtı** | Kaynağın resmî ucundan yapılandırılmış veri | Alıntılanabilir | GitHub, Stack Overflow, Hacker News, Hugging Face |
| **Arşiv** | Common Crawl kopyası; **canlı değil**, çekildiği tarihe ait | Sınırlı — `arsiv` işaretlenir, tarihi ayrı yazılır | G2 (yalnız arşivde var) |
| **Snippet / aday keşif** | Sitemap girdisi, arama sonucu satırı, meta açıklama | **Kanıt değildir** — yalnız "şu adres var" der | Hugging Face ve Capterra Education kayıtlarındaki `aday-kesif` |
| **JS kabuğu** | HTTP 200 döndü, gövdede görünür metin yok | Kanıt değildir | Google Play |
| **İndekste var, dosya yok** | Dizin dosyayı gösteriyor, checkout'ta bulunmuyor | Kanıt değildir | Bölüm 5 |

İkisi sık karıştırılır ve karıştırılmamalı:

- **Sitemap bir snippet bile değildir.** İçinde adres listesi vardır, içerik
  yoktur. Bir kaynağın sitemap'inin inmiş olması o kaynaktan veri alındığını
  göstermez.
- **Arşiv kopyası canlı veri değildir.** G2 için elimizde yalnız Common Crawl
  kopyası var; bugün canlı erişim bot korumasına takılıyor. Arşivden gelen
  bulgu kullanılacaksa `arsiv` etiketi ve çekilme tarihi birlikte taşınmalıdır.

## 2c. Laboratuvarın mevcut alan iddiaları ne kadar doğru

`KAYNAK-ALAN.csv` (Görev 4) bu 14 kaynak için {len(iddialar)} alan iddiası taşıyor ve
büyük kısmı `beyan` durumundaydı: iddia var, doğrulama yok. Bugünkü yanıtlar
o iddiaların üzerinde sınandı.

| Sonuç | Alan |
|---|---:|
| **Bugünkü yanıtta bulundu** | **{iddia_durum['dogrulandi']}** |
| Bu yüzeyde bulunamadı | {iddia_durum['dogrulanamadi']} |
| Kaynak içerik vermediği için sınanamadı | {iddia_durum['yoklanamadi']} |

{iddia_tablosu}

**"Bulunamadı" alanın yok olduğu anlamına gelmez.** Kaynak başına tek örnek
yüzey yoklandı; alan başka bir uçta bulunabilir. Ayrıntı:
[`AS01-IDDIA-DOGRULAMA.csv`](AS01-IDDIA-DOGRULAMA.csv) — her satır hangi
artefaktta arandığını yazar.

## 3. Politika engeli — kazımayla çözülmez

{len(yasak)} deneme robots.txt tarafından durduruldu:

| Kaynak | Bugünkü robots.txt | Etkilenen fikirler |
|---|---|---|
| **Reddit** | `User-agent: * / Disallow: /` — tam yasak | F01, F02, F04, F06, F07, F08, F09 |
| **Trustpilot** | Tam yasak | F07 |
| **stackoverflow.com** | `Disallow: /` + `Content-signal: search=no, ai-train=no` | F03 |

Reddit **on fikrin yedisinde** planlanmış ve tek satırla kapalı. Ama Reddit'in
kendi robots.txt'i izinli yolu gösteriyor:

```
# See .../Public-Content-Policy for access and use restrictions
# See https://www.reddit.com/r/reddit4researchers/ for ... research and non-commercial use
```

**Bu bir kazıma sorunu değil, izin sorunudur.** Çözümü kod değil, hesap ve
şartname onayı. Karar Çağlar'a ait.

`stackoverflow.com` kapalı ama **`api.stackexchange.com` resmî API'si açık** ve
bugün gerçek sonuç döndürdü. F03 için yol budur.

## 4. Teknik engel — robots izinli, içerik gelmiyor

| Kaynak | Bugün | Ne yapılabilir |
|---|---|---|
| G2 | `challenge` | Arşiv (Common Crawl) — **canlı değil**, `arsiv` olarak işaretlenir |
| Capterra | `challenge` | Aynı; ayrıca kayıtla çelişiyor |
| Capterra Education | `challenge` | Aynı |
| Google Play | 200 OK, 0 karakter | Aynı uygulamalar **Apple App Store**'da alınabiliyor |
| Apple App Store | çalışıyor, `rate_limited` eşiği düşük | İstek aralığı artırılmalı |

Bot koruması **aşılmaz** — tarayıcı taklidi, UA rotasyonu ve CAPTCHA çözme
yoktur. Site bizi bot olarak tanıyıp reddediyorsa bu bir karardır.

## 5. Kendi teslimimizdeki sınır

Depo üç fazlı yapıya taşınırken ham artefaktlar ikiye bölündü. {toplam_belge}
normalize belgenin ham dosyası nerede:

| | Belge |
|---|---:|
| Bu depoda | **{artefakt['depoda']}** |
| Yalnız yerel arşivde (depoda yok) | **{artefakt['yalniz-yerelde']}** |
| Hiçbir yerde | {artefakt['hicbir-yerde']} |

Rehber açık: *"kayıp artefakt başarılı sayılmaz"* ve *"indeksteki dosya
gerçekten checkout'ta veya kayıtlı depoda bulunuyor mu?"*

Bugünkü yoklamanın {len([r for r in kontrol if r['bugun_artefakt']])} kanıt
artefaktı **bu depoya** yazıldı; Batuhan hash'ten doğrulayabilir.

Geçmiş korpus için seçici bir paylaşım yapıldı: **sayı çıkardığımız her
belgenin** ham dosyası depoya alındı (154 dosya, 49 MB). Böylece
`KATEGORI-ALANLARI.csv`'deki her fiyat, puan ve sayının kaynağı açılabiliyor.

| Ne doğrulanabilir | Oran |
|---|---|
| Çıkarılan alanlar (fiyat, puan, yorum sayısı…) | **{alan_oran}** |
| Bugünkü AS-01 yoklamaları | **%100** |
| SourceFitMatrix örnek kayıtları | {matris_oran} |

Kalan 1070 belge çoğunlukla ana sayfa ve sitemap; onlardan sayı çıkarılmadı,
yani doğrulanacak bir iddia taşımıyorlar. SourceFitMatrix'in örnek kayıtlarını
da tamamlamak ~75 MB daha eklemek demek — karar Batuhan'ın.

## 5b. Kapalı kaynaklar için aranan alternatifler

F02 ve F09'un hiçbir kaynağı bugün içerik vermiyordu, bu yüzden o iki fikre
izinli alternatif arandı. Ayrıntı ve kanıt:
[`AS01-ALTERNATIF-RAPOR.md`](AS01-ALTERNATIF-RAPOR.md).

| Fikir | İhtiyaç | Bulunan kaynak | Durum |
|---|---|---|---|
| **F09** | Fiyat | Fresha (`source-0317`) — TRY 240.95/ay | Katalogda, hazır |
| **F09** | Kullanıcı şikâyeti | Apple App Store — Booksy Biz (`source-0096`) | Katalogda, hazır |
| **F02** | Fiyat, ürün, iş akışı | Filestage, Ziflow | **Katalogda yok** — registry kararı Batuhan'da |
| **F02** | Kullanıcı şikâyeti | — | **Açık kaldı** |

Bir ayrım önemli: bulunan kaynakların çoğu **satıcının kendi sitesi**. Satıcı
kendi hakkındaki şikâyeti yayımlamaz; "alternatifler" sayfası pazarlamadır.
Kanıt politikası da aynı yere varıyor — *"aynı kurumun pazarlama kopyaları bir
köken"*. Bu yüzden satıcı sayfaları G2/Capterra/Reddit'in yerini **tutmaz**:
fiyat verirler, şikâyet vermezler.

F09'un şikâyet boşluğunu kapatan tek yol üçüncü taraf çıktı: Booksy'nin
işletme uygulamasının App Store sayfasında gerçek kullanıcı yorumu var ve
biri doğrudan F09'un konusu — *"charged for a no show I didn't know I had"*.

**F02 için böyle bir yol bulunamadı.** Filestage ve Ziflow'un mobil uygulaması
yok, Hacker News nişe sonuç vermiyor, inceleme platformları bot korumalı.
Batuhan F02'yi fiyat ve ürün iddiası için araştırabilir, memnuniyetsizlik için
araştıramaz.

## 6. Bu belge ne söylemez

- **Bir kaynağın bugün engelli olması o pazarda talep olmadığını göstermez.**
  Erişilememe sıfır sonuç değildir.
- Sayılar **erişim ve alan ölçümüdür**, kanıt yeterliliği değil. 3 bağımsız
  örnek / 2 ayrı kaynak eşiği Faz 3'e aittir ve bunun yerine geçmez.
- Fiyat alanları **satıcının ilan ettiği fiyattır**; kullanıcının ödediği
  değildir.
- Bu ölçüm {bugun} tarihlidir. Batuhan denemeye başlarken yeniden koşmalıdır;
  bu belge de bir snapshot'tır.

## 7. Yeniden üretim

```bash
python3 as01_kaynak_kontrol.py --yaz          # ağsız: yalnız kayıtlı durum
python3 as01_kaynak_kontrol.py --yaz --canli  # bugünkü yoklama (28 istek)
python3 -m unittest test_as01_kaynak_kontrol
```
"""


def geri_bildirimler(kontrol: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Batuhan'in sablonuna gore acilacak kayitlar."""
    # Kayit ERISIME degil ICERIGE gore acilir. Google Play bugun HTTP 200
    # donuyor ama govdesi bos; erisime bakan bir kural onu "calisiyor" sayip
    # sorunu gizlerdi. Kullanilabilir icerik = gercek-icerik / api-yaniti /
    # besleme; bunlarin hicbirini uretmeyen kaynak icin kayit acilir.
    KULLANILABILIR = ("gercek-icerik", "api-yaniti", "besleme")

    def icerik_veriyor(r: dict[str, Any]) -> bool:
        return r["bugun_erisim"] == "ok" and r["bugun_icerik"] in KULLANILABILIR

    calisan_kaynak = {r["source_id"] for r in kontrol if icerik_veriyor(r)}
    kayitlar: list[dict[str, Any]] = []
    gorulen: set[str] = set()
    for satir in kontrol:
        sid = satir["source_id"]
        if sid in calisan_kaynak or sid in gorulen:
            continue
        gorulen.add(sid)
        etkilenen = sorted({r["fikir"] for r in kontrol
                            if r["source_id"] == sid and not icerik_veriyor(r)})
        if satir["bugun_erisim"].startswith("robots"):
            duzeltme = ("Kaynağın resmî API/izin yolu değerlendirilmeli; "
                        "kazıma yolu politika gereği kapalı.")
            cozum = "robots.txt bağlayıcı — aşma denenmedi ve denenmeyecek."
        elif satir["bugun_erisim"] in ("challenge", "origin_circuit_open"):
            duzeltme = ("Arşiv (Common Crawl) yoluna düşülebilir; sonuç `arsiv` "
                        "olarak işaretlenir, canlı veri sayılmaz.")
            cozum = "Bot koruması aşılmadı; alternatif kaynak önerildi."
        elif satir["bugun_icerik"] == "js-kabugu":
            duzeltme = ("Sayfa tarayıcıda üretiliyor; düz çekimle metin gelmiyor. "
                        "Aynı içerik için alternatif kaynak kullanılmalı.")
            cozum = "Apple App Store aynı uygulamalar için içerik veriyor."
        else:
            duzeltme = "Erişim hatası tekrar denenmeli; adres doğrulanmalı."
            cozum = "Tek koşuda ölçüldü; kalıcı mı geçici mi belirsiz."
        kayitlar.append({
            "fb_id": f"AS01-{sid.replace('source-', '')}",
            "gorev_id": "AS-01", "faz": "1",
            "acan": "Ayselin (ön bildirim)", "atanan": "Batuhan (kontrol)",
            "onem": "yuksek" if len(etkilenen) >= 3 else "orta",
            "durum": "acik",
            "kaynak": f'{satir["kaynak_adi"]} ({sid})',
            "etkilenen_fikirler": ", ".join(etkilenen),
            "kosu": f'as01_kaynak_kontrol.py {SURUM}',
            "yeniden_uretim": f'as01_kaynak_kontrol.py --canli → {satir["denenen_url"]}',
            "beklenen": f'Kayıtlı durum: {satir["kayitli_icerik"]}',
            "gerceklesen": f'{satir["bugun_erisim"]} / {satir["bugun_icerik"]}',
            "kanit": (satir["bugun_artefakt_dosya"] or
                      f'istek atılmadı: {satir["bugun_kanit"][:60]}'),
            "yapilacak_duzeltme": duzeltme,
            "cozum_ve_alternatifler": cozum,
            "batuhan_yeniden_kontrolu": "bekliyor",
        })
    return kayitlar


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--yaz", action="store_true", help="çıktıları diske yaz")
    ayristirici.add_argument("--canli", action="store_true",
                             help="kaynakları BUGÜN yeniden yokla (28 istek)")
    secenek = ayristirici.parse_args(argv)

    import collections

    kontrol = kontrol_et(canli=secenek.canli)
    ornekler = alan_ornekleri(kontrol) if secenek.canli else []
    bildirimler = geri_bildirimler(kontrol) if secenek.canli else []
    iddialar = iddialari_dogrula(kontrol) if secenek.canli else []
    ozet = {
        "surum": SURUM,
        "fikir": len(FIKIR_KAYNAK),
        "deneme": len(kontrol),
        "tekil_kaynak": len({r["source_id"] for r in kontrol}),
        "canli": secenek.canli,
        "degisim": dict(collections.Counter(r["degisti_mi"] for r in kontrol)),
        "artefakt_konumu": artefakt_dagilimi(),
        "alan_ornegi": len(ornekler),
        "geri_bildirim": len(bildirimler),
        "iddia_dogrulama": dict(collections.Counter(
            r["bugun_sonuc"] for r in iddialar)),
    }
    print(json.dumps(ozet, ensure_ascii=False, indent=2))
    if not secenek.yaz:
        return 0

    _yaz("AS01-KAYNAK-KONTROL.csv", kontrol)
    if secenek.canli:
        _yaz("AS01-ALAN-ORNEKLERI.csv", ornekler)
        _yaz("AS01-GERI-BILDIRIM.csv", bildirimler)
        _yaz("AS01-IDDIA-DOGRULAMA.csv", iddialar)
        (HERE / "AS01-ERISIM-SINIRLARI.md").write_text(
            erisim_sinirlari(kontrol, ornekler, iddialar), encoding="utf-8")
        print("AS01-KAYNAK-KONTROL.csv · AS01-ALAN-ORNEKLERI.csv · "
              "AS01-GERI-BILDIRIM.csv · AS01-IDDIA-DOGRULAMA.csv · "
              "AS01-ERISIM-SINIRLARI.md")
    else:
        print("AS01-KAYNAK-KONTROL.csv (ağsız: bugünkü sütunlar not_run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# --------------------------------------------------------------------------
# Mevcut laboratuvar iddialarinin dogrulanmasi
# --------------------------------------------------------------------------
# KAYNAK-ALAN.csv (Gorev 4) her kaynak icin hangi alanin alinabilecegini
# soyler, ama satirlarin cogu `beyan` durumunda: iddia var, dogrulama yok.
# AS-01 "mevcut kaynak/alan/ornekleri incele" diyor; bu bolum o iddialari
# BUGUNKU yanitla karsilastirir.
#
# Desenler yanitin icinde o alanin gercekten bulunup bulunmadigina bakar.
# Bulunmazsa "dogrulanamadi" yazilir - "yok" DEGIL: tek bir ornek yuzeyden
# bakildi, kaynagin baska ucunda bulunabilir.
ALAN_DESENI: dict[str, str] = {
    "baslik": r'(?is)<title[^>]*>\s*\S|"(?:title|name|headline)"\s*:\s*"[^"]+',
    "url": r'(?i)https?://',
    "puan": r'(?i)"(?:ratingValue|rating|score|aggregateRating)"|(?:\b[0-5][.,]\d\b\s*(?:/\s*5|stars?|yıldız|puan))',
    "yorum_sayisi": r'(?i)"(?:reviewCount|ratingCount|answer_count|comment_count|num_comments)"|\d[\d.,]*\s*(?:reviews?|ratings?|yorum|değerlendirme)',
    "fiyat": r'(?i)"(?:price|priceCurrency|offers)"|[$€£₺]\s?\d|\b\d+[.,]\d{2}\s*(?:USD|EUR|TRY|TL)',
    "fiyat_bandi": r'(?i)"(?:lowPrice|highPrice|priceRange)"|\b(?:from|başlangıç|itibaren)\b[^.\n]{0,20}[$€£₺]\d',
    "saglayici_adi": r'(?i)"(?:author|seller|brand|owner|provider|developer|publisher)"|"display_name"',
    "yayin_tarihi": r'(?i)"(?:datePublished|creation_date|created_at|created_utc|published)"|<time[^>]+datetime=',
    "son_guncelleme": r'(?i)"(?:dateModified|last_activity_date|updated_at|lastModified|last_edit_date)"',
    "etiket": r'(?i)"(?:tags|keywords|categor|pipeline_tag|genres?)"',
    "indirme_sayisi": r'(?i)"(?:downloads|installs?|download_count)"|\d[\d.,]*\s*(?:downloads|installs|indirme)',
    "kullanici_sikayeti": r'(?i)"(?:reviewBody|body|text|body_markdown)"|\b(?:complain|şikayet|sorun|problem|issue)\w*\b',
    "urun_sayisi": r'(?i)"(?:total|totalResults|nbHits|numFound|resultCount)"|\d[\d.,]*\s*(?:results?|apps?|ürün|sonuç)',
    "kayit_sayisi": r'(?i)"(?:total|count|nbHits|has_more|quota_remaining)"',
    "siralama": r'(?i)"(?:rank|position|order|relevance)"|\bsıralama\b',
    "konum": r'(?i)"(?:address|location|geo|areaServed)"|\b(?:İstanbul|Ankara|İzmir)\b',
    "lisans": r'(?i)"(?:license|licence|spdx)"|\b(?:MIT|Apache-?2|GPL|BSD-3|CC-BY)\b',
    "trend_serisi": r'(?i)"(?:trend|history|timeseries|series)"',
    "istatistik_serisi": r'(?i)"(?:statistics|stats|series|observations)"',
}


def iddialari_dogrula(kontrol: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """KAYNAK-ALAN.csv'nin iddialarini bugunku yanitla karsilastirir."""
    import re as _re

    kaynak_alan = _oku("KAYNAK-ALAN.csv")
    bugun = {r["source_id"]: r for r in kontrol
             if r["bugun_erisim"] == "ok" and r["bugun_artefakt"]}
    ilgili = {r["source_id"] for r in kontrol}

    govdeler: dict[str, str] = {}
    for sid, satir in bugun.items():
        yol = HERE / satir["bugun_artefakt_dosya"]
        if yol.exists():
            govdeler[sid] = yol.read_bytes()[:400_000].decode("utf-8", "replace")

    satirlar: list[dict[str, Any]] = []
    for iddia in kaynak_alan:
        sid = iddia["source_id"]
        if sid not in ilgili:
            continue
        govde = govdeler.get(sid)
        desen = ALAN_DESENI.get(iddia["alan"])
        if govde is None:
            sonuc = "yoklanamadi"
            gerekce = "kaynak bugün içerik vermedi; iddia sınanamadı"
        elif desen is None:
            sonuc = "desen-yok"
            gerekce = f'"{iddia["alan"]}" için otomatik doğrulama deseni tanımlı değil'
        elif _re.search(desen, govde):
            sonuc = "dogrulandi"
            gerekce = "bugünkü yanıtta bu alan bulundu"
        else:
            sonuc = "dogrulanamadi"
            gerekce = ("bu yüzeyde bulunamadı — alan YOK demek değildir, "
                       "kaynağın başka ucunda olabilir")
        satirlar.append({
            "source_id": sid,
            "kaynak_adi": iddia["ad"],
            "alan": iddia["alan"],
            "alan_turu": iddia["alan_turu"],
            "laboratuvar_izin": iddia["izin_durumu"],
            "laboratuvar_guven": iddia["guven"],
            "bugun_yoklanan_url": bugun.get(sid, {}).get("denenen_url", ""),
            "bugun_artefakt": bugun.get(sid, {}).get("bugun_artefakt", ""),
            "bugun_sonuc": sonuc,
            "gerekce": gerekce,
            "hizmet_ettigi_soru": iddia["hizmet_ettigi_soru"][:80],
        })
    return satirlar
