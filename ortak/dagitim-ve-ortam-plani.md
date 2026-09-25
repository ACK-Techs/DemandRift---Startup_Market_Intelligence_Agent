# Hetzner backend ve Vercel frontend — dağıtım planı ve durum

**22 Eylül 2026 durumu:** Frontend https://demandrift.vercel.app üzerinde yayında (`main`, root `apps/web`, Next.js). Hetzner `/opt/demandrift-build` altında kısıtlı SSH tetiklemesiyle Docker veri-scripti build/test akışı kuruldu. GitHub `build-test.yml` push ve manuel tetiklemesi başarıyla doğrulandı (70 offline test). Batuhan `gh workflow run build-test.yml --repo ACK-Techs/DemandRift---Startup_Market_Intelligence_Agent --ref main` komutunu kullanabilir. Genel runner yerine yalnız build komutuna izin veren anahtar kullanılıyor. FastAPI/worker/veritabanı servis yayını hâlâ sonraki backend teslimidir. [Kontrol raporu](raporlar/dagitim-kontrol-2026-09-22.md).

**25 Eylül 2026 güncellemesi:** `apps/api` FastAPI sağlık servisi ve ayrı `api-ci.yml` / `api-deploy.yml` eklendi. Tek komut `bash scripts/build-backend.sh`; laboratuvar için sona `lab` eklenir. GitHub hosted runner → kısıtlı SSH yaklaşımı sürer; aşağıdaki self-hosted runner önerisi uygulanmış kurulum değildir. [Güncel API işletim belgesi](../infra/api/README.md).

## Kesinleşen yerleşim

| Bileşen | Yer / sorumluluk |
|---|---|
| Kod deposu | Private GitHub repository; Hetzner tarafında kodu çekmek için erişim sağlanacak. Depo ayarı/erişim bu çalışmada değiştirilmedi. |
| Backend | Hetzner: Python + FastAPI + Pydantic. |
| Uzun işler | Hetzner: ayrı Celery worker; Redis kuyruk; kalıcı araştırma durumu PostgreSQL. Vercel isteği içinde uzun crawl işi yürütülmez. |
| Veri | PostgreSQL ve kalıcı ham dosya alanı; deploy/image rebuild bu alanları silmez. |
| Backend kurulum | Docker Compose: API, worker, Redis ve PostgreSQL. Yerel frontend container opsiyonel; yayınlanan frontend Vercel'de. |
| Frontend | Mevcut Next.js uygulaması Vercel'e bağlanacak; Ayşenur arayüz/API entegrasyonunu hazırlayacak. |
| API erişimi | Çağlar test için backend API erişimini/adresini sağlayacak; tam URL ve HTTPS ayarları kurulum aşamasında belirlenecek. |
| Gemini anahtarı | Çağlar Batuhan’a verecek; yalnız backend/worker runtime yapılandırması. Vercel'in tarayıcıya açık değişkenlerinde bulunmaz. |
| Kullanıcılar | Genel kayıt açık; kullanıcı oturumu ve proje bazlı erişim kontrolü sürer. Uygulama hesabı deployment yetkisi değildir. |

## Planlanan GitHub tetikleme akışı

Batuhan belirlenen deployment branch'ine push attığında veya manuel GitHub workflow komutuyla tetiklediğinde Hetzner kodu alacak, offline kontrolleri ve Docker build'i yapacak, başarılı sürümü test ortamına geçirecek. Bu akışta Batuhan’ın doğrudan SSH/masaüstü hesabı kullanması gerekmeyecek.

Planlanan uygulama GitHub Actions ve Hetzner'de projeye ayrılmış self-hosted runner'dır. Runner kayıt/izolasyon ve çalışma yetkileri kurulum sırasında yapılandırılacak. Manuel `workflow_dispatch` ile `gh workflow run WORKFLOW` kullanılabilir; workflow tanımı default branch'te olmalı, tetikleyen hesabın uygun repo yetkisi bulunmalı. [Manuel workflow referansı](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

Dağıtımın beklenen davranışı:

1. Yalnız belirlenen repo/branch ve yetkili manuel istek; genel kullanıcı veya fork/PR otomatik deploy yetkisi almaz. Branch adı henüz verilmedi, uydurulmaz.
2. İlgili commit SHA ayrı checkout'a alınır; kişisel geliştirme klasöründe pull/reset yapılmaz.
3. Offline kontroller → Docker build → servis güncellemesi → sağlık kontrolü. Canlı kaynak/Gemini testleri her push'ta çalışmaz; ayrı tetiklenir.
4. Aynı ortama deploy seri yapılır; eski commit yeni sürümü sonradan ezmez. Başarısız build çalışan sürümü değiştirmez. Sağlık hatası/DB migration geri dönüşü kurulum planında somutlaştırılır.
5. Loglar ve commit/image kimliği izlenebilir olur; Batuhan sonucu GitHub ve uygulama üzerinden kontrol eder. DB/ham veri volume'ları korunur.

Runner GitHub'a dışarı doğru bağlantı kurar; tetikleme için SSH paylaşımı gerekmez. Ancak build kodu runner ortamında çalışır: makineye SSH verilmemesi kod çalıştırma yetkisini ortadan kaldırmaz. Runner'a kişisel dosyalar veya ilgisiz servis erişimi verilmez; gerekirse proje için ayrı VM kullanılır. [Runner iletişimi](https://docs.github.com/en/actions/reference/runners/self-hosted-runners), [erişim sınırları](https://docs.github.com/en/actions/reference/security/secure-use).

## Vercel ↔ Hetzner bağlantı teslimi

- Ayşenur API adresini ortam ayarından alabilen frontend, gerçek yüklenme/hata/kısmi durumlar ve sürümlü istek/yanıt eşlemesini hazırlar.
- Batuhan FastAPI/OpenAPI, kullanıcı/proje yetkisi, frontend origin izinleri ve oturum davranışını hazırlar. CORS bir kimlik doğrulama mekanizması değildir.
- Çağlar ile kurulumda Vercel projesi/repo bağlantısı, Hetzner API HTTPS adresi, ortam değişkenleri, izinli origin'ler ve oturum/cookie/CSRF gereksinimleri birlikte ayarlanır. Domain ve kimlik bilgileri bu belgeye eklenmez.
- Kabul kontrolü: Vercel'den kayıt/giriş → fikir gönderme → doğru research_id → gerçek iş durumu → kaynaklı rapor; yenileme ve hata durumları; başka kullanıcının projesine erişimin reddi. Bunlar sonraki çalışmanın kontrolleridir, bugün çalıştırılmadı.

## Kurulum sırasında alınacak bilgiler

Hetzner işletim sistemi/bağlantı yöntemi ve proje izolasyonu; GitHub repository adresi, erişim yöntemi ve deployment branch'i; Vercel proje/domain ve API adresi. Bu bilgiler planlama teslimini engellemez; şimdi tek tek soru olarak açılmayacak. Kurulum adımı başlamadan birlikte alınacak.
