# Stage 18: Upgrade The Hidden Runner

## Purpose

Stage 18 connects the generated RuleLedger v2 hidden suite to actual hidden
test execution. Stage 17 created the private v2 oracle and deterministic hidden
cases, but the current hidden runner still executes only the v1 operation
surface plus basic normalization. Stage 18 should teach the runner how to run
the new v2 operation types while preserving v1 behavior and result privacy.

This stage should answer:

```text
Can the same hidden runner execute v1 and v2 hidden suites, score v2
hard-mode operations and performance failures as case results, and keep hidden
payloads out of run artifacts?
```

## Scope

Stage 18 owns:

- Adding v2 operation support to the temporary TypeScript and Python runner
  harnesses embedded in `harness.hidden_runner`.
- Preserving v1 operation names, v1 behavior, v1 defaults, and the existing
  hidden result schema.
- Supporting separate `business_as_of` and `audit_as_of` inputs for v2 cases.
- Supporting v2 summary, entitlement, report, metamorphic, performance, and
  parity pipelines.
- Adding case-level timeout metadata for v2 performance cases.
- Recording language timeouts and performance failures as scored case failures
  when the language runner launches successfully.
- Keeping all output sanitized to opaque case ids, categories, languages,
  statuses, points, and short reason codes.
- Extending tests so a synthetic v2 worktree can execute every new operation
  type.

Stage 18 does not own:

- Regenerating v2 hidden cases.
- Changing v2 oracle semantics.
- Reweighting scoring components.
- Changing report outputs.
- Calibrating the generated hidden case mix.
- Editing locked source-of-truth documents unless explicitly requested.
- Committing generated run output under `runs/`.

## Inputs

Stage 18 starts from:

```text
harness/hidden_runner.py
hidden_tests/cases/
hidden_tests/cases_v2/
hidden_tests/generators/ruleledger_v2_oracle.py
hidden_tests/generators/generate_v2_cases.py
benchmark_template/
benchmark_template_v2/
tests/test_stage6_codex_execution.py
tests/test_stage11_validation.py
tests/test_stage17_v2_oracle_generator.py
```

The generated v2 hidden cases include these operation names:

```text
parse_line
normalize_event
v2_reduce_and_summarize
v2_calculate_proration
v2_export_report
v2_metamorphic
v2_performance_digest
v2_parity
```

Stage 18 should support those operations without removing support for existing
v1 operations.

## Current Runner Shape

The hidden runner currently:

- Loads case files from a selected `--cases-dir`.
- Verifies manifest file membership and SHA-256 hashes.
- Creates temporary JavaScript and Python runner scripts outside the measured
  worktree.
- Builds TypeScript once with `npm run build`.
- Executes each case in TypeScript, Python, or parity mode.
- Compares actual output to hidden expected output.
- Writes sanitized `hidden-results.json`.

The current temporary runners support v1-style operations:

```text
parse_line
normalize_event
reduce_and_summarize
reduce_and_evaluate
export_report
immutability_repeatability
```

They should continue to support these operations exactly as before.

## V2 Operation Design

### V2 Summary Pipeline

Add `v2_reduce_and_summarize`.

Input shape:

```json
{
  "raw_events": [],
  "as_of": "optional timestamp",
  "business_as_of": "optional timestamp",
  "audit_as_of": "optional timestamp"
}
```

Runner behavior:

- Normalize every raw event through the measured implementation.
- If normalization fails, return a structured `normalization_failed` object.
- Prefer a v2-capable implementation API if present.
- Fall back to existing `reduceAccountState` / `reduce_account_state` and
  `summarizeAccount` / `summarize_account` when only single-`asOf` APIs exist.
- Pass `as_of`, `business_as_of`, and `audit_as_of` consistently according to
  whatever v2 API shape is adopted by the starter.

### V2 Entitlement Pipeline

Add `v2_reduce_and_evaluate` even if Stage 17 has no generated case for it yet.

Input shape:

```json
{
  "raw_events": [],
  "account_id": "acct_id",
  "as_of": "optional timestamp",
  "business_as_of": "optional timestamp",
  "audit_as_of": "optional timestamp"
}
```

Runner behavior:

- Build the same v2 state view as summary cases.
- Find the requested canonical account.
- Evaluate entitlements at the requested cutoff.
- Return `missing_account` as a structured case result if absent.

### V2 Report Export

Add `v2_export_report`.

Input shape:

```json
{
  "summaries": []
}
```

Runner behavior:

- Call the measured implementation's report export function.
- Preserve exact bytes including CSV escaping and trailing newline.
- Compare output exactly against hidden expected CSV.

### V2 Proration

Add `v2_calculate_proration`.

Input shape:

```json
{
  "old_plan": "starter",
  "new_plan": "pro",
  "period_start": "2026-01-01T00:00:00Z",
  "period_end": "2026-02-01T00:00:00Z",
  "change_effective_at": "2026-01-15T00:00:00Z",
  "quantity": 1
}
```

