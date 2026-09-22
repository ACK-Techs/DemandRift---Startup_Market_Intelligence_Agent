# Faz 4 — Veri Temizleme, Standartlaştırma ve İlişkilendirme

> Ortak veri sözleşmesi, storage, workflow, Citation Service, tenant ve sürümleme kuralları için `Platform-Temeli.md`; entegrasyon sırası için `Ust-Yonetim-Ana-Mimari-Plani.md` bağlayıcıdır.

## Amaç

Faz 3'ten gelen farklı biçimdeki ham verileri, kaynak bağlamını ve ham içeriği kaybetmeden ortak bir kanıt veri modeline dönüştürmek.

Bu fazın amacı AI ile veri özetlemek veya yorumlamak değildir. Amaç; analiz ve karar katmanlarının temiz, karşılaştırılabilir, izlenebilir ve tekrarları yönetilmiş veri üzerinde çalışmasını sağlamaktır.

> Faz 4, deterministik bir Evidence Normalization Pipeline olacaktır.

## Faz sınırı

```text
Faz 3: Ham kaynakları ve artefact'ları getirir
Faz 4: Temizler, standartlaştırır, ilişkilendirir
Faz 5: Gerektiğinde AI destekli Deep Research yapar
Faz 6: Kanıtları analiz eder
```

### Faz 4'ün yaptığı işler

- farklı kaynak tiplerini ortak veri modeline dönüştürmek,
- URL, tarih, dil, kaynak türü ve etkileşim metadatasını standartlaştırmak,
- ham içeriği koruyarak ayrıştırılmış metin üretmek,
- kesin ve yakın tekrarları ilişkilendirmek,
- kayıt bütünlüğü ve veri kalite bayrakları üretmek,
- kaynak zincirini, sürümleri ve toplama bağlamını korumak.

### Faz 4'ün yapmadığı işler

- kullanıcı yorumlarını problem kümelerine ayırmak,
- sentiment analizi yapmak,
- metni özetlemek, çevirmek veya yeniden yazmak,
- rakip analizi veya market gap çıkarmak,
- kanıt gücü, talep veya iş fırsatı puanı vermek,
- Build / Modify / Kill / Investigate More kararı vermek,
- LLM veya vektör veritabanıyla anlamsal benzerlik analizi yapmak.

## Önceki fazlarla sözleşme

- Faz 3, ham kaynak verisini, metadata'sını ve provenance bilgisini getirir.
- Faz 4, ham veriyi değiştirmez; ondan sürümlenmiş normalize kayıtlar üretir.
- Faz 5 ve Faz 6, analiz için Faz 4'ün ürettiği normalize veri setini kullanır.
- Her normalized kayıt, ait olduğu raw artifact, Research Run, Research Plan ve connector sürümüne geri izlenebilir olmalıdır.

## Seçilen veri modeli

Ham veri ile temizlenmiş veri asla aynı kayıtta tutulmaz.

```text
Raw Artifact
   ↓
Normalized Document
   ↓
Document Segments / Document Relations
```

### Raw Artifact

Faz 3'ten geldiği haliyle değiştirilemez kaynak kaydıdır.

```text
artifact_id
research_run_id
source_id
connector_version
access_method
raw_payload_reference
collected_at
license_or_restriction
artifact_hash
```

### Normalized Document

Farklı platformlardaki sayfa, post, yorum, issue, review veya video verisinin ortak biçimidir.

```text
document_id
artifact_id
source_type
external_id
document_type          page | post | comment | issue | review | video
title
body_original
body_normalized
source_url
canonical_url
parent_document_id
author_reference
published_at
updated_at
collected_at
language
locale
engagement_metadata
source_integrity_flags
content_hash
normalization_version
normalized_content_hash
supersedes_document_id
```

### Document Segments

Kaynak metninin bağlamını koruyarak ayrıştırılmış parçalardır.

```text
segment_id
document_id
segment_type            title | body | quote | code | comment | metadata
text
start_offset
end_offset
sequence
```

Segmentler daha sonra alıntı üretmek için kullanılır. Faz 4 hangi segmentin önemli kanıt olduğuna karar vermez.

Segment kimliği yalnızca değişebilir offset'e dayanmaz. Her segment `segment_text_hash`, `normalization_version`, `normalized_content_hash` ve mümkünse kaynak içi kararlı locator taşır. Böylece yeniden normalizasyonun eski alıntıları sessizce başka metne bağlaması engellenir.

### Document Relations

