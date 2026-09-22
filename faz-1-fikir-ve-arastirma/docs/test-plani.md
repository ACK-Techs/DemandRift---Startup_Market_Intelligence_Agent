# Test planı ve tüm test gereksinimleri

Bu bir **planlanan kabul paketi**dir. Buradaki yeni senaryolar çalıştırılmadı; çalışan ürün backend'i veya ölçülmüş model başarısı iddiası yoktur. Yerel kayıtlı veri ve ortak entegrasyon düzeni onaylandı; Hetzner ve Vercel/API bağlantı ayrıntıları sonraki kurulumda tamamlanacak.

## 1. Fikir, kategori ve sorgu testleri

[fikir-senaryolari.json](../tests/fikir-senaryolari.json) onaylanan 10 fikrin **net**, **eksik** ve **yanlış kategori etiketli** anlatımlarını içerir: toplam 30 girdi. Yedi ana kategori, mobil oyun kesişimi, yerel işletme SaaS'ı ve AI özellikli eğitim ürünü özellikle kapsanır.

Her girdi için müşteri/problem çıkarımı, ana/ek kategori, açıklama ihtiyacı, hedef pazar, soru ve sorgu kapsamı değerlendirilir. Aynı kelimeleri üretme şartı yoktur: örnek sorgular anlam düzeyinde referanstır. Eksik girdiye net senaryonun gizli bilgisi verilmez; beklenen kategori yalnız gözlenen metin yeterliyse zorunlu tutulur. Yanlış kullanıcı etiketi ürünün esas işini değiştirmez; esas iş de belirsizse model bunu gerekçelendirerek soru sorar.

### Önerilen ilk kabul eşikleri

Bu eşikler ekip için başlangıç önerisidir; henüz ölçülmüş sonuç veya kullanıcıca kesinleştirilmiş limit değildir.

| Ölçüm | Başlangıç kabul hedefi |
|---|---|
| Şema, kimlik ve sürüm kuralları | Kabul edilen planların %100'ü geçerli; geçersiz örneklerin hiçbiri Faz 2'ye geçmez |
| Ana kategori doğruluğu | Net 10 + yanlış etiketli 10 girdi üzerinde en az 18/20; sonuç kategori bazında da raporlanır |
| Kritik kategori kesişimleri | Mobil oyun, berber SaaS ve AI özellikli eğitim ürünü senaryolarının tamamı doğru gerekçe/katman ayrımı gösterir |
| Eksik bilgi | 10 eksik girdinin tamamı gerekli boşlukları belirtir; kullanıcı söylememiş bilgiyi kesin gerçek yapmaz |
| Kaynak/sorgu sözleşmesi | Kabul edilen sorguların %100'ünde kaynak, niyet, locale ve izinli yüzey bağı mevcut |
| Sorgu anlam kalitesi | İki değerlendiricinin 0–2 puanladığı müşteri/problem/niyet/dil/kaynak uygunluğu ölçütlerinde ortalama en az 1,6; hiçbir fikirde konu dışı kritik sorgu kabul edilmez |
| Kapsama | Fikir için uygulanabilir her zorunlu niyet sorguyla veya açık erişim/kanıt boşluğuyla açıklanır |
| Köken ve hipotez | Onaysız yeni niş/segmentin sessizce kesin kapsama girmesi 0 |

Birbirinden bağımsız Batuhan/Ayselin puanları ve anlaşmazlık gerekçeleri saklanır. İlk pilot sonrası aynı model/promptla en az üç tekrar önerilir; kategorizasyon ve anlam dalgalanması raporlanır. Metnin birebir aynı kalması beklenmez. Her çalışmanın model/prompt/taksonomi/registry sürümü, süre, token ve hata kaydı bulunur.

## 2. Backend ve sözleşme senaryoları

- Boş/çok uzun/yalnız kategori adı içeren fikir; desteklenmeyen kategori; çelişkili müşteri ve ürün tanımı.
- Eksik/ekstra JSON alanı, yanlış tür, bilinmeyen kategori ID'si, uydurma kaynak ID'si, bozuk sürüm.
- Kullanıcının soruyu atlaması, bilgi eklemesi, fikri değiştirmesi; orijinal metin ve alan kökenlerinin korunması.
- Sağlayıcı zaman aşımı, rate limit ve şema hatası; sınırlı tekrar, metnin kaybolmaması, yinelenen iş oluşmaması.
- Kaynak yüzeyi olmayan API, yerel aramaya uzak URL üretme, desteklenmeyen locale parametresi, engelli kaynağın seçilmesi.
- Tekrarlı sorgular, uygun olmayan kaynak/niyet çifti, bütçe aşımı, mevcut olmayan indeks referansı.
- Prompt injection içeren kullanıcı metni; sistem kurallarını veya kategori listesini değiştirememesi.
- Plan tekrar gönderimi ve sürüm değişikliği; Faz 2'nin yalnız kaydedilmiş, doğrulanmış ve doğru sürümlü planı kabul etmesi.

## 3. Sitelerden çekilen veri ve mevcut script testleri

