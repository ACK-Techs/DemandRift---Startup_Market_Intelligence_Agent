# Veri sözleşmeleri — taslak v0.1

Bu alan listeleri uygulanacak sözleşmedir; mevcut scriptlerin bunları döndürdüğü iddia edilmez. Kanonik ortak zarf [ortak veri sözleşmelerinde](../../ortak/veri-sozlesmeleri.md) tutulur. Alanlar açıkça opsiyonel denmedikçe zorunludur. Bilinmeyen skaler `null`, boş koleksiyon `[]` olur; bilinmeme gerekçesi kalite/eksik alanına yazılır.

## Ortak zarf ve giriş

Her faz çıktısı `schema_version`, `project_id`, `research_id`, `status`, `versions` taşır. Bu faz ayrıca `evidence_bundle_id`, `created_at` kullanır. Girdi doğrulanmış `ResearchPlan`: `brief`, `categories`, `intents`, `source_plan`, `query_plan`, `budget`, `unknowns`. `versions` içinde kullanılan `brief`, `plan`, `source_registry`, `connector`, `normalization`, `extraction`, `prompt`, `model`, `policy` sürümleri kaydedilir; çoklu connector için ID→sürüm eşlemesi kullanılır, kullanılmayan AI sürümü `null` olur.

Faz 2'nin zarf `status` değeri completed/partial/failed/cancelled olabilir; bu paket hazırlama durumudur. Kaynak işi sonuçları aşağıdaki `SourceReport.status` enum'udur ve bu iki kayıt türü karıştırılmaz. Yalnız Faz 1 `status=ready` planı yürütülür; `versions.plan` değeri değiştirilmeden devralınır.

## SourceProfile ve çalışma bütçesi

| Alan | Tip / kural |
| --- | --- |
| `source_id`, `profile_version`, `connector_id`, `connector_version` | Boş olmayan string; etkin registry kaydına bağlı. |
| `eligible_categories`, `supported_intents`, `languages`, `markets` | String listeleri; unknown kapsam açıkça belirtilir. |
| `capabilities` | search/fetch/metadata/reviews/archive gibi açık yetenek listesi. |
| `access_method`, `allowed_domains`, `allowed_content_types` | Registry'de tanımlı erişim ve izinli yüzey. |
| `extract_fields` | Alan adı, beklenen tip, required/optional, kaynaktaki locator/API alanı. |
| `access_policy`, `retention_policy`, `rate_limit_policy` | Sürümlü politika referansları; erişim inceleme tarihiyle. |
| `fallback_source_ids` | Yalnız önceden tanımlanmış alternatifler. |
| `limits` | max_items/pages/requests/response_bytes/total_bytes/seconds/retries/llm_tokens; hepsi sonlu ve negatif olmayan, gerekli alım sınırları pozitif. |
| `date_range`, `depth` | Araştırma planına ait zaman ve derinlik seçimi. |

`SourceProfile`, Faz 1'in Source Registry kaydından ve run planından türetilen yürütme görünümüdür; ikinci bağımsız kaynak kataloğu değildir. Faz 1 `allowed_categories` → `eligible_categories`, `available_fields` + `source_plan` seçimi → `extract_fields`, `locale_coverage` → `languages`/`markets`, `surfaces` → `capabilities`/`allowed_domains` eşlemesi adapter'da açıkça doğrulanır. Nihai kod şemasında bu alanlar kanonik sözleşmeden türetilecek. Faz 1'in onaylanmış erişim/yetenek sınırları bu dönüşümle genişletilemez.

Bütçe aynı sınırlardan kaynak ve run toplamı için ayrı tavanlar içerir. Varsa `max_cost` para birimiyle kaydedilir. Harcama `actual_usage` ile ayrıca tutulur; hesaplanamayan maliyet sıfır gibi yazılmaz. Limit tüketimi eşzamanlı işler için tutarlı uygulanır.

## Ham içerik → belge → segment

- **RawArtifact:** `artifact_id`, `research_id`, `source_id`, `query_id`, `access_method`, `source_url`, `fetched_url`, `raw_content_ref`, `content_hash`, `content_type`, `collected_at`, `published_at`, `archive_captured_at`, `connector_version`, `research_plan_version`, `license_or_restriction`. Yayın/arşiv tarihi bilinmiyorsa null; bulunmayan içerik için artefact uydurulmaz.
- **NormalizedDocument:** `document_id`, `artifact_id`, `external_id`, `document_type`, `title`, `body_original_ref`, `body_normalized`, `source_url`, `canonical_url`, `parent_document_id`, `author_reference`, `published_at`, `updated_at`, `collected_at`, `language`, `locale`, `engagement_metadata`, `quality_flags`, `normalized_content_hash`, `normalization_version`, `supersedes_document_id`. Harici kimlik, başlık, yazar ve parent bilinmiyorsa null; kaynak sürümleri birleştirilip ezilmez.
- **Segment:** `segment_id`, `document_id`, `segment_type`, `text`, `start_offset`, `end_offset`, `segment_text_hash`, `normalized_content_hash`, `normalization_version`. Offset'ler normalize metin üzerinde tanımlanır; hash/sürümle doğrulanır. Kaynak locator varsa eklenir.
- **Relation:** `relation_id`, `from_id`, `to_id`, `relation_type`, `method`, `review_status`. Türler: duplicate_of/repost_of/comment_on/quote_of/derived_from/same_entity_candidate. Belirsiz eşleşme kesin merge değildir.

