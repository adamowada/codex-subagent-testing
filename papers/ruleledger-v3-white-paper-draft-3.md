# RuleLedger v3: Measuring Reasoning Effort in LLM Software Engineering

A controlled benchmark for solo GPT-5.5 coding runs

By Adam Owada, with Codex<br>
Benchmark completed June 17, 2026<br>
Draft revised June 25, 2026

## Abstract

RuleLedger v3 is a controlled software-engineering benchmark for measuring whether larger reasoning budgets produce better code on a realistic repair-and-extension task. The benchmark asks a model to implement one coherent subscription-ledger engine across TypeScript and Python, bitemporal replay, account lineage, corrections and voids, exact billing, deterministic reports, performance constraints, and maintainable architecture.

This paper reports a completed 200-run GPT-5.5 study: 50 solo implementation runs each at `low`, `medium`, `high`, and `xhigh` reasoning. The primary endpoint is aggregate quality under the `reasoning_ladder_v3` scoring profile, a 0 to 1 composite weighted toward hidden correctness and cross-language parity. Mean quality was `0.434` for low, `0.462` for medium, `0.696` for high, and `0.755` for xhigh.

The central result is the jump from medium to high reasoning. High exceeded medium by `+0.234` quality points with an approximate 95% interval of `[+0.161, +0.308]`. High and xhigh also strongly outperformed low and medium as groups. Xhigh had the best observed mean quality, hidden correctness, judge score, parity, performance, and tail behavior; no xhigh run fell below `0.4` quality. The adjacent xhigh-over-high mean gap was smaller: `+0.059` with an approximate 95% interval of `[-0.014, +0.132]`.

For RuleLedger v3-like solo coding tasks, high reasoning is the practical quality/cost knee: it captures the main quality transition at materially lower token and wall-clock cost than xhigh. Xhigh is the maximum-quality setting when the user values best observed mean quality and weak-run reduction over cost. The supported benchmark claim is precise: RuleLedger v3 strongly differentiates high/xhigh reasoning from low/medium reasoning, and it strongly differentiates high from medium. Medium-over-low and xhigh-over-high are directional in the observed means, but weaker under the adjacent-interval analysis used here.

## Decision Summary

| Developer or evaluator goal | Recommended setting | Why |
| --- | --- | --- |
| Measure whether reasoning effort matters | RuleLedger v3 across low, medium, high, xhigh | The benchmark produced a clear high/xhigh versus low/medium split |
| Test the main adjacent reasoning jump | Medium vs high | Largest adjacent gap: `+0.234` quality |
| Choose a practical solo coding setting | GPT-5.5 high | Main quality jump with lower cost than xhigh |
| Maximize expected quality | GPT-5.5 xhigh | Highest observed mean quality: `0.755` |
| Reduce weak-run risk | GPT-5.5 xhigh | `0/50` xhigh runs fell below `0.4` quality |
| State adjacent claim boundaries | High > medium is strong; medium > low and xhigh > high are directional | Medium-low and xhigh-high intervals cross zero |

The benchmark's diagnostic force comes from global consistency. Low and medium runs often make useful local progress, but high and xhigh more reliably infer that the task needs one replay model shared across both language implementations and all report surfaces.

## Terminology

| Term | Meaning |
| --- | --- |
| RuleLedger v3 | A synthetic but realistic subscription-ledger repair benchmark with TypeScript and Python implementation surfaces. |
| GPT-5.5 | The implementation model used for all measured solo runs and the judge model used for scoring. |
| Reasoning level | A runtime reasoning-effort setting in the benchmark harness: `low`, `medium`, `high`, or `xhigh`. It is not a model-size or temperature label. |
| Solo run | One GPT-5.5 implementation process works directly on the frozen starter project. No subagents are used. |
| Hidden correctness | Private RuleLedger v3 behavior checks excluding parity and performance categories. |
| Hidden parity | Private checks that TypeScript and Python outputs agree on equivalent cases. |
| Judge score | A GPT-5.5 xhigh review signal over source, diffs, logs, public checks, and hidden-result summaries. |
| Aggregate quality | The weighted 0 to 1 composite score used as the primary endpoint. |
| Tail behavior | The distribution of weak and strong runs, especially threshold counts such as runs below `0.4` or above `0.8` quality. |

## Benchmark Task

