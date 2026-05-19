# RuleLedger Shared Task

You are working inside one measured RuleLedger implementation workspace. Implement the visible benchmark contract in both TypeScript and Python, preserve the public APIs, and keep behavior aligned across languages.

## Public TypeScript API

Exports live in `src/index.ts`:

- `parseEventLine`
- `normalizeEvent`
- `reduceAccountState`
- `evaluateEntitlements`
- `summarizeAccount`
- `exportLedgerReport`

Preserve these names and their visible result shapes unless the local source and public tests clearly require a compatible refinement.

## Public Python API

Exports live in `ruleledger/engine.py`:

- `parse_event_line`
- `normalize_event`
- `reduce_account_state`
- `evaluate_entitlements`
- `summarize_account`
- `export_ledger_report`

Keep Python naming idiomatic while matching the TypeScript behavior for the same inputs.

## Required Behavior

RuleLedger models subscription account events from newline-delimited JSON records. Implement deterministic behavior for parsing, normalization, state reduction, entitlement evaluation, account summaries, and CSV reports.

Visible requirements:

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
  "summary": "Implemented RuleLedger behavior in TypeScript and Python.",
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
