# Kalite Raporu — DR-L05

**Sürüm 1.0.0** · Üreten: `denetim.py` · Kategori başına 12 örnek

Bu rapor yeni veri üretmez; üretilmiş olanı sınar. Sözlük, veri seti ve
eşleme tablosu birlikte gözden geçirildi.

## 1. Denetim sonucu

192 kayıt incelendi, **3 bulgu** kaldı.

| Bulgu türü | Adet |
|---|---:|
| `yanlis-etiket` | 2 |
| `konu-disi` | 1 |
| `mukerrer` | 0 |
| `eksik-provenance` | 0 |

| Tür | Kategori | Kaynak | Yol | Önerilen düzeltme |
|---|---|---|---|---|
| yanlis-etiket | egitim | Skillshare | `/hc/en-us` | belge_turu yeniden değerlendirilmeli |
| konu-disi | saglik | CDC | `/about-us/community/` | araştırma kanıtı havuzundan çıkar |
| yanlis-etiket | yeme-icme | Foursquare | `/products/` | belge_turu → liste-sayfasi |

### Düzeltilenler ve nedenleri

İlk koşuda **25 bulgu** çıktı. İkisi düzeltildi, biri denetimin kendi hatasıydı:

| Ne | Kaç | Neden yanlıştı | Nasıl düzeltildi |
|---|---:|---|---|
| Tanınmayan iç sayfa türleri | 21 | Sözlük JSON-LD sinyaline dayanıyordu; JSON-LD yayımlamayan iç sayfalar `belirsiz` kalıyordu | `kategori_sozlugu.py`'ye üç yeni tür ve **yol + gövde birlikte** doğrulayan kurallar eklendi |
| Boş gövdeli belgeler mükerrer sanıldı | 3 | Boş dizenin SHA-256'sı hepsinde aynı (`e3b0c442…`); iki boş sayfa "aynı içerik" değil, ikisi de içerik yokluğu | Denetim kontrolüne `uzunluk > 0` şartı kondu |

Düzeltme **CSV'ye elle yazılmadı**, üreten scripte kondu; etiketleme yeniden
çalıştırıldığında aynı sonucu verir.

Etkisi:

| | Önce | Sonra |
|---|---:|---:|
| `belirsiz` etiketli belge | 297 | **122** |
| Ölçüm kanıtı üreten belge | 145 | **316** |
| Açık bulgu | 25 | **3** |

## 2. Kategori bazında metrikler

Toplam **1291 kayıt**, bunların **329'i** ölçüm kanıtı üretiyor.

| Kategori | Kaynak | Kayıt | Ölçüm kanıtı | Alan % | Belirsiz | Tekrar % | İşlenemeyen |
|---|---:|---:|---:|---:|---:|---:|---:|
| b2b-web-yazilimi | 52 | 140 | 45 | 23.6 | 4 | 5.7 | 64 |
| egitim | 15 | 26 | 1 | 3.8 | 4 | 3.8 | 18 |
| eklenti-entegrasyon | 24 | 94 | 31 | 20.2 | 18 | 8.5 | 35 |
| fintech | 20 | 62 | 14 | 41.9 | 9 | 6.5 | 38 |
| gayrimenkul | 14 | 34 | 4 | 0.0 | 5 | 0.0 | 22 |
| gelistirici-araci | 27 | 66 | 21 | 24.2 | 4 | 4.5 | 53 |
| mobil-uygulama | 8 | 27 | 6 | 11.1 | 4 | 0.0 | 17 |
| ortak | 217 | 549 | 147 | 8.6 | 43 | 3.1 | 359 |
| oyun | 12 | 38 | 13 | 21.1 | 5 | 0.0 | 20 |
| regule-sektor | 20 | 41 | 7 | 34.1 | 11 | 29.3 | 23 |
| saglik | 11 | 22 | 4 | 13.6 | 4 | 4.5 | 15 |
| seyahat | 19 | 34 | 2 | 2.9 | 2 | 2.9 | 26 |
| turkiye-pazari | 16 | 37 | 7 | 0.0 | 3 | 0.0 | 21 |
| yapay-zeka-urunu | 19 | 62 | 17 | 4.8 | 8 | 4.8 | 35 |
| yeme-icme | 11 | 20 | 3 | 15.0 | 3 | 0.0 | 10 |
| yerel-hizmet | 17 | 39 | 7 | 15.4 | 3 | 5.1 | 24 |

*Alan %: en az bir alan çıkarılabilmiş kayıtların oranı. Kategoriler örtüşür —
bir kaynak birden çok kategoriye bağlı olabilir, bu yüzden sütunlar toplanmaz.*

### Dikkat çeken üç değer

- **`gayrimenkul` ve `turkiye-pazari`: %0 alan doluluğu.** Kayıt var, içerik
  var, ama ölçülebilir alan çıkmıyor. Alan desenleri bu kaynakların yapısına
  uymuyor — kaynakların değersiz olduğu anlamına gelmez.
- **`regule-sektor`: %29 tekrar oranı.** En yüksek. Kamu kaynakları aynı
  içeriği birden çok adreste yayımlıyor.
- **`ortak`: 549 kayıt, 43 belirsiz.** En büyük havuz; belirsizlerin yarısından
  fazlası burada.

## 3. Bu veri paketi hangi soruyu cevaplayabiliyor

Her satır gerçek bir kayıttır; `document_id` ile veri setine, `artifact_hash`
ile diskteki dosyaya bağlanır.

