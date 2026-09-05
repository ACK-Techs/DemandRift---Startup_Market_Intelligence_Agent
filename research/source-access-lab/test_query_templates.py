from __future__ import annotations

import csv
import unittest
import urllib.parse
from pathlib import Path

import compile_queries as derleyici
import query_templates as sablon

HERE = Path(__file__).resolve().parent


class CekirdekTerimTests(unittest.TestCase):
    def test_bilinen_fikirler(self):
        for fikir, beklenen in (
                ("diyabet hastaları için mobil takip uygulaması", "diyabet takip"),
                ("veteriner için randevu sistemi", "veteriner randevu"),
                ("react için bir grafik kütüphanesi", "react grafik")):
            self.assertEqual(beklenen, sablon.cekirdek_terim(fikir), fikir)

    def test_dagitim_bicimi_atilir(self):
        """Magazaya soruyorsak urun zaten mobildir; 'mobil' sorguyu daraltir."""
        self.assertNotIn("mobil", sablon.cekirdek_terim("mobil takip uygulaması"))
        self.assertNotIn("bulut", sablon.cekirdek_terim("bulut tabanlı CRM"))

    def test_urun_soneki_atilir(self):
        for sonek in ("uygulaması", "yazılımı", "sistemi", "kütüphanesi"):
            self.assertNotIn(
                sablon.sadelestir(sonek),
                sablon.sadelestir(sablon.cekirdek_terim(f"fatura {sonek}")))

    def test_konu_kelimesi_korunur(self):
        """Dolgu temizligi konuyu yutmamali."""
        for fikir, konu in (("diyabet takip uygulaması", "diyabet"),
                            ("veteriner randevu sistemi", "veteriner"),
                            ("muhasebeciler için fatura yazılımı", "fatura")):
            self.assertIn(konu, sablon.cekirdek_terim(fikir))

    def test_deterministik(self):
        f = "diyabet hastaları için mobil takip uygulaması"
        self.assertEqual(sablon.cekirdek_terim(f), sablon.cekirdek_terim(f))


class KapsamaTests(unittest.TestCase):
    def test_her_kaynak_grubunun_dili_tanimli(self):
        with (HERE / "KATEGORI-KAYNAK.csv").open(encoding="utf-8") as handle:
            gruplar = {g.strip() for r in csv.DictReader(handle)
                       for g in r["kaynak_grubu"].split(" | ")}
        self.assertEqual(set(), gruplar - set(sablon.GRUP_DILI))

    def test_her_sorunun_niyet_eki_tanimli(self):
        with (HERE / "KATEGORI-SORU.csv").open(encoding="utf-8") as handle:
            sorular = {r["soru_id"] for r in csv.DictReader(handle)}
        self.assertEqual(set(), sorular - set(sablon.NIYET_EKI))

    def test_kullanilmayan_grup_dili_yok(self):
        with (HERE / "KATEGORI-KAYNAK.csv").open(encoding="utf-8") as handle:
            gruplar = {g.strip() for r in csv.DictReader(handle)
                       for g in r["kaynak_grubu"].split(" | ")}
        self.assertEqual(set(), set(sablon.GRUP_DILI) - gruplar)


class SorguMetniTests(unittest.TestCase):
    CEKIRDEK = "diyabet takip"

    def test_ayni_soru_farkli_kaynakta_farkli_metin(self):
        """Gorevin sarti: sorgu kaynaga gore degismeli."""
        magaza = sablon.sorgu_metni(self.CEKIRDEK, "Mobil uygulama mağazaları", "doygun-mu")
        akademik = sablon.sorgu_metni(self.CEKIRDEK, "Akademik araştırma ve bilimsel yayınlar", "doygun-mu")
        self.assertNotEqual(magaza, akademik)

    def test_ayni_kaynak_farkli_soruda_farkli_metin(self):
        """Gorevin sarti: sorgu niyete gore degismeli."""
        grup = "Mobil uygulama mağazaları"
        talep = sablon.sorgu_metni(self.CEKIRDEK, grup, "talep-var-mi")
        sikayet = sablon.sorgu_metni(self.CEKIRDEK, grup, "sikayet-ne")
        self.assertNotEqual(talep, sikayet)
        self.assertIn("problem", sikayet)

    def test_cekirdek_her_metinde_var(self):
        for grup in sablon.GRUP_DILI:
            for soru in sablon.NIYET_EKI:
                self.assertIn(self.CEKIRDEK,
                              sablon.sorgu_metni(self.CEKIRDEK, grup, soru))

    def test_bos_ek_bosluk_birakmaz(self):
        metin = sablon.sorgu_metni(self.CEKIRDEK, "Genel web arama ve keşif", "talep-var-mi")
        self.assertEqual(metin, metin.strip())
        self.assertNotIn("  ", metin)


