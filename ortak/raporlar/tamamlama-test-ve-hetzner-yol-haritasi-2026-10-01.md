# DemandRift tamamlama ve Hetzner yol haritası

1 Ekim 2026 işlevsel kapsamı; **3 Ekim 2026 kullanıcı kararıyla çalışma süreci güncellendi.** Güncel uygulama sırası [geliştirme planında](../gelistirme-plani.md), test politikası [kalite ve test ilkelerinde](../kalite-ve-test-ilkeleri.md). Bu düzenleme ürün uygulaması, test başarısı veya deployment teslimi değildir.

Önce aktif üç fazın frontend/backend işlevleri tamamlanır. Ardından bütün ürün tek final test ve kontrol aşamasına girer; gerçek hatalar düzeltilir ve ilgili testler yeniden çalıştırılır. Geliştirme sırasında test, lint/typecheck, browser kabulü, bağımsız review/verify/integration veya PM kabul kapıları aranmaz. Eski run grafiği ve kanıt arşivleri tarihsel kayıt olarak saklanır; yeni işler bunlara bağlanmaz.

## Tamamlanacak ürün

Kullanıcı local frontend'de kayıt/giriş yapar, proje ve fikrini oluşturur, netleştirme sorularını cevaplar veya bilinmeyenleri koruyarak devam eder; kategori/sorgu/kaynak/bütçe planını inceler ve onaylar. Tek bir kalıcı araştırma başlar. Backend kaynakları izinli yöntemlerle toplar; arama adayı ile gerçekten alınmış içerik ayrıdır. Kullanıcı kaynak bazlı ilerleme, kısmi hata ve bütçeyi görür. Kaynaklı bulgular ve doğrulanmış alıntılar rapora dönüşür. Sayfa veya worker yeniden başladığında kayıt ve sürüm ilişkileri korunur.

Başka kullanıcının proje, iş, ham veri, citation veya raporu erişilemez. Yetersiz veriyle doğru `Investigate More` geçerli sonuçtur. Her fikre olumlu rapor üretmek başarı ölçütü değildir. Görünür frontend kontrolleri gerçek işlev sunar veya açıkça kullanılamaz durumdadır; sahte kayıt/başlatma, sabit ilerleme/maliyet, dayanıksız verified/confidence ve araştırılan fikir için kapsam dışı Build/MVP/PRD kalmaz.

Final teslim çalışan Hetzner API/worker/PostgreSQL/Redis, gerçek API'ye bağlı local frontend, final test özeti, backup/restore/rollback sonucu ve kısa işletim talimatıdır. **Frontend Vercel yayını bu aşamanın teslimi değildir.**

## Çalışma yöntemi

- Tek uygulayıcı AI geliştirme planını takip eder; tamamlanmış işlevleri tekrar yazmaz. Ayrı dosyalarda faydalı geliştirme işleri subagent'lara verilebilir. Aynı dosyaya eşzamanlı yazım yapılmaz.
- Bütün çalışma mevcut checkout'ta `main` üzerinde yapılır. Yeni branch/worktree açılmaz. Diğer branch'lerin benzersiz ilerlemesi main'e korunarak birleştirilir; branch silmek bu kararın gereği değildir.
- Tek **code pusher subagent** Git fetch/status/diff/add/commit/merge/push işlerini yürütür. Ürün, test ve doküman kodu yazmaz; review/test kabulü istemez. Main'e normal push yapar; force push, kullanıcı değişikliklerini atan reset/clean ve geniş `git add .` kullanmaz.
- Ayrı implement→review→verify→integration zinciri, acceptance düğümü, sürekli yeni JSON/kanıt dosyası ve her küçük değişiklik için kontrol işi oluşturulmaz. İlerleme [geliştirme planındaki](../gelistirme-plani.md) kısa durum tablosuna yazılır.
- Çağlar ürün/kapsam sahibidir; Batuhan backend/yürütücü, Ayşenur frontend, Ayselin kaynak/veri sorunları için mevcut sahipliklerini korur. Süreç kapıları kaldırılır; auth/tenant, secret, egress, bütçe, veri bütünlüğü, şema ve citation kontrolleri ürün kodunda korunur.
- CI yalnız final aşamada manuel çalıştırılır; geliştirme push'ları test başlatmaz. Runtime image build'i test koşusuna dönüşmez. Yayın exact `main` SHA ve aynı SHA'nın başarılı final CI sonucuyla yapılır.

