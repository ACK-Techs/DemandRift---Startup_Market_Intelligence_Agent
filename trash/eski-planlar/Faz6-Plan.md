# Faz 6 — Kanıt Analizi ve İçgörü Üretimi

> Ortak AI Gateway, Cost Ledger, Citation Service, sözleşme, tenant ve evaluation kuralları için `Platform-Temeli.md`; Faz 5 geri besleme ve entegrasyon sırası için `Ust-Yonetim-Ana-Mimari-Plani.md` bağlayıcıdır.

## Amaç

Faz 4'te standardize edilmiş ilk veya gap-driven kanıt setinden; problem sinyallerini, kullanıcı sesini, rakip verisini, fiyat sinyallerini, karşıt kanıtları ve fırsat hipotezlerini izlenebilir biçimde çıkarmak. İlk analizden sonra kapanabilir boşluklar Faz 5 üzerinden araştırılır ve Faz 6 yeni sürüm olarak tekrar çalışır.

Bu faz, AI'ın serbest rapor yazdığı bir katman değildir. Kaynağa bağlı atomik claim'ler ve tekrarı/bağımlılığı kontrol edilmiş evidence cluster'lar üzerinden çalışan bir Evidence Analysis Engine olacaktır.

Faz 6 karar vermez; kararın dayanacağı anlamlandırılmış ve kaynaklı kanıt haritasını üretir.

## Faz sınırı

### Girdi

- Faz 4 normalize veri seti
- Raw artifact ve provenance ilişkileri
- Duplicate, repost ve entity ilişkileri
- Kaynak kalite bayrakları
- Faz 5 varsa ek Deep Research kanıtları ve araştırma sınırlılıkları
- Araştırma planı ve araştırma niyetleri

### Çıktı

- Problem Evidence Map
- Voice of Customer Map
- Competitor Matrix
- Pricing Evidence Map
- Opportunity Hypotheses
- Counter-Evidence Map
- Research Limitations
- Evidence Confidence Profiles
- Market Maturity Profile
- Research Gap Requests
- Primary Validation Gaps

### Faz 6'nın yapmadığı işler

- Build, Modify, Kill veya Investigate More kararı vermek
- Nihai executive summary veya kullanıcı raporu yazmak
- Kaynağa dayanmayan ürün/market iddiası üretmek
- Ham kaynak metnini değiştirmek
- Doğrudan yeni web araştırması yürütmek; yalnızca yapısal `ResearchGapRequest` üretir
- Kullanıcı adına ürün kapsamı veya fiyat modeli seçmek

## Seçilen mimari

1. Deterministik kanıt hazırlığı
2. Semantik aday bulma ve kümelendirme
3. Kaynaklı AI claim extraction ve yorumlama

Bu üç katman ayrıdır. AI, deterministik veri ve kaynak zincirinin yerine geçmez.

Akış:

Faz 4 normalize veri seti
→ Evidence Eligibility Gate
→ Claim Extractor ve Claim Validator
→ Lexical ve Semantic Candidate Generation
→ Cluster Builder ve Contradiction Mapper
→ Competitor, Pricing ve Opportunity analizleri
→ Market Maturity ve Primary Validation Gap analizi
→ Faz 7 karar katmanı

## 1. Deterministik kanıt hazırlığı

AI kullanılmadan yapılan hazırlık işlemleri:

- Exact duplicate kayıtları tek kanıt grubu olarak ele alma
- Repost/sendikasyon ilişkilerini dikkate alma
- Kaynak, tarih, dil, etkileşim ve kalite bayraklarını birleştirme
- Doğrulanmış entity ID'lerini birleştirme
- Kanıtları araştırma niyetine göre ayırma
- Kaynak ailesi ve bağımsızlık gruplarını hesaplama
- Frekans, güncellik ve kaynak çeşitliliği metriklerini üretme

Temel ilke: Bir içeriğin beş farklı sitede görünmesi, beş bağımsız kanıt olduğu anlamına gelmez.

