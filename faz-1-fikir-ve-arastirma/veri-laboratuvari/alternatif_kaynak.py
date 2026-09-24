"""AS-01/AS-03 — kapali kaynaklara izinli alternatif arar ve kanitla raporlar.

AS-01 olctu: Batuhan'in F01-F10 matrisindeki 14 kaynaktan 6'si bugun icerik
vermiyor ve **F02 ile F09'un hicbir kaynagi calismiyor**. Bu modul o iki fikre
izinli alternatif arar.

Uc kural:

1. **Bot korumasi asilmaz, robots baglayicidir.** Aday once robots'tan gecer;
   gecmezse denenmez ve sebebi yazilir.

2. **HTTP 200 ilgili icerik demek degildir.** SourceForge "salon scheduling
   software" aramasina 200 ve 19 bin karakter dondurdu; icerigi Kubernetes
   orkestrasyon araci ve kripto fiyatlama idi. Bu yuzden her aday ayrica
   **ilgililik** testinden gecer: nisin kendi kelimeleri yanit govdesinde
   geciyor mu, ve genel navigasyon disinda geciyor mu.

3. **source_id uydurulmaz.** Katalogda olmayan aday ``oneri`` olarak
   isaretlenir; registry'ye eklenmesi Batuhan'in karari.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import urllib.parse
import urllib.robotparser
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SURUM = "1.0.0"

# (fikir, nis, [(ad, source_id|"", origin, yol)])
# source_id bos ise katalogda YOKTUR ve oneri olarak islenir.
ADAYLAR: list[tuple[str, str, list[tuple[str, str, str, str]]]] = [
    ("F02", "ajans müşteri onayı ve revizyon", [
        ("Filestage", "", "https://filestage.io", "/pricing/"),
        ("Ziflow", "", "https://www.ziflow.com", "/pricing"),
        ("SourceForge Reviews", "source-0141", "https://sourceforge.net",
         "/directory/?q=proofing%20software"),
        ("GetApp", "source-0136", "https://www.getapp.com", "/search?query=proofing"),
    ]),
    ("F09", "berber/salon randevu ve gelmeme", [
        ("Fresha", "source-0317", "https://www.fresha.com", "/pricing"),
        ("Booksy", "source-0318", "https://booksy.com", "/en-us/"),
        ("SourceForge Reviews", "source-0141", "https://sourceforge.net",
         "/directory/?q=salon%20scheduling%20software"),
        ("SoftwareSuggest", "source-0146", "https://www.softwaresuggest.com",
         "/search/index?query=salon"),
        # Satici sitesi sikayet yayimlamaz. Booksy'nin isletme uygulamasi
        # App Store'da ve orada gercek kullanici yorumu var — F09'un
        # dissatisfaction bosluğunu kapatan tek yol bu cikti.
        ("Apple App Store — Booksy Biz", "source-0096", "https://apps.apple.com",
         "/us/app/booksy-biz-booking-payments/id725335996"),
        ("Apple App Store — Fresha", "source-0096", "https://apps.apple.com",
         "/us/app/fresha-for-business/id1455346253"),
    ]),
]

# Satici sitesi ile kullanici yorumu ayni sey degildir. Bir satici kendi
# hakkindaki sikayeti yayimlamaz; "alternatifler" sayfasi da pazarlamadir.
# Kanit politikasi da ayni sonuca variyor: "Ayni kurumun pazarlama kopyalari
# bir koken" — yani satici sayfalari bagimsiz ornek saymaz.
SATICI_SITESI = frozenset({"Filestage", "Ziflow", "Fresha", "Booksy"})

# Nisin kendi kelimeleri. Ilgililik bunlarin govdede gecmesiyle olculur;
# "software" gibi her sayfada gecen genel kelimeler kasten disarida.
NIS_KELIMELERI: dict[str, tuple[str, ...]] = {
    "F02": ("proof", "approval", "revision", "annotat", "review round",
            "creative", "agency", "client feedback", "markup"),
    "F09": ("salon", "barber", "berber", "kuaför", "appointment", "randevu",
            "no-show", "booking", "stylist", "spa"),
}
ASGARI_NIS_ISARETI = 3
NAVIGASYON_ESIGI = 400


def _yaz(ad: str, satirlar: list[dict[str, Any]]) -> None:
    if not satirlar:
        return
    with (HERE / ad).open("w", newline="", encoding="utf-8") as tutamak:
        yazici = csv.DictWriter(tutamak, fieldnames=list(satirlar[0]))
        yazici.writeheader()
        yazici.writerows(satirlar)


def ilgililik(metin: str, fikir: str) -> tuple[str, str]:
    """(etiket, gerekce). relevant / irrelevant / uncertain.

    Rehber ornek sonuclarin insan etiketiyle relevant/irrelevant/uncertain
    ayrilmasini istiyor; bu otomatik on eleme o etiketlemeyi hazirlar,
    yerine gecmez.
    """
    govde = metin[NAVIGASYON_ESIGI:] or metin
    kucuk = govde.casefold()
    bulunan = [k for k in NIS_KELIMELERI[fikir] if k.casefold() in kucuk]
    if len(bulunan) >= ASGARI_NIS_ISARETI:
        return "relevant", f'nişe özgü {len(bulunan)} işaret: {", ".join(bulunan[:5])}'
    if bulunan:
        return "uncertain", f'yalnız {len(bulunan)} işaret: {", ".join(bulunan)}'
    return "irrelevant", ("nişin hiçbir kelimesi gövdede yok — sayfa geldi ama "
                          "konu başka")


def dene(ad: str, source_id: str, origin: str, yol: str,
         fikir: str, canli: bool) -> dict[str, Any]:
    if not canli:
        return {"erisim": "not_run", "icerik": "not_run", "ilgililik": "not_run",
                "gerekce": "", "artefakt": "", "artefakt_dosya": "",
                "bulunan_fiyat": "", "metin_uzunlugu": 0}

    import normalize_belgeler as nb
    import veri_envanteri as ve
    from bulk_site_access_lab import (ROBOTS_BLOCKED, OriginRuntime,
                                      USER_AGENT, robots_state)

    bos = {"icerik": "alinmadi", "ilgililik": "sinanamadi", "artefakt": "",
           "artefakt_dosya": "", "bulunan_fiyat": "", "metin_uzunlugu": 0}
    runtime = OriginRuntime(origin, lease=4, live=True)
    robots = runtime.fetch("as01alt", "robots_preflight", origin + "/robots.txt",
                           "robots", robots_decision="not_required")
    durum = robots_state(robots)
    if durum == ROBOTS_BLOCKED:
        return {**bos, "erisim": "robots_preflight_blocked",
                "gerekce": "robots.txt 401/403 — RFC 9309 tam yasak"}
    ayristirici = urllib.robotparser.RobotFileParser()
    ayristirici.set_url(origin + "/robots.txt")
    ayristirici.parse(robots.body.decode("utf-8", "replace").splitlines()
                      if durum == "policy" else [])
    runtime.robots_parser = ayristirici
    hedef = origin + yol
    if not ayristirici.can_fetch(USER_AGENT, hedef):
        return {**bos, "erisim": "robots_disallowed",
                "gerekce": "robots.txt bu yolu yasaklıyor — istek atılmadı"}

    cikti = runtime.fetch("as01alt", "alternatif", hedef, "html",
                          robots_decision="required")
    if not cikti.ok:
        return {**bos, "erisim": cikti.stop_reason or cikti.outcome, "gerekce": ""}

    ozet = hashlib.sha256(cikti.body).hexdigest()
    dosya = HERE / "results" / "raw" / f"{ozet}.bin"
    dosya.parent.mkdir(parents=True, exist_ok=True)
    if not dosya.exists():
        dosya.write_bytes(cikti.body)

    govde = cikti.body[:400_000]
    cikarim = nb.metin_cikar(govde, "text/html")
    icerik, _g = ve.icerik_durumu("alternatif", "text/html", govde)
    etiket, gerekce = ilgililik(cikarim["metin"], fikir)
    fiyatlar = [b["deger"] for b in nb.alan_cikar("urun", cikarim["metin"], "")
                if b["alan"] == "fiyat"]
    return {"erisim": "ok", "icerik": icerik, "ilgililik": etiket,
            "gerekce": gerekce, "artefakt": ozet,
            "artefakt_dosya": f"results/raw/{ozet}.bin",
            "bulunan_fiyat": ", ".join(fiyatlar[:3]),
            "metin_uzunlugu": len(cikarim["metin"])}


def ara(canli: bool) -> list[dict[str, Any]]:
    satirlar: list[dict[str, Any]] = []
    for fikir, nis, adaylar in ADAYLAR:
        for ad, sid, origin, yol in adaylar:
            sonuc = dene(ad, sid, origin, yol, fikir, canli)
            sonuc["kaynak_cinsi"] = ("satıcı sitesi — kendi hakkında şikâyet yayımlamaz"
                                     if ad in SATICI_SITESI else "üçüncü taraf")
            kullanilabilir = (sonuc["erisim"] == "ok"
                              and sonuc["icerik"] in ("gercek-icerik", "api-yaniti")
                              and sonuc["ilgililik"] == "relevant")
            satirlar.append({
                "fikir": fikir, "nis": nis, "aday": ad,
                "source_id": sid or "(katalogda yok)",
                "katalog_durumu": "kayitli" if sid else "öneri — registry kararı Batuhan'da",
                "denenen_url": origin + yol,
                **sonuc,
                "kullanilabilir_mi": "evet" if kullanilabilir else "hayir",
                "neden_kullanilamaz": "" if kullanilabilir else _neden(sonuc),
            })
    return satirlar


def _neden(sonuc: dict[str, Any]) -> str:
    if sonuc["erisim"] == "not_run":
        return "canlı koşu yapılmadı"
    if sonuc["erisim"].startswith("robots"):
        return "politika engeli — aşılmaz"
    if sonuc["erisim"] != "ok":
        return f'erişim hatası: {sonuc["erisim"]}'
    if sonuc["icerik"] == "js-kabugu":
        return "sayfa tarayıcıda üretiliyor; gövde boş"
    if sonuc["ilgililik"] == "irrelevant":
        return ("içerik geldi ama nişle ilgisiz — anahtar kelime eşleşmesi "
                "ilgililik değildir")
    if sonuc["ilgililik"] == "uncertain":
        return "ilgililik belirsiz; insan etiketi gerekir"
    return "belirsiz"


def rapor(satirlar: list[dict[str, Any]]) -> str:
    import collections
    import datetime

    bugun = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    fikir_bazinda: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for r in satirlar:
        fikir_bazinda[r["fikir"]].append(r)

    bolumler = []
    for fikir in sorted(fikir_bazinda):
        kayitlar = fikir_bazinda[fikir]
        nis = kayitlar[0]["nis"]
        calisan = [r for r in kayitlar if r["kullanilabilir_mi"] == "evet"]
        kayitli = [r for r in calisan if r["source_id"] != "(katalogda yok)"]
        oneri = [r for r in calisan if r["source_id"] == "(katalogda yok)"]
        tablo = "\n".join(
            f'| {r["aday"]} | {r["source_id"]} | {r["erisim"]} | {r["ilgililik"]} | '
            f'{r["bulunan_fiyat"] or "—"} | {r["kullanilabilir_mi"]} | '
            f'{r["neden_kullanilamaz"] or "—"} |' for r in kayitlar)
        durum = ("**Çözüldü — katalogdaki kaynaklarla.**" if kayitli and not oneri
                 else "**Çözüldü — ama registry'ye ekleme gerekiyor.**" if oneri
                 else "**Çözülemedi.**")
        bolumler.append(f"""### {fikir} — {nis}

