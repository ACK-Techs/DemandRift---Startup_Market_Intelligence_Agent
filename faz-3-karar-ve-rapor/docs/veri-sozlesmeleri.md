# Veri sözleşmeleri — taslak v0.1

Girdi [Faz 2 EvidenceBundle](../../faz-2-veri-toplama-ve-hazirlama/docs/veri-sozlesmeleri.md) ve ilişkili ResearchPlan/brief'tir. Ortak zarf [ortak sözleşmededir](../../ortak/veri-sozlesmeleri.md). Buradaki taslak henüz çalışan API değildir.

## DecisionReport

Aksi belirtilmedikçe alanlar zorunludur; boşluklar boş liste/null ve gerekçeyle ifade edilir.

| Alan | Tip / kural |
| --- | --- |
| `schema_version`, `project_id`, `research_id`, `status`, `versions` | Ortak zarf. Başarı yalnız son doğrulama geçildikten sonra. |
| `decision_id`, `evidence_bundle_id`, `created_at`, `previous_decision_id` | String ID'ler/ISO tarih; ilk kararda previous null. |
| `outcome` | positive_findings/modify/kill/investigate_more. Olumlu etiket: “Olumlu bulgular — yönetici değerlendirmesi bekliyor”; bulgu market_assessment içinde. Build yasak. |
| `management_review_required` | true; sonraki ürün geliştirme/MVP aşaması Çağlar tarafından değerlendirilecek. |
| `eligible_outcomes` | Backend politikasından; seçilen outcome bu listede olmalı. positive_findings kaynaklı olumlu değerlendirme ve zorunlu yönetici incelemesiyle geçerlidir. |
| `summary`, `rationale` | Kaynaklı anlatım ve gerekçe blokları. |
| `evidence_sufficiency` | passed/insufficient, kontrol sonuçları, eksik niyetler, policy_version. |
| `pillar_profiles` | Problem/customer/competition/opportunity/feasibility/evidence_quality için strong/mixed/weak/insufficient, destek/karşıt claim'ler, unknowns. |
| `target_customer`, `problem`, `competitors`, `opportunity_hypotheses` | İlgili claim referanslı alanlar; destek yoksa unknown/boş ve gerekçe. |
| `supporting_claim_ids`, `challenging_claim_ids`, `citation_ids` | Girdi snapshot'ında var ve doğrulanmış ID'ler. |
| `critical_unknowns`, `assumptions`, `limitations` | Kanıt yokluğu, kullanıcı koşulu veya kapsam sınırı açıkça etiketlenir. |
| `market_assessment`, `execution_constraints` | Ayrı profiller; kişisel bütçe pazarın değersizliği olarak yazılmaz. |
| `primary_validation` | status (not_started/partial/available), doğrulanmış gözlem referansları/sayıları, henüz doğrulanmayan davranışlar. |
| `decision_stability` | status stable/sensitive/fragile/not_evaluated, method, critical_claim_ids, assumptions_that_change_outcome; ölçülmeyen metrik üretilmez. |
| `next_actions` | Araştırma sorusu/kanıt eksikliği veya yönetici değerlendirmesine devir; ürün geliştirme/deney planı içermez. |
| `modification` | Modify için zorunlu nesne, diğerlerinde null. |
| `investigation` | Investigate More için zorunlu nesne, diğerlerinde null. |
| `costs`, `validation`, `errors` | Gerçek kullanım, doğrulama sonucu ve hata listesi; yoksa []/null açık. |

`versions`: brief/plan/evidence_bundle/decision_policy/prompt/model/validator sürümleri. Yeniden üretim için kullanılan kullanıcı koşulları snapshot'ı da saklanır.

`status`: completed/failed/cancelled; karar üretim sonucudur. Geçerli ama yetersiz kanıtla üretilmiş Investigate More raporu `completed` olabilir. Bu durum EvidenceBundle'ın partial kapsamını silmez; `limitations` ve `evidence_sufficiency` içinde korunur.

## Kaynaklı gerekçe

