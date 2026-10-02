# Ortak kalite ve test ilkeleri

**3 Ekim 2026 kullanıcı kararı:** geliştirme sırasında test ve kontrol kapıları kullanılmaz. Onaylı ürün işlevleri tamamlandıktan sonra tek final test/kontrol aşaması yapılır; bulunan gerçek hatalar düzeltilir, ilgili testler yeniden çalıştırılır ve son sürümün final suite'i tamamlanır. [Geliştirme planı](gelistirme-plani.md) çalışma yönteminin güncel kaynağıdır.

## Testlerin zamanı ve durumu

- Mevcut API/frontend/laboratuvar test kodları, fixture'lar, senaryo JSON'ları ve geçmiş sonuçlar korunur. Test dosyası veya planlı senaryo geçmiş başarı kanıtı değildir.
- Geliştirmede başlangıç/baseline testi, her dilimde test, lint/typecheck, tarayıcı kabulü, bağımsız review/verify/integration ve ayrı acceptance işi yoktur. Eski run/skill belgelerindeki kapılar bu yeni süreçte uygulanmaz.
- CI yalnız final aşamada manuel `workflow_dispatch` ile başlatılır; push/branch başına koşmaz. Test image build sırasında pytest çalıştırmaz. Aynı testi final suite içinde hem build'de hem container'da tekrar koşma.
- Uygulayıcı kodu okuyabilir, gerçek bir yazım hatasını hemen düzeltebilir ve sözleşme/consumer bağlantısını aynı işte tamamlayabilir. Ürünün runtime doğrulamaları kodda uygulanır; kaldırılanlar geliştirme süreci kapılarıdır.

## Finalde kontrol edilecek kapsam

| Kapsam | Beklenen davranış |
|---|---|
| API/platform | DB/migration, oturum, kullanıcı/proje izolasyonu, idempotency, worker retry/cancel/restart, atomik ortak bütçe, secret ve güvenli egress |
| Sözleşme | Producer/consumer ve FE tipleri aynı sürüm; unknown, hata ve kısmi sonuç anlamları korunur |
| Kayıtlı kaynak verisi | Gerçek içerik≠sitemap/challenge/snippet; URL/hash/tarih/owner bağı, ham artifact, normalizasyon ve segment doğruluğu |
| Faz 1 | 10 fikir × üç anlatım = 30 senaryo; original idea, kullanıcı onayı, unknown ve doğru plan |
| Faz 2 | 24 senaryo; edinme/hata ayrımı, dedup/bağımsızlık, ilgililik/karşıt kanıt, quote/hash/lineage |
| Faz 3 | 33 senaryo; 3/2+nitel yeterlilik, dört outcome, kaynaklı rapor ve sonlu gap; Build/MVP/PRD kapsamı kapalı |
| Model | Etiketli örnekte semantik doğruluk ve kaynak desteği; schema tek başına model kalitesi sayılmaz; araçlar kapalı |
| Frontend/E2E | Gerçek local FE→Hetzner BE hesap→fikir→plan→run→kanıt→rapor→refresh; iki kullanıcı/proje, hata/boş/kısmi durumlar, mobil/desktop/tema/klavye |
| İşletim | Readiness, API/worker/DB/Redis kesinti ve recovery, budget/cancel yarışları, backup/restore/rollback; diğer uygulamalar korunur |

**87 senaryo** planlı değerlendirme girdisidir. Otomatik runner bulunmuyorsa finalde gerçek girdi/çıktı ile kontrol edilir; var olmayan komut veya ölçülmemiş başarı yazılmaz. Gerekli test hazırlığı final aşamada tamamlanır. Belge haritası, görev kartı ve zorunlu rapor cümlesi testleri ürün kabulünü durduran kapılar değildir.

## Final koşu ve düzeltme düzeni

