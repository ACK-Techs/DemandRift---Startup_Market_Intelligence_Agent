"""AS-02 — Batuhan'in hata bildirimini yeniden uretir ve sorunu ayirir.

Gorev karti: "Batuhan'in hata bildirimindeki ayni kaynak ve sorguyu yeniden
uret. Erisim, alan cikarimi, yanlis/bos icerik ve dil/pazar sorununu ayir.
Duzeltmeyi once/sonra ham ornek, script surumu ve kalan sinirliliklarla teslim
et. **Batuhan yeniden kontrol etmeden kabul edilmis sayma.**"

Bu modul bildirim gelmeden once kurulmus bir **hazirliktir**, AS-02'nin
tamamlanmasi degil. Girdisi ``AS02-BILDIRIM.csv``; Batuhan bir hata
bildirdiginde o dosyaya bir satir eklenir ve tek komutla kosar.

Dort sorun sinifi ayri tutulur cunku dordu farkli duzeltme ister:

* ``erisim``            — siteye ulasilamiyor (robots, bot korumasi, hiz siniri)
* ``yanlis-bos-icerik`` — yanit geldi ama govde bos ya da konu disi
* ``alan-cikarimi``     — icerik dogru, bizim cikarici alani alamiyor
* ``dil-pazar``         — icerik dogru ama yanlis dil ya da yanlis pazar

Ayrim onemli: "sorgu calismadi" uc farkli seyi ayni kefeye koyar. Sitenin
kapisi kapaliysa duzeltme bizde degildir; sayfa geldi de alan cikmadiysa
duzeltme tam olarak bizdedir.

``--asama once`` bozuk hali kaydeder, duzeltme yapilir, ``--asama sonra``
ayni sorguyu tekrar kosar. Iki asamanin ham artefakti da saklanir ve
``AS02-YENIDEN-URETIM.csv`` ikisini yan yana koyar.

Hicbir satir kendiliginden "kabul edildi" olmaz: ``batuhan_yeniden_kontrolu``
alani daima ``bekliyor`` ile baslar.
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
BILDIRIM_DOSYASI = "AS02-BILDIRIM.csv"
SONUC_DOSYASI = "AS02-YENIDEN-URETIM.csv"

# Batuhan'in dolduracagi girdi sutunlari.
BILDIRIM_SUTUNLARI: tuple[str, ...] = (
    "fb_id",            # geri bildirim kaydi kimligi
    "fikir",            # F01..F10
    "source_id",        # katalog kimligi
    "denenen_url",      # tam adres; sorgu parametresi dahil
    "sorgu_metni",      # kullanilan anahtar kelime (varsa)
    "beklenen",         # ne bekliyordu
    "batuhan_gozlemi",  # ne gordu
    "hedef_dil",        # tr / en / (bos = onemsiz)
    "hedef_pazar",      # TR / US / global
    "bildirim_tarihi",
)

# Icerik dogru geldiginde alan cikarimini sinamak icin: hangi alanlar bekleniyor.
# Bos birakilirsa alan kontrolu yapilmaz, yalniz erisim ve icerik olculur.
BEKLENEN_ALANLAR_SUTUNU = "beklenen_alanlar"

ERISIM_SORUNLARI = {
    "robots_disallowed", "robots_preflight_blocked", "challenge",
    "origin_circuit_open", "rate_limited", "source_unavailable",
    "origin_denied", "budget_exhausted", "blocked_by_policy",
}
BOS_ICERIK = {"js-kabugu", "dosya-yok", "engel-sayfasi"}


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


def bildirim_sablonu_yaz() -> Path:
    """Batuhan'in dolduracagi bos sablonu olusturur."""
    yol = HERE / BILDIRIM_DOSYASI
    if yol.exists():
        return yol
    with yol.open("w", newline="", encoding="utf-8") as tutamak:
        yazici = csv.writer(tutamak)
        yazici.writerow(list(BILDIRIM_SUTUNLARI) + [BEKLENEN_ALANLAR_SUTUNU])
    return yol


