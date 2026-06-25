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

The main matrix result is that direct edit mode is the better default. Across
the 20 main direct-edit runs, mean quality was `0.702291`, versus `0.592326`
for the 20 proposal-mode runs. Direct edit also used fewer average
implementation tokens: about `2.76M` total tokens per run versus `3.02M` for
proposal mode. Direct edit won clearly for `low`, `medium`, and `high` roots.

Two follow-up extensions added 15 direct runs and 15 proposal runs at `high`
and `xhigh` root reasoning. Combined with the original main matrix, both
focused comparisons now have 20 direct runs versus 20 proposal runs. In the
larger high sample, direct edit remains higher quality (`0.711964` vs
`0.652004`) and much more token efficient than proposal mode, but the direct
mean is only slightly above the historical 50-run high GPT-only quality mean
(`0.696050`) while using more implementation tokens.

In the larger xhigh sample, direct edit is also slightly higher quality
(`0.733897` vs `0.714206`), while proposal mode uses fewer GPT tokens (`3.64M`
vs `3.88M`) and fewer total implementation tokens (`4.43M` vs `4.49M`) but more
Spark tokens (`0.79M` vs `0.61M`). Both combined xhigh Spark-assisted modes
underperform the historical 50-run xhigh GPT-only quality mean (`0.755057`).

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

The xhigh extension config,
`configs/spark_mode_efficiency_xhigh_extension.yaml`, ran:

- 15 additional xhigh direct runs.
- 15 additional xhigh proposal runs.
- 30 total extension runs.

The high extension config,
`configs/spark_mode_efficiency_high_extension.yaml`, ran:

- 15 additional high direct runs.
- 15 additional high proposal runs.
- 30 total extension runs.

Pilot, main, and the xhigh extension used:

- Implementation jobs: `5`
- Judge jobs: `4`

The high extension used the requested higher concurrency:

- Implementation jobs: `7`
- Judge jobs: `6`

All measured runs used:

- Benchmark: RuleLedger v3
- Judge: `gpt-5.5` xhigh
- Spark leaves: six `gpt-5.3-codex-spark` xhigh leaves

The main experiment was repaired with `-Resume` and `-RerunFailed` after an
initial set of judge JSON parse failures. The xhigh extension also required a
resume after a usage-limit interruption; the repair used a short workspace root
to avoid Windows path length failures during failed implementation refresh.
The high extension also required a usage-limit wait and resume. Final
validation status is `passed` for pilot, main, xhigh extension, and high
extension.

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

## Main Matrix Results

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
higher quality and uses fewer total tokens. The original five-run `xhigh`
result looked different: proposal mode was essentially tied on quality but
slightly ahead, and it saved enough GPT tokens to reduce total implementation
tokens despite spending more Spark tokens. Because that difference was tiny, the
xhigh extension was run to test whether the apparent proposal advantage held.
The original five-run `high` result also deserved a closer look because high
direct was one of the strongest main-matrix cells while high proposal was much
weaker. The high extension tested whether that large high direct advantage held
at 20 runs per Spark mode.

## High Extension Deep Dive

The high extension keeps the high direct-vs-proposal result directionally
intact, but it makes the comparison to historical GPT-only high more cautious.
Combining the original five main high runs per mode with the 15 extension runs
per mode gives:

| Cohort | Mode | Runs | Quality mean | Quality median | Quality sd | GPT tokens mean | Spark tokens mean | Total tokens mean |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| high Spark | direct | 20 | 0.711964 | 0.691288 | 0.157685 | 2,801,135 | 632,108 | 3,433,243 |
| high Spark | proposal | 20 | 0.652004 | 0.592725 | 0.161956 | 2,933,084 | 1,563,753 | 4,496,837 |
| high GPT-only historical | solo | 50 | 0.696050 | 0.684818 | 0.194662 | 2,612,154 | n/a | 2,612,154 |

Proposal-minus-direct deltas for the combined high sample:

| Metric | Delta |
| --- | ---: |
| Quality mean | -0.059960 |
| Hidden correctness mean | -0.044444 |
| Performance mean | -0.056667 |
| Judge mean | -0.123451 |
| GPT implementation tokens mean | +131,950 |
| Spark implementation tokens mean | +931,645 |
| Total implementation tokens mean | +1,063,595 |
| Quality per GPT token mean | -1.91e-8 |
| Quality per total token mean | -5.77e-8 |

The observed high-mode result favors direct edit: it is higher quality, spends
less GPT, spends far less Spark, and uses about `1.06M` fewer total
implementation tokens per run. The quality uncertainty is still meaningful,
though. A bootstrap interval for proposal-minus-direct quality was
approximately `[-0.155647, 0.035416]`, so the 20-run sample supports direct as
the practical high-mode default but not a strong claim about a guaranteed
quality gap.

The extension-only high runs explain why the original five-run gap narrowed.
The 15 added high direct runs averaged `0.673590`, while the 15 added high
proposal runs averaged `0.669870`; in the extension batch alone, quality was
nearly tied, but proposal remained much more expensive (`4.88M` total
implementation tokens versus `3.51M` for direct).

Against the historical high GPT-only baseline:

| Comparison | Quality delta | GPT token delta | Total token delta | Quality/total-token delta |
| --- | ---: | ---: | ---: | ---: |
| high direct minus historical solo | +0.015914 | +188,981 | +821,089 | -7.43e-8 |
| high proposal minus historical solo | -0.044046 | +320,931 | +1,884,684 | -1.32e-7 |

The high Spark-vs-historical result is therefore mixed. Combined high direct is
slightly above the historical high solo quality mean, but the bootstrap interval
for high direct minus historical high quality was approximately `[-0.069460,
0.101787]`. Combined high proposal is below historical high solo, with a
bootstrap interval of approximately `[-0.130477, 0.043197]`. Both Spark-assisted
high modes use more total implementation tokens than historical GPT-only high,
so GPT-only high remains the cleaner token-efficiency baseline. If Spark is a
separate and cheaper budget, high direct is still the better Spark-assisted high
configuration.

## Xhigh Extension Deep Dive

The xhigh extension changes the xhigh interpretation. Combining the original
five main xhigh runs per mode with the 15 extension runs per mode gives:

| Cohort | Mode | Runs | Quality mean | Quality median | Quality sd | GPT tokens mean | Spark tokens mean | Total tokens mean |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| xhigh Spark | direct | 20 | 0.733897 | 0.693232 | 0.151871 | 3,877,968 | 610,527 | 4,488,495 |
| xhigh Spark | proposal | 20 | 0.714206 | 0.611879 | 0.162431 | 3,636,127 | 793,673 | 4,429,799 |
| xhigh GPT-only historical | solo | 50 | 0.755057 | 0.709206 | 0.171127 | 3,333,886 | n/a | 3,333,886 |

Proposal-minus-direct deltas for the combined xhigh sample:

| Metric | Delta |
| --- | ---: |
| Quality mean | -0.019691 |
| Hidden correctness mean | -0.035243 |
| Performance mean | 0.000000 |
| Judge mean | -0.010640 |
| GPT implementation tokens mean | -241,841 |
| Spark implementation tokens mean | +183,146 |
| Total implementation tokens mean | -58,696 |
| Quality per GPT token mean | +9.57e-9 |
| Quality per total token mean | -1.68e-9 |

The quality difference is small relative to run-to-run variance. A bootstrap
interval for proposal-minus-direct quality was approximately `[-0.113342,
0.076207]`, so this extension does not support a strong claim that either
xhigh Spark mode is meaningfully higher quality than the other. The practical
distinction is budget shape: direct edit has the higher observed mean quality
and better hidden correctness, while proposal mode saves GPT tokens and total
tokens by spending more Spark tokens.

Against the historical xhigh GPT-only baseline:

| Comparison | Quality delta | GPT token delta | Total token delta | Quality/total-token delta |
| --- | ---: | ---: | ---: | ---: |
| xhigh direct minus historical solo | -0.021161 | +544,083 | +1,154,609 | -7.26e-8 |
| xhigh proposal minus historical solo | -0.040852 | +302,241 | +1,095,914 | -7.42e-8 |

