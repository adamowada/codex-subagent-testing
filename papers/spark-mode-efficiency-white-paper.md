# Spark Mode Efficiency: Direct Edit vs Proposal Mode

Authored by Adam Owada/Codex

## Abstract

This paper evaluates when to use `gpt-5.3-codex-spark` subagents as coding
workers under a `gpt-5.5` root agent, and whether those Spark workers should
directly edit code or only propose changes. The benchmark is RuleLedger v3
([RuleLedger v3 white paper](ruleledger-v3-white-paper.md)), a cross-language
software-engineering task that requires TypeScript and Python implementations
to preserve prior APIs, implement new ledger semantics, maintain parity, pass
hidden tests, and remain reviewable.

The experiment compares three ways to implement the same RuleLedger v3 task at
each GPT-5.5 root reasoning level:

- Solo GPT-5.5, using the 50-run RuleLedger v3 benchmark-test results as the
  solo comparison group.
- GPT-5.5 root plus six Spark xhigh leaves in direct edit mode, with 20 runs
  per root reasoning level.
- GPT-5.5 root plus six Spark xhigh leaves in proposal mode, with 20 runs per
  root reasoning level.

Quality is a 0 to 1 composite score:

- Hidden correctness: 50%.
- TypeScript/Python hidden parity: 15%.
- Performance: 10%.
- Blind judge assessment: 22%.
- Minimality: 3%.

The headline results are:

- Best quality overall: solo GPT-5.5 xhigh at `0.755`.
- Xhigh with Spark direct leaves: `0.734`.
- Xhigh with Spark proposal leaves: `0.714`.
- Medium with Spark direct leaves: `0.622`, compared with `0.462`
  for medium solo and `0.696` for high solo.

Direct edit mode beat proposal mode on observed quality at all four root
reasoning levels: `+0.010` at low, `+0.093` at medium, `+0.060` at
high, and `+0.020` at xhigh. At low, medium, and high, direct edit also
used fewer GPT, Spark, and total implementation tokens than proposal mode.
The total-token savings for direct edit were about `183k` tokens per low run,
`477k` per medium run, and `1.064M` per high run. Xhigh was the exception in
budget shape: proposal mode saved about `242k` GPT tokens and `59k` total
tokens per run relative to xhigh direct, but it scored `0.020` lower on
quality.

Medium direct is the clearest Spark-assisted quality lift over the same root
reasoning level: it raised mean quality from `0.462` for medium solo GPT-5.5
to `0.622`, a `+0.160` absolute gain and about a 35% relative lift over
the solo medium score. That result should be compared against simply raising
the root reasoning level. High solo scored `0.696`, used about `176k` more
GPT tokens than medium direct, and was more efficient by quality per GPT token
using ratio-of-means math (`2.66e-7` versus `2.55e-7`). The practical
conclusion is: prefer solo xhigh for maximum quality, prefer high solo over
medium direct when GPT-token efficiency matters, and use direct-edit Spark
leaves when Spark budget is strategically cheaper or when parallel implementation
search is more valuable than raw token efficiency.

## Reader Context: Models and Reasoning Levels

This study uses two model families in different roles.

`gpt-5.5` is the root model. It plans the work, integrates leaf outputs into
the final measured workspace, and serves as the blind judge. The root reasoning
level is varied across `low`, `medium`, `high`, and `xhigh`. In this paper,
those labels should be read operationally as increasing reasoning effort:
lower levels are cheaper and lighter, while higher levels spend more compute
and tokens to reason through larger implementation and integration problems.

`gpt-5.3-codex-spark` is the leaf model. Spark is used as a coding-specialized
worker budget that is tracked separately from GPT-5.5 token usage. Every Spark
leaf in this experiment used xhigh reasoning. The experiment does not compare
different Spark reasoning levels; it compares how xhigh Spark leaves should be
used under GPT-5.5 roots.

