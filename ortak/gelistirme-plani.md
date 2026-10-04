# DemandRift geliştirme planı

**3 Ekim 2026 kullanıcı kararı:** mevcut üç fazın frontend/backend işlevlerini önce tamamla; test ve kontrolleri bütün ürün hazır olduktan sonra tek final aşamada yap. Ardından gerçek hataları düzelt, ilgili testleri yeniden çalıştır ve son sürümün final suite'ini tamamla. Bu belge çalışma yönteminin güncel kaynağıdır; eski run/rol/skill belgelerindeki sürekli review/verify/integration kapılarının yerini alır.

İşlevsel backend/frontend/Hetzner kapsamı [tamamlama yol haritasında](raporlar/tamamlama-test-ve-hetzner-yol-haritasi-2026-10-01.md), final test kapsamı [kalite ve test ilkelerinde](kalite-ve-test-ilkeleri.md). [RULES](RULES.md), veri sözleşmeleri ve kanıt yeterliliği ürün davranışını tanımlar. Süreç sadeleşmesi ürünün auth/tenant/secret, kaynak izin/egress, bütçe, veri bütünlüğü ve citation güvenliğini kaldırmaz.

## Main üzerinde çalışma

1. Mevcut checkout, kullanıcı değişiklikleri ve branch'lerin benzersiz commit'lerini oku. Main'de bulunmayan ilerlemeyi kaybetmeden main'e birleştir; merge çakışmalarını çöz. Tamamlanan işlevleri yeniden yazma.
2. Bütün yazım mevcut checkout'ta `main` üzerindedir. Yeni branch/worktree açma, sürekli PR veya branch turu oluşturma. Eski branch'leri silmek zorunlu değildir.
3. Tek **code pusher subagent** Git işlerini yürütür. Ona somut dosya listesi ve kısa commit amacı ver; yalnız status/diff/fetch/stage/commit/merge/push yapar. Test, review veya ayrı kabul kanıtı istemez; ürün/test/docs dosyası yazmaz. Normal main push'ı kullanılır; force push ve kullanıcı değişikliklerini kaybettiren işlemler yapılmaz.
4. Uygulayıcı AI ürün kodunu ve gerekli belgeleri yazar. Faydalı olduğunda ayrık dosya kapsamlarıyla geliştirme subagent'ları kullanabilir; aynı dosyaya eşzamanlı yazım yapılmaz. Değişikliklerin main'e alınması için bağımsız review/verify/integration agent'ları beklenmez.

## Uygulama sırası ve kısa takip

Bu yeniden planlama sırasında ürün geliştirmesi veya test başlatılmadı. Sıra tablosu bağımlılıkları gösterir; bütün satırların yeniden yapılması gerektiği iddiası değildir. Birleşmiş main kodundaki mevcut ilerleme temel alınır. Devam eden AI yalnız durum hücresini kısa günceller; ikinci backlog, run graph veya ayrı acceptance JSON'ları açmaz.

| Sıra | İş | Korunan iş kimlikleri | Durum |
|---|---|---|---|
| 1 | Mevcut ilerleme ve eksik işlevleri main'den belirle | Tüm BE/FE/OP | 3 Ekim: taşınmış aynı main checkout okundu; auth/DB/bütçe/Faz 1 çekirdeği korundu; worker ve Faz 2/3 bağlantıları eksik |
| 2 | Hesap/proje, worker, Gemini+bütçe, source registry ve erken read API; frontend hesap/proje bağlantısı | BE-03–06, BE-15A/16A, FE-03/04 | Temel ve runtime/API bağlantıları kodlandı; final doğrulaması bekliyor |
| 3 | Fikir/netleştirme/kategori/sorgu/onaylı plan ve tek araştırma başlatma | BE-07, FE-05/06 | Kod ve frontend bağlantıları tamamlandı; final doğrulaması bekliyor |
| 4 | Kaynak edinme, ham kayıt, normalizasyon/dedup, ilgililik, claim/citation ve EvidenceBundle; kaynak/kanıt ekranları | BE-08–12, BE-15B, FE-07/08 | Kod ve frontend bağlantıları tamamlandı; final doğrulaması bekliyor |
| 5 | Yeterlilik, dört outcome, rapor/gap/sürüm/export; dashboard/ayar ve tüm ekran durumları | BE-13/14, BE-15C/16B, FE-09–12 | Kod ve frontend bağlantıları tamamlandı; final doğrulaması bekliyor |
| 6 | Hetzner Compose/secret/migration/yedek/rollback/route ve işletim talimatını hazırla | OP-02–05 | Kalıcı izin/bütçe, toparlanma, log/metric ve DB+raw yedek/restore kodlandı; yayın ve kontrol finalde |
| 7 | Bütün ürün için test/kontrol, hata düzeltme ve son suite | QA-01–08; 30+24+33=87 senaryo | Final: 87 girdi için offline sınırlar ve 10 runtime regresyonu geçti; 0e58246 manuel CI başarılı (API/infra, PostgreSQL, frontend, lab). Hesap değişimi düzeltmesi sonrası son SHA koşusu sırada; canlı model semantiği ve 71 eksik pilot artifact doğrulanmadı |
| 8 | Final Hetzner yayını ve gerçek local FE akışı; kısa teslim özeti | OP-06 | Gerçek FE→Hetzner iki hesap/proje/fikir ve oturum izolasyonu geçti; dört viewport/tema/klavye geçti. Backend yayın/restore/recovery sırada; mevcut kalıcı bütçe suite’i ve incelenmiş kaynak izinleri bulunamadı |

