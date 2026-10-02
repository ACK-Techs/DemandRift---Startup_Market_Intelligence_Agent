# Güncel kaynak yetkisi ve Faz 1 plan derleyicisi

Bu dilim salt okunur güncel yetki okuyucusu ve saf plan derleyicisidir. HTTP
endpoint, worker çalıştırma, DNS/HTTP kaynak çağrısı, model çağrısı veya yetki
yayımlama işlemi yapmaz. Aktif mimari üç fazdır. Frontend local kalır.

## Yetki üreticisi ve tarihsel kayıtlar

`source_qualification_snapshots` ve `source_qualification_current` PostgreSQL
`public` şemasında admin tarafından sahiplenilen global metadata tablolarıdır.
Uygulama rolünün yetkisi yalnız SELECT'tir. Tablolarda başlangıç güncel kaydı
yoktur. Native 009 teslimi bu tabloları ve izin kontrollerini ayrıca sağlar;
bu modül migration veya runtime head değiştirmez.

Snapshot anahtarı `(qualification_version, qualification_digest)`; güncel
slot `1` bu anahtara FK ile bağlanır. Sürüm en fazla 48 karakterdir. Payload
tam olarak `sources`, `registry_version`, `registry_digest`, `grant_digest`
alanlarını içerir. `sources`, bütün alanları açıkça yazılmış canonical
`SourcePlanItem` şablonlarıdır. Kaynak tarihleri, URL'leri ve ham tipleri zaten
canonical JSON üretici biçiminde olmalıdır; örneğin UTC tarihleri `Z` taşır.
Derleyici hiçbir izin alanını normalleştirerek yetkiye yükseltmez.

`qualification_digest`, PostgreSQL'in
`encode(sha256(convert_to(payload::text,'UTF8')),'hex')` sonucudur. Okuyucu önce
ham `payload::text` UTF-8 baytlarının SHA-256 değerini hesaplar ve saklanan/native
değerlerle karşılaştırır. Python'ın compact JSON özeti JSONB özeti yerine
kullanılmaz. Registry/grant özetleri sıfır olmayan 64 küçük harf hex karakterdir;
registry sürümü ve özeti paketli canonical registry ile tam eşleşir.

Paketli 636 kimlik ve 15 profil yapısal kimlik/aile/kategori/yüzey eşleştirmesine
yarar. Bütün `runtime_enabled` değerleri hâlâ false ve güncel izinleri unknown'dır.
Tarihsel ölçüm, F03 önizlemesi, katalog alanı veya `trial_expected_fields` güncel
izin, robot/lisans incelemesi ya da alan doğrulaması sayılmaz. DB/admin yayımlama
üreticisi gerçek güncel izin, lisans/robots sonucu, doğrulanmış extraction
locator'ları, dil/pazar ve kısıtları inceleyip exact payload/grant özetiyle
bağlamadan bu kayıt yayımlanamaz. Bu üretici/aktivasyon ayrı zorunlu kabul kapısıdır;
bu modül bir grant digest'inden izin belgesi üretmez veya provider'a başvurmaz.

Şablon `permission=permitted`, `health=qualified|supported`, desteklenen mevcut
API/izinli HTTP yüzeyi, search capability, gerçekten review edilmiş extraction
alanları ve expected alan kapsamını açıkça taşır. Origin seçilen exact yüzeye
bağlıdır; aynı sağlayıcının başka alan adı yeterli olmaz. Kimlik/profil eksikliği,
schema/tip/özet uyuşmazlığı, expiry, revocation, unknown/default izin veya eksik
şablon fail closed davranır. URL yapısal kontrolü gerçek SSRF/TLS kapısının yerini
almaz; actual egress ayrıca numeric pin/TLS ve gerçek server grant ister. Bu
teslim egress'in kapalı registry/grant koşulunu açmaz.

## Okuyucu

`load_current_qualification(connection, *, user_id, project_id, checked_at)`
çağıranın sahip olduğu SQLAlchemy session/connection üzerinde iki SELECT yapar.
İlk sorgu RLS altında `public.projects` kayıt sahibi/proje kimliği,
`app.user_id` native tenant GUC ve arşiv durumunu doğrular. Bağlam yanlışsa global
yetki sorgusu yapılmaz. Okuyucu GUC, transaction, environment veya tabloyu
değiştirmez. Native transaction ve current brief/project kilidi HTTP/kernel
üreticisine aittir. Tablolar okunamazsa `qualification_unavailable` döner.

`QualificationState.current(checked_at)` expiry/integrity koşullarını tekrar
denetler ve bağımsız DTO kopyaları döndürür. Yetki sahibinden farklı kullanıcı/
proje derleyicide reddedilir. Gerçek kayıt yoksa veya geçersizse yürütülebilir
kaynaklar boştur; source unavailable, `no_results` olarak etiketlenmez.

