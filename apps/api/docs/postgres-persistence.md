# PostgreSQL persistence teslim sınırı

BE-02 ilk alt teslimi `20261001_0001` migration, dokuz tablo ve transaction-scoped bağlantıdır. Users/sessions kimlik doğrulama lookup; projects/researches/briefs/plans/source/query/approval kayıtları üç fazın hazırlık temelidir. Auth route, worker, evidence persistence ve typed repository sonraki ayrı kabul işleridir. Bu migration tek başına BE-02 üst paketini veya ürün kabulünü kapatmaz.

PostgreSQL16, SQLAlchemy2.0.54 sync, Alembic1.20.0 ve psycopg3.3.6 kullanılır. `DATABASE_URL` yalnız backend/migration runtime'dadır; DSN veya parola log'a yazılmaz. `Database` import sırasında bağlanmaz. Her `transaction(user_id)` tenant kimliğini, kimlik verilmediğinde boş değeri, `set_config(..., true)` ile atar. Böylece pool'da önceden commit edilmiş session-level kimlik olsa da bağlamsız transaction tenant verisi göstermez. Dış HTTP/AI çağrıları bu transaction içinde yürütülmez.

Migration credentials uygulama credentials'ından ayrıdır. DBA uygulama rolünü LOGIN/NOSUPERUSER/NOBYPASSRLS/NOCREATEDB/NOCREATEROLE olarak önceden oluşturur; migration `DATABASE_APP_ROLE` rolüne yalnız gereken SELECT/INSERT ve mutable hesap/proje UPDATE yetkilerini verir. `Database.assert_application_role()` current ve session kullanıcılarının public tablo/schema sahipliklerini, sahip rol üyeliğini (NOINHERIT dahil), schema CREATE ve ayrıcalıklı rol üyeliğini reddeder. Bu kontrol bu teslimde DB fonksiyonu ve gerçek PostgreSQL testleriyle doğrulanır; API startup bağlantısı BE-03'te yapılacaktır. Auth ve session tabloları backend'in belirli email/opaque hash lookup'ı içindir; kullanıcıya genel DB erişimi verilmez. Tenant tablolarında ENABLE+FORCE RLS ve composite owner/project/research parent FK vardır. Kullanıcı bağlamı olmadan tenant okuması boş, yazması reddedilir. Repository katmanındaki proje yetkisi bunun üstüne gelir.

Research kimliği server tarafından fikir kaydında oluşturulur; original idea whitespace/satır sonlarıyla immutable kalır. Brief kimlik/sürüm snapshot'ı değiştirilemez. Plan belirli brief snapshot'ını aynen taşır; onay belirli confirmed plan_version+fingerprint'e bağlıdır. Plan sürümü proje içinde monoton olacaktır; sürüm allocation ve fingerprint hesaplama typed repository/BE-07 diliminde uygulanır. Source/query planının FK'si aynı plan snapshot'ını ve izinli source_id'yi seçer. Source profile payloadının bütün shape doğrulaması typed repository'de yapılır; DB identity/scope guardı bunun yerine geçmez.

Immutable snapshot'larda UPDATE/DELETE DB trigger ile migrator için de reddedilir; yeni explicit version veya sürümsüz nesnelerde yeni UUID gerekir. Research kimlik/original kayıtları da immutable'dır. FK alanları indekslidir; tam wire snapshot JSONB yanında kimlik/sürüm kolonlarıyla eşleşir. Migration DDL'si dosyada sabittir; gelecekteki ORM modelinden yeniden oluşturulmaz.

```sh
# Yalnız ayrı migration rolünün runtime ortamında:
alembic -c apps/api/alembic.ini upgrade head
# Yalnız projeye özel disposable PostgreSQL test server'ına verilen env ile:
DEMANDRIFT_DB_TESTS=1 python -m pytest -q apps/api/tests/test_postgres_foundation.py
```

Gerçek DB testlerinde `DEMANDRIFT_TEST_ADMIN_URL` ayrı test server'ını seçer. Her test kendi rastgele isimli database ve sınırlı app role oluşturur, test bitince yalnız bunları kaldırır. Offline DB'siz kontroller bu suite'i skip eder; gerçek PostgreSQL kapısı ayrıca çalışmadan üst kabul kapanmaz. Downgrade/re-upgrade sadece disposable DB'de test edilir. Production migration rollback, server restart, backup/restore ve diğer servislerin korunması OP-04/05/06'nın ayrıca zorunlu kabul işleridir.

API CI ayrıca Python3.13/Linux job container'ı ile PostgreSQL16 service container'ını çalıştırır; host portu açılmaz. Job/service ağı yaklaşımı [GitHub'ın PostgreSQL service belgesine](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers) dayanır; [resmî PostgreSQL imajı](https://hub.docker.com/_/postgres) test majorını sağlar. Buradaki sabit test parolaları yalnız disposable CI/test rollerine aittir; runtime credential değildir. CI'nin bu job'ı exact kabul edilmiş commit üzerinde fiilen geçmeden hedef platform kapısı kapanmaz. Production exact image/digest OP-02'de ayrıca kaydedilir.
