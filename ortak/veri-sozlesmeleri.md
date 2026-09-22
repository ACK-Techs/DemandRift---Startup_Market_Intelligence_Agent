# Ortak veri sözleşmeleri

Bu belge sözleşme **taslağıdır**. Gerçek API/DB şeması veya çalışan doğrulayıcı değildir. Kodlama öncesi producer ve consumer aynı sürümlü şemayı kabul eder; alanlar birbirinden bağımsız kopyalanmaz.

## Ortak zarf

Her faz çıktısı `schema_version`, `project_id`, `research_id`, `status`, `versions` taşır. Uygulama erişim bağlamı `user_id` ve gerekiyorsa `tenant_id` ile ilişkilendirilir; model bu kimlikleri üretmez. Kalıcı kayıtlarda oluşturulma/güncellenme zamanları ve çıktı kimliği tutulur.

`versions`: kullanılan brief/plan/kategori-katalog/source-registry/connector/prompt/model/normalizer/extractor/decision-policy sürümlerinden ilgili olanlar. Bilinmeyen bilgi uydurulmaz; null/unknown anlamı alan şemasında açıklanır.

| Sınır | Üreten | Tüketen | Temel içerik |
|---|---|---|---|
| `ResearchPlan` | Faz 1 | Faz 2 | Orijinal/onaylı brief, kategoriler, araştırma soruları/niyetleri, kaynak ve sorgu işleri, bütçe, bilinmeyenler |
| `RawArtifact` | Faz 2 kaynak işi | Faz 2 temizleme | Kaynak/URL, alınma/yayın tarihi, sorgu, erişim yolu, ham gövde referansı/hash, durum |
| `NormalizedDocument` + segmentler | Faz 2 temizleme | Faz 2 bulgu çıkarımı | Orijinal/temiz metin, dil, alanlar, kalite/tekrar ilişkileri, sürüm |
| `SourceReport` | Faz 2 | Faz 2 paketleme / Faz 3 | Site bulguları, alıntılar, karşıt bulgular, eksikler, toplama/erişim sınırları |
| `EvidenceBundle` | Faz 2 | Faz 3 | Site raporları, claims/citations, bağımsızlık, kapsama, tekrarlar, sınırlamalar, maliyet |
| `DecisionReport` | Faz 3 | Sonuç tüketicisi | Araştırma değerlendirmesi, gerekçe, karşıt kanıt, belirsizlik, araştırma boşlukları ve kaynak bağları |
| `ResearchGapRequest` | Faz 2/3 | Faz 2 yürütücüsü | Cevapsız soru, eksik kanıt, izinli kaynak/sorgu önerisi, kalan bütçe ve durma koşulu |

Fazların ayrıntılı alanları kendi `docs/veri-sozlesmeleri.md` belgesinde. Faz 1'in mevcut kaynak araştırması üretim `SourceRegistry` yerine geçmez; adaptasyon ve kabul gerekir.

## Fikir ve sorgu kökeni

- `user_stated`, `user_confirmed`, `ai_inferred`, `ai_hypothesis` ayrılır. Kullanıcının fikri AI tarafından sessizce değiştirilmez.
- Kategorilerde ana kategori, ek katman/dikey ve belirsizlik ayrılır. Sağlık/eğitim/Türkiye gibi bağlamlar her zaman ayrı ürün kategorisi değildir.
- Her sorgu bir araştırma sorusuna, niyete, kaynak profiline ve dil/pazar kapsamına bağlıdır.
- Kullanıcının onaylamadığı öneri, kesin araştırma kapsamına gizlice dönüştürülmez.
- `original_idea` değişmez; düzeltme/onay yeni brief/plan sürümü üretir.

## Kaynak ve kanıt bağı

```text
ResearchPlan → QueryExecution → RawArtifact
 → NormalizedDocument → Segment → Claim + Citation
 → SourceReport → EvidenceBundle → DecisionReport
```

Arama URL/title/snippet kaydı adaydır. Sitemap'te URL bulunması, o URL'nin içeriğinin fetch edildiği anlamına gelmez. Ana sayfa alınması yorumların veya fiyatların elde edildiğini kanıtlamaz. Arşiv verisi canlı gözlem olarak sunulmaz.

Citation: `citation_id`, `claim_ids`, `artifact_id`, `document_id`, `segment_id`, `verbatim_quote`, `start_offset`, `end_offset`, `segment_text_hash`, `normalized_content_hash`, `normalization_version`, `source_url`, `collected_at`, doğrulama durumu. Bir alıntı birden fazla claim'i destekleyebilir; Claim üzerindeki `citation_ids` ile bu bağ tutarlı doğrulanır. Üretim şeması kabul edildiğinde alan isimleri tek kaynaktan türetilir.

Alıntı kaynakta birebir bulunur; AI açıklaması ayrı alandır. Yeniden normalizasyon eski alıntıyı sessizce yeni metne bağlamaz. Kaynak sayısı ile bağımsız kanıt sayısı ayrıdır; aynı basın bülteninin beş kopyası beş bağımsız kanıt değildir.

## Durum ve hata anlamları

| Durum | Anlam |
|---|---|
| `succeeded` | İlgili iş kendi kabul koşullarını tamamladı |
| `no_results` | Kaynak başarıyla okundu/ayrıştırıldı; sorguya uygun sonuç yok |
| `source_unavailable` | Kaynağa erişilemedi; sonuç var/yok bilinmiyor |
| `rate_limited` | Kota/istek hızı engeli; tekrar zamanı profilce belirlenir |
| `blocked_by_policy` | İzin/robots/erişim kuralı engeli |
| `challenge` | Doğrulama/bot koruması engeli; başarıya çevrilmez |
| `invalid_output` | Şema, ayrıştırma veya bütünlük koşulu sağlanmadı |
| `partial` | Bazı işler/veriler başarılı, gereken kapsam eksik |
| `cancelled` | Çalışma iptal edildi |
| `failed` | Diğer teknik başarısızlık; hata kodu/gerekçe gerekir |

Çalışma yaşam döngüsü (`draft`, `awaiting_user`, `planned`, `acquiring`, `normalizing`, `analyzing`, `deciding`, `completed`) tek kaynak işinin sonucuyla aynı enum değildir. Faz belgesinde hangi durumun hangi kayıt üzerinde bulunduğu yazılır.

Hata zarfı: makine kodu, işlem/kaynak kimliği, güvenli kullanıcı açıklaması, tekrar denenebilirlik, gerçekleşen kullanım, kalan iş ve biliniyorsa sonraki adım. Secret veya ham özel girdi hata metnine yazılmaz.

## Karar anlamları

Build mevcut çıktı kümesinden çıkarılmıştır. Modify/Kill/Investigate More araştırma değerlendirmeleridir. Olumlu kanıt `market_assessment` içinde raporlanır; olumlu sonuç `outcome = positive_findings` ve “Olumlu bulgular — yönetici değerlendirmesi bekliyor” etiketiyle sunulur. `management_review_required = true` yönetici değerlendirmesini belirtir; geliştirme onayı anlamına gelmez. Investigate More için `investigate_secondary` ve `validate_primary` ayrımı korunur. MVP/PRD, ürün veya pilot planlamasını sonraki aşamada Çağlar yapacaktır.

Fiyat gözlemi, “öderdim” beyanı ve doğrulanmış ödeme davranışı ayrı kanıt türleridir. Kanıt bulunamaması veya şikâyet olmaması tek başına Kill üretemez. Yeterlilik ve alıntı kontrolü başarısızsa kesin karar yayınlanmaz.