Runner behavior:

- Prefer an explicit measured implementation helper if one exists, such as
  `calculatePlanChangeProration` / `calculate_plan_change_proration`.
- If no helper exists, return `unsupported_operation` as a scored case failure.
- Do not implement the oracle formula inside the hidden runner; the hidden
  runner should execute measured code, not become a second oracle.

### V2 Metamorphic Pipeline

Add `v2_metamorphic`.

Input shape:

```json
{
  "baseline": [],
  "variants": [
    {
      "name": "shuffled",
      "raw_events": []
    }
  ],
  "target_account_id": "optional acct_id",
  "as_of": "optional timestamp",
  "business_as_of": "optional timestamp",
  "audit_as_of": "optional timestamp"
}
```

Runner behavior:

- Execute the baseline through the v2 summary pipeline.
- Execute each variant through the same pipeline.
- If `target_account_id` is present, compare only that account's summary.
- Return the baseline, each variant result, and an `equivalent` boolean.
- Avoid exposing any hidden payload in result artifacts; full actual output
  remains inside the language runner response only for comparison.

### V2 Performance Digest

Add `v2_performance_digest`.

Input shape:

```json
{
  "raw_events": [],
  "as_of": "optional timestamp",
  "business_as_of": "optional timestamp",
  "audit_as_of": "optional timestamp"
}
```

Runner behavior:

- Execute the v2 summary pipeline.
- Export a report from the summaries.
- Return a compact digest:
  - `eventCount`
  - `summaryCount`
  - `firstAccountId`
  - `lastAccountId`
  - `totalUsage`
  - `totalPaidCents`
  - `summarySha256`
  - `reportSha256`
- Do not write full performance summaries into `hidden-results.json`.

### V2 Parity Pipeline

Add `v2_parity`.

Input shape:

```json
{
  "raw_events": [],
  "as_of": "optional timestamp",
  "business_as_of": "optional timestamp",
  "audit_as_of": "optional timestamp"
}
```

Runner behavior:

- Run TypeScript and Python on the same v2 pipeline.
- Produce summaries and CSV report from each language.
- Require JSON-compatible summaries and byte-identical CSV.
- Compare against hidden expected output where the case includes one.

## API Compatibility Strategy

Measured implementations may expose either existing v1 functions or newer v2
helpers. The runner should probe for functions in a predictable order.

Recommended TypeScript names:

```text
normalizeEvent
reduceAccountState
summarizeAccount
evaluateEntitlements
exportLedgerReport
calculatePlanChangeProration
```

Potential v2-specific names if added later:

```text
reduceAccountStateV2
summarizeAccountV2
evaluateEntitlementsV2
exportLedgerReportV2
calculatePlanChangeProrationV2
```

Recommended Python names:

```text
normalize_event
reduce_account_state
summarize_account
evaluate_entitlements
export_ledger_report
calculate_plan_change_proration
```

Potential v2-specific names:

```text
reduce_account_state_v2
summarize_account_v2
evaluate_entitlements_v2
export_ledger_report_v2
calculate_plan_change_proration_v2
```

If a required operation is unavailable, the runner should produce a scored
`unsupported_operation` failure for that case rather than crashing the hidden
runner.

## Timeout Design

Keep existing v1 defaults:

```text
TS_TIMEOUT_SECONDS = 20
PY_TIMEOUT_SECONDS = 20
NPM_TIMEOUT_SECONDS = 120
```

Add case-level timeout support:

```json
{
  "timeout_seconds": {
    "typescript": 45,
    "python": 45
  }
}
```

or a simpler numeric form:

```json
{
  "timeout_seconds": 45
}
```

Recommended behavior:

- Use existing language defaults when no case timeout is present.
- Use longer timeouts for performance category cases when the case requests
  them.
- Treat subprocess timeout as a case result with reason `timeout`.
- Keep setup/build failures as setup errors.
- Keep case-load failures and runner infrastructure exceptions as
  infrastructure failures.

## Result Schema

Do not change the top-level hidden result schema unless absolutely necessary.
The existing schema is:

```json
{
  "schema_version": 1,
  "seed": 20260520,
  "started_at": "...",
  "finished_at": "...",
  "summary": {},
  "categories": {},
  "languages": {},
  "typescript_setup": {},
  "cases": []
}
```

Case results should stay sanitized:

```json
{
  "id": "case-opaquehash",
  "category": "bitemporal_replay",
  "language": "typescript",
  "status": "passed",
  "points_earned": 2.0,
  "points_possible": 2.0,
  "reason": "ok"
}
```

Allowed reasons should stay short and non-revealing:

```text
ok
output_mismatch
parity_mismatch
timeout
unsupported_operation
normalization_failed
missing_account
typescript_execution_failed
python_execution_failed
```

Do not include raw hidden inputs, expected outputs, actual outputs, stack
traces, full stderr, or rule metadata in case results.

## Privacy Rules

