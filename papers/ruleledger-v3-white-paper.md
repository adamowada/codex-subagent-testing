# RuleLedger v3: A Controlled Benchmark for Measuring Reasoning Effort in LLM Software Engineering

Version: 1.0 final white paper
Date: June 17, 2026
Study ID: `ruleledger_v3_reasoning_whitepaper`
Experiment config: `configs/ruleledger_v3_paper_50.yaml`
Evidence scope: six completed measured batches, repeats 1-50
Measured sample: 200 scored runs, 50 repeats per reasoning level

## Abstract

RuleLedger v3 is a controlled software-engineering benchmark designed to test whether larger reasoning budgets produce measurably better code on a realistic repair-and-extension task. It was developed after earlier RuleLedger variants proved too easy to separate low, medium, high, and xhigh reasoning settings reliably. Version 3 raises the difficulty by requiring one coherent implementation model across bitemporal ledger replay, account lineage, corrections and voids, exact billing, deterministic reporting, TypeScript/Python parity, performance constraints, and maintainable multi-module architecture.

This white paper reports the completed 200-run study: 50 repeats each for GPT-5.5 at low, medium, high, and xhigh reasoning. The primary endpoint is aggregate quality under the `reasoning_ladder_v3` scoring profile. The final pooled results show clear separation between medium and high reasoning, and between lower-reasoning and higher-reasoning groups overall. Mean quality was 0.433800 for low, 0.461959 for medium, 0.696050 for high, and 0.755057 for xhigh. The strongest adjacent result is high over medium: +0.234091 quality points with an approximate 95% interval of [0.160561, 0.307621]. Xhigh had the best mean result and no run below 0.4 quality, but its mean advantage over high was smaller: +0.059007 with an approximate 95% interval of [-0.013715, 0.131729]. The responsible conclusion is that RuleLedger v3 strongly differentiates low/medium from high/xhigh reasoning and provides directional evidence that xhigh improves on high, while not yet proving a robust adjacent high-vs-xhigh separation under this sample and analysis.

## Executive Summary

RuleLedger v3 was built to answer a narrow but important benchmark-design question: can a controlled software-engineering task distinguish model reasoning effort without relying on superficial task size, leaked hidden cases, or public-test overfitting?

The completed study says yes. Across 200 measured runs, higher reasoning settings produced substantially better implementations on hidden correctness, judge assessment, parity, performance, and the aggregate quality score. The benchmark's main diagnostic force comes from forcing the model to maintain one coherent ledger engine across multiple surfaces that are easy to patch independently but hard to make jointly correct.

| Reasoning | Runs | Quality mean | Quality SD | 95% CI half-width | Hidden correctness | Judge | Mean impl tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| low | 50 | 0.433800 | 0.181064 | 0.051443 | 0.363958 | 0.393869 | 815,190 |
| medium | 50 | 0.461959 | 0.175457 | 0.049850 | 0.409375 | 0.459012 | 1,389,968 |
| high | 50 | 0.696050 | 0.194662 | 0.055306 | 0.674375 | 0.683359 | 2,612,154 |
| xhigh | 50 | 0.755057 | 0.171127 | 0.048620 | 0.739375 | 0.752072 | 3,333,886 |

The most defensible paper-grade claims are:

- RuleLedger v3 is a reproducible, artifact-backed benchmark that differentiates reasoning effort in solo LLM software-engineering work.
- The benchmark produces a large and stable quality separation between medium and high reasoning.
- High and xhigh reasoning substantially outperform low and medium reasoning.
- Xhigh has the best mean result and the strongest tail behavior in this study, but the high-vs-xhigh adjacent comparison should be framed as suggestive rather than settled.

The result is not that every adjacent reasoning step creates the same gain. Medium only modestly exceeded low, while high produced the main improvement. Xhigh then added a smaller additional lift at higher token and wall-clock cost.

## Background and Motivation

Modern LLM software-engineering benchmarks increasingly emphasize repository-scale repair, hidden tests, issue-style prompts, and artifact preservation. Benchmarks such as SWE-bench, SWE-bench Verified, SWE-Bench Pro, and SWE-Lancer helped establish that useful evaluation should resemble actual engineering work: a model must understand a codebase, infer intent from incomplete natural-language context, edit multiple files, preserve old behavior, and generalize beyond visible tests.

