# Eski belgelerden üç faza içerik eşlemesi

22 Eylül 2026. Eski dosyalar silinmedi. Aktif sorumluluklar yeni üç faz ve ortak belgelerle tanımlanır; eski dosyalar tarihsel referanstır.

| Eski belge / içerik | Aktif karşılığı | Korunan asıl |
|---|---|---|
| Faz1: fikir, netleştirme, alan kökeni, brief | Faz 1 hazırlık, sözleşme, entegrasyon ve test planı | [Faz1](../../trash/eski-planlar/Faz1-Plan.md) |
| Faz2: sorular, kategori/source fit, sorgu derleme, kapsam ve bütçe | Faz 1 entegrasyon, sözleşme ve test planı | [Faz2](../../trash/eski-planlar/Faz2-Plan.md) |
| Faz3: kaynak aileleri, connector, quota, egress, ham içerik | Faz 2 hazırlık/entegrasyon; ortak mimari ve sözleşmeler | [Faz3](../../trash/eski-planlar/Faz3-Plan.md) |
| Faz4: parse, tarih/dil/URL, tekrar, entity, segment ve kaynak zinciri | Faz 2 veri hazırlığı ve kalite testleri | [Faz4](../../trash/eski-planlar/Faz4-Plan.md) |
| Faz5: gap-driven ek araştırma, bütçe, karşıt sorgu, durma | Faz 2 kontrollü tekrar; Faz 3 boşluk çıktısı | [Faz5](../../trash/eski-planlar/Faz5-Plan.md) |
| Faz6: ilgili parça seçimi, claim/quote, bağımsızlık, fiyat/rakip, karşıt bulgu | Faz 2 kaynaklı bulgular; Faz 3 siteler arası değerlendirme | [Faz6](../../trash/eski-planlar/Faz6-Plan.md) |
| Faz7: yeterlilik, dört karar, pazar/koşul ayrımı, sonraki doğrulama | Faz 3 altı belge ve senaryoları | [Faz7](../../trash/eski-planlar/Faz7-Plan.md) |
| Platform: kimlik, sürüm, workflow, maliyet, saklama, alıntı, kalite | Ortak mimari/veri sözleşmeleri/kalite ilkeleri | [Platform](../../trash/eski-planlar/Platform-Temeli.md) |
| Üst Yönetim: bağımlılıklar, teslim kabulü, sınırlar ve riskler | Ortak ekip/teslim ve faz görev planları | [Üst Yönetim](../../trash/eski-planlar/Ust-Yonetim-Ana-Mimari-Plani.md) |
| Gerekli İyileştirmeler: tarihsel değerlendirme | Aktif plan olarak kullanılmaz; geçerli ilkeler ortak/faz belgelerinde | [Eski değerlendirme](../../trash/eski-planlar/Gerekli-Iyilestirmeler.md) |
| KILAVUZ: Ayselin görev 1–6 anlatımı | Faz 1 kategori/sorgu ve Faz 2 kaynak/alan hazırlığı | [Kılavuz](../arastirmalar/ayselin/KILAVUZ.md) |
| Ayselin görev T01–T09 | Faz 1 hazırlık, değerlendirme ve teslim; Faz 2 veri gereksinimleri | [Görev aslı](../arastirmalar/ayselin/GOREV-TANIMI.md) |
| Altı internal/pazar belgesi | Tek tarihli [pazar araştırması](../arastirmalar/pazar-2026-08-16.md) | [Eski pazar dosyaları](../../trash/eski-pazar/) |
| research/source-access-lab | Faz 1 [veri laboratuvarı](../../faz-1-fikir-ve-arastirma/veri-laboratuvari/README.md) | Dosyalar taşındı; ikinci kopya üretilmedi |
| SITE-LISTESI, KAYNAK-DEFTERI, manifest/CSV indeksleri | Aynı lab içinde korunur; kaynak hazırlığı ve mevcut test bağımlılığı | Aynı dosyalar |
| results ve veriler-ornek | Aynı lab içinde mevcut ham/örnek kanıt | Aynı dosyalar |
| Python scriptler ve test_*.py | Aynı lab kökünde; Faz 1 kalite hazırlığı / Faz 2 çalışma zamanı tüketimi | Aynı dosyalar |
| DDG ve HN pilotları | Lab docs/pilots altında script referansı | Aynı dosyalar |
| İlk erişim özeti ve 2 Eylül durum raporu | Güncel durum yerine kullanılmaz; [kayıt özeti](kaynak-verisi-durumu.md) aktif | [Tarihsel raporlar](../../trash/eski-raporlar/) |
| Eski root/tasks/lab indeksleri | Yeni README ve faz/ortak girişleri | [Eski indeksler](../../trash/eski-indeksler/) |

