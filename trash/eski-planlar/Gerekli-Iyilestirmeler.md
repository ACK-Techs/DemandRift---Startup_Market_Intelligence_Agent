# Gerekli İyileştirmeler — Faz 1–7 Çapraz Mimari Değerlendirme

> **Belge durumu:** Bu dosya tarihsel değerlendirme ve tartışma kaydıdır. Kararların güncel, bağlayıcı ve uygulanmış hali `Ust-Yonetim-Ana-Mimari-Plani.md`, `Platform-Temeli.md` ve revize Faz 1–7 dosyalarındadır. Buradaki “Faz 0”, Redis/BullMQ, transactional outbox, öncelik ve benzeri öneriler güncel mimariyle çelişirse güncel ana mimari üstündür.

## Değerlendirme özeti

Faz 1–7 planı, sıradan bir AI rapor aracından daha güçlü bir omurga oluşturuyor. Özellikle şu kararlar doğru yönde:

- AI'ı ham veri toplama ve kesin kararın tek sahibi yapmamak
- Faz 1 ve 2'de şemalı, kullanıcı onaylı veri sözleşmesi kullanmak
- Faz 3'te kaynak/connector tabanlı, provenance koruyan araştırma mimarisi kurmak
- Faz 4'te ham veriyi değiştirmeden normalize etmek
- Faz 5'te sınırlı, policy-gated Deep Research kullanmak
- Faz 6'da alıntı ile AI yorumunu ayırmak ve karşıt kanıtı tutmak
- Faz 7'de tek skor yerine evidence gate, stabilite ve Value of Information kullanmak

Buna rağmen plan, uygulamaya geçmeden önce bazı temel çapraz kararlarla güçlendirilmelidir. En büyük risk teknik yetersizlik değil; kapsamın çok iyi düşünülmüş ancak henüz ortak platform kurallarıyla bağlanmamış olmasıdır.

Bu belgedeki öneriler Faz 8'e ait değildir. Faz 1–7'nin daha güvenilir, sürdürülebilir ve ölçeklenebilir çalışması için gereken iyileştirmelerdir.

---

# 1. Teknik teknoloji ve yapı değerlendirmesi

## 1.1 Korunması gereken ana mimari kararlar

### Modüler monolith ile başlamak

Mevcut TypeScript tabanlı modüler monolith yaklaşımı ilk sürüm için doğru karardır. Fazlara göre mikroservis kurmak, connector, worker, AI ve veri sözleşmelerini gereksiz biçimde dağıtır.

Korunacak yapı:

- Next.js tabanlı uygulama/BFF
- PostgreSQL ana işlem ve metadata verisi
- S3 uyumlu object storage ile ham artefact saklama
- Redis + BullMQ ile uzun süren araştırma işleri
- Python worker yalnızca analitik/NLP ihtiyacı gerçekten oluştuğunda

Değişmesi gereken nokta: Modüler monolith, yalnızca klasör yapısı değil; açık modül sınırları, ortak domain event'leri ve şema sözleşmesi olan bir yapı olarak tanımlanmalıdır.

### Source Registry ve Connector Adapter yaklaşımı

Bu karar doğru ve ürünün sürdürülebilirliği için zorunludur. Her kaynak için ayrı özel kod yazmak yerine, erişim yöntemi, lisans, maliyet, rate limit, ürün tipi uyumu ve retention politikası Source Registry'de tutulmalıdır.

Ek iyileştirme: Registry yalnızca teknik katalog değil, policy-as-code sistemi olmalıdır. Bir connector'ın aktif olması için teknik sağlık, hukuk/uyum onayı, maliyet limiti ve veri saklama politikası birlikte değerlendirilmelidir.

### Ham veri ve normalize veri ayrımı

Faz 4'teki Raw Artifact → Normalized Document → Relations modeli güçlü ve korunmalıdır. Bu model daha sonra kaynak gösterimi, hata ayıklama, yeniden işleme ve karar denetimi için temel sağlar.

Ek iyileştirme: Her dönüşüm için input hash, normalizer sürümü, işlem zamanı ve işlem sonucunu içeren ayrı bir Transformation Ledger eklenmelidir.

### Gated Decision Support yaklaşımı