Aynı içeriğin tekrarlarını, bir yorumun bağlı olduğu postu veya olası aynı varlığı ilişkilendirir.

```text
relation_type
  duplicate_of
  repost_of
  comment_on
  quote_of
  derived_from
  same_entity_candidate
confidence
created_by              deterministic_rule | later_review
```

İlişki kurmak içerik silmek anlamına gelmez. Analiz katmanı aynı kanıtı tekrar tekrar saymamak için bu ilişkileri kullanır.

## Normalizasyon pipeline'ı

```text
1. Şema ve bütünlük kontrolü
2. Encoding / Unicode standardizasyonu
3. İçerik ayrıştırma
4. URL standardizasyonu
5. Tarih ve timezone standardizasyonu
6. Dil ve locale tespiti
7. Exact duplicate tespiti
8. Near-duplicate aday tespiti
9. Kalite ve erişim bayrakları
10. Provenance ve sürüm kaydı
```

### 1. Şema ve bütünlük kontrolü

Aşağıdakiler kontrol edilir:

- kaynak ve connector kimliği var mı,
- kaynak URL'si geçerli mi,
- zorunlu alanlar mevcut mu,
- içerik gövdesi var mı,
- kaynakta dış ID bulunuyor mu,
- tarih kaynak tarafından mı verildi, yoksa bilinmiyor mu.

Geçersiz veri silinmez. `invalid_payload`, `missing_body` veya `unknown_date` gibi bayraklar alır.

### 2. Encoding, Unicode ve metin temizleme

- Girdi UTF-8 olarak işlenir.
- Unicode NFC standardizasyonu uygulanır.
- Kontrol karakterleri ve gereksiz boşluklar temizlenir.
- HTML'den görünür metin çıkarılır.
- Cookie banner, navigation, footer ve tekrarlayan boilerplate ayrıştırılır.
- Kod blokları, alıntılar ve ana metin mümkün olduğunca ayrı segmentlere bölünür.

`body_original` hiçbir zaman değiştirilmez. Temizlenmiş çalışma metni yalnızca `body_normalized` alanına yazılır.

### 3. URL standardizasyonu

- URL'ler WHATWG uyumlu parser ile ayrıştırılır.
- Kaynağın tanımladığı canonical URL varsa değerlendirilir.
- Bilinen tracking parametreleri güvenli biçimde ayrıştırılır.
- Fragment'ler işleme politikasına göre kaldırılabilir.
- İçeriği değiştirebilecek query parametreleri körlemesine silinmez.
- Orijinal kaynak URL'si her zaman korunur.

```text
source_url       Kaynaktan gelen orijinal URL
canonical_url    İçerik kimliği/dedup için normalize edilmiş URL
```

### 4. Tarih ve timezone standardizasyonu

Her kayıtta üç zaman alanı ayrıdır:

```text
published_at   İçeriğin ilk yayınlandığı zaman
updated_at     Kaynakta son güncellendiği zaman
collected_at   Sistemimizin içeriği topladığı zaman
```

- Tarihler UTC saklanır.
- Kaynağın timezone bilgisi ayrıca korunur.
- Tarih bilinmiyorsa tahmin edilmez.
- `published_at` ile `collected_at` asla aynı anlamda kullanılmaz.

### 5. Dil ve locale tespiti

- Dil tespiti temizlenmiş görünür metin üzerinde yapılır.
- Çok kısa metinlerde yanlış kesinlik üretmek yerine `unknown` kullanılır.
- Kaynağın bilinen dili yardımcı metadata olabilir; metin dilinin yerine geçmez.
- Kullanıcının hedef pazarı, kaynak dili ve içerik dili ayrı alanlardır.
- Çeviri Faz 4'te yapılmaz; orijinal kanıt metni korunur.

Önerilen yaklaşım: yerelde çalışan fastText dil tespit modeli veya aynı sözleşmeye uyan başka bir model. Uygulama, minimum metin uzunluğu ve güven eşiğini konfigürasyonla uygular.

## Duplicate ve tekrar yönetimi

Aynı kanıt farklı arama sonuçları, platformlar veya sendikasyon sayfaları aracılığıyla birden fazla kez gelebilir. Faz 4 içeriği silmek yerine tekrar ilişkisinin türünü kaydeder.

### Seviye 1 — Exact duplicate

Aşağıdaki durumlar otomatik eşleştirilebilir:

- aynı `source_id + external_id`,
- aynı canonical URL,
- aynı normalize metin SHA-256 hash'i,
- aynı API kaydının yeniden çekilmesi.

