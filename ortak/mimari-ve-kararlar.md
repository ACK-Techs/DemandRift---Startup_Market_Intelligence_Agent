# Ortak mimari ve kararlar

**Kapsam kararı — Çağlar:** Build kararı, MVP/PRD önerisi, geliştirilecek ürünün özellikleri ve geliştirme yol haritası mevcut üç fazın hiçbirine dahil değildir. Bunlar projenin sonraki aşamasıdır; yönetici Çağlar tarafından daha sonra değerlendirilip planlanacaktır. Bu aşama kanıtları, araştırma değerlendirmesini ve eksikleri raporlar. Olumlu bulgu otomatik geliştirme kararı üretmez.

## Amaç ve mevcut durum

Ürün, fikri araştırma planına dönüştürür; kaynaklardan veri toplar ve hazırlar; gerekçeli karar raporu üretir. Bugün örnek verili `apps/web` arayüzü ve bağımsız Python kaynak araçları vardır. Aşağıdaki backend akışı **hedef tasarımdır**, uygulanmış servis değildir.

```text
Fikir
  → Faz 1: brief, kategori, araştırma soruları, kaynak/sorgu planı
  → Faz 2: script/connector → ham veri → temiz veri → kaynaklı bulgular
  → Faz 3: yeterlilik kontrolü → karar AI → doğrulanmış karar raporu
                     ↑                         |
                     └── izinli ek araştırma ──┘
```

İkincil veri boşluğu aynı Faz 2 hattına döner; ikinci bir crawler sistemi kurulmaz. Müşteri görüşmesi, pilot veya gerçek ödeme doğrulaması gerektiren boşluklar web döngüsüne sokulmaz.

## Karar durumu

| Konu | Durum / yaklaşım |
|---|---|
| Ürün düzeni | Üç faz ve ortak klasör; eski yedi faz aktif plan değildir |
| İlk fikir akışı | Doğrudan LLM çağrısı, yapılandırılmış JSON, backend doğrulaması, kısa netleştirme |
| Kategoriler | Kontrollü yedi kategori; bağlama göre ek kategori/dikey; sorgular dinamik |
| Kaynak seçimi | Yalnız tanımlı kaynak yetenekleri ve doğrulanmış sorgu/erişim yolları |
| RAG / LangGraph | İlk fikir aşamasının önkoşulu değil; sonradan ölçülmüş ihtiyaçla değerlendirilebilir |
| Ana backend dili | Python + FastAPI + Pydantic; tek backend projesi, üç ayrı iş modülü; kaynak işleri ayrı worker sürecinde |
| Mevcut veri araçları | Python; yeni backend ile sürümlü girdi/çıktı adaptörü üzerinden çalıştırılacak |
| Veritabanı / ham veri | PostgreSQL; ham içerik başlangıçta kalıcı dosya alanında, DB’de dosya yolu/hash; gerektiğinde S3 uyumlu depolama |
| Uzun araştırma yürütücüsü | Celery + Redis; araştırmanın kalıcı durumu PostgreSQL’de. Retry/iptal/devam ve tekrar güvenliği uygulamada kurulacak |
| Şema | Pydantic doğrulaması ve JSON Schema/OpenAPI sözleşmeleri; frontend aynı sözleşmeyi tüketir |
| AI seçimi | Üç faz için Gemini 3.1 Flash Lite; araçsız verilen-veri analizi; prompt/model sürümü ve kalite/maliyet kaydı |
| Frontend | Ayşenur tasarım eksiklerini giderir; her fazın backend çıktısı hazır oldukça sayfaları bağlar |

Kullanıcı kararıyla üç fazda da Gemini 3.1 Flash Lite ile başlanır. Yüksek hacimli bulgu çıkarımı ile son sentez için farklı model seçimi kalite/maliyet ölçümü sonrasında yapılır; çok ajanlı ürün runtime'ı başlangıç şartı değildir.

## Ortak bileşenlerin sorumluluğu

- **Uygulama API'si:** kullanıcı/proje bağlamı, girdi doğrulaması, kayıt, araştırmayı başlatma/durum/iptal/sonuç uçları. Rota adları henüz çalışan API değildir.
- **Araştırma yürütücüsü:** plan snapshot'ı, kaynak işleri, durum geçişleri, geçici hatada sınırlı retry, aynı işin tekrarında çift kayıt/harcamayı önleme.
- **Kaynak kataloğu:** kategoriler, araştırma niyetleri, diller/pazarlar, alanlar, arama/fetch yolu, izin, sağlık, limit ve kayıt sürümü. Erişim snapshot'ı üretim connector onayı değildir.
- **Python adaptörü:** izinli script adını seçer, yapılandırılmış parametreleri iletir, çıkış kodu/stdout/sonuç dosyasını ortak sözleşmeye dönüştürür. Kullanıcı metnini shell komutu haline getirmez. Parametrelerin hangi scriptte desteklendiği ayrı eşlenir.
- **AI adaptörü:** görev + girdi + şema; timeout, sınırlı retry, schema hatası, prompt/model sürümü ve kullanım kaydı. Kaynak içeriği talimat sayılmaz.
- **Veri katmanı:** ham yanıt, normalizasyon, segment, bulgu, alıntı ve karar farklı sürümlü kayıtlardır. Tek bir özete indirgenip kaynakları kaybedilmez.
- **Bütçe:** kaynak/sorgu/sayfa/kayıt/istek/byte/süre/token sınırları ve toplam çalışma bütçesi. Paralel işler aynı sınırı paylaşır; durunca kalan boşluk raporlanır.
- **Alıntı doğrulayıcı:** birebir metin, segment, hash/sürüm ve URL ilişkisinin doğruluğunu kontrol eder.
- **İz kayıtları:** kimlik, faz, işlem, model/connector sürümü, süre, maliyet, hata ve sonuç. Hassas ham içerik varsayılan log malzemesi değildir.

