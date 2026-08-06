# Üst Yönetim Ana Mimari ve Entegrasyon Planı

## Bu belgenin rolü

Bu dosya projenin ana yönetim, mimari ve entegrasyon referansıdır. Yeni bir sohbet veya yeni bir geliştirici önce bu dosyayı, ardından `Platform-Temeli.md` ve ilgili faz dosyasını okumalıdır.

Belge sırası:

1. `Ust-Yonetim-Ana-Mimari-Plani.md` — bütün sistem ve entegrasyon sırası
2. `Platform-Temeli.md` — ortak teknik omurga ve bağlayıcı kurallar
3. `Faz1-Plan.md` … `Faz7-Plan.md` — alan bazlı ayrıntılar
4. `Gerekli-Iyilestirmeler.md` — tarihsel çapraz değerlendirme; çelişki halinde güncel ana mimari ve revize faz dosyaları üstündür

Faz 8 bilinçli olarak sona bırakılmıştır ve bu belgede tasarlanmaz.

## Ürün amacı

Bir startup fikrini araştırma, doğrulama ve MVP hazırlığı öncesinde geçen onlarca saatlik işi tek bir denetlenebilir akışta toplamak; kullanıcıya yalnızca rapor değil şu soruya güvenilir cevap vermek:

> Bu fikri mevcut haliyle geliştirmeli miyim, değiştirmeli miyim, bırakmalı mıyım, yoksa hangi kritik bilgiyi doğrulamalıyım?

Ürün vaadi:

> Don't just validate your idea. Leave with a build-ready MVP.

Temel akış:

```text
Discover -> Decide -> Build
```

Bu doküman Discover ve Decide bölümlerini, yani Faz 1–7'yi kapsar. Build/entegrasyon çıktılarının ayrıntısı Faz 8'de ele alınacaktır.

## Kapsam kararı

Proje kapsamı sadeleştirilmeyecektir. Web, resmî siteler, teknik platformlar, sosyal/topluluk kaynakları, marketplace/review kaynakları, domain/web footprint ve vertical research pack'ler mimari kapsamda korunur. SimHash, MinHash, embedding, pgvector, HDBSCAN, browser rendering ve Deep Research gibi gelişmiş yetenekler de kapsamdan çıkarılmaz.

Ancak kapsamlı olmak bütün araçların her run'da çalışması demek değildir. En doğru mimari, ürün tipine ve araştırma niyetine göre gerekli bileşeni seçen policy-driven/adaptive bir sistemdir. Gereksiz connector çalıştırmak kapsamlılık değil, gürültü ve hata üretir.

Süre hedefi mimari karar ölçütü değildir. Öncelik doğruluk, izlenebilirlik, güvenlik, tekrar üretilebilirlik ve tam kapsamdır.

## Çözülmüş ana tartışmalar

### 1. Faz 0 kararı

“Faz 0” kullanıcı fazı değildir. Adı **Platform Temeli** olarak kesinleştirilmiştir ve bütün fazların altında yatay çalışır. Ayrı bir altyapı projesi olarak tamamen bitirilmesi beklenmez; ortak yetenek ilk ihtiyaç duyan modülle beraber uygulanır.

### 2. Faz 5 kararı

Faz 5 ürün yeteneği ve doküman olarak korunur. Kodda ikinci araştırma pipeline'ı değildir. Gap Auditor ve AI Research Controller, Faz 3'ün aynı acquisition altyapısını `gap_driven` tetikleyiciyle kullanır. Akış:

```text
Faz 6 -> Faz 5 policy/controller -> Faz 3 -> Faz 4 -> Faz 6
```

### 3. Karar geçerliliği

