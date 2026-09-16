from __future__ import annotations

import collections
import csv
import json
import unittest
from pathlib import Path

import veri_envanteri as env

HERE = Path(__file__).resolve().parent


class KanonikKimlikTests(unittest.TestCase):
    """Kabul kriteri: kanonik source_id korunur, tüm adaylar görünür."""

    def setUp(self):
        with (HERE / "VERI-ENVANTERI.csv").open(encoding="utf-8") as handle:
            self.satirlar = list(csv.DictReader(handle))
        self.manifest = json.loads(
            (HERE / "source_manifest.json").read_text(encoding="utf-8"))["sources"]

    def test_her_manifest_kaynagi_envanterde(self):
        manifest_id = {s["source_id"] for s in self.manifest}
        envanter_id = {r["source_id"] for r in self.satirlar}
        self.assertEqual(manifest_id, envanter_id)

    def test_source_id_tekrar_etmez(self):
        say = collections.Counter(r["source_id"] for r in self.satirlar)
        self.assertEqual([], [k for k, v in say.items() if v > 1])

    def test_manifeste_yabanci_kimlik_yok(self):
        manifest_id = {s["source_id"] for s in self.manifest}
        for r in self.satirlar:
            self.assertIn(r["source_id"], manifest_id)


class ErisimIcerikAyrimiTests(unittest.TestCase):
    """Kabul kriteri: erişildi etiketi karar kanıtı sayılmaz."""

    def setUp(self):
        with (HERE / "VERI-ENVANTERI.csv").open(encoding="utf-8") as handle:
            self.satirlar = list(csv.DictReader(handle))

    def test_erisim_ve_icerik_ayri_sutunlar(self):
        for r in self.satirlar:
            self.assertIn("erisim_durumu", r)
            self.assertIn("icerik_durumu", r)

    def test_cekildi_etiketi_icerik_garanti_etmez(self):
        """Ölçülmüş gerçek: 'cekildi' kaynakların bir kısmında açılabilir dosya yok."""
        cekildi = [r for r in self.satirlar if r["erisim_durumu"] == "cekildi"]
        dosyasiz = [r for r in cekildi if r["icerik_durumu"] == "dosya-yok"]
        self.assertTrue(dosyasiz, "erişim/içerik ayrımı ölçülememiş")
        self.assertLess(len(dosyasiz), len(cekildi))

    def test_erisilemeyen_kaynakta_icerik_olamaz(self):
        for r in self.satirlar:
            if r["erisim_durumu"] in ("erisim_yok", "adres_yok"):
                self.assertEqual("dosya-yok", r["icerik_durumu"], r["ad"])

    def test_icerik_durumu_tanimli_kumeden(self):
        for r in self.satirlar:
            self.assertIn(r["icerik_durumu"], env.ICERIK_SIRASI, r["ad"])


class ElindeOlmayanIncelenmisSayilmazTests(unittest.TestCase):
    """Kabul kriteri: elde olmayan dosyalar incelenmiş gösterilmez."""

    def setUp(self):
        with (HERE / "VERI-ENVANTERI.csv").open(encoding="utf-8") as handle:
            self.satirlar = list(csv.DictReader(handle))

    def test_dosyasi_olmayan_kaynak_incelenmis_olamaz(self):
        for r in self.satirlar:
            if int(r["dosyasi_diskte"]) == 0:
                self.assertEqual("hayir", r["incelendi"], r["ad"])

    def test_incelenen_kaynak_artefakt_kimligi_tasir(self):
        for r in self.satirlar:
            if r["incelendi"] == "evet":
                self.assertTrue(r["incelenen_artefakt"].strip(), r["ad"])

    def test_sayimlar_tutarli(self):
        """Başarılı artefakt = diskte + gövdesiz + kayıp."""
        for r in self.satirlar:
            toplam = (int(r["dosyasi_diskte"]) + int(r["govdesi_saklanmamis"])
                      + int(r["dizinde_var_diskte_yok"]))
            self.assertEqual(int(r["artefakt_basarili"]), toplam, r["ad"])

    def test_eksik_olan_kaynak_gerekce_tasir(self):
        for r in self.satirlar:
            if int(r["dizinde_var_diskte_yok"]) or int(r["govdesi_saklanmamis"]):
                self.assertTrue(r["eksik"].strip(), r["ad"])


