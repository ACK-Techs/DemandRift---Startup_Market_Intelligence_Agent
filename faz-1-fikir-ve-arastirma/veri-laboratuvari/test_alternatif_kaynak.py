"""Alternatif kaynak aramasinin kurallarini koruyan testler."""
from __future__ import annotations

import csv
import hashlib
import unittest
from pathlib import Path

import alternatif_kaynak as alt

HERE = Path(__file__).resolve().parent


def oku(ad: str) -> list[dict[str, str]]:
    with (HERE / ad).open(encoding="utf-8") as tutamak:
        return list(csv.DictReader(tutamak))


class IlgililikTests(unittest.TestCase):
    """HTTP 200 ilgili icerik demek degildir."""

    def test_nise_ozgu_kelimeler_relevant_yapar(self):
        metin = "x" * 400 + " salon barber appointment randevu stylist"
        self.assertEqual("relevant", alt.ilgililik(metin, "F09")[0])

    def test_ilgisiz_icerik_relevant_sayilmaz(self):
        """SourceForge 19 bin karakter dondurdu ama konu Kubernetes idi."""
        metin = "x" * 400 + " Kubernetes orchestration multi-cloud crypto pricing"
        self.assertEqual("irrelevant", alt.ilgililik(metin, "F09")[0])

    def test_tek_isaret_belirsiz_birakir(self):
        metin = "x" * 400 + " salon"
        self.assertEqual("uncertain", alt.ilgililik(metin, "F09")[0])

    def test_navigasyon_sayilmaz(self):
        """Sayfanin ilk bolumu menudur; ilgililik govdeden okunur."""
        self.assertEqual("irrelevant",
                         alt.ilgililik("salon barber appointment " + "z" * 900, "F09")[0])


class KullanilabilirlikUcTestiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.satirlar = oku("AS01-ALTERNATIF-KAYNAK.csv")

    def test_kullanilabilir_ucunu_birden_gecer(self):
        for r in self.satirlar:
            if r["kullanilabilir_mi"] == "evet":
                self.assertEqual("ok", r["erisim"], r["aday"])
                self.assertIn(r["icerik"], ("gercek-icerik", "api-yaniti"), r["aday"])
                self.assertEqual("relevant", r["ilgililik"], r["aday"])

    def test_kullanilamayan_neden_tasir(self):
        for r in self.satirlar:
            if r["kullanilabilir_mi"] == "hayir":
                self.assertTrue(r["neden_kullanilamaz"].strip(), r["aday"])

    def test_200_donen_ilgisiz_sayfa_kullanilabilir_degil(self):
        for r in self.satirlar:
            if r["erisim"] == "ok" and r["ilgililik"] != "relevant":
                self.assertEqual("hayir", r["kullanilabilir_mi"], r["aday"])


class SourceIdUydurulmazTests(unittest.TestCase):
    """RULES.md: modelin uydurdugu source_id reddedilir."""

    @classmethod
    def setUpClass(cls):
        cls.satirlar = oku("AS01-ALTERNATIF-KAYNAK.csv")
        cls.katalog = {r["source_id"] for r in oku("VERI-ENVANTERI.csv")}

    def test_verilen_her_source_id_katalogda_var(self):
        for r in self.satirlar:
            if r["source_id"] != "(katalogda yok)":
                self.assertIn(r["source_id"], self.katalog, r["aday"])

    def test_katalogda_olmayan_oneri_olarak_isaretli(self):
        for r in self.satirlar:
            if r["source_id"] == "(katalogda yok)":
                self.assertIn("öneri", r["katalog_durumu"])
                self.assertIn("Batuhan", r["katalog_durumu"])


class PolitikaKorunurTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.satirlar = oku("AS01-ALTERNATIF-KAYNAK.csv")

    def test_robots_engeli_asilmamis(self):
        for r in self.satirlar:
            if r["erisim"].startswith("robots"):
                self.assertEqual("", r["artefakt"], r["aday"])
                self.assertIn("aşılmaz", r["neden_kullanilamaz"])

    def test_bot_korumasi_zorlanmamis(self):
        for r in self.satirlar:
            if r["erisim"] == "challenge":
                self.assertEqual("", r["artefakt"], r["aday"])

    def test_basarili_deneme_kanit_birakir(self):
        for r in self.satirlar:
            if r["erisim"] != "ok":
                continue
            self.assertEqual(64, len(r["artefakt"]), r["aday"])
            yol = HERE / r["artefakt_dosya"]
            self.assertTrue(yol.exists(), r["aday"])
            self.assertEqual(r["artefakt"],
                             hashlib.sha256(yol.read_bytes()).hexdigest(), r["aday"])


class RaporTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metin = (HERE / "AS01-ALTERNATIF-RAPOR.md").read_text(encoding="utf-8")

    def test_rapor_ilgisizlik_dersini_yaziyor(self):
        self.assertIn("HTTP 200 ilgili içerik demek değildir", self.metin)
        self.assertIn("SourceForge", self.metin)

    def test_rapor_kapali_kaynaklari_zorlamadigini_soyluyor(self):
        self.assertIn("bot koruması aşılmadı", self.metin)

    def test_rapor_3_2_esigini_karistirmiyor(self):
        self.assertIn("Faz 3'e aittir", self.metin)

    def test_rapor_oneri_kararini_batuhana_birakiyor(self):
        self.assertIn("kayıt kararı Batuhan'ın", self.metin)


if __name__ == "__main__":
    unittest.main()