RuleLedger v3 adopts those lessons in a smaller, fully controlled setting. The goal is not to replace broad repository benchmarks. The goal is to create a benchmark whose task, hidden tests, scoring profile, run harness, batch metadata, and artifact freeze can be fully owned and audited by the experimenter.

The project began from a practical failure mode. Earlier RuleLedger versions contained meaningful ledger semantics, but the task was not hard enough to consistently separate low, medium, high, and xhigh reasoning. A model could often localize the visible issue, patch a narrow behavior, and score well without building a durable model of the domain. That made the benchmark useful for basic correctness testing but weak as a reasoning-effort instrument.

RuleLedger v3 changes the unit of evaluation from "can the model patch this ledger bug?" to "can the model infer and implement one coherent ledger engine across interacting constraints?"

## Benchmark Design

RuleLedger v3 is a synthetic but realistic subscription-ledger repair benchmark. The visible task is written as an issue brief rather than a complete truth table. Public tests are readable and intentionally incomplete. Hidden tests evaluate whether the implementation generalizes across behavior families while preserving earlier compatibility behavior.

The measured agent starts from a frozen starter project with both TypeScript and Python implementation surfaces. Public callers enter through existing APIs, while the intended implementation shape separates responsibilities into normalization, replay, billing, reporting, and domain modules. A strong solution must make those surfaces agree rather than satisfy each one through isolated patches.

| Axis | What it tests | Why it challenges reasoning |
|---|---|---|
| Bitemporal replay | Audit-visible and business-effective cutoffs, corrections, voids, and deterministic event ordering | Requires temporal reasoning before state application, not after-the-fact patching |
| Account lineage | Merges, older identifiers, target resolution, and post-merge actions | Requires durable alias modeling across event history |
| TypeScript/Python parity | Comparable public outputs, CSV serialization, replay digests, and edge-case normalization | Penalizes language-specific shortcuts and divergent implementations |
| Exact billing | Proration, money parsing, rounding, invoice dates, and large seat-count behavior | Exposes imprecise numeric handling and incomplete normalization |
| Regression pressure | v1/v2 public APIs and pass-to-pass behavior remain in scope | Prevents narrow fixes that break earlier contracts |
| Performance | Large generated ledgers and replay/report workloads | Catches nested scans and per-account full-history recomputation |
| Maintainability | Multi-module architecture with thin compatibility boundaries | Rewards code that future reviewers can reason about |

The key design decision is the resolution standard visible to measured agents: a credible v3 fix should be explainable as one canonical replay model that drives summaries, CSV reports, parity checks, and replay digests. This standard makes the benchmark harder without exposing private test fixtures. It also moves the task closer to real engineering, where correctness often depends on choosing the right abstraction and applying it consistently.

## Development Path

RuleLedger v3 was developed through iterative calibration rather than a one-shot benchmark build. The main stages were:

1. Preserve the RuleLedger v2 behavior contract while changing the implementation challenge from monolithic patching to reviewable multi-file engineering.
2. Add an issue-style v3 brief that describes support escalations rather than enumerating every rule.
3. Define visible architecture expectations for TypeScript and Python so maintainability becomes part of the task surface.
4. Build hidden behavior families that exercise regression, fail-to-pass repair, parity, metamorphic behavior, performance, localization, and staged requirement evolution.
5. Repair harness and judge reliability issues, including strict judge JSON parsing and explicit infrastructure-failure handling.
6. Calibrate the prompt around a resolution standard that makes the need for a canonical replay model explicit without disclosing hidden cases.
7. Add batched repeat accumulation so the same frozen study could be run over several days while preserving metadata, selected repeat ranges, artifact hashes, and validation evidence.

The end product is a benchmark harness that can run measured Codex implementation jobs through `codex exec --json`, preserve raw artifacts for every run, score outputs against hidden tests and a fixed judge, and render experiment reports. For the reasoning-effort paper study, the harness was configured as a solo-agent experiment to isolate the reasoning level of a single GPT-5.5 implementation model.

## Experimental Protocol

The active experiment is `ruleledger_v3_paper_50`. It contains four solo GPT-5.5 cells, each with 50 repeats:

| Cell | Reasoning | Model | Topology | Planned repeats | Completed repeats |
|---|---|---|---|---:|---:|
| V3P0 | low | GPT-5.5 | solo | 50 | 50 |
| V3P1 | medium | GPT-5.5 | solo | 50 | 50 |
| V3P2 | high | GPT-5.5 | solo | 50 | 50 |
| V3P3 | xhigh | GPT-5.5 | solo | 50 | 50 |

Measured implementation runs used `codex exec --json`. Raw JSONL events, prompts, rendered configs, stderr logs, diffs, test logs, judge output, metadata, scores, HTML reports, and PDF reports were preserved under run-specific directories. The judge used GPT-5.5 at xhigh reasoning with schema-enforced output. The measured implementation model and judge were held fixed across reasoning conditions.

The planned config includes default parallelism of `implementation_jobs: 3` and `judge_jobs: 1`, but the paper batches were launched with explicit command-line overrides of `Jobs 5 / JudgeJobs 4`. This setting had already worked for earlier RuleLedger v1-style runs and was used consistently for all six paper batches.

The experiment was batchable by design. Batches could run days apart if the following pooling requirements were preserved:

- The full expanded matrix hash remained identical.
- Selected repeat ranges were planned and non-overlapping.
- Benchmark template, hidden cases, prompts, scoring config, judge schema, model identifiers, timeout policy, and failure policy remained fixed.
- Each batch recorded metadata, selected matrix hash, timestamps, repository state, and artifact hashes.
- Pooled claims were checked against per-batch results before being presented.

All six measured batches passed final validation. There were zero implementation failures and zero judge failures. Result rows with `status=partial` mean partial benchmark credit, not failed harness execution; every batch-6 run, for example, reached the `scored` phase.

## Batched Execution

The completed study accumulated repeats in six measured batches:

| Batch | Repeat range | Runs | Started UTC | Finished UTC | Validation | Implementation failures | Judge failures |
|---|---:|---:|---|---|---|---:|---:|
| v3-paper-batch-001 | 1-5 | 20 | 2026-06-05T19:05:14 | 2026-06-05T20:00:48 | passed | 0 | 0 |
| v3-paper-batch-002 | 6-10 | 20 | 2026-06-05T22:20:18 | 2026-06-05T23:17:05 | passed | 0 | 0 |
| v3-paper-batch-003 | 11-20 | 40 | 2026-06-10T08:11:40 | 2026-06-10T09:58:36 | passed | 0 | 0 |
| v3-paper-batch-004 | 21-30 | 40 | 2026-06-10T17:10:24 | 2026-06-10T18:47:24 | passed | 0 | 0 |
| v3-paper-batch-005 | 31-40 | 40 | 2026-06-11T05:37:56 | 2026-06-11T07:25:00 | passed | 0 | 0 |
| v3-paper-batch-006 | 41-50 | 40 | 2026-06-17T21:11:06 | 2026-06-17T22:49:53 | passed | 0 | 0 |

The first three batches were launched from a clean repository. Batches 4-6 recorded `repo.dirty: true` because the untracked `papers/` artifact already existed. The measured repository head stayed fixed across all six batches:

`2cd7314b10cacaf8b1b3089aa9febdd081b328bf`

The core freeze hashes were identical across all six measured batches:

| Artifact | SHA-256 |
|---|---|
| Experiment config | `2f47b30ad9763cebb332fcbcef60488b0daab479c2aec2765f447d0af7d38aa3` |
| Full expanded matrix | `2ec216ba7cf6d9e01528a355ac590aec7aedf8b026c9aa8d49f49fdd623a27e1` |
| Benchmark template tree | `edfde6362042bfdf100bedfe63c273c817072004cc42ff3952ad3afb9c319699` |
| Hidden cases tree | `bf742505d0503883a3e8dc001d41a16254b67d1aa3aea1fd337acb5e620a8d6b` |
| Hidden manifest | `63937005528b0ff1842bcd10a57617da49acbbbc0e4b67dfa8b5f65547ecb362` |
| Scoring config | `dc50227fd818efc567b756bc2be2bf6bf2a22850072bd7ab14ca6673c68cb76c` |
| Judge output schema | `b220aa3d16e51b086fae4cb608058b9896312c8522b392bf8b12fd398704a208` |
| Common v3 task prompt | `6c25e3ade31a651292576e66635fce7c9e9af637bfbe05a6ab9732975af29e2d` |
| Solo task prompt | `a94405f8a31274566b63e96e86581a6a38fb006511f12d04b84a4a698126369d` |
| Judge prompt | `90ccb0b4b51d786cc239ea0227aadf029a49267b0f8ce3994c93c8f62a0f53ed` |

