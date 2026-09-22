# Görev ve teslim planı

## Sorumluluklar

| Sıra | İş | Sorumlu | Bağımlılık / teslim |
| --- | --- | --- | --- |
| 1 | Kaynakların gerçek veri yeteneklerini ve örnek payload'ları etiketle | Ayselin (veri kalitesi) | Faz 1 laboratuvarı; kaynak/alan matrisi, ham kayıt referansları. |
| 2 | Kaynak profili, budget ve ResearchPlan adapter sözleşmesini netleştir | Batuhan + Ayselin | Faz 1 veri sözleşmesi; sürümlü profil ve fixture. |
| 3 | Scriptleri ürün işine bağla; durum/limit/retry/iptal kaydı ekle | Batuhan | Doğrulanmış plan; mock adapter entegrasyonu. |
| 4 | Ham depolama, normalizasyon, dedup ve citation bağlarını kur | Batuhan | Ayselin beklenen alanlar/ilişkiler; sürümlü tekrar işleme. |
| 5 | Filtreleme ve kanıt seçimini ölç/kalibre et | Ayselin; uygulama Batuhan | Relevant/irrelevant/karşıt etiketler; kalite raporu. |
| 6 | Claim çıkarımı, SourceReport ve EvidenceBundle doğrulamasını kur | Batuhan + Ayselin | Şema ve kaynaklı fixture; LLM doğruluğu ayrı değerlendirilir. |
| 7 | Gap döngüsü ve Faz 3 teslimini bağla | Batuhan | Bütçe/durma ve primary/secondary ayrımı. |
| 8 | Faz kapanışını veri kalitesi açısından değerlendir | Ayselin + Batuhan | Test raporu, hata listesi, karşılanan/açık kabul kriterleri. |

Ayşenur kaynak durumu, kanıt, rakip ve problem ekranlarını backend hazır oldukça bağlar. Batuhan gerçek veriyi ve hata/kısmi sonuç durumlarını kontrol eder. Veri sorunu Ayselin’e, görüntüleme sorunu Ayşenur’a somut geri bildirimle döner; API hatasını Batuhan giderir.

## Tamamlanmış sayılma koşulları

- Doğrulanmış bir Faz 1 planı, seçilen gerçek kaynak profilleri üzerinden izlenebilir işe dönüşür.
- Hangi kaynaktan ne kadar/hangi alan çekileceği kod içine dağılmış sabitler yerine profil ve bütçeyle belirlenir.
- Ham veri bozulmaz; normalize metin, kopya ilişkisi ve claim'den kaynağa geri gidilir.
- Erişilememe ile sıfır sonuç ayrılır; kısmi hata nihai bulguları gizlemez.
- Filtreler etiketli örneklerle ölçülür; önemli/karşıt kanıt kaybı gözden geçirilir.
- Her site raporu ve EvidenceBundle JSON doğrulamasından geçer; desteklenmeyen alıntılar elenir.
- Ek araştırma aynı hattı kullanır ve sonlu durur; birincil doğrulama talebi web'e dönmez.
- [Test planının](test-plani.md) zorunlu senaryoları gerçek sonuçlarıyla raporlanır; açık hata ve sayısal kalite eşikleri görünürdür.
- Faz 3 kabul ettiği sürümlü payload örneğiyle teslim alır.

Bu koşullar **hedef**, mevcut tamamlanma beyanı değildir. Mevcut veri/script varlığı yeni backend akışının tamamlandığı anlamına gelmez.

## Kişi takibi ve kabul

[Batuhan](../../ortak/gorevler/batuhan.md), [Ayselin](../../ortak/gorevler/ayselin.md), [Ayşenur](../../ortak/gorevler/aysenur.md). Batuhan her teslimi [kontrol rehberi](kontrol-ve-kabul-rehberi.md) üzerinden inceleyip somut düzeltme geri bildirimi verir, yeniden testten sonra kabul eder. Frontend gereksinimleri [ortak rehberde](../../ortak/frontend-entegrasyon-ve-eksikler.md).
