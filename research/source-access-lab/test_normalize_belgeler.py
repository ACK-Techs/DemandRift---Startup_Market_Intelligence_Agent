"""DR-L03 normalize veri kumesinin kurallarini koruyan testler.

Testler kodu degil **kurallari** korur: tarih tahmin edilmemesi, ayni
icerigin yeni kanit sayilmamasi, etkilesim sayilarinin talep kanitina
cevrilmemesi ve yorumlayici siniflandirmanin teknik normalizasyondan ayri
kalmasi.
"""
from __future__ import annotations

import csv
import unittest
from pathlib import Path

import normalize_belgeler as nb

HERE = Path(__file__).resolve().parent


def oku(ad: str) -> list[dict[str, str]]:
    with (HERE / ad).open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class TarihTahminEdilmezTests(unittest.TestCase):
    """Yasak 1: sayfada tarih yoksa uydurulmaz."""

    @classmethod
    def setUpClass(cls):
        cls.belgeler = oku("NORMALIZE-BELGELER.csv")

    def test_tarihsiz_belge_bos_kalir_ve_bayrak_tasir(self):
        for r in self.belgeler:
            if not r["published_at"]:
                self.assertIn("unknown_date", r["source_integrity_flags"], r["source_adi"])

    def test_published_at_collected_at_ile_ayni_degil(self):
        """collected_at yayin tarihi yerine gecemez."""
        for r in self.belgeler:
            if r["published_at"]:
                self.assertNotEqual(r["published_at"], r["collected_at"], r["source_adi"])

    def test_tarihi_olan_belge_kaynagini_soyler(self):
        for r in self.belgeler:
            if r["published_at"] or r["updated_at"]:
                self.assertTrue(r["tarih_kaynagi"].strip(), r["source_adi"])

    def test_tarih_yoksa_kaynak_da_bos(self):
        for r in self.belgeler:
            if not (r["published_at"] or r["updated_at"]):
                self.assertEqual("", r["tarih_kaynagi"], r["source_adi"])

    def test_cikarim_tarih_uydurmaz(self):
        cikarim = nb.metin_cikar(b"<html><body>tarihsiz metin</body></html>",
                                 "text/html")
        self.assertEqual(("", "", ""), nb.tarih_cikar(cikarim))


class TekrarSilinmezIliskilendirilirTests(unittest.TestCase):
    """Yasak 2: ayni icerik yeni bagimsiz kanit degildir - ama silinmez."""

    @classmethod
    def setUpClass(cls):
        cls.belgeler = oku("NORMALIZE-BELGELER.csv")
        cls.iliskiler = oku("BELGE-ILISKILERI.csv")

    def test_tekrarlar_silinmemis(self):
        """Tekrar isaretli satirlar veri kumesinde duruyor olmali."""
        tekrar = [r for r in self.belgeler
                  if "duplicate_exact" in r["source_integrity_flags"]]
        self.assertTrue(tekrar, "tekrar tespiti hic calismamis")

    def test_her_iliski_iki_gercek_belgeyi_baglar(self):
        kimlikler = {r["document_id"] for r in self.belgeler}
        for r in self.iliskiler:
            self.assertIn(r["document_id"], kimlikler)
            self.assertIn(r["hedef_document_id"], kimlikler)

    def test_belge_kendisiyle_iliskilendirilmez(self):
        for r in self.iliskiler:
            self.assertNotEqual(r["document_id"], r["hedef_document_id"])

    def test_iliski_turleri_faz4_sozlugunden(self):
        for r in self.iliskiler:
            self.assertIn(r["relation_type"], ("duplicate_of", "possible_duplicate"))

    def test_yakin_tekrar_kesin_sayilmaz(self):
        """SimHash adaydir; guveni 1.00 olamaz."""
        for r in self.iliskiler:
            if r["relation_type"] == "possible_duplicate":
                self.assertLess(float(r["confidence"]), 1.0)
                self.assertIn("ADAY", r["gerekce"])

    def test_iliskiler_modele_sorularak_uretilmedi(self):
        for r in self.iliskiler:
            self.assertEqual("deterministic_rule", r["created_by"])

    def test_simhash_ayni_metinde_ayni(self):
        metin = "bu metin iki kez ayni sekilde ozetlenmeli " * 10
        self.assertEqual(nb.simhash(metin), nb.simhash(metin))
        self.assertEqual(0, nb.hamming(nb.simhash(metin), nb.simhash(metin)))