The Spark topology is staged. A measured Spark-assisted run invokes:

1. A GPT-5.5 root planning stage.
2. Six independent Spark leaf stages.
3. A GPT-5.5 root integration stage.
4. A GPT-5.5 judge stage.

The final submitted code is whatever the GPT-5.5 root integration stage lands
in the final workspace. Spark leaf outputs supply diffs, proposals, test
evidence, and review notes for the root to integrate.

## Research Question

The experiment asks:

> Given a GPT-5.5 root and six xhigh Spark leaf agents, are Spark leaves more
> useful when they directly edit isolated leaf workspaces backed by git
> worktrees, or when they only produce proposals for the GPT root to implement?

The measured prompts made the edit permissions explicit.

The shared staged-topology prompt told every staged Spark run:

```text
The harness, not this Codex process, invokes the GPT root planning run, six
Spark leaf runs, and the GPT root integration run as separate measured
processes. Do not spawn subagents, invoke `codex`, call external AI, or start
other agent processes from inside any measured process.
```

The same prompt assigned exactly six Spark leaves:

```text
1. TypeScript parsing, normalization, views, and migration compatibility.
2. TypeScript replay, billing, reporting, performance, and public API
   integration.
3. Python parsing, normalization, views, and migration compatibility.
4. Python replay, billing, reporting, performance, and public API integration.
5. Cross-language parity, fixture, public-test, and regression review.
6. Adversarial review for localization, maintainability, performance, and
   hidden-test risk.
```

Direct edit leaves ran in isolated writable git worktrees. The prompt described
that environment to the model as an "isolated leaf workspace":

```text
You are in direct edit mode inside an isolated leaf workspace. You may edit
files in this copy. The root integration run will inspect your diff and decide
what to land in the final measured workspace.
```

Proposal leaves were told:

```text
You are in proposal mode. Do not edit files. Inspect the visible workspace and
return concrete findings, proposed patches, tests, and integration notes.
```

The GPT-5.5 root integrator received different instructions depending on mode.
For direct edit:

```text
Inspect the leaf diffs and manually integrate only changes you judge correct.
```

For proposal mode:

```text
Inspect the leaf proposals and implement only changes you judge correct.
```

All implementation agents also received the same RuleLedger v3 task prompt,
including this central instruction:

```text
Before finalizing, reconcile the implementation as one replay model across the
surfaces the brief names: summaries, CSV reports, TypeScript/Python parity,
replay digests, billing, and module ownership. Avoid a single-surface fix that
passes one symptom while leaving a separate code path for the next view.
```

These prompts matter because direct edit mode gives the root executable diffs
to inspect, while proposal mode gives the root written advice that still has to
be converted into code.

## Experiment Design

The reported Spark-assisted cells are the final 20-run cells for this
experiment. The paper does not separate earlier and later batches in the result
sections because the final analysis treats them as one design: four GPT-5.5
root reasoning levels crossed with two Spark leaf modes.

Spark-assisted matrix:

- Root reasoning levels: `low`, `medium`, `high`, `xhigh`.
- Spark modes: `direct`, `proposal`.
- Runs per Spark-assisted cell: 20.
- Spark leaves per run: six.
- Spark leaf reasoning: xhigh.
- Judge: GPT-5.5 xhigh.
- Benchmark: RuleLedger v3.

Solo comparison group:

- Source: the 50-run RuleLedger v3 benchmark-test results.
- Root reasoning levels: `low`, `medium`, `high`, `xhigh`.
- Runs per solo reasoning level: 50.
- Mode: solo GPT-5.5, with no subagents.

Concurrency was part of the harness configuration, not the measured model
prompt. Pilot, initial Spark-assisted, and xhigh runs used implementation jobs
5 and judge jobs 4. Low/medium and high Spark-assisted runs used implementation
jobs 7 and judge jobs 6. A two-run contemporaneous GPT-only bridge was kept as
a drift sanity check, but it is too small to replace the 50-run solo comparison
group and is not used as the official baseline in the tables below.

