# Runtime secret ilk kurulum üreticisi

`runtime_provision.py`, bağımsız review/verify ve integration kabulünden sonra
yönetici tarafından root:root0755 `/usr/local/lib/demandrift/runtime_provision.py`
olarak kurulur. Fetched Git kodu otomatik çalıştırılmaz. Gerçek Hetzner secret
mount/UID, native SCRAM/Redis auth ve dört servis kabulü ayrıca doğrulanır.

CLI yalnız root kullanıcısını ve sıfır argümanı kabul eder. Kullanıcı Gemini
anahtarı yalnız SSH'nin şifreli stdin akışından en fazla4098 byte okunur; ASCII
grafik1–4096 byte ve tek isteğe bağlı son LF sözleşmesine uyar. Değerler komut
argümanı, environment, Git, image, frontend ve çıktı/loglara yazılmaz. Anahtar
sağlayıcı/mod/permission onayı oluşturmaz ve hiçbir model/kaynak isteği başlatmaz.

Mevcut private `/opt/demandrift-api/deploy.lock`, release ile aynı kilittir.
Kilit meşgulse işlem hata döner. Bütün ancestor dizinleri root sahipliğinde,
symlink olmayan ve grup/diğer yazımına kapalı olmalıdır. Yönetici mevcut
`/etc/demandrift` dizinini önceden doğrular/oluşturur; üretici başka dizinleri
oluşturmaz veya mevcut dosyaların izinlerini değiştirmez. Herhangi bir mevcut
`/etc/demandrift/runtime` dizini, dosyası veya dangling symlink stdin okunmadan
reddedilir. Mevcut secret'lar benimsenmez, üzerine yazılmaz veya döndürülmez.

Üç bağımsız256-bit rastgele parola PostgreSQL admin/application ve Redis için
üretilir. App/admin DSN aynı açıkpostgres:5432/demandrift kapsamını ve ayrı
demandrift_app/demandrift_admin kullanıcılarını taşır. Redis DSN demandrift
kullanıcısını, Redis6379 ve database0'ı kullanır. Redis config default kullanıcıyı
kapatır, demandrift:* key/channel namespace'ini ve AOF/everysec politikasını
tanımlar. ACL config yalnız SHA256 parola hash'ini içerir; plaintext Redis
parolası yalnız ayrı broker/password FILE'larındadır.
ACL, Kombu queue/unacked/pipeline/lock ve runtime heartbeat için açık komut
listesi kullanır; `+@all` veya yönetici komutları verilmez. FLUSHALL/FLUSHDB,
CONFIG, ACL ve SHUTDOWN yetkileri yoktur. Gerçek broker roundtrip ve namespace
dışı key/channel/admin redleri native kabulde ayrıca sınanır.

Yedi fixed-name regular single-link FILE, private root0700 sibling staging
dizininde O_EXCL/no-follow ile yazılır. Application/admin/broker/Gemini dosyaları
UID/GID10001, PostgreSQL/Redis password/config dosyaları999 ve hepsi0400 olur.
File/dir fsync ve aynı kilit altında ikinci absence kontrolünden sonra staging
dizini Linux `renameat2(RENAME_NOREPLACE)` ile runtime adına publish edilir,
parent fsync yapılır. Son kontrol ile publication arasında kilidi kullanmayan
başka işlem boş target dizini oluştursa bile üzerine yazılmaz. Primitive yoksa
fail closed olur; bu producer yalnız Hetzner Linux içindir. Rename öncesi hata
yalnız sahip olunan staging'i temizler. Rename sonrası parent fsync hatası tam
private dizini korur ve başarısızlık bildirir; tekrar mevcut dizini reddeder.
Bu durumda yönetici secret değerlerini basmadan metaveri/mount kabulü yapar;
otomatik parola sıfırlama veya silme uygulanmaz.

Bu dosyalar Compose'un kabul edilmiş FILE sözleşmesine uyar. Yönetici kurulumda
host ve container içinde gerçek UID/mode/nlink/no-symlink'i doğrular; PostgreSQL
ve Redis'in boş projeye ait volume'larına gerekli999 sahipliğini ayrıca verir.
Runtime secret'ları database dump'ın parçası değildir; özel yedekleme/restore
politikasına dahil edilir. Frontend yalnız local kalır.
