# Stage 1 Plan: Benchmark Template

## Goal

Create `benchmark_template/`, the frozen visible starter project used by every measured implementation run. The project should be a mixed TypeScript and Python benchmark task called RuleLedger. It must expose the same ledger behavior in both languages, include public tests that guide implementation without being exhaustive, and remain free of hidden test data.

Stage 1 is complete when an implementation run can copy `benchmark_template/`, run the visible commands, and receive deterministic public feedback.

## Non-Goals

- Do not create hidden tests in this stage.
- Do not add generated run output under `runs/`.
- Do not implement the experiment orchestrator, scoring pipeline, judge, or report generator.
- Do not place hidden edge cases, hidden fixtures, or private scoring rules in prompts or the starter project.

## Target Directory Layout

```text
benchmark_template/
  package.json
  tsconfig.json
  src/
    index.ts
  tests_public_ts/
    ruleledger.test.ts
  ruleledger/
    __init__.py
    engine.py
  tests_public_py/
    test_ruleledger.py
  fixtures/
    public_events.jsonl
    public_expected_summary.json
```

The exact test runner can change if there is a good reason, but the visible commands must remain:

```powershell
npm run typecheck
npm run test:public
python -m unittest discover -s tests_public_py
```

## Public API Contract

### TypeScript

`src/index.ts` must export:

- `parseEventLine`
- `normalizeEvent`
- `reduceAccountState`
- `evaluateEntitlements`
- `summarizeAccount`
- `exportLedgerReport`

### Python

`ruleledger/engine.py` must export:

- `parse_event_line`
- `normalize_event`
- `reduce_account_state`
- `evaluate_entitlements`
- `summarize_account`
- `export_ledger_report`

The starter implementation can be incomplete, but every function must exist and be importable. Public tests should fail in a useful way against the initial starter if the target behavior is not yet implemented.

## Domain Model

RuleLedger models subscription account events. A run receives newline-delimited JSON events and must derive current account state, entitlements, summaries, and CSV reports.

Recommended visible event fields:

- `id`: unique event ID after trimming.
- `account_id`: account identifier after trimming.
- `type`: event type.
- `timestamp`: parseable timestamp normalized to ISO UTC.
- `plan`: subscription plan where relevant.
- `amount`: decimal money string where relevant.
- `coupon`: coupon code or coupon metadata where relevant.
- `usage`: numeric usage value where relevant.

Recommended event types:

- `account_opened`
- `plan_changed`
- `payment_succeeded`
- `payment_failed`
- `coupon_applied`
- `usage_recorded`
- `account_closed`

Recommended plans:

- `free`
- `starter`
- `pro`
- `enterprise`

Plan prices, feature sets, and usage limits should be defined as explicit constants in both implementations so agents can discover the intended business rules from the visible source.

## Required Behavior

The template should make these requirements visible through comments, test names, fixtures, or starter code structure:

- Parse newline-delimited JSON subscription events.
- Reject malformed JSON, empty lines, and non-object JSON without throwing.
- Trim required string fields.
- Reject missing or whitespace-only IDs.
- Reject invalid event types and plans.
- Normalize timestamps to deterministic ISO UTC strings.
- Reject invalid timestamps.
- Convert decimal money strings such as `"12.34"` to integer cents.
- Reject invalid money fields, including ambiguous precision.
- Sort events deterministically by timestamp and then event ID.
- Deduplicate event IDs after sorting.
- Handle out-of-order input.
- Apply plan prices, feature sets, and usage limits.
- Apply coupons and coupon expiration behavior.
- Apply failed-payment grace periods.
- Ensure closed accounts override otherwise-active entitlements.
- Produce deterministic account summaries.
- Export deterministic CSV with stable headers, stable row ordering, stable booleans, explicit missing-date behavior, and a trailing newline.
- Preserve parity between TypeScript and Python for shared public fixtures.

## Starter Implementation Strategy

Use intentionally incomplete but well-shaped implementations rather than empty files. The starter should help measured agents understand the architecture while still requiring real work.

Recommended approach:

- Define exported types or docstrings for event, normalized event, account state, entitlement state, and summary output.
- Include plan and feature constants.
- Implement simple parsing stubs.
- Leave validation, reduction, entitlement calculation, and export behavior incomplete enough for public tests to reveal gaps.
- Keep TypeScript and Python naming idiomatic while preserving equivalent semantics.

Avoid making the starter so complete that public tests mostly pass before agents do meaningful work.

## Public Test Plan

Public tests should cover normal behavior and obvious edge cases. They should be strong enough to verify command wiring and basic correctness, but not exhaustive enough to replace hidden scoring.

Suggested TypeScript tests:

- Imports expose all public functions.
- `parseEventLine` handles valid JSON and invalid JSON without throwing.
- `normalizeEvent` trims IDs and normalizes a simple UTC timestamp.
- Decimal money conversion works for a normal payment amount.
- Out-of-order events produce a deterministic summary.
- CSV export includes the expected header and trailing newline.

Suggested Python tests:

- Imports expose all public functions.
- `parse_event_line` handles valid JSON and invalid JSON without throwing.
- `normalize_event` trims IDs and normalizes a simple UTC timestamp.
- Decimal money conversion works for a normal payment amount.
- Shared public fixture produces the expected summary.
- CSV export is deterministic.

Suggested parity test:

- Store one shared public JSONL fixture and one expected summary fixture.
- Both TypeScript and Python public tests should use the same fixture.
- The fixture should cover a normal account lifecycle without including hidden adversarial cases.

## Determinism Requirements

- Do not use current time in benchmark behavior.
- Do not use random values in starter code or public tests.
- If a fixture needs a reference date, encode it explicitly.
- Sort all output rows and object-derived collections before exporting.
- Keep public fixture files stable and small.

## Hidden-Test Hygiene

Stage 1 must be safe for measured agents to inspect completely. Therefore:

- No hidden test files belong under `benchmark_template/`.
- No hidden case descriptions should appear in public fixtures.
- No private scoring weights should appear in the starter project.
- Public tests may signal categories of behavior, but should not enumerate all adversarial cases.

## Implementation Steps

1. Create `benchmark_template/` with TypeScript and Python package structure.
2. Add `package.json`, `tsconfig.json`, and a minimal public TypeScript test setup.
3. Add `src/index.ts` with exported functions, types, constants, and incomplete starter behavior.
4. Add `ruleledger/__init__.py` and `ruleledger/engine.py` with matching Python public functions.
5. Add small shared public fixtures under `benchmark_template/fixtures/`.
6. Add public TypeScript tests under `tests_public_ts/`.
7. Add public Python unittest tests under `tests_public_py/`.
8. Run the three visible commands from inside `benchmark_template/`.
9. Confirm the project is deterministic and contains no hidden tests.

## Acceptance Checklist

- `benchmark_template/` exists and can be copied into a run workspace.
- `npm run typecheck` is defined.
- `npm run test:public` is defined.
- `python -m unittest discover -s tests_public_py` runs.
- All required TypeScript exports exist.
- All required Python exports exist.
- Public tests exercise both language surfaces.
- Shared fixtures are visible, deterministic, and non-hidden.
- No files under `hidden_tests/` are required for public tests.
- No run artifacts are committed.

## Risks And Mitigations

- Risk: Public tests become too exhaustive.
  Mitigation: Keep public tests focused on ordinary behavior and basic edge cases. Reserve adversarial combinations for Stage 2.

- Risk: TypeScript and Python drift in behavior.
  Mitigation: Use shared public fixtures and mirror constants in both implementations.

- Risk: The starter implementation accidentally solves too much.
  Mitigation: Include structure, names, and constants, but leave enough missing behavior for agents to implement.

- Risk: Hidden-test logic leaks into the visible template.
  Mitigation: Keep hidden cases outside `benchmark_template/` and review the tree before Stage 1 is marked done.

## Open Decisions

- Choose the TypeScript public test runner. A minimal Node test runner keeps dependencies small; Jest or Vitest may improve ergonomics but adds dependency weight.
- Decide the exact normalized result shape for validation failures.
- Decide whether money conversion should accept only string inputs or also numeric JSON values.
- Decide the exact coupon schema and expiration boundary semantics.
- Decide whether CSV export accepts summaries, account states, or raw events.