def sorunu_ayir(erisim: str, icerik: str, metin: str, ilgili_mi: bool | None,
                bulunan_alanlar: set[str], beklenen_alanlar: set[str],
                dil: str, hedef_dil: str) -> tuple[str, str]:
    """(sinif, gerekce). Kartin dort sinifindan birine ayirir.

    Sira onemli: erisim yoksa icerik konusulamaz, icerik yoksa alan
    konusulamaz. Her katman bir ustune bagli.
    """
    if erisim in ERISIM_SORUNLARI:
        return "erisim", f"siteye ulaşılamadı: {erisim}"
    if erisim != "ok":
        return "erisim", f"istek başarısız: {erisim}"
    if icerik in BOS_ICERIK:
        return "yanlis-bos-icerik", f"yanıt geldi ama gövde kullanılabilir değil: {icerik}"
    if ilgili_mi is False:
        return "yanlis-bos-icerik", "içerik geldi ama sorgunun konusuyla ilgisiz"
    if hedef_dil and dil not in ("unknown", "") and dil != hedef_dil:
        return "dil-pazar", f"içerik {dil} dilinde, hedef {hedef_dil}"
    if beklenen_alanlar:
        eksik = beklenen_alanlar - bulunan_alanlar
        if eksik:
            return "alan-cikarimi", ("içerik doğru ama şu alanlar çıkarılamadı: "
                                     + ", ".join(sorted(eksik)))
    if hedef_dil and dil == "unknown":
        return "dil-pazar", "içerik dili belirlenemedi; hedef dil doğrulanamıyor"
    return "sorun-yok", ("bu koşuda sorun görülmedi — bildirimdeki durum "
                         "tekrarlanmadı, koşul değişmiş olabilir")


# Sorgunun ayirt edici olmayan kelimeleri. "software" bir yazilim dizininin
# her sayfasinda gecer; onu saymak SourceForge'u "ilgili" yapar. On dogrulama
# tam olarak bu tuzagi yakaladi.
GENEL_KELIMELER = frozenset({
    "software", "yazilim", "yazılım", "tool", "tools", "arac", "araç",
    "online", "platform", "system", "sistem", "service", "hizmet",
    "program", "uygulama", "best", "free", "ucretsiz", "ücretsiz",
    "download", "indir", "review", "reviews", "yorum", "yorumlar",
})


def _ilgili_mi(metin: str, sorgu: str) -> bool | None:
    """Sorgunun AYIRT EDICI kelimeleri govdede geciyor mu.

    Sorgu yoksa ya da yalniz genel kelimelerden ibaretse None doner:
    ilgililik olculemez, "ilgisiz" de denmez.

    Navigasyonu saymamak icin ilk 400 karakter atlanir; menu ve baslik her
    sayfada sorgunun kelimesini tasiyabilir.
    """
    kelimeler = [k for k in re.findall(r"\w{4,}", sorgu.casefold())
                 if k not in GENEL_KELIMELER]
    if not kelimeler:
        return None
    govde = (metin[400:] or metin).casefold()
    # Arama sonucu sayfalari sorguyu kendi icinde tekrarlar:
    # "Search Results for 'salon scheduling software'". Bu yanki sayilirsa
    # her arama sayfasi "ilgili" cikar. SourceForge'da tam boyle oldu:
    # 'salon' uc kez geciyordu, ucu de sitenin sorguyu geri yazmasiydi.
    govde = govde.replace(sorgu.casefold(), " ")
    bulunan = sum(1 for k in kelimeler if k in govde)
    # Iki ya da daha az ayirt edici kelime varsa HEPSI aranir; bir tanesinin
    # gecmesi yetmez.
    gereken = len(kelimeler) if len(kelimeler) <= 2 else (len(kelimeler) + 1) // 2
    return bulunan >= gereken


