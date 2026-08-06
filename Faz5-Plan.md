# Faz 5 — Kontrollü Deep Research Politikası ve Araştırma Boşluğu Döngüsü

> Faz 5 ikinci bir araştırma altyapısı kurmaz. Ortak workflow, Policy Gateway, maliyet ve Source Registry için `Platform-Temeli.md`; Faz 3–4–6 döngüsü için `Ust-Yonetim-Ana-Mimari-Plani.md` bağlayıcıdır.

## Amaç

İlk Faz 3–4–6 turunda ölçülen gerçek kanıt boşluklarını, kullanıcının araştırma modu ve bütçe sözleşmesine uygun biçimde kontrollü olarak kapatmak.

Deep Research, serbest bir AI browser agent veya tek seferlik AI rapor cevabı değildir. AI'ın araştırma stratejisi önerdiği; uygulamanın ise izinli connector'lar, bütçe ve politika kurallarıyla kanıt topladığı kontrollü bir araştırma döngüsüdür.

> Faz 5, kanıt boşluğu odaklı, karşıt kanıt da arayan, tek agent'lı ve policy-gated bir Deep Research orkestrasyonudur.

## Faz sınırı ve mimari statüsü

Faz 5 ürün akışında ayrı bir yetenek alanıdır; fakat kod ve altyapıda ikinci bir araştırma pipeline'ı değildir. Faz 3'ün `Evidence Acquisition` altyapısını `gap_driven` tetikleyiciyle yeniden kullanır. Faz 5'in kendine ait connector, crawler, kuyruk, provenance veya bütçe uygulaması bulunmaz.

### Girdi

- Faz 1'den gelen onaylı Idea Brief
- Faz 2'nin Research Plan'ı
- Faz 3'ün Research Run kayıtları
- Faz 4'ün normalize veri seti, duplicate ilişkileri ve kalite bayrakları
- Faz 6'nın Evidence Eligibility/coverage değerlendirmesinden üretilen yapısal `ResearchGapRequest`
- Kullanıcı araştırma modu, pazar/dil tercihi ve Deep Research onayı
- Source Registry ve connector politikalarının ilgili sürümü

### Çıktı

- Ek ResearchRun ve connector görevleri
- Yeni ham artefact'lar ve Faz 4'ten geçmiş normalize kayıtlar
- Araştırma boşluğu kapanma durumu
- Deep Research trace, bütçe kullanımı ve durdurma nedeni

Bu faz nihai araştırma raporu, rakip analizi, market gap veya karar sonucu üretmez. Bunlar Faz 6 ve Faz 7'nin sorumluluğudur.

## Ne zaman çalışır?

Faz 5 yalnızca Faz 6 yapısal bir `secondary_research_gap` ürettiğinde çalışır. Kullanıcının modu davranışı belirler:

1. `standard`: Gap Auditor kritik boşluğu görünür öneriye dönüştürür; maliyetli/geniş ek araştırma kullanıcı onayı olmadan başlamaz.
2. `deep_research`: önceden onaylanmış BudgetContract ve Source Policy içinde gap-driven turlar otomatik yürüyebilir; yeni bütçe veya yeni veri erişim sınıfı gerekiyorsa yeniden onay alınır.

Premium seçim Faz 2'de daha geniş ilk plan ve bütçe de oluşturabilir; fakat Faz 5'in ek turları yine Faz 6'nın ölçülmüş boşluğuna dayanır. AI sırf bütçe var diye amaçsız ek arama başlatamaz.

## Seçilen mimari

```text
Faz 6 coverage ve kanıt boşluğu değerlendirmesi
        ↓
Gap Auditor
        ↓
AI Research Controller
        ↓
Policy Gateway
        ↓
Faz 3 connector'ları
        ↓
Faz 4 normalizasyonu
        ↓
Faz 4 üzerinden yeniden Faz 6'ya dönen genişletilmiş kanıt seti
```

### Bileşen sorumlulukları

| Bileşen | Sorumluluk |
| --- | --- |
| Gap Auditor | Araştırma niyeti, kaynak çeşitliliği, güncellik, kalite ve başarısız kaynak denemelerine göre boşlukları deterministik biçimde tespit eder. |
| AI Research Controller | Araştırma hipotezi, karşıt hipotez, sorgu ve kaynak önerisi üretir. |
| Policy Gateway | Kaynak, connector, kota, maliyet, kullanıcı onayı ve erişim kuralını bağımsız olarak doğrular. |
| Research Orchestrator | Onaylanan arama/fetch görevlerini Faz 3 altyapısında yürütür. |
| Evidence Store | Faz 4'ten gelen normalize veri setini ve coverage durumunu sağlar. |
| Research Trace | Her aksiyonun kullanıcıya gösterilebilir denetlenebilir özetini saklar. |