## Uygulama sırası

| Sıra | İşlevsel dilim | Kapsam |
|---|---|---|
| 1 | Var olan main kodunu temel al | BE-01/02, FE-01/02 ve OP-01 gibi tarihsel tamamlanan işleri mevcut koddan belirle; kalan işi sürdür |
| 2 | Platform ve gerçek hesap/proje | BE-03/04/05/06, erken BE-15A/16A; FE-03/04; altyapı konfigürasyonu |
| 3 | Faz 1 fikir ve onaylı plan | BE-07, FE-05/06 |
| 4 | Faz 2 kaynak ve kanıt | BE-08–12, BE-15B, FE-07/08 |
| 5 | Faz 3 rapor ve bütün ekranlar | BE-13/14, BE-15C/16B, FE-09–12; OP-02–05 konfigürasyon/runbook |
| 6 | Final test, kontrol ve düzeltme | QA-01–08 kapsamı birlikte; offline suite, 87 senaryo, model/tarayıcı/işletim kontrolleri |
| 7 | Final Hetzner/local teslim | OP-06; hatalar sonrası son suite, exact SHA final CI ve canlı ürün kabulü |

Backend dilimi uygulanınca ilgili frontend bağlanır; ayrı entegrasyon kabulü beklenmez. Testler için eksik runner veya anlamlı fixture gerekiyorsa final aşamada tamamlanır; ürün davranışını tekrar eden ya da belge metnini sabitleyen testler eklenmez.

### Tarihsel süre tahmini

1 Ekim planının M1–M7 süreleri sırasıyla **5–8, 5–8, 6–10, 6–10, 4–7, 5–9, 3–5 aktif iş günü**, toplam **34–57 aktif iş günü** idi. Bu eski süreç için tahmindi ve taahhüt değildi. Yeni sade çalışma için doğrulanmış yeni süre veya bitiş tarihi yoktur; bu güncellemede tahmin uydurulmaz. BT/AS/AY ve aşağıdaki BE/FE/OP kimlikleri kapsam bağlantısı için korunur; ayrı kontrol düğümleri değildir.

## Backend işlevsel kapsamı

Uygulama sahibi Backend/Batuhan; mevcut Python/FastAPI/Pydantic mimarisi korunur. P0/P1 öncelik sırasıdır; P1 kapsamdan çıkarılan iş değildir. Aşağıdaki davranışlar finalde kontrol edilir, her satır için ayrı review/verify veya kabul dosyası açılmaz.

