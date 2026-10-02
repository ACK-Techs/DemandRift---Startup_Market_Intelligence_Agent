# Celery / Redis durable job bridge

This bounded BE04 slice connects an existing native job/outbox to one JSON-only
Celery wake task. PostgreSQL owns job state, leases, fences, retries and partial
evidence. Redis carries wake messages. Production pipeline execution remains
unavailable until a real handler is explicitly injected; no source/model/phase
handler or provider send is introduced here, and full BE04 acceptance is open.

Root pins Celery 5.6.3, Redis client 6.4.0 and Kombu 5.6.2 in the backend runtime.
`WorkerSettings` requires an explicit Redis URL, queue and key prefix. Lease
seconds are 1–300, visibility seconds are bounded by 3600, and handler duration
is bounded by 3600. Credentials are excluded from settings repr and diagnostics.
`make_worker_app` registers only the application wake task
`demandrift.jobs.wake`; serializer/accepted content is JSON, result backend is
disabled, remote control and Celery publish/task autoretry are disabled, and
prefetch is one. `configured_application()` requires environment configuration
and supplies no production handler. Root owns runtime command/service wiring.

The task message contains only resolved UUIDs for user, project, research, job
and delivery. The task ID equals the delivery UUID. The broker is an internal
trusted boundary; these identities are never accepted through a public user API.
The consumer re-reads the immutable job/run tuple and scoped delivery and rejects
malformed messages, archived projects and mismatched task IDs. UUID payloads
contain no research idea, provider input or user credentials.

`JobPublisher.publish` checks handler availability before claiming an outbox
delivery. Native publisher lease/fence permits one publish attempt. A successful
broker acceptance is followed by native `acknowledge_delivery`; an exception,
including a timeout after Redis received the message, leaves the leased row
unacknowledged. Native expiry/reclaim preserves the same delivery UUID and is
bounded at 16 publisher attempts. This can duplicate a wake. Broker delivery is
at least once, and the stable task ID does not itself deduplicate Redis messages.

Each publication binds an explicit application connection and queue namespace.
The focused tests use a unique queue/key prefix and delete only those fixture
keys. Kombu 5.6.2's prefixed Redis transport does not prefix `EXISTS`, so a passive
queue declaration can incorrectly report a missing queue. Queue-size tests use
non-passive declaration and prefixed `LLEN`; actual workers prove consumption.
The two original observation failures remain in the evidence history.

The consumer uses native expiry recovery and job claim before calling a handler.
A live duplicate cannot claim. Held unknown budget outcomes remain held, and
cancelled or terminal jobs cannot advance. Heartbeats use the same token/fence
and stop at the handler deadline; every checkpoint remains a native guarded
command. Celery hard/soft limits are configured for supported process pools.
The solo test pool proves process loss/replacement; it does not establish signal
time-limit enforcement. A late/stale handler cannot checkpoint after lease
expiry, and provider deadlines still belong to the later budget-coupled gate.

Handlers may persist checkpoint progress or raise an explicit classified
transient failure. Native retry generates the next outbox delivery and finite
backoff; unresolved budget attempts prevent retry/finish. Unclassified failures
use a sanitized error and preserve recoverable state. A handler's `completed`
return is accepted only after reading an actual canonical `ResearchRun` with
status `completed`; a return value cannot manufacture a research result.
A checkpoint-only handler returns an incomplete transport result and retains a
recoverable lease. Production handler absence claims no job, publishes no wake
and writes no successful phase/job/run completion.

If a wake was acknowledged in the outbox and later disappears from Redis,
`redrive_sent` provides one explicit scoped republish for a sent delivery and a
queued/retry-wait job. Recovery of an expired job must happen first. This is a
bounded operator action, with no automatic redrive loop, and cannot replay an
external provider effect or authorize a refund. Cancellation can race an internal
wake publication; the consumer rechecks the durable cancelled state and performs
no new progress. Full job/budget joint outbound authorization and cancellation
are still separate integration gates.

Native tests use actual Redis and Celery subprocesses with restricted disposable
PostgreSQL roles/databases. They prove duplicate wakes, durable publish/lost-ack
reclaim, process kill/restart and stale fencing, explicit recovery after purging
only an owned queue, cancellation, finite transient exhaustion, unknown-budget
hold, missing handlers and rejection of fabricated completion. Fixture handlers
are synthetic checkpoint/error probes confined to the tests. No paid call or
live research pipeline is exercised. Shared Redis daemon restart/AOF recovery is
an independent final QA gate; the owned queue-loss test does not claim it.
