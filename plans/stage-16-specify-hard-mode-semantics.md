# Stage 16: Specify Hard-Mode Semantics

## Purpose

Stage 16 turns RuleLedger v2 from a visible hard-mode vocabulary into an
explicit semantic contract. Stage 15 added the v2 starter template, public
examples, and field surface. Stage 16 should define exactly how those fields
behave so the oracle, hidden generator, hidden runner, starter tests, and
measured agents all target the same rules.

This stage should answer:

```text
Can an implementation agent, oracle author, and hidden-case generator all read
one v2 semantics document and make the same decisions for hard-mode RuleLedger
behavior?
```

Stage 16 is primarily a specification stage. It should avoid building the
private oracle, final hidden cases, hidden-runner operations, or scoring changes.

## Scope

Stage 16 owns:

- Defining bitemporal business-time and audit-time semantics.
- Defining canonical replay ordering after normalization.
- Defining correction and void behavior.
- Defining lifecycle precedence for all v2 event families.
- Defining account merge behavior and canonical account reporting.
- Defining billing period, proration, currency, and rounding rules.
- Defining CSV and report stability rules.
- Naming rule identifiers that later oracle and hidden-case work can reuse.
- Updating v2 public documentation or adding a dedicated v2 semantics spec.
- Adding small public examples for each major hard-mode concept.

Stage 16 does not own:

- Implementing the private v2 oracle.
- Generating final v2 hidden cases.
- Upgrading hidden-runner operation types.
- Reweighting scoring or report aggregation.
- Changing the default v1 experiment config.
- Solving every v2 behavior inside the starter implementation.
- Editing locked top-level source-of-truth documents unless explicitly
  requested.
- Committing generated run output under `runs/`.

## Inputs

Stage 16 starts from:

```text
benchmark_template_v2/
configs/ruleledger_v2.yaml
configs/scoring_v2.yaml
hidden_tests/cases_v2_placeholder/
plans/stage-15-create-v2-starter-template.md
PLANS.md
```

The v2 starter currently exposes the hard-mode fields and basic examples. Stage
16 should make those examples precise and extend the documentation so later
implementation stages can use it as a contract.

## Recommended Outputs

Use one or both of these paths:

```text
plans/stage-16-specify-hard-mode-semantics.md
benchmark_template_v2/docs/semantics.md
```

If the v2 starter needs measured agents to see the rule contract, add or link a
visible starter document such as:

```text
benchmark_template_v2/docs/ruleledger_v2_semantics.md
```

Keep planning rationale in `plans/`. Put only the agent-facing benchmark
contract in the v2 starter.

## Rule Naming

Every hard-mode rule should have a stable name that future stages can reference.
Suggested prefixes:

```text
BT-*  bitemporal behavior
OR-*  replay ordering
CV-*  corrections and voids
LC-*  lifecycle precedence
MG-*  account merge behavior
BL-*  billing and proration
RP-*  reporting and CSV stability
PY-*  TypeScript/Python parity
```

Examples:

```text
BT-001 missing effective_at defaults to timestamp
BT-002 missing recorded_at defaults to timestamp
OR-001 replay sorts by effectiveAt, recordedAt, sequence, id
RP-001 CSV booleans are lowercase
```

Rule identifiers should appear in public examples, oracle comments or metadata,
hidden case categories, and runner tests once those later stages are built.

## Bitemporal Semantics

Define two timelines:

- Business time: controlled by `effectiveAt`.
- Audit time: controlled by `recordedAt`.

Required decisions:

- `timestamp` remains the raw event timestamp after normalization.
- Missing `effective_at` defaults to normalized `timestamp`.
- Missing `recorded_at` defaults to normalized `timestamp`.
- Audit views include only events whose `recordedAt` is at or before the audit
  cutoff.
- Business summaries apply included events according to `effectiveAt`.
- If a function accepts only one `asOf` value, define whether it means business
  time, audit time, or both.
- If later APIs need separate business and audit cutoffs, define their names and
  expected behavior before hidden-runner work begins.

Open questions to resolve in the spec:

- Should public functions keep a single `asOf` argument for v2, or should hidden
  runner operations pass richer inputs such as `business_as_of` and
  `audit_as_of`?
- Should events with future `effectiveAt` but past `recordedAt` be visible in
  audit output but excluded from current business state?

## Replay Ordering

Define replay ordering as:

```text
(effectiveAt, recordedAt, sequence, id)
```

Required decisions:

- Sorting happens after normalization.
- Timestamp comparisons use canonical ISO UTC strings with millisecond
  precision.
- `sequence` must be an integer.
- Missing `sequence` defaults to `0`.
- Duplicate event ids are handled deterministically.
- Tie-breaking by `id` is lexical and stable across TypeScript and Python.

Open questions to resolve:

- Should duplicate event ids be first-wins, last-wins, or invalid?
- Should duplicate ids across merged accounts follow the same rule as duplicate
  ids within one account?