RuleLedger v3 is a subscription-ledger implementation benchmark. The visible prompt is an issue brief rather than a complete truth table. Public tests are readable and intentionally incomplete. Hidden tests evaluate whether the model generalizes across behavior families while preserving earlier compatibility behavior.

The measured agent starts from a frozen starter project with both TypeScript and Python implementation surfaces. A strong solution must normalize event streams, replay account state, compute billing and entitlements, export deterministic reports, and preserve compatibility with earlier public APIs. The two language implementations must agree.

The hard part is coherence. A run can make a summary pass while CSV output remains wrong, fix TypeScript while Python drifts, or handle corrections before account merges but fail after lineage changes. RuleLedger v3 rewards implementations that build one canonical replay model and apply it across summaries, reports, parity outputs, replay digests, and performance-sensitive paths.

## Benchmark Design

| Axis | What it tests | Why it challenges reasoning |
| --- | --- | --- |
| Bitemporal replay | Audit-visible and business-effective cutoffs, corrections, voids, and deterministic ordering | Requires temporal reasoning before state application |
| Account lineage | Merges, old identifiers, target resolution, and post-merge actions | Requires durable alias modeling across event history |
| TypeScript/Python parity | Comparable public outputs, CSV serialization, replay digests, and edge-case normalization | Penalizes language-specific shortcuts |
| Exact billing | Proration, money parsing, rounding, invoice dates, and large seat counts | Exposes imprecise numeric handling |
| Regression pressure | v1/v2 public APIs and pass-to-pass behavior remain in scope | Prevents narrow fixes that break earlier contracts |
| Performance | Large generated ledgers and replay/report workloads | Catches nested scans and repeated full-history recomputation |
| Maintainability | Multi-module architecture with thin compatibility boundaries | Rewards code that reviewers can reason about |

RuleLedger v3 was developed after earlier RuleLedger variants proved too easy to separate reasoning levels reliably. Those earlier tasks were meaningful, but models could often localize the visible issue and patch narrowly. Version 3 changed the unit of evaluation from "can the model patch this ledger bug?" to "can the model infer and implement one coherent ledger engine across interacting constraints?"

## Experiment Design

The official study contains `200` scored implementation runs:

| Cell | Reasoning | Model | Topology | Runs |
| --- | --- | --- | --- | ---: |
| V3P0 | low | GPT-5.5 | solo | 50 |
| V3P1 | medium | GPT-5.5 | solo | 50 |
| V3P2 | high | GPT-5.5 | solo | 50 |
| V3P3 | xhigh | GPT-5.5 | solo | 50 |

Measured implementation runs used `codex exec --json`. Raw JSONL events, prompts, rendered configs, stderr logs, diffs, test logs, judge output, metadata, scores, HTML reports, and PDF reports were preserved under run-specific directories. The implementation model was GPT-5.5 in all cells. The judge was GPT-5.5 xhigh in all cells.

The study accumulated repeats in six measured batches. Pooling required the full expanded matrix hash, selected repeat ranges, benchmark template, hidden cases, prompts, scoring config, judge schema, model identifiers, timeout policy, and failure policy to remain fixed. All six measured batches passed final validation. There were zero implementation failures and zero judge failures.

## Measurement

### Quality

Quality is a 0 to 1 composite score from `configs/scoring_v3.yaml`:

| Component | Weight | Meaning |
| --- | ---: | --- |
| Hidden correctness | 0.50 | Correctness on frozen private RuleLedger v3 cases, excluding parity and performance categories |
| Hidden parity | 0.15 | TypeScript/Python agreement on hidden parity checks |
| Performance | 0.10 | Performance behavior on hidden workloads |
| Judge | 0.22 | GPT-5.5 xhigh assessment of source, diffs, logs, public checks, and hidden-result summaries |
| Minimality | 0.03 | Production LOC minimality signal relative to the configured target |

The weighting intentionally places most emphasis on hidden behavioral correctness while preserving signals from parity, performance, expert-style judge review, and implementation size. Minimality is deliberately small so a compact but incomplete patch cannot dominate a correct and maintainable implementation.

The judge was fixed across conditions and contributes to a broader scoring profile anchored mostly in hidden tests. Its output should be read as a consistent expert-style review signal, not as a replacement for independent human adjudication.

### Cost and Time

The harness parsed implementation usage from `codex exec --json` event streams. Because every measured implementation run was solo GPT-5.5, implementation tokens are GPT-5.5 implementation tokens. Judge tokens are excluded from the cost table because the measured developer decision is which implementation reasoning level to run.

