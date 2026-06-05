# Stage 22: RuleLedger V3 Reasoning-Differentiation Benchmark

## Objective

Develop RuleLedger v3 so the benchmark can differentiate GPT-5.5 solo runs at
`low`, `medium`, `high`, and `xhigh` reasoning levels. The target is not merely
to make the task harder. The target is a calibrated benchmark where added
reasoning budget has a clear opportunity to improve outcomes through planning,
localization, multi-file coordination, regression control, and performance
engineering.

The working loop is:

1. Improve the benchmark.
2. Run a one-repeat solo sanity sweep across `low`, `medium`, `high`, and
   `xhigh`.
3. If results separate cleanly, run multiple repeats to check consistency.
4. If results cluster or invert, analyze the failure modes and adjust the v3
   benchmark assets, generator, or scoring profile.
5. Preserve each checkpoint as ACP: artifacted, checkable progress.

## Public Benchmark Lessons

RuleLedger v3 should borrow from recent SWE benchmark design rather than only
adding more hidden unit tests.

- SWE-bench and SWE-bench Verified demonstrate the value of fail-to-pass and
  pass-to-pass tests on real repositories, but also show that underspecified
  issues, over-specific tests, and unreliable environments can make a benchmark
  unfair instead of hard.
  Source: https://openai.com/index/introducing-swe-bench-verified/
- SWE-Bench Pro explicitly raises difficulty through diverse, actively
  maintained repositories, substantial multi-file changes, human-augmented
  requirements, reproducible environments, contamination controls, and
  fail-to-pass plus pass-to-pass scoring. It reports that performance degrades
  sharply as file count increases and the frontier/smaller-model gap widens
  beyond roughly three files.
  Source: https://openreview.net/forum?id=9R2iUHhVfr
- SWE-CI shifts evaluation from static one-shot repair toward long-term
  maintainability by replaying repository evolution across dozens of analysis
  and coding rounds.
  Source: https://arxiv.org/abs/2603.03823
- SWE-fficiency highlights a missing dimension in functional benchmarks:
  correct but slow code is still broken, and performance engineering requires
  bottleneck localization plus tradeoff reasoning.
  Source: https://www.openhands.dev/blog/20260216-swefficiency-benchmark
- SWE-Lancer ties tasks to real freelance economic value and uses end-to-end
  tests verified by experienced engineers.
  Source: https://openai.com/index/swe-lancer/
- ProgramBench shows that holistic software construction stresses architecture,
  behavioral inference, and project organization. It also warns that models
  often collapse complex work into monolithic single-file solutions.
  Source: https://arxiv.org/abs/2605.03546
- OpenAI's 2026 SWE-bench Verified retirement note reinforces that older public
  issue benchmarks can stop measuring frontier coding once contamination and
  flawed tests dominate the residual misses. RuleLedger should therefore keep
  hidden cases generated from private fixtures, while keeping visible
  requirements fair and human-interpretable.
  Source: https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/
- SWE-Bench+ reports that solution leakage and weak tests can greatly inflate
  apparent solve rates. This supports v3's split between visible issue-style
  requirements and hidden pass/fail/parity/performance cases that validate
  general behavior rather than a named fixture.
  Source: https://arxiv.org/abs/2410.06992
- SWE-bench Multimodal shows that real software issues often include partial
  context beyond a literal rule list. RuleLedger v3 should mimic that pressure
  textually with support-escalation notes that require synthesizing intent,
  compatibility, and module ownership.
  Source: https://www.swebench.com/multimodal.html

## Why V2 Is Not Enough

RuleLedger v2 improved semantic depth, but its main implementation surfaces are
still easy to localize. A capable agent can read the visible rule list and patch
the obvious TypeScript and Python files. That tests careful rule following, but
it gives high and xhigh reasoning limited room to outperform medium reasoning.

V3 should preserve the deterministic subscription-ledger domain while adding
software-engineering pressure:

- More files and cross-module contracts.
- Existing behavior that must not regress.
- Public issue-style requirements rather than a single fully ordered rule list.
- Hidden fail-to-pass, pass-to-pass, metamorphic, parity, and performance
  checks.
- A maintainability signal that discourages monolithic bypasses.
- A calibration ladder where different categories are expected to separate
  different reasoning levels.

## Target Calibration

The initial v3 solo sanity sweep should produce visible spread, not perfect
monotonicity on the first try. A useful first target:

| Reasoning | Expected Pattern |
|---|---|
| low | Passes basic public checks and some normalization/reporting cases, but misses cross-module or performance interactions. |
| medium | Solves most ordinary behavior, with failures in deep lineage, evolution/regression, or large-workload cases. |
| high | Handles most hidden behavior and parity, with occasional misses around maintainability or staged interactions. |
| xhigh | Best aggregate quality and fewer category holes, but still below saturation so the benchmark remains informative. |

Do not tune by making requirements vague. Tune by increasing interaction depth,
repo navigation, staged regression pressure, and runtime constraints.

## V3 Asset Shape

Add v3 as a new benchmark version, not a mutation of v2:

- `benchmark_template_v3/`
  - TypeScript and Python public packages split across 8-15 source files each.
  - Visible public tests that cover smoke behavior and regression examples.
  - Public docs under `docs/` containing an issue brief, architecture map, API
    contracts, and migration notes.
  - Starter code that is intentionally incomplete but coherent enough to run.
- `prompts/task_common_v3.md`
  - Issue-resolution style task prompt.
  - Explicit nested-Codex prohibition.
  - Clear final JSON contract.
  - No hidden case names, hidden case paths, or expected hidden payloads.
- `hidden_tests/generators/ruleledger_v3_oracle.py`
  - Private oracle independent from the starter implementation.
  - May reuse v2 semantics where appropriate, but v3 expected outputs should be
    generated from the v3 oracle and fixed seed.
