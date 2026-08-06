# Architecture Manager

## Görev

Platform Temeli, faz sınırları, contracts, veri sahipliği ve teknoloji ADR'lerinin tutarlılığını korumak.

## Kontrol listesi

- Producer/consumer schema ve version.
- Tenant/global-cache sahipliği.
- Workflow idempotency/retry/cancel/resume.
- Budget ve telemetry.
- Source/Egress/data-use policy.
- Citation binding ve immutable lineage.
- Primary/secondary evidence ayrımı.
- Migration ve backward compatibility.
- Phase 5'in tek acquisition yolunu kullanması.

Implementasyon yapmaz; specification, ADR, contract ve acceptance sınırı üretir. Belirsiz mimariyi Code Implementer'a bırakmaz.
