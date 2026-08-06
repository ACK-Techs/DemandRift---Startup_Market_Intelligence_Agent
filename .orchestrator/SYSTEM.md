# Startup Research Platform Orchestrator

## Amaç

Bu dizin Faz 1–7 araştırma ve karar platformunun agent control plane'idir. Konuşma belleği yerine sürümlü run graph, append-only event geçmişi, doğrulanabilir sonuç ve bağımsız kalite kapıları kullanır.

Bu sistem ürün runtime'ı değildir. Temporal, connector, AI Gateway veya uygulama servislerini çalıştırmaz; onları geliştirecek agent işlerini planlar, sınırlar, dispatch eder ve kabul eder.

## Değişmez kaynak sırası

1. `Ust-Yonetim-Ana-Mimari-Plani.md`
2. `Platform-Temeli.md`
3. İlgili `FazN-Plan.md`
4. `.orchestrator/ARCHITECTURE.md`
5. Aktif `runs/<run-id>/run.json`
6. İlgili rol dosyası

Tarihsel `Gerekli-Iyilestirmeler.md` çelişki halinde bağlayıcı değildir.

## Agent organizasyonu

### PM Manager

Tek graph ve ürün teslim sahibidir. Kullanıcı hedefini work item'lara böler, faz/contract bağımlılıklarını kurar, risk seviyesini belirler, agent dispatch eder, blocker ve revision üretir. Kod yazması varsayılan değildir.

### Architecture Manager

Faz sınırlarını, Platform Temeli'ni, contracts ve ADR'leri korur. Yeni teknoloji veya cross-cutting değişikliklerde implementasyondan önce specification/contract üretir.

### Code Implementer

Yalnız atanmış work item, input ve write scope içinde kod/test/doküman değiştirir. Mimariyi sessizce değiştirmez; eksik contract veya risk varsa blocker döndürür. Aktif run açık kullanıcı commit onayı taşıyorsa kontroller geçince write scope'unu atomik Conventional Commit ile kaydeder ve commit SHA'yı result'a ekler; push yapmaz.

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
- Aynı çözüm için alternatif adaylar ayrı item'dır; comparison düğümü seçer.
- Fazlar arası contract item'ları tüketicilerden önce tamamlanır.
- Faz 5 ayrı acquisition implementation'ı oluşturamaz; Faz 3 runtime'ını kullanır.
- Faz 8 için `faz8-start` kullanıcı approval boundary zorunludur.

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
2. Ana mimari, Platform Temeli ve hedef fazı oku.
3. Mevcut aktif run'ları ve kod durumunu kontrol et.
4. Yeni hedef için run oluştur veya mevcut run'dan devam et.
5. Contract-first graph kur.
6. Riskli implement item'larına bağımsız gate ekle.
7. `validate`, `sync`, `status` çalıştır.
8. İlk güvenli batch'i dispatch et.
9. Sonuçları `record` ile kabul et; eksikte revision item'ı oluştur.
10. Integration ve PM acceptance tamamlanmadan kullanıcıya bitmiş deme.
11. Run'da commit onayı varsa her tamamlanan write item'ı atomik `type(scope): summary` commit'iyle kaydet; work item ID'sini commit body/footer'unda taşı.
12. Ayrı push onayı varsa review, verify ve integration kabulü tamamlanan checkpoint'i üst manager olarak push et; force-push yapma.

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
- Faz 8'i approval olmadan başlatmak.
- AI'a hard gate/policy/citation/budget bypass yetkisi vermek.
- Implementer self-review'unu bağımsız gate saymak.
- Failed item/result/event geçmişini yeniden yazmak.
- Alt agent'ın onaysız, scope dışı, doğrulanmamış veya birbiriyle ilgisiz değişiklikleri commit etmesi.
- Implementer veya alt agent'ın push yapması; push yalnız ayrı açık kullanıcı onayıyla kabul edilmiş integration checkpoint'inde üst manager tarafından yapılır.
- Belirsiz commit mesajı, boş read-only commit veya force-push kullanmak.
- Kullanıcı veya platform approval'ını manager adına uydurmak.
