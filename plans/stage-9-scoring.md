# Stage 9: Scoring

## Purpose

Stage 9 converts each measured run's preserved artifacts into a stable, comparable scoring record. It is the bridge between per-run evidence from Stages 6 through 8 and aggregate reporting in Stage 10.

The primary output is `score.json` for every run, including partial and failed runs. A failed run is still a measured run. Missing evidence should lower only the affected component scores; it should not remove the run from tables, summaries, CSV exports, SQLite exports, HTML reports, or PDF reports.

The central benchmark question is:

```text
How much implementation quality did this topology produce, and how expensive was that quality in scarce model usage and wall-clock time?
```

## Scope

Stage 9 owns:

- Per-run component score extraction.
- Weighted `quality_score` computation.
- Token-efficiency metrics.
- Wall-clock-efficiency metrics.
- Diff and code-size metrics.
- Run scoring status.
- `score.json` generation.
- Consistency with downstream result rows.

Stage 9 does not own:

- Running implementation agents.
- Running public tests.
- Running hidden tests.
- Running the blind judge.
- Parsing Codex JSONL usage events.
- Generating the final HTML or PDF report.

Those steps are upstream or downstream stages. Stage 9 should read their artifacts, preserve missing or malformed-artifact behavior, and produce a score record that Stage 10 can consume without guessing.

## Inputs

Each run directory should already contain as many of these artifacts as the run was able to produce:

```text
metadata.json
state.json
typecheck.meta.json
public_ts.meta.json
public_py.meta.json
hidden-results.json
judge.json
usage.json
wall_time.json
judge.wall_time.json
diff-numstat.txt
```

The expanded run record remains the source of truth for:

- `run_id`
- `cell_id`
- `spark_mode`
- scoring weights
- topology metadata used by reports
- model and reasoning metadata used by usage attribution

Stage 9 should not infer experiment identity from directory names when the run record is available.

## Output

Stage 9 writes one file per run:

```text
score.json
```

Recommended schema:

```json
{
  "schema_version": 1,
  "run_id": "C1_direct_01",
  "cell_id": "C1",
  "spark_mode": "direct",
  "component_scores": {
    "public_tests": 0.5,
    "hidden_tests": 0.72,
    "judge": 0.68,
    "typecheck": 1.0,
    "parity": 0.8
  },
  "weights": {
    "public_tests": 0.15,
    "hidden_tests": 0.45,
    "judge": 0.25,
    "typecheck": 0.1,
    "parity": 0.05
  },
  "quality_score": 0.713,
  "efficiency": {
    "quality_per_gpt55_impl_token": 0.000000412,
    "quality_per_judge_inclusive_gpt55_token": 0.000000288,
    "quality_per_total_impl_token": 0.00000019,
    "quality_per_wall_clock_minute": 0.0246
  },
  "diff_stats": {
    "changed_files": 7,
    "insertions": 420,
    "deletions": 31,
    "binary_files": 0,
    "production_loc": 360,
    "test_loc": 60
  },
  "wall_time": {
    "implementation_elapsed_seconds": 1739.2,
    "judge_elapsed_seconds": 318.5
  },
  "status": "partial",
  "warnings": []
}
```

The implementation may add fields, but it should not remove or rename existing fields without updating report generation and tests.

## Component Scores

All component scores should be normalized to `0.0` through `1.0`.

### Public Test Score

Public tests include both language surfaces:

```text
public_test_score = (public_ts_score + public_py_score) / 2
```

For the initial implementation, each public command score is binary:

```text
1.0 if returncode == 0 and timed_out is false
0.0 otherwise
```

This keeps public tests simple and reproducible. A future enhancement can parse framework-level test counts, but that should be deliberate and documented because partial public-test pass rates may not be comparable across TypeScript and Python test runners.

### Typecheck Score

`typecheck_score` is binary:

```text
1.0 if typecheck.meta.json reports returncode == 0 and timed_out is false
0.0 otherwise
```

Typecheck is separated from public tests because syntax, typing, and import health are valuable even when behavioral tests are incomplete.

### Hidden Test Score

`hidden_test_score` comes from `hidden-results.json`:

```text
summary.score
```

If `summary.score` is absent, Stage 9 may fall back to:

```text
summary.point_score
```

The hidden runner owns the internal category weighting. Stage 9 should treat the final hidden score as an opaque normalized score and must not inspect private hidden case payloads.

### Judge Score

The blind judge returns strict JSON in `judge.json`.

Preferred field:

```text
overall_score
```

Fallback fields:

```text
correctness_score
parity_score
maintainability_score
test_evidence_score
```

If `overall_score` is not present, Stage 9 should average the available numeric fallback fields. If none are available, the judge component scores `0.0`. The raw judge artifact should remain preserved even when malformed, but malformed judge output should not receive judge credit.

### Parity Or Minimality Score

The top-level plan originally names `minimality_score` as the fifth component. The current initial scoring config instead uses `parity`.

This is acceptable because the orchestration scoring contract allows:

```text
parity score or minimality score, depending on the scoring config
```

