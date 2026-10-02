# DemandRift proje durum raporu

1 Ekim 2026, Europe/Istanbul. Bu rapor frontend ve backend'in aktif üç faz planına göre mevcut durumunu, teslim açıklarını ve planlama geriliğinin ölçülebilir sınırlarını gösterir. Sonuç: **arayüz prototipi, gerçek bir FastAPI temeli, kaynak laboratuvarı ve çalışan Hetzner API container'ı var; fikirden kalıcı ve kaynaklı araştırma raporuna tamamlanmış ürün akışı henüz yok.**

İncelenen yerel sürüm: `9f36ead7bacbc16f4b777147e423ce6b10b40348`. Checkout'un gerçek yeri `/Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent`; sohbetin eski `Desktop/GitHub` yolu artık mevcut değil. İnceleme başlangıcında çalışma ağacı temizdi.

## Kapsam ve kanıt yöntemi

Aktif kapsam, 22 Eylül kullanıcı kararıyla üç fazdır: fikir ve araştırma hazırlığı; veri toplama ve hazırlama; karar ve rapor. Eski yedi faz `trash/eski-planlar/` altında tarihsel referanstır. PM Manager rolü ve `orchestrate-research-platform` skill'i okunmuştur. Eski agent yolları aktif belge eşlemesiyle yorumlanmıştır; eski Temporal/yedi faz mimarisi yeni zorunluluk olarak geri eklenmemiştir.

Araştırılan iş fikri için Build, MVP/PRD, ürün özellikleri ve geliştirme planı üretmek kapsam dışıdır. **DemandRift'in kendisini tamamlamak için bu rapordaki geliştirme yol haritasını hazırlamak kapsam içindedir.** Olumlu araştırma sonucu `positive_findings` ve yönetici incelemesi gerektirir; otomatik geliştirme onayı değildir.

Kanıt düzeyleri ayrı tutulmuştur:

- **Kodda mevcut:** dosya ve statik davranış incelendi. Çalıştırılmış ve işlevsel olarak kabul edilmiş anlamına gelmez.
- **Tarihsel koşu:** tarihli rapor/result dosyasındaki sonuç. Bugünkü sürümde tekrar çalıştırılmış değildir.
- **Güncel sunucu metadatası:** SSH ile container/imaj/port/son başarılı SHA ve bellek bilgisi salt okunur alındı. Araştırma veya model testi yapılmadı.
- **Planlı veya doğrulanmamış:** dokümanda beklenen, henüz sonuç/kabul kaydı olmayan davranış.

Bu aşamada uygulama kodu, sunucu ayarı, servis, ortam değişkeni veya deployment değiştirilmedi. Paket kurulumu, build, ürün testi, frontend tarayıcı testi, Gemini veya canlı kaynak çalıştırması yapılmadı. Yalnız planlama belgeleri ve orkestrasyon kayıtları oluşturuldu.

## 1 Frontend durumu

### Mevcut yapı

Next.js uygulamasında 10 route var: `/`, `/new-validation`, `/projects`, `/research`, `/evidence`, `/competitors`, `/pain-points`, `/decision-reports`, `/settings`, `/help`. Gezinti iskeleti, tema tercihi, bazı yerel filtreler ve seçimler mevcut.

`apps/web` kaynaklarında backend veri çağrısı, API taban adresi yapılandırması veya gerçek proje/araştırma kaydı bağlantısı bulunmadı. İş verisini kalıcı saklayan yapı yok; görülen `localStorage` yalnız tema tercihi içindir. Dinamik proje/araştırma kimliği rotaları, kayıt/giriş akışı ve frontend test suite'i mevcut değil.

### Dokümana göre olması gereken ve gerçekte olan

