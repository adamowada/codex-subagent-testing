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

- Import validation still needs to reject malformed optional date fields instead
  of letting host libraries coerce them into plausible-looking values.
- CSV output must remain byte-stable across languages and hosts. Use a single
  deterministic ordering and escaping contract for every report path.
- Support views increasingly involve source and destination identifiers after
  account lineage changes. Corrections and voids should target the original
  event identity first, then flow through whatever lineage is visible for the
  requested view.
- Business-effective and audit-visible cutoffs are separate dimensions. Do not
  collapse them into one timestamp; decide which facts are known before deciding
  which facts belong in the business view.
- Correction and void operations compose. A robust replay pass should handle
  operations against ordinary events and lineage-changing events without
  depending on the order or wording of a particular ticket.
- Billing compatibility still depends on exact integer money math. Avoid
  floating-point shortcuts for prorations, credits, charges, quantities, or
  old/new plan transitions.
- Archival timestamp normalization should preserve the represented UTC instant
  across supported year ranges instead of relying on host constructor quirks.
- Support now compares the same imported ledger through point-in-time
  summaries, CSV reports, parity checks, and replay digests. These surfaces
  should derive from one canonical replay model; do not fix a summary path while
  leaving reporting, duplicate handling, or audit/business cutoff behavior to a
  separate path-specific interpretation.
