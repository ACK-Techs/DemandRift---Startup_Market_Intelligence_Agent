# Faz 1 — Batuhan kontrol ve kabul rehberi

Bu rehber **yapılacak kontrolleri** tanımlar; mevcut bir başarılı test raporu değildir. Batuhan yürütür ve kabul eder, Ayselin veri/kaynak sorunlarını çözer, Ayşenur hazır API'leri ekrana bağlar. [Kişi görevleri](../../ortak/ekip-ve-teslim.md) ve [model kuralları](../../ortak/RULES.md) geçerlidir. Ortam ve API erişimi kararlaştırılmadan canlı test varsayılmaz.

## Sıra ve teslim

1. Onaylanan 10 fikrin 30 net/eksik/yanlış etiketli girdisini sabitle. [Senaryo dosyası](../tests/fikir-senaryolari.json) içindeki yalnız `input` modele verilir; `expected` gizli değerlendirme referansıdır.
2. Kategori/niyet/pazar kararından sonra kaynak eşleme tablosunu hazırla. Aşağıdaki site örnekleri mevcut manifest adaylarıdır; çalışan erişim veya hedef alan garantisi değildir. Batuhan gerçek source_id, script, yüzey, alan ve limit eşlemesini doğrular; Ayselin destekler.
3. Her fikir için ilgili sorguları seçili sitelerde backend scriptleriyle dene. Gemini sorgu metni hazırlayabilir, **arama çalıştırmaz**. Fikir AI çağrısına browsing/grounding veya URL erişim aracı verilmez.
4. Başarı yanıtıyla yetinme: gerçekten ilgili yorum/fiyat/issue/ürün içeriği geldi mi kontrol et. Hataları [geri bildirim şablonuyla](../../ortak/gorevler/geri-bildirim-sablonu.md) ayır; veri/erişim Ayselin’e, backend akışı Batuhan’a, ekran Ayşenur’a.
5. Ayselin’in düzeltmesini aynı sorguyla yeniden dene; farklı fikir veya kaynak üzerindeki etkiyi de kontrol et. Önce/sonra kanıt olmadan kapatma.
6. Batuhan sürümlü ResearchPlan ve hata örneklerini Ayşenur’a teslim eder. Fikir/plan ekranını gerçek kayıt ve kullanıcı girdisiyle birlikte kontrol eder.

## Fikir → kategori → kaynak deneme matrisi

Aşağıdaki kaynaklar katalogdan alınmış **denenecek adaylardır**. Her satırda ilgili resmî ürün/doküman sayfaları da araştırma planına göre eklenebilir. Engelli veya alan sağlamayan kaynağı zorlamak yerine nedenini ve uygun alternatifi kaydet. Hiçbir kaynağın tüm kategorilerde çalışması beklenmez. Sorgu örnekleri birebir metin zorunluluğu değildir; kullanıcının pazarına göre yerelleştirilir.