Aynı basın bülteni, aynı Reddit postunun alıntısı veya aynı review'un farklı widget'larda görünmesi tek bağımsız kanıt sayılır.

## Atomik claim extraction

AI'ın ana görevi, kaynak segmentlerinden şemalı ve kaynaklı claim çıkarmaktır.

### Claim veri modeli

- claim_id
- document_id
- source_segment_id
- claim_type
- polarity
- verbatim_quote
- claim_interpretation
- subject_entity
- extraction_confidence
- claim_version

### Claim türleri

- problem_report
- workaround
- feature_request
- competitor_complaint
- competitor_praise
- pricing_signal
- stated_wtp_weak_signal
- observed_payment_behavior
- switching_signal
- market_signal
- counter_evidence

### Polarity

- supports
- challenges
- neutral

### Zorunlu kurallar

- Verbatim quote kaynak segmentinden birebir alınır.
- AI'ın yazdığı claim interpretation alıntı gibi gösterilmez.
- Her claim en az bir source segment ve offset ile doğrulanır.
- Her binding ayrıca `segment_text_hash`, `normalized_content_hash` ve `normalization_version` taşır; yalnızca offset yeterli değildir.
- Kaynakta açıkça olmayan iddia üretilemez.
- No claim veya uncertain geçerli AI çıktılarıdır.
- Extractor güveni, claim'in gerçeği değil, extraction uygunluğu hakkındaki güvendir.
- Claim Validator; segment/offset, şema, kaynak ve duplicate bağını kontrol etmeden claim'i analize aktaramaz.
- `stated_wtp_weak_signal` gerçek ödeme isteği değildir ve karar motorunda pozitif satın alma kanıtı olarak kullanılamaz. `observed_payment_behavior` yalnızca doğrulanabilir işlem, ön sipariş, pilot sözleşme veya güvenilir birincil doğrulama kaydından üretilebilir; kamu yorumundan türetilemez.

### Evidence Eligibility Gate ve maliyet kontrolü

Claim extraction bütün corpus'a körlemesine uygulanmaz. Gate, araştırma sorusu/niyeti başına BM25, lexical relevance, kaynak türü, güncellik, duplicate ailesi, dil/coğrafya kapsamı ve kalite bayraklarıyla adayları sıralar. Her niyet ve kaynak ailesi için çeşitliliği koruyan bütçeli `top-K` seçimi yapılır.

- `K` sabit global sayı değildir; Research Plan bütçesi, corpus hacmi ve coverage ihtiyacına bağlıdır.
- Düşük maliyetli deterministik filtreler LLM'den önce çalışır.
- Claim extraction yüksek hacimli şemalı iş olduğundan uygun küçük/hızlı model kademesine yönlendirilir; karmaşık sentez daha güçlü modele ayrılır.
- Prompt/model cache yalnızca tenant ve veri izolasyonu korunarak kullanılır.
- Elenen belgeler kaybolmaz; eligibility skoru ve eleme nedeni saklanır ve gap oluşursa yeniden değerlendirilebilir.
- Gerçek token, provider, fetch ve işleme maliyetleri ortak Cost Ledger'a yazılır.

## 2. Semantik aday bulma ve kümelendirme

Aynı kullanıcı problemi farklı kelimelerle ifade edilebilir. Bu nedenle yalnızca anahtar kelime analizi yeterli değildir. Ancak doğrudan LLM'e bütün kanıt setini gruplatmak pahalı, tutarsız ve denetlenemezdir.

### Her zaman çalışan AI'sız taban

- TF-IDF
- BM25
- n-gram
- token ve Jaccard benzerliği
- PostgreSQL pg_trgm
- kaynak, dil, ürün tipi ve araştırma niyeti filtreleri

Bu katman hızlı, düşük maliyetli ve açıklanabilirdir.

### Opsiyonel semantik aday üretimi