- `hidden_tests/generators/generate_v3_cases.py`
  - Deterministic generator with manifest hashes.
  - No hand-edited generated cases.
- `hidden_tests/cases_v3/`
  - Generated private cases only.
- `configs/scoring_v3.yaml`
  - Hidden correctness dominates, but include pass-to-pass, performance, parity,
    maintainability/minimality, and judge signals.
- `configs/ruleledger_v3_sanity.yaml`
  - Four solo cells: low, medium, high, xhigh, one repeat each.
- `configs/ruleledger_v3_experiment.yaml`
  - Multi-repeat follow-up matrix after the sanity sweep shows useful spread.

## V3 Hidden Categories

Recommended first categories:

- `public_gate`: public tests and typecheck remain low-weight gates.
- `fail_to_pass`: new v3 issue requirements that must become true.
- `pass_to_pass`: v2 compatibility and existing v3 behavior that must not
  regress.
- `localization`: cases that require edits across parser, ledger, billing,
  reporting, and migration modules.
- `evolution`: staged requirements where an earlier fix can regress after a
  later one.
- `metamorphic`: shuffled input, duplicate idempotence, unrelated-account
  injection, split-batch equivalence, and replay stability.
- `parity`: byte-identical TypeScript/Python report output and JSON-compatible
  summaries.
- `performance`: 50k-250k event workloads with timeouts that catch quadratic
  algorithms.
- `maintainability`: deterministic source-shape checks and judge review to
  discourage one giant replacement file.

## Implementation Strategy

1. Land the v3 planning contract and matrix config tests.
2. Scaffold `benchmark_template_v3` from v2, then split implementation into
   modules while preserving public API compatibility.
3. Add v3 public docs and prompt text in issue-style form.
4. Add config/scoring files and matrix tests for the four-run sanity sweep.
5. Add an initial v3 generator and hidden runner support.
6. Run static tests, then a dry-run of the v3 sanity config.
7. Run the measured low/medium/high/xhigh sanity sweep when Codex execution is
   available and cost/time are acceptable.
8. Compare category spread and adjust only through generator/template/scoring
   source changes.

## Acceptance Criteria

Static readiness:

- V1 and v2 tests still pass.
- V3 config expands to exactly four sanity runs with root reasoning levels
  `low`, `medium`, `high`, and `xhigh`.
- V3 prompts render without hidden-test leakage.
- V3 starter public checks pass before measured agents run.
- V3 hidden cases regenerate deterministically from source.

Calibration readiness:

- The v3 sanity run produces preserved prompts, configs, diffs, logs, usage,
  hidden results, judge output, scores, aggregate outputs, and validation
  reports.
- No major hidden category saturates across all four reasoning levels.
- Aggregate quality and at least two important hidden categories show visible
  reasoning-level spread.
- Multi-repeat follow-up confirms the spread is not a one-run accident.

## Checkpoint: Windows Execution Guard

The first measured v3 sanity attempt did not produce reasoning data. All runs
were no-op baselines because Codex shell commands failed under
`workspace-write`/`read-only` with `windows sandbox: spawn setup refresh`.

Follow-up smoke tests showed:

- `codex exec --sandbox workspace-write` reproduced the Windows sandbox spawn
  failure for shell commands.
- `codex exec --sandbox read-only` reproduced the same shell failure.
- `codex exec --sandbox danger-full-access` allowed shell commands to run.

V3 sanity and follow-up configs therefore record `danger-full-access` as the
effective root and judge sandbox for this Windows workflow. The original initial
experiment contract still requires a read-only judge sandbox.

A second single-run smoke then hit the account-level Codex usage limit before
model work began. The harness treats Codex JSONL `error`/`turn.failed` events
as failed implementation infrastructure, preserves the failure summary in
`state.json`, and forces quality to `0.0` for those infrastructure-failed runs
instead of scoring the starter baseline as a partial benchmark result.

## Checkpoint: First V3 Sanity Signal

Run `20260531T054503-ruleledger_v3_sanity-v3_sanity_measured_02` completed the
four solo reasoning cells after quota reset. Official quality was initially
zeroed because malformed implementation/judge final JSON marked otherwise
healthy Codex turns as infrastructure failures. The raw hidden results still
showed the desired reasoning ladder:

- low: hidden correctness `0.363636`, no source changes.
- medium: hidden correctness `0.363636`, no source changes.
- high: hidden correctness `0.636364`, two runtime files changed.
- xhigh: hidden correctness `1.0`, seven focused module/test files changed.

This is useful benchmark signal, not an infrastructure failure. The harness now
keeps malformed final JSON as recorded protocol evidence and judge-score loss,
but only treats process failures, timeouts, missing event streams, and Codex
`error`/`turn.failed` events as implementation infrastructure failures.

Next calibration step: rerun the four-run v3 sanity sweep with the corrected
harness scoring path, then run the multi-repeat follow-up if the ladder remains
visible.

## Checkpoint: Reasoning-Pressure Hardening

The next hardening pass incorporated the SWE-benchmark lessons above into the
RuleLedger v3 generator and prompt:

- Added source-shape localization pressure so a measured run cannot solve v3
  only by growing the compatibility runtime.
- Added issue-style ambiguity in the visible brief and prompt instead of a full
  hidden truth table.
- Added harder evolution cases for audit-visible duplicate IDs, merge chains,
  post-merge source events, corrections, invoices, and seats.
- Added an 11k-event merge/correction performance digest to catch replay logic
  that scales only on simple per-account streams.

Starter hidden score after this pass was `18/49` points (`0.367347`
point-score), with `localization` and `fail_to_pass` at zero and the simpler
compatibility/metamorphic/parity categories still passing.

Run `20260604T104608-ruleledger_v3_sanity-v3_sanity_measured_04` showed better
separation but still saturated high and xhigh hidden correctness:

| Cell | Reasoning | Hidden Points | Hidden Categories | Quality |
|---|---:|---:|---|---:|
| V3S0 | low | `39/49` | localization `0.0` | `0.664865` |
| V3S1 | medium | `43/49` | localization `0.4` | `0.718919` |
| V3S2 | high | `49/49` | all saturated | `0.762906` |
| V3S3 | xhigh | `49/49` | all saturated | `0.757062` |

Qualitatively, the run was useful: low made a runtime-only patch, medium
localized mostly into replay and missed merge state migration, while high and
xhigh both performed broad modular rewrites. The remaining problem was that the
hidden suite did not distinguish high from xhigh on correctness.

## Checkpoint: Runtime-Boundary Calibration

To target the high/xhigh tie without making hidden behavior arbitrary, the next
pass added a separate localization contract for compatibility runtime files:
after domain modules own v3 logic, `src/runtime.ts` and `ruleledger/_runtime.py`
should remain thin delegates instead of a stale second implementation. This is
a split-brain compatibility risk, not just style preference, and it follows the
visible architecture notes.

The new generated suite has 28 language cases and 53 possible points. Replaying
it against the previous measured outputs produced the intended retrospective
ladder: low `39/53`, medium `43/53`, high `49/53`, xhigh `53/53`. The starter
baseline remained weak at `18/53`.

Fresh measured run
`20260604T114216-ruleledger_v3_sanity-v3_sanity_measured_05` adapted to the
visible runtime-boundary guidance:

| Cell | Reasoning | Hidden Points | Main Hidden Misses | Quality |
|---|---:|---:|---|---:|
| V3S0 | low | `38/53` | merge-chain evolution plus module/runtime ownership | `0.617073` |
| V3S1 | medium | `48/53` | chain merge/correction evolution | `0.710337` |
| V3S2 | high | `53/53` | none | `0.766844` |
| V3S3 | xhigh | `53/53` | none | `0.760250` |

This is a strong low/medium/high separation and a useful architecture signal.
It still does not fully meet the original calibration target because high and
xhigh tie on hidden correctness; they separate only through minimality,
implementation tokens, and judge-observed residual risks. A quick oracle fuzz
probe found candidate next edges around corrected source-account plan changes
after merge and TypeScript/Python invalid-date parity. These should be reviewed
for semantic fairness before adding another hidden case. The next calibration
step is either a multi-repeat sweep to measure variance at the current
difficulty, or one more evolution/parity hardening pass if strict high-vs-xhigh
correctness spread is required.

## Checkpoint: Exact-Proration Top-End Pressure

The next hardening pass added one fair pass-to-pass compatibility edge for
large-quantity proration. The visible v2 billing rule `BL-004` already requires
integer/rational arithmetic instead of floating point. A fuzz probe found that
the measured high solution still used TypeScript `number` arithmetic while the
measured xhigh solution used `BigInt`. The new generated case uses a safe JSON
integer quantity greater than `100_000_000_000` and expects exact cent rounding
for a near-full-period starter-to-pro change.

The generated v3 suite now has 30 language cases and 57 possible points. The
starter baseline remains weak at `20/57`, with `fail_to_pass` and
`localization` at zero.

Fresh measured run
`20260604T125222-ruleledger_v3_sanity-v3_sanity_measured_06` produced a clear
top-end correctness split:

| Cell | Reasoning | Hidden Points | Main Hidden Misses | Quality |
|---|---:|---:|---|---:|
| V3S0 | low | `26/57` | exact proration, fail-to-pass, localization, performance | `0.462222` |
| V3S1 | medium | `20/57` | no-op implementation; broad evolution/localization misses | `0.395556` |
| V3S2 | high | `30/57` | exact proration, fail-to-pass, evolution, performance | `0.487698` |
| V3S3 | xhigh | `52/57` | one two-language evolution case | `0.704538` |

The hidden categories now differentiate the high/xhigh boundary: high still
misses `pass_to_pass`, `fail_to_pass`, `evolution`, and `performance`, while
xhigh reaches full `fail_to_pass`, `localization`, `pass_to_pass`, and
`performance`. The single-repeat low/medium ordering is still noisy because
the medium run was effectively a no-op. The next calibration step should be a
multi-repeat sanity sweep to estimate variance before further hidden-case
hardening.

The run completed all implementation, hidden, report, and validation artifacts.
Final validation warned only on judge-output shape: the judge responses did not
consistently provide recognized numeric score fields, so the judge component
scored as zero. The correctness spread above is therefore driven by hidden
tests, public checks, typecheck, performance, parity, and minimality rather than
numeric judge scoring.

## Checkpoint: Multi-Repeat Variance Finding

The three-repeat follow-up run
`20260604T134244-ruleledger_v3_full-v3_full_measured_01` completed all 12
implementations, judges, scores, aggregate outputs, HTML report, PDF report,
CSV, SQLite, and validation artifacts. Validation warned only that every judge
final response failed strict JSON parsing and therefore contributed zero judge
score. Hidden-test isolation, run artifacts, resume compatibility, and report
outputs passed validation.

Hidden correctness showed that the exact-proration hardening improved the
single-run top-end signal, but did not produce a stable low/medium/high/xhigh
ladder across repeats:

| Reasoning | Hidden Points By Repeat | Mean Hidden Points | Mean Quality |
|---|---:|---:|---:|
| low | `44/57`, `40/57`, `20/57` | `34.67` | `0.546126` |
| medium | `57/57`, `55/57`, `46/57` | `52.67` | `0.728133` |
| high | `50/57`, `47/57`, `55/57` | `50.67` | `0.697171` |
| xhigh | `52/57`, `57/57`, `57/57` | `55.33` | `0.736159` |

The result is useful but not complete. It proves low is unstable and usually
weaker, and it keeps xhigh as the best average performer. It also shows that
medium can saturate the current hidden suite and that high does not reliably
beat medium. The benchmark is therefore close to the target, but current
evidence does not prove clear differentiation between every adjacent reasoning
level.

