"""Ic sayfa gecisi: elimizdeki adreslerden kanit tasiyan sayfalari ceker.

DR-L03 olctu: 591 belgenin yalnizca 42'si olcum kaniti uretiyor. Kanit
uretmeyen 549 belgenin **350'si ana sayfa**. Sebep engellenme degil; erisim
laboratuvari kaynak basina birkac istek atacak sekilde kurulmustu
(``SURFACE_REQUESTS_PER_SOURCE``) cunku cevapladigi soru "ulasabiliyor
muyuz" idi. Ana sayfada fiyat da yorum da yoktur.

Bu gecis o eksigi kapatir ve **hicbir yeni kesif istegi atmaz**: aday
adresler zaten diskte duran dosyalardan okunur.

* indirilmis sitemap'lerdeki ``<loc>`` adresleri
* indirilmis ana sayfalardaki ayni-origin ``href`` baglantilari

Her aday bir **arama niyetine** baglanir (Faz2-Plan.md). Niyeti olmayan
adres alinmaz: hedef daha cok sayfa degil, cevabi olan sayfa.

``stated_wtp_weak_signal`` icin URL deseni **yoktur** ve uydurulmaz. O sinyal
sayfanin adresinden degil metninden okunur; buradaki ``problem_demand``
yuzeylerinden gelir ve beyan olarak isaretlenir.

Canli cekim ``bulk_site_access_lab.run_lab`` uzerinden yapilir: robots
kontrolu, cikis guvenligi, istek butcesi ve sha256 artefakt saklama tek
yerdedir ve burada tekrarlanmaz.
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

# Faz2-Plan.md'nin arama niyetleri. Desenler URL YOLUNA bakar, tam metne degil.
NIYET_DESENLERI: dict[str, re.Pattern[str]] = {
    # Ilan ve menu sayfalari fiyat tasir: bir emlak ilani ya da restoran menusu
    # gozlemlenmis piyasa fiyatidir. Ilk desen kumesi yalniz Anglo-SaaS
    # kaliplariydi (/pricing, /plans) ve gayrimenkul kategorisinde 0/7 verdi;
    # o sitelerin yolu /ilan, /satilik-konut, /for_rent seklinde.
    "observed_market_pricing": re.compile(
        r"(?i)(^|/)(pricing|prices?|plans?|fiyat(lar)?|fiyatlandirma|abonelik|subscription"
        r"|ilan(lar)?|satilik[\w-]*|kiralik[\w-]*|for[-_]rent|for[-_]sale|menu(ler)?)(/|$)"),
    "dissatisfaction": re.compile(
        r"(?i)(^|/)(reviews?|yorum(lar)?|complaints?|sikayet|ratings?|feedback)(/|$)"),
    "existing_alternatives": re.compile(
        r"(?i)(^|/)(alternatives?|alternatif(ler)?|compare|comparison|versus|vs"
        r"|danismanlar|professionals?|for-pros|uzmanlar|firmalar|isletmeler)(/|$)"),
    "competitor_discovery": re.compile(
        r"(?i)(^|/)(categor(y|ies)|kategori(ler)?|browse|directory|catalog(ue)?|listings?"
        r"|marketplace|products?|urunler|apps?|extensions?|integrations?)(/|$)"),
    "use_case": re.compile(
        r"(?i)(^|/)(use-?cases?|solutions?|customers?|case-stud(y|ies)|kullanim|musteri(ler)?)(/|$)"),
    "problem_demand": re.compile(
        r"(?i)(^|/)(questions?|forum(lar)?|discussions?|community|topics?|ask|sorular?"
        r"|piyasa[\w-]*|[\w-]*-piyasasi|market-(report|insight|trend)s?)(/|$)"),
}

# URL'den okunamayan niyet. Boyle isaretlenir ki matriste "desen yok" ile
# "kanit yok" birbirine karismasin.
URLDEN_OKUNMAYAN = {
    "stated_wtp_weak_signal":
        "beyan sinyali sayfanin adresinden degil metninden okunur; "
        "problem_demand yuzeylerinden toplanir",
}

# Alinmayacak yollar: kanit tasimazlar, istek harcarlar.
ELEME = re.compile(
    r"(?i)(^|/)(login|signin|sign-?up|register|account|cart|checkout|privacy|terms|"
    r"legal|cookie|careers?|jobs?|press|investors?|rss|feed|sitemap|wp-admin|"
    r"wp-content|static|assets)(/|$)|\.(png|jpe?g|gif|svg|css|js|pdf|zip|xml)$")

AZAMI_YOL_DERINLIGI = 4
IZLENEN_YONTEMLER = ("root_html", "entry_url")


def _oku(ad: str) -> list[dict[str, str]]:
    with (HERE / ad).open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def niyet_ata(url: str) -> str | None:
    """Adresin yolundan arama niyetini okur. Eslesmezse None."""
    yol = urllib.parse.urlsplit(url).path
    if not yol or ELEME.search(yol):
        return None
    if yol.strip("/").count("/") + 1 > AZAMI_YOL_DERINLIGI:
        return None
    for niyet, desen in NIYET_DESENLERI.items():
        if desen.search(yol):
            return niyet
    return None


def _puan(url: str) -> tuple[int, int, str]:
    """Kucuk puan once secilir.

    Bolum sayfasi (``/pricing``) tekil bir ic sayfadan (``/pricing/enterprise
    /2026/detay``) daha iyi bir kanit yuzeyidir: fiyat tablosunun tamami
    oradadir. Sorgu parametresi tasiyan adres en sona birakilir.
    """
    parcalar = urllib.parse.urlsplit(url)
    derinlik = len([p for p in parcalar.path.split("/") if p])
    return (1 if parcalar.query else 0, derinlik, url)


def adaylari_topla(azami_dosya_bayt: int = 2_000_000) -> dict[str, dict[str, list[str]]]:
    """source_id -> niyet -> aday URL listesi. **Ag istegi atmaz.**"""
    # Bos govdeli "ok" yanitlar da vardir (200 ama sifir bayt); bunlarin
    # dosya yolu bostur ve okunmaya calisilirsa dizin acilmis olur.
    dizin = [r for r in _oku("ARTEFAKT-DIZINI.csv") + ek_dizin_oku()
             if r["sonuc"] == "ok" and r["saklama"] != "kosu_json_icinde"
             and r["dosya"].strip()]
    havuz: dict[str, dict[str, set[str]]] = collections.defaultdict(
        lambda: collections.defaultdict(set))

    for kayit in dizin:
        yol = HERE / kayit["dosya"]
        if not yol.exists():
            continue
        sid, yontem = kayit.get("source_id", ""), kayit["yontem"]
        if not sid:
            continue
        if yontem == "sitemap_xml":
            ham = yol.read_bytes()[:azami_dosya_bayt].decode("utf-8", "replace")
            adresler = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", ham)
        elif yontem in IZLENEN_YONTEMLER:
            ham = yol.read_bytes()[:400_000].decode("utf-8", "replace")
            taban = kayit["cekilen_url"]
            taban_host = urllib.parse.urlsplit(taban).netloc
            adresler = []
            for parca in re.findall(r"href=[\"']([^\"'#]+)", ham):
                try:
                    tam = urllib.parse.urljoin(taban, parca)
                except ValueError:
                    continue
                if urllib.parse.urlsplit(tam).netloc == taban_host:
                    adresler.append(tam)
        else:
            continue
        for url in adresler:
            if not url.startswith(("http://", "https://")):
                continue
            niyet = niyet_ata(url)
            if niyet:
                havuz[sid][niyet].add(url.split("#")[0])

    return {sid: {n: sorted(u, key=_puan) for n, u in niyetler.items()}
            for sid, niyetler in havuz.items()}


def hedefleri_sec(havuz: dict[str, dict[str, list[str]]], kaynak_sayisi: int,
                  niyet_basina: int) -> list[dict[str, Any]]:
    """Kapsam derinlikten once gelir: cok kaynaktan az sayfa.

    Kaynaklar **kapsadiklari niyet sayisina** gore siralanir; esitlik
    source_id ile bozulur, boylece ayni girdi ayni secimi verir.
    """
    envanter = {r["source_id"]: r for r in _oku("VERI-ENVANTERI.csv")}
    sirali = sorted(havuz.items(), key=lambda t: (-len(t[1]), t[0]))
    hedefler: list[dict[str, Any]] = []
    for sid, niyetler in sirali[:kaynak_sayisi]:
        kayit = envanter.get(sid)
        if not kayit:
            continue
        for niyet in sorted(niyetler):
            for url in niyetler[niyet][:niyet_basina]:
                parcalar = urllib.parse.urlsplit(url)
                hedefler.append({
                    "source_id": sid,
                    "ad": kayit["ad"],
                    "niyet": niyet,
                    "url": url,
                    "origin": f"{parcalar.scheme}://{parcalar.netloc}",
                    "entry_path": urllib.parse.urlunsplit(
                        ("", "", parcalar.path, parcalar.query, "")),
                })
    return hedefler


# --------------------------------------------------------------------------
# Canli cekim
# --------------------------------------------------------------------------
EK_DIZIN = "EK-ARTEFAKT-DIZINI.csv"
EK_SUTUNLAR = ("source_id", "ad", "adres", "yontem", "niyet", "cekilen_url",
               "mime", "sha256", "saklama", "dosya", "bayt", "sonuc", "kosu", "tarih")


def ek_dizin_oku() -> list[dict[str, str]]:
    yol = HERE / EK_DIZIN
    if not yol.exists():
        return []
    with yol.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _cek(hedefler: list[dict[str, Any]], *, kosu: str, canli: bool,
         origin_butcesi: int) -> list[dict[str, Any]]:
    """Origin basina sirali, robots'a tabi cekim.

    Ag kodu burada yazilmaz: ``bulk_site_access_lab.OriginRuntime`` kullanilir,
    yani cikis guvenligi, istek araligi, yonlendirme siniri ve sha256 artefakt
    saklama tek yerde kalir. ``run_lab`` yerine dogrudan OriginRuntime
    kullanilmasinin sebebi yuzey plani: run_lab her kaynak icin sitemap ve
    beslemeleri de ceker, bunlar elimizde zaten var ve istegin bes katina
    cikmasi sitelere gereksiz yuktur.

    Her satir ``EK-ARTEFAKT-DIZINI.csv``'ye yazilir; ana dizin
    (``ARTEFAKT-DIZINI.csv``) bir baska betigin ciktisidir ve elle duzenlenmez.
    """
    import base64
    import urllib.robotparser

    from bulk_site_access_lab import (RESULTS_DIR, ROBOTS_BLOCKED, OriginRuntime,
                                      atomic_write_bytes, robots_state, utc_now)

    ham_dizin = RESULTS_DIR / "raw"

    def govdeyi_sakla(islem: Any) -> str:
        """16 KB alti yanitlar diske degil kosu JSON'una base64 yazilir
        (``MAX_INLINE_ARTIFACT_BYTES``). DR-L01'in "govdesi saklanmamis"
        dedigi 137 sitemap tam olarak bu yuzden dosyasizdi. Burada govde
        icerik-adresli dosyaya yazilir ki sonraki adimlar okuyabilsin."""
        if not islem or not islem.sha256:
            return ""
        hedef = ham_dizin / f"{islem.sha256}.bin"
        if not hedef.exists() and islem.inline_body_base64:
            atomic_write_bytes(hedef, base64.b64decode(islem.inline_body_base64),
                               islem.sha256)
        return islem.sha256 if hedef.exists() else ""

    origin_bazinda: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for hedef in hedefler:
        origin_bazinda[hedef["origin"]].append(hedef)

    satirlar: list[dict[str, Any]] = []
    for sira, origin in enumerate(sorted(origin_bazinda), 1):
        grup = origin_bazinda[origin]
        runtime = OriginRuntime(origin, lease=origin_butcesi, live=canli,
                                raw_dir=RESULTS_DIR / "raw")
        islemler: list[Any] = []
        runtime.transaction_callback = islemler.append

        # robots.txt her origin icin ONCE. RFC 9309: 404/410 kisit yok,
        # 401/403 tam yasak. Yasakli origin'e tek istek atilmaz.
        robots = runtime.fetch(grup[0]["source_id"], "robots_preflight",
                               origin + "/robots.txt", "robots",
                               robots_decision="not_required")
        durum = robots_state(robots)
        if durum != ROBOTS_BLOCKED:
            ayristirici = urllib.robotparser.RobotFileParser()
            ayristirici.set_url(origin + "/robots.txt")
            ayristirici.parse(robots.body.decode("utf-8", "replace").splitlines()
                              if durum == "policy" else [])
            runtime.robots_parser = ayristirici

        for hedef in grup:
            ortak = {
                "source_id": hedef["source_id"], "ad": hedef["ad"],
                "adres": origin, "yontem": hedef["yontem"],
                "niyet": hedef.get("niyet", ""), "cekilen_url": hedef["url"],
                "kosu": kosu, "tarih": utc_now(),
            }
            if durum == ROBOTS_BLOCKED:
                satirlar.append({**ortak, "mime": "", "sha256": "", "saklama": "",
                                 "dosya": "", "bayt": 0,
                                 "sonuc": "robots_preflight_blocked"})
                continue
            onceki = len(islemler)
            cikti = runtime.fetch(hedef["source_id"], hedef["yontem"], hedef["url"],
                                  hedef.get("beklenen", "html"),
                                  robots_decision="required")
            islem = islemler[onceki] if len(islemler) > onceki else None
            hash_ = govdeyi_sakla(islem)
            satirlar.append({
                **ortak,
                "mime": (islem.mime or "") if islem else "",
                "sha256": hash_,
                "saklama": "ham_dosya" if hash_ else "",
                "dosya": f"results/raw/{hash_}.bin" if hash_ else "",
                "bayt": (islem.decoded_bytes if islem else 0),
                "sonuc": ("ok" if hash_ else "bos_govde") if cikti.ok
                         else (cikti.stop_reason or cikti.outcome),
            })
        if sira % 25 == 0:
            print(f"  ... {sira}/{len(origin_bazinda)} origin", flush=True)

    mevcut = ek_dizin_oku()
    _yaz(HERE / EK_DIZIN, mevcut + [{k: r.get(k, "") for k in EK_SUTUNLAR}
                                    for r in satirlar])
    return satirlar


def sitemap_hedefleri() -> list[dict[str, Any]]:
    """Cekilmis ama govdesi saklanmamis sitemap'ler.

    Bu istekler bir kez basariyla atilmis; yalnizca yanit diske yazilmamis.
    Tek istekle geri gelirler ve aday havuzunu genisletirler.
    """
    zaten = {r["cekilen_url"] for r in ek_dizin_oku() if r["sonuc"] == "ok"}
    hedefler: list[dict[str, Any]] = []
    for kayit in _oku("ARTEFAKT-DIZINI.csv"):
        if (kayit["yontem"] != "sitemap_xml" or kayit["sonuc"] != "ok"
                or kayit["saklama"] != "kosu_json_icinde"
                or kayit["cekilen_url"] in zaten):
            continue
        parcalar = urllib.parse.urlsplit(kayit["cekilen_url"])
        hedefler.append({
            "source_id": kayit["source_id"], "ad": kayit["ad"],
            "yontem": "sitemap_xml", "beklenen": "xml",
            "url": kayit["cekilen_url"],
            "origin": f"{parcalar.scheme}://{parcalar.netloc}",
        })
    return hedefler


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--kaynak", type=int, default=20,
                             help="Kac kaynaktan cekilecek")
    ayristirici.add_argument("--niyet-basina", type=int, default=1,
                             help="Kaynak basina her niyetten kac sayfa")
    ayristirici.add_argument("--origin-butcesi", type=int, default=12)
    ayristirici.add_argument("--canli", action="store_true",
                             help="Verilmezse yalniz aday havuzu cikarilir; ag istegi atilmaz")
    secenek = ayristirici.parse_args(argv)

    havuz = adaylari_topla()
    hedefler = hedefleri_sec(havuz, secenek.kaynak, secenek.niyet_basina)

    _yaz(HERE / "IC-SAYFA-ADAYLARI.csv", [
        {"source_id": s, "niyet": n, "aday_sayisi": len(u), "en_iyi_aday": u[0]}
        for s, niyetler in sorted(havuz.items())
        for n, u in sorted(niyetler.items())])

    ozet = {
        "aday_tasiyan_kaynak": len(havuz),
        "toplam_aday_adres": sum(len(u) for n in havuz.values() for u in n.values()),
        "urlden_okunmayan_niyet": sorted(URLDEN_OKUNMAYAN),
        "secilen_hedef": len(hedefler),
        "secilen_kaynak": len({h["source_id"] for h in hedefler}),
        "canli": secenek.canli,
    }
    print(json.dumps(ozet, ensure_ascii=False, indent=2), flush=True)
    if not secenek.canli:
        _yaz(HERE / "IC-SAYFA-HEDEFLERI.csv", hedefler)
        return 0

    sonuclar = _calis(hedefler, canli=True, origin_butcesi=secenek.origin_butcesi)
    _yaz(HERE / "IC-SAYFA-SONUCLARI.csv", sonuclar)
    basarili = [s for s in sonuclar if s["sonuc"] == "ok"]
    print(json.dumps({
        "istek": len(sonuclar),
        "basarili": len(basarili),
        "niyet_bazinda_basarili": dict(collections.Counter(
            s["niyet"] for s in basarili)),
        "basarisizlik_sebepleri": dict(collections.Counter(
            f'{s["sonuc"]}:{s["sebep"]}' for s in sonuclar if s["sonuc"] != "ok")),
    }, ensure_ascii=False, indent=2))
    return 0


def _yaz(yol: Path, satirlar: list[dict[str, Any]]) -> None:
    if not satirlar:
        return
    with yol.open("w", newline="", encoding="utf-8") as handle:
        yazici = csv.DictWriter(handle, fieldnames=list(satirlar[0]))
        yazici.writeheader()
        yazici.writerows(satirlar)


if __name__ == "__main__":
    raise SystemExit(main())


# Alt sitemap secimi: indeks dosyasi sayfa degil, baska sitemap'lere isaret
# eder. Hepsi cekilemez (108 indeksin altinda 2.291 dosya var); urun/kategori
# tasiyan olanlar tercih edilir, haber arsivi geri birakilir.
ALT_TERCIH = re.compile(
    r"(?i)(product|app|categor|listing|static|main|page|item|shop|urun|kategori)")
ALT_GERI = re.compile(r"(?i)(news|post|article|tag|author|archive|blog|/20\d\d)")


def alt_sitemap_hedefleri(kaynak_basina: int = 3) -> list[dict[str, Any]]:
    """Indeks dosyalarinin isaret ettigi alt sitemap'ler."""
    zaten = {r["cekilen_url"] for r in ek_dizin_oku()}
    hedefler: list[dict[str, Any]] = []
    for kayit in ek_dizin_oku():
        if kayit["sonuc"] != "ok" or kayit["yontem"] != "sitemap_xml":
            continue
        yol = HERE / kayit["dosya"]
        if not yol.exists():
            continue
        ham = yol.read_bytes().decode("utf-8", "replace")
        if re.search(r"(?is)<url>\s*<loc>", ham):
            continue                      # zaten sayfa adresi tasiyor
        cocuklar = re.findall(r"(?is)<sitemap>.*?<loc>\s*([^<]+?)\s*</loc>", ham)
        cocuklar = [c for c in cocuklar
                    if c.startswith(("http://", "https://")) and c not in zaten
                    and not c.endswith(".gz")]
        cocuklar.sort(key=lambda u: (bool(ALT_GERI.search(u)),
                                     not bool(ALT_TERCIH.search(u)), len(u), u))
        for cocuk in cocuklar[:kaynak_basina]:
            parcalar = urllib.parse.urlsplit(cocuk)
            hedefler.append({
                "source_id": kayit["source_id"], "ad": kayit["ad"],
                "yontem": "sitemap_xml", "beklenen": "xml", "url": cocuk,
                "origin": f"{parcalar.scheme}://{parcalar.netloc}",
            })
    return hedefler