Çok dilli veya yüksek hacimli veri oluştuğunda, generative AI yerine küçük bir multilingual embedding modeli kullanılabilir.

- Embedding yalnızca muhtemel benzer claim adaylarını bulur.
- Embedding sonucu otomatik cluster veya karar değildir.
- Vektörler PostgreSQL içindeki pgvector uzantısında tutulabilir.
- Ayrı bir vector database veya RAG sistemi zorunlu değildir.
- Local model veya provider adapter kullanılabilir; model/versiyon saklanır.

### Cluster Builder

Kümeleme çok kademeli ve ölçüme bağlıdır:

- Lexical/embedding benzerlik grafiği ve connected components açıklanabilir tabandır.
- HDBSCAN, veri yoğunluğu ve evaluation sonuçları uygun olduğunda aynı adaylar üzerinde gelişmiş yoğunluk tabanlı seçenek olarak kullanılır.
- Sabit sayıda küme zorlanmaz.
- Zayıf/tekil claim'ler outlier olarak kalabilir.
- Kümeleme önce aday üretir; cluster doğrulama ve etiketleme ayrı aşamadır.
- Küme eşikleri ve parametreleri test verisiyle kalibre edilir.

BERTopic ve benzeri topic modelleri deneysel/yardımcı araç olabilir; ancak ürünün kesin problem keşif motoru değildir. Konu modelleri iş açısından anlamsız fakat dilsel olarak benzer gruplar üretebilir.

## Cluster veri modeli

- cluster_id
- cluster_type: problem, competitor, pricing, use_case veya market_signal
- candidate_claim_ids
- representative_claim_ids
- cluster_label
- cluster_description
- supporting_claim_ids
- challenging_claim_ids
- independence_groups
- source_families
- recency_distribution
- quality_flags
- cluster_confidence_profile
- cluster_version

Kurallar:

- Cluster label ve cluster description AI tarafından üretilebilse de kaynaklı claim'lere dayanmalıdır.
- Bir cluster destekleyici ve karşıt evidence'ı ayrı tutar.
- Outlier içerikler zorla cluster içine alınmaz.
- Cluster başlığı kanıtların yerine geçmez; kullanıcı alttaki alıntıları görebilmelidir.

## 3. Kaynaklı AI yorumlama

AI yalnızca şu sınırlı işlerde kullanılır:

- Atomik claim extraction
- Cluster label ve kısa açıklama üretimi
- Kaynaklı competitor/user feedback sınıflandırması
- Fırsat hipotezi taslağı üretimi
- Araştırma sınırlılığını anlaşılır ifadeye dönüştürme

AI şu işlerde kullanılmaz:

- Kanıt olmadan problem var/yok iddiası
- Kaynak uydurma
- Counter-evidence'ı görmezden gelme
- Frekansı pazar büyüklüğü gibi yorumlama
- Nihai karar veya yatırım tavsiyesi
- Alıntıyı yeniden yazıp kullanıcı sözü gibi sunma

Tüm AI çıktıları JSON Schema ve Zod ile doğrulanır; model, prompt ve extraction sürümleri saklanır.

## Kanıt gücü: tek skor değil, kanıt profili

Tek bir 0–100 skor kullanıcıyı yanıltabilir. Her claim cluster için ayrı boyutlar gösterilir:

- independent_source_count
- independent_source_families
- recency_distribution
- cross_platform_coverage
- direct_experience_count
- engagement_context
- duplicate_ratio
- supporting_evidence_count
- challenging_evidence_count
- data_limitations

Bu değerler pazar büyüklüğü veya kesin doğruluk anlamına gelmez. Kanıtın kapsamı, çeşitliliği ve sınırlarını görünür kılar.

### Kanıt profilinin yorum ilkeleri

