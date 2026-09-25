# DemandRift FastAPI

`apps/api` ana Python backend'in uygulama dizinidir. Bu ilk iskelet yalnız
`GET /health` sağlar; araştırma, kimlik doğrulama, PostgreSQL, Redis, worker ve
AI entegrasyonlarının uygulandığı anlamına gelmez. Güncel ürün tasarımı
[`ortak/mimari-ve-kararlar.md`](../../ortak/mimari-ve-kararlar.md) içindedir.

## Yerel çalıştırma

Python 3.13 ve repo kökünden:

```bash
python3.13 -m venv apps/api/.venv
apps/api/.venv/bin/python -m pip install -r apps/api/requirements-dev.txt
cd apps/api
.venv/bin/python -m pytest -q
.venv/bin/uvicorn app.main:app --reload --port 8000
```

`http://localhost:8000/docs` OpenAPI arayüzünü açar. `/health` yanıtı:

```json
{"status":"ok","service":"demandrift-api","revision":"development"}
```

`APP_REVISION` deploy edilen Git commit SHA'sını taşır. Değer uygulama açılışında
okunur. Endpoint sadece API sürecinin ayakta olduğunu gösterir; henüz bağlı
olmayan DB/worker servisleri için readiness garantisi vermez. Secret döndürmez.

## Docker test ve build

Repo kökünden:

```bash
docker build --target test -t demandrift-api:test apps/api
docker build --target runtime --build-arg APP_REVISION="$(git rev-parse HEAD)" -t demandrift-api:local apps/api
docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges -p 127.0.0.1:8000:8000 demandrift-api:local
```

Test ve runtime hedefleri ayrıdır; yayınlamadan önce test hedefi başarılı olmalıdır.
Runtime image test bağımlılıklarını içermez ve UID/GID 10001 ile çalışır. Docker
healthcheck `/health` üzerinden çalışır. Secret dosyaları Docker build context'ine
alınmaz; ileride eklenecek servis anahtarları yalnız çalışma zamanında sağlanmalıdır.

`.github/workflows/api-ci.yml`, API değişikliklerinde PR ve `main` push'larında
Docker test aşamasını, runtime image build'ini ve gerçek container health kontrolünü
GitHub-hosted runner üzerinde çalıştırır. Secret veya Hetzner erişimi gerektirmez;
Actions ekranından elle de başlatılabilir. Deploy ayrı workflow ile yönetilir.
