# RuleLedger V2 Benchmark Template

RuleLedger v2 is a mixed TypeScript and Python implementation task. The public
surface keeps the v1 function names and adds v2-compatible hooks for hard-mode
views and billing helpers. The task introduces a harder subscription ledger
vocabulary: bitemporal timestamps, deterministic replay ordering, minor-unit
money, corrections and voids, account merges, seats, quantities, invoices, and
billing periods.

The starter is intentionally incomplete. Public tests are visible guidance, not
a complete scoring suite.

## Hard-Mode Semantics

The v2 semantic contract is documented in
[`docs/ruleledger_v2_semantics.md`](docs/ruleledger_v2_semantics.md). That
document defines the rule identifiers used by public examples and future hidden
cases, including bitemporal replay, corrections and voids, lifecycle
precedence, account merges, billing proration, reporting stability, and
TypeScript/Python parity.

Public examples for the contract live in
`fixtures/public_semantics_examples.json`.

## Setup

Install the pinned TypeScript dependency before running Node-based commands:

```powershell
npm ci
```

## Visible Commands

```powershell
npm run typecheck
npm run test:public
python -m pytest -q tests_public_py
```

## Public API

TypeScript exports live in `src/index.ts`:

- `parseEventLine`
- `normalizeEvent`
- `reduceAccountState`
- `evaluateEntitlements`
- `summarizeAccount`
- `exportLedgerReport`
- `normalizeEventV2`
- `reduceAccountStateV2`
- `evaluateEntitlementsV2`
- `summarizeAccountV2`
- `exportLedgerReportV2`
- `calculatePlanChangeProrationV2`

Python exports live in `ruleledger/engine.py`:

- `parse_event_line`
- `normalize_event`
- `reduce_account_state`
- `evaluate_entitlements`
- `summarize_account`
- `export_ledger_report`
- `normalize_event_v2`
- `reduce_account_state_v2`
- `evaluate_entitlements_v2`
- `summarize_account_v2`
- `export_ledger_report_v2`
- `calculate_plan_change_proration_v2`

V2 state, entitlement, and summary functions may receive a view object with
business and audit cutoffs. The object may use camelCase keys (`asOf`,
`businessAsOf`, `auditAsOf`) or snake_case keys (`as_of`, `business_as_of`,
`audit_as_of`). A single `asOf` value is interpreted as both cutoffs.

## Raw Event Fields

Required raw fields:

- `id`
- `account_id`
- `type`
- `timestamp`

Common v1 fields remain visible:

- `plan`
- `amount`
- `amount_cents`
- `coupon`
- `expires_at`
- `usage`

V2 additions:

- `effective_at`
- `recorded_at`
- `sequence`
- `currency`
- `quantity`
- `seat_delta`
- `merge_from_account_id`
- `correction_of`
- `voided_event_id`
- `invoice_id`
- `period_start`
- `period_end`

## Normalized Fields

Raw snake_case fields normalize to camelCase output fields:

- `account_id` -> `accountId`
- `effective_at` -> `effectiveAt`
- `recorded_at` -> `recordedAt`
- `amount_cents` or `amount` -> `amountCents`
- `seat_delta` -> `seatDelta`
- `merge_from_account_id` -> `mergeFromAccountId`
- `correction_of` -> `correctionOf`
- `voided_event_id` -> `voidedEventId`
- `invoice_id` -> `invoiceId`
- `period_start` -> `periodStart`
- `period_end` -> `periodEnd`

Normalized events always include `id`, `accountId`, `type`, `timestamp`,
`effectiveAt`, `recordedAt`, and `sequence`. Optional fields are omitted when
absent. CSV exports use empty strings for absent optional values.

## Representation Rules

Money uses integer minor units in normalized output. Decimal strings such as
`"49.00"` and integer `amount_cents` inputs both normalize to `amountCents`.
Credits may be negative where the semantics permit credit or adjustment values.
Currencies normalize to three-letter uppercase codes.

Timestamps normalize to canonical ISO UTC strings with millisecond precision.
When `effective_at` or `recorded_at` is absent, it defaults to the normalized
`timestamp`.

Replay order is:

```text
(effectiveAt, recordedAt, sequence, id)
```

The visible tests include small examples of out-of-order input, bitemporal
timestamps, a correction or void reference, an account merge reference, seat and
quantity changes, invoice fields, billing periods, and CSV/report parity.
Future hidden tests exercise deeper lifecycle, correction, merge, proration,
performance, and metamorphic behavior.