Stage 18 must preserve hidden-test privacy:

- Keep temporary runner scripts outside measured worktrees.
- Do not write hidden input payloads into implementation worktrees.
- Continue stripping `id`, `expected`, `source_file`, `category`, `languages`,
  `points`, and `rule_ids` before passing case payloads into measured code.
- If timeout metadata is added, ensure it is runner metadata and not passed to
  measured code unless needed by the runner.
- Keep `hidden-results.json` sanitized.
- Keep validation pointed at the selected hidden case directory.

## Implementation Steps

1. Add small helper functions in `harness.hidden_runner` for case timeout
   resolution.
2. Extend `strip_runner_metadata` to strip timeout metadata if needed.
3. Update `execute_case` to use case-level timeout overrides.
4. Refactor embedded JavaScript runner helpers so v1 and v2 pipelines can share
   normalization and summary logic.
5. Add TypeScript support for `v2_reduce_and_summarize`.
6. Add TypeScript support for `v2_reduce_and_evaluate`.
7. Add TypeScript support for `v2_export_report`.
8. Add TypeScript support for `v2_calculate_proration`.
9. Add TypeScript support for `v2_metamorphic`.
10. Add TypeScript support for `v2_performance_digest`.
11. Add TypeScript support for `v2_parity`.
12. Mirror the same operation support in the Python runner.
13. Update parity execution so v2 parity compares summaries and CSV report.
14. Add synthetic v2 worktree fixtures or temporary test worktrees that expose
    every required v2 operation.
15. Add tests for unsupported v2 operations becoming scored failures.
16. Add tests for per-case timeout behavior.
17. Add tests proving v1 hidden cases still produce the current schema.
18. Run focused hidden-runner tests, validation checks, and the full suite.

## Testing Strategy

Recommended tests:

- Unit test `strip_runner_metadata` for v2-only metadata.
- Unit test timeout resolution:
  - no metadata uses v1 default
  - numeric timeout applies to both languages
  - per-language timeout applies correctly
- Synthetic case test for each v2 operation.
- Synthetic timeout case where the language subprocess launches but exceeds the
  case timeout, yielding a scored `timeout` result.
- V1 regression test using existing v1 fixture cases.
- V2 loader/regression test using `hidden_tests/cases_v2`.
- Privacy test confirming hidden outputs still exclude raw inputs and expected
  outputs.

## Verification

Recommended commands:

```powershell
python -m pytest tests/test_stage6_codex_execution.py
python -m pytest tests/test_stage11_validation.py tests/test_stage17_v2_oracle_generator.py
python -m harness.hidden_runner --worktree benchmark_template_v2 --cases-dir hidden_tests/cases_v2 --out <temp>\hidden-results.json
python -m harness.validation --config configs/initial_experiment.yaml --skip-preflight --allow-missing-report
python -m harness.validation --config configs/ruleledger_v2.yaml --skip-preflight --allow-missing-report
python -m pytest
git diff --check
```

If running the full v2 hidden suite against the intentionally incomplete v2
starter produces failures, that is acceptable. The runner should still exit
successfully and write scored case results unless setup fails.

## Done Criteria

Stage 18 is complete when:

- Existing v1 hidden cases still run and preserve the current result schema.
- The runner recognizes every generated v2 operation type.
- A synthetic v2 worktree can execute every new operation type.
- V2 performance timeouts appear as scored case failures.
- Unsupported v2 implementation APIs become scored case failures, not
  infrastructure crashes.
- `hidden-results.json` remains sanitized.
- Hidden-test privacy validation still scans the selected hidden case directory
  and catches copied hidden files or matching contents.
- Full repo tests pass.

## Risks

Risk: V2 support accidentally changes v1 scoring behavior.

Mitigation: Keep v1 operation branches intact and add explicit v1 regression
tests around the existing schema.

Risk: The hidden runner accidentally becomes a second oracle.

Mitigation: The runner should orchestrate measured code and compare outputs. It
may compute digests from measured outputs, but it should not reimplement private
business semantics.

Risk: Performance cases become infrastructure failures.

Mitigation: Treat case subprocess timeouts as scored case failures once setup
has succeeded.

Risk: Hidden payloads leak through diagnostics.

Mitigation: Keep case results terse, strip metadata before language execution,
and rely on artifact privacy validation.

Risk: V2 APIs are not stable yet.

Mitigation: Probe a small set of documented function names and return scored
`unsupported_operation` failures when unavailable.

## Open Questions

- Should Stage 18 add v2-specific function names to the starter public API, or
  only probe for them if measured agents choose to add them?
- Should v2 parity cases compare against hidden expected output in addition to
  TypeScript/Python agreement, or should parity be purely cross-language?
- Should performance case timeout metadata be added by regenerating Stage 17
  cases, or should Stage 18 infer defaults by category?
- Should `hidden-results.json` include a benchmark version field now, or wait
  for Stage 19 scoring/reporting changes?
