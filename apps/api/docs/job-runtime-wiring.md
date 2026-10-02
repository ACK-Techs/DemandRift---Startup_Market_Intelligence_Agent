# Kalıcı işlerin runtime schema ve role kapısı

Runtime yalnız açık migration head `20261002_0006` ile başlayabilir; migration
startup sırasında otomatik uygulanmaz. Alembic metadata, research_jobs,
job_outbox ve job_journal tablolarını kaydeder. Migration0001–0005 bu teslimde
değiştirilmez.

Uygulama rolü tüm ulaşılabilir üyelikler üzerinden incelenir; NOINHERIT olsa
bile SET ROLE ile ulaşılabilen bir rol güvenlik kontrolüne dahildir. Bu üç
tablo için doğrudan UPDATE/DELETE/TRUNCATE/TRIGGER/REFERENCES veya korunmuş
kolon UPDATE/REFERENCES yetkisi startup'ı durdurur. PUBLIC'ten gelen kolon
yetkileri de reddedilir. jobs/outbox üzerinde UPDATE(command) meşru sınırdır;
state, fence, checkpoint ve lease alanlarını native trigger üretir.

Native testler gerçek PostgreSQL üzerinde geçici database ve kısıtlı uygulama
rolü kullanır. Üç job guard fonksiyonu invoker'dır. Yalnız gerçek research_jobs
trigger'ına bağlanan job_append yazıcısı SECURITY DEFINER'dır; sabit search_path
kullanır ve PUBLIC/uygulama EXECUTE hakkı taşımaz. Uygulama journal/outbox'a
doğrudan INSERT yapamaz, kolon INSERT yetkileri de startup tarafından reddedilir.
Append fonksiyonuna sonradan verilen EXECUTE yetkisi de startup'ı durdurur.
Genel ledger'ın ayrı SECURITY DEFINER sınırı ve RLS kontrolleri korunur.

Bu wiring tek başına worker çalıştırmaz. Celery/Redis lifecycle, gerçek API
run başlatma ve ortak job/budget dispatch/cancel consumer kapıları BE04/BE05
içinde açık kalır; final recovery kabulü ayrıca yürütülür.
