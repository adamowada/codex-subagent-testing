# RuleLedger V2 Shared Task

You are working inside one measured RuleLedger v2 implementation workspace. Implement the visible hard-mode benchmark contract in both TypeScript and Python, preserve the public APIs, and keep behavior aligned across languages.

The public semantic contract is in `docs/ruleledger_v2_semantics.md` inside the starter workspace. Treat that document as the implementation target, not just as background reading.

## Public TypeScript API

Exports live in `src/index.ts`.

V1-compatible exports must remain available:

- `parseEventLine`
- `normalizeEvent`
- `reduceAccountState`
- `evaluateEntitlements`
- `summarizeAccount`
- `exportLedgerReport`

V2-compatible exports are also part of the visible contract:

- `normalizeEventV2`
- `reduceAccountStateV2`
- `evaluateEntitlementsV2`
- `summarizeAccountV2`
- `exportLedgerReportV2`
- `calculatePlanChangeProrationV2`

The V2 state, entitlement, and summary functions may receive a view object with `asOf`, `businessAsOf`, and `auditAsOf` plus snake_case aliases. A single `asOf` value means both business and audit cutoffs.

## Public Python API

Exports live in `ruleledger/engine.py`.

V1-compatible exports must remain available:

- `parse_event_line`
- `normalize_event`
- `reduce_account_state`
- `evaluate_entitlements`
- `summarize_account`
- `export_ledger_report`

V2-compatible exports are also part of the visible contract:

- `normalize_event_v2`
- `reduce_account_state_v2`
- `evaluate_entitlements_v2`
- `summarize_account_v2`
- `export_ledger_report_v2`
- `calculate_plan_change_proration_v2`

Keep Python naming idiomatic while matching TypeScript behavior for the same inputs.

## Required Behavior

RuleLedger v2 models subscription account events from newline-delimited JSON records. Implement deterministic behavior for parsing, normalization, bitemporal state reduction, entitlement evaluation, account summaries, billing proration, and CSV reports.

Visible requirements:

- Parse newline-delimited JSON subscription events.
- Reject malformed JSON, empty lines, and non-object JSON without throwing.
- Trim required string fields.
- Reject missing or whitespace-only IDs.
- Reject invalid event types and plans.
- Normalize timestamps to deterministic ISO UTC strings.
- Default missing `effective_at` and `recorded_at` to the normalized `timestamp`.
- Sort events deterministically by `(effectiveAt, recordedAt, sequence, id)`.
- Deduplicate event IDs after sorting.
- Support separate business and audit cutoffs for V2 views.
- Apply lifecycle events including trial, pause, resume, cancel, reactivate, close, payment failure, and payment recovery.
- Apply plan prices, feature sets, usage limits, seats, quantities, coupons, invoices, and billing periods.
- Normalize money to integer minor units, including negative credit values where the public semantics permit them.
- Implement deterministic correction, void, and account-merge behavior.
- Calculate plan-change proration with the documented half-away-from-zero rounding.
- Produce deterministic account summaries.
- Export deterministic CSV with stable headers, RFC-style escaping, stable row ordering, stable booleans, explicit missing-date behavior, and a trailing newline.
- Preserve cross-language parity for shared fixtures.

Use constants and visible source structure where possible. Public tests are guidance, not the complete scoring suite, so implement the contract rather than only the examples.

## Public Commands

Run the visible checks when practical:

```powershell
npm run typecheck
npm run test:public
python -m pytest -q tests_public_py
```

Record commands you actually ran in the final response.

## Constraints

- Keep hidden tests hidden. Do not inspect, copy, request, or reconstruct private case files.
- Do not add private fixture data to prompts, tests, source, or generated files.
- Do not modify repository-level harness files from inside the measured implementation workspace.
- Avoid large new dependencies unless they are already present or plainly necessary for deterministic behavior.
- Keep outputs deterministic across repeated runs.
- Prefer straightforward code that future scoring and review can audit.

## Nested Codex And External AI Prohibition

Do not invoke `codex`, `codex exec`, any nested Codex process, any external AI service, or any other AI agent process from inside this measured run. Use only the configured topology described in this prompt. Spark leaves, subleads, and the root must not create deeper agent processes than the configured topology permits.

## Final Response

Finish with strict JSON only, with no prose before or after it. Use this schema:

```json
{
  "status": "success",
  "summary": "Implemented RuleLedger v2 behavior in TypeScript and Python.",
  "changed_files": [
    "src/index.ts",
    "ruleledger/engine.py"
  ],
  "tests_run": [
    {
      "command": "npm run typecheck",
      "status": "passed",
      "notes": ""
    },
    {
      "command": "npm run test:public",
      "status": "passed",
      "notes": ""
    },
    {
      "command": "python -m pytest -q tests_public_py",
      "status": "passed",
      "notes": ""
    }
  ],
  "known_issues": [],
  "nested_codex_invoked": false
}
```

Allowed `status` values are `success`, `partial`, and `failed`. Allowed test statuses are `passed`, `failed`, and `not_run`. Set `nested_codex_invoked` to `false`; invoking nested Codex or external AI is prohibited.
