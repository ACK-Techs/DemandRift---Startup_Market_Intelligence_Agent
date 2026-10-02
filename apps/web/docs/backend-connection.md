# Local backend connection

The local frontend's `/api/backend/{path}` server route accepts two exact server
origins: the dedicated SSH tunnel `http://127.0.0.1:18082` or the approved Hetzner
API `https://demandrift-api.ack-techs.com`. Set `DEMANDRIFT_BACKEND_ORIGIN` to the
chosen exact origin. Every other value fails startup through the existing strict
`backendRewrites` validator. The transport uses that configured protocol and host;
HTTPS never silently falls back to the tunnel. This task keeps the frontend local. An unconfigured frontend returns
a canonical, generic503 without making an upstream request. There is no browser,
query, header, environment-port or alternate-host target override.

The App Router uses Node's `http.request` or `https.request` with `agent:false`
and `Connection:close`. HTTPS uses the system trust store and verifies the fixed
API hostname; runtime configuration cannot override its CA or TLS verification.
Every incoming request gets one new upstream connection. Next16.3.6's external
rewrite implementation constructs its own keepalive agent; `httpAgentOptions`
cannot disable that separate agent. The external rewrite has therefore been
removed. No method is automatically retried, including GET and uncertain POST.
No redirect is followed or forwarded. Standard GET/HEAD/POST/PUT/PATCH/DELETE/OPTIONS
methods are supported; encoded separators and noncanonical path
characters are rejected before forwarding. Query bytes remain unchanged.

Cookie, Origin, X-CSRF-Token and Idempotency-Key values pass through unchanged.
The browser's actual Origin remains the frontend origin, including port3100; it
is not rewritten to the tunnel. Host and framing are generated for the fixed
upstream. Hop-by-hop headers and every header named by Connection are removed in
both directions. Response rawHeaders preserve separate Set-Cookie values, so
multiple authentication cookies survive the route. Response status, content type
and bytes otherwise pass through; responses are never cached.

Requests are buffered up to64KiB before the single upstream send, matching the
accepted preparation body guard. Valid schema fields still share that total body
bound. Authentication already has a stricter16KiB API bound. Responses
are buffered up to10MiB of upstream wire bytes; the existing API client retains
its stricter JSON response validation/size limit. An overall45-second deadline
covers reading the client body, connecting and reading the response. Client abort
closes the upstream request/response. Oversize request/header/path, upstream reset,
truncated/oversize response, refused redirect, timeout and abort return generic
canonical errors. Transport502/504 include a newly generated UUID and never raw
upstream errors, bytes, credentials or request details. No request/header/body is
logged or persisted by this route. A502/504 after sending a mutation cannot prove
it did not commit. Research/brief RAM recovery keeps the original key/body under
its accepted lifecycle; the proxy never replays it. The existing component-local
project holder loses its unknown-create RAM when passive checking remounts the
owner Fragment. That separate lifecycle gap is outside this transport change;
no claim is made that project uncertainty survives that remount. Explicit saved
project list reconciliation without a remount is covered by the local controls.

The exported factory accepts an explicit internal fixture port/deadline for native
tests and an isolated browser snapshot. HTTPS fixtures additionally require an
explicit test CA and connect only to their own loopback listener while verifying
the fixed production hostname. HTTP fixtures cannot supply TLS controls. Production calls it with only the strict
origin. The fixture seam cannot be selected through runtime environment, browser
input or a general proxy URL. Tests use own loopback ports, synthetic identities
and cookies, and do not touch the actual tunnel, Root frontend or API credentials.
They cover fresh sockets after idle, exact bytes/methods/auth values, duplicate
cookies, hop-header removal, bounds, abort/deadline, upstream drop and ambiguous
mutation count=1. Local Chrome desktop/mobile checks are frontend controls with a
synthetic upstream. Actual Hetzner acceptance and the original live rewrite
failure remain separate independent evidence; this author change does not claim
live platform recovery, hosting or complete FE-03/FE-05 acceptance.
