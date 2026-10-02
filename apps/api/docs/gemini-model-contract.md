# Gemini backend model ve kullanım sözleşmesi

BE-05 contract alt teslimi yalnız server-internal immutable `GeminiPolicy`,
`GeminiUsage`, price-card hesabı ve ledger receipt üretir. HTTP transport, key
okuma, plan onayı, worker veya canlı erişim bu teslimde açılmaz. Browser/model
çıktısı endpoint, model, fiyat veya tools seçemez. Runtime backend açıkça
`developer` veya `vertex_express` olur; otomatik route/model fallback yoktur.

Sabit model `gemini-3.1-flash-lite` ve yalnız metin kullanılır. Resmî
[model sayfası](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite)
1.048.576 giriş ve 65.536 çıktı token tavanını doğrular. Seçilen route/anahtarın
gerçek erişimi ayrı zorunlu canlı kapıdır; dokümanda listelenmesi erişim kanıtı
değildir. Gemini policy giriş tavanını kendisi tahmin etmez. Consumer aynı
request için güvenilir giriş tavanını kanıtlamadan rezervasyon/gönderim açamaz.

[GenerateContent thinking kılavuzu](https://ai.google.dev/gemini-api/docs/generate-content/thinking?hl=en)
`maxOutputTokens` tavanının hem düşünme hem görünen çıktıyı kapsadığını açıklar.
`MINIMAL` düşünmeyi sıfıra indirme garantisi değildir. Rezervasyon bilinen giriş
tavanı + istenen toplam çıktı tavanını ve tamamı normal giriş fiyatından giriş
maliyetini tutar. Consumer gerçek response byte sınırını ayrıca uygular.

Resmî [usage alanları](https://ai.google.dev/api/generate-content) ve
[provider proto](https://raw.githubusercontent.com/googleapis/googleapis/master/google/ai/generativelanguage/v1beta/generative_service.proto)
ile [ProtoJSON varsayılanları](https://protobuf.dev/programming-guides/json/)
birlikte okunur. Mevcut usage nesnesinde pozitif prompt ve total zorunludur.
Proto'da implicit int32 olan cache/candidate/thought/tool sayacı sıfırken
atlanabilir; bu açık encoding kuralı yalnız mevcut ve tutarlı usage için geçer.
Eksik/null/tip bozuk bütün usage nesnesi sıfır sayılmaz. Total tam olarak
prompt + candidate + thought olmalıdır. Cache prompt'un alt kümesidir; ikinci
kez toplam tokena eklenmez. Tool tokenları, text dışı modalite, bilinmeyen
maliyet alanı veya standard/ON_DEMAND dışı tier kapalı sonuç üretir. Present
modalite listeleri aynı sayaçla tam eşleşir. Null veya belirtilmiş bozuk
sayaçlar implicit sıfır kabul edilmez.

`ModalityTokenCount.tokenCount` da aynı implicit int32 encoding'ini kullanır:
bilinen TEXT detayında atlanmış tokenCount sıfırdır. Belirtilmiş null/tip hatası,
bilinmeyen alan veya text dışı modalite bu istisnaya girmez. Pozitif prompt
detayının atlanmış sıfır tokenCount'u mevcut pozitif prompt toplamıyla uyuşmadığı
için reddedilir.
[Resmî content proto](https://raw.githubusercontent.com/googleapis/googleapis/master/google/ai/generativelanguage/v1beta/content.proto)
bu alt mesajın presence kuralını doğrular.

`gemini-3.1-flash-lite-standard-text-20261001` price card'ı
[Developer standard fiyatı](https://ai.google.dev/gemini-api/docs/pricing) ve
[Cloud global standard fiyatı](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing)
üzerinden sabittir: milyon token başına normal giriş $0,25, cached giriş $0,025,
candidate + düşünme çıktısı $1,50. Picousd/token değerleri 250000, 25000 ve
1500000 olarak integer hesaplanır; ambient Decimal veya her çağrıda microUSD
yuvarlama hesabı değiştirmez. Bu provider usage ve sabit price card'a dayanan
bütçe **maliyet tahminidir**, invoice veya ücretsiz-tier gerçek tahsilatı
değildir. Non-global, priority, flex, batch, multimodal, tool/grounding, cache
storage veya başka fiyatlandırma uygulanmaz. Böyle bir sonuç yeni doğrulanmış
price/schema sürümü gerektirir; consumer bilinmeyen tutarı iade edemez.

Receipt provider response ID'sini ve bildirilen tam model sürümünü korur;
önizleme/başka model kabul edilmez. ASCII bounded lineage ledger ile aynıdır.
Response içeriği için JSON/schema ve kaynak/alıntı hard gate'leri sonraki
consumer tesliminin görevidir. Sözleşme parsing'i başarılı olsa da araştırma
başlatma veya kanıt doğruluğu yetkisi oluşmaz. Tüm test verileri açık offline
fixture'dır; gerçek Gemini, kullanıcı anahtarı, canlı suite veya final 87
senaryo kabulü olarak sayılmaz.
