# Native worker CI kapısı

PostgreSQL CI job'ı Python 3.13, PostgreSQL 16 ve Redis 7.4 servislerini kullanır.
`DEMANDRIFT_TEST_REDIS_URL=redis://redis:6379/0` açıkça verilir; native worker
fixture'ları varsayılan broker bulamadığında sessizce kabul edilmiş sayılmaz.
Fixture yalnız kendi rastgele queue/key prefix'ini temizler, global purge veya
Redis daemon restart yapmaz.

Genel PostgreSQL suite'inden sonra iki worker dosyası ayrıca JUnit çıktısıyla
çalışır. En az 13 native test ve sıfır skip/error/failure koşulu CI'yi durdurur.
İkinci çalışma hedef CI broker kapısıdır; toplam benzersiz test sayısına yeniden
eklenmez. Network-free Docker test job'ı kendi offline kapsamını korur.

Local native broker kanıtı Redis 8.10.1 kullanmıştır. Redis 7.4/Python 3.13
kanıtı yalnız bu workflow'un ilgili commit için başarılı GitHub koşusuyla
tamamlanır. Bu belge başarılı hedef koşu, Hetzner recovery veya ürünün 87 final
kabul senaryosu iddiası değildir. Push CI çalıştırır; frontend hosting veya
backend deployment başlatmaz. Backend deploy ayrı acceptance/review kapısıyla
explicit workflow_dispatch üzerinden yürür.
