# Spark Mode Efficiency: Direct Edit vs Proposal Mode

Benchmarking Spark subagent write modes under GPT-5.5 coordinators

By Adam Owada, with Codex<br>
June 25, 2026

## Abstract

This study evaluates whether `gpt-5.3-codex-spark` coding subagents are more
effective when they directly edit code or when they only propose changes for a
`gpt-5.5` coordinator to implement. The benchmark is RuleLedger v3
([RuleLedger v3 white paper](ruleledger-v3-white-paper.md)), a TypeScript and
Python software-engineering task built around event replay, billing semantics,
cross-language parity, hidden tests, and maintainability.

The strongest observed quality result was solo GPT-5.5 xhigh: `0.755` mean
composite quality. Spark-assisted xhigh did not improve on that result.
Direct-edit Spark leaves had higher observed mean composite quality than
proposal-only leaves at every root reasoning level, but only the medium
direct-vs-proposal gap was clearly separated in the observed sample. Medium
direct was the strongest Spark-assisted lift over the same reasoning level
(`0.622` vs `0.462` for medium solo), while high solo remained better than
medium direct on both quality and aggregate GPT-token efficiency.

The practical result is straightforward: use direct-edit Spark leaves when a
Spark-assisted topology is appropriate, prefer solo xhigh for maximum quality,
and prefer high solo over medium direct when aggregate GPT-token efficiency is
the main decision criterion.

## Executive Summary

- **Best observed quality:** solo GPT-5.5 xhigh scored `0.755`.
- **Best Spark-assisted same-reasoning lift:** medium direct scored `0.622`,
  compared with `0.462` for medium solo.
- **Best default Spark write mode:** direct edit. It had higher observed mean
  composite quality than proposal mode at low, medium, high, and xhigh.
- **Best token-efficient high-quality solo choice:** high solo. It scored
  `0.696` and had higher aggregate quality per GPT token than medium direct.
- **Proposal mode's role:** useful for review-only or governance-constrained
  workflows, but not the default implementation mode in this benchmark.
- **Total-token view:** when GPT and Spark tokens are counted equally, solo
  runs were generally more token efficient than Spark-assisted runs.

## Recommendation Matrix

| Scenario | Recommendation | Why | Caution |
| --- | --- | --- | --- |
| Maximum code quality | Solo GPT-5.5 xhigh | Highest observed mean quality: `0.755` | Uses the most GPT reasoning budget among solo modes |
| Strong quality with good aggregate GPT-token efficiency | Solo GPT-5.5 high | `0.696` quality and `2.66466e-7` quality/GPT token by ratio-of-means | Lower quality than xhigh solo |
| Medium root is fixed and Spark budget is useful | Medium root + direct Spark leaves | `+0.160` quality over medium solo | High solo is still better on quality and aggregate GPT-token efficiency |
| Spark topology is required | Direct-edit Spark leaves | Higher observed mean composite quality than proposal at all four root levels | Low and xhigh direct/proposal gaps are small |
| Review-only or edit-restricted workflow | Proposal-only Spark leaves | Leaves can inspect, propose patches, and produce review notes without writing | Usually not cheaper in measured tokens; xhigh proposal only saves GPT tokens versus xhigh direct |

## Terminology

This paper uses the following terms:

| Term | Meaning |
| --- | --- |
| GPT-5.5 coordinator | The root agent. It plans the run, integrates subagent outputs, and owns the final submitted workspace. |
| Spark leaf | A `gpt-5.3-codex-spark` worker assigned one slice of the implementation or review task. |
| Reasoning level | A runtime reasoning-effort setting: `low`, `medium`, `high`, or `xhigh`. It is not a model size, temperature, or context-length label. |
| Direct edit mode | Spark leaves work in isolated writable git worktrees and return diffs for the coordinator to inspect. |
| Proposal mode | Spark leaves run read-only and return findings, proposed patches, tests, and integration notes. |
| GPT tokens | GPT-5.5 implementation tokens. For Spark-assisted runs, this means coordinator planning and integration tokens only. |
| Spark tokens | Spark leaf implementation tokens. |
| Total tokens | GPT implementation tokens plus Spark implementation tokens. Judge tokens are excluded from efficiency tables. |

