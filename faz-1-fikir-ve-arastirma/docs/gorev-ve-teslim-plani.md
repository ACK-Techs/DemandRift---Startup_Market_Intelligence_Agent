# Görev ve teslim planı

Batuhan proje yürütücüsü ve backend sahibidir; kategori/sorgu akışını ve ilk kaynak testlerini yapar. Veri/erişim eksiklerini Ayselin’e iletir, çözümü yeniden kontrol eder. Ayşenur hazır API'lere ekranları bağlar ve tasarım eksiklerini giderir. Aşağıdaki işler planlanmıştır, tamamlandı işareti değildir.

| İş | Sorumlu | Bağımlılık | Somut teslim ve bitiş koşulu |
|---|---|---|---|
| F1-01 Kategori ve kapsam | Batuhan + Ayselin | Onaylanan 10 fikir | Yedi kategori tanımı, katmanlar, bilinmeyen/çakışma kuralları; her fikir için gerekçeli beklenen sınıf |
| F1-02 Kanıt matrisi | Ayselin | F1-01 | Kategori/soru/alan/kanıt tablosu; yanlış proxy ve birincil doğrulama boşlukları işaretli |
| F1-03 Mevcut kaynak ve veri incelemesi | Batuhan ilk deneme; Ayselin sorun çözümü | Laboratuvar varlıkları, F1-02 | Alan bazlı etiketli örnekler, erişim/kalite ayrımı, bozuk/eksik veriler ve registry düzeltme listesi |
| F1-04 Kaynak eşleme ve sorgu kuralları | Batuhan + Ayselin | F1-02, F1-03 | Kaynak profilleri, uygunluk matrisi, niyet ve locale bağlı şablonlar, izinli fallback'ler |
| F1-05 30 senaryonun değerlendirme rubriği | Batuhan + Ayselin | F1-01, F1-02 | Net/eksik/yanlış etiketli girdiler için beklenen kategori, sorular, sorgu kapsamı ve ret koşulları |
| F1-06 Sözleşme ve doğrulayıcı | Batuhan; Ayselin alan incelemesi | F1-01, F1-04 | Brief/ResearchPlan şemaları, semantik doğrulama, durumlar, kimlik ve sürüm kayıtları |
| F1-07 LLM ve netleştirme akışı | Batuhan; Ayselin veri değerlendirmesi | F1-05, F1-06 | Şemalı üretim, kısa sorular/atlama, prompt/model sürümü, hata ve sınırlı tekrar |
| F1-08 Kaynak/sorgu derleme | Batuhan; Ayselin kalite kontrolü | F1-04, F1-06, F1-07 | Etkin registry'den izinli plan, bütçe/dedupe/locale/hipotez kontrolleri |
| F1-09 Offline kabul değerlendirmesi | Batuhan + Ayselin; Batuhan düzeltmeleri | F1-03, F1-05–08 | Senaryo bazlı sonuçlar, ham model çıktısı referansları, ölçümler ve açık hata listesi |
| F1-10 Faz 2 devri | Batuhan + Ayselin | F1-09 | Sürümlü örnek ResearchPlan, laboratuvar adaptör gereksinimleri ve giderilmemiş kapsama boşlukları |

## Teslim paketi

Taksonomi, EvidenceNeedMatrix, SourceCapabilityProfile, SourceFitMatrix, QueryPlaybook ve derinlik/fallback tablosu geliştiricinin makinece okuyabileceği sürümlü dosya veya kayıt olarak teslim edilir. Dokümanda anlatılmış olması implementasyon teslimi değildir. Ayselin kılavuzunda adı geçen ama mevcut olmayan çıktılar F1-01–04 görevlerinde doğrulanır; bulunamayanlar yeniden üretilir veya gerekli değilse gerekçesi kaydedilir.

## Faz tamamlandı sayılmadan

30 planlı senaryonun sonuç raporu, [test planındaki](test-plani.md) semantik kontroller, kaynak veri kalitesi örnekleri ve geçerli/bozuk planların Faz 2 kabul-ret örnekleri bulunmalıdır. Sayısal eşikler pilotla kesinleştirilecek; bu doküman mevcut başarı iddiası içermez. Eksik veri, kaynak erişim engeli ve model hatası ayrı sahip ve sonraki işle birlikte teslim edilir.

API anahtarını Çağlar Batuhan’a verecek. Yerel kayıtlı-veri testleri ve ortak entegrasyon ortamı onaylandı; Hetzner kurulumu/uzaktan build ve Vercel/API bağlantısının ayrıntıları [ortak mimari kaydına](../../ortak/mimari-ve-kararlar.md) göre netleştirilecek.

## Kişi takibi ve kabul

[Batuhan](../../ortak/gorevler/batuhan.md), [Ayselin](../../ortak/gorevler/ayselin.md), [Ayşenur](../../ortak/gorevler/aysenur.md). Batuhan her teslimi [kontrol rehberi](kontrol-ve-kabul-rehberi.md) üzerinden inceleyip somut düzeltme geri bildirimi verir, yeniden testten sonra kabul eder. Frontend gereksinimleri [ortak rehberde](../../ortak/frontend-entegrasyon-ve-eksikler.md).