| Kategori | Soru | Kaynak | Bulunan veri | Sınır |
|---|---|---|---|---|
| ortak | Mevcut çözümlerden neden memnun değiller? | DataForSEO | `engagement_yorum_sayisi=10 | engagement_yild` | tek belgeye dayanıyor |
| ortak | Rakiplerin gözlemlenen fiyatı ne? | AppSumo | `fiyat=$29` | 3 belge |
| ortak | Kullanıcılar bu problemi nasıl anlatıyor? | Bureau of Labor Stat | `gosterge=rates) Productivity increased  | yi` | tek belgeye dayanıyor |
| b2b-web-yazilimi | Rakip kim? | SourceForge Reviews | `surum=1.0.0` | tek belgeye dayanıyor |
| b2b-web-yazilimi | Mevcut çözümlerden neden memnun değiller? | AppSumo | `engagement_yorum_sayisi=926` | 3 belge |
| b2b-web-yazilimi | Rakiplerin gözlemlenen fiyatı ne? | AppSumo | `fiyat=$29` | 3 belge |
| eklenti-entegrasyon | Mevcut çözümlerden neden memnun değiller? | WooCommerce Marketpl | `engagement_yildiz=5` | 2 belge |
| eklenti-entegrasyon | Rakiplerin gözlemlenen fiyatı ne? | WooCommerce Marketpl | `fiyat=$79` | 3 belge |
| eklenti-entegrasyon | Bu ürün hangi iş akışında kullanılıyor? | Canva Apps Marketpla | `ozellik_basligi=Features` | tek belgeye dayanıyor |
| fintech | Kullanıcılar bu problemi nasıl anlatıyor? | European Central Ban | `gosterge=rate statistics: July 2026 | yil_ar` | tek belgeye dayanıyor |
| fintech | Mevcut çözümlerden neden memnun değiller? | Investing.com | `engagement_yorum_sayisi=1.3M` | tek belgeye dayanıyor |
| fintech | Bu ürün hangi iş akışında kullanılıyor? | Companies House | `mevzuat_atfi=regulation` | tek belgeye dayanıyor |
| oyun | Rakip kim? | itch.io | `surum=26.18.0` | 2 belge |
| oyun | Mevcut çözümlerden neden memnun değiller? | Steam | `engagement_yildiz=34.99` | tek belgeye dayanıyor |

## 4. Geçersiz proxy çıkarımları

Bu verinin **desteklemediği** çıkarımlar. Yapmamak yetmez, hangilerinin
geçersiz olduğu yazılı olmalı:

| Alan | YAPILAMAZ çıkarım | Neden |
|---|---|---|
| `engagement_indirme_sayisi` | talep var | İndirme sayısı ilgi gösterir, ödeme davranışı göstermez. Ücretsiz bir uygulamanın 5M indirmesi bir ödeme kanıtı değildir. |
| `engagement_yorum_sayisi` | memnuniyetsizlik düzeyi | Yorum SAYISI şikâyetin miktarını değil, ürünün kullanım hacmini gösterir. Şikâyet kanıtı yorum METNİNDEDİR ve bu veri kümesinde taranmadı. |
| `engagement_yildiz` | ürün kalitesi | Yıldız ortalaması kaynağın kendi ölçüm yöntemine bağlıdır ve kaynaklar arasında karşılaştırılamaz. |
| `fiyat` | ödeme isteği | Satıcının ilan ettiği fiyat, kullanıcının o fiyatı ödediğini göstermez. stated_wtp_weak_signal ayrı bir niyettir ve kanıtı yoktur. |
| `belge_sayisi` | pazar büyüklüğü | Bir kategoride çok belge olması pazarın büyük olduğunu değil, o kaynakların bize açık olduğunu gösterir. |
| `icerik_yoklugu` | talep yokluğu | Veri bulunamaması toplama yönteminin sınırıdır; pazarda sinyal olmadığı anlamına GELMEZ. |

## 5. Biten kapsam ve kalan iş

| | Adet |
|---|---:|
| Dizin satırı (iki dizin) | 3351 |
| Başarılı çekim | 2108 |
| **İşlenmiş belge** | **1249** |
| İşlenemeyen kayıt | 754 |

| # | İş | Adet | Çözülebilir mi |
|---|---|---:|---|
| 1 | Gövdesi saklanmamış artefaktları yeniden çek | 695 | evet |
| 2 | stated_wtp_weak_signal için metin taraması | 16 | evet |
| 3 | Tek gruba dayanan hücrelere ikinci bağımsız kaynak | 28 | evet |
| 4 | Dizinde yazıp diskte olmayan dosyalar | 58 | evet |
| 5 | Bot koruması dönen kaynaklar | 353 | HAYIR — politika gereği aşılmıyor |
| 6 | robots.txt yasaklı kaynaklar | 91 | HAYIR — bağlayıcı |
| 7 | Uygulama mağazası kayıt sayfaları | 14948 | HAYIR — bu yöntemle değil |
| 8 | Erişilemeyen kaynaklar | 537 | kısmen — adres düzeltmesi gerekir |

İlk dört satır çözülebilir ve toplamı **797 kayıt**. En büyüğü ilk satır:
gövdesi saklanmamış 695 artefakt, tek istekle geri gelir — sitemap tamirinde
bu yöntem %93 başarı verdi.

Beşinci satırdan sonrası bu çalışmanın yöntemiyle **çözülemez** ve bu bir
tercih: bot koruması aşılmıyor, robots.txt bağlayıcı sayılıyor.

## 6. Ham kaynak değişmedi

`results/raw/` altındaki artefaktlar salt okunur açıldı. Her normalize satır
`body_original_ref` ile ham dosyayı işaret eder ve `artifact_hash` ile
doğrulanabilir. Denetim hiçbir bayt yazmadı.
