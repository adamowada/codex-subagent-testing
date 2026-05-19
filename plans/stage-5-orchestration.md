# Stage 5 Plan: Orchestration

## Goal

Create the user-facing experiment commands and the Python orchestration spine that turns the Stage 1-4 assets into a reproducible benchmark run.

Stage 5 is complete when a user can run:

```powershell
.\scripts\run_experiment.ps1 -Jobs 3
```

and the harness can validate the environment, expand the configured matrix, create isolated run workspaces, render per-run prompts and Codex config, schedule implementation runs, preserve raw evidence, run tests and judges, compute result artifacts, and generate experiment-level outputs.

Create a smaller smoke-test entrypoint:

```powershell
.\scripts\run_pilot.ps1
```

The pilot should run one C0 repeat and one C1 proposal repeat end to end before the full 45-run experiment is attempted.

## Non-Goals

- Do not edit locked top-level source-of-truth documents.
- Do not change the benchmark task or hidden case content.
- Do not copy hidden tests, hidden expected outputs, or private case payloads into prompts, starter projects, run worktrees, logs, reports, or judge prompts.
- Do not hard-code C0-C4 experiment behavior in the orchestrator when it can come from `configs/initial_experiment.yaml`.
- Do not require manual per-run orchestration steps.
- Do not silently overwrite completed experiment directories.
- Do not discard failed or partial runs; failures are measured outcomes.
- Do not invoke nested Codex from inside measured workspaces.

## Target Directory Layout

Stage 5 should add or complete:

```text
scripts/
  run_experiment.ps1
  run_pilot.ps1

harness/
  orchestrator.py
  preflight.py
  codex_runner.py
  jsonl_usage.py
  scoring.py
  report_data.py
```

Some helper modules may be skeletal if their deeper behavior is owned by later stages, but the orchestrator should call through stable interfaces rather than growing into one large script.

## Inputs From Earlier Stages

Stage 5 consumes:

- `benchmark_template/` as the frozen starter implementation workspace.
- `hidden_tests/cases/manifest.json` and hidden case files through `harness.hidden_runner`.
- `configs/initial_experiment.yaml` as the source of experiment topology, repeats, prompts, models, reasoning levels, Spark modes, timeouts, and default parallelism.
- `configs/scoring.yaml` through the resolved scoring config exposed by `harness.matrix`.
- `prompts/` and `codex_templates/` through `harness.prompt_rendering`.
- `harness.matrix.load_experiment_config`, `validate_experiment_config`, `expand_experiment_matrix`, and `summarize_matrix`.
- `harness.prompt_rendering.render_implementation_prompt`, `render_judge_prompt`, and `render_codex_config`.

The orchestrator should treat these modules as source-of-truth helpers. If orchestration needs information that is already available in a run record, use the run record instead of re-reading config manually.

## Command-Line Contract

### `scripts/run_experiment.ps1`

Primary user command:

```powershell
.\scripts\run_experiment.ps1 -Jobs 3
```

Recommended parameters:

- `-Config configs/initial_experiment.yaml`
- `-Jobs 3`
- `-JudgeJobs 2`
- `-RunsRoot runs`
- `-ExperimentName <optional-name>`
- `-Resume <experiment-directory>`
- `-RerunFailed`
- `-NoReport`
- `-DryRun`

PowerShell should remain thin. It should locate the repo root, select Python, pass arguments to `harness.orchestrator`, and exit with the Python process exit code.

### `scripts/run_pilot.ps1`

Smoke-test command:

```powershell
.\scripts\run_pilot.ps1
```

Recommended parameters:

- `-Jobs 1`
- `-JudgeJobs 1`
- `-Config configs/initial_experiment.yaml`
- `-RunsRoot runs`
- `-Resume <pilot-directory>`
- `-RerunFailed`
- `-NoReport`

The pilot should filter the expanded matrix to:

- One C0 run.
- One C1 proposal run.

The filter should be implemented in orchestrator options, not by creating a separate hard-coded config file unless a future stage deliberately adds pilot configs.

