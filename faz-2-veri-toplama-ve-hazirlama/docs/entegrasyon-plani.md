# Entegrasyon planı

## Uygulama sırası

1. **Plan doğrulama:** şema/sürüm, proje sahipliği, etkin kaynak ve connector, sorgu niyeti, pazar/dil, sonlu bütçe kontrol edilir. Geçersiz plan dış çağrı başlatmaz.
2. **İş üretimi:** her `(research_id, plan_version, source_id, query_id)` için kimliği belirli iş açılır. Aynı istek tekrarlandığında mükerrer toplama ve maliyet oluşmaması sağlanır.
3. **Mevcut script adaptörü:** [Faz 1 laboratuvarındaki](../../faz-1-fikir-ve-arastirma/veri-laboratuvari/) Python araçları parametreli, yapılandırılmış sonuç veren adapter arkasına alınır. Script çıktısı ürün sözleşmesine dönüştürülür. Dosya taşınmış olması backend entegrasyonu tamamlandı demek değildir.
4. **Toplama:** API/HTTP/RSS/sitemap/arşiv kaynağın yeteneğine göre seçilir. Arama, aday keşfi ve içerik alma farklı iş türleridir. Redirect, response boyutu, süre, kaynak kotası ve toplam bütçe merkezi kontrol edilir.
5. **Ham kayıt:** içerik referansı, hash, kaynak URL'si, tarih, sorgu/plan/connector sürümüyle değişmez artefact kaydedilir. Kaynak hatası ayrı iş sonucudur.
6. **Normalizasyon:** encoding/Unicode, görünür metin, URL, tarih, dil, yorum-parent ilişkisi ve kalite bayrakları çıkarılır. Orijinal metin korunur. Yayın tarihi bilinmiyorsa `null` kalır; toplama tarihi onun yerine yazılmaz.
7. **Tekrar ve varlık ilişkileri:** dış ID/hash ile kesin tekrarlar gruplanır. Yakın kopya adayları silinmez. Aynı sorunu anlatan farklı kullanıcılar tek kopyaya indirgenmez. Aynı isimli iki ürün doğrulanmış dış kimlik olmadan birleştirilmez.
8. **İlgililik ve kanıt seçimi:** ucuz metin/alan filtreleri önce çalışır. Araştırma niyeti, kaynak ailesi, dil, tarih, bağımsızlık ve karşıt bulguyu koruyan sınırlı segment seçimi yapılır. Eleme nedenleri saklanır.
9. **Kaynaklı çıkarım:** seçili segmentlerden şemalı claim ve site raporu üretilir. Alıntının birebir metni, segment hash'i ve sürümü doğrulanmadan claim kabul edilmez. `no_claim`/`uncertain` geçerlidir.
10. **Birleştirme:** site raporları, kaynaklar arası kopya/alıntı bağımlılıkları, problem/rakip/fiyat haritaları ve kapsam profili tek `EvidenceBundle` içine alınır. Faz 3 yalnız doğrulanmış sürümü tüketir.

## Kaynak raporu ve toplu paket

Her site raporu veri alım sonucu, taranan kapsam, bulgular, karşıt bulgular, alıntılar, eksikler ve maliyeti taşır. Aynı basın bülteninin beş sitedeki kopyası, site sayısı 5 olsa da bağımsız kanıt sayısını 5 yapmaz. Global bağımsızlık hesabı site raporlarının ardından tekrar yapılır.

Metin hacmi model sınırını aşarsa kaynak/niyet bazında küçük partiler ve kaynaklı ara çıktılar kullanılır. Sadece serbest özetleri üst üste özetleyerek kanıt zinciri kaybedilmez. Son karar modeli gerektiğinde claim'in orijinal alıntı bağını görebilir.

## Ek araştırma döngüsü

Faz 2 kapsam kontrolü veya Faz 3 `ResearchGapRequest` üretir. Backend boşluğun web araştırmasıyla kapatılabilirliğini, kalan bütçeyi, kaynak erişimini ve tekrarları kontrol eder. İzinli ek sorgular **aynı** toplama/normalizasyon hattına `gap_driven` olarak girer; ayrı crawler kurulmaz.

Her turda önceki paket, talep kimliği, önce/sonra kapsam, yeni bağımsız kanıt, kullanılan bütçe ve durma nedeni saklanır. Sonlu tur limiti vardır; yeni bilgi yoksa durur. Bütçe/erişim kapsamı sessizce artırılmaz. Gerçek müşteri ödeme davranışı gibi `primary_validation_gap` web döngüsüne gönderilmez.

## Hata ve yeniden başlatma

- `no_results`, `source_unavailable`, `rate_limited`, `blocked_by_policy`, `parse_failed`, `partial` ayrılır.
- Yalnız geçici hatalar sınırlı ve gecikmeli yeniden denenir; kalıcı izin engeli tekrar döngüsü yaratmaz.
- Kısmi sonuç kullanılabilir; eksik kapsam rapora taşınır. Bütün kaynakların başarılı olması şart koşulmaz.
- Yeniden normalizasyon yeni sürüm üretir; eski claim/citation/karar sessizce değiştirilmez. Eşleşmeyen alıntı `stale_binding` olur.
- İptal yeni işler üretimini durdurur; eldeki artefact ve son durum kaybolmaz.

Ortak kimlik, veri ayrımı, maliyet ve yürütme ilkeleri [ortak mimaride](../../ortak/mimari-ve-kararlar.md); kesin payload kuralları [veri sözleşmelerinde](veri-sozlesmeleri.md).
