# Güvenilen dört servis runtime release

Bu teslim yönetici tarafından kurulan coordinator temelidir. Hetzner kurulumu,
gerçek backup/restore, restart/recovery ve 87 final senaryo kabulü ayrı kapılardır.
Mevcut `demandrift-api-deploy` sağlık servisi kurulu kaldığı sürece eski davranışı
korur. Yeni dosyalar push ile sunucuya yüklenmez.

Bağımsız review/verify/integration ve exact güncel main SHA'nın başarılı API CI
sonrası yönetici `runtime_release.py` dosyasını
`/usr/local/lib/demandrift/runtime_release.py` root:root 0755 olarak;
`demandrift-runtime-deploy` wrapper'ını mevcut restricted `build-api` hedefi
`/usr/local/sbin/demandrift-api-deploy` olarak kurar. Eski helper/Compose/başarılı
SHA'nın özel kopyası ilk geçiş için korunur. Kabul edilmiş `runtime.compose.yml`
`/opt/demandrift-api/runtime.compose.yml` root:root 0600 olarak kurulur. Base/log
dizinleri root sahipliğinde ve grup/diğer yazımına kapalı; backup dizini 0700'dür.
Runtime FILE secret ve native volume sahipliği ayrı kurulum kabulünde doğrulanır.

CLI yalnız tek 40 karakterli küçük hex SHA kabul eder. Sabit repository ve proje
yollarından bounded regular API context çıkarır, exact main'i build öncesi ve
sonrası tekrar doğrular; fetched deploy kodu çalıştırmaz. Test container ağı
kapalıdır. Build/test/main kontrolü geçmeden uygulama durdurulmaz. Paylaşılan
build ve deployment kilitleri başka builder/release ile çakışmayı engeller.

PostgreSQL/Redis sağlıklı başlatıldıktan sonra API/worker quiesce edilir; private
custom-format `pg_dump` 180 saniye ve 1 GiB sınırıyla, parola yalnız PostgreSQL
container'ında FILE'dan okunarak alınır. Arşiv owner ve ACL bilgilerini içerir;
hash/byte manifest fsync edilerek yazılır. Role parolaları, runtime secret'ları ve
artifact volume bu database arşivinin parçası değildir ve ayrıca özel yedeklenir.
Parola FILE'ı strict runtime sözleşmesindeki bare ASCII veya tek final LF
biçiminde okunur; EOF tek başına geçerli bare parolayı reddetmez, boş dosya reddedilir.
Restore yalnız ayrı test database/volume üzerinde, aynı gerekli rollerin güvenli
bootstrap'ından sonra doğrulanır; otomatik production restore yapılmaz.

Backup tamamlanmadan migration başlatılmaz. Operations migrator yalnız kabul
edilmiş forward head `20261002_0008` ve restricted application rolünü kullanır.
Dört servisin bounded Compose health beklemesi, ardından exact SHA ve bütün
process/database/queue/worker kontrollerini içeren `/ready` başarılı olmalıdır.
`research_execution: unconfigured` bu hazırlık runtime'ında açık kalan pipeline
kapsamını gösterir; readiness ürünün tamamlandığı anlamına gelmez.

Başarı yalnız bütün kapılardan sonra private `runtime-success.json` dosyasında
atomik olarak kaydedilir. Sonraki rollback aynı schema008 için kayıtlı önceki
runtime imajını kullanır; önceki migrator actual schema/ACL'yi tekrar doğrulamadan
API/worker açılmaz. İlk geçiş rollback'i kayıtlı eski Compose ile eski API'yi
açar ve yeni worker'ı kapalı bırakır. PostgreSQL/Redis ve bütün data volume'ları
korunur. Migration downgrade, volume silme veya otomatik backup restore yoktur.
Rollback güvenlik doğrulaması başarısızsa uygulama kapalı tutulur, başarı pointer'ı
ilerlemez ve yönetici müdahalesi gerekir. SSH/CLI hata çıktısı private command
çıktısı, URL, parola veya SQL içermez.
Başarı kaydının rename sonrası fsync hatasında eski başarılı kayıt, herhangi bir
rollback denemesinden önce geri yazılır; önceki schema/ACL kontrolü de başarısız
olursa başarısız yeni SHA başarı kaydı olarak kalmaz. Kayıt geri yazımı başarısızsa
uygulama servisleri durdurulur ve otomatik geri dönüş başarı olarak bildirilmez.

Unit failure-path testleri gerçek Hetzner deploy veya restore kanıtı değildir.
Release işleminde kısa kesinti beklenir; mevcut diğer backend projelerine komut
uygulanmaz. Frontend yalnız local çalışır, bu coordinator frontend yayını yapmaz.