- İnternette “para verirdim” cümlesi gerçek ödeme isteği değildir.
- Rakip fiyatı yalnızca gözlemlenen pazar fiyatıdır; bizim ürüne talep kanıtı değildir.
- Şikâyet bulunmaması memnuniyet kanıtı değildir.
- Kill için pozitif ve bağımsız karşıt kanıt gerekir.
- Yeni/emerging pazarda kanıt azlığı otomatik Kill üretmez.
- Build iç anlamı `build_to_validate`dır: doğrulama MVP'si geliştirmeye değer.
- Secondary research ile primary validation birbirine karıştırılmaz.

### 4. Maliyet kararı

Maliyet modelinin amacı kapsamı azaltmak değil, doğru model/connector yönlendirmek ve kontrolsüz harcamayı engellemektir. Her run yürütme öncesi tahmin, yürütme sırasında rezervasyon ve sonrasında gerçek kullanım kaydı taşır.

### 5. Teknoloji kararı

- Modüler monolith korunur.
- TypeScript/Node.js ana runtime'dır.
- PostgreSQL ana veri deposudur.
- S3 uyumlu object storage ham artefact içindir.
- Tam kapsamlı dayanıklı akış için Temporal tabanlı Workflow Engine seçilir.
- Redis zorunlu queue değildir; yalnız gerekli cache/rate-limit koordinasyonu içindir.
- Python worker gelişmiş NLP/analytics için korunur ancak her run'ın zorunlu yolu değildir.
- Playwright browser connector korunur fakat izole ve policy kontrollüdür.

## Uçtan uca sistem

```text
Kullanıcı fikri
   |
   v
Faz 1 — Intake ve netleştirme
   |  IdeaBrief + field origins + assumptions
   v
Faz 2 — Araştırma planı
   |  ResearchPlan + query/source plan + budget contract
   v
Faz 3 — Evidence Acquisition (plan_driven)
   |  RawArtifact + provenance + execution status
   v
Faz 4 — Normalizasyon ve ilişkilendirme
   |  NormalizedDocument + segments + duplicate/entity relations
   v
Faz 6 — Kanıt analizi
   |  claims + clusters + evidence maps + gaps
   +-------------------------------+
   | secondary gap                 |
   v                               |
Faz 5 — Gap policy/controller      |
   |                               |
   +-> Faz 3 (gap_driven) -> Faz 4-+
   |
   | analysis sufficient / primary gap classified
   v
Faz 7 — Karar motoru
   |  Build | Modify | Kill | Investigate More
   |  + investigate_secondary | validate_primary subtype
   v
Decision Dossier -> gelecekte Faz 8
```

## Fazların kesin sorumlulukları

| Faz | Tek ana sorumluluk | AI rolü | Deterministik rol | Çıkış |
| --- | --- | --- | --- | --- |
| 1 | Belirsiz fikri araştırılabilir brief yapmak | Yapılandırma ve soru önerisi | Köken, state ve onay kuralları | IdeaBriefVersion |
| 2 | Nerede/ne aranacağını planlamak | Soru ve query seed önerisi | Source policy, query compile, coverage, bütçe | ResearchPlanVersion |
| 3 | İzinli kaynaklardan ham kanıt toplamak | Yok; provider deep-search yalnız aday kaynak olabilir | Connector, quota, provenance, egress | RawArtifact seti |
| 4 | Veriyi kayıpsız normalize/ilişkilendirmek | Yok | Parse, normalize, language, duplicate, entity adayları | Normalized corpus |
| 5 | Eksik kanıt için kontrollü araştırma önermek | Gap'e göre sorgu/karşıt hipotez | Policy, budget, stop ve Faz 3 tetikleme | DeepResearch trace/gap closure |
| 6 | Atomik claim ve evidence map üretmek | Grounded extraction/label/sınıflandırma | Eligibility, binding, clustering adayları, independence | Evidence/Analysis dossier |
| 7 | Kanıta bağlı yön kararı vermek | Kaynaklı anlatım ve açıklama | Sufficiency, policy, counterfactual, validation route | Decision Dossier |

## Ana entegrasyon ilkesi: önce sözleşme, sonra üretici, sonra tüketici

Her entegrasyon şu sırayı izler:

1. Input/output schema.
2. Kimlik, tenant ve version alanları.
3. Hata ve partial durumları.
4. Idempotency davranışı.
5. Maliyet ve telemetry alanları.
6. Producer implementasyonu.
7. Consumer contract testi.
8. Uçtan uca workflow bağlantısı.
9. Golden dataset/evaluation.
10. UI görünürlüğü ve kullanıcı düzeltmesi.

Bu sıra tamamlanmadan serbest metinle faz bağlamak yasaktır.

## Entegrasyon sırası

Bu sıra süre tahmini değil, bağımlılık sırasıdır. Sonraki adım öncekinin sözleşme ve kabul testlerine dayanır.

### A. Repository ve ortak contracts

Kurulacaklar:

- Monorepo workspace ve modül sınırları.
- TypeScript strict mode, lint, formatting ve test düzeni.
- `packages/contracts`.
- Ortak ID, timestamp, money, locale, source, status ve version tipleri.
- Error taxonomy.
- Contract snapshot ve compatibility testleri.
- Migration sistemi.

İlk sözleşmeler:

```text
IdeaBrief
ResearchPlan
SourceRegistryEntry
BudgetContract
ResearchRun
RawArtifact
NormalizedDocument
DocumentSegment
Claim
ResearchGapRequest
AnalysisDossier
DecisionDossier
```

### B. Identity, tenant ve proje omurgası

- User/Tenant/Membership/Project modeli.
- TenantContext middleware.
- Repository filtreleri ve PostgreSQL RLS.
- Object storage namespace.
- Audit actor modeli.
- Cross-tenant negatif testler.

Bu yapı billing'in tamamını gerektirmez; fakat bütün kullanıcıya özel kayıtların tenant/project kimliği baştan bulunur.

### C. Workflow ve durum yönetimi

- Temporal namespace, worker ve workflow/activity adapter'ları.
- `IdeaResearchWorkflow` iskeleti.
- Workflow ID ve idempotency standardı.
- Retry/error sınıfları, heartbeat, timeout, cancellation ve signal.
- Workflow state'i ile uygulama DB projection'ının tutarlılığı.
- Partial completion ve resume testleri.

### D. Policy, Source Registry ve Egress

- Kanonik Source Registry schema/repository.
- Connector enable/disable ve policy version.
- Secret manager adapter.
- Egress Gateway.
- SSRF, redirect, DNS rebinding, response limit ve MIME testleri.
- robots/terms/license/retention policy hook'ları.

Dış connector yazılmadan önce bu sınır çalışmalıdır.

### E. Cost Ledger ve AI Gateway

- Provider adapter arayüzü.
- Task-based model routing.
- Prompt Registry ve prompt version.
- Structured output validation.
- Token/cost/latency kaydı.
- Atomic budget reservation/settlement.
- Provider timeout/fallback.
- Tenant-safe cache policy.

### F. Faz 1 entegrasyonu

- Idea input UI/API.
- LLM structured intake.
- `field_origin` ve `assumption` kaydı.
- Clarification state machine.
- User confirmation.
- Onaysız `ai_hypothesis` propagasyon engeli.
- Immutable IdeaBriefVersion.

### G. Faz 2 entegrasyonu

- AI Research Planner.
- Deterministic Plan Compiler.
- Query Compiler/Validator.
- Source Registry okuma.
- Product-type/source-intent eşleştirme.
- Dil/coğrafya kapsamı.
- Estimated cost envelope ve BudgetContract.
- ResearchPlan snapshot.

### H. Faz 3 temel acquisition platformu

Önce connector SDK'sı:

```text
discover
fetch
normalizeMeta
healthCheck
estimateCost
policyRequirements
```

Ardından connector aileleri, kapsamdan çıkarılmadan şu teknik bağımlılık sırasıyla kurulur:

