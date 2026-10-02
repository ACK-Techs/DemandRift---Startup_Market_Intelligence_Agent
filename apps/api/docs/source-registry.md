# Offline Source Registry foundation

`app/data/source-registry.v1.json` is the packaged source authority. It retains
all 636 historical source identities and the 15 profiles referenced by the
existing category, scenario and F03 preview views. These three consumers derive
names, dated health, fields and request definitions from the same immutable
registry. Scenario query text and source-ID order remain scenario policy.

This foundation does not enable acquisition. All identities are candidate-only;
all current runtime profiles have `runtime_enabled=false`, deferred health and
unknown permission. No key, HTTP request, worker dispatch or shell execution is
part of registry loading or query compilation. The historical F03 HTTP endpoint
remains unavailable (`410`) and is excluded from database-backed production.
Existing mock source tests exercise the old preview without claiming product
source acceptance. DNS pinning, robots, shared budget/lease/cancel, owner-scoped
raw storage and actual source qualification require separate accepted slices.

## Provenance and dated observations

The bundle includes SHA-256 references to the fixed lab manifest, health,
field and category CSVs. Its registry version is bound to the digest of the
complete canonical bundle, including curated surface definitions and history.
An offline builder reproduces the same bytes; changing input observations
requires a reviewed regenerated version, never automatic runtime elevation.
API runtime reads the packaged file under `app/data`; it does not require the
laboratory tree or a repository working directory. Existing Docker `COPY app`
includes the data file.

`source_manifest.json` provides stable identity, historical origins and
resolution provenance, including five unresolved candidates. The real health
observation date is `2026-09-27`, from `KAYNAK-SAGLIK.csv`. The category view's
`last_measured_at` uses that date and its `source_registry_version` uses the
current bundle version. The previous hardcoded AS-01/BT-02 outputs remain in
`legacy_snapshots_json` as immutable historical records; they are not rewritten
to look newly verified.

Historical eligible status means a dated trial candidate, including a real
content surface. Policy-blocked, challenged and insufficient-content records
remain visible and ineligible. Source unavailable is not no-results. Current
license, retention, ownership, market and language coverage remain unknown;
no default Turkish/global market or independent organization is invented.

## Expected fields and distinct surfaces

Trial candidate `expected_fields` are expectations. F03 preview fields belong
to its selected surface: GitHub issues, StackExchange advanced search, or HN
Algolia search. GitHub issue results do not acquire repository license/version
fields; `surum` remains explicitly not applicable. HN comment evidence points
to its HN item, not the linked news story as though that story was fetched.

The lab field catalogue's `dogrulandi` records retain their locator, query kind
and permission snapshot under `catalog_field_evidence`. They lack exact
surface URL/date/content-hash bindings. Therefore they cannot populate current
`verified_fields`; this list remains empty until a future accepted field proof
supplies those bindings. This preserves old observations without manufacturing
fresh verification. Historical API endpoints remain separate: repository search
versus issue search, questions versus advanced search, and Firebase topstories
versus third-party Algolia search. Origins and paths are never inferred by
silently rewriting another surface.

## Typed request boundary

`compile_preview_request` accepts a source ID, literal query string and integer
item bound of 1–5. It returns a fixed HTTPS endpoint and typed parameter mapping;
it neither opens a socket nor grants live permission. Unknown/non-preview source
IDs, invalid Unicode scalar text, empty/oversized queries and boolean/string/float
limits fail closed. Query whitespace and shell/URL metacharacters remain data.
The caller cannot select URL, origin, path, parameter names, site filter or MIME.
The packaged registry uses frozen models and tuples; consumer DTOs are fresh
copies. Parsing first checks the digest and version against the complete parsed
JSON payload, before typed validation or defaults. JSON whitespace, object-key
layout and equivalent string escaping may vary; values, types and array order
remain part of the canonical integrity check. Every record explicitly includes
all fields, including defaults. Enable flags require actual booleans, fixed caps
require actual integers; zero cannot stand in for false, equal-valued floats
cannot stand in for integers, and missing fields are not reconstructed. These
invalid shapes also fail when a caller recomputes their digest. Compilation
revalidates content and digest before use, including model copy/update tampering.
No new wire root or canonical schema/catalog is added.

## Development acceptance

From the repository root, with the project Python environment:

```sh
PYTHONPATH=apps/api python apps/api/scripts/build_source_registry.py --check
PYTHONPATH=apps/api python -m pytest -q apps/api/tests/test_source_registry.py apps/api/tests/test_source_plan.py apps/api/tests/test_initial_runs.py apps/api/tests/test_source_execution.py apps/api/tests/test_contracts.py
PYTHONPATH=apps/api python apps/api/scripts/generate_contracts.py --check
```

The source-registry tests verify historical hashes, 636 identities/15 profiles,
seven category and 30 scenario projections, source-specific field boundaries,
hostile literal parameters, immutable copies, corrupt bundles, and app-only
packaging in a clean subprocess. Historical-input checks run from the repository;
they are explicitly skipped in app-only images which do not package the lab.
The builder is a developer/CI preparation tool, not an application startup job.
Canonical contract generation must remain unchanged. Test evidence and failures
are recorded separately by the completion run; these commands are not a final
87-scenario or live source acceptance claim.
