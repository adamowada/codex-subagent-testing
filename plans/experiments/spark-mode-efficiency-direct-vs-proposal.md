# Spark Mode Efficiency: Direct Edit vs Proposal

## Objective

Determine whether `gpt-5.3-codex-spark` xhigh leaf agents produce better
RuleLedger v3 outcomes, better token efficiency, or both when used in:

- Direct edit mode: Spark agents produce working-tree changes or diffs.
- Proposal mode: Spark agents produce recommendations or patch proposals only,
  and the GPT root integrates the final solution.

The primary comparison is Spark usage mode. GPT-5.5 root reasoning level is the
main interaction variable.

## Core Design

Use outer-harness orchestration so GPT and Spark token usage can be measured
separately.

Each Spark-assisted measured run should follow this shape:

1. GPT-5.5 root planning run creates six task briefs.
2. Six `gpt-5.3-codex-spark` xhigh leaf runs execute separately through
   `codex exec --json`.
3. GPT-5.5 root integration run consumes Spark outputs and finalizes the
   solution.
4. RuleLedger v3 scores the final artifact.
5. The harness records GPT and Spark token usage from their separate JSONL
   event streams.

This avoids estimating Spark token usage by subtracting an assumed GPT-only
usage value from mixed-agent total usage.

## Experiment Matrix

### Spark-Assisted Cells

| Root model | Root reasoning | Spark leaves | Spark reasoning | Spark mode |
| --- | --- | ---: | --- | --- |
| GPT-5.5 | low | 6 | xhigh | direct edit |
| GPT-5.5 | low | 6 | xhigh | proposal |
| GPT-5.5 | medium | 6 | xhigh | direct edit |
| GPT-5.5 | medium | 6 | xhigh | proposal |
| GPT-5.5 | high | 6 | xhigh | direct edit |
| GPT-5.5 | high | 6 | xhigh | proposal |
| GPT-5.5 | xhigh | 6 | xhigh | direct edit |
| GPT-5.5 | xhigh | 6 | xhigh | proposal |

### GPT-Only Bridge Cells

| Model | Reasoning | Mode | Purpose |
| --- | --- | --- | --- |
| GPT-5.5 | low | solo | drift and calibration check |
| GPT-5.5 | medium | solo | drift and calibration check |
| GPT-5.5 | high | solo | drift and calibration check |
| GPT-5.5 | xhigh | solo | drift and calibration check |

## Run Counts

### Pilot Phase

- 2 runs per Spark-assisted cell.
- 2 runs per GPT-only bridge cell.
- 8 Spark-assisted cells plus 4 bridge cells.
- Total pilot runs: 24.

### Main Phase

- 5 runs per Spark-assisted cell.
- The main Spark-assisted matrix contains 8 cells.
- Total main Spark-assisted runs: 40.

The main phase does not need to rerun full GPT-only baselines unless the pilot
bridge runs indicate meaningful drift from the prior 50-run RuleLedger v3
baseline distributions.

### Optional Expansion

Make a note of a possible expansion after the full matrix is finished, but do
not implement it yet.

Potential expansion triggers:

- Direct edit and proposal results are close enough that more power is needed.
- A cell has unusually high variance.
- Bridge runs suggest model, harness, or scoring drift.
- A surprising interaction appears between root reasoning and Spark mode.

## Baseline Strategy

Use the existing 50-run-per-reasoning-level RuleLedger v3 GPT-only results as
the primary GPT-only baseline, assuming benchmark assets, prompts, harness,
judge, scoring, model IDs, and environment are materially unchanged.

Add two contemporaneous GPT-only bridge runs per reasoning level during the
pilot phase:

| Model | Reasoning | Runs | Purpose |
| --- | --- | ---: | --- |
| GPT-5.5 | low | 2 | drift and calibration check |
| GPT-5.5 | medium | 2 | drift and calibration check |
| GPT-5.5 | high | 2 | drift and calibration check |
| GPT-5.5 | xhigh | 2 | drift and calibration check |

If the bridge runs are consistent with the historical 50-run distributions, use
the historical 50-run results as the official GPT-only comparison baseline.

If the bridge runs differ meaningfully from the historical distributions, report
both baselines and decide whether additional contemporary GPT-only runs are
needed before making strong efficiency claims.

## Token Accounting

Because the harness invokes each model role separately:

- GPT planning and GPT integration tokens count as GPT implementation usage.
- Spark leaf tokens count as Spark implementation usage.
- Judge tokens are tracked separately from implementation tokens.
- Implementation-only usage and judge-inclusive usage should both be preserved.
- `turn.completed.usage` from each JSONL stream remains the source of token
  accounting evidence.

This design should avoid relying on the weaker assumption that a GPT-only solo
run consumes the same number of GPT tokens as a GPT root coordinating multiple
Spark leaves.

## Primary Metrics

- RuleLedger v3 quality score.
- Hidden test pass rate and score components.
- Total implementation tokens.
- GPT implementation tokens.
- Spark implementation tokens.
- Judge-inclusive total tokens.
- Quality per total implementation token.
- Quality per GPT implementation token.
- Quality per Spark implementation token.
- Wall-clock duration.
- Compile, test, timeout, and invalid-output failure rates.
- Root integration burden after Spark outputs.
- Proposal adoption rate or Spark diff adoption rate.
- Final diff size and changed-file count.

## Primary Comparisons

- Direct edit vs proposal at each GPT-5.5 root reasoning level.
- Direct edit vs proposal aggregated across root reasoning levels.
- Spark-assisted cells vs same-reasoning GPT-only historical baselines.
- Spark-assisted cells vs contemporaneous GPT-only bridge runs as a drift check.
- Token efficiency of Spark-assisted modes against GPT-only baselines.

## Expected Interaction To Watch

Proposal mode may improve with stronger GPT roots because the root can evaluate,
synthesize, and filter Spark suggestions more effectively.

Direct edit mode may help lower-reasoning GPT roots more because Spark performs
more implementation work directly, but it may also introduce more integration
burden, merge conflicts, inconsistent design choices, or repair work.

The interaction between GPT root reasoning and Spark mode is likely to be as
important as the direct edit vs proposal main effect.

## Reporting Notes

- Preserve raw evidence for every run.
- Do not hide failed runs; failures are part of the measurement.
- Label historical GPT-only baselines and contemporary bridge runs clearly.
- Clearly distinguish implementation-only tokens from judge-inclusive tokens.
- Report any token split as exact for this experiment design, because GPT and
  Spark invocations are measured separately.
- Include limitations around small pilot bridge sample sizes and any detected
  drift from the prior 50-run RuleLedger v3 study.