1. Search provider adapter'ları: Brave, Exa ve ek/fallback sağlayıcılar.
2. Generic HTTP fetch ve Official Site Scanner.
3. Sitemap/robots, pricing/features/docs/changelog tarayıcıları.
4. GitHub, Hacker News, Stack Exchange ve Product Hunt.
5. App Store, Google Play ve ürün tipine özel marketplace'ler.
6. Reddit ve X — resmî/lisanslı erişim politikasıyla.
7. YouTube ve uygun video metadata/comment kaynakları.
8. Instagram/TikTok/Mastodon/açık forum gibi koşullu sosyal connector'lar.
9. G2/Capterra/GetApp ve review sağlayıcıları — lisanslı erişimle.
10. Domain/RDAP/DNS/Certificate Transparency/web footprint.
11. Ads, funding, jobs, maps, kamu, akademik, regülasyon, patent ve marka vertical pack'leri.
12. İzole Playwright render profile ve JS-only sayfalar.
13. Hazır deep research/semantic provider adapter'ları — sadece aday URL/citation üreticisi olarak.

Her connector aynı provenance, error, cost, rate-limit ve health sözleşmesini geçmeden aktif olmaz.

### I. Faz 4 normalizasyon

- Immutable RawArtifact ve object storage doğrulama.
- Parser registry ve normalization version.
- Unicode, HTML, URL, tarih, dil ve locale.
- Document/segment/relation üretimi.
- Exact dedup: native ID, canonical URL, SHA-256.
- Near dedup adayları: pg_trgm/TF-IDF, SimHash; uygun corpus'ta MinHash+LSH.
- Entity identity confidence ve human correction.
- Transformation Ledger.
- Re-normalization lineage.
- Citation için segment hash/content hash.

### J. Citation Service

Faz 6'dan önce çalışmalıdır:

- Verbatim quote binding.
- Offset + hash + version doğrulaması.
- Citation URL ve collected_at.
- `stale_binding` lifecycle.
- Kaynak değişimi/re-normalizasyon testleri.
- UI için citation resolver.

### K. Faz 6 analiz motoru

Sıra:

1. Evidence Eligibility Gate.
2. BM25/lexical relevance ve diversity-aware top-K.
3. Şemalı claim extraction için küçük model routing.
4. Claim Validator ve Citation Service.
5. Independence group ve counter-evidence mapping.
6. Lexical similarity graph/connected components.
7. Embedding + pgvector semantic candidates.
8. Python worker + HDBSCAN gelişmiş clustering.
9. Competitor Matrix.
10. Pricing Evidence Map + extraction confidence + correction UI.
11. Voice of Customer ve Problem Evidence Map.
12. Opportunity Hypotheses.
13. Market Maturity Profile.
14. Research Limitations.
15. Secondary Research Gap ve Primary Validation Gap sınıflandırması.

Gelişmiş algoritmalar kapsamda korunur; shadow/evaluation sonucu uygun policy ile çalıştırılır. Aynı veri üzerinde lexical ve gelişmiş sonuç karşılaştırılabilir.

### L. Faz 5 gap-driven döngü

- Faz 6 `ResearchGapRequest` üretir.
- Gap Auditor deterministik olarak boşluğun gerçekten ikincil araştırmayla kapanabilir olduğunu doğrular.
- AI Research Controller hipotez, karşıt hipotez, sorgu ve kaynak önerir.
- Policy Gateway source/budget/onay kontrolü yapar.
- Faz 3 aynı connector runtime'ını `gap_driven` çalıştırır.
- Faz 4 yeni artefact'ları normalize eder.
- Faz 6 yeni `AnalysisRunVersion` üretir.
- Stop rules coverage artışı, kaynak doygunluğu, tekrar oranı, hard budget, policy block ve maksimum döngü sınırını uygular.

Primary validation boşluğu bu döngüye girmez.

### M. Faz 7 karar motoru

Kurulum sırası:

1. Evidence Sufficiency Gate.
2. Dil/coğrafya coverage gate'i.
3. Market maturity'ye göre rubric seçimi.
4. Problem, davranış, rekabet, fırsat, uygulanabilirlik ve kanıt profilleri.
5. Hard policy kuralları.
6. Kill asimetri kuralı: pozitif karşıt kanıt zorunlu.
7. WTP kuralı: stated signal gerçek ödeme değildir.
8. Outcome eligibility.
9. Gate counterfactual.
10. Value of Information.
11. `investigate_secondary` / `validate_primary` routing.
12. AI grounded synthesis.
13. Decision/Citation Validator.
14. Immutable Decision Dossier.

Kullanıcıya her sonuçta şu gerçek açıkça gösterilir:

```text
secondary_source_count
independent_source_count
primary_interview_count
observed_payment_count
unvalidated_assumptions
```

Örneğin 214 internet kaynağı ve sıfır görüşme varsa “0 gerçek kullanıcı görüşmesi, ödeme isteği doğrulanmadı” görünür olmalıdır.

### N. Evaluation, feedback ve kalibrasyon

Evaluation sona bırakılan kalite süsü değildir; her modülle birlikte fixture/golden örnek eklenir.

- Faz bazlı evaluation setleri Platform Temeli'ndeki ayrımla tutulur.
- En az farklı ürün türleri: developer tool, B2B SaaS, mobil/consumer, marketplace, yerel hizmet, regüle dikey.
- Pazar türleri: existing, resegmented, emerging, new, unknown.
- Dil/coğrafya çeşitliliği.
- Deliberate adversarial içerik ve prompt injection örnekleri.
- Kullanıcı citation, price, entity, claim ve decision düzeltmesi yapabilir.
- Düzeltme ham kanıtı ezmez; yeni annotation/version üretir.
- Görüşme, landing test, preorder, concierge ve pilot sonucu dossier'e follow-up evidence olarak bağlanır.
- Karar policy kalibrasyonu gerçek feedback ile yapılır; “startup daha sonra başarılı oldu” tek ve kısa dönem etiketi değildir.

## Fazlar arası minimum sözleşmeler

### Faz 1 -> Faz 2

```text
idea_brief_id/version
original_idea
normalized_idea
product_type
target_user
problem_or_job
context_or_niche
constraints
field_origins
assumptions
clarity_status
user_confirmation
```

### Faz 2 -> Faz 3

```text
research_plan_id/version
idea_brief_version
research_questions
query_plan
source_plan
source_registry_version
market/language scope
budget_contract
estimated_cost_envelope
scope_origins
```

### Faz 3 -> Faz 4

```text
research_run_id
trigger_type
query/connector executions
raw_artifact references
provenance
access/policy/license metadata
execution outcomes
cost usage
```

### Faz 4 -> Faz 6

```text
normalization_run/version
normalized_documents
segments + hashes
relations
entity candidates
quality flags
transformation ledger
```

### Faz 6 -> Faz 5

```text
research_gap_id
gap_type=secondary_research_gap
affected_pillar
missing_evidence
coverage snapshot
expected decision value
eligible source families
```

### Faz 6 -> Faz 7

```text
analysis_run/version
claims + valid citations
clusters
independence groups
problem/voc/competitor/pricing maps
counter-evidence
opportunity hypotheses
market maturity
research limitations
secondary gaps
primary validation gaps
cost/coverage summary
```

### Faz 7 -> Faz 8 için yalnız çıkış sınırı

```text
decision_dossier_id/version
outcome
outcome_subtype
market_signal_profile
execution_condition_profile
rationale_claim_ids
counter_evidence_claim_ids
critical_unknowns
gate_counterfactuals
primary_validation_status
recommended_validation_actions
assumptions
policy/model/prompt/input versions
```

Faz 8 bu sözleşmeyi tüketir; nasıl PRD, teknik plan veya prompt pack üreteceği daha sonra kararlaştırılacaktır.

## Hata sınıflandırması