Elapsed seconds are per-run harness measurements. They are useful for comparing this study's conditions, but they are affected by local scheduling, batch parallelism, and the execution environment.

### Uncertainty

The paper reports observed sample means, standard deviations, approximate confidence intervals, pairwise mean-difference intervals, and descriptive effect sizes. These are not preregistered inferential tests. Small adjacent gaps should be read cautiously, especially when intervals cross zero.

## Results at a Glance

| Reasoning | Runs | Quality mean | Quality sd | Hidden correctness | Judge | Impl tokens | Impl seconds | Primary read |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| low | 50 | 0.433800 | 0.181064 | 0.363958 | 0.393869 | 815,190 | 199 | Useful local progress, weak global consistency |
| medium | 50 | 0.461959 | 0.175457 | 0.409375 | 0.459012 | 1,389,968 | 318 | Modest gain over low |
| high | 50 | 0.696050 | 0.194662 | 0.674375 | 0.683359 | 2,612,154 | 686 | Main quality jump |
| xhigh | 50 | 0.755057 | 0.171127 | 0.739375 | 0.752072 | 3,333,886 | 1,019 | Best mean and tail behavior |

## Detailed Findings

### Low Reasoning

Low reasoning scored `0.434` mean quality. It produced some successful runs (`5/50` at or above `0.7` quality), but `20/50` runs fell below `0.4`. The pattern is consistent with local repair ability without reliable global integration.

Low is useful as a lower-bound condition for benchmark calibration. It is not the practical setting for RuleLedger v3-style implementation work when quality matters.

### Medium Reasoning

Medium reasoning scored `0.462`, only `+0.028` above low. The approximate 95% interval for medium minus low was `[-0.043, +0.099]`, so the study supports only a weak adjacent-separation claim between those two levels.

Medium used substantially more tokens than low (`1.390M` vs `0.815M`) while producing only a modest mean quality gain. In this benchmark, medium did not represent the quality/cost knee.

### High Reasoning

High reasoning scored `0.696`, a `+0.234` gain over medium. This is the dominant empirical result. The approximate 95% interval for high minus medium was `[+0.161, +0.308]`, and the descriptive effect size was large (`d = 1.263`).

High is the practical knee of the curve. It costs materially more than medium, but it is the first setting where the benchmark consistently moves into a stronger implementation regime.

### Xhigh Reasoning

Xhigh reasoning scored `0.755`, the best observed mean. It also had the best hidden correctness, judge score, parity, performance, and tail behavior. No xhigh run fell below `0.4` quality, compared with `3/50` for high, `17/50` for medium, and `20/50` for low.

The adjacent xhigh-over-high gap was `+0.059`, with an approximate 95% interval of `[-0.014, +0.132]`. That supports directional evidence and a practical maximum-quality recommendation, but not the same robust adjacent-separation claim as high over medium.

## Pairwise Quality Differences

| Comparison | Mean difference | Approx. 95% interval | Cohen's d | Interpretation |
| --- | ---: | ---: | ---: | --- |
| medium - low | +0.028159 | [-0.042583, +0.098901] | 0.158 | Small, not robustly separated |
| high - medium | +0.234091 | [+0.160561, +0.307621] | 1.263 | Large, robust adjacent separation |
| xhigh - high | +0.059007 | [-0.013715, +0.131729] | 0.322 | Positive mean, interval crosses zero |
| high - low | +0.262250 | [+0.187657, +0.336843] | 1.395 | Large separation |
| xhigh - low | +0.321257 | [+0.251355, +0.391159] | 1.824 | Very large separation |
| xhigh - medium | +0.293099 | [+0.224331, +0.361867] | 1.691 | Very large separation |

This is the paper's main claim boundary. RuleLedger v3 strongly separates high/xhigh from low/medium. It strongly separates high from medium. The medium-over-low and xhigh-over-high observed means point in the expected direction, but they do not carry the same evidentiary weight.

## Secondary Metrics

| Reasoning | Hidden tests | Hidden correctness | Hidden parity | Performance | Judge |
| --- | ---: | ---: | ---: | ---: | ---: |
| low | 0.378911 | 0.363958 | 0.531111 | 0.556000 | 0.393869 |
| medium | 0.420218 | 0.409375 | 0.505556 | 0.515334 | 0.459012 |
| high | 0.687041 | 0.674375 | 0.734445 | 0.738000 | 0.683359 |
| xhigh | 0.753693 | 0.739375 | 0.791111 | 0.800000 | 0.752072 |

