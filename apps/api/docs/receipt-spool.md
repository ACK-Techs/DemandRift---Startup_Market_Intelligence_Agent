# Private complete-observation spool

ReceiptSpool preserves complete provider observations before known settlement.
It performs no provider request, refund, retry or database operation. Live
remains disabled pending Root's native gateway/recovery acceptance. Filesystem
author tests do not prove native ledger commits.

Use a canonical absolute root with no symlink components. Root and UUID-only
user/project/research directories require backend ownership and mode 0700;
regular record/lock/ack files require mode 0600 and one hard link. Unsafe existing
owners, modes and types fail closed. API/worker must share the authorized
filesystem identity and private artifact volume. Scope comes from authenticated
server resolution. ReceiptBinding copies scope, stable attempt UUID, exact
AdmissionContext, native operation fingerprint, reservation and the seven
versioned model metadata fields before I/O.

Raw bytes are stored after a bounded canonical JSON envelope containing status,
elapsed time, incoming/outgoing counts, response hash, fixed model operation and
pinned response cap. The raw hard cap is 2,097,152 bytes; magic/length/envelope
are bounded by 16,384 bytes, making the aggregate 2MiB+16KiB. Caller caps can only
lower the fixed cap. No request headers, runtime key, outgoing body/prompt or
arbitrary metadata enters this interface. Raw response output may contain
private user data and stays backend-private; repr and generic errors omit it.

Each attempt has a process lock. File fsync precedes atomic no-overwrite rename;
directory fsync confirms it. Supported Linux renameat2 RENAME_NOREPLACE and macOS
renameatx_np RENAME_EXCL are required, with no overwrite or hard-link publication
fallback. Anchored no-follow descriptors, ownership/mode/link/size checks,
canonical fields and response digest protect reads. Different/corrupt replay
fails closed; identical replay reconfirms file/directory fsync.

```python
binding = ReceiptBinding(ReceiptScope(user_id, project_id, research_id),
    admission.attempt_id, context, prepared.fingerprint,
    admission.reserved, version_metadata)
record = spool.store_complete(binding, observation, operation="generate",
    outgoing_bytes=len(prepared.body), response_limit_bytes=policy.max_response_bytes)
spool.acknowledge(binding, expected_actual=actual,
    reconcile=lambda stored: ledger.settle(stored.binding.attempt_id, actual, receipt))
```

The trusted callback must use the actual same-scope native ledger and return
only after COMMIT. The spool checks attempt, reservation, exact expected actual
(one request and stored outgoing+incoming bytes), settled/overrun state and no
send permit. Root verifies native scope/fingerprint/version and actual provider
usage. A caller boolean or unknown/pending receipt cannot acknowledge. No DB
transaction may remain open across spool I/O. Ack markers are immutable and raw
records stay retained. Callback/ack write failure leaves pending work; an exact
known settlement can retry acknowledgement without provider replay or new charge.

Complete non2xx/malformed-usage responses are also retained and unacknowledged
until explicit reconciliation establishes known usage. Partial UnknownObservation
is never accepted as complete, and existing native unknown holds retain capacity
without TTL/refund/automatic resend.

pending(scope, limit=1..100, after_attempt_id=UUID) returns a bounded private
PendingPage in stable UUID order (default 50). It streams directory names,
retains at most limit+1 records, and fails closed above 4,096 namespace entries
(including locks, markers and incomplete files). Entries added before a cursor
are caught by a later full scan. This is a bounded scan, not a database snapshot;
concurrent acknowledgements can require a subsequent full reconciliation pass.
Recognized incomplete temp files after process kill are
uncommitted and ignored; corrupt entries, orphan acks and link/mode attacks fail
closed. A crash before publication leaves no complete record; post-rename
restart sees the whole record, while real power/storage recovery can lose an
unconfirmed directory entry. SIGKILL tests cover file-fsync/rename/directory-fsync
restart boundaries for records and markers; the acknowledgement crash fixture
simulates the trusted callback contract. They do not prove power-loss durability
or native accounting. Root must
store before settlement, reconcile the committed ledger idempotently, then ack.
An absent receipt or marker never authorizes another provider request.
