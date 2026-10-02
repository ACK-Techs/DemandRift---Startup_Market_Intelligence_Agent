# Faz 1 model girdisi

`phase1_prompts.build_phase1_prompt` kalıcı insan brief'i ve varsa aynı brief'e bağlı immutable plan için deterministik model girdisi hazırlar. Prompt sürümü `phase1-human-proposals-v1`, kategori kataloğu `v1`'dir. Bu modül sağlayıcı çağrısı, anahtar okuma, DB bağlantısı, bütçe başlangıcı veya onay işlemi yapmaz. Native analysis producer, HTTP ve canlı semantik kabul ayrı teslimlerdir.

Orijinal fikir Unicode ve whitespace ile aynen JSON veri alanında kalır; normalleştirme ayrı öneridir. İnsan metnindeki talimatlar sistem talimatına eklenmez. Kategori, sektör ve AI özellikleri temel ürünün sınıflandırılmasını destekler; kullanıcı etiketi cevap veya kaynak izni kabul edilmez. Belirsiz değerler unknown kalır; en fazla üç netleştirme sorusu ve açık insan onayı gerektiren niyet/sorgu önerileri istenir. Model çıktısının bu kurallara gerçekten uyduğu, typed output doğrulaması ve 30 canlı Faz 1 senaryosuyla ayrıca kanıtlanmalıdır.

Server, provider girdisine owner/project/research/brief/plan/query UUID, kaynak URL/izin/connector, runtime veya bütçe yetkisi eklemez. Orijinal insan metninde böyle görünen ifadeler varsa aynen untrusted veri olarak kalır; yetki kazanmaz. Native producer bunları aynı seçili snapshot'a ait request, attempt ve receipt bağında saklar. Plan girildiyse scope, exact brief içeriği ve kanonik fingerprint yeniden doğrulanır. Tarihsel/latest seçimi ve tekrar yayınlamadan önce current kontrolü producer'ın sorumluluğudur.

Input JSON en fazla 18.000 UTF-8 byte'tır; toplam hazırlanmış istek ayrıca metered gateway'in 32 KiB sınırına tabidir. Uzun bir girdi sessizce kırpılmaz; çağrı kabulünden önce güvenli hata döner. JSON schema, gerçek output token sınırı ve input reservation policy ayrı versioned gateway kontrolüdür. Unit kontrolleri girdi korumasını kanıtlar; model kalitesi veya canlı kaynak kabulü sayılmaz.

Mutable DTO içindeki geçersiz değerler serialization aşamasında güvenli hatayla reddedilir. Pydantic uyarıları stderr'e yazılmaz; brief ve plan canary kontrolleri özel girdinin uyarı, stdout, stderr veya public hata mesajına taşınmadığını doğrular.
