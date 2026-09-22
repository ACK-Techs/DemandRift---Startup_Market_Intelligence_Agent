# Test planı

**Durum: planlandı.** Bu doküman ve [JSON senaryoları](../tests/planlanan-senaryolar.json) çalıştırılmış test sonucu değildir. Mevcut site verileri ve mevcut script testleri [Faz 1 laboratuvarında](../../faz-1-fikir-ve-arastirma/veri-laboratuvari/) korunur. Testlerin hangi bilgisayar/sunucuda çalıştırılacağı açık karardır.

## Test katmanları

| Katman | Doğrulanacak özellik | Beklenen kanıt |
| --- | --- | --- |
| Kaynak adapter sözleşmesi | Kaynak/query/bütçe parametreleri doğru script'e gidiyor mu? | Sahte adapter çağrı kaydı ve beklenen normalize cevap. |
| Kaydedilmiş veri tekrar oynatımı | HTML/API/RSS/arşiv alanları doğru ayrışıyor mu? | Kaynak ID + artefact/hash referansı + Ayselin beklenen alanları. |
| Normalizasyon/dedup | Ham içerik korunuyor, yakın kopya ile aynı problem ayrılıyor mu? | Önce/sonra metin, ilişkiler ve sürümler. |
| Filtreleme | İlgisiz içerik eleniyor, önemli ve karşıt kanıt tutuluyor mu? | Etiketli relevant/irrelevant/counterevidence setinde precision/recall. |
| Kaynaklı LLM çıkarımı | Alıntı ve yorum ayrılıyor, citation doğru mu? | Doğrulanmış segmentler ve insan değerlendirmesi. |
| Toplama akışı | Limit, retry, iptal, kısmi sonuç ve yeniden başlatma | Mock dış servis ile durum/maliyet günlüğü. |
| Kaynak sağlığı pilotu | Seçili kaynak bugün doğru yüzeyi döndürüyor mu? | Tarihli, kapsamı açık erişim/payload raporu; ayrı çalıştırılacak. |
| Fazlar arası sözleşme | ResearchPlan → EvidenceBundle → Faz 3 aktarımı | Sabit fixture ile kayıtlı sözleşme sonucu. |

Canlı kaynak ve ücretli LLM testleri varsayılan offline testlere karıştırılmaz. API/ortam kararı verilmeden canlı test kurulumu yapılmış sayılmaz.

## Zorunlu senaryo grupları

1. Başarılı API yorum alımı ve kaynak bağları; sadece metadata/sitemap erişimini içerik başarısından ayırma.
2. Sıfır sonuç, ağ hatası, 429, izin engeli, bozuk payload, büyük yanıt, süre aşımı, iptal.
3. Sonlu sayfa/kayıt/istek/byte/token sınırı; eşzamanlı işlerin toplam tavanı aşmaması; fallback'in plan sınırında kalması.
4. Eksik yayın tarihi, Türkçe karakterler, çok dilli/kısa metin, canonical parametrelerin içerik anlamını bozmaması.
5. Exact kopya, yakın kopya, aynı problemin bağımsız anlatımı, beş domain'de tek basın bülteni, belirsiz ürün adı.
6. Filtre eşik sınırı, dolaylı kullanıcı dili, çok sayıda tanıtım sonucu arasında tek önemli şikâyet, az sayıdaki karşıt kanıt.
7. Hatalı/uydurma alıntı, eski normalizasyon sürümüne bağlı citation, kaynak içinden prompt injection.
8. Aylık/yıllık fiyat ve farklı para birimi, eski arşiv fiyatı, bilinmeyen tutar, yorumdan ödeme davranışı uydurma.
9. Gap turunda yeni kanıt gelmemesi, bütçe bitmesi, birincil doğrulama boşluğunun web'e yönlendirilmemesi.
10. İş tekrarı, resume/retry, kısmi başarı, başka proje/run verisinin karışmaması.

## Ölçümler ve kabul kuralları

- **Zorunlu bütünlük:** dış çağrı öncesi plan/kaynak/bütçe doğrulaması; kabul edilen her claim'de geçerli citation; ham artefact hash'i ve sürümü korunması; fixture'larda bütçe aşımı ve çapraz proje veri karışması olmaması. Bunlar toleranslı kalite hedefi değildir.
- **Kaynak bazlı kalite:** payload kullanılabilirliği, zorunlu alan doluluğu, parser doğruluğu, erişim yöntemi ve veri türü ayrımı. “534 yüzeye erişildi” gibi geçmiş toplamlar doğru arama/test başarı oranı sayılmaz.
- **Filtre kalitesi:** precision, recall, yanlış elenen önemli/karşıt kanıt oranı; sonuçlar kategori, kaynak ailesi ve dil kırılımında raporlanır.
- **Dedup kalitesi:** yanlış birleşme ve kaçan tekrar oranları; bağımsız kullanıcıların birleştirilmesi ayrıca kontrol edilir.
- **Claim kalitesi:** kaynak tarafından desteklenme, alıntı doğruluğu, eksik bağlam ve hallucination oranları. Şemadan geçmek semantik doğruluk kanıtı değildir.
- **Kapsam/maliyet:** niyet başına bağımsız kanıt, yeni kanıt/tur, kaynak başına süre, token ve maliyet. Faz 1'in kabul edilen 10 fikri/30 anlatımıyla kategori kapsamı korunur.

Kalite için sayısal yayın eşikleri henüz belirlenmedi. Ayselin etiketli pilot tabanını çıkarır, backend geliştiriciyle eşikler kayıt altına alınır; eşik yazılmadan “test başarılı” denmez. Veri çıkarımı ve prompt değişiklikleri aynı sabit regresyon seti üzerinde karşılaştırılır; değerlendirme için ayrılan örnekler tuning setinden ayrılır.

## Teslim raporu

Her koşu: fixture seti ve hash/sürümü, kod/prompt/model/policy sürümleri, yürütülen senaryolar, gerçek sonuç, beklenen sonuçla fark, hata örnekleri, kaynak/tarih sınırları ve maliyet. `planned`, `not_run`, `passed`, `failed`, `blocked` açıkça ayrılır.

## Yürütücü kontrolü

Batuhan [kontrol ve kabul rehberini](kontrol-ve-kabul-rehberi.md) kullanır; Ayselin veri sorunlarını çözer, Ayşenur ekranları bağlar. Model tüm fazlarda Gemini 3.1 Flash Lite; AI isteklerinde web/grounding/URL/script araçlarının kapalı olması ve gelen araç isteğinin yürütülmemesi zorunlu kontrol. Yerel kayıtlı veri/ortak entegrasyon düzeni onaylandı; Hetzner/Vercel bağlantı ayrıntıları sonraki kurulumda tamamlanacak.