- Frekans, tek başına talep veya ödeme isteği değildir.
- Etkileşim platformlar arasında doğrudan karşılaştırılamaz.
- Kullanıcı şikâyeti, ödeme yapma isteği anlamına gelmez.
- Tek kaynak ailesinden gelen yüksek sayıda içerik bağımsız doğrulama sayılmaz.
- Kaynağa erişilememesi, kanıtın veya problemin olmadığı anlamına gelmez.
- Yetersiz kanıt insufficient_evidence olarak açıkça gösterilir.

## Karşıt kanıt ve çelişki analizi

Her problem, rakip veya fırsat kümesi aşağıdakilerden birini veya birkaçını taşımalıdır:

- supporting_evidence
- challenging_evidence
- mixed_evidence
- insufficient_evidence

Karşıt kanıt örnekleri:

- Kullanıcı problemi yaşıyor fakat ödeme yapmak istemiyor.
- Rakip bu alanı zaten yeterince güçlü çözüyor.
- Problem yalnızca dar bir segmente ait.
- Kullanıcı workaround'dan memnun.
- Şikâyet eski sürüme ait ve ürün sonradan düzeltmiş.
- Kaynaklar birbiriyle çelişiyor.

Kanıt bulunmadı ile karşıt kanıt var aynı durum değildir.

## Voice of Customer Map

Kullanıcı sesi, kaynaklı claim'lerden üretilir.

Her VoC bulgusu şunları taşır:

- problem_cluster_id
- verbatim_quote
- source_url
- source_type
- published_at
- user_context
- claim_type
- polarity
- independence_group

Kullanıcı cümlesi kaynak metninden birebir alınır. AI yorumu alıntıdan ayrı tutulur. Aynı veya repost edilmiş kullanıcı cümlesi tekrar sayılmaz. Kısa, bağlamsız veya quote-only kayıtlar uygun kalite bayrağıyla gösterilir.

## Competitor Matrix

Rakip bilgisi iki katmana ayrılır:

| Katman | Kaynak | Anlamı |
| --- | --- | --- |
| Rakibin söylediği | Resmî site, pricing, docs | Özellik, konum, fiyat, hedef kitle iddiası |
| Kullanıcının söylediği | Review, forum, sosyal kaynak | Kullanıcı deneyimi, övgü, şikâyet, switching sinyali |

Her rakip için tutulacak alanlar:

- competitor_entity
- target_user_claims
- value_proposition_claims
- feature_claims
- pricing_observations
- integration_claims
- user_praise_claims
- user_complaint_claims
- source_coverage
- data_freshness
- data_limitations

Rakibin pazarlama metni doğrudan güçlü yön sayılmaz. Güç veya zaaf yorumları kullanıcı veya bağımsız kanıtla ayrıca desteklenmelidir.

## Pricing Evidence Map

Fiyat gözlemleri ayrı ve tarihli bir modelde tutulur:

- competitor
- plan_name
- price
- currency
- billing_period
- free_tier
- trial
- usage_limit
- observed_at
- source_url

Farklı para birimleri ve aylık/yıllık paketler körlemesine kıyaslanmaz. Fiyat bilgisi tarih, kaynak ve paket bağlamı olmadan analiz edilmez. Bilinmeyen fiyat alanları tahmin edilmez. Fiyat gözlemi ödeme isteği kanıtı değildir.

Her fiyat kaydı `pricing_extraction_confidence`, `page_render_mode`, `currency_confidence`, `billing_period_confidence` ve kullanıcı düzeltme geçmişi taşır. Dinamik/A-B testli veya eksik fiyat sayfası kesin veri gibi gösterilmez. Kullanıcı düzeltmesi ham kaydı ezmez; yeni doğrulama katmanı üretir.

## Market Maturity Profile

Sistem kanıt bolluğunu otomatik olarak fırsat gücü saymaz. Faz 6; rakip sayısı ve yaşı, fiyatlandırma görünürlüğü, kaynakların zaman dağılımı, kategori dili ve alternatiflerin olgunluğu üzerinden şu profili üretir:

```text
market_maturity: existing | resegmented | emerging | new | unknown
signals
counter_signals
coverage_bias
confidence_profile
```

Yeni veya az konuşulan pazarda düşük kanıt, zayıf problemle aynı şey değildir. Bu profil Faz 7'nin rubric ve sufficiency kurallarını değiştirir.

## Research Gap ve Primary Validation ayrımı

Faz 6 kapanmayan boşlukları iki sınıfa ayırır:

- `secondary_research_gap`: erişilemeyen kaynak, eksik dil/coğrafya, güncellik, rakip sürümü veya karşıt kanıt boşluğu. Faz 5 üzerinden gap-driven araştırmaya dönebilir.
- `primary_validation_gap`: gerçek ödeme davranışı, problem şiddeti, segment uyumu, çözüm kullanılabilirliği veya satın alma süreci. Daha fazla web araştırmasıyla kapatılmaz; Faz 7'ye eylem gereksinimi olarak aktarılır.

## Opportunity Hypotheses

Faz 6 kesin market gap bulundu sonucu vermez. Karar katmanına kaynaklı fırsat hipotezleri aktarır:

- opportunity_hypothesis
- supporting_clusters
- competitor_coverage
- counter_evidence
- confidence_profile
- open_questions

Bir fırsat hipotezinin gösterilebilmesi için mümkün olduğunda şunlar aranır:

- tekrar eden kullanıcı problemi,
- bağımsız kaynak çeşitliliği,
- mevcut alternatiflerde eksik/şikâyet sinyali,
- görünür karşıt kanıt,
- açık kalan doğrulama soruları.

## Kaynak bağımsızlığı

Her claim veya cluster için source_independence_group tutulur.

Bağımsızlık hesabında aşağıdakiler dikkate alınır:

- aynı domain veya yayıncı,
- aynı orijinal içeriğin sendikasyonu,
- alıntı/repost ilişkisi,
- aynı kullanıcı yorumunun farklı yerde görünmesi,
- aynı şirketin birden fazla resmî sayfası,
- ortak kaynak/doküman zinciri.

Kaynak sayısı ve bağımsız kaynak sayısı ayrı metriklerdir.

## Araştırma sınırlılıkları

Faz 6 sonucu güçlendiren veriler kadar araştırma sınırlarını da çıkarır:

- source_unavailable
- policy_limited
- language_coverage_limited
- recency_limited
- single_platform_bias
- duplicate_heavy_corpus
- insufficient_pricing_data
- insufficient_user_voice
- unverified_entity_match

Bu sınırlılıklar Faz 7'nin karar güvenini etkiler; Faz 6 nihai güven veya karar üretmez.

## Teknik yapı

- Evidence Eligibility Gate
- Claim Extractor
- Claim Validator
- Lexical Candidate Generator
- Semantic Candidate Generator
- Cluster Builder
- Contradiction Mapper
- Competitor Matrix Builder
- Pricing Normalizer
- Opportunity Hypothesis Builder
- Research Limitation Generator

### Önerilen teknoloji yaklaşımı

- Ana uygulama/veri katmanı: TypeScript + PostgreSQL
- Lexical analiz: TF-IDF, BM25, n-gram, PostgreSQL pg_trgm
- Semantic aday üretimi: opsiyonel local multilingual embedding modeli veya provider adapter
- Vektör saklama: opsiyonel PostgreSQL pgvector
- Gelişmiş yoğunluk tabanlı kümeleme: izole Python analytics worker + HDBSCAN; policy/evaluation ile gerektiğinde
- AI: şemalı claim extraction, cluster label/açıklama, kaynaklı sınıflandırma
- Şema: Zod + JSON Schema
- Gözlemlenebilirlik: OpenTelemetry
- Sürümleme: model, prompt, extractor, cluster ve analiz sürümü

