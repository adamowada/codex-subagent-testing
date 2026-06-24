# RuleLedger V3 Benchmark Template

RuleLedger v3 is a mixed TypeScript and Python implementation task. It keeps
the v2 subscription-ledger contract while shifting the benchmark toward
realistic software-engineering pressure: repo navigation, cross-module
compatibility, regression preservation, performance, and maintainability.

The starter is intentionally incomplete. Public tests are visible guidance, not
a complete scoring suite.

## Visible Task Documents

- `docs/ruleledger_v2_semantics.md` defines the compatibility baseline.
- `docs/ruleledger_v3_issue_brief.md` describes the v3 issue to solve.
- `docs/ruleledger_v3_architecture.md` describes the intended source shape and
  maintainability expectations.

Measured agents should implement the v3 issue brief without breaking the v2
public APIs or TypeScript/Python parity.

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

TypeScript exports live behind `src/index.ts`:

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

Python exports live behind `ruleledger/engine.py`:

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

V3 work may add internal modules, helpers, or package files. Existing public
imports must remain valid.

## Calibration Intent

V3 is designed to create a reasoning ladder:

- Low reasoning should be able to pass simple compatibility checks.
- Medium reasoning should solve ordinary behavior but may miss deeper
  interactions.
- High reasoning should handle most hidden correctness and parity cases.
- Xhigh reasoning should perform best on cross-module, performance, regression,
  and maintainability pressure.

The benchmark should remain deterministic and fair. Difficulty should come from
interacting requirements and repo-scale implementation work, not from hidden
ambiguity.
