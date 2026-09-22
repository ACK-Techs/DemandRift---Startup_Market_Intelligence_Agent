# Veri Sözlüğü — DR-L03 normalize veri kümesi

Üreten: `normalize_belgeler.py` · normalizasyon sürümü **1.0.0**

Her alan ya diskteki bir artefaktta **yazan** bir şeydir ya da ondan
deterministik bir kuralla hesaplanır. Hiçbir alan tahmin değildir.

## Alanlar

| Alan | Dosya | Anlamı |
|---|---|---|
| `document_id` | NORMALIZE-BELGELER | `source_id` + artefakt hash'inden türeyen kimlik. Aynı dosyayı paylaşan iki kaynak ayrı belge olur; aralarındaki bağ `duplicate_of` ile kurulur. |
| `source_adi` | NORMALIZE-BELGELER | Kaynağın katalogdaki adı. Okunabilirlik içindir; birleştirmede `source_id` kullanılır. |
| `artifact_hash` | NORMALIZE-BELGELER | Diskteki ham dosyanın adı. Her satır buradan geri izlenir. |
| `source_id` | NORMALIZE-BELGELER | Kanonik kaynak kimliği; VERI-ENVANTERI.csv ile ortak. |
| `source_url` | NORMALIZE-BELGELER | Çekilen adres, **olduğu gibi**. Hiçbir koşulda değiştirilmez. |
| `canonical_url` | NORMALIZE-BELGELER | Yalnız bilinen takip parametreleri ayıklanmış hâli. İçerik parametresi silinmez. |
| `access_method` | NORMALIZE-BELGELER | Artefaktın hangi yüzeyden alındığı (root_html, sitemap_xml, rss_feed, common_crawl_warc …). |
| `title` | NORMALIZE-BELGELER | JSON-LD `name`/`headline`, yoksa `og:title`, yoksa `<title>`. Uydurulmaz. |
| `body_normalized` | NORMALIZE-BELGELER | Script/stil/şablon atılmış, boşluğu ve kontrol karakteri temizlenmiş görünür metin (ilk 4000 karakter). |
| `body_uzunlugu` | NORMALIZE-BELGELER | Kırpılmadan önceki tam uzunluk. 4000'den büyükse CSV'deki metin kısaltılmıştır. |
| `body_original_ref` | NORMALIZE-BELGELER | Ham dosyanın yolu. Ham içerik hiçbir zaman üzerine yazılmaz. |
| `language` | NORMALIZE-BELGELER | Düz yazıdan okunan dil kodu; adres listeleri sayılmaz. Emin olunamazsa `unknown`. |
| `language_confidence` | NORMALIZE-BELGELER | 0–1. `unknown` satırlarda da yazılır, böylece eşiğe ne kadar yaklaşıldığı görünür. |
| `published_at` | NORMALIZE-BELGELER | Sayfanın kendi beyan ettiği yayın tarihi. **Yoksa boş bırakılır, tahmin edilmez.** |
| `updated_at` | NORMALIZE-BELGELER | Sayfanın kendi beyan ettiği güncelleme tarihi. |
| `collected_at` | NORMALIZE-BELGELER | Bizim çektiğimiz an. `published_at` yerine **asla** kullanılmaz. |
| `tarih_kaynagi` | NORMALIZE-BELGELER | Tarihin nereden okunduğu (json-ld, meta:…, time[datetime]). Boşsa tarih bulunamamıştır. |
| `content_hash` | NORMALIZE-BELGELER | Ham baytların SHA-256'sı. Bit düzeyinde değişimi yakalar. |
| `normalized_content_hash` | NORMALIZE-BELGELER | Normalize metnin SHA-256'sı. Tam tekrar tespitinin dayanağı. |
| `normalization_version` | NORMALIZE-BELGELER | Bu satırı üreten kural sürümü (1.0.0). Kural değişirse sürüm artar. |
| `source_integrity_flags` | NORMALIZE-BELGELER | Faz4 kalite bayrakları. **Kanıt skoru değildir**, veri bütünlüğü işaretidir. |
| `kaynak_ailesi` | SINIFLANDIRMA | Kaynağın ait olduğu kanıt ailesi (KATEGORI-KAYNAK.csv). |
| `urun_kategorileri` | SINIFLANDIRMA | DR-L02'nin kanonik ürün tipleri. Her aileye bağlı kaynak için geçerli tipler. |
| `belge_turu` | SINIFLANDIRMA | DR-L02 sözlüğündeki 13 belge türünden biri ya da `belirsiz`. |
| `ikincil_belge_turu` | SINIFLANDIRMA | Aynı anda geçerli olabilen ikinci tür(ler). Tek etiket zorlanmaz. |
| `arastirma_niyeti` | SINIFLANDIRMA | Bu kaynağın ailesinin cevaplayabildiği araştırma soruları (KATEGORI-SORU.csv). |
| `icerik_durumu` | SINIFLANDIRMA | DR-L01'in ölçümü: gercek-icerik, js-kabugu, aday-kesif, arsiv, politika … |
| `olcum_kaniti_uretir_mi` | SINIFLANDIRMA | Bu belgeden **ölçülebilir** kanıt çıkar mı. Ana sayfa, sitemap ve JS kabuğu için `hayir`. |
| `belirsizlik` | SINIFLANDIRMA | Kararsız kalınan eksen. Boş olmayan her satır elle incelemeye adaydır. |
| `relation_type` | BELGE-ILISKILERI | `duplicate_of` (kesin) ya da `possible_duplicate` (aday). Faz4 ilişki sözlüğü. |
| `confidence` | BELGE-ILISKILERI | 1.00 tam hash eşleşmesi · 0.90 aynı canonical URL · SimHash'te 1−(mesafe/64). |
| `created_by` | BELGE-ILISKILERI | `deterministic_rule` — ilişkilerin hiçbiri modele sorularak üretilmedi. |
| `alan` | KATEGORI-ALANLARI | Bu belgeden çıkarılabilen alan adı (fiyat, surum, gosterge, engagement_…). |
| `alan_turu` | KATEGORI-ALANLARI | `olcum` karşılaştırılabilir bir değer · `etiket` yalnız sayfada geçen bir ifade. Görev 4'teki ayrımın aynısı. |
| `deger` | KATEGORI-ALANLARI | Sayfada yazan değer, **olduğu gibi**. Birim çevrilmez, yorumlanmaz. |
| `etkilesim` | KATEGORI-ALANLARI | `engagement_*` alanlarında uyarı metni taşır: bu sayı ödeme davranışı değildir. |

