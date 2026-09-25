"""AS-04 kabul kosullarini koruyan testler.

Kartin en sert kurali: "Etiketli referans olmadan web recall orani uretme."
"""
from __future__ import annotations

import csv
import unittest
from pathlib import Path

import hata_incelemesi as hi

HERE = Path(__file__).resolve().parent


def oku(ad: str) -> list[dict[str, str]]:
    with (HERE / ad).open(encoding="utf-8") as tutamak:
        return list(csv.DictReader(tutamak))


class RecallUretilmezTests(unittest.TestCase):
    def test_recall_none_doner(self):
        olcum = hi.precision(hi.etiketli_referans())
        self.assertIsNone(olcum["recall"])

    def test_recall_neden_yok_yazili(self):
        olcum = hi.precision(hi.etiketli_referans())
        self.assertIn("referans küme yoktur", olcum["recall_neden_yok"])

    def test_rapor_recall_orani_iddia_etmiyor(self):
        metin = (HERE / "AS04-HATA-RAPORU.md").read_text(encoding="utf-8")
        self.assertIn("Recall hesaplanmadı ve hesaplanamaz", metin)
        self.assertIn("recall          : YOK", metin)

    def test_precision_tanimli(self):
        olcum = hi.precision(hi.etiketli_referans())
        self.assertIn("incelenen sonuç", olcum["precision_tanimi"])


class EtiketliReferansTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.etiketler = oku("AS04-ETIKETLI-REFERANS.csv")

    def test_her_etiket_sebep_tasir(self):
        for r in self.etiketler:
            self.assertTrue(r["sebep"].strip(), r["etiket_id"])
            self.assertGreater(len(r["sebep"]), 20, r["etiket_id"])

    def test_etiketler_uc_degerden(self):
        for r in self.etiketler:
            self.assertIn(r["etiket"], ("relevant", "irrelevant", "uncertain"))

    def test_uc_etiket_de_kullanilmis(self):
        kullanilan = {r["etiket"] for r in self.etiketler}
        self.assertEqual({"relevant", "irrelevant", "uncertain"}, kullanilan)

    def test_insan_etiketi_oldugu_yazili(self):
        for r in self.etiketler:
            self.assertIn("elle", r["etiketleyen"])

    def test_karsit_bulgular_ayri_isaretli(self):
        karsit = [r for r in self.etiketler if r["dogrudan_karsit_bulgu"] == "EVET"]
        self.assertTrue(karsit, "doğrudan karşıt bulgu işaretlenmemiş")
        for r in karsit:
            self.assertIn("KARŞIT", r["sebep"].upper())

    def test_hicbiri_kabul_edilmis_degil(self):
        for r in self.etiketler:
            self.assertEqual("bekliyor", r["batuhan_yeniden_kontrolu"])


class DortHataSinifiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hatalar = oku("AS04-HATA-INCELEMESI.csv")

    def test_dort_sinif_da_incelenmis(self):
        siniflar = {r["hata_sinifi"] for r in self.hatalar}
        for s in ("dedup-yanlis-birlesme", "yanlis-eksik-alan",
                  "filtrede-kayip-kanit", "desteksiz-claim"):
            self.assertIn(s, siniflar, s)

    def test_her_kayit_karar_ve_gerekce_tasir(self):
        for r in self.hatalar:
            self.assertTrue(r["karar"].strip(), r["document_id"])
            self.assertTrue(r["gerekce"].strip(), r["document_id"])

    def test_bulunan_hatalar_duzeltme_onerisi_tasir(self):
        for r in self.hatalar:
            if r["karar"].isupper():
                self.assertNotEqual("—", r["duzeltme"], r["document_id"])

    def test_aranip_bulunamayan_da_kayitli(self):
        """'Arandi ve bulunamadi' ile 'hic bakilmadi' ayni sey degil."""
        dedup = [r for r in self.hatalar if r["hata_sinifi"] == "dedup-yanlis-birlesme"]
        self.assertTrue(dedup, "dedup hiç incelenmemiş")
        for r in dedup:
            self.assertTrue(r["gerekce"].strip())

    def test_gurultu_ile_kayip_kanit_ayri(self):
        filtre = [r for r in self.hatalar if r["hata_sinifi"] == "filtrede-kayip-kanit"]
        kararlar = {r["karar"] for r in filtre}
        self.assertIn("KAYIP KANIT", kararlar)
        self.assertIn("gürültü", kararlar)


class AlanCikarimiDuzeltmesiTests(unittest.TestCase):
    """Kok sebep: cikarim yalniz kaynagin ailesine bakiyordu."""

    def test_sayfa_turu_de_sinif_belirliyor(self):
        import normalize_belgeler as nb
        self.assertIn("urun", nb.cikarim_siniflari("", "fiyatlandirma-sayfasi", ""))
        self.assertIn("urun", nb.cikarim_siniflari("", "", "observed_market_pricing"))

    def test_hicbir_isaret_yoksa_varsayilan(self):
        import normalize_belgeler as nb
        self.assertEqual((nb.VARSAYILAN_SINIF,),
                         nb.cikarim_siniflari("", "ana-sayfa", ""))

    def test_duzeltme_sonrasi_fiyat_arttı(self):
        alanlar = oku("KATEGORI-ALANLARI.csv")
        fiyat = sum(1 for r in alanlar if r["alan"] == "fiyat")
        self.assertGreater(fiyat, 56, "düzeltme öncesi seviyede kalmış")


if __name__ == "__main__":
    unittest.main()