| ID / öncelik |Teslim ve atanmış yazma kapsamı | Bağımlılık | Finalde beklenen davranış |
|---|---|---|---|
| BE-01 P0 | Kanonik Brief/Plan/Run/Raw/Document/Segment/Claim/Citation/Bundle/Report/Gap/hata şemaları; `apps/api/app` schema modülleri, `packages/contracts`, ilgili docs | M0 | Pydantic/OpenAPI ve FE tipleri aynı sürümden; eski route/faz drift yok; unknown/hata anlamları aynı |
| BE-02 P0 | PostgreSQL ilişkileri, migration ve repository; `apps/api` DB/migrations | BE-01 | Kullanıcı/proje/brief/onay/plan/run/attempt/artifact/segment/claim/citation/bundle/rapor ilişkileri restart sonrası korunur; değiştirme yeni sürüm üretir |
| BE-03 P0 | Genel kayıt, giriş/çıkış/oturum, proje yetkisi; API auth/project modülleri | BE-01,02 | A kullanıcısı B'nin liste/detail/status/artifact/export işlemlerine erişemez; yanlış/bitmiş oturum reddedilir; local FE oturumu çalışır |
| BE-04 P0 | Celery/Redis ve kalıcı job state; API lifecycle ve aynı Python projesinin worker girişi | BE-02,03 | İki eşzamanlı başlatma tek run oluşturur; retry/cancel/restart/recovery kontrollü; iptal sonrası yeni dış çağrı yok; kısmi sonuç korunur |
| BE-05 P0 | Araçsız Gemini adaptörü, model/prompt/schema/usage ve ortak budget; API AI/budget modülleri | BE-01,02 | Resmi model ID/anahtar erişimi doğrulanır; tools kapalı; schema/timeout/retry sınırları; paralel kaynak+LLM bütçesi atomik; secret log/client/image'a geçmez |
| BE-06 P0 | Kanonik Source Registry, typed script/API adaptör ve güvenli egress; API source modülleri ve gerekli lab adaptasyonu | BE-01,04 | Üç sabit kaynak listesi tek kaynaktan türetilir; profile göre parametre; kullanıcı metni shell olmaz; origin/DNS/redirect/robots/MIME/byte kısıtları korunur |
| BE-07 P1 | Kalıcı Faz 1 fikir/netleştirme/kategori/niyet/sorgu/onaylı plan; API phase1 | BE-02,03,05,06 | 10 fikir/30 anlatımda original idea değişmez; AI hypothesis onaysız çalıştırılmaz; unmatched/unknown/atlama ve yanlış etiket düzeltme; her plan sürümü bütün içeriği temsil eder |
| BE-08 P1 | Genel kaynak yürütme ve kalıcı ham storage; API phase2 acquisition/storage | BE-04,06,07 | Planlı yöntem/sorgu gerçekten çalışır; search/snippet/sitemap keşfi fetch sayılmaz; unavailable/challenge/policy/no_results ayrıdır; hash/sorgu/attempt/owner kaydı tam |
| BE-09 P1 | Tam normalizasyon/segment/dil/tarih/boilerplate, exact/near dedup, kişi/kurum/sahiplik; API phase2 normalization | BE-08 | Tam metin ve segment offset/hash/version korunur; arşiv-canlı ayrımı; kopya ve unknown örnekler bağımsız sayılmaz |
| BE-10 P1 | İlgililik/kanıt seçimi, karşıt kanıt koruması; API phase2 filtering | BE-09 | İnsan etiketli TR/EN ve yedi kategori setinde precision/recall ve kaybedilen önemli/karşıt örnekler raporlanır; token sınırına seçim kaydı var |
| BE-11 P0 | Claim extraction ve tam citation validator; API phase2 evidence | BE-05,09,10 | Birebir quote+offset+segment/full hash+normalizer sürümü+owner doğrulanır; uydurma/stale bağ reddedilir; ödeme beyanı gerçek ödeme olmaz |
| BE-12 P1 | SourceReport/EvidenceBundle, rakip/problem/fiyat haritaları; API phase2 output | BE-08,11 | Doğrulanmış claim'lere bağlı destek/karşıt/unknown, kaynak/örnek/kapsam/maliyet/hata ayrımı; Faz 3 consumer contract geçer |
| BE-13 P0 | Deterministik yeterlilik ve outcome eligibility; API phase3 policy | BE-12 | 3/2 aynı ilgili tez yönünde doğrulanmış bağımsız örnek/kaynakla; aynı sahiplik/unknown/yanlış pazar/kritik çelişki geçmez; sessizlik veya budget Kill üretmez |
| BE-14 P1 | Kaynaklı rapor, validator, sonlu secondary gap, primary ayrımı ve revizyon; API phase3 | BE-05,13 | Dört outcome ve management_review; Build/MVP yok; desteklenmeyen iddia yayınlanmaz; secondary aynı hattı kullanır; primary web'e dönmez; eski rapor/citation korunur |
| BE-15 P1 | Proje/run/status/plan/evidence/report read API, ayar ve kabul edilmiş export; API routes | BE-07; ilgili uç için BE-12/14 | FE'nin seçili kimlik/sürümü tekrar okuyabilmesi; cursor/pagination/error/partial; artifact ve export owner kontrolünde |
| BE-16 P0 | Readiness, structured log/metric, retention ve işletim contract; API ops + infra | BE-02,04,05; final için tüm BE | API health dependency durumunu doğru ayırır; job/queue/maliyet/hata izlenir; DB/ham veri rebuild'de korunur; backup/restore ve migration geri dönüşü kanıtlanır |

