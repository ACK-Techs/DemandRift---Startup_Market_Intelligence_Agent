# Ölçülen generation consumer temeli

Gateway her çağrıda server policy, trusted output modeli, instruction/input ve
prompt/schema sürümlerinden araçsız kanonik PreparedGeneration üretir. Caller
hazır body, receipt veya persisted send permit veremez. CountTokens başlangıçta
kapalıdır ve zorunlu preliminary çağrı değildir.

`compact-32k-estimate65536-totalpayload-v1` tam request için 32KiB ve 65.536
input token tahmini kullanır. Tahminin kanıtlanmış üst sınır olduğu iddia edilmez.
Output+thinking policy limiti eklenir. Reserve byte hesabı outgoing kanonik body
artı incoming response cap; known actual byte hesabı outgoing body artı alınmış
response payload'dır. Transport received_bytes yalnız incoming payload olarak
kalır. TLS/framing overhead bu payload metriklerine dahil değildir.

Somut `JobBudgetRepository.admit` producer arayüzü aynı kısa native transaction
içinde preparation/currentbrief veya approvedjob/lease/fence ve ortak budget
dispatch'i kontrol eder. Fresh permit commit sonrası tek send açar; replay hiçbir
send açmaz. Mevcut BudgetRepository known settle/unknown owner'ıdır. Minimum native
deadline transport'a aktarılır. Ağ boyunca DB kilidi tutulmaz.

Complete 2xx raw JSON accounting ayrı decode edilir. Geçerli usage ve exact
receipt önce commit edilir; output validator daha sonra çalışır. Blocked,
truncated, invalid output ve custom validator exception known harcamayı silmez.
Overrun gerçek actual ve kapalı suite'i korur; output verilmez. Timeout, partial,
cancel, non2xx, invalid usage/receipt unknown hold bırakır. Cancellation unknown
kalıcı kaydından sonra dışarı iletilir. DB settlement/unknown hatası safe generic
exception olur, successful output yayımlanmaz. Retry/fallback/suite reset yoktur.

Bu teslim yalnız offline metered consumer temelidir. Live enablement açıkça
reddedilir: durable provider receipt inbox/spool ve restart settlement recovery,
native8 producer kabulü/runtime wiring ve canlı format kapıları tamamlanmalıdır.
MockTransport fiziksel ağ yapamaz. Native gerçek producer ile mocked HTTP kanıtı
ayrı integration gate'tir; ducktyped offline fixture ledger native DB kanıtı
sayılmaz. Main router/worker handler veya ürün başarısı bu modülden oluşmaz.
Gemini key yalnız backend runtime header parametresidir; prompt, output, exception,
repr veya browser bundle'a taşınmaz. 87 final kabul hâlâ açıktır.
