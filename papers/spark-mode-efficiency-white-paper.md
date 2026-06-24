# Spark Mode Efficiency: Direct Edit vs Proposal Mode

## Abstract

This study tested whether `gpt-5.3-codex-spark` xhigh leaf agents are more
effective when they directly edit the workspace or when they operate in
proposal-only mode and leave final integration to a `gpt-5.5` root. The
benchmark was RuleLedger v3. The main matrix used four GPT-5.5 root reasoning
levels (`low`, `medium`, `high`, `xhigh`) crossed with two Spark leaf modes
(`direct`, `proposal`), with five measured runs per cell. Each Spark-assisted
run used six Spark xhigh leaves and separate `codex exec --json` invocations
for root planning, Spark leaves, and root integration, which made GPT and Spark
implementation token accounting exact rather than estimated.

The main result is that direct edit mode is the better default. Across the
20 main direct-edit runs, mean quality was `0.702291`, versus `0.592326` for
the 20 proposal-mode runs. Direct edit also used fewer average implementation
tokens: about `2.76M` total tokens per run versus `3.02M` for proposal mode.
Direct edit won clearly for `low`, `medium`, and `high` roots. The important
exception was the `xhigh` root, where proposal mode narrowly beat direct edit
on quality (`0.835775` vs `0.832860`) while using fewer GPT tokens and fewer
total implementation tokens, but more Spark tokens.

## Research Question

The experiment asked how to use Codex Spark most effectively when Spark token
usage is budgeted separately from GPT model usage. The central comparison was:

- Direct edit mode: Spark leaves can write into their own worktrees and return
  concrete implementation diffs or artifacts.
- Proposal mode: Spark leaves are read-only and return recommendations or patch
  proposals; the GPT root performs the final implementation.

The design also tested whether the answer changes as the GPT-5.5 root moves
from `low` to `xhigh` reasoning.

## Experimental Design

The experiment plan lives at
`plans/experiments/spark-mode-efficiency-direct-vs-proposal.md`.

The pilot config, `configs/spark_mode_efficiency_pilot.yaml`, ran:

- 2 GPT-only bridge runs per root reasoning level.
- 2 Spark-assisted runs per root reasoning x Spark mode cell.
- 24 total pilot runs.

The main config, `configs/spark_mode_efficiency_main.yaml`, ran:

- 5 Spark-assisted runs per root reasoning x Spark mode cell.
- 8 Spark-assisted cells.
- 40 total main runs.

Both pilot and main used:

- Implementation jobs: `5`
- Judge jobs: `4`
- Benchmark: RuleLedger v3
- Judge: `gpt-5.5` xhigh
- Spark leaves: six `gpt-5.3-codex-spark` xhigh leaves

The main experiment was repaired with `-Resume` and `-RerunFailed` after an
initial set of judge JSON parse failures. The final validation status for both
pilot and main is `passed`.

## Measurement

The harness invoked each model role separately:

1. GPT-5.5 root planning.
2. Six Spark xhigh leaf runs.
3. GPT-5.5 root integration.
4. GPT-5.5 judge.

Implementation token accounting is exact for this experiment because GPT and
Spark usage came from separate JSONL event streams. GPT planning and root
integration tokens count as GPT implementation usage. Spark leaf tokens count
as Spark implementation usage. Judge tokens are tracked separately and are not
included in the implementation-token efficiency figures below.

Historical GPT-only baselines come from the completed 50-run RuleLedger v3
study for each GPT-5.5 reasoning level. The contemporaneous bridge runs were
used as a drift check rather than as the official baseline because they contain
only two runs per reasoning level.

## Main Results

The table below uses only the official 40-run main Spark-assisted matrix.

| Root reasoning | Mode | Runs | Quality mean | GPT tokens mean | Spark tokens mean | Total impl tokens mean | Quality/GPT token |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| low | direct | 5 | 0.516768 | 782,597 | 597,255 | 1,379,852 | 7.36772e-7 |
| low | proposal | 5 | 0.471714 | 1,224,262 | 820,204 | 2,044,466 | 4.17192e-7 |
| medium | direct | 5 | 0.632449 | 1,449,335 | 613,971 | 2,063,306 | 4.73829e-7 |
| medium | proposal | 5 | 0.463412 | 1,842,329 | 833,818 | 2,676,147 | 2.60694e-7 |
| high | direct | 5 | 0.827086 | 2,581,375 | 630,694 | 3,212,069 | 3.25508e-7 |
| high | proposal | 5 | 0.598405 | 2,597,205 | 746,058 | 3,343,263 | 2.70813e-7 |
| xhigh | direct | 5 | 0.832860 | 3,774,608 | 621,630 | 4,396,238 | 2.49780e-7 |
| xhigh | proposal | 5 | 0.835775 | 3,128,829 | 888,597 | 4,017,426 | 2.69236e-7 |