Faz 7'deki Evidence Sufficiency Gate, karşıt kanıt, stability analysis ve Value of Information yaklaşımı çok doğru yöndedir. Özellikle Build ve Kill sonucunun kanıt azlığında verilmemesi önemlidir.

Ek iyileştirme: Bu sistem başlangıçta istatistiksel başarı olasılığı veya kesin ağırlıklı skor üretmeye çalışmamalıdır. Karar politikası sürümlenmiş, açıklanabilir ve kalibrasyona açık kalmalıdır.

## 1.2 Daha iyi veya daha güvenli alternatifler

### Arama sağlayıcısını şimdi kilitlememek

Brave birincil, Exa ikincil aday olarak düşünülebilir; ancak bunları kalıcı teknoloji tercihi olarak erken kilitlemek doğru değildir.

Öneri:

- Search Provider Adapter zorunlu olsun.
- En az iki sağlayıcı, aynı golden query seti üzerinde ölçülsün.
- Ölçümler: sonuç kapsama, kaynak çeşitliliği, güncellik, duplicate oranı, fetch başarısı, maliyet ve gecikme.
- Standart araştırmada daha deterministik web araması; Deep Research'te semantic search sağlayıcısı opsiyonel olsun.

Bing Search API'nin sonlandırılmış olması, tek sağlayıcıya bağımlı olmamak gerektiğini gösterir. [Microsoft duyurusu](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement)

Karar: Değiştirilmeli.

### Faz 6'da embedding ve HDBSCAN'i zorunlu başlamamak

Embedding, pgvector ve HDBSCAN doğru araçlar olabilir; fakat ilk sürümde zorunlu olursa ürünün operasyonel karmaşıklığı artar.

Önerilen aşamalı yaklaşım:

1. Exact duplicate, lexical aday üretimi, TF-IDF/BM25 ve yapılandırılmış claim extraction
2. Corpus hacmi ve yanlış negatifler ölçüldüğünde local multilingual embedding
3. Yeterli claim yoğunluğu oluştuğunda HDBSCAN/benzeri cluster deneyi
4. Her aşamada insan değerlendirmeli golden dataset ile kalite ölçümü