## Measurement

Reported precision is standardized across the RuleLedger and Spark papers: quality-like scores, deltas, intervals, and component means are rounded to three decimals; token counts are shown as whole-token means or `M` shorthand in prose; efficiency ratios use three significant figures in scientific notation.

The primary outcome is quality, a 0 to 1 composite from
`configs/scoring_v3.yaml`:

| Component | Weight | Meaning |
| --- | ---: | --- |
| Hidden correctness | 0.50 | Normalized hidden-test correctness on the frozen private RuleLedger v3 cases. |
| Hidden parity | 0.15 | TypeScript/Python agreement on hidden parity checks. |
| Performance | 0.10 | Normalized performance behavior on hidden workloads. |
| Judge | 0.22 | Blind GPT-5.5 xhigh judge score from available source, diffs, logs, public checks, and hidden-result summaries. |
| Minimality | 0.03 | Small penalty/reward signal based on production LOC relative to a target. |

The paper also reports:

- GPT implementation tokens: GPT-5.5 root planning and root integration tokens
  for Spark-assisted runs; total implementation tokens for solo runs.
- Spark implementation tokens: Spark leaf tokens only.
- Total implementation tokens: GPT implementation tokens plus Spark
  implementation tokens.
- Quality per GPT token and quality per total token, reported as ratio of
  means: mean quality divided by mean implementation tokens. This is the value
  a reader gets by doing the table math directly.
- Mean implementation elapsed seconds from the harness.
- Changed files, production LOC, and test LOC from measured diffs.

Token attribution is exact for the staged Spark-assisted design because GPT
and Spark roles ran as separate `codex exec --json` invocations. The analysis
parses usage from `turn.completed.usage` events in each role's JSONL stream.
Judge tokens are tracked separately and are excluded from the implementation
token efficiency figures in the main result tables.

## Results

### Quality and Score Components

| Root | Mode | Runs | Quality mean | Quality median | Quality sd | Hidden correctness | Hidden parity | Performance | Judge |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| low | solo | 50 | 0.434 | 0.447 | 0.181 | 0.364 | 0.531 | 0.556 | 0.394 |
| low | direct | 20 | 0.482 | 0.455 | 0.137 | 0.400 | 0.603 | 0.612 | 0.458 |
| low | proposal | 20 | 0.472 | 0.479 | 0.153 | 0.424 | 0.528 | 0.543 | 0.439 |
| medium | solo | 50 | 0.462 | 0.480 | 0.175 | 0.409 | 0.506 | 0.515 | 0.459 |
| medium | direct | 20 | 0.622 | 0.576 | 0.160 | 0.571 | 0.728 | 0.710 | 0.575 |
| medium | proposal | 20 | 0.529 | 0.489 | 0.114 | 0.439 | 0.661 | 0.663 | 0.522 |
| high | solo | 50 | 0.696 | 0.685 | 0.195 | 0.674 | 0.734 | 0.738 | 0.683 |
| high | direct | 20 | 0.712 | 0.691 | 0.158 | 0.680 | 0.775 | 0.775 | 0.698 |
| high | proposal | 20 | 0.652 | 0.593 | 0.162 | 0.635 | 0.736 | 0.718 | 0.575 |
| xhigh | solo | 50 | 0.755 | 0.709 | 0.171 | 0.739 | 0.791 | 0.800 | 0.752 |
| xhigh | direct | 20 | 0.734 | 0.693 | 0.152 | 0.720 | 0.750 | 0.750 | 0.751 |
| xhigh | proposal | 20 | 0.714 | 0.612 | 0.162 | 0.685 | 0.750 | 0.750 | 0.740 |

### Resource and Size Metrics

