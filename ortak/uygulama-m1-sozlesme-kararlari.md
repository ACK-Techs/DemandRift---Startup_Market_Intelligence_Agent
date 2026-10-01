# DemandRift M1 uygulama sözleşmesi ve kararları

1 Ekim 2026, Europe/Istanbul. Run: `.orchestrator/runs/tamamlama-20261001/run.json`. Bu belge uygulanacak üretici/tüketici sınırlarını sabitler; bir davranış yalnız ayrı review, verification ve integration sonucu varsa kabul edilmiştir. Kullanıcının bu çalışma için yetkilendirdiği atomik commit/push işlemlerini yalnız `/root/git_publisher` yürütür.

Aktif kapsam üç faz: fikir ve araştırma hazırlığı; veri toplama ve hazırlama; karar ve rapor. Eski yedi faz, Temporal ve eski paket ağacı zorunlu değildir. Araştırılan fikrin Build/MVP/PRD, ürün özellikleri, geliştirme veya deney planı hiçbir çıktıda üretilmez. DemandRift uygulamasının geliştirilmesi bu sınırın dışındadır.

## Kanonik veri ve kimlik

Tek kaynak `apps/api/app/contracts.py` Pydantic v2 modelleridir. Aynı modellerden JSON Schema ve `packages/contracts/src/generated.ts` üretilir; CI üretim sonrası fark kontrolü yapar. OpenAPI gerçek route kayıtlarından alınır. Elle tutulan eski Zod IdeaBrief ve confidence alanları kanonik değildir; tüketici geçişinde kaldırılacaktır. Girdi ve model çıktısı `extra=forbid`; desteklenmeyen schema version ilerleyemez. Frontend, doğruladığı sürümün ham JSON yanıtını korur; bilinmeyen alanlardan değer uydurmaz.

Zarf: `schema_version`, `project_id`, `research_id`, `status`, `versions`, `created_at`. UUID/owner/project/run kimliklerini backend üretir, model üretmez. Brief/Plan/Run/RawArtifact/NormalizedDocument/Segment/Claim/Citation/SourceReport/EvidenceBundle/DecisionReport/ResearchGapRequest/Error ayrı modellerdir. Bilinmeyen skaler null; boş liste [] ve bilinmeme nedeni ayrı alandır. Araştırma lifecycle, kaynak sonucu ve outcome ayrı enum'lardır.

Brief `original_idea` aynen ve değişmez saklanır. Her alan value/state/origin/assumption_id taşır; köken user_stated/user_confirmed/ai_inferred/ai_hypothesis. Atlanan netleştirme unknown kalır; devam tercihi kullanıcı tarafından kaydedilir. Onaylanmamış AI hipotezi kesin kaynak/sorgu tohumu olamaz.

Plan UUID server tarafından atanır. `(project_id, plan_version)` artan immutable snapshot; içerik fingerprint'i canonical JSON SHA-256'dır. Brief, kategori/modifier, pazar/dil, niyetler, kaynaklar/sorgular, onay, limit/bütçe ve ilgili sürümler fingerprint'e dahildir. Idempotency fingerprint değildir: `(user_id, project_id, operation, key)` unique; aynı key ile farklı payload 409, aynı payload aynı kayıt. İki eşzamanlı start onaylanmış plan için tek run döndürür. Plan `ready` olması araştırma başarısı anlamına gelmez.

## PostgreSQL ve saklama

Python 3.13 ve mevcut FastAPI/httpx/uvicorn pinleri korunur; Pydantic doğrudan pinlenir. SQLAlchemy 2 sync session, Alembic ve psycopg 3 seçilmiştir; paket patchleri resolver/compatibility kontrolüyle sabitlenecek. PostgreSQL 16, Redis 7.4 host uyumu için başlangıç majorlarıdır; exact image/digest OP-02 kabulünde kaydedilir. SQLite gerçek PostgreSQL eşzamanlılık ve ilişki kabulünün yerine geçmez.

İlişkisel kullanıcı/proje/brief/onay/plan/run/job/attempt/artefact/document/segment/claim/citation/bundle/report/gap ve budget/outbox kayıtları. Immutable payload JSONB olabilir; owner/project/research FKs ve composite ilişkiler cross-run bağı DB'de de engeller. Güncelleme mevcut delili/raporu ezmez, yeni sürüm üretir. Repository her okuma/yazmada owner/proje bağlamını ister. Liste pagination/cursor ve stable order taşır.

Raw content özel `demandrift_api_artifacts` volume'unda; DB dosya ref/hash/byte/owner/project/research/query/attempt/connector/plan bağını tutar. Dosya temp+atomic rename, hash doğrulamasıyla yazılır; path traversal/symlink reddedilir. Hash eşitliği başka kullanıcının erişim yetkisini sağlamaz. API arbitrary file path açmaz; authorized artifact_id join üzerinden okur. Hash/version mismatch citation'ı bloke eder.

