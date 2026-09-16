from __future__ import annotations

import csv
import unittest
from pathlib import Path

import kategori_sozlugu as sozluk

HERE = Path(__file__).resolve().parent


class EksenAyrimiTests(unittest.TestCase):
    """Kabul kriteri: kaynak ailesi ile urun kategorisi karistirilmaz."""

    def test_urun_tipi_ve_kaynak_ailesi_ayri_kumeler(self):
        with (HERE / "KATEGORI-KAYNAK.csv").open(encoding="utf-8") as handle:
            aileler = {g.strip() for r in csv.DictReader(handle)
                       for g in r["kaynak_grubu"].split(" | ")}
        self.assertEqual(set(), set(sozluk.URUN_TIPI) & aileler)

    def test_her_eksenin_coklu_etiket_kurali_var(self):
        for eksen in ("urun_tipi", "kaynak_ailesi", "belge_turu", "arastirma_niyeti"):
            self.assertIn(eksen, sozluk.COKLU_ETIKET)
            self.assertTrue(sozluk.COKLU_ETIKET[eksen].strip())

    def test_her_eksenin_belirsizlik_kurali_var(self):
        for eksen in ("urun_tipi", "kaynak_ailesi", "belge_turu", "arastirma_niyeti"):
            self.assertIn(eksen, sozluk.BELIRSIZ_DURUMU)
            self.assertTrue(sozluk.BELIRSIZ_DURUMU[eksen].strip())

    def test_her_urun_tipinde_dahil_ve_haric_ornegi_var(self):
        for anahtar, bilgi in sozluk.URUN_TIPI.items():
            for alan in ("tanim", "dahil", "haric", "hedef_kullanici", "satin_alma"):
                self.assertTrue(bilgi.get(alan, "").strip(), f"{anahtar}/{alan}")

    def test_gorev1_kategorileri_eslenmis(self):
        with (HERE / "URUN-KATEGORILERI.csv").open(encoding="utf-8") as handle:
            kategoriler = {r["kategori"] for r in csv.DictReader(handle)
                           if r["tur"] == "kategori"}
        self.assertEqual(set(), kategoriler - set(sozluk.URUN_TIPI_ESLEME))

    def test_esleme_hedefleri_gercek_urun_tipi(self):
        self.assertEqual(set(), set(sozluk.URUN_TIPI_ESLEME.values())
                         - set(sozluk.URUN_TIPI))


class KokYoluTests(unittest.TestCase):
    def test_yerellestirilmis_ana_sayfalar_kok_sayilir(self):
        """base.com/en-US/home/ ve bigspy.com/en de ana sayfadir."""
        for yol in ("/", "/index.html", "/en", "/en-US/home/", "/intl/tr/", "/tr"):
            self.assertTrue(sozluk.kok_yolu_mu(yol), yol)

    def test_ic_sayfalar_kok_sayilmaz(self):
        for yol in ("/store/search", "/pricing/calculator/", "/us/iphone/today",
                    "/apps/", "/projeler"):
            self.assertFalse(sozluk.kok_yolu_mu(yol), yol)


class BelgeTuruKurallariTests(unittest.TestCase):
    """Kabul kriteri: icerik bulunmayan yerde yorum/fiyat verisi varsayilmaz."""

    def _sinyal(self, **ek):
        temel = {"baslik": "", "jsonld_turleri": [], "yol": "/", "bayt": 1000,
                 "arama_parametresi": False, "itemlist_sayisi": 0,
                 "aggregate_rating": False, "yorum_sayisi": 0,
                 "fiyatli_offer_sayisi": 0, "urun_nesnesi": False,
                 "makale_nesnesi": False}
        temel.update(ek)
        return temel

    def test_tek_itemlist_liste_sayfasi_yapmaz(self):
        """Gezinme menuleri de ItemList olarak isaretlenir."""
        tur, _i, _k = sozluk.belge_turu_belirle(
            "root_html", "text/html", self._sinyal(itemlist_sayisi=1))
        self.assertNotEqual("liste-sayfasi", tur)

    def test_tek_yorum_inceleme_sayfasi_yapmaz(self):
        """Pazarlama sayfasindaki musteri gorusu yorum govdesi degildir."""
        tur, _i, _k = sozluk.belge_turu_belirle(
            "root_html", "text/html", self._sinyal(yorum_sayisi=1))
        self.assertNotEqual("inceleme-sayfasi", tur)

    def test_tek_offer_fiyatlandirma_sayfasi_yapmaz(self):
        tur, _i, _k = sozluk.belge_turu_belirle(
            "root_html", "text/html", self._sinyal(fiyatli_offer_sayisi=1))
        self.assertNotEqual("fiyatlandirma-sayfasi", tur)

    def test_kok_yolda_kendini_tarif_eden_urun_kayit_sayfasi_yapmaz(self):
        """Pazarlama ana sayfasi kendi urununu Product olarak gomer."""
        tur, _i, _k = sozluk.belge_turu_belirle(
            "root_html", "text/html",
            self._sinyal(urun_nesnesi=True, jsonld_turleri=["SoftwareApplication"]))
        self.assertEqual("ana-sayfa", tur)

    def test_guclu_liste_kaniti_kok_yolu_ezer(self):
        tur, _i, _k = sozluk.belge_turu_belirle(
            "root_html", "text/html", self._sinyal(itemlist_sayisi=20))
        self.assertEqual("liste-sayfasi", tur)

    def test_kok_olmayan_isaretsiz_sayfa_belirsizdir(self):
        """Tahmin edilmez: 'belirsiz' gecerli bir etikettir."""
        tur, _i, kanit = sozluk.belge_turu_belirle(
            "root_html", "text/html", self._sinyal(yol="/us/iphone/today"))
        self.assertEqual("belirsiz", tur)
        self.assertIn("kök değil", kanit)

    def test_sitemap_ve_arama_aday_kesiftir(self):
        for yontem, yol, beklenen in (("sitemap_xml", "/sitemap.xml", "sitemap"),
                                      ("root_html", "/search", "arama-sonucu")):
            tur, _i, _k = sozluk.belge_turu_belirle(
                yontem, "text/html", self._sinyal(yol=yol))
            self.assertEqual(beklenen, tur)

    def test_her_belge_turu_sirada_var(self):
        self.assertEqual(set(sozluk.BELGE_TURU), set(sozluk.BELGE_TURU_SIRASI))

    def test_her_belge_turunun_kanit_kurali_yazili(self):
        for anahtar, bilgi in sozluk.BELGE_TURU.items():
            for alan in ("tanim", "kanit", "niyet_degeri"):
                self.assertTrue(bilgi.get(alan, "").strip(), f"{anahtar}/{alan}")


