# Kanıt yeterliliği ve araştırma kararı — başlangıç politikası v1

**Kullanıcı tarafından onaylandı:** en az **3 bağımsız kullanıcı/kurum örneği**, en az **2 farklı kaynak**. Bu minimum araştırma eşiğidir; istatistiksel temsil, pazar büyüklüğü veya başarı garantisi değildir. Batuhan uygular, Ayselin örneklerin doğruluğunu ve bağımsızlığını inceler. Eşiği değiştirme gereği ölçüm ve örneklerle Çağlar’a iletilir; başarısız örneği geçirmek için sessizce düşürülmez.

## Sayım ve zorunlu kontroller

| Kontrol | Geçme koşulu |
|---|---|
| Hedef müşteri/problem | İncelenen kullanıcı, problem ve fikir varsayımı açık; AI'ın eklediği varsayım kullanıcı beyanı sayılmıyor. |
| Bağımsız örnek | Aynı somut problem/temel varsayımla ilgili en az 3 farklı kullanıcı veya kurum gözlemi; her örnek kaynaklı ve içerik bakımından ilgili. |
| Kaynak çeşitliliği | Bu örnekler en az 2 ayrı kaynak/platformda; aynı kaynağın sayfaları ayrı kaynak sayılmaz. Aynı sahipli/kopya yayınlar çeşitlilik geçişini sağlamaz. |
| Bağımsızlık doğruluğu | Aynı kişi farklı platformlarda bir örnek, aynı kurumun pazarlama kopyaları bir köken. Kimliği/bağımsızlığı belirsiz örnek alt eşiğe eklenmez; bilinen/unknown ayrı raporlanır. |
| Mevcut çözümler | Alternatifler ve bunların probleme yaklaşımı araştırılmış; eksik alanlar ve erişim sınırları açık. Rakibin varlığı tek başına olumlu/olumsuz karar değil. |
| Karşıt kanıt araması | Destek araması yanında gerçek karşıt sorgu/inceleme yürütülmüş; sorgu, kaynak ve sonuç kaydı var. Karşıt bulgu mutlaka bulunmak zorunda değil; arandı diye bulunmuş sayılmaz. |
| Pazar/dil/tarih | Kanıt hedef pazara ve müşteri bağlamına uygun; yayın/çekim/arşiv tarihleri ayrı. Her kaynak için güncellik gerekçesi; evrensel gün sayısı henüz seçilmedi. |
| Alıntı ve kaynak | Olgu kaynakta doğrulanabiliyor; URL, artefakt, metin/offset/hash/sürüm bağı geçerli. Yanlış/boş alıntı sayımdan çıkarılır. |

Üç destekleyici örnek olumlu problem değerlendirmesinin tabanıdır. Buna karşı mevcut tezi çürüten veri değerlendirilirken aynı 3/2 bağımsızlık tabanı, **doğrudan ilgili karşıt örnekler** üzerinden uygulanır; önce destek bulmak şart değildir. İlgisiz olumlu/olumsuz örnekleri birleştirip sayıyı doldurmak yeterli değildir. Destekleyen, karşıt ve belirsiz örnek sayıları ayrı raporlanır. Aynı kanıt iki tarafta bağımsızmış gibi iki kez sayılamaz.

Bir kontrol geçmezse ilgili boyut insufficient olur. Kritik boyut eksik/çelişkiliyse genel sonuç Investigate More; erişim engeli, bütçe bitmesi veya no_results ile Kill üretilmez. Sayıların dolması kritik çelişkiyi ya da yanlış pazarı gidermez.

## Sonuç kuralları

- **Olumlu bulgular:** problem/farklılaşma dayanaklarını ve bilinmeyenleri sun. Build, MVP veya ürün pilotu önerme. Etiket “Olumlu bulgular — yönetici değerlendirmesi bekliyor”; `positive_findings` outcome + yönetici incelemesi zorunludur.
- **Modify:** desteklenen problem mevcut, ancak segment/çözüm/konumlandırma varsayımı kanıtla uyuşmuyor. Korunacak sinyali ve sorgulanacak varsayımı açıkla; ürün özellik listesi ya da geliştirme planı üretme. Kritik belirsizliği kesin değişiklik tavsiyesiyle gizleme.
- **Kill:** yeterli araştırma ve 3/2 tabanını sağlayan bağımsız doğrudan karşıt örnekler mevcut fikrin temel varsayımını güçlü biçimde çürütüyor. Rakip sayısı, sessizlik, az veri veya kişisel bütçe tek başına gerekçe olamaz. Hangi yeni kanıtın değerlendirmeyi değiştireceğini yaz; yönetici adına projeyi kapatma.
- **Investigate More:** eksik/çelişkili/güncelliği belirsiz veya erişilemeyen kanıt. Eksik soru ve gereken kanıtı belirt. İkincil boşluk backend'in mevcut hattına kontrollü dönebilir. Birincil doğrulama eksikliği raporlanır; sonraki çalışma planını Çağlar yapar.

Fiyat ve “öderdim” yorumları gerçek ödeme değildir. Gerçek ödeme bilinmiyorsa unknown kalır; AI bunu web verisinden kesinleştiremez.

## Policy çıktısı ve sınır testleri

`policy_version`, `relevant_independent_examples`, `supporting_examples`, `challenging_examples`, `unknown_independence_examples`, `distinct_sources`, `gate_results`, `critical_gaps`, `eligibility_reason` kaydedilir. Başlangıç alt sınırları `min_independent_examples = 3`, `min_distinct_sources = 2`. Model bu değerleri veya kanıt bağlarını değiştiremez.

Kontrol seti: 2/2 yetersiz; 3/1 yetersiz; 3/2 + nitel kontroller olumlu değerlendirmeye uygun; 3/2 ama yanlış pazar yetersiz; üç kopya tek örnek; belirsiz kimlikle alt sınır doldurulamaz; doğrudan karşıt 3/2 mevcut tez için Kill'e uygun olabilir; karşıt arama yapılmamışsa yeterlilik geçmez; eşik dolu olsa da Build/MVP çıktılamaz. Bunlar planlı testlerdir, sonuç değildir.
