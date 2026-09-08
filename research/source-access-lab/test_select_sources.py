from __future__ import annotations

import collections
import csv
import unittest
from pathlib import Path

import build_source_fields as alanlar
import select_sources as sec

HERE = Path(__file__).resolve().parent


def _veri() -> dict:
    def oku(ad):
        with (HERE / ad).open(encoding="utf-8") as h:
            return list(csv.DictReader(h))
    kaynak_alan = oku("KAYNAK-ALAN.csv")
    olcum, dog, izin = (collections.defaultdict(set) for _ in range(3))
    for r in kaynak_alan:
        izin[r["ad"]].add(r["izin_durumu"])
        if r["alan"] in alanlar.OLCUM_ALANLARI:
            olcum[r["ad"]].add(r["alan"])
            if r["guven"] == "dogrulandi":
                dog[r["ad"]].add(r["alan"])
    kategori_kaynak = oku("KATEGORI-KAYNAK.csv")
    rol = {}
    for r in kategori_kaynak:
        if r["rol"] == "cekirdek" or r["kaynak"] not in rol:
            rol[r["kaynak"]] = r["rol"]
    return {
        "kategori_kaynak": kategori_kaynak,
        "kategori_soru": oku("KATEGORI-SORU.csv"),
        "olcum_alani": olcum, "dogrulanan": dog, "izin": izin, "rol": rol,
        "host": {r["ad"]: r["host"] for r in oku("ADAY-KATALOG.csv")},
        "metin_bayt": {r["ad"]: int(r["tam_metin_bayt"] or 0)
                       for r in oku("ARAMA-YUZEYLERI.csv")},
    }


VERI = _veri()
FIKIR = "diyabet hastaları için mobil takip uygulaması"


class KategoriTespitiTests(unittest.TestCase):
    def test_bilinen_fikirler_beklenen_kategoriye_duser(self):
        for fikir, beklenen in (
                ("diyabet hastaları için mobil takip uygulaması", "mobil-uygulama"),
                ("muhasebeciler için fatura yazılımı", "b2b-web-yazilimi"),
                ("react için bir kütüphane", "gelistirici-araci"),
                ("mobil bulmaca oyunu", "oyun")):
            self.assertEqual(beklenen, sec.hedefleri_bul(fikir)[0], fikir)

    def test_katman_kurali_gorev1den_devralinir(self):
        """'mobil bulmaca oyunu' hem oyun hem mobil anahtari tasir. Gorev 1
        katman kurali ana kategorinin oyun, mobil-uygulama'nin katman
        oldugunu soyluyor; secim bunu yeniden icat etmez, devralir."""
        kategori, katmanlar, _ek, _p = sec.hedefleri_bul("mobil bulmaca oyunu")
        self.assertEqual("oyun", kategori)
        self.assertEqual(["mobil-uygulama"], katmanlar)

    def test_katman_kategorisi_tek_basina_ana_kategori_olabilir(self):
        kategori, katmanlar, _e, _p = sec.hedefleri_bul("diyabet takip uygulaması")
        self.assertEqual("mobil-uygulama", kategori)
        self.assertEqual([], katmanlar)

    def test_ek_paket_fikirden_tetiklenir(self):
        self.assertIn("saglik", sec.hedefleri_bul(FIKIR)[2])
        self.assertIn("fintech", sec.hedefleri_bul("fatura yazılımı")[2])

    def test_anahtar_yoksa_sessizce_varsayilana_dusmez(self):
        """Yanlis kategori butun secimi yanlis yapar; tahmin edilmemeli."""
        with self.assertRaises(SystemExit):
            sec.hedefleri_bul("zzzz qqqq")

    def test_turkce_harfler_eslesmeyi_bozmaz(self):
        self.assertEqual(sec.sadelestir("Sağlık"), sec.sadelestir("saglik"))
        self.assertEqual(sec.sadelestir("İSTANBUL"), sec.sadelestir("istanbul"))


class DeterminizmTests(unittest.TestCase):
    def test_ayni_fikir_ayni_paketi_verir(self):
        """Gorevin acik sarti: deterministik."""
        a = sec.paket_sec(FIKIR, "mobil-uygulama", ["saglik"], VERI)
        b = sec.paket_sec(FIKIR, "mobil-uygulama", ["saglik"], VERI)
        self.assertEqual(a, b)

    def test_ek_paket_sirasi_sonucu_degistirmez(self):
        a = sec.paket_sec(FIKIR, "mobil-uygulama", ["saglik", "fintech"], VERI)
        b = sec.paket_sec(FIKIR, "mobil-uygulama", ["fintech", "saglik"], VERI)
        self.assertEqual([r["birincil_kaynak"] for r in a],
                         [r["birincil_kaynak"] for r in b])


