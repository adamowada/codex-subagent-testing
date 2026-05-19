# Stage 2 Plan: Hidden Tests

## Goal

Create the private RuleLedger hidden-test suite and scoring entrypoint used to judge every measured implementation run. The hidden suite should validate the full benchmark contract across TypeScript and Python, including cross-language parity, while remaining unavailable to implementation agents.

Stage 2 is complete when the harness can run one command against a copied implementation worktree and produce deterministic, machine-readable hidden-test results without copying hidden cases into that worktree.

## Non-Goals

- Do not change the visible `benchmark_template/` API unless Stage 1 is explicitly reopened.
- Do not add hidden cases, hidden fixtures, private expected outputs, or private scoring details to prompts or starter files.
- Do not implement the full experiment orchestrator, report generator, or judge in this stage.
- Do not run measured Codex experiments from the hidden runner.
- Do not commit generated run outputs under `runs/`.

## Target Directory Layout

```text
hidden_tests/
  README.md
  cases/
    manifest.json
    parse_validation.json
    normalization.json
    state_reduction.json
    reporting.json
    immutability.json
    parity.json
  generators/
    generate_cases.py
    ruleledger_oracle.py
harness/
  hidden_runner.py
```

The exact case file names can change, but hidden case data must stay under `hidden_tests/` and must not be copied into `benchmark_template/`, prompts, or run worktrees.

## Hidden Runner Contract

Expose one command:

```powershell
python -m harness.hidden_runner --worktree <run_worktree> --out <hidden-results.json>
```

The runner should:

- Load hidden cases from `hidden_tests/`.
- Import or invoke TypeScript code from `<run_worktree>/src/index.ts`.
- Import Python code from `<run_worktree>/ruleledger/engine.py`.
- Execute hidden cases outside the implementation workspace.
- Record pass/fail/error results per language and category.
- Write a deterministic JSON result file to `--out`.
- Exit non-zero only for runner infrastructure failures, not for ordinary test failures.

Ordinary implementation failures should be represented in `hidden-results.json` so partial runs can receive partial credit.

## Result Schema

Use a stable JSON shape that scoring code can consume directly:

```json
{
  "schema_version": 1,
  "seed": 20260519,
  "worktree": "<absolute path>",
  "started_at": "<iso timestamp>",
  "finished_at": "<iso timestamp>",
  "summary": {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "errors": 0,
    "score": 0.0
  },
  "categories": {},
  "languages": {
    "typescript": {},
    "python": {},
    "parity": {}
  },
  "cases": []
}
```

Each case result should include an opaque case ID, category, language, status, points earned, points possible, and a short failure reason. Do not embed private input payloads or full expected outputs in result artifacts.

## Hidden Test Categories

### Parsing And Validation

Cover malformed and boundary input handling:

- Empty lines.
- Invalid JSON.
- Valid JSON that is not an object.
- Missing required fields.
- Whitespace-only `id` or `account_id` after trimming.
- Invalid event types.
- Invalid plan names.

These tests should confirm that implementations return structured failures without throwing uncaught exceptions.

### Timestamp Normalization

Cover deterministic timestamp handling:

- Equivalent instants with different timezone offsets.
- Inputs requiring UTC normalization.
- Invalid date strings.
- Missing or non-string timestamps.
- Boundary dates relevant to coupon and grace-period behavior.

Expected normalized values should be produced by the oracle, not duplicated manually in multiple places.

### Money And Usage Fields

Cover numeric correctness and rejection behavior:

- Valid decimal money strings converted to integer cents.
- Zero-value payments.
- Invalid precision or ambiguous amount strings.
- Non-string or malformed money values.
- Valid integer usage values.
- Negative, fractional, non-numeric, or missing usage values where usage is required.

The suite should distinguish parsing failures from state-reduction behavior so errors are easier to interpret.

### State Reduction

Cover account lifecycle behavior:

- Duplicate event IDs after deterministic sorting.
- Out-of-order input.
- Plan changes.
- Payment success and failure.
- Failed-payment grace-period dates.
- Coupon application and expiration boundaries.
- Usage-limit overage.
- Closed-account precedence over later plan, payment, coupon, or usage events.

These cases should validate final account state and summarized account output.

### CSV Reporting

Cover deterministic report output:

- Exact header.
- Stable row sorting by account ID.
- Stable boolean formatting.
- Empty strings for missing nullable fields.
- Correct `closed_at` and `last_event_at` values.
- Trailing newline.

CSV cases should compare complete output strings, because report formatting is part of the benchmark contract.

### Immutability And Repeatability

Cover robustness properties:

- Re-running the same function with the same inputs produces the same result.
- Input event objects are not mutated unexpectedly.
- No module-level state leaks between cases.
- Multiple accounts remain isolated from each other.

These tests help catch solutions that accidentally depend on execution order.

### Cross-Language Parity

Run shared hidden fixtures through both TypeScript and Python and compare normalized summaries and CSV output. Parity checks should count separately from per-language correctness so the report can show whether one language is correct and the other drifted.

## Oracle Strategy

Use a small Python oracle under `hidden_tests/generators/ruleledger_oracle.py` to define expected behavior once. The oracle should be independent from `benchmark_template/` implementation code.

