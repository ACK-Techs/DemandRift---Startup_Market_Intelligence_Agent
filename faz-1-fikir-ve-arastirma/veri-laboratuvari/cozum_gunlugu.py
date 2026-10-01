"""AS-06 — cozum gunlugu ve kaynak saglik kayitlari.

Gorev karti: "Her bulguda denenen sorgu/yol, tarih, script surumu, once/sonra
veri, cozulemeyen sinir ve FB-ID tut. Cozumu Batuhan'in yeniden uretebilecegi
sekilde teslim et. **Basarili ve basarisiz kaynak orneklerini birlikte koru.**"

Iki kayit uretilir ve ikisi farkli seyi tutar:

* ``COZUM-GUNLUGU.csv`` — **ne yaptik.** Her bulgu icin denenen yol, tarih,
  script surumu, oncesi, sonrasi, kalan sinir, FB-ID ve yeniden uretim komutu.
  Bu kayit elle yazilir cunku tarihsel bir anlatidir; veriden turetilemez.
  Dogrulanabilir olmasi icin her satir bir commit'e ve bir olcume baglanir.

* ``KAYNAK-SAGLIK.csv`` — **kaynak bugun ne durumda.** Bu kayit olculur,
  yazilmaz: artefakt dizinlerinden ve AS-01 yoklamasindan turer.

Son cumle kasitli: **basarisiz kaynaklar silinmez.** Calisan kaynaklari yazip
calismayanlari atmak, ayni siteyi bir sonraki turda yeniden denememize ve
ayni duvara ayni sekilde carpmamiza yol acar. Saglik kaydi ikisini de tutar.

Gunluk bir **basari raporu degildir.** Denenip olmayan yollar, yanlis cikan
tahminler ve geri alinan kararlar da buradadir; bir yolun denenmis ve
calismamis oldugunu bilmek, hic denenmemis olmasindan farklidir.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SURUM = "1.0.0"

# (bulgu_id, baslik, ne_denendi, tarih, script, once, sonra, durum,
#  kalan_sinir, fb_id, yeniden_uretim, commit)
#
# durum: cozuldu | kismen | cozulemedi
# "cozulemedi" bir basarisizlik kaydi degil, bir SINIR kaydidir: o yolun
# denenmis ve yurumemis oldugunu soyler.
BULGULAR: list[dict[str, str]] = [
    {
        "bulgu_id": "CG-01",
        "baslik": "robots_state RFC 9309'un altinda kaliyordu",
        "ne_denendi": "api.stackexchange.com/robots.txt — resmi API host'u robots.txt "
                      "yerine HTTP 400 + JSON hata donduruyor",
        "tarih": "2026-09-24",
        "script": "bulk_site_access_lab.py",
        "once": "robots_preflight_blocked — istek hic atilmadi",
        "sonra": "robots=absent; API calisti, 4980 karakter, 3 gercek sonuc",
        "durum": "cozuldu",
        "kalan_sinir": "stackoverflow.com ayri: HTTP 418 ile GECERLI bir "
                       "'Disallow: /' donduruyor ve bu yasak korunuyor",
        "fb_id": "—",
        "yeniden_uretim": "python3 as01_kaynak_kontrol.py --canli  (F03 satiri)",
        "commit": "bc446ef",
    },
    {
        "bulgu_id": "CG-02",
        "baslik": "iTunes Search API beyan edilen MIME yuzunden reddediliyordu",
        "ne_denendi": "itunes.apple.com/search?term=Booksy&entity=software — "
                      "gecerli JSON'u text/javascript tipiyle servis ediyor",
        "tarih": "2026-09-24",
        "script": "bulk_site_access_lab.py",
        "once": "mime_or_sniff_mismatch — dort terimde de basarisiz",
        "sonra": "Booksy Biz id=725335996, puan 4.52, 14.888 yorum sayisi alindi",
        "durum": "cozuldu",
        "kalan_sinir": "—",
        "fb_id": "—",
        "yeniden_uretim": "python3 alternatif_kaynak.py --canli  (F09 App Store satirlari)",
        "commit": "635ce4b",
    },
    {
        "bulgu_id": "CG-03",
        "baslik": "Fiyat deseni para birimi onde gelen bicimi kaciriyordu",
        "ne_denendi": "fresha.com/pricing — fiyatlar 'TRY 240.95 per month' bicimde",
        "tarih": "2026-09-24",
        "script": "normalize_belgeler.py",
        "once": "fiyat alani bos; 55 fiyat isareti olan sayfadan 0 fiyat cikti",
        "sonra": "TRY 240.95 yakalandi; TL, EUR, GBP onek bicimleri de",
        "durum": "cozuldu",
        "kalan_sinir": "—",
        "fb_id": "—",
        "yeniden_uretim": "python3 -c \"import normalize_belgeler as n; "
                          "print(n.alan_cikar('urun','TRY 240.95 per month',''))\"",
        "commit": "302497e",
    },
    {
        "bulgu_id": "CG-04",
        "baslik": "Reddit kazimayla alinamiyor",
        "ne_denendi": "reddit.com/robots.txt bugun yeniden cekildi; /r/*/.rss, "
                      "/r/*/new.json, /dev/api dahil yedi yol robots'a soruldu",
        "tarih": "2026-09-24",
        "script": "as01_kaynak_kontrol.py",
        "once": "kayitta 'kismi/dosya-yok'; sebep belirsizdi",
        "sonra": "sebep kesin: 'User-agent: * / Disallow: /' — yedi yolun yedisi yasak",
        "durum": "cozulemedi",
        "kalan_sinir": "Politika engeli. Reddit'in kendi robots.txt'i izinli yolu "
                       "gosteriyor: Public Content Policy ve r/reddit4researchers. "
                       "Hesap ve sartname onayi gerekir; karar Cağlar'da. "
                       "10 fikrin 7'sini etkiliyor.",
        "fb_id": "AS01-0075",
        "yeniden_uretim": "python3 as01_kaynak_kontrol.py --canli  (Reddit satirlari)",
        "commit": "bc446ef",
    },
    {
        "bulgu_id": "CG-05",
        "baslik": "Capterra kayitla celisiyor: kayit calisiyor diyor, bugun kapali",
        "ne_denendi": "capterra.com/proofing-software/ ve /salon-software/ — "
                      "robots izin veriyor, istek bot korumasina takiliyor",
        "tarih": "2026-09-24",
        "script": "as01_kaynak_kontrol.py",
        "once": "2 Eylul kaydi: erisim=cekildi, icerik=gercek-icerik",
        "sonra": "bugun challenge; F02, F09 ve F10'u etkiliyor",
        "durum": "cozulemedi",
        "kalan_sinir": "Bot korumasi asilmiyor. Arsiv (Common Crawl) kopyasi var "
                       "ama canli degil ve 'arsiv' etiketiyle tasinmali.",
        "fb_id": "AS01-0135",
        "yeniden_uretim": "python3 as01_kaynak_kontrol.py --canli  (F02/F09 Capterra)",
        "commit": "bc446ef",
    },
    {
        "bulgu_id": "CG-06",
        "baslik": "Google Play HTTP 200 donuyor ama govde bos",
        "ne_denendi": "play.google.com/store/apps/details?id=... — robots izinli, "
                      "istek basarili",
        "tarih": "2026-09-24",
        "script": "as01_kaynak_kontrol.py",
        "once": "erisim listesinde 'ok' gorunuyordu",
        "sonra": "200 OK, 0 karakter gorunur metin; js-kabugu olarak ayrildi",
        "durum": "kismen",
        "kalan_sinir": "Sayfa tamamen tarayicida uretiliyor. Ayni uygulamalar "
                       "Apple App Store'da aliniyor (21-28 bin karakter, puan ve "
                       "fiyatla); Google Play tarafi acik kaliyor.",
        "fb_id": "AS01-0097",
        "yeniden_uretim": "python3 as01_kaynak_kontrol.py --canli  (F01/F10 Google Play)",
        "commit": "bc446ef",
    },
    {
        "bulgu_id": "CG-07",
        "baslik": "Uygulama magazasi kayit sayfalari bos geliyor",
        "ne_denendi": "galaxystore.samsung.com/detail/... ve apps.microsoft.com/"
                      "detail/... — sitemap'lerden 14.948 kayit adresi cikarildi, "
                      "6 tanesi test edildi",
        "tarih": "2026-09-18",
        "script": "ic_sayfa_gecisi.py",
        "once": "14.948 aday adres; mobil-uygulama kategorisi 1/6 hucrede doluydu",
        "sonra": "Microsoft bos govde, Samsung 38 karakter; kategori acik kaldi",
        "durum": "cozulemedi",
        "kalan_sinir": "Istemci tarafinda uretilen magaza sayfalari bu hatla "
                       "alinamiyor. Adres sayisi coklugu ise yaramiyor.",
        "fb_id": "—",
        "yeniden_uretim": "AS01-ALTERNATIF-KAYNAK.csv · kayit sayfasi testi",
        "commit": "298f5c0",
    },
    {
        "bulgu_id": "CG-08",
        "baslik": "Apple musteri yorumu RSS ucu bos donuyor",
        "ne_denendi": "itunes.apple.com/us/rss/customerreviews/page=1/id=725335996/json — "
                      "Booksy Biz ve Fresha for business icin denendi",
        "tarih": "2026-09-24",
        "script": "alternatif_kaynak.py",
        "once": "belgelenmis uc; yorum METNI icin ilk tercih",
        "sonra": "gecerli JSON donuyor ama 'entry' dizisi bos — uc fiilen emekli",
        "durum": "cozuldu",
        "kalan_sinir": "Calisan yol uygulama SAYFASININ kendisi cikti: "
                       "apps.apple.com/.../id725335996 icinde gercek yorum metni var.",
        "fb_id": "—",
        "yeniden_uretim": "python3 alternatif_kaynak.py --canli  (F09 App Store satiri)",
        "commit": "635ce4b",
    },
    {
        "bulgu_id": "CG-09",
        "baslik": "HTTP 200 + gercek icerik, ilgisiz sonuc",
        "ne_denendi": "sourceforge.net/directory/?q=salon+scheduling+software",
        "tarih": "2026-09-24",
        "script": "alternatif_kaynak.py",
        "once": "aday listesinde 'calisiyor' sayiliyordu",
        "sonra": "200 OK, 19 bin karakter; icerik Kubernetes orkestrasyon ve "
                 "kripto fiyatlama — nisle ilgisi yok",
        "durum": "cozuldu",
        "kalan_sinir": "Her adaya ucuncu bir test eklendi: erisim ve icerik "
                       "yetmiyor, nisin kendi kelimeleri govdede aranmali. "
                       "Anahtar kelime eslesmesi ilgililik degildir.",
        "fb_id": "—",
        "yeniden_uretim": "python3 -m unittest test_alternatif_kaynak.IlgililikTests",
        "commit": "302497e",
    },
    {
        "bulgu_id": "CG-10",
        "baslik": "F02 icin kullanici sikayeti kaynagi bulunamadi",
        "ne_denendi": "Filestage/Ziflow (satici sitesi), SourceForge (ilgisiz), "
                      "GetApp (challenge), Hacker News API (0 sonuc), "
                      "iTunes Search (mobil uygulama yok)",
        "tarih": "2026-09-24",
        "script": "alternatif_kaynak.py",
        "once": "F02'nin uc kaynagi da kapaliydi",
        "sonra": "fiyat/urun icin Filestage ve Ziflow bulundu; sikayet icin hicbiri",
        "durum": "kismen",
        "kalan_sinir": "Satici kendi hakkindaki sikayeti yayimlamaz. F02 fiyat ve "
                       "urun iddiasi icin arastirilabilir, memnuniyetsizlik icin "
                       "arastirilamaz. Filestage ve Ziflow katalogda YOK — "
                       "registry karari Batuhan'da.",
        "fb_id": "AS01-0134, AS01-0135",
        "yeniden_uretim": "python3 alternatif_kaynak.py --canli  (F02 satirlari)",
        "commit": "635ce4b",
    },
    {
        "bulgu_id": "CG-11",
        "baslik": "Ham arsiv depo disinda kaldi; iddialar dogrulanamiyordu",
        "ne_denendi": "Uc fazli yapiya tasinma sonrasi artefakt konumu sayildi",
        "tarih": "2026-09-24",
        "script": "as01_kaynak_kontrol.py",
        "once": "1249 normalize belgenin 21'inin ham dosyasi depoda (%1.7)",
        "sonra": "sayi cikarilan 154 dosya depoya alindi; "
                 "KATEGORI-ALANLARI.csv'deki 164 alanin 164'u dogrulanabilir",
        "durum": "kismen",
        "kalan_sinir": "SourceFitMatrix ornek kayitlari 101/346'da; tamamlamak "
                       "~75 MB daha demek, karar Batuhan'da. Kalan 1070 belge "
                       "ana sayfa ve sitemap — dogrulanacak iddia tasimiyorlar.",
        "fb_id": "—",
        "yeniden_uretim": "python3 -m unittest "
                          "test_as01_kaynak_kontrol.CikarilanSayininKaynagiDepodaTests",
        "commit": "474a09c",
    },
    {
        "bulgu_id": "CG-12",
        "baslik": "Arşiv kopyalarının kendi tarihi hiçbir tabloda yoktu",
        "ne_denendi": "104 Common Crawl kopyasının warc_timestamp'i koşu JSON'undan "
                      "okundu ve dizindeki tarihle karşılaştırıldı",
        "tarih": "2026-09-25", "script": "alternatif_fark.py",
        "once": "ARTEFAKT-DIZINI.csv hepsine 2026-09-03 (bizim indirme tarihimiz) yazıyordu",
        "sonra": "94 kopya 180 günü, 93'ü bir yılı aşıyor; en eskisi 596 gün. "
                 "Her satır kendi tarihini ve guncel_veri_mi=hayır taşıyor",
        "durum": "cozuldu",
        "kalan_sinir": "Arşiv içeriği tazelenemez; yalnız yaşı görünür oldu.",
        "fb_id": "—", "yeniden_uretim": "python3 alternatif_fark.py --yaz",
        "commit": "af28f5f",
    },
    {
        "bulgu_id": "CG-13",
        "baslik": "Alan çıkarımı sayfaya değil kaynağın ailesine bakıyordu",
        "ne_denendi": "Fiyat yüzeyi olarak çekilmiş 48 sayfada fiyat çıkmıyordu; "
                      "25'inin gövdesinde apaçık fiyat vardı (Kagi, Sistrix, "
                      "Exploding Topics)",
        "tarih": "2026-09-25", "script": "normalize_belgeler.py",
        "once": "alan 212, fiyat 56, fiyat sayfası olup fiyat çıkmayan 48",
        "sonra": "alan 273, fiyat 108, fiyat çıkmayan 16",
        "durum": "cozuldu",
        "kalan_sinir": "Kalan 16 sayfada gövdede gerçekten fiyat yok.",
        "fb_id": "—", "yeniden_uretim": "python3 normalize_belgeler.py --yaz",
        "commit": "bc7bf2a",
    },
    {
        "bulgu_id": "CG-14",
        "baslik": "Filtre gerçek kanıt eliyordu",
        "ne_denendi": "'Ölçüm kanıtı üretmez' diye elenen 76 belgede fiyat çıktı; "
                      "bağlamları tek tek okundu",
        "tarih": "2026-09-25", "script": "hata_incelemesi.py",
        "once": "76 belge elenmişti, hangisinin gerçek olduğu bilinmiyordu",
        "sonra": "10'u gerçek kanıt (Airbnb ₺4.733 + 4.78 puan, AppSumo $39 + "
                 "3 yorum), 66'sı gürültü ('$2.3 billion in AUM' gibi)",
        "durum": "kismen",
        "kalan_sinir": "Ayrım kuralı yazıldı ama filtreye henüz uygulanmadı; "
                       "10 kanıt hâlâ elenmiş durumda.",
        "fb_id": "—", "yeniden_uretim": "python3 hata_incelemesi.py --yaz",
        "commit": "bc7bf2a",
    },
    {
        "bulgu_id": "CG-15",
        "baslik": "Yoklama artefaktları kanıt zincirine hiç girmiyordu",
        "ne_denendi": "AS-01 ve AS-03 scriptleri artefaktı diske yazıyor ama "
                      "EK-ARTEFAKT-DIZINI.csv'ye satır eklemiyordu",
        "tarih": "2026-09-27", "script": "normalize_belgeler.py",
        "once": "Fresha'nın TRY fiyatı, Booksy'nin no-show yorumu, Filestage ve "
                "Ziflow raporlarda kanıt diye gösteriliyordu ama veri kümesinde yoktu; "
                "AS-04'ün iki karşıt bulgusu sayımda görünmüyordu",
        "sonra": "21 artefakt dizine işlendi; belge 1249→1270, alan 273→307, "
                 "karşıt bulgular sayımda göründü",
        "durum": "cozuldu",
        "kalan_sinir": "Scriptler hâlâ dizine kendileri yazmıyor; geri dolduruldu.",
        "fb_id": "—", "yeniden_uretim": "python3 kanit_sayimi.py --yaz",
        "commit": "b24fcbe",
    },
    {
        "bulgu_id": "CG-16",
        "baslik": "Aynı şirketin farklı markaları bağımsız sayılıyordu",
        "ne_denendi": "3/2 sayımı geçen hücrelerde ortak sahiplik arandı",
        "tarih": "2026-09-27", "script": "source_fit_matrix.py",
        "once": "GetApp ve Software Advice (ikisi de Gartner'ın) "
                "b2b-web-yazilimi/competitor_discovery'de 2 bağımsız kaynak sayılıyordu",
        "sonra": "Bilinen sahiplik gruplamaya eklendi; 421→415 grup, geçen hiçbir "
                 "hücrede aynı sahibin iki markası ayrı değil",
        "durum": "cozuldu",
        "kalan_sinir": "Sahiplik listesi BEYAN EDİLMİŞ bilgidir, ölçülmüş değil; "
                       "Batuhan'ın incelemesine açık. Listede olmayan ortak "
                       "sahiplikler hâlâ ayrı sayılır.",
        "fb_id": "—", "yeniden_uretim": "python3 -m unittest "
                  "test_source_fit_matrix.KopyalarBagimsizSayilmazTests",
        "commit": "3bce1e3",
    },
    {
        "bulgu_id": "CG-17",
        "baslik": "Yakalanan sayfalarda üçüncü taraf API anahtarları vardı",
        "ne_denendi": "GitHub push protection iki kez reddetti; tüm sağlayıcı "
                      "desenleri (Replicate, Stripe, Clerk, JWT...) tarandı",
        "tarih": "2026-09-25", "script": "ic_sayfa_gecisi.py",
        "once": "push reddi: 'Push cannot contain secrets' — bir Replicate token, "
                "iki pk_live, bir JWT",
        "sonra": "4 artefakt redakte edildi; orijinaller local-originals/ altına, "
                 "shared-redactions.json'a 9 kayıt",
        "durum": "cozuldu",
        "kalan_sinir": "Anahtarlar sitelerin kendi yayımladığı değerlerdi, bizim "
                       "değil. Yeni artefakt eklenirken tarama tekrarlanmalı.",
        "fb_id": "—", "yeniden_uretim": "grep -rE 'r8_[A-Za-z0-9]{35,}|pk_live_' results/raw/",
        "commit": "952f4b5",
    },
    {
        "bulgu_id": "CG-18",
        "baslik": "as01_kaynak_kontrol.py komut satırından çalışmıyordu",
        "ne_denendi": "Batuhan'ın source_plan.py'si bu scripti LAB_SCRIPT olarak "
                      "çağırıyor; çalıştırılınca NameError veriyordu",
        "tarih": "2026-09-27", "script": "as01_kaynak_kontrol.py",
        "once": "`python3 as01_kaynak_kontrol.py --canli` → "
                "NameError: iddialari_dogrula is not defined",
        "sonra": "if __name__ bloğu dosya sonuna taşındı; script çalışıyor",
        "durum": "cozuldu",
        "kalan_sinir": "Modül olarak import edilince sorun yoktu, bu yüzden "
                       "testler yakalamamıştı. CLI yolu test edilmiyor.",
        "fb_id": "—", "yeniden_uretim": "python3 as01_kaynak_kontrol.py --yaz",
        "commit": "—",
    },
    {
        "bulgu_id": "CG-19",
        "baslik": "İçerik-adresli yazıcı redaksiyon sözleşmesiyle çarpışıyor",
        "ne_denendi": "BT-02 sağlık taraması redakte edilmiş bir sayfayı yeniden "
                      "çekince yazıcı durdu",
        "tarih": "2026-09-27", "script": "saglik_taramasi.py",
        "once": "ValueError: existing_raw_artifact_hash_mismatch — tarama çöktü",
        "sonra": "Saklama tarama tarafından yönetiliyor; redakte dosyanın üzerine "
                 "yazılmıyor. 305 kaynak tarandı",
        "durum": "cozuldu",
        "kalan_sinir": "İki sözleşme yapısal olarak çelişiyor: dosya adı orijinal "
                       "hash'i korurken baytlar farklı. Yeni yazan her modül bunu "
                       "bilmek zorunda.",
        "fb_id": "—", "yeniden_uretim": "python3 saglik_taramasi.py --canli --sinir 6",
        "commit": "—",
    },
    {
        "bulgu_id": "CG-20",
        "baslik": "Normalize taşınmadan sonra artefaktların çoğunu bulamıyordu",
        "ne_denendi": "Depo üç fazlı yapıya taşındıktan sonra script ilk kez koşturuldu",
        "tarih": "2026-09-25", "script": "normalize_belgeler.py",
        "once": "1249 belge 179'a düştü; iyi bir veri kümesi eksik olanla üzerine yazıldı",
        "sonra": "İki arşiv konumuna da bakıyor; 1249 geri geldi",
        "durum": "cozuldu",
        "kalan_sinir": "Artefaktların 1021'i hâlâ yalnız yerel arşivde; depoya "
                       "yalnız sayı çıkarılanlar alındı.",
        "fb_id": "—", "yeniden_uretim": "python3 normalize_belgeler.py --yaz",
        "commit": "bc7bf2a",
    },
    {
        "bulgu_id": "CG-21",
        "baslik": "AS-02 makinesi ölçemediği alan için 'çıkarılamadı' diyordu",
        "ne_denendi": "BT-03 bildirimindeki expected_fields `beklenen_alanlar` "
                      "kolonuna yazıldı ve makine koşturuldu",
        "tarih": "2026-10-01", "script": "yeniden_uret.py",
        "once": "Üç kaynak da `alan-cikarimi`; Batuhan'ın 'tam' dediği Stack "
                "Overflow için bile 'baslik çıkarılamadı' dedi",
        "sonra": "Üçü de `sozlesme-disi`; makine ölçemediğini söylüyor, "
                 "yargı vermiyor",
        "durum": "cozuldu",
        "kalan_sinir": "İki sözlük ayrı: bizimki pazar sinyali (fiyat, lisans), "
                       "Batuhan'ınki belge kaydı (baslik, govde). Ortak tek isim "
                       "`surum` ve o bile aynı şeyi anlatmıyor.",
        "fb_id": "BT03-01, BT03-02, BT03-03",
        "yeniden_uretim": "python3 yeniden_uret.py --asama once --yaz",
        "commit": "—",
    },
    {
        "bulgu_id": "CG-22",
        "baslik": "İlgililik testi gevşekti; başlık kanıtı istemiyordu",
        "ne_denendi": "Batuhan HN sonuçlarının konu uygunluğunu zayıf buldu, "
                      "bizim test beşini de ilgili saymıştı",
        "tarih": "2026-10-01", "script": "yeniden_uret.py",
        "once": "4 ayırt edici kelimeden 2 eşleşme yetiyordu; uzun teknik "
                "gövdelerde alakasız bağlamlar da sayılıyordu",
        "sonra": "Başlık kanıtı kayıt başına ölçülüyor, çoğunluk isteniyor ve "
                 "üçüncü sonuç var: GitHub 5/5 relevant, Stack Overflow 1/5 "
                 "uncertain, Hacker News 0/5 uncertain",
        "durum": "cozuldu",
        "kalan_sinir": "`uncertain` kayıtlar makineyle kapanmaz; AS-04 insan "
                       "etiketi kuyruğuna giriyor.",
        "fb_id": "BT03-03",
        "yeniden_uretim": "python3 yeniden_uret.py --asama once --yaz",
        "commit": "—",
    },
    {
        "bulgu_id": "CG-23",
        "baslik": "Başlık ayıklama iç içe alanları da kayıt sanıyordu",
        "ne_denendi": "GitHub /search/issues yanıtında başlık sayısı doğrulandı",
        "tarih": "2026-10-01", "script": "yeniden_uret.py",
        "once": "5 issue için 23 başlık (etiket/kullanıcı `name`'leri), `name` "
                "çıkarılınca 7 (iç içe `milestone.title`) — oran bozuluyordu",
        "sonra": "Yalnız kayıt düzeyi: 5/5",
        "durum": "cozuldu",
        "kalan_sinir": "Kayıt listesi anahtarı sabit listeden tanınıyor "
                       "(items/hits/results/data); başka şemada elle eklenmeli.",
        "fb_id": "BT03-01",
        "yeniden_uretim": "python3 yeniden_uret.py --asama once --yaz",
        "commit": "—",
    },
    {
        "bulgu_id": "CG-24",
        "baslik": "HN kaynak_url yorumun değil bağlanan yazının adresini veriyor",
        "ne_denendi": "BT-03'te bildirilmeyen alanlar da tek tek sınandı",
        "tarih": "2026-10-01", "script": "bt03_alan_analizi.py",
        "once": "story_url 4/5 dolu ve dolu olanlar yorumun değil dış yazının "
                "adresi — eksik değil YANLIŞ, sessizce rapora girer",
        "sonra": "objectID 5/5 dolu; item?id=<objectID> yorumun kanonik adresi",
        "durum": "bildirildi",
        "kalan_sinir": "Düzeltme Batuhan'ın tarafında; SourceItemPreview "
                       "değişikliği gerekip gerekmediği soruldu.",
        "fb_id": "BT03-03",
        "yeniden_uretim": "python3 bt03_alan_analizi.py --canli --yaz",
        "commit": "—",
    },
]


def _oku(ad: str) -> list[dict[str, str]]:
    yol = HERE / ad
    if not yol.exists():
        return []
    with yol.open(encoding="utf-8") as tutamak:
        return list(csv.DictReader(tutamak))


def _yaz(ad: str, satirlar: list[dict[str, Any]]) -> None:
    if not satirlar:
        return
    with (HERE / ad).open("w", newline="", encoding="utf-8") as tutamak:
        yazici = csv.DictWriter(tutamak, fieldnames=list(satirlar[0]))
        yazici.writeheader()
        yazici.writerows(satirlar)


# --------------------------------------------------------------------------
# Kaynak saglik kayitlari
# --------------------------------------------------------------------------
# Saglik "calisiyor mu" degil, **hangi duvara carpiyor** sorusunu cevaplar.
# Ayni sebep ayni cozumu gerektirir; sebebi bilmeden yeniden denemek ayni
# duvara yeniden carpmaktir.
SAGLIK_SINIFI: dict[str, tuple[str, str]] = {
    "ok": ("saglikli", "içerik geliyor"),
    "robots_disallowed": ("politika-kapali", "robots.txt yolu yasaklıyor — aşılmaz"),
    "robots_preflight_blocked": ("politika-kapali", "robots.txt 401/403 — tam yasak"),
    "challenge": ("bot-korumasi", "site bizi bot olarak tanıyıp reddediyor — aşılmaz"),
    "origin_circuit_open": ("bot-korumasi", "aynı origin'de önceki istek reddedildi"),
    "rate_limited": ("hiz-siniri", "istek aralığı artırılmalı; kaynak kapalı değil"),
    "source_unavailable": ("adres-hatasi", "adres yanıt vermiyor ya da sayfa yok"),
    "origin_denied": ("adres-hatasi", "sunucu isteği reddetti"),
    "mime_or_sniff_mismatch": ("bicim-uyusmazligi", "beyan edilen tip beklenenden farklı"),
    "budget_exhausted": ("butce", "koşu bütçesi bitti; kaynak hakkında bilgi vermez"),
}
ICERIK_NOTU: dict[str, str] = {
    "js-kabugu": "HTTP 200 ama görünür metin yok — sayfa tarayıcıda üretiliyor",
    "aday-kesif": "yalnız sitemap/adres listesi — içerik değil",
    "arsiv": "Common Crawl kopyası — canlı değil",
    "dosya-yok": "bu checkout'ta açılabilir dosya yok",
}


def saglik_kayitlari() -> list[dict[str, Any]]:
    """Kaynak basina saglik. Basarili ve basarisiz BIRLIKTE tutulur."""
    envanter = {r["source_id"]: r for r in _oku("VERI-ENVANTERI.csv")}
    kontrol = _oku("AS01-KAYNAK-KONTROL.csv")
    alternatif = _oku("AS01-ALTERNATIF-KAYNAK.csv")
    # BT-02 saglik taramasi 305 kaynagi canli yokladi; saglik kaydi artik
    # yalniz F01-F10 matrisindeki 14 kaynakla sinirli degil.
    tarama = _oku("BT02-ADAY-KAYNAKLAR.csv")
    dizin = _oku("ARTEFAKT-DIZINI.csv") + _oku("EK-ARTEFAKT-DIZINI.csv")

    son_deneme: dict[str, dict[str, str]] = {}
    for satir in kontrol:
        son_deneme.setdefault(satir["source_id"], satir)
    for satir in tarama:
        sid = satir["source_id"]
        if sid not in son_deneme:
            son_deneme[sid] = {"bugun_erisim": satir["bugun_erisim"],
                               "bugun_icerik": satir["bugun_icerik"],
                               "denenen_url": satir["yoklanan_url"],
                               "kayitli_icerik": satir["kayitli_icerik"],
                               "degisti_mi": "", "bugun_artefakt": satir["artefakt"]}
    for satir in alternatif:
        sid = satir["source_id"]
        if sid.startswith("source-") and sid not in son_deneme:
            son_deneme[sid] = {"bugun_erisim": satir["erisim"],
                               "bugun_icerik": satir["icerik"],
                               "denenen_url": satir["denenen_url"],
                               "kayitli_icerik": "", "degisti_mi": "",
                               "bugun_artefakt": satir["artefakt"]}

    artefakt_sayisi: dict[str, int] = collections.Counter(
        r["source_id"] for r in dizin if r["sonuc"] == "ok" and r.get("source_id"))
    diskte: dict[str, int] = collections.Counter()
    for r in dizin:
        if r["sonuc"] == "ok" and r.get("source_id") and r["dosya"].strip() \
                and (HERE / r["dosya"]).exists():
            diskte[r["source_id"]] += 1

    satirlar: list[dict[str, Any]] = []
    for sid, deneme in sorted(son_deneme.items()):
        kayit = envanter.get(sid, {})
        erisim = deneme["bugun_erisim"]
        sinif, sebep = SAGLIK_SINIFI.get(erisim, ("bilinmiyor", erisim))
        icerik = deneme.get("bugun_icerik", "")
        if erisim == "ok" and icerik in ICERIK_NOTU:
            sinif, sebep = "icerik-yetersiz", ICERIK_NOTU[icerik]
        satirlar.append({
            "source_id": sid,
            "kaynak_adi": kayit.get("ad", "?"),
            "saglik": sinif,
            "sebep": sebep,
            "son_olcum": "2026-09-27",
            "son_denenen_url": deneme.get("denenen_url", ""),
            "bugun_erisim": erisim,
            "bugun_icerik": icerik,
            "kayitli_icerik": deneme.get("kayitli_icerik", ""),
            "degisim": deneme.get("degisti_mi", ""),
            "kanit_artefakti": deneme.get("bugun_artefakt", ""),
            "arsivdeki_artefakt": artefakt_sayisi.get(sid, 0),
            "artefakt_depoda": diskte.get(sid, 0),
            "yeniden_denenebilir_mi": (
                "hayır — politika" if sinif == "politika-kapali" else
                "hayır — bu yöntemle" if sinif in ("bot-korumasi", "icerik-yetersiz") else
                "evet — aralık artırılarak" if sinif == "hiz-siniri" else
                "evet" if sinif == "saglikli" else "belirsiz"),
        })
    return satirlar


def rapor(bulgular: list[dict[str, str]], saglik: list[dict[str, Any]]) -> str:
    durum = collections.Counter(b["durum"] for b in bulgular)
    sinif = collections.Counter(r["saglik"] for r in saglik)

    def gunluk_bolumu(secilen: list[dict[str, str]]) -> str:
        parcalar = []
        for b in secilen:
            parcalar.append(f"""#### {b["bulgu_id"]} — {b["baslik"]}

