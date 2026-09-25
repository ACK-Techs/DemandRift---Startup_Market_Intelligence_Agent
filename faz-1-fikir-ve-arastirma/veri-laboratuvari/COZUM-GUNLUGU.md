# Çözüm Günlüğü ve Kaynak Sağlık Kayıtları — AS-06

**Sürüm 1.0.0** · Hazırlayan: Ayselin Aydoğdu · Kontrol eden: Batuhan
Üreten: `cozum_gunlugu.py` · Son ölçüm: 2026-09-24

Bu belge bir **başarı raporu değildir.** Denenip yürümeyen yollar, yanlış
çıkan tahminler ve geri alınan kararlar da burada. Bir yolun *denenmiş ve
çalışmamış* olduğunu bilmek, *hiç denenmemiş* olmasından farklıdır — ikincisi
tekrar denemeye değer, birincisi aynı duvara yeniden çarpmaktır.

## Özet

| Bulgu durumu | Adet |
|---|---:|
| Çözüldü | 5 |
| Kısmen çözüldü | 3 |
| Çözülemedi (sınır kaydı) | 3 |
| **Toplam** | **11** |

Her bulgu bir tarihe, bir script sürümüne ve bir commit'e bağlı; her satırın
altında Batuhan'ın çalıştırabileceği komut var.

## 1. Çözülen bulgular

Bunların hepsinde **öncesi ve sonrası ölçüldü**; iddia değil, ölçüm.

#### CG-01 — robots_state RFC 9309'un altinda kaliyordu

| | |
|---|---|
| **Ne denendi** | api.stackexchange.com/robots.txt — resmi API host'u robots.txt yerine HTTP 400 + JSON hata donduruyor |
| **Tarih** | 2026-09-24 · `bulk_site_access_lab.py` · commit `bc446ef` |
| **Önce** | robots_preflight_blocked — istek hic atilmadi |
| **Sonra** | robots=absent; API calisti, 4980 karakter, 3 gercek sonuc |
| **Kalan sınır** | stackoverflow.com ayri: HTTP 418 ile GECERLI bir 'Disallow: /' donduruyor ve bu yasak korunuyor |
| **FB-ID** | — |

```bash
python3 as01_kaynak_kontrol.py --canli  (F03 satiri)
```

#### CG-02 — iTunes Search API beyan edilen MIME yuzunden reddediliyordu

| | |
|---|---|
| **Ne denendi** | itunes.apple.com/search?term=Booksy&entity=software — gecerli JSON'u text/javascript tipiyle servis ediyor |
| **Tarih** | 2026-09-24 · `bulk_site_access_lab.py` · commit `635ce4b` |
| **Önce** | mime_or_sniff_mismatch — dort terimde de basarisiz |
| **Sonra** | Booksy Biz id=725335996, puan 4.52, 14.888 yorum sayisi alindi |
| **Kalan sınır** | — |
| **FB-ID** | — |

```bash
python3 alternatif_kaynak.py --canli  (F09 App Store satirlari)
```

#### CG-03 — Fiyat deseni para birimi onde gelen bicimi kaciriyordu

| | |
|---|---|
| **Ne denendi** | fresha.com/pricing — fiyatlar 'TRY 240.95 per month' bicimde |
| **Tarih** | 2026-09-24 · `normalize_belgeler.py` · commit `302497e` |
| **Önce** | fiyat alani bos; 55 fiyat isareti olan sayfadan 0 fiyat cikti |
| **Sonra** | TRY 240.95 yakalandi; TL, EUR, GBP onek bicimleri de |
| **Kalan sınır** | — |
| **FB-ID** | — |

```bash
python3 -c "import normalize_belgeler as n; print(n.alan_cikar('urun','TRY 240.95 per month',''))"
```

#### CG-08 — Apple musteri yorumu RSS ucu bos donuyor

| | |
|---|---|
| **Ne denendi** | itunes.apple.com/us/rss/customerreviews/page=1/id=725335996/json — Booksy Biz ve Fresha for business icin denendi |
| **Tarih** | 2026-09-24 · `alternatif_kaynak.py` · commit `635ce4b` |
| **Önce** | belgelenmis uc; yorum METNI icin ilk tercih |
| **Sonra** | gecerli JSON donuyor ama 'entry' dizisi bos — uc fiilen emekli |
| **Kalan sınır** | Calisan yol uygulama SAYFASININ kendisi cikti: apps.apple.com/.../id725335996 icinde gercek yorum metni var. |
| **FB-ID** | — |

```bash
python3 alternatif_kaynak.py --canli  (F09 App Store satiri)
```