| Root | Mode | Runs | GPT tokens | Spark tokens | Total tokens | Quality/GPT token | Quality/total token | Elapsed seconds | Changed files | Prod LOC | Test LOC |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| low | solo | 50 | 815,190 | n/a | 815,190 | 5.32e-7 | 5.32e-7 | 199 | 2.68 | 286 | 6 |
| low | direct | 20 | 1,444,628 | 1,472,207 | 2,916,835 | 3.34e-7 | 1.65e-7 | 494 | 3.00 | 287 | 7 |
| low | proposal | 20 | 1,486,511 | 1,613,103 | 3,099,614 | 3.18e-7 | 1.52e-7 | 541 | 4.00 | 302 | 0 |
| medium | solo | 50 | 1,389,968 | n/a | 1,389,968 | 3.32e-7 | 3.32e-7 | 318 | 5.14 | 735 | 0 |
| medium | direct | 20 | 2,436,094 | 1,406,665 | 3,842,759 | 2.55e-7 | 1.62e-7 | 589 | 5.50 | 609 | 17 |
| medium | proposal | 20 | 2,508,418 | 1,811,092 | 4,319,510 | 2.11e-7 | 1.22e-7 | 628 | 6.00 | 774 | 10 |
| high | solo | 50 | 2,612,154 | n/a | 2,612,154 | 2.66e-7 | 2.66e-7 | 686 | 10.92 | 1,858 | 4 |
| high | direct | 20 | 2,801,135 | 632,108 | 3,433,243 | 2.54e-7 | 2.07e-7 | 650 | 10.45 | 1,856 | 0 |
| high | proposal | 20 | 2,933,084 | 1,563,753 | 4,496,837 | 2.22e-7 | 1.45e-7 | 751 | 10.20 | 1,602 | 12 |
| xhigh | solo | 50 | 3,333,886 | n/a | 3,333,886 | 2.26e-7 | 2.26e-7 | 1,019 | 12.08 | 2,359 | 6 |
| xhigh | direct | 20 | 3,877,968 | 610,527 | 4,488,495 | 1.89e-7 | 1.64e-7 | 951 | 12.85 | 2,385 | 34 |
| xhigh | proposal | 20 | 3,636,127 | 793,673 | 4,429,799 | 1.96e-7 | 1.61e-7 | 968 | 12.85 | 2,349 | 57 |

### Direct Edit Minus Proposal

Positive quality means direct edit was better. Negative token values mean
direct edit used fewer tokens than proposal mode.

| Root | Quality | GPT tokens | Spark tokens | Total tokens | Quality/GPT token | Quality/total token |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| low | +0.010 | -41,883 | -140,896 | -182,779 | 1.62e-8 | 1.30e-8 |
| medium | +0.093 | -72,324 | -404,427 | -476,751 | 4.44e-8 | 3.93e-8 |
| high | +0.060 | -131,950 | -931,645 | -1,063,595 | 3.19e-8 | 6.24e-8 |
| xhigh | +0.020 | +241,841 | -183,146 | +58,696 | -7.17e-9 | 2.28e-9 |

### Spark-Assisted Minus Solo

Positive quality means the Spark-assisted mode beat solo GPT-5.5 at the same
root reasoning level. Positive tokens mean the Spark-assisted mode used more
tokens than solo.

| Root | Mode | Quality | GPT tokens | Total tokens | Quality/total token | Quality/GPT token |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| low | direct | +0.049 | +629,438 | +2,101,645 | -3.67e-7 | -1.98e-7 |
| low | proposal | +0.038 | +671,321 | +2,284,424 | -3.80e-7 | -2.14e-7 |
| medium | direct | +0.160 | +1,046,126 | +2,452,791 | -1.71e-7 | -7.71e-8 |
| medium | proposal | +0.067 | +1,118,450 | +2,929,542 | -2.10e-7 | -1.21e-7 |
| high | direct | +0.016 | +188,981 | +821,089 | -5.91e-8 | -1.23e-8 |
| high | proposal | -0.044 | +320,931 | +1,884,684 | -1.21e-7 | -4.42e-8 |
| xhigh | direct | -0.021 | +544,083 | +1,154,609 | -6.30e-8 | -3.72e-8 |
| xhigh | proposal | -0.041 | +302,241 | +1,095,914 | -6.53e-8 | -3.01e-8 |

