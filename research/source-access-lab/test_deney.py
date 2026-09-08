from __future__ import annotations

import csv
import unittest
from pathlib import Path

import deney

HERE = Path(__file__).resolve().parent


class TasarimTests(unittest.TestCase):
    """Deneyin kendi kurallarini korur: olcut once yazilir, sonra kosulur."""

    def test_her_kategori_bir_fikirle_temsil_ediliyor(self):
        """Gorev 1'in iddiasi tek kategoride sinanirsa sinanmis olmaz."""
        with (HERE / "URUN-KATEGORILERI.csv").open(encoding="utf-8") as handle:
            kategoriler = {r["kategori"] for r in csv.DictReader(handle)
                           if r["tur"] == "kategori"}
        beklenenler = {b for _f, b in deney.DENEY_FIKIRLERI}
        self.assertEqual(kategoriler, beklenenler)

    def test_negatif_kontrol_tanimli(self):
        self.assertTrue(deney.ANLAMSIZ_FIKIR.strip())

    def test_beklentiler_onceden_yazili(self):
        for anahtar in ("icerik_donme_orani", "konu_ilgisi_orani", "alan_izi_orani"):
            self.assertIn(anahtar, deney.BEKLENTI)
            self.assertTrue(0 < deney.BEKLENTI[anahtar] <= 1)

    def test_post_hoc_olcumler_isaretli(self):
        """Sonradan eklenen olcum, onceden yazilanla karistirilmamali."""
        kaynak = (HERE / "deney.py").read_text(encoding="utf-8")
        self.assertIn("SONRADAN EKLENEN", kaynak)
        self.assertIn("post-hoc", deney.K2B_ACIKLAMA)


class KaynakDogrulugunuTests(unittest.TestCase):
    def setUp(self):
        self.veri = deney._veri_yukle()
        self.sonuc = deney.kaynak_dogrulugu(self.veri)

    def test_her_fikir_beklenen_kategoriye_duser(self):
        for b in self.sonuc["bulgular"]:
            if b["olcut"].startswith("K1"):
                self.assertTrue(b["gecti"], f'{b["fikir"]} -> {b["gerceklesen"]}')

    def test_hicbir_fikirde_yasakli_kaynak_secilmez(self):
        for b in self.sonuc["bulgular"]:
            if b["olcut"].startswith("K4"):
                self.assertTrue(b["gecti"], b["fikir"])

    def test_her_fikrin_kendine_ozel_kaynagi_var(self):
        """Butun fikirler ayni listeyi uretiyorsa kategori ayrimi islememis."""
        for b in self.sonuc["bulgular"]:
            if b["olcut"].startswith("K3"):
                self.assertTrue(b["gecti"], b["fikir"])

    def test_anlamsiz_fikir_reddedilir(self):
        for b in self.sonuc["bulgular"]:
            if b["olcut"].startswith("K5"):
                self.assertTrue(b["gecti"])

    def test_katman_haric_ortusme_esigin_altinda(self):
        """K2b: paylasilan katman disarida birakilinca kategoriler ayrisir."""
        for b in self.sonuc["bulgular"]:
            if b["olcut"].startswith("K2b"):
                self.assertTrue(b["gecti"], f'{b["fikir"]} = {b["gerceklesen"]}')


class YanitSinifiTests(unittest.TestCase):
    def test_konu_gecen_yanit_calismis_sayilir(self):
        self.assertEqual("sunucu-html-veya-api", deney.yanit_sinifi(
            {"V1_icerik_dondu": "evet", "V2_konu_ilgili": "evet", "bayt": "9000"}))

    def test_buyuk_ama_konusuz_yanit_js_kabugu(self):
        """HTTP 200, 400 KB, terim yok: sayfa tarayicida uretiliyor."""
        self.assertEqual("istemci-js-kabugu", deney.yanit_sinifi(
            {"V1_icerik_dondu": "evet", "V2_konu_ilgili": "hayir", "bayt": "400000"}))

    def test_icerik_donmeyen_yanit_ayirt_edilir(self):
        self.assertEqual("icerik-yok", deney.yanit_sinifi(
            {"V1_icerik_dondu": "hayir", "V2_konu_ilgili": "hayir", "bayt": "0"}))


class CanliSonucTests(unittest.TestCase):
    """Kosulmus deneyin ciktisi; ag erisimi gerektirmez."""

    def setUp(self):
        yol = HERE / "DENEY-VERI.csv"
        if not yol.exists():
            self.skipTest("canlı deney henüz koşulmadı")
        with yol.open(encoding="utf-8") as handle:
            self.satirlar = list(csv.DictReader(handle))

    def test_her_satir_siniflandirilabiliyor(self):
        for r in self.satirlar:
            self.assertIn(deney.yanit_sinifi(r),
                          {"sunucu-html-veya-api", "istemci-js-kabugu",
                           "icerik-yok", "konu-yok-diger"})

    def test_calisan_kaynaklarda_konu_ilgisi_tam(self):
        """Sunucu tarafinda uretilen sayfalarda tasarim calisiyor."""
        sunucu = [r for r in self.satirlar
                  if deney.yanit_sinifi(r) == "sunucu-html-veya-api"]
        self.assertTrue(sunucu, "hiç çalışan kaynak yok")
        for r in sunucu:
            self.assertEqual("evet", r["V2_konu_ilgili"], r["kaynak"])

    def test_uretilen_sorgularda_doldurulmamis_yer_tutucu_yok(self):
        for r in self.satirlar:
            self.assertNotIn("{", r["sorgu"], r["kaynak"])

    def test_hicbir_sorgu_yinelenen_arama_parametresi_tasimaz(self):
        for r in self.satirlar:
            for parametre in ("text=", "search_for="):
                self.assertLessEqual(r["sorgu"].count(parametre), 1, r["kaynak"])


if __name__ == "__main__":
    unittest.main()
