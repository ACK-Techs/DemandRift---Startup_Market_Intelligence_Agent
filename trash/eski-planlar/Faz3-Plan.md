# Faz 3 — Araştırma ve Kanıt Toplama Altyapısı

> Ortak workflow, Source Registry, Egress Gateway, maliyet, tenant, veri yönetişimi ve gözlemlenebilirlik kuralları için `Platform-Temeli.md`; entegrasyon sırası için `Ust-Yonetim-Ana-Mimari-Plani.md` bağlayıcıdır.

## Amaç

Faz 2'nin ürettiği **Research Plan** içindeki araştırma sorularına, izinli ve izlenebilir kaynaklardan ham kanıt toplamak.

Bu fazın amacı çok sayıda link veya yüzeysel özet üretmek değildir. Amaç; her sonraki analiz ve kararın, kaynağı, tarihi, erişim biçimi ve araştırma bağlamı bilinen gerçek veriye dayanmasını sağlamaktır.

> Faz 3, tek bir web scraper değil; kaynak yetkinliği, erişim izni, maliyet, kalite ve fallback bilgisi tanımlı bir Evidence Acquisition Platform olacaktır.

## Faz sınırı

### Girdi

- Faz 2'den gelen, sürümlenmiş ve doğrulanmış Research Plan
- Araştırma modu: `standard` veya kullanıcının onayladığı `deep_research`
- Source Registry'nin ilgili sürümü
- Kullanıcının pazar, dil, bütçe ve kapsam tercihleri

### Çıktı

Kaynak gösterimi korunmuş ham araştırma artefact'ları ve toplama durumu.

Bu faz:

- araştırma bulgularını anlamlandırmaz,
- kullanıcı yorumlarını gruplamaz,
- market gap çıkarmaz,
- Build / Modify / Kill / Investigate More kararı vermez,
- rapor metni üretmez.

Bu işler Faz 4 ve sonraki fazların sorumluluğudur.

## Genel akış

```text
Research Plan
      ↓
Research Orchestrator
      ↓
Kaynak seçimi, kota ve iş kuyruğu
      ↓
API / arama / izinli crawl connector'ları
      ↓
Ham belge + metadata + toplama geçmişi
      ↓
Faz 4: temizleme, normalizasyon ve kanıt analizi
```

## Önceki fazlarla sözleşme

- Faz 1 kullanıcı onaylı Idea Brief'i üretir.
- Faz 2 bu brief'ten Research Plan, araştırma niyetleri, kaynak türleri ve sorgu bütçesi üretir.
- Faz 3 yalnızca Faz 2'de izin verilen sorgu, kaynak ve bütçe ile çalışır.
- Faz 3'ün topladığı her veri parçası, ait olduğu plan, sorgu ve connector sürümüyle ilişkilendirilir.
- Faz 2'de belirtilmeyen bir kaynağa otomatik geçiş yapılmaz. Gerekirse yeniden planlama ya da Deep Research önerisi oluşturulur.
- Aynı toplama altyapısı iki tetikleyici kabul eder: `plan_driven` (Faz 2 başlangıç planı) ve `gap_driven` (Faz 6 boşluk analizinden dönen, Faz 5 kontrol modüllerince doğrulanmış ek plan). İki ayrı crawler veya orkestrasyon hattı kurulmaz.

## Seçilen mimari

```text
ResearchRun
 ├── Plan Snapshot
 ├── Work Items
 │    ├── Web discovery
 │    ├── Official-site scan
 │    ├── Community evidence
 │    ├── Marketplace/review evidence
 │    ├── Social signal
 │    ├── Domain & web footprint
 │    └── Vertical-specific evidence
 │
 ├── Connector Registry
 ├── Rate-limit / cost controller
 ├── Raw artifact storage
 └── Provenance ledger
```

Her araştırma çalışması bağımsız bir `ResearchRun` olarak saklanır. Bu, aynı fikir farklı planla veya farklı zamanda tekrar araştırıldığında sonuçların karşılaştırılmasını sağlar.

`ResearchRun.trigger_type = plan_driven | gap_driven` alanı zorunludur. Gap-driven çalışmada `parent_analysis_run_id`, `gap_request_id` ve önceki coverage snapshot saklanır.

