"""AS-01 teslim kosullarini koruyan testler.

Gorev karti: "indekste gorunen ama erisilemeyen dosya, arsiv/snippet ve gercek
icerik farkini belirt; eski erisim kaydini bugunku basari sayma." Rehber:
"kanitsiz veya calistirilmamis test kabul edilmis sayilmaz."
"""
from __future__ import annotations

import csv
import hashlib
import unittest
from pathlib import Path

import as01_kaynak_kontrol as as01

HERE = Path(__file__).resolve().parent


def oku(ad: str) -> list[dict[str, str]]:
    with (HERE / ad).open(encoding="utf-8") as tutamak:
        return list(csv.DictReader(tutamak))


class EskiKayitBugunkuBasariDegildirTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kontrol = oku("AS01-KAYNAK-KONTROL.csv")

    def test_kayitli_ve_bugunku_ayri_sutunlarda(self):
        satir = self.kontrol[0]
        for alan in ("kayitli_erisim", "kayitli_icerik", "bugun_erisim", "bugun_icerik"):
            self.assertIn(alan, satir, alan)

    def test_her_satir_fark_yorumu_tasir(self):
        for r in self.kontrol:
            self.assertTrue(r["degisti_mi"].strip(), r["source_id"])

    def test_gerileme_acikca_isaretli(self):
        """Kayit calisiyor diyip bugun calismayan satir gizlenmez."""
        geriledi = [r for r in self.kontrol if "BUGÜN ÇALIŞMIYOR" in r["degisti_mi"]]
        for r in geriledi:
            self.assertNotEqual("ok", r["bugun_erisim"])

    def test_bugun_ok_olmayan_satir_icerik_iddia_etmez(self):
        for r in self.kontrol:
            if r["bugun_erisim"] not in ("ok", "not_run"):
                self.assertEqual("alinmadi", r["bugun_icerik"], r["source_id"])


class UcEksenAyriTests(unittest.TestCase):
    """erisim / icerik / artefakt ayri olculur."""

    @classmethod
    def setUpClass(cls):
        cls.kontrol = oku("AS01-KAYNAK-KONTROL.csv")

    def test_http_200_icerik_garantisi_degil(self):
        """Google Play bugun 200 dondu ve govdesi bos: erisim ok, icerik js-kabugu."""
        kabuk = [r for r in self.kontrol
                 if r["bugun_erisim"] == "ok" and r["bugun_icerik"] == "js-kabugu"]
        self.assertTrue(kabuk, "js-kabugu ornegi olculememis")
        for r in kabuk:
            self.assertIn("0 karakter", r["bugun_kanit"])

    def test_artefakt_konumu_uc_degerden(self):
        for r in self.kontrol:
            toplam = (int(r["artefakt_depoda"]) + int(r["artefakt_yalniz_yerelde"])
                      + int(r["artefakt_hicbir_yerde"]))
            self.assertEqual(int(r["kayitli_artefakt"]), toplam, r["source_id"])

    def test_konum_fonksiyonu_ayirt_ediyor(self):
        self.assertEqual("hicbir-yerde", as01.artefakt_konumu("results/raw/yok.bin"))
        self.assertEqual("yol-yok", as01.artefakt_konumu(""))


class KanitZorunluTests(unittest.TestCase):
    """Rehber: kanitsiz test kabul edilmis sayilmaz."""

    @classmethod
    def setUpClass(cls):
        cls.kontrol = oku("AS01-KAYNAK-KONTROL.csv")

    def test_basarili_yoklama_artefakt_birakir(self):
        for r in self.kontrol:
            if r["bugun_erisim"] == "ok":
                self.assertTrue(r["bugun_artefakt"].strip(), r["source_id"])

    def test_artefakt_bu_depoda_ve_hashi_dogru(self):
        kontrol_edilen = 0
        for r in self.kontrol:
            if not r["bugun_artefakt"]:
                continue
            yol = HERE / r["bugun_artefakt_dosya"]
            self.assertTrue(yol.exists(), r["source_id"])
            self.assertEqual(r["bugun_artefakt"],
                             hashlib.sha256(yol.read_bytes()).hexdigest(), r["source_id"])
            kontrol_edilen += 1
        self.assertGreater(kontrol_edilen, 0)

    def test_istek_atilmayan_satir_artefakt_iddia_etmez(self):
        for r in self.kontrol:
            if r["bugun_erisim"].startswith("robots"):
                self.assertEqual("", r["bugun_artefakt"], r["source_id"])


