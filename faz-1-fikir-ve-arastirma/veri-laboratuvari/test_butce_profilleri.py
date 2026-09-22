from __future__ import annotations

import csv
import unittest
from pathlib import Path

import butce_profilleri as butce
import select_sources as sec
from test_select_sources import VERI

HERE = Path(__file__).resolve().parent
FIKIR = "diyabet hastaları için mobil takip uygulaması"


class ProfilTanimiTests(unittest.TestCase):
    def test_iki_profil_ayni_dugmeleri_tasir(self):
        """Ayni tasarim iki seviyede calisiyor; dugme kumeleri ayni olmali."""
        u, p = butce.PROFILLER["ucretsiz"], butce.PROFILLER["premium"]
        self.assertEqual(set(u), set(p))

    def test_premium_artan_dugmelerde_geride_kalmaz(self):
        for dugme in butce.ARTAN_DUGMELER:
            self.assertGreaterEqual(butce.PROFILLER["premium"][dugme],
                                    butce.PROFILLER["ucretsiz"][dugme], dugme)

    def test_bilinmeyen_profil_sessizce_gecmez(self):
        with self.assertRaises(SystemExit):
            butce.profil("altin")

    def test_her_dugmenin_gerekcesi_yazili(self):
        """Sabitler kod icinde yorumla gerekcelendirilmis olmali."""
        kaynak = (HERE / "butce_profilleri.py").read_text(encoding="utf-8")
        for dugme in butce.ARTAN_DUGMELER:
            self.assertIn(dugme, kaynak)
        self.assertGreater(kaynak.count("#"), 20)


class PolitikaDegismezTests(unittest.TestCase):
    """Butce dugmesi olmayan kurallar: para odeyerek gevsetilemezler."""

    def test_hicbir_profil_yasakli_izni_kabul_etmez(self):
        for ad in butce.PROFILLER:
            kabul = set(butce.kabul_edilen_izin(ad))
            self.assertNotIn("yasak", kabul, ad)
            self.assertNotIn("yol-yok", kabul, ad)

    def test_hicbir_profilde_robots_yasakli_kaynak_secilmez(self):
        with (HERE / "KAYNAK-DEFTERI.csv").open(encoding="utf-8") as handle:
            yasakli = {r["ad"] for r in csv.DictReader(handle)
                       if r.get("sebep") == "robots_disallowed"}
        for ad in butce.PROFILLER:
            satirlar = sec.paket_sec(FIKIR, "mobil-uygulama", ["saglik"], VERI,
                                     profil_adi=ad)
            secilen = {r["birincil_kaynak"] for r in satirlar}
            self.assertEqual(set(), secilen & yasakli, ad)

    def test_degismeyen_kurallar_belgelenmis(self):
        for anahtar in ("robots_yasagi", "bot_korumasi", "determinizm"):
            self.assertIn(anahtar, butce.DEGISMEYEN)
            self.assertTrue(butce.DEGISMEYEN[anahtar].strip())

    def test_premium_butcesi_sinirli(self):
        """'Kontrolsuz' olmamak: premium daha buyuk butce alir, sinirsiz degil."""
        self.assertLess(butce.PROFILLER["premium"]["istek_butcesi"], 10_000)

    def test_her_profil_deterministik(self):
        for ad in butce.PROFILLER:
            a = sec.paket_sec(FIKIR, "mobil-uygulama", ["saglik"], VERI, profil_adi=ad)
            b = sec.paket_sec(FIKIR, "mobil-uygulama", ["saglik"], VERI, profil_adi=ad)
            self.assertEqual(a, b, ad)