## Connector tasarımı

Her kaynak ayrı bir connector/adaptör olarak uygulanır. Kaynak URL'leri uygulama koduna dağılmaz.

### Ortak connector sözleşmesi

```text
discover()       Kaynakta aday ürün, URL veya içerik bulur
fetch()          İzinli biçimde ham içeriği getirir
normalizeMeta()  Kaynak, tarih, URL ve etkileşim metadatasını standartlaştırır
healthCheck()    Erişim, kota ve hata durumunu bildirir
```

### Connector sorumlulukları

- Kaynağın resmî API'sini, varsa öncelikli olarak kullanır.
- API yoksa yalnızca kaynak politikası ve izinler uygunsa kamuya açık sayfayı toplar.
- `robots.txt`, kullanım koşulları, rate limit ve lisans kısıtlarını uygular.
- Kaynak bazlı kota, concurrency ve retry kurallarına uyar.
- Ham yanıtı değiştirmeden saklar; ayrıştırılmış metadata ayrı kaydedilir.
- Kaynak erişilemezse bunu bulgu yokmuş gibi göstermez.

### Connector Registry

Her connector için Source Registry'de aşağıdakiler yer alır:

```text
source_id
source_type
eligible_product_types
supported_search_intents
language_or_market_coverage
access_method
cost_tier
rate_limit_policy
risk_or_restrictions
retention_policy
enabled_status
```

Bir connector ancak registry'de etkin ve ilgili Research Plan için izinliyse çalışabilir.

Yukarıdaki alan listesi açıklayıcıdır; kanonik Source Registry sözleşmesi Platform Temeli'ndeki ortak contracts paketinde tek kez tanımlanır. Faz 2 ve Faz 3 aynı şema ve sürümü kullanır.

## Kanıt türleri ve kaynak aileleri

### 1. Açık web discovery

**Amaç:** yeni rakip, niş site, forum, landing page, doküman, alternatif ve kullanım dili keşfetmek.

- Birincil aday: Brave Search API
- İkincil/fallback aday: Exa Search
- Arama sağlayıcısı mutlaka adapter arkasında tutulur.
- Arama sonucu kanıtın kendisi değil, aday kaynak keşif sinyalidir; uygun URL'ler ayrıca fetch edilmelidir.

Bing Search API ürünün temel bağımlılığı değildir; eski Bing Search API'leri sonlandırılmıştır. Google veya başka bir arama sağlayıcısına doğrudan bağımlılık da kurulmaz.

### 2. Rakiplerin resmî web siteleri

**Amaç:** konumlandırma, hedef kullanıcı, özellik, fiyat, entegrasyon, changelog, müşteri dili ve ürün olgunluğu hakkında birincil kaynak toplamak.

Official Site Scanner şunları yapar:

- alan adı ve site keşfi,
- `robots.txt` ve sitemap incelemesi,
- pricing, features, docs, integrations, changelog, customers ve FAQ sayfalarını bulma,
- JSON-LD, OpenGraph ve görünür sayfa metnini çıkarma,
- öncelikle HTTP + HTML parsing kullanma,
- yalnızca gerekli ve izinli ise JavaScript render fallback'i kullanma.

JavaScript render connector kapsamından çıkarılmaz; ancak ayrı bir yüksek riskli yürütme profili olarak Egress Guard, DNS/IP yeniden doğrulama, izole browser worker, kaynak allowlist'i, indirme limiti ve sıkı timeout altında çalışır. Basit HTTP fetch yeterliyse browser çalıştırılmaz.

Rakiplerin kendi sitesi, fiyat ve özellik iddiaları için öncelikli kaynaktır. Üçüncü taraf özetleri yalnızca ikincil sinyal kabul edilir.

### 3. Teknik ürün ve developer ekosistemi

Agent, developer tool, API veya teknik ürün fikirlerinde öncelikli kaynak grubu:

- GitHub: repository, issue, discussion, release, yıldız, fork ve açık şikâyetler
- Hacker News: gönderi, yorum ve etkileşim
- Stack Exchange: soru, cevap, etiket, tarih ve oy
- Product Hunt: launch, yorum, oy ve kategori
- YouTube: hedefli demo, inceleme ve yorum sinyalleri

