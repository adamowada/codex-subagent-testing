# Implementation Plan

## Summary

Build a benchmark harness that can run the full initial Codex subagent experiment with one command, score every run, and generate a detailed PDF report.

Initial experiment size:

| Cell | Topology | Spark Mode Toggle | Repeats |
|---|---|---:|---:|
| C0 | GPT-5.5 xhigh solo baseline | none | 5 |
| C1 | GPT-5.5 medium lead -> 6 Spark xhigh leaves | direct + proposal | 10 |
| C2 | GPT-5.5 high lead -> 6 Spark xhigh leaves | direct + proposal | 10 |
| C3 | GPT-5.5 xhigh lead -> 6 Spark xhigh leaves | direct + proposal | 10 |
| C4 | GPT-5.5 xhigh root -> 3 GPT-5.5 medium subleads -> 18 Spark xhigh leaves | direct + proposal | 10 |

Total: 45 implementation runs.

Primary metric:

```text
quality_per_gpt55_impl_token = quality_score / max(gpt55_implementation_tokens, 1)
```

The harness must also track judge-inclusive GPT-5.5 cost, total token usage, best-effort Spark usage, wall-clock time, code quantity, failure rate, and direct-edit versus proposal-only differences.

## Repository Structure

Create these top-level areas:

```text
benchmark_template/
  package.json
  tsconfig.json
  src/
  tests_public_ts/
  ruleledger/
  tests_public_py/

hidden_tests/
  cases/
  generators/
  README.md

configs/
  initial_experiment.yaml
  scoring.yaml

prompts/
  task_common.md
  task_solo.md
  task_flat_spark.md
  task_depth2_subleads.md
  judge.md

codex_templates/
  config.toml.j2
  agents/

harness/
  orchestrator.py
  preflight.py
  matrix.py
  prompt_rendering.py
  codex_runner.py
  scoring.py
  hidden_runner.py
  jsonl_usage.py
  report_data.py

report/
  template.html
  styles.css
  render_pdf.js

scripts/
  run_experiment.ps1
  run_pilot.ps1

runs/
```

`runs/` is generated output and should not be committed by default.

## Planning Documents

Incremental planning documents belong in `plans/`. Use that directory for follow-up implementation notes, revised stage plans, experiment design notes, and planning artifacts that are not meant to replace this top-level source-of-truth plan.

## Stage 1: Benchmark Template

Create the visible starter project under `benchmark_template/`.

The implementation target is a mixed TypeScript and Python project called RuleLedger. Agents must implement equivalent behavior in both languages.

TypeScript public API in `src/index.ts`:

- `parseEventLine`
- `normalizeEvent`
- `reduceAccountState`
- `evaluateEntitlements`
- `summarizeAccount`
- `exportLedgerReport`

Python public API in `ruleledger/engine.py`:

- `parse_event_line`
- `normalize_event`
- `reduce_account_state`
- `evaluate_entitlements`
- `summarize_account`
- `export_ledger_report`

Required behavior:

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

Visible commands inside each copied run workspace:

```text
npm run typecheck
npm run test:public
python -m unittest discover -s tests_public_py
```

Public tests should cover normal behavior and obvious edge cases but intentionally leave room for hidden tests to differentiate quality.

Done when:

- `benchmark_template/` contains a runnable mixed TypeScript and Python starter project.
- The required public APIs exist as stubs or incomplete implementations for agents to fill in.
- Public test commands exist and run against the starter project.
- The visible project is deterministic and contains no hidden test cases.

## Stage 2: Hidden Tests

Create hidden tests outside the implementation workspaces.

Hidden test requirements:

- Created once before measured runs.
- Frozen for the entire initial experiment.
- Unavailable in implementation source and prompts.
- Exhaustive enough to resemble LeetCode-style judging.
- Deterministic and seed-recorded.
- Cover both TypeScript and Python.
- Include cross-language parity checks.

Hidden test categories:

- Empty lines, invalid JSON, non-object JSON.
- Missing required fields and whitespace-only IDs.
- Invalid event types and plans.
- Timestamp normalization and invalid dates.
- Coupon expiration boundary behavior.
- Decimal amount conversion and invalid amount values.
- Duplicate IDs and out-of-order events.
- Failed-payment grace-period dates.
- Closed account precedence.
- Usage-limit overage.
- CSV header, row sorting, booleans, missing dates, trailing newline.
- Immutability and deterministic repeatability.
- TypeScript/Python parity on shared fixture sets.

