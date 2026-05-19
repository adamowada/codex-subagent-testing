# Stage 7 Plan: Artifacts

## Goal

Define and enforce the artifact contract for every measured run and for the experiment as a whole.

Stage 7 is complete when every run directory contains enough durable evidence to:

- Reconstruct what was measured.
- Inspect what Codex did.
- Verify what changed from the frozen starter project.
- Understand public, hidden, and judge outcomes.
- Parse usage and compute scores in later stages.
- Resume or rerun failed phases without silently overwriting evidence.
- Generate stable experiment-level CSV, SQLite, aggregate JSON, HTML, and PDF outputs.

This stage is the evidence layer of the harness. Stage 5 orchestrates phases, Stage 6 captures Codex subprocess evidence, and later stages parse usage, score, and report. Stage 7 makes those pieces concrete by specifying stable paths, minimum schemas, validation rules, privacy limits, and failure-preservation behavior.

## Non-Goals

- Do not edit locked top-level source-of-truth documents.
- Do not change benchmark task behavior, public tests, hidden case payloads, hidden expected outputs, scoring weights, or experiment topology.
- Do not copy `hidden_tests/` into measured worktrees.
- Do not include full hidden inputs or expected outputs in prompts, logs, judge prompts, run artifacts, reports, CSV rows, SQLite rows, or aggregate JSON.
- Do not delete failed, timed-out, malformed, or partial run evidence.
- Do not rewrite generated artifacts by hand. Fix generators, harness code, or templates instead.
- Do not make report styling the focus of this stage. The reports must exist and be readable; deeper report polish belongs to the reporting stage.

## Inputs

Stage 7 consumes artifacts and data produced by earlier stages:

- Expanded run records from `harness.matrix`.
- Per-run worktrees copied from `benchmark_template/`.
- Per-run git baseline commits.
- Rendered implementation prompts, judge prompts, and Codex configs from `harness.prompt_rendering`.
- Implementation and judge JSONL/stdout, stderr, wall-time, timeout, and final-response evidence from Stage 6.
- Public TypeScript, typecheck, and public Python test logs.
- Hidden result summaries from `harness.hidden_runner`.
- Diff output captured from each run worktree against its baseline commit.
- Usage summaries and scores when those later phases have executed.

The run record remains the authority for topology, model, reasoning, timeout, Spark mode, repeat index, scoring weights, and run identity. Artifact metadata should reference the resolved run record rather than reconstructing configuration from path names.

## Run Directory Layout

Every measured run should live under:

```text
runs/<experiment_id>/runs/<run_id>/
```

Each run directory should contain:

```text
metadata.json
state.json
rendered_prompt.md
judge_prompt.md
codex_config/
events.jsonl
stderr.log
final_response.json
wall_time.json
diff.patch
diff-numstat.txt
npm-ci.log
npm-ci.meta.json
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
worktree/
```

The shorter top-level contract in `PLANS.md` names the core files. This expanded layout includes implementation details already used by the harness, especially `.meta.json` files for ordinary subprocesses, `judge_prompt.md`, `state.json`, and optional dependency-install logs.

## Core Artifact Groups

### Identity And Configuration

`metadata.json` should contain:

- `schema_version`.
- `run_id`.
- `cell_id`.
- `cell_name`.
- `repeat_index`.
- `topology`.
- `spark_mode`.
- Resolved root, sublead, leaf, judge, timeout, and agent-thread settings.
- Full expanded run record.
- Absolute or experiment-relative `run_dir` and `worktree` paths.
- Baseline commit SHA.
- Creation timestamp.

`rendered_prompt.md` preserves the exact implementation prompt passed to `codex exec --json`.

`judge_prompt.md` preserves the exact judge prompt passed to the blind judge.

`codex_config/` preserves rendered Codex config and agent prompt files. It is an audit artifact even when command-line overrides are what actually control execution.

`state.json` records resumable phase status. It should stay small and machine-readable.

### Implementation Codex Evidence

Implementation execution writes:

```text
events.jsonl
stderr.log
final_response.json
wall_time.json
```

`events.jsonl` is the raw Codex JSONL stream. It must be preserved even if malformed lines exist.

`stderr.log` captures subprocess stderr, spawn failures, timeout markers, and process errors.

`final_response.json` stores structured extraction of the agent's final JSON response. If extraction fails, the artifact should still exist and explain the parse failure.

`wall_time.json` stores command display, cwd, start time, finish time, elapsed seconds, return code, timeout status, and stdout/stderr paths.