#### CG-09 — HTTP 200 + gercek icerik, ilgisiz sonuc

| | |
|---|---|
| **Ne denendi** | sourceforge.net/directory/?q=salon+scheduling+software |
| **Tarih** | 2026-09-24 · `alternatif_kaynak.py` · commit `302497e` |
| **Önce** | aday listesinde 'calisiyor' sayiliyordu |
| **Sonra** | 200 OK, 19 bin karakter; icerik Kubernetes orkestrasyon ve kripto fiyatlama — nisle ilgisi yok |
| **Kalan sınır** | Her adaya ucuncu bir test eklendi: erisim ve icerik yetmiyor, nisin kendi kelimeleri govdede aranmali. Anahtar kelime eslesmesi ilgililik degildir. |
| **FB-ID** | — |

```bash
python3 -m unittest test_alternatif_kaynak.IlgililikTests
```

## 2. Kısmen çözülenler

Bir tarafı açıldı, bir tarafı açık kaldı. Açık kalan taraf gizlenmiyor.

#### CG-06 — Google Play HTTP 200 donuyor ama govde bos

| | |
|---|---|
| **Ne denendi** | play.google.com/store/apps/details?id=... — robots izinli, istek basarili |
| **Tarih** | 2026-09-24 · `as01_kaynak_kontrol.py` · commit `bc446ef` |
| **Önce** | erisim listesinde 'ok' gorunuyordu |
| **Sonra** | 200 OK, 0 karakter gorunur metin; js-kabugu olarak ayrildi |
| **Kalan sınır** | Sayfa tamamen tarayicida uretiliyor. Ayni uygulamalar Apple App Store'da aliniyor (21-28 bin karakter, puan ve fiyatla); Google Play tarafi acik kaliyor. |
| **FB-ID** | AS01-0097 |

```bash
python3 as01_kaynak_kontrol.py --canli  (F01/F10 Google Play)
```

#### CG-10 — F02 icin kullanici sikayeti kaynagi bulunamadi

| | |
|---|---|
| **Ne denendi** | Filestage/Ziflow (satici sitesi), SourceForge (ilgisiz), GetApp (challenge), Hacker News API (0 sonuc), iTunes Search (mobil uygulama yok) |
| **Tarih** | 2026-09-24 · `alternatif_kaynak.py` · commit `635ce4b` |
| **Önce** | F02'nin uc kaynagi da kapaliydi |
| **Sonra** | fiyat/urun icin Filestage ve Ziflow bulundu; sikayet icin hicbiri |
| **Kalan sınır** | Satici kendi hakkindaki sikayeti yayimlamaz. F02 fiyat ve urun iddiasi icin arastirilabilir, memnuniyetsizlik icin arastirilamaz. Filestage ve Ziflow katalogda YOK — registry karari Batuhan'da. |
| **FB-ID** | AS01-0134, AS01-0135 |

```bash
python3 alternatif_kaynak.py --canli  (F02 satirlari)
```

#### CG-11 — Ham arsiv depo disinda kaldi; iddialar dogrulanamiyordu

| | |
|---|---|
| **Ne denendi** | Uc fazli yapiya tasinma sonrasi artefakt konumu sayildi |
| **Tarih** | 2026-09-24 · `as01_kaynak_kontrol.py` · commit `474a09c` |
| **Önce** | 1249 normalize belgenin 21'inin ham dosyasi depoda (%1.7) |
| **Sonra** | sayi cikarilan 154 dosya depoya alindi; KATEGORI-ALANLARI.csv'deki 164 alanin 164'u dogrulanabilir |
| **Kalan sınır** | SourceFitMatrix ornek kayitlari 101/346'da; tamamlamak ~75 MB daha demek, karar Batuhan'da. Kalan 1070 belge ana sayfa ve sitemap — dogrulanacak iddia tasimiyorlar. |
| **FB-ID** | — |

```bash
python3 -m unittest test_as01_kaynak_kontrol.CikarilanSayininKaynagiDepodaTests
```

## 3. Çözülemeyenler — sınır kayıtları

Bunlar başarısızlık değil **sınır** kaydıdır. Yol denendi, yürümedi, sebebi
ölçüldü. Aynı yolu tekrar denemek yerine sebebe bakılmalı.

#### CG-04 — Reddit kazimayla alinamiyor

