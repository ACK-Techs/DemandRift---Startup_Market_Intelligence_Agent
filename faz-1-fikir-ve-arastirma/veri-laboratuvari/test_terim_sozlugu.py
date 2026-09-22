from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import query_templates as sablon
import terim_sozlugu as sozluk

HERE = Path(__file__).resolve().parent

# Testler ага cikmaz: butun senaryolar onbellek ya da saf fonksiyonlar
# uzerinden kurulur. Ag bagimli test, determinizm sartini bozar.
ORNEK_WIKITEXT = """
==Turkish==
===Noun===
# {{l|en|date}} (pre-arranged social meeting), [[rendezvous]]
# [[appointment]]; {{gloss|tryst}}
==English==
===Noun===
# an unrelated english sense
"""


class AyristirmaTests(unittest.TestCase):
    def test_sablon_cozulur(self):
        """{{l|en|date}} bir aday degil, 'date' adayidir."""
        adaylar = sozluk.adaylari_ayikla(ORNEK_WIKITEXT)
        self.assertIn("date", adaylar)
        self.assertNotIn("l|en|date", adaylar)

    def test_parantezli_aciklama_aday_sayilmaz(self):
        adaylar = sozluk.adaylari_ayikla(ORNEK_WIKITEXT)
        self.assertNotIn("pre-arranged social meeting", adaylar)
        for a in adaylar:
            self.assertNotIn("(", a)

    def test_virgul_ve_noktali_virgul_boler(self):
        adaylar = sozluk.adaylari_ayikla(ORNEK_WIKITEXT)
        for beklenen in ("date", "rendezvous", "appointment", "tryst"):
            self.assertIn(beklenen, adaylar)

    def test_ingilizce_bolum_karismaz(self):
        adaylar = sozluk.adaylari_ayikla(ORNEK_WIKITEXT)
        self.assertNotIn("an unrelated english sense", adaylar)

    def test_turkce_bolumu_yoksa_bos_doner(self):
        self.assertEqual([], sozluk.adaylari_ayikla("==English==\n# only english"))


class OrtusmeKorumasiTests(unittest.TestCase):
    def test_tam_kapsayan_baslik_kabul_edilir(self):
        self.assertEqual(1.0, sozluk.ortusme_orani("kan şekeri", "Kan şekeri seviyesi"))

    def test_alakasiz_baslik_sifir_verir(self):
        """Wikipedia aramasi ilgisiz makaleye dusebilir; koruma bunu yakalar."""
        self.assertEqual(0.0, sozluk.ortusme_orani("randevu sistemi", "Sağlık.NET"))

    def test_yarim_eslesme_esigin_altinda(self):
        """'diyabet takip' -> 'Diyabet' kabul edilirse 'takip' sessizce duser."""
        oran = sozluk.ortusme_orani("diyabet takip", "Diyabet")
        self.assertLess(oran, sozluk.ASGARI_ORTUSMe)

    def test_turkce_harf_ortusmeyi_bozmaz(self):
        self.assertEqual(1.0, sozluk.ortusme_orani("şeker", "Şeker"))


class KategoriDiliTests(unittest.TestCase):
    def setUp(self):
        with (HERE / "KATEGORI-KAYNAK.csv").open(encoding="utf-8") as handle:
            self.kategori_kaynak = list(csv.DictReader(handle))

    def test_yerel_hizmet_dilinde_randevu_karsiligi_var(self):
        """Belirsizligi bu kume cozuyor: 'date' degil 'appointment'."""
        dil = sozluk.kategori_dili(self.kategori_kaynak, "yerel-hizmet",
                                   sablon.GRUP_DILI)
        self.assertIn("appointment", dil)
        self.assertNotIn("date", dil)

    def test_kategoriler_farkli_dil_uretir(self):
        mobil = sozluk.kategori_dili(self.kategori_kaynak, "mobil-uygulama",
                                     sablon.GRUP_DILI)
        yerel = sozluk.kategori_dili(self.kategori_kaynak, "yerel-hizmet",
                                     sablon.GRUP_DILI)
        self.assertNotEqual(mobil, yerel)

    def test_bilinmeyen_kategori_bos_kume(self):
        self.assertEqual(set(), sozluk.kategori_dili(
            self.kategori_kaynak, "olmayan-kategori", sablon.GRUP_DILI))


class OnbellekTests(unittest.TestCase):
    def test_onbellekteki_terim_aga_cikmaz(self):
        onbellek = {"diyabet|mobil-uygulama": {
            "orijinal": "diyabet", "kullanilan": "diabetes", "guven": "yuksek",
            "cozen_katman": "wikipedia", "adaylar": [], "iz": "test", "uyari": ""}}
        # cevrimdisi=False olmasina ragmen ag cagrisi yapilmamali; onbellek once.
        kayit = sozluk.terim_cevir("diyabet", "mobil-uygulama", set(), onbellek)
        self.assertTrue(kayit["onbellekten"])
        self.assertEqual("diabetes", kayit["kullanilan"])

    def test_cevrimdisi_eksik_terimde_cokmez(self):
        kayit = sozluk.terim_cevir("bilinmeyenkelime", "mobil-uygulama", set(),
                                   {}, cevrimdisi=True)
        self.assertEqual("bilinmeyenkelime", kayit["kullanilan"])
        self.assertEqual("yok", kayit["guven"])
        self.assertTrue(kayit["uyari"])

    def test_onbellek_yazilip_okunur(self):
        with tempfile.TemporaryDirectory() as gecici:
            yol = Path(gecici) / "onbellek.json"
            sozluk.onbellek_yaz({"a|b": {"kullanilan": "x"}}, yol)
            self.assertEqual({"a|b": {"kullanilan": "x"}}, sozluk.onbellek_yukle(yol))

    def test_repodaki_onbellek_gecerli(self):
        veri = sozluk.onbellek_yukle()
        self.assertTrue(veri, "önbellek boş; derleme ağa bağımlı kalır")
        for anahtar, kayit in veri.items():
            self.assertIn("|", anahtar)
            for alan in ("orijinal", "kullanilan", "guven", "cozen_katman", "iz"):
                self.assertIn(alan, kayit, anahtar)

    def test_her_kayit_iz_tasir(self):
        """Ceviri kararinin nereden geldigi denetlenebilir olmali."""
        for anahtar, kayit in sozluk.onbellek_yukle().items():
            self.assertTrue(kayit["iz"].strip(), anahtar)

    def test_cozulemeyen_kayit_uyari_tasir(self):
        for anahtar, kayit in sozluk.onbellek_yukle().items():
            if kayit["guven"] in ("yok", "orta"):
                self.assertTrue(kayit["uyari"].strip(), anahtar)


class PazarTests(unittest.TestCase):
    def test_turkiye_pazarinda_ceviri_gerekmez(self):
        """Fikir Turkce, sorgu Turkce; sozluge hic gidilmez."""
        self.assertEqual("hayir", sablon.PAZAR["TR"]["ceviri_gerekir"])

    def test_ingilizce_pazarda_ceviri_gerekir(self):
        self.assertEqual("evet", sablon.PAZAR["US"]["ceviri_gerekir"])


if __name__ == "__main__":
    unittest.main()
