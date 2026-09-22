# Faz 3 — Batuhan kontrol ve kabul rehberi

Durum: planlandı, testler çalıştırılmadı. [Ekip döngüsü](../../ortak/ekip-ve-teslim.md), [AI kuralları](../../ortak/RULES.md) ve [kanıt politikası](../../ortak/kanit-yeterliligi-ve-karar-kurallari.md) geçerlidir.

| Kontrol | Beklenen davranış | Sahip / kabul |
|---|---|---|
| Snapshot ve alıntı | Doğru proje/araştırma/sürüm; uydurma veya eski citation reddedilir. Kaynak URL, quote ve tarih ekranda doğrulanır. | Batuhan; Ayselin veri kontrolü |
| 3/2 sınırı | 2/2 ve 3/1 insufficient; 3/2 tek başına geçmez. Kopya, aynı kullanıcı ve bilinmeyen bağımsızlık sayımı düşürür. | Batuhan uygular; Ayselin sayımı inceler |
| Nitel yeterlilik | Hedef müşteri/problem, mevcut çözüm, karşıt araştırma ve pazar/tarih uyumu. Eksik kritik boyut Investigate More. | Batuhan + Ayselin |
| Karar gerekçesi | Modify dayanaklı varsayım; Kill doğrudan güçlü karşıt kanıt; veri yokluğu Kill değil. Olumlu bulgular yönetici değerlendirmesi. | Batuhan + Ayselin |
| Kapsam sınırı | Build/MVP/PRD/ürün geliştirme veya deney planı hiçbir yeterlilik düzeyinde üretilemez. Çağlar sonraki aşamayı planlar. | Batuhan; Ayşenur ekran kontrolü |
| Gemini sınırı | Verilen EvidenceBundle dışında web araştırma veya model hafızasından olgu tamamlama yok; model policy/sayı değişikliği yapamaz. | Batuhan |
| Belirsizlik ve kaynak | Destek/karşıt/unknown ayrı; fiyat beyanı gerçek ödeme değil; uydurma başarı/confidence yüzdesi yok. | Ayselin inceleme; Batuhan kabul |
| Hata ve sürüm | Model/schema/bütçe/timeout hatası başarılı rapor sayılmaz; truthful Investigate More hata değil. Yeni veri yeni sürüm. | Batuhan |
| Ekran ve devir | Ayşenur gerçek rapor, gate sonuçları, kaynak bağı ve yönetici incelemesini gösterir. Birincil eksiklere ürün planı butonu eklenmez. | Ayşenur teslim; Batuhan kabul |

## Çalıştırma ve raporlama

1. [Planlanan senaryoları](../tests/planlanan-senaryolar.json) sürümlü gerçek/etiketli payload fixture'larına bağla; JSON davranış taslağı test runner değildir. Onaylı 10 fikir setinin kategori çeşitliliğini koru. Başarılı, kısmi, erişilemeyen, ilgisiz, kopya ve karşıt veri örnekleri olsun.
2. Aynı senaryoda model girdisi/çıktısı, beklenen/gözlenen davranış, kaynak/claim/artefakt kimlikleri, model/prompt/policy sürümleri ve süre/token/hata kaydı tut. Sonuç kaydı alanları: senaryo ID, durum, kanıt bağlantısı, gözlenen fark, FB-ID, sorumlu, düzeltme ve Batuhan tekrar sonucu.
3. Batuhan veri/erişim/semantik sorununu Ayselin’e; API/sözleşme/yürütme hatasını kendisine; ekran eşleme/tasarım hatasını Ayşenur’a atar. [Geri bildirim şablonu](../../ortak/gorevler/geri-bildirim-sablonu.md) ile yapılması gereken düzeltmeyi somutlaştırır.
4. Teslimi aynı girdi ve ilgili regresyonlarla yeniden kontrol et; “düzeldi” mesajı yeterli değildir. Yeni model denemeleri aynı sabit veriyle karşılaştırılır; baseline korunur.
5. Faz kapanışında kategori ve kaynak kırılımı, bütünlük/kapsam/model/ekran hataları ayrı raporlanır. Not_run/blocked sonuçlar passed gibi sunulmaz. Çözülmeyen zorunlu kontrol için açık engel veya Çağlar değerlendirmesi gerekir.

API/test ortamı ve altyapı seçimleri ayrıca konuşulacaktır. Bu rehber çalışma yeri veya ücretli test yetkisi seçmez.
