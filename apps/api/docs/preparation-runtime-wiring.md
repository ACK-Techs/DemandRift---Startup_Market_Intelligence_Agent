# Araştırma hazırlığı runtime entegrasyonu

Ana FastAPI uygulaması gerçek oturum bağımlılıklarıyla preparation router'ını
bağlar. Auth body guard kendi 16KiB auth/proje kapsamını korur; preparation
mutasyonları ayrı 64KiB strict JSON guard'ından geçer. Özel yanıtlar, guard ve
validation hataları dahil `private, no-store` taşır. Başlangıç migration çalıştırmaz;
kısıtlı runtime rolü ve kabul edilen `20261002_0007` başlığı gerekir.

Migration metadata'sına immutable preparation receipt tablosu açıkça kaydedilir.
Kanonik katalog iki request ve beş response modeliyle 39 export içerir; schema ve
TypeScript üreticisi bu gerçek sözleşmeyle eşleşir. Önceki 32-katalog ve 0006-head
beklentilerinin üç fiili integration failure kanıtı korunur; R1 bunları kapatır.
Eski 0001–0006 migration dosyaları değiştirilmez.

Başlangıç rol kontrolü preparation receipt için SELECT/INSERT'e izin verir.
UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER, protected column UPDATE/REFERENCES ve
trigger function EXECUTE haklarını erişilebilir roller/PUBLIC üzerinden de
reddeder. Receipt'in zorunlu RLS'i ve tek, tam owner_scope USING/WITH CHECK
politikası yoksa başlangıç reddedilir. Rol veya politika genişlemesi sessiz kabul
edilmez. SQL policy karşılaştırması hedef PostgreSQL16'nın native gösterimidir.

Native testler gerçek main.py lifespan, güvenli cookie/auth/origin/CSRF, 16KiB'ı
aşan legal araştırma metni, 64KiB sınırı, duplicate JSON ve kalıcı aynı-key replay'i
birlikte çalıştırır. Bu teslim provider/worker dış çağrısı, AI plan üretimi, gerçek
Hetzner veya final87 kabulü değildir; bu kapılar ayrı kalır.