## Results by Reasoning Level

### Low

Low root reasoning is the cheapest GPT-5.5 root setting in the experiment, and
Spark assistance produced only a modest quality lift. Solo low scored
`0.434`. Low direct scored `0.482`, a `+0.049` improvement. Low
proposal scored `0.472`, a `+0.038` improvement.

The direct/proposal comparison at low is close on quality: direct beat proposal
by only `0.010`. The cost comparison is clearer. Low direct used about
`42k` fewer GPT tokens, `141k` fewer Spark tokens, and `183k` fewer total
implementation tokens than low proposal.

Compared with solo low, both Spark-assisted low modes are expensive. Low direct
used about `2.917M` total implementation tokens per run versus `815k` for solo
low. Low direct is a quality upgrade over low solo, best suited for situations
where the extra Spark spend is acceptable for a modest improvement.

### Medium

Medium is the strongest same-reasoning case for Spark subagents. Solo medium
scored `0.462`. Medium direct scored `0.622`, a `+0.160` absolute
gain. Medium proposal scored `0.529`, a `+0.067` gain.

Direct edit also clearly beat proposal at medium. It scored `0.093` higher
while using about `72k` fewer GPT tokens, `404k` fewer Spark tokens, and `477k`
fewer total tokens per run.

The important comparison is medium direct versus simply raising the root to
high. High solo scored `0.696`, which is `0.074` higher than medium
direct. High solo also had better GPT-token efficiency by ratio of means:
`2.66e-7` quality per GPT token versus `2.55e-7` for medium direct.
Medium direct is therefore not a replacement for high solo. Its best case is a
workflow where medium root behavior is desirable, Spark tokens are meaningfully
cheaper or separately budgeted, and parallel implementation search is worth
the coordination cost.

### High

High solo was already strong at `0.696`. High direct scored `0.712`, only
`+0.016` above high solo. High proposal scored `0.652`, which was
`-0.044` below high solo.

Within Spark-assisted high, direct edit is the better mode. It scored
`0.060` higher than proposal and used about `132k` fewer GPT tokens,
`932k` fewer Spark tokens, and `1.064M` fewer total tokens per run.

The solo comparison changes the recommendation. High direct is better than
high proposal, but high solo remains the cleaner default when total token usage
matters. The marginal quality gain from high direct over high solo is small,
and it costs about `821k` more total implementation tokens per run.

### Xhigh

Xhigh solo is the best quality result in the study: `0.755`. Both
Spark-assisted xhigh modes underperformed it. Xhigh direct scored `0.734`,
and xhigh proposal scored `0.714`.

Direct edit still beat proposal on quality by `0.020`, but xhigh proposal
has a different budget profile. Proposal used about `242k` fewer GPT tokens
and `59k` fewer total tokens than direct, while using about `183k` more Spark
tokens. If GPT tokens are the only scarce resource, xhigh proposal has a
narrow argument. If code quality is the goal, xhigh solo is better.

This is the most important caution in the paper. More agents did not improve
the highest-reasoning configuration. On this benchmark, a single xhigh GPT-5.5
agent appears better able to preserve the whole cross-language replay model
than a staged six-leaf Spark topology coordinated by an xhigh root.

## Interpretation

### Why Direct Edit Beat Proposal

Direct edit gave the GPT root concrete diffs to inspect. Even when the root did
not accept a leaf's work wholesale, it could compare executable code, tests,
and implementation choices. Proposal mode asked leaves to translate their work
into advice, then asked the root to translate that advice back into code. That
extra translation step likely created loss.