GitHub connector'ı arama limitleri nedeniyle kuyruk, kota ve kontrollü eşzamanlılık kullanmalıdır. Stack Exchange ve Hacker News, resmî açık API'leri nedeniyle erken sürümde düşük riskli kaynaklardır.

### 4. Kullanıcı sesi ve topluluk kanıtı

Bu grup ürünün farklılaşması için çok değerlidir; fakat her platformun erişim durumu farklıdır.

| Kaynak | Araştırma değeri | Faz 3 kararı |
| --- | --- | --- |
| Reddit | Güçlü problem, şikâyet ve workaround kanıtı | Ticari erişim/uyum netleşirse connector |
| X | Güncel tartışma ve launch sinyali | Resmî API ile opsiyonel connector |
| YouTube | İnceleme, demo ve yorum sinyali | Hedefli connector |
| Discord / Slack | Kapalı topluluklarda yüksek değer | Kullanıcı izinli import dışında kullanılmaz |
| LinkedIn | B2B sinyali | Araştırma çekirdeği değildir; scrape edilmez |
| Instagram | Consumer/trend sinyali | Dar kapsamlı ve koşullu connector |
| TikTok | Trend/consumer sinyali | Sonraki aşama, koşullu connector |
| Mastodon / açık forumlar | Niş topluluk kanıtı | Uygun fikirlerde connector |

Reddit, ticari kullanım veya ücretsiz kota üstü kullanım için ayrı anlaşma gerektirebilir. Bu nedenle Reddit, onaylı erişim yoksa standart araştırmanın zorunlu bağımlılığı değildir.

X connector'ı yalnızca resmî API ve uygun maliyet/kota altında çalışır.

LinkedIn connector'ı, API dışı scraping veya crawling yapmaz. LinkedIn verisi yalnızca açıkça izinli API/partner kullanım alanlarında değerlendirilir.

Instagram, geniş internet araştırmasının ana kaynağı değildir; profesyonel hesap/izin kapsamı uygunsa consumer ürünlerde yardımcı sinyal olabilir.

### 5. Marketplace ve review kaynakları

Ürün türüne göre aşağıdaki kaynaklar kullanılabilir:

- Apple App Store
- Google Play
- Chrome Web Store
- Shopify App Store
- WordPress dizini
- Product Hunt
- G2, Capterra, GetApp ve benzeri review kaynakları

Burada **metadata keşfi** ile **yorum/review toplama** ayrı yetkinliklerdir.

- Uygulama metadata'sı, izinli katalog veya resmî arama mekanizmasından toplanabilir.
- Review verisi yalnızca resmî, partner veya lisanslı erişim mevcutsa kullanılmalıdır.
- Review siteleri ilk sürümde scraping bağımlılığı olarak tasarlanmaz.
- Kaynak kullanılamazsa rapor bunu açıkça belirtmelidir; eksik veri doldurulmaz.

### 6. Domain, marka ve web footprint araştırması

Bu bölüm ürün fikrinin marka/alan adı çakışması ve mevcut web varlığı hakkında sinyal üretir.

Yapılabilecekler:

- arama indekslerinde benzer ürün/marka/site keşfi,
- domain varyasyonları üretme,
- RDAP ile kayıt durumu sorgulama,
- DNS çözümleme,
- HTTP/HTTPS erişim kontrolü,
- Certificate Transparency kayıtlarında alan adı veya organizasyon izi arama,
- resmî sayfalardan veya lisanslı araçlardan teknoloji sinyali alma.

Bu sinyallerin iddia düzeyi sınırlı tutulur:

```text
registered_domain_signal
active_website_signal
historical_certificate_signal
brand_collision_candidate
not_verified
```

RDAP sonucu anlık domain satın alınabilirliği garantisi değildir. Certificate Transparency sonucu da aktif ürün veya güncel sahiplik kanıtı değildir.

### 7. Pazar, ticari niyet ve görünürlük sinyalleri

İleriki connector paketlerinde şu alanlar değerlendirilir:

- reklam kütüphaneleri,
- SEO ve keyword veri sağlayıcıları,
- funding ve şirket verisi,
- job posting kaynakları,
- Google Maps ve yerel dizinler,
- kamu, regülasyon, akademik veya dikey veri kaynakları,
- patent ve marka veri tabanları.