## Orchestrator Responsibilities

The orchestrator should perform these phases in order:

1. Parse CLI arguments and normalize repository paths.
2. Run preflight checks.
3. Load and validate experiment config.
4. Expand the experiment matrix.
5. Apply pilot or run-id filters, if any.
6. Create or resume a timestamped experiment directory under `runs/`.
7. Write experiment-level metadata and rendered config snapshots.
8. Prepare every run directory and copied worktree.
9. Initialize a git baseline in every worktree.
10. Render per-run implementation prompts, judge prompts, and Codex config files.
11. Schedule implementation jobs with bounded parallelism.
12. Capture implementation JSONL, stderr, exit code, final response, wall time, and diff artifacts.
13. Run public TypeScript tests, typecheck, and public Python tests.
14. Run hidden tests from outside the worktree.
15. Run blind judge jobs with bounded parallelism.
16. Parse JSONL usage.
17. Compute per-run scores.
18. Write CSV, SQLite, aggregate JSON, HTML, and PDF outputs.
19. Write a final experiment status summary.

Each phase should be restartable. A resumed run should validate existing artifacts before skipping work.

## Preflight Checks

Preflight should fail early with actionable messages.

Required checks:

- Repository root contains the expected directories and files.
- `benchmark_template/` exists and has TypeScript and Python implementation surfaces.
- `configs/initial_experiment.yaml` loads, validates, and expands to the expected run count.
- Prompt and Codex config rendering succeeds for at least the first run and one Spark run.
- Hidden test manifest loads and hashes match.
- `runs/` is writable or can be created.
- Python can import required harness modules.
- Node and npm are available for TypeScript public and hidden checks.
- Public benchmark dependencies can be installed or are already available where needed.
- Codex is callable through `CODEX_BIN` or `codex`.
- `codex exec --json` supports the command shape needed by implementation and judge runs.
- The configured models and reasoning levels are present in the expanded run records.

If `codex` is unavailable, the message should mention:

```powershell
$env:CODEX_BIN = "path\to\working\codex"
```

Preflight should not run measured implementation jobs. A dry-run mode may render artifacts and print the planned run table without invoking Codex.

## Experiment Directory Contract

Create new full experiment directories under `runs/`:

```text
runs/
  20260519-121530-initial_subagent_topology/
```

Recommended experiment-level files:

```text
experiment-metadata.json
config.resolved.json
matrix.json
matrix-summary.json
preflight.json
orchestrator.log
status.json
results/
  results.csv
  results.sqlite
  aggregate.json
report/
  report.html
  report.pdf
runs/
  C0_r01/
  C1_proposal_r01/
```

The timestamp format should sort lexicographically. The experiment ID should come from config unless the user supplies an additional safe name.

Never create a new experiment directory with the same path as an existing completed directory. Resume must require an explicit path.

## Run Directory Contract

Each implementation run directory should eventually contain:

```text
metadata.json
state.json
rendered_prompt.md
judge_prompt.md
codex_config/
worktree/
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

The copied starter project should live under `worktree/`. Hidden tests must remain outside `worktree/`.

`metadata.json` should include:

- Run ID.
- Cell ID and cell name.
- Repeat index.
- Topology.
- Spark mode.
- Root model and reasoning.
- Sublead model, reasoning, and count when present.
- Leaf model, count, and per-role reasoning when present.
- Agent depth and thread settings.
- Timeout settings.
- Paths to rendered prompt and config.
- Baseline git commit SHA.
- Orchestrator version or git commit of the harness repo when available.

`state.json` should be machine-readable and small. It should record phase completion, artifact validation status, and any failure reason.

## Workspace Preparation

For each run:

1. Copy `benchmark_template/` into `run_dir/worktree/`.
2. Exclude generated or local-only files such as `node_modules/`, `dist/`, coverage, caches, and Python bytecode if present.
3. Initialize a git repository inside `worktree/`.
4. Configure local git identity if needed.
5. Add all baseline starter files.
6. Commit the baseline.
7. Record the baseline commit SHA in metadata.

The baseline commit enables reliable diff extraction after the implementation run:

```text
git diff --patch <baseline> HEAD
git diff --numstat <baseline> HEAD
```

If the implementation changes files without committing, diff against the working tree as well as `HEAD`. The benchmark should measure final file contents, not only committed changes.

## Prompt And Config Rendering

For each run, call `harness.prompt_rendering` and write:

- `rendered_prompt.md`
- `judge_prompt.md`
- `codex_config/config.toml`
- `codex_config/agents/*.toml`

Rendering should be deterministic. Re-rendering during resume should either produce byte-identical output or fail loudly with a clear drift message unless the user explicitly starts a new experiment.

The rendered implementation prompt must preserve the nested Codex and external AI prohibition. The Codex config should match the run record's model, reasoning, sandbox, depth, and thread settings.

## Codex Execution Contract

Implementation command shape:

```text
codex exec --json
  --cd <run_worktree>
  --sandbox workspace-write
  --ask-for-approval never
  --model <root_model>
  -c model_reasoning_effort=<root_reasoning>
  -c agents.max_threads=<agents.max_threads>
  -c agents.max_depth=<agents.max_depth>
  <rendered_prompt>
```

Judge command shape:

```text
codex exec --json
  --cd <run_worktree>
  --sandbox read-only
  --ask-for-approval never
  --model gpt-5.5
  -c model_reasoning_effort=xhigh
  <judge_prompt>
```

Use `CODEX_BIN` if set. Otherwise use `codex`.

The runner should capture:

- JSONL stdout to `events.jsonl` or `judge.events.jsonl`.
- Stderr to `stderr.log` or `judge.stderr.log`.
- Exit code.
- Start time, finish time, elapsed seconds.
- Timeout status.

Timeouts come from the run record. A timeout should produce a partial run artifact set, not delete the run.

## Parallel Scheduling

Implementation jobs and judge jobs should use separate bounded parallelism settings:

- Implementation jobs default to config `parallelism.implementation_jobs`, overridden by `-Jobs`.
- Judge jobs default to config `parallelism.judge_jobs`, overridden by `-JudgeJobs`.

Scheduling should be deterministic in submission order, even if completion order varies. Result aggregation should sort by matrix order or run ID, not by completion time.

Avoid sharing mutable run state across workers except through per-run artifact files and an experiment-level status update guarded by ordinary file writes.

## Public Test Execution

After implementation, run visible checks inside `worktree/`:

```powershell
npm run typecheck
npm run test:public
python -m pytest -q tests_public_py
```

Each command should write a log file and structured status. Non-zero exits are normal measured outcomes and should not stop the whole experiment.

If dependency installation is required, prefer deterministic installation from `package-lock.json` with `npm ci`.

## Hidden Test Execution

Run hidden checks through `harness.hidden_runner` from outside the worktree:

```text
python -m harness.hidden_runner --worktree <run_worktree> --out <run_dir>/hidden-results.json
```

The runner should load hidden cases from the repository-level hidden case directory, verify manifest hashes, execute cases against the implementation, and write only result summaries. It must not copy private cases into the worktree.

Hidden-test failure, setup error, or timeout should be preserved in `hidden-results.json` and reflected in scoring.

## Judge Execution

The judge should be blind to the producing topology. It may inspect source, diffs, public logs, hidden-result summaries, stderr logs, timing data, and the implementation final response. It must not see private hidden case payloads.

Judge output should be parsed as strict JSON when possible and preserved raw when malformed. Malformed judge JSON should score as a judge failure but should not erase the raw evidence.

## Usage Parsing

Parse `turn.completed.usage` events from implementation and judge JSONL.

`usage.json` should include:

- Input tokens.
- Cached input tokens.
- Output tokens.
- Reasoning output tokens.
- Total implementation tokens.
- Total judge tokens.
- Implementation-only GPT-5.5 tokens when observable.
- Judge-inclusive GPT-5.5 tokens.
- Spark tokens when observable.
- Attribution method.
- Warnings for missing or ambiguous attribution.

If mixed-agent JSONL lacks per-model attribution, preserve total usage and mark model-level attribution as best effort.

## Scoring Contract

Per-run `score.json` should combine:

- Public test score.
- Hidden test score.
- Judge score.
- Typecheck score.
- Parity score or minimality score, depending on the scoring config used by the implementation.
- Token-efficiency metrics.
- Wall-clock-efficiency metrics.
- Failure indicators.
- Code quantity and diff statistics.

The scoring implementation should use resolved config weights rather than hard-coded weights. Missing outputs should score as zero for that component, while the run remains visible in aggregate outputs.

## Experiment-Level Outputs

Write:

```text
results/results.csv
results/results.sqlite
results/aggregate.json
report/report.html
report/report.pdf
```

CSV and SQLite should contain one row per implementation run, including failed and partial runs.

Aggregate JSON should include:

- Counts by cell, topology, Spark mode, and status.
- Mean, median, and standard deviation for key scores.
- Token-efficiency summaries.
- Failure rates.
- Direct versus proposal comparisons.
- C4 stress-test summaries.

The report generator can be implemented in later report modules, but the orchestrator owns calling it and preserving its outputs.

## Resume Model

Every phase should be resumable based on artifact validation.

Recommended phase names:

```text
prepared
baseline_committed
rendered
implemented
diff_captured
public_tested
hidden_tested
judged
usage_parsed
scored
recorded
reported
```

Skip a phase only when:

- The expected artifact exists.
- The artifact parses or validates.
- The phase status in `state.json` agrees with the artifact.
- The run metadata matches the current resolved config and run record.

Do not rerun failed implementation or judge phases unless `-RerunFailed` is supplied. Rerun should preserve old artifacts by moving them to an archive subdirectory or by writing attempt-numbered artifacts.

Resume should detect these cases clearly:

- Completed experiment: refuse to overwrite unless resuming only to regenerate missing aggregate/report outputs.
- Partial experiment: continue missing phases.
- Config drift: fail with a message explaining that a new experiment directory should be created.
- Corrupt artifact: fail or rerun only with an explicit flag.

## Status And Logging

The orchestrator should produce concise console progress and detailed file logs.

Console output should show:

- Experiment directory.
- Matrix summary.
- Preflight result.
- Number of scheduled runs.
- Current run phase updates.
- Failure summaries.
- Final report paths.

`orchestrator.log` should include command lines, timings, return codes, and artifact paths. Do not log hidden case payloads.

`status.json` should be enough for a future command to display progress without parsing every log.

## Pilot Behavior

The pilot should exercise the full pipeline with minimal cost:

- One C0 solo run.
- One C1 proposal run.
- Implementation execution.
- Public tests.
- Hidden tests.
- Judge execution.
- Usage parsing.
- Scoring.
- CSV, SQLite, HTML, and PDF generation when report dependencies are available.

The pilot should be treated as a real experiment directory under `runs/`, likely with a `pilot` marker in metadata and directory name.

Pilot acceptance checks:

- Codex invocation works.
- Hidden tests remain outside implementation workspaces.
- Public and hidden test logs are written.
- JSONL usage is parsed or a clear warning is recorded.
- Judge JSON is parsed or raw malformed output is preserved.
- Resume skips completed phases.
- Aggregate outputs include exactly two implementation rows.

## Failure Handling

The orchestrator should distinguish:

- Implementation failure: the measured agent failed, timed out, produced bad code, or returned malformed final JSON.
- Test failure: the implementation completed but public or hidden tests failed.
- Judge failure: judging failed or returned malformed JSON.
- Infrastructure failure: Codex executable missing, hidden manifest corrupt, npm unavailable, workspace copy failed, or report renderer unavailable.

Infrastructure failures before measured runs should stop the experiment. Per-run implementation, test, hidden-test, and judge failures should be recorded and the scheduler should continue with other runs.

## Suggested Implementation Steps

1. Add thin PowerShell wrappers.
2. Add `harness.preflight` with environment, config, prompt-rendering, and hidden-manifest checks.
3. Add `harness.orchestrator` CLI with dry-run support.
4. Implement experiment directory creation and resume selection.
5. Implement per-run workspace preparation and baseline git commit.
6. Write per-run metadata, prompt, judge prompt, and Codex config artifacts.
7. Add `harness.codex_runner` for subprocess execution, timeout handling, JSONL/stderr capture, and wall-time metadata.
8. Add public test command runners.
9. Integrate `harness.hidden_runner`.
10. Add judge execution.
11. Add JSONL usage parsing.
12. Add scoring and result table generation.
13. Add report generation hook.
14. Implement pilot filtering.
15. Add resume validation and rerun-failed behavior.
16. Add tests for dry-run, matrix filtering, artifact paths, resume decisions, and command construction.

## Test Plan

Add tests that do not require real Codex execution:

- `run_experiment.ps1` forwards arguments to the Python orchestrator.
- Config expansion produces 45 planned runs in orchestrator dry-run mode.
- Pilot filtering selects exactly one C0 run and one C1 proposal run.
- Experiment directory names are filesystem-safe and sortable.
- Run directories are stable and derived from run IDs.
- Workspace preparation excludes generated dependency directories.
- Baseline git commit is created in a temporary copied workspace.
- Prompt and config artifacts are written for a sample solo, flat Spark, and C4 run.
- Resume logic skips valid completed phases.
- Resume logic refuses config drift.
- Rerun-failed behavior does not overwrite old artifacts silently.
- Codex command construction uses `CODEX_BIN` when set.
- Implementation and judge command construction includes model, reasoning, sandbox, depth, and thread settings.
- Public test runners record non-zero exits without raising experiment-fatal errors.
- Hidden runner is invoked with hidden cases outside the worktree.
- Malformed final response JSON is preserved and marked parse-failed.

Add integration tests or manual validation for:

- `.\scripts\run_pilot.ps1`
- `.\scripts\run_experiment.ps1 -Jobs 3 -DryRun`
- Resume of an interrupted pilot.
- Report regeneration from existing scored pilot results.

## Risks And Mitigations

Risk: The orchestrator grows into a monolith.

Mitigation: Keep config loading, prompt rendering, Codex subprocess handling, usage parsing, scoring, and report data in separate modules with small typed data contracts.

Risk: Resume skips stale or drifted artifacts.

Mitigation: Store resolved config snapshots and run metadata, then validate them before skipping phases.

Risk: Hidden tests leak into workspaces or prompts.

Mitigation: Run hidden cases only from repository-level paths, never copy case files into `worktree/`, and avoid logging private payloads.

Risk: A single failed run stops the full experiment.

Mitigation: Treat per-run failures as outcomes. Stop only for preflight or shared infrastructure failures that invalidate the experiment.

Risk: Mixed-agent JSONL lacks per-model token attribution.

Mitigation: Preserve total usage, record best-effort attribution method, and surface attribution limitations in outputs.

Risk: Report generation dependencies are missing on the first pilot.

Mitigation: Make report generation failure visible and resumable. Preserve scored CSV/SQLite/aggregate outputs even if PDF generation fails.

## Done When

- `scripts/run_experiment.ps1` exists and launches the Python orchestrator.
- `scripts/run_pilot.ps1` exists and runs a minimal C0/C1 proposal smoke test.
- The orchestrator can load config, validate it, expand the matrix, and write a planned run table.
- A new timestamped experiment directory is created without overwriting completed runs.
- Per-run workspaces are copied from `benchmark_template/`, initialized as git repositories, and baseline commits are recorded.
- Per-run prompts and Codex config artifacts are rendered and preserved.
- Implementation and judge commands are constructed from run records and use `CODEX_BIN` when present.
- Public tests and hidden tests run after implementation and write artifacts.
- Failed and partial runs remain visible in results.
- Resume skips completed valid phases and requires an explicit flag to rerun failed phases.
- Pilot mode verifies the end-to-end pipeline before the full experiment.
- Full experiment mode can schedule all 45 configured implementation runs with bounded parallelism.
