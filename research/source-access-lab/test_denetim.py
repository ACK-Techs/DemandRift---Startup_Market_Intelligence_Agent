"""DR-L05 denetiminin kabul kriterlerini koruyan testler.

Uc sart test edilir: ciktilar source_id ve kayit kimlikleriyle baglanir,
etiketleme tekrar uygulanabilir ve ham kaynak degismez, kategoriler
orneklerle dogrulanir ve gecersiz proxy cikarimlari acikca gosterilir.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import unittest
from pathlib import Path

import denetim as dn
import source_fit_matrix as sfm

HERE = Path(__file__).resolve().parent


def oku(ad: str) -> list[dict[str, str]]:
    with (HERE / ad).open(encoding="utf-8") as tutamak:
        return list(csv.DictReader(tutamak))


class KimlikleBaglanmaTests(unittest.TestCase):
    """Kabul kriteri: ciktilar source_id ve artefakt/kayit kimlikleriyle baglanir."""

    @classmethod
    def setUpClass(cls):
        cls.belgeler = {r["document_id"]: r for r in oku("NORMALIZE-BELGELER.csv")}
        cls.kaynaklar = {r["source_id"] for r in oku("VERI-ENVANTERI.csv")}

    def test_bulgular_gercek_belgeye_baglanir(self):
        for r in oku("DENETIM-BULGULARI.csv"):
            self.assertIn(r["document_id"], self.belgeler)
            self.assertIn(r["source_id"], self.kaynaklar)

    def test_ornekler_gercek_belgeye_baglanir(self):
        for r in oku("DENETIM-ORNEKLERI.csv"):
            self.assertIn(r["document_id"], self.belgeler)

    def test_veri_paketi_ornekleri_artefakta_kadar_izlenir(self):
        for r in oku("VERI-PAKETI-ORNEKLERI.csv"):
            belge = self.belgeler[r["document_id"]]
            self.assertTrue(belge["artifact_hash"].startswith(r["artifact_hash"]))
            self.assertTrue(belge["body_original_ref"].strip())

    def test_teslim_paketindeki_her_dosya_var(self):
        for dosya, _rol, _anahtar in dn.TESLIM_PAKETI:
            self.assertTrue((HERE / dosya).exists(), dosya)


class HamKaynakDegismezTests(unittest.TestCase):
    """Kabul kriteri: ham kaynak degismez."""

    def test_ornek_artefaktin_hashi_dogrulanir(self):
        """artifact_hash diskteki dosyanin SHA-256'si olmali."""
        kontrol = 0
        for r in oku("NORMALIZE-BELGELER.csv"):
            yol = HERE / r["body_original_ref"]
            if not yol.exists():
                continue
            self.assertEqual(r["artifact_hash"],
                             hashlib.sha256(yol.read_bytes()).hexdigest(),
                             r["source_adi"])
            kontrol += 1
            if kontrol >= 25:
                break
        self.assertGreater(kontrol, 0, "hiç artefakt doğrulanamadı")

    def test_denetim_yazma_yapmaz(self):
        """denetle() yalniz okur; cikti yazmak main()'in isidir."""
        once = {p.name: p.stat().st_mtime for p in (HERE / "results" / "raw").glob("*.bin")} \
            if (HERE / "results" / "raw").exists() else {}
        dn.denetle()
        sonra = {p.name: p.stat().st_mtime for p in (HERE / "results" / "raw").glob("*.bin")} \
            if (HERE / "results" / "raw").exists() else {}
        self.assertEqual(once, sonra)


class EtiketlemeTekrarUygulanabilirTests(unittest.TestCase):
    """Kabul kriteri: etiketleme tekrar uygulanabilir."""

    def test_ornek_secimi_deterministik(self):
        birinci = [r["document_id"] for r in dn.denetle()["incelenen"]]
        ikinci = [r["document_id"] for r in dn.denetle()["incelenen"]]
        self.assertEqual(birinci, ikinci)

    def test_bulgular_iki_kosuda_ayni(self):
        anahtar = lambda s: sorted((b["document_id"], b["bulgu_turu"])
                                   for b in s["bulgular"])
        self.assertEqual(anahtar(dn.denetle()), anahtar(dn.denetle()))

    def test_etiket_kurali_yol_tek_basina_yetmez(self):
        """DR-L02 kurali: site adina bakarak etiketleme yapilmaz."""
        self.assertIsNone(dn.onerilen_etiket("/reviews", "burada hiçbir şey yok"))
        self.assertIsNotNone(
            dn.onerilen_etiket("/reviews", "Read reviews and ratings from users"))

    def test_icerik_tek_basina_da_yetmez(self):
        self.assertIsNone(
            dn.onerilen_etiket("/rastgele-yol", "reviews ratings stars"))


