# Faz 2 ResearchPlan API sözleşmesi — taslak v1

Bu belge, `apps/api` içindeki ilk ResearchPlan uygulamasının sözleşme sınırıdır.
Faz 2 yalnızca plan üretir; web crawl, kaynak çağrısı, Gemini çağrısı veya
araştırma sonucu üretmez.

## Kanonik kategori girdisi

Kategori kataloğu `KILAVUZ.md` içindeki ürün tipi temelli araştırma tasarımına
dayanır. İlk API sürümünde aşağıdaki ana kategoriler desteklenir:

- `mobil-uygulama`
- `b2b-web-yazilimi`
- `gelistirici-araci`
- `eklenti-entegrasyon`
- `yapay-zeka-urunu`
- `oyun`
- `yerel-hizmet`

Ek araştırma paketleri ana kategori değildir; seçilen ana kategoriye eklenir:
`saglik`, `fintech`, `egitim`, `gayrimenkul`, `seyahat`, `yeme-icme`,
`regule-sektor`, `turkiye-pazari`.

Bir kategori, kaynak paketi veya kanıt ihtiyacını değiştirmiyorsa yeni bir
kategori olarak eklenmez. Bir fikir birden fazla kategoriye bağlanırsa birincil
kategori ve ek paketler ayrı görünür; ilişkili fakat farklı iki ana kategori
tek etiket altında birleştirilmez.

## İlk HTTP yüzeyi

| Yöntem | Yol | Amaç |
| --- | --- | --- |
| `GET` | `/health` | Süreç canlılığı; araştırma hazırlığını göstermez. |
| `GET` | `/api/v1/research/categories` | Kanonik ana kategori ve ek paket kataloğunu döndürür. |
| `POST` | `/api/v1/research-plans` | Doğrulanmış bir Idea Brief için, dış çağrı yapmadan sürümlü ResearchPlan taslağı üretir. |
| `GET` | `/api/v1/research/source-plans/{category}` | AS-01 sağlık kaydına göre kategori → kaynak → script → alan eşlemesini döndürür; script çalıştırmaz. |

`POST /api/v1/research-plans` yalnız planlama kontratını uygular. Kaynak
çalıştırma Faz 3'ün sorumluluğudur ve bu endpointten başlatılamaz.

`GET /api/v1/research/source-plans/{category}` BT-02'nin ilk eşleme yüzeyidir.
Kaynak satırları 2026-09-24 AS-01 sağlık ölçümünü taşır. `eligible_for_first_run`
değeri yalnız ilk deneme uygunluğunu anlatır; kaynak güncelliği ve izin durumu
her gerçek koşuda yeniden doğrulanır.

## Plan girdisi

İlk istek aşağıdaki alanları taşır:

```text
idea_brief_id
idea_brief_version
product_type
clarity_status
field_origins
assumption_ids
research_mode: standard | deep_research
market_scope
language_scope
primary_category
add_on_packages
source_registry_version
budget_contract
```

Kurallar:

1. `idea_brief_version` pozitif sürüm olmalıdır.
2. `clarity_status` yalnız `ready` veya `broad_but_continue` ise plan üretilebilir.
3. `ai_hypothesis` kökenli bir alan kullanıcı tarafından onaylanmamışsa kaynak,
   sorgu veya zorunlu kapsam girdisi olamaz.
4. `deep_research` yalnız kullanıcının seçimiyle kabul edilir; API varsayılanı
   `standard`dır.
5. `source_registry_version` ve `budget_contract` plan snapshot'ında zorunludur.

## Plan çıktısı

Her plan şunları taşır:

```text
research_plan_id
plan_version
idea_brief_id/version
primary_category + add_on_packages
research_mode
research_questions
search_intents
market/language scope
source_plan (yalnız referans; kaynak çalıştırmaz)
query_plan (yalnız taslak; sorgu çalıştırmaz)
coverage_budget
known_unknowns
scope_origins
source_registry_version
estimated_cost_envelope
budget_contract
```

İlk uygulama kalıcı veri tabanı yazımı yapmaz; bu yüzden dönen plan,
deterministik sözleşme doğrulaması için geçici bir taslaktır. PostgreSQL ile
kalıcı plan sürümlemesi ayrı bir work item'dır.

## Test kabulü

- Sağlanan yedi ana kategori ve sekiz ek paket eksiksiz döner.
- Geçersiz kategori veya tekrarlanan ek paket 422 ile reddedilir.
- `needs_clarification` statüsündeki brief plan üretemez.
- Onaysız `ai_hypothesis` kapsam girdisi plana geçemez.
- `standard` dışındaki modlar ve geçersiz bütçe sınırları reddedilir.
- Endpointin testleri herhangi bir ağ, Gemini veya secret gerektirmez.

## Sonraki bağımlılıklar

Ayselin kaynak ailelerinin önceliklerini ve rapor alanlarını kesinleştirdiğinde
`source_plan` ile `query_plan` ayrıntılandırılır. Ayşe'nin ürün/API tüketici
ihtiyaçları netleştiğinde kullanıcıya gösterilecek plan özeti alanları ayrı bir
uyumluluk testiyle eklenir.
