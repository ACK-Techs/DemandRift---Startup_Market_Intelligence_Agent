"""Ayni tasarimi iki butce seviyesinde calistiran profiller.

Akla ilk gelen premium tasarimi sudur: "ucretsizde 10 kaynak, premiumda 50
kaynak". Bu yanlistir ve nedenini kendi olcumumuz gosterdi. Gorev 5'te duz bir
"en yuksek puanli 12 kaynagi sec" denendiginde cikan paketin dokuzu uygulama
magazasiydi; dokuzu da ayni seyi ayni yontemle olcuyordu. **Kaynak sayisini
artirmak kanit artirmaz**, ayni bilgiyi daha cok kez okur. Boyle bir premium,
para odeyen kullaniciya gurultu satar.

Profiller bu yuzden **sayiyi degil derinligi** degistirir. Alti eksende:

1. **Kanit derinligi** — soru basina kac bagimsiz olcme yontemi. Gorev 5 bunu
   uce sinirliyordu ve diyabet orneginde 5 yuva bu sinir yuzunden elenmisti.
2. **Yedek zinciri** — birincil kaynak yanit vermezse kac alternatif denenir.
3. **Sorgu genisligi** — gorev 6'nin niyet ekleri coktur ("problem", "issue",
   "not working"); ucretsiz birini, premium birkacini calistirir.
4. **Dogrulama** — gorev 4'te olcum alanlarinin 10'u dogrulanmis, 1378'i
   beyandir. Premium alani tasiyan sayfayi cekip dogrular.
5. **Tazelik** — yalniz arsiv kopyasi olan kaynak ucretsizde kabul edilir,
   premiumda canli erisim aranir.
6. **Pazar kapsami** — ucretsiz tek pazar, premium karsilastirmali.

**"Kontrolsuz" olmamak** cumlenin ikinci sartidir. Premium daha derindir ama
sinirsiz degildir: butcesi vardir, deterministiktir ve **politikayi gevsetmez.**
Asagidaki ``DEGISMEYEN`` kurallari iki profilde de aynidir; premium derinlik
satar, izin satmaz.
"""
from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------
# Iki profilde de ayni kalan kurallar. Bunlar butce dugmesi DEGILDIR: para
# odeyerek gevsetilemezler. Testler bunu korur.
# --------------------------------------------------------------------------
DEGISMEYEN: dict[str, str] = {
    "robots_yasagi": "robots.txt kapatan kaynak hiçbir profilde çalıştırılmaz",
    "bot_korumasi": "tarayıcı taklidi, UA rotasyonu ve engel aşma hiçbir profilde yok",
    "determinizm": "aynı fikir aynı profilde her zaman aynı sonucu verir",
    "kaynak_suzgeci": "ölçüm alanı ve izinli yolu olmayan kaynak hiçbir profilde havuza girmez",
    "bagimsizlik": "bir sorunun yuvaları her profilde farklı grup ve host'tan gelir",
    "gerekce": "kullanılmayan yuva ve çevrilemeyen terim her profilde gerekçesiyle yazılır",
}

# --------------------------------------------------------------------------
# Butce dugmeleri. Her degerin yaninda neden o oldugu yazili.
# --------------------------------------------------------------------------
PROFILLER: dict[str, dict[str, Any]] = {
    "ucretsiz": {
        "aciklama": "Karar vermeye yetecek kanıt — görev 5 ve 6'nın kurduğu tasarım",
        # Gorev 5'te gerekcesi yazili: uc farkli olcme yontemi bir soruyu
        # desteklemeye yeter. Ucretsiz profil o tasarimin kendisidir.
        "soru_basina_yuva": 3,
        # Birincil + iki yedek.
        "yuva_basina_yedek": 2,
        # Niyet ekinin ilki kullanilir.
        "niyet_eki_sayisi": 1,
        # Arsiv kopyasi kabul edilir: veri eski olabilir ama bedava.
        "arsiv_kabul": True,
        # Alan dogrulamasi icin ek cekim yapilmaz; beyan yeterli sayilir.
        "alan_dogrulama": False,
        # Tek pazar.
        "pazarlar": ("TR",),
        # Kaba istek butcesi; bulk_site_access_lab'in global_budget'ina karsilik.
        "istek_butcesi": 120,
    },
    "premium": {
        "aciklama": "Aynı sorulara daha çok bağımsız açı ve doğrulanmış kanıt",
        # Dordoncu ve besinci olcme yontemi gercek aci ekler: diyabet
        # orneginde rakip-kim sorusunun 6 yuvasi vardi, ucretsizde 3'u
        # kullaniliyordu.
        "soru_basina_yuva": 5,
        # Birincil bot korumasi verirse zincir daha derin yurutulur.
        "yuva_basina_yedek": 4,
        # Ayni kaynak birden fazla niyet ekiyle taranir.
        "niyet_eki_sayisi": 3,
        # Yalniz arsiv kopyasi olan kaynak premiumda birincil secilmez;
        # tazelik bir kalite boyutudur.
        "arsiv_kabul": False,
        # Alani tasiyan sayfa cekilip alan dogrulanir.
        "alan_dogrulama": True,
        # Iki pazar karsilastirmali derlenir.
        "pazarlar": ("TR", "US"),
        # Daha buyuk, ama sinirli. 'Kontrolsuz' olmamanin karsiligi budur.
        "istek_butcesi": 600,
    },
}

