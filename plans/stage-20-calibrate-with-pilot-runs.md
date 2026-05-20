# Stage 20: Calibrate With Pilot Runs

## Purpose

Stage 20 turns the RuleLedger v2 benchmark from a completed harness path into a
measured calibration target. Stages 14 through 19 made v2 selectable, created
the v2 starter, specified hard-mode semantics, generated hidden cases, upgraded
the hidden runner, and revised scoring/reporting. Stage 20 should run a small
real v2 pilot and use its evidence to decide whether v2 is hard enough,
stable enough, and visible enough for a full experiment.

This stage should answer:

```text
Can a small RuleLedger v2 pilot run end to end, preserve all evidence, and show
useful category and quality spread without hidden-case leakage or category
saturation?
```

## Scope

Stage 20 owns:

- Adding a dedicated v2 pilot experiment config.
- Selecting a small but meaningful set of v2 cells.
- Running the v2 pilot through the normal orchestration path.
- Preserving and validating all run evidence.
- Inspecting v2 category means, saturated categories, performance pass/timeout
  behavior, judge spread, token usage, and wall-clock time.
- Defining a reproducible calibration process if the pilot shows saturation,
  instability, or poor discrimination.
- Keeping v1 configs, v1 pilot behavior, and v1 reporting intact.

Stage 20 does not own:

- Adding the full v2 matrix.
- Changing locked source-of-truth documents unless explicitly requested.
- Hand-editing generated hidden cases.
- Hand-editing run outputs, score outputs, or report outputs.
- Committing generated `runs/` output.
- Hiding weak or failed pilot runs from the report.

## Inputs

Stage 20 starts from:

```text
configs/ruleledger_v2.yaml
configs/scoring_v2.yaml
scripts/run_pilot.ps1
scripts/run_experiment.ps1
harness/orchestrator.py
harness/matrix.py
harness/validation.py
harness/report_data.py
harness/scoring.py
hidden_tests/generators/generate_v2_cases.py
hidden_tests/generators/ruleledger_v2_oracle.py
hidden_tests/cases_v2/manifest.json
benchmark_template_v2/
plans/stage-19-revise-v2-scoring-and-reporting.md
```

The current v2 config is a single-run starter config. Stage 20 should add a
separate pilot config instead of overloading that starter config.

## Current State

The repository has:

- A v2 starter benchmark under `benchmark_template_v2/`.
- V2 hidden cases under `hidden_tests/cases_v2/`.
- A v2 scoring profile in `configs/scoring_v2.yaml`.
- A one-cell v2 config in `configs/ruleledger_v2.yaml`.
- A configurable pilot script:

```powershell
.\scripts\run_pilot.ps1 -Config configs\ruleledger_v2.yaml
```

That one-cell config is useful as a smoke path, but it is not enough for
calibration because it only exercises one xhigh solo cell. Stage 20 needs at
least one weaker cell and one stronger cell so the report can show spread.

## Proposed Pilot Config

Add:

```text
configs/ruleledger_v2_pilot.yaml
```

The config should use the v2 benchmark assets:

```json
{
  "benchmark": {
    "version": "ruleledger_v2"
  },
  "paths": {
    "benchmark_template": "benchmark_template_v2",
    "hidden_cases": "hidden_tests/cases_v2"
  },
  "scoring": {
    "path": "configs/scoring_v2.yaml"
  }
}
```

The exact JSON-compatible YAML shape should follow the existing config style in
`configs/ruleledger_v2.yaml`.

## Pilot Cell Design

The pilot should stay small, but it must provide enough contrast to diagnose
whether v2 is too easy, too hard, or too noisy.

Recommended cells:

```text
V2P0: solo, GPT-5.5 low
V2P1: solo, GPT-5.5 medium
V2P2: solo, GPT-5.5 xhigh
V2P3: flat Spark-assisted, GPT-5.5 high or xhigh root, Spark leaves xhigh
```

Recommended repeats:

```text
1 repeat per cell for the first calibration pass
```

If early results are noisy or contradictory, increase only the pilot repeat
count, not the full experiment matrix.

### Why These Cells

`V2P0` and `V2P1` test whether lower reasoning levels struggle with hard-mode
semantics. If they score near perfect, the benchmark is probably too easy.

`V2P2` gives a strong solo reference. If it also fails broadly, the benchmark or
starter prompt may be too hard or operationally broken.

`V2P3` tests whether Spark assistance improves coverage or introduces
coordination overhead. This is useful before designing the full v2 matrix.

## Commands

Dry-run the pilot config first:

```powershell
.\scripts\run_pilot.ps1 -Config configs\ruleledger_v2_pilot.yaml -DryRun
```

Run the pilot:

```powershell
.\scripts\run_pilot.ps1 -Config configs\ruleledger_v2_pilot.yaml -Jobs 1 -JudgeJobs 1
```

