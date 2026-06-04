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
