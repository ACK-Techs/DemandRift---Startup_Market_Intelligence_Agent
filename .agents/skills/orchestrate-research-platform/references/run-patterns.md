# Reusable run graph patterns

## Single module

`scope-contract -> implement -> review -> verify -> pm-acceptance`

## Cross phase

`pm-scope -> shared-contract -> producer/consumer implementations -> review -> verification -> integration -> acceptance`

## Connector

`source-policy-review -> connector-contract -> connector-implement -> security-review + connector-verify -> integration`

## Decision policy

`epistemic-rule-spec -> policy-implement -> adversarial-review + golden-evaluation -> decision-integration`

## Revision

Keep failed item immutable. Add a new item with `relations.revises=[failed-item]`, then new review and verify items.

## Alternatives

Create one candidate item per solution with identical acceptance rubric. Add a read-only `comparison` item depending on all candidates and record selection in `run.decisions`.
