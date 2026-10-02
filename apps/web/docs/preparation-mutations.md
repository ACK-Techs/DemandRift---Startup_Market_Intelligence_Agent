# Local research creation and recovery

This bounded FE-05 delivery connects human research creation to the accepted
preparation API. It saves an original idea and its first awaiting-user brief;
it does not approve a plan, run AI, acquire evidence, or start research.

## Requests and validation

- `POST /api/v1/projects/{projectId}/research` sends canonical `ResearchCreate`
  through the existing fixed same-origin proxy. Its successful response is
  `IdeaBrief`: 201 for a new creation, 200 for an identical-key replay.
- `GET /api/v1/projects/{projectId}/preparation-mutations/create_research/{key}`
  reads `PreparationMutationReceipt` only after an explicit recovery action.
- The store captures one UUID, the exact sparse body, owner, project and CSRF
  identity before publishing pending state. It suppresses simultaneous POSTs,
  receipt GETs, and overlapping replay. Nothing automatically retries or polls.
- The canonical wire validator checks the input without coercion, defaults,
  trimming, language sorting, or deduplication. Unspecified languages remain
  absent on the wire. When enabled, the form sends each language line exactly
  as entered. The backend owns any default for omitted languages.
- The original idea is immutable request input. The form counts Unicode code
  points and uses canonical validation without HTML UTF-16 `maxLength` or
  truncation. 10,000 astral characters and non-space U+FEFF are accepted;
  lone surrogates, whitespace-only input, and oversized input are rejected.
- A successful POST must match captured owner/project, exact original idea,
  explicit language values in order, awaiting-user status, first brief version,
  `versions.brief=1`, and `versions.plan=null`. A receipt additionally must match
  the captured operation/key and all nested receipt identities and versions.
  The schema validates its fingerprint format; its PostgreSQL JSONB fingerprint
  and stored payload relationship remain backend authority.

## Uncertain results

Network failure, timeout, in-flight abort, 5xx or unverified success retain the
original operation as unknown. The form locks its input and offers explicit
“Check saved creation” and “Resend this exact idea” actions. Replaying is allowed
only with the captured same owner/project/session, UUID and identical sparse
body; it never substitutes another key. A recovery 404 means no receipt was
returned at that moment. It cannot prove that an in-flight write will not commit,
so it preserves unknown and never enables replacement creation.

The recovery receipt proves the original creation and links its research ID. Its
first brief is historical: it never replaces a separately selected current brief
or assumes it is the latest version. Opening the existing preparation route reads
current backend state. After success, the list may be refreshed while its current
owner/project binding still matches; a failed list refresh does not revoke a
verified creation. Explicit “Create another idea” is available after verified
success. Definitive rejected first requests may be corrected and resubmitted.

Canonical protected 401 responses call global session invalidation with captured
owner+CSRF compare-and-set before stale response suppression. A late401 cannot
clear a newer owner/token or auth mutation. Malformed401,403,404 and transport
failure on a protected preparation request do not reset global authentication.

## Session checks and private continuity (R1)

The preparation resource lives in a route-scoped memory holder inside
`SessionProvider`, above its owner Fragment. The Fragment still unmounts private
views when the visible session is hidden. A passive focus/visibility session
check suspends the resource first: its public snapshot contains no owner, draft
or result, all operation methods refuse requests, and pending preparation
requests are aborted. An aborted in-flight write becomes unknown with its exact
UUID/body retained privately. Its late result cannot populate the new view;
canonical401 CAS still runs before stale-drop.

Only a canonical verified Session can resume the resource. Matching owner and
CSRF restores the original draft/capture/status after the private view remounts.
An unknown save still exposes only original receipt recovery and identical-key,
identical-input replay; it cannot create a replacement operation. A failed or
malformed passive session lookup leaves the capture suspended until verification
or its original absolute expiry. It does not authorize a write. The global auth
snapshot and existing account error states retain their established behavior.

Logout, absolute expiry, confirmed protected/session401, explicit invalidation,
confirmed account change or token rotation purge the capture and abort pending
requests immediately. The absolute expiry timer remains active during checking.
Navigation to another route/project disposes the prior resource. Broadcast
`session_changed` clears preparation resources immediately and invalidates a
pending session GET; a pending login/register/logout keeps its established
deferred auth reconciliation behavior. Other private views retain their existing
owner-bound stores and never display old private DOM during checking.