class YuzeyAyrimiTests(unittest.TestCase):
    """Sitemap, robots, ana sayfa, API, bot sayfası ve arşiv karıştırılmaz."""

    def test_sitemap_aday_kesiftir(self):
        self.assertEqual("aday-kesif", env.yuzey_turu("sitemap_xml"))

    def test_robots_politikadir(self):
        self.assertEqual("politika", env.yuzey_turu("robots_preflight"))

    def test_arsiv_ayri_turdur(self):
        self.assertEqual("arsiv", env.yuzey_turu("common_crawl_warc"))

    def test_bilinmeyen_yontem_api_sayilir(self):
        self.assertEqual("api-yaniti", env.yuzey_turu("npm_registry_search"))

    def test_bos_metinli_buyuk_html_js_kabugudur(self):
        ham = b"<html><head><title>X</title></head><body>" + b"<div></div>" * 4000 + b"</body></html>"
        durum, gerekce = env.icerik_durumu("root_html", "text/html", ham)
        self.assertEqual("js-kabugu", durum)
        self.assertIn("görünür metin", gerekce)

    def test_metin_tasiyan_sayfa_gercek_icerik(self):
        govde = ("Bu sayfada gerçek metin var. " * 40).encode()
        ham = b"<html><head><title>X</title></head><body><p>" + govde + b"</p></body></html>"
        durum, _g = env.icerik_durumu("root_html", "text/html", ham)
        self.assertEqual("gercek-icerik", durum)

    def test_engel_sayfasi_yalniz_basliktan_taninir(self):
        """Gövdede 'captcha' geçmesi yetmez: sayfanın kendi scriptleri de taşır."""
        ham = (b"<html><head><title>Access Denied</title></head>"
               b"<body>short</body></html>")
        durum, _g = env.icerik_durumu("root_html", "text/html", ham)
        self.assertEqual("engel-sayfasi", durum)

        govde = ("Normal içerik metni burada. " * 40).encode()
        yanlis = (b"<html><head><title>Brave Search</title></head><body><p>"
                  + govde + b" captcha </p></body></html>")
        durum2, _g2 = env.icerik_durumu("root_html", "text/html", yanlis)
        self.assertEqual("gercek-icerik", durum2)


class IslenemeyenKayitTests(unittest.TestCase):
    def setUp(self):
        with (HERE / "ENVANTER-ISLENEMEYEN.csv").open(encoding="utf-8") as handle:
            self.satirlar = list(csv.DictReader(handle))

    def test_her_kayit_neden_tasir(self):
        for r in self.satirlar:
            self.assertTrue(r["neden"].strip(), r["ad"])

    def test_nedenler_iki_turden(self):
        for r in self.satirlar:
            self.assertTrue(
                r["neden"].startswith("gövde saklanmamış")
                or r["neden"].startswith("dizinde 'dosya' yazıyor"), r["neden"])

    def test_kayitlar_envanterdeki_sayimla_uyusur(self):
        with (HERE / "VERI-ENVANTERI.csv").open(encoding="utf-8") as handle:
            envanter = list(csv.DictReader(handle))
        beklenen = sum(int(r["govdesi_saklanmamis"]) + int(r["dizinde_var_diskte_yok"])
                       for r in envanter)
        self.assertEqual(beklenen, len(self.satirlar))


class RaporTests(unittest.TestCase):
    def test_kapsama_raporu_capraz_tabloyu_iceriyor(self):
        metin = (HERE / "KAPSAMA-RAPORU.md").read_text(encoding="utf-8")
        self.assertIn("Erişim durumu × içerik durumu", metin)
        self.assertIn("karar kanıtı değildir", metin)

    def test_gun2_plani_uretildi(self):
        """Kabul kriteri: gün 2 örneklem planı çıkarılır."""
        metin = (HERE / "GUN2-ORNEKLEM-PLANI.md").read_text(encoding="utf-8")
        self.assertIn("Örneklem kuralı", metin)
        self.assertIn("eksik kaydı", metin)

    def test_kapsama_raporu_aile_bazinda_rapor_veriyor(self):
        """Kabul kriteri: işlenen ve bekleyen miktar kategori bazında raporlanır."""
        metin = (HERE / "KAPSAMA-RAPORU.md").read_text(encoding="utf-8")
        self.assertIn("Kaynak ailesi bazında kapsama", metin)
        self.assertIn("Bekleyen", metin)


if __name__ == "__main__":
    unittest.main()
