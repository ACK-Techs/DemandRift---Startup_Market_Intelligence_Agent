# Ayselin — kaynak ve veri sorunlarının çözümü

Calendar kullanıcı adı: **ayselinaydogdu**. [İçe aktarılacak görev dosyası](../calendar-import/demandrift-ayselinaydogdu.json).

Tüm işler **planlandı**; bu dosya tamamlanma raporu değildir. Kabul eden ve düzeltmeleri yeniden kontrol eden: **Batuhan**. [Ortak takip/geri bildirim kuralları](../ekip-ve-teslim.md).

| ID | Faz | Görev | Bağımlılık | Teslim / kabul koşulu | Durum | Kanıt / FB / son güncelleme |
|---|---|---|---|---|---|---|
| AS-01 | 1 | Mevcut kaynak alanlarını/örneklerini Batuhan’la eşle; beklenen sonuçları incele | Mevcut laboratuvar; BT-02 hazırlığı | Kaynak yeteneği, alan örnekleri ve erişim sınırları | teslim edildi, Batuhan kontrolü bekliyor | [AS-01 raporu](../../faz-1-fikir-ve-arastirma/veri-laboratuvari/AS01-ERISIM-SINIRLARI.md) · 6 FB: [geri-bildirim/](geri-bildirim/) · [alternatif raporu](../../faz-1-fikir-ve-arastirma/veri-laboratuvari/AS01-ALTERNATIF-RAPOR.md) · ölçüm 2026-09-24 |
| AS-02 | 1 | Batuhan’ın başarısız kaynak/sorgu bildirimlerini yeniden üret ve düzelt | BT-03 ilk geri bildirimi; görevin kapanması beklenmez | Aynı sorgunun önce/sonra ham sonucu; çözüm veya kanıtlı engel | planlandı | — |
| AS-03 | 1 | İzinli alternatif yöntem/kaynak dene; kategori/veri kalitesini kontrol et | AS-02 | Alternatifin alan/kapsam farkı, limitleri ve kalan eksikleri; Batuhan kabulü | planlandı | — |
| AS-04 | 2 | Alan çıkarımı, tekrar, ilgililik, karşıt kanıt kaybı ve kaynak raporu hatalarını çöz | BT-06 ilk hata bildirimi; sürümlü etiketli örnekler | Hatalı/korunacak örnekler ve düzeltme sonrası kalite farkı | planlandı | — |
| AS-05 | 3 | Bağımsızlık, 3/2 sayımı, alıntı ve rapor yorumunu veriyle kontrol et | BT-07 | Yanlış sayım/yorum için claim düzeyinde bildirim; kanıtlı düzeltme | planlandı | — |
| AS-06 | Tümü | Çözüm günlüğünü ve kaynak sağlık kayıtlarını güncelle | Her bulgu | Denenmiş yollar ve çalışmadığı sınırlar kayıtlı; Batuhan yeniden kontrolüne hazır | planlandı | — |
## Açık geri bildirimler

[Şablon](geri-bildirim-sablonu.md) kullanılır; görev ID ve kanıt bağlantısı üst tabloya eklenir.

AS-01 ön bildirimleri (2026-09-24 ölçümü, hepsi **açık**, Batuhan kontrolü bekliyor):

| FB-ID | Kaynak | Önem | Etkilenen fikirler | Bugünkü sonuç |
|---|---|---|---|---|
| [AS01-0097](geri-bildirim/AS01-0097.md) | Google Play Store (source-0097) | yuksek | F01, F08, F10 | ok / js-kabugu |
| [AS01-0075](geri-bildirim/AS01-0075.md) | Reddit (source-0075) | yuksek | F01, F02, F04, F06, F07, F08, F09 | robots_disallowed / alinmadi |
| [AS01-0134](geri-bildirim/AS01-0134.md) | G2 (source-0134) | orta | F02, F09 | challenge / alinmadi |
| [AS01-0135](geri-bildirim/AS01-0135.md) | Capterra (source-0135) | orta | F02, F09 | challenge / alinmadi |
| [AS01-0148](geri-bildirim/AS01-0148.md) | Trustpilot (source-0148) | orta | F07 | robots_disallowed / alinmadi |
| [AS01-0466](geri-bildirim/AS01-0466.md) | Capterra Education Software (source-0466) | orta | F10 | challenge / alinmadi |

Bunlar Ayselin'in ön bildirimidir; kapatılmış bulgu değildir. Kanıt artefaktları
ve ölçüm yöntemi AS-01 raporundadır.

## Bağımlılıkların anlamı

Başlatma girdisi ile son kabul ayrı adımlardır. Batuhan önce API/örnek veya hata bildirimini teslim eder; karşı taraf bu girdiye dayanarak çalışır. Batuhan’ın kabul alt adımı karşı tarafın tesliminden sonra yürür. API/hata bildirimi hazır olduğunda Batuhan’ın bütün görevinin kapanması beklenmez.

## Ortam ve teslim sınırı

Kaynak/veri düzeltmeleri Batuhan’a kanıtla teslim edilir. Gerçek ortak entegrasyon testleri Hetzner/API erişimi hazır olduğunda yürütülür; erişim beklenirken kayıtlı örneklerin incelenmesi ve düzeltme hazırlığı ilerleyebilir.