Sentence embedding modelleri semantik aday üretimi için uygundur; ancak benzerlik sonucu otomatik gerçek veya aynı problem sonucu değildir. [Sentence-BERT](https://aclanthology.org/D19-1410/)

Karar: Faz 6 planında “opsiyonel ve veri eşiğine bağlı” olarak daha güçlü vurgulanmalı.

### Faz 5'i doğrusal değil, Faz 6 ile döngüsel kurmak

Mevcut faz sırası Faz 5'i Faz 6'dan önce gösteriyor. Teknikte Gap Auditor, Faz 4'ün kapsama eksiklerini bulabilir; fakat en değerli boşlukların bir bölümü ancak Faz 6 problem/fiyat/rakip analizi sonrasında görünür.

Önerilen gerçek akış:

Faz 2 → Faz 3 → Faz 4 → Faz 6
                         ↓
                 Kanıt boşluğu var mı?
                         ↓
                      Faz 5
                         ↓
                    Faz 3 → Faz 4 → Faz 6

Faz 5, sıralı bir adım değil; Faz 6'nın da tetikleyebildiği koşullu araştırma döngüsüdür.

Karar: Değiştirilmeli.

### Hazır Deep Research sağlayıcısını ana motor yapmamak

Hazır sağlayıcılar hızlı başlangıç için yararlı olabilir; ancak nihai kanıt zinciri olarak kullanılmamalıdır.

Doğru yapı:

- Hazır sağlayıcı, yalnızca provider connector olabilir.
- Sağlayıcıdan gelen URL ve alıntılar Faz 3–4 hattından yeniden toplanır.
- Kullanılamayan URL veya source policy dışı kaynak, doğrulanmış kanıt sayılmaz.
- Maliyetli sağlayıcı yalnızca kullanıcı onayı/bütçesiyle çalışır.

Karar: Mevcut yaklaşım korunmalı.

---

# 2. Proje ölçeği ve uçtan uca kaldırabilirlik değerlendirmesi

## 2.1 Mevcut plan ölçeği kaldırabilir mi?

Evet, fakat iki şartla:

1. İlk sürümde connector sayısı sınırlı tutulursa
2. Aşağıdaki platform/güvenilirlik katmanları eklenirse

İlk sürüm için önerilen canlı connector seti:

- Web search adapter
- Official competitor website scanner
- GitHub
- Hacker News
- Stack Exchange
- Product Hunt
- YouTube
- Domain/RDAP/DNS/web footprint

Reddit, X, app store reviews, G2/Capterra, LinkedIn, Instagram, TikTok, reklam/funding/SEO kaynakları ilk gün bağımlılık olmamalıdır. Bu kaynaklar capability registry içinde tanımlanabilir; fakat erişim, lisans ve maliyet şartları karşılanınca açılmalıdır.

## 2.2 Eksik olan üretim altyapısı

### A. Güvenilir job çalıştırma

BullMQ kullanmak tek başına yeterli değildir. Araştırma ve normalizasyon işleri en az bir kez teslim edilebilir; bu yüzden tekrar çalıştırılmaya karşı güvenli olmalıdır.

Eklenmesi gerekenler:

- idempotency key
- processed message kaydı
- transactional outbox
- retry sınıfları: geçici hata, rate limit, policy block, kalıcı hata
- dead-letter queue
- iş timeout ve cancel mekanizması
- aynı Research Run'ın iki kez başlamasını engelleyen kilit
- run resume ve safe reprocessing kuralları

Transactional outbox ve idempotent consumer yaklaşımı, mesajın tekrar teslim edildiği yapılarda veri tutarlılığı için kullanılan standart dayanıklılık desenleridir. [Transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html), [Idempotent consumer](https://microservices.io/patterns/communication-style/idempotent-consumer.html)

Öncelik: P0 — uygulamaya başlamadan önce.

### B. Çok kiracılı yapı, yetkilendirme ve bütçeleme

Planlar kullanıcı verisinden söz ediyor; fakat tenant isolation, auth, billing ve kullanım kotası net değil.

Eklenmesi gerekenler:

- workspace veya tenant_id tüm iş verilerinde zorunlu olmalı
- Research Run, artefact, citation, plan, karar ve object storage prefix'leri tenant'a bağlanmalı
- row-level authorization veya servis katmanında zorunlu tenant scope
- araştırma bütçesi, token bütçesi, connector maliyeti ve kullanıcı kredisi için immutable usage ledger
- plan bazlı hard limit ve kullanım aşımında graceful stop
- kullanıcı/veri silme ve export akışı

Öncelik: P0 — ilk ücretli kullanıcıdan önce.

### C. Veri yönetişimi, lisans ve retention

Faz 3'te lisans/restriction alanı var; fakat bütünsel retention policy yok.

Eklenmesi gerekenler:

- her connector için izinli saklama süresi
- ham metnin mi, yalnızca metadata/alıntının mı saklanacağı
- silinen kaynak ve cache politikasının ayrımı
- kullanıcı silme talepleri
- kişisel veri minimizasyonu
- PII redaction veya pseudonymization politikası
- telifli içerik için alıntı uzunluğu ve tekrar kullanım sınırları
- kaynak erişim/politika değişikliklerini periyodik gözden geçirme

GDPR ilkeleri, amaca gerekli veriyle sınırlı kalmayı ve veriyi gerekli süreden uzun tutmamayı vurgular. [European Commission](https://commission.europa.eu/law/law-topic/data-protection/rules-business-and-organisations/principles-gdpr/overview-principles/what-data-can-we-process-and-under-which-conditions_en)

Öncelik: P0 — kaynak entegrasyonlarından önce.

### D. Crawler güvenlik sınırı

Kullanıcının girdiği veya arama sağlayıcısının döndürdüğü URL'ler sunucu tarafından fetch edildiği için SSRF riski oluşur.

Eklenmesi gerekenler:

- yalnızca HTTP/HTTPS
- URL parse ve DNS çözümleme sonrası private, loopback, link-local ve metadata IP bloklama
- redirect her adımda yeniden doğrulama
- egress network izolasyonu
- response size, MIME type, download time ve redirect limiti
- HTML dışındaki dosya türleri için ayrı işlem hattı
- credential içeren URL ve internal hostname reddi
- Playwright/browser worker için ayrı sandbox

OWASP, URL fetch yapan sistemlerde allowlist, ağ katmanı izolasyonu ve redirect/DNS kontrollerini özellikle önerir. [OWASP SSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)

Öncelik: P0 — crawler veya arbitrary URL fetch öncesi.

### E. Gözlemlenebilirlik ve kalite

OpenTelemetry kararı doğru; ancak hangi iş metriklerinin zorunlu olduğu ayrıca tanımlanmalıdır.

Eklenmesi gerekenler:

- trace_id: kullanıcı isteği → Research Run → connector task → artifact → analysis claim → decision
- her LLM çağrısında model, prompt sürümü, token, maliyet, latency ve schema sonucu
- connector health dashboard
- kaynak başına error/rate limit/policy block oranı
- plan başına süre ve maliyet
- citation completeness ve decision reproducibility metrikleri
- alarm eşikleri ve SLO tanımları

OpenTelemetry semantic conventions, uygulama ve platformlar arasında izlenebilir telemetry alanları için ortak adlandırma sağlar. [OpenTelemetry](https://opentelemetry.io/docs/specs/semconv/)

Öncelik: P1 — ilk beta öncesi.

### F. Değerlendirme ve kalibrasyon altyapısı

Bu, mevcut planın en büyük kalite eksiklerinden biridir.

Eklenmesi gerekenler:

- Anonimleştirilmiş golden idea seti
- Her fikir için beklenen Idea Brief, source plan, claim, duplicate, cluster ve karar rubric'i
- Connector contract testleri ve recorded response fixture'ları
- Prompt/schema regression testleri
- Claim extraction için source offset doğruluk testi
- Cluster coherence ve false merge testi
- Karar politikası için kullanıcı/uzman değerlendirmesi
- Gerçek kullanıcı geri bildirimiyle karar kalibrasyonu

Bu sistemin kalitesi, AI modelinin güçlü olmasından çok bu değerlendirme hattının kalitesine bağlı olacaktır.

Öncelik: P0 — Faz 1/2 prototipiyle birlikte başlamalı.

## 2.3 20–30 dakika vaadi için eksik performans planı

Ürünün ana vaadi hızlı karar hazırlığıdır; ancak mevcut plan çok sayıda connector ve worker içeriyor. Bu nedenle standard ve deep akış için performans bütçesi tanımlanmalıdır.

Öneri:

- Standard run: kısa bir ilk sonuç ve progressive completion
- İlk executive snapshot: mümkün olan en erken güvenli noktada
- Connector sonuçları geldikçe raporun kanıt bölümleri güncellenir
- Deep Research: ayrı uzun çalışma, kullanıcıya beklenen süre/maliyet gösterilir
- Her kaynak için timeout ve minimum kanıt eşiği tanımlanır
- Uzun çalışan bir kaynak tüm run'ı bloklamaz

Karar: Tartışılmalı; ürün deneyimi ve fiyatlandırma ile birlikte belirlenmeli.

---

# 3. Fazlar birlikte değerlendirildiğinde eksik görülen konular

## 3.1 Faz 0 — çapraz platform temeli eklenmeli

Bu bir kullanıcı akışı fazı değil; bütün fazların altında çalışan platform katmanıdır.

İçermesi gerekenler:

- Identity, tenant isolation ve authorization
- Billing, credit, cost ledger ve budget enforcement
- Schema Registry ve API versioning
- Source Policy Registry ve connector approval lifecycle
- Secrets management
- Object storage ve encryption
- Outbox, idempotency, retry, DLQ
- Audit/provenance ledger
- Observability ve SLO
- Data retention, deletion, privacy ve copyright policy
- Feature flag ve connector rollout
- Evaluation harness ve golden datasets

Bu katman eklenmezse faz planları mantıklı olsa bile üretimde kırılgan olur.

Karar: Yeni bir Faz 0 / Cross-Cutting Platform Foundation belgesi oluşturulmalı.

## 3.2 Fazlar arası ortak veri sözleşmesi eksik

Her fazın kendi şeması var; fakat bu şemaların ortak owner'ı, sürümleme yöntemi ve migration politikası tanımlı değil.

Eklenmesi gerekenler:

- Schema Registry
- Her event/veri nesnesi için version alanı
- Backward/forward compatibility kuralı
- Contract testleri
- Data migration politikası
- Immutable snapshot ve mutable çalışma kaydının ayrımı
- Hangi servisin hangi alanın owner'ı olduğu

Örnek kritik nesneler:

- Idea Brief
- Research Plan
- Source Policy
- Research Run
- Raw Artifact
- Normalized Document
- Claim
- Cluster
- Evidence Dossier
- Decision Dossier
- Usage Ledger

Karar: Faz 0'a eklenmeli; Faz 1–7 dokümanları bu registry'ye referans vermeli.

## 3.3 Faz 5 ile Faz 6 arasında geri besleme döngüsü eksik

Bu en önemli akış iyileştirmesidir.

Faz 5 sadece Faz 4'teki kaynak sayısı eksikliğini değil, Faz 6'nın bulduğu anlamlı boşlukları da kapatabilmelidir.

Örnek:

- Problem sinyali yeterli, fakat ödeme isteği belirsiz
- Rakip sayısı var, fakat rakiplerin yeni sürümünde şikâyet çözülmüş mü belirsiz
- Kullanıcı sesi güçlü, fakat tek coğrafyada yoğunlaşmış
- Fırsat hipotezi var, fakat karşıt kanıt zayıf

Bu durumda Faz 6, structured Research Gap Request üretmeli; Faz 5 bu isteği Policy Gateway ile araştırmaya dönüştürmelidir.

Karar: Faz 5, Faz 6 ve Faz 7 planları güncellenmeli.

## 3.4 İkincil araştırma ile birincil doğrulama ayrımı eksik

İnternet araştırması, gerçek kullanıcı doğrulamasının tamamı değildir. Araç bunu açıkça söylemelidir.

Eklenmesi gereken kavram:

Primary Validation Action

Örnekler:

- 5–10 hedef kullanıcı görüşmesi
- ücretli pilot talebi
- landing page / waitlist testi
- ön satış veya concierge MVP
- çözüm demosu üzerinden ödeme niyeti testi

Bu aksiyonlar Faz 7'nin Value of Information çıktısında önerilebilir; ürünün “Build” sonucu da “tam ürünü yap” değil, “dar doğrulama MVP'si inşa et” anlamına gelmelidir.

Karar: Faz 7'ye eklenmeli. Ayrı araştırma fazı olmak zorunda değildir.

## 3.5 Kullanıcı geri bildirimi ve düzeltme döngüsü eksik

Kullanıcı, sistemin bulduğu rakibin yanlış eşleştiğini veya bir alıntının bağlam dışı olduğunu söyleyebilmelidir.

Eklenmesi gerekenler:

- Claim, cluster, competitor ve source için kullanıcı feedback mekanizması
- accept, reject, incorrect, irrelevant, outdated etiketleri
- Feedback'in source verisini değiştirmeden analiz overlay'i oluşturması
- Feedback verisinin evaluation harness'e aktarılması
- Kullanıcı override ile sistem önerisini ayırma

Karar: Faz 4, Faz 6 ve Faz 7'ye eklenmeli.

## 3.6 Coğrafya, dil ve dikey risk modeli eksik

Faz 1/2 hedef pazar ve dil alabiliyor; fakat kaynak seçimi ve karar kalitesine etkisi daha net olmalı.

Eklenmesi gerekenler:

- country/region/language scope zorunlu veya açıkça unknown olmalı
- kaynak kapsamasının coğrafi önyargısı gösterilmeli
- regüle sektörlerde vertical risk pack tetiklenmeli
- sağlık, finans, hukuk, çocuklar, hassas veri gibi alanlarda özel uyarı ve karar sınırı olmalı
- Türkiye odaklı fikirde yalnızca İngilizce global kaynaklardan gelen sonucu evrensel kabul etmemeli

Karar: Faz 1, Faz 2, Faz 3 ve Faz 7'ye eklenmeli.

## 3.7 Citation ve rapor doğrulama servisi eksik

Provenance bilgisi var; fakat kullanıcıya gösterilecek citation üretiminin doğruluk kuralları ayrı tanımlı değil.

Eklenmesi gerekenler:

- Alıntı metni source segment offset'i ile doğrulama
- URL, başlık, yayın tarihi ve erişim tarihi
- Kısa alıntı limiti ve telif politikası
- Kaynak silinmişse last-seen ve erişim durumu
- AI yorumunun kaynak alıntısından tipografik/semantik ayrımı
- Citation completeness score

Karar: Faz 4/6/7 için ortak bir Citation Service olarak tanımlanmalı.

---

# 4. Önerilen güncellenmiş sistem akışı

Faz 0: Cross-Cutting Platform Foundation

Faz 1: Fikir toplama ve netleştirme

Faz 2: Araştırma planı üretimi

Faz 3: Araştırma ve kanıt toplama

Faz 4: Veri temizleme, standartlaştırma ve ilişkilendirme

Faz 6: Kanıt analizi ve içgörü üretimi

Koşullu döngü:
Faz 6'nın veya kullanıcının tespit ettiği kritik boşluk
→ Faz 5 Deep Research
→ Faz 3
→ Faz 4
→ Faz 6

Faz 7: Karar motoru ve yön önerisi

Faz 7 sonucu Investigate More ise:
- Faz 2/5'e yeni Research Gap Request
- veya Primary Validation Action önerisi

Faz 8: Raporlama, MVP planı, PRD, teknik plan, entegrasyon önerileri ve prompt paketi

Bu değişiklik, Faz 5'i bağımsız doğrusal bir aşama olmaktan çıkarır ve gerçek araştırma sisteminin iteratif doğasına uyar.

---

# 5. Önceliklendirilmiş karar listesi

| Öncelik | Karar | Önerilen aksiyon | Etkilenen fazlar |
| --- | --- | --- | --- |
| P0 | Faz 0 platform temeli | Yeni belge oluştur | Tümü |
| P0 | Job güvenilirliği | Outbox, idempotency, DLQ, cancel/resume ekle | 3, 4, 5 |
| P0 | Crawler güvenliği | SSRF/egress/redirect sandbox politikası ekle | 3, 5 |
| P0 | Tenant/billing/retention | Kullanım, yetki ve veri yaşam döngüsü ekle | Tümü |
| P0 | Evaluation harness | Golden dataset ve regression testleri tanımla | 1, 2, 4, 6, 7 |
| P1 | Faz 5–6 döngüsü | Structured Research Gap Request tanımla | 5, 6, 7 |
| P1 | Ortak Schema Registry | Versiyon, owner, migration ve contract testleri tanımla | Tümü |
| P1 | Citation Service | Alıntı doğrulama ve kaynak gösterme sözleşmesi ekle | 4, 6, 7 |
| P1 | User feedback loop | Claim/cluster/rakip düzeltme overlay'i ekle | 4, 6, 7 |
| P1 | Performance budget | Standard/deep süre, maliyet ve progressive sonuç hedefi belirle | 2, 3, 5, 8 |
| P2 | Embedding/HDBSCAN | Veri hacmi eşiği sonrası deneysel olarak aç | 6 |
| P2 | Search provider seçimi | Golden query set ile A/B değerlendirme yap | 3 |
| P2 | Vertical risk packs | Regüle sektör/coğrafya kurallarını genişlet | 1, 2, 3, 7 |

---

# 6. Son karar

Planın ana fikri ve fazların çoğu doğru yönde. En büyük iyileştirme ihtiyacı, yeni AI özelliği eklemek değildir.

Önce şu dört temel konu netleştirilmelidir:

1. Faz 0 platform güvenilirliği ve veri yönetişimi
2. Faz 5–6'nın iteratif araştırma döngüsü
3. Golden dataset ve kalite/kalibrasyon sistemi
4. Araştırma kaynaklarının teknik erişiminden önce lisans, güvenlik ve retention politikası

Bu iyileştirmeler yapılırsa ürün; geniş kaynak kullanan ama kırılgan bir AI araştırma aracı yerine, denetlenebilir kanıta dayanan ve zamanla kalibre olabilen gerçek bir startup decision-support platformuna dönüşür.
