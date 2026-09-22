"""Bir urun fikri icin calistirilacak kaynak paketini deterministik secer.

Ilk dort gorev bir katalog uretti: hangi kaynak hangi urun tipine hizmet eder,
hangi soruyu cevaplar, hangi alani hangi izinli yoldan verir. Bu adim katalogu
**kullanan** ilk parcadir: fikir gelince 636 kaynagin hepsini calistirmak yerine
kucuk bir paket secer.

Secim uc sarta baglidir:

**Degerli.** Kaynak, o fikrin kategorisindeki sorulari cevaplayan olcum alanini
izinli bir yoldan vermeli. Gorev 4'un suzgeci budur; suzgecten gecmeyen kaynak
havuza bile girmez.

**Bagimsiz.** Burasi isin zor kismi. Bir soruya on uygulama magazasindan bakmak
on kanit degildir -- ayni sey on kez okunmus olur, ve "on kaynak da dogruladi"
cumlesi kanit gucunu oldugundan yuksek gosterir. Bu yuzden cikti duz bir kaynak
listesi degil, **soru basina kanit yuvalaridir**: her yuva ayri bir kaynak
grubundan gelir, yani ayri bir olcme yontemidir. Ayni gruptaki kaynaklar
birbirinin rakibi degil **yedegidir**; ilki bot korumasi verirse ikincisi
denenir.

**Deterministik.** Ayni fikir iki kez verildiginde ayni paket cikar. Siralama
olculebilir kriterlere dayanir (izin sinifi, dogrulanmis alan sayisi, kapsanan
soru sayisi) ve esitlik ``source_id`` ile bozulur. Modele sorulmaz.

Bilincli bir sinir: elimizde **pazar buyuklugu verisi yok**. Google Play'in
F-Droid'den buyuk oldugunu soyleyen bir sutun yoktur. Bu yuzden secim kapsama
ve bagimsizlik garantisi verir, pazar agirligi garantisi vermez; yuva ici sira
olculebilir kriterlere dayanir, tahmini populerlige degil.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import unicodedata
from pathlib import Path
from typing import Any

import butce_profilleri as butce

HERE = Path(__file__).resolve().parent

# Her soru icin en fazla kac ayri kanit yuvasi acilir. Uc farkli olcme yontemi
# bir soruyu desteklemeye yeter; dordunculer getiriyi artirmadan maliyet ekler.
# Bu bir tercihtir, veriden turetilmis bir esik degil -- ``--yuva`` ile
# degistirilebilir, ve kesilen yuva sayisi ciktida gorunur kalir.
SORU_BASINA_YUVA = 3
# Yuva icinde kac yedek tutulur. Ilki calismazsa sirayla denenir.
YUVA_BASINA_YEDEK = 3
# Bir soru icin en az kac ayri yuva hedeflenir; altina duserse cikti uyarir.
ASGARI_YUVA = 2

# --------------------------------------------------------------------------
# Fikir metninden kategoriye. Sabit tablo kullanilir cunku gorev 'deterministik'
# sart kosuyor: ayni fikir her zaman ayni kategoriye dusmeli.
# --------------------------------------------------------------------------
KATEGORI_ANAHTAR: dict[str, tuple[str, ...]] = {
    "mobil-uygulama": ("mobil", "uygulama", "app", "ios", "android", "telefon"),
    "b2b-web-yazilimi": ("saas", "b2b", "kurumsal", "isletme", "panel", "crm",
                         "erp", "abonelik", "yazilim", "platform"),
    "gelistirici-araci": ("kutuphane", "sdk", "cli", "api", "framework", "paket",
                          "gelistirici", "altyapi", "kod"),
    "eklenti-entegrasyon": ("eklenti", "plugin", "entegrasyon", "uzanti",
                            "extension", "tema"),
    "yapay-zeka-urunu": ("yapay zeka", "yapay zekâ", "ai", "model", "agent",
                         "llm", "makine ogrenmesi", "veri seti"),
    "oyun": ("oyun", "game", "oyuncu"),
    "yerel-hizmet": ("yerel", "randevu", "esnaf", "kurye", "mahalle", "sehir",
                     "hizmet", "usta"),
}

EK_ANAHTAR: dict[str, tuple[str, ...]] = {
    "saglik": ("saglik", "diyabet", "hasta", "tibbi", "klinik", "doktor",
               "ilac", "biyoteknoloji"),
    "fintech": ("finans", "odeme", "banka", "fatura", "muhasebe", "kredi",
                "sigorta", "yatirim"),
    "egitim": ("egitim", "ogrenci", "kurs", "okul", "ders", "sinav"),
    "gayrimenkul": ("emlak", "gayrimenkul", "kiralik", "satilik", "insaat",
                    "konut"),
    "seyahat": ("seyahat", "otel", "ucus", "rezervasyon", "tatil", "konaklama"),
    "yeme-icme": ("yemek", "restoran", "teslimat", "kafe", "menu", "siparis"),
    "regule-sektor": ("mevzuat", "regulasyon", "lisans", "uyum", "kvkk",
                      "gdpr", "hukuk"),
    "turkiye-pazari": ("turkiye", "turk", "yerli", "istanbul", "ankara"),
}

# Izin sinifinin secim sirasindaki agirligi. API belgelenmis ve programatik
# erisim icin tasarlanmis yoldur; HTML kazima ayni garantiyi vermez.
IZIN_AGIRLIGI: dict[str, int] = {"api-acik": 2, "robots-izinli": 1}

# Gorev 1'in katman kurali. Calisma aninda ``URUN-KATEGORILERI.csv`` okunur;
# bu sabit yalniz dosyasiz cagrilar icin varsayilandir.
KATMAN_VARSAYILAN: frozenset[str] = frozenset(
    {"mobil-uygulama", "eklenti-entegrasyon", "yapay-zeka-urunu"})


def sadelestir(metin: str) -> str:
    """Turkce harfleri ve buyuk/kucuk farkini eleyip anahtar aramasina hazirlar."""
    metin = metin.replace("ı", "i").replace("I", "i").replace("İ", "i")
    ayrik = unicodedata.normalize("NFKD", metin.casefold())
    return "".join(k for k in ayrik if not unicodedata.combining(k))


def hedefleri_bul(fikir: str,
                  katman_olabilir: frozenset[str] = KATMAN_VARSAYILAN
                  ) -> tuple[str, list[str], list[str], dict[str, int]]:
    """Fikirden ana kategoriyi, katmanlari ve tetiklenen ek paketleri cikarir.

    Kategori tahmini sessizce varsayilana dusmez: hicbir anahtar eslesmezse
    hata verir, cunku yanlis kategori butun secimi yanlis yapar.

    Bir fikir birden fazla kategoriye uyabilir -- 'mobil bulmaca oyunu' hem
    ``oyun`` hem ``mobil-uygulama`` anahtari tasir. Gorev 1 bu durumu zaten
    karara baglamis: ``katman_olabilir`` isaretli kategoriler (mobil-uygulama,
    eklenti-entegrasyon, yapay-zeka-urunu) dagitim ya da teknoloji katmanidir,
    baskasinin ustune biner. Ana kategori arastirmanin ayirt edici sorusunu
    cevaplayandir, yani katman OLMAYAN kategoridir; katman ayrica eklenir.
    Bu kural burada yeniden icat edilmez, gorev 1'in ciktisindan okunur.
    """
    sade = sadelestir(fikir)
    puan = {k: sum(1 for a in anahtarlar if sadelestir(a) in sade)
            for k, anahtarlar in KATEGORI_ANAHTAR.items()}
    varolan = {k: v for k, v in puan.items() if v}
    if not varolan:
        raise SystemExit(
            "kategori_belirlenemedi: fikirde tanınan anahtar yok. "
            "--kategori ile açıkça verin.")
    # Once katman olmayanlar, sonra anahtar sayisi, sonra alfabetik:
    # ayni fikir her zaman ayni kategoriye dussun.
    kategori = min(sorted(varolan),
                   key=lambda k: (k in katman_olabilir, -varolan[k], k))
    katmanlar = sorted(k for k in varolan
                       if k != kategori and k in katman_olabilir)
    ekler = sorted(e for e, anahtarlar in EK_ANAHTAR.items()
                   if any(sadelestir(a) in sade for a in anahtarlar))
    return kategori, katmanlar, ekler, puan


def oku(yol: Path) -> list[dict[str, str]]:
    with yol.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def paket_sec(fikir: str, kategori: str, ekler: list[str],
              veri: dict[str, Any], katmanlar: list[str] | None = None,
              soru_basina_yuva: int = SORU_BASINA_YUVA,
              profil_adi: str = "ucretsiz") -> list[dict[str, Any]]:
    """Soru basina kanit yuvalari uretir; her yuva ayri bir olcme yontemidir."""
    kategori_kaynak = veri["kategori_kaynak"]
    kategori_soru = veri["kategori_soru"]
    olcum_alani = veri["olcum_alani"]
    metin_bayt = veri["metin_bayt"]
    izin = veri["izin"]
    dogrulanan = veri["dogrulanan"]
    host = veri["host"]
    rol = veri["rol"]

    katmanlar = sorted(katmanlar or [])
    hedefler = {kategori, *katmanlar, *ekler, "ortak"}
    havuz = {r["kaynak"] for r in kategori_kaynak if r["hedef"] in hedefler}
    # Gorev 4 suzgeci: izinli yolu ve olcum alani olmayan kaynak havuza girmez.
    # Profil yalniz TAZELIGI degistirir: ucretsiz arsiv kopyasini kabul eder,
    # premium etmez. Yasak ve yolsuz kaynak iki profilde de disaridadir.
    kabul = set(butce.kabul_edilen_izin(profil_adi))
    yedek_sayisi = int(butce.profil(profil_adi)["yuva_basina_yedek"])
    aday = {a for a in havuz
            if olcum_alani.get(a) and (izin.get(a, set()) & kabul)}

    def kaynak_sirasi(ad: str) -> tuple[int, int, int, int, int, int, str]:
        """Yuva icindeki sira. Kriterlerin hepsi olculmus degerlerdir;
        'hangisi daha populer' gibi elimizde verisi olmayan bir yargi girmez.

        ``tam_metin_bayt`` o kaynaktan **fiilen alinan metin miktaridir**.
        Buyuk katalogu olan bir kaynak daha cok metin dondurur, o yuzden bu
        deger icerik zenginliginin dolayli ama olculmus gostergesidir. Hic
        icerik dondurmemis kaynak (0 bayt) once elenir: API'si olsa bile
        elimizde ondan gelmis tek satir yoktur.
        """
        bayt = metin_bayt.get(ad, 0)
        en_iyi_izin = max((IZIN_AGIRLIGI.get(i, 0) for i in izin.get(ad, set())),
                          default=0)
        # Profil tazelik istiyorsa, yalniz arsiv kopyasi olan kaynak birincil
        # olmaz ama havuzdan da cikmaz: yedege duser, boylece kanit acisi
        # kaybolmaz.
        yalniz_arsiv = izin.get(ad, set()) <= {"arsiv-kopyasi"}
        arsiv_cezasi = 0 if (butce.arsiv_birincil_olabilir(profil_adi)
                             or not yalniz_arsiv) else 1
        return (arsiv_cezasi, 0 if (bayt or dogrulanan.get(ad)) else 1,
                -len(dogrulanan.get(ad, set())), -en_iyi_izin, -bayt,
                -len(olcum_alani.get(ad, set())), ad.casefold())

    # Soru -> hangi kaynak gruplari kanit veriyor (yalniz bu kategori/ekler icin)
    soru_gruplari: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for r in kategori_soru:
        if r["kategori"] in hedefler:
            soru_gruplari[r["soru_id"]].append(r)

    grup_kaynaklari: dict[str, set[str]] = collections.defaultdict(set)
    for r in kategori_kaynak:
        if r["kaynak"] in aday:
            for g in r["kaynak_grubu"].split(" | "):
                grup_kaynaklari[g.strip()].add(r["kaynak"])

    satirlar: list[dict[str, Any]] = []
    for soru_id in sorted(soru_gruplari):
        kanitlar = soru_gruplari[soru_id]
        # Ayni grup birden fazla kategoriden gelebilir; grup basina tek yuva.
        gruplar: dict[str, dict[str, str]] = {}
        for k in kanitlar:
            gruplar.setdefault(k["kanit_kaynak_grubu"], k)

        yuvalar: list[tuple[str, dict[str, str], list[str]]] = []
        kullanilan_host: set[str] = set()
        for grup in sorted(gruplar):
            kaynaklar = sorted(grup_kaynaklari.get(grup, set()), key=kaynak_sirasi)
            # Ayni host'tan ikinci bir yuva acmak bagimsizlik saglamaz.
            kaynaklar = [k for k in kaynaklar
                         if host.get(k, k) not in kullanilan_host]
            if not kaynaklar:
                continue
            yuvalar.append((grup, gruplar[grup], kaynaklar[:yedek_sayisi + 1]))
            kullanilan_host.add(host.get(kaynaklar[0], kaynaklar[0]))

        # Yuva sirasi: once dogrulanmis kaynagi olan grup, sonra kaynak bollugu.
        def yuva_sirasi(y: tuple[str, dict[str, str], list[str]]) -> tuple[int, int, int, str]:
            _grup, _kanit, kaynaklar = y
            dog = sum(1 for k in kaynaklar if dogrulanan.get(k))
            bayt = sum(metin_bayt.get(k, 0) for k in kaynaklar)
            return (-dog, -bayt, -len(grup_kaynaklari.get(y[0], set())), y[0])

        yuvalar.sort(key=yuva_sirasi)
        # Sinirin kestigi yuva sessizce kaybolmaz: kac yuva vardi, kaci
        # kullanildi ve elenenin hangi gruplar oldugu her satirda yazili kalir.
        kullanilan = yuvalar[:soru_basina_yuva]
        elenen = [g for g, _k, _s in yuvalar[soru_basina_yuva:]]
        for sira, (grup, kanit, kaynaklar) in enumerate(kullanilan, 1):
            birincil = kaynaklar[0]
            satirlar.append({
                "fikir": fikir, "profil": profil_adi, "kategori": kategori,
                "katmanlar": ", ".join(katmanlar),
                "ekler": ", ".join(ekler), "soru_id": soru_id,
                "soru": kanit["soru"], "yuva": sira,
                "kaynak_grubu": grup, "kanit_turu": kanit["kanit_turu"],
                "birincil_kaynak": birincil,
                "yedekler": ", ".join(kaynaklar[1:]),
                "host": host.get(birincil, ""),
                "izin_durumu": sorted(izin.get(birincil, set()))[0],
                "olcum_alani": ", ".join(sorted(olcum_alani.get(birincil, set()))),
                "dogrulanmis_alan": ", ".join(sorted(dogrulanan.get(birincil, set()))),
                "kaynak_rolu": rol.get(birincil, ""),
                "neden_secildi": _gerekce(birincil, grup, sira, izin, dogrulanan, rol),
                "yuva_sayisi": len(kullanilan),
                "mevcut_yuva": len(yuvalar),
                "kullanilmayan_yuva": ", ".join(elenen),
            })
    return satirlar


def _gerekce(ad: str, grup: str, sira: int, izin: dict[str, set[str]],
             dogrulanan: dict[str, set[str]], rol: dict[str, str]) -> str:
    parcalar = [f"{sira}. kanıt yuvası ({grup})"]
    if rol.get(ad) == "cekirdek":
        parcalar.append("kategorinin çekirdek kaynağı")
    if "api-acik" in izin.get(ad, set()):
        parcalar.append("açık API")
    if dogrulanan.get(ad):
        parcalar.append(f"{len(dogrulanan[ad])} alanı artefaktta doğrulanmış")
    return "; ".join(parcalar)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fikir", required=True)
    parser.add_argument("--kategori", help="Otomatik tespiti geçersiz kılar")
    parser.add_argument("--katman", action="append", default=None)
    parser.add_argument("--kategoriler", type=Path,
                        default=HERE / "URUN-KATEGORILERI.csv")
    parser.add_argument("--ek", action="append", default=None)
    parser.add_argument("--profil", default="ucretsiz",
                        choices=sorted(butce.PROFILLER),
                        help="Bütçe profili: yuva, yedek ve tazelik ayarları")
    parser.add_argument("--yuva", type=int, default=None,
                        help=f"Soru başına en fazla kanıt yuvası (varsayılan {SORU_BASINA_YUVA})")
    parser.add_argument("--kategori-kaynak", type=Path,
                        default=HERE / "KATEGORI-KAYNAK.csv")
    parser.add_argument("--kategori-soru", type=Path, default=HERE / "KATEGORI-SORU.csv")
    parser.add_argument("--kaynak-alan", type=Path, default=HERE / "KAYNAK-ALAN.csv")
    parser.add_argument("--katalog", type=Path, default=HERE / "ADAY-KATALOG.csv")
    parser.add_argument("--surfaces", type=Path, default=HERE / "ARAMA-YUZEYLERI.csv")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    import build_source_fields as alanlar

    kaynak_alan = oku(args.kaynak_alan)
    olcum_alani: dict[str, set[str]] = collections.defaultdict(set)
    dogrulanan: dict[str, set[str]] = collections.defaultdict(set)
    izin: dict[str, set[str]] = collections.defaultdict(set)
    for r in kaynak_alan:
        izin[r["ad"]].add(r["izin_durumu"])
        if r["alan"] in alanlar.OLCUM_ALANLARI:
            olcum_alani[r["ad"]].add(r["alan"])
            if r["guven"] == "dogrulandi":
                dogrulanan[r["ad"]].add(r["alan"])

    kategori_kaynak = oku(args.kategori_kaynak)
    rol: dict[str, str] = {}
    for r in kategori_kaynak:
        if r["rol"] == "cekirdek" or r["kaynak"] not in rol:
            rol[r["kaynak"]] = r["rol"]

    veri = {
        "kategori_kaynak": kategori_kaynak,
        "kategori_soru": oku(args.kategori_soru),
        "olcum_alani": olcum_alani, "dogrulanan": dogrulanan, "izin": izin,
        "host": {r["ad"]: r["host"] for r in oku(args.katalog)},
        "metin_bayt": {r["ad"]: int(r["tam_metin_bayt"] or 0)
                       for r in oku(args.surfaces)},
        "rol": rol,
    }

    katman_olabilir = frozenset(
        r["kategori"] for r in oku(args.kategoriler)
        if r["tur"] == "kategori" and r["katman_olabilir"] == "evet")

    if args.kategori:
        kategori = args.kategori
        katmanlar = sorted(args.katman or [])
        ekler = sorted(args.ek or [])
    else:
        kategori, katmanlar, otomatik_ek, _ = hedefleri_bul(args.fikir, katman_olabilir)
        if args.katman:
            katmanlar = sorted(args.katman)
        ekler = sorted(args.ek) if args.ek else otomatik_ek

    yuva_siniri = (args.yuva if args.yuva is not None
                   else int(butce.profil(args.profil)["soru_basina_yuva"]))
    satirlar = paket_sec(args.fikir, kategori, ekler, veri, katmanlar,
                         yuva_siniri, args.profil)
    if args.out:
        with args.out.open("w", newline="", encoding="utf-8") as handle:
            yazici = csv.DictWriter(handle, fieldnames=list(satirlar[0]))
            yazici.writeheader()
            yazici.writerows(satirlar)

    kaynaklar = {r["birincil_kaynak"] for r in satirlar}
    zayif = sorted({r["soru_id"] for r in satirlar if r["yuva_sayisi"] < ASGARI_YUVA})
    print(json.dumps({
        "fikir": args.fikir, "profil": args.profil, "kategori": kategori,
        "katmanlar": katmanlar, "ekler": ekler,
        "soru": len({r["soru_id"] for r in satirlar}),
        "kanit_yuvasi": len(satirlar),
        "birincil_kaynak": len(kaynaklar),
        "tum_kaynak_yedeklerle": len(kaynaklar | {
            y.strip() for r in satirlar for y in r["yedekler"].split(",") if y.strip()}),
        "farkli_host": len({r["host"] for r in satirlar}),
        "tek_yuvali_soru": zayif,
        "yuva_siniri": yuva_siniri,
        "sinirin_eledigi_yuva": sum(
            int(r["mevcut_yuva"]) - int(r["yuva_sayisi"])
            for r in satirlar if r["yuva"] == "1" or r["yuva"] == 1),
        "cikti": str(args.out) if args.out else None,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
