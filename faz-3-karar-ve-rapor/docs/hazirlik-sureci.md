# Hazırlık süreci

**Kapsam kararı — Çağlar:** Build kararı, MVP/PRD önerisi, geliştirilecek ürünün özellikleri ve geliştirme yol haritası mevcut üç fazın hiçbirine dahil değildir. Bunlar projenin sonraki aşamasıdır; yönetici Çağlar tarafından daha sonra değerlendirilip planlanacaktır. Bu aşama kanıtları, araştırma değerlendirmesini ve eksikleri raporlar. Olumlu bulgu otomatik geliştirme kararı üretmez.

## Gerekli girdiler

- Kullanıcının onayladığı fikir özeti ve Faz 1 ResearchPlan sürümü.
- Faz 2'den doğrulanmış EvidenceBundle: site raporları, claim/citation, bağımsızlık ilişkileri, araştırma kapsamı, sınırlar ve maliyet.
- Biliniyorsa kullanıcı bütçesi, teknik kapasitesi, zamanı ve platform tercihi. Bilinmeyen koşullar tahmin edilmez; kararı sınırlayan varsayım olur.
- Sürümlü karar kuralları ve kanıt yeterlilik kontrolü.
- Ayselin tarafından incelenmiş karar fixture'ları ve destekleyen/çürüten kanıt etiketleri.

## AI öncesi kanıt yeterliliği

Backend kritik araştırma niyetlerinin kapsanmasını, bağımsız kaynak sayısını/ailelerini, tarih/dil/pazar uyumunu, karşıt kanıt aramasını, kopya yoğunluğunu, erişim engellerini ve pazar olgunluğu bağlamını kontrol eder. Çok belge tek başına yeterlilik değildir.

Yetersizlik `Investigate More` üretir; erişilememe veya hiç sonuç bulamama `Kill` sayılmaz. Yeni/emerging/unknown pazarda az web kanıtı, müşteriyle birincil doğrulama ihtiyacı olabilir. Kullanıcı tarafından başlangıç eşiği 3 bağımsız kullanıcı/kurum örneği ve 2 farklı kaynak olarak onaylandı. [Policy v1](../../ortak/kanit-yeterliligi-ve-karar-kurallari.md) nitel kontroller ve sayım kurallarıyla birlikte uygulanır; salt sayıya göre yeterlilik verilmez.

## Değerlendirilecek alanlar

| Alan | İçerik |
| --- | --- |
| Problem/müşteri | Tekrarlanan problem, doğrudan kullanıcı bağlamı, mevcut workaround. |
| Rakip/farklılaşma | Resmî ürün iddiaları ve bağımsız kullanıcı deneyimi ayrı; kaynaklı fırsat hipotezleri. |
| Fiyat/ödeme | Tarihli fiyat gözlemi, beyan edilen ödeme isteği ve gözlenmiş ödeme davranışı ayrı. |
| Pazar kanıtı | Kapsam, bağımsızlık, karşıt kanıt ve olgunluk. |
| Uygulama koşulu | Kullanıcının bütçe/zaman/kapasite sınırları; pazar fırsatından ayrı. |

Her boyut `strong`, `mixed`, `weak` veya `insufficient` profili; destekleyen/karşıt claim'ler ve bilinmeyenler taşır. Birleşik fikir başarı yüzdesi üretmez.

## Araştırma sonuçlarının anlamı

- **Olumlu bulgular:** dayanaklar ve bilinmeyenler raporlanır; Build veya MVP önerilmez. Etiket “Olumlu bulgular — yönetici değerlendirmesi bekliyor”; sonraki ürün aşamasını Çağlar değerlendirir.
- **Modify:** desteklenen problem korunur; hedef segment, konumlandırma veya çözüm/kapsam varsayımı değişmeli. Önerilen değişiklik ve yeniden değerlendirme kanıtı somut olmalı.
- **Kill:** yeterli ve bağımsız karşıt kanıt mevcut teze şimdi ilerlememeyi destekler. Sessizlik veya şikâyet bulunmaması memnuniyet kanıtı değildir.
- **Investigate More:** kritik belirsizlik çözülmeden yön seçilemez. Web'de kapatılabilecek boşlukla müşteri görüşmesi/pilot gerektiren boşluk ayrılır.

## Hazırlık teslimi

Karar rubric'i, yeterlilik kuralları, outcome uygunluk tablosu, örnek geçerli/geçersiz DecisionReport ve [test planındaki](test-plani.md) etiketli değerlendirme seti. Build ve MVP önerisi kanıt yeterli olsa da kapsam dışıdır; model çıktısında kabul edilmez.