# Bilinen yol yoklamasi: bagi gorulmemis ama yaygin olan yollar denenir.
# Adres uydurmak degildir - web'de yerlesmis kaliplar sinanir ve 404 donerse
# "bu kaynakta bu yuzey yok" diye kaydedilir. robots yine zorunludur.
BILINEN_YOLLAR: dict[str, tuple[str, ...]] = {
    "observed_market_pricing": ("/pricing", "/plans", "/fiyatlar"),
    "dissatisfaction": ("/reviews", "/yorumlar"),
    "existing_alternatives": ("/alternatives", "/compare"),
    "competitor_discovery": ("/categories", "/browse", "/products"),
    "use_case": ("/use-cases", "/solutions", "/customers"),
    "problem_demand": ("/community", "/forum", "/questions"),
}


def bos_hucreler() -> list[tuple[str, str]]:
    """(kategori, niyet) — aday adresi hic olmayan hucreler.

    ``stated_wtp_weak_signal`` disaridadir: o niyet sayfanin adresinden
    okunamaz, bu yuzden yoklamayla da doldurulamaz.
    """
    havuz = adaylari_topla()
    env = {r["source_id"]: r for r in _oku("VERI-ENVANTERI.csv")}
    ad_kimlik = {r["ad"]: r["source_id"] for r in env.values()}
    kapsanan: dict[str, set[str]] = collections.defaultdict(set)
    kategoriler: set[str] = set()
    for satir in _oku("KATEGORI-KAYNAK.csv"):
        kategoriler.add(satir["hedef"])
        sid = ad_kimlik.get(satir["kaynak"])
        if sid in havuz:
            kapsanan[satir["hedef"]] |= set(havuz[sid])
    return [(k, n) for k in sorted(kategoriler) for n in sorted(NIYET_DESENLERI)
            if n not in kapsanan.get(k, set())]


