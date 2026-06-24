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

## Resolution Standard

Do not stop after making one visible surface look correct. A credible v3 fix
should be explainable as one canonical replay model that drives point-in-time
summaries, CSV reports, TypeScript/Python parity checks, and replay digests.
Before finalizing, reconcile the incident shape end to end: strict import
normalization, deterministic replay ordering, audit-visible versus
business-effective cutoffs, correction and void target resolution, merge
lineage, exact billing, and report serialization should agree rather than live
in separate patches.

If a rule seems necessary for only one screen, first check whether that rule
belongs in normalization, replay, billing, or reporting so every public surface
inherits the same behavior. This is not a request to reconstruct private
fixtures; it is the expected way to resolve the visible incident reports
without creating another split-brain runtime path.

## Recent Support Escalations

Support has stopped filing isolated rule tickets for this work. The recent
escalations read more like incident reports, and the examples below are not a
complete truth table.

### Month-Close Reconciliation Drift

Finance says a customer looks correct in the account summary dashboard until
the same imported ledger is reviewed through CSV exports, parity checks, and
replay fingerprints. The mismatch appears after several accounts were folded
together and later support actions were entered against identifiers that the
operator saw in the older account history. Some of those actions were visible
to audit before they belonged in the business view for the requested close
date. Other actions were themselves retracted after review.

The business ask is to make those surfaces tell one story. A fix that special
cases the summary screen but leaves reporting or parity on a separate replay
path will come back as another reconciliation incident.

### Backfill Import Drift

Data operations is backfilling older ledgers from customer archives. A few rows
look harmless in one host runtime but land differently in another: optional
invoice dates are not always real dates, older timestamps must keep their
represented instant, and large seat-count changes have exposed cent-level
rounding drift. The same backfill also made CSV rows move between machines
after account identifiers were imported in a mix of human and system formats.

The migration team wants one boring import and reporting contract that works
the same way in TypeScript and Python. Normalize records strictly, keep money
math exact, and make replay/report output deterministic enough that a byte
comparison is meaningful.