Validate the pilot:

```powershell
.\scripts\validate_stage11.ps1 -Config configs\ruleledger_v2_pilot.yaml -ExperimentDir <pilot-run-dir>
```

If the existing validation script does not expose the needed config and
experiment directory switches, use the Python module directly:

```powershell
python -m harness.validation --config configs\ruleledger_v2_pilot.yaml --experiment-dir <pilot-run-dir>
```

## Evidence Contract

Every pilot run should preserve the same evidence as v1 and the v2 starter:

```text
rendered_prompt.md
judge_prompt.md
codex_config/config.toml
events.jsonl
stderr.log
final_response.json
wall_time.json
diff.patch
diff-numstat.txt
typecheck.log
typecheck.meta.json
public_ts.log
public_ts.meta.json
public_py.log
public_py.meta.json
hidden-runner.log
hidden-runner.meta.json
hidden-results.json
judge.events.jsonl
judge.stderr.log
judge.wall_time.json
judge.json
usage.json
score.json
state.json
```

Experiment-level outputs should include:

```text
matrix.json
matrix-summary.json
resolved_config.json
preflight.json
status.json
orchestrator.log
results/results.csv
results/results.sqlite
results/aggregate.json
report/report.html
report/report.pdf
validation.json
```

Do not commit these generated outputs unless explicitly requested.

## Calibration Metrics

Stage 20 should inspect the aggregate report and per-run score data.

### Category Saturation

Use Stage 19 report fields:

```text
aggregate.v2.category_means
aggregate.v2.category_saturation
```

Target:

```text
No major hidden category mean should exceed 0.95 across pilot cells.
```

If a major category saturates, inspect whether:

- the category is genuinely too easy.
- the starter template already solves too much.
- public tests accidentally reveal too much.
- hidden cases lack adversarial variety.
- the scoring category has too few cases or too few points.

### Quality Spread

Compare:

```text
quality_score
hidden_correctness
hidden_parity
performance
judge
minimality
```

Target:

```text
Lower-reasoning cells and stronger cells should separate visibly.
```

The exact spread threshold should be conservative at first. A useful initial
target is a visible hidden-correctness gap of at least 0.10 between weak and
strong cells, unless all cells fail due to an infrastructure issue.

### Performance Behavior

Inspect:

```text
performance
performance_pass_rate
performance_timeout_rate
implementation_elapsed_seconds
```

Target:

- performance cases should be hard enough to catch inefficient solutions.
- timeout rate should not be dominated by harness instability.
- wall-clock time should remain practical for the full experiment.

Timeouts are valid scored failures when implementation code is too slow. They
are a calibration problem only if correct or near-correct solutions time out
because the case sizes or harness limits are unreasonable.

### Judge Variance

Inspect:

```text
judge
score_warnings
judge.wall_time.json
judge.json
```

Target:

- judge scores should broadly align with hidden correctness and maintainability.
- malformed judge output should be rare and visible.
- judge runtime should remain within configured timeouts.

The judge is a secondary signal, not ground truth. Hidden correctness remains
the primary calibration anchor.

### Token And Time Cost

Inspect:

```text
implementation_tokens
gpt55_implementation_tokens
judge_tokens
quality_per_gpt55_impl_token
quality_per_wall_clock_minute
implementation_elapsed_seconds
```

Target:

- v2 costs should be explainable relative to v1.
- Spark-assisted cells should not be added to the full v2 matrix unless their
  quality signal justifies the token and time cost.

## Calibration Adjustment Rules

If calibration changes are needed, make them reproducible.

Allowed changes:

- Modify `hidden_tests/generators/ruleledger_v2_oracle.py`.
- Modify `hidden_tests/generators/generate_v2_cases.py`.
- Regenerate `hidden_tests/cases_v2/` from the fixed seed.
- Update manifests and hashes through the generator.
- Adjust case counts, point values, category weights, or input distributions in
  generator code.
- Adjust v2 pilot config repeat count or selected cells.

Forbidden changes:

- Hand-edit generated hidden case JSON.
- Hand-edit `hidden-results.json`.
- Hand-edit score, aggregate, CSV, SQLite, HTML, or PDF outputs.
- Copy hidden cases into prompts, starter templates, or run worktrees.
- Drop failed runs from calibration summaries.

## Decision Outcomes

Stage 20 should end with one of these outcomes.

### Outcome A: Pilot Is Calibrated

The pilot passes end to end, categories do not saturate, performance behavior is
stable, and quality spread is useful.

Next action:

```text
Proceed to Stage 21 full v2 experiment readiness.
```

### Outcome B: Benchmark Too Easy

Weak cells score near strong cells or major categories saturate above 0.95.

Next action:

```text
Increase hidden-case difficulty through generator/oracle changes, regenerate
cases, and rerun the pilot.
```