class EtkilesimTalepKanitiDegildirTests(unittest.TestCase):
    """Yasak 3: indirme/yorum sayisi odeme davranisina cevrilmez."""

    @classmethod
    def setUpClass(cls):
        cls.alanlar = oku("KATEGORI-ALANLARI.csv")

    def test_her_etkilesim_satiri_uyari_tasir(self):
        for r in self.alanlar:
            if r["alan"].startswith("engagement_"):
                self.assertEqual(nb.ETKILESIM_UYARISI, r["not"], r["alan"])

    def test_etkilesim_alani_talep_diye_adlandirilmamis(self):
        for r in self.alanlar:
            self.assertNotIn("talep", r["alan"])
            self.assertNotIn("demand", r["alan"])

    def test_puan_indirme_sayisi_sayilmaz(self):
        """Aptoide: '4.33 Download' buton yazisiydi, indirme sayisi degil."""
        bulgu = nb.alan_cikar("urun", "Omniheroes 4.33 Download Vegas Slots", "")
        self.assertEqual([], [b for b in bulgu
                              if b["alan"] == "engagement_indirme_sayisi"])

    def test_gercek_indirme_sayisi_yakalanir(self):
        bulgu = nb.alan_cikar("urun", "Over 5M downloads worldwide", "")
        self.assertEqual(["5M"], [b["deger"] for b in bulgu
                                  if b["alan"] == "engagement_indirme_sayisi"])


class OlcumEtiketAyrimiTests(unittest.TestCase):
    """Gorev 4'un ayrimi: bulunmak ile olculebilmek ayni sey degil."""

    def test_her_alan_turu_tanimli(self):
        for r in oku("KATEGORI-ALANLARI.csv"):
            self.assertIn(r["alan_turu"], ("olcum", "etiket"), r["alan"])

    def test_etiket_alani_olcum_gibi_sunulmaz(self):
        for r in oku("KATEGORI-ALANLARI.csv"):
            if r["alan_turu"] == "etiket":
                self.assertTrue(r["not"].strip(), r["alan"])

    def test_bulunmayan_alan_uydurulmaz(self):
        self.assertEqual([], nb.alan_cikar("urun", "burada hicbir sey yok", ""))

    def test_sitemap_oncelik_degeri_surum_sayilmaz(self):
        """<priority>0.7</priority> bir surum numarasi degildir."""
        bulgu = nb.alan_cikar("urun", "weekly 1 0.7 daily 0.5", "")
        self.assertEqual([], [b for b in bulgu if b["alan"] == "surum"])

    def test_ciplak_kelime_gosterge_sayilmaz(self):
        self.assertEqual([], nb.alan_cikar("kamu", "the index of this page", ""))


