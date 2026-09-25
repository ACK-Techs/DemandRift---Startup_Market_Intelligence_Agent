"""AS-06 kabul kosullarini koruyan testler.

Kart: "Her bulguda denenen sorgu/yol, tarih, script surumu, once/sonra veri,
cozulemeyen sinir ve FB-ID tut. Cozumu Batuhan'in yeniden uretebilecegi
sekilde teslim et. Basarili ve basarisiz kaynak orneklerini birlikte koru."
"""
from __future__ import annotations

import csv
import re
import subprocess
import unittest
from pathlib import Path

import cozum_gunlugu as cg

HERE = Path(__file__).resolve().parent


def oku(ad: str) -> list[dict[str, str]]:
    with (HERE / ad).open(encoding="utf-8") as tutamak:
        return list(csv.DictReader(tutamak))


class HerBulguIstenenAlanlariTasirTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bulgular = oku("COZUM-GUNLUGU.csv")

    def test_kartin_istedigi_alanlar_dolu(self):
        zorunlu = ("ne_denendi", "tarih", "script", "once", "sonra",
                   "kalan_sinir", "fb_id", "yeniden_uretim")
        for b in self.bulgular:
            for alan in zorunlu:
                self.assertTrue(b[alan].strip(), f'{b["bulgu_id"]}/{alan}')

    def test_tarih_biciminde(self):
        for b in self.bulgular:
            self.assertRegex(b["tarih"], r"^\d{4}-\d{2}-\d{2}$", b["bulgu_id"])

    def test_bulgu_kimlikleri_tekil(self):
        kimlikler = [b["bulgu_id"] for b in self.bulgular]
        self.assertEqual(len(kimlikler), len(set(kimlikler)))

    def test_durum_tanimli_kumeden(self):
        for b in self.bulgular:
            self.assertIn(b["durum"], ("cozuldu", "kismen", "cozulemedi"), b["bulgu_id"])


class BatuhanYenidenUretebilirTests(unittest.TestCase):
    """Kart: cozumu Batuhan'in yeniden uretebilecegi sekilde teslim et."""

    @classmethod
    def setUpClass(cls):
        cls.bulgular = oku("COZUM-GUNLUGU.csv")

    def test_her_bulgu_calistirilabilir_komut_tasir(self):
        for b in self.bulgular:
            self.assertTrue(b["yeniden_uretim"].strip(), b["bulgu_id"])

    def test_anilan_scriptler_gercekten_var(self):
        for b in self.bulgular:
            self.assertTrue((HERE / b["script"]).exists(),
                            f'{b["bulgu_id"]}: {b["script"]} yok')

    def test_komutta_anilan_dosyalar_var(self):
        for b in self.bulgular:
            for ad in re.findall(r"\b([a-z0-9_]+\.py)\b", b["yeniden_uretim"]):
                self.assertTrue((HERE / ad).exists(), f'{b["bulgu_id"]}: {ad}')

    def test_anilan_commitler_gercek(self):
        for b in self.bulgular:
            if b["commit"] == "—":
                continue
            sonuc = subprocess.run(["git", "cat-file", "-e", f'{b["commit"]}^{{commit}}'],
                                   cwd=HERE, capture_output=True)
            self.assertEqual(0, sonuc.returncode, f'{b["bulgu_id"]}: {b["commit"]}')

    def test_fb_id_gercek_kayda_isaret_eder(self):
        for b in self.bulgular:
            if b["fb_id"] == "—":
                continue
            for fb in [x.strip() for x in b["fb_id"].split(",")]:
                yol = HERE / ".." / ".." / "ortak" / "gorevler" / "geri-bildirim" / f"{fb}.md"
                self.assertTrue(yol.exists(), f'{b["bulgu_id"]}: {fb}')


class BasarisizlarSilinmezTests(unittest.TestCase):
    """Kart: basarili ve basarisiz kaynak orneklerini BIRLIKTE koru."""

    @classmethod
    def setUpClass(cls):
        cls.saglik = oku("KAYNAK-SAGLIK.csv")
        cls.bulgular = oku("COZUM-GUNLUGU.csv")

    def test_saglik_kaydi_calismayan_kaynaklari_da_tutar(self):
        saglikli = [r for r in self.saglik if r["saglik"] == "saglikli"]
        bozuk = [r for r in self.saglik if r["saglik"] != "saglikli"]
        self.assertTrue(saglikli, "çalışan kaynak yok")
        self.assertTrue(bozuk, "çalışmayan kaynaklar silinmiş")

    def test_cozulemeyen_bulgular_gunlukte_duruyor(self):
        cozulemeyen = [b for b in self.bulgular if b["durum"] == "cozulemedi"]
        self.assertTrue(cozulemeyen, "sınır kayıtları silinmiş")
        for b in cozulemeyen:
            self.assertNotEqual("—", b["kalan_sinir"], b["bulgu_id"])

    def test_her_saglik_kaydi_sebep_tasir(self):
        for r in self.saglik:
            self.assertTrue(r["sebep"].strip(), r["kaynak_adi"])
            self.assertTrue(r["yeniden_denenebilir_mi"].strip(), r["kaynak_adi"])

    def test_politika_ve_bot_korumasi_ayri(self):
        """Ikisi de asilmaz ama cozumleri farkli; karistirilmamali."""
        sinif = {r["kaynak_adi"]: r["saglik"] for r in self.saglik}
        self.assertEqual("politika-kapali", sinif.get("Reddit"))
        self.assertEqual("bot-korumasi", sinif.get("G2"))

    def test_asilamaz_kaynak_yeniden_denenebilir_demiyor(self):
        for r in self.saglik:
            if r["saglik"] in ("politika-kapali", "bot-korumasi"):
                self.assertTrue(r["yeniden_denenebilir_mi"].startswith("hayır"),
                                r["kaynak_adi"])


class GunlukBasariRaporuDegildirTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metin = (HERE / "COZUM-GUNLUGU.md").read_text(encoding="utf-8")

    def test_rapor_bunu_acikca_soyluyor(self):
        self.assertIn("başarı raporu değildir", self.metin)

    def test_rapor_sinir_kayitlarini_ayri_bolumde_tutuyor(self):
        self.assertIn("Çözülemeyenler — sınır kayıtları", self.metin)

    def test_rapor_veri_yoklugunu_pazar_sonucu_saymiyor(self):
        self.assertIn("talep olmadığını göstermez", self.metin)

    def test_rapor_olcum_tarihinin_eskiyecegini_soyluyor(self):
        self.assertIn("Kaynak durumu değişir", self.metin)


if __name__ == "__main__":
    unittest.main()
