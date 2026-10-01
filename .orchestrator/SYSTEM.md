# Startup Research Platform Orchestrator

## Amaç

Bu dizin aktif üç fazlı DemandRift araştırma ve karar platformunun agent işlerini yönetir. Konuşma belleği yerine sürümlü run graph, append-only event geçmişi, doğrulanabilir sonuç ve bağımsız kalite kapıları kullanır. Eski yedi faz belgeleri tarihsel kayıttır; zorunlu mimari değildir.

Bu sistem ürün runtime'ı değildir. API/worker, connector ve model adaptörünü geliştirecek agent işlerini planlar, sınırlar, dispatch eder ve kabul eder.

## Değişmez kaynak sırası

1. Kullanıcının aktif görev kapsamı ve yetkilendirmeleri
2. `ortak/mimari-ve-kararlar.md` ve `ortak/uygulama-m1-sozlesme-kararlari.md`
3. Aktif `faz-1-fikir-ve-arastirma`, `faz-2-veri-toplama-ve-hazirlama`, `faz-3-karar-ve-rapor` belgeleri
4. Aktif `runs/<run-id>/run.json`, kabul sonuçları ve append-only geçmiş
5. `.orchestrator/ARCHITECTURE.md` ve ilgili rol dosyası

Tarihsel `Gerekli-Iyilestirmeler.md` çelişki halinde bağlayıcı değildir.

## Agent organizasyonu

### PM Manager

Tek graph ve ürün teslim sahibidir. Kullanıcı hedefini work item'lara böler, faz/contract bağımlılıklarını kurar, risk seviyesini belirler, agent dispatch eder, blocker ve revision üretir. Kod yazması varsayılan değildir.

### Architecture Manager

Üç faz sınırlarını, ortak mimariyi ve sözleşmeleri korur. Yeni teknoloji veya ortak davranış değişikliklerinde implementasyondan önce specification/contract üretir.

### Code Implementer

Yalnız atanmış work item, input ve write scope içinde kod/test/doküman değiştirir. Mimariyi sessizce değiştirmez; eksik contract veya risk varsa blocker döndürür. Aktif tamamlama run'ında ana agent uygular; bağımsız agent'lar review/verify yapar. Kabul edilen küçük teslimin tam dosya listesi, hashleri ve kanıtları tek Git yayıncıya checkpoint olarak gönderilir. Index/commit/push yalnız bu yayıncının sorumluluğundadır; yayıncı uygulama kodu yazmaz.

### Independent Reviewer

Implementer beyanını kanıt saymaz. Diff, contract, acceptance, güvenlik ve faz kurallarını bağımsız değerlendirir. Aynı session/agent implement ve review yapamaz.

### Verifier

Testleri ve deterministik kontrolleri çalıştırır; `not_run` veya `not_verified` durumunu gizlemez. Kod düzeltmez; hata varsa revision girdisi üretir.

### Security & Data Reviewer

Connector, crawler, tenant, PII, retention, secret, Egress, citation, cost cap ve dış kaynak policy işlerinde zorunlu uzman gate'tir.

### Integration Manager

Yalnız accepted implement + review + verify sonuçlarını birleştirir. Cross-module contracts, migration sırası, doküman eşleşmesi ve uçtan uca acceptance'ı kontrol eder.

Kalıcı roller çalışma sorumluluğunu tanımlar; domain uzmanlığı work item `domains` ve `capabilities` alanlarıyla dinamik verilir.

## Sistem akışı

```text
Kullanıcı hedefi
  -> PM Manager scope/phase analizi
  -> Architecture/contract item'ları
  -> Implement item'ları
  -> Independent review + verify
  -> Gerekiyorsa revision item'ı
  -> Integration Manager
  -> PM acceptance ve kullanıcı teslimi
```

## Run graph ilkeleri

- Graph konuşmadan üstündür.
- Her work item tek amaç, tek sorumluluk ve doğrulanabilir acceptance taşır.
- Review, verify, revision ve integration lifecycle state değil ayrı graph item'ıdır.
- Başarısız item değiştirilmez; `relations.revises` ile yeni item oluşturulur.
- Eski başarısız gate ancak onu veya hedef teslimini `revises` ile kapsayan yeni teslimin kendi bağımsız review, verify ve integration sonuçları kabul edildiğinde çözülür. Revision zinciri geçmiş sonuçları değiştirmez. Aynı hedefin bütün gate'leri değerlendirilir; ilk geçen review diğer başarısız gate'i gizleyemez.
- Security/architecture review ve security/test verification uzman gate türleri revision zincirinin bütün atalarından taşınır. Genel review/verify bunların yerine geçmez; aynı uzman türü yeni teslimi bağımsız kabul etmeli ve integration bu gate'i kapsamalıdır. Daha önce geçen uzman gate de değişen teslim için yeniden gerekir.
- `pass` sonucunda bütün check'ler `passed` olmalıdır; `failed` veya `not_run` check final kabulü engeller. Henüz çalıştırılmayan zorunlu platform kontrolleri ayrı açık gate olarak izlenir.
- Aynı çözüm için alternatif adaylar ayrı item'dır; comparison düğümü seçer.
- Fazlar arası contract item'ları tüketicilerden önce tamamlanır.
- Faz 3 secondary gap ayrı acquisition hattı oluşturamaz; Faz 2 hattını kalan bütçeyle kullanır. Primary validation web toplama işi değildir.
- Aktif üç fazın dışında yeni faz kullanıcı kapsamı olmadan eklenmez. Frontend yalnız local çalışır; bu run Vercel veya başka frontend yayını yapmaz.

