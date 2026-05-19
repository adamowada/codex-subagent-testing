# Stage 10: Report

## Purpose

Stage 10 turns scored experiment artifacts into a readable, reproducible report for humans. It is the final presentation layer for the initial Codex subagent topology benchmark.

The report should answer the central benchmark question:

```text
Which topology produced the most implementation quality per scarce GPT-5.5 implementation token, and what tradeoffs did it make in correctness, time, coordination complexity, failures, and Spark edit mode?
```

Stage 10 should not rescore runs, rerun tests, rerun judges, or reinterpret raw Codex JSONL. Earlier stages produce the evidence. This stage prepares aggregate data, explains the method, visualizes the results, and preserves links back to the raw run artifacts.

## Scope

Stage 10 owns:

- Collecting report rows from `score.json`, `usage.json`, and expanded run records.
- Writing experiment-level CSV, SQLite, and aggregate JSON outputs.
- Producing a styled HTML report.
- Rendering the HTML report to PDF.
- Ranking cells by quality per GPT-5.5 implementation token.
- Visualizing primary and secondary metrics.
- Explaining token-attribution confidence and limitations.
- Including failed, partial, and missing-score runs in appendices.

Stage 10 does not own:

- Running measured implementation agents.
- Running public tests, hidden tests, typecheck, or judges.
- Parsing raw Codex usage JSONL.
- Computing per-run component scores.
- Editing hidden tests or revealing hidden test cases.
- Rewriting top-level source-of-truth documents.

## Inputs

The experiment directory should already contain expanded run records from the selected configuration and run directories under:

```text
runs/<run_id>/
```

Each run directory should contain as many of these artifacts as the run was able to produce:

```text
metadata.json
state.json
usage.json
score.json
wall_time.json
judge.wall_time.json
diff.patch
diff-numstat.txt
```

The report should primarily consume:

```text
score.json
usage.json
expanded run record
```

It may reference artifact paths from each run directory, but it should not parse hidden test payloads, raw public test logs, raw hidden test logs, judge prompts, or implementation prompts to compute report metrics.

## Outputs

Stage 10 writes experiment-level outputs:

```text
results/results.csv
results/results.sqlite
results/aggregate.json
report/report.html
report/report.pdf
```

These paths are stable contracts used by tests, resume logic, manual inspection, and downstream analysis.

## Report Row Contract

Every selected run should produce one report row, even if scoring is missing or incomplete. Missing evidence should result in zero or null metric values and a clear status, not row deletion.

Required row fields:

- `run_id`
- `cell_id`
- `cell_name`
- `topology`
- `spark_mode`
- `repeat_index`
- `status`
- `quality_score`
- `public_tests`
- `hidden_tests`
- `judge`
- `typecheck`
- `parity`
- `minimality`
- `implementation_tokens`
- `gpt55_implementation_tokens`
- `judge_tokens`
- `quality_per_gpt55_impl_token`
- `quality_per_judge_inclusive_gpt55_token`
- `quality_per_total_impl_token`
- `quality_per_wall_clock_minute`
- `implementation_elapsed_seconds`
- `changed_files`
- `insertions`
- `deletions`
- `binary_files`
- `production_loc`
- `test_loc`
- `run_dir`

Useful optional fields:

- `root_model`
- `root_reasoning`
- `leaf_model`
- `leaf_reasoning`
- `sublead_model`
- `sublead_reasoning`
- `agent_max_depth`
- `agent_max_threads`
- `usage_attribution_method`
- `usage_warnings`
- `score_warnings`
- `failure_phase`
- `artifact_status`

## Aggregate Data Contract

`results/aggregate.json` should include:

- `schema_version`
- `total_runs`
- `by_cell`
- `by_spark_mode`
- `failure_rate`
- `best_run`
- `rankings`
- `token_attribution`
- `generated_at`

Each cell aggregate should include:

- run count
- mean quality score
- median quality score
- quality standard deviation
- mean hidden-test score
- mean public-test score
- mean judge score
- mean typecheck score
- mean parity score
- mean GPT-5.5 implementation tokens
- mean total implementation tokens
- mean implementation elapsed seconds
- mean quality per GPT-5.5 implementation token
- failure rate
- best run by quality score
- best run by primary efficiency metric

Direct-edit versus proposal-only aggregates should compare:

- quality delta
- hidden-test delta
- GPT-5.5 implementation token delta
- total implementation token delta
- wall-clock delta
- failure-rate delta

## Report Structure

The PDF should be readable by a non-academic audience while keeping an academic-paper structure.

Required sections:

1. Title.
2. Abstract.
3. Methods.
4. Benchmark task.
5. Experiment matrix.
6. Results.
7. Direct edit versus proposal-only comparison.
8. C4 stress-test analysis.
9. Token attribution notes.
10. Limitations.
11. Appendix with per-run rows and artifact paths.

### Title

The title should identify the benchmark and the compared topology family.

Example:

```text
Codex Subagent Topology Benchmark: Quality per GPT-5.5 Token
```

### Abstract

The abstract should summarize:

- the benchmark purpose
- the RuleLedger task
- the compared cells
- the primary metric
- the main result once data exists
- the biggest limitation

For pilot data, clearly label the report as a pilot summary.

### Methods

Methods should explain:

- all runs start from the same frozen starter project
- run artifacts are isolated by `run_id`
- implementation and judge runs use `codex exec --json`
- hidden tests stay outside implementation workspaces
- partial and failed runs remain in the dataset
- scoring uses configured weights
- usage parsing preserves total usage even when attribution is ambiguous

### Benchmark Task

Describe RuleLedger at a high level:

- TypeScript and Python implementation surfaces
- event parsing and validation
- normalization
- state reduction
- entitlement evaluation
- account summaries
- deterministic CSV reporting
- cross-language parity

Do not include hidden test cases, hidden inputs, or hidden expected outputs.

### Experiment Matrix

The matrix should show:

- C0 solo GPT-5.5 xhigh baseline
- C1 flat Spark with GPT-5.5 medium lead and Spark xhigh leaves
- C2 flat Spark with GPT-5.5 high lead and Spark xhigh leaves
- C3 flat Spark with GPT-5.5 xhigh lead and Spark xhigh leaves
- C4 depth-2 stress topology with GPT-5.5 xhigh root, GPT-5.5 medium subleads, and Spark xhigh leaves

For C1 through C4, show both Spark modes:

- direct edit
- proposal-only

### Results

Results should emphasize the primary metric first:

```text
quality_per_gpt55_impl_token
```

Then show:

- mean quality score
- hidden-test score
- public-test score
- judge score
- typecheck score
- parity score
- GPT-5.5 implementation tokens
- judge-inclusive GPT-5.5 tokens
- total implementation tokens
- wall-clock time
- changed files and LOC
- failure rate

### Direct Edit Versus Proposal-Only

This section should compare Spark modes within matching cells. It should avoid comparing proposal-only C1 against direct-edit C3 as though edit mode were the only variable.

For each topology/reasoning cell that supports both modes, report:

- direct mean quality
- proposal mean quality
- quality delta
- GPT-5.5 implementation token delta
- total implementation token delta
- wall-clock delta
- failure-rate delta

### C4 Stress-Test Analysis

C4 should be discussed as an intentional stress test, not just a larger variant. The analysis should mention:

- it exceeds normal default guidance
- coordination may dominate implementation gains
- sublead and leaf parallelism may improve coverage but increase integration risk
- direct-edit C4 may expose merge and conflict hazards
- proposal-only C4 may expose lead bottlenecks

### Token Attribution Notes

The report should surface attribution confidence from `usage.json`.

If mixed-agent JSONL cannot expose per-model attribution, report:

- total implementation usage
- judge usage
- GPT-5.5 implementation usage as best effort or upper bound
- Spark split as unavailable or best effort
- warnings from usage parsing

Do not drop total usage because model-level attribution is incomplete.

### Limitations

Expected limitations:

- initial benchmark uses a contrived but structured project
- hidden tests are exhaustive for the intended task, not for all possible coding work
- five repeats per cell may still have high variance
- GPT-5.5 judge scores can be useful but are not ground truth
- token attribution may be best effort for mixed-agent runs
- C4 is intentionally beyond normal guidance
- wall-clock time depends on local and service conditions

### Appendix

The appendix should include:

- one row per run
- artifact paths
- run status
- component scores
- usage totals
- efficiency metrics
- warning summaries

The appendix should make failures easy to inspect instead of hiding them.

## Charts

Required charts:

- primary metric by cell
- hidden-test score by cell
- GPT-5.5 implementation token usage by cell
- wall-clock time by cell
- failure rate by cell
- direct edit versus proposal-only deltas

Recommended chart treatment:

- Use compact bar charts for cell comparisons.
- Use grouped bars for direct versus proposal mode.
- Use small tables beside charts when exact values matter.
- Keep charts readable in both HTML and printed PDF.
- Use consistent colors for cells and Spark modes.
- Include enough labels that the PDF is understandable without hover interactions.

## HTML and PDF Rendering

Use Python for data preparation and HTML generation. Use HTML/CSS for layout. Use Node Playwright to render the HTML to PDF.

Recommended implementation shape:

```text
harness/report_data.py
harness/report_render.py
scripts/render_report_pdf.mjs
```

`harness/report_data.py` can continue to own row collection, CSV, SQLite, and aggregate JSON.

`harness/report_render.py` can own report-specific view models and HTML rendering.

`scripts/render_report_pdf.mjs` can open `report/report.html` with Playwright and save `report/report.pdf`.

The current minimal PDF writer is useful as a bootstrap fallback, but the Stage 10 target is a styled PDF rendered from the same HTML as the browser report.

## Styling Requirements

The report should feel like a lightweight academic paper:

- clear title page area
- readable abstract
- section headings
- compact tables
- chart captions
- page-friendly margins
- print CSS
- appendix tables that can span pages cleanly

Avoid decorative visual design that makes the report harder to audit. The report is an experiment artifact first.

## Failure Handling

