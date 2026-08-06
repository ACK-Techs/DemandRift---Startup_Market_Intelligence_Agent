# Platform Temeli — Faz 1–7 Ortak Teknik Mimari

## Belgenin amacı

Bu belge kullanıcıya görünen yeni bir faz tanımlamaz. Faz 1–7'nin aynı veri dili, güvenlik sınırı, workflow modeli, maliyet kontrolü ve denetim izi üzerinde çalışmasını sağlayan yatay platform mimarisini tanımlar.

Platform Temeli'nin tamamı ayrı bir ön proje olarak bitirilip sonra fazlara geçilmez. Her ortak yetenek ilk tüketen fazla birlikte geliştirilir; ancak sahibi, sözleşmesi ve sınırı baştan burada tanımlıdır. Böylece fazlar kendi kuyruklarını, policy yapılarını veya veri modellerini tekrar kurmaz.

## Bağlayıcı mimari kararlar

1. Ana uygulama **TypeScript tabanlı modüler monolith** olacaktır.
2. Web ve API katmanı **Next.js + Node.js** üzerinde çalışacaktır.
3. İşlemsel ve analitik ana veri deposu **PostgreSQL** olacaktır.
4. Ham içerik ve büyük immutable payload'lar **S3 uyumlu object storage** içinde tutulacaktır.
5. Uzun süren Faz 2–7 akışları, retry, cancellation, resume, timer ve human-in-the-loop gereksinimleri nedeniyle ortak bir **durable workflow engine** üzerinden yürütülecektir. Tam kapsamlı hedef mimari için tercih **Temporal**'dır; adapter sınırı korunur.
6. Connector çalıştırma, AI çağrısı, normalizasyon ve analitik işler idempotent workflow activity'leridir. Fazlar kendi job sistemlerini kurmaz.
7. Redis zorunlu kuyruk değildir. Yalnızca dağıtık rate limit, kısa ömürlü cache veya yüksek hacimli koordinasyon gerçekten gerektirirse kullanılır.
8. Mikroservis zorunlu değildir. Browser ve Python analytics worker güvenlik/runtime izolasyonu için ayrı worker process olabilir; iş alanı yine modüler monolith sözleşmelerine bağlıdır.
9. Ortak veri sözleşmeleri monorepo içindeki `packages/contracts` altında Zod + JSON Schema ile sürümlenir. Başlangıçta harici schema-registry servisi kurulmaz.
10. Bütün dış HTTP erişimi tek **Egress Gateway** ve Source Policy üzerinden geçer.
11. AI hiçbir zaman doğrudan credential, connector veya sınırsız internete erişmez.
12. Kamuya açık ve lisansı uygun ham artefact global cache olabilir; kullanıcıya özel yorum, claim, analiz ve karar tenant-scoped kalır.
13. İkincil internet kanıtı ile birincil kullanıcı/ödeme doğrulaması farklı veri sınıflarıdır.
14. Faz 8 bu belgede tasarlanmaz; yalnızca ona verilecek sürümlü Decision Dossier sözleşmesi korunur.

## Sistem bağlamı

```text
Client / Web UI
      |
Application API / Auth / Project Scope
      |
Durable Workflow Engine
      |
      +-- Phase modules (1, 2, 4, 5 policy, 6, 7)
      +-- Evidence Acquisition / Connector Runtime (Phase 3)
      +-- Isolated Browser Worker
      +-- Optional Python Analytics Worker
      +-- AI Gateway
      |
PostgreSQL ---- Object Storage ---- Observability Backend
```

## Modül sınırları

```text
apps/web                    UI ve HTTP/BFF
apps/worker                 workflow worker ve TypeScript activities
apps/browser-worker         izole Playwright işleri
apps/analytics-worker       Python embedding/HDBSCAN/ileri NLP işleri

packages/contracts          kanonik Zod/JSON Schema ve event/activity payload'ları
packages/platform-auth      kullanıcı, tenant, proje ve yetki
packages/platform-workflow  workflow tanımları, idempotency ve state mapping
packages/platform-policy    Source Registry, Egress ve data-use policy
packages/platform-cost      bütçe rezervasyonu, usage ve Cost Ledger
packages/platform-ai        model routing, prompt registry, şemalı çıktı
packages/platform-citation  quote binding ve citation doğrulama
packages/platform-storage   PostgreSQL/object storage repository sınırları
packages/platform-observe   log, trace, metric ve audit
packages/phase-1-intake
packages/phase-2-planning
packages/phase-3-acquisition
packages/phase-4-normalization
packages/phase-5-gap-policy
packages/phase-6-analysis
packages/phase-7-decision
packages/connectors/*
```

