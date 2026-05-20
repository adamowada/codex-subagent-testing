# Stage 19: Revise V2 Scoring And Reporting

## Purpose

Stage 19 makes RuleLedger v2 results interpretable. Stages 14 through 18 made
v2 selectable, documented the hard-mode contract, generated deterministic hidden
cases, and upgraded the hidden runner. The current v2 scoring profile is still a
temporary profile that treats the hidden suite as one large score plus
minimality. Stage 19 should split the v2 score into the components that matter
for calibration and reporting.

This stage should answer:

```text
Can the harness score and report v2 runs in a way that highlights hard-mode
correctness, parity, performance, and calibration spread without breaking v1
reports or silently mixing benchmark versions?
```

## Scope

Stage 19 owns:

- Revising the v2 scoring profile so hidden correctness dominates, but parity,
  performance, judge review, and minimality remain visible.
- Adding v2-specific component scores derived from sanitized hidden-runner
  output.
- Keeping public tests and typecheck visible as sanity checks without allowing
  them to hide weak hidden correctness.
- Adding report fields for benchmark version, scoring profile, v2 category
  means, category saturation, performance pass rate, and spread by root
  reasoning.
- Ensuring CSV, SQLite, aggregate JSON, HTML, and PDF outputs agree.
- Guarding mixed v1/v2 reports so they are split, warned about, or explicitly
  labeled instead of silently ranked together.
- Preserving all existing v1 scoring and report behavior.

Stage 19 does not own:

- Changing the v2 starter template.
- Changing v2 semantics.
- Regenerating hidden cases.
- Changing hidden-runner operation behavior.
- Calibrating the hidden case mix from pilot outcomes.
- Editing locked source-of-truth documents unless explicitly requested.
- Committing generated `runs/` output.

## Inputs

Stage 19 starts from:

```text
configs/scoring.yaml
configs/scoring_v2.yaml
configs/initial_experiment.yaml
configs/ruleledger_v2.yaml
harness/scoring.py
harness/report_data.py
harness/matrix.py
harness/validation.py
harness/hidden_runner.py
tests/test_stage9_scoring.py
tests/test_stage10_report.py
tests/test_stage11_validation.py
tests/test_matrix.py
hidden_tests/cases_v2/manifest.json
```

The v2 hidden runner already writes sanitized category summaries in
`hidden-results.json`. Stage 19 should consume those summaries rather than
reading private hidden case files.

## Current State

The current v1 scoring config uses:

```json
{
  "public_tests": 0.15,
  "hidden_tests": 0.50,
  "judge": 0.15,
  "typecheck": 0.15,
  "minimality": 0.05
}
```

The current v2 scoring config uses:

```json
{
  "hidden_tests": 0.95,
  "minimality": 0.05
}
```

That v2 profile is intentionally simple, but it collapses too much signal:

- `parity` is just another hidden category unless split out.
- `performance` is just another hidden category unless split out.
- easy hidden categories can mask hard hidden categories.
- public/typecheck pass rates are visible in rows, but not clearly described as
  gates or sanity checks for v2.
- reports show benchmark version metadata, but not v2 category saturation or
  calibration spread.

## Proposed V2 Scoring Profile

Replace the temporary v2 profile with a profile that makes the important v2
signals explicit:

```json
{
  "hidden_correctness": 0.55,
  "hidden_parity": 0.15,
  "performance": 0.10,
  "judge": 0.15,
  "minimality": 0.05
}
```

The scoring implementation should remain config-driven. Do not hard-code this
profile as the only v2 profile; instead, add support for the new component names
and update `configs/scoring_v2.yaml` to use them.

## Component Semantics

### Hidden Correctness

`hidden_correctness` should measure the main v2 hidden semantic score while
excluding categories that have their own components.

Recommended excluded categories:

```text
parity
performance
```

If category-level point totals are available, compute the weighted point score
from the remaining categories:

```text
hidden_correctness =
  sum(points_earned for non-parity, non-performance cases)
  / sum(points_possible for non-parity, non-performance cases)
```

If category detail is missing, fall back to the top-level hidden score and add a
score warning.

### Hidden Parity

`hidden_parity` should use the hidden category score for `parity`.

If the parity category is missing, score `0.0` and add a warning when the v2
profile references the component.

### Performance

`performance` should use the hidden category score for `performance`.

Timeouts recorded by the hidden runner are already scored case failures. Stage
19 should also expose performance pass/fail rates in reporting so users can see
whether the score is semantic, runtime, or both.

### Judge

`judge` keeps the existing judge scoring behavior. It remains useful as a blind
maintainability and robustness signal, but it should not dominate v2 quality.

### Minimality

`minimality` keeps the existing production LOC penalty formula unless Stage 19
needs a more explicit label such as `maintainability`. If a rename is desired,
add it as an alias instead of removing `minimality`.

### Public Tests And Typecheck

Public tests and typecheck should remain collected and reported as
`public_tests` and `typecheck`.

