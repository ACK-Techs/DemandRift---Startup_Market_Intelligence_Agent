# Durable job foundation

BE-04's bounded foundation persists job, transactional outbox and append-only
journal state in PostgreSQL. It does not run Celery/Redis, publish a queue message,
start a research through HTTP, call a provider, or complete a research pipeline.
The canonical `ResearchRun` remains the evidence repository's record; a job's
terminal state never manufactures a canonical completed run or report.

`JobRepository` requires server-resolved owner/project UUIDs and an existing
queued run. `enqueue(research_id, EnqueueJob)` locks project, research and job in
that order, checks the existing typed run, and binds the exact approved
plan/version/fingerprint and brief/version. The initial enqueue also requires
the current plan and brief. One scoped run has one job. Identical repeats return
that job, including its terminal or cancelled state; conflicting fingerprints,
selections or retry limits fail. Creation also persists one queue delivery and
one journal entry in the same transaction.

Additional request keys replaying the same immutable input are recorded as
journal aliases. A scoped unique index reserves each key, so replaying through
another key cannot later reuse that key for a different run. Repeating an
already recorded key adds no event or delivery.

Claims consume a finite attempt (1–8 configured), increment a monotonic fence,
and lease to a server worker UUID for 1–300 seconds. Duplicate deliveries cannot
claim an active lease. Every heartbeat, checkpoint, retry, completion and
dispatch guard validates the owner/fence and a fresh PostgreSQL clock after the
locks. Checkpoints only increase. Only timeout, rate limit and provider 5xx
classifications retry, with exponential backoff capped at 300 seconds; the final
attempt fails instead of resetting the limit. Expired leases require recovery.
Terminal replays preserve their attempt count, fence, finish time and evidence.

Cancellation is terminal for job execution. It disables new claims and pending
outbox publications and rejects a prior worker's guard or progress command.
Stored evidence is retained. A publisher which already received its permit can
still have sent a Redis message before cancellation; a later worker delivery
must claim this durable job and will receive no lease. Publisher leases have
separate monotonic fences and a finite 16-claim limit. A lost Redis acknowledgement
can cause another publication, while duplicate worker claims remain bounded.

The existing `budget_attempts` table is the only external operation ledger.
Recovery inspects the exact job owner/project/research scope: dispatched or
held-unknown attempts produce `held_unknown`, and no new job lease or completion
is granted until those attempts have known settlement. Cancellation/recovery
never refunds a hold, settles an unknown attempt, or grants a second provider
dispatch. Partial checkpoints remain available throughout reconciliation.

`dispatch_guard` audits a current lease/cancel precondition. Its `permitted`
flag is **not external network authorization**. Only the budget repository's
`dispatch_permitted` receipt authorizes one send. This foundation has no coupled
job/budget send transaction. Worker integration must check both under the agreed
lock order, recheck cancellation and budget deadlines, commit the sole dispatch
permit, and preserve unknown outcomes before any outbound operation. It must
also couple run/job/budget cancellation and publish truthful source/run states.
Those are open acceptance gates for the rest of BE-04.

Native tables use composite scoped foreign keys and FORCE RLS. The application
has INSERT only on jobs, SELECT on all three tables, and UPDATE only on the
job/outbox `command` columns. It has no table or column INSERT permission on
outbox/journal. Triggers derive mutable state from stored rows; direct state,
fence and counter changes fail even for accidental operator updates.

Only `demandrift_job_append` is SECURITY DEFINER. It checks the real bound
`public.research_jobs` AFTER ROW trigger and the tenant context before writing
the outbox/journal. The other three functions remain SECURITY INVOKER. All four
use fixed `pg_catalog, pg_temp` search paths and fully qualified public tables.
PUBLIC and the application have no EXECUTE permission on these trigger
functions; PostgreSQL invokes their already bound native triggers. The
application cannot bind the privileged writer to its own temporary trigger.
Insert guards also require the append writer's database role; nesting depth is
an additional guard, not insert authorization. This prevents an app-owned
temporary trigger from forging protected writes. Runtime role
validation must reject reachable/PUBLIC table or column INSERT grants on the
outbox/journal and any reachable EXECUTE grant on the privileged append writer.
Journal updates, deletes and table truncation are unavailable. Migration 0006
contains frozen DDL, independent of future ORM definitions.

Targeted checks use the repository's real PostgreSQL disposable-database
fixture. Enable `DEMANDRIFT_DB_TESTS=1` and provide
`DEMANDRIFT_TEST_ADMIN_URL` for a dedicated development PostgreSQL server, then:

```sh
PYTHONPATH=apps/api python -m pytest -q \
  apps/api/tests/test_job_contract.py apps/api/tests/test_job_repository.py
```

Each native test owns and drops a random database and restricted app role. These
checks use synthetic evidence and measured database behavior. They do not prove
live-source success, Redis availability, full worker recovery, real API start,
or local frontend-to-Hetzner acceptance. Shared migration metadata/head/policy
registration is assembled separately by the integration owner.