### Outcome C: Benchmark Too Hard Or Broken

All cells fail nearly everything, or strong cells cannot clear basic intended
semantics.

Next action:

```text
Inspect starter prompt, public tests, hidden runner, and v2 semantics for
contract mismatch. Fix source issues and rerun the pilot.
```

### Outcome D: Operational Instability

Runs fail due to timeouts, malformed artifacts, judge instability, hidden runner
errors, or report/validation issues.

Next action:

```text
Fix harness stability before changing benchmark difficulty.
```

## Implementation Steps

1. Add `configs/ruleledger_v2_pilot.yaml`.
2. Include at least one low/medium solo v2 cell and one stronger high/xhigh or
   Spark-assisted v2 cell.
3. Ensure pilot matrix expansion works with the existing config validator.
4. Ensure `scripts/run_pilot.ps1 -Config configs/ruleledger_v2_pilot.yaml
   -DryRun` selects the intended pilot runs.
5. Add or update tests for v2 pilot config expansion and pilot selection.
6. Run static validation for the v2 pilot config.
7. Run the real v2 pilot.
8. Generate report outputs and validation output.
9. Inspect v2 category means, category saturation, performance rates, judge
   variance, token usage, and wall-clock time.
10. If calibration changes are needed, update generator/oracle code and
    regenerate hidden cases from the fixed seed.
11. Rerun the pilot after any calibration change.
12. Record the calibration conclusion in a follow-up planning note or report
    artifact under `plans/` if source-level changes are needed.

## Test Plan

Run focused tests:

```powershell
python -m pytest tests/test_matrix.py tests/test_stage11_validation.py tests/test_stage10_report.py
```

Run the full test suite:

```powershell
python -m pytest
```

Validate configs:

```powershell
python -m harness.validation --config configs/initial_experiment.yaml --skip-preflight --allow-missing-report
python -m harness.validation --config configs/ruleledger_v2.yaml --skip-preflight --allow-missing-report
python -m harness.validation --config configs/ruleledger_v2_pilot.yaml --skip-preflight --allow-missing-report
```

Dry-run pilot:

```powershell
.\scripts\run_pilot.ps1 -Config configs\ruleledger_v2_pilot.yaml -DryRun
```

Run pilot:

```powershell
.\scripts\run_pilot.ps1 -Config configs\ruleledger_v2_pilot.yaml -Jobs 1 -JudgeJobs 1
```

Run diff hygiene:

```powershell
git diff --check
```

## Acceptance Criteria

Stage 20 is complete when:

- `configs/ruleledger_v2_pilot.yaml` exists and validates.
- The v2 pilot config expands to the intended small run set.
- The existing v1 pilot behavior remains unchanged.
- The v2 pilot runs end to end.
- Run-level artifacts are preserved for every v2 pilot run.
- Experiment-level CSV, SQLite, aggregate JSON, HTML report, PDF report, and
  validation output are generated.
- Hidden case isolation validation passes.
- `aggregate.v2.category_means` and `aggregate.v2.category_saturation` are
  present and useful.
- No major hidden category mean is above 0.95 across pilot cells.
- Pilot cells show useful quality and hidden-correctness spread.
- Performance pass and timeout rates are visible.
- Any calibration adjustment is reproducible from generator/oracle source and a
  fixed seed.

## Risks And Mitigations

Risk: The pilot is too small to distinguish signal from noise.

Mitigation: Start with one repeat per cell, then increase pilot repeats before
designing a full v2 matrix.

Risk: A category saturates because cases are too easy.

Mitigation: Add harder cases through the generator and regenerate from the fixed
seed.

Risk: All cells fail because the prompt or starter contract is unclear.

Mitigation: Inspect public tests, starter README, prompt templates, and hidden
runner operation expectations before increasing hidden difficulty.

Risk: Performance cases dominate wall-clock time.

Mitigation: Tune generated case sizes or timeouts through source-controlled
generator/harness settings, then rerun the pilot.

Risk: Calibration accidentally leaks hidden details.

Mitigation: Keep analysis at category and aggregate level. Do not copy hidden
case inputs or expected outputs into prompts, plans, reports, or comments.

Risk: V2 results are compared directly against v1 rankings.

Mitigation: Use Stage 19 mixed-version labeling and benchmark-specific rankings.
Do not interpret v1 and v2 quality scores as a single leaderboard unless an
explicit cross-version analysis mode is added later.

## Open Questions

- Should the first v2 pilot include Spark assistance, or should Spark wait until
  after low/medium/high/xhigh solo spread is confirmed?
- What minimum hidden-correctness spread should be required before moving to
  Stage 21?
- Should the pilot require more than one repeat per cell if judge or hidden
  performance variance is high?
- Should calibration conclusions be captured in a structured JSON artifact, a
  Markdown note under `plans/`, or both?