For v2, they should be treated as gates or low-weight sanity checks:

- If omitted from weights, they do not directly raise quality.
- If they fail, the run row and report should make that failure obvious.
- A public/typecheck pass must not compensate for low hidden correctness.

## Score JSON Contract

Keep the existing score schema backward compatible. Add fields rather than
renaming existing fields.

Recommended additions:

```json
{
  "benchmark": {
    "version": "ruleledger_v2",
    "scoring_profile": "starter_quality_v2"
  },
  "component_scores": {
    "hidden_tests": 0.62,
    "hidden_correctness": 0.58,
    "hidden_parity": 0.50,
    "performance": 0.75,
    "public_tests": 1.0,
    "typecheck": 1.0,
    "judge": 0.70,
    "minimality": 0.90
  },
  "hidden_category_scores": {
    "account_merges": 0.50,
    "billing_proration": 0.75,
    "bitemporal_replay": 0.40,
    "lifecycle_precedence": 0.60,
    "metamorphic_invariants": 0.80,
    "normalization": 1.0,
    "parse_validation": 1.0,
    "parity": 0.50,
    "performance": 0.75,
    "reporting": 1.0
  },
  "gate_scores": {
    "public_tests": 1.0,
    "typecheck": 1.0
  }
}
```

The exact nesting can differ, but the same data should be available to report
generation without re-reading private hidden cases.

## Result Row Contract

Extend result rows with v2-aware columns while preserving current columns:

```text
hidden_correctness
hidden_parity
performance
performance_pass_rate
hidden_category_scores
category_saturation
public_tests_gate
typecheck_gate
```

CSV and SQLite can store structured fields as JSON text, matching existing
patterns for warnings and complex values.

## Aggregate JSON Contract

Extend `aggregate.json` with:

```json
{
  "benchmark": {
    "version": "ruleledger_v2",
    "scoring_profile": "starter_quality_v2",
    "versions": {
      "ruleledger_v2": 1
    }
  },
  "v2": {
    "category_means": {},
    "category_saturation": {},
    "performance": {
      "score_mean": 0.0,
      "pass_rate": 0.0,
      "timeout_rate": 0.0
    },
    "spread_by_root_reasoning": {},
    "mixed_version_policy": "single_version"
  }
}
```

If the selected rows are v1-only, the v2 section may be omitted or empty. If the
selection contains mixed versions, aggregate JSON should include a clear warning
or policy field.

## Category Saturation

Stage 19 should identify saturated categories. A practical first definition:

```text
saturated = category_mean >= 0.95
```

The report should list:

- saturated categories
- non-saturated categories
- categories with the largest spread when repeats or multiple cells exist

This helps Stage 20 calibration by showing which hidden categories differentiate
runs and which categories are already too easy.

## Performance Reporting

Performance should not be buried in a single score.

Report:

- mean performance score
- performance pass rate
- performance timeout rate when reason data is available
- performance failures by cell or run group

The hidden runner already records timeout reasons in sanitized case rows. Stage
19 can compute timeout rates from `hidden-results.json` case summaries without
reading hidden inputs.

## Reasoning-Level Spread

For v2 calibration, the report should summarize spread by root reasoning:

```text
root_reasoning -> mean quality, hidden correctness, performance, run count
```

When the selected matrix has only one v2 run, this section should render as a
small table with one row and explain that spread requires multiple reasoning
levels.

## Cross-Version Report Safety

V1 and v2 scores are not directly comparable. Stage 19 should prevent silent
cross-version rankings.

Recommended behavior:

- Single-version reports behave normally.
- Mixed-version reports include a prominent warning in `aggregate.json` and
  HTML/PDF.
- Primary rankings are grouped by benchmark version unless the caller explicitly
  requests cross-version mode.
- Cross-version mode, if added, must label rankings as non-equivalent.

The first Stage 19 implementation can stop at warnings and version-grouped
rankings if full cross-version CLI mode is too large.

## HTML/PDF Report Changes

Add v2-specific report sections when selected rows include `ruleledger_v2`:

```text
V2 Scoring Profile
Hidden Category Calibration
Performance And Timeout Behavior
Reasoning-Level Spread
Cross-Version Notes
```

Keep existing sections for v1:

```text
Abstract
Methods
Benchmark Task
Experiment Matrix
Results
Direct Edit Versus Proposal-Only Comparison
C4 Stress-Test Analysis
Token Attribution Notes
Limitations
Appendix
```

The C4 section should continue to be omitted when no C4 rows are selected.

## Privacy Rules

Stage 19 must not read or emit private hidden inputs or expected outputs.

Allowed hidden data sources:

- `hidden-results.json` summary
- `hidden-results.json` categories
- sanitized `hidden-results.json` cases

Forbidden in scoring/report outputs:

- raw hidden inputs
- hidden expected outputs
- private rule payloads beyond existing public category names
- hidden case file contents

