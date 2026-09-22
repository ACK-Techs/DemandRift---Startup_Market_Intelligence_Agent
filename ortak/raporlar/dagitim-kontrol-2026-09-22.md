# Dağıtım kontrolü — 22 Eylül 2026

**Güncel sonuç:** Vercel frontend ve Hetzner veri-scripti Docker build/test otomasyonu çalışıyor. PR #2 main ile birleştirildi; push ve manuel GitHub çalışmaları başarılı. Aşağıdaki ilk inceleme ve onay bekleme kayıtları tarihçedir; ilgili engeller giderildi.

## Tamamlananlar

- GitHub: `ACK-Techs/DemandRift---Startup_Market_Intelligence_Agent`, varsayılan branch `main`. GitHub API kontrolünde **public**; private hedefi henüz uygulanmamış. Görünürlük değiştirilmedi.
- Hetzner: `167.235.158.118`, host `immense-machine-v1`; root SSH erişimi doğrulandı. Mevcut diğer uygulamalara müdahale edilmedi.
- `/opt/demandrift`: shallow/partial clone ve non-cone sparse checkout. Çalışma ağacında yalnız `research/source-access-lab/` var; `apps/web` yok. Commit: `dda14f9` (Merge remote-tracking branch 'origin/main'). Yerel henüz push edilmemiş faz klasör düzeni sunucuya kopyalanmadı.
- Sunucuda Python 3.10.12, Docker ve Docker Compose v5.1.1 mevcut. 55 Python dosyası AST sözdizimi kontrolünden geçti. Canlı kaynak sorgusu, Gemini çağrısı veya kapsamlı test çalıştırılmadı.
- Vercel projesi: `caglarkcs-projects/demandrift`. GitHub repo bağlantısıyla `main`, root `apps/web`, Next.js seçildi. Otomatik önerilen 42 backend ortam alanı kaydetmeden formdan çıkarıldı; API anahtarı yüklenmedi.
- Vercel dağıtım başarı ekranı görüldü ve https://demandrift.vercel.app/ açılarak arayüz doğrulandı. Özel domain eklenmedi.

## Backend ve Batuhan komutu

GitHub tree kontrolünde çalışan API uygulaması, Dockerfile/Compose veya `.github/workflows` yok. Actions API sonucu: `total_count: 0`. Bu nedenle `gh workflow run build-test.yml` şu an kullanılabilir bir komut değildir; önceki belgelerdeki tetikleme akışı plan düzeyindedir. Docker build veya servis sağlık testi yapılmış sayılmaz. Sunucuda runner, webhook veya otomatik pull servisi kurulmadı.

Sonraki backend teslimi: FastAPI giriş noktası ve bağımlılık tanımı, API/worker Docker yapılandırması, Redis/PostgreSQL kalıcı alanları, sağlık endpoint’i; ardından yetkileri sınırlandırılmış dağıtım tetiklemesi ve başarı/başarısızlık kontrolü. Test API URL’si ve Gemini anahtarı ayrıca sağlanacak.

## Frontend sınırı

Yayınlanan sürüm mevcut örnek verili arayüzdür; gerçek backend, kayıt/giriş veya araştırma yürütmesi bağlı değildir. Ekrandaki BUILD/örnek güven puanları eski mock tasarım içeriğidir; onaylı üç aşamalı ürün kararı değildir. Ayşenur’un planlanmış frontend düzenleme/entegrasyon görevlerinde düzeltilmelidir. Gerçek backend hazır olduğunda HTTPS API adresi ve CORS origin (`https://demandrift.vercel.app`) birlikte yapılandırılacak.


## Docker build kurulumu — sonraki çalışma

Hetzner’de `/opt/demandrift-build` alanı, bare kaynak deposu, yönetici sahipli Dockerfile ve `/usr/local/sbin/demandrift-build` kuruldu. Mevcut yetkili SSH bağlantısıyla `dda14f9` sürümü build edildi: 95 dosya (~10 MB), container içinde 70 offline test geçti. Canlı sitelere veya Gemini’ye istek atılmadı.