Recurring misses mapped to named cases:

- `case-332dfe6baf13` -> `v3.compat.proration_large_quantity_exactness`.
- `case-3dd88ef1ca5b` -> `v3.evolution.chain_merge_correction`.
- `case-13275aa6eee4` -> `v3.localization.module_ownership`.
- `case-80e510435da1` -> `v3.localization.runtime_compatibility_boundary`.
- `case-dd63e85189dc` -> `v3.reasoning.audit_before_late_plan`.
- `case-48ce9076decc` -> `v3.reasoning.audit_after_correction`.

Next hypothesis: the current suite still rewards careful implementation of an
explicit rule list more than it rewards high/xhigh-style triage under human
ambiguity. The next benchmark hardening pass should add visible support-style
escalation notes that require synthesizing priority, backwards compatibility,
and cross-module ownership without enumerating every fixture. Hidden cases
should validate fair implications of those visible notes, such as conflicting
audit/business views, normalized invalid optional timestamps, deterministic
cross-language ordering, and report/billing effects after merge correction.
This should be done by changing the visible v3 issue brief, generator/oracle,
and generated cases together, then rerunning the one-repeat sanity sweep before
another multi-repeat check.

## Checkpoint: Support-Escalation Ambiguity Pass

The next hardening pass added visible "Recent Support Escalations" to the v3
issue brief and generated three fair hidden implications:

- `v3.compat.invalid_optional_period_end`: optional invoice period timestamps
  like `2026-02-30T00:00:00Z` must fail normalization rather than host-date
  rollover.
- `v3.compat.report_lexical_ordering`: report rows sort by plain deterministic
  string order, not locale-aware or natural numeric collation.
- `v3.parity.merge_source_correction_report`: a correction recorded on a source
  account after merge still targets the original source event and updates the
  canonical destination report.

The generated v3 suite now has 36 language cases and 67 possible points. A
baseline hidden-runner pass against the starter template completed without
runner errors and scored `23/67` points (`15/36` language cases), so the new
cases are executable and do not make the starter accidentally strong.

Fresh measured run
`20260604T152750-ruleledger_v3_sanity-v3_sanity_measured_07` completed all
implementations, judges, scores, aggregate outputs, HTML report, PDF report,
CSV, SQLite, and validation artifacts. Validation warned only that every judge
final response failed strict JSON parsing and therefore contributed zero judge
score; hidden-test isolation, run artifacts, resume compatibility, and report
outputs passed validation.

| Cell | Reasoning | Hidden Points | Hidden Executions | Main Hidden Misses | Quality |
|---|---:|---:|---:|---|---:|
| V3S0 | low | `32/67` | `21/36` | exact proration, chain merge/correction, localization, merge-source correction, performance, audit views | `0.394902` |
| V3S1 | medium | `55/67` | `31/36` | TypeScript exact proration and architecture/runtime ownership | `0.682353` |
| V3S2 | high | `50/67` | `29/36` | TypeScript exact proration, chain merge/correction, architecture/runtime ownership | `0.633333` |
| V3S3 | xhigh | `67/67` | `36/36` | none | `0.758813` |

This pass materially improved top-end separation: xhigh solved every hidden
case and was the only cell to satisfy both domain behavior and module-ownership
pressure. It also showed the new support-style cases are fair but not by
themselves sufficient for medium/high separation: all non-low runs solved the
invalid-date, lexical-ordering, and merge-source-correction cases, while low
missed only the merge-source-correction support case among the new additions.

The calibration remains incomplete for the original adjacent-level goal.
Medium beat high in this single repeat because medium solved the evolution
chain case and high did not. The current evidence supports a useful split of
low vs medium/high and medium/high vs xhigh, but not a stable monotonic
low/medium/high/xhigh ladder. Next hypotheses:

- Add another evolution or bitemporal case that rewards full chain reasoning
  without being as easy for medium to saturate, possibly involving audit-visible
  correction/void operations across a merge chain and report/proration impact.
- Add an exact-arithmetic or TypeScript-specific compatibility case that is
  visible through the billing docs but hard to patch with `number` arithmetic.
- Consider weighting or category design so architecture/localization gains
  from xhigh remain visible without letting medium/high behavioral misses be
  masked by broad pass-to-pass coverage.

## Checkpoint: Bitemporal Merge-Chain Pressure

The next hardening pass turned the support-escalation ambiguity into paired
hidden cases rather than a single fixture:

- `v3.reasoning.merge_chain_audit_before_source_operations`: a two-hop source
  merge chain where late source-side operations are not yet audit-visible, so
  the final destination still reflects the inherited original usage, payment,
  invoice, and merge lineage.
- `v3.reasoning.merge_chain_after_source_corrections`: the same chain after
  late corrections become audit-visible, requiring the original source usage
  and payment to be amended before replaying into the final destination.
- `v3.evolution.merge_chain_void_retracts_source_correction`: a later void that
  references the correction record must void the original corrected usage fact,
  while preserving the corrected payment and final report row.

The visible issue brief now says support views may carry separate business and
audit cutoffs, that audit visibility decides which corrections/voids are known,
and that voiding a correction event retracts the original corrected fact. This
keeps the hidden cases fair while still requiring multi-step synthesis across
bitemporal replay, correction/void targeting, account alias lineage, and CSV
reporting.

Targeted verification after this pass:

- `python -m pytest -q tests\test_stage22_ruleledger_v3.py` -> `13 passed`.
- `python -m pytest -q` -> `170 passed`.
- Starter hidden-runner baseline -> `23/83` points, `15/42` language cases, no
  runner errors.