class DerinlikTests(unittest.TestCase):
    def setUp(self):
        self.paket = {
            ad: sec.paket_sec(FIKIR, "mobil-uygulama", ["saglik"], VERI,
                              soru_basina_yuva=int(butce.PROFILLER[ad]["soru_basina_yuva"]),
                              profil_adi=ad)
            for ad in ("ucretsiz", "premium")}

    def test_premium_daha_cok_bagimsiz_aci_verir(self):
        self.assertGreater(len(self.paket["premium"]), len(self.paket["ucretsiz"]))

    def test_premium_yeni_soru_grup_ciftleri_ekler(self):
        """Bagimsizlik soru basinadir: ayni grup farkli soruda tekrar
        kullanilabilir. O yuzden olculecek sey grup sayisi degil,
        (soru, grup) ciftlerinin sayisidir -- her cift bir soruya bakan
        ayri bir olcme yontemidir.
        """
        def ciftler(satirlar):
            return {(r["soru_id"], r["kaynak_grubu"]) for r in satirlar}
        u, p = ciftler(self.paket["ucretsiz"]), ciftler(self.paket["premium"])
        self.assertGreater(len(p), len(u))
        self.assertEqual(set(), u - p, "ücretsizdeki bir açı premiumda kaybolmamalı")

    def test_premium_sayiya_kaymaz(self):
        """Gorevin acik sarti: premium 'kontrolsuz daha cok site' olmamali.

        Aci basina kaynak orani premiumda artmamali; artiyorsa tasarim
        derinlik yerine sayiya kaymis demektir.
        """
        def oran(satirlar):
            return len({r["birincil_kaynak"] for r in satirlar}) / len(satirlar)
        self.assertLessEqual(oran(self.paket["premium"]),
                             oran(self.paket["ucretsiz"]) + 1e-9)

    def test_premium_ek_yuvasi_ek_kaynaktan_fazla(self):
        ek_yuva = len(self.paket["premium"]) - len(self.paket["ucretsiz"])
        ek_kaynak = (len({r["birincil_kaynak"] for r in self.paket["premium"]})
                     - len({r["birincil_kaynak"] for r in self.paket["ucretsiz"]}))
        self.assertGreater(ek_yuva, ek_kaynak)

    def test_bagimsizlik_premiumda_da_korunur(self):
        """Derinlik artarken ayni gruptan iki yuva acilmamali."""
        import collections
        soruya_gore = collections.defaultdict(list)
        for r in self.paket["premium"]:
            soruya_gore[r["soru_id"]].append(r)
        for soru, grp in soruya_gore.items():
            gruplar = [r["kaynak_grubu"] for r in grp]
            self.assertEqual(len(gruplar), len(set(gruplar)), soru)
            hostlar = [r["host"] for r in grp if r["host"]]
            self.assertEqual(len(hostlar), len(set(hostlar)), soru)


class TazelikTests(unittest.TestCase):
    def test_havuz_iki_profilde_de_ayni(self):
        """Havuzu daraltmak premiumun bir kanit acisini kaybetmesine yol acar."""
        self.assertEqual(set(butce.kabul_edilen_izin("ucretsiz")),
                         set(butce.kabul_edilen_izin("premium")))

    def test_arsiv_yalniz_ucretsizde_birincil_olabilir(self):
        """Tazelik siralamada uygulanir: premiumda arsiv yedege duser."""
        self.assertTrue(butce.arsiv_birincil_olabilir("ucretsiz"))
        self.assertFalse(butce.arsiv_birincil_olabilir("premium"))


class KarsilastirmaCiktisiTests(unittest.TestCase):
    def setUp(self):
        with (HERE / "BUTCE-KARSILASTIRMA.csv").open(encoding="utf-8") as handle:
            self.satirlar = list(csv.DictReader(handle))

    def test_her_fikir_iki_profilde_de_var(self):
        import collections
        say = collections.Counter(r["fikir"] for r in self.satirlar)
        for fikir, adet in say.items():
            self.assertEqual(2, adet, fikir)

    def test_her_fikirde_premium_derinlik_ekliyor(self):
        for r in self.satirlar:
            if r["profil"] == "premium":
                self.assertGreater(int(r["premium_ek_yuva"]), 0, r["fikir"])

    def test_hicbir_fikirde_sayiya_kaymamis(self):
        for r in self.satirlar:
            if r["profil"] == "premium":
                self.assertEqual("evet", r["sayiya_kaymadi"], r["fikir"])


if __name__ == "__main__":
    unittest.main()