BE-15 ve BE-16 alt başlıkları yalnız uygulama bağımlılığını anlatır; ayrı kabul işleri değildir.

| Alt teslim |Bağımlılık | İşlev |
|---|---|---|
| BE-15A Liste/detail/status | BE-02,03,04 | Kullanıcıya ait proje/run listesi ve kalıcı job status; FE-04/07 için yeterli |
| BE-15B Evidence read | BE-12, BE-15A | Doğrulanmış claim/citation/bundle okuma ve owner yetkisi; FE-08 için yeterli |
| BE-15C Report/revision/export, dashboard ve ayar API | BE-14, BE-15A | Doğru rapor sürümü, gap, kabul edilen export ve gerçek dashboard özeti; kapsamda desteklenen kullanıcı/araştırma ayarları read/update ve kalıcı kayıt; FE-09/10/11 için yeterli |
| BE-16A Temel readiness/log/metric | BE-02,04,05 | DB/queue/worker/process sağlık ayrımı ve güvenli log; OP-02 temel runtime'ı açabilir |
| BE-16B Tam ürün işletim contract | BE-07,08,09,10,11,12,13,14, BE-15A,15B,15C, BE-16A | Bütün ürün stage/job/kullanım göstergeleri, retention/backup/restore/rollback test girdileri; OP-04/05 final kontrol kapsamı |

### Backend tasarım kararları

- FastAPI/Pydantic, PostgreSQL, Celery/Redis, kalıcı ham dosya, Docker Compose ve REST/polling mevcut onaylı seçimlerdir. Mevcut ORM/migration/auth uygulaması korunur; gerçekten eksik bir seçim varsa uygulama sırasında somutlaştırılır.
- Plan kimliği yalnız kategori/brief üzerinden türetilmez. Market, dil, ek paket, budget, kaynak/sorgu ve onay değişimi yeni immutable sürüm/fingerprint üretir; idempotency ayrı kavramdır.
- Kaynak HTTP işi API request'inin ömrüne bağlanmaz. API job yaratır/okur; worker typed profile'ı yürütür; kalıcı araştırma durumu PostgreSQL'dedir.
- Source registry'de capability, izin, source health, source ownership, dil/pazar, sorgu/erişim yolu ve alan sınırları sürümlüdür. Erişim snapshot'ı üretim destek sertifikası değildir.
- Ham kayıtların content hash'i yanında owner/project/research/query/attempt bağı bulunur. İçerik adresli dosya paylaşımı proje yetkisini aşamaz.
- Run budget; request, byte, sayfa/kayıt, süre, token ve maliyet sınırlarını içerir. Retry ve eşzamanlı işler aynı toplam bütçeyi tüketir; bilinmeyen provider sonucu yeniden harcamadan uzlaştırılır.
- Model yalnız kendisine verilen brief veya evidence üzerinde çalışır. Grounding, URL context, browser, shell veya crawler araçları bağlanmaz. Resmi model ID ve erişim mevcut anahtarla doğrulanmadan başka modele sessiz geçiş yapılmaz.

## Frontend işlevsel kapsamı

Mevcut `apps/web` ve tasarım korunur; büyük yeniden tasarım yapılmaz. Backend hazır oldukça FE bağlanır. FE-12 responsive/klavye/uzun içerik davranışları ekranlar geliştirilirken uygulanır; tarayıcı testi bütün işlevler bittikten sonra yapılır.