Recommended approach:

- Keep hand-authored fixtures small and readable.
- Use deterministic generators for combinatorial edge cases.
- Store the generation seed in `manifest.json`.
- Commit generated hidden cases only after review.
- Regenerate cases only when intentionally revising the benchmark, never during measured runs.

The generator may write frozen case files, but the hidden runner should read frozen cases rather than generating new random cases at scoring time.

## TypeScript Invocation

The hidden runner needs a reliable way to execute TypeScript exports from a copied worktree.

Recommended path:

- Run `npm ci` during run setup, not inside every hidden test case.
- Use the worktree's existing TypeScript toolchain and `npm run typecheck` as a separate public/typecheck component.
- For hidden tests, execute a small temporary Node harness outside the worktree that imports compiled or loader-backed TypeScript exports from the worktree.
- Capture stdout, stderr, exit code, and timeout per case group.

The temporary harness must not write hidden inputs into the worktree. If temporary files are needed, place them under a harness-owned temp directory.

## Python Invocation

The runner should import Python implementation modules by temporarily prepending `<run_worktree>` to `sys.path`, then removing it after each isolated group.

Recommended safeguards:

- Clear relevant `ruleledger` modules from `sys.modules` between case groups.
- Use subprocess isolation for groups that could leave global state behind.
- Capture exceptions as case errors rather than crashing the whole runner.
- Use explicit timeouts for long-running or hanging implementations.

## Scoring Approach

Hidden-test score should be a normalized value from `0.0` to `1.0`.

Recommended weighting:

- Parsing and validation: 15 percent.
- Timestamp, money, and usage normalization: 20 percent.
- State reduction and entitlement rules: 35 percent.
- CSV reporting: 15 percent.
- Immutability and repeatability: 5 percent.
- Cross-language parity: 10 percent.

These hidden-test weights are internal to Stage 2. The later overall scoring stage should treat the final hidden-test score as the `hidden_test_score` component.

## Isolation Requirements

- Hidden cases live outside implementation workspaces.
- Hidden expected outputs are never included in implementation prompts.
- Hidden case files are never copied into run worktrees.
- Runner logs and result files use opaque case IDs and short diagnostic categories.
- Temporary execution files are created outside the worktree.
- Any cache or build output created inside a worktree must be ordinary language tooling output, not hidden data.

Before Stage 2 is marked complete, run a tree inspection that confirms no hidden case files are present under `benchmark_template/`.

## Implementation Steps

1. Create `hidden_tests/` and `harness/` directories.
2. Add `hidden_tests/README.md` documenting privacy and regeneration rules without listing private case values.
3. Add the oracle module for expected RuleLedger behavior.
4. Add deterministic case-generation script and seed handling.
5. Generate frozen hidden case files and manifest.
6. Implement `harness.hidden_runner` CLI argument parsing.
7. Implement Python execution and result capture.
8. Implement TypeScript execution and result capture.
9. Implement parity comparison on shared hidden fixtures.
10. Write `hidden-results.json` with stable schema and opaque diagnostics.
11. Add runner self-tests that use small synthetic throwaway worktrees, not measured outputs.
12. Verify hidden cases are absent from `benchmark_template/`, prompts, and run worktrees.

## Acceptance Checklist

- `hidden_tests/` exists outside `benchmark_template/`.
- Hidden cases are deterministic, frozen, and seed-recorded.
- `python -m harness.hidden_runner --worktree <run_worktree> --out <hidden-results.json>` works.
- TypeScript and Python implementations are both scored.
- Cross-language parity is scored separately.
- Ordinary case failures do not crash the runner.
- Infrastructure failures are distinguishable from implementation failures.
- Result JSON is deterministic apart from documented timestamps and paths.
- Result artifacts do not expose full hidden inputs or expected outputs.
- Hidden cases are not present in `benchmark_template/`, prompts, or run worktrees.

## Risks And Mitigations

- Risk: Hidden tests leak through generated artifacts.
  Mitigation: Store only opaque case IDs, categories, points, and short reason codes in run artifacts.

- Risk: The hidden suite becomes too brittle or overfits one implementation style.
  Mitigation: Assert public API behavior and externally visible outputs, not internal implementation details.

- Risk: TypeScript invocation requires dependencies that are not installed.
  Mitigation: Keep dependency installation in setup/preflight and report missing dependencies as infrastructure errors.

- Risk: Cross-language parity masks both languages being wrong in the same way.
  Mitigation: Score parity separately from oracle-based per-language correctness.

- Risk: Generated cases accidentally change between runs.
  Mitigation: Commit frozen case files, record the seed, and fail preflight if the generated output differs from committed cases.

## Resolved Implementation Decisions

- Coupon expiration is inclusive at the exact `as_of` instant.
- Failed-payment grace lasts seven days from the failed payment timestamp; the boundary instant is inclusive, and a successful payment restores active status.
- Hidden TypeScript tests run against compiled `dist/index.js`; the runner performs `npm ci` when dependencies are missing unless `--no-install` is supplied.
- Hidden results include summary, category, language, TypeScript setup, and opaque per-case result records.
- Diagnostics preserve case IDs, categories, operations, points, statuses, and short reason codes, but not hidden inputs or expected outputs.
