# Faz 1 HTTP sözleşmeleri

Bu teslim kanonik veri sözleşmesini ve frontend doğrulayıcısını hazırlar. Aşağıdaki yeni HTTP yolları tasarımdır; bu checkpoint onları route, kalıcı receipt, migration, worker veya canlı model/kaynak çağrısı olarak uygulamaz. Mevcut hazırlık create/revise davranışları korunur. Aktif mimari hazırlık, kanıt ve karar olmak üzere üç fazdır; runtime şema başı `008` kalır.

Kanonik üretici `app/contracts.py`, açık export listesi `WIRE_MODELS` ve `scripts/generate_contracts.py` birlikte 51 modeli üretir: önceki 39 modelin payload biçimleri korunur, `PreparationMutationReceipt.operation` yalnız `confirm_brief` değerini de kabul eder. Şema sürümü additive teslimde `1.0.0` kalır. Yeni nested tipler `$defs`/TypeScript içinde bulunur; bağımsız top-level export değildir. JSON Schema, TypeScript ve üretici örnekleri generator ile üretilir; `--check` drift'i reddeder.

## Yeni modeller

| Model | Anlamı ve sınırlar |
|---|---|
| `HumanBriefConfirm` | Exact brief UUID/sürüm; current/proposal/unmatched kategori seçimi; optional analysis; en çok 64 unique field proposal. Proposal seçimi exact analysis ister. Kategori ID'si field seçimlerinden ayrıdır. Clarification skip açık continue-with-unknowns ister. |
| `PreparationAnalysisCreate` | brief/plan türü; exact brief; immutable bütçe kapasitesi için `BudgetLimits`; plan UUID/sürüm/fingerprint üçlüsü birlikte bulunur veya üçü de yoktur. Brief türü plan seçemez. |
| `PreparationAnalysis` | Exact scoped input snapshot ve versions; en çok 64 field proposal, 64 intent, 512 query hypothesis, 3 clarification question, 64 missing field ve 128 unknown. Öneri ID'leri analysis içinde unique'tir. Query yalnız included intent proposal'a bağlanır. |
| `PreparationAnalysisOperation` | Exact request key/fingerprint; server analysis/attempt kimlikleri; pending/completed/invalid_output/provider_unknown/overrun/not_dispatched/disabled; historical analysis ve usage. Completed analysis ile aynı owner/research/brief/plan tuple'ını korur. Dispatched terminal sonuç attempt ister. Unknown provider usage açıkça unknown kalır. |
| `PreparationAnalysisPage` | En çok 100 item, page limit kadar ve tek research/owner kapsamındaki immutable analysis history. Duplicate analysis ID reddedilir. |
| `PlanDraftCreate` | Exact brief; optional analysis; research mode ve bütçe. Caller source, connector, query plan veya permission payload göndermez. |
| `HumanPlanPatch` | Exact plan UUID/sürüm/fingerprint ve brief; en az bir explicit edit. Mode/budget edit null olamaz. En çok 128 source exclusion, 512 query exclusion/edit ve 64 intent decision. Aynı query hem edit hem exclusion olamaz. |
| `PlanApprovalCreate` | Exact plan ve brief; en çok 512 unique query confirmation ID ve 128 unique gap acknowledgment ID. Tam plan veya yetki değiştiren alan taşımaz. |
| `PlanReference` | Immutable plan UUID/sürüm/fingerprint, status ve brief seçimi. |
| `ResearchPlanPage` | En çok 100 historical plan; tek scoped research; unique plan UUID/version ve page limit. İç `ResearchPlan` sözleşmesi korunur. |
| `ResearchPlanPreparation` | Scoped plan; current brief; latest etiketi; explicit eligibility ve coverage gaps. Qualified scope ve plan hâli üzerinden approval/start ayrı hesaplanır. |
| `PlanMutationReceipt` | draft/revise/approve işlem scope'u ve exact input/result tuple. Nested historical plan result UUID/version/fingerprint ile tam eşleşir. Revision/approval aynı planın daha yeni project-wide sürümünü seçer; sürümler aralık atlayabilir. |

Yeni sürüm seçimleri JSON integer olarak `1..2147483647` aralığındadır; bool, float/exponent veya string coercion kabul edilmez. FE safe-number sınırını, scalar Unicode'u, Rust `\S` whitespace anlamını ve Pydantic'in şemada gösterilmeyen ilişkilerini doğrular. Query text en çok 1000 Unicode code point'tir ve normalleştirilmez. Yeni request model'lerinde omitted default ile explicit null/empty ayrıdır. Request'i serialize ederken `exclude_unset=True` kullanılır; generator request fixture'larında bunu uygular. `HumanPlanPatch` için omitted list edit değildir, explicit empty exclusion list insanın temizleme tercihi olabilir. Response alanlarının varsayılanları açıkça serialize edilir.

AI field proposal yalnız kök editable alan veya bounded `constraints.<safe_identifier>` yoluna bağlanır; arbitrary path traversal ve `original_idea` değişikliği reddedilir. Mevcut insan constraint anahtarlarının Unicode davranışı değişmez. AI kökeni yalnız `ai_inferred`/`ai_hypothesis` olur; orijinal fikir, owner, kaynak izni, source URL, runtime flag veya confirmed durumu modelden alınmaz. Query hypothesis henüz execution seed değildir. Enum kategori ve intent katalogları aynen kullanılır; alias veya kullanıcı tarafından gelen label otomatik izin ya da doğrulanmış kategori olmaz.

## Eligibility ve yetki sınırı

