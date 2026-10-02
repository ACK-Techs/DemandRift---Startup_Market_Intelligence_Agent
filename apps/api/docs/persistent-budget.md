# Kalıcı ortak bütçe ledger temeli

BE-05 ledger alt teslimi native migration `20261001_0005` ile dört tablo ekler:
`budget_suites`, owner/research kapsamlı `budget_accounts`, `budget_attempts` ve
append-only `budget_journal`. Eski 0001–0004 migration'ları değişmez. API startup
aynı açık required head'i denetler; otomatik migration veya privileged app rolü yok.

Suite yalnız operator/migration rolü tarafından kullanıcının sabit yetkisiyle
oluşturulur. Uygulama rolünden mevcut tablo yetkileri açıkça geri alınır; yalnız account,
attempt ve journal tablolarında owner RLS ile SELECT alır. Global suite
tablosunu okuyamaz. Startup, current/session rolü ve bütün MEMBER rollerin
tablo/kolon yazma yetkilerini denetler; NOINHERIT fakat SET ROLE ile erişilebilen
yazıcı üyelikleri de reddedilir. Global suite tablo/kolon SELECT yetkisi de aynı
denetimde reddedilir. Yazma işlemleri
`demandrift_budget_operate` scoped RPC üzerinden yapılır. SECURITY DEFINER
fonksiyonu PUBLIC execution'a kapalıdır, schema nitelikleri açıktır ve
search_path `pg_catalog, pg_temp` olarak sabittir. Caller'ın transaction-local
owner UUID'si null-safe tam scope ile doğrulanır. Account/attempt/journal FORCE
RLS ve composite foreign key taşır. Kullanıcıya account snapshot'ı verilir;
başka tenant harcaması global suite toplamından çıkarılmaz.

Her RPC kısa transaction içinde Suite → account → attempt kilit sırasını izler.
Dış ağ çağrısı bu transaction'ın içinde yapılmaz. Reserve altı boyutu ve ortak
aktif kapasiteyi atomik tutar. Aynı server attempt UUID, fingerprint, reservation
ve metadata aynı kaydı döndürür; değişen replay reddedilir. Reservation metadata
yedi dolu, sabit alan taşır: kind, operation_version, provider, model,
prompt_version, schema_version ve pricing_version. Kaynak adaptörü model/prompt
için açık not_applicable sürümü kullanır; offline fixture sürümleri gerçek
provider doğruluğu kanıtı değildir. Version/receipt etiketleri yalnız 1–256 ASCII kimlik karakteri taşır; kontrol
karakterleri veya Unicode whitespace kabul edilmez. Receipt
response_id/model_version/usage_version alanları dolu olmalıdır; provider alanlarının gerçek anlamı adapter kabulünde
ayrıca doğrulanır. Direct attempt
INSERT/UPDATE/UPSERT yetkisi verilmediği için trigger side effect veya farklı
kilit sırası yoluyla ikinci debit açılamaz.

`reserved → dispatched` geçişi yalnız bir kez `dispatch_permitted=true` döndürür.
Caller bu izni yalnız o gönderim için kullanır. İlk gönderim suite/account
saatini DB clock_timestamp ile başlatır; kilit bekleme süresi deadline kontrolüne
katılır. Sonraki kayıt, retry, yeni owner, restart veya account replay süreyi
sıfırlamaz. Gönderim commit'i ile gerçek ağ iletimi arasındaki crash, sağlayıcının
idempotency garantisi olmadığı için otomatik tekrar gönderime izin vermez.

`dispatched → held_unknown` tüm reservation ve aktif kapasiteyi tutar. TTL,
worker ölümü veya cancellation sonucu bilinmeyen harcamayı iade etmez. Bilinen
receipt `settled` olur: gerçekleşen kaynak/token/picousd maliyet toplamları yazılır,
kalan reservation ve aktif slot bırakılır. Her gönderilmiş deneme bir request
harcar; geçersiz içerik veya model schema başarısızlığı bu harcamayı geri almaz.
Receipt replay ancak aynı actual/metadata ile idempotenttir. Measured usage
reservation'ı aşarsa gerçek değer journal/attempt/toplamlarda korunur, `overrun`
olayı yazılır ve hem hesap hem global suite yeni gönderimlere kapanır. Bu sonuç
commit edildikten sonra caller başarısız analiz olarak bildirebilir; transaction'ı
rollback ederek bilinen harcama kaybedilmez. Büyük aggregate sayaçlar numeric JSON
olarak korunur; taşan bir gerçek toplam küçük değere clamp edilmez.

Account cancellation önce yeni gönderimleri kapatır, yalnız henüz gönderilmeyen
reservation'ları aynı transaction içinde bırakır. Gönderilmiş veya bilinmeyen
attempt sonradan bilinen usage ile uzlaştırılabilir. Journal state değişimlerini
server saatinde yazar; duplicate çağrı aynı olayı ikinci kez yazmaz. Policy,
başlangıç saati, harcama ve cancellation geri alınamaz.

Bu temel provider çağrısı, worker, HTTP uç noktası veya plan onayı açmaz. Faz 1
hazırlığı server-created ResearchRecord'a bağlanır; sonraki consumer teslimi
araştırma başlamadan önce tam approved plan/run/fingerprint/version bağını ve
onaylanan plan tavanlarını eklemek zorundadır. Ledger'ın varlığı araştırma
başlatma yetkisi değildir. Gerçek anahtar/model ve canlı bütçe kabulü, Hetzner
restart/restore/rollback ve 87 final senaryo ayrı açık kapılardır. Offline testler
ayrı sentetik suite kullanır ve kullanıcının canlı 30 dakikasını tüketmez.
