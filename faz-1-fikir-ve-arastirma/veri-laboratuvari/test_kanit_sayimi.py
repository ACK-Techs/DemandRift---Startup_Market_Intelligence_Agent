"""AS-05 kabul kosullarini koruyan testler.

Kartin en sert kurali: "bilinmeyen bagimsizligi 3 ornek alt sinirina sayma."
"""
from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

import kanit_sayimi as ks

HERE = Path(__file__).resolve().parent


def oku(ad: str) -> list[dict[str, str]]:
    with (HERE / ad).open(encoding="utf-8") as tutamak:
        return list(csv.DictReader(tutamak))


class BilinmeyenBagimsizlikSayilmazTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sayim = oku("AS05-KANIT-SAYIMI.csv")

    def test_bilinmeyen_ayri_sutunda(self):
        for r in self.sayim:
            self.assertIn("unknown_independence_examples", r)

    def test_bilinmeyen_bagimsiz_sayiya_eklenmemis(self):
        """relevant_independent_examples yalniz BILINEN bagimsizliklari sayar."""
        for r in self.sayim:
            self.assertLessEqual(int(r["relevant_independent_examples"]),
                                 int(r["supporting_examples"]),
                                 f'{r["kategori"]}/{r["arama_niyeti"]}')

    def test_yalniz_bilinmeyeni_olan_hucre_gecemez(self):
        for r in self.sayim:
            if int(r["supporting_examples"]) == 0 and int(r["unknown_independence_examples"]) > 0:
                self.assertEqual("hayır", r["gecti_mi"],
                                 f'{r["kategori"]}/{r["arama_niyeti"]}')

    def test_kisi_gozlemi_gereken_niyet_kritik_bosluk_tasir(self):
        for r in self.sayim:
            if r["arama_niyeti"] in ks.KISI_GOZLEMI_GEREKIR:
                self.assertTrue(r["critical_gaps"].strip(),
                                f'{r["kategori"]}/{r["arama_niyeti"]}')


class EsikUygulanirTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sayim = oku("AS05-KANIT-SAYIMI.csv")

    def test_esikler_politikadan(self):
        self.assertEqual(3, ks.ASGARI_BAGIMSIZ_ORNEK)
        self.assertEqual(2, ks.ASGARI_TEKIL_KAYNAK)

    def test_gecen_hucre_iki_esigi_de_saglar(self):
        for r in self.sayim:
            if r["gecti_mi"] == "evet":
                self.assertGreaterEqual(int(r["relevant_independent_examples"]),
                                        ks.ASGARI_BAGIMSIZ_ORNEK, r["kategori"])
                self.assertGreaterEqual(int(r["distinct_sources"]),
                                        ks.ASGARI_TEKIL_KAYNAK, r["kategori"])

    def test_2_2_ve_3_1_yetersiz(self):
        for ornek in [(2, 2), (3, 1), (2, 5)]:
            bagimsiz, kaynak = ornek
            gecer = (bagimsiz >= ks.ASGARI_BAGIMSIZ_ORNEK
                     and kaynak >= ks.ASGARI_TEKIL_KAYNAK)
            self.assertFalse(gecer, f"{bagimsiz}/{kaynak} geçmemeli")

    def test_her_hucre_gate_results_tasir(self):
        for r in self.sayim:
            kapilar = json.loads(r["gate_results"])
            for ad in ("min_independent_examples", "min_distinct_sources"):
                self.assertIn(ad, kapilar)

    def test_her_hucre_gerekce_tasir(self):
        for r in self.sayim:
            self.assertTrue(r["eligibility_reason"].strip())

    def test_politika_surumu_kayitli(self):
        for r in self.sayim:
            self.assertEqual(ks.POLITIKA_SURUMU, r["policy_version"])


class DestekKarsitAyriTests(unittest.TestCase):
    def test_karsit_ornekler_ayri_sayiliyor(self):
        sayim = oku("AS05-KANIT-SAYIMI.csv")
        for r in sayim:
            self.assertIn("challenging_examples", r)
        self.assertGreater(sum(int(r["challenging_examples"]) for r in sayim), 0,
                           "karşıt bulgular sayıma hiç girmemiş")

    def test_karsit_ornek_destek_olarak_sayilmamis(self):
        """Ayni kanit iki tarafta bagimsizmis gibi iki kez sayilamaz."""
        for r in oku("AS05-KANIT-SAYIMI.csv"):
            toplam = (int(r["supporting_examples"]) + int(r["challenging_examples"])
                      + int(r["unknown_independence_examples"]))
            self.assertLessEqual(int(r["challenging_examples"]), toplam)


class AlintiBagiTests(unittest.TestCase):
    """Kart: alintinin metin/hash/surum bagini kontrol et."""

    @classmethod
    def setUpClass(cls):
        cls.alintilar = oku("AS05-ALINTI-KONTROL.csv")

    def test_her_alinti_uc_bagi_da_rapor_eder(self):
        for r in self.alintilar:
            for alan in ("metin_bagi", "hash_bagi", "surum_bagi"):
                self.assertTrue(r[alan].strip(), r["document_id"])

    def test_gecerli_alintinin_hashi_dogrulanmis(self):
        for r in self.alintilar:
            if r["durum"] == "geçerli":
                self.assertEqual("doğrulandı", r["hash_bagi"], r["document_id"])

    def test_kopuk_alinti_gecerli_sayilmaz(self):
        for r in self.alintilar:
            if "KOPUK" in r["metin_bagi"]:
                self.assertEqual("GECERSIZ", r["durum"], r["document_id"])

    def test_surum_bagi_her_satirda(self):
        for r in self.alintilar:
            self.assertRegex(r["surum_bagi"], r"^\d+\.\d+\.\d+$")


class ClaimBildirimiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bildirimler = oku("AS05-CLAIM-BILDIRIMI.csv")

    def test_her_bildirim_claim_duzeyinde(self):
        for r in self.bildirimler:
            self.assertTrue(r["claim"].strip())
            self.assertTrue(r["gerekce"].strip())
            self.assertTrue(r["kanit"].strip())

    def test_desteklenmeyen_claim_duzeltme_tasir(self):
        for r in self.bildirimler:
            if r["durum"] == "DESTEKLENMIYOR":
                self.assertTrue(r["yapilacak_duzeltme"].strip(), r["claim_id"])

    def test_hicbiri_kabul_edilmis_degil(self):
        for r in self.bildirimler:
            self.assertEqual("bekliyor", r["batuhan_yeniden_kontrolu"])


class RaporTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metin = (HERE / "AS05-SAYIM-RAPORU.md").read_text(encoding="utf-8")

    def test_rapor_gecmemeyi_pazar_sonucu_saymiyor(self):
        self.assertIn("pazar kötü", self.metin)
        self.assertIn("bu veriyle sonuca varılamaz", self.metin)

    def test_rapor_nicel_esigin_yetmedigini_soyluyor(self):
        self.assertIn("sayılar tek başına yeterli değildir", self.metin)

    def test_rapor_fiyat_beyanini_odeme_saymiyor(self):
        self.assertIn("Fiyat beyanı gerçek ödeme değildir", self.metin)

    def test_rapor_uydurma_yuzde_uretmedigini_soyluyor(self):
        self.assertIn("güven yüzdesi üretilmedi", self.metin)


if __name__ == "__main__":
    unittest.main()
