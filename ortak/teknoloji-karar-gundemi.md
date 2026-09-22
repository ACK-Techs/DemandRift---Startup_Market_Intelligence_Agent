# Teknoloji kararları — onay durumu

Kullanıcı paket önerisini genel kayıt ve anahtar paylaşımı düzeltmeleriyle onayladı. Bu kayıt kurulum/çalışan ürün beyanı değildir.

| Konu | Karar | Durum |
|---|---|---|
| Backend | Python + FastAPI + Pydantic | onaylandı |
| Yapı | Tek backend projesi; fikir/veri/rapor modülleri; ayrı worker süreci | onaylandı |
| Veritabanı | PostgreSQL | onaylandı |
| Ham içerik | Kalıcı dosya alanı; DB’de referans/hash; gerekirse S3 | onaylandı |
| İş kuyruğu | Celery + Redis; kalıcı araştırma durumu PostgreSQL | onaylandı |
| Frontend | Mevcut Next.js + REST API + ilk sürümde periyodik durum sorgulama | onaylandı |
| Kayıt | Genel kayıt; davet zorunluluğu yok; oturum ve proje yetkisi gerekli | onaylandı |
| Model | Üç fazda Gemini 3.1 Flash Lite; model web/URL/grounding/script araçları yok | onaylandı |
| Anahtar | Çağlar Batuhan’a verecek; sadece backend/worker yapılandırmasında tutulacak | onaylandı |
| Kurulum | Docker Compose | onaylandı |
| Test | Yerelde kayıtlı veri; ortak ortamda entegrasyon; canlı/model testleri ayrı tetiklenir | onaylandı |
| Olumlu çıktı | Olumlu bulgular — yönetici değerlendirmesi bekliyor; Build/MVP yok | onaylandı |
| Kanıt tabanı | 3 bağımsız örnek/2 kaynak ve nitel koşullar | onaylandı |
| Backend dağıtımı | Hetzner + private GitHub; push/manuel workflow ile build/test güncelleme | planlandı; kurulum sonraki çalışma |
| Frontend yayını | Vercel; Çağlar test backend API erişimini/adresini sağlayacak | onaylandı; bağlantı sonraki çalışma |

## Sonraki kurulumda alınacak bilgiler

Hetzner erişimi/işletim sistemi, private repository erişimi ve deployment branch’i, runner izolasyonu, API adresi ve Vercel proje/domain bilgileri kurulum aşamasında alınacak. [Dağıtım ve ortam planı](dagitim-ve-ortam-plani.md) teslimleri tanımlar. Şimdi kurulum yapılmaz; planlama teslim edilir.

Kaynak/derinlik/alan eşikleri Batuhan ve Ayselin’in denemelerinden; paket sürümleri, auth ayrıntısı, ORM/migration ve saklama süreleri uygulama hazırlığından gelecek. Bu ayrıntılar yeni teknoloji onayı varmış gibi doldurulmaz.