AI'ın connector'lara, API anahtarlarına veya doğrudan internete erişimi yoktur. Tüm dış erişim Policy Gateway ve Research Orchestrator üzerinden yürür.

`Research Orchestrator`, `Evidence Store`, `Research Trace` ve `Budget Controller` ortak Platform/Faz 3 bileşenleridir; Faz 5 bunların ikinci kopyasını oluşturmaz. Faz 5'e özgü kod yalnızca Gap Auditor, AI Research Controller ve gap policy kurallarıdır.

## Gap Auditor

Deep Research ihtiyacı AI'ın sezgisine göre belirlenmez. Gap Auditor, her araştırma niyeti için aşağıdaki sinyalleri değerlendirir:

- yeterli sayıda bağımsız kaynak var mı,
- kaynaklar güncel mi,
- bulunan içerikler duplicate/repost mu,
- kaynak erişilemedi mi yoksa gerçekten sonuç mu bulunmadı,
- kritik araştırma sorusu cevapsız mı,
- kanıt tek bir platformdan mı geliyor,
- kalite bayrakları nedeniyle kullanılabilir içerik az mı.

Örnek çıktı:

```text
gap_type: insufficient_independent_evidence
research_intent: dissatisfaction
severity: high
reason: "Yalnızca iki sonuç bulundu; ikisi de aynı kaynakta."
eligible_sources: [reddit, X, YouTube, web_search]
```

Gap Auditor bir karar veya pazar yorumu üretmez; yalnızca araştırma kapsamındaki eksikliği tanımlar.

## AI Research Controller

Tek, kontrollü bir AI controller kullanılır. Multi-agent mimarisi bu fazın gereksinimi değildir.

### AI'ın yapabildiği işler

- kanıt boşluğunu ve araştırma amacını anlamak,
- araştırılacak hipotez ve karşıt hipotez önermek,
- alternatif anahtar kelimeler ve kullanıcı dili varyantları üretmek,
- hedef pazara göre dil/sorgu varyantları önermek,
- yeni kaynak aileleri önermek,
- araştırma hareketlerini önceliklendirmek,
- durdurma koşulunun oluşup oluşmadığını önermek.

### AI'ın yapamadığı işler

- doğrudan internete veya rastgele URL'lere erişmek,
- Source Registry dışı araç ya da kaynak kullanmak,
- browser'da hesap açmak, giriş yapmak veya form doldurmak,
- e-posta, mesaj, ödeme veya dış sistem yazma işlemi yapmak,
- kota, bütçe veya connector yetkisini artırmak,
- kaynak içeriğindeki talimatları uygulamak,
- bulguyu gerçek kabul etmek, rapor yazmak veya nihai karar vermek.

## Karşıt kanıt araştırması

Deep Research, kullanıcı fikrini doğrulayan içerik toplamaya odaklanmamalıdır. Her kritik araştırma hipotezi için destekleyici ve karşıt araştırma yönü üretilir.

```text
Destekleyici:
"people struggle with X"
"alternatives to X"

Karşıt:
"why X failed"
"problems with X product"
"do users need X"
"why people do not pay for X"
```

Bu yaklaşım confirmation bias riskini azaltır ve ilerideki Build / Modify / Kill kararının daha güvenilir olmasını sağlar.

## Deep Research döngüsü

```text
1. Gap Auditor kritik boşlukları çıkarır.
2. AI en yüksek değerli araştırma adımlarını önerir.
3. Policy Gateway her öneriyi doğrular.
4. Faz 3 connector'ları çalışır.
5. Faz 4 yeni veriyi normalize eder.
6. Faz 6 claim, cluster, coverage ve karşıt kanıt analizini yeni veriyle tekrar çalıştırır.
7. Coverage ve bağımsız kanıt sayısı yeniden ölçülür.
8. Gerekirse kontrollü yeni tur başlar.
9. Durdurma koşulu oluşunca Deep Research tamamlanır.
```

AI'ın her turdaki çıktısı şema ile doğrulanır:

```text
research_gap_id
hypothesis
counter_hypothesis
proposed_queries
proposed_sources
expected_evidence_type
expected_value
cost_estimate
stop_condition
```

`hypothesis` ve `counter_hypothesis` kanıtlanmış bilgi değildir; yalnızca araştırma yönüdür.

