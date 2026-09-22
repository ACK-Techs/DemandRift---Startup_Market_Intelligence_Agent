# Faz 1 — Fikir Toplama ve Netleştirme

> Ortak kimlik, sözleşme, workflow, AI Gateway, maliyet, güvenlik ve gözlemlenebilirlik kuralları için `Platform-Temeli.md`; fazlar arası entegrasyon sırası için `Ust-Yonetim-Ana-Mimari-Plani.md` bağlayıcıdır.

## Amaç

Kullanıcının serbest metinle yazdığı fikri, araştırma yapılabilecek yapılandırılmış bir **Idea Brief** haline getirmek.

Bu faz araştırma, kaynak tarama, anahtar kelime üretimi veya karar verme yapmaz. Bunlar sonraki fazların sorumluluğudur.

## Kullanıcı akışı

1. Kullanıcı fikrini tek cümle veya serbest metin olarak girer.
2. AI metni yapılandırılmış alanlara ayırır ve fikrin araştırmaya yeterince net olup olmadığını değerlendirir.
3. Sistem, gerekirse en fazla 1–3 odaklı netleştirme sorusu gösterir.
4. Kullanıcı:
   - soruları yanıtlayabilir,
   - önerilen bir nişi seçebilir,
   - fikrini değiştirebilir,
   - veya mevcut kapsamla devam edebilir.
5. Kullanıcı onayıyla Idea Brief oluşturulur ve Faz 2'ye aktarılır.

## Temel ilkeler

- AI araştırma yapmaz; yalnızca fikri anlar, düzenler ve netleştirme önerir.
- Kullanıcının ilk metni her zaman saklanır; AI çıkarımı kullanıcı gerçeği sayılmaz.
- Kullanıcı, fikir geniş olsa bile devam edebilmelidir.
- Uzun sohbet yerine kısa, odaklı ve aşamalı bir deneyim sunulur.
- AI çıktısı serbest metin değil, şemaya uygun yapılandırılmış veri olmalıdır.

## Seçilen deneyim ve mimari kararı

Faz 1, **serbest metin başlangıcı + şemalı AI çıkarımı + kural tabanlı akış** kullanan hibrit bir intake deneyimi olacaktır.

- Kullanıcı, ürün fikrini form alanlarıyla anlatmak zorunda kalmadan başlayabilmelidir.
- AI, fikri anlamlandırır; fakat kullanıcı akışını, soru sayısını ve geçiş koşullarını uygulama belirler.
- Kullanıcı, sistemin önerdiği nişi seçmek zorunda değildir; mevcut fikriyle ilerleme seçeneği her zaman görünür.
- Fazın sonunda üretilen brief, Faz 2'nin doğrudan girdisidir; kullanıcı onayı olmadan kesinleşmiş sayılmaz.

Bu seçim, sabit formun yüksek sürtünmesini ve tamamen serbest chatbot yapısının tutarsızlığını dengeler.

## Değerlendirilen alternatifler

| Alternatif | Neden seçilmedi |
| --- | --- |
| Sabit form / wizard | Veri kalitesi yüksek olabilir; ancak ilk kullanımda çok fazla alan sorarak kullanıcıyı yorar. |
| Tam serbest AI sohbeti | Akıcıdır; fakat tutarsız soru sayısı, kapsam kayması ve makinece işlenemeyen çıktı riski taşır. |
| Ayrı ML sınıflandırıcı | Başlangıçta yeterli etiketli veri olmadığı için maliyet ve bakım yükü yaratır. |
| Hibrit yapı | Seçilen yaklaşımdır. Serbest başlangıcı, kurallı akışı ve doğrulanabilir çıktıyı birleştirir. |

## Idea Brief veri modeli

```text
original_idea           Kullanıcının ilk metni
normalized_idea         AI'ın sadeleştirilmiş açıklaması
product_type            agent | mobile_app | web_saas | extension | other
target_user             known | inferred | missing
problem_or_job          known | inferred | missing
context_or_niche        known | inferred | missing
constraints             bütçe, teknik seviye, platform tercihi (opsiyonel)
clarity_status          ready | needs_clarification | broad_but_continue
missing_fields          Eksik veya belirsiz alanlar
clarifying_questions    En fazla üç soru
suggested_niches        Kullanıcının seçebileceği opsiyonel öneriler
confidence              AI değerlendirme güveni
user_confirmed_fields   Kullanıcının açıkça onayladığı alanlar
field_origins           user_stated | user_confirmed | ai_inferred | ai_hypothesis
assumption_ids          Araştırma boyunca taşınacak açık varsayım kimlikleri
brief_version           Değiştirilemez brief sürümü
```

