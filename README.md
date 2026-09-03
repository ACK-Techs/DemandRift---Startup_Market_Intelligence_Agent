# DemandRift — Startup Market Intelligence Agent
 
DemandRift is an evidence-driven startup research and decision platform. It turns an early idea into a traceable research brief, gathers and normalizes permitted market evidence, identifies what is still unknown, and produces a defensible direction: **Build**, **Modify**, **Kill**, or **Investigate More**.

> Don't just validate your idea. Leave with a build-ready MVP.

## Repository status

This repository currently contains the approved architecture and implementation plans for Phases 1–7. It is a planning baseline, not a claim that the application runtime is already implemented. Phase 8 is intentionally out of scope until it is explicitly approved.

## Research lifecycle

| Phase | Responsibility | Primary output |
| --- | --- | --- |
| 1 — Intake | Turn an ambiguous idea into a user-confirmed, researchable brief while preserving field origins and assumptions. | `IdeaBriefVersion` |
| 2 — Planning | Compile research questions, source/query coverage, market and language scope, and a budget contract. | `ResearchPlanVersion` |
| 3 — Acquisition | Collect raw evidence from policy-approved sources with provenance, execution status, cost, and access metadata. | `RawArtifact` set |
| 4 — Normalization | Parse and normalize immutable artifacts; produce segments, deduplication relations, entity candidates, and lineage. | Normalized corpus |
| 5 — Gap policy | Audit secondary-research gaps and, when policy and budget permit, route gap-driven work back through the Phase 3 acquisition runtime. | Gap-closure trace |
| 6 — Analysis | Create citation-bound claims, independence groups, clusters, evidence maps, counter-evidence, and classified research gaps. | `AnalysisDossier` |
| 7 — Decision | Apply deterministic sufficiency and decision gates, then generate a grounded, versioned decision dossier. | `DecisionDossier` |

The core flow is:

```text
Intake -> Plan -> Acquire -> Normalize -> Analyze -> Decide
                                      ^        |
                                      |        v
                                      +-- Gap policy
```

Phase 5 does not create a second acquisition pipeline. It controls a bounded `gap_driven` loop through Phases 3, 4, and 6. Primary-validation gaps are kept separate and cannot be closed by additional web research.

## Planned platform architecture

DemandRift is designed as a TypeScript/Node.js modular monolith with clear, versioned contracts between phase modules.

- Next.js for the web and API layer
- PostgreSQL as the primary transactional and analytical store
- S3-compatible object storage for immutable raw artifacts
- Temporal, behind an adapter boundary, for durable workflows
- A provider-neutral AI Gateway with schema validation, model routing, prompt versioning, and cost accounting
- A policy-controlled connector runtime behind a shared Egress Gateway
- Optional isolated Playwright and Python analytics workers
- OpenTelemetry-based traces, metrics, structured logs, and audit records

Cross-cutting platform modules own tenant isolation, source policy, workflow state, budget reservations, citation binding, storage, and observability. Shared contracts are planned under `packages/contracts` using Zod and JSON Schema.

## Non-negotiable evidence rules

- An unconfirmed AI hypothesis cannot seed research.
- A search result is not fetched evidence, and an unavailable source is not a no-results finding.
- Duplicates and reposts are not independent evidence.
- A citation must bind an exact quote to offsets, content hashes, and a normalization version.
- Stated willingness to pay is not observed payment behavior.
- Absence of complaints is not evidence of satisfaction.
- Evidence scarcity in a new market is not, by itself, a Kill signal.
- AI cannot bypass source, tenant, budget, citation, or decision-policy gates.

## Planning documents

Read the project documents in this order:

1. [`Ust-Yonetim-Ana-Mimari-Plani.md`](Ust-Yonetim-Ana-Mimari-Plani.md) — system scope, phase boundaries, and integration order
2. [`Platform-Temeli.md`](Platform-Temeli.md) — shared technical architecture and invariants
3. [`Faz1-Plan.md`](Faz1-Plan.md) through [`Faz7-Plan.md`](Faz7-Plan.md) — phase-specific plans
4. [`.orchestrator/SYSTEM.md`](.orchestrator/SYSTEM.md) — delivery control plane and evidence-based work-item lifecycle

## Repository map

- [`research/source-access-lab/`](research/source-access-lab/) — source-access
  evidence, provenance indexes, reproducible tools, tests, and constrained
  pilots.
- [`research/source-access-lab/docs/`](research/source-access-lab/docs/) —
  dated access reports and pilot contracts, separate from canonical evidence.
- [`research/`](research/) — research workspaces and internal market records.
- [`tasks/`](tasks/) — durable owner-specific project tasks. The current
  research-design brief is [`tasks/ayselin-task/`](tasks/ayselin-task/).
- [`internal/pazar/`](internal/pazar/) — private market-positioning record;
  it is not product-runtime data.

## Local configuration

Only safe templates are committed. Copy the appropriate template and replace blank or `replace-with-*` values locally:

```powershell
Copy-Item .env.example .env.local
```

Use `.env.test.example` as the basis for isolated test configuration. Real `.env` variants are ignored by Git and must never be committed.

## License

DemandRift is available under the [MIT License](LICENSE).
