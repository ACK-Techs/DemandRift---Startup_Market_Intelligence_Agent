"""SourceFitMatrix'in kabul kriterlerini koruyan testler.

Gorev kartinin dort sarti test edilir: her eslesme incelenmis icerige dayanir,
veri olmayan kategori acik gap tasir, ayni kaynagin kopyalari bagimsiz
sayilmaz, ve beyan edilen odeme istegi gercek odeme davranisindan ayrilir.
"""
from __future__ import annotations

import collections
import csv
import unittest
from pathlib import Path

import source_fit_matrix as sfm

HERE = Path(__file__).resolve().parent


def oku(ad: str) -> list[dict[str, str]]:
    with (HERE / ad).open(encoding="utf-8") as tutamak:
        return list(csv.DictReader(tutamak))


class IncelenmisIcerikSartiTests(unittest.TestCase):
    """Kabul kriteri: her onerilen eslesme incelenmis icerikle desteklenir."""

    @classmethod
    def setUpClass(cls):
        cls.matris = oku("SOURCE-FIT-MATRIX.csv")
        cls.belgeler = {r["document_id"]: r for r in oku("NORMALIZE-BELGELER.csv")}

    def test_her_satir_ornek_kayit_tasir(self):
        for r in self.matris:
            self.assertTrue(r["ornek_kayit"].strip(), r["source_id"])

    def test_ornek_kayit_gercek_bir_belgeyi_isaret_eder(self):
        for r in self.matris:
            belge_id = r["ornek_kayit"].split(" · ")[0]
            self.assertIn(belge_id, self.belgeler, r["source_id"])

    def test_ornek_kayit_diskteki_dosyaya_kadar_izlenebilir(self):
        for r in self.matris:
            belge = self.belgeler[r["ornek_kayit"].split(" · ")[0]]
            self.assertTrue(belge["body_original_ref"].strip(), r["source_id"])
            self.assertEqual(64, len(belge["artifact_hash"]))

    def test_her_satir_kanit_gerekcesi_tasir(self):
        for r in self.matris:
            self.assertTrue(r["kanit_gerekcesi"].strip(), r["source_id"])

    def test_bos_belge_eslesme_uretmez(self):
        """Gorunur metni olmayan belge kanit sayilmaz."""
        for r in self.matris:
            belge = self.belgeler[r["ornek_kayit"].split(" · ")[0]]
            self.assertGreater(int(belge["body_uzunlugu"]), 0, r["source_id"])


class GapAcikTasinirTests(unittest.TestCase):
    """Kabul kriteri: veri olmayan kategori acik gap tasir."""

    @classmethod
    def setUpClass(cls):
        cls.yeterlilik = oku("KATEGORI-YETERLILIK.csv")

    def test_her_kategori_niyet_cifti_satir_tasir(self):
        """Hucre atlanmaz: kanit yoksa bile satiri vardir."""
        kategoriler = {r["kategori"] for r in self.yeterlilik}
        self.assertEqual(len(kategoriler) * len(sfm.NIYETLER), len(self.yeterlilik))

    def test_bos_hucre_sebep_kodu_tasir(self):
        for r in self.yeterlilik:
            if r["durum"] in ("bos", "zayif"):
                self.assertTrue(r["gap_kodu"].strip(), f'{r["kategori"]}/{r["arama_niyeti"]}')
                self.assertTrue(r["gap_aciklamasi"].strip())

    def test_gap_aciklamasi_pazar_sonucu_iddia_etmez(self):
        """Veri yoklugu olumsuz pazar sonucu olarak yorumlanmaz."""
        yasak = ("talep yok", "pazar yok", "pazar kötü", "ilgi yok", "potansiyel yok")
        for r in self.yeterlilik:
            for kelime in yasak:
                self.assertNotIn(kelime, r["gap_aciklamasi"].casefold(),
                                 f'{r["kategori"]}/{r["arama_niyeti"]}')

    def test_gap_kodlari_tanimli_kumeden(self):
        gecerli = {"", "yontem-disi", "yuzey-bulunamadi", "js-kabugu",
                   "erisilemiyor", "icerik-yok", "kaynak-yok", "tek-grup"}
        for r in self.yeterlilik:
            self.assertIn(r["gap_kodu"], gecerli, r["kategori"])

    def test_yeterli_hucre_gap_tasimaz(self):
        for r in self.yeterlilik:
            if r["durum"] == "yeterli":
                self.assertEqual("", r["gap_kodu"])