class CikarilanSayininKaynagiDepodaTests(unittest.TestCase):
    """Rapor edilen her sayinin ham dosyasi bu depoda olmali.

    Kontrol ve kabul rehberi: "kayip artefakt basarili sayilmaz" ve
    "indeksteki dosya gercekten checkout'ta veya kayitli depoda bulunuyor mu?"
    """

    @classmethod
    def setUpClass(cls):
        cls.belgeler = {r["document_id"]: r for r in oku("NORMALIZE-BELGELER.csv")}

    def test_her_cikarilan_alan_depodaki_dosyaya_dayanir(self):
        eksik = []
        for r in oku("KATEGORI-ALANLARI.csv"):
            belge = self.belgeler.get(r["document_id"])
            if belge is None or not (HERE / belge["body_original_ref"]).exists():
                eksik.append(f'{r["source_adi"]}/{r["alan"]}')
        self.assertEqual([], eksik[:10], f"{len(eksik)} alan doğrulanamıyor")

    def test_ornek_alanlarin_hashi_tutuyor(self):
        kontrol = 0
        for r in oku("KATEGORI-ALANLARI.csv"):
            belge = self.belgeler.get(r["document_id"])
            yol = HERE / belge["body_original_ref"] if belge else None
            if not yol or not yol.exists():
                continue
            self.assertEqual(belge["artifact_hash"],
                             hashlib.sha256(yol.read_bytes()).hexdigest(),
                             r["source_adi"])
            kontrol += 1
            if kontrol >= 20:
                break
        self.assertGreater(kontrol, 0)


class AlanUydurulmazTests(unittest.TestCase):
    """Rehber: kaynak desteklemiyorsa null; alan uydurma yok."""

    @classmethod
    def setUpClass(cls):
        cls.ornekler = oku("AS01-ALAN-ORNEKLERI.csv")

    def test_bos_alanlar_acikca_listeleniyor(self):
        for r in self.ornekler:
            dolu = sum(1 for a in as01.ISTENEN_ALANLAR if r[a].strip())
            self.assertEqual(int(r["dolu_alan_sayisi"]), dolu, r["kaynak_adi"])

    def test_js_kabugu_alan_iddia_etmez(self):
        for r in self.ornekler:
            if r["icerik_durumu"] == "js-kabugu":
                self.assertEqual("", r["baslik"].strip(), r["kaynak_adi"])
                self.assertEqual("", r["puan"].strip(), r["kaynak_adi"])

    def test_her_ornek_artefakta_bagli(self):
        for r in self.ornekler:
            self.assertEqual(64, len(r["artefakt_sha256"]), r["kaynak_adi"])
            self.assertTrue((HERE / r["artefakt_dosya"]).exists(), r["kaynak_adi"])

    def test_puan_varsa_olcegi_de_aranmis(self):
        """Rehber puan+olcek istiyor; olcek yoksa bos kalir, uydurulmaz."""
        for r in self.ornekler:
            if r["puan"].strip():
                self.assertIn("puan_olcegi", r)


class GeriBildirimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bildirimler = oku("AS01-GERI-BILDIRIM.csv")

    def test_her_kayit_sablonun_alanlarini_tasir(self):
        zorunlu = ("fb_id", "gorev_id", "beklenen", "gerceklesen", "kanit",
                   "yapilacak_duzeltme", "batuhan_yeniden_kontrolu")
        for r in self.bildirimler:
            for alan in zorunlu:
                self.assertTrue(r[alan].strip(), f'{r["fb_id"]}/{alan}')

    def test_kayitlar_icerik_vermeyen_kaynaklar_icin(self):
        """ERISIM degil ICERIK olcutu: HTTP 200 donen bos sayfa calismiyor demektir."""
        kontrol = oku("AS01-KAYNAK-KONTROL.csv")
        icerik_veren = {r["source_id"] for r in kontrol
                        if r["bugun_erisim"] == "ok"
                        and r["bugun_icerik"] in ("gercek-icerik", "api-yaniti", "besleme")}
        for r in self.bildirimler:
            sid = r["kaynak"].split("(")[-1].rstrip(")")
            self.assertNotIn(sid, icerik_veren, r["fb_id"])

    def test_200_donen_bos_sayfa_icin_kayit_acilmis(self):
        """Google Play HTTP 200 donuyor ama govdesi bos; kayit acilmali."""
        kontrol = oku("AS01-KAYNAK-KONTROL.csv")
        kabuk = {r["source_id"] for r in kontrol if r["bugun_icerik"] == "js-kabugu"}
        kayitli = {r["kaynak"].split("(")[-1].rstrip(")") for r in self.bildirimler}
        for sid in kabuk:
            self.assertIn(sid, kayitli, sid)

    def test_hicbiri_kabul_edildi_baslamaz(self):
        for r in self.bildirimler:
            self.assertEqual("bekliyor", r["batuhan_yeniden_kontrolu"])
            self.assertEqual("acik", r["durum"])


