# Teknolojiler ve düşünülecek kararlar

**Kapsam kararı — Çağlar:** Build kararı, MVP/PRD önerisi, geliştirilecek ürünün özellikleri ve geliştirme yol haritası mevcut üç fazın hiçbirine dahil değildir. Bunlar projenin sonraki aşamasıdır; yönetici Çağlar tarafından daha sonra değerlendirilip planlanacaktır. Bu aşama kanıtları, araştırma değerlendirmesini ve eksikleri raporlar. Olumlu bulgu otomatik geliştirme kararı üretmez.

| Konu | Yaklaşım | Durum |
| --- | --- | --- |
| LLM | Tek şemalı karar sentezleme çağrısı; gerektiğinde sınırlı düzeltme | Gemini 3.1 Flash Lite; yalnız verilen EvidenceBundle üzerinde sentez. Anahtarı Çağlar Batuhan’a verecek; runtime yapılandırması kullanılacak. |
| Yapısal doğrulama | Pydantic + JSON Schema | Ortak sözleşmeyle tek sürüm. |
| Karar kuralları | Kaynaklı boyut profilleri, yeterlilik ve outcome uygunluğu | Onaylı 3 bağımsız örnek/2 kaynak alt sınırı ve nitel kontroller; policy v1. |
| Veri | Değişmez evidence/decision snapshot ve citation referansları | PostgreSQL ve kalıcı ham dosya referansları. |
| İş yürütme | Durum takibi, idempotency, sonlu retry, iptal | Ortak Celery/Redis worker; kalıcı durum PostgreSQL’de. |
| İzleme | Model/prompt/policy sürümü, hata, gecikme, token ve maliyet | Ortak kayıtlarla ilişkilendirilecek. |
| RAG | Faz 2'nin seçilmiş kanıtı başlangıç girdisidir | İlk teslimde ayrı retrieval sistemi zorunlu değil. |
| LangGraph/Temporal | Karmaşık kalıcı/dallanan akış ihtiyacı büyürse değerlendirme | Seçilmiş veya kurulmuş kabul edilmez. |

## Korunan ileri tasarım seçenekleri

Eski plandaki gated MCDA, Value of Information ve stability yaklaşımı korunur; ilk teslimde bunların anlaşılır kural tabanlı karşılıkları yeterlidir. Kalibre edilmemiş ağırlıklarla toplam başarı skoru veya Monte Carlo yüzdesi üretilmez. Gerçek değerlendirme/geri bildirim birikirse ağırlık duyarlılığı ikincil analiz olarak değerlendirilebilir.

Daha iyi model seçimi, çoklu model karşılaştırması veya retrieval ancak sabit etiketli set üzerinde kalite/maliyet artışı gösterirse eklenir. Çok ajanlı karar sistemi bu teslimin gereksinimi değildir.

## Açık kararlar

- Onaylı 3/2 alt sınırını koruyarak kategoriye özel kritik niyetler ve güncellik pencerelerinin ayrıntıları.
- Kaynaklı öneri ile deterministik karar politikasının ayrıntılı alan eşlemesi.
- İnsan değerlendirme rubric'i, sayısal kalite eşikleri ve model regresyon seti.
- Raporun dil/uzunluk seçenekleri; semantik destek kontrolünün otomatik ve insan denetimi sınırı.
- Karar hassasiyetinin ilk teslimde hangi kapsamda uygulanacağı. Uygulanmayan ölçüm `not_evaluated` kalmalı.

API anahtarını Çağlar Batuhan’a verecek. Yerel kayıtlı-veri testleri ve ortak entegrasyon ortamı onaylandı; Hetzner kurulumu/uzaktan build ve Vercel/API bağlantısının ayrıntıları [ortak mimari kaydına](../../ortak/mimari-ve-kararlar.md) göre netleştirilecek.

## Bağlayıcı AI sınırı

[Ortak RULES](../../ortak/RULES.md): Gemini 3.1 Flash Lite kullanılır. Sohbet/sorgu taslağı veya verilen veri analizi yapar; web arama, grounding, URL fetch, browser/deep research ve script araçları yoktur. Veri alımını yalnız backend script/connector hattı yürütür. Model API kimliği uygulama öncesi doğrulanır; sonraki değişiklikler ölçümle değerlendirilir.

Ana backend Python olacak; bu faz aynı Python backend içinde uygulanır. FastAPI + Pydantic ortak kararda onaylandı.