Faz modülleri birbirinin tablolarına doğrudan yazmaz. Sürüm sınırlı application service/repository ve contracts kullanır. Aynı deploy içinde olmak sınırların kaldırılması anlamına gelmez.

## Kanonik kimlikler ve bağlam

Her kayıt uygun olduğu ölçüde şu bağlamı taşır:

```text
tenant_id
user_id
project_id
idea_id
research_run_id
workflow_id
trace_id
schema_version
created_at
```

Global cache kayıtlarında `tenant_id` bulunmayabilir; ancak erişim ilişkisi ve kullanım kaydı tenant-scoped olmak zorundadır.

## Ana veri varlıkları

### Tenant-scoped

- User, Tenant, Membership, Project
- IdeaInput, IdeaBriefVersion, FieldOrigin, Assumption
- ResearchPlanVersion, QueryPlan, BudgetContract
- ResearchRun, RunArtifact, QueryExecution, ConnectorExecution
- NormalizationRun görünürlüğü ve tenant-private Document
- Claim, Cluster, Evidence Map, Research Gap
- AnalysisRun, DecisionDossier, DecisionFeedback
- AI call, usage, budget reservation ve audit kayıtlarının kullanıcı bağlamı

### Global veya paylaşılabilir cache

- Lisansı izin veren Public RawArtifact
- Aynı public artefact'ın NormalizedDocument sürümleri
- Connector health ve kamu kaynağı metadata cache'i

### Kesinlikle tenant-private

- Kullanıcı yüklemeleri
- Kapalı topluluk veya yetkili hesap verisi
- Kullanıcı görüşmeleri, pilot ve ödeme/ön sipariş kayıtları
- Prompt'a giren özel iş verisi
- Claim yorumları, fırsat hipotezleri ve kararlar

## Ortak veri sözleşmesi ve sürümleme

Her faz çıktısı immutable bir sürüm üretir; sonraki faz önceki kaydı değiştirmez.

```text
IdeaBrief vN
  -> ResearchPlan vN
  -> ResearchRun snapshot
  -> RawArtifact + Provenance
  -> NormalizedDocument vN
  -> AnalysisRun vN
  -> DecisionDossier vN
```

Kurallar:

- Her payload `schema_version` taşır.
- Backward-compatible değişiklik minor, kırıcı değişiklik major sürüm oluşturur.
- Consumer-driven contract ve snapshot testleri CI'da çalışır.
- Eski workflow yeni şemayla sessizce devam etmez; uygun migrator/adapter seçilir.
- Prompt, model, connector, policy, normalizer, extractor, clustering ve decision-policy sürümleri dossier'e kadar taşınır.
- Source Registry tek kanonik şemaya sahiptir; Faz 2 planlar, Faz 3 yürütür.

## Source Registry kanonik modeli

```text
source_id
source_family
connector_id
connector_version
eligible_product_types
supported_search_intents
supported_languages
market_coverage
access_method
credential_class
cost_tier
rate_limit_policy
concurrency_policy
robots_policy
terms_policy
license_policy
retention_policy
pii_policy
browser_policy
allowed_content_types
max_response_bytes
enabled_status
policy_version
```

Registry policy-as-code olarak sürümlenir. Runtime ayarları ve acil kapatma anahtarı veritabanından yönetilebilir; değişiklik audit log'a yazılır.

## Durable workflow modeli

### Ana workflow

```text
IdeaResearchWorkflow
  1. Intake / clarification wait
  2. Research plan generation
  3. Plan-driven acquisition
  4. Normalization
  5. Analysis
  6. Gap policy
     6a. gap-driven acquisition
     6b. normalization revision
     6c. analysis revision
  7. Decision
  8. User-visible completion
```

