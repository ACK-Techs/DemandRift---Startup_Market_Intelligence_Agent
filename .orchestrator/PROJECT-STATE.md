# Güncel proje durumu

22 Eylül 2026: Kullanıcı ürün planını üç faz + ortak düzenine geçirdi. Aktif giriş noktası [README](../README.md) ve [ortak belgeler](../ortak/README.md).

- Faz 1: fikir, kategori, sorgu ve kaynak/veri hazırlığı.
- Faz 2: toplama, normalizasyon, filtreleme ve site bulguları.
- Faz 3: kanıt yeterliliği, karar ve rapor.
- Eski Faz1–Faz7, Platform ve Üst Yönetim belgeleri `trash/eski-planlar/` altında tarihsel kaldı.
- Web prototipi `apps/web/` içinde var; üretim backend'i henüz yok.
- Python scriptleri, çekilmiş veriler ve mevcut testler `faz-1-fikir-ve-arastirma/veri-laboratuvari/` altında.
- Yeni faz senaryoları planlı fixture'lardır; uygulanmış backend/test başarı kanıtı değildir.
- Ayselin kılavuz/görev asılları `ortak/arastirmalar/ayselin/` altında; bazı anlatılan kod/veri teslimleri halen eksik.
- API kullanım/dağıtım ve test yürütme ortamı kararları açık; frontend ayrıntılı planı sonraya bırakıldı.

Agent talimatları kullanıcı kapsamı dışında bırakıldığı için değiştirilmedi. Oralardaki eski yolların karşılığı `ortak/raporlar/belge-esleme.md` belgesindedir. Yeni scope, bu oturumdaki açık kullanıcı kararıdır; eski yedi faz zorunluluğu diye geri çevrilmez.

Bu yeniden düzenleme için `.orchestrator/runs/three-phase-docs-20260922` kullanılır. Git commit/push istenmedi. Run sonucundaki kontroller belge/taşıma doğrulamasıdır, ürünün çalıştığı iddiası değildir.

**Kapsam kararı — Çağlar:** Build kararı, MVP/PRD önerisi, geliştirilecek ürünün özellikleri ve geliştirme yol haritası mevcut üç fazın hiçbirine dahil değildir. Bunlar projenin sonraki aşamasıdır; yönetici Çağlar tarafından daha sonra değerlendirilip planlanacaktır. Bu aşama kanıtları, araştırma değerlendirmesini ve eksikleri raporlar. Olumlu bulgu otomatik geliştirme kararı üretmez.

## Ekip/model karar güncellemesi

Gemini 3.1 Flash Lite üç fazda seçildi; modelin web/grounding/fetch/script aracı yok. Backend kaynak erişimini yürütür. 3 bağımsız örnek/2 kaynak başlangıç eşiği nitel kontrollerle onaylandı. Batuhan yürütücü/backend ve kabul sahibi, Ayselin kaynak/veri sorunlarını çözer, Ayşenur tasarım ve backend geldikçe entegrasyon yapar. Önceki frontend'i tamamen sonraya bırakan plan bu kararla güncellendi. Ayrıntı ortak/RULES.md, kişi dosyaları ve faz kontrol rehberlerinde. Bu güncellemenin run kaydı team-ai-planning-20260922; uygulama ve canlı test yapılmadı.

Ana backend dili kullanıcı kararıyla Python olarak kesinleşti. Framework, Python sürümü ve doğrulama kütüphanesi henüz seçilmedi.

Son teknoloji onayı: FastAPI/Pydantic, PostgreSQL, kalıcı ham dosya, Celery/Redis, Docker Compose, Next.js/REST/polling. Genel kayıt açık. Çağlar anahtarı Batuhan’a verecek. Olumlu sonuç etiketi ve positive_findings sözleşmesi onaylandı. Dağıtım Çağlar’ın makinesinde push/komutla tetiklenecek; yöntem ve hedef makine henüz görüşülüyor, kurulum yapılmadı.

Planlama teslimi ortak/teslim.md ile tamamlandı. Son hedef: Hetzner backend, private GitHub, Vercel frontend; test API erişimini/adresini Çağlar sağlayacak. Sunucu/runner ve Vercel kurulumu sonraki ayrı çalışma; bu turda bağlantı/deployment yapılmadı.
