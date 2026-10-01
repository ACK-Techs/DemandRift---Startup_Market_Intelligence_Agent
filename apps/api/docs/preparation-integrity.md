# BE02 native hazırlık bütünlüğü

0002 migration global `(kind,logical_id)` kimliğini immutable owner/project/research anchor kaydına bağlar. Brief ve plan sürümleri aynı UUID ile başka araştırma/proje/kullanıcıya taşınamaz. Anchor kendi FORCE RLS politikasına, research composite FK ve immutable triggerına sahiptir. Eski 0001 migration değiştirilmez.

Deferred constraint triggerlar transaction commitinde source/query child sayısını, ID ve full JSON payloadını parent plan arrayleriyle birebir karşılaştırır. Bütün plan ve çocukları aynı transactionda eklenebilir; eksik, değiştirilmiş veya sonradan eklenen ilişki commit edilemez. Var olan kayıt update/delete ile değiştirilemez. Brief/plan wire created_at değeri relational timestamp ile aynı olmalıdır. Bu SQL kontrolleri full Pydantic validation yerine geçmez: repository yazımda ve her okumada typed doğrulamayı sürdürür.

Migration kimlik ve ilişkileri görünür bütün geçmişten backfill eder. Migrator bütün tenant verisini görebilen ayrı yönetici rolü olmalıdır; runtime app/worker rolü migration çalıştırmaz. Tarihsel kimlik scope çakışması, eksik/ekstra child veya timestamp farkında upgrade transactionı bütünüyle rollback olur; eski snapshotlar sessizce onarılmaz. Migration öncesi backup ve prod restore/rollback kapıları OP04/05 içinde zorunludur. Destructive downgrade yalnız disposable test veritabanında doğrulanır; üretimde otomatik uygulanmaz.

Bu alt teslim yalnız hazırlık grafiğidir. Downstream run/attempt/artifact/document/segment/claim/citation/bundle/report/gap ilişkileri, exact Linux/PostgreSQL accepted-SHA CI ve full BE02 kabulü ayrıca açık kalır.
