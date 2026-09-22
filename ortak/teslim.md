# Planlama ve görev teslimi

**Durum: planlama paketi teslim edildi.** Backend geliştirme, ekip görevlerinin uygulanması, test çalıştırma ve deployment tamamlandı anlamına gelmez.

| Teslim | İçerik / giriş |
|---|---|
| Üç faz | Her fazın hazırlık, entegrasyon, teknoloji, sözleşme, test ve görev belgeleri ile kontrol/kabul rehberi |
| AI ve ürün sınırı | [RULES](RULES.md): üç fazda Gemini 3.1 Flash Lite; model site aramaz/veri çekmez; backend scriptleri alımı yapar |
| Kanıt yeterliliği | [Policy v1](kanit-yeterliligi-ve-karar-kurallari.md): 3 bağımsız örnek/2 kaynak ve nitel koşullar |
| Batuhan | [Yürütücü/backend görevleri](gorevler/batuhan.md); ekip teslimlerini kontrol ve kanıtlı düzeltme/yeniden test |
| Ayselin | [Kaynak/veri sorunları](gorevler/ayselin.md); düzeltme, farklı yol ve önce/sonra kanıt |
| Ayşenur | [Tasarım/API görevleri](gorevler/aysenur.md); backend geldikçe ekran bağlantısı; [koddan çıkarılmış eksikler](frontend-entegrasyon-ve-eksikler.md) |
| Faz 1 kontrol paketi | [Kategori/site/sorgu/veri rehberi](../faz-1-fikir-ve-arastirma/docs/kontrol-ve-kabul-rehberi.md); 30 fikir ve 30 boş sonuç takip satırı |
| Faz 2–3 kontrol paketi | Kendi docs/kontrol-ve-kabul-rehberi.md belgeleri; Faz 2’de 24, Faz 3’te 33 planlı davranış senaryosu |
| Mimari | [Onaylı kararlar](mimari-ve-kararlar.md): Python/FastAPI/Pydantic, PostgreSQL, kalıcı ham dosya, Celery/Redis, Docker Compose, Next.js/REST/polling |
| Kayıt/anahtar | Genel kayıt açık; proje erişimi denetlenir. Çağlar Gemini anahtarını Batuhan’a verecek; sırlar backend/worker’da |
| Ortam planı | [Hetzner backend + Vercel frontend](dagitim-ve-ortam-plani.md); private GitHub; push/manuel tetikle build hedefi |

## Ekibin başlayacağı sıra

Batuhan fikir/kategori/sorgu/backend ve ilk kaynak denemeleriyle başlar. Ayselin bildirilen veri sorunlarını çözer; Batuhan yeniden kontrol eder. Ayşenur tasarım eksiklerini giderir ve her backend teslimi geldikçe ilgili ekranı bağlar. Faz 2 ve Faz 3 aynı geri bildirim/kabul döngüsünü kullanır. İlk test ortamı hazır olana kadar mock/fixture hazırlığı gerçek entegrasyon kabulü sayılmaz.

## Çağlar ile sonraki ayrı çalışma

Hetzner bağlantısı ve Docker ortamı; private repository erişimi ve deployment branch’i; runner/otomatik build; API HTTPS adresi; Vercel repo/proje ve ortam ayarları; frontend/backend bağlantısı ve gerçek ortam kabulü. Bunlar bu planlama tesliminde çalıştırılmadı. Gerekli erişim/URL bilgileri o çalışma başlarken topluca alınacak.

Paket sürümleri, ORM/migration kütüphanesi, auth ayrıntıları, kaynak limitleri, güncellik/saklama ve etiketli kalite eşikleri Batuhan’ın ilgili hazırlık görevlerinde somutlaştırılacak; açık olmaları tamamlanmış uygulama gibi gizlenmez. Onaylı kapsam veya maliyet tercihi değişirse Çağlar’a iletilir.

Araştırılan fikir için Build/MVP/PRD ve sonraki ürün/deney planlaması kapsam dışıdır; yönetici Çağlar daha sonra değerlendirecek ve planlayacaktır.

## Doğrulama sınırı

Bu teslimde belge bağlantıları, görev/sözleşme tutarlılığı ve JSON senaryo kayıtları kontrol edildi. Senaryolar planned/not_run durumundadır; canlı kaynak veya model çağrısı ve ürün testi yapılmadı. Mevcut uygulama/script kodu, ham kaynak verisi ve agent talimat dosyaları bu planlama için değiştirilmedi.

[Calendar içe aktarma paketi](calendar-import/README.md): 22 görev, üç kullanıcıya atanmış toplu ve kişi bazlı JSON dosyaları. 22 Eylül 2026 tarihinde canlı Calendar’a aktarıldı (22 görev).