## Sorgu ve kaynak önceliklendirme

AI aday sorgu ve kaynak önerir. Nihai seçim deterministik olarak yapılır.

```text
next_query_score =
gap_severity
× expected_coverage_gain
× source_fit
× source_independence
× freshness_potential
- cost_penalty
- redundancy_penalty
```

İlk sürümde puanlar kural tabanlı ve açıklanabilir kalır.

- `gap_severity`: Gap Auditor'dan gelir.
- `expected_coverage_gain`: seçilen niyet için beklenen yeni kapsama katkısıdır.
- `source_fit`: Source Registry'nin ürün tipi/niyet uyumudur.
- `source_independence`: mevcut kanıttan bağımsız kaynak ailesi olma değeridir.
- `freshness_potential`: güncel sonuç getirme olasılığıdır.
- `cost_penalty`: sorgu, API, crawl veya lisans maliyetidir.
- `redundancy_penalty`: aynı kaynak/sorgu/sonuç kümesine tekrar yaklaşma riskidir.

AI, kullanıcı dili ve hedef pazar için sorgu varyantı; destekleyici ve karşıt sorgular; farklı kullanıcı ifadeleri önerir. Sistem bunları Query Validator, Source Registry ve bütçe kurallarıyla denetler.

Sonuçlardan otomatik query expansion ancak kontrolle uygulanabilir:

- yeni sorgu tekrar, kaynak uyumu ve bütçe açısından doğrulanır,
- yalnızca yüksek kaliteli/uygun sonuçlardan türetilen adaylar değerlendirilir,
- konu kayması riskinde yeni sorgu çalıştırılmaz,
- ilk sürümde sonuç tabanlı genişletme zorunlu değildir.

## Durdurma koşulları

Deep Research aşağıdaki koşullardan biri oluştuğunda durur:

- kritik araştırma boşlukları hedef kapsama ulaştı,
- son tur anlamlı yeni ve bağımsız kanıt getirmedi,
- sorgular veya kaynaklar tekrar etmeye başladı,
- süre, kaynak veya maliyet bütçesi tükendi,
- uygun ve izinli ek kaynak kalmadı,
- kullanıcı tarafından belirlenen sınır aşıldı.

Durdurma, “kesin doğruya ulaşıldı” anlamına gelmez. Yalnızca araştırma planının belirlediği kapsama hedefine veya doğal sınıra gelindiğini ifade eder.

## Standard ve Deep Research ilişkisi

- Standard araştırma, Faz 2 planındaki sınırlı kaynak ve sorgu bütçesiyle çalışır.
- Deep Research aynı araştırma ve provenance yapısını kullanır; daha fazla sorgu, kaynak, dil/pazar ve vertical research pack kullanabilir.
- Deep Research, standart araştırmanın yerine geçen bağımsız rapor sistemi değildir.
- Kullanıcı onayı olmadan premium/maliyetli kaynaklar başlatılmaz.
- Deep Research çıktısı yine Faz 3 ve Faz 4 hattından geçer; özel ve izlenemeyen bir AI cevabı olarak kalmaz.

## Hazır Deep Research sağlayıcıları

Hazır deep research veya semantic search sağlayıcıları yardımcı bir provider connector olabilir.

- Sağlayıcı sonucu nihai kanıt kabul edilmez.
- Sağlayıcının sunduğu URL/citation'lar mümkünse Faz 3–4 hattından yeniden fetch edilip normalize edilir.
- Sağlayıcı, Source Registry ve Policy Gateway dışına çıkamaz.
- Sağlayıcı değiştirilebilir adapter arkasında tutulur; ürün tek bir vendor'a bağlanmaz.

Bu yaklaşım, hız kazanırken kanıt zincirini ve maliyet kontrolünü korur.

## Güvenlik ve politika

Tarayıcı veya harici içerik kullanan AI sistemlerinde prompt injection önemli bir risktir. Bu fazda savunma mimari düzeyde uygulanır:

- Web içeriği güvenilmeyen veri olarak tutulur; sistem talimatı değildir.
- AI'a yalnızca gerekli normalize segmentler ve metadata verilir.
- Araçlar allowlist ile sınırlandırılır.
- Her tool çağrısı Policy Gateway tarafından bağımsız biçimde doğrulanır.
- AI API anahtarını, kullanıcı sırrını veya connector credential'larını görmez.
- Giriş gerektiren, yazma yapan veya finansal etki oluşturabilecek browser aksiyonları yoktur.
- Kaynak içeriği connector seçimini, bütçeyi veya kullanıcı yetkisini değiştiremez.
- Araştırma aksiyonları ve policy kararları Research Trace'e kaydedilir.
- Deep Research prompt'ları, tool şemaları ve güvenlik testleri sürümlenir.