### Zorunlu davranışlar

- Workflow ID: `tenant/project/research-run` üzerinden deterministik ve benzersiz.
- Activity idempotency key: operasyon türü + run + input hash + sürüm.
- Retry yalnızca transient hata sınıflarında; policy, validation ve authentication hataları retry edilmez.
- Exponential backoff + jitter, connector özelinde üst sınır.
- Timeout'lar: schedule-to-start, start-to-close ve heartbeat ayrı tanımlanır.
- Cancellation bütün child workflow ve maliyet rezervasyonlarına yayılır.
- Resume aynı immutable snapshot'tan devam eder.
- Human-in-the-loop kullanıcı cevabı/Deep Research onayı workflow signal ile alınır.
- Aynı run için duplicate execution workflow ID ile engellenir.
- Activity sonucu DB'ye yazıldıktan sonra idempotent read ile yeniden kullanılabilir.

Transactional outbox varsayılan P0 değildir. Domain event'in ayrı bir broker'a kesin teslimi gerektiğinde eklenir. Workflow engine koordinasyonun ana kaynağıdır; Postgres kayıtları iş verisinin kaynağıdır.

## Durum modeli

```text
draft
awaiting_user
planned
acquiring
normalizing
analyzing
gap_review
deep_research
deciding
completed
partial
cancelled
failed
```

Alt işler şu sonuçları ayırır:

```text
succeeded | no_results | source_unavailable | rate_limited |
blocked_by_policy | invalid_output | partial | cancelled | failed
```

`no_results` hiçbir zaman `source_unavailable` veya `blocked_by_policy` ile birleştirilmez.

## Egress Gateway ve crawler güvenliği

Bütün connector, fetch ve browser trafiği ortak güvenlik katmanından geçer:

- Yalnızca `http` ve `https` şemaları.
- Kullanıcı adı/parola içeren URL reddi.
- Port allowlist'i.
- DNS çözümleme öncesi hostname doğrulama.
- Çözülen her IP için private, loopback, link-local, multicast, reserved ve cloud metadata ağlarının engellenmesi.
- Her redirect adımında hostname ve IP'nin yeniden doğrulanması.
- DNS rebinding'e karşı bağlantı hedefinin doğrulanması.
- Maksimum redirect, response byte, süre ve sıkıştırma oranı sınırı.
- MIME sniffing ve izinli content-type kontrolü.
- Dosya protokolü, localhost, metadata endpoint ve iç servis isimlerinin reddi.
- Browser worker'ın izole network namespace/container, düşük yetki, indirme kapalı ve kalıcı profil olmadan çalışması.
- Kaynak içeriğinin hiçbir zaman sistem prompt'u, tool izni veya politika girdisi sayılmaması.
- Credential'ların secret manager'dan activity runtime'a kısa ömürlü verilmesi; AI'a aktarılmaması.

## AI Gateway

AI kullanımı tek adapter/gateway üzerinden yürütülür:

```text
task_type
model_policy
provider_candidates
input_schema
output_schema
prompt_version
token_budget
timeout
retry_policy
cache_policy
data_classification
```

Model yönlendirme görev temellidir:

- Intake ve query planning: şemalı, bağlam güçlü model.
- Yüksek hacimli claim extraction: küçük/hızlı ve doğruluk testinden geçmiş model.
- Zor cluster yorumlama ve decision synthesis: daha güçlü model.
- Deterministik yapılabilen normalizasyon, duplicate, gate ve policy işleri AI'a verilmez.

Her çağrıda input/output hash, token, latency, provider/model, prompt sürümü, schema sonucu, hata sınıfı ve tahmini/gerçek maliyet saklanır. Kullanıcı verisi farklı tenant için prompt cache anahtarı olamaz.

## Bütçe ve Cost Ledger

Maliyet kontrolü ürün kapsamını küçültmek için değil, her tam araştırmanın öngörülebilir ve denetlenebilir olmasını sağlamak içindir.

### Maliyet kategorileri

- Search API
- Platform API
- HTTP fetch ve proxy
- Browser render
- Lisanslı veri
- LLM input/output/cache
- Embedding
- Analytics worker compute
- Object storage ve egress

