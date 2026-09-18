# Dönüşüm ve Etiketleme Kuralları — DR-L03

Ham artefakt → normalize belge dönüşümünün tam kuralları. Tekrar çalıştırıldığında
aynı girdiden aynı çıktı üretilir; hiçbir adımda rastgelelik yoktur.

## Neden iki ayrı çıktı

`NORMALIZE-BELGELER.csv` **teknik**tir: başlık, metin, URL, tarih, dil, hash.
`SINIFLANDIRMA.csv` **yorumlayıcı**dır: belge türü, ürün kategorisi, niyet.

Ayrı tutulmalarının karşılığı somut: yarın sınıflandırma kuralı değişirse
1249 belgenin metni yeniden çıkarılmaz, ve yanlış bir sınıflandırma kararı
doğru çıkarılmış metni kirletmez. İkisi `document_id` ile bağlanır.

## 1. Okuma

Ham dosyalar salt okunur açılır. `results/raw/` altındaki hiçbir bayt
değiştirilmez; `body_original_ref` ham dosyayı işaret eder.

## 2. Metin çıkarımı

`script`, `style`, `noscript`, `template`, `svg`, `iframe` etiketlerinin **içeriğiyle birlikte** atılması,
ardından kalan etiketlerin sökülmesi, HTML varlıklarının çözülmesi, kontrol
karakterlerinin silinmesi ve boşluğun tekleştirilmesi.

JSON-LD blokları ayrıca ayrıştırılır; başlık önceliği:
JSON-LD `name`/`headline` → `og:title` → `<title>`. Hiçbiri yoksa başlık boş kalır.

## 3. URL kanonikleştirme

Şema ve alan adı küçültülür, `www.` düşer, varsayılan port atılır, fragment
silinir. Sorgu parametrelerinden **yalnız bilinen takip parametreleri**
(17 adet: `utm_*`, `gclid`, `fbclid` …) ayıklanır.
`?q=`, `?page=` gibi içeriği değiştiren parametreler korunur — silinseydi iki
farklı sayfa aynı belge sayılırdı. `source_url` her hâlükârda değişmeden saklanır.

## 4. Tarih — tahmin yok

Sıra: JSON-LD `datePublished` → `article:published_time` → `<time datetime>`.
Hiçbiri yoksa `published_at` **boş** kalır ve `missing_published_date` +
`unknown_date` bayrakları konur. `collected_at` ayrı bir alandır ve yayın tarihi
yerine geçmez.

Ölçülen: 1249 belgenin 1150 tanesi hiçbir tarih beyan etmiyor.
Tarih okunabilen 99 belgenin kaynağı `tarih_kaynagi` sütununda yazar.

## 5. Dil

Dil yalnızca **düz yazıdan** okunur. Adresler, alan adları ve dosya yolları
metinden çıkarılır; ardından 8 dilin durdurma kelimeleri sayılır.

İki eşik birden aranır: en yüksek payın ≥ 0.25 olması **ve** o dilden
en az 4 **farklı** durdurma kelimesi görülmesi. İkincisi olmasaydı
sitemap'lerdeki `.com` tekrarı yüzünden adres listeleri "Portekizce" etiketlenirdi —
ilk koşuda tam olarak bu oldu. Emin olunamayan her belge `unknown` kalır.

| Dil | Belge |
|---|---:|
| `en` | 663 |
| `unknown` | 505 |
| `tr` | 68 |
| `de` | 7 |
| `fr` | 3 |
| `pt` | 1 |
| `it` | 1 |
| `es` | 1 |

## 6. Tekrar — silme değil, ilişkilendirme

Aynı içerik yeni bağımsız kanıt sayılmaz. Ama **hiçbir satır silinmez**;
`BELGE-ILISKILERI.csv` içinde ilişkilendirilir:

| Yöntem | İlişki | Güven |
|---|---|---|
| Normalize metin hash'i aynı | `duplicate_of` | 1.00 |
| Kanonik URL aynı | `duplicate_of` | 0.90 |
| SimHash Hamming mesafesi ≤ 3 | `possible_duplicate` | 1 − mesafe/64 |

| İlişki | Satır |
|---|---:|
| `duplicate_of` | 146 |
| `possible_duplicate` | 26 |

`possible_duplicate` bir **adaydır**, karar değil: otomatik eleme yapılmaz.
Üçünün de `created_by` değeri `deterministic_rule`'dur.

## 7. Kategori bazında alan çıkarımı

Kaynağın ailesine göre sınıf seçilir (kamu, teknik, urun) ve o
sınıfın alan desenleri aranır. **Bulunmayan alan uydurulmaz**; satır yazılmaz.

| Alan | Bulgu |
|---|---:|
| `fiyat` | 56 |
| `engagement_yorum_sayisi` | 33 |
| `gosterge` | 31 |
| `mevzuat_atfi` | 25 |
| `yil_araligi` | 19 |
| `engagement_yildiz` | 13 |
| `paket_adi` | 8 |
| `surum` | 6 |
| `repo_yolu` | 6 |
| `ozellik_basligi` | 5 |
| `lisans` | 5 |
| `engagement_indirme_sayisi` | 4 |
| `issue_sayisi` | 1 |

`engagement_*` alanlarının her biri şu uyarıyı taşır:
> gözlemlenmiş etkileşim sayısı; ödeme davranışı ya da talep kanıtı DEĞİLDİR

## 8. Sınıflandırma ve ölçüm kanıtı

| Belge türü | Belge |
|---|---:|
| `sitemap` | 392 |
| `ana-sayfa` | 388 |
| `belirsiz` | 297 |
| `fiyatlandirma-sayfasi` | 74 |
| `politika-dosyasi` | 29 |
| `besleme` | 25 |
| `kayit-sayfasi` | 21 |
| `api-yaniti` | 10 |
| `yazi` | 6 |
| `liste-sayfasi` | 5 |
| `arama-sonucu` | 1 |
| `dokumantasyon` | 1 |

Bir belgenin **ölçülebilir kanıt üretip üretmediği** ayrı sorudur. Ana sayfa,
sitemap, arama sonucu, politika dosyası, `belirsiz` ve JS kabuğu olan belgeler
`hayir` işaretlidir:

| Ölçüm kanıtı üretir mi | Belge |
|---|---:|
| `hayir` | 1109 |
| `evet` | 140 |

Bu oran kötü bir sonuç değil, **ölçülmüş** bir sonuçtur: kaynakların çoğundan
ana sayfa çekilmiştir, ana sayfa da fiyat/yorum/talep kanıtı taşımaz.

## 9. Kalite bayrakları

| Bayrak | Belge |
|---|---:|
| `missing_published_date` | 1150 |
| `unknown_date` | 1150 |
| `quote_only` | 392 |
| `short_content` | 101 |
| `duplicate_exact` | 58 |
| `source_policy_limited` | 57 |
| `missing_body` | 12 |

Bunlar kanıt skoru değildir. Bir belge `short_content` olabilir ve yine de
doğru bir fiyat taşıyabilir; bayrak yalnızca ne ölçüldüğünü söyler.

## 10. İşlenemeyenler

`ISLENEMEYEN-BELGELER.csv` iki durumu ayırır: gövdesi hiç saklanmamış kayıtlar
ve dizinde yazıp bu checkout'ta bulunmayan dosyalar. Hiçbiri "işlenmiş" sayılmaz.
