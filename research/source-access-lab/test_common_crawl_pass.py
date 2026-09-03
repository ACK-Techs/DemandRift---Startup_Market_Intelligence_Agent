from __future__ import annotations

import gzip
import json
import unittest

import common_crawl_pass as cc


def warc_parcasi(govde: bytes, mime: str = "text/html", durum: int = 200) -> bytes:
    kayit = (
        b"WARC/1.0\r\nWARC-Type: response\r\nContent-Length: 10\r\n\r\n"
        + f"HTTP/1.1 {durum} OK\r\nContent-Type: {mime}\r\n\r\n".encode()
        + govde
    )
    return gzip.compress(kayit)


class KayitSecimiTests(unittest.TestCase):
    def kayit(self, url, **ek):
        temel = {"url": url, "status": "200", "filename": "crawl/x.warc.gz",
                 "offset": "100", "length": "500", "mime": "text/html"}
        temel.update(ek)
        return temel

    def test_robots_bir_icerik_sayilmaz(self):
        secim = cc.pick_record([self.kayit("https://a.example/robots.txt")])
        self.assertIsNone(secim)

    def test_basarisiz_kayitlar_elenir(self):
        secim = cc.pick_record([self.kayit("https://a.example/", status="404")])
        self.assertIsNone(secim)

    def test_ana_sayfaya_en_yakin_html_secilir(self):
        secim = cc.pick_record([
            self.kayit("https://a.example/blog/2024/bir-yazi"),
            self.kayit("https://a.example/"),
            self.kayit("https://a.example/urunler"),
        ])
        self.assertEqual("https://a.example/", secim["url"])

    def test_html_olmayan_kayit_geride_kalir(self):
        secim = cc.pick_record([
            self.kayit("https://a.example/veri.json", mime="application/json"),
            self.kayit("https://a.example/sayfa", mime="text/html"),
        ])
        self.assertEqual("https://a.example/sayfa", secim["url"])

    def test_eksik_ofset_tasiyan_kayit_kullanilmaz(self):
        secim = cc.pick_record([self.kayit("https://a.example/", offset="")])
        self.assertIsNone(secim)


class WarcCozmeTests(unittest.TestCase):
    def test_govde_mime_ve_durum_ayiklanir(self):
        govde, mime, durum = cc.warc_govde(warc_parcasi(b"<html><title>Bir</title></html>"))
        self.assertEqual(b"<html><title>Bir</title></html>", govde)
        self.assertEqual("text/html", mime)
        self.assertEqual(200, durum)

    def test_bozuk_gzip_sessizce_bos_doner(self):
        self.assertEqual((b"", None, None), cc.warc_govde(b"gzip degil"))

    def test_eksik_kayit_bos_doner(self):
        self.assertEqual((b"", None, None), cc.warc_govde(gzip.compress(b"WARC/1.0\r\n\r\n")))