class OrneklerleDogrulamaTests(unittest.TestCase):
    """Kabul kriteri: kategoriler orneklerle dogrulanir."""

    @classmethod
    def setUpClass(cls):
        cls.ornekler = oku("VERI-PAKETI-ORNEKLERI.csv")
        cls.incelenen = oku("DENETIM-ORNEKLERI.csv")

    def test_her_kategoriden_ornek_incelendi(self):
        kategoriler = {r["kategori"] for r in oku("KALITE-METRIKLERI.csv")
                       if int(r["kayit"]) > 0}
        incelenen = {r["kategori"] for r in self.incelenen}
        self.assertEqual(kategoriler, incelenen)

    def test_ornek_niyetine_uygun_veri_gosterir(self):
        """Fiyat, dissatisfaction ornegi olarak gosterilemez."""
        for r in self.ornekler:
            for parca in r["bulunan_veri"].split(" | "):
                alan = parca.split("=")[0]
                self.assertEqual(sfm.ALAN_NIYETI.get(alan), r["arama_niyeti"],
                                 f'{r["kategori"]}/{r["arama_niyeti"]}: {alan}')

    def test_her_ornek_cevapladigi_soruyu_yazar(self):
        for r in self.ornekler:
            self.assertTrue(r["cevaplanan_soru"].strip())
            self.assertEqual(dn.NIYET_SORUSU[r["arama_niyeti"]], r["cevaplanan_soru"])

    def test_her_ornek_sinirini_soyler(self):
        for r in self.ornekler:
            self.assertTrue(r["sinir"].strip())


class GecersizProxyAcikTests(unittest.TestCase):
    """Kabul kriteri: gecersiz proxy cikarimlari acikca gosterilir."""

    def test_gecersiz_proxy_listesi_bos_degil(self):
        self.assertGreaterEqual(len(dn.GECERSIZ_PROXY), 5)

    def test_her_proxy_kaydi_neden_tasir(self):
        for alan, cikarim, neden in dn.GECERSIZ_PROXY:
            self.assertTrue(alan.strip())
            self.assertTrue(cikarim.strip())
            self.assertGreater(len(neden), 40, alan)

    def test_indirme_talep_sayilmaz(self):
        alanlar = {a for a, _c, _n in dn.GECERSIZ_PROXY}
        self.assertIn("engagement_indirme_sayisi", alanlar)

    def test_veri_yoklugu_talep_yoklugu_sayilmaz(self):
        alanlar = {a for a, _c, _n in dn.GECERSIZ_PROXY}
        self.assertIn("icerik_yoklugu", alanlar)

    def test_rapor_proxy_bolumunu_iceriyor(self):
        metin = (HERE / "KALITE-RAPORU.md").read_text(encoding="utf-8")
        self.assertIn("Geçersiz proxy çıkarımları", metin)
        self.assertIn("YAPILAMAZ", metin)

    def test_devir_notu_neye_guvenilmemeli_diyor(self):
        metin = (HERE / "DEVIR-NOTU.md").read_text(encoding="utf-8")
        self.assertIn("Neye güvenilmemeli", metin)


class KalanIsTests(unittest.TestCase):
    """Kabul kriteri: biten kapsam ve onceliklendirilmis kalan acik sayilarla."""

    @classmethod
    def setUpClass(cls):
        cls.kalan = oku("KALAN-IS.csv")

    def test_her_kalem_adet_ve_neden_tasir(self):
        for r in self.kalan:
            self.assertTrue(r["adet"].isdigit(), r["is"])
            self.assertTrue(r["neden_kaldi"].strip(), r["is"])

    def test_oncelik_sirasi_tekil_ve_artan(self):
        oncelikler = [int(r["oncelik"]) for r in self.kalan]
        self.assertEqual(sorted(set(oncelikler)), oncelikler)

    def test_cozulemeyecekler_acikca_isaretli(self):
        cozulemez = [r for r in self.kalan if r["cozulebilir_mi"].startswith("HAYIR")]
        self.assertTrue(cozulemez, "hiçbir iş çözülemez işaretlenmemiş")
        for r in cozulemez:
            self.assertIn("—", r["tahmini_maliyet"])

    def test_rapor_biten_kapsami_sayiyla_veriyor(self):
        metin = (HERE / "KALITE-RAPORU.md").read_text(encoding="utf-8")
        self.assertIn("Biten kapsam ve kalan iş", metin)
        self.assertIn("3351", metin)


class KaliteMetrikleriTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metrikler = oku("KALITE-METRIKLERI.csv")

    def test_istenen_metrikler_var(self):
        istenen = ("kayit_veren_kaynak", "kayit", "alan_dolulugu_yuzde",
                   "bilinmeyen_belge_turu", "tekrar_orani_yuzde", "islenemeyen_kayit")
        for alan in istenen:
            self.assertIn(alan, self.metrikler[0], alan)

    def test_kanit_sayisi_kayit_sayisini_gecemez(self):
        for r in self.metrikler:
            self.assertLessEqual(int(r["olcum_kaniti_ureten"]), int(r["kayit"]),
                                 r["kategori"])

    def test_oranlar_sifir_yuz_arasinda(self):
        for r in self.metrikler:
            for alan in ("alan_dolulugu_yuzde", "tekrar_orani_yuzde"):
                self.assertGreaterEqual(float(r[alan]), 0.0)
                self.assertLessEqual(float(r[alan]), 100.0)


if __name__ == "__main__":
    unittest.main()
