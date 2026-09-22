# Ayselin Task — Ürün Tipine Göre Araştırma Tasarımı

**Sahip:** Ayselin Aydoğdu<br>
**Kanonik görev adı:** `ayselin-task`<br>
**Başlangıç:** Yalnız T01 ile başla. Bir kartın teslimi ve kabul kriteri
karşılanmadan sonraki karta geçme.

Bu görev, live crawl, ücretli kaynak çağrısı veya connector implementasyonu
yetkisi vermez. Bu sınırları aşan her çalışma için ayrı approval ve execution
run gerekir.

---

## Amaç

Bu çalışma, herhangi bir yazılımsal ürün fikri için araştırmanın rastgele
sitelerde arama yaparak başlamasını engeller. Hedef; aşağıdaki zinciri
kurmaktır:

```text
ürün tipi → araştırma sorusu → gerekli kanıt → kaynak ailesi →
kaynak yeteneği → alınacak veri alanı → sorgu şablonu → policy/bütçe/fallback
```

Bu bir connector implementasyonu veya toplu canlı crawl görevi değildir. Her
çıktı Faz 2'nin `ResearchPlan`ı ve Faz 3'ün `Source Registry`si tarafından
kullanılabilecek, sürümlü bir tasarım girdisidir.

## Değişmez kurallar

- Bir siteye erişilebilmesi, o sitenin araştırma için yararlı kanıt verdiği
  anlamına gelmez.
- Arama sonucu, snippet veya sitemap karar kanıtı değildir; yalnız aday URL
  keşif sinyalidir. Kanıt sayılabilmesi için hedef içerik ayrıca fetch edilir.
- Kullanıcının “öderim” demesi gözlemlenmiş ödeme davranışı değildir. İnternet
  araştırması bu boşluğu kapatamaz; gerekirse `primary_validation_gap` olarak
  işaretlenir.
- `source_unavailable`, `blocked_by_policy` ve `no_results` asla aynı sonuç
  gibi yazılmaz.
- Lisansı, kullanım şartı, erişim yöntemi, saklama hakkı veya veri alanı belirsiz
  bir kaynak production planına alınmaz.
- Aynı platformun farklı sayfaları veya repost edilmiş içerik bağımsız kanıt
  değildir.
- Kapsamdaki hiçbir kaynak ailesi silinmez; her ürün/run için yalnız uygun olan
  kaynaklar seçilir.

## Ortak çıktı sözleşmesi

Her görev kendi ana çıktısını üretir. İsimler öneridir; alanlar zorunludur.

| Çıktı | Zorunlu alanlar |
|---|---|
| `ProductResearchTaxonomy` | `product_type_id`, tanım, dahil/hariç örnekleri, hedef kullanıcı, satın alma tipi, pazar/locale etkisi, araştırma riskleri |
| `EvidenceNeedMatrix` | ürün tipi, araştırma niyeti, cevaplanacak soru, kabul edilen kanıt, kabul edilmeyen proxy, `secondary_or_primary`, öncelik |
| `SourceCapabilityProfile` | `source_id`, kaynak ailesi, resmî/lisanslı erişim yöntemi, alınabilir alanlar, sorgu yüzeyi, kısıtlar, maliyet/kota, tazelik, retention, PII riski |
| `SourceFitMatrix` | ürün tipi × araştırma niyeti × kaynak; beklenen benzersiz katkı, veri alanı, öncelik, bağımsızlık grubu, fallback |
| `QueryPlaybook` | niyet, kaynak, şablon, yer tutucular, dil/pazar, negatif terimler, sonuç/fetch bütçesi, durdurma kuralı |
| `ResearchPack` | standard/deep seçimleri, minimum kanıt çeşitliliği, maliyet zarfı, policy koşulu, fallback ve raporlama sınırlaması |

---

## T01 — Ürün evreni ve kategori taksonomisi

**Amaç:** Araştırılacak yazılım ürünlerini, kaynak seçimini gerçekten etkileyen
ayrık kategorilere bölmek. Kategori yalnız etiket olmamalı; farklı araştırma
niyeti veya kaynak paketi doğurmalıdır.

**Yapılacaklar:**

1. İlk taksonomiyi en az şu aileleri kapsayacak biçimde öner: B2B SaaS,
   developer tool/API/agent, consumer mobile app, consumer web product,
   two-sided marketplace, local-service platform, e-commerce enablement,
   data/analytics product ve regulated vertical software.