| Fikir | Beklenen ana kategori / kritik ayrım | Örnek sorgular | Denenecek katalog kaynakları | İçerikte aranacak kanıt |
|---|---|---|---|---|
| F01 — Vardiyalı çalışanlar için uyku takibi | mobil-uygulama | shift worker sleep tracking app complaints; vardiyalı çalışan uyku takibi uygulaması | Apple App Store source-0096; Google Play Store source-0097; Reddit source-0075 | Vardiya bağlamında gerçek uyku takip sorunu; genel sağlık yazısı tek başına uygun değil |
| F02 — Ajans müşteri onayı ve revizyon SaaS | b2b-web-yazilimi | agency client approval revision tracking software; creative agency approval software complaints pricing | G2 source-0134; Capterra source-0135; Reddit source-0075 | Ajans/müşteri onayı-revizyon iş akışı, alternatif, tarihli plan fiyatı |
| F03 — API geriye uyumluluk CLI | gelistirici-araci | API breaking changes backward compatibility CLI; OpenAPI diff tool false positives issues | GitHub source-0017; Stack Overflow source-0023; Hacker News source-0022 | Breaking change/false positive örneği, issue içeriği ve sürüm bağlamı |
| F04 — Shopify iade nedenleri eklentisi | eklenti-entegrasyon | Shopify return reasons analytics app reviews; Shopify merchants return reason reporting problems | Shopify App Store source-0114; Reddit source-0075 | Mağaza sahibinin iade nedeni raporlama eksikliği, uygulama alanı ve yorum |
| F05 — Self-host Türkçe konuşma tanıma API | yapay-zeka-urunu | Turkish speech recognition self hosted API; Turkish ASR self hosted benchmarks licensing | Hugging Face source-0534; GitHub source-0017; Hacker News source-0022 | Türkçe/self-host koşulu, teknik sınırlama, lisans ve ölçüm kaynağı; benchmark talep kanıtı değildir |
| F06 — PC için iki kişilik bulmaca oyunu | oyun | PC two player co op puzzle game reviews; cooperative puzzle games player complaints | Steam source-0518; Reddit source-0075 | PC, iki kişilik/co-op, bulmaca türü ve oyuncu yorumu |
| F07 — İstanbul ev temizliği rezervasyonu | yerel-hizmet | İstanbul ev temizliği rezervasyon şikayetleri; İstanbul temizlik hizmeti fiyat rezervasyon | Armut source-0319; Trustpilot source-0148; Reddit source-0075 | İstanbul temizliği/rezervasyon deneyimi; başka şehir/ülke aynı kapsam değil |
| F08 — Günlük mobil kelime bulmacası | oyun | daily mobile word puzzle game reviews; günlük kelime oyunu kullanıcı şikayetleri | Apple App Store source-0096; Google Play Store source-0097; Reddit source-0075 | Günlük kelime oyunu ve oyuncu deneyimi; oyun ana kategori, mobil ek katman |
| F09 — Berber randevu ve gelmeme SaaS | b2b-web-yazilimi | barbershop scheduling software no show problems; berber randevu yazılımı fiyat yorum | Capterra source-0135; G2 source-0134; Reddit source-0075 | Berber işletmesinin no-show/randevu sorunu; yerel tüketici hizmetiyle karıştırma |
| F10 — Öğretmen notlarından AI alıştırma mobil uygulaması | mobil-uygulama | teacher notes to exercises AI app reviews; teachers AI worksheet generator accuracy complaints | Apple App Store source-0096; Google Play Store source-0097; Capterra Education Software source-0466 | Öğretmen/not→alıştırma bağlamı ve doğruluk sorunu; AI özellik, mobil ana kategori |

## Kategori ve sorgu değerlendirmesi

| Kontrol | Beklenen | Hata / kayıt |
|---|---|---|
| Net fikir | Ana kategori ürünün temel işine göre; müşteri/problem kaybolmuyor | Beklenen ve üretilen kategori ile gerekçe yazılır |
| Eksik fikir | Kritik boşluğu sor veya unknown bırak; net varyantın gizli bilgisini bilmesi beklenmez | Uydurulan müşteri/pazar/özellik kritik hata |
| Yanlış kullanıcı etiketi | Metindeki ürün esas alınır; belirsizse soru sorulur | Etiketi kör kopyalama veya gerekçesiz tersleme |
| Kategori kesişimi | F08 oyun+mobil; F09 B2B SaaS; F10 mobil+eğitim, AI özellik | Bu üç kritik örnekte katman ayrımı ayrıca kontrol edilir |
| Soru ve niyet | Problem, alternatif, şikâyet, rakip/fiyat gibi ilgili amaçlar; uygulanmayan amaç gerekçeli | Fiyatı ödeme davranışı yapma; tüm amaçları kör çalıştırma |
| Sorgu | Müşteri/problem/niyet/dil/pazar ve kaynağa uygun; onaysız yeni niş yok | Anahtar kelimeler doğru görünse bile yanlış hedef problem kabul edilmez |
| Kaynak planı | Registry kaynağı, gerçek yüzey ve desteklenen alan; bütçe ve fallback belli | Modelin uydurduğu source_id/URL veya desteksiz parametre reddedilir |

Kategori için net+yanlış etiketli 20 girdide doğru adet/toplam ve kategori kırılımı raporlanır. Mevcut test planındaki 18/20 ve semantik 1,6/2 eşikleri **başlangıç önerisi** olarak kalır; kullanıcı tarafından onaylanan 3/2 kanıt eşiğiyle karıştırılmaz. Sayısal kabul kesinleştirilmeden bunlara dayanarak faz kapatılmaz.

Sorgu kalitesi 0/1/2 ile müşteri, problem, niyet, dil/pazar ve kaynak uygunluğunda ayrı puanlanır: 0 yanlış/eksik, 1 kısmen uygun, 2 uygun. Batuhan puanlar, Ayselin veri tarafını karşılaştırır; anlaşmazlık gerekçesi saklanır. Sadece kelime eşleşmesi veya tek ortalama ile başarısız kategori gizlenmez.

## Sitelerden dönen veride zorunlu kontrol