Proposal mode also made the Spark leaves spend tokens explaining work rather
than producing code. The measured resource table shows this pattern: proposal
used more Spark tokens than direct at every reasoning level. At low, medium,
and high it also used more GPT tokens and more total tokens, because the root
still had to implement the proposed changes after reading them.

The root retained final ownership of the measured workspace. In that setup,
diffs appear to be a better integration substrate than recommendations when the
task is a concrete coding benchmark with hidden tests.

### Why Tokens Increased

Spark assistance adds coordination costs before it can add value. A
Spark-assisted run includes root planning, six leaf contexts, leaf outputs,
and root integration. Those stages duplicate some task context, and the root
must spend additional tokens reading and reconciling leaf evidence.

That cost is visible even when Spark improves quality. Medium direct improved
quality substantially, but it used about `2.453M` more total implementation
tokens than medium solo. Low direct improved quality modestly and used about
`2.102M` more total tokens than low solo. Spark can be worthwhile when Spark
tokens are a separate or cheaper budget, with the tradeoff that coordination
becomes part of the implementation cost.

Proposal mode is especially vulnerable to coordination cost. Leaves cannot
make changes, so they often produce longer explanations, proposed patches, and
integration notes. The root then has to spend GPT tokens converting those notes
into final code.

### Why Solo Won at Higher Reasoning

RuleLedger v3 rewards a coherent global implementation model. The task spans
normalization, replay, billing, reporting, migration compatibility,
performance, and TypeScript/Python parity. At xhigh, solo GPT-5.5 appears to
have enough reasoning budget to keep that global model in one place.

The staged Spark topology decomposes the task into useful local views, but it
also fragments context. The root must decide which local patches to trust,
merge partially overlapping ideas, and avoid parity drift. At medium, that
extra search helped. At xhigh, the coordination overhead and fragmentation
appear to outweigh the benefit of six additional workers.

## Recommendations

Use solo xhigh when maximum code quality matters most. It produced the highest
mean quality in the experiment (`0.755`) and beat both xhigh Spark-assisted
modes. This is the cleanest conclusion for developers working on high-stakes,
cross-language tasks where cost is secondary to correctness.

Use medium direct when medium reasoning is the practical root setting and
Spark budget is cheaper, separately constrained, or useful for parallel search.
It delivered the clearest Spark-assisted lift over the same reasoning level:
`0.622` versus `0.462` for medium solo. It did not beat high solo on
quality or GPT-token efficiency.

Use high solo as the default high-reasoning configuration when total token
usage matters. High direct is better than high proposal, but it barely improves
over high solo and costs more total tokens. High direct is reasonable only when
the extra Spark budget is cheap enough to justify chasing a small observed
quality gain.

Use low direct only when a modest quality lift is worth a large token increase.
Low direct beats low proposal and low solo on quality, but the lift over solo
is small relative to total token cost.

Do not use proposal mode as the default Spark strategy. Proposal mode can be
useful when leaves are intentionally restricted to review, when edits must be
blocked for governance reasons, or when an xhigh root needs to save GPT tokens
and a small quality drop is acceptable. For this benchmark, though, proposal
lost to direct edit on quality at every reasoning level.

For developers balancing quality, wall clock, and cost, the practical heuristic
is:

- Need the best code quality: use solo xhigh.
- Need high quality with strong GPT-token efficiency: use high solo before
  medium direct.
- Need a medium-root topology and can spend Spark: use medium direct.
- Need cheap exploration or review-only advice: proposal mode is acceptable,
  but treat it as review support rather than the primary implementation path.
- Counting GPT and Spark tokens equally: Spark-assisted modes are usually less
  token efficient than solo, even when they improve quality.

## Limitations

The benchmark is RuleLedger v3. It stresses cross-language parity, replay
semantics, compatibility, and hidden-test robustness. Results may differ for
tasks that are more modular, easier to split, or more naturally review-based.

