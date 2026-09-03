from __future__ import annotations

import collections
import csv
import tempfile
import unittest
from pathlib import Path

import build_product_categories as kat

HERE = Path(__file__).resolve().parent


class SiniflandirmaTests(unittest.TestCase):
    def test_her_baslik_siniflandirilmis(self):
        """Yeni bir baslik eklenirse sessizce ortak havuza dusmemeli."""
        basliklar = set(kat.baslik_kaynaklari(HERE / "SITE-LISTESI.md"))
        self.assertEqual(set(), basliklar - set(kat.BASLIK_ROLU))

    def test_her_baslikta_ne_saglar_ve_arama_tanimli(self):
        self.assertEqual(set(), set(kat.BASLIK_ROLU) - set(kat.BASLIK_BILGISI))

    def test_kategori_hedefleri_tanimli(self):
        hedefler = {h for r, h in kat.BASLIK_ROLU.values() if r == "kategori"}
        self.assertEqual(set(), hedefler - set(kat.KATEGORI_BILGISI))

    def test_ek_hedefleri_tanimli(self):
        hedefler = {h for r, h in kat.BASLIK_ROLU.values() if r == "ek"}
        self.assertEqual(set(), hedefler - set(kat.EK_BILGISI))

    def test_arama_kaliplari_urun_yer_tutucusu_tasir(self):
        """Kalip {urun} tasimazsa kullanicinin fikri sorguya giremez."""
        for baslik, (_saglar, arama) in kat.BASLIK_BILGISI.items():
            self.assertIn("{urun}", arama, baslik)


class BaslikOkumaTests(unittest.TestCase):
    def dosya(self, metin: str) -> Path:
        yol = Path(tempfile.mkdtemp()) / "liste.md"
        yol.write_text(metin, encoding="utf-8")
        return yol

    def test_basliklar_ve_kaynaklar_ayrilir(self):
        okunan = kat.baslik_kaynaklari(self.dosya(
            "# Liste\n\n## Bir\n\n- A\n- B\n\n## Iki\n\n- C\n"
        ))
        self.assertEqual({"Bir": ["A", "B"], "Iki": ["C"]}, okunan)

    def test_ayni_baslikta_tekrar_eden_kaynak_bir_kez_sayilir(self):
        okunan = kat.baslik_kaynaklari(self.dosya("## Bir\n\n- A\n- A\n- B\n"))
        self.assertEqual({"Bir": ["A", "B"]}, okunan)


class CiktiTests(unittest.TestCase):
    """Uretilen dosyalar depodaki hâliyle tutarli mi?"""

    def oku(self, ad: str) -> list[dict[str, str]]:
        with (HERE / ad).open(encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def setUp(self):
        self.kategoriler = self.oku("URUN-KATEGORILERI.csv")
        self.kaynaklar = self.oku("KATEGORI-KAYNAK.csv")

    def test_her_kategori_ve_ek_satiri_var(self):
        yazilan = {r["kategori"] for r in self.kategoriler}
        self.assertEqual(set(), set(kat.KATEGORI_BILGISI) - yazilan)
        self.assertEqual(set(), set(kat.EK_BILGISI) - yazilan)

    def test_ayni_kategoride_kaynak_tekrar_etmez(self):
        sayac = collections.Counter((r["hedef"], r["kaynak"]) for r in self.kaynaklar)
        tekrar = [k for k, v in sayac.items() if v > 1]
        self.assertEqual([], tekrar)

    def test_kategoriler_buyuk_olcude_ayrik(self):
        """Iki kategorinin cekirdegi buyuk olcude ortaksa ayrim etiketten ibarettir."""
        cekirdek = collections.defaultdict(set)
        for r in self.kaynaklar:
            if r["hedef_turu"] == "kategori":
                cekirdek[r["hedef"]].add(r["kaynak"])
        for a in cekirdek:
            for b in cekirdek:
                if a >= b:
                    continue
                ortak = cekirdek[a] & cekirdek[b]
                kucuk = min(len(cekirdek[a]), len(cekirdek[b]))
                self.assertLess(len(ortak), kucuk * 0.25, f"{a} ile {b} fazla ortak")

    def test_katman_olabilir_alani_dogru_isaretli(self):
        """Katman kategorileri baska bir kategorinin ustune binebilir; digerleri binmez."""
        isaret = {r["kategori"]: r["katman_olabilir"] for r in self.kategoriler
                  if r["tur"] == "kategori"}
        for anahtar in kat.KATMAN_OLABILIR:
            self.assertEqual("evet", isaret[anahtar], anahtar)
        for anahtar in set(kat.KATEGORI_BILGISI) - kat.KATMAN_OLABILIR:
            self.assertEqual("hayir", isaret[anahtar], anahtar)

    def test_ek_paketler_her_zaman_katman(self):
        for r in self.kategoriler:
            if r["tur"] == "ek":
                self.assertEqual("evet", r["katman_olabilir"], r["kategori"])

    def test_her_kategori_kaynaginin_durumu_yazili(self):
        """Kategori 'etiket' olmamali: satirda kaynagin gercek durumu bulunmali."""
        for r in self.kaynaklar:
            self.assertTrue(r["kaynak"], r)
            self.assertIn(r["rol"], {"cekirdek", "ek", "destekleyici"})
            self.assertIn("{urun}", r["hangi_arama"], r["kaynak"])


if __name__ == "__main__":
    unittest.main()
