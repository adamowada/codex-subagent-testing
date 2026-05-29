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
model work began. The harness now treats Codex JSONL `error`/`turn.failed`
events and malformed implementation final JSON as failed implementation
infrastructure, preserves the failure summary in `state.json`, and forces
quality to `0.0` for those infrastructure-failed runs instead of scoring the
starter baseline as a partial benchmark result.

Next calibration step: after the Codex quota resets, rerun the four-run v3
sanity sweep and compare category spread across `low`, `medium`, `high`, and
`xhigh`.