def yoklama_hedefleri(yol_basina: int = 2,
                      hucre_basina_kaynak: int = 8) -> list[dict[str, Any]]:
    """Bos hucrelerin kategorilerindeki, aday tasimayan kaynaklari yoklar.

    Bir hucreyi doldurmak icin o kategorideki her kaynagi yoklamak gerekmez;
    ``hucre_basina_kaynak`` kadari denenir. Amac kanit bulmak, siteleri
    taramak degil.
    """
    havuz = adaylari_topla()
    env = {r["source_id"]: r for r in _oku("VERI-ENVANTERI.csv")}
    ad_kimlik = {r["ad"]: r["source_id"] for r in env.values()}
    kategori_kaynak: dict[str, set[str]] = collections.defaultdict(set)
    for satir in _oku("KATEGORI-KAYNAK.csv"):
        sid = ad_kimlik.get(satir["kaynak"])
        if sid:
            kategori_kaynak[satir["hedef"]].add(sid)

    zaten = {r["cekilen_url"] for r in ek_dizin_oku()}
    gorulen: set[tuple[str, str]] = set()
    hedefler: list[dict[str, Any]] = []
    for kategori, niyet in bos_hucreler():
        denenen = 0
        for sid in sorted(kategori_kaynak.get(kategori, set())):
            if denenen >= hucre_basina_kaynak:
                break
            if (sid, niyet) in gorulen or niyet in havuz.get(sid, {}):
                continue
            kayit = env.get(sid)
            if not kayit or not kayit["adres"].strip():
                continue
            gorulen.add((sid, niyet))
            denenen += 1
            parcalar = urllib.parse.urlsplit(kayit["adres"])
            origin = f"{parcalar.scheme or 'https'}://{parcalar.netloc or parcalar.path}"
            for yol in BILINEN_YOLLAR[niyet][:yol_basina]:
                if origin + yol in zaten:
                    continue
                hedefler.append({
                    "source_id": sid, "ad": kayit["ad"], "niyet": niyet,
                    "yontem": "yoklama", "beklenen": "html",
                    "url": origin + yol, "origin": origin,
                })
    return hedefler