2. Her aile için alt kategori ancak kaynak veya kanıt ihtiyacını değiştiriyorsa
   aç; örneğin health/fintech/legal ayrı policy ve regülasyon paketi gerektirir.
3. Her kategori için dahil/hariç örnekleri, hedef kullanıcı/satın alma yapısı,
   tipik pazar kapsamı ve araştırmada yanlış eşleşme risklerini yaz.
4. Yeni bir fikrin tek veya birden fazla kategoriye hangi kuralla bağlanacağını
   gösteren karar ağacını oluştur.

**Teslim:** `ProductResearchTaxonomy v1` ve kategori karar ağacı.

**Kabul:** Her kategori için en az bir farklı kaynak/kanıt sonucu vardır;
"genel uygulama" gibi araştırma kararını değiştirmeyen kategoriler yoktur.

**Sınır:** Henüz site, anahtar kelime veya canlı veri araştırması yapılmaz.

## T02 — Araştırma soruları ve kanıt gereksinimleri

**Amaç:** Her ürün kategorisinde hangi soruların cevaplanacağını ve hangi
kanıtın bu soruyu gerçekten desteklediğini tanımlamak.

**Yapılacaklar:**

1. Her kategori için şu niyetleri ayrı değerlendir: `problem_demand`,
   `existing_alternatives`, `dissatisfaction`, `use_case`,
   `competitor_discovery`, `observed_market_pricing`, `stated_wtp_weak_signal`,
   adoption/traction, regulatory constraint ve technical feasibility.
2. Her niyet için kabul edilen kanıtı, yanlış/eksik proxy'leri ve gereken
   bağımsız kaynak çeşitliliğini tanımla.
3. İnternet araştırması ile kapanabilecek ikincil boşlukları; görüşme, pilot,
   landing test, preorder veya ödeme gözlemi gerektiren birincil boşluklardan
   ayır.
4. Pazar/dil/coğrafya ve ürün olgunluğu farklı olduğunda kanıt eşiğinin nasıl
   değişeceğini yaz.

**Teslim:** `EvidenceNeedMatrix v1`.

**Kabul:** Her soru bir ölçülebilir kanıt tanımına bağlıdır; "şikâyet yok =
memnun" veya "fiyat var = talep var" gibi geçersiz çıkarımlar açıkça yasaktır.

**Bağımlılık:** T01.

## T03 — Mevcut 636 kaynak envanterini temizleme ve kaynak ailesi atama

**Amaç:** Mevcut kaynak defterini ürün araştırması için anlamlı bir aday
kataloğa dönüştürmek; aynı host/farklı marka, discovery yüzeyi ve gerçek
veri yüzeyi ayrımını görünür kılmak.

**Yapılacaklar:**

1. Her adayı kaynak ailesine ata: web search, resmî ürün sitesi, code/technical
community, launch/startup, marketplace/app store, review, social/open forum,
domain/web footprint, ads/funding/jobs, public/regulatory, academic/patent,
vertical data.
2. Aynı host veya aynı içerik sağlayıcısına dayanan kayıtları `independence_group`
ile işaretle; ayrı bağımsız kanıt sayılmayacakları belirt.
3. `root_html`, `sitemap`, `RSS`, `archive snapshot`, resmî API ve hedef kayıt/
yorum/ürün sayfasını ayrı yüzey türü olarak sınıflandır.
4. Kaynak defterindeki erişim durumunu `access_snapshot` olarak koru; bunu
"production-ready" veya "kanıt üretir" diye yorumlama.

**Teslim:** `SourceInventoryCleanup v1` ve kaynak ailesi/bağımsızlık matrisi.

**Kabul:** Her kayıt tek kaynak ailesine, her tekrar eden host aynı bağımsızlık
grubuna bağlanır; sitemap veya kök sayfa doğrudan evidence olarak etiketlenmez.

**Bağımlılık:** T01, T02.

## T04 — Kaynak yeteneği ve veri alanı profilleri

**Amaç:** "Bu siteden veri çekilir" yerine, her kaynağın hangi anlamlı alanı
hangi izinli yolla sağlayabileceğini belirlemek.

**Yapılacaklar:**

1. T03'teki her kaynak ailesi için ortak `SourceCapabilityProfile` şablonunu
   doldur; önceliği Faz 3 başlangıç paketi kaynaklarına ver.
