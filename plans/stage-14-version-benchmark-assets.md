# Stage 14: Version Benchmark Assets

## Purpose

Stage 14 makes benchmark assets selected by experiment configuration instead of
implicitly tied to the original RuleLedger v1 files.

This stage should answer:

```text
Can the same harness run RuleLedger v1 and a future RuleLedger v2 without
mixing starter templates, hidden cases, scoring profiles, metadata, validation,
or report evidence?
```

Stage 14 is an infrastructure stage. It does not create the v2 starter task,
generate hard-mode hidden cases, or recalibrate scoring. Those happen in later
stages. Its job is to add the version-aware wiring that makes those later
assets safe to introduce.

## Scope

Stage 14 owns:

- Config-selected benchmark version.
- Config-selected starter template path.
- Config-selected hidden cases directory.
- Config-selected scoring profile path.
- Propagating benchmark asset metadata into expanded run records.
- Recording benchmark asset metadata in experiment and run artifacts.
- Passing the selected hidden cases directory into hidden test execution.
- Pointing hidden-test privacy validation at the selected hidden cases
  directory.
- Updating preflight and Stage 11 validation to use selected asset paths.
- Preserving v1 default script behavior.
- Adding tests that prove v1 and a synthetic v2 configuration remain isolated.

Stage 14 does not own:

- Creating the final v2 starter template.
- Creating the final v2 hidden test suite.
- Changing RuleLedger APIs or task semantics.
- Reweighting the scoring system beyond selecting a profile path.
- Designing cross-version ranking semantics.
- Editing locked top-level source-of-truth documents.
- Committing run outputs under `runs/`.

## Current State

The harness already has some config-driven behavior:

- `configs/initial_experiment.yaml` and
  `configs/c5_c7_solo_reasoning.yaml` select prompt templates, Codex config
  templates, cell definitions, model choices, and `scoring.path`.
- `harness.matrix.load_experiment_config` resolves `scoring.path` into the
  experiment config.
- `harness.hidden_runner` accepts `--cases-dir`.

The remaining v1 assumptions are still hard-coded:

- The orchestrator copies `benchmark_template/` for every run.
- The orchestrator invokes the hidden runner without passing `--cases-dir`,
  which leaves the hidden runner defaulting to `hidden_tests/cases`.
- Preflight checks `benchmark_template/` and `hidden_tests/cases/manifest.json`
  directly.
- Stage 11 hidden isolation indexes `hidden_tests/cases` directly.
- Experiment metadata, run metadata, matrix summaries, and reports do not yet
  identify the benchmark version or selected asset paths.

These assumptions are fine for v1, but they would make a v2 dry-run ambiguous
and could accidentally validate a v2 run against v1 hidden cases.

## Proposed Config Shape

Add a benchmark identity object and asset paths to each experiment config:

```json
{
  "schema_version": 1,
  "benchmark": {
    "version": "ruleledger_v1"
  },
  "paths": {
    "benchmark_template": "benchmark_template",
    "hidden_cases": "hidden_tests/cases",
    "prompt_templates": {
      "common": "prompts/task_common.md",
      "solo": "prompts/task_solo.md",
      "flat_spark": "prompts/task_flat_spark.md",
      "depth2_subleads": "prompts/task_depth2_subleads.md",
      "judge": "prompts/judge.md"
    },
    "codex_config_template": "codex_templates/config.toml.j2"
  },
  "scoring": {
    "path": "configs/scoring.yaml"
  }
}
```

The resolved scoring block should continue to include the scoring profile from
the referenced file:

```json
{
  "path": "configs/scoring.yaml",
  "profile": "initial_quality_v1",
  "weights": {
    "public_tests": 0.15,
    "hidden_tests": 0.50,
    "judge": 0.15,
    "typecheck": 0.15,
    "minimality": 0.05
  }
}
```

A synthetic v2 config for Stage 14 tests should use the same shape:

```json
{
  "benchmark": {
    "version": "ruleledger_v2"
  },
  "paths": {
    "benchmark_template": "tests/fixtures/stage14/ruleledger_v2_template",
    "hidden_cases": "tests/fixtures/stage14/ruleledger_v2_cases"
  },
  "scoring": {
    "path": "tests/fixtures/stage14/scoring_v2.yaml"
  }
}
```

The synthetic v2 assets can be tiny fixtures because this stage only needs to
prove path selection, metadata propagation, and privacy isolation. The final v2
benchmark assets belong to Stages 15 through 18.

## Compatibility Rules

Default script behavior must remain v1:

```powershell
.\scripts\run_experiment.ps1 -Jobs 3
.\scripts\run_pilot.ps1
```

Both commands should still default to `configs/initial_experiment.yaml`, and
that config should still expand to the original v1 45-run matrix.

The loader may support missing `benchmark.version`, `paths.benchmark_template`,
and `paths.hidden_cases` as backward-compatible v1 defaults, but the checked-in
v1 configs should be updated to include the fields explicitly. Explicit fields
make `resolved_config.json` self-describing and remove guesswork from future
reports.

## Run Record Propagation

Every expanded run record should carry benchmark asset metadata. A compact
shape is preferable so all components can copy one object:

```json
{
  "benchmark": {
    "version": "ruleledger_v1",
    "template_path": "benchmark_template",
    "hidden_cases_path": "hidden_tests/cases",
    "scoring_path": "configs/scoring.yaml",
    "scoring_profile": "initial_quality_v1"
  }
}
```

The existing top-level run fields should remain stable. If compatibility with
older report code is useful, the harness can also expose flattened aliases such
as `benchmark_version` or `scoring_profile`, but the object above should be the
primary representation.

Run metadata should include the selected benchmark object in two places:

- The embedded expanded `run` record.
- A top-level `benchmark` object in `metadata.json` for quick inspection.

This keeps resume validation strict: if a run directory was prepared for v1 and
the caller resumes with a v2 config, the metadata comparison should fail.

## Experiment Metadata

`write_experiment_metadata` should add:

```json
{
  "benchmark": {
    "version": "ruleledger_v1",
    "template_path": "benchmark_template",
    "hidden_cases_path": "hidden_tests/cases",
    "scoring_path": "configs/scoring.yaml",
    "scoring_profile": "initial_quality_v1"
  }
}
```

`resolved_config.json` should remain the full resolved config. It should include
both explicit selected paths and the resolved scoring profile.

`matrix.json` should include the benchmark object on each run. `matrix-summary`
should include enough version information for quick inspection, for example:

```json
{
  "benchmark_versions": {
    "ruleledger_v1": 45
  }
}
```

The summary should not replace existing cell, topology, mode, or reasoning
summaries.

## Orchestrator Changes

Preparation should copy the selected template:

```text
copy_benchmark_template(repo_root / run["benchmark"]["template_path"], worktree)
```

Hidden-test execution should pass the selected cases directory:

```text
python -m harness.hidden_runner
  --worktree <worktree>
  --out <run_dir>/hidden-results.json
  --cases-dir <repo_root>/<run["benchmark"]["hidden_cases_path">
```

All selected asset paths should be resolved under the repository root unless a
future stage explicitly introduces absolute path support. Relative-only paths
are easier to preserve in artifacts and safer for reproducibility.

## Preflight Changes

Preflight should load the selected config before checking benchmark paths. The
path checks should become:

- Selected benchmark template directory exists.
- Selected hidden cases manifest exists.
- Selected scoring config exists or was resolved successfully.
- Existing prompts and Codex templates still exist.

The hidden case load check should call:

```text
load_cases(repo_root / config["paths"]["hidden_cases"])
```

The preflight payload should record selected benchmark metadata so dry-runs can
be audited without opening the config file.

## Validation Changes

Stage 11 validation should use selected asset paths consistently:

- Experiment config validation checks `benchmark.version`,
  `paths.benchmark_template`, and `paths.hidden_cases`.
- Experiment metadata validation confirms the metadata benchmark object matches
  the selected config.
- Run artifact validation continues comparing `metadata.json` to the expanded
  run record, which now includes the selected benchmark object.
- Hidden-test isolation builds its filename and hash index from the selected
  hidden cases directory.

The privacy check should still reject:

- Any copied hidden case filename.
- Any copied hidden case file contents.
- Any worktree path segment named `hidden_tests`.

For v2, the filename and hash checks must use v2 hidden cases, not v1. This is
the main isolation guarantee for Stage 14.

## Report Changes

Stage 14 should make reports version-aware at the metadata level without
redesigning report interpretation.

Add benchmark metadata to:

- `results/aggregate.json`.
- `results/results.csv` rows.
- `results/results.sqlite` rows.
- HTML report method or benchmark section.
- PDF report through the rendered HTML.

Minimum fields:

```text
benchmark_version
benchmark_template_path
hidden_cases_path
scoring_path
scoring_profile
```

If a single report contains multiple benchmark versions, Stage 14 can emit a
clear warning in aggregate JSON and the HTML report. Full cross-version ranking
rules are a Stage 19 concern.

## Testing Plan