| Alan | Beklenen işlev | Mevcut durum | Durum / kod kanıtı |
|---|---|---|---|
| Dashboard | Gerçek proje, araştırma, kanıt ve rapor özetleri; hata ile boş veriyi ayırma | Altı içerik bileşeni sahte sayıları kaldırmış, unavailable gösteriyor | Kısmi hazırlık; `components/dashboard/dashboard.tsx:20`, `metric-card.tsx:10` |
| Projeler | Kalıcı kimlikli liste/detail, doğru araştırmaya geçiş | Üç sabit proje; isimle yerel seçim; Open project işlemsiz | Prototip; `components/workspace/projects-board.tsx:5` |
| Fikir girişi | Girdiyi koruyan brief, alan doğrulama, köken ve bilinmeyenler | Yalnız adım/started state; uncontrolled alanlar, ortak taslak yok | Eksik; `new-validation-form.tsx:17`, `:41` |
| Netleştirme | Backend soruları, cevap/atlama, bilinmeyenlerle devam, kategori düzeltme | Sabit checkbox soruları; gerçek netleştirme/onay ekranı yok | Eksik; `new-validation-form.tsx:53` |
| Araştırma planı | Sürümlü niyet, kaynak, sorgu ve bütçe önizlemesi; onay | Sabit kaynak seçimi ve 2–4 saat tahmini | Prototip; `new-validation-form.tsx:60` |
| Başlatma | Kaydedilmiş onaylı plan, tek run, gerçek research_id | `setStarted(true)` ile Validation started | Sahte başarı; `new-validation-form.tsx:61` |
| Araştırma durumu | REST polling, üç faz, kaynak durumları, gerçek kullanım ve iptal | Dört eski aşama; %68, 318 kaynak, 129 kanıt, $4.20 sabit; yerel Pause/Resume | Prototip; `research-run.tsx:8`, `:19` |
| Kanıt | Citation/URL/tarih/bağlam/hash/sürüm ve doğrulama sonucu | Üç mock alıntı; Verified/Primary etiketi; kaynak açma işlemsiz | Gerçek kanıt bağı yok; `evidence-library.tsx:5`, `:22` |
| Rakip ve fiyat | Kaynaklı claim, resmi iddia/deneyim ayrımı, para birimi/dönem/tarih | Üç sabit rakip/fiyat; karşılaştırma işlemsiz | Prototip; `competitor-table.tsx:5` |
| Problemler | Bağımsız örnek sayımı, kaynaklar, kapsam ve karşıt bulgu | Sabit mention/trend; kanıt inceleme işlemsiz | Prototip; `pain-points-board.tsx:11` |
| Karar raporu | positive_findings/Modify/Kill/Investigate More; yeterlilik ve kaynaklar | BUILD, %82 confidence ve 91/88/86 skorları; ürün planına ekleme; sahte kayıt; export işlemsiz | Aktif kapsamla çelişiyor; `decision-report.tsx:8` |
| Tip ve fixture | Güncel sürümlü outcome ve yeterlilik sözleşmesi | BUILD/numeric confidence tipleri ve eski mock'lar duruyor; dashboard artık tüketmiyor | Sözleşme borcu; `lib/types/dashboard.ts:1`, `:17` |
| Ayarlar | Kapsamdaki ayarları backend onayıyla kaydetme | Sabit profil/uncontrolled alanlar; setSaved ile başarı | Sahte başarı; `settings-panel.tsx:7` |
| Üst bar ve eylemler | İşlevli gezinme/işlem, gerçek kullanıcı ve kayıt tarihleri | Ağustos 2026/Batuhan sabit; bazı başlık, bildirim ve yeni araştırma düğmeleri işlemsiz | Kısmi gezinme; `layout/top-bar.tsx:8`, `app-sidebar.tsx:64` |
| Kullanıcı hesabı | Genel kayıt, giriş, çıkış, oturum; proje bazlı yetki | Hesap ekranları ve oturum akışı yok | Eksik; aktif AY-06 ve ortak mimari gereksinimi |
| Yardım ve kapsam | Üç faz ve kanıt politikasıyla uyumlu açıklamalar | Tanımlanmamış confidence yöntemi; işlemsiz destek düğmesi | Düzeltme gerekli; `help-center.tsx:6` |
| Erişilebilirlik | Klavye, isimli kontroller, mobil panel odağı ve uzun içerik | Tıklanabilir rakip satırında klavye eşdeğeri yok; mobil panelde focus trap/Escape görülmedi | Statik risk; `competitor-table.tsx:14`, `app-sidebar.tsx:86` |

Bu tablodaki kısa component yolları `apps/web/` altındadır. Beklenenler `ortak/frontend-entegrasyon-ve-eksikler.md`, AY görevleri ve üç fazın veri sözleşmelerine dayanır.

### Frontend plan geriliği ve test durumu

