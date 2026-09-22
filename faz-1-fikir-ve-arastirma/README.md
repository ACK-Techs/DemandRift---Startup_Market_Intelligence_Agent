# Faz 1 — Fikir ve araştırma hazırlığı

**Kapsam kararı — Çağlar:** Build kararı, MVP/PRD önerisi, geliştirilecek ürünün özellikleri ve geliştirme yol haritası mevcut üç fazın hiçbirine dahil değildir. Bunlar projenin sonraki aşamasıdır; yönetici Çağlar tarafından daha sonra değerlendirilip planlanacaktır. Bu aşama kanıtları, araştırma değerlendirmesini ve eksikleri raporlar. Olumlu bulgu otomatik geliştirme kararı üretmez.

Kullanıcının fikrini kategori, araştırma soruları, kaynak seçimi, sorgular ve bütçesi belirli bir `ResearchPlan` çıktısına dönüştürür. Bu akış planlanmıştır; mevcut scriptlerin çalışan ürün backend'ine bağlandığı anlamına gelmez.

**Çalışma akışı:** fikir → gerekirse kısa netleştirme → kontrollü kategoriden seçim → dinamik sorgu taslağı → backend doğrulaması → Faz 2'ye araştırma planı.

| Konum | Kullanım |
|---|---|
| [Hazırlık süreci](docs/hazirlik-sureci.md) | Kategori, kanıt, kaynak ve sorgu hazırlıkları |
| [Entegrasyon planı](docs/entegrasyon-plani.md) | Model, backend ve veri laboratuvarının bağlantısı |
| [Teknolojiler ve kararlar](docs/teknolojiler-ve-kararlar.md) | Alınan kararlar ve açık seçimler |
| [Test planı](docs/test-plani.md) | Fikir testleri, veri testleri ve önerilen kabul eşikleri |
| [Veri sözleşmeleri](docs/veri-sozlesmeleri.md) | Brief, kategori, sorgu ve ResearchPlan alanları |
| [Görev ve teslim planı](docs/gorev-ve-teslim-plani.md) | Üç kişilik ekibin görevleri ve bağımlılıkları |
| [Fikir test dosyaları](tests/README.md) | Onaylanan 10 fikrin 30 planlanmış test girdisi |
| [Veri laboratuvarı](veri-laboratuvari/README.md) | Mevcut veri çekme/arama scriptleri, gerçek örnekler, indeksler ve Python testleri |

## Veriler neden Faz 1'de?

Kullanıcının isteğiyle sitelerden önceden çekilen veriler ve bunların mevcut testleri **bu fazın hazırlık varlığı** olarak `veri-laboratuvari/` altında birlikte tutulur. Kaynakların hangi veriyi gerçekten verdiğini incelemek, kategori ve sorgu planını doğru kurmak için gereklidir. Ürün çalışırken siteleri sorgulama, içerik toplama ve filtreleme sorumluluğu yine **Faz 2**'dedir; scriptler oradan yeniden kullanılır, kopyalanmaz.

Laboratuvarın `KAYNAK-DEFTERI.csv`, `ARTEFAKT-DIZINI.csv`, `ARAMA-YUZEYLERI.csv`, `source_manifest.json`, `SITE-LISTESI.md`, `results/`, `veriler-ornek/` ve `test_*.py` dosyaları birlikte korunur. Bir sitenin kök sayfasının ya da sitemap'inin indirilmesi, ürün araştırması için yeterli veri elde edildiğini göstermez. Tarihsel sayılar güncel erişim garantisi değildir.

Ortak kurallar için [ortak klasör](../ortak/README.md); Ayselin'in araştırma tasarımının tarihsel açıklaması için [kılavuz](../ortak/arastirmalar/ayselin/KILAVUZ.md) kullanılır. Bu faz belgeleri eski yedi fazın ilk iki fazını birleştirir; eski faz numaraları aktif akışı tarif etmez.

## Güncel ekip ve kabul rehberi

[Kontrol ve kabul rehberi](docs/kontrol-ve-kabul-rehberi.md), [kişi görevleri](../ortak/ekip-ve-teslim.md), [model ve kapsam kuralları](../ortak/RULES.md). Ayşenur her fazın backend teslimi geldikçe ilgili ekranları bağlar; frontend entegrasyonu üç fazın tamamlanmasını beklemez.