class ArsivdenGetirmeTests(unittest.TestCase):
    def sahte(self, cdx_satirlari, parca):
        cagrilar = []

        def isteyici(url, *, aralik=None):
            cagrilar.append((url, aralik))
            if "index.commoncrawl.org" in url:
                return ("\n".join(json.dumps(s) for s in cdx_satirlari).encode(), 200)
            return (parca, 206)

        isteyici.cagrilar = cagrilar
        return isteyici

    def test_iki_istekle_icerik_getirilir(self):
        isteyici = self.sahte(
            [{"url": "https://a.example/", "status": "200", "filename": "crawl/x.warc.gz",
              "offset": "1000", "length": "250", "mime": "text/html"}],
            warc_parcasi(b"<html>merhaba</html>" + b" " * 2000),
        )
        sonuc = cc.fetch_from_archive("a.example", isteyici=isteyici, uyuyucu=lambda _s: None)
        self.assertTrue(sonuc["ok"])
        self.assertTrue(sonuc["govde"].startswith(b"<html>merhaba</html>"))
        self.assertEqual(2, len(isteyici.cagrilar))
        self.assertEqual("bytes=1000-1249", isteyici.cagrilar[1][1])

    def test_arsivde_icerik_yoksa_ikinci_istek_atilmaz(self):
        isteyici = self.sahte([{"url": "https://a.example/robots.txt", "status": "200",
                                "filename": "f", "offset": "1", "length": "2"}], b"")
        sonuc = cc.fetch_from_archive("a.example", isteyici=isteyici, uyuyucu=lambda _s: None)
        self.assertFalse(sonuc["ok"])
        self.assertEqual("arsivde_icerik_yok", sonuc["stop_reason"])
        self.assertEqual(1, len(isteyici.cagrilar))

    def test_kucuk_arsiv_kaydi_icerik_sayilmaz(self):
        """Yonlendirme kocu 'cekildi' olarak deftere yazilmamali."""
        isteyici = self.sahte(
            [{"url": "https://a.example/", "status": "200", "filename": "crawl/x.warc.gz",
              "offset": "0", "length": "80", "mime": "text/html"}],
            warc_parcasi(b"<html>moved</html>"),
        )
        sonuc = cc.fetch_from_archive("a.example", isteyici=isteyici, uyuyucu=lambda _s: None)
        self.assertFalse(sonuc["ok"])
        self.assertEqual("arsiv_kaydi_cok_kucuk", sonuc["stop_reason"])

    def test_dizin_gecici_hatada_yeniden_denenir(self):
        yanitlar = [(b"", 502), (b"", 503),
                    (json.dumps({"url": "https://a.example/", "status": "200",
                                 "filename": "f", "offset": "0", "length": "9",
                                 "mime": "text/html"}).encode(), 200)]
        cagrilar = []

        def isteyici(url, *, aralik=None):
            cagrilar.append(url)
            if "index.commoncrawl.org" in url:
                return yanitlar[min(len(cagrilar) - 1, len(yanitlar) - 1)]
            return (warc_parcasi(b"x" * 2000), 206)

        sonuc = cc.fetch_from_archive("a.example", isteyici=isteyici, uyuyucu=lambda _s: None)
        self.assertTrue(sonuc["ok"], sonuc.get("stop_reason"))
        self.assertEqual(3, sum(1 for c in cagrilar if "index.commoncrawl.org" in c))

    def test_kalici_dizin_hatasinda_bosuna_denenmez(self):
        cagrilar = []

        def isteyici(url, *, aralik=None):
            cagrilar.append(url)
            return (b"", 404)

        sonuc = cc.fetch_from_archive("a.example", isteyici=isteyici, uyuyucu=lambda _s: None)
        self.assertFalse(sonuc["ok"])
        self.assertEqual(1, len(cagrilar))

    def test_bos_dizin_yaniti_kosuyu_dusurmez(self):
        def isteyici(url, *, aralik=None):
            return (b"", 503)

        sonuc = cc.fetch_from_archive("a.example", isteyici=isteyici, uyuyucu=lambda _s: None)
        self.assertFalse(sonuc["ok"])
        self.assertTrue(sonuc["stop_reason"].startswith("cdx_bos"))


class CokluTurTests(unittest.TestCase):
    def isteyici_uret(self, icerikli_tur):
        cagrilar = []

        def isteyici(url, *, aralik=None):
            cagrilar.append(url)
            if "index.commoncrawl.org" in url:
                if icerikli_tur in url:
                    return (json.dumps({"url": "https://a.example/", "status": "200",
                                        "filename": "f", "offset": "0", "length": "9",
                                        "mime": "text/html"}).encode(), 200)
                return (json.dumps({"url": "https://a.example/robots.txt", "status": "200",
                                    "filename": "f", "offset": "0", "length": "9"}).encode(), 200)
            return (warc_parcasi(b"x" * 2000), 206)

        isteyici.cagrilar = cagrilar
        return isteyici

    def test_ilk_turda_bulunamayan_kaynak_sonraki_turda_bulunur(self):
        isteyici = self.isteyici_uret("2026-17")
        sonuc = cc.fetch_from_any_index(
            "a.example", indexes=("CC-MAIN-2026-34", "CC-MAIN-2026-25", "CC-MAIN-2026-17"),
            isteyici=isteyici, uyuyucu=lambda _s: None,
        )
        self.assertTrue(sonuc["ok"], sonuc.get("stop_reason"))
        self.assertEqual("CC-MAIN-2026-17", sonuc["index"])
        self.assertEqual(3, sonuc["denenen_tur"])

    def test_icerik_bulununca_kalan_turlar_sorgulanmaz(self):
        isteyici = self.isteyici_uret("2026-34")
        cc.fetch_from_any_index(
            "a.example", indexes=("CC-MAIN-2026-34", "CC-MAIN-2026-25", "CC-MAIN-2026-17"),
            isteyici=isteyici, uyuyucu=lambda _s: None,
        )
        dizin_istegi = [c for c in isteyici.cagrilar if "index.commoncrawl.org" in c]
        self.assertEqual(1, len(dizin_istegi))

    def test_hicbir_turda_yoksa_son_sonuc_dondurulur(self):
        isteyici = self.isteyici_uret("hicbiri")
        sonuc = cc.fetch_from_any_index(
            "a.example", indexes=("CC-MAIN-2026-34", "CC-MAIN-2026-25"),
            isteyici=isteyici, uyuyucu=lambda _s: None,
        )
        self.assertFalse(sonuc["ok"])
        self.assertEqual("arsivde_icerik_yok", sonuc["stop_reason"])


if __name__ == "__main__":
    unittest.main()
