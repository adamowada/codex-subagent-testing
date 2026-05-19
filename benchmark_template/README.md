# RuleLedger Benchmark Template

RuleLedger is a mixed TypeScript and Python implementation task. Implement the same subscription-ledger behavior in both languages and keep their outputs aligned for shared fixtures.

## Setup

Install the pinned TypeScript dependency before running the Node-based commands:

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

Python exports live in `ruleledger/engine.py`:

- `parse_event_line`
- `normalize_event`
- `reduce_account_state`
- `evaluate_entitlements`
- `summarize_account`
- `export_ledger_report`

## Required Behavior

- Parse newline-delimited JSON subscription events.
- Normalize timestamps to ISO UTC strings.
- Validate malformed records without throwing.
- Trim required strings.
- Convert decimal money strings such as `"12.34"` to cents.
- Reject invalid event types, plans, timestamps, and money fields.
- Deduplicate event IDs after deterministic sorting by timestamp and ID.
- Handle out-of-order events.
- Apply plan prices, feature sets, usage limits, coupons, grace periods, payment failures, and account closure.
- Produce deterministic summaries and CSV exports.
- Preserve cross-language parity for shared fixtures.

The starter implementation is intentionally incomplete. Public tests are visible guidance, not a complete scoring suite.