For the initial profile:

```text
parity_score = hidden-results.json categories.parity.score
```

For future profiles that use `minimality`, Stage 9 should compute a deterministic minimality score from diff metrics. The formula should be configurable or explicitly versioned before it affects benchmark results. A reasonable first version would reward solutions that solve the task without excessive churn while avoiding penalties for necessary test additions:

```text
minimality_score = clamp(1.0 - max(0, production_loc - target_production_loc) / penalty_window, 0.0, 1.0)
```

That formula is only a candidate. The important requirement is that minimality must be specified before measured runs, not tuned after seeing outcomes.

## Default Weight Profiles

The top-level planning formula is:

```text
quality_score =
  0.50 * hidden_test_score
+ 0.15 * public_test_score
+ 0.15 * typecheck_score
+ 0.15 * judge_overall_score
+ 0.05 * minimality_score
```

The current initial config uses:

```text
quality_score =
  0.45 * hidden_tests
+ 0.25 * judge
+ 0.15 * public_tests
+ 0.10 * typecheck
+ 0.05 * parity
```

The scoring implementation should not hard-code either profile. It should use the resolved `scoring.weights` copied into the run record by experiment configuration expansion.

Validation requirements:

- Weights must be numeric.
- Weights must be non-negative.
- Weights must sum to `1.0`.
- Unknown component names should produce a warning or config validation error.
- A component with no artifact should score `0.0`.

## Quality Score

Given normalized component scores and validated weights:

```text
quality_score = sum(component_scores[name] * weights[name])
```

Round `quality_score` to six decimal places for JSON output and result tables. Keep internal calculations as floats until the final write.

Example:

```text
hidden_tests = 0.80, weight = 0.45 -> 0.3600
judge       = 0.70, weight = 0.25 -> 0.1750
public      = 0.50, weight = 0.15 -> 0.0750
typecheck   = 1.00, weight = 0.10 -> 0.1000
parity      = 0.60, weight = 0.05 -> 0.0300

quality_score = 0.7400
```

## Efficiency Metrics

Stage 9 reads `usage.json` from Stage 8 and computes:

```text
quality_per_gpt55_impl_token
quality_per_judge_inclusive_gpt55_token
quality_per_total_impl_token
quality_per_wall_clock_minute
```

Definitions:

- `quality_per_gpt55_impl_token`: `quality_score / gpt55_implementation_tokens`
- `quality_per_judge_inclusive_gpt55_token`: `quality_score / gpt55_judge_inclusive_tokens`
- `quality_per_total_impl_token`: `quality_score / implementation_tokens`
- `quality_per_wall_clock_minute`: `quality_score / (implementation_elapsed_seconds / 60)`

If a denominator is missing, zero, or unknown, write `null`. Do not invent token totals or divide by one, because that makes failed usage attribution look artificially efficient.

When GPT-5.5 attribution is best effort, Stage 8 should already record that in `usage.json`. Stage 9 should preserve efficiency metrics and let Stage 10 explain attribution confidence in the report.

## Diff And LOC Metrics

Stage 9 reads `diff-numstat.txt` and computes:

- `changed_files`
- `insertions`
- `deletions`
- `binary_files`

The plan also calls for:

- `production_loc`
- `test_loc`
- total added/deleted LOC

The current implementation has aggregate insertions and deletions but does not yet split production LOC from test LOC. The recommended split is path-based and should be stable before the full experiment:

Production paths:

```text
src/
lib/
package source files outside test directories
Python implementation modules outside test directories
```

Test paths:

```text
tests/
test/
__tests__/
tests_public_py/
*.test.ts
*.spec.ts
test_*.py
*_test.py
```

Generated files, dependency directories, and run artifacts should not count as production or test LOC. If a path cannot be classified, count it in aggregate insertions/deletions and add a warning rather than silently guessing.

## Status And Failure Handling

Stage 9 should distinguish between score and status.

Score answers:

```text
How much did this run earn?
```

Status answers:

```text
How complete was the run evidence?
```

Recommended statuses:

- `passed`: all weighted components are complete and score `1.0`.
- `partial`: the run completed enough to score, but at least one phase failed or at least one component is below `1.0`.
- `failed`: infrastructure or setup failure prevented meaningful implementation measurement.
- `missing_score`: report-time status when `score.json` is absent.

The current implementation mainly emits `passed` or `partial`. If `failed` is added later, Stage 10 failure-rate logic should be updated so infrastructure failures remain visible in aggregate results.

Partial runs should receive whatever score they earn. For example:

- Implementation times out before changing files: public, hidden, judge, typecheck likely score `0.0`, but usage and wall time still report.
- Public tests pass but hidden tests fail: the run receives public and typecheck credit but reduced hidden credit.
- Judge output is malformed: judge component scores `0.0`, raw `judge.json` and logs remain available.
- Hidden runner errors: hidden component scores `0.0`, run stays in the result table.

## Privacy Requirements

Stage 9 must not expose hidden case payloads.

Allowed hidden-test information:

- Opaque case IDs.
- Category names.
- Pass/fail/error counts.
- Point totals.
- Normalized category scores.
- Short reason codes.

Forbidden hidden-test information:

- Full hidden inputs.
- Full expected outputs.
- Private fixture payloads.
- Oracle internals.
- Prompts or report text that reveal hidden cases.

If scoring needs more detail than `hidden-results.json` currently provides, update the hidden runner summary schema rather than reading hidden case files directly from Stage 9.

## Orchestration Contract

The orchestrator should call Stage 9 after:

1. Implementation execution.
2. Public tests.
3. Hidden tests.
4. Judge execution.
5. Usage parsing.

The scoring phase should be resumable:

- If `score.json` exists and the `scored` phase is complete, skip scoring.
- If `usage.json` is regenerated, regenerate `score.json`.
- If `-RerunFailed` is supplied, allow failed scoring phases to rerun.
- Do not mutate raw upstream artifacts during scoring.

The scorer should be deterministic. Running Stage 9 twice on the same run directory and run record should produce byte-stable JSON apart from deliberate schema changes.

## Report Contract

Stage 10 should be able to build per-run rows from `score.json` plus `usage.json` without reparsing raw test logs or judge JSON.

At minimum, result rows should include:

- `run_id`
- `cell_id`
- `cell_name`
- `topology`
- `spark_mode`
- `repeat_index`
- `status`
- `quality_score`
- component scores
- implementation tokens
- GPT-5.5 implementation tokens
- judge tokens
- efficiency metrics
- implementation elapsed seconds
- changed files
- insertions
- deletions
- run artifact path

Aggregate rows should compute:

- mean quality score
- median quality score
- standard deviation when useful
- mean hidden score
- mean GPT-5.5 implementation tokens
- failure rate
- best run by quality score

## Implementation Steps

1. Keep `harness.scoring.compute_run_score` as the central scoring entry point.
2. Ensure scoring consumes only run artifacts and the expanded run record.
3. Validate scoring weights during config loading and reject unknown component names unless explicitly allowed.
4. Preserve the current component extraction behavior for public tests, typecheck, hidden tests, judge, and parity.
5. Add a versioned optional minimality component before any scoring config uses `minimality`.
6. Extend diff stats to classify production LOC and test LOC.
7. Add warnings to `score.json` for missing artifacts, malformed JSON, unknown component weights, and unclassified diff paths.
8. Ensure malformed or missing upstream artifacts score as zero for only their affected components.
9. Ensure `write_run_score` writes deterministic, sorted, pretty JSON.
10. Update result row generation if new score fields are added.
11. Add tests for passed, partial, failed, missing-artifact, malformed-artifact, and unknown-weight cases.

## Test Plan

Unit tests should cover:

- Public command score succeeds only for `returncode == 0` and no timeout.
- Missing public command metadata scores `0.0`.
- Public test score averages TypeScript and Python public command scores.
- Hidden score reads `summary.score`.
- Hidden score falls back to `summary.point_score`.
- Hidden parity reads `categories.parity.score`.
- Judge score uses `overall_score` when present.
- Judge score averages fallback numeric fields when `overall_score` is absent.
- Malformed `judge.json` scores `0.0`.
- Quality score uses run-provided weights.
- Missing weighted components score `0.0` and produce a warning.
- Efficiency ratios return `null` for missing or zero denominators.
- Diff numstat parsing counts changed files, insertions, deletions, and binary files.
- Production LOC and test LOC classification is path-stable.
- Failed phases in `state.json` produce partial or failed status as specified.
- `score.json` is deterministic for repeated scoring.

Integration tests should cover:

- A synthetic complete run produces expected `score.json`.
- A synthetic partial run remains in collected report rows.
- Regenerating `usage.json` causes `score.json` to refresh.
- Report CSV, SQLite, aggregate JSON, HTML, and PDF read the same score values for a sample run.

## Acceptance Checklist

- `score.json` is written for passed, partial, and failed runs.
- Component scores are normalized to `0.0` through `1.0`.
- Config weights drive `quality_score`.
- Missing artifacts score as zero for the affected component only.
- Hidden payloads are never read or emitted by scoring.
- Token-efficiency metrics are computed from `usage.json`.
- Wall-clock-efficiency metrics are computed from wall-time artifacts.
- Diff stats include changed files, insertions, deletions, and binary files.
- Production LOC and test LOC are either implemented or explicitly recorded as not available.
- Partial and failed runs remain visible in result rows.
- Score JSON and downstream CSV/SQLite rows agree for sampled runs.

## Open Questions

- Should the initial experiment keep the current `parity` component, or should it switch back to the top-level `minimality` component before the full 45-run experiment?
- If minimality is used, what fixed formula and thresholds should be frozen before measured runs?
- Should public test scoring stay binary per language, or should it eventually parse per-test pass rates?
- Should infrastructure failures get a distinct `failed` status now, or should the current `partial` status remain until reporting needs finer categories?
- Should unknown scoring weight names fail config validation or produce a score-time warning with zero contribution?
