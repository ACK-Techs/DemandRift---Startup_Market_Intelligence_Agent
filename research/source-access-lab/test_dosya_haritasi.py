"""Haritanin eskimesini engelleyen testler.

Klasorde 88 dosya var. Yeni bir dosya eklenip haritaya yazilmazsa mentor onu
gorup hangi goreve ait oldugunu bilemez. Bu testler tam olarak bunu yakalar.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import dosya_haritasi as dh

HERE = Path(__file__).resolve().parent


class HaritaEksiksizTests(unittest.TestCase):
    def test_her_izlenen_dosya_bir_goreve_ait(self):
        """Kabul kriteri: sahipsiz dosya kalmaz."""
        self.assertEqual([], dh.sahipsiz_dosyalar())

    def test_her_test_dosyasi_bir_modulu_korur(self):
        self.assertEqual([], dh.yetim_test_dosyalari())

    def test_haritada_var_olmayan_dosya_yok(self):
        izlenen = set(dh.izlenen_dosyalar())
        for ad in dh.HARITA:
            self.assertIn(ad, izlenen, f"{ad} haritada var ama git'te yok")

    def test_her_gorev_anahtari_tanimli(self):
        for ad, (gorev, rol, aciklama) in dh.HARITA.items():
            self.assertIn(gorev, dh.GOREVLER, ad)
            self.assertIn(rol, dh.ROL_SIRASI, ad)
            self.assertTrue(aciklama.strip(), ad)

    def test_her_gorevin_en_az_bir_dosyasi_var(self):
        sahip = {g for g, _r, _a in dh.HARITA.values()}
        for anahtar in dh.GOREVLER:
            self.assertIn(anahtar, sahip, anahtar)


class ReadmeSenkronTests(unittest.TestCase):
    def test_readme_haritayla_ayni(self):
        """Harita degistiyse README yeniden uretilmeli."""
        metin = (HERE / "README.md").read_text(encoding="utf-8")
        bas = metin.index(dh.BASLANGIC)
        bit = metin.index(dh.BITIS) + len(dh.BITIS)
        self.assertEqual(dh.readme_bolumu(), metin[bas:bit],
                         "README eskimiş: python3 dosya_haritasi.py çalıştırın")

    def test_readme_her_cikti_dosyasina_bag_veriyor(self):
        metin = (HERE / "README.md").read_text(encoding="utf-8")
        for ad, (_g, rol, _a) in dh.HARITA.items():
            if rol in ("cikti", "belge"):
                self.assertIn(f"]({ad})", metin, ad)


if __name__ == "__main__":
    unittest.main()
