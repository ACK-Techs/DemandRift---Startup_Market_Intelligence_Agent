"""AS-02/AS-03 — BT-03'ün bildirdiği eksik alanları yeniden üretir ve ayırır.

Batuhan'in BT-03 bildirimi (2026-09-30): F03 canli kosusunda GitHub'da `govde`
ve `surum`, Hacker News'te `govde` alanlari gelmedi; Stack Overflow tam.

Sorulan soru su: **alan API'de yok mu, yoksa cikarim mi kaciriyor?** Ikisi
tamamen farkli duzeltme gerektirir:

* API vermiyorsa duzeltme bizde degil — **beklenti listesi yanlis**.
* API veriyorsa duzeltme cikarimda — **alan okunmuyor**.

Bu modul ucuncu bir ihtimali de ayirir: alan API'de VAR ama bu sorgunun
sonuclarinda BOS. O zaman kaynak sinirli degildir, sonuç kümesi öyledir.

Her bulgu AS-03 icin `basarisiz` ya da `kismi` olarak siniflandirilir;
"calisti" demek yetmez, hangi alanin neden gelmedigi kayda gecer.
"""
from __future__ import annotations

import argparse
import csv
import json
import urllib.parse
import urllib.robotparser
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SURUM = "1.0.0"
SORGU = "API breaking changes backward compatibility"

# Batuhan'in f03-live-source-run-contract.md'deki beklentisi ve her alanin
# API'de hangi anahtara karsilik geldigi. Birden cok aday varsa sirayla aranir.
# Aday listesi bos ise: API'de boyle bir alan YOKTUR.
SOZLESMELER: list[dict[str, Any]] = [
    {
        "source_id": "source-0017", "ad": "GitHub",
        "origin": "https://api.github.com",
        "yol": f"/search/issues?q={urllib.parse.quote(SORGU)}&per_page=5",
        "liste_anahtari": "items",
        "beklenen": {
            "baslik": ["title"],
            "govde": ["body"],
            "kaynak_url": ["html_url"],
            "yayin_tarihi": ["created_at"],
            "surum": [],          # /search/issues sürüm alanı yayımlamıyor
        },
    },
    {
        "source_id": "source-0023", "ad": "Stack Overflow",
        "origin": "https://api.stackexchange.com",
        "yol": ("/2.3/search/advanced?site=stackoverflow&q="
                f"{urllib.parse.quote(SORGU)}&pagesize=5"),
        "liste_anahtari": "items",
        "beklenen": {
            "baslik": ["title"],
            "etiket": ["tags"],
            "kaynak_url": ["link"],
            "yayin_tarihi": ["creation_date"],
        },
    },
    {
        "source_id": "source-0022", "ad": "Hacker News",
        "origin": "https://hn.algolia.com",
        "yol": f"/api/v1/search?query={urllib.parse.quote(SORGU)}&hitsPerPage=5",
        "liste_anahtari": "hits",
        "beklenen": {
            "baslik": ["title", "story_title"],
            "govde": ["comment_text", "story_text"],
            # story_url bağlanan YAZININ adresi; yorumun kendi adresi degil.
            # Yorumun kanonik adresi item?id=<objectID> ile turetilir.
            "kaynak_url": ["url", "hn:objectID"],
            "yayin_tarihi": ["created_at"],
            "yazar": ["author"],
        },
    },
]


def _alan_coz(kayit: dict[str, Any], adaylar: list[str]) -> tuple[str, str]:
    """Adaylari sirayla dener; ilk dolu olani doner. `hn:` oneki turetir."""
    for aday in adaylar:
        if aday.startswith("hn:"):
            ham = kayit.get(aday[3:])
            if ham:
                return f"https://news.ycombinator.com/item?id={ham}", aday
            continue
        deger = kayit.get(aday)
        if deger:
            return (", ".join(map(str, deger)) if isinstance(deger, list)
                    else str(deger)), aday
    return "", ""


def _yaz(ad: str, satirlar: list[dict[str, Any]]) -> None:
    if not satirlar:
        return
    with (HERE / ad).open("w", newline="", encoding="utf-8") as tutamak:
        yazici = csv.DictWriter(tutamak, fieldnames=list(satirlar[0]))
        yazici.writeheader()
        yazici.writerows(satirlar)


def api_cagir(origin: str, yol: str,
              ozet_kutusu: list[str] | None = None) -> Any | str:
    """Yaniti doner, ya da hata sebebini string olarak.

    `ozet_kutusu` verilirse yanitin sha256'si ve kaydedildigi dosya yolu
    icine yazilir. Kanit zinciri icin sart: rapordaki her sayi diskteki bir
    dosyaya geri izlenebilmeli.
    """
    from bulk_site_access_lab import (ROBOTS_BLOCKED, OriginRuntime,
                                      USER_AGENT, robots_state)

    runtime = OriginRuntime(origin, lease=3, live=True)
    robots = runtime.fetch("bt03", "robots_preflight", origin + "/robots.txt",
                           "robots", robots_decision="not_required")
    durum = robots_state(robots)
    if durum == ROBOTS_BLOCKED:
        return "robots_preflight_blocked"
    ayristirici = urllib.robotparser.RobotFileParser()
    ayristirici.set_url(origin + "/robots.txt")
    ayristirici.parse(robots.body.decode("utf-8", "replace").splitlines()
                      if durum == "policy" else [])
    runtime.robots_parser = ayristirici
    if not ayristirici.can_fetch(USER_AGENT, origin + yol):
        return "robots_disallowed"
    cikti = runtime.fetch("bt03", "bt03_alan", origin + yol, "json",
                          robots_decision="required")
    if not cikti.ok:
        return cikti.stop_reason or cikti.outcome
    if ozet_kutusu is not None:
        import hashlib
        ozet = hashlib.sha256(cikti.body).hexdigest()
        dosya = HERE / "results" / "raw" / f"{ozet}.bin"
        dosya.parent.mkdir(parents=True, exist_ok=True)
        if not dosya.exists():
            dosya.write_bytes(cikti.body)
        ozet_kutusu[:] = [ozet, f"results/raw/{ozet}.bin"]
    try:
        return json.loads(cikti.body)
    except ValueError:
        return "invalid_output"


