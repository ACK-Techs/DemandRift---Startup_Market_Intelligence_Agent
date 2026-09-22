# Teknolojiler ve düşünülecek kararlar

Bu belge teknoloji kurulumu yapmaz. **Mevcut**, **planlanan** ve **aday** ayrımı korunur.

| Konu | İlk teslim yaklaşımı | Durum / karar gereksinimi |
| --- | --- | --- |
| Mevcut veri araçları | Faz 1'deki Python laboratuvarını adapter ile kullanmak | Mevcut scriptler var; ürün adapter'ı yazılacak. |
| Backend dili/çatı | Scriptlerden bağımsız sözleşme sınırı | Python + FastAPI onaylandı. |
| Şema | JSON Schema; seçilen runtime'da doğrulayıcı | Pydantic onaylandı. Tek kanonik JSON Schema/OpenAPI sözleşmesi gerekir. |
| Depolama | Ham artefact ve normalize/analiz kayıtları ayrı, sürümlü | PostgreSQL + başlangıçta kalıcı ham dosya alanı; gerektiğinde S3 uyumlu depolama. |
| Dış erişim | Ortak kaynak allowlist'i, egress kontrolü, kota/bütçe | API/HTTP/RSS/arşiv mevcut yeteneğe göre; yeni sağlayıcı kesinleştirilmedi. |
| HTML ayrıştırma | Mevcut parser'ı fixture ile ölç, gerekirse değiştir | Python parser seçimi mevcut araçların etiketli örneklerdeki sonuçlarına bağlı. |
| Exact dedup | Dış ID, canonical URL bağlamı ve SHA-256 | İlk teslimde deterministik; aynı URL'nin farklı tarihteki sürümleri kaybolmaz. |
| Yakın kopya | Etiketli veride aday eşleştirme | SimHash, pg_trgm, TF-IDF; büyük corpus'ta MinHash/LSH adayları korunur. |
| Dil | Dil alanını bilinmiyorsa unknown bırak | fastText/yerel model gibi seçenekler çok dilli ölçümle seçilir. |
| İlgililik | Ucuz lexical/BM25/TF-IDF filtreleri ve çeşitliliği koruyan seçim | Eşikler Ayselin verisiyle kalibre edilir; sırf kelime eşleşmiyor diye kanıt silinmez. |
| LLM | Şemalı claim çıkarımı ve kaynak raporu, backend doğrulaması | Gemini 3.1 Flash Lite; yalnız backend tarafından verilen veri. Anahtarı Çağlar Batuhan’a verecek; runtime yapılandırması kullanılacak. |
| Uzun işler | Kalıcı durum, tekrar güvenliği, sınırlı retry ve iptal | Celery + Redis seçildi; kalıcı araştırma durumu PostgreSQL’de. Temporal/LangGraph ilk teslimde yok. |
| Gözlemlenebilirlik | İş, kaynak, sürüm, hata, süre, maliyet kayıtları | OpenTelemetry ortak uygulama adayı. |

## İleri seçenekler: ihtiyaç ölçülmeden kurulmaz

- **RAG / embedding / pgvector:** corpus büyür veya çok dilli lexical yöntem önemli kanıt kaçırırsa retrieval için değerlendirilir. Vektör benzerliği gerçeklik ya da bağımsızlık doğrulaması değildir.
- **Kümeleme:** açıklanabilir lexical benzerlik grafiği temel aday; HDBSCAN etiketli veri ve yoğunluk uygunsa, BERTopic yalnız deneysel yardımcı seçenek. Outlier zorla kümeye sokulmaz.
- **Browser render / Playwright:** basit HTTP yeterli değilse ve kaynak erişimi uygunsa izole worker adayı. Kaynak/URL sınırları, özel IP engeli, redirect kontrolü, timeout ve indirme limitleri olmadan eklenmez.
- **Hazır deep research:** tarihsel seçenek; mevcut model kullanımına dahil değildir. Bu plan kapsamında modele web araştırma aracı bağlanmaz. Yeni dış araştırma servisi ayrı kapsam kararı gerektirir.
- **Redis:** kuyruk için otomatik ön koşul değildir; dağıtık kota/cache koordinasyonu ihtiyacı ölçülür.

## Açık ürün kararları

Kaynak başına limitler, araştırma derinliği adları/varsayılanları, ilk kaynak paketi, tarih pencereleri, kalite eşikleri, ek araştırma tur sayısı ve model token dağılımı pilotla belirlenecek. Örnek 30/150 kayıt sayıları karar değildir. Ücretli/premium model ve koşulsuz otomatik deep research bu planla onaylanmış sayılmaz.

API anahtarını Çağlar Batuhan’a verecek. Yerel kayıtlı-veri testleri ve ortak entegrasyon ortamı onaylandı; Hetzner kurulumu/uzaktan build ve Vercel/API bağlantısının ayrıntıları [ortak mimari kaydına](../../ortak/mimari-ve-kararlar.md) göre netleştirilecek.

## Bağlayıcı AI sınırı

[Ortak RULES](../../ortak/RULES.md): Gemini 3.1 Flash Lite kullanılır. Sohbet/sorgu taslağı veya verilen veri analizi yapar; web arama, grounding, URL fetch, browser/deep research ve script araçları yoktur. Veri alımını yalnız backend script/connector hattı yürütür. Model API kimliği uygulama öncesi doğrulanır; sonraki değişiklikler ölçümle değerlendirilir.
