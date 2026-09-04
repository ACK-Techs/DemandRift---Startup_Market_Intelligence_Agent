from __future__ import annotations

import collections
import csv
import unittest
from pathlib import Path

import build_source_fields as alan

HERE = Path(__file__).resolve().parent


class SozlukTests(unittest.TestCase):
    def test_kullanilan_her_alan_tanimli(self):
        kullanilan = {a for alanlar in alan.GRUP_ALANLARI.values() for a in alanlar}
        kullanilan |= {a for alanlar in alan.KAYNAK_ALAN_ISTISNASI.values() for a in alanlar}
        self.assertEqual(set(), kullanilan - set(alan.ALANLAR))

    def test_tanimli_her_alan_kullaniliyor(self):
        """Kullanilmayan alan tanimi olu sozluktur; karsilastirmayi yaniltir."""
        kullanilan = {a for alanlar in alan.GRUP_ALANLARI.values() for a in alanlar}
        kullanilan |= {a for alanlar in alan.KAYNAK_ALAN_ISTISNASI.values() for a in alanlar}
        self.assertEqual(set(), set(alan.ALANLAR) - kullanilan)

    def test_her_grubun_alani_tanimli(self):
        with (HERE / "KATEGORI-KAYNAK.csv").open(encoding="utf-8") as handle:
            gruplar = {g.strip() for r in csv.DictReader(handle)
                       for g in r["kaynak_grubu"].split(" | ")}
        self.assertEqual(set(), gruplar - set(alan.GRUP_ALANLARI))

    def test_istisna_kaynaklari_envanterde_var(self):
        with (HERE / "KAYNAK-DEFTERI.csv").open(encoding="utf-8") as handle:
            envanter = {r["ad"] for r in csv.DictReader(handle)}
        self.assertEqual(set(), set(alan.KAYNAK_ALAN_ISTISNASI) - envanter)

    def test_gorev2nin_sayisal_kanit_dedigi_grupta_olcum_alani_var(self):
        """Gorev 2 bu gruplar icin sayilabilir kanit tanimlamis; alan eslemesi
        onu tasimazsa iki dosya birbiriyle celisir.

        Gorev 2'nin kendi ifadeleri: akademik -> 'yillik yayin sayisinin egrisi',
        sosyal aglar -> 'topluluklar ve uye sayilari', haber -> 'yatirim
        turlarinin yillara gore sayisi', Turkiye -> 'yillara gore dagilimi'.
        """
        for grup in ("Akademik araştırma ve bilimsel yayınlar",
                     "Sosyal ağlar ve açık topluluklar",
                     "Haber, basın ve sektör yayınları",
                     "Türkiye startup ve teknoloji ekosistemi"):
            self.assertTrue(
                set(alan.GRUP_ALANLARI[grup]) & alan.OLCUM_ALANLARI, grup)

    def test_mevzuat_grubu_sayisal_alan_tasimaz(self):
        """Regulasyon kaynaklarinin kaniti baglayici metindir, sayi degil --
        oraya sayisal alan eklemek kanit tanimini bozar."""
        self.assertFalse(
            set(alan.GRUP_ALANLARI["Regülasyon ve hukuk kaynakları"])
            & alan.OLCUM_ALANLARI)

    def test_esleme_hedefleri_sozlukte(self):
        """Artefakttan kanonik alana esleme, sozluk disina cikamaz."""
        for esleme in (alan.JSONLD_ALAN, alan.API_ALAN, alan.RSS_ALAN):
            self.assertEqual(set(), set(esleme.values()) - set(alan.ALANLAR))


class IzinTests(unittest.TestCase):
    def test_robots_yasagi_her_seyi_gecer(self):
        durum = alan.izin_durumu(
            {"sebep": "robots_disallowed"}, {"api_ucu": "https://x/api"},
            {"root_html"})
        self.assertEqual("yasak", durum)

    def test_api_ucu_varsa_api_acik(self):
        self.assertEqual("api-acik", alan.izin_durumu(
            {}, {"api_ucu": "https://x/api"}, {"root_html"}))

    def test_yalniz_arsiv_kopyasi_ayirt_edilir(self):
        """Arsivden gelen veri canli veriyle ayni sayilamaz."""
        self.assertEqual("arsiv-kopyasi", alan.izin_durumu(
            {}, {}, {"common_crawl_warc", "robots_preflight"}))

    def test_hicbir_yol_yoksa_yol_yok(self):
        self.assertEqual("yol-yok", alan.izin_durumu({}, {}, set()))

    def test_sitemap_de_canli_erisimdir(self):
        """Sitemap robots'tan gecip indi; izin verilmis bir yoldur."""
        self.assertEqual("robots-izinli", alan.izin_durumu(
            {}, {}, {"sitemap_xml", "robots_preflight"}))