Fresh measured run
`20260604T162656-ruleledger_v3_sanity-v3_sanity_measured_08` completed all
four implementations, judges, scores, aggregate outputs, HTML report, PDF
report, CSV, SQLite, and validation artifacts. Validation again warned that
judge outputs were not parsed as strict JSON, so the reported quality scores
still include zero judge contribution.

| Cell | Reasoning | Hidden Points | Hidden Executions | New Bitemporal Cases | Quality |
|---|---:|---:|---:|---|---:|
| V3S0 | low | `29/83` | `19/42` | failed all six language executions | `0.311642` |
| V3S1 | medium | `23/83` | `15/42` | failed all six language executions | `0.266865` |
| V3S2 | high | `77/83` | `39/42` | passed all six language executions | `0.721505` |
| V3S3 | xhigh | `81/83` | `41/42` | passed all six language executions | `0.743887` |

This pass materially improved the high/xhigh split from the lower reasoning
cells. The new bitemporal merge-chain cases behaved as intended: only high and
xhigh solved them in both TypeScript and Python. Xhigh still led high, mainly
because it also satisfied module ownership/runtime pressure that high only
partly solved.

The full objective is still not proven. Medium produced a near-baseline/no-op
implementation in this repeat, so low beat medium slightly and the evidence is
not a clean adjacent reasoning ladder. The next calibration step should be a
multi-repeat sweep or a targeted second sanity repeat to determine whether the
medium result is stochastic noise. If medium remains unstable, add one or two
medium-accessible but low-resistant cases so the bottom of the ladder has a
more reliable separation without weakening the high/xhigh pressure.

A targeted medium-only recheck
`20260604T171449-ruleledger_v3_sanity-v3_medium_recheck_01` confirmed the
six-second medium result was a prompt/measurement anomaly rather than the
normal medium behavior. The recheck spent `374.5s` in implementation, changed
four files, and scored `71/83` hidden points (`37/42` language executions),
quality `0.710448`. It failed TypeScript exact proration and both
architecture/runtime ownership checks, matching the expected medium profile.

The subsequent 12-run consistency sweep
`20260604T172734-ruleledger_v3_full-v3_full_measured_02` completed three
repeats per reasoning level:

| Reasoning | Hidden Scores | Mean Hidden | Mean Quality | Notes |
|---|---:|---:|---:|---|
| low | `0.572473`, `0.825564`, `0.326905` | `0.574981` | `0.521543` | high variance, often misses architecture and bitemporal chain pressure |
| medium | `0.523375`, `0.854135`, `0.854135` | `0.743882` | `0.638209` | two strong behavioral runs, still misses architecture/runtime and TS exact proration |
| high | `0.985714`, `0.704052`, `0.985714` | `0.891827` | `0.697742` | two near-perfect runs, one bitemporal-chain miss |
| xhigh | `0.718337`, `1.000000`, `1.000000` | `0.906112` | `0.705230` | two perfect runs, one bitemporal-chain miss |

This is the best evidence so far: means are monotonic across all four reasoning
levels and the medium no-op did not recur. It is still not a fully proven clear
ladder because high and xhigh overlap heavily and each had one chain-family
miss. A stable xhigh/high distinction did appear in TypeScript exact billing:
high failed `v3.compat.proration_large_quantity_exactness` in all three
repeats, while xhigh passed it in all three repeats. The next hardening pass
should broaden that fair compatibility pressure rather than inventing vague
new requirements.

## Checkpoint: Exact Compatibility Tail Pass

The next pass adds visible support notes and hidden pass-to-pass cases for two
old-behavior tails that high-reasoning runs commonly miss while xhigh handles:

- exact large-seat downgrade proration with half-away-from-zero rounding across
  both negative credits and positive replacement charges;
- archival four-digit timestamp years before 0100, which catch host date
  constructor quirks such as JavaScript's `Date.UTC` year remapping.

These cases borrow from SWE-Bench+ and SWE-bench Verified lessons: preserve
old behavior with pass-to-pass tests while adding new issue pressure, and keep
the public requirement human-readable instead of leaking hidden fixtures.

Verification after this pass:

- `python -m pytest -q tests\test_stage22_ruleledger_v3.py` -> `14 passed`.
- `python -m pytest -q` -> `171 passed`.
- Starter hidden-runner baseline -> `30/90` points, `19/46` language cases, no
  runner errors.

The follow-up sanity run
`20260604T182952-ruleledger_v3_sanity-v3_sanity_measured_09` completed all
four implementations, judges, scoring, aggregate outputs, HTML report, PDF
report, CSV, SQLite, and validation artifacts. Validation again warned that
judge outputs were not parsed as strict JSON.

| Cell | Reasoning | Hidden Points | Hidden Executions | Exact-Tail Cases | Quality |
|---|---:|---:|---:|---|---:|
| V3S0 | low | `80/90` | `42/46` | passed all six language executions | `0.732433` |
| V3S1 | medium | `80/90` | `42/46` | passed all six language executions | `0.732433` |
| V3S2 | high | `59/90` | `34/46` | passed all six language executions | `0.590541` |
| V3S3 | xhigh | `66/90` | `36/46` | passed all six language executions | `0.592057` |

This run shows the exact-tail additions are fair but saturated in this sample:
all reasoning levels solved archival year `0001`, large upgrade proration, and
large downgrade proration in both languages. The high/xhigh drop came from
missed bitemporal merge-chain cases, while low and medium happened to solve
them. The current benchmark should keep these compatibility guards, but they
do not by themselves strengthen adjacent reasoning separation. The next
pressure pass should focus on deeper chain reasoning or scoring design rather
than adding more concrete compatibility arithmetic.

## Checkpoint: Corrected Merge-Record Pressure

The next pass moved back toward the user's preferred ambiguity shape: support
describes an issue class rather than a concrete arithmetic tail. The visible
brief now notes that back-office corrections may target merge records
themselves, that corrected merge records should replay lineage from the
corrected source account, and that voiding such a correction voids the original
merge fact rather than reverting to the mistaken source account.