Her `rationale` bloğu `id`, `statement`, `kind` (evidence_interpretation/assumption/recommendation/limitation), `claim_ids`, `citation_ids` taşır. Olgusal bulgunun claim/citation listesi boş olamaz. Varsayım veya öneri olgu gibi sunulmaz. Backend ID ve alıntı bütünlüğünü doğrular; semantik destek ayrıca değerlendirilecek kalite boyutudur.

Kaynak URL'si, alıntı ve tarih Faz 2 snapshot'ından okunur. Model yeni citation ID, URL veya uydurma alıntı üretemez. Sırf aynı konuya değinen kaynak eklemek iddiayı doğrulanmış yapmaz.

## Outcome özel alanları

- **Olumlu bulgular:** yeterlilik ve kaynak dayanakları raporlanır; `outcome = positive_findings`, `management_review_required = true`. Kullanıcı etiketi “Olumlu bulgular — yönetici değerlendirmesi bekliyor”. Build veya MVP önerisi üretilmez.
- **Modify:** `modification = {preserve_signal, change_assumption, proposed_focus, avoid, evidence_to_reassess}`; her öneri dayanak claim'lere veya açık varsayıma bağlı. Kabul edilmeden kullanıcının fikri değiştirilmez.
- **Kill:** yeterlilik passed ve pozitif bağımsız karşıt claim gerekir. `rationale` mevcut teze sınırlı olmalı; `next_actions` kararı değiştirebilecek koşulu belirtmeli. Sıfır sonuç veya erişim engeli gerekçe olamaz.
- **Investigate More:** `investigation = {subtype, gaps, priority_reason}`. Alt tür investigate_secondary/validate_primary/mixed; mixed içindeki her boşluk kendi türünü taşır. Build her durumda kapsam dışıdır; yeterlilik yetersizken Kill engellenir; gerçek belirsizlik kesin Modify ile de gizlenmez.

## Sonraki adımlar ve ek araştırma

`NextAction`: `action_id`, `kind` (secondary_research/report_primary_gap/management_review/reassess), `target_segment`, `question_or_hypothesis`, `evidence_to_capture`, `priority_reason`, `reassessment_trigger`. Deney tasarımı, örneklem/trafik hedefi, teklif metni, MVP özellikleri ve geliştirme planı alanları bu kapsamda bulunmaz.

Birincil doğrulamada yalnız eksik bilgi raporlanır. Görüşme/ödeme/pilot ve ürün geliştirme süreçlerini daha sonra yönetici Çağlar değerlendirip planlar; rapor bunlar için uygulama önerisi üretmez.

Web boşluğu için `ResearchGapRequest` Faz 2 sözleşmesini kullanır; `parent_decision_id` ve `parent_bundle_id` zorunlu olur. Birincil doğrulama boşluğu için web sorgusu oluşturulmaz. Ek araştırma mevcut kapsam/bütçe içinde doğrulanır; otomatik yeni bütçe yaratılmaz.

## Hata ve doğrulama

Hata: `code`, `stage`, `retryable`, `message`, `details_ref`. Kodlar: invalid_evidence_bundle/cross_project_reference/stale_citation/unknown_claim/unsupported_statement/outcome_policy_violation/scope_violation/model_schema_invalid/model_timeout/budget_exhausted/cancelled.

Geçerli kanıt yetersizliği hata değildir: `Investigate More` raporu olarak döner. Geçersiz payload kullanıcıya güvenilir karar gibi sunulmaz. Şema, ID bütünlüğü, source binding ve outcome kuralı kontrolü `validation` içinde ayrı sonuçlar taşır. Başarı olasılığı veya AI self-confidence yüzdesi bu sözleşmede alan değildir.

## Yeterlilik politikası v1

[Onaylı politika](../../ortak/kanit-yeterliligi-ve-karar-kurallari.md): min_independent_examples=3, min_distinct_sources=2 ve nitel kontroller birlikte uygulanır. evidence_sufficiency çıktısı destekleyen/karşıt/belirsiz sayımları, gate_results, critical_gaps ve policy_version içerir. Erişim/alan pilotlarından gelecek diğer eşikler bu onaylı tabanın yerine geçmez.