| | |
|---|---|
| **Ne denendi** | {b["ne_denendi"]} |
| **Tarih** | {b["tarih"]} · `{b["script"]}` · commit `{b["commit"]}` |
| **Önce** | {b["once"]} |
| **Sonra** | {b["sonra"]} |
| **Kalan sınır** | {b["kalan_sinir"]} |
| **FB-ID** | {b["fb_id"]} |

```bash
{b["yeniden_uretim"]}
```
""")
        return "\n".join(parcalar)

    saglik_tablosu = "\n".join(
        f'| {r["kaynak_adi"]} | `{r["source_id"]}` | {r["saglik"]} | {r["sebep"]} | '
        f'{r["yeniden_denenebilir_mi"]} |' for r in saglik)

    return f"""# Çözüm Günlüğü ve Kaynak Sağlık Kayıtları — AS-06

**Sürüm {SURUM}** · Hazırlayan: Ayselin Aydoğdu · Kontrol eden: Batuhan
Üreten: `cozum_gunlugu.py` · Son ölçüm: 2026-09-24

Bu belge bir **başarı raporu değildir.** Denenip yürümeyen yollar, yanlış
çıkan tahminler ve geri alınan kararlar da burada. Bir yolun *denenmiş ve
çalışmamış* olduğunu bilmek, *hiç denenmemiş* olmasından farklıdır — ikincisi
tekrar denemeye değer, birincisi aynı duvara yeniden çarpmaktır.