AY-01 yalnız dashboard içerikleri bakımından alt teslim aşamasında; AY-02–AY-07 planlandı. Tam kabul ile kapanmış frontend görevi **0/7**. Bu oran kodun %0'ının yazıldığı anlamına gelmez; prototip ve dashboard düzeltmesi vardır.

28 Eylül raporu typecheck, lint, build ve ana sayfa HTML kontrollerinin geçtiğini kaydediyor. Browser görsel/responsive/klavye ve canlı API kontrolleri `not_run`. Referans verilen yerel `ay01-dashboard-20260928` run dizini bu checkout'ta bulunmuyor; kalıcı rapor ve Git commit'leri mevcut. Bugün hiçbir frontend kontrolü yeniden çalıştırılmadı.

Frontend açısından ürün teslim açığı: kullanıcı → kalıcı fikir → onaylı plan → tek araştırma → gerçek ilerleme → kanıt → kaynaklı rapor → yenilemede aynı kayda dönüş zincirinin tamamı henüz bağlı değil. Kullanıcının güncel talimatına göre geliştirme aşamasında frontend **local çalışacak**, Vercel deploy yapılmayacak.

## 2 Backend durumu

### Mevcut API ve sınırları

Backend artık yalnız sağlık endpoint'inden ibaret değildir. FastAPI/Pydantic uygulaması ve altı araştırma endpoint'i kodda mevcuttur; tam ürün backend'i ise henüz tamamlanmış değildir.

| Endpoint | Mevcut sorumluluk | Eksik ürün sorumluluğu |
|---|---|---|
| `GET /health` | Süreç liveness ve revision | DB/Redis/worker/readiness kontrolü yok |
| `GET /api/v1/research/categories` | Kontrollü kategori kataloğu | Kullanıcı fikrinin modelle kategorilenmesi/onayı yok |
| `POST /api/v1/research/plans` | Verilen alanlardan doğrulanmış plan taslağı | Orijinal fikir/netleştirme, kalıcı plan, ortak zarf ve kimlik bağları eksik |
| `GET /api/v1/research/source-plans/{category}` | Kaynak profili ve önerilmiş iş planı | Kullanıcıya ait onaylı planla kalıcı yürütme bağlanmamış |
| `GET /api/v1/research/initial-runs` | İlk değerlendirme koşularının tanımı | Kullanıcı araştırması oluşturma/durum/iptal/history API'si değil |
| `POST /api/v1/research/run-records/validate` | Kaynak koşusu kaydını doğrulama | `storage: not_persisted`; kayıt/iş yaratmıyor |
| `POST /api/v1/research/source-runs/f03` | Sabit F03 senaryosunda izinli kaynakları gerçekten çalıştırma; ham gövdeleri hashli dosyaya saklama | Genel üç faz araştırma yürütücüsü/rapor servisi değil |

F03, test fikri kimliğidir; yeni Faz 3 karar/rapor teslimi değildir. Çalıştırıcı üç izinli kaynağa ve kaynak başına en fazla beş sonuca sınırlıdır. Bu kullanım sınırlı kaynak adaptasyonu için yararlı bir başlangıçtır; kullanıcı metninden bütün ürün akışını sağlamaz.

### Dokümana göre olması gereken ve gerçekte olan