Bunlar çekirdek araştırmanın ilk gün bağımlılıkları değildir. Fikir türüne göre seçilen **vertical research packs** olarak uygulanırlar.

Örnek yaklaşım:

- sağlık: yayınlar ve regülasyon kaynakları,
- fintech: regülasyon, şirket ve lisans kaynakları,
- lokal hizmet: harita, yerel dizin ve review kaynakları,
- B2B SaaS: resmî siteler, job post'lar, teknik topluluklar,
- consumer app: uygulama mağazaları, açık topluluklar ve trend kaynakları.

## Standard araştırma için ilk kaynak paketi

İlk canlı sürümde önerilen güvenilir temel:

```text
Web Search
Official Competitor Website Scanner
GitHub
Hacker News
Stack Exchange
Product Hunt
YouTube
Domain / RDAP / DNS / Web Footprint
```

Koşullu veya sonraki connector'lar:

```text
Reddit        Ticari erişim ve uyum netleşirse
X             Fikir/plan uygunsa ve resmî API ile
App stores    Ürün türü uygunsa
Review sites  Lisanslı erişim varsa
Instagram     Consumer/trend fikrinde ve uygun erişim varsa
Ads/Funding/Jobs/Maps
              Vertical pack gerektirdiğinde
```

Bu paket kapsam envanteridir; her run bütün connector'ları körlemesine çalıştırmaz. Research Plan ürün tipi, araştırma niyeti, dil, erişim politikası ve beklenen bilgi değerine göre ilgili connector'ları seçer. Tüm connector aileleri ürün mimarisinde korunur ve uygun planlarda etkinleştirilebilir.

## Deep Research kapsamı

Deep Research, standart araştırmanın alternatifi değil, genişletilmiş biçimidir.

- Daha fazla sorgu ve kaynak bütçesi kullanır.
- Daha geniş dil/pazar ve dikey paket çalıştırabilir.
- Birden fazla arama sağlayıcısı veya ek lisanslı kaynak kullanabilir.
- Kullanıcının premium tercihi olmadan otomatik başlamaz.
- Her ek kaynak ve maliyet, ResearchRun içinde izlenir.

## Teknik altyapı

Faz 3 uzun süren, hata verebilen ve kota tüketen işler barındırdığı için basit bir HTTP request/response akışıyla çalışmamalıdır.

Önerilen başlangıç stack'i:

- Dil/platform: TypeScript / Node.js
- Uygulama: mevcut modüler monolith yaklaşımı
- Veritabanı: PostgreSQL
- Ham artefact saklama: S3 uyumlu object storage
- Dayanıklı workflow/job yürütme: Platform Temeli'nde seçilen ortak Workflow Engine; connector işi için idempotent activity/job sözleşmesi
- Redis: zorunlu kuyruk değil; dağıtık rate limit, kısa ömürlü cache veya provider quota koordinasyonu gerektiğinde yardımcı bileşen
- HTTP istemcisi: undici
- HTML parsing: Cheerio + Mozilla Readability
- Sitemap/robots: sitemap parser + robots-parser
- Browser fallback: izole Playwright worker; yalnızca source policy ve Egress Guard izin veriyorsa
- Şema: Zod + JSON Schema
- Gözlemlenebilirlik: OpenTelemetry
- İçerik kimliği/dedup hazırlığı: canonical URL normalizasyonu + SHA-256 content hash

Workflow teknolojisi faz içinde yerel olarak seçilmez. Faz 1–7'nin uzun süren, yeniden başlatılabilir, iptal edilebilir ve insan onaylı akışları Platform Temeli'nin Workflow Engine kararıyla yürütülür. Modüler monolith korunur; workflow motoru kullanılması mikroservis zorunluluğu doğurmaz.

## Orkestrasyon ve durum yönetimi

```text
ResearchRun
 ├── plan snapshot
 ├── connector tasks
 ├── query executions
 ├── source budget
 ├── raw artifacts
 └── provenance log
```

Her görev aşağıdaki durumları taşımalıdır:

```text
queued → running → succeeded
                ↘ partial
                ↘ rate_limited
                ↘ blocked_by_policy
                ↘ failed
```

