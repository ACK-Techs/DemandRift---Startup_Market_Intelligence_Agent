# Hetzner backend build

Mevcut veri laboratuvarını Docker imajı yapıp 70 offline sorgu/kaynak seçimi/bütçe testini çalıştırır. Henüz FastAPI servisi yok: bu workflow çalışan bir API yayınladığını iddia etmez. Gerçek API/worker geldiğinde servis dağıtımı ayrıca eklenecek.

## Batuhan'ın komutu

GitHub CLI ile repo yazma/Actions çalıştırma yetkisi olan hesabına giriş yaptıktan sonra:

```sh
gh workflow run build-test.yml --repo ACK-Techs/DemandRift---Startup_Market_Intelligence_Agent --ref main
```

Repo içinden alternatif: `bash scripts/build-backend.sh`.

Sonuç: GitHub → Actions → **Hetzner backend build and test**. `gh run list --repo ACK-Techs/DemandRift---Startup_Market_Intelligence_Agent --workflow build-test.yml --limit 5` ve `gh run watch RUN_ID --repo ACK-Techs/DemandRift---Startup_Market_Intelligence_Agent --exit-status` ile izlenebilir.

`main` branch'ine veri scripti veya build dosyası değişikliği push edilmesi de tetikler. Yalnız frontend/docs değişikliklerinde backend build atlanır. PR/fork ve başka branch deploy edemez. Kuyrukta eski kalan SHA mevcut main değilse açık hata ile reddedilir; yeni main sürümünü tetikleyin.

## Kurulum

- Hetzner: `167.235.158.118`; ayrı çalışma alanı `/opt/demandrift-build`; backend kaynak deposu `repository/` bare/partial clone. Frontend checkout edilmez.
- Yönetici `demandrift-build` dosyasını `/usr/local/sbin/demandrift-build` (root:root, 0755), Dockerfile'ı `/opt/demandrift-build/Dockerfile` (0600) olarak kurar. Sunucudaki bu iki dosya repo push ile otomatik değiştirilmez; değişiklikleri yönetici inceleyip yükler.
- Anahtarın authorized_keys satırı: `restrict,command="/usr/local/sbin/demandrift-build"` öneki. Yalnız `build <40hex SHA>` kabul edilir; shell/PTY/forwarding yok. Docker socket, host klasörü veya API key test container'ına verilmez.
- GitHub secrets: `HETZNER_BUILD_SSH_KEY`, `HETZNER_BUILD_KNOWN_HOSTS`. Variable: `HETZNER_BUILD_HOST`. Host key mevcut güvenilir SSH bağlantısından alınır; workflow StrictHostKeyChecking kullanır. Anahtar ekip üyelerine verilmez.
- Repo şu an public; private yapılınca sunucuya yalnız bu repoyu okuyabilen ayrı deploy key gerekir. Build SSH anahtarı GitHub repo okuma anahtarı değildir.

## Kontroller ve sınırlar

Kilit ile tek build; exact-current-main kontrolü; yalnız normal `.py/.csv/.json` dosyaları; en fazla 1000 dosya, dosya başına32 MiB, toplam128 MiB. Fetch180 sn, build600 sn, test300 sn sınırı var. Container kullanıcı65534, ağ kapalı, salt okunur, capabilities yok,512 MiB RAM,1CPU,128PID. Canlı siteler/Gemini çağrılmaz.

Başarılı sürüm `/opt/demandrift-build/last-successful-sha`; loglar `/opt/demandrift-build/logs`; imaj `demandrift-lab:<SHA>`. Başarısız build/test başarılı sürüm işaretini değiştirmez. Geçici context/container temizlenir. SHA imajları/logları korunur; bu ilk kurulum otomatik retention uygulamaz. Büyüme durumunda yönetici yalnız `demandrift-lab` imajlarını seçerek temizler, genel `docker system prune` kullanmaz. Sunucudaki diğer uygulamalara dokunulmaz.

FastAPI/PostgreSQL/Redis/Celery yayını, HTTPS API, CORS ve Gemini anahtarı bu veri-scripti build'inden ayrı sonraki teslimdir. Frontend Vercel'de `apps/web` olarak kalır.