## Hazır olma kontrolü

AI her alanı `known`, `inferred`, `missing` veya `conflicting` olarak işaretler. Uygulama, bu bilgiyi kural tabanlı biçimde değerlendirir.

- Ürün türü, hedef kullanıcı ve problem/iş bağlamı belirsizse: `needs_clarification`
- Temel bağlam var fakat niş eksikse: `broad_but_continue`
- Araştırma için yeterli bağlam varsa: `ready`

Bu eşikler ilk sürümde basit kalacak; gerçek kullanım verisi ile daha sonra iyileştirilecektir.

## Netleştirme politikası

- Sistem yalnızca araştırma kalitesini anlamlı biçimde artıracak soruları sorar.
- Soru önceliği: hedef kullanıcı, çözülen iş/problem, ürün türü ve kullanım bağlamıdır.
- Bir turda en fazla üç soru gösterilir; toplam netleştirme turu en fazla ikidir.
- Kullanıcı yanıt vermek istemezse `broad_but_continue` durumuyla Faz 2'ye geçebilir.
- AI'ın önerdiği nişler varsayım olarak etiketlenir; kullanıcı seçmedikçe brief'in onaylı alanı olmaz.
- `ai_hypothesis` kökenli hiçbir niş, segment, problem veya ürün türü kullanıcı açıkça seçmeden Faz 2 sorgularını tohumlayamaz. Bu kural yalnızca prompt ile değil, şema ve Plan Compiler doğrulamasıyla uygulanır.
- Kullanıcı AI önerisini seçerse alan `user_confirmed` olur; önceki `ai_hypothesis` kökeni de denetim izi olarak korunur ve sonraki raporda varsayım olarak görünür.
- Kullanıcı yeni bilgi verirse önceki AI çıkarımları yeniden değerlendirilir; ilk kullanıcı metni değişmeden saklanır.

## Teknik yaklaşım

- Uygulama yapısı: TypeScript tabanlı modüler monolith
- Arayüz: Next.js
- Veri tabanı: PostgreSQL
- AI erişimi: Tek bir LLM Gateway / provider adapter
- Şema doğrulama: Zod ve JSON Schema
- Akış yönetimi: Veritabanında durum makinesi

```text
draft -> assessed -> clarifying -> confirmed -> brief_ready
```

### Bileşen sorumlulukları

| Bileşen | Sorumluluk |
| --- | --- |
| Next.js arayüzü | Serbest metin girişi, soru/öneri gösterimi, onay ve düzenleme deneyimi |
| Faz 1 servis modülü | Durum geçişleri, kullanıcı tercihleri ve hazır olma kuralları |
| LLM Gateway | Prompt sürümü, sağlayıcı seçimi, şemalı istek/yanıt ve hata yönetimi |
| Zod + JSON Schema | AI çıktısının beklenen veri sözleşmesine uyduğunu doğrulama |
| PostgreSQL | Oturum, orijinal metin, AI çıkarımları, kullanıcı onayları, durum geçmişi ve metrikleri saklama |

### AI çağrısı sözleşmesi

- Tek çağrı, tek sorumluluk: fikri yapılandırmak ve yalnızca gerekli netleştirme önerilerini döndürmek.
- AI'a sistem talimatları, kullanıcı metni ve çıktı şeması ayrı alanlarda verilir.
- AI çıktısı şema denetiminden geçmezse kullanıcıya gösterilmez; otomatik yeniden deneme veya güvenli hata durumu uygulanır.
- Prompt ve model sürümü her değerlendirmeyle birlikte kaydedilir. Böylece kalite farkları daha sonra izlenebilir.
- Bu fazda AI'ın dış araç, web, API veya kullanıcı hesabı erişimi yoktur.

## AI sınırları

- Kullanıcı adına ürün fikri seçmez veya değiştirmez.
- Araştırma sonucu, pazar iddiası, rakip veya fiyat bilgisi üretmez.
- Eksik bilgiyi kesin bilgi gibi kaydetmez.
- Şema doğrulamasından geçmeyen yanıtlar kabul edilmez.

## Hata, güven ve izlenebilirlik kuralları