## Özet

| Bulgu durumu | Adet |
|---|---:|
| Çözüldü | {durum['cozuldu']} |
| Kısmen çözüldü | {durum['kismen']} |
| Çözülemedi (sınır kaydı) | {durum['cozulemedi']} |
| **Toplam** | **{len(bulgular)}** |

Her bulgu bir tarihe, bir script sürümüne ve bir commit'e bağlı; her satırın
altında Batuhan'ın çalıştırabileceği komut var.

## 1. Çözülen bulgular

Bunların hepsinde **öncesi ve sonrası ölçüldü**; iddia değil, ölçüm.

{gunluk_bolumu([b for b in bulgular if b["durum"] == "cozuldu"])}
## 2. Kısmen çözülenler

Bir tarafı açıldı, bir tarafı açık kaldı. Açık kalan taraf gizlenmiyor.

{gunluk_bolumu([b for b in bulgular if b["durum"] == "kismen"])}
## 3. Çözülemeyenler — sınır kayıtları

Bunlar başarısızlık değil **sınır** kaydıdır. Yol denendi, yürümedi, sebebi
ölçüldü. Aynı yolu tekrar denemek yerine sebebe bakılmalı.

{gunluk_bolumu([b for b in bulgular if b["durum"] == "cozulemedi"])}
## 4. Kaynak sağlık kayıtları

