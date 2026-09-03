from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import keyword_search_pass as ara


class OpenSearchTests(unittest.TestCase):
    def belge(self, *url_satirlari: str) -> bytes:
        return ("<OpenSearchDescription>" + "".join(url_satirlari) + "</OpenSearchDescription>").encode()

    def test_html_sablonu_tercih_edilir(self):
        xml = self.belge(
            '<Url type="application/x-suggestions+json" template="https://a.example/sug?q={searchTerms}"/>',
            '<Url type="text/html" template="https://a.example/search?q={searchTerms}"/>',
        )
        self.assertEqual("https://a.example/search?q={searchTerms}", ara.opensearch_sablonu(xml))

    def test_sorgu_yeri_olmayan_sablon_kullanilmaz(self):
        xml = self.belge('<Url type="text/html" template="https://a.example/search"/>')
        self.assertIsNone(ara.opensearch_sablonu(xml))

    def test_kelime_yerine_konur_ve_kalan_belirtecler_temizlenir(self):
        dolu = ara.sablonu_doldur(
            "https://a.example/search?q={searchTerms}&start={startIndex}", "fitness app",
        )
        self.assertEqual("https://a.example/search?q=fitness%20app&start=", dolu)


class SorguParametresiTests(unittest.TestCase):
    def test_mevcut_sorgu_degeri_degistirilir(self):
        self.assertEqual(
            "https://a.example/search?q=fitness&page=2",
            ara.sorgu_parametresini_degistir("https://a.example/search?q=eski&page=2", "fitness"),
        )

    def test_bos_biten_kalibin_sonuna_eklenir(self):
        self.assertEqual(
            "https://a.example/search?query=fitness",
            ara.sorgu_parametresini_degistir("https://a.example/search?query=", "fitness"),
        )

    def test_sorgu_alani_yoksa_uydurulmaz(self):
        self.assertIsNone(
            ara.sorgu_parametresini_degistir("https://a.example/browse?page=2", "fitness"),
        )


class AramaUrlTests(unittest.TestCase):
    def satir(self, **ek):
        temel = {"en_iyi_yol": "site_search", "site_arama": "", "api_ucu": "", "adres": "https://a.example"}
        temel.update(ek)
        return temel

    def test_site_arama_kalibindaki_yer_tutucu_doldurulur(self):
        url = ara.arama_url(
            self.satir(site_arama="https://a.example/search?query={kelime}"), "fitness app",
        )
        self.assertEqual("https://a.example/search?query=fitness%20app", url)

    def test_api_ucundaki_sorgu_degistirilir(self):
        url = ara.arama_url(
            self.satir(en_iyi_yol="api", api_ucu="https://api.a.example/v1?q=stars&per_page=5"),
            "fitness",
        )
        self.assertEqual("https://api.a.example/v1?q=fitness&per_page=5", url)

    def test_yerel_dizin_satiri_canli_url_uretmez(self):
        self.assertIsNone(ara.arama_url(self.satir(en_iyi_yol="local_index"), "fitness"))


class YerelAramaTests(unittest.TestCase):
    def dizin(self, *satirlar: str) -> Path:
        gecici = Path(tempfile.mkdtemp()) / "dizin.tsv"
        gecici.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
        return gecici

    def test_tireli_ve_bitisik_yazim_ayni_kelimeyi_bulur(self):
        dizin = self.dizin(
            "s1\tBir\thttps://a.example/blog/fitness-app-market",
            "s2\tIki\thttps://b.example/fitnessapp",
            "s3\tUc\thttps://c.example/hakkinda",
        )
        vurus = ara.yerel_ara("fitness app", dizin)
        self.assertEqual(["s1", "s2"], [v["source_id"] for v in vurus])

    def test_kelimeler_dagitik_gecse_de_bulunur(self):
        dizin = self.dizin("s1\tBir\thttps://a.example/apps/fitness/tracker")
        self.assertEqual(1, len(ara.yerel_ara("fitness app", dizin)))

    def test_kelimelerden_yalnizca_biri_gecerse_bulunmaz(self):
        dizin = self.dizin("s1\tBir\thttps://a.example/blog/fitness-news")
        self.assertEqual([], ara.yerel_ara("fitness app", dizin))

    def test_limit_asilmaz(self):
        dizin = self.dizin(*[f"s{i}\tKaynak\thttps://a.example/fitness-{i}" for i in range(50)])
        self.assertEqual(5, len(ara.yerel_ara("fitness", dizin, limit=5)))

    def test_eksik_dizin_kosuyu_dusurmez(self):
        self.assertEqual([], ara.yerel_ara("fitness", Path("/yok/olmayan.tsv")))


if __name__ == "__main__":
    unittest.main()