Timeouts and nonzero exits should mark the phase failed or partial, but they must not delete these artifacts.

### Diff Evidence

Diff capture writes:

```text
diff.patch
diff-numstat.txt
```

`diff.patch` should be a full git patch against the per-run baseline commit.

`diff-numstat.txt` should be parseable by scoring/reporting for changed-file, insertion, deletion, and binary-file counts.

An empty diff is still evidence and should produce valid empty files rather than missing files.

### Public Test Evidence

Public validation writes:

```text
npm-ci.log
npm-ci.meta.json
typecheck.log
typecheck.meta.json
public_ts.log
public_ts.meta.json
public_py.log
public_py.meta.json
```

`npm-ci.*` is required only when dependency installation is performed for a run.

Each `.meta.json` should include the same process metadata shape used for wall-time/process results: command, cwd, timestamps, elapsed seconds, return code, timeout status, and log path.

Logs should preserve enough stdout/stderr for debugging while avoiding hidden-test payloads.

### Hidden Test Evidence

Hidden validation writes:

```text
hidden-runner.log
hidden-runner.meta.json
hidden-results.json
```

`hidden-results.json` must contain privacy-safe summaries only:

- Opaque case IDs.
- Category names.
- Language/surface when useful.
- Status.
- Points earned.
- Points possible.
- Short failure reason codes or brief generic messages.
- Aggregate category and total scores.

It must not contain full hidden inputs, full expected outputs, private fixtures, or oracle internals.

`hidden-runner.log` should be checked for leakage. If the hidden runner emits sensitive payloads, fix the runner rather than filtering after the fact where possible.

### Judge Evidence

Judge execution writes:

```text
judge.events.jsonl
judge.stderr.log
judge.wall_time.json
judge.json
```

The judge run is read-only against the implementation worktree and should not know the topology that produced the implementation except through ordinary artifacts available to scoring.

`judge.json` should store parsed judge output. If parsing fails, it should still explain the failure in a structured way and the judge phase should be marked failed or partial.

### Usage And Score Evidence

Usage parsing writes:

```text
usage.json
```

It should include:

- Implementation token totals.
- Judge token totals.
- Judge-inclusive totals.
- GPT-5.5 implementation-only tokens when observable.
- GPT-5.5 judge-inclusive tokens.
- Spark implementation tokens when observable.
- Per-model totals when exposed by JSONL.
- Attribution method.
- Warnings when model attribution is best effort.

Scoring writes:

```text
score.json
```

It should include:

- Component scores.
- Scoring weights.
- Final quality score.
- Efficiency metrics.
- Diff stats.
- Wall-time stats.
- Run status.

## Experiment-Level Layout

Every experiment directory should contain:

```text
experiment_metadata.json
resolved_config.json
matrix.json
preflight.json
orchestrator.log
status.json
runs/
results/
report/
```

The required experiment-level outputs are:

```text
results/results.csv
results/results.sqlite
results/aggregate.json
report/report.html
report/report.pdf
```

`results.csv` should be easy to inspect and import into spreadsheet tools.

`results.sqlite` should preserve the same row set for reproducible querying.

`aggregate.json` should include summary buckets by cell and Spark mode, failure rates, and best-run summaries.

`report.html` and `report.pdf` should be readable by a non-academic audience while retaining the academic-paper structure required by the top-level plan.

## Artifact Stability

Artifact paths are part of the public contract of the harness. Reports, appendices, resume logic, tests, and manual inspection all depend on stable names.

Prefer adding new artifacts over renaming existing ones. If a rename is unavoidable, provide a compatibility read path during the transition and update tests in the same change.

Do not encode mutable timestamps into per-run artifact file names. Use the run directory or rerun archive directories to separate attempts.

## Resume And Rerun Behavior

Resume should skip a phase only when:

- The expected artifact exists.
- The artifact parses or validates.
- `state.json` marks the phase completed.
- The run metadata matches the current resolved run record.

Failed implementation and judge phases should not rerun unless the user supplies the explicit rerun-failed option.

When rerunning a failed phase, preserve previous artifacts before writing new ones. The preferred layout is:

```text
runs/<experiment_id>/runs/<run_id>/reruns/<phase>-<attempt>/
```

The new phase state should record the archive path in `state.json`.

Completed experiment directories must not be silently overwritten. The harness may resume to regenerate missing aggregate/report outputs when raw run evidence is complete and validated.

## Validation Rules