**Bu bölüm Faz 1 hazırlığının kritik teslimidir.** Mevcut Python testleri [veri-laboratuvari](../veri-laboratuvari/) içinde scriptlerin yanında korunur. `test_bulk_site_access_lab.py`, `test_keyword_search_pass.py`, `test_common_crawl_pass.py`, `test_probe_site_access.py`, `test_probe_hackernews_access.py`, `test_adaptive_domain_pass.py`, `test_secondary_index_pass.py` mevcut dosyalardır; bunların korunması ürün akışının test edildiği anlamına gelmez.

| Kontrol | Örnek ve beklenen sonuç |
|---|---|
| Dosya/provenance bütünlüğü | İndeks → dosya veya inline artefakt → hash → kaynak/URL/koşu/tarih bağı doğrulanır; checkout'ta olmayan içerik var sayılmaz |
| Yüzey sınıflandırması | Sitemap, root HTML, RSS, API, hedef yorum/ürün, arşiv snapshot ayrılır; yalnız keşif sonucu karar kanıtı olmaz |
| Başarı anlamı | HTTP 200 fakat bot sayfası/boş gövde/ilgisiz içerik, kullanılabilir veri sayılmaz |
| Alan doğruluğu | Fiyat+para birimi, yorum gövdesi, tarih, puan+ölçek gibi alanlar gerçek içerikle karşılaştırılır; eksik alan null kalır |
| Dil ve pazar | Türkçe fikir/İstanbul kapsamı otomatik ABD/global sonuca dönüşmez; çeviri belirsizliği görünür kalır |
| Tazelik | Çekim tarihi, yayın tarihi ve arşiv tarihi karıştırılmaz; arşiv verisi güncel diye sunulmaz |
| Tekrar/bağımsızlık | Aynı içerik farklı URL/platformda çoklu bağımsız kanıt sayılmaz |
| Kaynak-sorgu uyumu | Kaynakta ilgili alan/sorgu yüzeyi gerçekten vardır; katalogda yol bulunması canlı sorgunun başarılı olduğu anlamına gelmez |
| Hata ayrımı | `no_results`, `source_unavailable`, `blocked_by_policy`, rate limit ve eksik artefakt ayrı kaydedilir |
| Kaynak limitleri | İstek/sayfa/kayıt/süre sınırına uyum; duruş gerekçesi ve eksik kapsam raporlanır |

Batuhan ilk denemeleri yürütür; Ayselin erişim yolu ve içerik tipine göre küçük temsilci örnekler seçer; başarılı örneklerin yanında başarısız/boş/eski/tekrarlı örnekleri de etiketler. Her ilk sürüm kaynak profilinde en az bir doğrulanmış alan örneği ve varsa bir hata örneği bulunması önerilir. Zorunlu alan doluluğu, yanlış alan çıkarımı, ilgililik precision/recall, tekrar ve yanlış eleme oranı raporlanır; eşikler alan ve kaynağa göre pilotta belirlenir. Alan desteklemeyen kaynağı başarısız kabul edip zorla veri üretmek yerine yetenek sınırı kaydedilir.

Mevcut fixture/örneklerle offline kontroller ayrı, gelecekte yapılacak canlı erişim doğrulamaları ayrı sonuçlandırılır. Bu düzenleme sırasında canlı crawl, model çağrısı veya kapsamlı test çalıştırılması istenmedi ve yapılmadı.

## 4. Faz 2'ye teslimin kontrolü

Bir geçerli ResearchPlan, bir geçersiz plan, bir kaynak kapsamı eksik plan ve kullanıcı bilinmeyenlerle devam etmiş plan hazırlanır. Faz 2'nin kabul/ret/kısmi kapsam davranışı ortak sözleşmeyle değerlendirilir. Kaynak hazırlık örnekleri Faz 2'nin temizleme ve filtreleme değerlendirmesine aktarılır; gerçek sorgu sonucu ilgililiği ancak bu sonraki entegrasyonda ölçülebilir.

Sonuç raporu senaryo ID, fixture sürümü, beklenen/gözlenen davranış, puan, model/prompt sürümü, kaynak/artefakt bağı ve hata sahibi içerir. `not_run`, `passed`, `failed`, `blocked` ayrımı korunur; JSON dosyalarının yazılmış olması testlerin geçtiğini göstermez. Ortak ilkeler [kalite ve test belgesinde](../../ortak/kalite-ve-test-ilkeleri.md) bulunur.

## Yürütücü kontrolü

Batuhan [kontrol ve kabul rehberini](kontrol-ve-kabul-rehberi.md) kullanır; Ayselin veri sorunlarını çözer, Ayşenur ekranları bağlar. Model tüm fazlarda Gemini 3.1 Flash Lite; AI isteklerinde web/grounding/URL/script araçlarının kapalı olması ve gelen araç isteğinin yürütülmemesi zorunlu kontrol. Yerel kayıtlı veri/ortak entegrasyon düzeni onaylandı; Hetzner/Vercel bağlantı ayrıntıları sonraki kurulumda tamamlanacak.