Expose one hidden scoring entrypoint:

```text
python -m harness.hidden_runner --worktree <run_worktree> --out <hidden-results.json>
```

The hidden runner imports or invokes code from the run workspace but never copies hidden cases into that workspace.

Done when:

- Hidden test cases are generated or authored outside implementation workspaces.
- The hidden test set is deterministic, frozen, and seed-recorded.
- `harness.hidden_runner` can score a copied worktree and write machine-readable results.
- Hidden cases are not present in `benchmark_template/`, prompts, or run workspaces.

## Stage 3: Experiment Configuration

Create `configs/initial_experiment.yaml` as the source of truth.

It must define:

- repeat count: `5`
- default implementation parallelism: `3`
- default judge parallelism: `2`
- C0-C4 cell definitions
- Spark edit modes: `direct`, `proposal`
- root, sublead, and leaf models
- root, sublead, and leaf reasoning levels
- per-role Spark reasoning knobs
- sublead count
- leaves per sublead
- `agents.max_threads`
- `agents.max_depth`
- job timeout
- prompt template path
- rendered Codex config template path
- scoring weights

Initial model constraints:

- Only `gpt-5.5` and `gpt-5.3-codex-spark` are used.
- Spark leaves always use `gpt-5.3-codex-spark`.
- Every initial Spark leaf uses `model_reasoning_effort = "xhigh"`.
- GPT-5.5 root reasoning varies by cell.
- C4 subleads use GPT-5.5 medium.

Default C4 topology:

```text
root: 1 x GPT-5.5 xhigh
subleads: 3 x GPT-5.5 medium
leaves: 18 x Spark xhigh
shape: each sublead coordinates 6 Spark leaves
max_depth: 2
max_threads: at least 24
```

Done when:

- `configs/initial_experiment.yaml` expands to exactly 45 implementation runs.
- C0-C4 encode the agreed models, reasoning levels, depth, breadth, repeats, and Spark edit modes.
- Spark reasoning is configurable per role while initially set to `xhigh`.
- Scoring weights and runtime knobs are config-driven.

## Stage 4: Prompts And Agent Configs

Create reusable prompt files.

`task_common.md` must include:

- Full RuleLedger behavior.
- TypeScript API.
- Python API.
- Constraints.
- Public test expectations.
- Prohibition on nested Codex calls.
- Final response JSON schema.

`task_solo.md`:

- Used by C0.
- Explicitly forbids subagents.
- Prioritizes correctness, deterministic behavior, hidden-test robustness, and maintainability.

`task_flat_spark.md`:

- Used by C1-C3.
- Root lead assigns six Spark leaves.
- Works for both direct and proposal modes.

Flat Spark roles:

1. TypeScript parser and normalizer.
2. TypeScript reducer, entitlements, and report.
3. Python parser and normalizer.
4. Python reducer, entitlements, and report.
5. Cross-language fixture and public-test writer.
6. Adversarial reviewer.

`task_depth2_subleads.md`:

- Used by C4.
- GPT-5.5 xhigh root lead delegates to three GPT-5.5 medium subleads.
- Each sublead delegates to six Spark xhigh leaves.

C4 sublead ownership:

- Sublead A: TypeScript implementation.
- Sublead B: Python implementation.
- Sublead C: parity, fixtures, public tests, integration risk, and adversarial review.

`judge.md`:

- Blind GPT-5.5 xhigh judge.
- Does not reveal topology.
- Does not modify files.
- Reviews source, tests, diffs, and logs.
- Returns strict JSON.

Custom Codex agent templates:

- Spark direct implementer: Spark xhigh, workspace-write.
- Spark proposal implementer: Spark xhigh, read-only.
- Spark tester direct: Spark xhigh, workspace-write for tests.
- Spark tester proposal: Spark xhigh, read-only.
- Spark adversary: Spark xhigh, read-only.
- GPT-5.5 medium sublead: GPT-5.5 medium.

Done when:

- All shared, solo, flat Spark, depth-2, and judge prompts exist.
- Prompts forbid nested Codex or external AI invocation inside measured runs.
- Prompt templates clearly distinguish direct edit mode from proposal-only mode.
- Codex agent templates render the correct model, reasoning, sandbox, and role instructions for each cell.

## Stage 5: Orchestration

Create `scripts/run_experiment.ps1` as the main user command:

```powershell
.\scripts\run_experiment.ps1 -Jobs 3
```

This script should call a Python orchestrator.

The orchestrator must:

1. Run preflight checks.
2. Create or verify frozen hidden tests.
3. Expand the configured experiment matrix into 45 implementation runs.
4. Create a timestamped experiment directory under `runs/`.
5. Copy `benchmark_template/` into each run workspace.
6. Initialize a git repo in each workspace and commit the baseline.
7. Render per-run prompts and `.codex` config files.
8. Run implementation jobs in parallel.
9. Run public tests and typecheck.
10. Run hidden tests from outside the workspaces.
11. Run blind GPT-5.5 xhigh judges.
12. Parse JSONL usage.
13. Compute scores.
14. Generate CSV, SQLite, HTML, and PDF outputs.

Support resume behavior:

- Skip completed steps when artifacts already exist and validate.
- Allow rerunning failed runs with an explicit flag.
- Never silently overwrite a completed experiment directory.

Create `scripts/run_pilot.ps1`:

- Runs one C0 repeat and one C1 proposal repeat.
- Verifies end-to-end behavior before the full experiment.

Done when:

- `scripts/run_experiment.ps1 -Jobs 3` launches the configured experiment through the Python orchestrator.
- The orchestrator can expand, schedule, resume, and record all configured runs.
- `scripts/run_pilot.ps1` executes a minimal C0/C1 smoke test.
- Completed runs are skipped unless an explicit rerun flag is supplied.

## Stage 6: Codex Execution

Measured implementation command shape:

```text
codex exec --json
  --cd <run_worktree>
  --sandbox workspace-write
  --ask-for-approval never
  --model gpt-5.5
  -c model_reasoning_effort=<cell_root_reasoning>
  -c agents.max_threads=<cell_threads>
  -c agents.max_depth=<cell_depth>
  <rendered_prompt>
```

Judge command shape:

```text
codex exec --json
  --cd <run_worktree>
  --sandbox read-only
  --ask-for-approval never
  --model gpt-5.5
  -c model_reasoning_effort="xhigh"
  <judge_prompt>
```

Preflight must detect whether `codex` is callable. If direct invocation fails, support:

```powershell
$env:CODEX_BIN = "path\to\working\codex"
```

Measured runs must not invoke `codex`, `codex exec`, external AI services, or nested agent processes from inside the run.

Done when:

- Preflight verifies a callable Codex executable or fails with a clear `CODEX_BIN` instruction.
- Implementation and judge commands use `codex exec --json` with the configured model, reasoning, depth, threads, sandbox, and prompt.
- Raw JSONL and stderr logs are captured for every implementation and judge run.
- Measured prompts and configs prevent nested Codex execution.

## Stage 7: Artifacts

Each run directory should contain:

```text
metadata.json
rendered_prompt.md
codex_config/
events.jsonl
stderr.log
final_response.json
wall_time.json
public_ts.log
typecheck.log
public_py.log
hidden-results.json
judge.events.jsonl
judge.stderr.log
judge.json
diff.patch
diff-numstat.txt
usage.json
score.json
```

Experiment-level outputs:

```text
results/results.csv
results/results.sqlite
results/aggregate.json
report/report.html
report/report.pdf
```

Done when:

- Every run produces the expected metadata, prompt, config, log, diff, usage, test, judge, and score artifacts.
- Experiment-level CSV, SQLite, aggregate JSON, HTML, and PDF outputs are written.
- Artifact paths are stable enough for the report appendix to reference.

## Stage 8: Usage Parsing

Parse `turn.completed.usage` from every `events.jsonl`.

Track:

- `input_tokens`
- `cached_input_tokens`
- `output_tokens`
- `reasoning_output_tokens`
- total implementation tokens
- total judge tokens
- implementation-only GPT-5.5 tokens when observable
- judge-inclusive GPT-5.5 tokens
- Spark tokens when observable
- best-effort attribution method