Stage 7 should add or strengthen validation for:

- Required run artifacts exist after each completed phase.
- JSON artifacts parse and have the expected `schema_version` where applicable.
- JSONL artifacts can be scanned line by line without aborting on a malformed line.
- Process metadata includes command display, cwd, timestamps, elapsed seconds, timeout status, return code, and output path.
- Diff artifacts exist even when no files changed.
- Hidden result artifacts do not contain known private keys such as full input payloads or expected output fields.
- Report rows reference valid run directories.
- Experiment-level outputs are regenerated from per-run artifacts, not from in-memory-only state.

Validation should be strict enough to prevent false resume success, but tolerant enough to preserve partial evidence from failed runs.

## Implementation Tasks

1. Document the run artifact contract in tests and helper constants.
2. Ensure `metadata.json` and `state.json` are written before measured execution begins.
3. Ensure prompt and config rendering always writes `rendered_prompt.md`, `judge_prompt.md`, and `codex_config/`.
4. Ensure implementation subprocesses always write `events.jsonl`, `stderr.log`, `wall_time.json`, and `final_response.json`.
5. Ensure diff capture always writes `diff.patch` and `diff-numstat.txt`.
6. Ensure public test commands write both logs and `.meta.json` process metadata.
7. Ensure hidden test execution writes `hidden-results.json`, `hidden-runner.log`, and `hidden-runner.meta.json`.
8. Ensure judge subprocesses always write `judge.events.jsonl`, `judge.stderr.log`, `judge.wall_time.json`, and `judge.json`.
9. Ensure usage parsing writes `usage.json` even when model attribution is incomplete.
10. Ensure scoring writes `score.json` for passed, partial, and failed runs.
11. Ensure experiment outputs write CSV, SQLite, aggregate JSON, HTML, and PDF artifacts.
12. Add artifact validation helpers for resume decisions.
13. Add rerun archive behavior for failed phases.
14. Add leakage checks for hidden-result artifacts and logs.
15. Add tests that compare actual artifact paths to this contract.

## Test Plan

Unit tests should cover:

- Metadata schema and required fields.
- State phase updates and resume decisions.
- Missing artifact prevents completed-phase skip.
- Corrupt JSON artifact prevents completed-phase skip.
- Failed phase is skipped without rerun-failed and archived with rerun-failed.
- Process metadata is written for implementation, judge, and ordinary logged commands.
- Diff artifacts exist for both changed and unchanged worktrees.
- Hidden result output does not expose full hidden inputs or expected outputs.
- Usage summary exists and records best-effort attribution warnings when needed.
- Score output includes component scores, efficiency metrics, diff stats, wall time, and status.
- Result CSV, SQLite, aggregate JSON, HTML, and PDF are written from run artifacts.

Integration tests can use a fake Codex executable that writes synthetic JSONL, stderr, and final JSON, then exits with controlled return codes. This makes artifact completeness testable without spending model tokens.

## Acceptance Checklist

- Every run produces the expected metadata, prompt, config, log, diff, usage, test, judge, and score artifacts.
- Every artifact path is stable and documented by tests.
- Failed runs preserve partial evidence.
- Timed-out runs preserve partial evidence and timeout markers.
- Resume does not skip missing, corrupt, stale, or config-drifted artifacts.
- Rerun-failed archives previous failed-phase artifacts before replacing them.
- Hidden-result artifacts and logs do not leak private hidden cases.
- Experiment-level CSV, SQLite, aggregate JSON, HTML, and PDF outputs are written.
- Report rows contain stable run artifact paths.

## Risks And Mitigations

Risk: Resume skips stale or drifted artifacts.
Mitigation: Validate metadata against the resolved run record before skipping phases.

Risk: Hidden tests leak through logs or result JSON.
Mitigation: Keep hidden runner summaries opaque and add explicit leakage checks for sensitive keys and payload fields.

Risk: Partial failures erase useful evidence.
Mitigation: Write artifacts as the phase runs, mark phase status separately, and archive failed attempts before rerun.

Risk: Reports depend on in-memory state rather than files.
Mitigation: Generate experiment-level outputs by reading `usage.json`, `score.json`, and run metadata from disk.

Risk: Artifact names drift as implementation evolves.
Mitigation: Centralize artifact-name constants and add tests that assert the expected file set.

Risk: JSONL shape changes across Codex versions.
Mitigation: Preserve raw JSONL, parse permissively, record attribution method and warnings, and avoid dropping total usage when per-model attribution is missing.