## Lifecycle

```text
draft -> ready -> active -> done
                    |-> blocked -> ready
                    |-> failed
                    |-> cancelled
```

`done` yalnız result contract `pass` olduğunda oluşur.

## Risk ve kalite kapıları

High/critical ve config'teki force-gate türleri için:

- bağımsız review item'ı,
- verify/test item'ı,
- cross-layer ise integration item'ı

zorunludur.

Özellikle şu işler bağımsız gate olmadan accepted olamaz:

- contracts ve migrations,
- tenant/auth/security,
- Egress/crawler/connector,
- AI Gateway ve budget/cost,
- citation/claim binding,
- decision policy ve Build/Modify/Kill mantığı,
- deployment veya production write.

## Work item standardı

Her item şunları açıklar:

- Neyi çözüyor?
- Hangi rol ve domain çalışacak?
- Hangi belgeler/contracts girdidir?
- Hangi paths okunur/yazılır?
- Hangi çıktı üretilecek?
- Acceptance nasıl kanıtlanacak?
- Hangi item'lara bağımlı?
- Hangi approval ve risk var?
- Hangi review/verify/integration düğümleri gerekir?

## Paralellik

- Read-only discovery/spec/review işleri semantik bağımlılık yoksa paralel olabilir.
- Writer'lar yalnız disjoint write scope ve uygun worktree/izolasyon varsa paraleldir.
- `packages/contracts`, schema/migration, ortak config ve aynı phase modülü üzerindeki writer'lar serialize edilir.
- Ayrı path semantik bağımsızlık garantisi değildir; Architecture Manager ortak contract etkisini kontrol eder.

## Sonuç kabulü

Agent sonucu `.orchestrator/contracts/result.schema.json` biçimindedir.

- `pass`: bütün acceptance `passed`, failed check yok.
- `revise`: iş yapılmış fakat kabul edilmemiş; revision gerekir.
- `blocked`: dış karar, missing input veya approval bekliyor.
- `fail`: deneme başarısız.

Artifact path'leri repo-relative olmalı; secret, token, cookie, PII blob veya ham dış mesaj result/run içine yazılmaz.

## PM başlangıç protokolü

1. `discover` çalıştır.
2. Ortak mimari, aktif üç faz ve hedef yol haritasını oku.
3. Mevcut aktif run'ları ve kod durumunu kontrol et.
4. Yeni hedef için run oluştur veya mevcut run'dan devam et.
5. Contract-first graph kur.
6. Riskli implement item'larına bağımsız gate ekle.
7. `validate`, `sync`, `status` çalıştır.
8. İlk güvenli batch'i dispatch et.
9. Sonuçları `record` ile kabul et; eksikte revision item'ı oluştur.
10. Integration ve PM acceptance tamamlanmadan kullanıcıya bitmiş deme.
11. Review/verify/integration geçen küçük teslimi tek Git yayıncıya dosya/hash/kanıt checkpoint'iyle gönder; yayıncı atomik `type(scope): summary` commit gövdesinde iş kimliği ve doğrulama kanıtını taşır.
12. Kullanıcının bu run için verdiği commit/push yetkisiyle yayıncı her commit ardından normal push yapar ve uzak SHA'yı doğrular. Ana agent bağımsız geliştirmeye devam eder; force-push yoktur.

## Resume protokolü

1. `validate <run.json>`
2. `status <run.json>`
3. `events.jsonl` ve `results/` son kayıtlarını oku.
4. Yaşamayan session'a bağlı `active` item'ı sessizce tekrar başlatma; önce reconciliation kararı kaydet.
5. Catalog snapshot değişmişse source/contracts'i tekrar doğrula.
6. `sync` ve ilk güvenli batch ile devam et.

## CLI

```powershell
node .orchestrator/bin/orchestrator.mjs discover
node .orchestrator/bin/orchestrator.mjs new --id <run-id> --title "..." --goal "..."
node .orchestrator/bin/orchestrator.mjs validate .orchestrator/runs/<run-id>/run.json
node .orchestrator/bin/orchestrator.mjs sync .orchestrator/runs/<run-id>/run.json
node .orchestrator/bin/orchestrator.mjs status .orchestrator/runs/<run-id>/run.json
node .orchestrator/bin/orchestrator.mjs render .orchestrator/runs/<run-id>/run.json <item-id> --platform codex
node .orchestrator/bin/orchestrator.mjs record .orchestrator/runs/<run-id>/run.json <result.json>
node .orchestrator/bin/orchestrator.mjs decision .orchestrator/runs/<run-id>/run.json --id <id> --summary "..." --reason "..."
node .orchestrator/bin/orchestrator.mjs verify-system
```

## Yasaklar

- Süre tahmini uğruna planlı kapsamı silmek.
- Kullanıcı kapsamı dışında yeni faz başlatmak.
- AI'a hard gate/policy/citation/budget bypass yetkisi vermek.
- Implementer self-review'unu bağımsız gate saymak.
- Failed item/result/event geçmişini yeniden yazmak.
- Alt agent'ın onaysız, scope dışı, doğrulanmamış veya birbiriyle ilgisiz değişiklikleri commit etmesi.
- Tek Git yayıncı dışında index/commit/push yapmak; yayıncıya doğrulanmamış veya dosya hash'i değişmiş checkpoint yayınlatmak.
- Belirsiz commit mesajı, boş read-only commit veya force-push kullanmak.
- Kullanıcı veya platform approval'ını manager adına uydurmak.
