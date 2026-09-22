# Entegrasyon planı

Bu belge hedef bağlantıyı tarif eder; bağlantı henüz uygulanmış değildir.

## İş akışı

1. Backend fikir metnini ve verilmişse pazar/dil/derinlik tercihini kimlikleriyle kaydeder.
2. LLM sağlayıcı adaptörü şemalı bir brief ve kategori taslağı üretir; model bu adımda site gezmez.
3. Backend alan kökenlerini, eksikleri ve çatışmaları kontrol eder. Gerekirse kısa netleştirme turunu yönetir; atlanan sorular `unknowns` olarak kalır.
4. Onaylı veya açıkça belirsizlikle devam edilmiş brief için LLM araştırma soruları ve sorgu tohumları üretir. Kategori listesi ve ilgili kurallar bağlama verilir.
5. Backend izinli kaynak profilleriyle eşleme yapar; sorgu, niyet, kaynak, alan, pazar ve bütçe uyumunu doğrular. Geçersiz/tekrarlı sorguları reddeder veya nedenini kaydederek eler.
6. Sürümlü `ResearchPlan` kalıcı olarak kaydedilir. Faz 2 aynı plan ve registry sürümünü kullanarak toplama işini başlatır.

İlk iki model görevi aynı sağlayıcıyı kullanabilir; tek dev çağrı zorunlu değildir. Araştırma başlatma yan etkisi, geçerli planın kaydı tamamlanmadan gerçekleşmez. Tekrarlanan istek aynı araştırma kimliği ve idempotency anahtarıyla ikinci bir iş oluşturmamalıdır.

## Laboratuvarın bağlantısı

| Mevcut varlık | Yeni akıştaki rol |
|---|---|
| `veri-laboratuvari/source_manifest.json`, `KAYNAK-DEFTERI.csv` | Kaynak kayıtları ve tarihsel erişim gözlemleri; üretim uygunluk kontrolünün girdisi |
| `veri-laboratuvari/ARAMA-YUZEYLERI.csv` | Yerel indeks/tam metin ile uzak site/API/OpenSearch ayrımı |
| `veri-laboratuvari/ARTEFAKT-DIZINI.csv`, `results/`, `veriler-ornek/` | Veri kalitesi ve alan doğrulama örnekleri; kaynak, tarih ve hash bağı |
| `veri-laboratuvari/keyword_search_pass.py` | Faz 2'de sorgu yürütücüsüne uyarlanacak mevcut araç |
| `veri-laboratuvari/bulk_site_access_lab.py`, `common_crawl_pass.py` | Faz 2'de kullanılacak toplama araçları; canlı/arşiv ayrımı korunur |
| `veri-laboratuvari/test_*.py` | Mevcut script davranışı için korunacak testler |

Tablodaki yollar faz klasörüne göredir. Scriptlerin girdi/çıktılarına adaptör yazılacak; LLM'e serbest shell komutu üretme yetkisi verilmeyecek. Dosyalar birden çok fazda çoğaltılmayacak. Tarihsel erişim sonucunu `enabled` kaynağa dönüştürmek için alan ve erişim uygunluğu ayrı doğrulanacak.

## Sınırlar ve hata davranışı

- Geçersiz model JSON'u yürütülemez; sınırlı tekrar ve `schema_invalid` hatası kullanılır.
- Boş fikir `invalid_input`; eşleşmeyen kategori `unmatched`; çelişkili brief `needs_clarification` olur. Bunlar aynı hata değildir.
- Kategoriye uygun kaynak yoksa boşluk raporlanır; desteklenmeyen URL/parametre oluşturulmaz.
- Pazar değişikliği yeni brief/plan sürümü oluşturur; eski planın kapsamı sessizce değiştirilmez.
- Kullanıcı verisindeki talimatlar sistem kurallarını değiştiremez. API sırları prompt, plan veya test çıktısına girmez.
- Araştırma sırasında ortaya çıkan yeni kelime/boşluklar Faz 2'den gerekçeli yeniden plan isteği olarak gelir; kapsam ve bütçe kontrolünden geçer.

Ortak kimlik, sürüm ve hata kuralları [ortak veri sözleşmesinde](../../ortak/veri-sozlesmeleri.md) tutulur. Frontend bağlantısının ayrıntıları, API anahtarı sahipliği/paylaşımı, sunucu ve testlerin hangi ortamda çalışacağı bu belgenin kararı değildir.
