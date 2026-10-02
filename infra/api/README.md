# FastAPI build ve deploy

Hedef klasör `apps/api`. Bu teslim çalışan `/health` endpoint'i olan API temelidir; kullanıcı/proje/araştırma API'si, PostgreSQL/Redis/worker ve public HTTPS entegrasyonu değildir.

## Kullanım

Repo kökünde GitHub CLI ile oturum açmış, Actions çalıştırma yetkili kullanıcı:

```sh
bash scripts/build-backend.sh api <final-tested-main-SHA>
```

Bu komut final testleri geçen 40 karakterli güncel `main` SHA'sıyla `api-deploy.yml` başlatır; yerel değişiklikleri yüklemez. `.orchestrator` run kimliği veya bağımsız ara review/verify/integration kaydı gerekmez. Önce tüm işlevler tamamlanır, ardından manuel final CI çalıştırılır. Sunucu helper'ının hazır olması tek başına bütün ürünün final kabulü değildir. Laboratuvar için `bash scripts/build-backend.sh lab`.

- `api-ci.yml`: yalnız main üzerinde manuel final test turu; secrets kullanmadan API/DB/worker/frontend/infra testleri, runtime build ve sağlık kontrolü. PR veya push otomatik test başlatmaz.
- `api-deploy.yml`: yalnız manuel tetikleme; exact güncel `main` SHA ve o SHA'nın son başarılı API CI kontrolü zorunludur. Push deployment başlatmaz. Bu kapılardan sonra mevcut Hetzner test → build → servis güncelleme → sağlık kontrolü çalışır. PR ve diğer branch'ler deploy edemez.
- `build-test.yml`: laboratuvar final testi için yalnız manuel çalışır.

## Sunucu

GitHub hosted runner aynı kısıtlı SSH anahtarını kullanır. `build-api <SHA>` yönetici tarafından kurulan `/usr/local/sbin/demandrift-api-deploy` komutuna yönlendirilir. Genel self-hosted runner gerekmez. GitHub secrets/variable mevcut `HETZNER_BUILD_SSH_KEY`, `HETZNER_BUILD_KNOWN_HOSTS`, `HETZNER_BUILD_HOST` değerleridir.

Yönetici `infra/backend-build/demandrift-build` ve `infra/api/demandrift-api-deploy` dosyalarını `/usr/local/sbin/` altına root:root 0755 olarak, `compose.yml` dosyasını `/opt/demandrift-api/compose.yml` yoluna root:root 0600 olarak kurar; `/opt/demandrift-api/logs` oluşturur. Bu güvenilen sunucu dosyaları repo push ile otomatik yüklenmez; değişiklikleri incelenip yönetici tarafından kurulur.

Servis yalnız `127.0.0.1:18082` üzerinde. Kontrol: `curl -fsS http://127.0.0.1:18082/health`. Uzak geliştirme için `ssh -L 18082:127.0.0.1:18082 root@167.235.158.118` ile tünel açılabilir. Local frontend için public HTTPS/session/CSRF entegrasyonu OP-03'te yapılır. Frontend yayını bu çalışmada yapılmaz. Mevcut Gemini dosyası bu sağlık servisine verilmez.

F03 ham API yanıtları için Compose yalnız bu projeye ait `demandrift_api_artifacts`
named volume'unu `/data/artifacts` olarak bağlar. API container'ı salt-okunur
kalır; bu volume dışında yazamaz. Volume mount'ı, Dockerfile içindeki UID/GID
10001 sahipliğindeki dizinden ilk kullanımda izinleri devralır.

`demandrift-api` Compose projesi başka servislere dokunmaz. Container root değildir, salt okunur, capabilities kapalı, kaynakları sınırlıdır. API kaynakları regular dosyalarla ve boyut sınırıyla çıkarılır. Dependencies build aşamasında indirilir; test container'ının ağı kapalıdır. Repo Dockerfile'ı build kodudur: `main` yazma yetkisi güvenilen geliştiricilerde olmalıdır.

Başlangıçta ve build sonrasında güncel main SHA kontrol edilir; eski SHA reddedilirse yeni main için komutu tekrar çalıştırın. Build/test başarısızsa servis değişmez. Sağlık kontrolü başarısızsa önceki başarılı imaj geri alınır; ilk kurulumda başarısız proje kaldırılır. Başarı işareti yalnız sağlık kontrolünden sonra `/opt/demandrift-api/last-successful-sha` olarak güncellenir. Sağlık kontrollü güncelleme kısa kesinti yaratabilir; DB migration kapsamda değildir. Loglar `/opt/demandrift-api/logs`; SHA imajları rollback için tutulur, otomatik retention yoktur.
