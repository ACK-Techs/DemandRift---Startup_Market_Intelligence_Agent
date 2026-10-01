# DemandRift — durma ve devam notu, 1 Ekim 2026

Kullanıcı mevcut çalışmanın kabul edilmiş değişikliklerini pushlayıp kalan işleri kaydetmemizi istedi. Yeni ürün işi başlatılmıyor. Proje tamamlanmadı: **42 ana paketin 6'i kabul edildi; 36 ana paket açık. 87 zorunlu final senaryosu henüz çalıştırılmadı.** Sayım beş uygulama/altyapı entegrasyonunu ve tamamlanmış QA-01 başlangıç doğrulamasını içerir. Alt teslimlerin commit sayısı ana paketlerin tamamlandığı anlamına gelmez.

## Repo ve kalıcı kayıtlar

- Gerçek checkout: `/Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent`. Sohbetteki `Desktop/GitHub/...` yolu mevcut değil.
- Branch: `main`; kaynak snapshot HEAD: `f611a1d56f0a600fc9b9e029a998d395a66038db`. Bu notun kendi yayın SHA'sı Git geçmişinden okunur.
- Canlı run: `.orchestrator/runs/tamamlama-20261001/run.json`, revision **504**. Sonradan devir kabul kayıtlarıyla ilerleyebilir.
- `.orchestrator/archives/tamamlama-20261001/` git ile taşınabilir run, olay, sonuç, failed geçmişi, kontrol kayıtları ve SHA manifestini saklar. Tam yaklaşık 96 MB yerel run ayrıca korunur; arşiv README sınırları ve geri yüklemeyi açıklar.
- Başlangıçtaki üç kullanıcı raporu yerelde, ilk hashleriyle aynen korunur; bu çalışmanın checkpoint'lerine stage edilmez. `initial-user-files.json` hashleri arşivdedir.

## Tamamlanan davranışlar

Kanonik Pydantic → JSON Schema → TypeScript sözleşmesi ve güvenli frontend API istemcisi hazır. Mock rapor/liste/sahte başarı kaldırıldı; taslak, tema, mobil menü ve gezinme düzeltildi. Next/bağımlılık güvenlik güncellemeleri yapıldı. Vercel otomatik Git yayını kapalı; backend dağıtımı manuel kabul edilmiş SHA ve başarılı CI kapısına bağlı.

PostgreSQL foundation, owner izolasyonu, immutable Brief/Plan/onay ve sürümlü evidence repository kabul edildi. Migration 001–003 frozen; tam snapshot graph ve alıntı/Unicode/hash/sürüm bağları için DB/repository kontrolleri var. Bu, canlı kaynak edinme veya model semantiğinin final kabulü değildir.

Son alt teslim **BE-03 auth-core R1**: Argon2id, hash-only kalıcı oturum/CSRF, Secure+HttpOnly cookie, expiry/rotation/logout, exact Origin+CSRF, owner proje oluşturma/liste/detay ve PostgreSQL'de ortak throttle. Migration 004 ve startup güvenli rol/head kontrolleri var. Eski public F03 execution endpoint artık valid isteklerde 410 döndürür; auth/budget kapılarını atlayarak canlı egress çalıştırmaz.

İlk auth-core adayı 8 bozuk cursor girdisinde 500 üretti. İlk bağımsız FAIL ve gerçek restart kanıtları korunur. R1 tüm cursor alanlarının JSON string olmasını zorunlu kılar: **216 test geçti; 134 gerçek PostgreSQL + 82 offline, sıfır skip. 8 yeni regresyon ve 108 bağımsız cursor kontrolü geçti.** Şema üretimi ve contracts/web TypeScript geçti. Önceki olumlu restart/hash-only/throttle kanıtlarının tekrar kullanımı açıkça belirtilir; yeniden çalıştırılmış gibi sayılmaz.