The solo comparison group has 50 runs per reasoning level, while each
Spark-assisted direct/proposal cell has 20 runs. The sample sizes are large
enough to guide practical decisions, but not every observed gap should be read
as a settled statistical law.

The solo comparison group comes from the RuleLedger v3 benchmark testing, not
from the same exact Spark-assisted run batch. A two-run contemporaneous GPT-only
bridge was kept as a drift check, but it was too small and noisy to replace the
50-run solo results.

All Spark leaves used xhigh reasoning. The experiment does not answer whether
lower-reasoning Spark leaves would be more token efficient, or whether mixed
Spark reasoning levels would work better.

The tested topology is fixed: one GPT root, six Spark leaves, and one GPT
integration pass. Deeper topologies, fewer leaves, more specialized leaves,
automatic patch application, or stronger merge tooling could change the
results.

The quality score includes a blind model judge. The judge is not a substitute
for human review, although it is only one component of the composite score and
hidden correctness carries the largest weight.

Token counts are cost inputs rather than prices. Spark and GPT tokens may have
different prices, quotas, or opportunity costs. This paper reports token counts
and quality-per-token ratios, but it does not convert them into dollars.

Elapsed seconds are harness measurements from batch execution. They are useful
for comparing this experiment, but they are not a full product-latency model
for an interactive developer workflow.

## Reproducibility Notes

Key source files:

- Experiment plan:
  `plans/experiments/spark-mode-efficiency-direct-vs-proposal.md`
- Shared RuleLedger v3 prompt: `prompts/task_common_v3.md`
- Staged Spark prompt: `prompts/task_staged_spark_v3.md`
- Judge prompt: `prompts/judge.md`
- Scoring profile: `configs/scoring_v3.yaml`
- Final analysis script: `scripts/analyze_spark_mode_efficiency.py`

Key result artifacts:

- Final analysis directory: `runs/analysis/spark_mode_efficiency_final`
- Final summary JSON: `runs/analysis/spark_mode_efficiency_final/summary.json`
- Final summary CSV: `runs/analysis/spark_mode_efficiency_final/summary.csv`
- Final rendered summary: `runs/analysis/spark_mode_efficiency_final/summary.md`
- Pilot run: `runs/20260624T023048-spark_mode_efficiency_pilot-pilot`
- Spark-assisted low/medium run:
  `runs/20260625T054133-spark_mode_efficiency_low_medium_extension-low_medium_extension_j7_j6`
- Spark-assisted high run:
  `runs/20260624T220413-spark_mode_efficiency_high_extension-high_extension_j7_j6`
- Spark-assisted xhigh run:
  `runs/20260624T105944-spark_mode_efficiency_xhigh_extension-xhigh_extension`
- Spark-assisted initial run:
  `runs/20260624T053702-spark_mode_efficiency_main-main`

Final analysis command:

```powershell
python scripts\analyze_spark_mode_efficiency.py --experiment-dir runs\20260624T023048-spark_mode_efficiency_pilot-pilot --experiment-dir runs\20260624T053702-spark_mode_efficiency_main-main --experiment-dir runs\20260625T054133-spark_mode_efficiency_low_medium_extension-low_medium_extension_j7_j6 --experiment-dir runs\20260624T220413-spark_mode_efficiency_high_extension-high_extension_j7_j6 --experiment-dir runs\20260624T105944-spark_mode_efficiency_xhigh_extension-xhigh_extension --output-dir runs\analysis\spark_mode_efficiency_final
```

Validation evidence:

- Pilot `validation.json`: `passed`
- Initial Spark-assisted run `validation.json`: `passed`
- Low/medium Spark-assisted run `validation.json`: `passed`
- High Spark-assisted run `validation.json`: `passed`
- Xhigh Spark-assisted run `validation.json`: `passed`
- Final analysis rows: `384`
- Full repository test suite: `python -m pytest -q` (`193 passed in 11.96s`)