2. Her kaynak için alınabilecek somut alanları yaz: örneğin ürün adı,
   kategorisi, açıklaması, fiyat/paket, yayın/tarih, rating/review metni,
   oy/etkileşim, issue/discussion, repo yıldızı/forku, iş ilanı, regülasyon
   kaydı veya patent alanı.
3. Alanların anlamsal sınırını yaz: "app rating" memnuniyetin evrensel ölçüsü
   değildir; "job posting" büyüme kanıtı değildir; "ad library" reklam
   harcamasını açıklamayabilir.
4. Resmî API, lisanslı erişim, açık web fetch, kullanıcı izinli import veya
   erişilemez/policy-blocked durumunu ayrı kaydet. Terms, robots, retention,
   PII, maliyet, rate limit, tazelik ve locale kapsamını ekle.
5. Kaynakta yalnız discovery yüzeyi varsa, sonraki hedef fetch için gerekli
   erişim yolunu ve bu yolun policy'sini ayrı tanımla.

**Teslim:** Kaynak başına `SourceCapabilityProfile` listesi; her alanın
anlamı ve kısıtı.

**Kabul:** "Hangi veri?" ve "hangi erişim izniyle?" soruları her profile
cevaplanır; belirsiz veya lisansı çözümlenmemiş kaynaklar `candidate_only`
durumunda kalır.

**Bağımlılık:** T03.

## T05 — Ürün tipi × araştırma niyeti × kaynak eşlemesi

**Amaç:** Bir ürün fikri geldiğinde tüm 636 kaynağı çalıştırmak yerine, en
değerli ve bağımsız kaynak paketini deterministik seçebilmek.

**Yapılacaklar:**

1. T01 kategorileri ile T02 niyetlerini satır/sütun yap; T04 kaynaklarını
   uygun hücrelere yerleştir.
2. Her eşleşmeye şu alanları ekle: `expected_unique_contribution`, alınacak
   alanlar, kanıt gücü, independence group, policy durumu, standard/deep
   önceliği, maliyet seviyesi, fallback ve bilinen kör nokta.
3. Faz 3 başlangıç paketi için her kategoriye minimum bağımsız kaynak ailesi
   ve minimum evidence surface belirle. Review/kapalı sosyal kaynakları
   zorunlu bağımlılık yapma.
4. Regülasyon, yerel hizmet, marketplace ve developer tool gibi dikeylerde
   `vertical_research_pack` seçim kuralını yaz.

**Teslim:** `SourceFitMatrix v1` ve her ürün kategorisi için kaynak paketi.

**Kabul:** Her zorunlu niyet en az bir izinli kaynak ailesiyle kapsanır;
tek platform bağımlılığı, duplicate bağımsızlığı ve policy block açıkça görünür.

**Bağımlılık:** T02, T04.

## T06 — Anahtar kelime ontolojisi ve kaynak-özel sorgu playbook'u

**Amaç:** Sorguları genel kelime listesi olmaktan çıkarıp kaynak, niyet,
ürün dili ve pazar bağlamına göre derlenebilir şablonlara dönüştürmek.

**Yapılacaklar:**

1. Her ürün kategorisi için controlled vocabulary oluştur: ürün, kullanıcı,
job/problem, pain language, alternatif/workaround, competitor category,
teknik terim, düzenleyici terim, locale/dil ve negatif terimler.
2. T05'te seçilen her kaynak için izinli sorgu yüzeyini ve şablonlarını yaz.
Örnek yüzeyler: resmî API parametresi, site arama formu, GitHub repository/
issue search, HN/Stack Exchange API, sitemap'ten aday URL + hedef fetch.
3. Her sorguyu araştırma niyeti, dil/pazar, kaynak, öncelik, sonuç/fetch
kotası ve beklenen veri alanlarıyla etiketle.
4. Dedupe, konu kayması, tekrar, uygunsuz kaynak-sorgu ve onaysız AI hipotezi
kontrollerini tanımla. İlk sonuçtan kontrolsüz query expansion yapma.

**Teslim:** `QueryPlaybook v1`, şablon kataloğu ve query validation kuralları.

**Kabul:** Her sorgu bir niyete, izinli yüzeye ve beklenen veri alanına bağlıdır;
arama snippet'i kanıt olarak değil aday keşfi olarak sınıflandırılır.

**Bağımlılık:** T04, T05.

## T07 — Standard ve Deep Research paketleri, maliyet ve fallback

**Amaç:** Aynı tasarımı iki bütçe seviyesinde çalıştırmak; premium modu
kontrolsüz daha çok site çalıştırma şeklinde tasarlamamak.

