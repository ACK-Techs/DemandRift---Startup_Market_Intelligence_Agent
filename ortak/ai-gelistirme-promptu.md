# DemandRift'i tamamlayacak AI için prompt

Aşağıdaki metni projenin mevcut main checkout'unda çalışan AI'a ver:

---

DemandRift'in aktif üç fazını `AGENTS.md`, `ortak/gelistirme-plani.md` ve ayrıntılı iş kapsamı için `ortak/raporlar/tamamlama-test-ve-hetzner-yol-haritasi-2026-10-01.md` üzerinden tamamla. Gerçek mevcut koddan devam et; eski durum raporlarına bakıp uygulanmış özellikleri yeniden yazma. Bu talimat frontend/backend/veri/runtime geliştirmesini ve sonunda test, kontrol ve hata düzeltmesini yetkilendirir. Frontend Vercel yayını bu çalışma kapsamının dışındadır.

Yalnız mevcut `main` üzerinde çalış. Yeni branch, worktree, PR veya ayrı checkout açma. Başka branch'te main'e alınmamış iş varsa mevcut kullanıcı değişikliklerini koruyarak main'e normal merge ile al. Force push, reset --hard ve git clean kullanma.

Başlangıçta `code_pusher` adlı tek bir subagent çağır ve aynı checkout'ta yalnız Git işlemleriyle görevlendir. Ana AI bütün işlevsel geliştirmeyi yapar; pusher kod geliştirmez veya test çalıştırmaz. Ona şu görev metnini ver:

"Bu projenin Git index/commit/push sahibisin. Aynı main checkout'unda çalış; yeni branch/worktree/PR açma. Ana AI'ın ilettiği tamamlanmış, birbirini tamamlayan dosyaları stage edip anlamlı Conventional Commit oluştur ve origin/main'e normal push yap. Bu prompt geliştirme commit/push yetkisini verir; her committe tekrar izin isteme. Ara commit/push için test/review bekleme: kullanıcı testleri proje sonuna bıraktı. Secret, env, ham özel veri, log ve yerel generated evidence ekleme. Stage/commit sırasında verilen dosyalara yazımı ana AI ile kısa koordine et. Remote ilerlemişse fetch ve normal merge yap; çatışma varsa ana AI'a bildir. Force push/reset --hard/git clean yok. Sonucu commit SHA ve push durumu ile bildir."

Planın kalan işlerini bağımlılık sırasıyla uygula: ortak kayıt/auth/proje/worker/bütçe temeli; Faz 1 netleştirme ve onaylı plan; Faz 2 kaynak toplama/normalizasyon/filtreleme/alıntılı bulgular; Faz 3 yeterlilik/rapor/sonlu gap; bunların frontend ve işletim bağlantıları. Mevcut ürün kapsamını sadeleştirme bahanesiyle eksiltme; ihtiyaç gösterilmeden yeni framework veya altyapı ekleme.

Geliştirme sırasında test, lint, typecheck, build doğrulaması, model değerlendirmesi, browser deneme paketi, ayrı reviewer/verifier/integration agent'ı veya kabul gate'i çalıştırma. Her küçük değişiklik için test yazma. Uygulamayı çalıştırmak için gereken dev sunucusu serbesttir; gözünün önündeki hatayı düzelt. Mevcut test/fixture'ları koru. `.orchestrator` run graph, event/result JSON, revision zinciri ve hash checkpoint oluşturma. Yalnız planın kısa ilerleme listesini güncelle; bir dosya yazmak işlevin doğrulandığı anlamına gelmez.

Ürün runtime'ında kullanıcı/proje izolasyonunu, kaynak erişim iznini, sert bütçe sınırlarını, kullanıcı onayını ve alıntı/kanıt doğruluğunu uygula. Ara kontrolün kaldırılması bunları kaldırmaz. Araştırılan fikir için Build/MVP/PRD ve sonraki ürün geliştirme planı üretme. LLM web/grounding/browser/script araçları kullanmaz; yalnız backend'in sağladığı veriyi analiz eder.

Anlamlı parçalar tamamlandığında code_pusher'a dosyaları ilet ve main üzerinde commit/push al; sen bağımsız kodlamaya devam et. Aynı dosyaları staging sırasında değiştirme. Çalıştırılmamış testleri geçti gibi gösterme. Push işlemi prod deployment sayılmaz; development sırasında CI/test veya manuel deploy workflow tetikleme.

Tüm işlevler kodlandıktan sonra `ortak/kalite-ve-test-ilkeleri.md` ile final aşamasını başlat: mevcut API/DB/worker/infra/frontend/lab testleri, 87 faz senaryosu, gerçek kullanıcı akışı, kaynak/alıntı/model değerlendirmesi ve işletim kontrolleri. CI yalnız bu aşamada main üzerinde manuel çalışır. Gerçek hataları öncelik sırasıyla düzelt; gerekli regresyon testini burada ekle. İlgili testleri tekrar çalıştır ve en sonda tam final paketini yeniden çalıştır. Final düzeltmeleri de code_pusher ile main'e yayımla. Backend deployment için aynı main SHA'nın final CI başarısını kullan; ayrıca orchestrator kabul kaydı gerekmez. Mevcut kullanıcı kapsamı/yetkisi içindeki backend işletimini uygula; frontend'i yayımlama.

Mevcut yetkilendirilmiş erişim ve bütçe kayıtlarını kullan; yeni ücretli kapsam icat etme. Dış erişim gerçekten eksikse yalnız o girdiye bağlı işin engelini açıkça belirt, diğer işleri tamamlamaya devam et. Kullanıcıdan rutin adımlar için yeniden onay isteme. Hiç çalışmamış bir kontrolü geçti veya kapsamı bitmemiş ürünü tamamlandı diye sunma.

İşi plan veya öneri aşamasında bırakma. Hedef çalışan üç faz, tamamlanmış final test/kontrol ve düzeltilmiş hatalardır. Son mesajda yapılan işlevleri, gerçek final test sonucunu, main commit/push bilgisini ve varsa kalan somut engeli kısa biçimde bildir.

---