class CiktiTests(unittest.TestCase):
    def setUp(self):
        with (HERE / "KAYNAK-ALAN.csv").open(encoding="utf-8") as handle:
            self.satirlar = list(csv.DictReader(handle))

    def test_her_alan_sozlukten(self):
        for r in self.satirlar:
            self.assertIn(r["alan"], alan.ALANLAR, r["ad"])

    def test_dogrulanan_satirin_izi_var(self):
        """Dogrulama iddiasi izi surulebilir olmali."""
        for r in self.satirlar:
            if r["guven"] == "dogrulandi":
                self.assertTrue(r["dogrulama_izi"].strip(), f"{r['ad']}/{r['alan']}")
                self.assertEqual("", r["neden_dogrulanmadi"], f"{r['ad']}/{r['alan']}")

    def test_beyan_satiri_gerekcesiz_kalmaz(self):
        """'beyan' etiketi tek basina savunmasizdir; neden dogrulanmadigi yazilmali."""
        for r in self.satirlar:
            if r["guven"] == "beyan":
                self.assertTrue(r["neden_dogrulanmadi"].strip(), f"{r['ad']}/{r['alan']}")

    def test_yasak_kaynakta_dogrulanmis_alan_olamaz(self):
        """robots kapaliysa hicbir sey indirilmedi; dogrulama imkansiz."""
        for r in self.satirlar:
            if r["izin_durumu"] == "yasak":
                self.assertEqual("beyan", r["guven"], r["ad"])

    def test_kaynak_alan_ikilisi_tekrar_etmez(self):
        say = collections.Counter((r["ad"], r["alan"]) for r in self.satirlar)
        tekrar = [k for k, v in say.items() if v > 1]
        self.assertEqual([], tekrar)

    def test_istisna_kaynak_grup_alanini_devralmaz(self):
        """Stack Overflow paket bagimliligi yayinlamaz; grup listesi ona uygulanmaz."""
        so = {r["alan"] for r in self.satirlar if r["ad"] == "Stack Overflow"}
        self.assertNotIn("bagimlilik_sayisi", so)
        self.assertNotIn("indirme_sayisi", so)
        self.assertIn("kullanici_sikayeti", so)

    def test_hizmet_ettigi_soru_gercek(self):
        with (HERE / "KATEGORI-SORU.csv").open(encoding="utf-8") as handle:
            sorular = {r["soru_id"] for r in csv.DictReader(handle)}
        for r in self.satirlar:
            for s in filter(None, (x.strip() for x in r["hizmet_ettigi_soru"].split(","))):
                self.assertIn(s, sorular, r["ad"])

    def test_sitenin_kendi_puani_olcum_sayilmaz(self):
        """Booksy'nin anasayfasindaki 4.9, Booksy uygulamasinin kendi puani --
        Booksy'de listelenen bir isletmenin puani degil. Olcum kaniti sayilamaz."""
        booksy = {r["alan"]: r for r in self.satirlar if r["ad"] == "Booksy"}
        self.assertEqual("beyan", booksy["puan"]["guven"])

    def test_kimlik_izli_satir_olcum_alani_dogrulamaz(self):
        for r in self.satirlar:
            if "(kimlik)" in r["dogrulama_izi"]:
                self.assertNotIn(r["alan"], alan.OLCUM_ALANLARI, f"{r['ad']}/{r['alan']}")

    def test_dogrulama_gercekten_calisiyor(self):
        """Hicbir satir dogrulanmadiysa artefakt taramasi bozulmus demektir."""
        dogru = [r for r in self.satirlar if r["guven"] == "dogrulandi"]
        self.assertGreater(len(dogru), 100)
        self.assertGreater(len({r["ad"] for r in dogru}), 50)


if __name__ == "__main__":
    unittest.main()