Two hidden cases exercise that behavior:

- `v3.reasoning.corrected_merge_record_retargets_lineage`: before the void is
  audit-visible, a corrected merge from `acct_cm_true` should cause the final
  account to inherit the true source's usage, payment, seats, invoice, and
  lineage while leaving the mistaken source separate.
- `v3.evolution.voided_merge_correction_removes_lineage`: after the correction
  void is audit-visible, the merge fact is removed and the report must show the
  final, true-source, and mistaken-source accounts as separate rows.

Verification after this pass:

- `python -m pytest -q tests\test_stage22_ruleledger_v3.py` -> `15 passed`.
- `python -m pytest -q` -> `172 passed`.
- Starter hidden-runner baseline -> `30/102` points, `19/50` language cases, no
  runner errors.

The follow-up sanity run
`20260604T193140-ruleledger_v3_sanity-v3_sanity_measured_10` completed all
four implementations, judges, scoring, aggregate outputs, HTML report, PDF
report, CSV, SQLite, and validation artifacts. Validation again warned that
judge outputs were not parsed as strict JSON. The first launch was stranded by
the outer shell timeout after low/medium implementation, then resumed cleanly
from the same experiment directory for high/xhigh, judging, and scoring.

| Cell | Reasoning | Hidden Points | Hidden Executions | Corrected-Merge Cases | Quality |
|---|---:|---:|---:|---|---:|
| V3S0 | low | `61/102` | `34/50` | failed retargeted lineage, passed voided merge correction | `0.484883` |
| V3S1 | medium | `92/102` | `46/50` | passed all four language executions | `0.741861` |
| V3S2 | high | `71/102` | `38/50` | passed all four language executions | `0.619768` |
| V3S3 | xhigh | `81/102` | `42/50` | passed all four language executions | `0.633126` |

This pass improved low-vs-rest separation: low missed the retargeted merge
lineage case that medium/high/xhigh solved. It still did not produce a clean
adjacent ladder. Medium again solved the older bitemporal chain family while
high and xhigh missed several of those cases; xhigh did outperform high by
passing the architecture/runtime localization checks, but its larger patch was
heavily penalized by minimality. The next hypothesis should address either the
stochastic old-chain family or the scoring design. In particular, stronger
multi-view cases that require the same ledger to satisfy summary, report, and
architecture expectations may reward xhigh's broader synthesis better than
adding another isolated fixture.

## Checkpoint: Judge JSON Scoring Repair

The next pass addressed a measurement-path problem rather than another hidden
fixture. The v3 judge was producing useful review prose, but the harness scored
judge contribution as zero because `judge.json` did not contain strict JSON.
The judge prompt now explicitly requires a single final JSON object, warns that
Markdown/prose output scores zero, and names the exact output shape. The scorer
and Stage 11 validation now also accept a parsed top-level `score` alias in
addition to `overall_score` and the four rubric-specific score fields. This
keeps the harness robust to the JSON shape the judge actually emitted while
still requiring parsed JSON.

Verification after this pass:

- `python -m pytest -q tests\test_stage9_scoring.py tests\test_stage11_validation.py tests\test_prompt_rendering.py`
  -> `45 passed`.
- `python -m pytest -q` -> `175 passed`.

The follow-up sanity run
`20260604T203502-ruleledger_v3_sanity-v3_sanity_measured_11_judge_json`
completed all four implementations, judges, scoring, aggregate outputs, HTML
report, PDF report, CSV, SQLite, and validation artifacts. After recomputing
with the patched scorer/validator, Stage 11 validation passed and the
`judge_json` check validated parsed judge JSON for all four runs.

| Cell | Reasoning | Hidden Points | Judge | Minimality | Quality |
|---|---:|---:|---:|---:|---:|
| V3S0 | low | `90/102` | `0.858897` | `1.000000` | `0.902012` |
| V3S1 | medium | `102/102` | `0.940000` | `0.444375` | `0.960219` |
| V3S2 | high | `71/102` | `0.650000` | `0.968750` | `0.748205` |
| V3S3 | xhigh | `102/102` | `1.000000` | `0.145625` | `0.957281` |

This repair materially improves measurement fidelity: xhigh now receives the
top judge score and no longer loses all judge contribution to formatting. It
still does not prove the full ladder. Medium and xhigh both reached perfect
hidden correctness in this repeat, while xhigh's larger implementation lost
enough minimality score to finish just below medium on aggregate quality. High
again missed the older bitemporal chain family. The next calibration question
is no longer "why is judge always zero"; it is whether scoring should reduce
minimality's ability to mask perfect correctness/judge results, and whether the
old chain cases need replacement or multi-view reinforcement to reduce
stochastic misses.

## Checkpoint: Scoring Profile and Judge Schema Calibration

The next pass addressed two measurement-calibration issues exposed by the
previous sanity run:

- v3 minimality was too strong for a two-language, multi-module benchmark. The
  v3 scoring profile now keeps hidden correctness at `0.50`, keeps hidden
  parity and performance unchanged, raises judge contribution from `0.20` to
  `0.22`, lowers minimality from `0.05` to `0.03`, and widens the v3
  production-LOC penalty from `900/1600` to `1200/4000`.
- Judge JSON reliability needed CLI enforcement, not just prompt wording. The
  harness now supplies `--output-schema judge_evidence/judge_output.schema.json`
  for judge runs, copies the schema into the judge evidence bundle, and marks a
  judge phase failed when the final response does not parse as JSON so
  `--rerun-failed` can repair it.

Verification after the source changes:

- `python -m pytest -q tests\test_stage5_orchestration.py tests\test_stage6_codex_execution.py tests\test_stage9_scoring.py tests\test_stage11_validation.py tests\test_prompt_rendering.py tests\test_matrix.py`
  -> `119 passed`.
