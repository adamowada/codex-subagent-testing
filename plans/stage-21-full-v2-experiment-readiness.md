# Stage 21: Full V2 Experiment Readiness

## Purpose

Stage 21 is the readiness gate for scaling RuleLedger v2 from a calibrated
pilot to a full experiment matrix. Stages 14 through 20 made v2 selectable,
implemented the starter and hard-mode hidden suite, split v2 scoring/reporting,
and added a small v2 pilot. Stage 21 should add the full v2 experiment shape
only after the pilot proves that v2 is hard enough, operationally stable, and
worth the runtime and token budget.

This stage should answer:

```text
Is RuleLedger v2 ready to run as a full, reproducible experiment with stable
hidden assets, useful reasoning/topology spread, and the same artifact rigor as
v1?
```

## Scope

Stage 21 owns:

- Defining the full v2 experiment matrix.
- Adding a dedicated full v2 config.
- Keeping v2 asset paths, scoring profile, topology choices, repeat counts, and
  reasoning levels configurable.
- Verifying that v1, v2 starter, v2 pilot, and full v2 configs all validate.
- Verifying that v2 hidden case generation is stable from source and fixed seed.
- Documenting the full v2 run command.
- Preserving raw evidence requirements for full v2 runs.

Stage 21 does not own:

- Running the full v2 experiment unless explicitly requested.
- Changing v2 hidden cases without a Stage 20 calibration conclusion.
- Hand-editing generated hidden cases or run outputs.
- Replacing v1 configs or v1 scoring.
- Editing locked top-level source-of-truth documents unless explicitly
  requested.
- Committing generated `runs/` output.

## Inputs

Stage 21 starts from:

```text
configs/initial_experiment.yaml
configs/ruleledger_v2.yaml
configs/ruleledger_v2_pilot.yaml
configs/scoring.yaml
configs/scoring_v2.yaml
scripts/run_experiment.ps1
scripts/run_pilot.ps1
scripts/validate_stage11.ps1
harness/matrix.py
harness/orchestrator.py
harness/preflight.py
harness/validation.py
harness/report_data.py
hidden_tests/generators/generate_v2_cases.py
hidden_tests/generators/ruleledger_v2_oracle.py
hidden_tests/cases_v2/manifest.json
benchmark_template_v2/
plans/stage-20-calibrate-with-pilot-runs.md
```

Stage 21 should use Stage 20 pilot results if they exist. If only dry-run
validation exists, Stage 21 can add the full v2 config and readiness checks, but
the final go/no-go decision should remain conditional on a real pilot.

## Current State

The repository has:

- `configs/ruleledger_v2.yaml`, a one-run v2 starter smoke config.
- `configs/ruleledger_v2_pilot.yaml`, a two-run v2 calibration pilot.
- `configs/ruleledger_v2_experiment.yaml`, an 18-run full v2 readiness matrix.
- `configs/scoring_v2.yaml`, the v2 scoring profile.
- `benchmark_template_v2/`, the v2 starter.
- `hidden_tests/cases_v2/`, the v2 hidden suite.
- Stage 19 report fields for category means, saturated categories,
  performance pass/timeout behavior, gates, and root-reasoning spread.

The repository has the full v2 matrix config analogous to the initial v1
experiment. It should be treated as config-ready. Full measured execution
remains conditional on real Stage 20 pilot evidence and working Codex access.

## Pilot Readiness Gate

Before treating the full v2 experiment as ready to execute, confirm the Stage
20 pilot result.

Required pilot signals:

```text
hidden-case isolation passes
report generation passes
major hidden categories do not saturate above 0.95
low/medium/high/xhigh or weak/strong pilot cells show visible quality spread
performance timeout rate is meaningful rather than infrastructure noise
judge output parses reliably
token and wall-clock costs are operationally acceptable
```

If a real v2 pilot has not been run because the local Codex executable is not
available, Stage 21 should mark full execution readiness as blocked while still
allowing static config readiness to be implemented and tested.

## Proposed Full V2 Config

Add:

```text
configs/ruleledger_v2_experiment.yaml
```

This config should use:

```text
benchmark.version: ruleledger_v2
paths.benchmark_template: benchmark_template_v2
paths.hidden_cases: hidden_tests/cases_v2
scoring.path: configs/scoring_v2.yaml
```

The config should stay JSON-compatible YAML, matching the existing repository
style.

## Proposed Matrix

The full matrix should be smaller than the initial 45-run v1 matrix until v2
runtime and token costs are proven, but it should cover enough variation to
answer the v2 question.

Recommended first full matrix:

```text
V2C0: solo GPT-5.5 low
V2C1: solo GPT-5.5 medium
V2C2: solo GPT-5.5 high
V2C3: solo GPT-5.5 xhigh
V2C4: flat Spark direct, GPT-5.5 high or xhigh root, six Spark xhigh leaves
V2C5: flat Spark proposal, GPT-5.5 high or xhigh root, six Spark xhigh leaves
```

Recommended repeats:

```text
3 repeats per cell for first full v2 pass
```

This yields 18 implementation runs if each Spark cell has one mode each. It is
large enough to compare reasoning levels and Spark modes, but still smaller
than the initial 45-run v1 experiment.

If the Stage 20 pilot shows high variance, increase repeats to 5 before using
the results for strong claims.

## Matrix Design Rationale

### Solo Reasoning Sweep

The solo cells establish the core v2 reasoning curve:

```text
low -> medium -> high -> xhigh
```

This is the main way to verify that v2 reports show visible quality spread
across reasoning levels.

### Flat Spark Direct

The direct Spark cell tests whether leaf editing improves hard-mode coverage
enough to justify coordination and token cost.

It should use six Spark leaves because the flat Spark prompt assigns exactly
six leaf roles.

### Flat Spark Proposal

The proposal Spark cell tests whether read-only Spark proposals help the
GPT-5.5 root without adding merge or direct-edit conflict risk.

This is especially useful if Stage 20 shows direct editing is risky or if v2
complexity benefits from parallel analysis.

### Depth-2 Subleads

Depth-2 should not be added by default unless Stage 20 or later analysis shows
that flat Spark is promising and coordination depth is worth testing.

If added, it should be a deliberate stress-test cell, similar to v1 C4, not a
default assumption.

## Config Requirements

The full v2 config should include:

- `schema_version: 1`
- a filesystem-safe experiment id, such as `ruleledger_v2_full`
- v2 benchmark metadata
- v2 template and hidden case paths
- v2 scoring config path
- GPT-5.5 and Spark model declarations
- direct and proposal Spark mode definitions if Spark cells are included
- judge model, reasoning, prompt template, and read-only sandbox
- cells with deterministic ids, repeats, topology, prompt template, root
  settings, leaf settings where applicable, and agent depth/thread settings

Recommended full config command:

```powershell
.\scripts\run_experiment.ps1 -Config configs\ruleledger_v2_experiment.yaml -Jobs 3 -JudgeJobs 1
```

## Hidden Case Stability Check

Stage 21 should verify that regenerated v2 hidden cases are stable.

Recommended check:

1. Capture current `hidden_tests/cases_v2/manifest.json`.
2. Run the v2 generator with the fixed seed.
3. Confirm generated manifest file list, hashes, seed, category weights, and
   case counts are unchanged.
4. Confirm no generated hidden file changes remain after the check unless a
   deliberate calibration update is being committed.

If the generator currently writes in place, use a temporary output directory if
supported. If it does not support alternate output directories, Stage 21 may add
that option to make stability checks safer.

## Artifact And Evidence Contract

Full v2 runs must preserve all evidence required for v1:

```text
JSONL events
stderr logs
rendered prompts
rendered Codex configs
worktree pointers
diffs
public test logs and metadata
hidden runner logs and sanitized hidden results
judge logs and judge JSON
usage summaries
score JSON
state JSON
CSV output
SQLite output
aggregate JSON
HTML report
PDF report
validation output
```

Failed and partial runs must remain in outputs. They are part of the
measurement, not noise to remove.

## Reporting Expectations

The full v2 report should show:

- benchmark version and scoring profile.
- category means.
- saturated categories.
- hidden correctness.
- hidden parity.
- performance score.
- performance pass rate.
- performance timeout rate.
- public/typecheck gates.
- root-reasoning spread.
- token-efficiency metrics.
- wall-clock time.
- direct versus proposal comparisons if both Spark modes are present.
- clear labeling if v1 and v2 rows are ever selected together.

## Validation Plan

Static config validation:

```powershell
python -m harness.validation --config configs/initial_experiment.yaml --skip-preflight --allow-missing-report
python -m harness.validation --config configs/ruleledger_v2.yaml --skip-preflight --allow-missing-report
python -m harness.validation --config configs/ruleledger_v2_pilot.yaml --skip-preflight --allow-missing-report
python -m harness.validation --config configs/ruleledger_v2_experiment.yaml --skip-preflight --allow-missing-report
```

Matrix summaries:

```powershell
python -m harness.matrix configs/ruleledger_v2_experiment.yaml
```

Dry-run the full v2 command:

```powershell
.\scripts\run_experiment.ps1 -Config configs\ruleledger_v2_experiment.yaml -Jobs 3 -JudgeJobs 1 -DryRun
```

Run tests:

```powershell
python -m pytest tests/test_matrix.py tests/test_stage5_orchestration.py tests/test_stage11_validation.py
python -m pytest
```

Check diff hygiene:

```powershell
git diff --check
```

## Implementation Steps

1. Review Stage 20 pilot outputs if available.
2. Decide whether full execution readiness is unblocked or still conditional on
   a real pilot.
3. Add `configs/ruleledger_v2_experiment.yaml`.
4. Include a solo reasoning sweep across low, medium, high, and xhigh.
5. Include Spark direct/proposal cells only if justified by pilot goals.
6. Use six Spark leaves for flat Spark cells to match the flat Spark prompt.
7. Set `max_threads` high enough for each configured topology.
8. Add matrix tests for full v2 run count, benchmark metadata, scoring weights,
   reasoning sweep, Spark modes, and leaf counts.
9. Add validation tests for the full v2 config.
10. Add hidden case regeneration stability checks if the generator supports a
    safe temporary output path.
11. Run static validation and dry-run commands.
12. Do not run the full measured experiment unless explicitly requested.

## Acceptance Criteria

Stage 21 is complete when:

- Full v2 config exists and validates.
- Full v2 config expands deterministically to the intended matrix.
- V1 initial config still validates.
- V2 starter config still validates.
- V2 pilot config still validates.
- V2 hidden case manifest stability is checked or a safe stability-check path is
  added.
- The full v2 dry-run command succeeds.
- The repository has a documented full v2 command.
- No generated run outputs are committed.
- If a real Stage 20 pilot has not run, the final readiness status clearly says
  full measured execution remains blocked on pilot evidence and executable
  Codex access.

## Risks And Mitigations

Risk: Full v2 matrix is too expensive.

Mitigation: Start with 18 runs and increase repeats only after pilot variance
justifies it.

Risk: Full v2 results are interpreted before pilot calibration is complete.

Mitigation: Keep Stage 21 execution readiness conditional on real Stage 20 pilot
evidence.

Risk: Spark topology config disagrees with prompt requirements.

Mitigation: Assert six flat Spark leaves and sufficient `max_threads` in tests.

Risk: Hidden case regeneration changes files unexpectedly.

Mitigation: Add or use a temp-output generator mode for stability checks.

Risk: V1 compatibility regresses.

Mitigation: Keep v1 validation and report tests in the Stage 21 verification
set.

Risk: V1 and v2 results are silently mixed.

Mitigation: Use Stage 19 benchmark labels and benchmark-specific rankings.

## Open Questions

- Should the first full v2 matrix use 3 repeats or 5 repeats per cell?
- Should Spark direct mode be included immediately, or should proposal mode be
  tested first if pilot results suggest direct editing adds risk?
- Should depth-2 subleads be deferred to a later v2 stress-test stage?
- Should hidden case stability be implemented as a dedicated script, a pytest,
  or a validation check?
- Where should pilot calibration conclusions be recorded if full readiness is
  still blocked?