BE-01/02 ve FE-01/02 gibi geçmiş tamamlanmış paketleri tekrar planlama. BE-15/16 alt kimlikleri uygulama sırasını anlatır; ayrı kontrol veya kabul işleri değildir. Backend dilimi uygulanınca ilgili frontend'i bağla; ürünün responsive/klavye/hata durumlarını uygularken düşün, browser testi finalde yapılır.

## Geliştirme boyunca uygulanacak süreç

- Kodu yaz, gerekli bağımlı consumer/frontend bağlantısını tamamla, sonraki işlevsel dilime geç.
- Otomatik veya manuel test, lint/typecheck, sürekli browser kontrolü ve final kabul koşusu çalıştırma. CI yalnız `workflow_dispatch` ile finalde başlatılır; her push test koşmaz. Runtime build içine pytest gömme.
- Her küçük düzeltme için yeni görev, review/verify/integration düğümü veya kanıt dosyası açma. Gerekli sözleşme değişikliğini producer/consumer ile aynı iş içinde tamamla.
- Mevcut testleri, fixture'ları, gerçek veri ve geçmiş sonuçları koru. Test sayısını hedef yapma; sırf dosya haritası, görev kartı veya rapor cümlesini sabitlemek için yeni test ekleme.
- Açıkça görülen gerçek kod hatasını yazım sırasında düzelt; hata düzeltilmesi için proje sonunu beklemek gerekmez. Ayrı kontrol turu başlatma. Uygulamayı ilerletmek için kod/şema/bağımlılık okumak bu politika kapsamında test değildir.
- Kullanıcı/model/kaynak kapsamını genişletme. Onaylı mimariyi yeniden tasarlama; ölçülmüş sorun yoksa ekstra framework, algoritma ve kontrol altyapısı kurma.

## Final test ve hata düzeltme

Bütün onaylı işlevler ve frontend bağlantıları yazılınca bu aşamaya geç:

1. Mevcut API/gerçek geçici PostgreSQL/Redis, contracts, frontend ve gerekli offline laboratuvar testlerini bir final suite olarak çalıştır. Manuel final CI aynı testi build/container/yerel ortamda gereksiz tekrarlamaz. Frontend lint/typecheck/build'i finalde tamamla.
2. 87 faz senaryosunu, model semantiğini, local frontend→gerçek backend iki kullanıcı akışını, mobil/klavye ve restart/bütçe/iptal/backup/restore/rollback durumlarını kontrol et. Senaryo JSON'unun varlığını başarı sayma.
3. Gerçek hataları tek kısa listede tut ve düzelt. Her düzeltmeden sonra ilgili başarısız test/senaryoyu tekrarla. Yeni bağımsız review zinciri açma.
4. Hatalar düzeldikten sonra son kod için gerekli final suite'i çalıştır. Kod değişmişse önceki SHA'nın sonucu yeni SHA'nın kabulü sayılmaz.
5. Exact main SHA ve aynı SHA'daki başarılı final CI ile Hetzner'e yayınla; local FE'nin gerçek akışını final canlı kontrolde tamamla. Frontend Vercel yayını bu teslimde yoktur.
6. Tek kısa sonuç yaz: main SHA, komut/CI bağlantısı, sonuç, gerçek hatalar/düzeltmeler, canlı kullanım ve çözülemeyen dış engeller. CI çıktısını yeniden çok sayıda JSON'a kopyalama.

1 Ekim devam notunda onaylanan ortak canlı limitleri korunur: **$5; 300 dış istek; 50.000.000 byte; 150 sayfa; 1000 kayıt; 1800 saniye; 300.000 token; concurrency 2.** Geçmiş harcamalar dahil kalan limit finalde kullanılır; sayaç veya suite bütçesi sıfırlanmaz. Canlı suite saatini geliştirme sırasında başlatma. Model seçimi Gemini 3.1 Flash Lite, araçsız; secret sadece backend/worker runtime'da kalır.

## Tamamlandı demek için

Onaylı üç faz, frontend ve işletim işlevleri uygulanmış; final suite ve gerçek akış kontrol edilmiş; kritik/yüksek hatalar düzeltilmiş olmalıdır. Zorunlu çalıştırılamayan test veya eksik dış girdi varsa bunu açık yaz; bütün proje geçti deme. Erişilemeyen kaynak doğru raporlanabilir; her fikre olumlu rapor veya her siteye erişim vaat edilmez.

1 Ekim planındaki **34–57 aktif iş günü** tarihsel tahmindir. Süreç değiştiği için yeni bitiş tarihi veya süre tahmini bu belgede üretilmedi.