| Katman | Beklenen işlev | Mevcut olan | Açık teslim |
|---|---|---|---|
| Ortak sözleşmeler | schema_version/project_id/research_id/status/versions; tek producer/consumer şeması | API Pydantic modelleri, eski IdeaBrief Zod paketi ve Markdown taslakları | Kanonik sınırlar ve üretilmiş FE tipleri; belge/runtime route uyumu |
| Kullanıcı/proje | Genel kayıt, oturum, proje bazlı yetki; güvenli liste/detail | Auth, kullanıcı/proje depolama veya erişim kontrolü yok | Tüm hesap ve proje katmanı |
| Kalıcılık | PostgreSQL brief/plan/run/job/claim/citation/rapor; migration | DB sürücüsü/ORM/migration/runtime yok | Veri modeli, ilişkiler ve sürümleme |
| Uzun araştırma | Celery/Redis; kalıcı durum, sonlu retry, iptal, restart/recovery, idempotency | Senkron sınırlı kaynak endpoint'i; ürün worker/queue yok | İş yürütücüsü ve tekrar güvenliği |
| Faz 1 | Original idea, araçsız Gemini netleştirme, köken/onay, kategori, dinamik sorgu ve budget planı | Kontrollü kategori ve deterministik planlama bileşenleri | Model adaptörü, kalıcı brief/plan ve kullanıcı döngüsü |
| Kaynak registry | Yeteneğe/izin/kategori/pazar/dile uygun sürümlü seçim | Laboratuvar kataloğu, source-fit/planlama dosyaları | Kabul edilmiş runtime registry ve capability adaptasyonu |
| Faz 2 toplama | Planlı kaynak işi, izinli HTTP/API/RSS/arşiv, ham içerik/metadata; kısmi durum | Bağımsız scriptler ve sınırlı F03 runner; artifact volume | Genel yürütme ve kaynak işi kayıtları |
| Ağ güvenliği | Origin/DNS/redirect/robots/MIME/byte/zaman/kota sınırları | Lab'da bazı kontroller, F03 allowlist | Tüm üretim adaptörlerinde ortak guard ve bağımsız doğrulama |
| Normalizasyon | Dil/tarih/URL/boilerplate, segment/hash/version, tam lineage | Offline normalize/filtre scriptleri ve CSV çıktıları | Sürümlü runtime belge/segment katmanı |
| Tekrar ve bağımsızlık | Kopya/yakın tekrar, aynı kişi/kurum/sahiplik, unknown ayrımı | Lab sayım ve gruplama denemeleri | Kanonik kimlik/bağımsızlık modeli, unknown'un sayımdan çıkarılması |
| Bulgu ve alıntı | Araçsız Gemini verilen parçada claim, tam quote+offset+hash+version, SourceReport | Offline örnek veri/sayım raporları | Üretim extractor ve deterministik citation validator |
| EvidenceBundle | Site raporları, claims/citations, karşıt kanıt, kapsama, maliyet, bağımsızlık | Ürün runtime bundle üreticisi yok | Faz 2→3 doğrulanmış sözleşme ve depolama |
| Faz 3 policy | İlgili 3 bağımsız örnek/2 bağımsız kaynak + nitel kontroller; destek/karşıt ayrı | Laboratuvar nicel kontrolleri ve planlı senaryolar | Doğru karar uygunluk motoru ve adversarial kabul |
| Faz 3 rapor | Dört outcome, yönetici incelemesi, limitations/unknowns, kaynaklı gerekçe | Rapor endpoint'i/model/persistence yok | Validated DecisionReport ve UI devri |
| Gap döngüsü | Sonlu secondary gap aynı hattı kullanır; primary gap web'e dönmez | Belgelenmiş; runtime yok | Budget-aware ek araştırma, durma ve revizyon |
| AI/maliyet | Model/prompt/version, timeout/retry/schema, usage/cost, sert budget | Gemini SDK/istemcisi/runtime çağrısı yok | Üç faz AI adaptörü ve maliyet kaydı |
| İşletim | API/worker/DB/Redis readiness, log/metric, backup/restore, retention | API Docker/CI/deploy ve process health | Ürün işletimi, migration/restore ve veri yaşam döngüsü |

### Özel teknik ve veri riskleri