## Son konuşmadan eklenenler

- Üç aşamalı ürün düzeni; her faz için altı belge ve ayrı tests dizini.
- Yedi ana kategoriyi kapsayan onaylı 10 fikir; net/eksik/yanlış etiketli anlatımla 30 planlı değerlendirme girdisi.
- Tek doğru kelime dizisi yerine niyet, müşteri/problem, kategori, kaynak ve dil uyumu ölçümü.
- İlk fikir akışında doğrudan LLM + JSON şeması + backend kontrolü; RAG/LangGraph önkoşulu yok.
- Her site için alınacak alan, derinlik/bütçe ve durma profili; 30/150 kayıt yalnız örnek, sabit ürün kararı değil.
- Ham veriyi koruyarak temizleme/tekrar/ilgililik süzgeci; LLM'e sınırlı ve kaynaklı parçalar.
- Site bazlı bulgu/alıntı/karşıt bulgu/eksik/erişim durumu; sonra genel karar raporu.
- İlk düzenlemede rol bazlı görevler yazıldı; sonraki kullanıcı kararıyla Batuhan yürütücü/backend, Ayselin veri sorunları, Ayşenur tasarım ve kademeli frontend bağlantısı olarak atandı. Kişi dosyaları ve frontend rehberi eklendi.
- API kullanım/dağıtım ve test yürütme ortamı belirlenmedi.

## Korunan doğruluk kuralları

Kullanıcı kapsamı ile AI varsayımı; arama adayı ile fetch edilmiş kanıt; erişilemeyen kaynak ile boş sonuç; kopya içerik ile bağımsız kaynak; birebir alıntı ile AI yorumu; fiyat/beyan ile gerçek ödeme; ikincil araştırma ile müşteri doğrulaması ayrı tutulur. Yetersiz veri kesin negatif karar değildir. Veri/prompt/model/sözleşme sürümleri ve tekrar üretilebilir kaynak bağı korunur.

## Eski kararların yeni statüsü

Temporal, geniş paket ağacı, ayrı browser/analytics worker, gelişmiş kümelendirme ve kalibre edilmiş karar stabilitesi eski hedef seçeneklerdir. Yeni ilk teslimde uygulanmış veya zorunlu sayılmaz; ihtiyaç/kalite/işletim kararları teknoloji belgelerinde açık tutulur. Kaynak aileleri ve ileri yöntemler tamamen silinmedi. Yeni faz numaraları eski numaraların yeniden adlandırılması değil, sorumlulukların üç ana akışta toplanmasıdır.

## Taşıma ile ilgili sınırlar

### Taşıma doğrulaması — 22 Eylül 2026

720 Markdown dışı laboratuvar dosyası (script, test, veri ve indeksler) ve arşivlenen 24 belgenin SHA-256 değerleri taşıma öncesi kayıtlarla aynı. AGENTS.md ve CLAUDE.md değişmedi. Yeni aktif belgelerin yerel dosya bağlantıları ve üç fazın senaryo JSON'ları doğrulandı. Taşıma tamamlandığında Faz 1'de 30, Faz 2 ve Faz 3'te 24'er planlı senaryo vardı. Sonraki kapsam düzeltmesiyle Faz 3'e bir kapsam kontrolü eklendi; o kapsam düzeltmesindeki sayı 25 idi; sonraki policy sınır senaryolarının güncel sayısı JSON fixture_count alanındadır. Bu kontrol dosya düzenine aittir; ürün testleri, canlı veri çekimi veya LLM çağrısı yapılmadı.

Tarihsel belge ve run kayıtlarının iç metni değiştirilmediği için eski göreli yollar bulunabilir. [Makinece okunur taşıma kaydı](dosya-tasima-kaydi.json) bunların karşılığını verir. Ham verilerin içindeki eski dosya yolu/acceptance_doc değerleri kanıt kimliğidir; yeni konuma uysun diye yeniden yazılmadı. AGENTS.md ve CLAUDE.md değiştirilmedi; eski yol talimatları bu eşleme ve güncel root README ile yorumlanmalıdır.

## Sonraki kapsam düzeltmesi

**Kapsam kararı — Çağlar:** Build kararı, MVP/PRD önerisi, geliştirilecek ürünün özellikleri ve geliştirme yol haritası mevcut üç fazın hiçbirine dahil değildir. Bunlar projenin sonraki aşamasıdır; yönetici Çağlar tarafından daha sonra değerlendirilip planlanacaktır. Bu aşama kanıtları, araştırma değerlendirmesini ve eksikleri raporlar. Olumlu bulgu otomatik geliştirme kararı üretmez. Tarihsel arşivlerdeki Build/MVP anlatımları aktif gereksinim değildir.
