# Kimlikli hesap ve proje API temel dilimi

Bu teslim genel kayıt, parola ile giriş, kalıcı session, çıkış ve proje
liste/detail/create uçlarını uygular. BE-03 ana paketinin artifact/export/status
yetkisi ve gerçek local frontend → Hetzner kabulü sonraki uçlarla doğrulanır;
bu temel dilimin geçmesi bütün BE-03'ün bittiği anlamına gelmez.

| Uç | Yetki ve sonuç |
|---|---|
| `POST /api/v1/auth/register` | Exact Origin, JSON; 201 Session ve HttpOnly cookie |
| `POST /api/v1/auth/login` | Exact Origin, JSON; 200 yeni Session; sunulan eski session iptal |
| `GET /api/v1/auth/session` | Geçerli cookie; public User/expiry/CSRF, ham session yok |
| `POST /api/v1/auth/logout` | Cookie + exact Origin + CSRF; kalıcı revoke, 204 ve cookie temizleme |
| `POST /api/v1/projects` | Cookie + Origin + CSRF; yalnız name girdisi, UUID server kaynaklı |
| `GET /api/v1/projects` | Owner filtresi + FORCE RLS; limit 1–100, owner bağlı keyset cursor |
| `GET /api/v1/projects/{project_id}` | Owner filtresi; foreign ve absent aynı 404 davranışı |

Parola 15–128 Unicode karakter; trim/case dönüşümü yok. `argon2-cffi==25.1.0`
RFC9106_LOW_MEMORY Argon2id (64 MiB, 3 geçiş, 4 lane) kullanılır. Sunulan
parola ve ham session hiçbir public DTO, validation hatası veya log'a eklenmez.
Unknown account girişinde aynı profilde dummy hash doğrulanır. İşlem başına
iki eşzamanlı hash slotu vardır; dolu kapasite güvenli 429 üretir.

Session 32 rastgele byte'tan base64url üretilir. DB'de yalnız SHA-256 session,
SHA-256(domain ayrımlı CSRF), owner ve zamanlar saklanır. Cookie adı
`demandrift_session`, path `/`, HttpOnly ve Secure zorunludur. Mutlak expiry
24 saattir; GET gizli yenileme yapmaz. Login/register yeni cookie oluşturur ve
sunulan eski session'ı aynı transaction'da revoke eder. CSRF karşılaştırması
constant-time yapılır. Duplicate Cookie/Origin/CSRF header ve yanlış/bitmiş
session kabul edilmez. Auth/project yanıtları `private, no-store` taşır;
public account/project timestamp'leri UTC olarak döner.

Auth policy `auth-2026-10-01.1`: account başına 10, doğrudan peer başına 100
deneme/600 saniye. Account ve peer bucket'ları tüm login/register yollarında
ortaktır; hashed anahtarlı PostgreSQL satırları deterministik kilitlenir.
Yeni API process'i sayaçları sıfırlamaz. Request içindeki Forwarded/XFF
başlıkları bu servis tarafından peer kimliği olarak kullanılmaz; deployment
proxy trust politikası OP-03'te ayrıca test edilir. Bu hız sınırı araştırma
bütçesinin yerine geçmez.

JSON input body parser/hash öncesinde 16 KiB ile sınırlandırılır; content-length
ve chunked gövde aynı limite tabidir. Form/yanlış MIME 415, büyük gövde 413,
bozuk girdi güvenli canonical ApiError üretir. DB hatası 503 olur; SQL, DSN,
parola veya sunulan input yanıt metnine katılmaz. Eski public F03 live preview
geçerli input için 410 döndürür; hesabı ve ortak bütçeyi atlayarak ağ çağrısı
yapamaz. Bounded adapter mock/harness dönüşüm testleri korunur.

Production (`APP_ENV=production` veya `DEMANDRIFT_REQUIRE_DATABASE=1`) startup
runtime DATABASE_URL, açık `CORS_ALLOWED_ORIGINS` ve migration 0004 ister.
Application role schema/table owner, superuser veya RLS bypass olamaz. 0004
frozen SQL auth_rate_limits yaratır; app role yalnız SELECT/INSERT/UPDATE ve
alembic_version SELECT alır. DDL/DELETE/TRUNCATE veya migration yazma izni
yoktur. Users/sessions/auth counters server içi lookup tablolarıdır; proje ve
araştırma ilişkileri FORCE RLS ve owner filtresiyle korunur. Migration admin
kimliği uygulama runtime'ına verilmez.

CORS tam origin listesi + credentials kullanır; wildcard yoktur. `API_ROOT_PATH`
prefix'i OpenAPI servers ve slash redirect'lerinde korunur. Backend cookie
Secure zorunluluğu local loopback için de kaldırılmaz. Local Next proxy cookie
aktarımı ve doğrudan cross-origin browser için `AUTH_COOKIE_SAME_SITE=none`
gereksinimi FE-03/OP-03'ün gerçek HTTPS/browser kabulünde ayrı değerlendirilir.
Frontend proxy modeli kullanıcıdan upstream URL veya model secret kabul etmez.

Geliştirme kontrolleri gerçek restricted PostgreSQL'de iki kullanıcı, expired
session, rotation/logout, owner cursor, Origin/CSRF, hash-only DB, gerçek
eşzamanlı rate-limit sınırı ve güvenli DB outage davranışını kapsar. Ayrı policy
kontrolleri chunked input ve prefix/OpenAPI/redirect'i doğrular. Bunlar final
87 senaryonun browser/Hetzner/backup/restore/rollback kabulü yerine geçmez.