Araştırma ekranı ve sonraki rapor, aşağıdaki durumları ayırmalıdır:

- kaynakta sonuç bulunamadı,
- kaynağa teknik olarak ulaşılamadı,
- rate limit veya kota aşıldı,
- kullanım şartı/izin nedeniyle kaynak kullanılmadı,
- sorgu yetersiz kaldı.

Bu ayrım, “kanıt bulunamadı” ile “kanıta erişilemedi” ifadelerinin karıştırılmasını önler.

## Ham veri ve provenance kuralları

Her toplanan belge veya API kaydı için en az aşağıdaki alanlar saklanır:

```text
source_id
source_url
canonical_url
access_method
query_id
research_plan_version
connector_version
collected_at
published_at
author_or_product
engagement_metadata
raw_content_reference
content_hash
license_or_restriction
```

- Ham yanıt değiştirilemez artefact olarak tutulur.
- Ayrıştırılmış metadata ham içerikten ayrı saklanır.
- Kullanıcıya gösterilecek alıntı, kaynağın URL'sine ve toplama zamanına bağlanır.
- Silinen veya erişilemeyen kaynaklar için son görülen kayıt saklanabilir; retention/uyum politikası connector bazında uygulanır.
- Faz 4, ham artefact'ı kaybetmeden normalize edilmiş veri üretir.

## Rate limit, maliyet ve hata politikası

- Her connector için ayrı concurrency, rate limit ve retry politikası uygulanır.
- Retry yalnızca geçici teknik hatalarda kullanılır; policy block durumunda tekrar denenmez.
- Her Research Plan kaynak ve sorgu bütçesini belirler; connector bu bütçeyi aşamaz.
- API anahtarları kullanıcıya veya AI'a verilmez.
- Bir connector sağlıksızsa circuit breaker ile geçici olarak devre dışı bırakılır.
- Fallback yalnızca Research Plan/Registry izin veriyorsa devreye girer.
- Maliyetli kaynaklar Deep Research veya açık kullanıcı seçimi gerektirebilir.
- Arama, fetch, browser, ücretli veri ve sonraki LLM işleme maliyetleri ortak `Cost Ledger` içine gerçek zamanlı yazılır. Hard limit atomik olarak rezerve edilmeden dış çağrı başlatılamaz.

## Güvenlik ve uyum

- Resmî API, lisanslı veri sağlayıcısı veya açıkça izinli erişim yöntemi önceliklidir.
- `robots.txt`, kaynak kullanım şartları ve platform politikaları connector seviyesinde uygulanır.
- Giriş metni veya toplanan web içeriği, sistem talimatı gibi yürütülmez.
- Toplanan içerikteki prompt injection benzeri metinler tool çağrısı, connector seçimi veya sorgu bütçesini değiştiremez.
- Kaynak içeriği güvenilmeyen veri olarak işlenir.
- Bütün dış HTTP erişimi tek Egress Gateway üzerinden geçer: yalnızca HTTP/HTTPS, DNS çözümleme öncesi ve yönlendirme sonrası özel/loopback/link-local/cloud-metadata IP engeli, port allowlist'i, redirect sınırı, response boyut ve MIME kontrolü uygulanır.
- LinkedIn, kapalı Discord/Slack toplulukları ve benzeri kaynaklar izinsiz scrape edilmez.
- Kişisel veri, erişim ve saklama politikaları connector/retention seviyesinde kontrol edilir.

## Bilinçli olarak kapsam dışı bırakılanlar

- Her siteyi veya her sosyal ağı scrape etmeye çalışan evrensel crawler
- Kaynak kullanım şartlarını aşmak veya rate limit'i bypass etmek
- AI'ın doğrudan rastgele URL/tool çağrısı yapması
- Arama sonucunu doğrulanmış kanıt saymak
- Kullanılamayan kaynaklardaki veriyi tahmin etmek veya uydurmak
- Faz 3 içinde kullanıcı şikâyetlerini analiz etmek, özetlemek veya puanlamak
- Faz 3 içinde rakip analizi/market gap/karar üretmek
- İlk sürümde 20+ connector'a bağımlı olmak
- RAG, vektör veritabanı, fine-tuning veya multi-agent mimarisini Faz 3'ün ön koşulu yapmak
- Kullanıcı onayı olmadan Deep Research veya maliyetli kaynak başlatmak