class TeknikVeYorumAyriTests(unittest.TestCase):
    """Gorev karti: yorumlayici siniflandirma ayri cikti olarak tutulur."""

    @classmethod
    def setUpClass(cls):
        cls.belgeler = oku("NORMALIZE-BELGELER.csv")
        cls.sinif = oku("SINIFLANDIRMA.csv")

    def test_iki_dosya_document_id_ile_baglanir(self):
        self.assertEqual({r["document_id"] for r in self.belgeler},
                         {r["document_id"] for r in self.sinif})

    def test_teknik_dosyada_yorum_sutunu_yok(self):
        yorum = {"belge_turu", "urun_kategorileri", "arastirma_niyeti",
                 "olcum_kaniti_uretir_mi", "siniflandirma_gerekcesi"}
        self.assertEqual(set(), yorum & set(self.belgeler[0]))

    def test_yorum_dosyasinda_govde_metni_yok(self):
        """Metin tek yerde durur; siniflandirma degisince yeniden cikarilmaz."""
        self.assertNotIn("body_normalized", self.sinif[0])

    def test_her_siniflandirma_gerekce_tasir(self):
        for r in self.sinif:
            self.assertTrue(r["siniflandirma_gerekcesi"].strip(), r["source_id"])

    def test_belirsiz_belge_belirsizlik_sutununda_gorunur(self):
        for r in self.sinif:
            if r["belge_turu"] == "belirsiz":
                self.assertTrue(r["belirsizlik"].strip(), r["source_id"])


class IzlenebilirlikTests(unittest.TestCase):
    """Her satir diskteki ham dosyaya kadar geri izlenebilmeli."""

    @classmethod
    def setUpClass(cls):
        cls.belgeler = oku("NORMALIZE-BELGELER.csv")

    def test_her_belge_ham_dosyayi_isaret_eder(self):
        for r in self.belgeler:
            self.assertTrue(r["body_original_ref"].strip(), r["source_adi"])
            self.assertEqual(64, len(r["artifact_hash"]), r["source_adi"])

    def test_source_url_degistirilmemis(self):
        for r in self.belgeler:
            self.assertTrue(r["source_url"].strip(), r["source_adi"])

    def test_document_id_artefakta_bagli_ve_tekil(self):
        """Ayni icerikli iki belge ayni kimligi paylasmaz; iliskiyle baglanir."""
        import hashlib
        for r in self.belgeler:
            beklenen = hashlib.sha256(
                f"{r['source_id']}|{r['artifact_hash']}".encode()).hexdigest()[:12]
            self.assertEqual(f"doc-{beklenen}", r["document_id"], r["source_adi"])
        kimlikler = [r["document_id"] for r in self.belgeler]
        self.assertEqual(len(kimlikler), len(set(kimlikler)))

    def test_normalizasyon_surumu_her_satirda(self):
        for r in self.belgeler:
            self.assertEqual(nb.NORMALIZASYON_SURUMU, r["normalization_version"])

    def test_kirpilan_metin_tam_uzunlugu_saklar(self):
        for r in self.belgeler:
            if int(r["body_uzunlugu"]) > 4000:
                self.assertEqual(4000, len(r["body_normalized"]), r["source_adi"])


class URLKanoniklestirmeTests(unittest.TestCase):
    def test_takip_parametresi_atilir_icerik_parametresi_kalir(self):
        self.assertEqual(
            "https://g2.com/browse?q=crm",
            nb.url_kanonik("https://www.G2.com/browse?utm_source=x&q=crm"))

    def test_fragment_ve_varsayilan_port_atilir(self):
        self.assertEqual("https://ornek.com/a",
                         nb.url_kanonik("https://ornek.com:443/a#bolum"))

    def test_sayfa_parametresi_silinmez(self):
        """?page=2 silinseydi iki ayri sayfa ayni belge sayilirdi."""
        self.assertIn("page=2", nb.url_kanonik("https://ornek.com/liste?page=2"))