1. **Sözleşme drift'i:** `apps/api/docs/phase2-research-plan-contract.md:35` eski `/api/v1/research-plans` yolunu tarif ediyor; runtime `research_plan.py:224` altında `/api/v1/research/plans`. Aynı belgede eski faz numaraları var. `packages/contracts/src/idea-brief.ts:4` eski Faz1/Faz2 modelini referanslıyor. Önce tek sözleşme kaynağı kabul edilmeli.
2. **Ham dosya varlığı bütün araştırmayı kalıcı yapmıyor:** F03 raw içerik saklıyor; research/run kaydı DB'de yok. Yeniden okuma, kullanıcıya bağlama, restart sonrası devam ve rapor sürüm ilişkisi açık.
3. **Laboratuvar validator'ı üretim kabulü değildir:** `normalize_belgeler.py:592` CSV body alanını 4.000 karakterle kırpıyor; `kanit_sayimi.py:183` whitespace çıkarılmış değerin ilk 12 karakterini arıyor. Tam quote/offset/segment/version doğrulaması yerine kullanılamaz; ham dosya korunup tam metin runtime'da segmentlenmeli.
4. **3/2 politikası yalnız sayaç değildir:** `kanit_sayimi.py:109` bağımsızlık grubu hesapları gate'e tam taşınmıyor; `:128` kaynakları bütün kayıtlardan sayıyor; `:134` nicel geçiş sağlıyor. Aynı sahiplik, unknown kimlik, yanlış pazar veya ilgisiz destek/karşıt kayıtlar ürün gate'ini geçirmemeli.
5. **Veri kalitesi açığı:** 27 Eylül AS05 raporunda 77 kategori/niyet hücresinin 14'ü nicel eşiği geçmiş, 50'si bağımsızlığı bilinmeyen, 13'ü az gözlem. Problem/dissatisfaction/stated_wtp/use_case alanlarında kimlikli kullanıcı gözlemi isteyen hiçbir hücre geçmiyor. Bu tarihli ölçüm, bugün yeniden koşulmuş sonuç değildir; 14 hücre de nitel ürün yeterliliği sayılmaz.
6. **Kaynak erişimi sınırları:** Google Play JS kabuğu, Reddit/Trustpilot robots ve G2/Capterra challenge açık. Bunlar kaynak sağlığı/izin sorunudur; Kill/no_results diye sunulmaz. İzinli fallback ve kapsama boşluğu gerekir.
7. **Kabul kaydı koddan geride:** AS06-BT02 bildirimindeki access_method/archive kökeni eksikleri güncel `run_record.py` ve `25934c6` değişikliğinde karşılanmış; yeniden kabul kaydı kapanmamış. Bu eski bildirim güncel kod hatası diye tekrar açılmamalı.
8. **Model kimliği:** Kullanıcı seçimi Gemini 3.1 Flash Lite; resmi API model ID'si ve hesap erişimi henüz doğrulanmadı. Model adı SDK/erişim garantisi olarak yazılmamalı; uygulama aşamasında anahtarla doğrulanmalı.
9. **Plan sürüm/kimlik açığı:** `research_plan.py:187` plan UUID'sini yalnız brief kimliği/sürüm, kategori, mod ve registry sürümünden üretiyor. Pazar, dil, ek paket ve bütçe değişimleri aynı kimliği üretebilir; `plan_version` sabit 1. Kalıcı plan ve başlatma öncesi immutable sürüm/idempotency ayrılmalı.
10. **Registry ve doğrulama açığı:** `source_plan.py`, `initial_runs.py` ve `source_execution.py` ayrı sabit kaynak listeleri taşıyor. Run-record validator gerçek artefakt dosyası/hash/insan etiketinin kökenini kontrol etmiyor; yalnız gönderilen zarfı kontrol ediyor. Tek registry ve gerçek lineage doğrulaması gerekiyor.

### Hetzner mevcut durum ve yerleşim

1 Ekim'de SSH ile salt okunur alınan güncel metadata:

| Alan | Gözlenen durum |
|---|---|
| Sunucu | `167.235.158.118` |
| Container | `demandrift-api-api-1`, running; Docker health healthy |
| Çalışan API imajı ve son başarılı SHA | `c74fdb66d2f6343abc67526d8a18a7c597b74d45` |
| Host bağlantısı | `127.0.0.1:18082 → container 8000` |
| Yerleşim | Mevcut `/opt/demandrift-api`; projeye ait artifact volume |
| Diğer sistemler | Immense, First, AnoOns, Ajanda, Steward; toplam 34 çalışan container |
| Bellek snapshot'ı | Toplam 7.747 MiB, available 4.533 MiB; swap yok. Kapasite/yük testi yapılmadı |

Çalışan SHA ile yerel HEAD farkı sekiz dosya: altı dashboard bileşeni ve iki belge. **Mevcut API kodu bakımından deploy geriliği saptanmadı**; SHA farkının tümü frontend/dokümantasyon değişikliğidir.

Mevcut CI/deploy akışı GitHub hosted runner → kısıtlı SSH → test/build → API Compose güncelleme → sağlık kontrolü ve rollback'tir. Self-hosted runner metni tarihsel öneri; uygulanmış çözüm değildir. Compose bugün yalnız API'yi başlatır; worker/PostgreSQL/Redis yoktur. Process health, bütün araştırma fonksiyonlarının çalıştığını kanıtlamaz.

