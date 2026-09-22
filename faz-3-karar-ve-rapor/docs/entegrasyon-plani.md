# Entegrasyon planı

## Akış

1. **Snapshot al:** fikir, plan, EvidenceBundle, kullanıcı koşulları ve karar politikası sürümlerini sabitle. Başka run/proje claim'leri reddedilir.
2. **Yeterlilik kontrolü:** kapsam ve citation bütünlüğünü doğrula; izin verilen sonuçları belirle. Kritik boşlukta varsayılan Investigate More.
3. **Boyutları değerlendir:** problem, müşteri, rakip/farklılaşma, fırsat ve uygulama koşullarını ayrı profillere dönüştür. Pazar fırsatı ile kişinin bütçesini tek puanda karıştırma.
4. **Karar adayını sınırla:** sürümlü politika Modify/Kill/Investigate More uygunluğunu ve olumlu bulguların yönetici değerlendirmesine bırakılmasını belirlesin. LLM bu sınırı aşamasın.
5. **Kaynaklı AI sentezi:** model yalnız doğrulanmış claim/citation, profiller, sınırlar ve uygun outcome listesini alır; gerekçe, karşıt kanıt, bilinmeyenler ve sonraki adımları JSON olarak üretir.
6. **Backend doğrulaması:** şema, ID/alıntı bağları, uygun outcome, eksik zorunlu alan, desteklenmeyen iddia ve yasak yüzde/uydurma ölçüm kontrol edilir. Şema doğruluğuna ek semantik değerlendirme gerekir; bu nedenle Ayselin'in insan incelemesi test planının parçasıdır.
7. **Kaydet ve sunuma hazırla:** yalnız doğrulanmış DecisionReport sürümü yayıma hazır olur. Geçersiz model cevabı başarı diye dönmez; sınırlı düzeltme denemesi sonrası açık hata döner.

## Sonuç sonrası

| Outcome | Sonraki adım |
| --- | --- |
| Olumlu bulgular | Kanıt ve belirsizlikler Çağlar’a sunulur; geliştirme/MVP kararı veya planı üretilmez. |
| Modify | Korunacak sinyal, değişecek varsayım ve önerilen segment/kapsam sunulur; kullanıcı kabul ederse ilgili Faz 1 planı revize edilir. |
| Kill | Mevcut tezle ilerlememe gerekçesi ve kararı değiştirebilecek kanıt gösterilir. |
| Investigate More | En değerli eksik bilgi ve elde etme yolu verilir. İkincil boşluk Faz 2'ye kontrol edilerek döner; birincil boşluk Çağlar’ın sonraki değerlendirmesine bırakılan bir kanıt eksikliğidir. |

Fikri kullanıcı adına otomatik değiştirme yapılmaz. Ek web turu, kalan bütçe ve kaynak sınırları içinde [Faz 2 hattını](../../faz-2-veri-toplama-ve-hazirlama/docs/entegrasyon-plani.md) kullanır. Yalnız hipotez/kanıt gereksinimi değiştiyse ilgili plan sürümü güncellenir; her sonuç tüm araştırmayı sıfırdan başlatmaz.

## Karar hassasiyeti ve sonraki bilgi

İlk yaklaşım açıklanabilir karşı-olgusal kontroldür: hangi kritik claim geçersizleşirse, hangi gate düşerse veya hangi varsayım değişirse karar değişir? `stable`, `sensitive`, `fragile` ancak uygulanmış analiz dayanağıyla verilir; analiz yapılmadıysa `not_evaluated` döner. Modelin kendine güveni bu alanı doldurmaz.

Sonraki adımlar mevcut araştırmanın eksik sorusu, gereken kanıt ve yeniden değerlendirme koşuluyla sınırlıdır. İkincil araştırma mevcut Faz 2 hattına dönebilir. Birincil doğrulama gereksinimi raporlanır; görüşme, landing, concierge, ön sipariş, MVP veya pilot tasarımı bu aşamada üretilmez. Bu sonraki süreci yönetici Çağlar değerlendirip planlar.

## Yeniden üretim ve hata

Aynı snapshot ile doğrulama/politika adımları tekrarlanabilir olmalı. LLM kelimelerinin birebir aynı çıkması garanti edilmez; outcome uygunluğu, kaynak bağları ve zorunlu içerikler kararlı olmalıdır. Yeni veri veya kullanıcı koşulu yeni DecisionReport oluşturur; eski rapor ve citation sürümleri değişmez.

Model süresi/hatası, şema hatası, kayıp/stale citation, politika dışı outcome, kanıt çelişkisi ve yetersiz kanıt farklı işlenir. Yetersiz kanıt geçerli Investigate More sonucudur; JSON parse hatası değildir. Ayşenur doğrulanmış rapor ve hata sözleşmesi geldikçe ekranları bağlar; Batuhan kabul eder.
