# Hazırlık süreci

## Amaç ve başlangıç koşulları

Faz 1'in doğrulanmış fikri, kategorileri, araştırma niyetleri ve sorgularını gerçek kaynağa bağlayıp kaynaklı bulgular üretmek. İlk teslimde, erişimi ve veri kalitesi doğrulanmış sınırlı kaynak paketiyle uçtan uca bir akış hazırlanır; katalogdaki tüm sitelerin desteklendiği varsayılmaz.

Başlamadan önce hazırlanacaklar:

1. [ResearchPlan sözleşmesi](../../faz-1-fikir-ve-arastirma/docs/veri-sozlesmeleri.md) ve ortak sürüm alanları.
2. Mevcut [laboratuvar](../../faz-1-fikir-ve-arastirma/veri-laboratuvari/) için script → desteklenen erişim yöntemi → gerçekten çıkan alanlar matrisi. Tarihli erişim kayıtları bugünkü kapasite garantisi değildir.
3. Kaynak profilleri: kategori/araştırma niyeti uyumu, arama/fetch yeteneği, alınacak alanlar, veri türü, dil/pazar, erişim koşulları ve izinli alternatifler.
4. Etiketli örnekler: doğru/bozuk HTML, API kaydı, yorum, fiyat sayfası, sitemap, arşiv ve tekrar içerikleri. Mevcut ham veriye referans verilir, kopyalanıp yeni doğruluk kaynağı yaratılmaz.
5. Ayselin tarafından hazırlanacak beklenen ayrıştırma, alıntı, ilgililik ve bağımsızlık etiketleri.
6. Her kaynak, sorgu ve çalışmanın sonlu bütçesi; maliyet ve durdurma kayıtları.

## Hangi kaynakta ne aranır?

| Kaynak ailesi | Alınabilecek veri | Kanıt sınırı |
| --- | --- | --- |
| Web araması | Aday URL, başlık, snippet | Keşif sonucudur; asıl içerik ayrıca alınmadan tam kanıt sayılmaz. |
| Rakibin resmî sitesi | Özellik, fiyat, entegrasyon, doküman, changelog, hedef müşteri | Şirketin iddiasıdır; müşteri memnuniyeti sayılmaz. |
| GitHub/Hacker News/Stack Exchange gibi teknik kaynaklar | Issue/soru, yorum, sürüm, tarih, bağlamlı etkileşim | Yıldız/oy sayısı ödeme veya pazar büyüklüğü değildir. |
| Uygulama mağazaları/eklenti dizinleri/review kaynakları | Ürün metadata'sı; ayrıca erişim uygunsa yorum ve puan | Metadata erişimi yorum erişimiyle aynı yetenek değildir. |
| Açık topluluklar ve medya | Problem, workaround, övgü, şikâyet, bağlam | Repost, tanıtım ve bağımsız kullanıcı deneyimi ayrılır. |
| Dikey kaynaklar | Kamu/akademik/regülasyon, jobs/funding/maps/ads/SEO | Sadece kategori ve amaç uygunsa; erişim ve lisans ayrıca değerlendirilir. |
| Domain ve web izi | RDAP/DNS, sertifika geçmişi, HTTP erişimi | Marka hukuku veya domain satın alınabilirliği garantisi değildir. |
| Common Crawl/arşiv | Tarihli yakalama ve asıl URL | Güncel sayfa veya güncel fiyat gibi sunulmaz. |

Reddit, X, LinkedIn, kapalı topluluklar ve lisanslı review verileri koşulsuz erişilebilir kabul edilmez. Kaynak profili etkin erişim yöntemini açıkça belirtmeden iş üretilmez. Yeni sağlayıcı seçimi bu belgeyle kesinleştirilmez.

## Ne kadar veri?

Her profil araştırma derinliğine göre `max_items`, `max_pages`, `max_requests`, `max_response_bytes`, `max_total_bytes`, `timeout_seconds`, `max_llm_tokens` ve varsa maliyet tavanı taşır. Tarih aralığı, dil ve pazar ayrıca sınırlandırılır. Hızlı araştırmada 30, detaylı araştırmada 150 kayıt **yalnız konuşulmuş örnektir; onaylı sabit varsayılan değildir.** Ayselin ölçümleriyle kaynak bazında ayarlanır.

Durdurma nedenleri: hedef kapsama ulaşıldı, yeni bağımsız bilgi gelmiyor, sonuç/sayfa tükendi, bütçe veya süre tükendi, izinli kaynak kalmadı, iptal ya da hata. Kayıt sınırına ulaşmak araştırmanın yeterli olduğu anlamına gelmez.

## Hazırlık teslimi

Kaynak profili taslakları, çalıştırılabilir script envanteri, örnek ham veri referansları, kalite etiketleri ve küçük ilk kaynak paketinin gerekçesi hazır olmalı. Ham içerik erişimi ile ürün seviyesinde doğru arama başarısı ayrı raporlanmalı.