class KopyalarBagimsizSayilmazTests(unittest.TestCase):
    """Kabul kriteri: ayni kaynagin kopyalari bagimsiz sayilmaz."""

    @classmethod
    def setUpClass(cls):
        cls.matris = oku("SOURCE-FIT-MATRIX.csv")
        cls.yeterlilik = oku("KATEGORI-YETERLILIK.csv")

    def test_ayni_alan_adi_ayni_grupta(self):
        self.assertEqual(sfm.kayitli_alan("https://www.g2.com/a"),
                         sfm.kayitli_alan("https://track.g2.com/b"))

    def test_bagimsiz_grup_kaynak_sayisini_gecemez(self):
        for r in self.yeterlilik:
            self.assertLessEqual(int(r["bagimsiz_grup"]), int(r["kanit_veren_kaynak"]),
                                 r["kategori"])

    def test_tek_gruplu_hucre_yeterli_sayilmaz(self):
        for r in self.yeterlilik:
            if int(r["bagimsiz_grup"]) < sfm.YETERLI_GRUP:
                self.assertNotEqual("yeterli", r["durum"],
                                    f'{r["kategori"]}/{r["arama_niyeti"]}')

    def test_fallback_farkli_gruptan_secilir(self):
        grup = {r["source_id"]: r["bagimsizlik_grubu"] for r in self.matris}
        ad_kimlik = {r["kaynak_adi"]: r["source_id"] for r in self.matris}
        for r in self.matris:
            if r["fallback"] == "(bağımsız yedek YOK)":
                continue
            yedek = ad_kimlik.get(r["fallback"])
            if yedek:
                self.assertNotEqual(grup[r["source_id"]], grup[yedek], r["source_id"])


class BeyanOdemeDavranisindanAyriTests(unittest.TestCase):
    """Kabul kriteri: beyan edilen odeme istegi gercek odeme davranisindan ayrilir."""

    def test_iki_fiyat_niyeti_ayri_deger(self):
        self.assertIn("observed_market_pricing", sfm.NIYETLER)
        self.assertIn("stated_wtp_weak_signal", sfm.NIYETLER)

    def test_beyan_niyetinin_tanimi_uyari_tasir(self):
        tanim = sfm.NIYET_TANIMI["stated_wtp_weak_signal"].casefold()
        self.assertIn("zayif beyan", tanim.replace("î", "i").replace("ı", "i"))
        self.assertIn("gerçek ödeme davranışı sayılmaz", sfm.NIYET_TANIMI["stated_wtp_weak_signal"])

    def test_fiyat_alani_beyan_niyetine_baglanmaz(self):
        """Sayfada yazan fiyat, kullanicinin odeme beyani degildir."""
        self.assertEqual("observed_market_pricing", sfm.ALAN_NIYETI["fiyat"])
        self.assertNotIn("stated_wtp_weak_signal", set(sfm.ALAN_NIYETI.values()))

    def test_beyan_niyeti_kanitsiz_ve_gap_tasiyor(self):
        """Bu veri kumesinde beyan sinyali taranmadi; uydurma satir uretilmemeli."""
        matris = oku("SOURCE-FIT-MATRIX.csv")
        self.assertEqual([], [r for r in matris
                              if r["arama_niyeti"] == "stated_wtp_weak_signal"])
        yeterlilik = oku("KATEGORI-YETERLILIK.csv")
        beyan = [r for r in yeterlilik if r["arama_niyeti"] == "stated_wtp_weak_signal"]
        self.assertTrue(beyan)
        for r in beyan:
            self.assertEqual("yontem-disi", r["gap_kodu"])