class PilotKayitTests(unittest.TestCase):
    def setUp(self):
        with (HERE / "PILOT-KAYITLAR.csv").open(encoding="utf-8") as handle:
            self.satirlar = list(csv.DictReader(handle))

    def test_her_kayitta_teslim_alanlari_dolu(self):
        """Teslim sarti: source_id, URL, artefakt kimligi, icerik alani, gerekce."""
        for r in self.satirlar:
            for alan in ("source_id", "url", "artefakt_kimligi",
                         "icerik_alani", "siniflandirma_gerekcesi"):
                self.assertTrue(r[alan].strip(), f"{r['kaynak']}/{alan}")

    def test_artefakt_dosyasi_diskte_var(self):
        """Etiket gercek bir artefakta baglanmali."""
        for r in self.satirlar:
            self.assertTrue((HERE / r["dosya"]).exists(), r["kaynak"])

    def test_her_etiket_sozlukte_tanimli(self):
        for r in self.satirlar:
            self.assertIn(r["belge_turu"], sozluk.BELGE_TURU, r["kaynak"])

    def test_aday_kesif_olcum_kaniti_sayilmaz(self):
        """Kabul kriteri: sitemap/arama sonucu kanit degildir."""
        for r in self.satirlar:
            if r["aday_kesif_mi"] == "evet":
                self.assertEqual("hayir", r["olcum_kaniti_uretir_mi"], r["kaynak"])

    def test_ana_sayfa_olcum_kaniti_sayilmaz(self):
        for r in self.satirlar:
            if r["belge_turu"] in ("ana-sayfa", "politika-dosyasi", "belirsiz"):
                self.assertEqual("hayir", r["olcum_kaniti_uretir_mi"], r["kaynak"])

    def test_belirsiz_kayit_gerekcesiz_kalmaz(self):
        for r in self.satirlar:
            if r["belge_turu"] == "belirsiz":
                self.assertIn("kök değil", r["siniflandirma_gerekcesi"], r["kaynak"])

    def test_her_aile_uc_ornek_ya_da_eksik_kaydi(self):
        """Yeterli ornek yoksa eksik acikca yazilmali."""
        import collections
        say = collections.Counter(r["kaynak_ailesi"] for r in self.satirlar)
        with (HERE / "PILOT-EKSIKLER.csv").open(encoding="utf-8") as handle:
            eksik = {r["kaynak_ailesi"] for r in csv.DictReader(handle)}
        for aile, adet in say.items():
            if adet < 3:
                self.assertIn(aile, eksik, f"{aile} eksik kaydı yok")

    def test_ayni_kaynak_birden_cok_aileye_ait_olabilir(self):
        """Kaynak ailesi coklu etiket kurali: aileler kaydedilir, biri secilmez."""
        coklu = [r for r in self.satirlar if r["kaynagin_diger_aileleri"]]
        self.assertTrue(coklu, "hiç çoklu aile örneği yok")


class BelgeCiktisiTests(unittest.TestCase):
    def test_sozluk_belgesi_dort_ekseni_de_iceriyor(self):
        metin = (HERE / "KATEGORI-SOZLUGU.md").read_text(encoding="utf-8")
        for baslik in ("Eksen 1 — Ürün tipi", "Eksen 2 — Kaynak ailesi",
                       "Eksen 3 — Belge türü", "Eksen 4 — Araştırma niyeti"):
            self.assertIn(baslik, metin)

    def test_gunlukte_her_pilot_kayit_var(self):
        metin = (HERE / "INCELEME-GUNLUGU.md").read_text(encoding="utf-8")
        with (HERE / "PILOT-KAYITLAR.csv").open(encoding="utf-8") as handle:
            for r in csv.DictReader(handle):
                self.assertIn(r["artefakt_kimligi"], metin, r["kaynak"])


if __name__ == "__main__":
    unittest.main()