Algoritma: platform native ID, canonical URL ve SHA-256 hash.

### Seviye 2 — Near duplicate

Örnek: aynı yazının şirket sitesi, Medium veya newsletter versiyonu.

Kapsamlı yaklaşım çoklu aday üreticidir; tek algoritmaya kilitlenmez. 64-bit **SimHash** büyük corpus için hızlı fingerprint adayı sağlar.

- Metinden token/shingle üretilir.
- 64-bit fingerprint hesaplanır.
- Hamming distance ile aday benzerlik aranır.
- Dil, içerik türü ve minimum metin uzunluğu ön koşul olarak kullanılır.
- Sonuç otomatik silme değildir; `possible_duplicate` veya `duplicate_of` ilişkisi için aday üretir.
- Eşikler kod içine sabit gömülmez; konfigürasyon ve test verisiyle kalibre edilir.
- Küçük/orta run'larda `pg_trgm` veya TF-IDF cosine adayları da hesaplanır; algoritma seçimi corpus profiline göre yapılır.

### Seviye 3 — Anlamsal benzerlik

Farklı kelimelerle ifade edilmiş aynı problem, near duplicate değildir. Örneğin iki farklı kullanıcının aynı iş akışı sıkıntısını anlatması Faz 6'nın analiz konusudur.

- Faz 4 semantic embedding veya LLM tabanlı birleştirme yapmaz.
- Vektör veritabanı Faz 4'ün gereksinimi değildir.
- Faz 4 yalnızca daha sonraki analiz için güvenli, düşük maliyetli aday ilişkileri hazırlar.

### MinHash'in yeri

Veri hacmi büyüdüğünde SimHash'in yanına veya yerine MinHash + LSH değerlendirilir.

- MinHash, doküman token kümeleri arasındaki Jaccard benzerliğini verimli tahmin eder.
- Büyük corpus'ta yakın kopya adaylarını bulmak için uygundur.
- MinHash + LSH büyük, tekrar oranı yüksek corpus profillerinde etkinleştirilir. Algoritma seçimi corpus büyüklüğü, dil, metin uzunluğu ve ölçülmüş false-positive/false-negative oranına bağlı policy ile yapılır; kapsamdan çıkarılmaz ve her run'da gereksiz yere zorunlu çalıştırılmaz.

## Entity identity resolution

Aynı rakip veya ürün farklı kaynaklarda farklı adla görünebilir. Yanlış birleştirme, sonraki rakip analizini bozar.

Faz 4'te sadece kesin eşleştirmeler otomatik yapılır:

- aynı canonical domain,
- aynı App Store / Google Play uygulama ID'si,
- aynı GitHub `owner/repository`,
- aynı Product Hunt ürün ID'si,
- registry'de tanımlı doğrulanabilir dış ID.

Benzer isimler veya benzer açıklamalar yalnızca `same_entity_candidate` ilişkisi alır. Kesin entity merge, Faz 6'da kanıtla veya kullanıcı onayıyla değerlendirilir.

## Veri kalite bayrakları

Faz 4, bir kaynağın iş değeri hakkında karar vermez. Yalnızca ölçülebilir veri bütünlüğü ve erişim durumlarını işaretler:

```text
missing_body
missing_published_date
deleted_or_unavailable
short_content
quote_only
duplicate_exact
possible_duplicate
out_of_scope_language
source_policy_limited
promotional_content_candidate
machine_generated_candidate
invalid_payload
unknown_date
```

Bu bayraklar kanıt skoru değildir. Faz 6, kaynak türü, güncellik, etkileşim ve bağlamla birlikte bunları değerlendirir.

## Teknik mimari

Faz 3'te belirlenen altyapı korunur:

- TypeScript / Node.js
- PostgreSQL
- S3 uyumlu object storage
- Platform Temeli ortak durable workflow/activity altyapısı
- Zod + JSON Schema
- OpenTelemetry

Faz 4'te eklenecek modüller:

```text
Normalization Worker
Content Extractor
URL Canonicalizer
Date Normalizer
Language Detector
Exact Deduper
Near-Duplicate Candidate Index
Relation Builder
Provenance Validator
```

### Önerilen teknik bileşenler