Wire qualification sürümü ve `plan.versions.source_registry`,
`raw_version:qualification_digest` token'ını aynı şekilde taşır. Wire'da digest
ayrı alanda da korunur. Gerçek native yayın/ACL/JSONB kanıtı unit mock testleriyle
iddia edilmez.

## Saf derleyici ve kullanıcı kararı

`compile_draft_plan(brief, request, *, plan_id, plan_version, created_at,
qualification, account_budget, suite_budget, analysis=None)` bir `CompiledPlan`
döndürür. `.plan`, `.eligibility`, `.query_hypotheses` ve `.coverage_gaps` her
okumada fresh typed kopyalardır; içerik repr/log'a yazılmaz. `plan_id/version/time`
internal provisional seçimlerdir; native repository proje kilidi altında bunları
kendi server değerleriyle yeniden bağlar.

Seçilmiş exact current insan-onaylı brief korunur: original whitespace/Unicode,
kökenler, kategori, bilinmeyenler, dil/pazar, kullanıcı koşulları ve soru atlama
tercihi değişmez. Unmatched kategori ve çözülmemiş clarification explicit blocker
üretir. Kullanıcının onaylamadığı AI brief alanları araştırma kapsamı olamaz.
Seçili analiz yalnız exact owner/project/research/brief tuple'ından plan önerisi
olabilir; kategori/brief alanları compiler tarafından değiştirilmez. Amaç ve sorgu
hipotezleri onay bekleyen önerilerdir; kaynağı, URL'yi, erişim parametresini, izni
veya bütçeyi model belirleyemez. Model hipotezleri source eligibility yoksa da
gösterilebilir; yürütülebilir sorgu yerine coverage gap ile kalır.

Analiz olmadan yalnız original insan metninden minimal problem/talep sorusu ve
ilk seçilmiş dilde sorgu önerilir; kategoriye bakıp tüm amaçlar körlemesine
açılmaz, yeni niş/çeviri uydurulmaz. 1000 karakterden uzun metin sessizce kesilmez;
sorgu eksikliği açık coverage gap olur. Sonraki kapsamlı proposal/model üreticisi
ayrı bütçeli native iş akışıdır.

Kaynak şablonunun izin, origin, surface, extraction, sürüm, tarih ve kısıt alanları
tam korunur. Yalnız `limits` şablon ve plan bütçesine göre daralır. Planın bütün
bütçe eksenleri hem account hem suite sınırına tabidir; fazla talep reddedilir.
Account/suite'nin harcanan/tutulan kullanım, concurrency ve başlangıç saati native
job admission kapısında ayrıca uygulanır; derleyici bu saati başlatmaz/sıfırlamaz.

Plan her zaman `awaiting_user`, `confirmed_at=null` ve `can_start=false` döner.
UUID'ler server namespace ve kapsam/proposal/source lineage üzerinden deterministik
üretilir; model kimliği kabul edilmez. Fingerprint mevcut canonical plan hash
algoritmasıyla son tam serialized snapshot üzerinden hesaplanır. Dolu uygun plan
onay formuna sunulabilir; kullanıcı query/gap onayı ve native current qualification
kontrolü gerçekleşmeden iş çalıştırılamaz. Empty plan execution taklidi değildir.

`compile_revised_plan(current, brief, patch, *, plan_version, created_at,
qualification, account_budget, suite_budget)` exact current plan/brief selection
ve hash'i tekrar doğrular. Kullanıcı yalnız mevcut source/query dışlaması,
query metni, amaç uygulanabilirliği/reason, mode veya budget değiştirebilir.
Query edit mevcut ID'yi korur ve `user_stated`, yeni onay bekleyen köken taşır.
Authority değişmiş/expired kaynak sorguları açık gap'e döner; kaynak/surface AI
veya eski onaydan sessizce değiştirilmez. Eski kabul ve birebir brief korunur;
yeni sürüm ayrıca insan onayı gerektirir. DTO serialization warning'leri hata
sayılır; private input hata mesajına eklenmez.

## Doğrulama sınırı

Odaklı offline testler gerçek modüller üzerinden owner-first SELECT sırasını,
tam/ham tip ve digest saldırılarını, izin/tarih/yüzey/alan/dil/pazar koşullarını,
bütçe eksenlerini, native hash algoritması uyumunu, immutable dönüşleri ve insan
revision davranışını doğrular. Native 009 veritabanı fixture'ı, gerçek permission
activation, tarayıcı/API entegrasyonu ve canlı kaynak kabulü ayrı kapılardır.
Bu doküman bunların tamamlandığını veya zorunlu 87 senaryonun geçtiğini söylemez.