- **Erişim:** no_results/source_unavailable/rate_limited/challenge/blocked_by_policy/invalid_output ayrımı. HTTP 200 + bot ekranı başarı değil. Tarihsel başarılı snapshot bugün çalışıyor kanıtı değil.
- **Yüzey:** sitemap/snippet/root HTML/metadata ile hedef yorum/issue/fiyat gövdesi ayrı. İndeksteki dosya gerçekten checkout'ta veya kayıtlı depoda bulunuyor mu?
- **Alanlar:** başlık, gerçek gövde, kaynak URL, alınma/yayın tarihi; kaynağa göre yazar, puan+ölçek, fiyat+para birimi+dönem. Kaynak desteklemiyorsa null; alan uydurma yok.
- **İlgililik:** örnek sonuçları insan etiketlesin: relevant/irrelevant/uncertain + neden. Anahtar kelime var ama yanlış müşteri/problem ise relevant sayma. İncelenen örneklem adedi ve seçilme yöntemi raporlansın.
- **Kapsam:** beklenen/alınan alan, dil/pazar/tarih ve kaynak; alınan/discovered/fetched/eligible/unique sayıları ayrı. Toplanan miktar etiketli ilgililik başarısı değildir.
- **Tekrar ve bağımsızlık:** canonical URL/dış ID/tam kopya; aynı kullanıcı ve kurumun tekrarları. Üç kayıt üç bağımsız gözlem varsayımı değildir.
- **Provenance:** girdi→query_id→source_id→script sürümü→ham dosya/hash→çıktı bağlantısı. Alıntı gövdede birebir bulunmalı; kayıp artefakt başarılı sayılmaz.
- **Limit/hata:** kayıt/sayfa/istek/byte/süre ve retry sınırları, erken durma, sıfır bütçe, iptal; model hiçbir limiti aşamaz. Kaynak problemi başka başarılı kaynakları silmez.
- **Alternatif:** Ayselin’in farklı yolu aynı gerekli alanı ve pazarı sağlıyor mu? Eski arşiv/kısıtlı metadata'ya düşüş açıkça partial ve sınırlılık olarak dönmeli.

Precision = ilgili bulunan etiketli sonuç / incelenen sonuç. Recall ancak etiketli ve bilinen referans kümesi varsa hesaplanır; açık web'in toplam ilgili içeriği bilinmediğinde gerçek web recall'u uydurulmaz. İlgililik ve veri alanı eşikleri kaynak bazında etiketli pilot sonrası önerilir.

## Hata, model ve ekran kontrolleri

Boş/uzun/çelişkili girdi, bozuk JSON, yanlış kategori/source_id, onaysız hipotez, model timeout/rate limit ve tekrar gönderme; geçersiz plan Faz 2'ye geçmez. Prompt injection kuralları değiştiremez. AI istek ayarlarında grounding/search/URL/shell araçları yok; model çıktısındaki araç çağrısı yürütülmez. UI girilen fikri korur, gerçek kayıt kimliğini gösterir, sahte başarı veya sessiz mock fallback üretmez. Gemini API anahtarı istemci payload/bundle/log içinde bulunmaz.

## Batuhan’ın dolduracağı sonuç raporu

[30 satırlık sonuç şablonu](../tests/kategori-sonuc-takibi.json) her fikir varyantı için boş kayıt içerir. Her kaynak/sorgu denemesi `source_runs` içine ayrı kaydedilir: source_id, query_id/query_text, script ve sürümü, yöntem, beklenen alanlar, bütçe, gerçek sayımlar, ham artefakt bağlantısı, etiketli örnekler, hata ve FB-ID. Aynı fikirde bir sitenin başarısı diğerini geçmiş saymaz. Sonradan incelenmemiş yüzeyin sonucu not_run kalır.

Faz raporu kategori bazında doğru/yanlış/eksik, site bazında erişim ve ilgililik, alan doluluğu, kopya/bağımsızlık, model süre/token/maliyet ve açık kusurları kapsar. Başarısız deneme Ayselin'e iletilir; düzeltme ve Batuhan tekrar sonucu aynı kayıt altında tutulur.

## Faz kapanışı

30 senaryo sonuçları, kaynak matrisi, ham kanıtlar, geri bildirimlerin yeniden kontrolleri ve gerçek UI/API örneği var. Zorunlu bir alan/yüzey çalışmıyorsa sessizce geçilmez: Batuhan düzeltme veya açık kapsam değişikliği ihtiyacını kaydeder. Faz 1 her kaynakta 3/2 kanıt bulmayı gerektirmez; bu eşik Faz 3 araştırma yeterliliğine aittir, erişim ve kategori testinin yerine geçmez.
