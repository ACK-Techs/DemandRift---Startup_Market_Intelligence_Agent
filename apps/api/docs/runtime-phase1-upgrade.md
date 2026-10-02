# Phase 1 native schema geçişi

Tek yayın birimi migration009, sabit 1–9 runner zinciri, startup head009,
application ACL/RLS kontrolleri ve schema009 release helper'ıdır. Eski 001–008
migration dosyaları değiştirilmez. Advisory migration lock kimliği korunur;
eski ve yeni runner aynı işlem kilidini kullanır.

Beş yeni tablodan owner verisi taşıyan `plan_mutations`,
`preparation_analysis_requests` ve `preparation_analysis_results` immutable
INSERT/SELECT ve FORCE RLS kapsamındadır. `source_qualification_snapshots` ve
`source_qualification_current` yalnız yönetici yazımlı, application SELECT
erişimli ortak izin metadatasıdır. Application veya rol üyelerinin table/column
UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER; ortak metadata INSERT yetkileri
startup'ta reddedilir. Private trigger helper'ları application EXECUTE alamaz.
Salt okunur `demandrift_phase1_plan_eligibility` RPC'si owner GUC kontrolüyle
application'a açık kalır; kaynak izni üretmez.

Geçerli current kaynak izni olmayan veya boş confirmed legacy plan okunabilir,
ancak approve/enqueue/fresh dispatch için yetki sağlamaz. Analiz native admission
öncesinde immutable claim commit edilmesini gerektirir. Tek gerçek suite saati
ilk dispatch'te başlar; yeni claim, hesap veya retry süre/bütçe sıfırlayamaz.

Hetzner schema008 sürümü, kabul edilmiş bu birleşik teslimin bağımsız kontrolleri
ve exact-SHA Linux CI kapıları geçene kadar korunur. Önce private backup alınır;
runner ileri migration ve kısıtlı app role kontrolünü birleştirir. Commit edilmiş
schema009'a eski schema008 image ile rollback fail closed olur; API/worker kapalı
tutulur ve müdahale gerekir. Başarı pointer'ını geri yazmak database restore
kanıtı değildir. Gerçek restart/recovery, restore ve rollback zorunlu son kabul
senaryolarında ayrıca gözlenir.
