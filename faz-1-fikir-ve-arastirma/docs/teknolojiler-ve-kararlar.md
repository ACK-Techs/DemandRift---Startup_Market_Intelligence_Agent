# Teknolojiler ve düşünülecek kararlar

## Konuşmada kabul edilen yapı

| Karar | Uygulama karşılığı |
|---|---|
| Doğrudan LLM API + JSON şeması + normal backend akışı | Fikri yorumlayan model, çıktıyı doğrulayan ve akışı yöneten uygulama |
| Kontrollü kategori ve araştırma amaçları | Küçük sürümlü liste/model bağlamı; kaynak eşlemesi uygulama kontrolünde |
| Dinamik anahtar kelime ve sorgu | Her fikrin müşteri/problem diline göre üretilir; sabit kelime seçimine indirgenmez |
| Başlangıçta RAG gerekmiyor | Bu faz harici belge araması yapmaz; küçük kategori listesi doğrudan bağlama girer |
| Başlangıçta LangGraph ve ayrı ajanlar gerekmiyor | Açık durum geçişleri ve kalıcı kayıt yeterli; karmaşıklık gerektirirse yeniden değerlendirilir |
| Mevcut Python araçları korunacak | Kaynak yeteneklerini doğrulamada kullanılır; Faz 2 adaptörü üzerinden yeniden kullanılır |

## Eski belgelerden taşınan teknik adaylar

Ana backend dili kullanıcı kararıyla **Python**. Tarihsel TypeScript/Node backend önerisi aktif seçim değildir. FastAPI + Pydantic, PostgreSQL ve kalıcı ham dosya alanı onaylandı; [ortak mimari](../../ortak/mimari-ve-kararlar.md) geçerlidir.

## Kısa karar listesi

1. İlk model kullanıcı kararıyla Gemini 3.1 Flash Lite. Sonraki model değişiklikleri aynı 30 fikir senaryosundaki kalite, şema geçerliliği, gecikme ve maliyetle değerlendirilecek. Sayısal model güveni tek başına doğruluk ölçütü değil.
2. Taksonomi ve source registry saklama: İlk sürümde sürümlü JSON yeterli olabilir; eşzamanlı düzenleme/denetim ihtiyacında veritabanına taşınabilir.
3. Kategori güven/çatışma eşiği: Kategori uydurmak yerine soru veya `unmatched`; eşik pilot çıktısıyla belirlenecek.
4. Netleştirme sınırı: 1–3 soru, en fazla iki tur başlangıç önerisi; atlama hakkı korunacak.
5. Araştırma derinliği: Hızlı/standart ve detaylı profiller aynı sözleşmeyi kullanacak. Önceden konuşulan kaynak başına 30/150 kayıt yalnız örnek; doğrulanmış limit değil. Ücretli paket kararı alınmadı.
6. Sorgu çevirisi: Modelin ürettiği dil/terimler hedef pazarla kontrol edilecek; eski sözlük zinciri zorunlu teknoloji değil. Çeviri belirsizliği gizlenmeyecek.
7. Otomatik tekrar: Şema hatası ve geçici sağlayıcı hatası için limitli tekrar sayısı belirlenecek; sınırsız maliyet oluşmayacak.

API anahtarını Çağlar Batuhan’a verecek. Yerel kayıtlı-veri testleri ve ortak entegrasyon ortamı onaylandı; Hetzner kurulumu/uzaktan build ve Vercel/API bağlantısının ayrıntıları [ortak mimari kaydına](../../ortak/mimari-ve-kararlar.md) göre netleştirilecek.

## Bağlayıcı AI sınırı

[Ortak RULES](../../ortak/RULES.md): Gemini 3.1 Flash Lite kullanılır. Sohbet/sorgu taslağı veya verilen veri analizi yapar; web arama, grounding, URL fetch, browser/deep research ve script araçları yoktur. Veri alımını yalnız backend script/connector hattı yürütür. Model API kimliği uygulama öncesi doğrulanır; sonraki değişiklikler ölçümle değerlendirilir.
