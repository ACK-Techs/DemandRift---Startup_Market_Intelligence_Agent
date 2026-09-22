# Test planı

API anahtarını Çağlar Batuhan’a verecek. Yerel kayıtlı-veri testleri ve ortak entegrasyon ortamı onaylandı; Hetzner kurulumu/uzaktan build ve Vercel/API bağlantısının ayrıntıları [ortak mimari kaydına](../../ortak/mimari-ve-kararlar.md) göre netleştirilecek.

## Temel test seti

Faz 1'de kabul edilen 10 fikir/30 anlatım uçtan uca izlenir. Karar kalitesi sadece fikir metninden ölçülmez: aynı fikir için farklı kaynaklı EvidenceBundle fixture'ları hazırlanır. Yeterli destek, güçlü karşıt kanıt, karma kanıt ve veri yokluğu aynı fikirde ayrı sonuç beklentisi yaratabilir.

Ayselin beklenen karar uygunluğunu, gerekçe kaynaklarını, görünür olması gereken karşıt claim'leri ve açık kalması gereken varsayımları etiketler. Tek bir ideal metne birebir eşleşme beklenmez.

## Zorunlu durumlar

| Senaryo | Beklenen davranış |
| --- | --- |
| Yeterli bağımsız problem/farklılaşma kanıtı | Olumlu bulgular kaynaklarıyla raporlanır; yönetici değerlendirmesine bırakılır, Build/MVP önerilmez. |
| Problem var; segment/kapsam uyumsuz | Modify, korunacak sinyal ve değişecek varsayım somut. |
| Yeterli araştırma ve mevcut teze karşı bağımsız güçlü kanıt | Kill uygun; mevcut tezle sınırlı gerekçe. |
| Bütün kaynaklara erişilemedi / sonuç yok | Investigate More; Kill veya “talep yok” üretilemez. |
| Aynı basın bülteninin çok sayıda kopyası | Bağımsızlık şişmez; yeterlilik geçilmiş sayılmaz. |
| Yeni pazarda az veri | Birincil doğrulama önerisi; otomatik Kill yok. |
| Güçlü pazar sinyali, yetersiz kişisel bütçe | Uygulama koşulları ayrı; pazar kötü diye yazılmaz. |
| Yalnız fiyat listesi veya “öderdim” yorumu | Gerçek ödeme davranışı diye sunulmaz. |
| Eski şikâyet yeni sürümde çözülmüş | Güncel karşıt kanıt görünür; karar eski şikâyete körlemesine dayanmaz. |
| Eksik pazar/dil veya eski fiyat kaydı | Kapsam sınırlılığı ve hedefli secondary gap. |
| Gerçek ödeme/çözüm uyumu bilinmiyor | Primary gap raporlanır; deney/MVP planı ve web arama döngüsü yok. |
| LLM kanıt yeterli olsa bile Build/MVP veya ürün pilot planı öneriyor | Backend kapsam dışı çıktıyı reddeder. |
| Uydurma claim/alıntı, başka projenin ID'si, stale binding | Doğrulama reddeder; rapor başarılı sayılmaz. |
| Kaynak metninde prompt injection | Kaynak talimatı karar kuralını/araçları değiştirmez. |
| Şema/model hatası veya token bütçesi bitmesi | Sonlu retry veya açık hata; sahte karar yok. |
| Kritik claim çıkarılınca yeterlilik düşüyor | Uygulandıysa stability hassasiyeti raporlanır; ölçülmediyse not_evaluated. |

## Ölçümler

- **Politika ihlali:** herhangi bir Build/MVP önerisi veya yetersiz kanıtta Kill, bilinmeyen kaynaktan claim, çapraz proje referansı; fixture'larda sıfır tolerans.
- **Kaynak doğruluğu:** citation bağlarının doğruluğu, desteklenmeyen olgu, yanlış/bağlamsız alıntı. Şema başarısı ayrı ölçülür.
- **Karşıt kanıt görünürlüğü:** etiketli kritik karşıt claim'lerin gerekçede ve sınırlılıklarda yer alması.
- **Karar uygunluğu:** insan rubric'iyle outcome eligibility, gerekçe ve aksiyon uygunluğu; kategoriler/diller arasında ayrı dağılım.
- **Aksiyon kalitesi:** hedef segment/soru/kanıt/yeniden değerlendirme koşulu somut mu; secondary ve primary doğru ayrılmış mı?
- **Kararlılık:** aynı snapshot/policy ile outcome uygunluğu ve kaynak seçimi; kelimelerin birebir aynı çıkması şart değildir.
- **Maliyet/süre:** rapor başına model çağrısı, token, hata/retry ve gerçek maliyet; hesaplanmayan kalem unknown.

İnsan değerlendirme eşikleri ve örneklem sayıları Ayselin pilotundan sonra belirlenir; henüz sayısal kabul eşiği varmış gibi sunulmaz. Başarı tahmini kalibrasyonu ancak ileride gerçek kullanıcı/ödeme sonuçlarıyla ele alınabilir; modelin self-confidence'ı metrik değildir.

## Teslim raporu

Fixture/etiket sürümü, kod/model/prompt/policy sürümü, koşu tarihi, yürütülen ve yürütülmeyen testler, gerçek çıktı, beklenen davranış farkı, hata örnekleri ve maliyet. Geçerli `Investigate More` bir test hatası değildir; kanıtın izin verdiği dürüst çıktıdır.

## Yürütücü kontrolü

Batuhan [kontrol ve kabul rehberini](kontrol-ve-kabul-rehberi.md) kullanır; Ayselin veri sorunlarını çözer, Ayşenur ekranları bağlar. Model tüm fazlarda Gemini 3.1 Flash Lite; AI isteklerinde web/grounding/URL/script araçlarının kapalı olması ve gelen araç isteğinin yürütülmemesi zorunlu kontrol. Yerel kayıtlı veri/ortak entegrasyon düzeni onaylandı; Hetzner/Vercel bağlantı ayrıntıları sonraki kurulumda tamamlanacak.