class DilTespitiTests(unittest.TestCase):
    def test_kisa_metinde_dil_iddia_edilmez(self):
        self.assertEqual(("unknown", 0.0), nb.dil_tespit("merhaba"))

    def test_adres_listesi_dil_kaniti_degildir(self):
        """Sitemap'teki '.com' tekrari Portekizce sayilmamali."""
        kod, _g = nb.dil_tespit(
            "https://www.airtable.com/company weekly 1 "
            "https://www.airtable.com/pricing daily 0.7 " * 20)
        self.assertEqual("unknown", kod)

    def test_duz_yazi_dogru_etiketlenir(self):
        self.assertEqual("tr", nb.dil_tespit(
            "Bu bir deneme metnidir ve icinde birden fazla kelime vardir ama "
            "daha sonra ne olacagi belli degildir cunku her sey degisir. " * 6)[0])
        self.assertEqual("en", nb.dil_tespit(
            "The quick brown fox is not a dog and the cat was in the house "
            "with a mouse that has been there for a while. " * 6)[0])

    def test_unknown_satirlar_guveni_yine_de_yazar(self):
        for r in oku("NORMALIZE-BELGELER.csv"):
            float(r["language_confidence"])


class IslenemeyenKayitTests(unittest.TestCase):
    def test_her_kayit_neden_tasir(self):
        for r in oku("ISLENEMEYEN-BELGELER.csv"):
            self.assertTrue(r["neden"].strip(), r["ad"])

    def test_her_basarili_kayit_ya_islendi_ya_islenemedi(self):
        """Ucuncu bir yer yok: kayip bir kayit sessizce dusmus olamaz.

        Ayni (kaynak, artefakt) cifti iki kosuda gorulmus olabilir; tekrarlar
        bir kez islenir, bu yuzden sayim tekil cift uzerinden yapilir.
        """
        satirlar = [r for r in oku("ARTEFAKT-DIZINI.csv") + oku("EK-ARTEFAKT-DIZINI.csv")
                    if r["sonuc"] == "ok"]
        tekil = {(r.get("source_id", ""), r["sha256"]) for r in satirlar}
        self.assertEqual(len(tekil),
                         len(oku("NORMALIZE-BELGELER.csv"))
                         + len(oku("ISLENEMEYEN-BELGELER.csv")))


class EnvanterleTutarlilikTests(unittest.TestCase):
    """DR-L01 ile celiski olmamali: elde olmayan dosya normalize edilmis gorunemez."""

    def test_normalize_edilen_her_kaynak_envanterde_dosyali(self):
        envanter = {r["source_id"]: r for r in oku("VERI-ENVANTERI.csv")}
        for r in oku("NORMALIZE-BELGELER.csv"):
            if r["source_id"]:
                self.assertGreater(int(envanter[r["source_id"]]["dosyasi_diskte"]), 0,
                                   r["source_adi"])

    def test_belge_turleri_drl02_sozlugunden(self):
        import kategori_sozlugu as sozluk
        for r in oku("SINIFLANDIRMA.csv"):
            self.assertIn(r["belge_turu"], sozluk.BELGE_TURU_SIRASI, r["source_id"])


class BelgelerTests(unittest.TestCase):
    def test_veri_sozlugu_her_sutunu_aciklar(self):
        metin = (HERE / "VERI-SOZLUGU.md").read_text(encoding="utf-8")
        for sutun in oku("NORMALIZE-BELGELER.csv")[0]:
            self.assertIn(f"`{sutun}`", metin, sutun)

    def test_sozluk_cevaplayamadigi_sorulari_soyler(self):
        metin = (HERE / "VERI-SOZLUGU.md").read_text(encoding="utf-8")
        self.assertIn("cevaplayamadığı", metin)
        self.assertIn("Talep var mı", metin)

    def test_kurallar_belgesi_uc_yasagi_yazar(self):
        metin = (HERE / "DONUSUM-KURALLARI.md").read_text(encoding="utf-8")
        self.assertIn("tahmin yok", metin)
        self.assertIn("silme değil, ilişkilendirme", metin)
        self.assertIn("ödeme davranışı", metin)

    def test_kurallar_belgesi_neden_iki_cikti_oldugunu_anlatir(self):
        metin = (HERE / "DONUSUM-KURALLARI.md").read_text(encoding="utf-8")
        self.assertIn("Neden iki ayrı çıktı", metin)


if __name__ == "__main__":
    unittest.main()