If scoring needs more detail than `hidden-results.json` provides, update the
hidden runner to emit additional sanitized aggregates rather than reading hidden
case files.

## Implementation Steps

1. Add new known scoring components:
   - `hidden_correctness`
   - `hidden_parity`
   - `performance`
2. Update `configs/scoring_v2.yaml` to use the revised v2 profile.
3. Add helper functions in `harness.scoring` to compute hidden category scores
   from sanitized hidden results.
4. Compute `hidden_correctness` by excluding v2 parity/performance categories
   from hidden category point totals.
5. Preserve the existing `hidden_tests` component as the overall hidden score
   for compatibility and optional profiles.
6. Add score warnings for missing categories referenced by active weights.
7. Add benchmark version and scoring profile metadata to `score.json` if not
   already available through run metadata.
8. Extend result rows in `harness.report_data` with the new component columns.
9. Store hidden category scores in row data as deterministic JSON text.
10. Extend aggregate output with v2 category means, saturation, performance
    stats, and root-reasoning spread.
11. Add mixed-version detection and reporting warnings.
12. Add v2-specific HTML report sections.
13. Ensure the minimal PDF fallback includes enough v2 summary text.
14. Update tests for scoring, CSV, SQLite, aggregate JSON, HTML, and PDF.
15. Run v1 and v2 validation to ensure both paths still pass.

## Testing Strategy

Add scoring tests:

- v2 score combines the revised weights.
- hidden correctness excludes `parity` and `performance`.
- hidden parity uses the `parity` category.
- performance uses the `performance` category.
- missing weighted v2 categories score zero with warnings.
- v1 scoring remains unchanged.

Add report tests:

- result rows include v2 component columns.
- CSV and SQLite include the new columns.
- aggregate JSON includes v2 category means and saturation.
- HTML report renders v2 scoring and category calibration sections.
- PDF fallback includes benchmark version and v2 scoring profile.
- mixed v1/v2 rows produce an explicit warning or grouped ranking behavior.
- existing v1 report tests still pass.

Add validation tests:

- v1 validation still accepts `configs/initial_experiment.yaml`.
- v2 validation accepts the updated `configs/ruleledger_v2.yaml`.
- scoring configs reject unknown component names but accept the new v2
  components.

## Verification

Recommended commands:

```powershell
python -m pytest tests/test_stage9_scoring.py
python -m pytest tests/test_stage10_report.py
python -m pytest tests/test_stage11_validation.py tests/test_matrix.py
python -m harness.validation --config configs/initial_experiment.yaml --skip-preflight --allow-missing-report
python -m harness.validation --config configs/ruleledger_v2.yaml --skip-preflight --allow-missing-report
python -m pytest
git diff --check
```

If report rendering uses the minimal PDF renderer in tests, keep the renderer
status explicit in `aggregate.json`.

## Done Criteria

Stage 19 is complete when:

- `configs/scoring_v2.yaml` uses the revised v2 scoring components.
- `harness.scoring` computes `hidden_correctness`, `hidden_parity`, and
  `performance` from sanitized hidden-runner output.
- V2 `score.json` includes benchmark version, scoring profile, category scores,
  and gate scores.
- Results CSV and SQLite include the new v2 component fields.
- Aggregate JSON includes v2 category means, saturation, performance stats, and
  reasoning-level spread.
- HTML and PDF reports render v2 scoring/reporting sections when v2 rows are
  selected.
- Mixed v1/v2 reports are warned about or grouped by version.
- Public/typecheck success cannot hide poor hidden correctness in the v2 quality
  score.
- Existing v1 scoring and report tests still pass.

## Risks

Risk: V2 score changes break v1 reports.

Mitigation: Add fields rather than rename fields, keep v1 config unchanged, and
run existing v1 report tests.

Risk: Hidden category analysis leaks private case details.

Mitigation: Consume only sanitized `hidden-results.json` summaries and case
result metadata.

Risk: New components are too v2-specific and reduce config flexibility.

Mitigation: Implement them as generic known components that are only used when
selected by a scoring profile.

Risk: Mixed-version reporting becomes confusing.

Mitigation: Default to warnings and version-grouped summaries; require explicit
cross-version mode before presenting a single primary ranking.

Risk: Category saturation thresholds are arbitrary.

Mitigation: Start with a documented threshold such as `>= 0.95`, expose it in
aggregate metadata, and avoid changing it after pilot results without a new
versioned decision.

## Open Questions

- Should `hidden_correctness` use point-weighted category totals or a simple
  average of non-parity, non-performance category scores?
- Should public tests and typecheck be hard gates that cap quality, or only
  visible unweighted sanity checks?
- Should `minimality` be renamed to `maintainability` for v2, or kept as-is for
  continuity?
- Should mixed-version reports fail by default, or render with warnings and
  grouped rankings?
- Should category saturation threshold be fixed at `0.95`, or configured per
  scoring profile?