- `python -m pytest -q` -> `177 passed`.

The schema-enforced sanity repeat reused experiment directory
`20260604T213736-ruleledger_v3_sanity-v3_sanity_measured_12_scoring`. A first
pass in that directory confirmed the scoring change but still had unparsed
judge prose. After adding the schema enforcement, a rerun produced parsed judge
JSON for all four cells; a direct Stage 11 validation pass confirmed parsed
judge JSON, report outputs, hidden isolation, and run artifacts after repairing
a generated state-file encoding issue from the manual rerun setup.

| Cell | Reasoning | Hidden Correctness | Judge | Minimality | Quality |
|---|---:|---:|---:|---:|---:|
| V3S0 | low | `0.465116` | `0.395000` | `1.000000` | `0.439458` |
| V3S1 | medium | `0.860465` | `0.765000` | `1.000000` | `0.878533` |
| V3S2 | high | `0.639535` | `0.699020` | `1.000000` | `0.753552` |
| V3S3 | xhigh | `1.000000` | `0.987500` | `0.719500` | `0.988835` |

This is the best v3 separation so far at the top end: xhigh solved all hidden
categories, received a pass-level judge assessment, and remained highest even
with a larger patch. The ladder is still not complete because medium
outperformed high in this repeat. The next improvement should target the
medium/high instability directly, likely by replacing or reinforcing the older
chain cases with multi-view reasoning cases that reward systematic replay
modeling rather than isolated fixture luck.

## Checkpoint: Multi-View Replay Pressure

The next pass added a same-ledger, multi-view pressure family instead of another
concrete arithmetic tail. The visible v3 issue brief now says support compares
the same imported ledger through point-in-time summaries, CSV reports, parity
checks, and replay digests, and that those surfaces should share one canonical
replay model. The hidden generator uses one ledger with duplicate event IDs,
multi-hop merges, late source-account corrections, a correction void, and
report-sensitive CSV fields, then checks it through:

- `v3.reasoning.multi_view_before_void_summary`, a summary view before the
  correction void is audit-visible;
- `v3.evolution.multi_view_after_void_parity`, a summary-plus-report view after
  the correction void is audit-visible;
- `v3.metamorphic.multi_view_replay_equivalence`, replay equivalence under
  reversed import order and unrelated ledger noise.

Verification after this pass:

- `python -m pytest -q tests\test_stage22_ruleledger_v3.py` -> `16 passed`.
- Starter hidden-runner baseline -> `30/119` points, `19/56` language cases,
  no runner errors.
- `python -m pytest -q` -> `178 passed`.

The follow-up sanity run
`20260605T024652-ruleledger_v3_sanity-v3_sanity_measured_13_multiview`
completed all four implementations, schema-enforced judges, scoring, aggregate
outputs, HTML report, PDF report, CSV, SQLite, and Stage 11 validation.

| Cell | Reasoning | Hidden Correctness | Judge | Minimality | Quality |
|---|---:|---:|---:|---:|---:|
| V3S0 | low | `0.533981` | `0.612500` | `1.000000` | `0.621741` |
| V3S1 | medium | `0.912621` | `0.785000` | `1.000000` | `0.909010` |
| V3S2 | high | `0.888350` | `0.670000` | `1.000000` | `0.841575` |
| V3S3 | xhigh | `0.766990` | `0.850000` | `0.731250` | `0.842432` |

The new multi-view cases separated low from the rest: low failed all six
language executions, while medium, high, and xhigh passed all six. That confirms
the pressure family is fair and useful, but it did not solve adjacent
reasoning-level separation. Medium still finished first, and high/xhigh were
nearly tied. Xhigh passed the new multi-view family but missed older small
bitemporal chain/cutoff cases, while medium solved those with a smaller runtime
patch.

Next hypothesis: the current benchmark still has too much reward for concrete
fixture-style patching. The next pass should either generalize/reduce the
over-concrete support bullets so measured agents must infer the replay model
from issue-style ambiguity, or replace some older small chain fixtures with
multi-view families that all point at the same underlying abstraction. Adding
more isolated hidden cases is unlikely to fix the medium/high/xhigh ordering on
its own.

## Checkpoint: Ambiguous Support Brief Calibration

The next pass held hidden cases and scoring fixed, but made the visible v3
support brief less concrete. The old `Recent Support Escalations` section was
too close to a hidden-case checklist: it named exact timestamp examples, exact
void/correction shapes, corrected merge records, and high-seat downgrade
arithmetic. The revised brief still exposes the same domains, but frames them
as broader support themes:

- malformed optional date fields;
- deterministic CSV ordering and escaping;
- source/destination identifiers after lineage changes;
- separate business-effective and audit-visible cutoffs;
- composed correction and void operations;
- exact integer money math;
- archival timestamp preservation;
- one canonical replay model across summaries, reports, parity, and digests.

Verification after this pass:

- `python -m pytest -q tests\test_stage22_ruleledger_v3.py tests\test_prompt_rendering.py`
  -> `38 passed`.
- `python -m pytest -q` -> `178 passed`.

The follow-up sanity run
`20260605T034428-ruleledger_v3_sanity-v3_sanity_measured_14_ambiguous_brief`
completed all four implementations, schema-enforced judges, scoring, aggregate
outputs, HTML report, PDF report, CSV, SQLite, and Stage 11 validation.

| Cell | Reasoning | Hidden Correctness | Judge | Minimality | Quality |
|---|---:|---:|---:|---:|---:|
| V3S0 | low | `0.616505` | `0.640000` | `1.000000` | `0.729052` |
| V3S1 | medium | `0.509709` | `0.655000` | `0.884750` | `0.675497` |
| V3S2 | high | `0.587379` | `0.690000` | `0.787000` | `0.719099` |
| V3S3 | xhigh | `0.985437` | `0.930000` | `0.679500` | `0.967703` |

