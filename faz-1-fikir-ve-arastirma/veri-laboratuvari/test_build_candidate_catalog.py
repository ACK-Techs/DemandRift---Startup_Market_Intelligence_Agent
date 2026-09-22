from __future__ import annotations

import collections
import csv
import unittest
from pathlib import Path

import build_candidate_catalog as katalog

HERE = Path(__file__).resolve().parent


class YuzeyRoluTests(unittest.TestCase):
    def test_veri_tasiyan_yuzeyler(self):
        for yontem in ("root_html", "entry_url", "common_crawl_warc"):
            self.assertEqual("veri", katalog.yuzey_rolu(yontem))

    def test_sitemap_kesiftir_veri_degildir(self):
        """Sitemap nereye bakilacagini soyler, kendisi arastirma verisi tasimaz."""
        self.assertEqual("kesif", katalog.yuzey_rolu("sitemap_xml"))

    def test_robots_arastirma_yuzeyi_degildir(self):
        self.assertEqual("politika", katalog.yuzey_rolu("robots_preflight"))

    def test_rss_karma_sayilir(self):
        """RSS baslik ve ozet tasir; tam icerik icin baglantiya gitmek gerekir."""
        self.assertEqual("karma", katalog.yuzey_rolu("rss_feed"))

    def test_bilinmeyen_api_yontemi_veri_sayilir(self):
        """API yanit adlari kaynaga gore degisir; varsayilan veri olmali."""
        self.assertEqual("veri", katalog.yuzey_rolu("stackexchange_questions"))
        self.assertEqual("veri", katalog.yuzey_rolu("yeni_bir_api_ucu"))


class HostTests(unittest.TestCase):
    def test_www_oneki_ayni_host_sayilir(self):
        self.assertEqual(katalog.sade_host("https://www.bing.com"),
                         katalog.sade_host("https://bing.com"))

    def test_alt_alan_adi_ayri_hosttur(self):
        """news.google.com ile google.com ayri sitelerdir; birlestirmek yanlis olur."""
        self.assertNotEqual(katalog.sade_host("https://news.google.com"),
                            katalog.sade_host("https://google.com"))

    def test_adressiz_kaynak_bos_host_verir(self):
        self.assertEqual("", katalog.sade_host(""))


class KatalogTests(unittest.TestCase):
    def setUp(self):
        with (HERE / "ADAY-KATALOG.csv").open(encoding="utf-8") as handle:
            self.satirlar = list(csv.DictReader(handle))

    def test_defterdeki_her_kaynak_katalogda(self):
        with (HERE / "KAYNAK-DEFTERI.csv").open(encoding="utf-8") as handle:
            defter = list(csv.DictReader(handle))
        self.assertEqual(len(defter), len(self.satirlar))

    def test_host_paylasimi_karsilikli(self):
        """A, B'yi kardes goruyorsa B de A'yi gormeli."""
        kardes = {r["ad"]: set(filter(None, (a.strip() for a in r["host_kardesleri"].split(","))))
                  for r in self.satirlar}
        for ad, kardesleri in kardes.items():
            for k in kardesleri:
                self.assertIn(ad, kardes.get(k, set()), f"{ad} <-> {k}")

    def test_yalniz_kesif_kaynagin_veri_yuzeyi_yok(self):
        for r in self.satirlar:
            if r["arastirma_degeri"] == "yalniz-kesif":
                self.assertEqual("", r["veri_yuzeyi"], r["ad"])
                self.assertTrue(r["kesif_yuzeyi"], r["ad"])

    def test_veri_var_diyen_kaynagin_veri_yuzeyi_dolu(self):
        for r in self.satirlar:
            if r["arastirma_degeri"] == "veri-var":
                self.assertTrue(r["veri_yuzeyi"], r["ad"])

    def test_defterin_cekildi_sayisi_uce_ayrilir(self):
        """Katalog defteri bozmaz, ayristirir: cekildi = veri + karma + kesif."""
        with (HERE / "KAYNAK-DEFTERI.csv").open(encoding="utf-8") as handle:
            cekildi = {r["ad"] for r in csv.DictReader(handle) if r["durum"] == "cekildi"}
        deger = collections.Counter(
            r["arastirma_degeri"] for r in self.satirlar if r["ad"] in cekildi)
        self.assertEqual(len(cekildi),
                         deger["veri-var"] + deger["kismi-veri"] + deger["yalniz-kesif"])

    def test_paylasimli_host_sayisi_kardes_sayisiyla_tutarli(self):
        for r in self.satirlar:
            kardes = [a for a in r["host_kardesleri"].split(",") if a.strip()]
            if r["host"]:
                self.assertEqual(int(r["host_marka_sayisi"]), len(kardes) + 1, r["ad"])


if __name__ == "__main__":
    unittest.main()