Python worker gelişmiş analitik/NLP ekosistemi için korunur; bütün run'ların zorunlu geçiş noktası değildir. Ana ürün mimarisi modüler TypeScript monolith olarak kalır; worker sürümlenmiş contracts üzerinden idempotent çalışır.

## Hata, güven ve izlenebilirlik

- Her claim kaynak segmenti, URL ve provenance bilgisine bağlanmalıdır.
- Alıntı ile AI yorumu görsel ve veri modeli düzeyinde ayrılır.
- AI output şeması geçmezse veya segment offset doğrulanmazsa claim kabul edilmez.
- Segment hash/content hash uyuşmazsa binding `stale_binding` olur; otomatik olarak yeni metne taşınmaz.
- Duplicate/repost içerikler bağımsız kanıt sayılmaz.
- Yakın semantik eşleşme cluster için adaydır; kesin eşleşme değildir.
- Cluster parametreleri ve embedding modeli sürümlenir.
- İddia, kanıt, karşıt kanıt ve araştırma sınırı ayrı veri türleri olarak saklanır.
- Ham artefact veya normalleştirilmiş kaynak metni analiz sırasında değiştirilemez.

## Bilinçli olarak kapsam dışı bırakılanlar

- Build, Modify, Kill veya Investigate More kararı
- Nihai kullanıcı raporu veya executive summary yazımı
- Yeni dış kaynak/crawler araştırması
- Kanıtsız ürün, pazar veya fiyat önerisi
- Frekansı pazar büyüklüğü gibi sunmak
- Tek skorla kanıt gücünü temsil etmek
- LLM'i tüm veri setini kontrolsüz gruplayan ana motor yapmak
- Her metni zorla bir cluster'a koymak
- Counter-evidence'ı tek net puanda yok saymak
- Ayrı bir RAG sistemi veya harici vector database'i zorunlu kılmak

## Ölçümler

- Claim extraction kabul/red oranı
- Offset ve kaynak doğrulama başarısı
- Claim başına kaynak/provenance tamlık oranı
- Cluster içi source diversity
- Cluster başına supporting/challenging evidence oranı
- Duplicate kaynakların bağımsız kanıt olarak sayılmasını engelleme oranı
- Outlier oranı
- Insufficient evidence olarak işaretlenen araştırma alanı oranı
- Fiyat/rakip/entity veri tamlık oranı
- Fırsat hipotezlerinin kaynak ve karşıt kanıt kapsamı
- Model/prompt maliyeti ve hata oranı

## Faz 6 kabul kriterleri

- Her analiz claim'i kaynak segmenti, URL ve provenance bilgisine bağlanmalıdır.
- Alıntılar birebir kaynak metinden gelmeli; AI yorumu ayrı tutulmalıdır.
- Exact duplicate ve repost kayıtları bağımsız kanıt olarak tekrar sayılmamalıdır.
- Semantic benzerlik otomatik kesin cluster veya entity merge sonucu doğurmamalıdır.
- Her önemli problem/fırsat cluster'ında destekleyici, karşıt ve eksik kanıt görünür olmalıdır.
- Rakip iddiası ile kullanıcı deneyimi iddiası ayrılmalıdır.
- Fiyat gözlemleri tarih, paket ve kaynak bağlamıyla saklanmalıdır.
- Yetersiz veya erişilemeyen veri kesin negatif sonuca dönüştürülmemelidir.
- Faz 6 herhangi bir nihai yatırım/ürün kararı üretmemelidir.

## Faz 6 çıkışı

Faz 7 karar katmanına aktarılmaya hazır; kaynaklı Problem Evidence Map, Voice of Customer Map, Competitor Matrix, Pricing Evidence Map, Opportunity Hypotheses, Counter-Evidence Map, Research Limitations ve Evidence Confidence Profiles.

Bu çıkış ayrıca Market Maturity Profile, Secondary Research Gap Requests, Primary Validation Gaps, eligibility kararları ve gerçekleşen analiz maliyetini içerir.