def bir_bildirimi_kos(bildirim: dict[str, str], asama: str) -> dict[str, Any]:
    """Tek bir bildirimi yeniden uretir ve ham artefakti saklar."""
    import normalize_belgeler as nb
    import veri_envanteri as ve
    from bulk_site_access_lab import (ROBOTS_BLOCKED, OriginRuntime,
                                      USER_AGENT, robots_state)

    url = bildirim["denenen_url"].strip()
    parcalar = urllib.parse.urlsplit(url)
    origin = f"{parcalar.scheme}://{parcalar.netloc}"
    beklenen_alanlar = {a.strip() for a in
                        bildirim.get(BEKLENEN_ALANLAR_SUTUNU, "").split(",") if a.strip()}
    hedef_dil = bildirim.get("hedef_dil", "").strip()

    temel: dict[str, Any] = {
        "erisim": "", "icerik": "", "metin_uzunlugu": 0, "dil": "",
        "bulunan_alanlar": "", "artefakt": "", "artefakt_dosya": "",
        "ilgili_mi": "", "http_durum": "",
    }

    runtime = OriginRuntime(origin, lease=4, live=True)
    robots = runtime.fetch("as02", "robots_preflight", origin + "/robots.txt",
                           "robots", robots_decision="not_required")
    durum = robots_state(robots)
    if durum == ROBOTS_BLOCKED:
        temel["erisim"] = "robots_preflight_blocked"
    else:
        ayristirici = urllib.robotparser.RobotFileParser()
        ayristirici.set_url(origin + "/robots.txt")
        ayristirici.parse(robots.body.decode("utf-8", "replace").splitlines()
                          if durum == "policy" else [])
        runtime.robots_parser = ayristirici
        if not ayristirici.can_fetch(USER_AGENT, url):
            temel["erisim"] = "robots_disallowed"
        else:
            beklenen_tip = "json" if ("/api/" in url or url.startswith(
                f"{parcalar.scheme}://api.")) else "html"
            cikti = runtime.fetch("as02", "as02_yeniden", url, beklenen_tip,
                                  robots_decision="required")
            islem = runtime.transactions[-1] if runtime.transactions else None
            temel["http_durum"] = str(islem.status) if islem and islem.status else ""
            if not cikti.ok:
                temel["erisim"] = cikti.stop_reason or cikti.outcome
            else:
                temel["erisim"] = "ok"
                ozet = hashlib.sha256(cikti.body).hexdigest()
                dosya = HERE / "results" / "raw" / f"{ozet}.bin"
                dosya.parent.mkdir(parents=True, exist_ok=True)
                if not dosya.exists():
                    dosya.write_bytes(cikti.body)
                temel["artefakt"] = ozet
                temel["artefakt_dosya"] = f"results/raw/{ozet}.bin"

                govde = cikti.body[:400_000]
                mime = ("application/json" if govde[:1] in (b"{", b"[")
                        else "text/html")
                cikarim = nb.metin_cikar(govde, mime)
                metin = cikarim["metin"]
                temel["icerik"], _g = ve.icerik_durumu("as02_yeniden", mime, govde)
                temel["metin_uzunlugu"] = len(metin)
                temel["dil"] = nb.dil_tespit(metin)[0]
                bulunan = {b["alan"] for sinif in ("urun", "teknik", "kamu")
                           for b in nb.alan_cikar(sinif, metin, "")}
                temel["bulunan_alanlar"] = ", ".join(sorted(bulunan))
                ilgili = _ilgili_mi(metin, bildirim.get("sorgu_metni", ""))
                temel["ilgili_mi"] = "" if ilgili is None else ("evet" if ilgili else "hayir")

    bulunan_kume = {a.strip() for a in temel["bulunan_alanlar"].split(",") if a.strip()}
    ilgili_deger = {"evet": True, "hayir": False, "": None}[temel["ilgili_mi"]]
    sinif, gerekce = sorunu_ayir(
        temel["erisim"], temel["icerik"], "", ilgili_deger,
        bulunan_kume, beklenen_alanlar, temel["dil"], hedef_dil)
    return {**temel, "asama": asama, "sorun_sinifi": sinif, "gerekce": gerekce}


