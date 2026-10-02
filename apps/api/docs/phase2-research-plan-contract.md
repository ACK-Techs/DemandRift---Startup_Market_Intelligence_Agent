# Faz 1 stateless plan önizleme API sözleşmesi — v1.1

Bu belge, `apps/api` içindeki ilk ResearchPlan uygulamasının sözleşme sınırıdır.
Aktif Faz 1 planı üretir; web crawl, kaynak çağrısı, Gemini çağrısı veya
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
| `POST` | `/api/v1/research/plans` | Doğrulanmış bir Idea Brief için, dış çağrı yapmadan sürümlü ResearchPlan taslağı üretir. |
| `GET` | `/api/v1/research/source-plans/{category}` | AS-01 sağlık kaydına göre kategori → kaynak → script → alan eşlemesini döndürür; script çalıştırmaz. |
| `GET` | `/api/v1/research/initial-runs` | BT-02 için 10 fikir × net/eksik/yanlış-etiket olmak üzere 30 senaryoluk manifest ve aday kaynakları döndürür; canlı sorgu veya kaynak çalıştırmaz. |
| `POST` | `/api/v1/research/run-records/validate` | Gerçek sorgudan sonra oluşan kaynak kaydını doğrular; kayıt yazmaz ve sorgu çalıştırmaz. |

`POST /api/v1/research/plans` yalnız planlama kontratını uygular. Kaynak
çalıştırma aktif Faz 2'nin sorumluluğudur ve bu endpointten başlatılamaz.

`GET /api/v1/research/source-plans/{category}` BT-02'nin ilk eşleme yüzeyidir.
Kaynak satırları kanonik bundled Source Registry üzerinden, gerçek
`KAYNAK-SAGLIK.csv` dosyasındaki 2026-09-27 ölçümünü taşır.
`source_registry_version` registry içeriğinin SHA-256 digestine bağlıdır;
`last_measured_at` ilgili gözlemin tarihidir. Eski 2026-09-24 AS-01 hardcoded
görünüm registry history kaydında korunur; daha yeni doğrulama gibi sunulmaz.
`eligible_for_first_run` yalnız tarihsel deneme adaylığıdır; bütün güncel runtime
profilleri kapalıdır. Kaynak güncelliği, alan/yüzey, izin, bütçe ve worker
yetkisi her üretim koşusunda ayrı kabul gerektirir. Katalogdaki doğrulanmış alan
etiketi tam yüzey/tarih/hash bağı içermediğinde bu endpointin
`verified_fields` listesine geçirilmez; beklenen alanlar bundan ayrıdır.
Ayrıntılar [Source Registry sözleşmesinde](source-registry.md).

`GET /api/v1/research/initial-runs` bir sonuç API'si değildir. Her satırın
`execution_status` değeri başlangıçta `not_run` olur; `raw_artifact_refs` ve
`feedback_ids` boş döner. Kaynak sağlık durumu ve uygunluğu planlama bilgisidir;
gerçek erişim, sayım, artefakt ve hata kaydı ancak yetkili runner gerçekten
çalıştıktan sonra eklenebilir. Böylece bot koruması, JS kabuğu veya robots/policy
kısıtı "sonuç yok" ya da başarılı çalışma olarak gizlenmez.

`POST /api/v1/research/run-records/validate`, canlı veya manuel çalıştırmadan
gelen bir sonucu kaydetmeden önce sözleşmeye karşı denetler. Başarılı kayıt;
ham artefakt referansı, dönen alanlar, sıfırdan büyük fetched sayısı ve insan
etiketi taşımak zorundadır. Kaynak erişilemez/challenge/policy engelli ise
başarı iddiası yerine erişim durumu ve hata açıklaması zorunludur. Bu endpoint
veri tabanına yazmaz, kaynak çağrısı veya model çağrısı yapmaz.

Her kaynak kaydı, yüzeyi `access_method` ile ve artefaktın güncelliğini
`artifact_origin` ile ayrı taşır. Geçerli yüzeyler `api`,
`permitted_browser`, `manual_export`, `ic_sayfa`, `root_html`, `sitemap_xml`,
`common_crawl_warc` ve `archive_copy` değerleridir. `artifact_origin` yalnız
`live_capture` veya `archive_copy` olur. Common Crawl WARC ve doğrudan arşiv
kopyası, mutlaka `archive_copy` olarak işaretlenir; arşiv sonucu canlı tarama
sonucu gibi gösterilemez.

Kayıt, manifestteki `scenario_id` ile `source_id` eşleşmesine ve o senaryonun
izin verdiği script yoluna bağlıdır. `success` yalnız `eligible_for_execution`
olan bir kaynakta kabul edilir; challenge, JS kabuğu veya policy engeli bulunan
adaylar ancak açık erişim durumu ve hata bilgisiyle kaydedilebilir.

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

Her stateless önizleme: research_plan_id, plan_fingerprint, plan_version=1,
idea_brief_id/version, primary_category, add_on_packages, research_mode,
research_questions, search_intents, market_scope, language_scope,
source_family_hints, source_registry_version, budget_contract, known_unknowns,
scope_origins ve assumption_ids döndürür. Source/query yürütme planı henüz yoktur;
known_unknowns bunu açıkça bildirir. Bu endpoint kalıcı/onaylı ürün planı değildir.

Plan fingerprint'i doğrulanmış isteğin tamamının canonical JSON SHA-256'sıdır.
Mapping anahtarları ve user_confirmed_fields kümesi sıralanır; diğer dizilerin
sırası korunur. Pazar, dil, ek paket, bütçe, köken/onay veya kapsam değişimi
başka fingerprint ve UUID üretir. Aynı doğrulanmış snapshot aynı kimliği üretir.
Non-finite bütçe ve bilinmeyen request alanları reddedilir.

Bu endpoint DB yazmaz; plan_version=1 yalnız önizleme sürümüdür. Kalıcı UUID,
artan immutable plan sürümleri, source/query/onay snapshot'ı ve start
idempotency ayrı BE-02/BE-07/BE-04 teslimlerinde uygulanır. İçerik fingerprint'i
idempotency anahtarı veya run başlatma yetkisi yerine kullanılamaz.

## Test kabulü

- Sağlanan yedi ana kategori ve sekiz ek paket eksiksiz döner.
- Geçersiz kategori veya tekrarlanan ek paket 422 ile reddedilir.
- `needs_clarification` statüsündeki brief plan üretemez.
- Onaysız `ai_hypothesis` kapsam girdisi plana geçemez.
- `standard` ve `deep_research` dışında modlar; geçersiz/non-finite bütçe reddedilir.
- Endpointin testleri herhangi bir ağ, Gemini veya secret gerektirmez.

## Sonraki bağımlılıklar

Ayselin kaynak ailelerinin önceliklerini ve rapor alanlarını kesinleştirdiğinde
`source_plan` ile `query_plan` ayrıntılandırılır. Ayşe'nin ürün/API tüketici
ihtiyaçları netleştiğinde kullanıcıya gösterilecek plan özeti alanları ayrı bir
uyumluluk testiyle eklenir.