## Corrections And Voids

Define correction and void behavior:

- `correctionOf` references the event id being corrected.
- `voidedEventId` references the event id being voided.
- A valid correction replaces the referenced event for audit views at or after
  the correction event's `recordedAt`.
- A valid void removes the referenced event for audit views at or after the void
  event's `recordedAt`.

Required decisions:

- What happens when the referenced event does not exist.
- What happens when the referenced event belongs to another account.
- How correction chains work.
- How multiple corrections of the same event are ordered.
- How void-after-correction and correction-after-void conflicts resolve.
- Whether corrected or voided events still appear in audit reports as lineage.
- Which fields in a correction are replacement fields versus metadata fields.

Recommended starter boundary:

- The visible v2 starter may normalize and expose correction/void fields without
  fully solving correction graph behavior.
- The spec should still be precise enough for the Stage 17 oracle.

## Lifecycle Precedence

Define event families and state transitions for:

- Account open.
- Trial start and trial end if added as v2 types.
- Plan change.
- Pause.
- Resume.
- Cancel.
- Reactivate.
- Close.
- Payment failure.
- Payment recovery.
- Coupon.
- Usage.
- Seat change.
- Account merge.

Required decisions:

- Which statuses exist in normalized account state.
- Which events can transition from each status.
- Whether `closed` is terminal.
- Whether `cancel` differs from `close`.
- Whether `pause` blocks usage, billing, entitlements, or all three.
- Whether payment failure makes an account `past_due` but still entitled.
- Whether payment recovery always restores `active`.
- How plan changes behave while paused, cancelled, or closed.
- How usage and seat changes behave before account open or after close.

Suggested explicit status vocabulary:

```text
pending
trialing
active
paused
past_due
cancelled
closed
```

Only include statuses that later stages are ready to test and support.

## Account Merge Semantics

Define account merge behavior for `mergeFromAccountId`.

Required decisions:

- The destination `accountId` is the canonical account id.
- Which state migrates from the source account.
- Whether source account reports disappear, remain as aliases, or become
  redirected records.
- How payments, usage, invoices, coupons, plans, seats, and billing periods
  migrate.
- How duplicate event ids are handled across source and destination accounts.
- How merge lineage is represented in summaries and CSV exports.
- Whether later source-account events after merge are ignored, redirected, or
  treated as invalid.

Recommended output fields:

```text
accountId
mergedFromAccountIds
canonicalAccountId
```

Only add fields to the public contract if they are needed by oracle and reports.

## Billing And Proration

Define billing rules for:

- `periodStart`.
- `periodEnd`.
- `invoiceId`.
- `currency`.
- `quantity`.
- `seatDelta`.
- `amountCents`.
- Decimal `amount` inputs.

Required decisions:

- Money uses integer minor units.
- Currency codes normalize to uppercase ISO-style three-letter strings.
- Currencies may not be mixed within one invoice unless explicitly allowed.
- Billing periods are half-open intervals: `[periodStart, periodEnd)`.
- Proration uses exact integer arithmetic where possible.
- Fractional minor units use deterministic half-away-from-zero rounding.
- Negative prorations and credits follow the same rounding rule.
- Seat counts cannot become negative.
- Quantity must be non-negative unless a specific event type allows negative
  adjustments.

Half-away-from-zero examples should be explicit:

```text
 1.5 ->  2
 1.4 ->  1
-1.5 -> -2
-1.4 -> -1
```

Open questions to resolve:

- Whether all billing calculations are invoice-based or event-based.
- Whether proration is calculated by seconds, milliseconds, calendar days, or
  whole billing days.
- Whether leap days and daylight-saving transitions are normalized through UTC
  instants only.

## Reporting And CSV Stability

Define report output exactly.

Required decisions:

- Header order is stable and specified.
- Row ordering is stable and specified.
- Booleans serialize as `true` and `false`.
- Null or absent optional values serialize as empty strings.
- Array fields serialize with a stable separator, likely `|`.
- Array values sort or preserve deterministic replay order, but the choice must
  be specified.
- CSV escaping rules are explicit if values can contain commas, quotes, or
  newlines.
- TypeScript and Python must produce byte-identical CSV for the same summaries.

Suggested v2 CSV fields to specify:

```text
account_id
status
plan
total_paid_cents
currency
seats
usage
usage_limit
over_limit
coupon_code
coupon_active
invoice_ids
last_invoice_id
last_period_start
last_period_end
merged_from_account_ids
closed_at
last_event_at
```

## Normalization Rules

Define validation and normalization for all raw v2 fields:

```text
effective_at -> effectiveAt
recorded_at -> recordedAt
sequence -> sequence
currency -> currency
quantity -> quantity
seat_delta -> seatDelta
merge_from_account_id -> mergeFromAccountId
correction_of -> correctionOf
voided_event_id -> voidedEventId
invoice_id -> invoiceId
period_start -> periodStart
period_end -> periodEnd
```