Hidden-test and judge signals show the same broad ladder: low and medium are clustered together, high improves sharply, and xhigh leads high on mean.

## Behavior-Family Results

Hidden categories should be interpreted as behavior-family aggregates rather than public fixture descriptions:

| Category | low | medium | high | xhigh |
| --- | ---: | ---: | ---: | ---: |
| evolution | 0.314348 | 0.295435 | 0.562391 | 0.604783 |
| fail_to_pass | 0.420000 | 0.431429 | 0.645000 | 0.706071 |
| localization | 0.133889 | 0.324444 | 0.773333 | 0.874722 |
| metamorphic | 0.384615 | 0.369231 | 0.552308 | 0.600000 |
| parity | 0.531111 | 0.505556 | 0.734445 | 0.791111 |
| pass_to_pass | 0.779524 | 0.800000 | 0.864762 | 0.932857 |
| performance | 0.556000 | 0.515334 | 0.738000 | 0.800000 |

The largest visible differences are in localization, staged evolution, parity, and performance. That pattern matches the benchmark design: lower-reasoning runs can often make local fixes, but higher-reasoning runs are better at maintaining one implementation model across interacting requirements and language surfaces.

## Tail Behavior

| Reasoning | >=0.4 quality | >=0.5 quality | >=0.7 quality | >=0.8 quality | >=0.9 quality | <0.4 quality |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| low | 30/50 | 15/50 | 5/50 | 4/50 | 0/50 | 20/50 |
| medium | 33/50 | 20/50 | 2/50 | 1/50 | 1/50 | 17/50 |
| high | 47/50 | 42/50 | 24/50 | 18/50 | 9/50 | 3/50 |
| xhigh | 50/50 | 48/50 | 26/50 | 22/50 | 14/50 | 0/50 |

The xhigh condition did not merely win on mean. It also removed the low-quality tail seen in the other settings. This matters for practical engineering use, where avoiding bad outputs can be as important as raising the average score.

## Cost and Latency

| Reasoning | Mean implementation tokens | Mean implementation seconds | Quality mean | Quality per GPT token |
| --- | ---: | ---: | ---: | ---: |
| low | 815,190 | 199 | 0.433800 | 5.32146e-7 |
| medium | 1,389,968 | 318 | 0.461959 | 3.32352e-7 |
| high | 2,612,154 | 686 | 0.696050 | 2.66466e-7 |
| xhigh | 3,333,886 | 1,019 | 0.755057 | 2.26480e-7 |

Raw quality per token falls as reasoning increases because low-reasoning runs are cheaper. That metric alone is not the right operational target when the implementation has to clear a quality threshold. The practical tradeoff is between quality level, weak-run risk, and cost. High is the quality/cost knee because it delivers the main quality jump. Xhigh costs more and has lower raw quality per token, but it gives the best observed mean and the strongest tail behavior.

## Why High Was the Main Jump

RuleLedger v3 combines local coding work with global consistency obligations. Low and medium runs often pass public tests and produce complete artifacts, but they more frequently leave independent replay paths, parity drift, incomplete merge-lineage handling, localization failures, or performance weaknesses.

High reasoning appears to cross the threshold where the model more often infers the required abstraction: one shared replay model that drives summaries, reports, parity outputs, and digests. Once that abstraction is in place, many hidden behavior families improve together.

## Why Xhigh Helped Less Than High

Xhigh produced the best mean and tail behavior, but the marginal gain over high was smaller than the high-over-medium jump. This is the expected shape for a benchmark where high reasoning already solves much of the abstraction problem.

The xhigh result is still practically valuable. It reduced weak-run risk and led every secondary mean. The cautious statistical statement is narrower: this 50-run-per-level study supports xhigh as the maximum-quality setting, while treating robust xhigh-over-high separation as unresolved.

## Recommendations

Use RuleLedger v3 when the evaluation goal is to measure whether a coding model can maintain a coherent implementation across interacting software constraints. It is especially useful for reasoning-effort studies because the task punishes narrow local fixes.

Use GPT-5.5 high as the practical solo setting for RuleLedger v3-like work. It captures the main quality jump while costing materially less than xhigh.