## Benchmark Task in Plain English

RuleLedger v3 is a subscription-ledger implementation benchmark. The model must
read event streams, normalize events, replay account state, compute billing and
entitlements, export deterministic reports, and preserve compatibility with
earlier public APIs. The task has both TypeScript and Python surfaces, and the
two implementations must agree on behavior.

The hard part is global consistency. A local fix that passes one public test can
still fail hidden cases if summaries, reports, billing, parity outputs, and
replay digests use different state-transition logic. RuleLedger v3 therefore
rewards implementations that build one coherent replay model and apply it
across the whole codebase.

## Topology

The Spark-assisted topology is staged:

```text
Frozen starter project
  -> GPT-5.5 coordinator planning stage
  -> six Spark leaf stages
       - direct mode: isolated writable git worktrees with diffs
       - proposal mode: read-only inspection with proposals
  -> GPT-5.5 coordinator integration stage
  -> public tests, hidden tests, scoring, and judge assessment
```

Each Spark-assisted run used exactly six xhigh Spark leaves:

| Leaf | Responsibility |
| --- | --- |
| 1 | TypeScript parsing, normalization, views, and migration compatibility |
| 2 | TypeScript replay, billing, reporting, performance, and API integration |
| 3 | Python parsing, normalization, views, and migration compatibility |
| 4 | Python replay, billing, reporting, performance, and API integration |
| 5 | Cross-language parity, fixtures, public tests, and regression review |
| 6 | Adversarial review for localization, maintainability, performance, and hidden-test risk |

The prompt shown to direct-edit leaves described their environment this way:

```text
You are in direct edit mode inside an isolated leaf workspace. You may edit
files in this copy. The root integration run will inspect your diff and decide
what to land in the final measured workspace.
```

Proposal-only leaves were told:

```text
You are in proposal mode. Do not edit files. Inspect the visible workspace and
return concrete findings, proposed patches, tests, and integration notes.
```

The implementation submitted for scoring was always the final workspace
produced by the GPT-5.5 coordinator integration stage.

## Experiment Design

The official comparison set contains `360` scored implementation runs:

| Group | Cells | Runs per cell | Rows |
| --- | ---: | ---: | ---: |
| Solo GPT-5.5 | 4 reasoning levels | 50 | 200 |
| Spark direct | 4 reasoning levels | 20 | 80 |
| Spark proposal | 4 reasoning levels | 20 | 80 |

The final analysis artifact ingested `384` rows for audit. The extra `24` rows
are pilot and bridge diagnostics and are excluded from the headline comparison
tables.

Spark-assisted variables:

- GPT-5.5 coordinator reasoning: `low`, `medium`, `high`, `xhigh`.
- Spark leaf model: `gpt-5.3-codex-spark`.
- Spark leaf reasoning: xhigh.
- Spark leaf count: six.
- Spark mode: direct edit or proposal-only.
- Judge: GPT-5.5 xhigh.

Solo comparison group:

- GPT-5.5 solo runs from the RuleLedger v3 benchmark testing.
- Reasoning levels: `low`, `medium`, `high`, `xhigh`.
- Runs per reasoning level: 50.

A two-run contemporaneous GPT-only bridge was kept as a drift check. It was
too small and noisy to replace the 50-run solo comparison group: bridge quality
deltas versus the solo set were `+0.022` for low, `-0.242` for medium,
`+0.264` for high, and `+0.197` for xhigh. No drift adjustment was applied.

## Measurement

### Quality Score

Quality is a 0 to 1 composite score from `configs/scoring_v3.yaml`:

| Component | Weight | Meaning |
| --- | ---: | --- |
| Hidden correctness | 0.50 | Correctness on frozen private RuleLedger v3 cases, excluding parity and performance categories |
| Hidden parity | 0.15 | TypeScript/Python agreement on hidden parity checks |
| Performance | 0.10 | Performance behavior on hidden workloads |
| Judge | 0.22 | GPT-5.5 xhigh assessment of source, diffs, logs, public checks, and hidden-result summaries |
| Minimality | 0.03 | Production LOC minimality signal relative to the configured target |

The judge was topology-blind: it was instructed not to infer or reward the
producing agent arrangement. It did see implementation evidence, public logs,
diffs, and hidden-result summaries, but it did not see private hidden case
payloads. If the judge returned numeric `correctness_score`, `parity_score`,
`maintainability_score`, and `test_evidence_score` fields, the harness averaged
those four fields. If strict JSON parsing failed, the judge component scored
zero.

### Token Efficiency

The paper reports two efficiency estimands:

| Metric | Formula | Interpretation |
| --- | --- | --- |
| Ratio of means | `mean(quality) / mean(tokens)` | Aggregate quality per aggregate token spend. This is the primary efficiency metric in tables and recommendations. |
| Mean of ratios | `mean(quality / tokens)` | Average per-run efficiency. Useful as a sensitivity check, but sensitive to very low-token runs. |

The generated analysis artifacts include fields named `quality_per_*_mean`.
Those fields are means of per-run ratios. The tables in this paper recompute
ratio-of-means from the displayed quality and token means so the table math is
directly reproducible.

This distinction matters. For the narrow GPT-token-efficiency comparison
between high solo and medium direct:

| Comparison | High solo | Medium direct | Winner |
| --- | ---: | ---: | --- |
| Ratio of means | `2.66466e-7` | `2.55230e-7` | High solo |
| Mean of ratios | `2.88289e-7` | `3.00435e-7` | Medium direct |

Because the winner changes, that comparison is metric-sensitive. The paper uses
ratio-of-means for recommendations because it best matches aggregate budget
planning. The mean-of-ratios sensitivity check keeps the conclusion honest:
medium direct is competitive on GPT-token efficiency, but high solo has higher
quality and a narrow aggregate-efficiency lead.

## Results at a Glance

| Root reasoning | Solo quality / total tokens | Direct quality / total tokens | Proposal quality / total tokens | Primary read |
| --- | ---: | ---: | ---: | --- |
| low | `0.434` / `0.815M` | `0.482` / `2.917M` | `0.472` / `3.100M` | Spark helps slightly, at high token cost |
| medium | `0.462` / `1.390M` | `0.622` / `3.843M` | `0.529` / `4.320M` | Direct is the strongest same-level Spark lift |
| high | `0.696` / `2.612M` | `0.712` / `3.433M` | `0.652` / `4.497M` | Direct has higher observed mean; solo remains cleaner |
| xhigh | `0.755` / `3.334M` | `0.734` / `4.488M` | `0.714` / `4.430M` | Solo xhigh has the best observed mean |

## Detailed Findings

### Low: Spark Helps Slightly, at High Token Cost

Low direct had higher observed mean composite quality than low solo:
`0.482` versus `0.434`. Low proposal scored `0.472`. The direct-vs-proposal
quality gap was small: `+0.010` in favor of direct. Low proposal also had the
higher median quality and hidden correctness, so the low direct result should
be read as an observed mean result, not a robust domination claim.

Token cost is the main issue. Low direct used `2.917M` total implementation
tokens versus `0.815M` for low solo. Low direct is useful only when the quality
lift is worth a large additional Spark spend.

### Medium: Direct Edit Is the Strongest Spark Case

Medium direct is the strongest same-reasoning Spark-assisted result. It scored
`0.622`, compared with `0.462` for medium solo and `0.529` for medium
proposal. The medium direct-vs-proposal quality delta was `+0.093` for direct,
and it used fewer GPT, Spark, and total implementation tokens than medium
proposal.