{durum}

| Aday | source_id | Erişim | İlgililik | Fiyat | Kullanılabilir | Neden olmaz |
|---|---|---|---|---|---|---|
{tablo}
""")

    kullanilabilir = [r for r in satirlar if r["kullanilabilir_mi"] == "evet"]
    oneriler = [r for r in kullanilabilir if r["source_id"] == "(katalogda yok)"]
    ilgisiz = [r for r in satirlar if r["ilgililik"] in ("uncertain", "irrelevant")]

    return f"""# AS-01 eki — kapalı kaynaklara izinli alternatif

**Sürüm {SURUM}** · Ölçüm tarihi: {bugun} · Üreten: `alternatif_kaynak.py`
Hazırlayan: Ayselin Aydoğdu · Kontrol eden: Batuhan

AS-01 ölçümü F02 ve F09'un **hiçbir kaynağının** bugün içerik vermediğini
gösterdi: G2 ve Capterra bot koruması, Reddit robots yasağı. Bu ek o iki
fikre izinli alternatif arar.

## Sonuç

| | |
|---|---|
| Denenen aday | {len(satirlar)} |
| Kullanılabilir bulunan | **{len(kullanilabilir)}** |
| Bunlardan katalogda olmayan | {len(oneriler)} |

{"".join(bolumler)}
## HTTP 200 ilgili içerik demek değildir