Use GPT-5.5 xhigh when maximum expected quality and weak-run reduction matter more than token and wall-clock cost. Xhigh had the best mean and no runs below `0.4` quality.

Frame adjacent reasoning claims carefully. The study strongly supports high over medium. It supports xhigh as the best observed mean and best tail-risk setting. It does not give medium-over-low or xhigh-over-high the same evidentiary strength.

For future benchmark work, add preregistered statistical tests, distribution plots, batch-stratified plots, a failure-mode taxonomy from sampled diffs, and an independent human or non-LLM review layer for maintainability-sensitive claims.

## Limitations

- The benchmark uses one main implementation model family and four reasoning settings, not a broad model marketplace.
- The judge is another LLM, held fixed across conditions, but not a substitute for independent human review.
- The benchmark is synthetic, even though it is designed to mimic realistic ledger engineering work.
- Hidden tests are finite and may not capture all semantically valid implementation strategies.
- Batch-level variance is visible. Small batches can invert adjacent reasoning levels.
- The execution environment used high local parallelism and `danger-full-access` sandboxing, which should be documented when comparing against other environments.
- Token and elapsed-time metrics are implementation-cost signals, not prices or universal latency measurements.
- The current analysis uses approximate confidence intervals and descriptive effect sizes, not a preregistered inferential analysis plan.

These limitations define the claim boundary. They do not erase the main result: RuleLedger v3 exposes a large quality transition between medium and high reasoning in solo GPT-5.5 software-engineering work.

## Appendix A: Batched Execution

| Batch | Repeat range | Runs | Started UTC | Finished UTC | Validation | Implementation failures | Judge failures |
| --- | ---: | ---: | --- | --- | --- | ---: | ---: |
| v3-paper-batch-001 | 1-5 | 20 | 2026-06-05T19:05:14 | 2026-06-05T20:00:48 | passed | 0 | 0 |
| v3-paper-batch-002 | 6-10 | 20 | 2026-06-05T22:20:18 | 2026-06-05T23:17:05 | passed | 0 | 0 |
| v3-paper-batch-003 | 11-20 | 40 | 2026-06-10T08:11:40 | 2026-06-10T09:58:36 | passed | 0 | 0 |
| v3-paper-batch-004 | 21-30 | 40 | 2026-06-10T17:10:24 | 2026-06-10T18:47:24 | passed | 0 | 0 |
| v3-paper-batch-005 | 31-40 | 40 | 2026-06-11T05:37:56 | 2026-06-11T07:25:00 | passed | 0 | 0 |
| v3-paper-batch-006 | 41-50 | 40 | 2026-06-17T21:11:06 | 2026-06-17T22:49:53 | passed | 0 | 0 |

The first three batches were launched from a clean repository. Batches 4-6 recorded `repo.dirty: true` because the untracked `papers/` artifact already existed. The measured repository head stayed fixed across all six batches:

`2cd7314b10cacaf8b1b3089aa9febdd081b328bf`

## Appendix B: Per-Batch Means

| Batch | Reasoning | Runs | Quality | Hidden correctness | Judge |
| --- | --- | ---: | ---: | ---: | ---: |
| batch 001 | low | 5 | 0.475156 | 0.401389 | 0.450583 |
| batch 001 | medium | 5 | 0.589751 | 0.547222 | 0.582500 |
| batch 001 | high | 5 | 0.527437 | 0.490278 | 0.429000 |
| batch 001 | xhigh | 5 | 0.673830 | 0.629861 | 0.702512 |
| batch 002 | low | 5 | 0.377782 | 0.294444 | 0.348000 |
| batch 002 | medium | 5 | 0.496087 | 0.497917 | 0.534968 |
| batch 002 | high | 5 | 0.864543 | 0.863194 | 0.831550 |
| batch 002 | xhigh | 5 | 0.797686 | 0.793750 | 0.779700 |
| batch 003 | low | 10 | 0.463410 | 0.409028 | 0.432339 |
| batch 003 | medium | 10 | 0.483799 | 0.428125 | 0.423988 |
| batch 003 | high | 10 | 0.801662 | 0.787153 | 0.779062 |
| batch 003 | xhigh | 10 | 0.852129 | 0.850347 | 0.838000 |
| batch 004 | low | 10 | 0.360163 | 0.273264 | 0.365750 |
| batch 004 | medium | 10 | 0.363847 | 0.297570 | 0.377338 |
| batch 004 | high | 10 | 0.636425 | 0.621528 | 0.655125 |
| batch 004 | xhigh | 10 | 0.782214 | 0.776389 | 0.778056 |
| batch 005 | low | 10 | 0.508938 | 0.436111 | 0.449464 |
| batch 005 | medium | 10 | 0.350944 | 0.274306 | 0.368750 |
| batch 005 | high | 10 | 0.676574 | 0.650347 | 0.667833 |
| batch 005 | xhigh | 10 | 0.655113 | 0.609375 | 0.702200 |
| batch 006 | low | 10 | 0.410020 | 0.353472 | 0.322500 |
| batch 006 | medium | 10 | 0.568285 | 0.524305 | 0.566250 |
| batch 006 | high | 10 | 0.669598 | 0.636111 | 0.684500 |
| batch 006 | xhigh | 10 | 0.750073 | 0.748958 | 0.701000 |