def analiz(canli: bool) -> list[dict[str, Any]]:
    import datetime

    bugun = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    satirlar: list[dict[str, Any]] = []
    for sozlesme in SOZLESMELER:
        if not canli:
            for alan in sozlesme["beklenen"]:
                satirlar.append({
                    "source_id": sozlesme["source_id"], "kaynak": sozlesme["ad"],
                    "alan": alan, "durum": "not_run", "api_anahtari": "",
                    "dolu_kayit": "", "toplam_kayit": "", "karar": "not_run",
                    "gerekce": "canlı koşu yapılmadı", "as03_sinifi": "",
                    "olcum_tarihi": bugun})
            continue

        kutu: list[str] = []
        veri = api_cagir(sozlesme["origin"], sozlesme["yol"], kutu)
        artefakt = {"artefakt": kutu[0] if kutu else "",
                    "artefakt_dosya": kutu[1] if len(kutu) > 1 else ""}
        if isinstance(veri, str):
            for alan in sozlesme["beklenen"]:
                satirlar.append({
                    "source_id": sozlesme["source_id"], "kaynak": sozlesme["ad"],
                    "alan": alan, "durum": veri, "api_anahtari": "",
                    "dolu_kayit": 0, "toplam_kayit": 0, "karar": "sinanamadi",
                    "gerekce": f"API çağrısı başarısız: {veri}",
                    "as03_sinifi": "basarisiz", "olcum_tarihi": bugun, **artefakt})
            continue

        kayitlar = [k for k in veri.get(sozlesme["liste_anahtari"], [])
                    if isinstance(k, dict)]
        for alan, adaylar in sozlesme["beklenen"].items():
            if not adaylar:
                satirlar.append({
                    "source_id": sozlesme["source_id"], "kaynak": sozlesme["ad"],
                    "alan": alan, "durum": "ok", "api_anahtari": "(yok)",
                    "dolu_kayit": 0, "toplam_kayit": len(kayitlar),
                    "karar": "API-SAGLAMIYOR",
                    "gerekce": ("bu uçta böyle bir alan yok; beklenti listesinden "
                                "çıkarılmalı ya da başka uç gerekir"),
                    "as03_sinifi": "basarisiz", "olcum_tarihi": bugun, **artefakt})
                continue
            cozum = [_alan_coz(kayit, adaylar) for kayit in kayitlar]
            dolu = sum(1 for deger, _ in cozum if deger)
            kullanilan = sorted({anahtar for deger, anahtar in cozum if deger})
            if dolu == len(kayitlar) and kayitlar:
                satirlar.append({
                    "source_id": sozlesme["source_id"], "kaynak": sozlesme["ad"],
                    "alan": alan, "durum": "ok",
                    "api_anahtari": ", ".join(kullanilan),
                    "dolu_kayit": dolu, "toplam_kayit": len(kayitlar),
                    "karar": "API-VERIYOR",
                    "gerekce": (f"API veriyor ({', '.join(kullanilan)}); "
                                f"{dolu}/{len(kayitlar)} kayıtta dolu"),
                    "as03_sinifi": "", "olcum_tarihi": bugun, **artefakt})
            elif dolu:
                satirlar.append({
                    "source_id": sozlesme["source_id"], "kaynak": sozlesme["ad"],
                    "alan": alan, "durum": "ok",
                    "api_anahtari": ", ".join(kullanilan),
                    "dolu_kayit": dolu, "toplam_kayit": len(kayitlar),
                    "karar": "API-KISMEN-VERIYOR",
                    "gerekce": (f"API veriyor ama {len(kayitlar) - dolu}/"
                                f"{len(kayitlar)} kayıtta boş; kaynak sınırı "
                                "değil sonuç kümesi sınırı"),
                    "as03_sinifi": "kismi", "olcum_tarihi": bugun, **artefakt})
            else:
                satirlar.append({
                    "source_id": sozlesme["source_id"], "kaynak": sozlesme["ad"],
                    "alan": alan, "durum": "ok",
                    "api_anahtari": ", ".join(adaylar),
                    "dolu_kayit": 0, "toplam_kayit": len(kayitlar),
                    "karar": "BU-SONUCLARDA-BOS",
                    "gerekce": ("anahtar şemada var ama bu sorgunun hiçbir "
                                "sonucunda dolu değil"),
                    "as03_sinifi": "kismi", "olcum_tarihi": bugun, **artefakt})
    return satirlar


def main(argv: list[str] | None = None) -> int:
    import collections

    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--yaz", action="store_true")
    ayristirici.add_argument("--canli", action="store_true")
    secenek = ayristirici.parse_args(argv)
    satirlar = analiz(secenek.canli)
    print(json.dumps({
        "surum": SURUM, "sorgu": SORGU, "canli": secenek.canli,
        "alan": len(satirlar),
        "karar": dict(collections.Counter(r["karar"] for r in satirlar)),
        "as03": dict(collections.Counter(r["as03_sinifi"] or "tam" for r in satirlar)),
    }, ensure_ascii=False, indent=2))
    if secenek.yaz:
        _yaz("BT03-ALAN-ANALIZI.csv", satirlar)
        print("BT03-ALAN-ANALIZI.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
