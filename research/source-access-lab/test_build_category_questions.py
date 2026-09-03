from __future__ import annotations

import collections
import csv
import unittest
from pathlib import Path

import build_category_questions as soru

HERE = Path(__file__).resolve().parent


class TanimTests(unittest.TestCase):
    def test_her_soru_tanimli(self):
        kullanilan = set(soru.ORTAK_SORULAR)
        for ozel in soru.KATEGORI_OZEL.values():
            kullanilan |= set(ozel)
        self.assertEqual(set(), kullanilan - set(soru.SORULAR))

    def test_tanimli_her_soru_kullaniliyor(self):
        """Kullanilmayan soru tanimi olu koddur; taksonomi buyudukce yaniltir."""
        kullanilan = set(soru.ORTAK_SORULAR)
        for ozel in soru.KATEGORI_OZEL.values():
            kullanilan |= set(ozel)
        self.assertEqual(set(), set(soru.SORULAR) - kullanilan)

    def test_ortak_soru_kategoriye_ozel_listede_tekrar_etmez(self):
        for kategori, ozel in soru.KATEGORI_OZEL.items():
            cakisan = set(ozel) & set(soru.ORTAK_SORULAR)
            self.assertEqual(set(), cakisan, kategori)

    def test_her_kanit_uc_alani_da_doldurur(self):
        """Kanit turu, neden gecerli ve zayif alternatif birlikte anlam tasir."""
        for anahtar, degerler in soru.KANIT.items():
            self.assertEqual(3, len(degerler), anahtar)
            for alan in degerler:
                self.assertTrue(alan.strip(), anahtar)

    def test_zayif_alternatif_kanit_turunden_farkli(self):
        """Ayni sey hem kanit hem zayif alternatif olamaz."""
        for anahtar, (tur, _gecerli, zayif) in soru.KANIT.items():
            self.assertNotEqual(tur, zayif, anahtar)


class CiktiTests(unittest.TestCase):
    def setUp(self):
        with (HERE / "KATEGORI-SORU.csv").open(encoding="utf-8") as handle:
            self.satirlar = list(csv.DictReader(handle))

    def test_her_kategorinin_her_sorusu_kanitli(self):
        """Kaniti olmayan soru cevaplanamaz; boyle bir satir kalmamali."""
        var = {(r["kategori"], r["soru_id"]) for r in self.satirlar}
        for kategori, ozel in soru.KATEGORI_OZEL.items():
            for soru_id in (*soru.ORTAK_SORULAR, *ozel):
                self.assertIn((kategori, soru_id), var, f"{kategori}/{soru_id}")

    def test_kategoriye_ozel_soru_baska_kategoride_gecmez(self):
        gorulen = collections.defaultdict(set)
        for r in self.satirlar:
            if r["soru_turu"] == "kategoriye-ozel":
                gorulen[r["soru_id"]].add(r["kategori"])
        for soru_id, kategoriler in gorulen.items():
            izinli = {k for k, ozel in soru.KATEGORI_OZEL.items() if soru_id in ozel}
            self.assertEqual(izinli, kategoriler, soru_id)

    def test_her_satirda_zayif_alternatif_var(self):
        """Gorevin 'gercekten destekleyen' sarti, desteklemeyeni de isaretlemeyi gerektirir."""
        for r in self.satirlar:
            self.assertTrue(r["zayif_alternatif"].strip(), r["soru_id"])
            self.assertTrue(r["neden_gecerli"].strip(), r["soru_id"])

    def test_ayni_soru_kategoriye_gore_farkli_kanit_alir(self):
        """Kanit kategoriye gore degismiyorsa gorev 1'deki ayrimin karsiligi yok."""
        kanit = collections.defaultdict(set)
        for r in self.satirlar:
            if r["kanit_kaynak_rolu"] == "kategori":
                kanit[r["soru_id"]].add((r["kategori"], r["kanit_turu"]))
        for soru_id in ("talep-var-mi", "doygun-mu", "odeme-istegi"):
            kategoriler = {k for k, _ in kanit[soru_id]}
            turler = {t for _, t in kanit[soru_id]}
            self.assertGreater(len(kategoriler), 1, soru_id)
            self.assertEqual(len(turler), len(kanit[soru_id]), soru_id)

    def test_her_ek_paketin_sorusu_kanitli(self):
        """Ek paket soru cevaplamiyorsa o paketin kaynaklari bosta kalir."""
        var = {(r["kategori"], r["soru_id"]) for r in self.satirlar}
        for ek, sorular in soru.EK_SORULARI.items():
            for soru_id in sorular:
                self.assertIn((ek, soru_id), var, f"{ek}/{soru_id}")

    def test_envanterin_buyuk_kismi_bir_soruya_bagli(self):
        """Soru seti envanteri gercekten kullanmali; bagsiz kaynak olu yatirimdir."""
        with (HERE / "KATEGORI-KAYNAK.csv").open(encoding="utf-8") as handle:
            kaynaklar = list(csv.DictReader(handle))
        kullanilan = {r["kanit_kaynak_grubu"] for r in self.satirlar}
        grup_kaynak = collections.defaultdict(set)
        for r in kaynaklar:
            for grup in r["kaynak_grubu"].split(" | "):
                grup_kaynak[grup.strip()].add(r["kaynak"])
        dokunulan = set()
        for grup in kullanilan:
            dokunulan |= grup_kaynak[grup]
        tum = {r["kaynak"] for r in kaynaklar}
        # Arama motorlari ve anket platformlari kasitla disarida: ilki kanita
        # ulastiran arac, ikincisi birincil arastirma altyapisi.
        self.assertGreater(len(dokunulan) / len(tum), 0.9)

    def test_ornek_kaynaklar_calisan_kaynaklardan_secilir(self):
        for r in self.satirlar:
            if r["ornek_kaynaklar"]:
                self.assertGreater(int(r["calisan_kaynak"]), 0, r["kanit_kaynak_grubu"])


if __name__ == "__main__":
    unittest.main()
