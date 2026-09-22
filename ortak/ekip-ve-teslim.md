# Ekip, görev takibi ve kabul

## Kesinleşen sorumluluklar

| Kişi | Sorumluluk | Takip |
|---|---|---|
| Batuhan | Proje yürütücüsü ve backend geliştiricisi; ilk denemeler, ekip koordinasyonu, geri bildirim ve teslim kabulü | [Batuhan](gorevler/batuhan.md) |
| Ayselin | Kaynak erişimi/veri çıkarımı/kalite sorunları; farklı yöntem denemeleri ve kanıtlı düzeltme teslimi | [Ayselin](gorevler/ayselin.md) |
| Ayşenur | Tasarım iyileştirmeleri, mevcut frontend eksikleri, backend geldikçe sayfa bağlantıları | [Ayşenur](gorevler/aysenur.md) |
| Çağlar | Kapsam, teknoloji/mimari ve nihai ürün kararları; sonraki Build/MVP aşamasının değerlendirme ve planlaması | Açık kararların muhatabı |

Eski VS1/VS2 ifadeleri sırasıyla Ayselin/Ayşenur anlamına gelir; Ayşenur veri bilimci etiketi nedeniyle kaynak sorunlarının sahibi sayılmaz.

## Çalışma döngüsü

1. Batuhan Faz 1 sohbet/kategori/sorgu/backend akışını kurar. Kategoriye göre beklenen kaynak ve alanları eşler; örnek sorgularla script denemelerini kendisi yapar. Bu test alımları Faz 1 kaynak hazırlığıdır; ürün araştırma yürütmesi Faz 2'de aynı scriptleri kullanır.
2. Batuhan erişim, yanlış alan, ilgisiz içerik, eksik kapsam veya tekrar sorununu kanıtıyla Ayselin’e atar. Backend sözleşmesi/kota/durum hatasını kendisi sahiplenir; yalnız model hatasını veri sorunu diye yönlendirmez.
3. Ayselin yeniden üretir, düzeltme veya izinli alternatif dener; önce/sonra örnekleri, kapsam ve yan etkilerle teslim eder. Çözülemiyorsa neden ve seçenekleri bildirir; görevi kendi kendine kabul edilmiş yapmaz.
4. Batuhan aynı sorguyu ve ilgili regresyonları tekrar kontrol eder; kabul eder veya yapılması gereken düzeltmeyi açık yazar. Başarılı tek örnek tüm kaynak/kategori kabulü değildir.
5. Her fazın sürümlü backend çıktısı ve hata sözleşmesi hazır oldukça Ayşenur ilgili ekranı bağlar. Tasarım iyileştirmesi eşzamanlı ilerleyebilir. Üç fazın bitmesi beklenmez; mock gösterimi gerçek entegrasyon sayılmaz.
6. Batuhan Ayşenur’un gerçek veri, yüklenme, boş/kısmi/hata, yenileme ve kaynak bağlantılarını kontrol eder. API eksiklerini kendisi, ekran sorunlarını Ayşenur sahiplenir.
7. Her fazda [kontrol rehberi](../faz-1-fikir-ve-arastirma/docs/kontrol-ve-kabul-rehberi.md), senaryo sonuçları ve açık kusurlar üzerinden kapanış yapılır. Faz 2/3 rehberleri kendi docs klasörlerinde bulunur.

## Her görevin takip alanları

Görev ID, faz, sahip, bağımlılık, durum, beklenen teslim, kabul eden Batuhan, teslim/kanıt bağlantısı, engel ve sonraki adım. Başlangıç durumları **planlandı / not_run**; uygulama yapılmış gibi işaretlenmez. Durumlar: planlandı → çalışılıyor → incelemede → kabul edildi; gerekirse düzeltme gerekli veya engelli. Son güncelleme ve gerçek teslim tarihi iş ilerledikçe yazılır; uydurma takvim yoktur.

## Batuhan’ın zorunlu geri bildirim kaydı

| Alan | Ne yazılacak? |
|---|---|
| Kimlik | FB-ID, ilişkili görev, faz, kişi, önem ve durum |
| Yeniden üretim | Fikir/kategori, source_id/query_id, girdi, script/şema/model/prompt sürümleri, koşu kimliği |
| Beklenen / gerçekleşen | Hangi alan veya davranış bekleniyordu; gerçekte ne döndü? |
| Kanıt | Ham kayıt/çıktı, hata, ilgili kaynak veya ekran kaydı; sırları ekleme |
| Düzeltme isteği | “Buna bak” yerine hangi davranış düzeltilecek, hangi koşul kabul edilecek? |
| Teslim ve yeniden kontrol | Düzeltme bağlantısı, aynı senaryonun önce/sonra sonucu, ilgili başka kaynak/ekrana etkisi |
| Kapatma | Batuhan’ın kabul/ret gerekçesi, doğrulama tarihi; kapsam kararı gerekiyorsa Çağlar’a soru |

Şablon: [geri bildirim kaydı](gorevler/geri-bildirim-sablonu.md). Batuhan kendi backend değişikliklerinde de aynı kanıtı tutar; ilgili veriyi Ayselin, tüketim sözleşmesini Ayşenur kontrol eder. Proje kabul koordinasyonu Batuhan’da kalır.

## Kapsam

API anahtarını Çağlar Batuhan’a verecek. Yerel kayıtlı-veri testleri ve ortak entegrasyon ortamı onaylandı; Hetzner kurulumu/uzaktan build ve Vercel/API bağlantısının ayrıntıları [ortak mimari kaydına](mimari-ve-kararlar.md) göre netleştirilecek.
