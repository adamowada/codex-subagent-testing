# RuleLedger V3 Shared Task

You are working inside one measured RuleLedger v3 implementation workspace. Implement the visible issue brief in both TypeScript and Python, preserve the public APIs, and keep behavior aligned across languages.

RuleLedger v3 keeps the v2 subscription-ledger semantics and adds software-engineering pressure through a larger starter surface, compatibility requirements, migration behavior, performance constraints, and maintainability expectations.

Read these visible files before editing:

- `README.md`
- `docs/ruleledger_v2_semantics.md`
- `docs/ruleledger_v3_issue_brief.md`
- `docs/ruleledger_v3_architecture.md`
- public TypeScript and Python tests

Treat the v3 issue brief as the immediate implementation target and the v2 semantic contract as the compatibility baseline.

## Public TypeScript API

Exports live behind `src/index.ts`. Preserve every existing v1/v2 export:

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

V3 work may add internal modules, helper types, or implementation files, but existing callers must not need new import paths.

## Public Python API

Exports live behind `ruleledger/engine.py`. Preserve every existing v1/v2 export:

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

Python behavior must remain JSON-compatible with TypeScript for the same inputs.

## V3 Priorities

- Preserve v2 behavior while implementing the v3 issue brief.
- Localize changes across the relevant modules instead of replacing the starter with one giant bypass file.
- Keep public APIs stable and deterministic.
- Maintain cross-language parity for summaries and CSV output.
- Preserve existing behavior while adding new behavior.
- Prefer algorithms that scale to large ledgers.
- Add or update public tests only for visible behavior and regressions. Never add private or reconstructed hidden cases.

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
- Favor readable, auditable code over fragile case-specific patches.

## Nested Codex And External AI Prohibition

Do not invoke `codex`, `codex exec`, any nested Codex process, any external AI service, or any other AI agent process from inside this measured run. Use only the configured topology described in this prompt. Spark leaves, subleads, and the root must not create deeper agent processes than the configured topology permits.

## Final Response

Finish with strict JSON only, with no prose before or after it. Use this schema:

```json
{
  "status": "success",
  "summary": "Implemented RuleLedger v3 behavior in TypeScript and Python.",
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
