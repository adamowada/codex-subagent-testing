# Stage 11: Validation

## Purpose

Stage 11 is the final integration gate for the initial Codex subagent topology benchmark. It proves that the benchmark harness can run the pilot and full experiment reproducibly, preserve evidence, keep hidden tests isolated, parse usage, score partial runs, resume safely, and generate readable reports.

This stage should answer:

```text
Is the harness trustworthy enough to spend the full 45-run experiment budget?
```

Stage 11 should not add new benchmark behavior unless validation exposes a gap. It should primarily run the existing workflow, inspect generated artifacts, and fix defects in the implementation stages that prevent the workflow from satisfying the benchmark contract.

## Scope

Stage 11 owns:

- End-to-end pilot validation.
- Preflight validation of local tools, config expansion, prompt rendering, hidden cases, and Codex invocation.
- Verification that hidden tests remain outside implementation workspaces.
- Verification that incomplete starter solutions receive partial or failing scores.
- Verification that Codex JSONL usage parsing produces usable token summaries.
- Verification that judge output is strict, parseable JSON.
- Verification that CSV, SQLite, aggregate JSON, HTML, and PDF outputs are generated.
- Resume validation for completed artifacts, config drift, matrix drift, and failed-phase reruns.
- Final acceptance of the full `run_experiment.ps1` workflow.

Stage 11 does not own:

- Designing new benchmark cases.
- Changing the experiment matrix.
- Reweighting the scoring system.
- Changing the reporting structure except to fix validation failures.
- Copying hidden cases into prompts, templates, run worktrees, or public artifacts.
- Editing locked source-of-truth documents.

## Inputs

Stage 11 consumes the completed implementation from Stages 1 through 10:

```text
benchmark_template/
configs/initial_experiment.yaml
configs/scoring.yaml
codex_templates/
hidden_tests/
harness/
prompts/
scripts/run_pilot.ps1
scripts/run_experiment.ps1
scripts/render_report_pdf.mjs
tests/
```

The initial experiment should expand to 45 measured implementation runs:

- C0 solo GPT-5.5 xhigh: 5 runs.
- C1 flat Spark GPT-5.5 medium: 5 direct and 5 proposal runs.
- C2 flat Spark GPT-5.5 high: 5 direct and 5 proposal runs.
- C3 flat Spark GPT-5.5 xhigh: 5 direct and 5 proposal runs.
- C4 depth-2 sublead stress test: 5 direct and 5 proposal runs.

The pilot should select:

```text
C0_r01
C1_proposal_r01
```

This pair validates both the solo path and the proposal-only Spark path without spending the full experiment budget.

## Outputs

Successful validation should leave an experiment directory under `runs/` containing:

```text
preflight.json
experiment_metadata.json
resolved_config.json
matrix.json
matrix-summary.json
orchestrator.log
status.json
runs/<run_id>/
results/results.csv
results/results.sqlite
results/aggregate.json
report/report.html
report/report.pdf
```

Each completed or partial run directory should preserve:

```text
metadata.json
state.json
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
```

Missing or failed evidence should remain visible as partial run evidence. Validation should not delete failed runs or hide them from reports.

## Validation Flow

### 1. Static Test Gate

Run the repository tests first:

```powershell
python -m pytest
```

This catches schema, matrix, artifact, usage parsing, scoring, orchestration, and report regressions before launching measured Codex runs.

Expected result:

- Unit tests pass.
- No protected top-level source-of-truth documents were edited accidentally.
- The experiment config still expands to 45 runs.
- The pilot selector still chooses `C0_r01` and `C1_proposal_r01`.

### 2. Dry-Run Gate

Run the pilot in dry-run mode:

```powershell
.\scripts\run_pilot.ps1 -DryRun
```

This validates config expansion, preflight checks, experiment metadata writing, matrix materialization, and prompt/config rendering without launching measured Codex jobs.

Inspect:

```text
preflight.json
experiment_metadata.json
resolved_config.json
matrix.json
matrix-summary.json
```

Expected result:

- `preflight.json.status` is `passed`, or only contains understood non-blocking warnings when Codex is intentionally unavailable for dry run.
- `matrix.json` contains the two pilot runs.
- Rendered prompt and Codex config paths are valid for sample runs.

### 3. Codex Invocation Gate

Confirm Codex is available through either the default `codex` command or `CODEX_BIN`:

```powershell
$env:CODEX_BIN = "path\to\codex"
.\scripts\run_pilot.ps1 -DryRun
```

Expected result:

- Preflight resolves the executable.
- `codex --version` succeeds.
- Implementation commands use `codex exec --json`.
- Implementation commands use `--sandbox workspace-write`.
- Judge commands use the configured read-only sandbox.
- Commands include the configured model, reasoning level, `agents.max_depth`, and `agents.max_threads`.

### 4. Pilot End-To-End Gate

Run the real pilot:

```powershell
.\scripts\run_pilot.ps1
```

Expected result:

- The pilot completes without manual orchestration.
- Each run records state transitions through preparation, rendering, implementation, diff capture, public tests, hidden tests, judging, usage parsing, and scoring.
- Failed implementation or judge attempts are preserved as evidence rather than erased.
- The pilot generates results and reports.

Important files to inspect:

```text
status.json
orchestrator.log
runs/C0_r01/state.json
runs/C1_proposal_r01/state.json
runs/C0_r01/score.json
runs/C1_proposal_r01/score.json
results/aggregate.json
report/report.html
report/report.pdf
```

### 5. Hidden-Test Isolation Gate

For each pilot worktree, confirm hidden cases are absent:

```powershell
Get-ChildItem -Recurse runs\<experiment>\runs\<run_id>\worktree | Select-String -Pattern "hidden_tests|expected_output|raw_events"
```

Also inspect hidden artifacts:

```text
hidden-results.json
hidden-runner.log
```

Expected result:

- Hidden test case payloads are not copied into run worktrees.
- `hidden-results.json` contains summaries, categories, and case identifiers only.
- Hidden artifacts do not expose private keys such as `input`, `expected`, `raw_event`, `raw_events`, or `expected_output`.
- Hidden-test failures remain measurable without revealing hidden answers.

### 6. Incomplete-Solution Sensitivity Gate

Validate that the frozen starter project does not receive a perfect score before implementation. This can be checked through a pilot run where the measured agent leaves the solution incomplete, or by running public and hidden tests against a fresh copied template.

Expected result:

- Public tests are visible but incomplete.
- Hidden tests catch behavior not covered by public tests.
- A deliberately incomplete implementation receives partial or failing component scores.
- `score.json.status` is `partial` or `failed`, not falsely `passed`.

This protects the benchmark from a hollow success condition where every topology appears correct.

### 7. Usage Parsing Gate

Inspect each pilot run's `usage.json`.

Expected result:

- `usage.json` has `schema_version`.
- Implementation and judge totals are present.
- `implementation_tokens`, `judge_tokens`, and `judge_inclusive_tokens` are non-negative.
- `gpt55_implementation_tokens` is populated when attribution is possible.
- Mixed or unattributed JSONL is marked with an explicit `attribution_method` and warnings.
- The report surfaces attribution warnings instead of hiding them.

If Codex JSONL format changes, update the parser and tests before accepting the run.

### 8. Judge JSON Gate

Inspect each pilot run's `judge.json`.

Expected result:

- The judge final response parses as strict JSON.
- The parsed value contains numeric scoring fields accepted by scoring.
- Failed or malformed judge output lowers the judge component and records warnings.
- Judge evidence is read-only and does not mutate the implementation worktree.

### 9. Report Output Gate

Confirm these files exist and validate:

```text
results/results.csv
results/results.sqlite
results/aggregate.json
report/report.html
report/report.pdf
```

Expected result:

- CSV includes one row per selected run.
- SQLite includes equivalent result rows.
- Aggregate JSON includes rankings by `quality_per_gpt55_impl_token`.
- HTML includes methods, benchmark task, experiment matrix, results, direct/proposal comparison, C4 analysis, token attribution notes, limitations, and appendix.
- PDF is readable and generated from the HTML report.
- Failed, partial, or missing-score runs remain visible in appendices.

### 10. Resume Gate

Resume the completed pilot:

```powershell
.\scripts\run_pilot.ps1 -Resume <experiment-directory-name>
```

Expected result:

- Completed phases are skipped when their required artifacts are present and valid.
- Resume rejects config drift.
- Resume rejects matrix drift.
- Resume validates existing run metadata against the selected run record.
- `-RerunFailed` archives failed phase artifacts before rerunning failed work.

The resume gate should prove that long full experiments can recover from interruption without silently mixing incompatible configurations or losing evidence.

### 11. Full-Run Acceptance Gate

After the pilot passes, run:

```powershell
.\scripts\run_experiment.ps1 -Jobs 3
```

Expected result:

- The full 45-run experiment launches from config without manual run selection.
- Implementation jobs use the requested parallelism.
- Judge jobs use configured judge parallelism.
- All raw artifacts are preserved per run.
- Results rank cells and mode variants by quality per GPT-5.5 implementation token.
- Hidden-test isolation checks remain valid for all run worktrees.
- HTML and PDF reports are complete enough to inspect or reproduce the experiment.

## Acceptance Criteria

Stage 11 is accepted when:

- `python -m pytest` passes.
- `.\scripts\run_pilot.ps1` completes end to end.
- Hidden tests are not present in implementation workspaces.
- Hidden output artifacts do not leak hidden inputs or expected outputs.
- Incomplete solutions score below perfect.
- Codex JSONL usage is parsed into valid `usage.json` files.
- Judge output is parsed into valid `judge.json` files or clearly scored as malformed evidence.
- `results.csv`, `results.sqlite`, `aggregate.json`, `report.html`, and `report.pdf` are generated.
- Resume skips completed artifacts and rejects drift.
- `.\scripts\run_experiment.ps1 -Jobs 3` can run the complete 45-run workflow.
- Future cells can be added by editing experiment config rather than orchestration code.

## Failure Handling

Validation failures should be fixed at the responsible layer:

- Config or matrix failures belong in `harness/matrix.py` or `configs/initial_experiment.yaml`.
- Prompt or Codex config rendering failures belong in `harness/prompt_rendering.py`, `prompts/`, or `codex_templates/`.
- Codex command failures belong in `harness/codex_runner.py` or environment setup.
- Artifact preservation and resume failures belong in `harness/orchestrator.py` or `harness/artifacts.py`.
- Hidden privacy failures belong in `harness/hidden_runner.py` or `harness/artifacts.py`.
- Usage parsing failures belong in `harness/jsonl_usage.py`.
- Scoring failures belong in `harness/scoring.py`.
- Report failures belong in `harness/report_data.py` or `scripts/render_report_pdf.mjs`.

Failed measured runs should remain in the experiment directory unless the user explicitly asks to delete generated output.

## Done When

Stage 11 is done when the pilot and full workflows can be run from PowerShell using the expected scripts, the generated artifacts are sufficient to audit every run, and the final report gives a non-academic reader a clear account of methods, results, limitations, and per-run evidence.
