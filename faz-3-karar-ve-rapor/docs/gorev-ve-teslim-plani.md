# Görev ve teslim planı

**Kapsam kararı — Çağlar:** Build kararı, MVP/PRD önerisi, geliştirilecek ürünün özellikleri ve geliştirme yol haritası mevcut üç fazın hiçbirine dahil değildir. Bunlar projenin sonraki aşamasıdır; yönetici Çağlar tarafından daha sonra değerlendirilip planlanacaktır. Bu aşama kanıtları, araştırma değerlendirmesini ve eksikleri raporlar. Olumlu bulgu otomatik geliştirme kararı üretmez.

| Sıra | İş | Sorumlu | Teslim |
| --- | --- | --- | --- |
| 1 | Karar rubric'i ve etiketli EvidenceBundle örnekleri | Ayselin + Batuhan | Olumlu bulgular ve Modify/Kill/Investigate More, veri yokluğu, çelişki ve primary/secondary örnekleri. |
| 2 | Girdi/citation bütünlüğü ve yeterlilik gate'i | Batuhan | Sürümlü kurallar, uygun outcome listesi, mock test sonucu. |
| 3 | Boyut profilleri ve pazar/uygulama ayrımı | Batuhan + Ayselin | Kaynak referanslı profiller ve hata örnekleri. |
| 4 | Şemalı karar sentezi ve validator | Batuhan | DecisionReport, sınırlı hata/düzeltme akışı. |
| 5 | Gerekçe, karşıt kanıt ve aksiyon kalitesi incelemesi | Ayselin | İnsan rubric'i, kategori kırılımında kalite raporu. |
| 6 | Faz 2 gap talebi ve karar sürümleme | Batuhan | Parent bağları, aynı toplama hattına dönüş, primary boşluğunda durma. |
| 7 | Nihai backend/AI kabulü | Batuhan + Ayselin | Doğrulanmış uçtan uca örnekler, açık hatalar/kararlar. |

Ayşenur doğrulanmış raporu, kanıt yeterliliğini, kaynakları ve eksikleri ekrana bağlar. Batuhan gerçek raporla karşılaştırır, kapsam dışı Build/MVP/uydurma güven yüzdelerini ve yanlış durumları düzelttirir. Sonraki ürün geliştirme planı yine kapsam dışıdır.

## Tamamlanmış sayılma koşulları

- Faz 2'den kaynaklı paket alınıp güncel araştırma değerlendirmesi sözleşmesine uygun rapor üretilebiliyor.
- Build/MVP çıktısı her durumda engelleniyor; kritik kanıt yetersizliğinde kesin Kill engelleniyor; veri yokluğu olumsuz pazar kanıtı sayılmıyor.
- Gerekçe, karşıt kanıt, belirsizlikler ve araştırma eksikleri eksiksiz. Sonraki ürün geliştirme/MVP planı Çağlar’a bırakılmış.
- Pazar fırsatı ve kullanıcı uygulama koşulları ayrı tutuluyor.
- Modify somut değişiklik, Kill pozitif karşıt kanıt, Investigate More doğru primary/secondary ayrımı taşıyor.
- Model JSON'u, claim/citation ve outcome politikası doğrulanmadan rapor tamamlanmış sayılmıyor.
- Girdi/policy/prompt/model sürümleriyle eski rapor korunuyor; yeni veri yeni sürüm üretiyor.
- [Test planındaki](test-plani.md) zorunlu senaryolar sonuçlarıyla teslim edilmiş; insan değerlendirmesi ve açık kalite eşikleri kayıtlı.
- Frontend'e ileride verilebilecek sabit örnek JSON ve hata sözleşmesi hazır.

Bunlar teslim hedefleridir; bu dokümanların hazırlanması backend/AI'ın tamamlandığı anlamına gelmez. API kullanımı ve test yürütme yeri ortak açık kararlardır.

## Kişi takibi ve kabul

[Batuhan](../../ortak/gorevler/batuhan.md), [Ayselin](../../ortak/gorevler/ayselin.md), [Ayşenur](../../ortak/gorevler/aysenur.md). Batuhan her teslimi [kontrol rehberi](kontrol-ve-kabul-rehberi.md) üzerinden inceleyip somut düzeltme geri bildirimi verir, yeniden testten sonra kabul eder. Frontend gereksinimleri [ortak rehberde](../../ortak/frontend-entegrasyon-ve-eksikler.md).
