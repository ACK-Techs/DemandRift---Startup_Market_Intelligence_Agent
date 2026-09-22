# Ayşenur — tasarım ve kademeli frontend entegrasyonu

Calendar kullanıcı adı: **aysenurdemezoglu**. [İçe aktarılacak görev dosyası](../calendar-import/demandrift-aysenurdemezoglu.json).

Tüm işler **planlandı**; bu dosya tamamlanma raporu değildir. Kabul eden ve düzeltmeleri yeniden kontrol eden: **Batuhan**. [Ortak takip/geri bildirim kuralları](../ekip-ve-teslim.md).

| ID | Faz | Görev | Bağımlılık | Teslim / kabul koşulu | Durum | Kanıt / FB / son güncelleme |
|---|---|---|---|---|---|---|
| AY-01 | Tümü | Mevcut ekran eksiklerini ve ortak tasarım durumlarını düzenle | Kod envanteri; frontend rehberi | Öncelikli ekran listesi; responsive/klavye/okunabilirlik kontrolleri | planlandı | — |
| AY-02 | Tümü | Batuhan ile sürümlü istek/yanıt/hata ve ekran alanlarını eşleştir | Her fazın BT teslimi | Eksik API alan listesi ve gerçek payload eşlemesi | planlandı | — |
| AY-03 | 1 | Fikir, netleştirme, kategori ve plan ekranını bağla | BT-01 + BT-04 API ilk teslimi; AY-02 | Gerçek kayıt, kullanıcı girdisinin korunması ve hata durumları | planlandı | — |
| AY-04 | 2 | Kaynak ilerlemesi, kanıt, problem ve rakip ekranlarını bağla | BT-05 API ilk teslimi; AY-02 (BT-06 sonraki kabul) | Gerçek ilerleme, kısmi/erişim durumu, kaynak/alıntı/tarih ve alanlar | planlandı | — |
| AY-05 | 3 | Rapor, olumlu bulgu/karşıt/eksik veri ve yönetici değerlendirmesini göster | BT-07 rapor API teslimi (BT-08 sonraki kabul) | Build/MVP ve uydurma confidence kaldırılmış; gerçek rapor/kanıt bağı | planlandı | — |
| AY-06 | Tümü | Dashboard/proje listesi ve kapsamda kalan diğer ekranları bağla | İlgili liste/ayar endpointleri; BT-09 önceliği | Mock başarı yok; desteklenmeyen buton/ayar açıkça ele alınmış | planlandı | — |
| AY-07 | Tümü | Batuhan geri bildirimlerini düzelt; yenileme ve entegrasyon kontrollerini teslim et | Her AY teslimi | Beklenen/gerçek ekran verisi, hata durumları ve düzeltme kanıtı | planlandı | — |

Dosya/ekran bazlı detay: [frontend entegrasyonu ve eksikler](../frontend-entegrasyon-ve-eksikler.md). Arayüzü şimdi yeniden inşa etme görevi bu belge oluşturulurken yürütülmedi; listedeki işler Ayşenur’a teslim planıdır.

## Açık geri bildirimler

Henüz gerçek bulgu kaydı açılmadı. [Şablon](geri-bildirim-sablonu.md) kullan; görev ID ve kanıt bağlantısını üst tabloya ekle.

## Bağımlılıkların anlamı

Başlatma girdisi ile son kabul ayrı adımlardır. Batuhan önce API/örnek veya hata bildirimini teslim eder; karşı taraf bu girdiye dayanarak çalışır. Batuhan’ın kabul alt adımı karşı tarafın tesliminden sonra yürür. API/hata bildirimi hazır olduğunda Batuhan’ın bütün görevinin kapanması beklenmez.

## Ortam ve teslim sınırı

Yayın hedefi Vercel. API adresini ortamdan alan Next.js entegrasyonunu ve gerçek durum ekranlarını hazırla. Vercel hesabı/proje/repo bağlantısı, domain ve yayın ayarlarını Çağlar ile sonraki ayrı çalışmada yapacağız. Bu takip dosyası mevcut deployment yapılmış gibi işaretlenmez.