If mixed-agent JSONL does not expose per-model usage, the report must label model-level attribution as best effort and still preserve total usage.

Done when:

- `turn.completed.usage` is parsed from implementation and judge JSONL files.
- Usage summaries include implementation-only and judge-inclusive token totals.
- Any per-model attribution is recorded with an explicit attribution method.
- Missing or ambiguous model attribution is reported without dropping total usage.

## Stage 9: Scoring

Default score:

```text
quality_score =
  0.50 * hidden_test_score
+ 0.15 * public_test_score
+ 0.15 * typecheck_score
+ 0.15 * judge_overall_score
+ 0.05 * minimality_score
```

Compute:

- quality per GPT-5.5 implementation token.
- quality per judge-inclusive GPT-5.5 token.
- quality per total implementation token.
- quality per wall-clock minute.
- hidden-test pass rate.
- public-test pass rate.
- judge score.
- changed files.
- production LOC.
- test LOC.
- total added/deleted LOC.
- failure rate.

Partial runs receive whatever score they earn. Missing outputs score as zero for that component but remain visible in results.

Done when:

- Scoring combines hidden tests, public tests, typecheck, judge score, and minimality using config weights.
- Partial and failed runs remain in the results table.
- Primary and secondary metrics are computed for every run.
- Score JSON, CSV rows, and SQLite rows agree for a sample of runs.

## Stage 10: Report

Generate a readable PDF styled like a lightweight academic paper.

Report sections:

- Title.
- Abstract.
- Methods.
- Benchmark task.
- Experiment matrix.
- Results.
- Direct edit versus proposal-only comparison.
- C4 stress-test analysis.
- Token attribution notes.
- Limitations.
- Appendix with per-run rows and artifact paths.

Charts:

- Primary metric by cell.
- Hidden-test score by cell.
- GPT-5.5 implementation token usage by cell.
- Wall-clock time by cell.
- Failure rate by cell.
- Direct edit versus proposal-only deltas.

Implementation:

- Use Python for data preparation.
- Use HTML/CSS for report layout.
- Use Node Playwright to render HTML to PDF.
- Save both `report.html` and `report.pdf`.

Done when:

- The report generator creates HTML and PDF from experiment results.
- The PDF includes methods, matrix, results, C4 stress-test analysis, limitations, and appendix.
- Charts and tables render correctly for pilot data and full experiment data.
- The report ranks cells by quality per GPT-5.5 implementation token.

## Stage 11: Validation

Before the full run:

1. Run the pilot.
2. Confirm Codex invocation works.
3. Confirm hidden tests are not in implementation workspaces.
4. Confirm public tests and hidden tests score a deliberately incomplete solution.
5. Confirm JSONL usage parsing works.
6. Confirm judge JSON parses.
7. Confirm CSV, SQLite, HTML, and PDF are generated.
8. Confirm resume behavior skips completed artifacts.

Acceptance criteria for the full implementation:

- `.\scripts\run_experiment.ps1 -Jobs 3` can run the full 45-run experiment.
- All raw artifacts are preserved.
- Hidden tests remain outside implementation workspaces.
- Results rank cells by quality per GPT-5.5 implementation token.
- The PDF report is human-readable and includes methods, results, limitations, and appendix.
- New cells can be added later by editing config rather than changing orchestration code.

Done when:

- The pilot passes end to end.
- The full `run_experiment.ps1` workflow can run without manual orchestration.
- Hidden-test isolation, JSONL parsing, scoring, resume behavior, and PDF generation are verified.
- The final report and raw artifacts are complete enough to inspect or reproduce the experiment.

## Assumptions

- This repository starts essentially empty.
- The main audience is a human Codex user, not an academic reviewer.
- The project is open source under MIT.
- The initial experiment uses only GPT-5.5 and GPT-5.3-Codex-Spark.
- Spark leaves are always leaves.
- Spark reasoning is initially locked to `xhigh`, but future experiments can vary it per role.
- C4 intentionally breaks away from documented defaults for subagent depth and breadth.
- Per-model token attribution may require best-effort inference if Codex JSONL does not expose child model usage.
