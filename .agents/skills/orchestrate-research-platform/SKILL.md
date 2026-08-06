---
name: orchestrate-research-platform
description: Manage and execute development of this startup research and decision platform through the repository's central .orchestrator run graph. Use for project planning, PM decomposition, architecture/contracts, implementation, connector work, Faz 1–7 changes, code review, verification, integration, resuming prior work, or coordinating Codex/Cursor/Claude agents. Enforces full project scope, phase boundaries, evidence/citation/decision invariants, risk gates, and result contracts.
---

# Orchestrate Research Platform

Use `.orchestrator` as the source of truth for non-trivial project work. Do not manage multi-step implementation only in conversation memory.

## Start

1. Read repository-root `Ust-Yonetim-Ana-Mimari-Plani.md` completely.
2. Read repository-root `Platform-Temeli.md` completely.
3. Read `.orchestrator/SYSTEM.md` completely.
4. Read the relevant `FazN-Plan.md` and role file under `.orchestrator/roles/`.
5. Run `node .orchestrator/bin/orchestrator.mjs discover` when catalog is missing or repository structure changed.
6. Inspect active runs before creating a duplicate run.

For phase and capability selection, read [phase-routing.md](references/phase-routing.md). For reusable graph shapes, read [run-patterns.md](references/run-patterns.md).

## Choose workflow

### Answer, audit, or design only

Use a read-only `analysis`, `specification`, `architecture-review`, or `pm-planning` item. Do not infer implementation authorization.

### Build or change

Create or resume a run. Apply contract-first ordering:

```text
PM scope -> architecture/contract -> implement -> review -> verify -> integration -> PM acceptance
```

Add independent review and verification for every item required by `.orchestrator/config.json` risk policy.

### Diagnose

Create read-only discovery/reproduction items first. Do not add a fix item unless the request includes fixing or the user later authorizes it.

### Resume

Run `validate`, `status`, then inspect `events.jsonl` and `results/`. Reconcile stale `active` ownership before redispatch.

## PM Manager protocol

- Preserve the complete approved scope; never remove planned connector or algorithm families for speed.
- Select components adaptively per research plan instead of running everything blindly.
- Make producer/consumer contracts explicit before implementation.
- Assign role, capabilities, write scopes, risks, approvals, outputs, and exact acceptance to every item.
- Keep architecture, implementation, review, verification, and integration ownership separate.
- Record durable decisions in `run.decisions`, not only prose.
- Create revision items; never rewrite failed history.
- Do not mark completion until accepted integration and documentation synchronization exist.

## Dispatch protocol

1. Run `sync` and `status`.
2. Select the first safe batch.
3. Prefer native subagents for bounded independent items when available.
4. Use worktrees for parallel writers when supported; otherwise serialize.
5. Render a platform handoff when native delegation is unavailable:

```powershell
node .orchestrator/bin/orchestrator.mjs render <run.json> <item-id> --platform codex
```

6. Require `.orchestrator/contracts/result.schema.json` output.
7. Record accepted attempt with `record`; do not manually set `done`.
8. If the active run records explicit user authorization for commits, require one atomic Conventional Commit after each write item passes its assigned checks. Use `type(scope): summary`, choose the phase/platform module/work-item area as `scope`, and include the work item ID in the body or footer.
9. Implementers never push. Push requires explicit user authorization and may be performed only by the upper manager for reviewed, verified, and accepted integration checkpoints; never force-push.

## Role routing

- `pm-planning`, backlog, scope, acceptance: `roles/pm-manager.md`
- architecture, ADR, schema, phase boundary: `roles/architecture-manager.md`
- code/config/test/docs mutation: `roles/code-implementer.md`
- independent diff/contract review: `roles/independent-reviewer.md`
- test/evaluation execution: `roles/verifier.md`
- connector/crawler/tenant/PII/cost/citation: `roles/security-data-reviewer.md`
- accepted cross-module assembly: `roles/integration-manager.md`

## Non-negotiable product invariants

- Unconfirmed AI hypotheses cannot seed research.
- Search results are not fetched evidence.
- Source unavailable is not no-results.
- Duplicate/repost is not independent evidence.
- Citation requires quote, offset, content hash, and normalization version.
- Stated willingness to pay is not observed payment behavior.
- Absence of complaints is not satisfaction.
- Evidence scarcity in a new market is not a Kill signal.
- Faz 5 reuses Faz 3 acquisition; it cannot create another connector pipeline.
- Primary validation gaps cannot be closed with more secondary web research.
- AI cannot override source, tenant, budget, citation, or decision hard gates.
- Do not design or implement Faz 8 without explicit user start approval.

## Completion

Return the outcome, accepted artifacts, executed checks, authorized write-item commit SHA, remaining risks, and next graph state. Never claim a check ran when it did not. Read-only items do not create empty commits. Never commit or push without explicit user authorization; push only reviewed, verified, and accepted integration checkpoints, and never force-push.