**Yapılacaklar:**

1. Her ürün kategorisi için Standard paketin kaynakları, sorgu/fetch kotası,
   minimum bağımsızlık hedefi ve beklenen limitation'ını yaz.
2. Deep Research'ün yalnız ek bilgi değeri olan kaynak ailesi, dil/pazar veya
   vertical pack genişletmelerini tanımla.
3. Her kaynak için policy-block, rate-limit, source-unavailable ve no-results
   durumunda ayrı fallback/raporlama davranışı oluştur.
4. Tahmini search/API/fetch/browser/lisans/LLM/storage maliyet sınıfını ve
   hard/soft budget davranışını ekle.

**Teslim:** Kategori bazlı `ResearchPack v1` ve fallback/bütçe tablosu.

**Kabul:** Deep Research kullanıcı onayı olmadan çalışmaz; erişilemeyen kaynak
bulgu yokluğu sayılmaz; fallback yalnız registry/policy izin veriyorsa seçilir.

**Bağımlılık:** T05, T06.

## T08 — Araştırma tasarımının gerçekçi pilot değerlendirmesi

**Amaç:** Tasarımın yalnız masa başında mantıklı değil, farklı ürün türlerinde
doğru kaynak ve doğru veri ürettiğini küçük, kontrollü örnekle kanıtlamak.

**Yapılacaklar:**

1. En az şu örnekleri seç: developer tool, B2B SaaS, consumer/mobile,
   marketplace veya local service, regulated vertical ve Türkiye odaklı fikir.
2. Her örnek için T05–T07'den bir ResearchPlan taslağı üret; live crawl veya
ücretli çağrı yapmadan önce policy/maliyet onayı ayrı görünür olsun.
3. Uygun ve izinli küçük bir pilot varsa yalnız seçili kaynakları çalıştır;
gerçek fetch edilmiş artefact ile search candidate'i ayır.
4. Şu ölçümleri değerlendir: source-fit, alan doluluk oranı, kanıt çeşitliliği,
   duplicate oranı, tazelik, policy block, maliyet ve research limitation.
5. Başarısız eşleşmeleri silme; nedenini ve gereken registry/query revision'ını
kaydet.

**Teslim:** `ResearchDesignEvaluation v1`, örnek planlar ve revision backlog'u.

**Kabul:** Her ürün türünde seçilen paketin hangi soruyu cevapladığı, hangi
soruyu cevaplayamadığı ve neden görünürdür. Başarı yalnız HTTP 200 sayısı ile
ölçülmez.

**Bağımlılık:** T07.

## T09 — Sözleşme, yönetim özeti ve uygulamaya devir

**Amaç:** Araştırma tasarımını Faz 2/3 implementasyonuna aktarılabilir tek
referans haline getirmek.

**Yapılacaklar:**

1. T01–T08 çıktılarından `SourceRegistryEntry`, `ResearchPlan.source_plan`,
   `query_plan`, `BudgetContract` ve connector `policyRequirements` alanlarına
   karşılık gelen şemayı yaz.
2. Önceliklendirilmiş implementation backlog'u oluştur: önce shared Source
Registry/policy/egress, sonra başlangıç connector paketi, sonra koşullu ve
vertical connector'lar.
3. Her kaynak için `candidate_only`, `qualified_for_standard`,
   `qualified_for_deep`, `blocked`, `needs_license` veya `retired` durumunu
tanımla; "çekildi" durumunu bu kararların yerine kullanma.
4. Yönetim özeti hazırla: hangi ürün tipleri ilk sürümde iyi araştırılabilir,
hangi sınıflar policy veya primary validation nedeniyle sınırlıdır.

**Teslim:** `Research Design v1`, contract mapping ve fazlı implementation
backlog'u.

**Kabul:** Faz 2 Plan Compiler ve Faz 3 Connector Registry, tasarımı serbest
metin yorumlamadan tüketebilecek alanlara sahiptir; kapsam daraltılmadan
uygulama sırası açıkça belirlenmiştir.

**Bağımlılık:** T08.

---

## Çalışma sırası

```text
T01 → T02 → T03 → T04 → T05 → T06 → T07 → T08 → T09
```

T03 teknik envanter temizliği, T01–T02 tamamlandığında başlatılabilir; ancak
T05'e yalnız T02 ve T04 kabul edildikten sonra girilir. Her görev sonunda
sonuç, belirsizlik ve bir sonraki görevin açık girdileri yazılır.