GitHub workflow ve Batuhan helper komutu izole checkout `/private/tmp/demandrift-deploy-work` içinde `af87bc5` commit’i olarak hazır. Bağımsız kod incelemesi, hatalı komut reddi ve dosya limit kontrolleri geçti. Önceki yerel plan dosyaları bu commit’e dahil edilmedi.

**Bekleyen erişim onayı:** Otomatik onay denetimi, GitHub Actions için `root authorized_keys` içine `restrict,command="/usr/local/sbin/demandrift-build"` kısıtlı kalıcı anahtar eklemeyi reddetti; bu yeni yetki için açık kullanıcı onayı istendi. Anahtar henüz sunucuya veya GitHub Secret'a eklenmedi. Workflow GitHub’a henüz push edilmedi; uçtan uca GitHub testi henüz yapılmadı.


## Kısıtlı SSH yetkisi onaylandı ve kuruldu

Kullanıcı onayı sonrasında açık anahtar Hetzner root authorized_keys içine yalnız `/usr/local/sbin/demandrift-build` komutuna izin verecek şekilde eklendi. Özel anahtar ve doğrulanmış host key GitHub Secrets'a, hedef adres repository variable'a kaydedildi. Yeni anahtarla normal `id` komutu exit64 ile reddedildi; geçerli `build dda14f9...` isteği Docker build ve70 testi başarıyla tamamladı.

Workflow ayrı `infra/hetzner-build` dalında yayınlandı. PR: https://github.com/ACK-Techs/DemandRift---Startup_Market_Intelligence_Agent/pull/2 . Otomatik onay denetimi doğrudan main push için ayrıca açık onay istedi. Main değişmedi; PR birleştirme onayı ve ardından GitHub uçtan uca tetiklemesi bekliyor.


## Uçtan uca kabul — tamamlandı

- PR #2 main'e birleştirildi: `a2851b6b04f2cc8a6d3d97fb5f1e92c35617ddce`.
- Otomatik push run başarılı: https://github.com/ACK-Techs/DemandRift---Startup_Market_Intelligence_Agent/actions/runs/35755465417
- `bash scripts/build-backend.sh` ile manuel run başarılı: https://github.com/ACK-Techs/DemandRift---Startup_Market_Intelligence_Agent/actions/runs/35755512269
- Hetzner 95 veri-scripti/fixture dosyasını paketledi; imajı build etti;70 offline test geçti. Workflow ve shell erişim kısıtı doğrulandı.
- Batuhan: `gh workflow run build-test.yml --repo ACK-Techs/DemandRift---Startup_Market_Intelligence_Agent --ref main` veya repo içinden `bash scripts/build-backend.sh`. Kendi GitHub hesabında repo yazma/Actions tetikleme yetkisi gerekir; Batuhan hesabına giriş yapılarak test yapılmadı.
- Yalnız ilgili backend/build dosyalarının main push'ları otomatik tetikler. Frontend-only/docs-only değişiklikler backend build başlatmaz. GitHub workflow başlatmak için SSH erişimi gerekmez.
- Bu akış mevcut veri scriptlerinin Docker build/test teslimidir. FastAPI servisi, API endpoint'i, Celery/PostgreSQL/Redis ürün runtime'ı henüz geliştirilmiş/yayınlanmış değildir.


## Gemini runtime anahtarı

Kullanıcının verdiği Gemini anahtarı yalnız Hetzner `/etc/demandrift/backend.env` dosyasına `GEMINI_API_KEY` olarak kaydedildi (root,0600). Anahtar repo,workflow,build context,container image veya Vercel'e eklenmedi. Henüz ürün API servisi olmadığı için runtime tüketimi/API geçerlilik testi yapılmadı; servis geliştirildiğinde bu dosya yalnız backend/worker runtime'a bağlanmalı. Veri çekme/araştırma AI araçları açılmadı.
