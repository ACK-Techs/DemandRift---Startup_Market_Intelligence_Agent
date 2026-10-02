# Coupled preparation and job admission

`JobBudgetRepository` grants no network operation by itself. It runs one short
PostgreSQL transaction over the existing budget ledger and returns a fresh
`DispatchReceipt` only after commit. The production metered gateway must obtain
that receipt itself and send exactly once only when `dispatch_permitted` is true.
Persisted receipts, duplicate calls and lost-response recovery never authorize
another send. No pipeline handler is supplied by this foundation.

`AdmissionContext("preparation", brief_id, brief_version)` supports clarification
and planning before any approved plan, ResearchRun or job exists. It requires
an active owned project/research, the exact current canonical brief and absence
of a job. Job mode adds exact current job/lease owner/fence, current approved
plan/brief/fingerprint and matching selected uncancelled nonterminal ResearchRun.
A newer awaiting plan invalidates an older confirmed selection. Context comes
from server-resolved authenticated scope, never model or browser authority.

The producer locks project→research→job (job mode only)→suite→account→attempt.
Scope rows use FOR NO KEY UPDATE: it serializes mutations while permitting
implicit FK KEY SHARE checks during legacy accounting. A real two-session test
captured and fixed the FOR UPDATE versus FK KEY SHARE deadlock.
Typed snapshot readers and the native RPC share the same Session. The RPC calls
the existing reserve and dispatch routines in that transaction, attaches an
immutable admission binding to `budget_attempts`, and journals the additional
job dispatch guard. Any failure rolls back reservation, clock start, binding
and job journal. Existing repositories' public methods still use separate
transactions; calling them in sequence is not coupled admission.

Migration 0008 adds no spend/effect ledger. Existing ledger/account FORCERLS and
composite scope FKs remain. New brief/job composite FKs bind the attempt to its
exact context. A fixed-search-path invoker trigger denies all fresh legacy
unbound dispatch, before or after a job exists. That trigger never obtains
project/research/job locks under the legacy Suite→Account→Attempt order.
Unknown, cancel and late settlement check immutable fields without current
lease/approval checks so expiry cannot hide actual charges. Application/PUBLIC
ledger writes, helper/guard EXECUTE and global Suite SELECT remain denied.
The exact privileged function inventory becomes budget_operate, job_append,
and job_budget_operate. The new JSON RPC is the sole newly executable function.

Each admitted deadline is the minimum of immutable Suite/account remaining
time, current job lease (job mode), and pinned model timeout. Native
`clock_timestamp()` runs after lock waits. `remaining()` returns only a scoped
minimum and never starts the clock. Fresh dispatch starts clocks through the
existing ledger. A receipt's monotonic deadline anchors at the Python instant
before admission, subtracting transaction/commit delay conservatively. Optional
trusted caller deadlines shorten it further. Transport must enforce this same
absolute deadline through response and cleanup. Heartbeat/replay never extends
an admitted attempt deadline. Unknown provider effects retain reservation and
active count without TTL or automatic refund/retry; known late usage remains
chargeable. Preparation and job modes share the same Suite/account limits:
$5, 300 requests, 50,000,000 bytes, 150 pages, 1000 records, 300,000 tokens,
1800 seconds and concurrency 2. Tests use disposable fixture suites only.

Admission commit is the authorization point. Cancellation/revision/fence
replacement serialized before admission denies a new send. Cancellation after
commit interrupts already authorized work best-effort; no short database
transaction can atomically commit an HTTP packet. Locks never cross HTTP.
CountTokens starts disabled and is optional separately metered work. No live
provider request or live Suite clock is started by this slice.

```python
producer = JobBudgetRepository(database, suite_id, user_id, project_id, research_id)
receipt = producer.admit(context, attempt_id=attempt_id,
    fingerprint=prepared.fingerprint, reserved=reservation, metadata=versions,
    model_timeout_ms=policy.timeout_seconds * 1000,
    outer_monotonic_deadline=handler_deadline)
# Gateway sends once only for a fresh, still-unexpired receipt; unknown outcomes
# use BudgetRepository.mark_unknown, and known usage uses its existing settle.
```

Root owns head008/main/env/runtime guard/old fixture/catalog wiring and the
production gateway consumer. Existing generic budget fixtures that dispatch an
unbound reservation now fail intentionally and must use a current brief/job
context; no fixture-only production bypass exists. Existing job worker tests'
`budget_for_job` helper also needs coupled admission for its unknown-attempt
setup. The shared old two-function inventory/head assertion needs revision.
Author tests use a dedicated fresh head008 fixture and prove native privileges;
they do not establish acceptance of Root's production startup integration,
transport, gateway reconciliation, configured phase handlers or parent packages.
