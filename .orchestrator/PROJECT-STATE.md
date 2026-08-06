# Current Project State

## Durum

- Faz 1–7 ürün ve teknik planları tamamlandı ve çapraz revize edildi.
- `Platform-Temeli.md` bağlayıcı yatay mimaridir.
- `Ust-Yonetim-Ana-Mimari-Plani.md` bağlayıcı entegrasyon ve yönetim sırasıdır.
- Faz 8 bilinçli olarak başlamadı.
- Uygulama source tree (`apps/`, `packages/`, `infra/`, `tests/`) henüz oluşturulmadı.
- `.orchestrator` geliştirme control plane'i kuruldu ve doğrulandı.

## Bir sonraki çalışma

Kullanıcı geliştirmeyi başlattığında PM Manager ilk run'ı repository/contracts/bootstrap için oluşturmalıdır. Sıra:

1. Repository baseline ve toolchain kararı.
2. `packages/contracts` kanonik şemaları.
3. Identity/tenant ve storage sınırları.
4. Durable workflow iskeleti.
5. Source Policy/Egress, Cost Ledger ve AI Gateway temelleri.
6. Faz 1 üretici ve Faz 2 tüketici entegrasyonu.

Bu maddeler doğrudan kodlanmadan önce aktif run içinde architecture/contract, implement, review, verify ve integration item'larına bölünmelidir.

## Açık kullanıcı sınırları

- Faz 8 başlangıcı kullanıcı onayı gerektirir.
- Paid provider/credential, production write, destructive operation ve legal source approval kullanıcı/platform boundary'sidir.
- Commit ve push ayrı açık kullanıcı onayları olmadan yapılmaz.
- Commit onayı verilen run'da her başarıyla tamamlanan write item, kontrollerden sonra atomik Conventional Commit olarak kaydedilir; mesaj `type(scope): summary` biçiminde aşamaya/modüle uygun scope taşır.
- Implementer push yapmaz. Push onayı verilmişse üst manager yalnız review, verify ve integration kabulü tamamlanan checkpoint'i push eder; force-push yasaktır.

## Resume

Yeni oturum bu dosyadan sonra `.orchestrator/runs/` altındaki aktif run'ları kontrol eder. Bu state dosyası run graph'ın yerine geçmez; run oluştuğunda gerçek execution state run/event/result dosyalarındadır.