### İşlem modeli

1. Faz 2 `estimated_cost_envelope` üretir.
2. Kullanıcı/plan için hard ve soft bütçe sözleşmesi oluşturulur.
3. Dış çağrı öncesi atomik maliyet rezervasyonu yapılır.
4. Çağrı sonunda gerçekleşen kullanım ledger'a yazılır ve fark serbest bırakılır.
5. Hard limit aşılmaz; soft limit uyarı veya policy kararı üretir.
6. Standard ve Deep Research aynı ledger'ı kullanır.
7. Claim extraction öncesi Eligibility Gate, bilgi çeşitliliğini koruyan bütçeli top-K seçimi yapar.

Cost Ledger fiyatlandırma, kapasite ve model kalibrasyonu için ana ölçüm kaynağıdır.

## Citation Service

Citation doğruluğu ayrı dağıtılmış servis olmak zorunda değildir; fakat tek sorumlu platform modülüdür.

Her citation binding şunları taşır:

```text
citation_id
claim_id
artifact_id
document_id
segment_id
verbatim_quote
start_offset
end_offset
segment_text_hash
normalized_content_hash
normalization_version
source_url
collected_at
binding_status: valid | stale_binding | source_removed | invalid
```

Kurallar:

- Quote normalize segmentte birebir bulunmalıdır.
- Offset tek başına yeterli değildir; hash ve sürüm eşleşmelidir.
- Yeniden normalizasyon eski binding'i sessizce taşımaz.
- Kaynak değiştiğinde eski dossier tarihsel snapshot olarak kalır.
- Kullanıcıya gösterilen bütün önemli iddialar Claim ID ve citation ile doğrulanır.
- Citation Validator başarısızsa AI sentezi yayımlanmaz.

## Veri yönetişimi

- Source policy lisans, saklama, alıntı ve yeniden kullanım hakkını tanımlar.
- Veri minimizasyonu uygulanır; araştırma için gereksiz kişisel veri toplanmaz.
- PII detection/redaction kaynağa ve kullanım amacına göre çalışır.
- Retention connector ve veri sınıfı bazındadır; global tek süre kullanılmaz.
- Kullanıcı silme isteği tenant-private veriyi ve erişim ilişkilerini kapsar.
- Global public cache'in silinmesi kaynak lisansı, hukuki yükümlülük ve başka tenant kullanımından bağımsız policy ile değerlendirilir.
- Tombstone ve audit kaydı içerik taşımadan silme işleminin gerçekleştiğini kanıtlayabilir.
- Kullanıcıya açık data-use özeti: hangi kaynak, hangi erişim yöntemi, ne zaman ve hangi kısıtla kullanıldı.

## Tenant güvenliği ve yetkilendirme

- Her API ve repository işlemi doğrulanmış `TenantContext` ister.
- PostgreSQL Row Level Security savunma katmanı olarak kullanılır; application authorization'ın yerine geçmez.
- Object storage anahtarları tenant/private veya global/public-cache namespace'ine ayrılır.
- Signed URL kısa ömürlü ve amaca özeldir.
- Role modeli: owner, member, viewer, service.
- Cross-tenant contract, integration ve güvenlik testleri zorunludur.
- Loglarda secret, tam prompt veya PII varsayılan olarak redakte edilir.

## Gözlemlenebilirlik

OpenTelemetry tabanlı ortak telemetry:

- Trace: kullanıcı aksiyonu -> workflow -> activity -> connector/AI -> DB/object storage.
- Metric: latency, error, retry, rate limit, coverage, cost, token, queue lag, browser failure, schema failure.
- Structured log: trace_id, tenant_id hash, project_id, run_id, phase, component, version ve error_class.
- Audit log: kullanıcı onayı, policy değişikliği, connector erişimi, model/prompt değişimi, karar ve düzeltme.

Dashboard/SLO aileleri:

- Workflow completion ve partial oranı
- Connector health ve erişilebilirlik
- Citation validity
- AI schema validity ve groundedness
- Faz başına maliyet ve süre
- Evidence coverage ve independence
- Decision outcome/override/feedback

## Evaluation ve kalibrasyon