| ID / AY eşlemesi |Teslim ve kapsam | Bağımlılık | Finalde beklenen davranış |
|---|---|---|---|
| FE-01 P0 / AY-01 | Kalan mock/sahte başarı/kapsam kalıntıları; workspace/layout/types/help | M0 | Tüm 10 route'ta gerçekmiş gibi BUILD/confidence/verified/ilerleme/sayım/kayıt yok; her görünür komut gerçek işlem veya açık unavailable |
| FE-02 P0 / AY-02 | Üretilmiş tipler, API client, durum/hata mapping; lib ve contracts tüketimi | BE-01 | Kimlik/schema version ve bilinmeyen alanlar kayıpsız; aynı hata/status her ekranda aynı anlamda |
| FE-03 P0 / AY-06 | Hesap, oturum, local API env, güvenli hata/yetki durumları | BE-03, OP-03, FE-02 | Kayıt/giriş/çıkış/expiry; izinli local origin ile gerçek Hetzner bağlantısı; model anahtarı bundle'da yok |
| FE-04 P0 / AY-06 | Kimlikli proje/run gezinmesi, deep link/refresh, gerçek liste | BE-15A, FE-03 | İki proje arasında yanıt/rapor karışmaz; eski istek yeni seçimi ezmez; yenileme aynı backend kaydına döner |
| FE-05 P0 / AY-03 | Kontrollü fikir formu, taslak/geri dönüş, netleştirme/atlama/kategori/plan onayı | BE-07, FE-02,04 | Net/eksik/yanlış etiketli girdiler korunur; kullanıcı/AI kökenleri ve unknown açık; onaylı plan/sürüm görünür |
| FE-06 P0 / AY-03 | Tek araştırma başlatma, unknown-result recovery | BE-04,07, FE-05 | Çift tıklama veya yanıt kaybında tek run; gerçek kimlikle araştırmaya geçiş; sahte success yok |
| FE-07 P1 / AY-04 | REST polling, üç faz/kaynak status, cancel/recovery, usage | BE-04,08, BE-15A, FE-06 | Loading/partial/unavailable/no_results/rate_limited/policy/challenge ayrı; uydurma yüzde yok; yalnız sözleşmesi olan pause/resume görünür |
| FE-08 P1 / AY-04 | Kanıt kütüphanesi, URL/alıntı bağlamı, rakip/problem/fiyat | BE-11,12, BE-15B, FE-07 | Her iddia gerçek citation'a gider; quote/tarih/hash/sürüm durumu açık; bağımsız örnek ve belge sayısı ayrı |
| FE-09 P0 / AY-05 | Faz 3 rapor/yeterlilik/karşıt/unknown/management review | BE-13,14, BE-15C, FE-08 | 3/2 ile nitel gate ayrı; completed+insufficient doğru; dört outcome doğru; Build/MVP/güven yüzdesi yok |
| FE-10 P1 / AY-05,06 | Rapor sürümleri/gap ve kararlaştırılmış export | BE-14, BE-15C, FE-09 | Secondary/primary farkı; eski rapor/citation bağı korunur; export aynı gerçek rapor sürümüdür |
| FE-11 P1 / AY-06 | Gerçek dashboard, desteklenen ayarlar ve genel gezinme | BE-15A,15C, FE-04,09 | Başarı backend onayıyla; ayarlar refresh sonrası korunur; sahte bildirim/destek/hizmet iddiası yok |
| FE-12 P1 / AY-07 | Responsive/tema/klavye/uzun içerik ve bütün durum ekranları | Her FE dilimi; final tüm FE | 360/390/768/1440 genişlikte uzun Türkçe metin/URL/quote taşmaz; focus/modal/klavye kontrolleri; ekran değerleri canlı API ile eşleşir |

## Hetzner ve local frontend

1 Ekim kaydındaki mevcut düzen `/opt/demandrift-api`, DemandRift Compose ve loopback **18082** portudur; bu tarihsel bilgi çalışma öncesinde mevcut hosttan okunur. İkinci bir DemandRift servis/port açılmaz. Projeye ait Compose/ağ/volume/secret ve nginx HTTPS kullanılır; diğer uygulamalar etkilenmez. Gereksiz dizin taşıması yapılmaz; `/opt/demandrift/backend/releases/<commit>` düzeni yalnız gerçekten gerekiyorsa seçilir.

