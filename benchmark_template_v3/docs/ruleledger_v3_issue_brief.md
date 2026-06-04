# RuleLedger V3 Issue Brief

## Problem

RuleLedger v2 grew into a monolithic starter implementation. It is hard to
audit, easy to patch in a case-specific way, and does not resemble the
multi-file software-engineering work that a real subscription ledger would
require.

RuleLedger v3 keeps the v2 behavior contract but expects the implementation to
be maintainable under future feature work. Public callers should still import
through the existing TypeScript and Python entrypoints, while implementation
logic should be organized around parsing, normalization, replay, billing,
reporting, and parity-friendly data shapes.

## Requirements

1. Preserve all v1 and v2 public APIs in TypeScript and Python.
2. Preserve v2 bitemporal semantics, corrections, voids, account merges,
   billing proration, reporting, and TypeScript/Python parity.
3. Keep compatibility behavior visible in `docs/ruleledger_v2_semantics.md`.
4. Avoid one-off handling of visible fixtures. Implement general logic.
5. Make large ledgers practical. Avoid nested scans over all events when a
   dictionary, precomputed lineage map, or sorted replay pass is sufficient.
6. Keep CSV output byte-stable across TypeScript and Python.
7. Keep public tests readable and do not expose private cases.
8. Organize new work so future changes can be reviewed by module rather than by
   scanning one large file.
9. Treat compatibility runtime files as migration scaffolding. When v3 behavior
   touches a clear domain area, prefer implementing or extracting it in that
   domain module rather than expanding the runtime indefinitely.
10. Do not treat the compatibility runtime as the final architecture. A v3
    solution should leave normalization, replay, billing, and reporting logic
    reviewable in their domain modules, even if small compatibility wrappers
    remain for older public APIs. Avoid leaving a second, stale runtime
    implementation that can drift from the public entrypoints.

## Regression Expectations

Existing v2 behavior is pass-to-pass behavior for v3. Any v3 implementation
that solves new issue requirements while breaking old normalization, replay,
reporting, proration, or parity behavior is incomplete.

## Performance Expectations

RuleLedger should process large event lists using predictable replay ordering
and near-linear account aggregation after sorting. The benchmark may include
large generated ledgers to catch implementations that repeatedly rescan full
event lists for every account, merge, correction, report row, or view cutoff.

## Maintainability Expectations

The public entrypoints may remain small facades, but production logic should be
structured into reviewable helpers or modules. A giant rewrite that happens to
pass a few examples is risky and should score poorly under judge and
minimality/maintainability review.

Support escalations for v3 are intentionally issue-style rather than a complete
truth table. Expect future views to combine audit cutoffs, business-effective
cutoffs, duplicate event IDs, corrections, voids, account merges, and reporting
in ways that are not all enumerated in the public examples.

## Recent Support Escalations

- A malformed optional invoice period timestamp should fail normalization. Do
  not let host date libraries silently roll values like a February 30 period end
  into a different valid date.
- CSV report row order must be byte-stable across languages and hosts. Sort
  account IDs by plain deterministic string order, not by locale-aware collation
  or natural numeric grouping.
- Corrections and voids recorded against a source account after an account merge
  still target the original event. If the corrected or voided event contributes
  value that the destination inherited through the merge, the destination view
  and report row should reflect the visible operation.