Across all root reasoning levels, direct edit mode had:

- `+0.109964` higher mean quality than proposal mode.
- `51,177` fewer GPT implementation tokens per run.
- `206,282` fewer Spark implementation tokens per run.
- `257,459` fewer total implementation tokens per run.
- Higher quality per GPT implementation token and per total implementation
  token.

## Direct Edit vs Proposal by Root Reasoning

Proposal-minus-direct deltas from the main matrix:

| Root reasoning | Quality delta | GPT token delta | Spark token delta | Efficiency delta |
| --- | ---: | ---: | ---: | ---: |
| low | -0.045054 | +441,665 | +222,949 | -3.1958e-7 |
| medium | -0.169037 | +392,994 | +219,847 | -2.13135e-7 |
| high | -0.228681 | +15,829 | +115,364 | -5.4695e-8 |
| xhigh | +0.002914 | -645,780 | +266,967 | +1.9456e-8 |

Direct edit mode dominates proposal mode for low, medium, and high roots: it is
higher quality and uses fewer total tokens. The `xhigh` result is different.
There, proposal mode is essentially tied on quality but slightly ahead, and it
saves enough GPT tokens to reduce total implementation tokens despite spending
more Spark tokens.

## Spark-Assisted vs GPT-Only Historical Baseline

The historical baseline remains the official GPT-only reference, with 50 runs
per reasoning level. Against that baseline:

| Root reasoning | Mode | Main quality | Historical quality | Quality delta | Main total tokens | Historical tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| low | direct | 0.516768 | 0.433800 | +0.082968 | 1,379,852 | 815,190 |
| low | proposal | 0.471714 | 0.433800 | +0.037914 | 2,044,466 | 815,190 |
| medium | direct | 0.632449 | 0.461959 | +0.170490 | 2,063,306 | 1,389,968 |
| medium | proposal | 0.463412 | 0.461959 | +0.001453 | 2,676,147 | 1,389,968 |
| high | direct | 0.827086 | 0.696050 | +0.131036 | 3,212,069 | 2,612,154 |
| high | proposal | 0.598405 | 0.696050 | -0.097645 | 3,343,263 | 2,612,154 |
| xhigh | direct | 0.832860 | 0.755057 | +0.077803 | 4,396,238 | 3,333,886 |
| xhigh | proposal | 0.835775 | 0.755057 | +0.080717 | 4,017,426 | 3,333,886 |

Direct edit Spark assistance improved mean quality over the historical GPT-only
baseline at every root reasoning level. Proposal mode was more mixed: it
improved low and xhigh, was essentially flat at medium, and underperformed the
historical high baseline.

Token efficiency is less favorable when Spark tokens are counted as part of
total implementation cost. Spark assistance generally raises quality, but it
also raises total implementation tokens. If Spark and GPT tokens are treated as
separate budgets, the more useful efficiency question is often whether Spark can
raise quality without increasing GPT usage too much. On that measure, direct
edit is attractive for low, medium, and high roots, while xhigh proposal is the
notable GPT-saving configuration.

## Bridge Drift Check

The two-run contemporaneous GPT-only bridge sample was small and noisy:

| Reasoning | Bridge quality | Historical quality | Delta |
| --- | ---: | ---: | ---: |
| low | 0.455483 | 0.433800 | +0.021683 |
| medium | 0.219533 | 0.461959 | -0.242425 |
| high | 0.959689 | 0.696050 | +0.263639 |
| xhigh | 0.951578 | 0.755057 | +0.196521 |

This does not cleanly prove that the environment is unchanged. It also does not
justify discarding the 50-run historical baseline. The bridge sample is best
read as a calibration check that flags possible drift or high sampling
variance, especially at medium, high, and xhigh. Strong claims about
Spark-assisted performance relative to GPT-only performance should therefore
keep the historical baseline visible and note this bridge uncertainty.

