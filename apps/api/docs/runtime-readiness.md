# Temel runtime readiness

`/health` process liveness ve revision'dır. Yeni dependency probe PostgreSQL migration head, queue bağlantısı ve aynı revision worker'ın süreli pulse kaydını ayrı değerlendirir. `ready` bu dört bileşenin erişimini gösterir; `research_execution=unconfigured` gerçek pipeline handler'ının henüz kurulmadığını açık tutar. Ürün tamamlanması veya final 87 kabulü değildir.

Worker yalnız private FILE application DSN ve broker ayarıyla açılır. Startup uygulama rolünün RLS/DDL/bütçe yetkilerini ve kabul edilen migration head'i kontrol eder. Admin DSN veya Gemini değeri worker health yanıtına/log'una girmez. Child process, fork öncesi DB/Redis bağlantılarını yeniden kullanmaz. Tek JSON wake task ve kapalı production handler davranışı korunur.

Worker hazır sinyalinden sonra 10 saniyede bir private Redis namespace'inde 30 saniye TTL'li pulse yazar. Pulse revision, UUID instance, pid, UTC timestamp ve DB readiness taşır; kullanıcı/proje/araştırma/secret/prompt taşımaz. Okuyucu bounded UTF-8 JSON, duplicate keys, exact alanlar, primitive types, TTL, timestamp ve revision denetler. Redis veya DB hatası güvenli degraded durumudur. Son pulse'ın bitmesini bekleyen kontrol, anlık worker ölümü kabulü sayılmaz; restart/recovery gerçek servis testleriyle ayrıca doğrulanacaktır.

API router ve dört servisli Compose bağlantısı bu modüllerin ayrı entegrasyon kapısındadır. Gerçek host UID/mount, container restart, native worker process ve local browser→Hetzner kanıtları ayrıca gerekir. Henüz handler olmadığı için health bilgisi araştırma başlatma yetkisi üretmez.

## Sınırlı bağımlılık kontrolü revizyonu

İlk native kontrolün gerçek libpq handshake'i 16 saniyeyi aştı; başarısız inceleme korunur. Revizyon, application pool'u kullanmadan fresh kısa statement/lock timeout'lu probe açar, aynı restricted role ve head008 denetimini yapar ve her bağlantıyı kapatır. Redis ping/TTL/body tek pipeline round trip'te okunur; retry ve ek CLIENT metadata komutları kapalıdır. Belirsiz/hatalı dependency sonucu ready değildir. Normal tek host bağlantı, native handshake/statement takılması ve queue soket takılması 15 saniyelik Compose penceresinden önce güvenli degraded döner; DNS çözümleme ve gerçek Linux ağ arızaları ayrı host kabulünde doğrulanır. Arka plan probe/thread veya otomatik reconnect retry oluşturulmaz.

CP44/45 Linux CI mevcut auth policy testinin beklediği database configuration exception yerine private FILE exception aldığı için başarısız oldu. Production startup eksik/uygunsuz application FILE credential'ını güvenli `DatabaseConfigurationError` olarak çevirir; secret içeriği ve environment fallback yoktur. CI başarısız geçmişi korunur ve güncel SHA koşusu ayrıca geçmelidir.

İkinci bağımsız native kontrol bounded503 sonrası başarısız PG socket'in GC'ye kadar açık kaldığını buldu; önceki no-orphan beyanının başarısız kanıtı korunur. ReadinessR2, public native start/poll/explicitfinish producer revizyonuna bağlıdır. Socket peer EOF/RST ve FD kapanması normal GC'ye güvenmeden ayrı doğrulanır; önceki pozitif TTL/prefork/recovery senaryoları bu FAIL'i iptal etmez.

ReadinessR3, successful authentication sonrasında ACK alan ama query sonucunu göndermeyen peer ile doğrulanan 16.006 saniyelik yeni FAIL'i kapatan producerR2'ye bağlıdır. Fresh DB probe'un bütün bağlantı/initialization/rol/head native wait'leri tek monotonic üç saniyelik deadline paylaşır; deadline sonrası socket doğrudan kapanır. Redis aynı iki saniyelik, tek pipeline sınırını korur. Continuous partial result da süreyi yenilemez. Normal DNS tamamlandıktan sonraki bu kontrol, Linux DNS ve gerçek Hetzner/container arıza kabulünün yerine geçmez.