class BagimsizlikTests(unittest.TestCase):
    def setUp(self):
        self.satirlar = sec.paket_sec(FIKIR, "mobil-uygulama", ["saglik"], VERI)

    def test_bir_sorunun_yuvalari_farkli_gruplardan(self):
        """Ayni gruptan iki yuva, ayni olcumu iki kez saymaktir."""
        for soru, grp in self._soruya_gore().items():
            gruplar = [r["kaynak_grubu"] for r in grp]
            self.assertEqual(len(gruplar), len(set(gruplar)), soru)

    def test_bir_sorunun_birincil_kaynaklari_farkli_hostlarda(self):
        """Ayni host'tan iki kanit sahte dogrulama uretir."""
        for soru, grp in self._soruya_gore().items():
            hostlar = [r["host"] for r in grp if r["host"]]
            self.assertEqual(len(hostlar), len(set(hostlar)), soru)

    def test_yedekler_birincil_ile_ayni_gruptan(self):
        """Yedek bir alternatif olcum degil, ayni olcumun baska kapisidir."""
        grup_kaynak = collections.defaultdict(set)
        for r in VERI["kategori_kaynak"]:
            for g in r["kaynak_grubu"].split(" | "):
                grup_kaynak[g.strip()].add(r["kaynak"])
        for r in self.satirlar:
            for yedek in filter(None, (y.strip() for y in r["yedekler"].split(","))):
                self.assertIn(yedek, grup_kaynak[r["kaynak_grubu"]],
                              f"{r['soru_id']}/{yedek}")

    def _soruya_gore(self):
        d = collections.defaultdict(list)
        for r in self.satirlar:
            d[r["soru_id"]].append(r)
        return d


class SecimKalitesiTests(unittest.TestCase):
    def setUp(self):
        self.satirlar = sec.paket_sec(FIKIR, "mobil-uygulama", ["saglik"], VERI)

    def test_secilen_her_kaynak_gorev4_suzgecinden_gecer(self):
        """Olcum alani olmayan kaynak hicbir profilde pakete giremez ve
        hicbir profil 'yasak' ya da 'yol-yok' kaynagi kabul etmez.

        Profil yalniz tazeligi degistirir: ucretsiz arsiv kopyasini kabul
        eder, premium etmez. Izin sinirlari butce dugmesi degildir.
        """
        import butce_profilleri as butce
        for profil_adi in butce.PROFILLER:
            kabul = set(butce.kabul_edilen_izin(profil_adi))
            self.assertEqual(set(), kabul & {"yasak", "yol-yok"}, profil_adi)
            satirlar = sec.paket_sec(FIKIR, "mobil-uygulama", ["saglik"], VERI,
                                     profil_adi=profil_adi)
            for r in satirlar:
                ad = r["birincil_kaynak"]
                self.assertTrue(VERI["olcum_alani"].get(ad), ad)
                self.assertTrue(VERI["izin"][ad] & kabul, f"{profil_adi}/{ad}")

    def test_paket_envanterden_cok_kucuk(self):
        """Gorevin amaci: 636 kaynagi calistirmamak."""
        kaynaklar = {r["birincil_kaynak"] for r in self.satirlar}
        self.assertLess(len(kaynaklar), 30)
        self.assertGreater(len(kaynaklar), 5)

    def test_kategorinin_her_sorusu_pakette(self):
        beklenen = {r["soru_id"] for r in VERI["kategori_soru"]
                    if r["kategori"] in {"mobil-uygulama", "saglik", "ortak"}}
        self.assertEqual(beklenen, {r["soru_id"] for r in self.satirlar})

    def test_yuva_ici_sira_olculen_metne_gore(self):
        """Google Play'den 2.9 MB, F-Droid'den 13 KB metin alinmis; sira bunu
        yansitmali. Kriter olculmus bir degerdir, tahmini populerlik degil."""
        magaza = [r for r in self.satirlar
                  if r["kaynak_grubu"] == "Mobil uygulama mağazaları"]
        self.assertTrue(magaza)
        for r in magaza:
            self.assertEqual("Google Play Store", r["birincil_kaynak"])
            self.assertNotIn("F-Droid", r["yedekler"])

    def test_hic_icerik_donmemis_kaynak_birincil_secilmez(self):
        """API'si olsa bile elimizde ondan gelmis tek satir yoksa one alinmaz."""
        for r in self.satirlar:
            ad = r["birincil_kaynak"]
            self.assertTrue(VERI["metin_bayt"].get(ad, 0) or VERI["dogrulanan"].get(ad),
                            f"{r['soru_id']}/{ad}")

    def test_kesilen_yuva_sessizce_kaybolmaz(self):
        """Gorev 4'un ilkesi: yapilmayan sey icin neden yazilir. Yuva siniri
        bir yuvayi elerse hangi gruplarin elendigi satirda gorunur kalmali."""
        for r in self.satirlar:
            self.assertGreaterEqual(int(r["mevcut_yuva"]), int(r["yuva_sayisi"]))
            if int(r["mevcut_yuva"]) > int(r["yuva_sayisi"]):
                self.assertTrue(r["kullanilmayan_yuva"].strip(), r["soru_id"])
            else:
                self.assertEqual("", r["kullanilmayan_yuva"], r["soru_id"])

    def test_sinir_yukselince_daha_cok_yuva_acilir(self):
        dar = sec.paket_sec(FIKIR, "mobil-uygulama", ["saglik"], VERI,
                            soru_basina_yuva=2)
        genis = sec.paket_sec(FIKIR, "mobil-uygulama", ["saglik"], VERI,
                              soru_basina_yuva=6)
        self.assertLess(len(dar), len(genis))

    def test_elenen_yuva_kullanilanla_ayni_grup_degil(self):
        for r in self.satirlar:
            elenen = {g.strip() for g in r["kullanilmayan_yuva"].split(",") if g.strip()}
            self.assertNotIn(r["kaynak_grubu"], elenen, r["soru_id"])

    def test_her_satir_gerekce_tasir(self):
        for r in self.satirlar:
            self.assertTrue(r["neden_secildi"].strip(), r["soru_id"])
            self.assertIn("kanıt yuvası", r["neden_secildi"])


if __name__ == "__main__":
    unittest.main()
