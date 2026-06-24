# RuleLedger V3 Architecture Notes

These notes describe the intended implementation shape. They are visible to
measured agents and are not hidden tests.

## TypeScript Shape

The public entrypoint remains `src/index.ts`. It may re-export or delegate to
internal modules such as:

- `src/domain.ts` for event, plan, state, summary, and result types.
- `src/normalize.ts` for parsing, timestamp, money, and field normalization.
- `src/replay.ts` for sorting, deduplication, bitemporal views, corrections,
  voids, and account lineage.
- `src/billing.ts` for proration and money arithmetic.
- `src/report.ts` for CSV serialization.

The starter includes these public module boundaries. Some implementation still
delegates through a compatibility runtime, leaving measured agents with a
realistic migration path: preserve public behavior while moving logic into the
right module as changes become necessary. A reviewable v3 solution should not
leave `normalize.ts`, `replay.ts`, `billing.ts`, and `report.ts` as direct
runtime re-export facades after those areas have been changed.

## Python Shape

The public entrypoint remains `ruleledger/engine.py`. It may re-export or
delegate to package modules such as:

- `ruleledger/domain.py`
- `ruleledger/normalize.py`
- `ruleledger/replay.py`
- `ruleledger/billing.py`
- `ruleledger/reporting.py`

The starter includes these public module boundaries. Some implementation still
delegates through a compatibility runtime, leaving measured agents with a
realistic migration path: preserve public behavior while moving logic into the
right module as changes become necessary. A reviewable v3 solution should not
leave `ruleledger/normalize.py`, `ruleledger/replay.py`,
`ruleledger/billing.py`, and `ruleledger/reporting.py` as direct `_runtime`
facades after those areas have been changed. The Python package should keep
JSON-compatible field names in public output so TypeScript and Python results
can be compared directly.

## Compatibility Boundary

Public callers should not need to know the internal module shape. Public
behavior checks call the documented entrypoints, while maintainability review
may also consider whether the visible source shape follows the intended module
ownership. Compatibility runtime files may remain as wrappers, but they should
delegate into the domain modules rather than keeping a second implementation
that can diverge from the public entrypoints.

## Review Heuristics

Useful v3 implementations are expected to:

- Isolate timestamp and money parsing.
- Use one canonical replay sort.
- Represent correction and void decisions in a way that can be reasoned about
  before state application.
- Maintain account merge aliases explicitly.
- Serialize CSV through a single shared contract per language.
- Keep TypeScript and Python behavior aligned by using parallel structure and
  names where practical.
- Leave domain modules with local implementation entrypoints instead of only
  re-exporting compatibility-runtime symbols.
- Keep compatibility runtime wrappers thin once domain modules own the logic.

Implementations that scatter equivalent logic across many branches, mutate
input events unexpectedly, or rely on public fixture names are unlikely to be
robust.