Tek bir genel “rapor iyi mi?” testi yeterli değildir. Ayrı evaluation setleri bulunur:

1. Intake extraction doğruluğu ve field-origin hataları.
2. Clarification soru faydası.
3. Query relevance, çeşitlilik ve source-fit.
4. Connector fetch/provenance doğruluğu.
5. Normalizasyon kaybı ve boilerplate oranı.
6. Exact/near duplicate false merge ve false split.
7. Citation quote/binding doğruluğu.
8. Claim extraction precision, recall ve unsupported claim oranı.
9. Cluster coherence, false merge/split ve label doğruluğu.
10. Counter-evidence omission oranı.
11. Pricing extraction doğruluğu.
12. Research-gap sınıflandırması: secondary vs primary.
13. Decision policy grounding, gate doğruluğu ve outcome açıklanabilirliği.
14. Reproducibility ve sürüm farkı.

Golden dataset başlangıçta elle incelenmiş farklı ürün tipleri, pazar olgunlukları, diller ve hem güçlü hem zayıf fikirlerden oluşur. Uzun vadeli startup başarısı kısa dönem ground truth sayılmaz. Kullanıcı düzeltmesi, görüşme/pilot/ön sipariş sonuçları ve karar sonrası feedback ayrı kalibrasyon sinyalleridir.

## Feature flag ve policy rollout

Kapsamdaki connector ve algoritmalar silinmez. Güvenli çalıştırma için feature flag/policy ile etkinleştirilir:

- Connector bazlı tenant/market erişimi
- Browser render
- Embedding/pgvector
- Python/HDBSCAN
- Deep Research provider
- Yeni karar policy sürümü

Shadow run ve karşılaştırmalı evaluation, yeni algoritmanın eski sonucu sessizce bozmasını engeller.

## Yedekleme, felaket kurtarma ve bakım

- PostgreSQL point-in-time recovery.
- Object storage versioning ve lifecycle policy.
- Workflow history retention ve arşivleme.
- Şema migration'ları forward uyumlu ve geri dönüş planlı.
- Secret rotasyonu.
- Connector kill switch.
- Provider outage fallback policy.
- Düzenli restore tatbikatı ve veri bütünlüğü kontrolü.

## Platform kabul kriterleri

- Faz 1–7 aynı kimlik, sözleşme, workflow, budget ve audit altyapısını kullanır.
- Aynı activity tekrar çalıştığında duplicate dış çağrı veya duplicate kayıt üretmez.
- Workflow iptal, retry ve resume davranışları test edilmiştir.
- Tenant verisi başka tenant tarafından okunamaz; global cache erişimi tenant sorgusunu sızdırmaz.
- AI credential veya sınırsız tool erişimi alamaz.
- SSRF ve redirect bypass testleri geçer.
- Her kullanıcıya gösterilen önemli claim geçerli citation binding'e sahiptir.
- Maliyet hard limit'i eşzamanlı çağrılarda dahi aşılamaz.
- Faz çıktıları sürümlü ve tekrar üretilebilirdir.
- Normalizasyon değişikliği eski citation ve dossier'i sessizce değiştiremez.
- Secondary research boşluğu ile primary validation boşluğu veri modeli düzeyinde ayrıdır.

## Kesinlikle kullanılmayacak yaklaşımlar

- Faz başına ayrı kuyruk, ayrı Source Registry veya ayrı policy motoru.
- AI'a doğrudan internet, credential veya serbest tool yetkisi.
- Ham ve normalize içeriği aynı değişebilir kayıtta tutmak.
- Offset dışında bağlayıcı taşımayan citation.
- Kullanıcı yorumu üzerinden gerçek ödeme davranışı varsaymak.
- Şikâyet yokluğunu memnuniyet veya Kill kanıtı saymak.
- Kaynak erişilememesini sonuç bulunamadı diye kaydetmek.
- Kalibre edilmemiş ağırlıklardan başarı yüzdesi veya bilimsel kesinlik üretmek.
- Tek sağlayıcıya gömülü arama, AI veya storage kodu.
- Kapsamdaki her connector ve ağır algoritmayı her araştırmada körlemesine çalıştırmak.
