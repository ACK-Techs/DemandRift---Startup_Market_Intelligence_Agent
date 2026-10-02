# Human preparation reads

`/projects/{projectId}/research` reads a project-scoped research page; a saved
project links to that screen. `/projects/{projectId}/research/{researchId}` reads
the research summary, latest brief and brief history independently. History buttons
read the exact selected `brief_id` and `brief_version`; the view labels historical
and latest selections separately. There is no inferred total across keyset pages.

The canonical API client sends only same-origin `/api/backend` GET requests with
credentials and `no-store`. The five paths are:

- `/api/v1/projects/{projectId}/research`
- `/api/v1/projects/{projectId}/research/{researchId}`
- `/api/v1/projects/{projectId}/research/{researchId}/briefs/latest`
- `/api/v1/projects/{projectId}/research/{researchId}/briefs`
- `/api/v1/projects/{projectId}/research/{researchId}/briefs/{briefId}/versions/{version}`

`ResearchPreparationPage`, `ResearchPreparation`, `IdeaBrief` and `BriefPage`
responses use the published 39-model parser. Every response validates its owner,
project and applicable research scope. Historical selection additionally requires
the exact requested brief identity and integer version (1–2,147,483,647). Lists
request 25 records, reject mismatched limits, oversized pages, duplicate identities,
empty continuation pages and repeated/invalid cursors. Cursors remain opaque and
are sent unchanged through URL encoding. A new page replaces the previous page.
The backend does not freeze a multi-request snapshot: refresh the first page to
check new inserts.

The store holds only memory data. Binding a new owner or CSRF session identity,
logout, expiry or route change purges the old private state and aborts its reads.
Per-selection request lineage prevents a late latest brief from replacing a selected
historical version. New reads hide the previous response while loading. Primitive
owner/CSRF identity is captured before notifying loading subscribers. A canonical
protected 401 calls the published session CAS before dropping stale responses;
it can reject the matching account GET lineage even after a private store clears
or unmounts. It cannot clear a newer owner/token or cancel a newer login, registration
or logout. 403/404, malformed/HTML 401 and network/timeout errors do not clear the
global session. No automatic retries or mutations occur.

Loading, empty, missing, permission, invalid selection, rate limit, backend/network,
timeout and unverifiable response states remain visible and distinct. A positive
canonical Retry-After deadline pauses manual reads without triggering another
request. Zero permits immediate manual retry. The account screen handles sign-in
and session checks. Invalid route values never become API paths.

Saved field values, state, origin, confirmation, prior origins, conflicts, assumptions,
category, clarification preferences and unknowns are shown as received. An absent
value/origin is explicitly unknown. `awaiting_user`, `needs_clarification`, a skip
preference or even a confirmed brief never implies approval of a research plan,
Gemini execution, source acquisition or a successful research run. Summary and
latest/history reads may reflect changes saved between requests. Creating and
editing human preparation are separate forthcoming mutation checkpoints.

Verification: `npm run test:preparation`, existing contract/auth/project controls,
typecheck, lint, an isolated production build and bounded local Playwright interactions
with explicitly mocked API responses. Browser plugin is unavailable; bundled
Playwright is used. Neither local mocks nor a build establishes actual Hetzner
integration, live source/Gemini correctness, or the roadmap's final 87 scenarios.
The author run passes 24 preparation tests on Node 22.23.2 and Node 25.8.2,
31 contract tests, 25 auth tests and 22 project tests. The isolated webpack
production build includes both preparation routes. Local Playwright passes 18
flows with 69 mocked requests, no external requests and no unexpected console
errors. Delivered stale-response races are native tests; browser evidence covers
rendered current-session 401 handling and user interactions. Initial failing
native/browser proof is retained alongside corrected runs in the author delivery.
The parent FE05 live backend acceptance remains open. No frontend deployment.
