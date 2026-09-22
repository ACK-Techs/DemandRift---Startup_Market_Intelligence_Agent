# Faz 2 — Veri toplama ve hazırlama

**Kapsam kararı — Çağlar:** Build kararı, MVP/PRD önerisi, geliştirilecek ürünün özellikleri ve geliştirme yol haritası mevcut üç fazın hiçbirine dahil değildir. Bunlar projenin sonraki aşamasıdır; yönetici Çağlar tarafından daha sonra değerlendirilip planlanacaktır. Bu aşama kanıtları, araştırma değerlendirmesini ve eksikleri raporlar. Olumlu bulgu otomatik geliştirme kararı üretmez.

**Durum: uygulanacak backend/AI planı.** Belgelerin varlığı bu akışın uygulamada çalıştığı anlamına gelmez. Mevcut bağımsız veri toplama scriptleri, site verileri ve bunların mevcut testleri kullanıcının isteğiyle [Faz 1 veri laboratuvarında](../faz-1-fikir-ve-arastirma/veri-laboratuvari/) birlikte tutulur. Faz 2 bunları ürün akışına bağlama ve veriyi karar için hazırlama işidir.

Girdi: Faz 1'in doğrulanmış `ResearchPlan` çıktısı. Çıktı: her kaynak için `SourceReport` ve Faz 3'e giden kaynaklı `EvidenceBundle`.

Akış: planı doğrula → kaynak profili ve bütçeyi uygula → veriyi çek → ham içeriği sakla → temizle/normalleştir → tekrarları ve ilgisiz veriyi ayır → bütçeli kanıt seç → kaynaklı bulgular çıkar → kapsam ve eksikleri kaydet.


- [Hazırlık süreci](docs/hazirlik-sureci.md)
- [Entegrasyon planı](docs/entegrasyon-plani.md)
- [Teknolojiler ve kararlar](docs/teknolojiler-ve-kararlar.md)
- [Test planı](docs/test-plani.md)
- [Veri sözleşmeleri](docs/veri-sozlesmeleri.md)
- [Görev ve teslim planı](docs/gorev-ve-teslim-plani.md)
- [Test senaryoları](tests/README.md)

## Sınırlar

- Bu faz her siteyi eksiksiz tarama taahhüdü vermez. Hangi alanın, kaç kaydın ve hangi zaman aralığının alınacağı kaynak profili ve araştırma bütçesine bağlıdır.
- Erişim sonucu, kullanılabilir veri ve araştırma kanıtı farklı şeylerdir. Sitemap almak kullanıcı yorumları alınmış demek değildir.
- AI kaynaktan bulgu çıkarabilir; nihai Build/Modify/Kill/Investigate More kararı [Faz 3](../faz-3-karar-ve-rapor/) işidir.
API anahtarını Çağlar Batuhan’a verecek. Yerel kayıtlı-veri testleri ve ortak entegrasyon ortamı onaylandı; Hetzner kurulumu/uzaktan build ve Vercel/API bağlantısının ayrıntıları [ortak mimari kaydına](../ortak/mimari-ve-kararlar.md) göre netleştirilecek.

## Eski içeriklerin karşılığı

Eski Faz 3 toplama, Faz 4 normalizasyon, Faz 5 ek araştırma ve Faz 6'nın kanıt hazırlama/analiz bölümleri burada birleştirildi. Eski planlar yeni iş sırasını yönetmez; tarihsel karşılaştırma için [trash/eski-planlar](../trash/eski-planlar/) altında tutulur.

## Güncel ekip ve kabul rehberi

[Kontrol ve kabul rehberi](docs/kontrol-ve-kabul-rehberi.md), [kişi görevleri](../ortak/ekip-ve-teslim.md), [model ve kapsam kuralları](../ortak/RULES.md). Ayşenur her fazın backend teslimi geldikçe ilgili ekranları bağlar; frontend entegrasyonu üç fazın tamamlanmasını beklemez.