Kalite bayrakları: missing_body/missing_published_date/short_content/quote_only/duplicate_exact/possible_duplicate/out_of_scope_language/source_policy_limited/promotional_content_candidate/invalid_payload/unknown_date/stale_binding. Etiketler kaydı otomatik silmez.

## Claim ve Citation

`Claim`: `claim_id`, `claim_type`, `polarity`, `interpretation`, `citation_ids`, `subject_entity`, `intent_ids`, `independence_group_ids`, `validation_status`, `claim_version`.

- `claim_type`: problem_report/workaround/feature_request/competitor_complaint/competitor_praise/pricing_signal/stated_wtp_weak_signal/observed_payment_behavior/switching_signal/market_signal/counter_evidence.
- `polarity`: supports/challenges/neutral; doğrulanmış claim en az bir citation taşır.
- `Citation`: `citation_id`, `claim_ids`, `artifact_id`, `document_id`, `segment_id`, `source_id`, `source_url`, `verbatim_quote`, `start_offset`, `end_offset`, `segment_text_hash`, `normalized_content_hash`, `normalization_version`, `collected_at`, `published_at`, `validation_status`.
- Alıntı birebir eşleşmeli; `interpretation` alıntı yerine geçmez. Hatalı citation claim'i bloke eder. Extraction uygunluğu ölçümü başarı/gerçeklik yüzdesi değildir.
- `observed_payment_behavior` yalnız doğrulanabilir işlem/pilot/ön sipariş veya ayrı birincil doğrulama kaydıyla üretilebilir. Kamu yorumundan türetilmez.

## SourceReport

Zorunlu alanlar: `source_report_id`, `source_id`, `status`, `query_ids`, `coverage`, `counts`, `findings`, `counter_findings`, `citation_ids`, `limitations`, `errors`, `costs`, `stop_reason`, `versions`.

- `status`: succeeded/partial/no_results/source_unavailable/rate_limited/blocked_by_policy/challenge/invalid_output/cancelled/failed.
- `parse_failed` kaynak status değil, `invalid_output` durumunun hata kodudur. Bot challenge ayrı `challenge` sonucudur.
- `counts`: discovered/fetched/normalized/eligible/unique/claims. Her biri ayrı ölçülür; sitemap URL sayısı çekilmiş belge sayısı değildir.
- `coverage`: intent_ids/languages/markets/date_range/actual_content_types. Yalnız erişilen yüzey kayıtlıdır.
- `findings` ve `counter_findings`: claim ID listeleri. İçerik yoksa boş listeler ve gerçek hata nedeni döner.
- `stop_reason`: completed/coverage_reached/no_new_evidence/exhausted_results/budget_exhausted/time_exhausted/no_eligible_sources/cancelled/error.

## EvidenceBundle

Ortak zarfa ek zorunlu alanlar:

- `source_reports`: SourceReport listesi.
- `claims`, `citations`: yalnız doğrulanmış, birbirine referans veren koleksiyonlar.
- `independence`: grup kimliği, üye claim/document ID'leri, ilişki gerekçesi, known/unknown durumu. Bilinmeyen ilişki bağımsız olduğu varsayımını üretmez.
- `coverage`: araştırma niyeti başına covered/partial/missing, bağımsız grup ve kaynak ailesi sayıları, güncellik/dil/pazar kapsamı, destekleyici/karşıt kanıt sayısı, değerlendirme kuralı sürümü.
- `evidence_maps`: problems/voice_of_customer/competitors/pricing/opportunity_hypotheses/market_maturity. Kanıt yoksa boş koleksiyon veya unknown profil ve gerekçe.
- `limitations`, `gaps`, `costs`, `selection_trace_ref`, `source_registry_version`, `parent_bundle_id` (ilk çalışmada null).

Rakip haritası resmi iddialar ve kullanıcı deneyimlerini ayrı claim listelerinde tutar. Fiyat gözlemi `competitor_id`, `plan_name`, `price`, `currency`, `billing_period`, `free_tier`, `trial`, `usage_limit`, `observed_at`, `citation_id`, `extraction_flags` taşır; bilinmeyen alanlar null olur. Para birimi/aylık-yıllık dönemler kendiliğinden eşitlenmez. Fiyat düzeltmesi ham kaydı ezmez.

Fırsat hipotezi `hypothesis`, `supporting_claim_ids`, `challenging_claim_ids`, `open_questions` taşır; kesin pazar boşluğu diye sunulmaz. Pazar olgunluğu existing/resegmented/emerging/new/unknown; dayanak claim'ler ve kapsam yanlılığıyla verilir.

## ResearchGapRequest ve hatalar

`ResearchGapRequest`: `gap_id`, `research_id`, `parent_bundle_id`, `gap_type` (secondary_research_gap/primary_validation_gap), `intent_id`, `reason`, `severity`, `proposed_queries`, `eligible_source_ids`, `expected_evidence_type`, `remaining_budget`, `stop_condition`. Faz 3'ten gelirse `parent_decision_id` eklenir. Birincil boşlukta önerilen web sorguları boş olmalıdır. Backend yalnız secondary türünü doğrulanmış plan revizyonuna dönüştürür.

Hata zarfı: `code`, `stage`, `source_id` (genel hata için null), `query_id` (yoksa null), `retryable`, `message`, `details_ref`. Kodlar: invalid_plan/unsupported_source/policy_blocked/network_unavailable/rate_limited/budget_exhausted/payload_too_large/parse_failed/invalid_provenance/citation_mismatch/stale_binding/model_schema_invalid/cancelled. Hata, iş sonucuyla birlikte taşınır; ham response sır/kişisel veri filtrelenmeden log'a yazılmaz.