class IddiaDogrulamaTests(unittest.TestCase):
    """AS-01: mevcut kaynak/alan/ornekleri incele."""

    @classmethod
    def setUpClass(cls):
        cls.iddialar = oku("AS01-IDDIA-DOGRULAMA.csv")

    def test_her_iddia_bir_sonuc_tasir(self):
        gecerli = {"dogrulandi", "dogrulanamadi", "yoklanamadi", "desen-yok"}
        for r in self.iddialar:
            self.assertIn(r["bugun_sonuc"], gecerli, r["alan"])
            self.assertTrue(r["gerekce"].strip())

    def test_dogrulanan_iddia_artefakta_bagli(self):
        for r in self.iddialar:
            if r["bugun_sonuc"] == "dogrulandi":
                self.assertEqual(64, len(r["bugun_artefakt"]), r["alan"])
                self.assertTrue((HERE / "results" / "raw" /
                                 f'{r["bugun_artefakt"]}.bin').exists())

    def test_bulunamadi_yok_demek_degil(self):
        """Tek yuzey yoklandi; alan baska ucta olabilir ve bu yazili."""
        for r in self.iddialar:
            if r["bugun_sonuc"] == "dogrulanamadi":
                self.assertIn("YOK demek değildir", r["gerekce"])

    def test_icerik_vermeyen_kaynak_sinanmis_sayilmaz(self):
        kontrol = {r["source_id"]: r for r in oku("AS01-KAYNAK-KONTROL.csv")}
        for r in self.iddialar:
            if r["bugun_sonuc"] == "yoklanamadi":
                self.assertEqual("", r["bugun_artefakt"], r["alan"])


class ArsivSnippetAyrimiTests(unittest.TestCase):
    """AS-01: arsiv/snippet ve gercek icerik farkini belirt."""

    @classmethod
    def setUpClass(cls):
        cls.metin = (HERE / "AS01-ERISIM-SINIRLARI.md").read_text(encoding="utf-8")

    def test_rapor_uc_turu_de_tanimliyor(self):
        for kavram in ("Gerçek içerik", "Arşiv", "Snippet"):
            self.assertIn(kavram, self.metin, kavram)

    def test_sitemap_snippet_sayilmiyor(self):
        self.assertIn("Sitemap bir snippet bile değildir", self.metin)

    def test_arsiv_canli_sayilmiyor(self):
        self.assertIn("Arşiv kopyası canlı veri değildir", self.metin)


class RaporTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metin = (HERE / "AS01-ERISIM-SINIRLARI.md").read_text(encoding="utf-8")

    def test_rapor_uc_ekseni_ayiriyor(self):
        self.assertIn("Üç ayrı eksen karıştırılmaz", self.metin)
        for kelime in ("Erişim", "İçerik", "Artefakt"):
            self.assertIn(kelime, self.metin)

    def test_rapor_erisilememe_sifir_sonuc_degil_diyor(self):
        self.assertIn("Erişilememe sıfır sonuç değildir", self.metin)

    def test_rapor_artefakt_bolunmesini_gizlemiyor(self):
        self.assertIn("yalnız yerel arşivde", self.metin.casefold()
                      .replace("i̇", "i").replace("I", "ı") or self.metin)

    def test_rapor_olcum_tarihi_tasiyor(self):
        self.assertIn("Ölçüm tarihi", self.metin)

    def test_rapor_3_2_esigini_karistirmiyor(self):
        self.assertIn("Faz 3'e aittir", self.metin)


if __name__ == "__main__":
    unittest.main()