| ID |Teslim / sahibi / kapsam | Bağımlılık | Finalde beklenen davranış |
|---|---|---|---|
| OP-01 P0 | Güncel host/port/route/volume/erişim/release baseline; Uygulayıcı, yalnız read-only host keşfi | M0 | DemandRift ve diğer proje ID/imaj/start/network/mount/route fingerprint'leri kaydedilir; port18082 ve kapasite/reverse proxy erişimi doğrulanır |
| OP-02 P0 | API/worker/DB/Redis Compose ve runtime secret; Backend/uygulayıcı, `infra/api`, yönetilen DemandRift host dosyaları | BE-02,04,05, BE-16A | Non-root uygulama, read-only rootfs, limit/restart/log rotasyonu; DB/Redis public değil; kalıcı volume; secret yalnız BE/worker |
| OP-03 P0 | HTTPS erişim, local origin/session/CSRF contract; Backend/uygulayıcı, yalnız DemandRift nginx snippet | BE-03, OP-01,02 | Önerilen `https://167.235.158.118/demandrift` prefix veya SSH tunnel; root_path/OpenAPI/redirect doğru; local browser HTTPS/CORS/session çalışır |
| OP-04 P0 | Mevcut hosted-runner/kısıtlı SSH dağıtımını tam runtime'a uyarlama; Uygulayıcı, workflows/scripts/trusted deploy helper | OP-02, BE-16B | main/SHA seri deploy, test→build→migration→start→readiness; stale/build-fail canlıyı değiştirmez; migration uyumlu rollback; deploy yetkisi hesap yetkisinden ayrı |
| OP-05 P0 | Başlangıç yedeği, restore/retention, gözlem ve işletim runbook; Uygulayıcı ve final kontrol | OP-02,04 | Ayrı test DB/alanında DB+raw restore; hash/ilişki doğruluğu; disk/log/imaj saklama; job/queue/health izlenebilir |
| OP-06 P0 | Final deploy ve local FE canlı kabul; Uygulayıcı ve final kontrol | Tüm BE/FE uygulaması ve final offline testleri | Yeni backend sürekli çalışır; local FE tam akışı tamamlar; restart/rollback sonrası kalıcılık; diğer sistem fingerprints ve smoke sonuçları korunur |

Altyapı konfigürasyonu geliştirme sırasında hazırlanabilir. Gerçek Hetzner yayın ve canlı kontrol final aşamasındadır:

1. DemandRift host/port/mount/release durumunu ve etkilenebilecek mevcut servisleri okuyarak belirle; secret içeriklerini çıktıya dökme.
2. Main'deki tamamlanmış revision için final offline CI'ı manuel çalıştır. Aynı testleri image build'de ve container'da tekrar koşturma.
3. Yeni schema için yedek al; migration'ı yalnız DemandRift DB'sine uygula. Image rollback ve schema geri dönüşü ayrı düşünülür.
4. API/worker/PostgreSQL/Redis'i projeye ait ağda başlat; DB/Redis public açılmaz. Secret backend/worker runtime'dadır; image/Git/`NEXT_PUBLIC_*` alanına girmez. DB ve ham veri kalıcı volume'dadır.
5. Local FE'yi gerçek API'ye bağla. Gerekirse SSH tunnel, session/browser akışı için uygun HTTPS route kullan. Exact origin/CSRF ve `root_path` davranışını finalde kontrol et.
6. Aynı research kimliğiyle kaynak→claim/citation→rapor, refresh/restart, yetkisiz erişim, backup/restore ve rollback'i finalde doğrula; yalnız process health'i ürün başarısı sayma.
7. Gerçek hataları düzelt, ilgili testi yeniden çalıştır; son kodun final suite'ini tamamla. Değişiklik varsa yeni SHA için final CI ve yayın yapılır.

## Tek final test ve kontrol aşaması

Geliştirme sırasında başlangıç/baseline testi veya her dilimde test yoktur. Mevcut API, frontend, laboratuvar testleri; fixture/senaryo JSON'ları ve geçmiş sonuçlar korunur. QA kimlikleri test kapsamını ifade eder; ayrı agent/run/acceptance düğümleri açılmaz.