Report generation should be failure-tolerant:

- Missing `score.json` creates a row with status `missing_score`.
- Missing `usage.json` creates usage zeros or nulls plus warnings when available.
- Missing artifact paths should be visible in the appendix.
- Malformed per-run JSON should not abort the entire report if a safe fallback row can be produced.
- PDF rendering failure should not delete the HTML, CSV, SQLite, or aggregate JSON outputs.
- The orchestrator should report PDF generation failure clearly so it can be resumed.

Infrastructure failures that should fail the report phase:

- inability to write output files
- invalid output schema that breaks CSV or SQLite generation
- Playwright renderer unavailable when PDF generation is required and no fallback is allowed

## Privacy and Hidden-Test Safety

Stage 10 must not reveal hidden test data.

Do not include:

- hidden test input payloads
- hidden expected outputs
- hidden fixture names that reveal cases beyond public category names
- judge prompts containing hidden data
- implementation prompts that embed hidden cases

Allowed hidden-test reporting:

- normalized hidden-test score
- category-level score if category names are already part of public scoring configuration
- failure counts
- aggregate pass rates

## Resume Behavior

Report generation should be resumable from completed run artifacts.

If all run-level score and usage artifacts are already present, rerunning the report phase should regenerate:

```text
results/results.csv
results/results.sqlite
results/aggregate.json
report/report.html
report/report.pdf
```

without mutating:

```text
runs/<run_id>/events.jsonl
runs/<run_id>/judge.events.jsonl
runs/<run_id>/diff.patch
```

## Implementation Steps

1. Extend report row collection with optional metadata fields from expanded run records and usage attribution warnings.
2. Extend aggregate JSON with rankings, direct/proposal deltas, and token-attribution summaries.
3. Add deterministic report view-model construction.
4. Replace minimal HTML with a structured report template containing all required sections.
5. Add chart data preparation.
6. Render charts with either inline SVG generated from data or lightweight HTML/CSS chart components.
7. Add print CSS for PDF output.
8. Add Playwright PDF rendering script.
9. Wire Playwright rendering into `write_results_outputs`.
10. Preserve a clear failure path if PDF rendering fails.
11. Add tests for row inclusion, aggregate rankings, direct/proposal deltas, token-attribution warnings, HTML sections, and PDF existence.
12. Run pilot output through the report generator and inspect the rendered PDF.

## Test Plan

Unit tests should cover:

- missing `score.json` creates a `missing_score` row
- malformed `score.json` does not drop the run
- missing `usage.json` preserves row and emits zero or null usage metrics
- aggregate rankings sort by `quality_per_gpt55_impl_token`
- direct/proposal deltas compare only matching cells
- C4 appears in the stress-test section
- token-attribution warnings appear in HTML
- all required report sections appear in HTML

Integration tests should cover:

- synthetic pilot data writes CSV, SQLite, aggregate JSON, HTML, and PDF
- CSV, SQLite, aggregate JSON, and HTML agree on sample score values
- failed or partial runs appear in appendix rows
- report generation can be rerun without measured-run execution
- PDF rendering succeeds when Playwright dependencies are available

Manual verification should include:

- open `report/report.html`
- inspect `report/report.pdf`
- confirm charts are readable in PDF
- confirm appendix tables are not truncated
- confirm hidden test payloads are absent

## Acceptance Checklist

- `report/report.html` is generated.
- `report/report.pdf` is generated.
- `results/results.csv` is generated.
- `results/results.sqlite` is generated.
- `results/aggregate.json` is generated.
- All selected runs appear in the per-run appendix.
- Partial and failed runs are visible.
- Missing-score runs are visible.
- Cells are ranked by quality per GPT-5.5 implementation token.
- Direct edit and proposal-only modes are compared within matching cells.
- C4 stress-test analysis is present.
- Token-attribution caveats are present when attribution is best effort.
- Limitations are present.
- Hidden test payloads are not present.
- Pilot and full experiment data both render without layout breakage.

## Risks

Risk: The report accidentally becomes a second scoring implementation.

Mitigation: Keep scoring in Stage 9 and make Stage 10 consume `score.json` fields only.

Risk: Hidden test details leak into report outputs.

Mitigation: Only report normalized scores, public category names, and aggregate counts.

Risk: PDF generation adds brittle dependencies.

Mitigation: Keep HTML generation independent of Playwright and make renderer failures clear and resumable.

Risk: Charts look fine in HTML but fail in PDF.

Mitigation: Prefer static inline SVG or print-friendly HTML/CSS charts and inspect generated PDF during pilot validation.

Risk: Token attribution is overclaimed.

Mitigation: Carry attribution methods and warnings into the report and label best-effort values plainly.

## Open Questions

- Should the PDF include confidence intervals, or are mean/median/stdev enough for the initial five-repeat experiment?
- Should category-level hidden-test scores appear if category names are public and payloads remain hidden?
- Should report generation have a strict mode that fails when PDF rendering is unavailable, or should the minimal PDF fallback remain available?
- Should the appendix include full warning arrays or compact warning counts with links to run artifacts?