## Hesap, oturum ve local frontend

Genel kayıt açık. Argon2id parola hash; yüksek entropili opaque session, DB'de yalnız hash/expiry/revocation. Generic auth hatası ve rate limit. Proje/list/detail/status/raw/citation/report/export sahiplik kontrolleri zorunlu. Session süresi ve şifre limitleri sürümlü auth config'de; session expiry sonrası eski kullanıcı verisi ekranda kalmaz.

Local Next.js same-origin `/api/backend/...` proxy üzerinden sabit upstream HTTPS Hetzner API'ye bağlanır. Upstream base server-only env; kullanıcı URL/proxy target seçemez. Model anahtarı NEXT_PUBLIC, proxy veya client response içine girmez. HttpOnly cookie, local geliştirmede same-origin cookie, prod backend route için güvenli session/CSRF ayarları. Mutating request exact Origin+CSRF token ile denetlenir; GET mutation yapmaz. Backend allowlist exact local origin; wildcard+credentials yok. Doğrudan cross-origin browser smoke OP-03'te ayrıca gerçek HTTPS/CORS ile değerlendirilir.

Route contract: `/api/v1/auth/{register,login,logout,session}`, `/api/v1/projects`, `/api/v1/projects/{project_id}`, `/api/v1/projects/{project_id}/briefs`, brief clarification/confirmation/plan revision, plan approval/start, `/api/v1/research/{research_id}` status/cancel/evidence/reports/gaps, owner kontrollü artifact/export, dashboard ve settings. GET aynı ID/version'ı yeniden okuyabilir. POST idempotency key ve payload fingerprint taşır. Exact alan/route isimleri BE-01/OpenAPI üretiminde sabitlenir. Mevcut stateless plan endpoint'i deprecation açıklamasıyla korunur; public F03 dış çağrı endpoint'i production'da kapalı olacak.

## Worker, retry ve budget

Aynı Python projesinde Celery worker; Redis kuyruk, PostgreSQL kalıcı job state. API request dış HTTP işini yürütmez. Transactional outbox DB commit sonrası dispatch; Redis kaybında DB'den yeniden dispatch. Late ack teslimi lease/attempt/idempotency ile birleştirilir; duplicate delivery çift harcama üretmez. Worker restart kalmış job/attempt'i uzlaştırır. Retry yalnız transient timeout/429/5xx, sonlu attempt/backoff; schema/auth/policy/challenge kör retry değil. Cancel DB'de kaydedilir; yeni dış çağrı öncesinde kontrol edilir; kısmi veri korunur.

Shared budget request/byte/page/record/duration/token/Decimal cost tavanlarını tutar. PostgreSQL row lock/conditional update ile atomik reservation. Retry/fallback/gap aynı run limitini tüketir; yeni bütçe yaratmaz. Provider sonucu bilinmiyorsa reservation held ve reconciliation gerekir; otomatik ikinci harcama yok. Usage/cost unknown sıfır sayılmaz. Ücretli/live suite ancak kullanıcı anahtarı ve max_requests/max_bytes/max_pages/max_records/max_duration/max_tokens/max_cost, toplam suite budget/concurrency sağlandığında çalışır.

## AI ve kaynak güvenliği

Üç faz başlangıç seçimi Gemini 3.1 Flash Lite. Resmî model ID ve hesap erişimi kullanıcı anahtarıyla doğrulanacak; erişim yoksa başka modele sessiz fallback yok. Gemini tools/grounding/search/URL context/browser/shell kapalı; tool call çıktısı yürütülmez. Model yalnız verilen brief/segment/bundle'ı analiz eder. Schema, timeout, finite retry, model/prompt/schema/usage sürümleri kayıtlı. Model sonucu hard gate ve scope/citation kontrolünden geçmeden kabul edilmez.

Kanonik source registry lab katalogları ve source plan/runtime listelerinin tek producer'ı. Source family/capability, field/surface/locale, ownership/independence, izin/health/retention ve fallback sürümlü. Tarihsel erişim enabled/support sertifikası değildir. Desteklenmeyen aileler blocked/unavailable/deferred durumuyla ve niyet boşluğuyla korunur. Model/keyfi kullanıcı URL'si egress genişletemez.

Lab URLGuard/PinnedTransport origin/DNS tüm adresler global/TCP pinned/peer IP+SNI+certificate/redirect revalidation/robots/MIME/decoded byte/time limitleri korunur; trust_env kapalı. Kullanıcı metni shell olmaz. Search/snippet/sitemap discovery fetch edilmiş içerik değildir. source_unavailable/no_results/challenge/blocked_by_policy ayrı; erişim engeli Kill sinyali değildir.

