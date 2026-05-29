# RuleLedger V2 Hard-Mode Semantics

This document is the public RuleLedger v2 semantic contract. It is visible to
measured agents and should be used by the private oracle, hidden case generator,
hidden runner, public tests, and future report logic.

The starter implementation is intentionally incomplete. The rules below define
the target behavior for hard-mode v2 implementations; they do not imply that
the starter already solves every rule.

## Rule Index

### BT-001: Timestamp Canonicalization

All accepted timestamps normalize to ISO UTC strings with millisecond precision.
Timezone-aware inputs are converted to UTC. Timestamp strings without an
explicit timezone are accepted as UTC.

### BT-002: Effective Time Default

If `effective_at` is omitted, `effectiveAt` defaults to the normalized
`timestamp`.

### BT-003: Recorded Time Default

If `recorded_at` is omitted, `recordedAt` defaults to the normalized
`timestamp`.

### BT-004: Audit Visibility

An audit view includes an event only when the event's `recordedAt` is less than
or equal to the audit cutoff. Events recorded after the audit cutoff are
invisible to that view even if their `effectiveAt` is earlier.

### BT-005: Business Applicability

A business-state view applies visible events only when the event's
`effectiveAt` is less than or equal to the business cutoff. Events recorded in
time but effective in the future are visible in audit lineage but do not affect
current business state until their effective time.

### BT-006: Single As-Of Compatibility

When an existing public function accepts a single `asOf` argument, v2 treats it
as both the business cutoff and audit cutoff. V2-compatible public hooks may
receive separate `business_as_of` and `audit_as_of` values, or camelCase
`businessAsOf` and `auditAsOf` aliases, to evaluate the same ledger from
different business and audit views.

### OR-001: Replay Sort Key

After normalization, replay order is:

```text
(effectiveAt, recordedAt, sequence, id)
```

### OR-002: Sequence Rules

`sequence` must be an integer greater than or equal to zero. Missing `sequence`
defaults to `0`.

### OR-003: Duplicate Event IDs

After sorting by OR-001, the first valid event for an `id` wins. Later events
with the same `id` are ignored for state reduction. This rule applies across
merged account lineages as well as within one account.

### OR-004: Lexical Tie Break

The final replay tie break is lexical ordering by normalized `id`. TypeScript
and Python implementations must produce the same ordering for ASCII event ids.

### CV-001: Correction Reference

`correctionOf` references the normalized `id` of the event being corrected. A
correction whose target does not exist in the same canonical account lineage is
a no-op for state reduction, but it remains a normalized audit event.

### CV-002: Correction Visibility

A valid correction becomes visible at the correction event's `recordedAt`. For
audit views before that time, the original event remains active. For audit views
at or after that time, the correction replaces the referenced event.

### CV-003: Correction Replacement Shape

A correction is metadata plus replacement data. The active replacement keeps the
target event id for duplicate handling and lineage, but uses replacement
business fields from the correction event. `correctionOf` remains available for
audit output.

### CV-004: Void Reference

`voidedEventId` references the normalized `id` of the event being voided. A void
whose target does not exist in the same canonical account lineage is a no-op for
state reduction, but it remains a normalized audit event.

### CV-005: Void Visibility

A valid void becomes visible at the void event's `recordedAt`. For audit views
before that time, the referenced event remains active. For audit views at or
after that time, the referenced event is removed from business state.

### CV-006: Correction And Void Precedence

For one target event, valid correction and void operations are ordered by:

```text
(recordedAt, sequence, id)
```

The latest visible operation decides whether the target is active. A correction
activates the corrected replacement. A void makes the target inactive. A later
correction can reactivate a previously voided target.

### LC-001: Status Vocabulary

The v2 status vocabulary is:

```text
pending
trialing
active
paused
past_due
cancelled
closed
```

Implementations may omit `pending` from summaries when no account state exists.

### LC-002: Account Open

`account_opened` creates or activates the account unless the account is already
`closed`. If `plan` is present, it sets the current plan. If `quantity` is
present, it sets the initial seat count with a minimum of one.

### LC-003: Trial Events

`trial_started` moves an open account to `trialing`. `trial_ended` moves a
`trialing` account to `active` unless another event with later replay order has
already moved it to `cancelled`, `paused`, or `closed`.

### LC-004: Plan Change

`plan_changed` updates the current plan for non-closed accounts. Plan changes
while `paused`, `past_due`, or `cancelled` update the stored plan but do not by
themselves restore active entitlements.

### LC-005: Pause And Resume

`account_paused` moves a non-closed account to `paused`. A paused account keeps
its plan, invoices, payments, coupons, and accumulated usage, but active
entitlements are disabled. `account_resumed` moves a paused account to
`active`.

### LC-006: Cancel And Reactivate

`account_cancelled` moves a non-closed account to `cancelled`. A cancelled
account keeps historical state but active entitlements are disabled.
`account_reactivated` moves a cancelled account to `active`.

### LC-007: Close Is Terminal

`account_closed` moves the account to `closed`. Later lifecycle events do not
reopen a closed account. Later reporting metadata may still be recorded for
audit lineage, but it does not restore business entitlements.

### LC-008: Payment Failure And Recovery

`payment_failed` moves an `active` or `trialing` account to `past_due`.
`payment_recovered` or `payment_succeeded` moves a `past_due` account back to
`active` unless the account is `paused`, `cancelled`, or `closed`.

### LC-009: Coupons

`coupon_applied` stores the normalized coupon code and optional expiration.
Coupons are active only when the account has active entitlements and the
business cutoff is less than or equal to `couponExpiresAt`.

