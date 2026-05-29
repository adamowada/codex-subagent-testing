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
right module as changes become necessary.

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
right module as changes become necessary. The Python package should keep
JSON-compatible field names in public output so TypeScript and Python results
can be compared directly.

## Compatibility Boundary

Public callers should not need to know the internal module shape. Public tests
and hidden tests call the documented entrypoints only.

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

Implementations that scatter equivalent logic across many branches, mutate
input events unexpectedly, or rely on public fixture names are unlikely to be
robust.
