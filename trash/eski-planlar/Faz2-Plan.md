# Faz 2 — Araştırma Planı Üretimi

> Ortak kimlik, sözleşme, workflow, Source Registry, AI Gateway, maliyet ve gözlemlenebilirlik kuralları için `Platform-Temeli.md`; fazlar arası entegrasyon sırası için `Ust-Yonetim-Ana-Mimari-Plani.md` bağlayıcıdır.

## Amaç

Faz 1'den gelen kullanıcının onaylı **Idea Brief** verisini, Faz 3'te çalıştırılacak kaynak, sorgu ve kapsama planına dönüştürmek.

Bu faz veri toplamaz, web veya API çağrısı yapmaz ve araştırma sonucu üretmez. Yalnızca şu soruya cevap verir:

> Nerede, neyi, hangi amaçla ve hangi kapsamda araştıracağız?

## Girdi ve çıktı sınırı

### Girdi

- Faz 1'de oluşturulmuş ve kullanıcı tarafından onaylanmış Idea Brief
- Kullanıcının seçtiği araştırma modu: `standard` veya `deep_research`
- Varsa hedef pazar, ülke ve dil tercihi

Faz 1'de fikir geniş kapsamla devam ettirilmişse, bu durum araştırma planına risk/eksik bağlam olarak aktarılır.

### Çıktı

Faz 2'nin çıktısı sürümlenmiş ve şema ile doğrulanmış bir **Research Plan** olur.

```text
idea_brief_version
research_mode                 standard | deep_research
research_questions
market_scope                  global | country | language
source_plan
query_plan
search_intents
coverage_budget
known_unknowns
deep_research_recommended     true | false
scope_origins                 Her kapsam alanının user/AI kökeni
estimated_cost_envelope       sağlayıcı, fetch, token ve depolama tahmini
budget_contract               hard_limit ve soft_limit'ler
source_registry_version
plan_version
```

Bu çıktı doğrudan Faz 3'ün girdisidir.

## Seçilen mimari

Faz 2, iki katmanlı hibrit bir planlama motoru olacaktır:

```text
Onaylı Idea Brief
        ↓
AI Research Planner
        ↓
Araştırma stratejisi taslağı
        ↓
Kural tabanlı Plan Compiler
        ↓
Doğrulanmış Research Plan
        ↓
Faz 3: arama ve veri toplama
```

### Katmanların sorumlulukları

- **AI Research Planner:** Fikir bağlamını anlar; araştırma soruları, sorgu tohumları, arama niyetleri ve olası kaynak türleri önerir.
- **Plan Compiler:** AI taslağını uygulamanın çalıştırabileceği biçime dönüştürür; yalnızca izinli kaynakları seçer, kota koyar ve kuralları uygular.
- **Query Validator:** Sorgu tekrarlarını, kaynak uyumunu, dil/pazar kurallarını ve plan sınırlarını denetler.
- **Coverage Engine:** Temel araştırma niyetlerinin kapsanıp kapsanmadığını kontrol eder.

AI planlama ve bağlam kurmada güçlüdür; fakat çalıştırılabilir planın kuralları, kaynak izinleri ve maliyet sınırları uygulama tarafından kontrol edilir.

## Neden hibrit yapı seçildi?

| Alternatif | Neden seçilmedi / tercih edilmedi |
| --- | --- |
| Tamamen AI ile kaynak ve sorgu seçimi | Tutarsız kaynak seçimi, tekrar eden sorgular, platform sınırlarının aşılması ve maliyet kontrolü riski vardır. |
| Yalnızca sabit kurallar ve şablonlar | Yeni nişleri, kullanıcıların farklı problem dilini ve ürün bağlamını zayıf yakalar. |
| Hibrit yapı | Seçilen yaklaşımdır. AI bağlamı yorumlar; deterministik katman güvenilir, sınırlı ve yürütülebilir plan üretir. |

## Araştırma soruları

Araştırma planı, fikre uygun biçimde aşağıdaki soruların hangilerinin inceleneceğini belirtir:

- Bu problem gerçekten yaşanıyor mu?
- Kimler bu problemi yaşıyor?
- Kullanıcılar bugün hangi alternatifleri kullanıyor?
- Mevcut çözümlerden neden memnun değiller?
- Ödeme, fiyat veya bütçe sinyali var mı?
- Rakiplerin gözlemlenen fiyat aralığı ve paket yapısı nedir?
- Hangi farklılaşma / pazar boşluğu araştırılmalı?

Bu faz soruların cevaplarını üretmez; yalnızca kanıt arama stratejisini oluşturur.

## Kaynak seçme modeli

AI kaynak önerebilir; ancak nihai kaynak seçimi **Source Registry** üzerinden yapılır. Registry, Faz 3'te aktif olacak kaynakların izinli ve teknik olarak kullanılabilir kataloğudur.

Her kaynak için aşağıdaki alanlar tanımlanır:

```text
source_id
source_type
eligible_product_types
supported_search_intents
language_or_market_coverage
access_method
cost_tier
risk_or_restrictions
enabled_status
```

### Ürün tipine göre kaynak eğilimleri

- **Agent / developer tool:** GitHub, Hacker News, Product Hunt, teknik topluluklar
- **Mobil uygulama:** App Store, Google Play, Reddit, rakip uygulama sayfaları
- **Web SaaS:** Rakip siteleri, pricing sayfaları, Product Hunt, review platformları
- **Consumer product:** Reddit, uygulama mağazaları, forumlar ve topluluklar

Bu liste kesin entegrasyon listesi değildir. Hangi kaynağın API, crawler veya lisanslı entegrasyonla kullanılacağı Faz 3'te kararlaştırılacaktır.

## Sorgu üretme modeli

Araştırma planı yalnızca bir anahtar kelime listesi üretmez. Her sorgu belirli bir **arama niyetine** bağlı olmalıdır.

```text
problem_demand          Kullanıcıların problemi veya ihtiyacı nasıl anlattığı
existing_alternatives   Bugün hangi ürün, yöntem veya workaround kullanıldığı
dissatisfaction         Mevcut çözümlerle ilgili şikâyet ve eksikler
pricing_willingness     Fiyat, bütçe veya ödeme isteği sinyalleri
use_case                Kullanım bağlamı ve gerçek iş akışı
competitor_discovery    Doğrudan ve dolaylı rakip adayları
```

`pricing_willingness` niyeti iki ayrı alt niyete derlenir:

- `observed_market_pricing`: rakip fiyatları, paketler ve görünür ticari model; ikincil araştırmayla incelenebilir.
- `stated_wtp_weak_signal`: kullanıcıların açık fiyat ifadeleri; yalnızca zayıf beyan sinyalidir, gerçek ödeme davranışı kabul edilmez.

Gerçek ödeme isteği, fiyat toleransı veya satın alma davranışı ikincil internet araştırmasıyla doğrulanmış sayılamaz. Bu boşluk Faz 7'de birincil doğrulama aksiyonu üretir.

### AI'ın ürettiği sorgu tohumları

```text
product_terms
user_terms
job_or_problem_terms
pain_language_terms
alternative_terms
competitor_category_terms
locale_or_language_terms
negative_terms
```

### Deterministik Query Compiler kuralları

1. Sorgu tohumlarını niyet ve kaynak özelindeki şablonlarla birleştirir.
2. Aynı veya çok benzer sorguları birleştirir ya da eler.
3. Kaynakla uyumsuz sorguları eler.
4. Her araştırma niyetinin kapsanıp kapsanmadığını kontrol eder.
5. Kaynak ve sorgu başına kota uygular.
6. Kullanıcının dil ve pazar kapsamına uygun sorguları seçer.
7. Her sorguya amaç, öncelik, kaynak, dil ve niyet etiketi ekler.

### Query expansion yaklaşımı

İlk plan, AI'ın bağlamdan çıkardığı kontrollü sorgu tohumlarıyla oluşturulur. İlk arama sonuçlarından otomatik kelime ekleme bu fazda yapılmaz.