| Final kapsamı | Ne yapılır? |
|---|---|
| QA-01–02 Mevcut suite ve platform | Manuel CI'da API offline, gerçek geçici PostgreSQL/Redis, sözleşme ve frontend testleri; final lint/typecheck/build; auth/owner/job/idempotency/budget/cancel/restart |
| QA-03 Faz 1 | 10 fikir × net/eksik/yanlış etiket = 30 senaryo; original idea, onay, köken, unknown ve plan |
| QA-04 Faz 2 | 24 senaryo; gerçek içerik, normalizasyon, dedup, ilgililik/karşıt kanıt, quote/hash/lineage ve kaynak hata ayrımı |
| QA-05 Faz 3 | 33 senaryo; 3/2+nitel yeterlilik, dört outcome, primary/secondary ve sonlu gap, kapsam ve kaynaklı rapor |
| QA-06 Model | Etiketli setle semantik doğruluk, destek/alıntı, model/prompt sürümü ve kullanım; tools/grounding kapalı |
| QA-07 Browser/E2E | Local FE→gerçek Hetzner BE: hesap→fikir→plan→run→kanıt→rapor→refresh; iki kullanıcı/proje, mobil/desktop/tema/klavye |
| QA-08 İşletim | API/worker/DB restart, Redis kesintisi, hata/retry/bütçe/iptal yarışları, backup/restore/rollback; diğer servisler korunur |

87 senaryo planlı girdidir; otomatik runner yoksa finalde gerçek payload/çıktı ve kısa sonuçla kontrol edilir. JSON dosyasının varlığı PASS değildir. API offline koşusunda ayrılan PostgreSQL testleri gerçek DB koşusunda çalışmalıdır; zorunlu bir testin skip/not_run olması başarı sayılmaz. Belge haritası, görev kartı ve zorunlu rapor cümlesi kontrolleri ürün kabulü için kapı yapılmaz.

### Finalde kullanılacak mevcut komutlar

Ortam/bağımlılıklar final koşusu için hazırlanır. Manuel `.github/workflows/api-ci.yml` API/DB/container/contracts/frontend native testlerini kapsar; başarılı aynı koşu tekrar yerelde koşturulmaz. CI'ın kapsamadığı komutlar finalde eklenir:

```sh
npm run lint --prefix apps/web
npm run build --prefix apps/web
```

Laboratuvarın Dockerfile'ında mevcut dar offline komut, laboratuvar kökünde:

```sh
python -m unittest -v test_query_templates test_select_sources test_butce_profilleri
```

Bu üç modül bütün laboratuvarı temsil etmez. Diğer gerekli offline laboratuvar testleri de finalde çalıştırılır; canlı ağ/model çağrısı yapan testler aşağıdaki ortak bütçede ayrı yürütülür. Mevcut olmayan runner için çalışıyormuş gibi komut yazılmaz. Güncel ve gerçek sonuçlar final özete yazılır; tarihsel test sayıları bugünkü başarı olarak taşınmaz.

### Finalde aranacak işlev ve hata davranışları

- Faz 1'de yedi kategori, on fikrin 30 anlatımı, unmatched, bağlam/modifier, TR/EN, uzun/eksik giriş; orijinal fikir, AI hypothesis ve onay kökeni korunur.
- İki farklı user/proje/run arasında kayıt/rapor/citation/cache/yanıt/URL karışması yok; expired session ve yetkisiz artifact/export erişimi reddedilir.
- Çift tık/eşzamanlı POST, timeout sonrası bilinmeyen create/start sonucu, worker crash ve at-least-once job teslimi çift run/harcama üretmez.
- 429/transient5xx/timeout sonlu retry; invalid auth/schema/policy/challenge kör retry değil; tek kaynak hatası bütün araştırmayı kaybettirmez.
- Başarıyla aranmış boş kaynak ile unavailable ayrıdır; kaynağın resmi iddiası müşteri deneyimi değildir; arşiv taze canlı kanıt değildir.
- Aynı kişi farklı platformlarda, aynı kurum farklı markalarda, repost/press-release kopyaları ve kimliği unknown örnekler yanlış bağımsız sayılmaz.
- Sahte/tam eşleşmeyen quote, offset kayması, eski normalizer/full text/segment hash ve başka run/citation bağı doğrulayıcıdan geçmez.
- 2 örnek/2 kaynak, 3 örnek/1 kaynak, aynı sahipli 3/2, yanlış pazar, karşıt arama eksik, unknown kimlik veya kritik çelişki yeterli olmaz. Destek ve karşıt örnekler sayıyı doldurmak için karıştırılmaz.
- Güçlü doğrudan karşıt 3/2 Kill uygunluğuna girebilir; yalnız rakip sayısı, veri yokluğu, bütçe veya sessizlik Kill üretemez.
- Fiyat/“öderdim” yorumu observed payment değildir. Birincil doğrulama boşluğu web araştırmasıyla kapatılmış gibi gösterilmez.
- Kaynak metnindeki prompt injection, modelin araç açmasına, source policy/citation/budget/tenant sınırını aşmasına veya Build/MVP üretmesine yol açmaz.
- Secondary gap aynı acquisition hattını ve kalan bütçeyi kullanır; tekrarlanan gap sonlu durur; yeni brief/plan/rapor sürümü eski delili sessizce değiştirmez.
- UI yüklenme/boş/kısmi/erişim/kota/yanlış şema/offline/refresh/back durumlarıyla, uzun Türkçe fikir/URL/alinti ile masaüstü ve mobilde kontrol edilir.

