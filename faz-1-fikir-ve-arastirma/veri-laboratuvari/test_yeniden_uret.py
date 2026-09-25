"""AS-02 yeniden uretim makinesinin kurallarini koruyan testler."""
from __future__ import annotations

import csv
import hashlib
import unittest
from pathlib import Path

import yeniden_uret as yu

HERE = Path(__file__).resolve().parent


def oku(ad: str) -> list[dict[str, str]]:
    yol = HERE / ad
    if not yol.exists():
        return []
    with yol.open(encoding="utf-8") as tutamak:
        return list(csv.DictReader(tutamak))


class DortSinifAyriTests(unittest.TestCase):
    """Kart: erisim, alan cikarimi, yanlis/bos icerik ve dil/pazar ayrilir."""

    def test_erisim_engeli_erisim_sayilir(self):
        for sebep in ("robots_disallowed", "challenge", "rate_limited"):
            sinif, _g = yu.sorunu_ayir(sebep, "", "", None, set(), set(), "", "")
            self.assertEqual("erisim", sinif, sebep)

    def test_bos_govde_icerik_sorunu(self):
        sinif, _g = yu.sorunu_ayir("ok", "js-kabugu", "", None, set(), set(), "", "")
        self.assertEqual("yanlis-bos-icerik", sinif)

    def test_ilgisiz_icerik_icerik_sorunu(self):
        sinif, _g = yu.sorunu_ayir("ok", "gercek-icerik", "", False, set(), set(), "", "")
        self.assertEqual("yanlis-bos-icerik", sinif)

    def test_eksik_alan_cikarim_sorunu(self):
        sinif, gerekce = yu.sorunu_ayir(
            "ok", "gercek-icerik", "", True, {"baslik"}, {"baslik", "fiyat"}, "en", "en")
        self.assertEqual("alan-cikarimi", sinif)
        self.assertIn("fiyat", gerekce)

    def test_yanlis_dil_dil_pazar_sorunu(self):
        sinif, _g = yu.sorunu_ayir("ok", "gercek-icerik", "", True, set(), set(), "en", "tr")
        self.assertEqual("dil-pazar", sinif)

    def test_erisim_yoksa_icerik_konusulmaz(self):
        """Katmanlar sirali: kapi kapaliysa alan eksikligi raporlanmaz."""
        sinif, _g = yu.sorunu_ayir(
            "challenge", "", "", None, set(), {"fiyat"}, "", "tr")
        self.assertEqual("erisim", sinif)


class IlgililikYanilmazTests(unittest.TestCase):
    """On dogrulamanin yakaladigi iki tuzak."""

    def test_genel_kelime_ilgili_yapmaz(self):
        """'software' bir yazilim dizininin her sayfasinda gecer."""
        metin = "x" * 400 + " Karmada Kubernetes advanced scheduling software"
        self.assertFalse(yu._ilgili_mi(metin, "salon scheduling software"))

    def test_sorgu_yankisi_sayilmaz(self):
        """Arama sayfasi sorguyu kendi icinde tekrarlar."""
        metin = "x" * 400 + ' Search Results for "salon scheduling software" Karmada'
        self.assertFalse(yu._ilgili_mi(metin, "salon scheduling software"))

    def test_gercek_icerik_ilgili_sayilir(self):
        metin = "x" * 400 + " salon booking for stylists scheduling appointments"
        self.assertTrue(yu._ilgili_mi(metin, "salon scheduling software"))

    def test_olculemeyen_durumda_ilgisiz_denmez(self):
        self.assertIsNone(yu._ilgili_mi("x" * 400, ""))
        self.assertIsNone(yu._ilgili_mi("x" * 400, "best free software"))


class OnDogrulamaTests(unittest.TestCase):
    """Kart: calistirilmamis test kabul edilmis sayilmaz."""

    @classmethod
    def setUpClass(cls):
        cls.satirlar = oku("AS02-ONDOGRULAMA.csv")

    def test_ondogrulama_kosulmus(self):
        self.assertTrue(self.satirlar, "ön doğrulama hiç koşulmamış")

    def test_dort_sinif_da_canli_sinanmis(self):
        cikan = {r["sorun_sinifi"] for r in self.satirlar}
        for sinif in ("erisim", "yanlis-bos-icerik", "dil-pazar", "sorun-yok"):
            self.assertIn(sinif, cikan, sinif)

    def test_her_vaka_beklentiyi_tutturmus(self):
        tutmayan = [r["fb_id"] for r in self.satirlar if r["tuttu_mu"] != "evet"]
        self.assertEqual([], tutmayan)

    def test_basarili_kosu_kanit_birakmis(self):
        for r in self.satirlar:
            if r["erisim"] != "ok":
                continue
            yol = HERE / r["artefakt_dosya"]
            self.assertTrue(yol.exists(), r["fb_id"])
            self.assertEqual(r["artefakt"],
                             hashlib.sha256(yol.read_bytes()).hexdigest(), r["fb_id"])

    def test_istek_atilmayan_vaka_artefakt_iddia_etmez(self):
        for r in self.satirlar:
            if r["erisim"].startswith("robots"):
                self.assertEqual("", r["artefakt"], r["fb_id"])



class BatuhanOnaylamadanKabulOlmazTests(unittest.TestCase):
    """Kart: Batuhan yeniden kontrol etmeden kabul edilmis sayma."""

    def test_sonuc_satirlari_bekliyor_ile_baslar(self):
        for r in oku(yu.SONUC_DOSYASI):
            self.assertEqual("bekliyor", r["batuhan_yeniden_kontrolu"], r["fb_id"])

    def test_bildirim_sablonu_var_ve_bos(self):
        yol = HERE / yu.BILDIRIM_DOSYASI
        self.assertTrue(yol.exists())
        for sutun in yu.BILDIRIM_SUTUNLARI:
            self.assertIn(sutun, yol.read_text(encoding="utf-8").splitlines()[0])

    def test_bildirim_yokken_sonuc_uretilmez(self):
        """Girdi olmadan cikti uretmek, girdiyi uydurmak olur."""
        gercek = [r for r in oku(yu.BILDIRIM_DOSYASI) if r.get("denenen_url", "").strip()]
        if not gercek:
            self.assertEqual([], oku(yu.SONUC_DOSYASI))


if __name__ == "__main__":
    unittest.main()