This does not mean medium direct should replace high solo. High solo scored
`0.696`, which is `0.074` higher than medium direct, and high solo narrowly
leads by aggregate GPT-token efficiency. Medium direct is best framed as a way
to improve a medium-root topology when Spark budget or parallel search is
valuable, not as the default substitute for raising the GPT reasoning level.

### High: Direct Leads the Spark Comparison, Solo Remains Cleaner

High direct scored `0.712`, high proposal scored `0.652`, and high solo scored
`0.696`. The observed mean favors high direct over high solo by `+0.016`, but
that gap is small relative to run-to-run variance. High solo remains cleaner on
total tokens: `2.612M` versus `3.433M` for high direct.

The high direct-vs-proposal comparison is more practically useful. Direct used
about `132k` fewer GPT tokens, `932k` fewer Spark tokens, and `1.064M` fewer
total tokens per run than proposal while also scoring higher on observed mean
quality.

### Xhigh: Solo GPT-5.5 Has the Best Observed Mean

Solo xhigh had the best observed mean quality in the study: `0.755`. Xhigh
direct scored `0.734`; xhigh proposal scored `0.714`. The direct-vs-proposal
quality gap was small (`+0.020` for direct), and the broader result is that
neither Spark-assisted xhigh mode improved on solo xhigh.

Xhigh proposal saved about `242k` GPT tokens and `59k` total tokens relative to
xhigh direct, but it did not save GPT tokens relative to xhigh solo. Xhigh
proposal is only attractive when a Spark-assisted xhigh topology is already
required and lower coordinator-token use versus xhigh direct is worth the
quality drop.

## Direct Edit vs Proposal Mode

Direct edit had higher observed mean composite quality than proposal mode at
all four root reasoning levels:

| Root | Direct minus proposal quality | Approx. bootstrap interval | Interpretation |
| --- | ---: | ---: | --- |
| low | `+0.010` | `[-0.080, +0.098]` | Small and noisy |
| medium | `+0.093` | `[+0.008, +0.177]` | Clearest direct-edit advantage |
| high | `+0.060` | `[-0.035, +0.156]` | Directionally favors direct |
| xhigh | `+0.020` | `[-0.076, +0.113]` | Small and noisy |

The stronger practical case for direct edit is token use. At low, medium, and
high, direct edit used fewer GPT tokens, fewer Spark tokens, and fewer total
tokens than proposal mode. Proposal mode used more Spark tokens at every root
reasoning level.

| Root | GPT token delta, direct minus proposal | Spark token delta | Total token delta |
| --- | ---: | ---: | ---: |
| low | `-41,883` | `-140,896` | `-182,779` |
| medium | `-72,324` | `-404,427` | `-476,751` |
| high | `-131,950` | `-931,645` | `-1,063,595` |
| xhigh | `+241,841` | `-183,146` | `+58,696` |

Proposal mode is therefore best treated as a review/governance mode. It gives
read-only workers a structured way to inspect code, propose patches, and write
integration notes. It was not a cheaper implementation strategy in this
benchmark except for the narrow xhigh-proposal-versus-xhigh-direct total-token
comparison.

## Why Direct Edit Helped

Direct edit gave the coordinator executable diffs. Even when the coordinator
did not accept a leaf's patch wholesale, it could inspect concrete code, tests,
and implementation choices. Proposal mode required an extra translation step:
the leaf translated implementation work into advice, then the coordinator
translated that advice back into code.

That translation step showed up in token usage. Proposal leaves often spent
more tokens explaining findings and proposed patches, while the coordinator
still had to implement the final changes. Direct edit gave the coordinator a
more compact integration substrate.

## Why Solo Won at Xhigh

RuleLedger v3 rewards a single coherent replay model across TypeScript,
Python, billing, reports, summaries, and parity checks. At xhigh, solo GPT-5.5
had the best observed mean, suggesting that the extra reasoning budget was
enough to keep the global model unified without subagent coordination.

