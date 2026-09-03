"""Her urun kategorisinde hangi sorularin cevaplanacagini ve hangi kanitin o
soruyu gercekten destekledigini tanimlar.

Gorev 1 nereye bakilacagini soyledi; bu adim ne sorulacagini ve cevabin kanitinin
ne olacagini soyler. Ayirt edici sart sudur: **konuyla ilgili gorunen her veri
kanit degildir.** "Bu pazar buyuyor" diyen bir haber yazisi ile arama hacminin
iki yilda uce katlanmasi ayni soruyla ilgilidir ama biri kanaat, digeri olcumdur.
Bu yuzden her kanit satirinda 'neden gecerli' ve 'zayif alternatif' alanlari
bulunur; ikincisi kanit gibi gorunup olmayani acikca isaretler.

Kanit, sorunun kendisine degil **soru x kaynak grubu** ikilisine baglidir:
'rakipler doygun mu' sorusu mobil uygulamada magazadaki uygulama sayisiyla,
gelistirici aracinda paket indirme dagilimiyla cevaplanir. Kategori kendi kaynak
gruplarindan kaniti devralir, boylece kategori-soru kombinasyonlari elle
yazilmaz, turetilir.
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
# Sorular. Ortak sorular her kategoride sorulur; kanitlari kategoriye gore
# degisir. Kategoriye ozel sorular baska kategoride sorulsa anlamsiz kalir.
# --------------------------------------------------------------------------
SORULAR: dict[str, tuple[str, str]] = {
    # soru_id -> (soru, neden onemli / karari nasil degistirir)
    "talep-var-mi": (
        "Bu ürüne gerçekten talep var mı?",
        "Talep yoksa diğer soruların cevabı önemsizdir; ilk elenme noktası budur"),
    "rakip-kim": (
        "Bu ihtiyacı şu an kim karşılıyor?",
        "Rakip yoksa ya pazar yoktur ya da erken; varsa kimin ne yaptığı bilinmeli"),
    "doygun-mu": (
        "Pazar doygun mu, boşluk var mı?",
        "Doygunsa farklılaşma zorunlu; değilse hızlı giriş mümkün"),
    "odeme-istegi": (
        "Kullanıcılar bunun için para ödüyor mu, ne kadar?",
        "Fiyat aralığı iş modelini ve gereken ölçeği belirler"),
    "talep-yonu": (
        "Talep büyüyor mu, küçülüyor mu?",
        "Küçülen pazara girmek, doygun pazara girmekten daha risklidir"),
    "sikayet-ne": (
        "Mevcut çözümlerden neden şikâyetçiler?",
        "Farklılaşmanın nereden geleceğini belirler; ürün kararını doğrudan etkiler"),
    "giris-engeli": (
        "Bu pazara girişin önünde ne var?",
        "Teknik, yasal ya da dağıtım engeli varsa maliyet ve süre değişir"),
    "ulasilabilir-mi": (
        "Hedef kullanıcıya ulaşılabiliyor mu?",
        "Ürün doğru olsa bile dağıtım kanalı yoksa satılamaz"),

    # kategoriye ozel
    "platform-politikasi": (
        "Platform politikası bu ürüne izin veriyor mu?",
        "Mağaza reddi ürünü tamamen engeller; geliştirmeden önce bilinmeli"),
    "lisans-modeli": (
        "Lisans modeli benimsenmeyi engelliyor mu?",
        "Açık kaynak beklenen bir alanda ticari lisans benimsenmeyi durdurur"),
    "platform-kendi-ekler-mi": (
        "Platform bu işlevi kendi ekler mi?",
        "Ana platform işlevi kendi eklerse eklenti bir gecede değersizleşir"),
    "birim-maliyet": (
        "Çalıştırma maliyeti sürdürülebilir mi?",
        "Çıkarım/işlem maliyeti birim ekonomiyi belirler, fiyatlandırmayı kısıtlar"),
    "cografi-yogunluk": (
        "Hedef bölgede yeterli yoğunluk var mı?",
        "Yerel üründe bir şehirde çalışan model diğerinde çalışmayabilir"),
    "kesfedilebilirlik": (
        "Ürün platformda keşfedilebilir mi?",
        "Katalog çok büyükse iyi ürün bile görünmez kalır"),
}

ORTAK_SORULAR = (
    "talep-var-mi", "rakip-kim", "doygun-mu", "odeme-istegi",
    "talep-yonu", "sikayet-ne", "giris-engeli", "ulasilabilir-mi",
)

KATEGORI_OZEL: dict[str, tuple[str, ...]] = {
    "mobil-uygulama": ("platform-politikasi", "kesfedilebilirlik"),
    "eklenti-entegrasyon": ("platform-politikasi", "platform-kendi-ekler-mi"),
    "gelistirici-araci": ("lisans-modeli",),
    "yapay-zeka-urunu": ("birim-maliyet", "lisans-modeli"),
    "oyun": ("kesfedilebilirlik", "platform-politikasi"),
    "yerel-hizmet": ("cografi-yogunluk",),
    "b2b-web-yazilimi": (),
    "eticaret-fiziksel-urun": ("birim-maliyet",),
}

# --------------------------------------------------------------------------
# Kanit: (soru, kaynak grubu) -> (kanit turu, neden gecerli, zayif alternatif)
# Kategori kendi kaynak gruplarindan kaniti devralir.
# --------------------------------------------------------------------------
KANIT: dict[tuple[str, str], tuple[str, str, str]] = {
    # ---- Mobil uygulama magazalari
    ("talep-var-mi", "Mobil uygulama mağazaları"): (
        "Kategorideki uygulama sayısı ve ilk 20'nin toplam yorum hacmi",
        "Yorum ancak indirip kullandıktan sonra yazılır; iddia değil davranıştır",
        "Uygulama sayısı tek başına — 50 uygulamanın 45'i terk edilmiş olabilir"),
    ("rakip-kim", "Mobil uygulama mağazaları"): (
        "Kategori sıralamasındaki ilk 20 uygulama, geliştirici adları",
        "Mağaza sıralaması indirme ve etkileşime dayanır, editoryal seçim değildir",
        "'En iyi 10 uygulama' listesi yapan blog yazıları — çoğu ortaklık bağlantılı"),
    ("doygun-mu", "Mobil uygulama mağazaları"): (
        "İlk 20'nin yorum sayısı dağılımı ve son güncelleme tarihleri",
        "Yorumun az sayıda uygulamada toplanması doygunluğu, dağılması boşluğu gösterir",
        "Toplam uygulama sayısı — bakımı bırakılmış uygulamalar rekabet değildir"),
    ("odeme-istegi", "Mobil uygulama mağazaları"): (
        "Ücretli uygulamaların fiyat aralığı, uygulama içi satın alma kalemleri",
        "Yayınlanmış fiyat, satıcının gerçekten talep ettiği bedeldir",
        "Anket sonuçları — 'öderim' demek ödemekle aynı şey değildir"),
    ("talep-yonu", "Mobil uygulama mağazaları"): (
        "Sıralama değişimi ve indirme tahmini eğrisi (Sensor Tower, AppMagic)",
        "Zaman serisi yön gösterir; tek ölçüm göstermez",
        "Tek bir aylık indirme sayısı — sezonluk dalgalanma olabilir"),
    ("sikayet-ne", "Mobil uygulama mağazaları"): (
        "Düşük puanlı yorumlarda tekrar eden şikâyet başlıkları",
        "Kullanıcının kendi cümlesiyle yazdığı sorun, ikinci elden yorum değil",
        "Uygulamanın ortalama puanı — neyin bozuk olduğunu söylemez"),
    ("kesfedilebilirlik", "Mobil uygulama mağazaları"): (
        "Kategorideki toplam uygulama sayısı ve ilk sayfaya girme eşiği",
        "Katalog büyüklüğü görünürlüğün maliyetini doğrudan belirler",
        "Genel 'ASO zor' yorumları — sayı vermez"),
    ("platform-politikasi", "Mobil uygulama mağazaları"): (
        "Mağazanın yayın kuralları ve reddedilen işlev listeleri",
        "Kural metni bağlayıcıdır; ret gerekçeleri önceden görülebilir",
        "Forumlardaki 'benimki reddedildi' anlatıları — tekil vaka"),

    # ---- SaaS inceleme siteleri
    ("talep-var-mi", "SaaS, yazılım ve hizmet inceleme siteleri"): (
        "Kategoride listelenen ürün sayısı ve toplam doğrulanmış yorum sayısı",
        "Doğrulanmış yorum, ürünü satın alıp kullanan kurumdan gelir",
        "Satıcının kendi sitesindeki referans listesi — seçilmiş örneklem"),
    ("rakip-kim", "SaaS, yazılım ve hizmet inceleme siteleri"): (
        "Kategori sayfasındaki ürünler ve pazar payı göstergeleri",
        "İnceleme siteleri rakipleri karşılaştırmalı listeler, tek ürün anlatmaz",
        "Google'da ilk çıkan ürünler — reklam bütçesini yansıtır"),
    ("doygun-mu", "SaaS, yazılım ve hizmet inceleme siteleri"): (
        "Ürün sayısı ile yorum sayısının dağılımı; ilk 5'in payı",
        "Yorumun az sayıda üründe toplanması yerleşik oyuncu olduğunu gösterir",
        "Ürün sayısı tek başına — çoğu ürün marjinal olabilir"),
    ("odeme-istegi", "SaaS, yazılım ve hizmet inceleme siteleri"): (
        "Yayınlanmış paket fiyatları ve kullanıcı başına aylık ücret aralığı",
        "Yayınlanmış fiyat pazarın kabul ettiği bandı gösterir",
        "'Fiyat için iletişime geçin' diyen sayfalar — bilgi vermez"),
    ("sikayet-ne", "SaaS, yazılım ve hizmet inceleme siteleri"): (
        "Yorumların 'eksiler' bölümlerinde tekrar eden başlıklar",
        "İnceleme siteleri artı/eksi ayrımını yapılandırılmış tutar",
        "Genel memnuniyet puanı — hangi işlevin eksik olduğunu söylemez"),
    ("ulasilabilir-mi", "SaaS, yazılım ve hizmet inceleme siteleri"): (
        "Rakiplerin hedeflediği şirket büyüklüğü ve sektör kırılımı",
        "Yorum yapan kurumların profili gerçek müşteri tabanını gösterir",
        "Satıcının 'herkes için' iddiası"),

    # ---- Fiyat karsilastirma
    ("odeme-istegi", "Fiyat, teknoloji ve pazar sinyali karşılaştırma kaynakları"): (
        "Aynı işlev için ödenen sözleşme bedelleri ve indirim oranları",
        "Gerçekleşmiş sözleşme, liste fiyatından daha güçlü kanıttır",
        "Liste fiyatı — kurumsal satışta neredeyse hiç uygulanmaz"),
    ("doygun-mu", "Fiyat, teknoloji ve pazar sinyali karşılaştırma kaynakları"): (
        "Teknoloji yığını dağılımı: kaç site hangi ürünü kullanıyor",
        "Kurulu taban, pazar payının doğrudan ölçümüdür",
        "Ürünün kendi 'X binden fazla müşteri' iddiası"),

    # ---- Is ilanlari
    ("talep-var-mi", "İş ilanları ve yetenek talebi"): (
        "Ürün/işlev adını içeren açık ilan sayısı",
        "Şirket para harcayarak insan arıyorsa o işlev gerçekten kullanılıyor",
        "LinkedIn'de o başlığa sahip kişi sayısı — geçmişi gösterir, talebi değil"),
    ("talep-yonu", "İş ilanları ve yetenek talebi"): (
        "İlan hacminin çeyreklik değişimi",
        "İşe alım bütçesi talebin öncü göstergesidir",
        "Tek bir tarihteki ilan sayısı"),
    ("ulasilabilir-mi", "İş ilanları ve yetenek talebi"): (
        "İlan veren şirketlerin sektör ve büyüklük dağılımı",
        "Kimin işe aldığı, kimin bütçesi olduğunu gösterir",
        "Sektör raporlarındaki genel 'hedef kitle' tanımları"),

    # ---- Gelistirici topluluklari ve paket depolari
    ("talep-var-mi", "Yazılım geliştirici ve teknik topluluklar"): (
        "Benzer paketlerin haftalık indirme sayıları",
        "İndirme, kurulum niyetinin ölçüsüdür ve manipüle edilmesi zordur",
        "GitHub yıldız sayısı — ilgi gösterir, kullanım göstermez"),
    ("rakip-kim", "Yazılım geliştirici ve teknik topluluklar"): (
        "Aynı işlevi sunan paketler ve bakım durumları (son commit, açık issue)",
        "Terk edilmiş paket rakip değildir; bakım durumu bunu ayırır",
        "Arama sonucundaki paket sayısı"),
    ("doygun-mu", "Yazılım geliştirici ve teknik topluluklar"): (
        "İndirmenin ilk 3 pakette toplanma oranı",
        "Tek bir paketin baskınlığı yerleşik standart olduğunu gösterir",
        "Toplam paket sayısı — çoğu deneysel olabilir"),
    ("sikayet-ne", "Yazılım geliştirici ve teknik topluluklar"): (
        "Açık issue'larda ve Stack Overflow sorularında tekrar eden başlıklar",
        "Geliştirici sorunu kendi yaşadığı için yazar, pazarlama dili yoktur",
        "Blog yazılarındaki 'X aracının eksikleri' listeleri"),
    ("odeme-istegi", "Yazılım geliştirici ve teknik topluluklar"): (
        "Ticari lisans/destek paketi sunan alternatiflerin fiyatları",
        "Açık kaynak alanında ödeme isteği ancak ticari katmanla ölçülür",
        "İndirme sayısı — ücretsiz kullanım ödeme isteği göstermez"),
    ("lisans-modeli", "Yazılım geliştirici ve teknik topluluklar"): (
        "Alanda baskın lisans türü ve ticari alternatiflerin benimsenme oranı",
        "Alanın lisans beklentisi benimsenmeyi doğrudan belirler",
        "Lisans tartışmalarındaki görüş yazıları"),

    # ---- Eklenti magazalari
    ("talep-var-mi", "Tarayıcı, e-ticaret ve CMS eklenti mağazaları"): (
        "Benzer eklentilerin kurulum sayıları",
        "Kurulum, platform tarafından sayılan gerçek bir eylemdir",
        "Eklenti sayfasındaki yıldız ortalaması"),
    ("doygun-mu", "Tarayıcı, e-ticaret ve CMS eklenti mağazaları"): (
        "Kategorideki eklenti sayısı ve kurulumun ilk 5'te toplanma oranı",
        "Kurulum yoğunlaşması pazarın kapandığını gösterir",
        "Eklenti sayısı tek başına"),
    ("platform-kendi-ekler-mi", "Tarayıcı, e-ticaret ve CMS eklenti mağazaları"): (
        "Platformun sürüm notlarında benzer işlevi eklediği örnekler",
        "Platformun geçmiş davranışı gelecekteki riskin en iyi göstergesidir",
        "'Platform bunu yapmaz' varsayımı"),
    ("platform-politikasi", "Tarayıcı, e-ticaret ve CMS eklenti mağazaları"): (
        "Mağaza yayın kuralları ve izin gerektiren işlev listesi",
        "Kural metni bağlayıcıdır",
        "Diğer eklentilerin yaptıklarına bakmak — kural değişmiş olabilir"),

    # ---- Yapay zeka ekosistemi
    ("rakip-kim", "Yapay zekâ modeli, veri seti ve agent ekosistemi"): (
        "Aynı işlevi sunan model/agent listeleri ve kıyaslama sıralamaları",
        "Kıyaslama tabloları ölçülmüş performans karşılaştırmasıdır",
        "Duyuru blog yazılarındaki iddia edilen performans"),
    ("birim-maliyet", "Yapay zekâ modeli, veri seti ve agent ekosistemi"): (
        "Model sağlayıcılarının token/istek başına yayınlanmış fiyatları",
        "Yayınlanmış fiyat birim maliyeti doğrudan hesaplanabilir kılar",
        "'Maliyetler düşüyor' genellemesi"),
    ("doygun-mu", "Yapay zekâ modeli, veri seti ve agent ekosistemi"): (
        "Entegrasyon dizinlerindeki benzer araç sayısı ve güncellik durumu",
        "Dizinler ekosistemin doluluk derecesini gösterir",
        "Ürün avı sitelerindeki günlük lansman sayısı"),

    # ---- Oyun
    ("doygun-mu", "Oyun dikeyi"): (
        "Türdeki oyun sayısı, eşzamanlı oyuncu dağılımı, inceleme sayıları",
        "Eşzamanlı oyuncu sayısı platformun kendi ölçümüdür",
        "Satış tahmini yapan üçüncü taraf blogları"),
    ("odeme-istegi", "Oyun dikeyi"): (
        "Türdeki oyunların fiyat aralığı ve indirim sıklığı",
        "Sık indirim, fiyat baskısının işaretidir",
        "Liste fiyatı tek başına"),
    ("kesfedilebilirlik", "Oyun dikeyi"): (
        "Platformdaki yıllık yayın sayısı ve öne çıkma kriterleri",
        "Katalog büyümesi görünürlük maliyetini belirler",
        "Başarılı tek bir bağımsız oyun hikâyesi — hayatta kalma yanılgısı"),

    # ---- E-ticaret pazar yerleri
    ("talep-var-mi", "E-ticaret ve fiziksel ürün pazar yerleri"): (
        "Aynı ürün kategorisindeki listeleme sayısı ve satıcı yoğunluğu",
        "Satıcı sayısı, kâr edilebildiğinin dolaylı ama güçlü göstergesidir",
        "Arama sonucu sayısı — alakasız ürünler dahil olabilir"),
    ("odeme-istegi", "E-ticaret ve fiziksel ürün pazar yerleri"): (
        "Fiyat dağılımı ve en çok satan ürünlerin fiyat bandı",
        "Gerçekleşmiş satışların fiyat bandı pazarın kabul ettiği aralıktır",
        "En pahalı ürünün fiyatı"),
    ("birim-maliyet", "E-ticaret ve fiziksel ürün pazar yerleri"): (
        "Platform komisyon oranları ve kargo maliyetleri",
        "Komisyon yayınlanmış ve bağlayıcıdır, marjı doğrudan belirler",
        "Tedarikçi tekliflerindeki tahmini maliyetler"),

    # ---- Yerel isletme dizinleri
    ("cografi-yogunluk", "Yerel işletme, harita ve hizmet dizinleri"): (
        "Hedef şehirdeki işletme sayısı ve yorum yoğunluğu",
        "Dizindeki işletme sayısı o bölgedeki gerçek arzın ölçüsüdür",
        "Şehrin nüfusu — hizmet talebiyle doğrudan orantılı değildir"),
    ("rakip-kim", "Yerel işletme, harita ve hizmet dizinleri"): (
        "Bölgedeki hizmet sağlayıcılar ve platform kullanım oranları",
        "Dizin kaydı, işletmenin dijital kanalda olduğunu gösterir",
        "Sektör derneği üye sayıları"),
    ("odeme-istegi", "Yerel işletme, harita ve hizmet dizinleri"): (
        "Hizmet fiyat aralıkları ve platform komisyonları",
        "İlan edilen hizmet fiyatı gerçek işlem bedeline yakındır",
        "Ortalama gelir istatistikleri"),

    # ---- Ortak havuzdan gelen kanitlar
    ("talep-yonu", "Trafik, SEO, anahtar kelime ve trend"): (
        "Anahtar kelimenin aylık arama hacmi ve 24 aylık eğrisi",
        "Arama hacmi niyetin ölçüsüdür ve zaman serisi yön verir",
        "Tek bir aylık hacim; 'trend oluyor' diyen yazılar"),
    ("talep-var-mi", "Trafik, SEO, anahtar kelime ve trend"): (
        "Problem ifade eden uzun kuyruk aramaların hacmi",
        "İnsanın kendi kelimeleriyle aradığı problem, doğrudan talep sinyalidir",
        "Marka adı aramaları — mevcut farkındalığı ölçer, ihtiyacı değil"),
    ("sikayet-ne", "Sosyal ağlar ve açık topluluklar"): (
        "Tekrar eden şikâyet ve 'alternatif arıyorum' gönderileri",
        "Kullanıcı kendi sorununu kendi cümlesiyle yazar",
        "Beğeni sayısı yüksek tek bir gönderi"),
    ("rakip-kim", "Şirket, yatırım ve startup verisi"): (
        "Alanda yatırım almış şirketler, tur büyüklükleri ve tarihleri",
        "Yatırım kaydı doğrulanabilir ve tarihlidir",
        "Basın bültenlerindeki 'lider konum' iddiaları"),
    ("giris-engeli", "Regülasyon ve hukuk kaynakları"): (
        "Alanı düzenleyen mevzuat, gereken izin ve lisanslar",
        "Mevzuat metni bağlayıcıdır; yorum değil kuraldır",
        "'Bu alan düzenlenmiyor' varsayımı"),
    ("giris-engeli", "Patent ve marka"): (
        "Alandaki patent başvuru yoğunluğu ve baskın hak sahipleri",
        "Patent kaydı kamuya açık ve tarihlidir",
        "Patent sayısının çokluğu tek başına — çoğu uygulanmıyor olabilir"),
    ("ulasilabilir-mi", "Reklam kütüphaneleri ve pazarlama sinyalleri"): (
        "Rakiplerin hangi kanalda reklam verdiği ve mesaj başlıkları",
        "Reklam kütüphaneleri yayınlanmış gerçek reklamları gösterir; para harcanan kanal, işleyen kanaldır",
        "'Sosyal medyadan ulaşırız' varsayımı — hangi kanalın çalıştığını söylemez"),
    ("ulasilabilir-mi", "Sosyal ağlar ve açık topluluklar"): (
        "Hedef kitlenin toplandığı topluluklar ve üye sayıları",
        "Var olan topluluk, kitlenin nerede olduğunun doğrudan kanıtıdır",
        "Genel kullanıcı sayısı istatistikleri — hedef kitleyi ayırmaz"),

    ("odeme-istegi", "Tarayıcı, e-ticaret ve CMS eklenti mağazaları"): (
        "Ücretli eklentilerin fiyatları ve ücretsiz/ücretli oranı",
        "Mağazada yayınlanmış fiyat, satıcının talep ettiği gerçek bedeldir",
        "Eklenti sayfasındaki 'binlerce kullanıcı' ifadesi — ücretsiz kullanım olabilir"),

    ("odeme-istegi", "Yapay zekâ modeli, veri seti ve agent ekosistemi"): (
        "Ücretli API katmanı sunan benzer ürünlerin fiyatlandırma sayfaları",
        "Yayınlanmış API fiyatı, ödeme isteğinin ölçülebilir karşılığıdır",
        "Açık kaynak modelin indirme sayısı — ücretsiz kullanım ödeme demek değil"),
    ("lisans-modeli", "Yapay zekâ modeli, veri seti ve agent ekosistemi"): (
        "Alandaki modellerin lisans türleri ve ticari kullanım kısıtları",
        "Model kartlarındaki lisans metni bağlayıcıdır ve ticari kullanımı belirler",
        "'Açık ağırlıklı' ifadesi — ticari kullanıma izin verdiği anlamına gelmez"),

    ("platform-politikasi", "Oyun dikeyi"): (
        "Platformun yayın kuralları ve içerik kısıtları",
        "Kural metni bağlayıcıdır; ret gerekçeleri önceden görülebilir",
        "Benzer oyunların yayınlanmış olması — kural değişmiş olabilir"),

    ("doygun-mu", "Yerel işletme, harita ve hizmet dizinleri"): (
        "Bölgedeki hizmet sağlayıcı sayısı ve yorumun ilk 10'da toplanma oranı",
        "Yorum yoğunlaşması yerleşik oyuncuların varlığını gösterir",
        "İşletme sayısı tek başına — çoğu dijital kanalda aktif olmayabilir"),

    ("doygun-mu", "E-ticaret ve fiziksel ürün pazar yerleri"): (
        "Kategorideki satıcı sayısı ve satışın ilk 10 satıcıda toplanma oranı",
        "Satışın az sayıda satıcıda toplanması pazarın kapandığını gösterir",
        "Listeleme sayısı — aynı satıcının çok sayıda varyantı olabilir"),

    ("talep-var-mi", "Kamu verisi ve istatistik"): (
        "Hedef kitlenin büyüklüğü ve ilgili sektör istatistikleri",
        "Resmî istatistik yöntemi açıklanmış ve tekrarlanabilir ölçümdür",
        "Pazar araştırması şirketlerinin ücretli rapor özetleri"),
}


def kategori_kaynak_gruplari(yol: Path) -> dict[str, dict[str, list[str]]]:
    """Her kategori icin kaynak grubu -> o gruptaki kaynak adlari."""
    veri: dict[str, dict[str, list[str]]] = collections.defaultdict(
        lambda: collections.defaultdict(list))
    with yol.open(encoding="utf-8") as handle:
        for satir in csv.DictReader(handle):
            for grup in satir["kaynak_grubu"].split(" | "):
                veri[satir["hedef"]][grup.strip()].append(satir["kaynak"])
    return {k: dict(v) for k, v in veri.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kategori-kaynak", type=Path, default=HERE / "KATEGORI-KAYNAK.csv")
    parser.add_argument("--ledger", type=Path, default=HERE / "KAYNAK-DEFTERI.csv")
    parser.add_argument("--out", type=Path, default=HERE / "KATEGORI-SORU.csv")
    args = parser.parse_args()

    gruplar = kategori_kaynak_gruplari(args.kategori_kaynak)
    with args.ledger.open(encoding="utf-8") as handle:
        defter = {r["ad"]: r for r in csv.DictReader(handle)}

    satirlar: list[dict[str, Any]] = []
    kanitsiz: list[tuple[str, str]] = []
    for kategori in KATEGORI_OZEL:
        # Kategorinin kendi gruplari + ortak havuzun gruplari birlikte taranir:
        # ortak havuz her kategoride kullanildigi icin kaniti da her kategoride
        # gecerlidir.
        kendi = gruplar.get(kategori, {})
        ortak = gruplar.get("ortak", {})
        for soru_id in (*ORTAK_SORULAR, *KATEGORI_OZEL[kategori]):
            soru, neden_onemli = SORULAR[soru_id]
            bulundu = False
            for kaynak_ol, grup_kumesi in (("kategori", kendi), ("ortak", ortak)):
                for grup, kaynaklar in grup_kumesi.items():
                    kanit = KANIT.get((soru_id, grup))
                    if kanit is None:
                        continue
                    tur, gecerli, zayif = kanit
                    calisan = [a for a in kaynaklar
                               if defter.get(a, {}).get("durum") == "cekildi"]
                    satirlar.append({
                        "kategori": kategori, "soru_id": soru_id, "soru": soru,
                        "soru_turu": "ortak" if soru_id in ORTAK_SORULAR else "kategoriye-ozel",
                        "neden_onemli": neden_onemli,
                        "kanit_turu": tur, "kanit_kaynak_grubu": grup,
                        "kanit_kaynak_rolu": kaynak_ol,
                        "ornek_kaynaklar": ", ".join(sorted(calisan)[:4]),
                        "kaynak_sayisi": len(kaynaklar), "calisan_kaynak": len(calisan),
                        "neden_gecerli": gecerli, "zayif_alternatif": zayif,
                    })
                    bulundu = True
            if not bulundu:
                kanitsiz.append((kategori, soru_id))

    satirlar.sort(key=lambda r: (r["kategori"], r["soru_id"], r["kanit_kaynak_grubu"]))
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        yazici = csv.DictWriter(handle, fieldnames=list(satirlar[0]))
        yazici.writeheader()
        yazici.writerows(satirlar)

    print(json.dumps({
        "cikti": str(args.out), "satir": len(satirlar),
        "soru": len(SORULAR), "ortak_soru": len(ORTAK_SORULAR),
        "kategori": len(KATEGORI_OZEL),
        # Kaniti olmayan soru, cevaplanamayan sorudur; sessizce gecilmez.
        "kanitsiz_soru": [f"{k}/{s}" for k, s in kanitsiz] or "yok",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
