# Trusted native Gemini runtime

`make_native_runtime` accepts server-only `RuntimeGeminiConfig`, an exact
`Database`, four resolved suite/owner/project/research UUIDs and a private
`ReceiptSpool`. It creates same-scope native accounting services. Construction
does not read a key, open a transaction, establish an account, start the suite
clock or call a provider. Default `live_enabled=False` and absent provider both
disable generation before credential/admission/input preparation. The only
providers are explicit `developer` and `vertex_express`; neither key prefixes nor
browser/model fields select one. Model/endpoints/pricing remain pinned by the
accepted policy. The separate test factory accepts only HTTPX MockTransport and
rejects live configuration.

For a fresh native attempt, the server prepares the canonical bounded request,
checks native current-context remaining time, reads `GEMINI_API_KEY_FILE` lazily
in a fixed isolated child, then rechecks current brief/job/budget atomically at
dispatch. The child gets only the FILE pointer, uses the accepted private regular
single-link/no-follow loader and is killed/reaped on cancellation or deadline.
Raw environment credentials, ambiguity and fallback are rejected. Credential
failure does not create an attempt or start the clock. The same earlier absolute
deadline includes loading and delivery. Fresh committed dispatch grants one
send; simultaneous/historical admission never grants a second one.

`recover` is an explicit send-free, keyless historical output operation. Its
caller supplies the server-stored exact request input, trusted output model and
prompt/schema versions. Native recovery verifies scope/context/fingerprint/
policy/reservation against an existing dispatched attempt, settles known actual
usage, commits and publishes an immutable ACK before decoding any value. Missing
or foreign attempts cannot create a reservation. Complete unknown bodies remain
pending and held; invalid output stays charged, overrun never releases output.
An enabled generator selects an existing scoped receipt before reading a key.
Partial observations without a complete spool record report recovery unavailable
and never authorize another send. A recovered proposal is historical output;
the analysis consumer must recheck the latest human brief before publishing it.

The factory is implementation enablement. It requires no earlier live-PASS flag,
which would prevent the first deliberate paid acceptance request. Production
routes/startup do not yet instantiate it or start calls. Final live acceptance
still needs the user's chosen provider, actual pinned model/schema/usage receipt
compatibility and the fully prepared product using the same authorized suite:
$5, 300 requests, 50,000,000 payload bytes, 150 pages, 1000 records, 1800 seconds,
300,000 tokens, concurrency 2. Setup/account construction cannot reset duration,
spent/held or retries. Vertex Express availability/schema and required provider
receipt fields remain explicit final checks; no fallback or probe is enabled.

Development evidence uses disposable real PostgreSQL, synthetic private FILEs
and mocked HTTP. It does not claim a real provider, Hetzner integration, semantic
correctness, all 42 packages or the mandatory 87 scenarios passed.