- URL parsing: Node.js WHATWG `URL`
- HTML parsing: Cheerio + Mozilla Readability
- Exact fingerprint: SHA-256
- Near duplicate: TypeScript içinde BigInt tabanlı 64-bit SimHash
- İleri ölçek: MinHash + LSH
- Dil tespiti: local fastText tabanlı worker
- Metin/başlık aday eşleştirme: PostgreSQL `pg_trgm`
- Sürümleme: `normalization_version`
- Citation binding: segment hash + normalized content hash + normalizasyon sürümü

Bu fazda ayrı vektör veritabanı, RAG, fine-tuned model, multi-agent mimarisi veya LLM servisi kullanılmaz.

## Çalışma ve yeniden işleme modeli

- Normalization Worker, Faz 3'te başarılı veya partial tamamlanan her raw artifact için ayrı job çalıştırır.
- Normalizer sürümü değişirse, raw artifact kaybolmadan tekrar işleme yapılabilir.
- Aynı artifact yeniden işlendiğinde eski normalize çıktı korunur veya sürümlenir.
- Yeniden normalizasyon eski claim/citation bağlarını otomatik olarak yeni offset'lere taşımaz. Citation Validator birebir metni yeniden bağlayabilirse yeni binding üretir; bağlayamazsa `stale_binding` işaretler ve eski Decision Dossier değişmeden korunur.
- Aynı ham artefact'ın farklı normalizasyon sürümleri lineage ilişkisiyle bağlanır.
- Hatalı bir normalizasyon, ham veriyi bozmaz.
- İleride daha iyi parser veya duplicate algoritması geldiğinde geçmiş araştırmalar yeniden normalize edilebilir.

## Hata, güven ve izlenebilirlik

- Raw artifact değiştirilemezdir.
- Her normalized document, artifact ve normalizer sürümüne bağlıdır.
- Geçersiz içerik kullanıcıya “kanıt” gibi gösterilmez.
- Kısa içerikte dil/duplicate gibi düşük güvenli tahminler kesin karar olarak saklanmaz.
- Yakın duplicate tespiti içerik silme sebebi değildir.
- Kaynağın erişilememesi ve içeriğin gerçekten bulunmaması ayrı bayraklarla korunur.
- Toplanan web içeriği güvenilmeyen veri sayılır; uygulama talimatlarını veya workflow'u değiştiremez.
- Eski claim, quote ve dossier yeni normalizasyon nedeniyle sessizce değiştirilemez.

## Bilinçli olarak kapsam dışı bırakılanlar

- AI ile özetleme, yeniden yazma veya çeviri
- Sentiment, konu, problem veya rakip analizi
- LLM/embedding ile semantic deduplication
- Vektör veritabanı ve RAG
- Kanıt gücü veya iş fırsatı puanı
- İçeriğin otomatik silinmesi
- Belirsiz isimlerin otomatik entity merge edilmesi
- Tarih, dil veya kaynak verisi olmayan içerik için tahminde bulunmak
- Faz 4 içinde Build / Modify / Kill / Investigate More sonucu üretmek

## Ölçümler

- Başarılı normalize edilen artifact oranı
- Eksik gövde/tarih/URL oranı
- Exact duplicate oranı
- Near duplicate aday oranı ve daha sonra doğrulanan aday oranı
- `unknown` dil oranı
- Canonical URL üretim başarısı
- Provenance alanlarının tamlık oranı
- Normalizer sürümü sonrası yeniden işleme başarı oranı
- Faz 6'da duplicate nedeniyle elenen kanıt oranı

## Faz 4 kabul kriterleri

- Her raw artifact için ham veri kaybolmadan normalize kayıt üretilebilmelidir.
- Her normalized document, kaynak, artifact, Research Run, plan ve sürüm bilgisine geri bağlanmalıdır.
- Orijinal metin ile normalleştirilmiş metin ayrı saklanmalıdır.
- URL, tarih, dil ve document type standart bir şemada bulunmalıdır; bilinmeyen veriler açıkça işaretlenmelidir.
- Kesin tekrarlar otomatik ilişkilendirilebilmelidir.
- Yakın tekrarlar otomatik silinmeden aday ilişki olarak saklanmalıdır.
- Semantik benzerlik veya iş analizi yapılmamalıdır.
- Normalizer algoritması değiştiğinde geçmiş raw artifact'lar yeniden işlenebilmelidir.

## Faz 4 çıkışı

Faz 5 ve Faz 6'ya aktarılmaya hazır; ham kaynağı korunmuş, standartlaştırılmış, sürümlenmiş, tekrar ilişkileri ve kalite bayrakları taşıyan denetlenebilir araştırma veri seti.