## Kanıt, policy ve rapor

Tam normalized text, segment offset/hash/full hash/normalization_version ve orijinal raw korunur. Dedup yalnız aynı içerik/kimlik ilişkisini kurar; farklı bağımsız kullanıcıların aynı problemi anlatması kopya değildir. Belirsiz kişi/kurum/sahiplik known bağımsız sayılmaz. Claim exact citation taşır; quote/offset/hash/version/owner/project/run iki yönlü bağ doğrulanır. Stated WTP/pricing observed payment değildir.

SourceReport sayıları discovered/fetched/normalized/eligible/unique/claims ayrı. EvidenceBundle doğrulanmış claims/citations, bağımsızlık, coverage, karşıt/unknown, costs/gaps ve kaynaklı problem/rakip/fiyat haritaları taşır. Official claim müşteri deneyiminden ayrı.

Policy v1: aynı ilgili tez yönünde en az 3 bağımsız örnek/2 bağımsız kaynak + hedef/problem, alternatifler, gerçek karşıt araştırma, pazar/dil/tarih, citation ve bağımsızlık kontrolleri. Destek/karşıt/unknown sayıları ayrı. Kritik gap/çelişkide Investigate More; sadece sessizlik/rakip sayısı/budget Kill üretemez. Outcome: positive_findings/modify/kill/investigate_more, management_review_required=true. Model policy uygunluğu dışına çıkamaz.

Report kaynaklı rationale, pillar/market/constraints, unknown/limitations, primary validation ve stability (ölçülmediyse not_evaluated) taşır. Olgusal blok claim/citation'sız yayımlanmaz. Secondary gap aynı acquisition hattını kalan bütçeyle sonlu kullanır; primary gap web'e gönderilmez. Plan/rapor revizyonu önceki delili korur.

## UI işlemleri ve deployment

Mevcut tasarım korunur. Her görünür kontrol gerçek route/işlem veya açık unavailable; mock success/verified/confidence/count/progress kaldırılır. Notifications ve destek mesajı gönderimi kapsamda backend contract yokken unavailable. Pause/resume yerine desteklenen cancel; gerçek backend pause contract olmadan pause yok. Export ilk teslim owner kontrollü aynı report_version JSON; evidence CSV yalnız canonical kayıt alanlarıyla. PDF yeni zorunluluk değil.

Frontend yalnız local. `apps/web/vercel.json` ile bütün Git otomatik deployment'ları kapalı. Mevcut GitHub main path workflow'ları ilk push öncesi incelenir; backend deploy yalnız review/test/integration kabul checkpoint'lerinde. Kod push'ı production kabulünün yerine geçmez.

Hetzner mevcut `/opt/demandrift-api`, Compose proje adı `demandrift-api`, loopback18082 ve artifact volume korunur. Projeye özel API/worker/PostgreSQL/Redis network/volume; DB/Redis public port yok. API/worker non-root, read-only rootfs, limit/restart/log rotation. Gemini yalnız API/worker runtime secret; env içeriği log/inspect/artifact'e dökülmez. OP-01 diğer servis fingerprints ve smoke baseline alır; deploy öncesi/sonrası karşılaştırılır. Global prune veya başka proje DB/Redis değişikliği yok.

Migration ayrı kontrollü adım; başlangıç DB/raw backup. Restore ayrı test DB/alanında hash/ilişkilerle doğrulanır. Image rollback schema rollback değildir; compatibility/forward-fix kaydı gerekir. Health liveness ayrı, readiness DB/queue/worker heartbeat ayrı. OP-06 gerçek restart/recovery/rollback/restore/load/browser kabulüne bağlıdır.

## Kabul ve doküman eşleşmesi

BE-01: contract fixture roundtrip, invalid/unknown/error örnekleri, generated type/schema drift, plan içerik değişimlerinin fingerprint/sürüm etkisi. BE-02–06: gerçek PostgreSQL A/B izolasyon, concurrent start/reservation/cancel, duplicate delivery ve Redis/worker restart; secret/SSRF/tool/citation kontrolleri bağımsız gate.

30 Faz 1, 24 Faz 2, 33 Faz 3 senaryosu fiili actual/evidence/evaluator/model/prompt/policy/schema/version/usage kaydı taşır; model semantiği ve etiketli precision/recall ayrıca ölçülür. Browser local→Hetzner, desktop/mobile/keyboard/theme/refresh iki kullanıcı akışı; OP backup/restore/rollback ve diğer sistemlerin korunduğu kanıt. Mandatory fail/not_run/not_verified finali engeller. Bu specification hiçbir testi çalışmış veya paketi tamamlanmış saymaz.