```text
ValidationError       retry yok, input/schema düzeltilir
PolicyBlocked         retry yok, kullanıcıya görünür neden
AuthenticationError   credential/izin düzeltilir
RateLimited           retry-after ve quota policy
TransientProvider     kontrollü retry/fallback
PermanentSource       erişilemedi olarak kaydet
BudgetExceeded        yeni çağrı yok, partial/gap sonucu
Cancelled             child işler durur, rezervasyon çözülür
InvariantViolation    yayın durur, alert/audit
```

Her hata kullanıcı raporunda kanıt yokluğu gibi gösterilmez.

## Test stratejisi

### Unit

- Query compiler, URL normalizer, duplicate fingerprint, gates, policy ve cost arithmetic.

### Contract

- Faz producer/consumer uyumu.
- Connector SDK ve provider adapter uyumu.
- TypeScript/Python payload uyumu.

### Integration

- PostgreSQL, object storage, Temporal, AI provider mock, connector sandbox.
- Retry, cancellation, resume, partial ve stale-binding.

### Security

- SSRF, redirect, DNS rebinding, decompression bomb, MIME spoof.
- Prompt injection ve tool-policy bypass.
- Tenant isolation ve signed URL.
- Secret leakage ve log redaction.

### Evaluation

- Faz bazlı golden datasets.
- Counter-evidence omission.
- WTP yanlış sınıflandırma.
- Complaint absence -> satisfaction yanlış çıkarımı.
- New-market evidence scarcity bias.
- Citation correctness ve re-normalization.

### End-to-end

- Geniş fikirle devam.
- Kullanıcının AI niche önerisini reddetmesi/seçmesi.
- Standard ve premium Deep Research.
- Kaynak unavailable ve no-results ayrımı.
- Gap-driven geri dönüş.
- Build/Modify/Kill/Investigate More ve iki alt tür.
- Kullanıcı düzeltmesi ve dossier revision.

## Definition of Done

Bir faz yalnızca ekran çalıştığında bitmiş sayılmaz. Aşağıdakilerin tamamı gerekir:

- Input/output contract ve version.
- Tenant/project scope.
- Idempotency ve workflow state.
- Error/partial/cancel davranışı.
- Budget/cost kaydı.
- Structured log/trace/metric.
- Security/policy kontrolü.
- Unit + contract + integration test.
- Golden evaluation örnekleri ve eşikleri.
- Kullanıcıya görünür limitation/düzeltme yolu.
- Doküman ve ADR güncellemesi.

## Kritik ürün doğruluk kuralları

Bu kurallar hiçbir AI prompt'u veya model değişikliğiyle aşılamaz:

1. Kullanıcı onaylamadığı AI hipotezi araştırmayı tohumlayamaz.
2. Arama sonucu fetch edilmiş kaynak değildir.
3. Erişilemeyen kaynak kanıt yokluğu değildir.
4. Duplicate/repost bağımsız kanıt değildir.
5. Quote birebir kaynağa ve sürüme bağlanır.
6. Fiyat gözlemi ödeme isteği değildir.
7. “Para verirdim” gerçek ödeme davranışı değildir.
8. Şikâyet yokluğu memnuniyet değildir.
9. Yeni pazarda düşük kanıt Kill değildir.
10. Kill pozitif karşıt kanıt ister.
11. Build başarı garantisi değil, doğrulama MVP'si önerisidir.
12. Primary validation boşluğu daha fazla web araştırmasıyla kapatılamaz.
13. AI hard gate, budget, source policy veya citation validator'ı geçersiz kılamaz.
14. Karar stabilitesi başarı olasılığı değildir.

## Kullanıcı deneyiminde zorunlu görünürlük

- Araştırılan ve araştırılamayan kaynaklar.
- Policy/izin nedeniyle kullanılmayan kaynaklar.
- Kaynakların dil/coğrafya dağılımı.
- Bağımsız kaynak ile toplam kaynak farkı.
- Fiyat çıkarım güveni.
- Karşıt kanıtlar.
- Kritik varsayımlar ve kökenleri.
- Secondary vs primary gap.
- Gerçek kullanıcı görüşmesi ve gerçek ödeme gözlemi sayısı.
- Kararı değiştirecek gate/claim'ler.
- Kullanıcının düzeltme ve yeniden değerlendirme yolu.

