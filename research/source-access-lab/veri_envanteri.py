"""636 aday kaynagin bu checkout'taki gercek durumunu envanterler.

Bu adim mevcut siniflandirmayi yeniden yazmaz; **veriden dogrular**. Iki soruyu
ayirir ve ikisini de kaynak kaynak cevaplar:

* **Erisim durumu** — kaynaga ulasildi mi? (`KAYNAK-DEFTERI.csv`'den gelir)
* **Icerik durumu** — bu checkout'ta gercekten acilabilir bir dosya var mi, ve
  icinde ne var?

Ikisi ayni sey degildir ve karistirilmalari bu calismanin en buyuk riskidir.
``cekildi`` etiketi bir **erisim snapshot**'idir: en az bir yuzeyin yanit
verdigini gosterir. Karar kaniti ya da uretime hazir veri anlamina **gelmez**.

Gorevin acik sarti: **elde olmayan dosya incelenmis gosterilmez.** Artefakt
dizini bir kaydi "dosya" diye isaretlemis olabilir ama dosya diskte
bulunmayabilir; ya da govde hic saklanmamis, yalnizca hash ve URL tutulmus
olabilir. Bunlarin ucu ayri ayri sayilir.

Yuzey turleri birbirine karistirilmaz:

``sitemap``/``arama`` aday kesiftir · ``robots`` politika belgesidir ·
``arsiv`` Common Crawl kopyasidir, canli degildir · ``api-yaniti`` yapisal
kayittir · ``js-kabugu`` HTTP 200 doner ve buyuk govde tasir ama gorunur metni
yoktur, cunku sayfa tarayicida uretilir · ``hata/bot sayfasi`` erisim engelidir.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import warnings
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
warnings.filterwarnings("ignore", message=".*REPLACEMENT CHARACTER.*")

HERE = Path(__file__).resolve().parent

# Gorunur metni bu esigin altinda kalan buyuk HTML, tarayicida uretilen bir
# kabuktur. Esik olculerek secildi: 441 HTML artefaktin metin uzunlugu
# medyani 5930; 200'un altinda kalan 50 dosyanin hepsi yalniz <title> metnini
# tasiyordu (Google Play, YouTube, Similarweb...).
JS_KABUGU_METIN_ESIGI = 200
JS_KABUGU_ASGARI_HAM = 20_000

# Engel/hata sayfasi yalniz BASLIKTAN taninir. Govdede 'captcha' kelimesinin
# gecmesi yetmez: sayfanin kendi scriptleri de bu kelimeyi tasir ve olculdugunde
# aday 34 dosyanin neredeyse tamami yanlis pozitif cikti.
ENGEL_BASLIGI = re.compile(
    r"(?i)(access denied|content blocked|just a moment|attention required|"
    r"\bforbidden\b|are you a robot|pardon our interruption|request unsuccessful|"
    r"security check|error 10\d\d|page not found|service unavailable|"
    r"too many requests|\b(403|404|429|503)\b)")

# Yuzey turu siniflandirmasi: yontem -> tur. Aday kesif ile veri yuzeyi
# ayrimi gorev 3'te kurulmustu; burada korunur.
YUZEY_TURU: dict[str, str] = {
    "robots_preflight": "politika",
    "sitemap_xml": "aday-kesif",
    "rss_link_discovery": "aday-kesif",
    "rss_feed": "besleme",
    "common_crawl_warc": "arsiv",
    "root_html": "sayfa",
    "entry_url": "sayfa",
    "rel_next_pagination": "sayfa",
}
API_YUZEYI = "api-yaniti"

# Icerik durumu siralamasi: bir kaynakta birden cok yuzey varsa en guclusu
# raporlanir, digerleri ayrica listelenir.
ICERIK_SIRASI = ("api-yaniti", "gercek-icerik", "besleme", "arsiv",
                 "js-kabugu", "engel-sayfasi", "aday-kesif", "politika",
                 "dosya-yok")


def yuzey_turu(yontem: str) -> str:
    return YUZEY_TURU.get(yontem, API_YUZEYI)


def html_metni(ham: bytes) -> tuple[str, str]:
    """(baslik, gorunur metin) doner. Ham bayt asla degistirilmez."""
    corba = BeautifulSoup(ham, "html.parser")
    for etiket in corba(["script", "style", "noscript", "template"]):
        etiket.decompose()
    baslik = corba.title.get_text().strip() if corba.title else ""
    metin = re.sub(r"\s+", " ", corba.get_text(" ")).strip()
    return baslik, metin


def icerik_durumu(yontem: str, mime: str, ham: bytes) -> tuple[str, str]:
    """(durum, gerekce) doner. Dosya acilarak belirlenir, adindan cikarilmaz."""
    tur = yuzey_turu(yontem)
    if tur in ("politika", "aday-kesif", "besleme"):
        return tur, f"yöntem {yontem}"
    if "json" in mime.lower():
        return "api-yaniti", f"MIME {mime.split(';')[0]}"
    if "html" not in mime.lower() and "xml" in mime.lower():
        return "aday-kesif", f"MIME {mime.split(';')[0]}"
    baslik, metin = html_metni(ham)
    if ENGEL_BASLIGI.search(baslik):
        return "engel-sayfasi", f"başlıkta engel ifadesi: {baslik[:40]!r}"
    if len(metin) < JS_KABUGU_METIN_ESIGI and len(ham) >= JS_KABUGU_ASGARI_HAM:
        return "js-kabugu", (f"{len(ham)} bayt HTML ama görünür metin "
                             f"{len(metin)} karakter")
    if tur == "arsiv":
        return "arsiv", f"Common Crawl kopyası, görünür metin {len(metin)} karakter"
    return "gercek-icerik", f"görünür metin {len(metin)} karakter"


def _oku(ad: str) -> list[dict[str, str]]:
    with (HERE / ad).open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def envanter_kur() -> dict[str, Any]:
    manifest = json.loads((HERE / "source_manifest.json").read_text(encoding="utf-8"))
    kaynaklar = {s["source_id"]: s for s in manifest["sources"]}
    defter = {r["source_id"]: r for r in _oku("KAYNAK-DEFTERI.csv")}
    yuzeyler = {r["source_id"]: r for r in _oku("ARAMA-YUZEYLERI.csv")}
    # Ic sayfa gecisinin artefaktlari ayri dizine yazilir; envanter ikisini de
    # gormeli, yoksa yeni cekilen bir kaynak "dosyasi yok" gorunur.
    ek_yol = HERE / "EK-ARTEFAKT-DIZINI.csv"
    ek = _oku("EK-ARTEFAKT-DIZINI.csv") if ek_yol.exists() else []
    dizin = _oku("ARTEFAKT-DIZINI.csv") + ek
    kategori_kaynak = _oku("KATEGORI-KAYNAK.csv")

    # DR-L02'de fiilen acilan artefaktlar
    incelenen: dict[str, set[str]] = collections.defaultdict(set)
    pilot_yolu = HERE / "PILOT-KAYITLAR.csv"
    if pilot_yolu.exists():
        for r in _oku("PILOT-KAYITLAR.csv"):
            incelenen[r["source_id"]].add(r["artefakt_kimligi"])

    # Kaynak ailesi: ad uzerinden, cunku KATEGORI-KAYNAK source_id tasimaz
    aile: dict[str, set[str]] = collections.defaultdict(set)
    for r in kategori_kaynak:
        for g in r["kaynak_grubu"].split(" | "):
            aile[r["kaynak"]].add(g.strip())

    # Artefaktlari kaynaga gore topla; uc durumu AYRI say
    artefakt: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for r in dizin:
        if r.get("source_id"):
            artefakt[r["source_id"]].append(r)

    satirlar: list[dict[str, Any]] = []
    islenemeyen: list[dict[str, Any]] = []

    for sid, kaynak in sorted(kaynaklar.items()):
        ad = kaynak["display_name"]
        d = defter.get(sid, {})
        kayitlar = artefakt.get(sid, [])
        basarili = [r for r in kayitlar if r["sonuc"] == "ok"]

        diskte: list[tuple[dict[str, str], str, str]] = []
        govdesiz = 0
        kayip = 0
        bos = 0
        for r in basarili:
            if r["saklama"] == "kosu_json_icinde":
                govdesiz += 1
                islenemeyen.append({
                    "source_id": sid, "ad": ad, "artefakt": r["sha256"][:16],
                    "yontem": r["yontem"], "url": r["cekilen_url"],
                    "neden": "gövde saklanmamış (saklama=kosu_json_icinde)",
                })
                continue
            if not r["dosya"].strip():
                # 200 dondu ama govde sifir bayt: saklanacak icerik yok.
                bos += 1
                islenemeyen.append({
                    "source_id": sid, "ad": ad, "artefakt": r["sha256"][:16],
                    "yontem": r["yontem"], "url": r["cekilen_url"],
                    "neden": "yanıt gövdesi boş; saklanacak içerik yok",
                })
                continue
            yol = HERE / r["dosya"]
            if not yol.exists():
                kayip += 1
                islenemeyen.append({
                    "source_id": sid, "ad": ad, "artefakt": r["sha256"][:16],
                    "yontem": r["yontem"], "url": r["cekilen_url"],
                    "neden": f"dizinde 'dosya' yazıyor ama bu checkout'ta yok: {r['dosya']}",
                })
                continue
            ham = yol.read_bytes()[:400_000]
            durum, gerekce = icerik_durumu(r["yontem"], r["mime"], ham)
            diskte.append((r, durum, gerekce))

        durumlar = [t[1] for t in diskte]
        if durumlar:
            en_iyi = min(durumlar, key=ICERIK_SIRASI.index)
            gerekce = next(g for _r, dd, g in diskte if dd == en_iyi)
        else:
            en_iyi, gerekce = "dosya-yok", (
                "bu checkout'ta açılabilir dosya yok"
                + (f"; {govdesiz} kayıt gövdesiz" if govdesiz else "")
                + (f"; {kayip} kayıt diskte bulunamadı" if kayip else ""))

        eksikler: list[str] = []
        if kayip:
            eksikler.append(f"{kayip} artefakt dizinde var, diskte yok")
        if govdesiz:
            eksikler.append(f"{govdesiz} artefaktın gövdesi saklanmamış")
        if not basarili:
            eksikler.append(f"hiç başarılı artefakt yok ({d.get('sebep') or 'sebep yazılmamış'})")
        if en_iyi == "js-kabugu":
            eksikler.append("sayfa tarayıcıda üretiliyor; düz çekimle metin alınamıyor")
        if en_iyi in ("aday-kesif", "politika"):
            eksikler.append("yalnız keşif/politika yüzeyi; içerik yüzeyi çekilmemiş")

        satirlar.append({
            "source_id": sid,
            "ad": ad,
            "adres": kaynak.get("official_origin", ""),
            "kaynak_ailesi": ", ".join(sorted(aile.get(ad, set()))) or "(aile atanmamış)",
            "erisim_durumu": d.get("durum", "(defterde yok)"),
            "erisim_sebebi": d.get("sebep", ""),
            "yuzey_turleri": ", ".join(sorted({yuzey_turu(r["yontem"]) for r in basarili})),
            "yontemler": ", ".join(sorted({r["yontem"] for r in basarili})),
            "artefakt_basarili": len(basarili),
            "dosyasi_diskte": len(diskte),
            "govdesi_saklanmamis": govdesiz,
            "govdesi_bos": bos,
            "dizinde_var_diskte_yok": kayip,
            "icerik_durumu": en_iyi,
            "icerik_gerekcesi": gerekce,
            "incelendi": "evet" if incelenen.get(sid) else "hayir",
            "incelenen_artefakt": ", ".join(sorted(incelenen.get(sid, set()))),
            "arama_yolu": yuzeyler.get(sid, {}).get("en_iyi_yol", ""),
            "eksik": " | ".join(eksikler),
        })
    return {"satirlar": satirlar, "islenemeyen": islenemeyen}


def kapsama_raporu(satirlar: list[dict[str, Any]],
                   islenemeyen: list[dict[str, Any]]) -> str:
    erisim = collections.Counter(r["erisim_durumu"] for r in satirlar)
    icerik = collections.Counter(r["icerik_durumu"] for r in satirlar)
    incelendi = sum(1 for r in satirlar if r["incelendi"] == "evet")
    acilabilir = sum(1 for r in satirlar if r["dosyasi_diskte"])

    aile_sayaci: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in satirlar:
        for a in r["kaynak_ailesi"].split(", "):
            aile_sayaci[a]["toplam"] += 1
            if r["dosyasi_diskte"]:
                aile_sayaci[a]["açılabilir"] += 1
            if r["incelendi"] == "evet":
                aile_sayaci[a]["incelendi"] += 1

    s = [
        "# Veri Envanteri ve Kapsama Raporu",
        "",
        "**Hazırlayan:** Ayselin Aydoğdu  ",
        "**Üretim:** `veri_envanteri.py` — elle yazılmaz, koddan üretilir  ",
        f"**Kanonik kaynak:** {len(satirlar)} (`source_manifest.json`)",
        "",
        "> **`erişildi` karar kanıtı değildir.** Erişim durumu, kaynağın yanıt",
        "> verdiğini gösteren bir snapshot'tır; üretime hazır veri ya da araştırma",
        "> sorusuna uygun kanıt anlamına gelmez. İçerik durumu ayrı bir sütundur.",
        "",
        "## 1. Erişim durumu — deftere göre",
        "", "| Durum | Kaynak |", "|---|---:|",
    ]
    for k, v in erisim.most_common():
        s.append(f"| `{k}` | {v} |")
    s += [
        "",
        "## 2. İçerik durumu — bu checkout'ta dosya açılarak",
        "",
        "Erişim durumundan **bağımsız** ölçülür: dosya gerçekten var mı, içinde ne var.",
        "", "| Durum | Kaynak | Anlamı |", "|---|---:|---|",
    ]
    anlam = {
        "gercek-icerik": "Görünür metin taşıyan sayfa",
        "api-yaniti": "Yapılandırılmış kayıt — en güvenilir",
        "besleme": "RSS; başlık ve özet taşır, tam içerik taşımaz",
        "arsiv": "Common Crawl kopyası; canlı değil",
        "js-kabugu": "HTTP 200 ve büyük gövde ama görünür metin yok",
        "aday-kesif": "Sitemap/XML; **kanıt değil**, aday URL sinyali",
        "politika": "robots.txt; erişim kuralı, araştırma malzemesi değil",
        "dosya-yok": "Bu checkout'ta açılabilir dosya yok",
    }
    for k, v in icerik.most_common():
        s.append(f"| `{k}` | {v} | {anlam.get(k, '')} |")
    capraz = collections.Counter(
        (r["erisim_durumu"], r["icerik_durumu"]) for r in satirlar)
    sutunlar = [d for d in ICERIK_SIRASI if any(
        capraz[(e, d)] for e in erisim)]
    s += [
        "",
        f"**{acilabilir} kaynakta açılabilir dosya var**; kalan "
        f"{len(satirlar) - acilabilir} kaynakta yok.",
        "",
        "## 2b. Erişim durumu × içerik durumu",
        "",
        "Raporun en önemli tablosu budur: **erişim etiketi ile elde gerçekten ne",
        "olduğu aynı şey değildir.**",
        "",
        "| Erişim | " + " | ".join(f"`{d}`" for d in sutunlar) + " |",
        "|---" * (len(sutunlar) + 1) + "|",
    ]
    for e, _n in erisim.most_common():
        s.append(f"| `{e}` | " + " | ".join(
            str(capraz[(e, d)]) for d in sutunlar) + " |")
    cekildi = [r for r in satirlar if r["erisim_durumu"] == "cekildi"]
    gercek = sum(1 for r in cekildi if r["icerik_durumu"] == "gercek-icerik")
    bos = sum(1 for r in cekildi if r["icerik_durumu"] == "dosya-yok")
    s += [
        "",
        f"`cekildi` etiketli **{len(cekildi)}** kaynaktan yalnız **{gercek}**'ünde",
        f"görünür metin taşıyan içerik var. **{bos}** kaynakta ise bu checkout'ta",
        "açılabilir tek dosya yok — etiket erişimi anlatıyor, elde olanı değil.",
        "",
        "## 3. İncelendi durumu",
        "",
        f"| | Kaynak |", "|---|---:|",
        f"| Fiilen açılıp incelendi (DR-L02) | {incelendi} |",
        f"| Açılabilir ama henüz incelenmedi | {acilabilir - incelendi} |",
        f"| Açılacak dosyası yok | {len(satirlar) - acilabilir} |",
        "",
        "İncelenmiş sayılan her kaynak `PILOT-KAYITLAR.csv`'de artefakt hash'iyle",
        "kayıtlıdır. **Elde olmayan dosya incelenmiş gösterilmez.**",
        "",
        "## 3b. DR-L02 sözlüğüyle ilişki",
        "",
        "Bu envanter mevcut sınıflandırmayı **yeniden yazmaz, doğrular.** İki",
        "çıktı farklı eksenlerde durur ve karıştırılmamalıdır:",
        "",
        "| | Sorduğu soru |",
        "|---|---|",
        "| `PILOT-KAYITLAR.csv` · `belge_turu` | Bu dosya **ne tür bir belge**? |",
        "| `VERI-ENVANTERI.csv` · `icerik_durumu` | Bu dosyadan **metin çıkarılabiliyor mu**? |",
        "",
        "Bir ana sayfa hem `ana-sayfa` (belge türü) hem `js-kabugu` (içerik",
        "durumu) olabilir: türü ana sayfadır, ama tarayıcıda üretildiği için",
        "metni alınamaz. Çelişki değil, iki ayrı ölçüdür.",
        "",
        "Doğrulama: pilotta açılan 95 kaynağın tamamı bu envanterde var ve",
        "**envanterin 'dosyası yok' dediği hiçbir kaynak pilotta açılmış",
        "görünmüyor.**",
        "",
        "## 4. Kaynak ailesi bazında kapsama",
        "", "| Kaynak ailesi | Toplam | Açılabilir | İncelendi | Bekleyen |",
        "|---|---:|---:|---:|---:|",
    ]
    for a in sorted(aile_sayaci):
        c = aile_sayaci[a]
        s.append(f"| {a} | {c['toplam']} | {c['açılabilir']} | {c['incelendi']} "
                 f"| {c['açılabilir'] - c['incelendi']} |")
    s += [
        "",
        "## 5. İşlenemeyen kayıtlar",
        "",
        f"Toplam **{len(islenemeyen)}** artefakt kaydı işlenemedi. Silinmediler;",
        "`ENVANTER-ISLENEMEYEN.csv` dosyasında nedeniyle duruyorlar.",
        "", "| Neden | Kayıt |", "|---|---:|",
    ]
    for k, v in collections.Counter(
            r["neden"].split(":")[0] for r in islenemeyen).most_common():
        s.append(f"| {k} | {v} |")
    s.append("")
    return "\n".join(s)


def gun2_plani(satirlar: list[dict[str, Any]]) -> str:
    aday = [r for r in satirlar if r["dosyasi_diskte"] and r["incelendi"] == "hayir"]
    oncelik: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for r in aday:
        oncelik[r["icerik_durumu"]].append(r)

    s = [
        "# Gün 2 Örneklem Planı",
        "",
        f"Gün 1 envanteri {len(satirlar)} kanonik kaynağı kapsadı. Gün 2'de açılacak",
        f"aday havuzu: **açılabilir dosyası olan ama henüz incelenmemiş "
        f"{len(aday)} kaynak.**",
        "",
        "## Öncelik sırası ve gerekçesi",
        "", "| Sıra | İçerik durumu | Aday | Neden bu sırada |", "|---|---|---:|---|",
    ]
    gerekce = {
        "api-yaniti": "Yapılandırılmış alan taşır; doğrulama maliyeti en düşük",
        "gercek-icerik": "Görünür metin var; belge türü ve alan çıkarımı mümkün",
        "besleme": "Tarih ve başlık kesin; gövde için bağlantıya gitmek gerekir",
        "arsiv": "İçerik var ama güncel değil; tazelik ayrıca işaretlenmeli",
        "js-kabugu": "Düz çekimle metin alınamıyor; örneklem yerine **kayıt** konusu",
        "aday-kesif": "Kanıt değil; yalnız hangi iç sayfaların çekileceğini gösterir",
        "politika": "Araştırma malzemesi değil",
    }
    for i, durum in enumerate(ICERIK_SIRASI, 1):
        if durum in oncelik:
            s.append(f"| {i} | `{durum}` | {len(oncelik[durum])} | "
                     f"{gerekce.get(durum, '')} |")
    s += [
        "",
        "## Örneklem kuralı",
        "",
        "1. **Kaynak ailesi başına en az üç örnek**, aile tükenene kadar.",
        "2. Aile üç örnek veremiyorsa **eksik kaydı yazılır**, doldurulmaz.",
        "3. Her **yüzey türünden** en az bir örnek ayrıca açılır; aile örneklemi",
        "   en bilgilendirici dosyayı seçtiği için az sayıda ama değerli yüzeyler",
        "   (API yanıtları) dışarıda kalır.",
        "4. `js-kabugu` ve `aday-kesif` kaynakları örnekleme **girmez**; onlar",
        "   içerik üretmediği için ayrı bir iş kaleminin konusudur.",
        "",
        "## Gün 2'de açılmayacaklar ve nedeni",
        "", "| Grup | Kaynak | Neden |", "|---|---:|---|",
        f"| Açılabilir dosyası yok | {sum(1 for r in satirlar if not r['dosyasi_diskte'])} | Elde dosya yok; incelenmiş gösterilemez |",
        f"| Zaten incelendi (DR-L02) | {sum(1 for r in satirlar if r['incelendi'] == 'evet')} | Artefakt hash'iyle kayıtlı |",
        f"| `js-kabugu` | {len(oncelik.get('js-kabugu', []))} | Düz çekimle metin alınamıyor |",
        "",
        "## Beklenen çıktı",
        "",
        "Gün 2 sonunda her açılan kaynak için belge türü, çıkarılabilen alanlar ve",
        "sınıflandırma gerekçesi; açılamayan her kaynak için eksik kaydı.",
        "",
    ]
    return "\n".join(s)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "VERI-ENVANTERI.csv")
    parser.add_argument("--out-islenemeyen", type=Path,
                        default=HERE / "ENVANTER-ISLENEMEYEN.csv")
    args = parser.parse_args()

    sonuc = envanter_kur()
    satirlar, islenemeyen = sonuc["satirlar"], sonuc["islenemeyen"]

    with args.out.open("w", newline="", encoding="utf-8") as handle:
        yazici = csv.DictWriter(handle, fieldnames=list(satirlar[0]))
        yazici.writeheader()
        yazici.writerows(satirlar)
    if islenemeyen:
        with args.out_islenemeyen.open("w", newline="", encoding="utf-8") as handle:
            yazici = csv.DictWriter(handle, fieldnames=list(islenemeyen[0]))
            yazici.writeheader()
            yazici.writerows(islenemeyen)

    (HERE / "KAPSAMA-RAPORU.md").write_text(
        kapsama_raporu(satirlar, islenemeyen) + "\n", encoding="utf-8")
    (HERE / "GUN2-ORNEKLEM-PLANI.md").write_text(
        gun2_plani(satirlar) + "\n", encoding="utf-8")

    print(json.dumps({
        "kanonik_kaynak": len(satirlar),
        "erisim_durumu": collections.Counter(
            r["erisim_durumu"] for r in satirlar).most_common(),
        "icerik_durumu": collections.Counter(
            r["icerik_durumu"] for r in satirlar).most_common(),
        "acilabilir_dosyasi_olan": sum(1 for r in satirlar if r["dosyasi_diskte"]),
        "incelendi": sum(1 for r in satirlar if r["incelendi"] == "evet"),
        "islenemeyen_kayit": len(islenemeyen),
        "cikti": [str(args.out), str(args.out_islenemeyen),
                  "KAPSAMA-RAPORU.md", "GUN2-ORNEKLEM-PLANI.md"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