## Kalite bayrakları

Adlar `Faz4-Plan.md`'den birebir alınmıştır.

| Bayrak | Ne demek |
|---|---|
| `invalid_payload` | Dosya beklenen biçimde çözümlenemedi |
| `missing_body` | Görünür gövde metni yok |
| `short_content` | Gövde 200 karakterden kısa |
| `missing_published_date` | Sayfa yayın tarihi beyan etmiyor |
| `unknown_date` | Tarih hiçbir alandan okunamadı |
| `source_policy_limited` | Kaynak politikası içeriği sınırlıyor (arşiv/robots) |
| `quote_only` | Yalnız alıntılanabilir; tam metin yeniden yayımlanmaz |
| `duplicate_exact` | Normalize metni daha önce görülmüş bir belgeyle birebir aynı |

## Bu veri kümesinin cevaplayamadığı sorular

- **Talep var mı?** Yok. `engagement_*` alanları gözlemlenmiş sayılardır;
  ödeme davranışı değildir.
- **İçerik güncel mi?** Belgelerin büyük kısmı tarih beyan etmiyor
  (`unknown_date`). `collected_at` yalnızca bizim çekme anımızdır.
- **Bu kaynak bu ürün için iyi mi?** Bu dosya kaynak seçmez; seçim
  `SECIM-ORNEKLERI.csv` işidir.