## Scoring Model

The active scoring profile is `reasoning_ladder_v3`. Aggregate quality is a weighted composite:

| Component | Weight |
|---|---:|
| Hidden correctness | 0.50 |
| Hidden parity | 0.15 |
| Performance | 0.10 |
| Judge score | 0.22 |
| Minimality | 0.03 |

The weighting intentionally places most emphasis on hidden behavioral correctness while preserving signals from parity, performance, expert-style judge review, and implementation size. Minimality is deliberately small in the paper profile so a compact but incomplete patch cannot dominate a correct and maintainable implementation.

Because the judge is another LLM, judge score should not be treated as independent human adjudication. It is useful here because it is fixed across conditions and contributes to a broader scoring profile anchored mostly in hidden tests.

## Results

### Primary Endpoint: Aggregate Quality

Aggregate quality was the primary endpoint. The completed 50-repeat-per-level study produced the following means:

| Reasoning | Runs | Mean | SD | Approx. 95% CI |
|---|---:|---:|---:|---:|
| low | 50 | 0.433800 | 0.181064 | [0.382357, 0.485243] |
| medium | 50 | 0.461959 | 0.175457 | [0.412109, 0.511809] |
| high | 50 | 0.696050 | 0.194662 | [0.640744, 0.751356] |
| xhigh | 50 | 0.755057 | 0.171127 | [0.706437, 0.803677] |

The dominant empirical result is the large jump from medium to high. Medium exceeded low only modestly, while high moved the benchmark into a different performance regime. Xhigh had the highest mean, best hidden correctness, best judge mean, best parity mean, best performance mean, and strongest tail behavior, but its adjacent advantage over high was smaller.

### Pairwise Quality Differences

The table below uses Welch-style approximate 95% intervals for mean differences and pooled-standard-deviation Cohen's d as a descriptive effect size.

| Comparison | Mean difference | Approx. 95% interval | Cohen's d | Interpretation |
|---|---:|---:|---:|---|
| medium - low | +0.028159 | [-0.042583, 0.098901] | 0.158 | small, not a robust adjacent separation |
| high - medium | +0.234091 | [0.160561, 0.307621] | 1.263 | large, robust adjacent separation |
| xhigh - high | +0.059007 | [-0.013715, 0.131729] | 0.322 | positive mean, interval crosses zero |
| high - low | +0.262250 | [0.187657, 0.336843] | 1.395 | large separation |
| xhigh - low | +0.321257 | [0.251355, 0.391159] | 1.824 | very large separation |
| xhigh - medium | +0.293099 | [0.224331, 0.361867] | 1.691 | very large separation |

This is the core paper-grade claim boundary. RuleLedger v3 strongly separates high/xhigh from low/medium. It strongly separates high from medium. It does not support equally strong language for medium over low or xhigh over high under this analysis.

### Secondary Endpoints

The secondary metrics align with the aggregate quality result:

| Reasoning | Hidden tests | Hidden correctness | Hidden parity | Performance | Judge |
|---|---:|---:|---:|---:|---:|
| low | 0.378911 | 0.363958 | 0.531111 | 0.556000 | 0.393869 |
| medium | 0.420218 | 0.409375 | 0.505556 | 0.515334 | 0.459012 |
| high | 0.687041 | 0.674375 | 0.734445 | 0.738000 | 0.683359 |
| xhigh | 0.753693 | 0.739375 | 0.791111 | 0.800000 | 0.752072 |

The hidden-test and judge signals both show the same broad ladder: low and medium are clustered together, high improves sharply, and xhigh leads high on mean.

### Hidden Category Means

The hidden categories should be interpreted as behavior-family aggregates rather than public fixture descriptions. They show where higher reasoning helped most:

| Category | low | medium | high | xhigh |
|---|---:|---:|---:|---:|
| evolution | 0.314348 | 0.295435 | 0.562391 | 0.604783 |
| fail_to_pass | 0.420000 | 0.431429 | 0.645000 | 0.706071 |
| localization | 0.133889 | 0.324444 | 0.773333 | 0.874722 |
| metamorphic | 0.384615 | 0.369231 | 0.552308 | 0.600000 |
| parity | 0.531111 | 0.505556 | 0.734445 | 0.791111 |
| pass_to_pass | 0.779524 | 0.800000 | 0.864762 | 0.932857 |
| performance | 0.556000 | 0.515334 | 0.738000 | 0.800000 |

The largest visible differences are in localization, staged evolution, parity, and performance. That pattern is consistent with the benchmark's design: lower-reasoning runs can often make local fixes, but higher-reasoning runs are better at maintaining one implementation model across interacting requirements and language surfaces.

### Tail Behavior

Threshold counts provide another view of robustness:

| Reasoning | >=0.4 quality | >=0.5 quality | >=0.7 quality | >=0.8 quality | >=0.9 quality | <0.4 quality |
|---|---:|---:|---:|---:|---:|---:|
| low | 30/50 | 15/50 | 5/50 | 4/50 | 0/50 | 20/50 |
| medium | 33/50 | 20/50 | 2/50 | 1/50 | 1/50 | 17/50 |
| high | 47/50 | 42/50 | 24/50 | 18/50 | 9/50 | 3/50 |
| xhigh | 50/50 | 48/50 | 26/50 | 22/50 | 14/50 | 0/50 |

The xhigh condition did not merely win on mean. It also removed the low-quality tail seen in the other settings. High still produced occasional weak runs, but far fewer than low or medium. This matters for practical engineering use, where avoiding bad outputs can be as important as raising the mean.

### Cost and Latency

Higher reasoning produced better code at higher cost:

| Reasoning | Mean implementation tokens | Mean implementation seconds | Quality mean |
|---|---:|---:|---:|
| low | 815,190 | 198.7 | 0.433800 |
| medium | 1,389,968 | 318.4 | 0.461959 |
| high | 2,612,154 | 686.2 | 0.696050 |
| xhigh | 3,333,886 | 1,019.4 | 0.755057 |

The cost-quality tradeoff is not linear. Medium consumed substantially more tokens than low while producing only a small quality gain. High consumed much more than medium but produced the largest quality jump. Xhigh consumed the most and produced the best mean score, but with a smaller marginal gain over high.

For a user choosing settings under a time or token budget, high appears to be the practical knee of the curve in this benchmark. Xhigh is the best setting when maximum expected quality and tail-risk reduction matter more than cost.

### Per-Batch Means

Batch-level variance is real and should remain visible. Small batches sometimes invert adjacent settings, which is why the final report uses 50 repeats per level.

| Batch | Reasoning | Runs | Quality | Hidden correctness | Judge |
|---|---|---:|---:|---:|---:|
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

## Interpretation

RuleLedger v3 challenges models because it combines local coding work with global consistency obligations. Low and medium runs often pass public tests and produce complete artifacts, but they more frequently leave independent replay paths, parity drift, incomplete merge-lineage handling, localization failures, or performance weaknesses. High and xhigh runs more often infer that the task needs one shared model of ledger replay and apply that model across summaries, reports, parity outputs, and digests.

The benchmark is diagnostic because it contains traps that look easy in isolation:

- A summary can be made correct while CSV output remains wrong.
- TypeScript can pass while Python drifts, or the reverse.
- Audit-time and business-time cutoffs can be accidentally conflated.
- Corrections and voids can work for direct targets but fail after lineage changes.
- Public tests can pass while hidden pass-to-pass behavior regresses.
- A patch can be behaviorally strong but structurally hard to maintain.
- A correct small-ledger implementation can degrade on generated large ledgers.

Those traps are not arbitrary. They mirror the cross-surface coupling that makes real software-engineering work hard for language models. The model must read requirements, infer the right abstraction, edit multiple files, preserve old behavior, and verify its work without seeing the final evaluator.

## What RuleLedger v3 Measures Well

RuleLedger v3 is strongest as a controlled reasoning-effort benchmark for solo coding agents. It measures:

- Cross-file implementation planning.
- Ability to infer a shared domain model from issue-style requirements.
- Regression awareness under incomplete public tests.
- Hidden-test generalization without hidden-test leakage.
- TypeScript/Python parity discipline.
- Deterministic serialization and exact arithmetic.
- Performance-aware implementation choices.
- Maintainability as a first-class scoring concern.
- Tail-risk reduction across repeated stochastic runs.

It is also useful as a harness-evaluation target because the experiment preserves raw evidence and supports batch accumulation. The run metadata makes it possible to audit whether pooled results belong to the same frozen study.

## What RuleLedger v3 Does Not Prove

The completed study supports stronger claims than the interim 80-run draft did, but it should still not be overstated.

It supports:

- Strong claim: RuleLedger v3 differentiates reasoning effort in a controlled solo LLM coding benchmark.
- Strong claim: high and xhigh reasoning outperform low and medium reasoning on this task.
- Strong claim: high reasoning substantially outperforms medium reasoning.
- Moderate claim: xhigh is the best-performing setting by mean quality, hidden correctness, judge score, parity, performance, and tail behavior.

It does not yet prove:

- That every adjacent reasoning level is robustly separated.
- That medium is meaningfully better than low on this benchmark.
- That xhigh is reliably better than high under a conservative adjacent-comparison standard.
- That the same effect sizes will hold for other model families, other coding agents, or multi-agent topologies.
- That the LLM judge component would match independent expert human review in all cases.

The paper-grade version of the strongest claim would require preregistered statistical tests, independent replication, and ideally at least one non-LLM or human audit layer for judge-sensitive conclusions. The current result is still valuable because the primary endpoint is mostly hidden-test driven and because the artifact trail is complete.

## Limitations and Threats to Validity

Several limitations remain:

- The benchmark uses one main implementation model family and four reasoning settings, not a broad model marketplace.
- The judge is another LLM, held fixed across conditions, but not a substitute for independent human review.
- The benchmark is synthetic, even though it is designed to mimic realistic ledger engineering work.
- Hidden tests are finite and may not capture all semantically valid implementation strategies.
- Batch-level variance is visible. Small batches can invert adjacent reasoning levels.
- The execution environment used high local parallelism and `danger-full-access` sandboxing, which should be documented when comparing against other environments.
- Token metrics are clean for solo GPT-5.5 cells, but future mixed-agent studies will need careful attribution between GPT-5.5 and Spark usage.
- The current analysis uses approximate confidence intervals and descriptive effect sizes, not a preregistered inferential analysis plan.

These limitations do not erase the main result. They define the boundary around it.

## Recommendations

For publication or external presentation, the next stage should turn this white paper into a formal empirical report:

- Predeclare aggregate quality as the primary endpoint.
- Treat hidden correctness, judge score, parity, performance, minimality, tokens, and wall-clock time as secondary endpoints.
- Include batch-stratified plots and distribution plots, not only means.
- Add bootstrap confidence intervals or a preregistered mixed-effects analysis.
- Analyze repeat-index pairing only if the run design justifies it.
- Audit a sample of run diffs and judge rationales to produce a failure-mode taxonomy.
- Add an independent human or non-LLM review layer for claims about maintainability.
- Replicate with at least one additional model family or coding harness.

For operational use, high reasoning is the practical default on RuleLedger v3: it captures most of the observed quality improvement with materially lower token and latency cost than xhigh. Xhigh is justified when the benchmark user values best mean quality and tail-risk reduction over cost.

## Conclusion

RuleLedger v3 succeeds at the design goal that motivated it. It makes the benchmark complex enough for reasoning effort to matter. The task is no longer a simple patch exercise; it requires a model to synthesize requirements, preserve old contracts, implement a canonical replay model, keep two language implementations aligned, and produce maintainable code under hidden evaluation.

The completed 200-run study shows that this pressure produces meaningful separation. Low and medium reasoning cluster together. High reasoning creates the main quality jump. Xhigh produces the best mean score and the strongest tail behavior, though its adjacent advantage over high remains modest under this analysis.

