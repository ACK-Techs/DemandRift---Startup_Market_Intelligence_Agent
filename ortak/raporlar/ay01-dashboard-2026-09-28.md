# AY-01 — dashboard ilk alt teslimi

28 Eylül 2026. Kullanıcının verdiği iki değerlendirme metni mevcut kod ve planlarla karşılaştırıldı. İlk uygulama kapsamı `apps/web/components/dashboard/` altındaki altı bileşendir. AY-01'in tamamı, API entegrasyonu veya Batuhan kabulü tamamlandı sayılmaz.

## Metinlerin doğruluk değerlendirmesi

- **Ana öneri doğru:** [README](../../README.md), [ürün kuralları](../RULES.md) ve [Faz 3 sözleşmesi](../../faz-3-karar-ve-rapor/docs/veri-sozlesmeleri.md) üç fazı esas alır. Build/MVP/PRD kapsam dışıdır; `positive_findings` yönetici değerlendirmesi gerektirir. Dayanaksız güven yüzdesi rapor alanı değildir.
- **Dashboard bulguları doğruydu:** eski bileşenler mock veriden 12 karar, BUILD, %82 güven, %68 ilerleme ve doğrulanmış kanıt iddiaları gösteriyordu. Bu alt teslim bunları dashboard'dan kaldırır.
- **API listesi kodda doğrulandı:** `/health`, `/api/v1/research/categories`, `/plans`, `/source-plans/{category}`, `/initial-runs`, `/run-records/validate`, `/source-runs/f03` mevcut. Araştırma yolları `/api/v1/research` önekini paylaşır. [API giriş noktası](../../apps/api/app/main.py) ilgili router'ları bağlar. Canlı sunucuya istek atılmadı.
- **API sınırı doğru:** [kayıt doğrulama](../../apps/api/app/run_record.py) `storage: not_persisted` döndürür; kayıt oluşturmaz. [F03 çalıştırıcısı](../../apps/api/app/source_execution.py) sabit senaryo ve izinli kaynaklarla sınırlıdır; genel araştırma/rapor servisi değildir. F03 bir senaryo kimliğidir, güncel Faz 3 raporlama teslimi değildir.
- **Düzeltilecek anlatım:** “backend yok” yerine “tam ürün backend akışı ve dashboard entegrasyonu yok” denmelidir. API README'sindeki yalnız `/health` açıklaması son kodun gerisindedir. “Tamamlanmamış değil” ifadesi ilk metinde ters anlam veren bir yazım hatasıdır; kastedilen “henüz tamamlanmamış” olmalıdır.
- **Tarihsel kanıtlar:** 636 kaynak/534 içerik yüzeyi [22 Eylül kaynak raporunda](kaynak-verisi-durumu.md), Vercel yayını ve 70 offline test [dağıtım kaydında](dagitim-kontrol-2026-09-22.md) yer alır. Bu çalışma corpus'u yeniden saymadı, canlı erişimi veya uzaktaki yayını yeniden doğrulamadı.
- **Belge yolu:** eski planların bu kopyadaki yeri `trash/eski-planlar/`; ilk metindeki yalnız `eski-planlar/` yolu güncel değildir. Orkestrasyon işleyişi korunur; eski faz adları güncel ürün kapsamının yerine geçirilmez.

## Uygulanan davranış

Dashboard artık gerçek veri bağlantısının bulunmadığını açıkça anlatır. Eksik entegrasyon, “0 karar”, “hiç projen yok” veya başarılı bir boş API yanıtı gibi sunulmaz.

- Karar dağılımı, sahte karar listesi ve güven yüzdeleri kaldırıldı.
- Sabit metrikler, doğrulanmamış bulgular, sahte ilerleme ve güncellenme zamanları kaldırıldı.
- Kişiye özel sabit karşılama yerine genel çalışma alanı başlığı kullanıldı.
- Proje, araştırma ve rapor bağlantıları gerçek route'lara gider; metinleri açıkça **prototype preview** belirtir. Hedef ekranlar hâlâ mock içerir.
- Araştırma aşamaları güncel üç fazın planlanan akışı olarak gösterilir; aktif/tamamlanmış iş gibi sunulmaz.
- Kart düzeni, mevcut tasarım değişkenleri ve responsive sınıflar korundu. Tarayıcıda görsel uygunluk bu ifadeden çıkarılamaz.

## Kalan AY-01 envanteri

Aşağıdaki yollar `apps/web/` altındadır. Bunlar kod incelemesi bulgularıdır; tarayıcı davranışı test edilmiş sayılmaz.