This is the most important update from the extension. The original five-run
main matrix made both xhigh Spark-assisted cells look slightly better than the
historical xhigh GPT-only mean. The expanded 20-run xhigh comparison reverses
that impression: both xhigh Spark-assisted modes are slightly lower quality
than historical xhigh solo and use substantially more total implementation
tokens. The direct-vs-proposal choice at xhigh is therefore secondary to the
larger finding that this staged six-leaf Spark pattern did not beat xhigh GPT
solo on RuleLedger v3.

## Spark-Assisted vs GPT-Only Historical Baseline

The historical baseline remains the official GPT-only reference, with 50 runs
per reasoning level. The original five-run-per-cell main matrix compared
against that baseline as follows:

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

In the original main matrix, direct edit Spark assistance improved mean quality
over the historical GPT-only baseline at every root reasoning level. Proposal
mode was more mixed: it improved low and xhigh, was essentially flat at medium,
and underperformed the historical high baseline. After the high and xhigh
extensions, that original five-run statement should be read as hypothesis
generation, not as settled evidence. The better-supported high result is that
combined high direct is only slightly above historical high solo quality while
using more total implementation tokens, and combined high proposal is below
historical high solo. The better-supported xhigh result is that both
Spark-assisted xhigh modes are below the historical xhigh solo mean.

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
  GPT root integrates the result. This appears most useful as a Spark-mode
  choice: direct edit beats proposal mode at low, medium, high, and expanded
  xhigh in observed quality. The high extension makes the GPT-only comparison
  more cautious, because high direct no longer shows a large quality margin over
  historical high solo.
- In proposal mode, the GPT root keeps more control. At xhigh, proposal mode is
  no longer the quality leader after the extension, but it remains the
  GPT-saving option.
- Proposal mode consistently spends more Spark tokens than direct edit in this
  design. That is likely because read-only leaves must explain and justify
  proposed work instead of simply producing concrete diffs.

The strongest original main-matrix quality results were xhigh proposal
(`0.835775`), xhigh direct (`0.832860`), and high direct (`0.827086`). The
xhigh extension shows why those five-run xhigh cells should be treated
cautiously: the added xhigh runs were lower on average, pulling the combined
xhigh means to `0.733897` direct and `0.714206` proposal. The high extension
does the same for high direct: the combined high direct mean is `0.711964`, not
the original main-cell `0.827086`, while combined high proposal is `0.652004`.

- If Spark and GPT tokens both matter, high direct edit is the best quality/cost
  compromise among the expanded Spark-assisted high cells, but GPT-only high is
  the better total-token baseline.
- If GPT tokens are the scarce budget and Spark tokens are cheaper, xhigh
  proposal remains attractive relative to xhigh direct because it saves about
  `242k` GPT implementation tokens per run in the combined xhigh sample.
- If the default policy must be simple, choose direct edit Spark leaves.

## Recommendation

Use direct edit mode as the default for xhigh Spark leaves under GPT-5.5 roots,
especially for `low`, `medium`, and `high` root reasoning. It produced higher
observed quality than proposal mode in the main matrix and in both expanded
high and xhigh comparisons.

For `high` roots, prefer direct edit over proposal mode when using this staged
six-Spark-leaf topology. In the combined high sample, proposal mode scored about
`0.0600` lower on quality and used about `1.06M` more total implementation
tokens per run. However, compare high direct against GPT-only high before
adopting Spark assistance solely for quality: the expanded high direct quality
mean is only `0.0159` above the historical high solo mean and is worse on total
token efficiency.

Use proposal mode selectively with an `xhigh` GPT-5.5 root when GPT budget is
the limiting resource and extra Spark usage is acceptable. In the combined
xhigh sample, proposal mode used about `242k` fewer GPT implementation tokens
and about `59k` fewer total implementation tokens than xhigh direct, while
spending about `183k` more Spark tokens and scoring about `0.0197` lower on
quality.

For xhigh specifically, prefer GPT-only xhigh before adopting this staged
six-Spark-leaf pattern. The 50-run historical xhigh solo baseline remains
higher quality and more token efficient than either combined xhigh Spark mode
in this experiment.

