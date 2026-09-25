"""AS-03 kabul kosullarini koruyan testler.

Kart: "Kaynak/alan/pazar/tarih ve limit farklarini goster; **metadata/arsiv
sonucunu tam veya guncel veri gibi sunma.** Cozulemeyen durumda kanitli engel
ve sonraki secenekleri Batuhan'a ilet."
"""
from __future__ import annotations

import csv
import datetime
import unittest
from pathlib import Path

import alternatif_fark as af

HERE = Path(__file__).resolve().parent


def oku(ad: str) -> list[dict[str, str]]:
    with (HERE / ad).open(encoding="utf-8") as tutamak:
        return list(csv.DictReader(tutamak))


class ArsivGuncelVeriDegildirTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arsiv = oku("AS03-ARSIV-YASI.csv")

    def test_her_arsiv_satiri_guncel_degil_diyor(self):
        for r in self.arsiv:
            self.assertEqual("hayır", r["guncel_veri_mi"], r["kaynak_adi"])

    def test_arsivin_kendi_tarihi_ayri_sutunda(self):
        for r in self.arsiv:
            self.assertTrue(r["arsiv_icerik_tarihi"].strip(), r["kaynak_adi"])
            self.assertNotEqual(r["arsiv_icerik_tarihi"], r["bizim_cekme_tarihimiz"],
                                r["kaynak_adi"])

    def test_yas_hesabi_dogru(self):
        for r in self.arsiv[:20]:
            a = datetime.date.fromisoformat(r["arsiv_icerik_tarihi"])
            self.assertGreater(int(r["yas_gun"]), 0, r["kaynak_adi"])
            self.assertLess(a, datetime.date.today(), r["kaynak_adi"])

    def test_eski_kopyalar_uyari_tasir(self):
        for r in self.arsiv:
            if int(r["yas_gun"]) >= af.TAZELIK_UYARI_GUNU:
                self.assertIn("ARŞİV", r["tazelik_uyarisi"], r["kaynak_adi"])
                self.assertIn("Güncel veri DEĞİLDİR", r["tazelik_uyarisi"])

    def test_tazelik_notu_esigi_uyguluyor(self):
        _g, eski = af.tazelik_notu("2025-02-12", "2026-09-25")
        self.assertIn("DEĞİLDİR", eski)
        _g2, yeni = af.tazelik_notu("2026-09-01", "2026-09-25")
        self.assertNotIn("DEĞİLDİR", yeni)
        self.assertIn("Canlı veri değildir", yeni)

    def test_tarihsiz_arsiv_yas_iddia_etmez(self):
        gun, not_ = af.tazelik_notu("", "2026-09-25")
        self.assertEqual(0, gun)
        self.assertEqual("", not_)


class FarkGosterilirTests(unittest.TestCase):
    """Kart: kaynak/alan/pazar/tarih ve limit farklarini goster."""

    @classmethod
    def setUpClass(cls):
        cls.fark = oku("AS03-FARK-MATRISI.csv")

    def test_kartin_istedigi_fark_sutunlari_var(self):
        for alan in ("alan_farki", "pazar_farki", "tazelik", "limit_farki",
                     "kalan_eksik"):
            self.assertIn(alan, self.fark[0], alan)

    def test_her_satir_kapananin_ne_verdigini_yaziyor(self):
        for r in self.fark:
            self.assertTrue(r["kapananin_verdigi"].strip(), r["kapanan_kaynak"])

    def test_satici_sitesi_sikayet_vermez_uyarisi(self):
        satici = [r for r in self.fark if r["alan_farki"].startswith("SATICI")]
        self.assertTrue(satici, "satıcı sitesi ayrımı yapılmamış")
        for r in satici:
            self.assertIn("VERMEZ", r["alan_farki"], r["alternatif"])
            self.assertTrue(r["kalan_eksik"].strip(), r["alternatif"])

    def test_alternatifi_olmayan_acikca_yaziyor(self):
        yok = [r for r in self.fark if r["alternatif"] == "(bulunamadı)"]
        self.assertTrue(yok, "alternatifi bulunamayan kayıt yok")
        for r in yok:
            self.assertIn("alternatif yok", r["alan_farki"])
            self.assertTrue(r["kalan_eksik"].strip())

    def test_katalogda_olmayan_alternatif_isaretli(self):
        for r in self.fark:
            if r["alternatif_id"].startswith("("):
                self.assertIn("Batuhan", r["alternatif_id"], r["alternatif"])


class SonrakiSeceneklerIletilirTests(unittest.TestCase):
    """Kart: cozulemeyen durumda kanitli engel ve sonraki secenekleri ilet."""

    @classmethod
    def setUpClass(cls):
        cls.fark = oku("AS03-FARK-MATRISI.csv")

    def test_her_satir_sonraki_secenek_tasir(self):
        for r in self.fark:
            self.assertTrue(r["sonraki_secenekler"].strip(), r["kapanan_kaynak"])

    def test_secenekler_zorlama_icermiyor(self):
        yasak = ("captcha", "user-agent rot", "tarayıcı taklidi", "bypass", "aşarak")
        for r in self.fark:
            for kelime in yasak:
                self.assertNotIn(kelime, r["sonraki_secenekler"].casefold(),
                                 r["kapanan_kaynak"])

    def test_politika_engelinde_karar_caglarda(self):
        politika = [r for r in self.fark if "robots" in r["kapanma_sebebi"]]
        self.assertTrue(politika)
        for r in politika:
            self.assertIn("Çağlar", r["sonraki_secenekler"], r["kapanan_kaynak"])


class RaporTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metin = (HERE / "AS03-ALTERNATIF-FARKI.md").read_text(encoding="utf-8")

    def test_rapor_arsivin_iki_tarihini_ayiriyor(self):
        self.assertIn("iki tarihi", self.metin)
        self.assertIn("arsiv_icerik_tarihi", self.metin)
        self.assertIn("bizim_cekme_tarihimiz", self.metin)

    def test_rapor_arsivi_guncel_sunmadigini_soyluyor(self):
        self.assertIn("Arşiv sonucu tam ya da güncel veri gibi sunulamaz", self.metin)

    def test_rapor_alternatif_bulunamayani_gizlemiyor(self):
        self.assertIn("Alternatifi bulunamayanlar", self.metin)

    def test_rapor_3_2_esigini_karistirmiyor(self):
        self.assertIn("Faz 3'e ait", self.metin)

    def test_rapor_alternatif_yoklugunu_pazar_sonucu_saymiyor(self):
        self.assertIn("talep olmadığını göstermez", self.metin)


if __name__ == "__main__":
    unittest.main()
