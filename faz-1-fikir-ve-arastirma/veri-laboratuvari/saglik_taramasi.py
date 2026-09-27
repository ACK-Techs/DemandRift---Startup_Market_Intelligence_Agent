"""BT-02 icin aday kaynak listesi: saglik kaydini canli olarak genisletir.

Batuhan'in BT02-AS01-KONTROL kaydindaki kabul kurali:

    Bir kaynak ancak su iki kosul BIRLIKTE saglaniyorsa ilk deneme adayidir:
    1. Son saglik kaydi `saglikli` olmali.
    2. Icerik turu `gercek-icerik` ya da `api-yaniti` olmali; sitemap, arsiv,
       snippet/adres kesfi ve JS kabugu kanit sayilmaz.

Ikinci kosulu 315 kaynak sagliyor ama birincisi icin yalniz 19 kaynakta canli
olcum vardi. Batuhan'in acikca belirttigi eksik buydu: "BT-02'nin ilk canli
denemesinde her secili kaynak icin yeni kosu, tarih ve ham artefakt kaydi
zorunludur."

Bu modul o bosluğu kapatir: icerik turu uygun olan her kaynagin **en son
basariyla cekilen adresini** bugun yeniden yoklar ve saglik kaydini tazeler.

Yoklama kaynagin ana sayfasini degil, daha once icerik veren yuzeyi dener;
boylece "bu kaynak calisiyor mu" sorusu kayitla ayni sey uzerinden sorulur.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import urllib.parse
import urllib.robotparser
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SURUM = "1.0.0"
UYGUN_ICERIK = ("gercek-icerik", "api-yaniti")
# Ana sayfa ve adres listesi kanit uretmedigi icin yoklamada tercih edilmez.
YUZEY_ONCELIGI = ("ic_sayfa", "entry_url", "api", "as01_yoklama",
                  "alternatif_deneme", "rss_feed", "root_html")


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


def hedefleri_sec() -> list[dict[str, str]]:
    """Icerik turu uygun her kaynagin en iyi yoklanabilir adresi."""
    envanter = {r["source_id"]: r for r in _oku("VERI-ENVANTERI.csv")}
    dizin = _oku("ARTEFAKT-DIZINI.csv") + _oku("EK-ARTEFAKT-DIZINI.csv")
    en_iyi: dict[str, tuple[int, str, str]] = {}
    for kayit in dizin:
        sid = kayit.get("source_id", "")
        if kayit["sonuc"] != "ok" or not sid:
            continue
        kaynak = envanter.get(sid)
        if not kaynak or kaynak["icerik_durumu"] not in UYGUN_ICERIK:
            continue
        yontem = kayit["yontem"]
        if yontem not in YUZEY_ONCELIGI:
            continue
        sira = YUZEY_ONCELIGI.index(yontem)
        mevcut = en_iyi.get(sid)
        if mevcut is None or sira < mevcut[0]:
            en_iyi[sid] = (sira, kayit["cekilen_url"], yontem)

    hedefler = []
    for sid, (_sira, url, yontem) in sorted(en_iyi.items()):
        parcalar = urllib.parse.urlsplit(url)
        if not parcalar.netloc:
            continue
        hedefler.append({
            "source_id": sid,
            "kaynak_adi": envanter[sid]["ad"],
            "kayitli_icerik": envanter[sid]["icerik_durumu"],
            "yoklanan_url": url,
            "yontem": yontem,
            "origin": f"{parcalar.scheme}://{parcalar.netloc}",
        })
    return hedefler


def _redakte_ozetler() -> set[str]:
    """Redakte edilmis kopyalarin ORIJINAL ozetleri; uzerine yazilmaz."""
    yol = HERE / "results" / "shared-redactions.json"
    if not yol.exists():
        return set()
    veri = json.loads(yol.read_text(encoding="utf-8"))
    return {k["original_sha256"] for k in veri["files"]}


def yokla(hedefler: list[dict[str, str]], canli: bool) -> list[dict[str, Any]]:
    import datetime

    bugun = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    if not canli:
        return [{**h, "bugun_erisim": "not_run", "bugun_icerik": "not_run",
                 "saglik": "not_run", "metin_uzunlugu": 0, "artefakt": "",
                 "olcum_tarihi": bugun, "bt02_adayi": "hayır",
                 "sebep": "canlı koşu yapılmadı"} for h in hedefler]

    import tempfile

    import normalize_belgeler as nb
    import veri_envanteri as ve
    from bulk_site_access_lab import (ROBOTS_BLOCKED, OriginRuntime,
                                      USER_AGENT, robots_state)

    gecici_dizin = Path(tempfile.mkdtemp(prefix="bt02-saglik-"))
    redakte = _redakte_ozetler()

    origin_bazinda: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for h in hedefler:
        origin_bazinda[h["origin"]].append(h)

    satirlar: list[dict[str, Any]] = []
    for sira, origin in enumerate(sorted(origin_bazinda), 1):
        grup = origin_bazinda[origin]
        # raw_dir VERILMEZ: artefakti kendimiz yaziyoruz. Runtime icerik-adresli
        # yazarken "bu adda dosya var ama hash tutmuyor" diye duruyor ve
        # redakte edilmis kopyalar tam olarak boyle: dosya adi ORIJINAL
        # sha256'yi koruyor, baytlar temizlenmis hali. Iki sozlesme burada
        # carpisiyor; saklamayi biz yonetince sorun kalmiyor.
        runtime = OriginRuntime(origin, lease=len(grup) + 2, live=True,
                                raw_dir=gecici_dizin)
        robots = runtime.fetch(grup[0]["source_id"], "robots_preflight",
                               origin + "/robots.txt", "robots",
                               robots_decision="not_required")
        durum = robots_state(robots)
        ayristirici = None
        if durum != ROBOTS_BLOCKED:
            ayristirici = urllib.robotparser.RobotFileParser()
            ayristirici.set_url(origin + "/robots.txt")
            ayristirici.parse(robots.body.decode("utf-8", "replace").splitlines()
                              if durum == "policy" else [])
            runtime.robots_parser = ayristirici

        for h in grup:
            temel = {**h, "olcum_tarihi": bugun, "artefakt": "",
                     "metin_uzunlugu": 0}
            if durum == ROBOTS_BLOCKED:
                satirlar.append({**temel, "bugun_erisim": "robots_preflight_blocked",
                                 "bugun_icerik": "alinmadi", "saglik": "politika-kapali",
                                 "bt02_adayi": "hayır",
                                 "sebep": "robots.txt 401/403 — tam yasak"})
                continue
            if not ayristirici.can_fetch(USER_AGENT, h["yoklanan_url"]):
                satirlar.append({**temel, "bugun_erisim": "robots_disallowed",
                                 "bugun_icerik": "alinmadi", "saglik": "politika-kapali",
                                 "bt02_adayi": "hayır",
                                 "sebep": "robots.txt bu yolu yasaklıyor"})
                continue
            beklenen = "json" if (h["yontem"] == "api"
                                  or "/api/" in h["yoklanan_url"]) else "html"
            cikti = runtime.fetch(h["source_id"], "bt02_saglik", h["yoklanan_url"],
                                  beklenen, robots_decision="required")
            if not cikti.ok:
                sebep = cikti.stop_reason or cikti.outcome
                saglik = ("bot-korumasi" if sebep in ("challenge", "origin_circuit_open")
                          else "hiz-siniri" if sebep == "rate_limited"
                          else "adres-hatasi")
                satirlar.append({**temel, "bugun_erisim": sebep,
                                 "bugun_icerik": "alinmadi", "saglik": saglik,
                                 "bt02_adayi": "hayır", "sebep": f"istek başarısız: {sebep}"})
                continue
            govde = cikti.body[:400_000]
            mime = "application/json" if govde[:1] in (b"{", b"[") else "text/html"
            icerik, _g = ve.icerik_durumu("bt02_saglik", mime, govde)
            metin = nb.metin_cikar(govde, mime)["metin"]
            ozet = hashlib.sha256(cikti.body).hexdigest()
            dosya = HERE / "results" / "raw" / f"{ozet}.bin"
            dosya.parent.mkdir(parents=True, exist_ok=True)
            if not dosya.exists():
                dosya.write_bytes(cikti.body)
            elif ozet in redakte:
                # Bu ad altinda redakte edilmis kopya duruyor; uzerine
                # yazilmaz, cunku paylasilan bayt bilerek farkli.
                pass
            uygun = icerik in UYGUN_ICERIK
            satirlar.append({
                **temel, "bugun_erisim": "ok", "bugun_icerik": icerik,
                "saglik": "saglikli" if uygun else "icerik-yetersiz",
                "metin_uzunlugu": len(metin), "artefakt": ozet,
                "bt02_adayi": "evet" if uygun else "hayır",
                "sebep": ("sağlıklı ve içerik üretiyor" if uygun
                          else f"içerik türü uygun değil: {icerik}"),
            })
        if sira % 40 == 0:
            print(f"  ... {sira}/{len(origin_bazinda)} origin", flush=True)
    return satirlar


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--yaz", action="store_true")
    ayristirici.add_argument("--canli", action="store_true")
    ayristirici.add_argument("--sinir", type=int, default=0,
                             help="kaç kaynak yoklanacak (0 = hepsi)")
    secenek = ayristirici.parse_args(argv)

    hedefler = hedefleri_sec()
    if secenek.sinir:
        hedefler = hedefler[:secenek.sinir]
    satirlar = yokla(hedefler, secenek.canli)
    aday = [r for r in satirlar if r["bt02_adayi"] == "evet"]
    print(json.dumps({
        "surum": SURUM, "hedef": len(hedefler), "canli": secenek.canli,
        "bt02_adayi": len(aday),
        "saglik": dict(collections.Counter(r["saglik"] for r in satirlar)),
    }, ensure_ascii=False, indent=2))
    if secenek.yaz:
        _yaz("BT02-ADAY-KAYNAKLAR.csv", satirlar)
        print("BT02-ADAY-KAYNAKLAR.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