`PlanExecutionEligibility` mevcut qualification version/digest, `checked_at`, `valid_until`, blocking reasons ve coverage gaps taşır. Qualification üçlüsü all-or-none'dır. `can_approve` ve `can_start` birlikte true olamaz. Actionable seçim güncel brief'i, latest planı, confirmed matched kategoriyi, çözülmüş clarity/provenance'i, en az bir qualified/permitted source, included intent ve compiled query gerektirir. Kaynak/query limitleri plan bütçesini aşamaz. Timestamp karşılaştırması FE'de microsecond precision ile yapılır. Yeni Faz 1 DTO'ları için ayrı AJV instance bütün şemada ilan edilen `date-time` alanlarını, nested receipt/history/source review/eligibility alanları dahil, gerçek Gregorian gün, `00..23` saat, `00..59` dakika/saniye ve geçerli aware offset bileşenleriyle kontrol eder. Leap second, year 0, calendar rollover ve trailing karakter kabul edilmez. Pydantic'in kabul ettiği aware ISO çeşitleri ve microsecond truncation korunur; payload/raw metin normalize edilmez. Eski 39 modelin decoder davranışı ve tarih olmayan serbest metin/metadata değerleri bu değişiklikten etkilenmez.

Approval preview, awaiting planın gösterilen AI query hypothesis'lerini formda onaylanabilir sayabilir; kayıtlı query flag'ini değiştirmez. Native approval producer exact query seçimlerini doğrulayıp yeni immutable plan üretmelidir. Start eligibility confirmed plan ve gerçek query confirmation ister. `confirmed` status'lü eski boş plan şekli okunmaya devam eder; yeni eligibility envelope böyle bir planı actionable göstermez.

Bu DTO'lar server grant veya gerçek kaynak review'u değildir. Tüm 636 registry kimliği bu teslimde production execution için kapalıdır. Tarihsel sample health/eligibility izin yerine geçmez. Endpoint/repository implementation, current reviewed source authority ve expiry'yi yeniden doğrulamak zorundadır. Yetki yoksa ürün blocked/unavailable ve coverage gap gösterir; canlı arama yapılmış veya no-results bulunmuş gibi raporlanamaz. Unit test'teki `source-0000`/`example.org` scope'u yalnız varsayımsal contract fixture'dır; registry'ye veya runtime'a yüklenmez.

## Planlanan HTTP yolları

Relative yollar `/api/v1/projects/{project_id}` altındadır. Bu tabloda listelenen yeni yollar henüz bu teslimde yayımlanmamıştır.

| Method/path | Request → response |
|---|---|
| POST `/research/{research_id}/brief-confirmations` | `HumanBriefConfirm` → `IdeaBrief` |
| GET `/preparation-mutations/confirm_brief/{request_key}` | `PreparationMutationReceipt` |
| POST `/research/{research_id}/preparation-analyses` | `PreparationAnalysisCreate` → `PreparationAnalysisOperation` |
| GET `/analysis-mutations/{operation}/{request_key}` | `PreparationAnalysisOperation` |
| GET `/research/{research_id}/preparation-analyses` | `PreparationAnalysisPage` |
| GET `/research/{research_id}/preparation-analyses/{analysis_id}` | `PreparationAnalysis` |
| POST `/research/{research_id}/plans` | `PlanDraftCreate` → `ResearchPlan` |
| POST `/research/{research_id}/plan-revisions` | `HumanPlanPatch` → `ResearchPlan` |
| POST `/research/{research_id}/plan-approvals` | `PlanApprovalCreate` → `ResearchPlan` |
| GET `/research/{research_id}/plans/latest` | `ResearchPlanPreparation` |
| GET `/research/{research_id}/plans/{plan_id}/versions/{version}` | `ResearchPlanPreparation` |
| GET `/research/{research_id}/plans` | `ResearchPlanPage` |
| GET `/plan-mutations/{operation}/{request_key}` | `PlanMutationReceipt` |

İlerideki native/HTTP dilimi auth, CSRF/Origin, private no-store, tenant RLS, latest locking, immutable receipt lookup-before-latest, atomic budget admission ve exact body fingerprints uygulamalıdır. Receipt 404 belirsiz mutasyonun etkisiz olduğunu kanıtlamaz; otomatik POST/retry veya yeni request key üretmez. Model endpoint'i accepted metered worker/attempt producer olmadan doğrudan paid request yapamaz. GET hiçbir provider/source send başlatmaz. İzin ve bütçe body'den türetilemez veya resetlenemez. HTTP byte caps ve paginated history server uygulamasıyla ayrıca bağlanmalıdır.

## Bu dilimin kontrolleri

`tests/test_contracts.py` ve `apps/web/tests/api-client.test.mjs` gerçek üretilmiş fixture'ların producer/consumer eşleşmesini; sparse empty/null; strict identity; foreign scoped receipt; query/intent lineage; immutable original idea; no caller authority; unknown accounting; Unicode bounds; closed/empty plan ve varsayımsal qualified scope için approval/start kapılarını kontrol eder. Generator bilinmeyen veya yinelenen model fixture'ını ve geçersiz export adını yazmadan reddeder. Önceki 39 model schema korunması ve dört fixture değerinin korunması author kabul kanıtında ayrıca karşılaştırılır.

Bunlar offline contract/development kontrolleridir. Yeni endpoint, native DB migration/receipt, gerçek tarayıcı UI, Hetzner canlı Gemini/source acquisition ve roadmap'in 87 final senaryosu bu teslim tarafından PASS ilan edilmez.