Sonuç tabanlı query expansion, Faz 3'te ancak kalite eşiği ve konu kayması kontrolleri ile ayrıca değerlendirilecektir. İlk sonuçların ilgisiz olabileceği durumlarda pseudo-relevance feedback, konu dışı terimler ekleyerek arama kalitesini düşürebilir.

## Kapsam ve bütçe yönetimi

Research Plan her araştırma niyeti için aşağıdakileri içermelidir:

- öncelik seviyesi
- seçilen kaynaklar
- planlanan sorgu sayısı
- kaynak/sorgu başına sonuç bütçesi
- dil ve pazar kapsamı
- veri eksik kalırsa uygulanacak fallback yaklaşımı

Bu bütçe, Faz 3'te maliyet, süre ve kaynak limitlerini kontrol etmek için kullanılır. Faz 2'nin görevi henüz arama çalıştırmak değildir.

Plan Compiler her plan için çağrı sayısı, ücretli arama maliyeti, beklenen fetch hacmi, çıkarılacak metin/token hacmi, model kademeleri ve depolama için bir `estimated_cost_envelope` üretir. Bu tahmin yürütme öncesi görünürdür; gerçekleşen maliyet Faz 3–6 tarafından aynı maliyet defterine yazılır. Maliyet yönetimi kapsamı azaltmak için değil, kontrolsüz tüketimi ve yanlış model yönlendirmesini önlemek için kullanılır.

## Kapsam kökeni ve hipotez güvenliği

- Faz 1'deki `ai_hypothesis` alanları kullanıcı onayı yoksa sorgu tohumu olamaz.
- Kullanıcı tarafından seçilmiş AI önerileri `scope_origin: ai_suggested_user_confirmed` olarak korunur.
- Plan, her araştırma sorusunun hangi Idea Brief alanından türetildiğini taşır.
- Plan Compiler, doğrulanmamış hipotezin zorunlu kapsam haline gelmesini reddeder.
- Geniş fikirle devam edilmesi durumunda sistem kapsamı kendiliğinden daraltmaz; alternatif segmentleri ayrı araştırma hipotezleri olarak, birbirine karıştırmadan planlar.

## Source Registry tek sahiplik kararı

Source Registry şeması Faz 2 veya Faz 3 içinde bağımsız olarak sahiplenilmez. Tek kanonik sözleşme `Platform-Temeli.md` ve ortak contracts paketindedir. Faz 2 registry'yi yalnızca okur ve kaynak planlar; Faz 3 aynı sürümü yürütür. Plan çıktısı `source_registry_version` taşımak zorundadır.

## Standard ve Deep Research ilişkisi

- **Standard:** Kısıtlı kaynak, sorgu ve süre bütçesiyle temel kanıt toplamaya hazırlanır.
- **Deep Research:** Kullanıcının premium tercihiyle daha geniş kaynak, sorgu ve keşif bütçesi oluşturur.
- Sistem, standart planın yetersiz kalma ihtimalini gösterebilir ve `deep_research_recommended` alanını işaretleyebilir.
- Sistem premium araştırmayı otomatik başlatmaz; seçim kullanıcıya aittir.

Deep Research, standart araştırmanın yerine geçen bağımsız bir sistem değil; aynı araştırma planı yapısının daha geniş kapsamlı sürümüdür.

## Kullanıcı deneyimi

- Faz 1 brief'i onaylandıktan sonra Research Plan otomatik üretilir; ayrıca bir onay turu zorunlu değildir.
- Kullanıcı araştırma başlarken planın kısa özetini görebilmelidir: seçilen araştırma alanları, kaynak türleri, dil/pazar kapsamı ve mod.
- Kullanıcı yalnızca hedef pazar/dil veya araştırma modunu değiştirebilmelidir.
- Kullanıcının yaptığı değişiklik yeni bir plan sürümü oluşturur.
- Faz 2'nin ayrıntılı iç sorgu listesi kullanıcıyı yormamalıdır; ancak şeffaflık için görüntülenebilir olmalıdır.

## Teknik yaklaşım

Faz 1 ile uyumlu temel yapı korunur:

- Uygulama yapısı: TypeScript tabanlı modüler monolith
- Arayüz: Next.js
- Veri tabanı: PostgreSQL
- AI erişimi: Tek LLM Gateway / provider adapter
- Şema doğrulama: Zod ve JSON Schema
- Plan/prompt sürümleme: veritabanında saklanır

Ek modüller:

```text
Research Planner
Source Registry
Query Compiler
Query Validator
Coverage Engine
```

## AI çağrısı sözleşmesi

- AI çağrısının tek görevi, Idea Brief'i araştırma stratejisi taslağına dönüştürmektir.
- Kullanıcı brief'i, sistem talimatları ve çıktı şeması ayrı alanlarda işlenir.
- AI yalnızca şemalı çıktı döndürür.
- Şema denetiminden geçmeyen plan yürütülebilir sayılmaz; yeniden deneme veya güvenli hata akışı uygulanır.
- Prompt sürümü, model sürümü, brief sürümü ve plan sürümü birlikte saklanır.
- AI bu fazda dış araç, web, API veya kullanıcı hesabına erişmez.

## Hata, güven ve izlenebilirlik

- Kullanıcı girdisi ve AI üretimi güvenilmeyen veri olarak ele alınır; uygulama kurallarını değiştiremez.
- Kullanıcı geniş fikirle devam etmeyi seçmişse, plan `known_unknowns` alanında bu belirsizliği taşır.
- Registry'de etkin olmayan, izinli olmayan veya teknik erişimi belirsiz kaynaklar plana eklenmez.
- Query Validator geçmeyen sorgular Faz 3'e gönderilmez.
- Her planın hangi brief, prompt, model, registry sürümü ve kurallarla üretildiği kayıt altına alınır.

## Bilinçli olarak kapsam dışı bırakılanlar

- Web, API, sosyal platform veya crawler çağrısı yapmak
- Gerçek rakip, fiyat, yorum veya pazar verisi toplamak
- Araştırma kanıtlarını analiz etmek veya özetlemek
- Sonuçlara göre sorguyu otomatik genişletmek
- Build, Modify, Kill veya Investigate More kararı üretmek
- Gerçek ödeme isteğini internetten doğrulanabilir bir araştırma hedefi gibi işaretlemek
- RAG / vektör veritabanı kullanmak
- Multi-agent mimarisi kullanmak
- Kullanıcı onayı olmadan premium Deep Research başlatmak
- Faz 3 entegrasyonlarının teknik ayrıntılarını kesinleştirmek

## Ölçümler

- Plan başına kapsanan araştırma niyeti oranı
- Tekrarlı veya elenen sorgu oranı
- Kaynak/ürün tipi uyumsuzluğu oranı
- Kullanıcının pazar/dil veya mod değiştirme oranı
- Faz 3 sonrasında yetersiz kaynak/sorgu nedeniyle oluşturulan yeniden plan oranı
- Standard araştırmadan Deep Research'e geçiş oranı
- Şema doğrulama hatası ve yeniden deneme oranı

## Faz 2 kabul kriterleri

- Onaylı bir Idea Brief için şemalı bir Research Plan üretilebilmelidir.
- Plan, araştırma sorularını, arama niyetlerini, kaynak türlerini, sorguları ve kapsam bütçesini içermelidir.
- Her sorgu en az bir araştırma niyetine ve izinli bir kaynak türüne bağlı olmalıdır.
- Kullanıcı geniş fikirle devam etmişse plan belirsizliği görünür biçimde taşımalıdır.
- Kullanıcı hedef pazar/dil veya modu değiştirdiğinde yeni plan sürümü oluşmalıdır.
- Geçersiz AI çıktısı veya izinli olmayan kaynak, Faz 3'e aktarılamamalıdır.
- Planın oluşturulması hiçbir dış kaynak araştırması başlatmamalıdır.
- Her plan yürütme öncesi maliyet zarfı, hard budget sınırları ve Source Registry sürümü içermelidir.
- Onaysız AI hipotezleri sorgu planına girememelidir.

## Faz 2 çıkışı

Kaynaklara ve arama araçlarına aktarılmaya hazır; denetlenebilir, sürümlenmiş ve kullanıcı tercihlerini içeren bir Research Plan.
