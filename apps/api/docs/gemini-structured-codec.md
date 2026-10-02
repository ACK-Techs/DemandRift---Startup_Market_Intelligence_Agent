# Araçsız yapılandırılmış Gemini codec

`gemini_codec.py` saf bir istek/yanıt dönüştürücüsüdür. Ağ, credential,
otomatik retry, iş başlatma veya bütçe dispatch yetkisi içermez.

Sunucunun seçtiği kapalı Pydantic sözleşmesi, açık sürümlü sistem talimatı ve
veri metni tek turlu isteğe dönüşür. İstek en fazla 256 KiB, tek candidate,
`tools: []`, `maxOutputTokens` ve `MINIMAL` düşünme düzeyi kullanır.
MINIMAL sıfır düşünme tokenı anlamına gelmez; düşünme dahil kullanım ayrıca
hesaplanır. Fingerprint endpoint, prompt/schema sürümü ve bütün istek byte'larını
kapsar; input token sınırı codec tarafından tahmin edilmez.

Provider şeması yalnız desteklenen yapıları içerir; yerel referanslar sonlu
olarak açılır. Recursive/open object ve sunucu kimlik/onay alanları reddedilir;
Pydantic'in çözümlenmiş `by_alias=False` şeması da kontrol edilir; Python alan
adları JSON alias, nested model, TypeAliasType/NewType wrapper kullansa da
incelenir. Provider'a gönderilen alias şeması ayrı ve aynı sınırlı traversal ile
kontrol edilir; annotation get_args varsayımı kullanılmaz.
`pattern`, metin uzunluğu ve exclusive sınırlar gibi provider'a taşınmayan
kısıtlar gerçek Pydantic doğrulamasında korunur. Tekil anahtar/nonfinite/UTF-8
kontrolünden sonra strict JSON modu enum/date/UUID'nin JSON string biçimlerini
korur; sayı/bool/metin türleri keyfi olarak dönüştürülmez. Model metni bir yetki değildir;
consumer ayrıca güncel scope, plan, bütçe ve citation kurallarını uygular.

Yanıt byte sınırı ve UTF-8/JSON tekil anahtarları kontrol edilir. Kullanım ve
provider receipt, çıktı kabulünden **önce** doğrulanır. Bilinen kullanımlı safety,
truncated veya geçersiz JSON/şema cevabı ücretli girişimi geri ödemez; bu durumlar
ayrı sonuçtur. Usage/receipt bilinmiyorsa miktar sıfır varsayılmaz. Yalnız tek
tamamlanmış STOP candidate içindeki text parçaları doğrulanabilir; function,
grounding ve URL context kullanımı kabul edilmez. Thought parçaları çıktıya
eklenmez. Raw prompt/çıktı veya credential hata mesajına taşınmaz.

Bu teslim offline protokol dilimidir. Ledger ile gerçek transport bağlantısı,
token-count admission, runtime secret, actual key/model erişimi, retry admission
ve canlı suite kabulü BE05 içinde açık kalır.

Resmi kaynaklar (2026-10-02 kontrolü):

- [GenerateContent REST ve ThinkingLevel](https://ai.google.dev/api/generate-content)
- [GenerateContent structured output ve JSON Schema desteği](https://ai.google.dev/gemini-api/docs/generate-content/structured-output)
- [Sabit model kartı](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite)
