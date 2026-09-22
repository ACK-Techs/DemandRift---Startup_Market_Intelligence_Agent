# Ürün kuralları — onaylanan kapsam

Bu belge 22 Eylül 2026 tarihli kullanıcı kararlarını toplar. Tarihsel planlardaki farklı model, ekip ve Build/MVP anlatımları aktif gereksinim değildir. Kurallar planlama gereksinimidir; bugün çalışan bir backend kontrolü olduğu iddia edilmez.

## AI modeli ve yetki sınırı

1. Faz 1, Faz 2 ve Faz 3 için başlangıç modeli **Gemini 3.1 Flash Lite**. Resmî API model kimliği ve erişim yöntemi uygulama öncesi doğrulanacak; kullanıcı seçimi burada bir SDK/model-ID iddiasına çevrilmez.
2. Faz 1: sohbet, fikir netleştirme, kategori, araştırma sorusu ve anahtar kelime/sorgu metni hazırlama. Modelin sorgu yazması sorguyu çalıştırması değildir.
3. Faz 2: backend'in önceden çektiği, hazırladığı ve sınırlandırdığı veride bulgu çıkarma, ilgililik desteği ve kaynak bazlı raporlama. Deterministik temizleme/limit/alıntı doğrulaması backend'de kalır.
4. Faz 3: yalnız teslim edilen EvidenceBundle üzerinde kanıt değerlendirme ve kaynaklı rapor sentezi. Eksik veriyi model hafızasıyla tamamlamak yasaktır.
5. **Modele Google Search/grounding, URL context/fetch, tarayıcı, crawler, deep research veya script/shell çalıştırma aracı bağlanmaz.** Modelin URL görmesi, URL'yi açmasına izin vermez. Model kendi başına site araştırmaz veya veri çekmez.
6. Kaynak seçimini ve sorgu önerisini backend registry, izin, kategori, pazar ve bütçeyle doğrular. HTTP/API/RSS/arşiv/arama işleri yalnız backend'in izinli script/connector hattında yürür. Yeni araştırma önerisi otomatik araç çağrısı değildir.
7. Model değişikliği ileride aynı sabit değerlendirme setinde kalite, gecikme ve maliyet karşılaştırmasıyla yapılabilir. Model/prompt sürümleri kaydedilir; sessiz fallback/model değişikliği yoktur.
8. API anahtarı istemciye veya repoya yazılmaz. Çağlar anahtarı Batuhan’a verecek; backend/worker çalışma zamanı yapılandırmasında tutulacak, Docker image içine de gömülmeyecek. Hedef Hetzner; private GitHub erişimiyle uzaktan build, frontend Vercel olarak planlandı. Sunucu/runner/Vercel kurulumu Çağlar ile sonraki ayrı çalışmada yapılacak.

## Kanıt ve çıktı

[Kanıt yeterlilik politikası](kanit-yeterliligi-ve-karar-kurallari.md) başlangıç eşiğini tanımlar: en az 3 bağımsız kullanıcı/kurum örneği, en az 2 farklı kaynak. Sayılar tek başına yeterli değildir. Kaynak/alıntı doğrulanabilirliği, hedef kullanıcı/problem, güncellik/pazar uyumu, alternatifler ve karşıt kanıt araması ayrıca zorunludur.

Arama sonucu/sitemap alınmış içerik değildir. Erişilememesi sıfır sonuç değildir. Aynı kullanıcının tekrarları ve kopyalar bağımsız örnek değildir. Fiyat/öderdim beyanı gerçek ödeme değildir. Prompt injection kaynak talimatına dönüştürülemez. AI erişim, bütçe, şema veya kanıt kontrollerini aşamaz.

Build kararı, MVP/PRD önerisi ve araştırılan fikrin ürün geliştirme/deney planı bu üç fazın kapsamı dışındadır. **Sonraki aşamayı yönetici Çağlar daha sonra değerlendirecek ve planlayacaktır.** Olumlu bulgu geliştirme onayı değildir. Mevcut DemandRift frontend/backend bağlantısını yapmak bu kapsam yasağından etkilenmez.

## Ekip ve kabul

Batuhan proje yürütücüsü ve backend sahibidir. İlk kategori/sorgu/kaynak denemelerini yapar, Ayselin ve Ayşenur teslimlerini kontrol eder, somut düzeltme geri bildirimi verir ve yeniden testten sonra kapatır. Ayselin kaynak/veri sorunlarını giderir ve alternatifleri kanıtlarıyla teslim eder. Ayşenur tasarım iyileştirmelerini yapar ve backend hazır oldukça ekranları bağlar. Kapsam/teknoloji kararları Çağlar ile netleştirilir.

Test dosyası yazmak testin geçtiği anlamına gelmez. Her kayıt planlandı/not_run ile başlar; gerçek girdi, çıktı ve inceleme kanıtı olmadan kabul edildi yapılamaz. Ayrıntı: [ekip ve teslim](ekip-ve-teslim.md).

Ana backend dili kullanıcı kararıyla Python olarak kesinleşti. Framework FastAPI, doğrulayıcı Pydantic olarak onaylandı; Python/paket sürümleri ayrıca sabitlenecek.

Genel kullanıcı kaydı açık; davet zorunlu değil. Kullanıcı ve proje yetkisi denetlenir. PostgreSQL, Celery/Redis, Docker Compose ve Next.js/REST/periyodik durum sorgulama onaylandı. Uzaktan build tetikleme, genel kayıt yapan kullanıcılara verilen bir yetki değildir; GitHub/dağıtım yetkisi ayrı tutulur.