## Teknik yapı

```text
Gap Auditor
Deep Research Controller
Policy Gateway
Research Orchestrator
Evidence Store
Research Trace
Budget Controller
Coverage Evaluator
```

Mimari yerleşim:

```text
Faz 6 ResearchGapRequest
  -> Faz 5 Gap Auditor + Research Controller
  -> Platform Policy Gateway
  -> Faz 3 Evidence Acquisition (trigger=gap_driven)
  -> Faz 4 Normalization
  -> Faz 6 Analysis revision
```

Bu döngünün tek workflow kimliği ve parent/child run ilişkisi vardır. Aynı budget ledger, Source Registry, connector adapter ve provenance sözleşmesi kullanılır.

### Veri modeli

```text
DeepResearchRun
research_run_id
parent_analysis_run_id
gap_request_id
gap_snapshot
coverage_before
research_actions
tool_execution_log
budget_usage
coverage_after
stop_reason
model_version
prompt_version
policy_version
created_at
completed_at
```

### Kullanıcıya gösterilecek araştırma özeti

Kullanıcıya modelin gizli düşünme süreci gösterilmez. Bunun yerine denetlenebilir çalışma özeti gösterilir:

- araştırılan boşluk,
- kullanılan kaynaklar,
- yeni bulunan bağımsız kanıtlar,
- ulaşılamayan veya policy nedeniyle kullanılmayan kaynaklar,
- bütçe/süre kullanımı,
- araştırmanın neden durduğu.

## Bilinçli olarak kapsam dışı bırakılanlar

- Serbest multi-agent mimarisi
- AI'ın rastgele browser, shell veya dış API erişimi
- Kullanıcı adına hesap açma, giriş yapma, form doldurma, mesaj atma veya ödeme
- Kullanıcı onayı olmadan premium araştırma başlatma
- AI'ın kendi bütçe, yetki veya connector kapsamını artırması
- Kaynak içeriğini talimat veya güvenilir karar kabul etmek
- Nihai rapor, pazar analizi veya Build/Modify/Kill kararı üretmek
- Vektör veritabanını veya RAG'ı Deep Research'ün zorunlu ön koşulu yapmak
- Hazır bir AI research sağlayıcısının cevabını doğrulanmış kanıt gibi sunmak

## Ölçümler

- Gap Auditor tarafından tespit edilen kritik boşluk oranı
- Deep Research sonrası kapanan boşluk oranı
- Tur başına yeni ve bağımsız kanıt sayısı
- Tekrarlı/elenen sorgu oranı
- Sorgu başına maliyet ve kanıt başına maliyet
- Kaynak çeşitliliği artışı
- Karşıt kanıt sorgularının kapsama oranı
- Budget exhaustion, policy block ve source unavailable oranları
- Kullanıcının Deep Research önerisini kabul etme oranı
- Faz 6'da Deep Research bulgularının kullanılabilirlik oranı

## Faz 5 kabul kriterleri

- Deep Research yalnızca kullanıcı tercihi veya görünür Gap Auditor önerisiyle başlatılabilmelidir.
- Her AI araştırma önerisi şemalı, sürümlenmiş ve Policy Gateway tarafından denetlenmiş olmalıdır.
- AI doğrudan dış kaynağa erişememeli; yalnızca izinli Faz 3 connector'ları çalıştırabilmelidir.
- Araştırma hem destekleyici hem karşıt kanıt yönlerini içermelidir.
- Yeni bulgular Faz 4 normalizasyonundan geçmeden analiz katmanına aktarılmamalıdır.
- Süre, maliyet, kaynak ve tur limitleri zorunlu olarak uygulanmalıdır.
- Her run için coverage değişimi, tool log, bütçe ve stop reason saklanmalıdır.
- Deep Research nihai karar veya rapor üretememelidir.
- Faz 5 ikinci bir connector/orkestrasyon hattı oluşturmamalı; bütün dış işleri Faz 3'e `gap_driven` olarak vermelidir.
- Her turdan sonra Faz 6 yeniden çalışmalı ve yeni analiz sürümü üretmelidir.

## Faz 5 çıkışı

Faz 6'ya yeniden aktarılmaya hazır; kritik boşlukları hedefleyen, Faz 3–4 ortak hattından geçmiş, provenance ve parent/child run zinciri korunmuş genişletilmiş araştırma veri seti ve kapanma durumu.
