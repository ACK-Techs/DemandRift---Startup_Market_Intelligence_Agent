# DemandRift çalışma talimatları

3 Ekim 2026 kullanıcı kararı: geliştirme doğrudan `main` üzerinde yapılır. Üç fazın bütün işlevleri tamamlanana kadar test, lint, typecheck, build doğrulaması, ayrı review/verify/integration veya kabul kapısı çalıştırılmaz. Çalıştırmak için gereken geliştirme sunucusunu açmak ve görülen hatayı düzeltmek bu yasağa dahil değildir. Kapsam bittiğinde tek final test ve kontrol turu yapılır; çıkan hatalar giderilir, ilgili testler ve son tam paket tekrar çalıştırılır.

## Başlangıç

1. `ortak/gelistirme-plani.md` dosyasını oku; yapılacak işi ve mevcut kodu incele.
2. İlgili ürün gereksinimleri için `ortak/RULES.md`, `ortak/uygulama-m1-sozlesme-kararlari.md` ve ilgili üç faz belgesini kullan. Her adımda bütün belgeleri tekrar okuma.
3. Git dalı `main` olmalı. Yeni branch, worktree, PR veya ayrı checkout oluşturma. Mevcut farklı branch işleri varsa kullanıcı kapsamı içinde `main`e normal merge ile al; çalışmaları kaybetme.

## Geliştirme

- Ana AI planı uygular ve yalnız `ortak/gelistirme-plani.md` içindeki kısa ilerleme listesini günceller. `.orchestrator` run graph, event, result JSON, hash checkpoint veya ayrı onay düğümü oluşturmaz; eski kayıtlar tarihçedir.
- Küçük değişiklikler için test yazma, bağımsız incelemeci/verifier çağırma, her teslimi yeniden kontrol ettirme. Mevcut test ve fixture dosyalarını koru. Gerekli yeni regresyon testlerini finalde gerçek hata veya kritik davranış için ekle.
- Ara commit/push için test geçme şartı yok. Test yapılmadıysa bunu açıkça belirt; ürün tamamlandı veya doğrulandı deme.
- Ürün güvenlik kuralları, proje izolasyonu, bütçe limitleri, onaylı hipotez, alıntı doğruluğu ve kanıt yeterliliği runtime'da uygulanır. Geliştirme kapılarının kaldırılması bu ürün kurallarını kaldırmaz.
- Aktif kapsam üç fazdır. Araştırılan fikir için Build/MVP/PRD veya sonraki ürün geliştirme planı üretme.
- Mevcut kullanıcı değişikliklerini ve ilgisiz dosyaları koru. Secret, `.env`, ham özel veri, log ve üretilmiş yerel kanıtları Git'e ekleme.

## Code pusher subagent

Git index/commit/push işlemlerinin tek sahibi aynı checkout'ta çalışan `code_pusher` subagent'tır. Ana AI ona biten, birbirini tamamlayan dosyaları ve kısa commit amacını iletir; pusher test, review, işlevsel geliştirme veya yeni branch yapmaz. Stage edilen dosyalar için kısa süreli yazma koordinasyonu yeterlidir; hash/approval zinciri kurulmaz. Açık commit/push yetkisi varsa bu yetkiyi her seferinde yeniden sorma.

`main` üzerinde anlamlı commit oluştur, `origin/main` ilerlemişse normal merge ile birleştir ve normal push yap. Force push, reset --hard, git clean veya kullanıcı çalışmasını silmek yasaktır. Git çatışması çıkarsa ana AI anlamını koruyarak çözer. Pusher sonucu commit SHA ve push durumu ile bildirir.

## Final

Tüm plan işlevleri kodlandığında `ortak/kalite-ve-test-ilkeleri.md` uygulanır. CI yalnız manuel final turunda çalıştırılır. Hatalar ana AI tarafından düzeltilir; ek geliştirme döngüsü ve yeni graph açılmaz. Son teslimde çalışan kapsamı, final sonuçlarını ve varsa gerçek engelleri kısa biçimde bildir.

Bu karar `.orchestrator`, eski skill, rol, faz görev ve kabul belgelerindeki farklı süreç talimatlarının yerine geçer. Git bütünlüğü ve dosya kaybını önlemek için yapılan işlemler ürün testi değildir.