# Premium'un ucretsizden asagi olamayacagi dugmeler. Bir profil duzenlenirken
# yanlislikla ters cevrilirse test duser.
ARTAN_DUGMELER = ("soru_basina_yuva", "yuva_basina_yedek", "niyet_eki_sayisi",
                  "istek_butcesi")


def profil(ad: str) -> dict[str, Any]:
    if ad not in PROFILLER:
        raise SystemExit(f"bilinmeyen profil: {ad}; seçenekler: {sorted(PROFILLER)}")
    return PROFILLER[ad]


def kabul_edilen_izin(ad: str) -> tuple[str, ...]:
    """Profilin birincil kaynak olarak kabul ettigi izin siniflari.

    Iki profil de **yalniz izinli yollari** kabul eder; fark tazeliktedir,
    izinde degil. Yasak ve yolu olmayan kaynak hicbir profilde girmez.

    Havuz iki profilde de aynidir. Tazelik farki **siralamada** uygulanir:
    premiumda yalniz arsiv kopyasi olan kaynak birincil secilmez, yedege
    duser (bkz. ``arsiv_birincil_olabilir``).

    Havuzu daraltmak cazip gorunur ama yanlistir: o zaman premium,
    ucretsizde bulunan bir kanit acisini **kaybederdi**. Para odeyen
    kullanici bir sey kaybetmemeli -- premium ucretsizin ustune eklemeli.
    """
    return ("api-acik", "robots-izinli", "arsiv-kopyasi")


def arsiv_birincil_olabilir(ad: str) -> bool:
    """Yalniz arsiv kopyasi olan kaynak bu profilde birincil olabilir mi.

    Ucretsizde olabilir: veri eski ama bedava ve bir seyden iyidir.
    Premiumda olamaz: tazelik bir kalite boyutudur. Kaynak havuzdan
    cikmaz, yedege duser -- aci kaybolmaz.
    """
    return bool(profil(ad)["arsiv_kabul"])


def fark_ozeti(ucretsiz: dict[str, Any], premium: dict[str, Any]) -> dict[str, Any]:
    """Premium'un ne ekledigini olcer.

    Kritik olcum ``aci_basina_kaynak``: premium kaynak sayisini artiriyorsa
    ama bagimsiz aci sayisini artirmiyorsa, tasarim 'daha cok site
    calistirma'ya kaymis demektir. Oran dusmelidir.
    """
    def oran(veri: dict[str, Any]) -> float:
        return veri["kaynak"] / veri["yuva"] if veri["yuva"] else 0.0
    return {
        "ek_yuva": premium["yuva"] - ucretsiz["yuva"],
        "ek_kaynak": premium["kaynak"] - ucretsiz["kaynak"],
        "ek_grup": premium["grup"] - ucretsiz["grup"],
        "ucretsiz_aci_basina_kaynak": round(oran(ucretsiz), 3),
        "premium_aci_basina_kaynak": round(oran(premium), 3),
        "derinlik_kazanci": premium["yuva"] - ucretsiz["yuva"] > 0,
        "sayiya_kaymadi": oran(premium) <= oran(ucretsiz) + 1e-9,
    }


# --------------------------------------------------------------------------
# Karsilastirma: ayni fikri iki profilde calistirip farki olcer.
# --------------------------------------------------------------------------
def _olc(satirlar: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "yuva": len(satirlar),
        "kaynak": len({r["birincil_kaynak"] for r in satirlar}),
        "grup": len({r["kaynak_grubu"] for r in satirlar}),
        "host": len({r["host"] for r in satirlar if r["host"]}),
        "yedekli_kaynak": len({r["birincil_kaynak"] for r in satirlar} | {
            y.strip() for r in satirlar for y in r["yedekler"].split(",") if y.strip()}),
        "elenen_yuva": sum(int(r["mevcut_yuva"]) - int(r["yuva_sayisi"])
                           for r in satirlar if str(r["yuva"]) == "1"),
    }


