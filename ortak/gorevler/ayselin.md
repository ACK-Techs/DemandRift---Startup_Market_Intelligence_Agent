# Ayselin — kaynak ve veri sorunlarının çözümü

Calendar kullanıcı adı: **ayselinaydogdu**. [İçe aktarılacak görev dosyası](../calendar-import/demandrift-ayselinaydogdu.json).

Tüm işler **planlandı**; bu dosya tamamlanma raporu değildir. Kabul eden ve düzeltmeleri yeniden kontrol eden: **Batuhan**. [Ortak takip/geri bildirim kuralları](../ekip-ve-teslim.md).

| ID | Faz | Görev | Bağımlılık | Teslim / kabul koşulu | Durum | Kanıt / FB / son güncelleme |
|---|---|---|---|---|---|---|
| AS-01 | 1 | Mevcut kaynak alanlarını/örneklerini Batuhan’la eşle; beklenen sonuçları incele | Mevcut laboratuvar; BT-02 hazırlığı | Kaynak yeteneği, alan örnekleri ve erişim sınırları | planlandı | — |
| AS-02 | 1 | Batuhan’ın başarısız kaynak/sorgu bildirimlerini yeniden üret ve düzelt | BT-03 ilk geri bildirimi; görevin kapanması beklenmez | Aynı sorgunun önce/sonra ham sonucu; çözüm veya kanıtlı engel | planlandı | — |
| AS-03 | 1 | İzinli alternatif yöntem/kaynak dene; kategori/veri kalitesini kontrol et | AS-02 | Alternatifin alan/kapsam farkı, limitleri ve kalan eksikleri; Batuhan kabulü | planlandı | — |
| AS-04 | 2 | Alan çıkarımı, tekrar, ilgililik, karşıt kanıt kaybı ve kaynak raporu hatalarını çöz | BT-06 ilk hata bildirimi; sürümlü etiketli örnekler | Hatalı/korunacak örnekler ve düzeltme sonrası kalite farkı | planlandı | — |
| AS-05 | 3 | Bağımsızlık, 3/2 sayımı, alıntı ve rapor yorumunu veriyle kontrol et | BT-07 | Yanlış sayım/yorum için claim düzeyinde bildirim; kanıtlı düzeltme | planlandı | — |
| AS-06 | Tümü | Çözüm günlüğünü ve kaynak sağlık kayıtlarını güncelle | Her bulgu | Denenmiş yollar ve çalışmadığı sınırlar kayıtlı; Batuhan yeniden kontrolüne hazır | planlandı | — |
## Açık geri bildirimler

Henüz gerçek bulgu kaydı açılmadı. [Şablon](geri-bildirim-sablonu.md) kullan; görev ID ve kanıt bağlantısını üst tabloya ekle.

## Bağımlılıkların anlamı

Başlatma girdisi ile son kabul ayrı adımlardır. Batuhan önce API/örnek veya hata bildirimini teslim eder; karşı taraf bu girdiye dayanarak çalışır. Batuhan’ın kabul alt adımı karşı tarafın tesliminden sonra yürür. API/hata bildirimi hazır olduğunda Batuhan’ın bütün görevinin kapanması beklenmez.

## Ortam ve teslim sınırı

Kaynak/veri düzeltmeleri Batuhan’a kanıtla teslim edilir. Gerçek ortak entegrasyon testleri Hetzner/API erişimi hazır olduğunda yürütülür; erişim beklenirken kayıtlı örneklerin incelenmesi ve düzeltme hazırlığı ilerleyebilir.