## Kaynak toplama profili

Her profil: `source_id`, kategori/niyet uyumu, izinli yöntemler, alınacak alanlar, sorgu dili, tarih aralığı, sayfalama, limitler, çıktı türleri, veri saklama koşulları, durma ve fallback kurallarını tanımlar. API, ana sayfa, sitemap, RSS, arşiv ve yorum erişimi ayrı yeteneklerdir.

Konuşmadaki kaynak başına 30/150 kayıt sayıları yalnız örnektir. Gerçek hızlı/detaylı profiller veri kalitesi ve maliyetle kalibre edilecek. Daha çok kayıt otomatik olarak daha iyi araştırma değildir; tekrar, çeşitlilik ve soruların kapsanması izlenir.

## Gerekli çalışma davranışları

1. İş durumunu kaydet; sunucu/worker yeniden başladığında nerede kaldığı bilinsin.
2. Aynı girdi ve işlem kimliğinin tekrarı önceki sonucu güvenle kullanabilsin; bilinmeyen sonucu yeniden çağırmadan uzlaştır.
3. Geçici ağ hatası ve rate limit için sınırlı retry; geçersiz şema, izin engeli ve yanlış kimlik doğrulama için kör retry yok.
4. Tek site hatası bütün araştırmayı yok etmesin; kısmi sonuç ve kapsam açığı görülsün.
5. Ham veriyi koru; temizleme/model sürümü değiştiğinde yeni türetilmiş sürüm üret.
6. İptal ve bütçe sonrasında yeni dış çağrı başlatma; çalışan işin sonucu ve harcamasını kaydet.
7. Kullanıcı/proje erişim sınırını API, veri deposu ve sonuç erişiminde koru.
8. Dış HTTP erişiminde mevcut laboratuvarın origin/DNS/redirect/robots/byte/MIME sınırlarını taşıma sırasında zayıflatma.

## İhtiyaç oluştuğunda değerlendirilecekler

SimHash/MinHash/LSH yakın tekrar adayları; BM25/TF-IDF/pg_trgm ilgililik; çok dilli embedding/pgvector; HDBSCAN; izole Playwright; gelişmiş karar stabilitesi ve kalibrasyon; paylaşılabilir public cache; telemetry, yedek/geri yükleme ve ölçek profilleri. Eski kapsamdan silinmediler; uygulanmış veya her araştırmada zorunlu sayılmıyorlar. Önce basit karşılığı ve hata örnekleri ölçülür.

Kaynak aileleri de korunur: açık web/resmî ürün siteleri, geliştirici toplulukları, marketplace/review, sosyal/açık topluluk, domain/web izi, reklam/trend/funding/jobs/maps, kamu/akademik/regülasyon/patent ve dikey paketler. Her araştırmada hepsi çalıştırılmaz; izin ve veri ihtiyacına göre seçilir.

## Onaylanan kurulum ve erişim kararları

- Mevcut Next.js korunur; REST API, ilk sürümde periyodik durum sorgulama.
- Genel kullanıcı kaydı açık; davet şartı yok. Kullanıcı oturumu ve proje bazlı erişim kontrolü gerekli. Kayıt açılması başkasının projesini görme yetkisi vermez.
- Çağlar Gemini API anahtarını Batuhan’a verecek. Anahtar backend/worker çalışma zamanı yapılandırmasında; frontend, repo ve Docker image katmanlarında bulunmaz.
- Hetzner üzerinde Docker Compose: API, worker, Redis ve PostgreSQL. Frontend Vercel’de yayınlanacak; yerel frontend container opsiyonel. DB/ham veri kalıcı alanları image rebuild sırasında silinmez.
- Yerelde kayıtlı verilerle test; ortak ortamda gerçek entegrasyon. Her push’ta offline kontroller; canlı kaynak/model testleri ayrıca başlatılır.
- Olumlu sonuç etiketi: **Olumlu bulgular — yönetici değerlendirmesi bekliyor**; sözleşme değeri `positive_findings`, yönetici değerlendirmesi zorunlu. Build/MVP kapsam dışı.
- Hedef Hetzner, repository private, frontend Vercel. Push veya Batuhan’ın manuel workflow tetiklemesiyle Hetzner’de build/test ortamını güncelleme planlandı. Test API erişimi/adresini Çağlar sağlayacak. [Dağıtım ve ortam planı](dagitim-ve-ortam-plani.md) sonraki kurulumun teslimlerini tanımlar; kurulum Çağlar ile ayrıca yapılacak.

## Açık kalan uygulama ayrıntıları

Hedef Hetzner ve frontend Vercel olarak kesinleşti. İşletim sistemi/erişim, deployment branch’i, runner izolasyonu ve tam API/Vercel adresleri sonraki kurulumda alınacak; planlama teslimi için engel değil. Python/paket sürümleri, auth uygulama ayrıntısı, başlangıç kaynak seti, registry biçimi, limitler, veri saklama süreleri ve kalite eşikleri ilgili görevlerde somutlaştırılacak. ORM/migration kütüphanesi henüz seçilmedi. Bu kararlar mevcut backend’in uygulanmış olduğu anlamına gelmez.