Add unit tests for config loading and matrix expansion:

- `configs/initial_experiment.yaml` expands to 45 runs.
- `configs/c5_c7_solo_reasoning.yaml` expands to 15 runs.
- Every v1 run contains benchmark version `ruleledger_v1`.
- Every v1 run contains template path `benchmark_template`.
- Every v1 run contains hidden cases path `hidden_tests/cases`.
- Every v1 run contains scoring path `configs/scoring.yaml` and scoring profile
  `initial_quality_v1`.
- Missing benchmark fields either receive explicit v1 compatibility defaults or
  fail with a clear validation error, depending on the chosen compatibility
  policy.

Add synthetic v2 tests:

- A synthetic v2 config expands without selecting v1 paths.
- A v2 dry-run writes experiment metadata with v2 asset paths.
- A v2 hidden-case privacy leak is detected from v2 case filenames and hashes.
- A v1 hidden-case filename alone is not enough to fail a v2 worktree unless it
  also violates a generic path rule such as containing a `hidden_tests`
  directory.

Add preflight tests:

- Preflight loads selected v1 hidden cases.
- Preflight loads selected synthetic v2 hidden cases.
- Preflight failure messages include the selected missing path when a configured
  template or hidden manifest is absent.

Add orchestrator tests:

- Preparing a run copies the selected template path.
- Hidden test invocation passes `--cases-dir` for the selected hidden cases.
- Resume validation fails when the previous run metadata uses a different
  benchmark version or asset path.

Add report tests:

- Report rows include benchmark version and scoring profile.
- Aggregate JSON includes benchmark metadata when all rows share a version.
- HTML report renders the benchmark version and scoring profile.
- Existing v1 report tests still pass.

## Suggested Implementation Order

1. Add explicit v1 benchmark fields to checked-in experiment configs.
2. Extend `harness.matrix` validation and expansion to produce benchmark
   metadata on every run.
3. Update experiment metadata and run metadata writers.
4. Change orchestrator template copying and hidden runner invocation to use
   selected paths.
5. Update preflight to load selected assets.
6. Update Stage 11 validation hidden isolation to index selected hidden cases.
7. Add report metadata fields.
8. Add synthetic v2 fixtures and tests.
9. Run focused tests, then the static Stage 11 validation for v1 and synthetic
   v2.

## Verification Commands

Run focused tests first:

```powershell
python -m pytest tests/test_matrix.py tests/test_stage11_validation.py tests/test_stage7_artifacts.py
```

Run report-focused tests after report metadata changes:

```powershell
python -m pytest tests/test_stage10_report.py
```

Run the full test suite when the stage is complete:

```powershell
python -m pytest
```

Run static validation for the default v1 config:

```powershell
python -m harness.validation --config configs/initial_experiment.yaml --skip-preflight --allow-missing-report
```

Run a synthetic v2 dry-run or validation command once the fixture config exists:

```powershell
.\scripts\run_experiment.ps1 -Config tests/fixtures/stage14/ruleledger_v2_experiment.yaml -DryRun -NoReport
```

## Risks

Path drift:

The harness writes paths into many artifacts. A helper that builds the benchmark
metadata object from the resolved config should be used wherever possible.

Hidden-test leakage:

The privacy validator must not keep a hidden v1 index when validating a v2 run.
Tests should prove this with different v1 and v2 case filenames and hashes.

Resume ambiguity:

If benchmark metadata is omitted from run records, an old v1 run directory could
look reusable for v2. The expanded run record and top-level metadata should both
include the selected benchmark object.

Report ambiguity:

Reports that omit benchmark version can make v1 and v2 scores look comparable.
Stage 14 should at least label reports clearly, even though cross-version
ranking policy is deferred.

Overbuilding v2 assets:

Stage 14 should use tiny synthetic fixtures for tests. The real v2 starter and
hidden tests should remain in later stages so this stage stays focused on
version-aware wiring.

## Done When

- `configs/initial_experiment.yaml` still expands to the v1 45-run matrix.
- Default `run_experiment.ps1` and `run_pilot.ps1` behavior still points at v1.
- A synthetic v2 config can dry-run without reading or mutating v1 hidden cases.
- Experiment metadata records benchmark version, template path, hidden cases
  path, scoring path, and scoring profile for v1 and synthetic v2.
- Per-run metadata records the same benchmark asset selection.
- Matrix summaries and reports include benchmark version and scoring profile.
- Hidden-test privacy validation indexes the selected hidden cases directory.
- Stage 11 validation passes for v1 and for the synthetic v2 config.
- Focused and full test suites pass.