| | |
|---|---|
| **Ne denendi** | reddit.com/robots.txt bugun yeniden cekildi; /r/*/.rss, /r/*/new.json, /dev/api dahil yedi yol robots'a soruldu |
| **Tarih** | 2026-09-24 · `as01_kaynak_kontrol.py` · commit `bc446ef` |
| **Önce** | kayitta 'kismi/dosya-yok'; sebep belirsizdi |
| **Sonra** | sebep kesin: 'User-agent: * / Disallow: /' — yedi yolun yedisi yasak |
| **Kalan sınır** | Politika engeli. Reddit'in kendi robots.txt'i izinli yolu gosteriyor: Public Content Policy ve r/reddit4researchers. Hesap ve sartname onayi gerekir; karar Cağlar'da. 10 fikrin 7'sini etkiliyor. |
| **FB-ID** | AS01-0075 |

```bash
python3 as01_kaynak_kontrol.py --canli  (Reddit satirlari)
```

#### CG-05 — Capterra kayitla celisiyor: kayit calisiyor diyor, bugun kapali

| | |
|---|---|
| **Ne denendi** | capterra.com/proofing-software/ ve /salon-software/ — robots izin veriyor, istek bot korumasina takiliyor |
| **Tarih** | 2026-09-24 · `as01_kaynak_kontrol.py` · commit `bc446ef` |
| **Önce** | 2 Eylul kaydi: erisim=cekildi, icerik=gercek-icerik |
| **Sonra** | bugun challenge; F02, F09 ve F10'u etkiliyor |
| **Kalan sınır** | Bot korumasi asilmiyor. Arsiv (Common Crawl) kopyasi var ama canli degil ve 'arsiv' etiketiyle tasinmali. |
| **FB-ID** | AS01-0135 |

```bash
python3 as01_kaynak_kontrol.py --canli  (F02/F09 Capterra)
```

#### CG-07 — Uygulama magazasi kayit sayfalari bos geliyor

| | |
|---|---|
| **Ne denendi** | galaxystore.samsung.com/detail/... ve apps.microsoft.com/detail/... — sitemap'lerden 14.948 kayit adresi cikarildi, 6 tanesi test edildi |
| **Tarih** | 2026-09-18 · `ic_sayfa_gecisi.py` · commit `298f5c0` |
| **Önce** | 14.948 aday adres; mobil-uygulama kategorisi 1/6 hucrede doluydu |
| **Sonra** | Microsoft bos govde, Samsung 38 karakter; kategori acik kaldi |
| **Kalan sınır** | Istemci tarafinda uretilen magaza sayfalari bu hatla alinamiyor. Adres sayisi coklugu ise yaramiyor. |
| **FB-ID** | — |

```bash
AS01-ALTERNATIF-KAYNAK.csv · kayit sayfasi testi
```

## 4. Kaynak sağlık kayıtları

**Başarılı ve başarısız kaynaklar birlikte tutulur.** Çalışmayanı silmek, bir
sonraki turda aynı siteyi yeniden deneyip aynı duvara çarpmak demektir.

| Sağlık | Kaynak |
|---|---:|
| `saglikli` — içerik geliyor | 11 |
| `bot-korumasi` — site reddediyor | 5 |
| `politika-kapali` — robots yasağı | 2 |
| `icerik-yetersiz` — 200 ama gövde boş | 1 |

| Kaynak | source_id | Sağlık | Sebep | Yeniden denenebilir mi |
|---|---|---|---|---|
| GitHub | `source-0017` | saglikli | içerik geliyor | evet |
| Hacker News | `source-0022` | saglikli | içerik geliyor | evet |
| Stack Overflow | `source-0023` | saglikli | içerik geliyor | evet |
| Reddit | `source-0075` | politika-kapali | robots.txt yolu yasaklıyor — aşılmaz | hayır — politika |
| Apple App Store | `source-0096` | saglikli | içerik geliyor | evet |
| Google Play Store | `source-0097` | icerik-yetersiz | HTTP 200 ama görünür metin yok — sayfa tarayıcıda üretiliyor | hayır — bu yöntemle |
| Shopify App Store | `source-0114` | saglikli | içerik geliyor | evet |
| G2 | `source-0134` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| Capterra | `source-0135` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| GetApp | `source-0136` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| SourceForge Reviews | `source-0141` | saglikli | içerik geliyor | evet |
| SoftwareSuggest | `source-0146` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| Trustpilot | `source-0148` | politika-kapali | robots.txt yolu yasaklıyor — aşılmaz | hayır — politika |
| Fresha | `source-0317` | saglikli | içerik geliyor | evet |
| Booksy | `source-0318` | saglikli | içerik geliyor | evet |
| Armut | `source-0319` | saglikli | içerik geliyor | evet |
| Capterra Education Software | `source-0466` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| Steam | `source-0518` | saglikli | içerik geliyor | evet |
| Hugging Face | `source-0534` | saglikli | içerik geliyor | evet |

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