## Interpretation

The core pattern is consistent with a practical division of labor:

- In direct edit mode, Spark leaves do concrete implementation work before the
  GPT root integrates the result. This appears to help low, medium, and high
  roots by giving the root more finished material and fewer speculative
  recommendations to translate.
- In proposal mode, the GPT root keeps more control. This is not enough to help
  low, medium, or high roots in this benchmark, but the xhigh root appears able
  to turn proposals into a near-best outcome while spending fewer GPT tokens
  than xhigh direct edit.
- Proposal mode consistently spends more Spark tokens than direct edit in this
  design. That is likely because read-only leaves must explain and justify
  proposed work instead of simply producing concrete diffs.

The strongest main-matrix quality results were xhigh proposal (`0.835775`),
xhigh direct (`0.832860`), and high direct (`0.827086`). Those three are close
enough that selection should depend on budget shape:

- If Spark and GPT tokens both matter, high direct edit is the best quality/cost
  compromise among the high-quality cells.
- If GPT tokens are the scarce budget and Spark tokens are cheaper, xhigh
  proposal becomes attractive because it saves GPT tokens relative to xhigh
  direct while maintaining quality.
- If the default policy must be simple, choose direct edit Spark leaves.

## Recommendation

Use direct edit mode as the default for xhigh Spark leaves under GPT-5.5 roots,
especially for `low`, `medium`, and `high` root reasoning. It produced higher
quality and better implementation-token efficiency in three of four reasoning
levels and won the aggregate comparison.

Use proposal mode selectively with an `xhigh` GPT-5.5 root when GPT budget is
the limiting resource and extra Spark usage is acceptable. In this experiment,
xhigh proposal produced the best mean quality by a very small margin and used
about `646k` fewer GPT implementation tokens than xhigh direct, while spending
about `267k` more Spark tokens.

Do not use proposal mode as the general Spark leaf default for this benchmark.
At low, medium, and high root reasoning, proposal mode was lower quality and
more expensive in total implementation tokens.

## Limitations

The main Spark-assisted matrix has five runs per cell. That is enough to reveal
a strong directional pattern, but not enough to settle small differences such
as xhigh proposal versus xhigh direct.

The contemporaneous GPT-only bridge sample has only two runs per reasoning
level. It is useful as a drift signal but not as a replacement for the 50-run
historical GPT-only baseline.

The benchmark is RuleLedger v3. Results may differ for tasks where proposals
are easier to evaluate than code diffs, or where the root has more explicit
merge and adjudication tooling.

The experiment measured exact GPT and Spark implementation token usage for the
staged design, but it does not directly measure opportunity cost, queueing
latency, or budget pricing between model families.

## Reproducibility Notes

Key artifact locations:

- Pilot run: `runs/20260624T023048-spark_mode_efficiency_pilot-pilot`
- Main run: `runs/20260624T053702-spark_mode_efficiency_main-main`
- Main HTML report:
  `runs/20260624T053702-spark_mode_efficiency_main-main/report/report.html`
- Main PDF report:
  `runs/20260624T053702-spark_mode_efficiency_main-main/report/report.pdf`
- Final analysis:
  `runs/analysis/spark_mode_efficiency_final`

Key commands:

```powershell
.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_pilot.yaml -Jobs 5 -JudgeJobs 4 -ExperimentName pilot -StudyId spark-mode-efficiency -BatchId pilot -BatchSequence 1

.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_main.yaml -Jobs 5 -JudgeJobs 4 -ExperimentName main -StudyId spark-mode-efficiency -BatchId main -BatchSequence 2

.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_main.yaml -Jobs 5 -JudgeJobs 4 -Resume 20260624T053702-spark_mode_efficiency_main-main -RerunFailed

python scripts\analyze_spark_mode_efficiency.py --experiment-dir runs\20260624T023048-spark_mode_efficiency_pilot-pilot --experiment-dir runs\20260624T053702-spark_mode_efficiency_main-main --output-dir runs\analysis\spark_mode_efficiency_final
```

Validation evidence:

- Pilot `validation.json`: `passed`
- Main `validation.json`: `passed`
- Analysis rows: `264`
- Focused analysis test: `python -m pytest tests\test_spark_mode_analysis.py -q`
- Full suite: `python -m pytest -q` (`187 passed`)