## Operasyon ve yönetişim

- Her dış provider adapter arkasındadır; tek sağlayıcı kilidi yoktur.
- Provider ve connector health otomatik izlenir.
- Source policy/terms düzenli gözden geçirilir.
- Connector kill switch bulunur.
- Prompt/model/decision-policy değişiklikleri shadow evaluation olmadan doğrudan herkese açılmaz.
- Schema ve migration değişiklikleri ADR ve compatibility testi ister.
- Retention ve deletion işleri workflow olarak izlenir.
- Cost anomaly ve citation invalidation alert üretir.

## Ana risk kayıtları

| Risk | Etki | Yapısal kontrol |
| --- | --- | --- |
| AI hipotezinin kendi kendini doğrulaması | Yanlış araştırma zinciri | Field origin + user confirmation gate |
| WTP yanlış çıkarımı | Yanlış Build | Weak signal ayrımı + primary validation |
| Şikâyet yokluğundan Kill | Zararlı karar | Pozitif karşıt kanıt kuralı |
| Olgun pazar yanlılığı | Yeni fırsatları kaçırma | Market Maturity Profile |
| Claim extraction maliyeti | Kontrolsüz run maliyeti | Eligibility top-K + model routing + ledger |
| Citation offset bozulması | Sessiz yanlış alıntı | Hash/version binding + stale status |
| İkinci acquisition hattı | Tutarsız provenance/budget | Faz 5'in Faz 3'e erimesi |
| SSRF/prompt injection | İç ağ/veri güvenliği | Egress Gateway + AI tool isolation |
| Cross-tenant sızıntı | Kritik güvenlik ihlali | TenantContext + RLS + tests |
| Connector policy değişimi | Hukuki/operasyonel risk | Source Registry + kill switch |
| Aşırı AI bağımlılığı | Maliyet ve tutarsızlık | Deterministik normalization/gates/policy |
| Sahte bilimsel kesinlik | Güven kaybı | Gate counterfactual; kalibrasyonsuz yüzde yok |

## Yeni sohbet için çalışma protokolü

Yeni bir Codex/Claude sohbetinde şu talimat uygulanmalıdır:

1. Önce bu dosyayı tamamen oku.
2. Sonra `Platform-Temeli.md` dosyasını tamamen oku.
3. Çalışılacak fazın dosyasını ve doğrudan komşu faz sözleşmelerini oku.
4. Mevcut kod/repository durumunu contracts ve Definition of Done'a göre denetle.
5. Kapsamı süre uğruna silme veya connector/algoritmayı plandan çıkarma.
6. Her bileşeni her run'da çalıştırmak yerine Source Registry/policy ile doğru yerde etkinleştir.
7. Değişiklik yaptıktan sonra ilgili docs, contracts, tests ve ADR'leri birlikte güncelle.
8. Faz 8'i kullanıcı açıkça başlatmadan tasarlama.

## Nihai yönetim kararı

Mimari yön şu şekilde kilitlenmiştir:

- Tam kapsam korunur.
- Ortak altyapı “Faz 0” değil yatay Platform Temeli'dir.
- Fazlar modüler monolith içinde kesin contracts ile ayrılır.
- Araştırmanın tek acquisition yolu Faz 3'tür; Faz 5 gap-driven kontrol katmanıdır.
- Karar motoru internet kanıtının epistemik sınırlarını açıkça tanır.
- Primary validation ürün çıktısının zorunlu parçasıdır.
- Maliyet, güvenlik, citation, tenant, evaluation ve gözlemlenebilirlik sonradan eklenecek aksesuarlar değil, ortak mimarinin bileşenleridir.
- Faz 8'e yalnızca sürümlenmiş, kaynaklı ve sınırları açık Decision Dossier aktarılır.