## Kaynak ekleme kriterleri

Yeni bir connector şu dört şartı karşılamadan ürün kapsamına eklenmez:

1. Araştırma sorularından birine benzersiz ve ölçülebilir katkı sağlıyor mu?
2. Resmî, lisanslı veya açıkça izinli erişim yöntemi var mı?
3. Veri kalitesi, kaynak gösterimi ve güncelliği yeterli mi?
4. Maliyet ve bakım yükü, ürettiği kanıt değerine değiyor mu?

## Ölçümler

- Planlanan kaynakların başarıyla çalıştırılma oranı
- Connector bazında sonuç, hata, rate limit ve policy block oranı
- Sorgu başına bulunan aday belge sayısı
- Fetch edilen belge / kullanılabilir ham artefact oranı
- Kaynak çeşitliliği ve araştırma niyeti kapsama oranı
- Standart araştırmada yetersiz kalan plan oranı
- Deep Research'e geçiş oranı
- Araştırma run süresi ve kaynak başına maliyet
- Her bulgu için provenance alanlarının tamlık oranı

## Faz 3 kabul kriterleri

- Onaylı Research Plan'daki her izinli work item, izlenebilir bir connector task'a dönüşmelidir.
- Connector yalnızca registry'de tanımlı erişim yöntemi ve kota ile çalışmalıdır.
- Her ham bulgu, kaynak URL'si, sorgu, toplama zamanı, plan sürümü ve connector sürümüyle saklanmalıdır.
- `partial`, `rate_limited`, `blocked_by_policy` ve `failed` durumları birbirinden ayrılmalıdır.
- Web search sonucu ile fetch edilmiş kaynak içeriği ayrı veri türü olarak tutulmalıdır.
- Kullanıcı onayı olmadan Deep Research veya maliyetli/koşullu connector başlatılmamalıdır.
- Faz 3, analiz veya karar üreten AI çağrısı yapmamalıdır.

## Araştırmada doğrulanan dış kısıtlar

- Bing Search API'leri sonlandırıldığı için temel arama bağımlılığı olarak kullanılmaz.
- Reddit ticari kullanım veya kota üstü kullanım için ayrı anlaşma gerektirebilir; bu yüzden koşullu connector'dır.
- X, resmî API üzerinden opsiyonel kaynak olarak ele alınır.
- LinkedIn, API dışı scraping/crawling'i yasakladığından araştırma çekirdeği değildir.
- Instagram API, geniş kamu araştırmasından çok profesyonel hesap yönetimi kapsamındadır.
- GitHub arama işlemlerinde rate limit uygulanır; kuyruk/kota gerektirir.
- Stack Exchange, Hacker News ve Product Hunt uygun resmî erişim yolları olan kaynaklardır.
- RDAP yapılandırılmış domain kayıt sinyali sağlar; domain satın alınabilirliği garantilemez.
- Certificate Transparency kayıtları, TLS sertifika geçmişi için sinyal sağlar; aktif ürün veya sahiplik kanıtı değildir.

## Faz 3 çıkışı

Faz 4'e aktarılmaya hazır; kaynak, tarih, sorgu, erişim yöntemi ve ham içerik referansı korunmuş, denetlenebilir bir araştırma veri seti.

## Veri sahipliği ve ortak artefact cache

- Kamuya açık ve lisansı paylaşmaya izin veren ham artefact'lar canonical URL, içerik kimliği, erişim yöntemi ve tazelik penceresiyle global cache'te tutulabilir.
- Tenant'ın hangi sorguyla hangi artefact'a eriştiği `ArtifactAccess`/`RunArtifact` eşlemesiyle tenant-scoped saklanır; tenantlar birbirlerinin sorgu ve kullanım bilgisini göremez.
- Özel importlar, kapalı topluluk verisi, kullanıcı tarafından yüklenen içerik ve lisansı paylaşımı yasaklayan kaynaklar kesinlikle tenant-scoped tutulur.
- Claim, analiz, cluster ve karar her zaman tenant/run-scoped'tur; global artefact ortak yorum veya ortak karar anlamına gelmez.
- Retention, silme ve lisans politikası global cache kullanımından önce kontrol edilir.