{len(ilgisiz)} aday sayfa döndürdü ama nişle ilgisi belirsiz ya da yoktu.
En net örnek **SourceForge**: `salon scheduling software` aramasına HTTP 200
ve 19 bin karakter döndürdü. İçeriği Kubernetes orkestrasyon aracı ve kripto
fiyatlama yazılımıydı — SourceForge açık kaynak proje dizini, salon SaaS'ı
yok.

Bu yüzden her aday üç ayrı testten geçti:

1. **Erişim** — robots izin veriyor mu, HTTP yanıtı geldi mi
2. **İçerik** — gövdede görünür metin var mı (JS kabuğu değil mi)
3. **İlgililik** — nişin kendi kelimeleri gövdede geçiyor mu

Üçü de geçmeyen aday `kullanilabilir_mi = hayir` işaretlidir. İlgililik
etiketi otomatik ön elemedir; rehberin istediği insan etiketinin
(`relevant`/`irrelevant`/`uncertain` + neden) yerine geçmez, onu hazırlar.

## Registry'ye önerilenler

{"Yok." if not oneriler else "Aşağıdaki adaylar katalogda **yok**. Uydurma `source_id` verilmedi; kayıt kararı Batuhan'ın:"}

{chr(10).join(f'- **{r["aday"]}** — `{r["denenen_url"]}` · {r["fikir"]} · kanıt `{r["artefakt"][:12]}`' for r in oneriler)}