1 Ekim yerel sunucu envanteri DemandRift için public nginx route olmadığını kaydediyor. Bu tur nginx/HTTPS route yeniden sorgulanmadı; uygulama öncesinde güncel route dosyası ve port kaydı kontrol edilecek. Diğer uygulamaların kullanılan modeli: loopback API, proje ağı/volume/env ve nginx 443 üzerinden HTTPS.

22 Eylül raporunda Vercel prototip yayını ve Hetzner runtime env içinde Gemini anahtarı kaydı var. Bu tarihsel kayıtlar bugün yayının/anahtarın geçerliliğini doğrulamaz. Güncel kullanıcı talimatı frontend deploy'u sonraya bıraktığı için mevcut Vercel projesi bu çalışmada değiştirilmez. Yeni anahtar kullanıcı tarafından sağlanacak; mevcut secret içerikleri okunmadı/gösterilmedi.

## Planlama geriliği

### Takvim geriliği neden hesaplanamıyor

22 görevde `deadline_date`, `deadline_time` ve `estimated_time` boş; `ortak/calendar-import/README.md:26` bunların kullanıcı tarafından belirlenmediğini açıklıyor. Faz/sprint hedef bitişleri ve ekip kapasitesi de yok. Bu nedenle kaç gün/hafta veya yüzde geride olduğu hesaplanamaz.

22 Eylül plan/takvim tesliminden 1 Ekim'e **9 takvim günü geçmiş olması gecikme değildir**. Önce yeni kapasite, başlangıç, hedef ve kabul baseline'ı oluşturulmalı.

| Sorumluluk | Takipteki mevcut durum | Tam kabul sonucu |
|---|---|---|
| Frontend / AY | 7 görev; AY-01 alt teslim devam ediyor, diğerleri planlı | Tam kapanış kanıtı 0/7 |
| Backend / BT | 9 görev; BT-02 çalışılıyor, diğerleri planlı; API/infra kodu ayrıca ilerlemiş | Tam BT görevi kapanış kanıtı yok |
| Veri / AS | 6 görev; AS-01/06 ön kabul, AS-02 hazırlık, AS-03/04/05 kısmi | Ön kabul/kısmi veri teslimi tam ürün kabulü değil |

Takip dosyalarında **22/22 görev için tüm kabul koşullarıyla kapanış kanıtı bulunmuyor**. Bu, yazılmış kodun veya yapılmış işin sıfır olduğu anlamına gelmez. Üç fazın uçtan uca ürün kabulü de belgelenmemiştir.

### Teslim ve test açığının ölçülebilir kısmı

| Kanıt | Mevcut sayım | Yorum |
|---|---|---|
| API test kaynakları | 6 dosyada 26 statik test fonksiyonu | Bugün çalıştırılmadı; coverage oranı değil |
| Laboratuvar test kaynakları | 29 test dosyasında 695 statik test metodu | Script davranışı; ürün kabulü değil |
| Faz 1 sonuç takibi | 30/30 not_run | Gerçek kategori/run/model/kabul alanları boş |
| Faz 2 senaryoları | 24/24 planned | execution_result boş |
| Faz 3 senaryoları | 33/33 planned | execution_result boş |
| Toplam faz senaryosu | 87 | Takip dosyalarında sonuç kanıtı yok; birim testle örtüşen davranış olabilir |
| Frontend suite | Test runner/E2E suite bulunmadı | lint/typecheck/build tek başına kullanıcı işlevini kanıtlamaz |
| Canlı üç faz/model kabulü | Bu checkout'ta kapatılmış bütün akış koşusu bulunmadı | Kullanıcının istediği işlevsel kabul henüz yapılmalı |

Tarihsel 70 lab testi (22 Eylül), 4 API testi ve 7 mocked deploy senaryosu (25 Eylül), dashboard build/lint/typecheck (28 Eylül) kendi sürüm ve kapsamlarıyla anlamlıdır. Bugünkü 26/695 tanımın tamamı geçti veya ürün tamamlandı diye kullanılamaz.

### Plan ve durum belgelerinin güncelliği