The staged Spark topology decomposed the work into useful local perspectives,
but it also fragmented context. The coordinator had to reconcile partial diffs,
overlapping proposals, and parity risks. At medium, that extra search helped.
At xhigh, the observed benefit did not overcome the coordination cost.

## Practical Guidance for Developers

Use the following heuristics for RuleLedger-like tasks:

| Goal | Use | Rationale |
| --- | --- | --- |
| Highest code quality | Solo GPT-5.5 xhigh | Best observed mean quality |
| High quality with strong aggregate GPT-token efficiency | Solo GPT-5.5 high | Higher quality and aggregate GPT efficiency than medium direct |
| Improve a medium-root workflow using Spark budget | Medium direct | Largest Spark-assisted lift over the same reasoning level |
| Use Spark subagents by default | Direct edit | Better observed mean quality and token profile than proposal in most cells |
| Review-only constraints | Proposal mode | Good fit when workers must not write, but not a measured cost advantage |

The strongest positive Spark story is specific: direct-edit Spark leaves can
materially improve a medium-root workflow. The strongest caution is equally
important: once the root is already xhigh, this six-leaf Spark topology did not
exceed solo GPT-5.5 xhigh.

## Limitations

- The benchmark is RuleLedger v3. Results may differ for tasks that are more
  modular, less parity-sensitive, or easier to split across workers.
- The solo comparison group has 50 runs per reasoning level; each
  Spark-assisted direct/proposal cell has 20 runs.
- The solo comparison group and Spark-assisted groups were not all run in one
  fully contemporaneous randomized batch. The two-run bridge was too noisy to
  support a drift adjustment.
- All Spark leaves used xhigh reasoning. The experiment does not test lower
  Spark reasoning levels or mixed Spark reasoning policies.
- The topology is fixed: one GPT coordinator, six Spark leaves, and one GPT
  integration pass. Deeper topologies, fewer leaves, or stronger merge tooling
  could change the result.
- Elapsed seconds are per-run harness measurements and are affected by batch
  parallelism and scheduler conditions. They are not a clean interactive
  latency endpoint.
- Token counts are cost inputs, not prices. GPT and Spark tokens may have
  different pricing, quotas, and opportunity costs.

## Appendix A: Detailed Quality Table

| Root | Mode | Runs | Quality mean | Quality median | Quality sd | Hidden correctness | Hidden parity | Performance | Judge |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| low | solo | 50 | 0.433800 | 0.447182 | 0.181064 | 0.363958 | 0.531111 | 0.556000 | 0.393869 |
| low | direct | 20 | 0.482419 | 0.455320 | 0.137152 | 0.400174 | 0.602778 | 0.611667 | 0.457950 |
| low | proposal | 20 | 0.472281 | 0.479403 | 0.152909 | 0.424305 | 0.527778 | 0.543334 | 0.439217 |
| medium | solo | 50 | 0.461959 | 0.480347 | 0.175457 | 0.409375 | 0.505556 | 0.515334 | 0.459012 |
| medium | direct | 20 | 0.621764 | 0.575937 | 0.160138 | 0.571007 | 0.727778 | 0.710000 | 0.575134 |
| medium | proposal | 20 | 0.528952 | 0.488858 | 0.114302 | 0.438889 | 0.661111 | 0.663334 | 0.522185 |
| high | solo | 50 | 0.696050 | 0.684818 | 0.194662 | 0.674375 | 0.734445 | 0.738000 | 0.683359 |
| high | direct | 20 | 0.711964 | 0.691288 | 0.157685 | 0.679687 | 0.775000 | 0.775000 | 0.698229 |
| high | proposal | 20 | 0.652004 | 0.592725 | 0.161956 | 0.635243 | 0.736111 | 0.718333 | 0.574779 |
| xhigh | solo | 50 | 0.755057 | 0.709206 | 0.171127 | 0.739375 | 0.791111 | 0.800000 | 0.752072 |
| xhigh | direct | 20 | 0.733897 | 0.693232 | 0.151871 | 0.720313 | 0.750000 | 0.750000 | 0.750591 |
| xhigh | proposal | 20 | 0.714206 | 0.611878 | 0.162431 | 0.685069 | 0.750000 | 0.750000 | 0.739951 |