| Ekran / dosya | Mevcut davranış ve sorun | Beklenen düzeltme | API bağımlılığı |
|---|---|---|---|
| `lib/mock-data/dashboard.ts`, `lib/types/dashboard.ts`, `components/ui/decision-badge.tsx`, `confidence-badge.tsx` | Eski BUILD/güven tipleri ve sahte fixture'lar dosyalarda duruyor; dashboard artık bunları tüketmiyor | Ayrı temizlikte kaldır veya kabul edilmiş sözleşmeye taşı; BUILD'i otomatik olumlu bulguya çevirme | Gelecek rapor/liste sözleşmesi |
| `components/workspace/new-validation-form.tsx` | Adımlar yalnız yerel state; alan taslağı korunmuyor; `setStarted(true)` sahte başlangıç bildiriyor | Girdiyi koru; desteklenmeyen başlatmayı başarı gibi sunma | Brief/proje kimliği, plan onayı ve tekrar güvenli başlatma |
| `components/workspace/research-run.tsx` | Sabit %68, 318 kaynak ve maliyet; yerel Pause/Resume | Prototip/erişilemeyen durumunu açıkla; sonra gerçek durumları bağla | Kalıcı araştırma ve kaynak durumları |
| `components/workspace/decision-report.tsx` | BUILD, %82 güven, puanlar, ürün planına ekleme ve işlevsiz dışa aktarma | Kapsam dışı öneri ve sahte kesinliği kaldır | DecisionReport / EvidenceBundle |
| `components/workspace/evidence-library.tsx`, `lib/mock-data/workspace.ts` | Mock alıntılar, doğrulanmış etiketi, işlevsiz kaynak açma | Örneği etiketle; doğrulanmamış kanıtı doğrulanmış gösterme | Alıntı/URL/tarih/hash/sürüm bağı |
| `components/workspace/competitor-table.tsx`, `pain-points-board.tsx` | Sabit satır/sayılar; karşılaştırma/kanıt düğmeleri bağlı değil | Örnek içerik ve desteklenmeyen eylemleri açıkla | SourceReport / EvidenceBundle |
| `components/workspace/projects-board.tsx` | Mock üzerinde filtre/seçim çalışıyor; proje açma bağlı değil | Yerel etkileşim ile gerçek proje kaydını ayır | Proje/araştırma liste ve detay uçları |
| `components/workspace/settings-panel.tsx` | `setSaved(true)` ile sahte kayıt bildirimi | Backend onayı olmadan kaydedildi yazma | Ayar/profil kapsamı |
| `components/layout/top-bar.tsx`, `app-sidebar.tsx`, `components/workspace/workspace-screen.tsx` | Sabit ay ve işlevsiz bildirim/yeni araştırma/workspace/başlık kontrolleri | Gezinmeyi bağla; desteklenmeyen işlemleri gizle veya açıklayarak pasifleştir | Gezinme yerelde yapılabilir; hesap/bildirim işlemleri API ister |
| `components/workspace/help-center.tsx` | Tanımlanmamış confidence yöntemi ve işlevsiz destek düğmesi | Metni güncel kanıt kurallarına uyarla | Metin düzeltmesi API beklemez |

Üst çubuk ve yan menü dashboard'da da görünür; bu teslim yalnız dashboard içerik bileşenlerini düzeltir. Ana sayfanın bütün kontrollerinin düzeltildiği iddia edilmez.

## Kontroller ve kabul

- Bağımsız kod incelemesi: geçti; engelleyici bulgu yok.
- `npm run typecheck --prefix apps/web`: geçti.
- `npm run lint --prefix apps/web`: geçti.
- `git diff --check -- apps/web/components/dashboard`: geçti.
- Üretim derlemesinin ilk denemesi sandbox `spawn EPERM` hatasıyla durdu. İzinli `npm run build --prefix apps/web` yeniden denemesi geçti: derleme, TypeScript ve 12 statik sayfa üretimi başarılı.
- Üretilen ana sayfanın `<main>` HTML kontrolü geçti: sahte BUILD/%82/%68/1.284/12 karar/doğrulanmış kanıt iddiaları yok; erişilemeyen veri açıklamaları ve üç prototip bağlantısı mevcut.
- Tarayıcı görsel/responsive/klavye kontrolü: **not_run**. Browser kurulumu sonrasında kullanılabilir tarayıcı listesi boş döndü. Kaynakta responsive sınıf ve focus stillerinin bulunması görsel test yerine geçmez.
- Canlı API, backend testleri ve deployment: bu frontend alt tesliminde çalıştırılmadı.

Yerel orkestrasyon kaydı: `.orchestrator/runs/ay01-dashboard-20260928/run.json`; uygulama, bağımsız inceleme ve doğrulama sonuçları aynı dizinde tutulur. Run dizini repository kuralıyla Git dışında kalır; bu rapor kalıcı teslim özetidir. Kullanıcı 28 Eylül'de bu değişikliklerin commit/push ve Vercel yayınına gönderilmesini onayladı. Yayın durumu Git/Vercel sonucu üzerinden ayrıca doğrulanır. Batuhan'ın ekran/API kabulü alınmadı; AY-01 açık kalır.
