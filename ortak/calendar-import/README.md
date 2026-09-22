# Calendar görev JSON teslimi

Format, alicaglarkocer.com/calendar/app.js içindeki normalizeImport ve importTasks fonksiyonları okunarak hazırlandı. 22 Eylül 2026: Kullanıcının açık talebiyle toplu dosya tarayıcıdan içe aktarıldı. Uygulama “22 görev eklendi.” onayını gösterdi. **Dosyaları tekrar yükleme.** [İçe aktarma kaydı](import-receipt.json).

## Dosyalar ve kişiler

| Dosya | Kullanıcı | Görev |
|---|---|---|
| [Tüm görevler](demandrift-tum-gorevler.json) | Üç kişi | 22 |
| [Batuhan](demandrift-batuhanevleksiz.json) | batuhanevleksiz | 9 |
| [Ayşenur](demandrift-aysenurdemezoglu.json) | aysenurdemezoglu | 7 |
| [Ayselin](demandrift-ayselinaydogdu.json) | ayselinaydogdu | 6 |

**Tek seferde yüklemek için yalnız tüm görevler dosyasını seç.** Alternatif olarak üç kişi dosyasını birer kez yükle. İkisini birlikte yükleme: aynı görevleri yeniden oluşturur.

## İçe aktarma

1. Calendar'da görev atama yetkisi olan hesapla “+ Görev içe aktar” ekranını aç.
2. Ürün adı `DemandRift` varsayıldı. İçe aktarıcı büyük/küçük harf dahil mevcut ürün adıyla birebir eşleştirir. Calendar'da ürün yoksa önce ürünü oluştur; farklı yazılıyorsa kullanacağın JSON'un üstteki `product` alanını o ada getir. Canlı ürün listesi bu çalışmada okunmadı. Projesiz aktarmak istenirse `product` boş bırakılabilir; başlıklarda DemandRift kalır.
3. Üç kullanıcı adı kullanıcının verdiği biçimde yazıldı; Calendar'da bu kullanıcılar mevcut olmalı. Uygulama username üzerinden gerçek kişi ID'sini kendisi çözer.
4. Toplu dosyayı seç ve içe aktar. Başarı sayısı 22 olmalı; kişi dosyalarında 9/7/6.
5. Kısmi hata olursa tüm dosyayı tekrar yükleme; sadece oluşturulamayan görevlerle yeni dosya kullan. Importer JSON id alanını sunucuya göndermiyor; tekrar yükleme güncelleme/dedup sağlamaz.

## İçerik ve kapsam

version=1; id, title, owner_username ve description mevcut. Öncelik high/medium. Tarih, saat ve süre kullanıcı tarafından belirlenmediğinden boş; görevler sonradan takvim günlerine yerleştirilebilir. Planlanan bağımlılık, somut iş, teslim/kabul ve belge başvuruları açıklamalardadır. Calendar bağımlılıkları otomatik yönetmez.

Batuhan'ın ilk kontrol/geri bildirim/yeniden kabul sorumluluğu, Ayselin'in veri düzeltmeleri ve Ayşenur'un tasarım/API görevleri kişisel takip dosyalarıyla eşlidir. Task ID'leri başlık ve açıklamada korunur. Sunucu/runner/Vercel kurulumu sonraki ayrı çalışma olduğundan bu dosyalara ayrı kurulum görevi eklenmedi.

## Doğrulama

Dört dosya gerçek yerel importer fonksiyonuyla, yalnız mock üyeler/ürün ve ağsız API taklidi kullanılarak kontrol edildi. Tekil ID, owner eşlemesi, assigned payload, açıklamanın korunması ve toplu/kişi dosyalarının aynı içeriği taşıması doğrulandı. Sonraki canlı işlemde DemandRift ürünü ve üç kullanıcı adı UI üzerinden doğrulandı; toplu dosya bir kez yüklendi ve 22 görev oluşturuldu.