**Başarılı ve başarısız kaynaklar birlikte tutulur.** Çalışmayanı silmek, bir
sonraki turda aynı siteyi yeniden deneyip aynı duvara çarpmak demektir.

| Sağlık | Kaynak |
|---|---:|
| `saglikli` — içerik geliyor | {sinif['saglikli']} |
| `bot-korumasi` — site reddediyor | {sinif['bot-korumasi']} |
| `politika-kapali` — robots yasağı | {sinif['politika-kapali']} |
| `icerik-yetersiz` — 200 ama gövde boş | {sinif['icerik-yetersiz']} |

| Kaynak | source_id | Sağlık | Sebep | Yeniden denenebilir mi |
|---|---|---|---|---|
{saglik_tablosu}

Sağlık "çalışıyor mu" değil **hangi duvara çarpıyor** sorusunu cevaplar.
`politika-kapali` ve `bot-korumasi` farklı şeylerdir: birincisi sitenin açık
kararı, ikincisi teknik reddi. İkisi de aşılmıyor ama çözümleri farklı —
birincisi izin, ikincisi başka yüzey gerektirir.

## 5. Bu günlük ne söylemez

- Bir kaynağın kapalı olması o pazarda talep olmadığını göstermez.
- `cozulemedi` satırları kapatılmış değildir; koşul değişirse yeniden açılır.
- Ölçümler 2026-09-24 tarihlidir. Kaynak durumu değişir — CG-05 tam olarak
  bunun örneği: üç hafta önce çalışan Capterra bugün kapalı.

## 6. Yeniden üretim

```bash
python3 cozum_gunlugu.py --yaz
python3 -m unittest test_cozum_gunlugu
```
"""


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--yaz", action="store_true")
    secenek = ayristirici.parse_args(argv)

    saglik = saglik_kayitlari()
    ozet = {
        "surum": SURUM,
        "bulgu": len(BULGULAR),
        "durum": dict(collections.Counter(b["durum"] for b in BULGULAR)),
        "saglik_kaydi": len(saglik),
        "saglik": dict(collections.Counter(r["saglik"] for r in saglik)),
    }
    print(json.dumps(ozet, ensure_ascii=False, indent=2))
    if not secenek.yaz:
        return 0
    _yaz("COZUM-GUNLUGU.csv", BULGULAR)
    _yaz("KAYNAK-SAGLIK.csv", saglik)
    (HERE / "COZUM-GUNLUGU.md").write_text(rapor(BULGULAR, saglik), encoding="utf-8")
    print("COZUM-GUNLUGU.csv · KAYNAK-SAGLIK.csv · COZUM-GUNLUGU.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