## Appendix B: Detailed Token Table

Efficiency columns use ratio-of-means.

| Root | Mode | Runs | GPT tokens | Spark tokens | Total tokens | Quality/GPT token | Quality/total token | Elapsed sec |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| low | solo | 50 | 815,190 | n/a | 815,190 | 5.32146e-07 | 5.32146e-07 | 199 |
| low | direct | 20 | 1,444,628 | 1,472,207 | 2,916,835 | 3.33940e-07 | 1.65391e-07 | 494 |
| low | proposal | 20 | 1,486,511 | 1,613,103 | 3,099,614 | 3.17711e-07 | 1.52368e-07 | 541 |
| medium | solo | 50 | 1,389,968 | n/a | 1,389,968 | 3.32352e-07 | 3.32352e-07 | 318 |
| medium | direct | 20 | 2,436,094 | 1,406,665 | 3,842,759 | 2.55230e-07 | 1.61801e-07 | 589 |
| medium | proposal | 20 | 2,508,418 | 1,811,092 | 4,319,510 | 2.10871e-07 | 1.22456e-07 | 628 |
| high | solo | 50 | 2,612,154 | n/a | 2,612,154 | 2.66466e-07 | 2.66466e-07 | 686 |
| high | direct | 20 | 2,801,135 | 632,108 | 3,433,243 | 2.54170e-07 | 2.07374e-07 | 650 |
| high | proposal | 20 | 2,933,084 | 1,563,753 | 4,496,837 | 2.22293e-07 | 1.44992e-07 | 751 |
| xhigh | solo | 50 | 3,333,886 | n/a | 3,333,886 | 2.26480e-07 | 2.26480e-07 | 1,019 |
| xhigh | direct | 20 | 3,877,968 | 610,527 | 4,488,495 | 1.89248e-07 | 1.63506e-07 | 951 |
| xhigh | proposal | 20 | 3,636,127 | 793,673 | 4,429,799 | 1.96419e-07 | 1.61228e-07 | 968 |

## Appendix C: Reproducibility

Key source files:

- Experiment plan: `plans/experiments/spark-mode-efficiency-direct-vs-proposal.md`
- Shared RuleLedger v3 prompt: `prompts/task_common_v3.md`
- Staged Spark prompt: `prompts/task_staged_spark_v3.md`
- Judge prompt: `prompts/judge.md`
- Scoring profile: `configs/scoring_v3.yaml`
- Analysis script: `scripts/analyze_spark_mode_efficiency.py`

Run directories preserve raw JSONL events, stderr logs, prompts, rendered
configs, diffs, test logs, judge output, metadata, scores, and generated HTML
and PDF reports.

Analysis command:

```powershell
python scripts\analyze_spark_mode_efficiency.py `
  --experiment-dir runs\20260624T023048-spark_mode_efficiency_pilot-pilot `
  --experiment-dir runs\20260624T053702-spark_mode_efficiency_main-main `
  --experiment-dir runs\20260625T054133-spark_mode_efficiency_low_medium_extension-low_medium_extension_j7_j6 `
  --experiment-dir runs\20260624T220413-spark_mode_efficiency_high_extension-high_extension_j7_j6 `
  --experiment-dir runs\20260624T105944-spark_mode_efficiency_xhigh_extension-xhigh_extension `
  --output-dir runs\analysis\spark_mode_efficiency_final
```

Validation evidence:

- Final analysis ingested rows: `384`.
- Official comparison rows in this paper: `360`.
- All official run `validation.json` files: `passed`.
- Full repository test suite: `python -m pytest -q` (`193 passed in 11.96s`).
