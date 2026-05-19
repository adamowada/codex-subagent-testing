# Stage 3 Plan: Experiment Configuration

## Goal

Create `configs/initial_experiment.yaml`, the source-of-truth configuration for the initial Codex subagent topology experiment. The config should describe the full 45-run experiment matrix, shared runtime knobs, Codex prompt and config template paths, agent topology settings, model and reasoning choices, Spark edit modes, and scoring weights.

Stage 3 is complete when orchestration code can load one YAML file, validate it, and expand it into exactly 45 deterministic implementation run records without hard-coded experiment logic.

## Non-Goals

- Do not implement the full experiment orchestrator in this stage.
- Do not run measured Codex implementation jobs.
- Do not create prompts, judge prompts, or Codex agent template files beyond path references.
- Do not generate reports or score real experiment outputs.
- Do not place hidden test cases, hidden fixtures, or private expected outputs in config.
- Do not commit generated run output under `runs/`.

## Target Directory Layout

```text
configs/
  initial_experiment.yaml
  scoring.yaml
harness/
  matrix.py
```

`configs/initial_experiment.yaml` should be the complete experiment definition. `configs/scoring.yaml` may exist as a separate file if scoring weights are shared by multiple experiments, but `initial_experiment.yaml` should either include those weights directly or reference the scoring file explicitly.

`harness/matrix.py` should contain the reusable config loader, validator, and matrix expansion helpers used later by the orchestrator and pilot script.

## Configuration Responsibilities

The experiment config should define:

- Experiment identity and schema version.
- Repeat count, initially `5`.
- Default implementation parallelism, initially `3`.
- Default judge parallelism, initially `2`.
- C0-C4 cell definitions.
- Spark edit modes: `direct` and `proposal`.
- Root, sublead, and leaf models.
- Root, sublead, and leaf reasoning levels.
- Per-role Spark reasoning knobs.
- Sublead count.
- Leaves per sublead.
- `agents.max_threads`.
- `agents.max_depth`.
- Implementation job timeout.
- Judge job timeout.
- Prompt template paths.
- Rendered Codex config template path.
- Scoring weights or scoring config path.

The config should make future experiments possible by changing data, not Python control flow. Adding a new topology, changing reasoning effort, changing role counts, or changing direct/proposal coverage should require a config edit and validation, not orchestrator surgery.

## Initial Cell Matrix

The first experiment contains five cells:

| Cell | Topology | Spark Modes | Repeats | Runs |
|---|---|---:|---:|---:|
| C0 | GPT-5.5 xhigh solo baseline | none | 5 | 5 |
| C1 | GPT-5.5 medium lead -> 6 Spark xhigh leaves | direct, proposal | 5 | 10 |
| C2 | GPT-5.5 high lead -> 6 Spark xhigh leaves | direct, proposal | 5 | 10 |
| C3 | GPT-5.5 xhigh lead -> 6 Spark xhigh leaves | direct, proposal | 5 | 10 |
| C4 | GPT-5.5 xhigh root -> 3 GPT-5.5 medium subleads -> 18 Spark xhigh leaves | direct, proposal | 5 | 10 |

Total implementation runs:

```text
5 + 10 + 10 + 10 + 10 = 45
```

The matrix expander should treat C0 specially only because it has no Spark edit-mode toggle. Prefer an explicit field such as `spark_modes: []` or `spark_modes: null` over inferring that behavior from the cell ID.

## Model And Reasoning Rules

The initial experiment should enforce these model constraints:

- `gpt-5.5` is used for solo runs, root leads, C1-C3 flat leads, C4 root lead, C4 subleads, and judges.
- `gpt-5.3-codex-spark` is used for Spark leaves.
- Spark leaves always use `model_reasoning_effort: xhigh` in the initial matrix.
- Spark reasoning must still be configurable per role for future experiments.
- C1 root/lead reasoning is `medium`.
- C2 root/lead reasoning is `high`.
- C3 root/lead reasoning is `xhigh`.
- C4 root reasoning is `xhigh`.
- C4 sublead reasoning is `medium`.
- Judges use GPT-5.5 `xhigh`, but judge configuration should remain distinct from implementation configuration.

The config validator should fail if the initial experiment references models outside this allowed set unless the schema explicitly opts into an expanded model allowlist.

## Spark Edit Modes

`direct` mode means Spark leaves may write to the implementation workspace according to their rendered Codex agent config.

`proposal` mode means Spark leaves are read-only. They inspect files and return proposed changes for the GPT-5.5 lead, root, or sublead to apply.

The configuration should store edit mode as data on each expanded run because later prompts, `.codex` config rendering, scoring breakdowns, and report groupings all need it.

Recommended mode shape:

```yaml
spark_modes:
  direct:
    leaf_write_mode: workspace-write
    proposal_only: false
  proposal:
    leaf_write_mode: read-only
    proposal_only: true
```

Cells C1-C4 should reference both mode names. C0 should reference no Spark mode.

## C4 Stress-Test Topology

C4 is an intentional stress test, not a default recommendation. Its topology should be explicit and validated:

```text
root: 1 x GPT-5.5 xhigh
subleads: 3 x GPT-5.5 medium
leaves: 18 x Spark xhigh
shape: each sublead coordinates 6 Spark leaves
agents.max_depth: 2
agents.max_threads: at least 24
```

Recommended config fields:

```yaml
subleads:
  count: 3
  model: gpt-5.5
  reasoning: medium
  leaves_per_sublead: 6
leaf:
  model: gpt-5.3-codex-spark
  reasoning_by_role:
    implementer: xhigh
    tester: xhigh
    adversary: xhigh
agents:
  max_depth: 2
  max_threads: 24
```

The matrix validator should confirm:

- C4 has exactly three subleads.
- C4 has exactly six leaves per sublead.
- C4 therefore has exactly eighteen Spark leaves.
- C4 `agents.max_depth` is `2`.
- C4 `agents.max_threads` is high enough for the configured breadth.

## Suggested YAML Shape

This shape is intentionally verbose so later code can validate and render it predictably:

```yaml
schema_version: 1
experiment:
  id: initial_subagent_topology
  repeat_count: 5
  seed: 20260519

parallelism:
  implementation_jobs: 3
  judge_jobs: 2

timeouts:
  implementation_seconds: 7200
  judge_seconds: 1800

paths:
  prompt_templates:
    common: prompts/task_common.md
    solo: prompts/task_solo.md
    flat_spark: prompts/task_flat_spark.md
    depth2_subleads: prompts/task_depth2_subleads.md
    judge: prompts/judge.md
  codex_config_template: codex_templates/config.toml.j2
  scoring: configs/scoring.yaml

models:
  gpt55: gpt-5.5
  spark: gpt-5.3-codex-spark

spark_modes:
  direct:
    leaf_write_mode: workspace-write
    proposal_only: false
  proposal:
    leaf_write_mode: read-only
    proposal_only: true

scoring:
  public_tests: 0.15
  hidden_tests: 0.45
  judge: 0.25
  typecheck: 0.10
  parity: 0.05

cells:
  - id: C0
    name: solo_gpt55_xhigh
    repeats: 5
    spark_modes: []
    topology: solo
    prompt_template: solo
    root:
      model: gpt-5.5
      reasoning: xhigh
    agents:
      max_depth: 0
      max_threads: 1

  - id: C1
    name: flat_spark_gpt55_medium
    repeats: 5
    spark_modes: [direct, proposal]
    topology: flat_spark
    prompt_template: flat_spark
    root:
      model: gpt-5.5
      reasoning: medium
    leaf:
      model: gpt-5.3-codex-spark
      count: 6
      reasoning_by_role:
        implementer: xhigh
        tester: xhigh
        adversary: xhigh
    agents:
      max_depth: 1
      max_threads: 8

  - id: C2
    name: flat_spark_gpt55_high
    repeats: 5
    spark_modes: [direct, proposal]
    topology: flat_spark
    prompt_template: flat_spark
    root:
      model: gpt-5.5
      reasoning: high
    leaf:
      model: gpt-5.3-codex-spark
      count: 6
      reasoning_by_role:
        implementer: xhigh
        tester: xhigh
        adversary: xhigh
    agents:
      max_depth: 1
      max_threads: 8

  - id: C3
    name: flat_spark_gpt55_xhigh
    repeats: 5
    spark_modes: [direct, proposal]
    topology: flat_spark
    prompt_template: flat_spark
    root:
      model: gpt-5.5
      reasoning: xhigh
    leaf:
      model: gpt-5.3-codex-spark
      count: 6
      reasoning_by_role:
        implementer: xhigh
        tester: xhigh
        adversary: xhigh
    agents:
      max_depth: 1
      max_threads: 8

  - id: C4
    name: depth2_subleads_stress
    repeats: 5
    spark_modes: [direct, proposal]
    topology: depth2_subleads
    prompt_template: depth2_subleads
    root:
      model: gpt-5.5
      reasoning: xhigh
    subleads:
      count: 3
      model: gpt-5.5
      reasoning: medium
      leaves_per_sublead: 6
    leaf:
      model: gpt-5.3-codex-spark
      reasoning_by_role:
        implementer: xhigh
        tester: xhigh
        adversary: xhigh
    agents:
      max_depth: 2
      max_threads: 24
```

Exact timeout values and scoring weights can be adjusted, but they should be present and documented. If scoring moves fully into `configs/scoring.yaml`, the matrix loader should still expose a resolved scoring object to downstream code.

## Expanded Run Record

`harness.matrix.expand_experiment(config)` should return deterministic run records. Each record should contain enough information for the orchestrator to render prompts, create run directories, configure Codex, and group results later.

Recommended record shape:

```json
{
  "run_id": "C1_direct_r03",
  "cell_id": "C1",
  "repeat_index": 3,
  "topology": "flat_spark",
  "spark_mode": "direct",
  "prompt_template": "flat_spark",
  "root": {
    "model": "gpt-5.5",
    "reasoning": "medium"
  },
  "subleads": null,
  "leaf": {
    "model": "gpt-5.3-codex-spark",
    "count": 6,
    "reasoning_by_role": {
      "implementer": "xhigh",
      "tester": "xhigh",
      "adversary": "xhigh"
    }
  },
  "agents": {
    "max_depth": 1,
    "max_threads": 8
  },
  "timeouts": {
    "implementation_seconds": 7200,
    "judge_seconds": 1800
  }
}
```

Recommended ordering:

1. Cell order as listed in config.
2. Spark mode order as listed on the cell.
3. Repeat index ascending from `1` to `repeats`.

C0 run IDs should omit a fake Spark mode:

```text
C0_r01
C0_r02
C0_r03
C0_r04
C0_r05
```

C1-C4 run IDs should include mode:

```text
C1_direct_r01
C1_proposal_r01
```

The chosen ordering only needs to be stable and documented. Stable ordering matters for resume behavior, artifact paths, deterministic report tables, and comparing pilot/full experiment behavior.

## Validation Rules

`harness.matrix.validate_experiment(config)` should reject invalid experiment definitions before any measured run starts.

Required validation:

- `schema_version` is supported.
- Experiment ID is present and filesystem-safe.
- Repeat count is positive.
- Default parallelism values are positive.
- Timeouts are positive.
- Referenced prompt template keys exist.
- Referenced template paths are relative repository paths.
- All cell IDs are unique.
- Every cell has a known topology.
- Every cell has a positive repeat count.
- Every non-C0 Spark mode reference exists under `spark_modes`.
- C0 has no Spark modes.
- C1-C4 include both `direct` and `proposal`.
- All model names are allowed for the initial experiment.
- All reasoning values are valid Codex reasoning values.
- Spark leaf model is `gpt-5.3-codex-spark`.
- Initial Spark leaf reasoning values are all `xhigh`.
- C4 sublead model is `gpt-5.5`.
- C4 sublead reasoning is `medium`.
- C4 leaf count resolves to eighteen.
- `agents.max_depth` matches topology depth.
- `agents.max_threads` is at least the configured agent breadth.
- Scoring weights are present and sum to `1.0`, unless the scoring implementation deliberately supports unnormalized weights.
- Matrix expansion produces exactly 45 implementation runs.

Validation errors should name the failing field path and the reason, for example:

```text
cells[4].agents.max_depth: C4 depth2_subleads requires max_depth=2
```

## Matrix Module API

Recommended `harness/matrix.py` API:

```python
def load_experiment_config(path: str | Path) -> dict:
    """Load YAML and return the raw config dictionary."""


def validate_experiment_config(config: dict) -> None:
    """Raise ValueError with actionable messages if config is invalid."""


def expand_experiment_matrix(config: dict) -> list[dict]:
    """Return deterministic implementation run records."""


def summarize_matrix(runs: list[dict]) -> dict:
    """Return counts by cell, mode, topology, model, and reasoning."""
```

The orchestrator should use these helpers rather than open-coding matrix behavior. Unit tests can target this module before any Codex execution exists.

## Test Plan

Add focused tests for config expansion and validation when a test harness exists.

Suggested cases:

- The initial config expands to exactly 45 runs.
- C0 expands to 5 runs and has no Spark mode.
- C1-C4 each expand to 10 runs.
- C1-C4 each include 5 direct and 5 proposal runs.
- C1 root reasoning is medium.
- C2 root reasoning is high.
- C3 root reasoning is xhigh.
- C4 root reasoning is xhigh.
- C4 has 3 subleads, 6 leaves per sublead, and 18 total Spark leaves.
- All Spark leaf reasoning values are xhigh.
- Invalid model names fail validation.
- Missing prompt template references fail validation.
- Duplicate cell IDs fail validation.
- Scoring weights that do not sum to 1.0 fail validation if normalized weights are required.

These tests should run quickly and should not invoke Codex.

## Implementation Steps

1. Create `configs/initial_experiment.yaml` with schema version, defaults, paths, Spark modes, scoring weights, and C0-C4 definitions.
2. Add `harness/matrix.py` with YAML loading, validation, expansion, and summary helpers.
3. Add a lightweight dependency for YAML parsing only if the project does not already have one available. Prefer `PyYAML` if adding a dependency is necessary.
4. Add tests for the matrix loader and validator.
5. Add a simple inspection command or script entrypoint if useful, for example:

```powershell
python -m harness.matrix configs/initial_experiment.yaml
```

The inspection command should print the expanded run count and a compact summary by cell and mode. It should not create run directories or invoke Codex.

## Done When

- `configs/initial_experiment.yaml` exists and is the source of truth for the initial experiment matrix.
- The matrix expands to exactly 45 implementation runs.
- C0-C4 encode the agreed models, reasoning levels, depth, breadth, repeats, and Spark edit modes.
- Spark reasoning is configurable per role while initially set to `xhigh`.
- Scoring weights and runtime knobs are config-driven.
- Validation catches malformed or drifted experiment definitions before orchestration begins.
- No hidden test data is copied into config, prompts, starter files, or run worktrees.
