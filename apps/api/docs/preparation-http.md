# Durable human preparation HTTP

This bounded BE03 slice creates a research and its first immutable `IdeaBrief`
with a recovery receipt in one PostgreSQL transaction. It appends human revisions
and exposes scoped latest, exact historical, and paged reads. It does not run
Gemini, clarification, a source connector, a worker, or an approved research plan.
The broader BE03, frontend integration and live pipeline acceptance remain open.

Canonical models live in `app/contracts.py`; the existing generator emits the
matching JSON Schema and TypeScript consumers. The request models are
`ResearchCreate` and `HumanBriefPatch`. Read models are `IdeaBrief`,
`ResearchPreparation`, `ResearchPreparationPage`, `BriefPage`, and
`PreparationMutationReceipt` (with `BriefReference` in a summary).

All paths below are relative to `/api/v1/projects/{project_id}`:

| Method | Path | Result |
| --- | --- | --- |
| POST | `/research` | Created first `IdeaBrief` |
| GET | `/research` | `ResearchPreparationPage` |
| GET | `/research/{research_id}` | `ResearchPreparation` |
| GET | `/research/{research_id}/briefs/latest` | Latest `IdeaBrief` |
| GET | `/research/{research_id}/briefs/{brief_id}/versions/{version}` | Exact `IdeaBrief` |
| GET | `/research/{research_id}/briefs` | `BriefPage` |
| POST | `/research/{research_id}/briefs` | Appended `IdeaBrief` |
| GET | `/preparation-mutations/{operation}/{request_key}` | Exact `PreparationMutationReceipt` |

Mutations require the existing session cookie, exact allowed `Origin`, CSRF
token, and one `Idempotency-Key` UUID header. New writes return 201. Replaying the
same operation key with identical typed input returns 200 and the original
immutable brief, even after later revisions. Reusing the key for different input
or a different revision target returns 409. Creation keys are scoped to owner,
project and operation; revision fingerprints also include the URL research ID.
Distinct keys with the same idea deliberately create distinct researches.

Fingerprints hash PostgreSQL's canonical JSONB representation of the operation,
resolved target and validated request body. Creation defaults are expanded;
revision omission remains distinct from explicit null. Object key order and
JSON transport formatting do not alter input identity. Exact string values,
including original Unicode, combining characters and whitespace, are preserved.
Receipts pin a composite owner/project/research/brief/version foreign key and
return the historical result rather than silently substituting a current brief.

After a lost response, retain the operation key and query its recovery path. A
404 means no visible receipt was found at that moment; it does not prove that an
in-flight request cannot commit later. There is no automatic mutation retry.
The server supports explicit same-key replay after reconciliation. A new key
requests a new operation. Keys and receipts are retained without an expiry in
this foundation.

Revisions require `expected_brief_version` and at least one edit. The transaction
locks the active project and selected research, reads the current version and
appends exactly its successor. Concurrent stale edits return 409. Original idea,
identities, status, field origins, AI assumptions and confirmation flags cannot
be submitted as edits. Plain submitted human fields receive `user_stated`
provenance and remain unconfirmed; clearing a field records it as unknown and
retains prior origin history. Untouched provenance remains visible. The new
brief is `awaiting_user`, its clarity assessment returns to
`needs_clarification`, and its plan version is cleared. Skip preferences require
an explicit `continue_with_unknowns` preference; they do not represent analysis.

Reads require a session and owner/project/research scope. Absent and foreign
selections return the same 404. Archived projects allow reads and reconciliation
but deny mutations, including replay. Stored invalid snapshots fail with a
sanitized 500 and never appear as a successful recovered write. Lists use limits
1–100 and 512-character cursors scoped to owner, project, research and list kind.
These are bounded keyset pages, not a frozen multi-request snapshot; concurrent
newer inserts may be omitted from subsequent pages, so refresh the first page.

Preparation responses, validation errors, auth errors and unsupported-method
errors carry `Cache-Control: private, no-store`. `PreparationBodyGuard` applies
only to preparation paths and bounds mutation intake at 65,536 bytes, including
chunked bodies. It rejects duplicate JSON keys, non-finite numbers, invalid UTF-8
or lone surrogates, non-object bodies, duplicate or malformed Content-Length,
unsupported media types and encoded bodies. Existing auth and project route
behavior continues through the existing account guard and authentication code.

Frozen migration `20261002_0007` follows `20261002_0006`; migrations 1–6 are
unchanged. `preparation_mutations` uses FORCE RLS, the owner policy, native scope
and fingerprint checks, an invoker-only input trigger with fixed
`pg_catalog,pg_temp` search path, and an immutable update/delete trigger. The app
has SELECT/INSERT only and cannot execute the input trigger function directly.
No new privileged routine or external-send ledger is introduced.

Parent integration must register the metadata, require migration 0007, mount the
router and body guard, and verify forced policies and reachable application ACLs
at startup. The focused HTTP tests use an isolated FastAPI harness with the real
existing auth routes/service and real PostgreSQL; they do not establish that
production startup registration has been accepted. Native tests allocate and
destroy only their own random databases and restricted roles on the development
server. Independent review and verification decide acceptance after candidate
freeze.