Son yayınlanan API kodu `f611a1d56f0a600fc9b9e029a998d395a66038db`; [Linux CI 36884845994](https://github.com/ACK-Techs/DemandRift---Startup_Market_Intelligence_Agent/actions/runs/36884845994) başarıyla tamamlandı. Fiili **134 PostgreSQL (sıfır skip) + 82 ağ erişimi kapalı offline = 216 farklı test**; şema/TypeScript ve non-root/read-only/cap-drop Docker runtime kontrolleri geçti. Bu sonuç Hetzner dağıtımı veya 87 final senaryosunun kabulü değildir. Devir notu/arşivi commit’i ürün kodunu değiştirmez; kendi yayın SHA’sı daha sonra Git geçmişinde bulunur.

## Tam olarak buradan devam et

1. Bu notu, üç başlangıç raporunu, `AGENTS.md`, proje orchestrator skill'ini, pm-manager rolünü ve aktif üç faz/ortak mimari belgelerini tam oku. Eski yedi fazı aktif mimari olarak geri getirme. Kullanıcının üç faz ve tek Git yayıncı talimatı önceliklidir.
2. `git status`, `git rev-parse HEAD`, remote SHA ve arşiv SHA kontrollerini yap. Kullanıcı değişikliklerini koru. Run restore gerekiyorsa mevcut yerel run üzerine sessizce yazma; arşiv README'yi izle. Run'ı validate et; failed geçmişini silme.
3. Kabul edilmiş auth-core SHA `f611a1d` ve başarılı Linux/Python3.13/PostgreSQL/Docker CI `36884845994` kanıtını oku; bütün kanıtlar arşivde. Sonraki API değişikliğinde yeni yayımlanan SHA için CI kapısını tekrar tamamla. CI başarısızsa revision işi aç; fail/not_run kabul sayma. BE-03 ana paketini tamamlandı sayma: korumalı status/artifact/export API, FE-03 ve OP-03/BE-15 kapsamı açık.
4. **Sıradaki bağımsız hazır paket BE-05**: araçsız Gemini adaptörü ve PostgreSQL'de atomik ortak budget reservation ledger. BE-04 için core auth CI kapısını tamamla; Celery/Redis persistent job/outbox/idempotency, lease/retry/cancel/recovery gerekir. BE-07 kalıcı Faz 1 plan/onaydan önce sahte demo araştırması başlatma.
5. Her backend dilimi hazır olunca FE-03 güvenli local backend proxy+hesap/oturum akışına, sonra gerçek proje/fikir/plan/run/kanıt/rapora bağla. FE-02 logout204 desteği henüz yok; bunu sözleşmeye uygun ekle. Raw session cookie veya parola frontend storage'a gitmez; kullanıcı değişimi/expiry'de eski owner yanıtları yeni oturuma yazamaz.
6. BE-04/05/16A ve kabul kapıları sonrası OP-02 API/worker/PG/Redis runtime'ını mevcut Hetzner servis düzeninde kur; OP-03 gerçek HTTPS/local origin/session/CSRF kabulünü yap. Henüz DemandRift runtime değişmedi; ikinci servis/port veya ortak DB kullanma.
7. BE-06 kaynak registry/egress → BE-07 Faz1 → BE-08–12 toplama/normalizasyon/filtre/claim/citation/bundle → BE-13–14 policy/rapor/sonlu gap sırasıyla run DAG bağımlılıklarını izle. Aynı run'ın bütçesini retry/restart/gap ile sıfırlama. Gap önerisi yürütme yetkisi değildir; yeni scope/plan onayı ve sürüm bağları gerekir.
8. QA-03/04/05 toplam **30+24+33=87** fiili zorunlu senaryo; QA-06 model semantiği, QA-07 gerçek tarayıcı local→Hetzner iki kullanıcı, QA-08 restart/Redis outage/budget/cancel/rate-limit/backup restore/rollback ve diğer servislerin korunması ayrı kabul kapılarıdır. Zorunlu fail/not_run/not_verified finali engeller.

## Runtime, erişim ve test bütçesi

- Local frontend: `http://127.0.0.1:3010` (bu durma sırasında HTTP200). Henüz gerçek Hetzner auth/araştırma akışına bağlı değildir. Dev server tekrar başlatılabilir; bu URL'nin gelecekte açık kalması garanti değildir.
- Hetzner: `167.235.158.118`, mevcut DemandRift loopback **18082**, `/opt/demandrift-api`, Compose proje `demandrift-api`, mevcut artifact volume korunacak. OP-01 salt-okuma baseline ve diğer 33 container fingerprint'i run/evidence içinde. Henüz yeni worker/PG/Redis/HTTPS/deploy/restore/rollback yapılmadı.
- **Frontend Vercel'e veya başka hosting'e deploy edilmez.** Git push frontend yayını tetiklemez; backend deploy otomatik yapılmaz.
- Gemini credential yalnız backend/worker için repo dışında izinli runtime dosyasında tutuluyor. Değeri Git'e, nota, log'a, frontend'e veya Docker image'a konulmaz. Korunan yerel konum `/tmp/demandrift-runtime-20261001/gemini.key`; dosya geçici dizinde olduğundan devam ederken varlığını ve 0600 iznini kontrol et, içeriğini terminale dökme. Henüz gerçek provider/model erişimi doğrulanmadı, ücretli çağrı **0**.
- Kullanıcının tüm deneme/retry'lar için ortak onayı: **$5; 300 dış istek; 50.000.000 byte; 150 sayfa; 1000 kayıt; 1800 saniye; 300.000 token; concurrency2.** Atomik global ledger kabul edilmeden ücretli çağrı başlatma. 30 dakikalık suite saatini geliştirme sırasında erken başlatma; final canlı koşu hazır olunca başlat.
- Plan model ID `gemini-3.1-flash-lite`. Key'nin Developer API veya Vertex Express route/erişimi doğrulanmadı. Developer fiyat kanıtı Vertex fiyatının kanıtı değildir; gerçek route/model/fiyatı resmi kaynakla doğrula, sessiz model fallback yok. Tools/grounding/search/URL context/shell kapalı kalır.
- Local PostgreSQL16.15: Root UNIX-only16432 `/tmp/demandrift-postgres-20261001/socket`; bağımsız doğrulayıcı UNIX-only16433. Bunlar test cluster'larıdır; üretim/veri backup'ı değildir. Aynı cluster'da başka reviewer fixture'i varken restart yapma.
- Temp venv: `/tmp/demandrift-baseline-20261001/venv`; Python3.14.4. CI Python3.13; local Docker runtime yok, Docker kanıtı GitHub CI'dan gelir.

## Doğrulama komutları

```sh
node .orchestrator/bin/orchestrator.mjs validate .orchestrator/runs/tamamlama-20261001/run.json
PYTHONPATH=apps/api /tmp/demandrift-baseline-20261001/venv/bin/python apps/api/scripts/generate_contracts.py --check
npm run typecheck --prefix packages/contracts
npm run typecheck --prefix apps/web
DEMANDRIFT_DB_TESTS=1 DEMANDRIFT_TEST_ADMIN_URL='postgresql+psycopg://demandrift_admin@/postgres?host=/tmp/demandrift-postgres-20261001/socket&port=16432' PYTHONPATH=apps/api /tmp/demandrift-baseline-20261001/venv/bin/python -m pytest -q apps/api/tests
```

Bunlar mevcut offline/API/DB kontrolleridir; 87 final/live/browser/işletim testini tamamlamaz. Running session gerçek exit0 vermeden PASS kaydı yazma. Beklenen eski test sayılarını fiili sayımla karşılaştır.

## Ana iş paketi durumu

| İş | Kabul durumu | Kapsam |
|---|---|---|
| BE-01 | Kabul edildi | Kanonik Brief/Plan/Run/Raw/Document/Segment/Claim/Citation/Bundle/Report/Gap/hata şemaları; `apps/api/app` schema modülleri, `packages/contracts`, ilgili docs |
| BE-02 | Kabul edildi | PostgreSQL ilişkileri, migration ve repository; `apps/api` DB/migrations |
| BE-03 | Açık | Genel kayıt, giriş/çıkış/oturum, proje yetkisi; API auth/project modülleri |
| BE-04 | Açık | Celery/Redis ve kalıcı job state; API lifecycle ve aynı Python projesinin worker girişi |
| BE-05 | Açık | Araçsız Gemini adaptörü, model/prompt/schema/usage ve ortak budget; API AI/budget modülleri |
| BE-06 | Açık | Kanonik Source Registry, typed script/API adaptör ve güvenli egress; API source modülleri ve gerekli lab adaptasyonu |
| BE-07 | Açık | Kalıcı Faz 1 fikir/netleştirme/kategori/niyet/sorgu/onaylı plan; API phase1 |
| BE-08 | Açık | Genel kaynak yürütme ve kalıcı ham storage; API phase2 acquisition/storage |
| BE-09 | Açık | Tam normalizasyon/segment/dil/tarih/boilerplate, exact/near dedup, kişi/kurum/sahiplik; API phase2 normalization |
| BE-10 | Açık | İlgililik/kanıt seçimi, karşıt kanıt koruması; API phase2 filtering |
| BE-11 | Açık | Claim extraction ve tam citation validator; API phase2 evidence |
| BE-12 | Açık | SourceReport/EvidenceBundle, rakip/problem/fiyat haritaları; API phase2 output |
| BE-13 | Açık | Deterministik yeterlilik ve outcome eligibility; API phase3 policy |
| BE-14 | Açık | Kaynaklı rapor, validator, sonlu secondary gap, primary ayrımı ve revizyon; API phase3 |
| BE-15 | Açık | Proje/run/status/plan/evidence/report read API, ayar ve kabul edilmiş export; API routes |
| BE-16 | Açık | Readiness, structured log/metric, retention ve işletim contract; API ops + infra |
| FE-01 | Kabul edildi | Kalan mock/sahte başarı/kapsam kalıntıları; workspace/layout/types/help |
| FE-02 | Kabul edildi | Üretilmiş tipler, API client, durum/hata mapping; lib ve contracts tüketimi |
| FE-03 | Açık | Hesap, oturum, local API env, güvenli hata/yetki durumları |
| FE-04 | Açık | Kimlikli proje/run gezinmesi, deep link/refresh, gerçek liste |
| FE-05 | Açık | Kontrollü fikir formu, taslak/geri dönüş, netleştirme/atlama/kategori/plan onayı |
| FE-06 | Açık | Tek araştırma başlatma, unknown-result recovery |
| FE-07 | Açık | REST polling, üç faz/kaynak status, cancel/recovery, usage |
| FE-08 | Açık | Kanıt kütüphanesi, URL/alıntı bağlamı, rakip/problem/fiyat |
| FE-09 | Açık | Faz 3 rapor/yeterlilik/karşıt/unknown/management review |
| FE-10 | Açık | Rapor sürümleri/gap ve kararlaştırılmış export |
| FE-11 | Açık | Gerçek dashboard, desteklenen ayarlar ve genel gezinme |
| FE-12 | Açık | Responsive/tema/klavye/uzun içerik ve bütün durum ekranları |
| OP-01 | Kabul edildi | Güncel host/port/route/volume/erişim/release baseline; Integration Manager, yalnız read-only host keşfi |
| OP-02 | Açık | API/worker/DB/Redis Compose ve runtime secret; Backend+Integration, `infra/api`, yönetilen DemandRift host dosyaları |
| OP-03 | Açık | HTTPS erişim, local origin/session/CSRF contract; Backend+Integration, yalnız DemandRift nginx snippet |
| OP-04 | Açık | Mevcut hosted-runner/kısıtlı SSH dağıtımını tam runtime'a uyarlama; Integration, workflows/scripts/trusted deploy helper |
| OP-05 | Açık | Başlangıç yedeği, restore/retention, gözlem ve işletim runbook; Integration+QA |
| OP-06 | Açık | Final deploy ve local FE canlı kabul; Integration+QA |
| QA-01 | Kabul edildi | Verifier; geliştirme başında mevcut API pytest, lab unittest ve FE lint/typecheck/build |
| QA-02 | Açık | Verifier+Security; BE-01–06 teslimlerinde schema, DB/auth/job/budget |
| QA-03 | Açık | Backend+Veri+Verifier; 10 fikir × net/eksik/yanlış etiket = 30 |
| QA-04 | Açık | Veri+Security+Verifier; 24 senaryo ve recorded/live sample |
| QA-05 | Açık | Bağımsız Veri/Policy reviewer+Verifier; 33 senaryo |
| QA-06 | Açık | Veri+Verifier; etiketler model çıktısı görülmeden hazırlanır; üç faz prompt/model sabit koşusu |
| QA-07 | Açık | Frontend+Verifier; local FE → gerçek Hetzner BE; her dilim ve final |
| QA-08 | Açık | Integration+Verifier; final tam runtime |

## Git yayın disiplini ve mevcut geçmiş

Tek yayıncı `/root/git_publisher`: `gpt-5.6-luna`, reasoning `high`, fork `none`. Fast seçim aracı yoktu; Fast açıkmış gibi davranılmadı. Uygulama/test/docs/host yazamaz; Root sahipliği belirli tam dosya listesi, SHA256 ve geçmiş review/check kanıtı içeren checkpoint gönderir. Publisher sadece bu sürümü stage/commit/push yapar; hash değişmişse yeni teslim ister. Git index/commit/push tek sahibidir. `git add .`, stash/reset/checkout ile Root tree değişimi, force push ve branch koruma bypass'ı yasak. Her atomik commit ardından push ve remote SHA eşleşmesi doğrulanır.

Aynı sohbet devamında aynı publisher subagent kullanılmalı; sona ermişse `followup_task` ile canlandır. Yeni sohbette canlı agent IDs taşınmaz; tek yayıncı kuralıyla yeniden bir tane oluştur. Publisher bu durma tesliminde son accepted push/remoteSHA sonrası işi bitirebilir; bütün ürünün tamamlandığı anlamına gelmez.

`dd1ca29` ve `1ebfe7a` dış kaynaklı ilerlemelerdir; kullanıcı tree'sini ezmeden entegre edildi. Typed evidence commit852 ilk push'ta remote ilerlemesi nedeniyle reddedildi; yerel commit korundu, normal iki parent merge723 ile yayınlandı. İlk CI ve failed review geçmişi arşivdedir.

```text
dd1ca29f8a852bf509a54152245f208f808bfd05 fix(as02): BT-03 eksik alanlarını ölç, ilgililik testini sıkılaştır
d3ea66f70ff2c3516788c8039a07267eaec3dc2d chore(deploy): disable automatic Vercel Git deployments
e35a0b733b6e9c8092985c269108b8f7c10a1711 docs(m1): record canonical contract decisions
688d0e8afbc05cb78588d778c862ab6f29068fad fix(fe-report): expose unavailable report state
effd0b88c786bb92c30553a670bde326d24d3447 fix(fe-reads): show unavailable workspace data state
d12b5aed0d6b5fafde77a6f32bb6dc0a2e778fe1 fix(fe-theme): persist theme preference across reloads
b9aca90ab1a117e82966df1c324415ae5adf434d fix(fe-draft): preserve drafts without backend writes
5aacc3e9ab71358b6215fb5bd7db2affe6e735f4 ci(api): gate backend deploy on accepted SHA
bdb676c924f8cfc61bc5321f558f75be8a75833d fix(fe-layout): keep mobile sticky navigation visible
89d2fe07e7ba3b46762b5cee500ef6f280f37e63 fix(fe-layout): align workspace shell and navigation
19331d1b208e1beee88de4f344f35e0b93f6b93c fix(api-identity): derive plan identity from validated scope
b75e296649709aefdbe4501cea03ef04c9701e82 fix(web-deps): pin Next and brace security fixes
f0db67bbc58c46f44bc04c36b2236023d07dee2e feat(contracts): publish canonical wire producer consumer
0c53a19c2963d0f684ff9a49ca79a7642ca2936a fix(orchestrator): enforce accepted revision gates
89b92fff4f6ec61493d2ccea9480f3bdc3e62ad6 fix(orchestrator): enforce same-scope retry gates
817ae7ad96e3716eb70d846bd0ebadd5a1e69f47 feat(db): add PostgreSQL foundation and pool context
c07ceba88dc17d9fd9d64ff86c73a6172cce2aa4 fix(api-build): include migration files in Docker context
793654fae045081fdfeddbc1a7ec66dbc21a36db feat(fe-api): validate canonical responses and preserve request safety
7faaf05f376290f10b00814882101ffbfd68011f feat(db): persist immutable preparation and guarded approvals
dbd7197d4a09c1affbc9712a6aaca8e64552a029 feat(db): bind snapshot scope and seal preparation graphs
bb35dd94c1b8c13d49311579fab9c2953a559a5d feat(db): add immutable evidence graph schema
1ebfe7a1c50fc695746f9daa993eac9c8d3f3b4f fix(faz-3): preserve F03 body and comment links
8529857f8183b39e707728ab25751356698df4bb feat(db): seal typed evidence version repository
723ae856354980c5be27e3b199a820091222b2cf fix(f03): contain malformed source conversion during integration
31c3ee63afcc3311fd7c0022bcac822dca59e59e feat(auth-contract): generate account inputs and session CSRF
f611a1d56f0a600fc9b9e029a998d395a66038db feat(auth): persist secure sessions and owner projects
```