Do not use proposal mode as the general Spark leaf default for this benchmark.
At low, medium, and high root reasoning, proposal mode was lower quality and
more expensive in total implementation tokens. The expanded high sample makes
that especially clear on cost.

## Limitations

The main Spark-assisted matrix has five runs per cell. That is enough to reveal
a strong directional pattern for the original matrix, but the high and xhigh
extensions showed that five runs were not enough to settle every root-reasoning
interaction.

The combined high and xhigh comparisons each have 20 runs per Spark mode. That
is stronger than the original five-run cells, but quality intervals still
overlap. The best-supported high claim is practical rather than absolute:
direct edit is the better high Spark mode, but GPT-only high remains the
cleaner total-token baseline. The best-supported xhigh claim is similarly
modest: direct edit is slightly higher quality in the observed sample, proposal
mode spends fewer GPT and total tokens, and both Spark-assisted modes trail the
historical xhigh solo mean.

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
- Xhigh extension run:
  `runs/20260624T105944-spark_mode_efficiency_xhigh_extension-xhigh_extension`
- High extension run:
  `runs/20260624T220413-spark_mode_efficiency_high_extension-high_extension_j7_j6`
- Main HTML report:
  `runs/20260624T053702-spark_mode_efficiency_main-main/report/report.html`
- Main PDF report:
  `runs/20260624T053702-spark_mode_efficiency_main-main/report/report.pdf`
- Xhigh extension PDF report:
  `runs/20260624T105944-spark_mode_efficiency_xhigh_extension-xhigh_extension/report/report.pdf`
- High extension PDF report:
  `runs/20260624T220413-spark_mode_efficiency_high_extension-high_extension_j7_j6/report/report.pdf`
- Final analysis:
  `runs/analysis/spark_mode_efficiency_final`

Key commands:

```powershell
.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_pilot.yaml -Jobs 5 -JudgeJobs 4 -ExperimentName pilot -StudyId spark-mode-efficiency -BatchId pilot -BatchSequence 1

.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_main.yaml -Jobs 5 -JudgeJobs 4 -ExperimentName main -StudyId spark-mode-efficiency -BatchId main -BatchSequence 2

.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_main.yaml -Jobs 5 -JudgeJobs 4 -Resume 20260624T053702-spark_mode_efficiency_main-main -RerunFailed

.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_xhigh_extension.yaml -Jobs 5 -JudgeJobs 4 -ExperimentName xhigh_extension -StudyId spark-mode-efficiency -BatchId xhigh-extension -BatchSequence 3

.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_xhigh_extension.yaml -Jobs 5 -JudgeJobs 4 -WorkspaceRoot C:\cstws -Resume 20260624T105944-spark_mode_efficiency_xhigh_extension-xhigh_extension -RerunFailed

.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_high_extension.yaml -Jobs 7 -JudgeJobs 6 -WorkspaceRoot C:\cstws -ExperimentName high_extension_j7_j6 -StudyId spark-mode-efficiency -BatchId high-extension-j7-j6 -BatchSequence 4

.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_high_extension.yaml -Jobs 7 -JudgeJobs 6 -WorkspaceRoot C:\cstws -Resume 20260624T220413-spark_mode_efficiency_high_extension-high_extension_j7_j6 -RerunFailed

python scripts\analyze_spark_mode_efficiency.py --experiment-dir runs\20260624T023048-spark_mode_efficiency_pilot-pilot --experiment-dir runs\20260624T053702-spark_mode_efficiency_main-main --experiment-dir runs\20260624T105944-spark_mode_efficiency_xhigh_extension-xhigh_extension --experiment-dir runs\20260624T220413-spark_mode_efficiency_high_extension-high_extension_j7_j6 --output-dir runs\analysis\spark_mode_efficiency_final
```

Validation evidence:

- Pilot `validation.json`: `passed`
- Main `validation.json`: `passed`
- Xhigh extension `validation.json`: `passed`
- High extension `validation.json`: `passed`
- Analysis rows: `324`
- Focused analysis test: `python -m pytest tests\test_spark_mode_analysis.py -q`
- Full suite: `python -m pytest -q` (`191 passed`)