class DerlemeTests(unittest.TestCase):
    def test_site_aramasi_url_uretir(self):
        tur, sorgu, notu = derleyici.derle(
            "diyabet takip", "site_search",
            {"site_arama": "https://ornek.com/search?q="}, "TR")
        self.assertEqual("uzak-url", tur)
        self.assertIn("diyabet+takip", sorgu)
        self.assertEqual("", notu)

    def test_turkce_karakter_kodlanir(self):
        _tur, sorgu, _n = derleyici.derle(
            "kan şekeri", "site_search", {"site_arama": "https://ornek.com/?q="}, "TR")
        self.assertNotIn("ş", sorgu)
        self.assertIn("%C5%9F", sorgu)

    def test_api_dogru_parametreyi_kullanir(self):
        tur, sorgu, _n = derleyici.derle(
            "diyabet", "api",
            {"api_ucu": "https://api.stackexchange.com/2.3/questions?site=stackoverflow"}, "TR")
        self.assertEqual("uzak-url", tur)
        self.assertIn("&q=diyabet", sorgu)

    def test_serbest_metin_kabul_etmeyen_api_isaretlenir(self):
        tur, sorgu, notu = derleyici.derle(
            "diyabet", "api", {"api_ucu": "https://api.biorxiv.org/details"}, "TR")
        self.assertEqual("", tur)
        self.assertEqual("", sorgu)
        self.assertIn("serbest metin", notu)

    def test_opensearch_sablonu_kaynagin_kendi_tanimindan(self):
        tur, sorgu, _n = derleyici.derle(
            "diyabet takip", "opensearch", {"opensearch": "https://x/opensearch.xml"},
            "TR", {"K": "https://x/store/search?q={searchTerms}"}, "K")
        self.assertEqual("uzak-url", tur)
        self.assertIn("q=diyabet+takip", sorgu)

    def test_sablon_yoksa_url_uydurulmaz(self):
        """Tanim cekilemediyse tahmin edilmis bir URL uretmek yanlis olur."""
        tur, sorgu, notu = derleyici.derle(
            "diyabet", "opensearch", {"opensearch": "https://x/opensearch.xml"},
            "TR", {}, "K")
        self.assertEqual("", tur)
        self.assertEqual("", sorgu)
        self.assertIn("alınamadı", notu)

    def test_doldurulmayan_opensearch_alanlari_atilir(self):
        _t, sorgu, _n = derleyici.derle(
            "diyabet", "opensearch", {"opensearch": "https://x/o.xml"}, "TR",
            {"K": "https://x/s?q={searchTerms}&lang={language}&enc={outputEncoding}"}, "K")
        self.assertNotIn("{", sorgu)
        self.assertNotIn("language", sorgu)

    def test_yerel_yollar_url_uretmez(self):
        """400 kaynagin sayfasi zaten indirilmis; onlara URL uretmek yaniltir."""
        for yol in ("fulltext", "local_index"):
            tur, sorgu, _n = derleyici.derle("diyabet takip", yol, {}, "TR")
            self.assertEqual("yerel-arama", tur)
            self.assertEqual("diyabet takip", sorgu)

    def test_yolu_olmayan_kaynak_gerekcesiyle_isaretlenir(self):
        tur, sorgu, notu = derleyici.derle("diyabet", "yok", {}, "TR")
        self.assertEqual("", tur)
        self.assertTrue(notu)

    def test_pazar_parametresi_yalniz_kabul_edene_eklenir(self):
        _t, google, _n = derleyici.derle(
            "diyabet", "site_search",
            {"site_arama": "https://play.google.com/store/search?q="}, "US")
        self.assertIn("hl=en", google)
        self.assertIn("gl=US", google)
        _t, digeri, _n = derleyici.derle(
            "diyabet", "site_search", {"site_arama": "https://ornek.com/?q="}, "US")
        self.assertNotIn("hl=", digeri)

    def test_pazar_mevcut_parametreyi_bozmaz(self):
        _t, sorgu, _n = derleyici.derle(
            "diyabet", "site_search",
            {"site_arama": "https://play.google.com/store/search?c=apps&q="}, "TR")
        self.assertIn("c=apps", sorgu)
        self.assertIn("hl=tr", sorgu)


class CiktiTests(unittest.TestCase):
    def setUp(self):
        with (HERE / "DERLENMIS-SORGULAR.csv").open(encoding="utf-8") as handle:
            self.satirlar = list(csv.DictReader(handle))

    def test_her_satir_ya_sorgu_ya_gerekce_tasir(self):
        """Gorev 4'un kurali: yapilmayan sey icin neden yazilir."""
        for r in self.satirlar:
            if r["sorgu_turu"]:
                self.assertTrue(r["derlenmis_sorgu"].strip(), r["kaynak"])
                self.assertEqual("", r["derlenemedi_nedeni"], r["kaynak"])
            else:
                self.assertTrue(r["derlenemedi_nedeni"].strip(), r["kaynak"])

    def test_uretilen_url_gecerli(self):
        for r in self.satirlar:
            if r["sorgu_turu"] == "uzak-url":
                ayrik = urllib.parse.urlsplit(r["derlenmis_sorgu"])
                self.assertIn(ayrik.scheme, ("http", "https"), r["kaynak"])
                self.assertTrue(ayrik.netloc, r["kaynak"])

    def test_sorgu_kaynak_ve_soruya_gore_degisiyor(self):
        """Tek bir kelime listesi olsaydi butun satirlar ayni metni tasirdi."""
        metinler = {r["sorgu_metni"] for r in self.satirlar}
        self.assertGreater(len(metinler), len(self.satirlar) * 0.5)

    def test_secim_dosyasindaki_her_yuva_derlendi(self):
        with (HERE / "SECIM-ORNEKLERI.csv").open(encoding="utf-8") as handle:
            yuvalar = list(csv.DictReader(handle))
        self.assertEqual(len(yuvalar), len(self.satirlar))


if __name__ == "__main__":
    unittest.main()
