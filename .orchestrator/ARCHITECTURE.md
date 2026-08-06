# Orchestrator Mimari Kararları

## Kontrol düzlemi

Sistem, AI agent framework daemon'ı değildir. Muhakemeyi manager modele; invariant, scheduling, history ve handoff üretimini dependency-free Node çekirdeğine verir.

```text
Manager reasoning
  + JSON run graph
  + JSONL append-only events
  + immutable results
  + platform adapters
  + role protocols
```

## Neden proje runtime'ından ayrı?

Ürün runtime'ı Temporal, PostgreSQL, object storage, connector ve AI Gateway içerir. Orchestrator yalnız bunların geliştirilmesini yönetir. İki orchestration katmanı birbirine karıştırılmaz:

- `.orchestrator`: geliştirme agent control plane'i.
- `packages/platform-workflow`: ürünün runtime workflow'u.

## Sabit roller ve dinamik uzmanlık

PM, architecture, implementer, reviewer, verifier, security/data ve integration sorumlulukları tekrar eden governance rolleri olduğu için kalıcı protokoldür. Faz/teknoloji uzmanlığı sabit agent listesi değildir; work item `domains` ve `capabilities` ile atanır.

Örnek capabilities:

```text
phase-1-intake
phase-2-research-planning
connector-search
connector-social
egress-security
normalization-dedup
citation-binding
claim-extraction
semantic-clustering
decision-policy
temporal-workflow
postgres-tenancy
evaluation-calibration
```

## JSON graph ve küçük lifecycle

Domain/kind açık uçlu; lifecycle küçüktür. Review veya integration state değildir çünkü kendi girdisi, sonucu, agent'ı ve acceptance kanıtı vardır.

## Contract-first graph

Faz sınırını geçen her özellik en az şu yapıya ayrılır:

```text
pm-scope
  -> architecture-contract
     -> implementation(s)
        -> independent-review
        -> verification
           -> integration
              -> pm-acceptance
```

Küçük ve düşük riskli tek-modül değişikliklerinde PM scope ile contract aynı item olabilir; risk gate politikası değişmez.

## Platform bağımsızlığı

Canonical run platform tool adlarını içermez. Codex, Cursor ve Claude adapter'ları dispatch guidance verir. Native subagent/worktree varsa kullanılır; yoksa `render` paste-ready prompt üretir.

## History ve concurrency

- `run.json` güncel snapshot.
- `events.jsonl` append-only audit.
- `results/` immutable attempt sonuçları.
- `revision` optimistic concurrency.
- `.lock` kısa filesystem mutation lock'u.

## Projeye özgü kalite invariant'ları

1. Onaysız AI hypothesis araştırma scope'una geçemez.
2. Search result fetched evidence değildir.
3. Unavailable source no-results değildir.
4. Duplicate bağımsız kanıt değildir.
5. Citation offset + content hash + version taşır.
6. Stated WTP observed payment değildir.
7. Complaint absence satisfaction değildir.
8. New market evidence scarcity Kill değildir.
9. Faz 5 ikinci connector runtime kuramaz.
10. Faz 7 primary ve secondary validation gap'i ayırır.

Bu invariant'ları etkileyen item `high` veya `critical` risk alır ve architecture/security review gerektirir.

## Repository hedef yapısı

```text
apps/web
apps/worker
apps/browser-worker
apps/analytics-worker
packages/contracts
packages/platform-*
packages/phase-*
packages/connectors/*
infra/*
tests/{unit,contract,integration,security,evaluation,e2e}
```

Orchestrator başlangıçta bu paths yoksa hata saymaz; catalog bunları `exists:false` gösterir.

## Genişletme kuralı

Yeni kalıcı role ancak farklı run'larda tekrar eden ayrı sorumluluk ve farklı permission/model/tool ihtiyacı kanıtlanırsa eklenir. Yeni relation veya lifecycle state, mevcut graph semantiğiyle kayıpsız ifade edilemiyorsa eklenir.