This is the clearest xhigh-vs-rest separation so far under the v3 benchmark:
xhigh nearly saturated hidden correctness and received the strongest judge
score despite a larger patch. The full ladder is still not proven, because the
lower three cells are nonmonotonic (`low` slightly above `high`, both above
`medium`). The lower-level ordering appears sensitive to which partial runtime
patch happens to land, while xhigh is the only cell that inferred enough of the
general replay model to pass almost everything.

Next hypothesis: before adding another hidden fixture, run repeats of the
ambiguous-brief configuration or add an aggregate separation metric that
explicitly rewards category saturation and judge-confirmed completeness. If
xhigh remains consistently isolated at the top while lower levels remain noisy,
the benchmark may be differentiating "complete reasoning" from partial patching
but not reliably ordering the three partial-reasoning modes.

## Checkpoint: Ambiguous Brief Full Repeat

The consistency run
`20260605T044407-ruleledger_v3_full-v3_full_measured_03_ambiguous_brief`
completed all twelve implementations, all twelve schema-enforced judges,
scoring, aggregate outputs, HTML report, PDF report, CSV, SQLite, and Stage 11
validation. Implementation and judge phases both completed with `12/12 ok, 0
failed`, and final validation passed.

| Reasoning | Quality Mean | Quality Range | Hidden Correctness Mean | Judge Mean |
|---|---:|---:|---:|---:|
| low | `0.610440` | `0.347031`-`0.835490` | `0.533981` | `0.530833` |
| medium | `0.889757` | `0.865584`-`0.916938` | `0.885113` | `0.760000` |
| high | `0.756127` | `0.690199`-`0.883316` | `0.642395` | `0.724167` |
| xhigh | `0.818525` | `0.735877`-`0.957343` | `0.744337` | `0.799167` |

This disproves the optimistic read from the preceding single-run sanity pass.
The ambiguous brief does not yet produce a stable reasoning ladder. Medium won
the repeat set and was the most consistent cell. Xhigh had the best single run
(`0.957343` quality, `0.985437` hidden correctness), but its other two repeats
fell back into the same partial-replay failure cluster as high.

The hidden category means explain the inversion:

- Medium saturated `evolution`, `fail_to_pass`, `metamorphic`, `parity`, and
  `performance` in all three repeats. Its remaining misses were mainly
  localization and pass-to-pass compatibility tails.
- High had one medium-like repeat but missed the deeper evolution, metamorphic,
  and reasoning-chain family in two of three repeats.
- Xhigh had one near-complete repeat, but two repeats missed the chain
  merge/correction, multi-view replay, and composed correction/void family.
- Low remained clearly separated from the rest, but had one unusually strong
  partial patch.

The next benchmark change should not add another isolated fixture or rely only
on category-saturation scoring. Those would likely preserve the medium plateau:
the medium runs already solved most behavioral categories consistently. The
next pass should make the visible task less checklist-shaped and more like a
messy support escalation: one or two narrative incident threads whose symptoms
span summaries, CSV reports, parity digests, and cross-language architecture,
without listing every underlying rule family as a bullet. Hidden cases should
then emphasize whether the implementation discovers a canonical replay model
and preserves the intended module boundary, not whether it patched the already
named domains one at a time.

## Checkpoint: Incident Narrative Brief Calibration

The next pass kept hidden cases and scoring fixed, but rewrote the visible
`Recent Support Escalations` section into two narrative incident reports:
`Month-Close Reconciliation Drift` and `Backfill Import Drift`. The old brief
still named each rule family directly, so medium-reasoning runs could patch the
listed domains one at a time. The revised brief describes cross-surface
symptoms across summaries, CSV exports, parity checks, replay fingerprints,
audit/business visibility, source-history identifiers, import validation,
timestamp handling, exact money math, and deterministic reporting without
presenting them as a checklist or complete truth table.

Verification after this pass:

- `python -m pytest -q tests\test_stage22_ruleledger_v3.py tests\test_prompt_rendering.py`
  -> `38 passed`.
- `python -m pytest -q` -> `178 passed`.

The follow-up sanity run
`20260605T060728-ruleledger_v3_sanity-v3_sanity_measured_15_incident_brief`
completed all four implementations, all four schema-enforced judges, scoring,
aggregate outputs, HTML report, PDF report, CSV, SQLite, and Stage 11
validation. Implementation and judge phases both completed with `4/4 ok, 0
failed`, and final validation passed.

| Cell | Reasoning | Hidden Correctness | Judge | Minimality | Quality |
|---|---:|---:|---:|---:|---:|
| V3S0 | low | `0.291262` | `0.370000` | `1.000000` | `0.347031` |
| V3S1 | medium | `0.650485` | `0.607500` | `1.000000` | `0.738893` |
| V3S2 | high | `0.985437` | `0.897500` | `0.804500` | `0.964303` |
| V3S3 | xhigh | `0.601942` | `0.782500` | `0.680500` | `0.743536` |

This is useful movement but not completion. The narrative brief knocked low
down hard and prevented the previous medium plateau from saturating the hidden
behavioral categories. High inferred the canonical replay shape almost
completely, missing only one compatibility tail in TypeScript. Xhigh consumed
the most implementation tokens and received a stronger judge score than medium,
but it missed the same evolution/metamorphic/reasoning-chain family that has
caused prior high/xhigh variance.

Next hypothesis: the visible ambiguity is now closer to the desired shape, but
the hidden suite still lets one strong non-xhigh run solve almost everything
while xhigh remains stochastic. The next benchmark hardening should add one
integrated incident fixture rather than another isolated rule case: a long
ledger that combines the month-close and backfill symptoms in the same
scenario, then checks summaries, reports, parity/digest, and architecture
boundaries from that shared replay. The goal is to reward durable synthesis of
the whole incident, not local patching of individually named behaviors.