Required decisions:

- Required fields and optional fields.
- Error codes for missing, blank, or invalid fields.
- Whether optional invalid fields fail the whole event.
- Whether unknown extra fields are preserved, ignored, or rejected.
- Whether timestamp strings without a timezone are accepted as UTC or rejected.
- Whether integer-like strings are accepted for numeric fields.

Stage 15 currently accepts some starter-friendly defaults. Stage 16 should make
the final intended behavior explicit before hidden cases are generated.

## Public Examples

Add or refine visible examples for:

- One bitemporal late-arriving event.
- One correction or void.
- One account merge.
- One proration.
- One CSV parity expectation.

Examples should be small, hand-authored, and public by design. They should not
reuse hidden fixtures or future hidden expected outputs.

Recommended files:

```text
benchmark_template_v2/fixtures/public_semantics_examples.json
benchmark_template_v2/fixtures/public_expected_semantics_summary.json
benchmark_template_v2/fixtures/public_expected_semantics_report.csv
```

Avoid making public examples so exhaustive that they become the hidden oracle.

## Starter Updates

Stage 16 may update the v2 starter documentation and public tests, but should be
careful about starter implementation scope.

Allowed starter changes:

- Add visible docs for hard-mode semantics.
- Add public examples that encode the rule names.
- Add small public tests for the examples.
- Tighten obvious normalization behavior if it avoids ambiguity.

Avoid:

- Fully implementing hidden hard-mode behavior in the starter.
- Adding private oracle logic to public code.
- Adding large dependencies.
- Changing v1 behavior.

## Hidden-Test Privacy

Stage 16 should not create final hidden cases. Any examples added during this
stage are public examples and should remain in the starter.

Do not include:

- Hidden case ids.
- Generated hidden fixture data.
- Private oracle expected outputs.
- Full hidden category payloads.

## Implementation Order

1. Review Stage 15 v2 starter docs, fixtures, tests, and config.
2. Choose the v2 semantics document path.
3. Draft stable rule identifiers for every hard-mode area.
4. Specify normalization and timestamp defaults.
5. Specify bitemporal audit/business behavior.
6. Specify replay ordering and duplicate-id behavior.
7. Specify correction and void behavior.
8. Specify lifecycle precedence.
9. Specify account merge behavior.
10. Specify billing, proration, currency, and rounding behavior.
11. Specify report and CSV stability.
12. Add small public examples and expected outputs if needed.
13. Add or update public tests that assert the examples.
14. Add repository tests that verify the semantics document exists and is
    referenced by the v2 starter docs or config if appropriate.
15. Run v2 public commands and repository tests.

## Verification Commands

From the v2 starter template directory:

```powershell
npm ci
npm run typecheck
npm run test:public
python -m pytest -q tests_public_py
```

From the repository root:

```powershell
python -m pytest
python -m harness.validation --config configs/initial_experiment.yaml --skip-preflight --allow-missing-report
python -m harness.validation --config configs/ruleledger_v2.yaml --skip-preflight --allow-missing-report
git diff --check
```

If a dry run is useful:

```powershell
.\scripts\run_experiment.ps1 -Config configs/ruleledger_v2.yaml -DryRun -NoReport
```

Use a temporary runs root for dry-runs when possible.

## Risks

Ambiguous spec:

If Stage 16 leaves hard choices unresolved, the Stage 17 oracle and measured
agents will encode different interpretations.

Over-implementation:

If this stage fully solves the hard-mode starter, hidden tests lose some
calibration value.

Cross-language drift:

Rules that rely on language-specific date, float, sort, or CSV behavior can
create accidental TypeScript/Python mismatches.

Hidden leakage:

Public examples should be small and hand-authored. They should not reveal future
hidden case data.

V1 regression:

Stage 16 should preserve v1 template, v1 config, and v1 scoring behavior.

Rounding ambiguity:

Billing and proration rules must avoid floating-point arithmetic and specify
rounding with examples.

## Done When

- A v2 semantics document or v2 README section defines every hard-mode rule
  needed by later stages.
- Rule identifiers exist for bitemporal behavior, replay ordering, corrections
  and voids, lifecycle precedence, account merges, billing, reporting, and
  parity.
- Public examples cover at least one bitemporal case, one correction or void,
  one account merge, one proration, and one CSV parity expectation.
- The oracle, hidden generator, hidden runner, and starter tests have a clear
  rule-name vocabulary to reference in later stages.
- V2 docs define exact output fields, timestamp formats, money representation,
  rounding, null handling, boolean serialization, and row/header ordering.
- The v2 starter remains intentionally incomplete against future hidden
  hard-mode categories.
- V1 behavior remains unchanged.
- No hidden cases or generated run outputs are committed.