def main() -> int:
    import argparse
    import csv
    import json
    from pathlib import Path as _Path

    import select_sources as sec

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fikir", action="append", default=None)
    parser.add_argument("--out", type=_Path,
                        default=_Path(__file__).resolve().parent / "BUTCE-KARSILASTIRMA.csv")
    args = parser.parse_args()
    fikirler = args.fikir or [
        "diyabet hastaları için mobil takip uygulaması",
        "muhasebeciler için fatura yazılımı",
        "yerel esnaf için randevu uygulaması",
    ]

    here = _Path(__file__).resolve().parent
    def oku(ad: str) -> list[dict[str, str]]:
        with (here / ad).open(encoding="utf-8") as h:
            return list(csv.DictReader(h))

    import build_source_fields as alanlar
    import collections
    kaynak_alan = oku("KAYNAK-ALAN.csv")
    olcum, dog, izin = (collections.defaultdict(set) for _ in range(3))
    for r in kaynak_alan:
        izin[r["ad"]].add(r["izin_durumu"])
        if r["alan"] in alanlar.OLCUM_ALANLARI:
            olcum[r["ad"]].add(r["alan"])
            if r["guven"] == "dogrulandi":
                dog[r["ad"]].add(r["alan"])
    kategori_kaynak = oku("KATEGORI-KAYNAK.csv")
    rol: dict[str, str] = {}
    for r in kategori_kaynak:
        if r["rol"] == "cekirdek" or r["kaynak"] not in rol:
            rol[r["kaynak"]] = r["rol"]
    veri = {
        "kategori_kaynak": kategori_kaynak,
        "kategori_soru": oku("KATEGORI-SORU.csv"),
        "olcum_alani": olcum, "dogrulanan": dog, "izin": izin, "rol": rol,
        "host": {r["ad"]: r["host"] for r in oku("ADAY-KATALOG.csv")},
        "metin_bayt": {r["ad"]: int(r["tam_metin_bayt"] or 0)
                       for r in oku("ARAMA-YUZEYLERI.csv")},
    }
    katman_olabilir = frozenset(
        r["kategori"] for r in oku("URUN-KATEGORILERI.csv")
        if r["tur"] == "kategori" and r["katman_olabilir"] == "evet")

    satirlar: list[dict[str, Any]] = []
    for fikir in fikirler:
        kategori, katmanlar, ekler, _p = sec.hedefleri_bul(fikir, katman_olabilir)
        olcumler = {}
        for ad in ("ucretsiz", "premium"):
            paket = sec.paket_sec(fikir, kategori, ekler, veri, katmanlar,
                                  int(PROFILLER[ad]["soru_basina_yuva"]), ad)
            olcumler[ad] = _olc(paket)
        fark = fark_ozeti(olcumler["ucretsiz"], olcumler["premium"])
        for ad in ("ucretsiz", "premium"):
            satirlar.append({
                "fikir": fikir, "kategori": kategori, "profil": ad,
                **olcumler[ad],
                "yuva_siniri": PROFILLER[ad]["soru_basina_yuva"],
                "yedek_siniri": PROFILLER[ad]["yuva_basina_yedek"],
                "arsiv_kabul": "evet" if PROFILLER[ad]["arsiv_kabul"] else "hayir",
                "niyet_eki_sayisi": PROFILLER[ad]["niyet_eki_sayisi"],
                "istek_butcesi": PROFILLER[ad]["istek_butcesi"],
                "aci_basina_kaynak": round(
                    olcumler[ad]["kaynak"] / olcumler[ad]["yuva"], 3)
                if olcumler[ad]["yuva"] else 0,
                "premium_ek_yuva": fark["ek_yuva"] if ad == "premium" else "",
                "premium_ek_kaynak": fark["ek_kaynak"] if ad == "premium" else "",
                "sayiya_kaymadi": ("evet" if fark["sayiya_kaymadi"] else "hayir")
                if ad == "premium" else "",
            })

    with args.out.open("w", newline="", encoding="utf-8") as h:
        yazici = csv.DictWriter(h, fieldnames=list(satirlar[0]))
        yazici.writeheader()
        yazici.writerows(satirlar)

    prem = [r for r in satirlar if r["profil"] == "premium"]
    print(json.dumps({
        "cikti": str(args.out), "fikir": len(fikirler),
        "premium_ek_yuva_toplam": sum(int(r["premium_ek_yuva"]) for r in prem),
        "premium_ek_kaynak_toplam": sum(int(r["premium_ek_kaynak"]) for r in prem),
        "her_fikirde_sayiya_kaymadi": all(r["sayiya_kaymadi"] == "evet" for r in prem),
        "degismeyen_kural": len(DEGISMEYEN),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