### Canlı kaynak ve Gemini sınırı

Model seçimi **Gemini 3.1 Flash Lite**, tarihsel plan ID'si `gemini-3.1-flash-lite` olarak korunur. Final canlı çağrısından önce gerçek API route/model erişimi ve fiyat resmi kaynaktan doğrulanır; sessiz model fallback yapılmaz. Modelin tools/grounding/search/URL context/browser/shell yetkisi yoktur. Secret'ın varlığı ve izinleri içerik gösterilmeden okunur; geçici eski dosya halen varmış gibi varsayılmaz.

1 Ekim devam notunda onaylanan bütün deneme/retry'lar için ortak limit: **$5; 300 dış istek; 50.000.000 byte; 150 sayfa; 1000 kayıt; 1800 saniye; 300.000 token; concurrency 2.** Final başlangıcında geçmiş harcamalar dahil kalan budget kullanılır; sayaç sıfırlanmaz. 1800 saniyelik canlı suite saati geliştirme sırasında başlatılmaz. Budget ledger çalışmadan ücretli dış çağrı başlatılmaz; limit bitince kalan boşluk açıkça raporlanır.

Kaynak aileleri ve registry kapsamı korunur: resmi web, teknik topluluk, marketplace/review, sosyal/açık topluluk, domain/web izi, reklam/trend/funding/jobs/maps, kamu/akademik/regülasyon/patent ve gerekli dikey kaynaklar. Küçük teknik pilot final canlı kontrolünün başlangıcıdır; diğer kategori veya engelli kaynakların başarı kanıtı değildir. Tarihsel 636 katalog satırı tüm kaynakların canlı desteklendiği iddiası değildir. Erişilemeyen veya eksik kaynak için uygun hata ve gerektiğinde `Investigate More` görünür.

## Final tamamlanma ölçütü ve kısa kayıt

Bütün onaylı BE/FE/OP işlevleri uygulanmış, 87 zorunlu senaryo ile mevcut gerekli testler finalde kontrol edilmiş, kritik/yüksek gerçek hatalar düzeltilmiş ve son revision için final suite geçmiş olmalıdır. Sızıntı, budget bypass, uydurma citation, veri kaybı veya scope ihlali bulunan sürüm tamamlandı diye sunulmaz. Düşük önemde kalan gerçek kusurlar etkisiyle açık yazılır. Erişilemeyen dış kaynak dürüstçe görünüyorsa bu tek başına yazılım hatası değildir.

Tek kısa final raporu yeterlidir: main commit SHA, ortam ve çalıştırılan komut/CI bağlantısı, geçme/kalma/çalıştırılamama özeti, 87 senaryonun kısa sonuçları, gerçek hatalar ve düzeltmeler, canlı maliyet ve kalan dış engeller. CI çıktısı veya mevcut dosya yeterliyse aynı kanıt başka JSON'lara kopyalanmaz. Secret ve özel ham içerik rapora girmez. Kod/docs/işletim talimatı değişen davranış kadar güncellenir.

İleri SimHash/MinHash/LSH, embedding/pgvector, HDBSCAN ve izole browser ölçülmüş ihtiyaç varsa kullanılabilecek seçeneklerdir; bütün algoritmaları sırf planda adı geçtiği için eklemek gerekmez. Finalde somut hata veya performans sorunu çıkarsa gerekli en küçük düzeltme yapılır; yeni review/verify zinciri açılmaz.