The end product is a reproducible, artifact-backed benchmark that can support serious empirical discussion of reasoning effort in LLM software engineering. Its strongest current claim is not that every rung of the reasoning ladder is equally spaced. Its strongest claim is sharper and more useful: RuleLedger v3 exposes the point where additional reasoning begins to materially improve the ability of a coding model to maintain a coherent implementation across interacting software constraints.

## Artifact Inventory

Primary configuration and scoring:

- `configs/ruleledger_v3_paper_50.yaml`
- `configs/scoring_v3.yaml`

Benchmark task documents:

- `benchmark_template_v3/docs/ruleledger_v3_issue_brief.md`
- `benchmark_template_v3/docs/ruleledger_v3_architecture.md`

Development notes:

- `plans/stage-22-ruleledger-v3.md`
- `plans/batched-repeat-study-requirements.md`

Completed measured batches:

- `runs/20260605T190514-ruleledger_v3_paper_50-v3_paper_batch_01_r01_r05_measured`
- `runs/20260605T222018-ruleledger_v3_paper_50-v3_paper_batch_02_r06_r10_measured`
- `runs/20260610T081140-ruleledger_v3_paper_50-v3_paper_batch_03_r11_r20_measured`
- `runs/20260610T171024-ruleledger_v3_paper_50-v3_paper_batch_04_r21_r30_measured`
- `runs/20260611T053756-ruleledger_v3_paper_50-v3_paper_batch_05_r31_r40_measured`
- `runs/20260617T211106-ruleledger_v3_paper_50-v3_paper_batch_06_r41_r50_measured`

Selected matrix hashes:

| Batch | Selected matrix SHA-256 |
|---|---|
| v3-paper-batch-001 | `6f176c55b27d2ff7f1d670f4b1b978818d7066bcdaf0a6609ec5ded9506adab9` |
| v3-paper-batch-002 | `7db65beae0b0044dc0a6343be80367a7ce44a7259e4b6b809552e6bc6b1c7379` |
| v3-paper-batch-003 | `b886e9c82270f89cf9299f3e1f1d646f6c8c67482db296419497231d06071634` |
| v3-paper-batch-004 | `5906f80a742512bb6ae32604adb23d976b62985cd9bed8d28e7ecd49d6bce1f2` |
| v3-paper-batch-005 | `efd7dd8125f2fcdb156b26204f02c0b2aa3dbfa78803791fd2f325648cc114f9` |
| v3-paper-batch-006 | `f12c36300b6c99dfffa78ec0fbe40b79d9616ef1b87bf88861bf0b2edc67de60` |

Shared frozen hashes:

- Full matrix SHA-256: `2ec216ba7cf6d9e01528a355ac590aec7aedf8b026c9aa8d49f49fdd623a27e1`
- Benchmark template SHA-256: `edfde6362042bfdf100bedfe63c273c817072004cc42ff3952ad3afb9c319699`
- Hidden cases tree SHA-256: `bf742505d0503883a3e8dc001d41a16254b67d1aa3aea1fd337acb5e620a8d6b`
- Hidden manifest SHA-256: `63937005528b0ff1842bcd10a57617da49acbbbc0e4b67dfa8b5f65547ecb362`
- Scoring config SHA-256: `dc50227fd818efc567b756bc2be2bf6bf2a22850072bd7ab14ca6673c68cb76c`
- Experiment config SHA-256: `2f47b30ad9763cebb332fcbcef60488b0daab479c2aec2765f447d0af7d38aa3`
- Repository head for measured source: `2cd7314b10cacaf8b1b3089aa9febdd081b328bf`

## References

- RuleLedger v3 issue brief: `benchmark_template_v3/docs/ruleledger_v3_issue_brief.md`
- RuleLedger v3 architecture notes: `benchmark_template_v3/docs/ruleledger_v3_architecture.md`
- RuleLedger v3 development plan and calibration log: `plans/stage-22-ruleledger-v3.md`
- Batched repeat study requirements: `plans/batched-repeat-study-requirements.md`
- SWE-bench repository: https://github.com/swe-bench/SWE-bench
- SWE-bench Verified announcement: https://openai.com/index/introducing-swe-bench-verified/
- SWE-Bench Pro: https://openreview.net/forum?id=6RYawev6L9
- SWE-Lancer: https://openai.com/index/swe-lancer/