- Kullanıcı girdisi güvenilmeyen veri olarak işlenir; uygulama talimatı ile aynı bağlama kontrolsüz biçimde karıştırılmaz.
- AI emin değilse bilgiyi `inferred` veya `missing` olarak işaretler; kesin ifade kullanmaz.
- AI çağrısı başarısız olursa kullanıcı metni kaybolmaz; kullanıcı tekrar deneyebilir veya manuel alanlarla devam edebilir.
- Her brief için orijinal metin, AI çıkarımı, kullanıcı değişikliği, onaylanan alanlar ve durum geçişleri saklanır.
- Faz 1 çıktısındaki her anlamlı alanın kökeni saklanır. Bilginin kullanıcı tarafından söylenmesi, AI tarafından çıkarılması ve AI tarafından önerilmesi birbirine dönüştürülemez.
- Bu kayıtlar model/prompt kalitesini ölçmek, hataları incelemek ve ileride kuralları iyileştirmek için kullanılır.

## Bilinçli olarak kapsam dışı bırakılanlar

Bu kararlar ilk sürümün odağını korumak ve gereksiz teknik karmaşıklığı önlemek için alınmıştır. İleride gerçek kullanım verisi ve açık bir ihtiyaç oluşursa tekrar değerlendirilebilir.

- **RAG / vektör veritabanı:** Bu fazda harici bir bilgi tabanı veya geçmiş dokümanlar üzerinde anlamsal arama yapılmaz. Görev yalnızca kullanıcının o an verdiği fikri yapılandırmaktır.
- **Multi-agent mimarisi:** Birden fazla agent'ın birbirini denetlediği ya da görev paylaştığı yapı kullanılmaz. Şemalı çıktı üreten tek, kontrollü AI çağrısı yeterlidir.
- **Fine-tuned model:** Başlangıçta eğitim verisi ve ölçülmüş hata örnekleri olmadığı için fine-tuning yapılmaz. Prompt, şema ve kurallar önce gerçek kullanıcı verisiyle doğrulanır.
- **Otomatik fikir seçme veya fikir değiştirme:** Sistem kullanıcı adına bir niş veya ürün fikri seçmez. Öneriler sunar; seçim ve mevcut kapsamla ilerleme hakkı kullanıcıdadır.
- **Uzun, açık uçlu chatbot deneyimi:** Faz 1 danışmanlık sohbeti değildir. Netleştirme akışı kısa, hedefli ve en fazla iki tur olacak şekilde tasarlanır.
- **Araştırma ve pazar doğrulaması:** Kaynak tarama, rakip bulma, fiyat analizi, anahtar kelime üretimi ve pazar iddiaları Faz 2 ve sonrasına aittir.
- **Karar üretimi:** Build, Modify, Kill veya Investigate More kararı bu fazda verilmez; Faz 1 yalnızca kararın dayanacağı doğru başlangıç brifini hazırlar.
- **Otomatik entegrasyon veya dış araç çağrısı:** Bu fazda tarayıcı, arama motoru, sosyal platform API'si veya üçüncü taraf kaynaklara erişim yapılmaz.

## Ölçümler

- Ortalama netleştirme turu
- Kullanıcının fikrini güncelleme oranı
- Mevcut fikirle devam etme oranı
- Faz 2 sonrasında kullanıcı düzeltme oranı
- Şema doğrulama hatası ve yeniden deneme oranı

## Faz 1 kabul kriterleri

- Kullanıcı tek cümlelik geniş bir fikirle akışı başlatabilmelidir.
- Sistem fikrin yeterince net olup olmadığını şemalı biçimde değerlendirebilmelidir.
- Kullanıcı en fazla iki netleştirme turunda ilerleyebilmeli veya istediği an mevcut fikirle devam edebilmelidir.
- Faz 2'ye yalnızca kullanıcı tarafından onaylanmış veya açıkça geniş kapsamla devam edilmesine izin verilmiş bir Idea Brief aktarılmalıdır.
- Geçersiz AI çıktısı, kullanıcı arayüzünde geçerli veri gibi görünmemelidir.
- Kullanıcı tarafından seçilmemiş `ai_hypothesis` alanları Faz 2 sorgu veya kaynak planına girememelidir.
- Idea Brief sürümlenmeli; Faz 2 hangi brief sürümünü kullandığını değiştirilemez biçimde kaydetmelidir.

## Faz 1 çıkışı

Kullanıcının onayladığı, kaynak/araştırma aşamasına aktarılmaya hazır bir Idea Brief.
