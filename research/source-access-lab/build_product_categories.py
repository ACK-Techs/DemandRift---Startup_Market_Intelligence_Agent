"""Arastirilacak yazilim urunlerini, kaynak secimini gercekten degistiren
kategorilere boler ve her kategori icin kaynak paketini uretir.

Kategori yalniz etiket degildir: iki urun farkli kategorideyse ilk bakilacak
kaynak listeleri de farkli olmalidir. Bu yuzden kategoriler havadan tanimlanmaz,
elimizdeki kaynak envanterinden turetilir -- ``SITE-LISTESI.md`` 636 kaynagi 30
baslik altinda tutuyor ve her baslik "hangi urun tipine hizmet ediyor" sorusuna
gore siniflandiriliyor:

* **ORTAK**  — her urun icin gecerli (haber, arama motorlari, trend, patent).
  Ayirt etmedigi icin kategori olamaz; 263 kaynak buraya duser.
* **KATEGORI** — urunun nerede yasadigini ya da kimin satin aldigini belirleyen
  baslik. Ana kategoriyi bu dogurur.
* **EK** — dikey ve bolge. Tek basina kategori degildir: 'saglik urunu' demek
  mobil mi web mi oldugunu soylemez, ana kategoriye eklenir.

Iki cikti uretir:

* ``URUN-KATEGORILERI.csv`` — kategori basina bir satir: tanim, arastirma
  niyeti, ornek urunler, kaynak sayilari.
* ``KATEGORI-KAYNAK.csv`` — kategori-kaynak esleşmesi basina bir satir: kaynagin
  rolu, ne sagladigi, hangi aramanin yapilacagi ve o kaynagin gercek durumu.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# Kaynak basliklarinin siniflandirmasi. Her baslik ya bir kategoriyi dogurur,
# ya bir ek pakettir, ya da her urunde kullanildigi icin ortak havuzdadir.
# --------------------------------------------------------------------------
ORTAK = "ortak"

BASLIK_ROLU: dict[str, tuple[str, str]] = {
    # baslik -> (rol, hedef)   rol: kategori | ek | ortak
    "Mobil uygulama mağazaları": ("kategori", "mobil-uygulama"),
    "Yazılım geliştirici ve teknik topluluklar": ("kategori", "gelistirici-araci"),
    "Tarayıcı, e-ticaret ve CMS eklenti mağazaları": ("kategori", "eklenti-entegrasyon"),
    "Yapay zekâ modeli, veri seti ve agent ekosistemi": ("kategori", "yapay-zeka-urunu"),
    "Oyun dikeyi": ("kategori", "oyun"),
    "E-ticaret ve fiziksel ürün pazar yerleri": ("kapsam-disi", ""),
    "SaaS, yazılım ve hizmet inceleme siteleri": ("kategori", "b2b-web-yazilimi"),
    "Fiyat, teknoloji ve pazar sinyali karşılaştırma kaynakları": ("kategori", "b2b-web-yazilimi"),
    "İş ilanları ve yetenek talebi": ("kategori", "b2b-web-yazilimi"),
    "Yerel işletme, harita ve hizmet dizinleri": ("kategori", "yerel-hizmet"),

    "Sağlık ve biyoteknoloji dikeyi": ("ek", "saglik"),
    "Finans ve fintech dikeyi": ("ek", "fintech"),
    "Eğitim dikeyi": ("ek", "egitim"),
    "Gayrimenkul ve inşaat dikeyi": ("ek", "gayrimenkul"),
    "Seyahat, konaklama ve mobilite dikeyi": ("ek", "seyahat"),
    "Yeme-içme ve teslimat dikeyi": ("ek", "yeme-icme"),
    "Regülasyon ve hukuk kaynakları": ("ek", "regule-sektor"),
    "Türkiye startup ve teknoloji ekosistemi": ("ek", "turkiye-pazari"),

    "Genel web arama ve keşif": ("ortak", ORTAK),
    "Haber, basın ve sektör yayınları": ("ortak", ORTAK),
    "Şirket, yatırım ve startup verisi": ("ortak", ORTAK),
    "Trafik, SEO, anahtar kelime ve trend": ("ortak", ORTAK),
    "Sosyal ağlar ve açık topluluklar": ("ortak", ORTAK),
    "Akademik araştırma ve bilimsel yayınlar": ("ortak", ORTAK),
    "Patent ve marka": ("ortak", ORTAK),
    "Kamu verisi ve istatistik": ("ortak", ORTAK),
    "Anket, birincil doğrulama ve kullanıcı araştırması platformları": ("ortak", ORTAK),
    "Domain, DNS, sertifika ve web footprint": ("ortak", ORTAK),
    "Reklam kütüphaneleri ve pazarlama sinyalleri": ("ortak", ORTAK),
    "Ürün lansmanı ve startup toplulukları": ("ortak", ORTAK),
}

# Kapsam disi basliklar: envanterde duruyorlar ama hicbir kategoriye kaynak
# vermiyorlar. Silmek yerine gerekceyle isaretlenirler ki karar gorunur kalsin.
KAPSAM_DISI_GEREKCE: dict[str, str] = {
    "E-ticaret ve fiziksel ürün pazar yerleri":
        "Fiziksel urun icin yapilan is pazar analizi degil fiyat arbitraji: ayni "
        "urun farkli sitede farkli fiyata satiliyor. 1.2'deki kurali gecemiyor, "
        "ayri bir arastirma niyeti dogurmuyor (mentor degerlendirmesi, 2026-09-04).",
}

# Baslik geneli disinda kalan kaynaklar. Baslik adi her zaman icerigini dogru
# anlatmaz: 'E-ticaret ve fiziksel urun pazar yerleri' basligi fiziksel pazar
# yerlerinin yaninda dijital urun satan ve kitle fonlamasi yapan siteleri de
# tutuyordu. Baslik kapsam disi kalinca bunlarin da dusmesi yanlis olurdu --
# fiziksel urun satmiyorlar, yazilim urununun kendisiyle ilgililer.
KAYNAK_ISTISNASI: dict[str, tuple[str, str, str, str, str]] = {
    # kaynak -> (rol, hedef, kaynak_grubu, ne saglar, hangi arama)
    **{ad: ("ortak", ORTAK, "Dijital ürün ve şablon pazar yerleri",
            "Bağımsız yazılımcının sattığı ürünler, fiyat noktaları, satıcı yoğunluğu",
            "{urun}; {urun} template; {urun} plugin")
       for ad in ("Gumroad", "Lemon Squeezy", "CodeCanyon", "ThemeForest",
                  "Envato Market", "Creative Market")},
    **{ad: ("ortak", ORTAK, "Kitle fonlaması platformları",
            "Kampanya sayısı, destekçi adedi, toplanan tutar ve hedefe ulaşma oranı",
            "{urun}; {urun} kickstarter")
       for ad in ("Kickstarter", "Indiegogo")},
}

# Her baslik ne saglar ve o baslikta hangi arama yapilir. {urun} kullanicinin
# fikriyle degistirilir.
BASLIK_BILGISI: dict[str, tuple[str, str]] = {
    "Mobil uygulama mağazaları": (
        "Uygulama listeleri, kullanıcı yorumları, puan dağılımı, kategori sıralaması",
        "{urun} app; {urun} tracker; best {urun} apps"),
    "Yazılım geliştirici ve teknik topluluklar": (
        "Paket indirme sayıları, depo ilgisi, çözülmemiş sorunlar, soru hacmi",
        "{urun}; {urun} library; {urun} sdk"),
    "Tarayıcı, e-ticaret ve CMS eklenti mağazaları": (
        "Eklenti listeleri, kurulum sayıları, kullanıcı yorumları",
        "{urun}; {urun} extension; {urun} plugin"),
    "Yapay zekâ modeli, veri seti ve agent ekosistemi": (
        "Model ve veri seti listeleri, entegrasyon dizinleri, kıyaslama sonuçları",
        "{urun}; {urun} agent; {urun} model"),
    "Oyun dikeyi": (
        "Oyun listeleri, oyuncu sayıları, inceleme puanları, satış tahminleri",
        "{urun}; {urun} game"),
    "E-ticaret ve fiziksel ürün pazar yerleri": (
        "Ürün listeleri, fiyat aralıkları, satıcı yoğunluğu, alıcı yorumları",
        "{urun}; {urun} satın al"),
    "SaaS, yazılım ve hizmet inceleme siteleri": (
        "Rakip listeleri, kurumsal kullanıcı yorumları, fiyatlandırma, artı/eksi listeleri",
        "{urun} software; {urun} alternatives; best {urun} tools"),
    "Fiyat, teknoloji ve pazar sinyali karşılaştırma kaynakları": (
        "Fiyat karşılaştırmaları, teknoloji yığını dağılımı, sözleşme kıyasları",
        "{urun} pricing; {urun} vs"),
    "İş ilanları ve yetenek talebi": (
        "İlan hacmi ve trendi — kurumsal talebin dolaylı göstergesi",
        "{urun} specialist; {urun} developer"),
    "Yerel işletme, harita ve hizmet dizinleri": (
        "İşletme yoğunluğu, hizmet fiyatları, müşteri yorumları",
        "{urun}; {urun} hizmeti"),

    "Sağlık ve biyoteknoloji dikeyi": (
        "Klinik çalışmalar, ruhsatlandırma kayıtları, hastalık istatistikleri",
        "{urun}; {urun} clinical"),
    "Finans ve fintech dikeyi": (
        "Düzenleyici kayıtlar, piyasa verileri, lisans gereklilikleri",
        "{urun}; {urun} regulation"),
    "Eğitim dikeyi": (
        "Öğrenci sayıları, kurum istatistikleri, kurs talebi",
        "{urun}; {urun} course"),
    "Gayrimenkul ve inşaat dikeyi": (
        "İlan hacmi, fiyat endeksleri, ruhsat istatistikleri",
        "{urun}; {urun} emlak"),
    "Seyahat, konaklama ve mobilite dikeyi": (
        "Rezervasyon platformları, fiyat karşılaştırmaları, kullanıcı yorumları",
        "{urun}; {urun} booking"),
    "Yeme-içme ve teslimat dikeyi": (
        "Restoran ve teslimat platformları, sipariş fiyatları, yorumlar",
        "{urun}; {urun} delivery"),
    "Regülasyon ve hukuk kaynakları": (
        "Mevzuat metinleri, kurum kararları, uyum yükümlülükleri",
        "{urun} mevzuat; {urun} compliance"),
    "Türkiye startup ve teknoloji ekosistemi": (
        "Yerel yatırım haberleri, ekosistem aktörleri, destek programları",
        "{urun}; Türkiye {urun}"),

    "Genel web arama ve keşif": (
        "Genel kapsam: kaynak keşfi ve doğrulama",
        "{urun}; {urun} market"),
    "Haber, basın ve sektör yayınları": (
        "Sektör haberleri, yatırım duyuruları, pazar yorumları",
        "{urun} funding; {urun} market"),
    "Şirket, yatırım ve startup verisi": (
        "Rakip şirketler, yatırım turları, kuruluş tarihleri",
        "{urun} startup; {urun} company"),
    "Trafik, SEO, anahtar kelime ve trend": (
        "Arama hacmi, trend eğrisi, anahtar kelime rekabeti",
        "{urun}; {urun} trend"),
    "Sosyal ağlar ve açık topluluklar": (
        "Kullanıcı şikâyetleri, talep ifadeleri, topluluk tartışmaları",
        "{urun} alternative; {urun} problem"),
    "Akademik araştırma ve bilimsel yayınlar": (
        "Alandaki bilimsel çalışma yoğunluğu, yeni yöntemler",
        "{urun}"),
    "Patent ve marka": (
        "Patent başvuru yoğunluğu, marka tescilleri",
        "{urun}"),
    "Kamu verisi ve istatistik": (
        "Pazar büyüklüğü, nüfus ve sektör istatistikleri",
        "{urun}"),
    "Anket, birincil doğrulama ve kullanıcı araştırması platformları": (
        "Birincil doğrulama için anket ve kullanıcı testi altyapısı",
        "{urun}"),
    "Domain, DNS, sertifika ve web footprint": (
        "Rakip sitelerin teknik izleri, alan adı hareketleri",
        "{urun}"),
    "Reklam kütüphaneleri ve pazarlama sinyalleri": (
        "Rakiplerin reklam yatırımı ve mesajlaşması",
        "{urun}"),
    "Ürün lansmanı ve startup toplulukları": (
        "Yeni lansmanlar, erken benimseyen tepkisi",
        "{urun}"),
}

# Bir urun birden fazla kategoriye uyabilir: mobil bulmaca oyunu hem 'oyun' hem
# 'mobil-uygulama'. Bunlar celiski degil, katmandir -- oyun kaynaklari turun
# doygunlugunu, magaza kaynaklari dagitimi anlatir. Ana kategori arastirmanin
# ayirt edici sorusunu cevaplayandir; ikinci kategorinin cekirdegi ek olarak
# alinir. Asagidaki alan hangi kategorilerin bu sekilde katman olabilecegini
# soyler, boylece kural belgede kalan bir temenni olmaz.
KATMAN_OLABILIR = {"mobil-uygulama", "eklenti-entegrasyon", "yapay-zeka-urunu"}

KATEGORI_BILGISI: dict[str, tuple[str, str, str]] = {
    # kategori -> (ad, tanim, arastirma niyeti)
    "mobil-uygulama": (
        "Mobil tüketici uygulaması",
        "Son kullanıcıya uygulama mağazaları üzerinden dağıtılan uygulama",
        "İndirme hacmi, kullanıcı şikâyetleri, rakip fiyatlandırma ve mağaza sıralaması"),
    "b2b-web-yazilimi": (
        "B2B web yazılımı",
        "İşletmelerin abonelikle kullandığı web tabanlı yazılım",
        "Kurumsal talep, rakip yorumları, fiyatlandırma ve işe alım sinyali"),
    "gelistirici-araci": (
        "Geliştirici aracı / kütüphane",
        "Yazılım geliştiricilerin kullandığı paket, SDK, CLI ya da altyapı aracı",
        "Kullanım hacmi, benimsenme eğrisi, çözülmemiş ihtiyaçlar"),
    "eklenti-entegrasyon": (
        "Eklenti / entegrasyon",
        "Var olan bir platformun üzerine kurulan eklenti ya da entegrasyon",
        "Platform ekosisteminin doygunluğu, kurulum sayıları, boşluklar"),
    "yapay-zeka-urunu": (
        "Yapay zekâ ürünü / agent",
        "Model, veri seti, agent ya da yapay zekâ altyapı ürünü",
        "Ekosistem doygunluğu, kıyaslama sonuçları, entegrasyon talebi"),
    "oyun": (
        "Oyun",
        "Dijital dağıtım platformları üzerinden yayınlanan oyun",
        "Tür doygunluğu, oyuncu ilgisi, fiyatlandırma ve inceleme puanları"),
    "yerel-hizmet": (
        "Yerel hizmet ürünü",
        "Belirli bir coğrafyada işletme ya da tüketiciye hizmet veren ürün",
        "İşletme yoğunluğu, hizmet fiyatları, yerel talep"),
}

EK_BILGISI: dict[str, str] = {
    "saglik": "Ürün sağlık, tıp ya da biyoteknoloji alanındaysa",
    "fintech": "Ürün finans, ödeme ya da bankacılık alanındaysa",
    "egitim": "Ürün eğitim ya da öğrenme alanındaysa",
    "gayrimenkul": "Ürün gayrimenkul ya da inşaat alanındaysa",
    "seyahat": "Ürün seyahat, konaklama ya da mobilite alanındaysa",
    "yeme-icme": "Ürün yeme-içme ya da teslimat alanındaysa",
    "regule-sektor": "Ürün yasal düzenlemeye tabi bir alandaysa",
    "turkiye-pazari": "Türkiye pazarı hedefleniyorsa",
}


def baslik_kaynaklari(liste: Path) -> dict[str, list[str]]:
    """SITE-LISTESI.md'yi baslik -> kaynak listesi olarak okur."""
    baslik = None
    esleme: dict[str, list[str]] = collections.defaultdict(list)
    for satir in liste.read_text(encoding="utf-8").splitlines():
        satir = satir.rstrip()
        if satir.startswith("## "):
            baslik = satir[3:].strip()
        elif satir.startswith("- ") and baslik:
            ad = satir[2:].strip()
            if ad not in esleme[baslik]:
                esleme[baslik].append(ad)
    return dict(esleme)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--liste", type=Path, default=HERE / "SITE-LISTESI.md")
    parser.add_argument("--ledger", type=Path, default=HERE / "KAYNAK-DEFTERI.csv")
    parser.add_argument("--surfaces", type=Path, default=HERE / "ARAMA-YUZEYLERI.csv")
    parser.add_argument("--out-kategori", type=Path, default=HERE / "URUN-KATEGORILERI.csv")
    parser.add_argument("--out-kaynak", type=Path, default=HERE / "KATEGORI-KAYNAK.csv")
    args = parser.parse_args()

    esleme = baslik_kaynaklari(args.liste)
    bilinmeyen = set(esleme) - set(BASLIK_ROLU)
    if bilinmeyen:
        # Yeni bir baslik eklenmisse sessizce ortak havuza atmak yanlis olur:
        # kategoriye mi ek mi oldugu kararidir, elle verilmelidir.
        raise SystemExit(f"siniflandirilmamis baslik: {sorted(bilinmeyen)}")

    defter = {r["ad"]: r for r in csv.DictReader(args.ledger.open(encoding="utf-8"))}
    yuzey = {r["ad"]: r for r in csv.DictReader(args.surfaces.open(encoding="utf-8"))}

    kaynak_satirlari: list[dict[str, Any]] = []
    kategori_kaynak: dict[str, set[str]] = collections.defaultdict(set)
    ek_kaynak: dict[str, set[str]] = collections.defaultdict(set)
    ortak: set[str] = set()

    for baslik, kaynaklar in esleme.items():
        baslik_rol, baslik_hedef = BASLIK_ROLU[baslik]
        for ad in kaynaklar:
            istisna = KAYNAK_ISTISNASI.get(ad)
            if istisna:
                rol, hedef, grup, saglar, arama = istisna
            elif baslik_rol == "kapsam-disi":
                # Kaynak envanterde kalir, kategori haritasina girmez.
                continue
            else:
                rol, hedef, grup = baslik_rol, baslik_hedef, baslik
                saglar, arama = BASLIK_BILGISI[baslik]
            d, y = defter.get(ad, {}), yuzey.get(ad, {})
            if rol == "kategori":
                kategori_kaynak[hedef].add(ad)
            elif rol == "ek":
                ek_kaynak[hedef].add(ad)
            else:
                ortak.add(ad)
            kaynak_satirlari.append({
                "hedef": hedef, "hedef_turu": rol, "kaynak_grubu": grup, "kaynak": ad,
                "rol": "cekirdek" if rol == "kategori" else ("ek" if rol == "ek" else "destekleyici"),
                "ne_saglar": saglar, "hangi_arama": arama,
                "durum": d.get("durum", ""), "adres": d.get("adres", ""),
                "arama_yolu": y.get("en_iyi_yol", ""),
            })

    # Ayni kaynak birden fazla baslikta gecebiliyor (G2 hem SaaS inceleme hem
    # fiyat karsilastirma basliginda). Ayni kategoride iki satir olmasi tekrar
    # gibi gorunur; satirlar birlestirilir ve iki baslikin katkisi korunur.
    birlesik: dict[tuple[str, str], dict[str, Any]] = {}
    for satir in kaynak_satirlari:
        anahtar = (satir["hedef"], satir["kaynak"])
        mevcut = birlesik.get(anahtar)
        if mevcut is None:
            birlesik[anahtar] = satir
            continue
        for alan in ("kaynak_grubu", "ne_saglar", "hangi_arama"):
            if satir[alan] not in mevcut[alan]:
                mevcut[alan] = f"{mevcut[alan]} | {satir[alan]}"
    kaynak_satirlari = list(birlesik.values())
    kaynak_satirlari.sort(key=lambda r: (r["hedef_turu"], r["hedef"], r["kaynak"].casefold()))
    with args.out_kaynak.open("w", newline="", encoding="utf-8") as handle:
        yazici = csv.DictWriter(handle, fieldnames=list(kaynak_satirlari[0]))
        yazici.writeheader()
        yazici.writerows(kaynak_satirlari)

    def cekilen(kume: set[str]) -> int:
        return sum(1 for ad in kume if defter.get(ad, {}).get("durum") == "cekildi")

    kategoriler: list[dict[str, Any]] = []
    for anahtar, (ad, tanim, niyet) in KATEGORI_BILGISI.items():
        ozel = kategori_kaynak[anahtar]
        kategoriler.append({
            "kategori": anahtar, "tur": "kategori", "ad": ad, "tanim": tanim,
            "arastirma_niyeti": niyet, "ne_zaman": "Ürün bu dağıtım/alıcı tipindeyse",
            "katman_olabilir": "evet" if anahtar in KATMAN_OLABILIR else "hayir",
            "cekirdek_kaynak": len(ozel), "cekirdek_cekilen": cekilen(ozel),
            "ortak_kaynak": len(ortak), "ortak_cekilen": cekilen(ortak),
        })
    for anahtar, ne_zaman in EK_BILGISI.items():
        ozel = ek_kaynak[anahtar]
        kategoriler.append({
            "kategori": anahtar, "tur": "ek", "ad": anahtar.replace("-", " ").title(),
            "tanim": "Ana kategoriye eklenen dikey/bölge paketi",
            "arastirma_niyeti": "Ana kategorinin sorularına alan-özel kanıt ekler",
            "ne_zaman": ne_zaman, "katman_olabilir": "evet",
            "cekirdek_kaynak": len(ozel), "cekirdek_cekilen": cekilen(ozel),
            "ortak_kaynak": 0, "ortak_cekilen": 0,
        })

    with args.out_kategori.open("w", newline="", encoding="utf-8") as handle:
        yazici = csv.DictWriter(handle, fieldnames=list(kategoriler[0]))
        yazici.writeheader()
        yazici.writerows(kategoriler)

    # Kategoriler gercekten ayrik mi? Iki kategorinin cekirdek kaynagi ortakse
    # ayrim etiketten ibarettir; bu kontrol raporlanir.
    cakisma = [
        (a, b, len(kategori_kaynak[a] & kategori_kaynak[b]))
        for i, a in enumerate(KATEGORI_BILGISI) for b in list(KATEGORI_BILGISI)[i + 1:]
        if kategori_kaynak[a] & kategori_kaynak[b]
    ]
    print(json.dumps({
        "kategori": len(KATEGORI_BILGISI), "ek": len(EK_BILGISI),
        "ortak_kaynak": len(ortak), "kategori_kaynak_satiri": len(kaynak_satirlari),
        "cekirdek_cakismasi": cakisma or "yok",
        "cikti": [str(args.out_kategori), str(args.out_kaynak)],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
