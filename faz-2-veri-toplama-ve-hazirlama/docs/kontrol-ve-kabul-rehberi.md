# Faz 2 — Batuhan kontrol ve kabul rehberi

Durum: planlandı, testler çalıştırılmadı. [Ekip döngüsü](../../ortak/ekip-ve-teslim.md), [AI kuralları](../../ortak/RULES.md) ve [kanıt politikası](../../ortak/kanit-yeterliligi-ve-karar-kurallari.md) geçerlidir.

| Kontrol | Beklenen davranış | Sahip / kabul |
|---|---|---|
| Plan ve kaynak yürütmesi | Doğru kategori/niyet→kaynak→script. Geçersiz/yeni sürümü olmayan plan reddedilir; inputu shell koduna çevirme. | Batuhan; kaynak alanlarında Ayselin |
| Limit ve tekrar | Kaynak ve toplam bütçe, byte/sayfa/istek/kayıt/süre/retry; rate limit, iptal, yeniden başlatma, çift gönderimde çift harcama/kayıt yok. | Batuhan |
| Ham kayıt ve yüzey | Snippets/sitemap ayrımı; raw içerik/hash ve tarih kaybı yok; başarı/kısmi/erişim engeli ayrılıyor. | Batuhan ilk kontrol; Ayselin düzeltme |
| Normalizasyon ve alanlar | Dil, tarih, fiyat/para birimi/dönem, gövde korunuyor; bilinmeyen null; eski içerik yeni diye gösterilmiyor. | Ayselin etiket/çözüm; Batuhan uygulama/kabul |
| Dedup ve ilgililik | Tam/yakın kopya, yanlış birleşme, önemli/karşıt kanıt kaybı. Etiketli referansta precision/recall; referans yoksa recall yok. | Ayselin inceleme; Batuhan yeniden kontrol |
| Gemini girdisi ve çıktısı | Yalnız seçilmiş veri; browsing/URL/search araçları yok; injection etkisiz; claim alıntısı ve ID bağları backend doğrulamalı. | Batuhan; Ayselin semantik kontrol |
| SourceReport ve paket | Her site için bulgu/karşıt/eksik, sayımlar ve erişim durumu; EvidenceBundle referansları ve bağımsızlık bilgisi tutarlı. | Batuhan + Ayselin |
| Ek araştırma | Sorgu önerisini model çalıştırmaz; aynı backend hattı, izin/bütçe/durma. Birincil boşluk raporlanır; web döngüsü yok. | Batuhan |
| Ekran | Ayşenur gerçek ilerleme, kanıt/rakip/problem ve kısmi durumları bağlar; sahte yüzdeler/sonuçlar yok. | Ayşenur teslim; Batuhan kabul |

## Çalıştırma ve raporlama

1. [Planlanan senaryoları](../tests/planlanan-senaryolar.json) sürümlü gerçek/etiketli payload fixture'larına bağla; JSON davranış taslağı test runner değildir. Onaylı 10 fikir setinin kategori çeşitliliğini koru. Başarılı, kısmi, erişilemeyen, ilgisiz, kopya ve karşıt veri örnekleri olsun.
2. Aynı senaryoda model girdisi/çıktısı, beklenen/gözlenen davranış, kaynak/claim/artefakt kimlikleri, model/prompt/policy sürümleri ve süre/token/hata kaydı tut. Sonuç kaydı alanları: senaryo ID, durum, kanıt bağlantısı, gözlenen fark, FB-ID, sorumlu, düzeltme ve Batuhan tekrar sonucu.
3. Batuhan veri/erişim/semantik sorununu Ayselin’e; API/sözleşme/yürütme hatasını kendisine; ekran eşleme/tasarım hatasını Ayşenur’a atar. [Geri bildirim şablonu](../../ortak/gorevler/geri-bildirim-sablonu.md) ile yapılması gereken düzeltmeyi somutlaştırır.
4. Teslimi aynı girdi ve ilgili regresyonlarla yeniden kontrol et; “düzeldi” mesajı yeterli değildir. Yeni model denemeleri aynı sabit veriyle karşılaştırılır; baseline korunur.
5. Faz kapanışında kategori ve kaynak kırılımı, bütünlük/kapsam/model/ekran hataları ayrı raporlanır. Not_run/blocked sonuçlar passed gibi sunulmaz. Çözülmeyen zorunlu kontrol için açık engel veya Çağlar değerlendirmesi gerekir.

API/test ortamı ve altyapı seçimleri ayrıca konuşulacaktır. Bu rehber çalışma yeri veya ücretli test yetkisi seçmez.
