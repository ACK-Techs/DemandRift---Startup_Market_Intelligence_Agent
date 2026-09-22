# DemandRift

**Kapsam kararı — Çağlar:** Build kararı, MVP/PRD önerisi, geliştirilecek ürünün özellikleri ve geliştirme yol haritası mevcut üç fazın hiçbirine dahil değildir. Bunlar projenin sonraki aşamasıdır; yönetici Çağlar tarafından daha sonra değerlendirilip planlanacaktır. Bu aşama kanıtları, araştırma değerlendirmesini ve eksikleri raporlar. Olumlu bulgu otomatik geliştirme kararı üretmez.

Fikri araştırma planına dönüştüren, kaynaklardan veri toplayıp hazırlayan ve kaynaklı karar raporu üreten ürün.

## Üç faz

| Faz | Amaç | Başlangıç |
|---|---|---|
| 1 — Fikir ve araştırma hazırlığı | Fikir, kategori, araştırma soruları, kaynak/sorgu planı; kaynak verisi ve test hazırlığı | [Faz 1](faz-1-fikir-ve-arastirma/README.md) |
| 2 — Veri toplama ve hazırlama | Aynı scriptlerle toplama, temizleme, filtreleme, alıntılı site bulguları | [Faz 2](faz-2-veri-toplama-ve-hazirlama/README.md) |
| 3 — Karar ve rapor | Kanıt yeterliliği, gerekçe, karşıt bulgular, belirsizlik ve sonraki adım | [Faz 3](faz-3-karar-ve-rapor/README.md) |

Her fazda `docs/` altında hazırlık, entegrasyon, teknolojiler/kararlar, test, veri sözleşmeleri ve görev/teslim belgeleri; `tests/` altında değerlendirme girdileri bulunur.

## Dosya haritası

- [ortak/](ortak/README.md): ortak mimari, sözleşmeler, kalite, ekip; araştırma ve durum raporları.
- [Faz 1 veri laboratuvarı](faz-1-fikir-ve-arastirma/veri-laboratuvari/README.md): mevcut Python scriptleri, çekilmiş veriler, kaynak indeksleri ve mevcut offline testler. Eski `research/source-access-lab` buraya taşındı; iç yerleşimi korundu.
- `apps/web/`: mevcut Next.js arayüz prototipi.
- [trash/](trash/README.md): kullanımdan kaldırılan eski plan ve raporlar; silinmedi.

## Şu an ne var?

Web arayüzü örnek veri kullanıyor. Bağımsız Python erişim/arama scriptleri, kaynak kayıtları ve örnek içerikler var. Fikirden gerçek karar raporuna çalışan backend henüz uygulanmış değil. Yeni faz belgeleri ve senaryo JSON'ları planlama teslimidir; çalışan servis veya geçmiş test sonucu olarak sunulmaz.

## Ekip için okuma sırası

1. Bu README ve [ortak belgeler](ortak/README.md).
2. Atanılan fazın README'si ve altı dokümanı.
3. Fazın test planı, senaryoları ve gerçek veri örnekleri.
4. Gerekiyorsa [Ayselin araştırma referansı](ortak/arastirmalar/ayselin/README.md).

API anahtarını Çağlar Batuhan’a verecek. Yerel kayıtlı-veri testleri ve ortak entegrasyon ortamı onaylandı; Hetzner kurulumu/uzaktan build ve Vercel/API bağlantısının ayrıntıları [ortak mimari kaydına](ortak/mimari-ve-kararlar.md) göre netleştirilecek.

## Belge geçişi

22 Eylül 2026'daki kullanıcı kararıyla eski yedi faz yerine bu üç aşamalı yapı kullanılmaktadır. [Eski–yeni eşleme](ortak/raporlar/belge-esleme.md) taşınan içerikleri gösterir. Agent talimat dosyaları değiştirilmedi; içlerindeki eski belge yolları tarihsel kaldı. Eski planlara ihtiyaç olursa `trash/eski-planlar/` altında bulunur. `.orchestrator` geliştirme araçlarıdır, ürünün araştırma motoru değildir.

## Lisans

[MIT](LICENSE).

## Ekip ve uygulama kuralları

Batuhan yürütücü/backend, Ayselin veri sorunları, Ayşenur tasarım ve kademeli frontend bağlantısı. [Kişi görevleri](ortak/ekip-ve-teslim.md), [AI kuralları](ortak/RULES.md) ve [onaylı 3/2 kanıt politikası](ortak/kanit-yeterliligi-ve-karar-kurallari.md) aktif planın parçasıdır.

[Planlama teslimi](ortak/teslim.md) hazır. Backend hedefi Hetzner, frontend hedefi Vercel, repo private; ortamların kurulması ve bağlanması Çağlar ile sonraki ayrı çalışmadır.
