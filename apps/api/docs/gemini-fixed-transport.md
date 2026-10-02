# Sabit Gemini HTTP taşıması

`GeminiTransport` yalnız sabit Developer veya Vertex Express endpoint'ine
gönderim yapar. Varsayılan canlı erişim kapalıdır. `TransportRequest` operation,
pinlenmiş `GeminiPolicy`, kanonik bounded JSON bytes ve mutlak monotonic deadline
taşır. URL, header, proxy, retry veya callback kullanıcı/model çıktısından alınmaz.
Anahtar yalnız backend runtime parametresi ve `x-goog-api-key` header'ında kullanılır;
query, DTO, observation, repr ve hata mesajına konmaz.

HTTPX TLS doğrulaması açıktır; ortam proxy'si, redirect ve otomatik retry kapalıdır.
Hem client hem native transport ortam güvenini kapatır; SSL_CERT_FILE/DIR
değerleri TLS trust store'u değiştiremez. R1 bu iki fiili inceleme hatasının
kanıtını korur ve ayrıca native constructor kontrolüyle kapatır.
Toplam deadline bağlantı, header ve tüm stream süresini kapsar; her chunk'ta
yenilenen bir süre değildir. Response identity encoding ile ham stream okunur.
Read işi aynı toplam sürenin en fazla son 20ms veya kalan sürenin %10'unu
kapanış için bırakır. Response ve client kendi ayrı bounded task'ında kapanır; timeout
sonrası context exit içinde sınırsız await yapılmaz. Süresi biten cleanup iptal
edilir ve join edilmez; cancellation-aware HTTPX cleanup kontrolüyle task sonlanır.
R2, iki cancellation-aware kapanışın birlikte takıldığı fiili R1 hatasını korur.
Her iki task ayrı iptal edilir; response iptalinden sonra bir finally bloğunda
iptal edilmemiş yeni client kapanışı başlatılmaz. Her ikisi birlikte takıldığında
deadline ve dış cancellation kontrolleri pending task kalmadığını doğrular.
Transport uncooperative Python test coroutine'ini zorla sonlandırdığını iddia etmez.
Belleğe alınan body policy byte sınırını aşmaz. `received_bytes` alınan ham payload
byte'ıdır; sınırı aşan son chunk da ölçülür. Giden request byte sayısı bu metrik
değildir; iki yönü kapsayan bütçe için ayrıca sözleşme revision gerekir.

`CompleteObservation` bütün bounded body'nin geldiğini bildirir; HTTP200,
bilinen usage, geçerli model cevabı veya başarılı iş anlamına gelmez. 3xx/4xx/5xx
bütün yanıtları da complete olabilir, redirect izlenmez. Consumer accounting ve
çıktı doğrulamasını ayrıca yapar. `UnknownObservation` deadline, cancellation,
timeout, network, encoding, oversize ve invalid response durumlarında status,
alınmış bytes, geçen süre ve partial SHA256'yı korur. Ham response bytes repr
dışındadır. HTTP exception veya request bilgisi hata metnine taşınmaz.

Cancellation observation'ı alan consumer kalıcı unknown kaydını yapıp kendi
cancellation davranışını sürdürmelidir. Bu modül ledger reserve/dispatch, lease,
scope, token upper bound veya settlement yetkisi üretmez. Canlı consumer bu
zorunlu kapıları geçmeden `live_enabled=True` açamaz. `httpx.MockTransport`
enjeksiyonu yalnız ağ kullanmayan fixture testleri içindir; canlı enablement ile
birleştirilemez. Gerçek anahtar/model/format, kalıcı count receipt, giriş sınırı,
atomik job/budget dispatch, restart/recovery ve BE05 final kabulü açık kalır.