README/PROJECT-STATE'deki “backend yok”, API README'sindeki “yalnız health” ve eski yedi faz referansları güncel kodun gerisinde. Bazı görevler kodda ilerlemiş fakat kabul kaydı kapanmamış. Bu yüzden yalnız yapılacaklar listesinden veya belge tarihinden ilerleme yüzdesi üretmek yanıltır.

Takip sistemi geliştirmede şu ayrımı korumalı: planlandı → kod mevcut → otomatik kontrol geçti → işlevsel kontrol geçti → bağımsız inceleme → sahibi tarafından kabul edildi. Durum belgeleri gerçek API/ekran/runtime teslimiyle birlikte güncellenecek.

## Öncelik sonucu

Frontend'in ilk işi kalan mock/sahte başarı ve kapsam ihlallerini gidermek, sonra kanonik sözleşme ve gerçek hesap/proje akışına bağlanmaktır. Backend'in ilk işi ortak sözleşme, PostgreSQL kimlik/sürüm modeli, oturum/proje erişimi ve kalıcı iş yürütücüsüdür. Faz 1/2/3 bu temele kademeli bağlanmalıdır.

Tamamlama, test ve Hetzner yayın sırası ayrı [yol haritasında](tamamlama-test-ve-hetzner-yol-haritasi-2026-10-01.md) verilmiştir. Salt kod/build kabulü yeterli değildir; local frontend → canlı Hetzner backend → gerçek kaynak/model → doğrulanmış kanıt/rapor işlev zinciri ve hata/kurtarma senaryoları birlikte kabul edilmelidir.

## Kaynaklar

- [Aktif kapsam ve başlangıç](../../README.md), [belge eşlemesi](belge-esleme.md), [PM yeteneği](../../.agents/skills/orchestrate-research-platform/SKILL.md), [PM rolü](../../.orchestrator/roles/pm-manager.md).
- [Mimari](../mimari-ve-kararlar.md), [veri sözleşmeleri](../veri-sozlesmeleri.md), [AI/ürün kuralları](../RULES.md), [3/2 policy](../kanit-yeterliligi-ve-karar-kurallari.md), [kalite/test](../kalite-ve-test-ilkeleri.md).
- [Frontend planı](../frontend-entegrasyon-ve-eksikler.md), [AY görevleri](../gorevler/aysenur.md), [dashboard alt teslimi](ay01-dashboard-2026-09-28.md), [BT görevleri](../gorevler/batuhan.md), [AS görevleri](../gorevler/ayselin.md).
- [API giriş](../../apps/api/app/main.py), [plan](../../apps/api/app/research_plan.py), [source plan](../../apps/api/app/source_plan.py), [run record](../../apps/api/app/run_record.py), [F03 runtime](../../apps/api/app/source_execution.py), [mevcut Compose](../../infra/api/compose.yml), [API işletimi](../../infra/api/README.md).
- [Faz 1 sonuç takibi](../../faz-1-fikir-ve-arastirma/tests/kategori-sonuc-takibi.json), [Faz 2 senaryoları](../../faz-2-veri-toplama-ve-hazirlama/tests/planlanan-senaryolar.json), [Faz 3 senaryoları](../../faz-3-karar-ve-rapor/tests/planlanan-senaryolar.json), [takvim açıklaması](../calendar-import/README.md).
- [AS05 sayım raporu](../../faz-1-fikir-ve-arastirma/veri-laboratuvari/AS05-SAYIM-RAPORU.md), [AS04 hata raporu](../../faz-1-fikir-ve-arastirma/veri-laboratuvari/AS04-HATA-RAPORU.md), [AS06 uyum bildirimi](../gorevler/geri-bildirim/AS06-BT02-UYUM-2026-09-27.md).
- [Dağıtım planı](../dagitim-ve-ortam-plani.md), [tarihsel dağıtım kontrolü](dagitim-kontrol-2026-09-22.md), [güncel planlama metadata kaydı](planlama-kanitlari-2026-10-01.json).

Sunucu envanteri dış yerel kaynak: `/Users/caglarkc/Desktop/ACK TECHS/sunucu-envanteri/2026-10-01/SUNUCU-RAPORU.txt` ve `steward/project-port-registry.json`. 34 container, çalışan SHA/port/bellek bilgisi bu tur SSH ile ayrıca doğrulandı; envanterin public routing kısmı yeniden doğrulanmadı.