def kos(asama: str) -> list[dict[str, Any]]:
    """Bildirim dosyasindaki her satiri yeniden uretir."""
    import datetime

    bugun = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    bildirimler = _oku(BILDIRIM_DOSYASI)
    onceki = {r["fb_id"]: r for r in _oku(SONUC_DOSYASI) if r["asama"] == "once"}

    satirlar: list[dict[str, Any]] = []
    for bildirim in bildirimler:
        if not bildirim.get("denenen_url", "").strip():
            continue
        sonuc = bir_bildirimi_kos(bildirim, asama)
        eski = onceki.get(bildirim["fb_id"], {}) if asama == "sonra" else {}
        satirlar.append({
            "fb_id": bildirim["fb_id"],
            "fikir": bildirim.get("fikir", ""),
            "source_id": bildirim.get("source_id", ""),
            "denenen_url": bildirim["denenen_url"],
            "sorgu_metni": bildirim.get("sorgu_metni", ""),
            "asama": asama,
            "kosu_tarihi": bugun,
            "script_surumu": f"yeniden_uret.py {SURUM}",
            "beklenen": bildirim.get("beklenen", ""),
            "batuhan_gozlemi": bildirim.get("batuhan_gozlemi", ""),
            **{k: v for k, v in sonuc.items() if k != "asama"},
            # once/sonra karsilastirmasi yalniz 'sonra' asamasinda anlamli
            "once_erisim": eski.get("erisim", ""),
            "once_icerik": eski.get("icerik", ""),
            "once_alanlar": eski.get("bulunan_alanlar", ""),
            "once_artefakt": eski.get("artefakt", ""),
            "degisim": _degisim(eski, sonuc) if asama == "sonra" else "",
            "kalan_sinirlilik": "",
            "batuhan_yeniden_kontrolu": "bekliyor",
        })
    return satirlar


def _degisim(once: dict[str, Any], sonra: dict[str, Any]) -> str:
    if not once:
        return "önce kaydı yok — --asama once ile koşulmamış"
    if once.get("sorun_sinifi") == sonra["sorun_sinifi"]:
        return f'DEĞİŞMEDİ — hâlâ {sonra["sorun_sinifi"]}'
    if sonra["sorun_sinifi"] == "sorun-yok":
        return f'düzeldi — önce {once.get("sorun_sinifi")}, şimdi sorun görülmüyor'
    return f'değişti — önce {once.get("sorun_sinifi")}, şimdi {sonra["sorun_sinifi"]}'


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--asama", choices=("once", "sonra"), default="once",
                             help="once: bozuk hali kaydet · sonra: düzeltme sonrası")
    ayristirici.add_argument("--yaz", action="store_true")
    secenek = ayristirici.parse_args(argv)

    import collections

    yol = bildirim_sablonu_yaz()
    bildirimler = [r for r in _oku(BILDIRIM_DOSYASI)
                   if r.get("denenen_url", "").strip()]
    if not bildirimler:
        print(json.dumps({
            "surum": SURUM, "bildirim": 0,
            "durum": "Batuhan'dan hata bildirimi bekleniyor",
            "sablon": str(yol.relative_to(HERE)),
            "nasil": f"{BILDIRIM_DOSYASI} dosyasına bildirim satırı eklenince "
                     "`python3 yeniden_uret.py --asama once --yaz` koşulur",
        }, ensure_ascii=False, indent=2))
        return 0

    satirlar = kos(secenek.asama)
    print(json.dumps({
        "surum": SURUM, "asama": secenek.asama, "bildirim": len(satirlar),
        "sorun_siniflari": dict(collections.Counter(
            r["sorun_sinifi"] for r in satirlar)),
    }, ensure_ascii=False, indent=2))
    if secenek.yaz:
        mevcut = [r for r in _oku(SONUC_DOSYASI)
                  if not (r["asama"] == secenek.asama
                          and r["fb_id"] in {s["fb_id"] for s in satirlar})]
        _yaz(SONUC_DOSYASI, mevcut + satirlar)
        print(SONUC_DOSYASI)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
