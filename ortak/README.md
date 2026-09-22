# Ortak çalışma belgeleri

**Kapsam kararı — Çağlar:** Build kararı, MVP/PRD önerisi, geliştirilecek ürünün özellikleri ve geliştirme yol haritası mevcut üç fazın hiçbirine dahil değildir. Bunlar projenin sonraki aşamasıdır; yönetici Çağlar tarafından daha sonra değerlendirilip planlanacaktır. Bu aşama kanıtları, araştırma değerlendirmesini ve eksikleri raporlar. Olumlu bulgu otomatik geliştirme kararı üretmez.

22 Eylül 2026 tarihli üç aşamalı düzen esas alınır. Eski yedi faz numarası yeni faz numarasıyla aynı değildir.

| Belge | Ne için kullanılır? |
|---|---|
| [Mimari ve kararlar](mimari-ve-kararlar.md) | Ortak bileşenler, seçilen yaklaşım, aday teknolojiler ve açık kararlar |
| [Veri sözleşmeleri](veri-sozlesmeleri.md) | Aşamalar arası veri anlamları, kimlikler, sürümler ve hata ayrımı |
| [Kalite ve test ilkeleri](kalite-ve-test-ilkeleri.md) | Test türleri, kanıt kaydı, ortak kabul kuralları |
| [Ekip ve teslim](ekip-ve-teslim.md) | Üç kişilik ekip, bağımlılıklar, teslim ve durum takibi |
| [Ayselin araştırması](arastirmalar/ayselin/README.md) | Kategori, kaynak ve sorgu tasarımının tarihsel çalışması |
| [Pazar araştırması](arastirmalar/pazar-2026-08-16.md) | Tarihli rakip/pazar araştırması; ürün runtime verisi değildir |
| [Kaynak verisinin mevcut durumu](raporlar/kaynak-verisi-durumu.md) | Çekilmiş kayıtlar, örnek veriler ve kanıt sınırları |
| [Eski–yeni belge eşlemesi](raporlar/belge-esleme.md) | Eski içeriğin yeni sorumlusu ve arşiv yolu |
| [Taşıma kaydı](raporlar/dosya-tasima-kaydi.json) | Eski/yeni yollar ve arşivlenen dosyaların hash'leri |

Her fazda altı belge vardır: hazırlık, entegrasyon, teknolojiler/kararlar, test planı, veri sözleşmeleri, görev/teslim planı. Fazlara özgü alanlar kendi belgelerinde; ortak kurallar burada tek kez tutulur. `tests/` altındaki yeni senaryo dosyaları **planlı değerlendirme girdileridir**; çalışan backend veya geçmiş test başarısı sayılmaz.

Mevcut kaynak laboratuvarı kullanıcı isteğiyle [Faz 1 altında](../faz-1-fikir-ve-arastirma/veri-laboratuvari/README.md) tutulur. Bu fiziksel yerleşim, fikir sınıflandırma çağrısının web tarayacağı anlamına gelmez. Faz 1 kaynak hazırlığını ve veri doğrulamasını sahiplenir; Faz 2 çalışma anında aynı araçları çağırır.

API kullanım/dağıtım tercihi ve testlerin hangi makine/sunucuda yürütüleceği bu pakette karara bağlanmamıştır. Frontend tasarım/bağlantı görevleri Ayşenur dosyası ve ortak frontend rehberindedir.

## Güncel çalışma dosyaları

- [RULES — model, yetki ve kapsam](RULES.md)
- [Kanıt yeterliliği ve karar politikası](kanit-yeterliligi-ve-karar-kurallari.md)
- [Batuhan görev takibi](gorevler/batuhan.md)
- [Ayselin görev takibi](gorevler/ayselin.md)
- [Ayşenur görev takibi](gorevler/aysenur.md)
- [Frontend eksikleri ve bağlantı planı](frontend-entegrasyon-ve-eksikler.md)
- [Teknoloji görüşmesi için açık kararlar](teknoloji-karar-gundemi.md)

[Hetzner backend ve Vercel frontend — sonraki kurulum planı](dagitim-ve-ortam-plani.md).

[Planlama ve görev teslim özeti](teslim.md). Kurulum/deployment sonraki ayrı çalışmadır.

[Calendar içe aktarma paketi](calendar-import/README.md): 22 görev, üç kullanıcıya atanmış toplu ve kişi bazlı JSON dosyaları. 22 Eylül 2026 tarihinde canlı Calendar’a aktarıldı (22 görev).