class ErisimAnligiGarantiDegildirTests(unittest.TestCase):
    def test_her_satir_erisim_anligi_uyarisi_tasir(self):
        for r in oku("SOURCE-FIT-MATRIX.csv"):
            self.assertIn("GÜNCEL İZİN GARANTİSİ DEĞİL", r["erisim_kisiti"],
                          r["source_id"])

    def test_tarihsiz_belge_tazelik_iddia_etmez(self):
        for r in oku("SOURCE-FIT-MATRIX.csv"):
            if "yayın tarihi YOK" in r["tazelik"]:
                self.assertIn("toplama anı", r["tazelik"])


class PaketTests(unittest.TestCase):
    """Gorev 7'nin kurali: Deep 'kontrolsuz daha cok site' degildir."""

    @classmethod
    def setUpClass(cls):
        cls.paketler = oku("PAKET-ONERILERI.csv")

    def test_her_kategori_iki_paket_tasir(self):
        say = collections.Counter(r["kategori"] for r in self.paketler)
        for kategori, adet in say.items():
            self.assertEqual(2, adet, kategori)

    def test_deep_standarttan_az_kapsamaz(self):
        bazinda = collections.defaultdict(dict)
        for r in self.paketler:
            bazinda[r["kategori"]][r["paket"]] = r
        for kategori, paketler in bazinda.items():
            self.assertGreaterEqual(int(paketler["deep"]["kapsanan_niyet"]),
                                    int(paketler["standard"]["kapsanan_niyet"]), kategori)
            self.assertGreaterEqual(int(paketler["deep"]["bagimsiz_grup"]),
                                    int(paketler["standard"]["bagimsiz_grup"]), kategori)

    def test_deep_farki_bagimsizlikta_olmali(self):
        """Deep daha cok kaynak aliyorsa, bagimsiz grup da artmali."""
        bazinda = collections.defaultdict(dict)
        for r in self.paketler:
            bazinda[r["kategori"]][r["paket"]] = r
        for kategori, paketler in bazinda.items():
            if int(paketler["deep"]["kaynak_sayisi"]) > int(paketler["standard"]["kaynak_sayisi"]):
                self.assertGreater(int(paketler["deep"]["bagimsiz_grup"]),
                                   int(paketler["standard"]["bagimsiz_grup"]), kategori)

    def test_her_paket_gerekce_tasir(self):
        for r in self.paketler:
            self.assertTrue(r["gerekce"].strip(), r["kategori"])

    def test_kapsanmayan_niyet_gizlenmiyor(self):
        for r in self.paketler:
            if int(r["kapsanan_niyet"]) < len(sfm.NIYETLER):
                self.assertNotEqual("(yok)", r["kapsanmayan_niyet"], r["kategori"])


class SemaTaslagiTests(unittest.TestCase):
    """Kabul kriteri: Ayse Sena icin sema/alan taslagi paylasilir."""

    @classmethod
    def setUpClass(cls):
        cls.metin = (HERE / "SOURCEFIT-SEMA.md").read_text(encoding="utf-8")

    def test_matrisin_her_sutunu_semada_aciklanmis(self):
        for sutun in oku("SOURCE-FIT-MATRIX.csv")[0]:
            if sutun in ("kategori", "niyet_tanimi", "kaynak_adi",
                         "ornek_kayit_basligi"):
                continue
            self.assertIn(f"`{sutun}`", self.metin, sutun)

    def test_yedi_niyetin_hepsi_semada(self):
        for niyet in sfm.NIYETLER:
            self.assertIn(f"`{niyet}`", self.metin, niyet)

    def test_sema_iki_fiyat_niyetinin_farkini_anlatiyor(self):
        self.assertIn("İki fiyat niyeti neden ayrı", self.metin)

    def test_sema_gap_kodlarini_listeliyor(self):
        for kod in ("yontem-disi", "yuzey-bulunamadi", "js-kabugu"):
            self.assertIn(kod, self.metin)


if __name__ == "__main__":
    unittest.main()
