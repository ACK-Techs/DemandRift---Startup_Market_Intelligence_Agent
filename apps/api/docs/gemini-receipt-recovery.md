# Native Gemini yanıtı ve bütçe kurtarma

CompleteObservation, bütün bounded incoming body'nin alınmasını ifade eder. Native
gateway bunu parsing veya usage/çıktı doğrulamasından önce private ReceiptSpool'a
yazar ve dosya/dizin fsync'i tamamlar. Header, Gemini key ve prompt spool envelope'a
girmez; canonical body yerine yalnız fingerprint ve outgoing byte sayısı saklanır.
Raw provider body, ürün çıktısına dönüştürülmeden private artifact olarak kalır.

GeminiReceiptRecovery yalnız somut native repository çiftini kabul eder. Çift aynı
Database nesnesi ve exact suite/owner/project/research kapsamını taşır. Recovery'nin
read-only native preflight'ı mevcut ve önceden bound edilmiş dispatched, held_unknown,
settled veya overrun attempt'ini arar. Missing, reserved, failed-before-dispatch ve
foreign scope burada reddedilir; admit çağrısıyla yeni ücretli izin üretilemez.
Ardından native historical admit RPC, immutable brief/job/fence, fingerprint,
reservation, prompt/schema/provider/model/pricing sürümleri ve timeout'u yeniden
doğrular. Sonucun dispatch_permitted=false olması zorunludur. Recovery HTTP transport,
Gemini key, yeni request body veya send permit kullanmaz.

Policy ve receipt record outgoing/incoming bound'ları aynı versioned reservation'a
uymalıdır. Non2xx veya malformed/eksik usage durable unknown hold ve pending raw
bırakır. Known usage bir request, exact outgoing+incoming byte ve model token/price
metrikleriyle native BudgetRepository.settle üzerinden commit edilir. ReceiptSpool
aynı attempt/reserved/actual/state sonucunu doğruladıktan sonra ack marker'ını fsync
eder. Output validator ancak bunlardan sonra çalışır. Invalid output, custom validator
hatası ve overrun known harcamayı geri almaz; overrun gerçek actual'ı ve kapalı suite'i
korur, çıktı vermez.

Settlement RPC erişimi kaybolursa tamamlanmış raw yanıt pending kalır ve successful
output verilmez. Erişim dönünce yeni connection pool/spool reader aynı attempt'i
reconcile eder. Native commit ile ack arasındaki SIGKILL, veya ack sonrasındaki
SIGKILL, restart'ta aynı known harcamayı idempotent doğrular; ikinci send/charge yoktur.
Cancel, newer brief, archive ve geçmiş deadline yeni send'i reddeder; daha önce
gönderilmiş exact attempt'in late known usage muhasebesini silmez.

Bu scope gerçek disposable PostgreSQL ve gerçek local process/SIGKILL kullanır;
provider response yalnız MockTransport'tur. Kullanıcının canlı Gemini anahtarı
okunmaz, dış API çağrısı yapılmaz ve ortak canlı suite clock'u başlamaz. Live gateway,
gerçek worker pipeline, Hetzner private mount ve browser kabulü ayrı kapılardır;
bu consumer teslimi BE05 veya 87 zorunlu ürün senaryosunun tamamlanması değildir.