The per-batch table explains why small pilots were informative but insufficient. Batch 001 made high look weaker than medium. Batch 002 made high look stronger than xhigh. Batch 005 again had xhigh below high on aggregate quality. The completed pooled sample is what stabilizes the broader result.

## Appendix C: Reproducibility

Key source files:

- Experiment config: `configs/ruleledger_v3_paper_50.yaml`
- Scoring profile: `configs/scoring_v3.yaml`
- Issue brief: `benchmark_template_v3/docs/ruleledger_v3_issue_brief.md`
- Architecture notes: `benchmark_template_v3/docs/ruleledger_v3_architecture.md`
- Development plan: `plans/stage-22-ruleledger-v3.md`
- Batched repeat requirements: `plans/batched-repeat-study-requirements.md`

Completed measured batches:

- `runs/20260605T190514-ruleledger_v3_paper_50-v3_paper_batch_01_r01_r05_measured`
- `runs/20260605T222018-ruleledger_v3_paper_50-v3_paper_batch_02_r06_r10_measured`
- `runs/20260610T081140-ruleledger_v3_paper_50-v3_paper_batch_03_r11_r20_measured`
- `runs/20260610T171024-ruleledger_v3_paper_50-v3_paper_batch_04_r21_r30_measured`
- `runs/20260611T053756-ruleledger_v3_paper_50-v3_paper_batch_05_r31_r40_measured`
- `runs/20260617T211106-ruleledger_v3_paper_50-v3_paper_batch_06_r41_r50_measured`

Shared frozen hashes:

- Full matrix SHA-256: `2ec216ba7cf6d9e01528a355ac590aec7aedf8b026c9aa8d49f49fdd623a27e1`
- Benchmark template SHA-256: `edfde6362042bfdf100bedfe63c273c817072004cc42ff3952ad3afb9c319699`
- Hidden cases tree SHA-256: `bf742505d0503883a3e8dc001d41a16254b67d1aa3aea1fd337acb5e620a8d6b`
- Hidden manifest SHA-256: `63937005528b0ff1842bcd10a57617da49acbbbc0e4b67dfa8b5f65547ecb362`
- Scoring config SHA-256: `dc50227fd818efc567b756bc2be2bf6bf2a22850072bd7ab14ca6673c68cb76c`
- Experiment config SHA-256: `2f47b30ad9763cebb332fcbcef60488b0daab479c2aec2765f447d0af7d38aa3`
- Repository head for measured source: `2cd7314b10cacaf8b1b3089aa9febdd081b328bf`

Run directories preserve raw JSONL events, stderr logs, prompts, rendered configs, diffs, test logs, judge output, metadata, scores, and generated HTML and PDF reports.

## Appendix D: References

- RuleLedger v3 issue brief: `benchmark_template_v3/docs/ruleledger_v3_issue_brief.md`
- RuleLedger v3 architecture notes: `benchmark_template_v3/docs/ruleledger_v3_architecture.md`
- RuleLedger v3 development plan and calibration log: `plans/stage-22-ruleledger-v3.md`
- Batched repeat study requirements: `plans/batched-repeat-study-requirements.md`
- SWE-bench repository: https://github.com/swe-bench/SWE-bench
- SWE-bench Verified announcement: https://openai.com/index/introducing-swe-bench-verified/
- SWE-Bench Pro: https://openreview.net/forum?id=6RYawev6L9
- SWE-Lancer: https://openai.com/index/swe-lancer/