### LC-010: Usage

`usage_recorded` increases usage by `usage` when present, otherwise by
`quantity` when present, otherwise by zero. Usage before account open is
recorded on a pending account. Usage after close is retained for audit but does
not restore entitlements.

### LC-011: Seat Changes

`seat_delta_recorded` and any event with `seatDelta` adjust seat count. Seat
count cannot become negative.

### MG-001: Canonical Account

For `account_merged`, the event's `accountId` is the destination and canonical
account id. `mergeFromAccountId` is the source account id.

### MG-002: State Migration

At the merge event's effective time, payments, usage, invoices, coupons, seat
counts, and merge lineage from the source account migrate to the destination
account. Destination plan and status win unless the destination has no explicit
plan or status.

### MG-003: Source Account Reporting

After a merge, normal account summaries report only the canonical destination
account. Audit views may expose the source id through `mergedFromAccountIds`.

### MG-004: Merge Lineage

`mergedFromAccountIds` is a stable, de-duplicated list sorted by first migration
order. CSV output joins this list with `|`.

### MG-005: Post-Merge Source Events

Events recorded for a source account after its merge are redirected to the
canonical destination account for business state. Audit output should preserve
their original `accountId` if a future operation exposes raw lineage.

### BL-001: Money Representation

All normalized money is represented as integer minor units. Decimal `amount`
inputs must have exactly two fractional digits. `amount_cents` inputs must be
integers. Credit and adjustment values may be negative; implementations should
not reject a negative `amount_cents` solely because of its sign.

### BL-002: Currency Rules

Currency codes normalize to uppercase three-letter strings. One invoice may not
mix currencies. If an account has multiple currencies across unrelated invoices,
reports use the most recent event currency unless a future report exposes
per-invoice currency detail.

### BL-003: Billing Period Boundaries

Billing periods are half-open UTC intervals:

```text
[periodStart, periodEnd)
```

`periodEnd` must be greater than `periodStart`.

### BL-004: Proration Formula

Proration uses UTC milliseconds:

```text
prorated_minor_units =
  round_half_away_from_zero(full_period_minor_units * active_ms / period_ms)
```

Implementations should use integer arithmetic or rational arithmetic, not
floating point, for scored calculations.

### BL-005: Half-Away-From-Zero Rounding

Fractional minor units round half away from zero:

```text
 1.5 ->  2
 1.4 ->  1
-1.5 -> -2
-1.4 -> -1
```

### BL-006: Plan Change Proration

For a mid-period plan change, the old plan receives a credit for the unused
portion of the period and the new plan receives a charge for the remaining
portion. Both values use BL-004 and BL-005.

### BL-007: Seat And Quantity Billing

Seat and quantity multipliers are applied before proration. Seat counts and
non-adjustment quantities cannot be negative.

### RP-001: Header Stability

V2 CSV reports use the exact header order documented in the Reporting Contract
section below.

### RP-002: Row Ordering

CSV rows sort lexically by `accountId`.

### RP-003: Boolean Serialization

Booleans serialize as lowercase `true` and `false`.

### RP-004: Null Serialization

Null or absent optional values serialize as empty strings.

### RP-005: Array Serialization

Array fields serialize as `|`-joined values. Values preserve deterministic
state order unless a field-specific rule says otherwise.

### RP-006: CSV Escaping

If a value contains a comma, quote, carriage return, or newline, it must be
quoted according to RFC 4180 style CSV escaping. Existing public examples avoid
these characters, but hidden reporting cases may include them.

### PY-001: Cross-Language Parity

For the same normalized inputs and cutoffs, TypeScript and Python must produce
JSON-compatible equivalent summaries and byte-identical CSV.

## Normalization Contract

Required raw fields:

```text
id
account_id
type
timestamp
```

V2 raw fields normalize as:

```text
account_id -> accountId
effective_at -> effectiveAt
recorded_at -> recordedAt
amount_cents -> amountCents
amount -> amountCents
expires_at -> couponExpiresAt
seat_delta -> seatDelta
merge_from_account_id -> mergeFromAccountId
correction_of -> correctionOf
voided_event_id -> voidedEventId
invoice_id -> invoiceId
period_start -> periodStart
period_end -> periodEnd
```

Unknown extra fields are ignored by the public output contract. Invalid known
optional fields fail normalization with an `invalid_*` issue. Missing or blank
required fields fail normalization with `missing_*` or `blank_*` issues.

## Reporting Contract

V2 CSV reports use this exact header:

```text
account_id,status,plan,total_paid_cents,currency,seats,usage,usage_limit,over_limit,coupon_code,coupon_active,invoice_ids,last_invoice_id,last_period_start,last_period_end,merged_from_account_ids,closed_at,last_event_at
```

Required summary fields:

```text
accountId
status
plan
features
usage
usageLimit
overLimit
totalPaidCents
currency
seats
couponCode
couponActive
invoiceIds
lastInvoiceId
lastPeriodStart
lastPeriodEnd
mergedFromAccountIds
closedAt
lastEventAt
```

Public functions that return summaries should keep these field names stable.
Future runner operations may add audit-lineage fields, but existing fields must
retain their meaning.

## Public Example Fixtures

The public semantics examples live in:

```text
fixtures/public_semantics_examples.json
fixtures/public_semantics_expected_report.csv
```

Each example lists the rule identifiers it is meant to demonstrate. These
examples are deliberately small and visible. They are not hidden cases and are
not a substitute for the private oracle.