1. Final suite için kilitli Python/Node bağımlılıkları ve geçici gerçek PostgreSQL/Redis ortamı hazırla. Testlerde üretim DB'sini kullanma.
2. Mevcut gerekli offline/native testleri ve frontend lint/typecheck/build'i çalıştır. Manuel final CI'ın çalıştırdığı aynı testleri yerelde tekrar koşmak gerekmez. Offline suite'de ayrılan DB testleri gerçek PostgreSQL koşusunda çalışmalıdır; zorunlu skip/not_run/not_verified başarı sayılmaz.
3. Faz senaryolarını ve model/tarayıcı/canlı işletim kontrollerini tamamla. Canlı kaynak/model koşularını toplam onaylı bütçede yürüt; offline başarı canlı kalite iddiası değildir.
4. Gerçek hataları kısa bir listede topla, düzelt ve ilgili testi/senaryoyu tekrarla. Düzeltme için yeni review/verify/integration zinciri açma. Anlamlı bir yeni regresyon örneği gerekiyorsa kalıcı sete ekle; uygulamayı tekrar eden veya düşük etkili belge biçimini sabitleyen testler yazma.
5. Düzeltmeler bitince son revision için gerekli final suite'i tamamla. Yayın exact main SHA'nın başarılı final CI sonucuna bağlıdır; yeni kodu önceki SHA sonucu ile geçti sayma.

## Üründe korunacak kurallar

Geçersiz şema ilerlemez. Başka kullanıcı verisi erişilemez; kaynak policy, bütçe ve secret sınırları aşılmaz. Uydurma/desteksiz alıntı veya iddia raporda kullanılmaz. Hata ile gerçek boş sonuç ayrıdır; eksik veri tam araştırma diye sunulmaz. Kanıt policy v1'in 3 bağımsız örnek/2 kaynak tabanı nitel kontrollerle uygulanır; sayı tek başına yeterlilik değildir.

[Veri laboratuvarındaki](../faz-1-fikir-ve-arastirma/veri-laboratuvari/README.md) dosya yolları, gerçek kaynak verisi ve testleri korunur. Eksik ham dosya `missing_artifact` olarak raporlanır; tek örneğin varlığı bütün corpus'u doğrulamaz. Arşiv/canlı ayrımı, tekrar/boilerplate, bağımsızlık ve kaynak tipinin araştırma sorusuna uygunluğu finalde kontrol edilir.

Model seçimi Gemini 3.1 Flash Lite; web/grounding/fetch/script/shell yetkisi yoktur. [RULES](RULES.md) ürün kapsamını korur. Model/prompt değişimi aynı veri setinde anlam/niyet/kaynak desteğiyle karşılaştırılır; birebir kelime veya tek sabit anahtar kelime dizisi zorunlu tutulmaz. Yüzde/eşik uydurulmaz; etiketli ölçüm ve hata örnekleri gösterilir.

1 Ekim devam notunun ortak canlı sınırları: **$5; 300 dış istek; 50.000.000 byte; 150 sayfa; 1000 kayıt; 1800 saniye; 300.000 token; concurrency 2.** Geçmiş deneme/retry'lar dahil kalan bütçe kullanılır. Final canlı suite hazır olmadan saat başlatılmaz ve sayaç sıfırlanmaz. Ücretli çağrıdan önce gerçek provider/model erişimi, fiyat ve atomik bütçe ledger'ı hazırdır; sessiz model fallback yoktur.

## Kayıt ve tamamlanma

Tek kısa final özeti yeterlidir: main SHA, ortam, çalıştırılan komutlar/CI bağlantısı, geçme/kalma/çalıştırılamama, 87 senaryonun kısa sonuçları, gerçek hatalar ve düzeltmeler, canlı maliyet ve kalan dış engeller. Mevcut CI çıktısı/dosya yeterliyse ayrı kanıt JSON'u veya acceptance dosyası üretilmez. Secret ve özel ham içerik sonuç kaydına yazılmaz; geçmiş başarısız sonuçlar sessizce değiştirilmez.

Kritik/yüksek ürün hataları düzeltilmeden ve zorunlu final kontrolleri çalıştırılmadan proje tamamlandı denmez. Batuhan final ürün kontrolü, Ayselin somut veri hataları, Ayşenur ekran düzeltmeleri için mevcut sahipliklerini korur; her küçük yazım işinde ayrıca onay vermeleri gerekmez.