## Bu ek ne söylemez

- Bir alternatifin çalışması **kanıt yeterliliği** sağlamaz. 3 bağımsız örnek
  / 2 ayrı kaynak eşiği Faz 3'e aittir.
- Fiyat alanları satıcının ilan ettiği fiyattır; ödeme davranışı değildir.
- Kapalı kaynaklar **zorlanmadı**: bot koruması aşılmadı, robots yasağına
  uyuldu. G2, Capterra ve Reddit hâlâ kapalı ve öyle raporlanıyor.
- Ölçüm {bugun} tarihlidir.

## Yeniden üretim

```bash
python3 alternatif_kaynak.py --yaz --canli
python3 -m unittest test_alternatif_kaynak
```
"""


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--yaz", action="store_true")
    ayristirici.add_argument("--canli", action="store_true",
                             help="adayları BUGÜN dene")
    secenek = ayristirici.parse_args(argv)

    import collections

    satirlar = ara(canli=secenek.canli)
    print(json.dumps({
        "surum": SURUM, "aday": len(satirlar),
        "kullanilabilir": sum(1 for r in satirlar if r["kullanilabilir_mi"] == "evet"),
        "ilgililik": dict(collections.Counter(r["ilgililik"] for r in satirlar)),
        "canli": secenek.canli,
    }, ensure_ascii=False, indent=2))
    if not secenek.yaz:
        return 0
    _yaz("AS01-ALTERNATIF-KAYNAK.csv", satirlar)
    if secenek.canli:
        (HERE / "AS01-ALTERNATIF-RAPOR.md").write_text(rapor(satirlar), encoding="utf-8")
        print("AS01-ALTERNATIF-KAYNAK.csv · AS01-ALTERNATIF-RAPOR.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