## Persistence boundary and verification

Draft, body, key, CSRF capture and private responses are memory-only. They are not
logged or stored in browser storage, navigation URLs or analytics. Same-page passive session
checks preserve this memory through matching identity verification. Leaving the
route/project, losing or changing the session, expiry, or reloading clears it.
Durable recovery after navigation or a full reload needs a separately designed
opaque locator and remains an open FE-05 follow-up; this delivery does not claim
complete FE-05 or full-reload acceptance.

Run `npm run test:preparation-mutations` with the supported Node runtime. Tests
exercise canonical Unicode/sparse input, request capture, deduplication,
unknown404, same-key replay, strict receipts, selected-read independence,
subscriber reentrancy, expiry, owner/project/token races, canonical401 CAS,
suspended resource continuity, actual identity boundaries, and navigation disposal.
Existing contract/auth/project/preparation suites, lint, typecheck and isolated
webpack build remain baseline checks. Local desktop/mobile browser tests use
synthetic route responses; they are not live Hetzner or Gemini verification.
Frontend hosting and shared canonical contracts/API/routes are outside this scope.

## Latest-only human brief revision

The latest brief view now offers explicit human edits. Historical selections remain
read-only. `POST /api/v1/projects/{project}/research/{research}/briefs` sends a
canonical sparse `HumanBriefPatch` and receives `IdeaBrief` (201 created, 200 replay).
Only canonical fields are editable; original idea, identities, provenance claims
and expected version are not form inputs. Omitted fields stay omitted; clearing a
nullable text/category or constraint value sends explicit null. Constraint entries
merge by name on the backend; an empty dictionary changes no existing entries.
Lists retain order and exact Unicode, empty modifiers are permitted, and omitted
languages acquire no frontend defaults. Text uses code-point validation up to
10,000 characters without UTF-16 maxlength/truncation. Booleans stay strict.

Before pending, one UUID, exact body, owner/project/research, CSRF and selected
original/brief identity are captured. No autosave, merge, POST retry or recovery
polling occurs. Unknown results lock edits and retain original same-key/body
replay; `GET .../preparation-mutations/revise_brief/{key}` is explicit. Receipt404
remains unknown. Receipts validate operation/key/scope, nested identities, original
idea, expected+1 brief version, awaiting-user state and actually submitted values.
A saved receipt may be historical and never overwrites a current read selection.

A definitive initial409 requires “Read latest and start a new draft”: a fresh latest
read followed by explicit discarding/redrafting. It never rewrites the existing
expected version or merges changes. A409 during unknown replay keeps the original
unknown capture. Switching to a historical selection hides the editor and blocks
its actions; returning to latest retains unresolved captured input.

Revision resources register with the accepted SessionStore public private-resource
API above the owner Fragment. Passive refresh suspends/hides/aborts; matching
verified owner+CSRF restores the same operation. Failed, malformed or network
GET remains paused. Logout/expiry/rotation/account change/navigation and broadcast
purge immediately, including broadcast during pending auth reconciliation.
Canonical private401 runs captured lineage CAS before stale-drop; malformed401,
403/404 and transport do not globally reset auth. No token, key, body or private
DTO is written to browser storage, navigation URLs, analytics or logs.

For a revision response with Retry-After, passive suspension cancels the old
generation's countdown. Matching verified owner+CSRF resumes it against the
original absolute deadline, including after repeated checks or a deadline that
elapsed while hidden. Verification never restarts or extends the wait. On expiry,
manual receipt/replay controls become available; the timer sends no request and
retains the original UUID and sparse body. Generation, research, owner and CSRF
guards prevent a stale countdown from affecting another scope.

Run `npm run test:brief-revisions`. Local native/browser proof uses synthetic
responses, with desktop/mobile and passive-session recovery checks. RAM recovery
does not survive reload/navigation; the separate opaque locator remains open.
This author delivery does not approve a plan, start research, run AI/provider calls,
host the frontend, prove Hetzner behavior or close the remaining FE-05 scope.
