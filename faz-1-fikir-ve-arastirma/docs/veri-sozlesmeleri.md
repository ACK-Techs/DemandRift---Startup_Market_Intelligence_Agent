# Veri sözleşmeleri — taslak

Bu alanlar uygulanacak sözleşmenin tasarımıdır; henüz API ya da doğrulayıcı implementasyonu değildir. Ortak zarf [ortak/veri-sozlesmeleri.md](../../ortak/veri-sozlesmeleri.md) ile birlikte sürümlenir.

## ResearchPlan

| Alan | Gereklilik |
|---|---|
| `schema_version`, `project_id`, `research_id` | Zorunlu ortak kimlik ve sözleşme sürümü |
| `status` | `draft`, `needs_clarification`, `ready` veya `failed`; yalnız `ready` yürütülebilir |
| `versions` | `brief`, `plan`, `taxonomy`, `source_registry`, `prompt` ve `model`; kullanılan sürümler değiştirilemez |
| `brief` | Orijinal ve normalize fikir; ürün, müşteri, problem, pazar, dil, kısıtlar; alan kökenleri ve kullanıcının devam seçimi |
| `categories` | `primary`, `secondary`, `modifiers`, `classification_status`, `rationale`; ana kategori eşleşmiyorsa null ve `unmatched` |
| `intents` | Araştırma sorusu, amaç kimliği, öncelik, brief dayanağı, gereken kanıt/alan, ikincil/birincil doğrulama ayrımı |
| `source_plan` | Seçilen kaynaklar, yetenek/yüzey, alınacak alanlar, niyet bağları, bağımsızlık grubu, erişim sınıfı, sınırlar ve fallback |
| `query_plan` | Kaynak ve niyet bağlı sorgular, dil/pazar, terim kökeni, öncelik, beklenen alanlar ve limitler |
| `budget` | Derinlik profili, toplam ve kaynak başına sert sınırlar; yumuşak hedefler, tahmini maliyet, zaman ve erken durdurma kuralları |
| `unknowns` | Bilinmeyen/çelişkili alan, etkisi, atlandı mı, nasıl giderilebilir; varsayım kimlikleri |

`brief` alanlarının her biri `value`, `state` (`known`, `inferred`, `missing`, `conflicting`), `origin` ve varsa `assumption_id` taşır. Kökenler `user_stated`, `user_confirmed`, `ai_inferred`, `ai_hypothesis` olarak ayrılır. Kullanıcı bir AI önerisini onaylarsa önceki köken denetim izinde korunur. `continue_with_unknowns` açık kullanıcı tercihini kaydeder.

## Araştırma amaçları

Çekirdek amaçlar `problem_demand`, `existing_alternatives`, `dissatisfaction`, `use_case`, `competitor_discovery`, `observed_market_pricing`, `stated_wtp_weak_signal` olarak ayrılır. Gerekli bağlamlarda `technical_feasibility`, `regulatory_constraints`, `adoption_signals` eklenir. Her amaç her üründe zorunlu değildir; hariç tutmanın gerekçesi tutulur. Görünür fiyat, kullanıcının öderim beyanı ve gerçek ödeme davranışı birbirine çevrilemez.

## Sorgu kaydı

Her kayıt `query_id`, `intent_id`, `source_id`, `query_text`, `query_kind`, `language`, `market`, `priority`, `expected_fields`, `origin_refs`, `limits` içerir. `query_kind`: `local_index`, `fulltext`, `site_search`, `opensearch` veya `api`. Uzak yöntemlerde doğrulanmış `surface_id` ve desteklenen parametreler; yerel yöntemlerde indeks/artefakt sürümü gerekir. Modelin keyfi URL üretmesi geçerli yüzey tanımı sayılmaz.

## Kaynak yetenek kaydı

Ortak Source Registry kaydına bağlı profil `source_id`, `family`, `allowed_categories`, `supported_intents`, `available_fields`, `surfaces`, `locale_coverage`, `independence_group`, `access_method`, `policy_status`, `enabled_status`, `rate_limits`, `cost_class`, `freshness`, `retention`, `pii_notes`, `access_snapshot_ref` taşır. `candidate_only`, etkin ve erişilemez kaynaklar ayrılır. Geçmiş `ok` yanıtı, bugün alan veya izin doğrulaması yapıldığı anlamına gelmez.

## Geçiş kontrolleri

- Her sorgu mevcut niyet, kaynak ve brief dayanağına bağlıdır; limitleri plan bütçesini aşamaz.
- Onaysız `ai_hypothesis` yeni nişin kesin sorgu tohumu olamaz.
- Kullanıcı pazar belirtmemişse Türkiye/global varsayımı kesin gerçek olarak eklenemez; bilinmeyen veya görünür tercih olur.
- Erişim belirsiz/engelli kaynak yürütülebilir plana girmez; kapsama boşluğu ve uygun fallback taşınır.
- `ready` plan şeması, kaynak sorgu uygunluğu ve sürüm doğrulamasını geçmiştir; bu, araştırmanın başarılı olduğu anlamına gelmez.
- `invalid_input`, `schema_invalid`, `category_unmatched`, `no_eligible_source`, `provider_error`, `budget_invalid` hata kodları ayrı tutulur; hata detayına sır veya ham özel veri yazılmaz.
