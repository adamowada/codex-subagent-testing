# RuleLedger v3 Benchmark Harness

This repository contains a reproducible benchmark harness for Codex coding experiments. The current focus is RuleLedger v3: a TypeScript and Python subscription-ledger task designed to measure whether larger reasoning budgets and Spark-assisted topologies produce better code.

The repo preserves measured evidence for each run: rendered configs, prompts, Codex JSONL events, stderr logs, diffs, public test logs, hidden-test summaries, judge output, usage metrics, scores, and generated reports.

## RuleLedger v3

RuleLedger v3 is a controlled software-engineering benchmark. A measured agent starts from a frozen mixed-language starter project and must implement one coherent ledger engine across:

- TypeScript and Python implementation surfaces.
- Bitemporal replay using business-effective and audit-visible cutoffs.
- Account lineage, merges, corrections, voids, billing, reports, and replay digests.
- Cross-language parity, deterministic CSV output, compatibility behavior, and performance constraints.

The benchmark is intentionally issue-like rather than a complete truth table. Public tests are visible and incomplete. Hidden tests remain outside implementation workspaces and score correctness, parity, performance, behavior-family coverage, and regression behavior. A fixed GPT-5.5 xhigh judge contributes an additional review signal.

The RuleLedger v3 paper reports a 200-run GPT-5.5 reasoning study: 50 runs each at `low`, `medium`, `high`, and `xhigh` reasoning. The main result is the quality jump from medium to high reasoning; xhigh produced the best observed mean quality and tail behavior.

Primary paper:

- [RuleLedger v3 white paper](papers/ruleledger-v3-white-paper.md)

Key assets:

- Starter project: `benchmark_template_v3/`
- Public prompt: `prompts/task_common_v3.md`
- Hidden cases: `hidden_tests/cases_v3/`
- Scoring profile: `configs/scoring_v3.yaml`
- Paper experiment config: `configs/ruleledger_v3_paper_50.yaml`
- Sanity config: `configs/ruleledger_v3_sanity.yaml`

## Spark Mode Efficiency

The Spark mode efficiency experiment uses RuleLedger v3 to compare two ways of using six `gpt-5.3-codex-spark` xhigh leaf workers under a GPT-5.5 coordinator:

- Direct edit mode: Spark leaves work in separate writable git worktrees and return diffs.
- Proposal mode: Spark leaves run read-only and return findings, proposed patches, tests, and integration notes.

The official comparison set contains 360 scored implementation runs:

| Group | Cells | Runs per cell | Rows |
| --- | ---: | ---: | ---: |
| GPT-5.5 solo comparison | 4 reasoning levels | 50 | 200 |
| Spark direct | 4 reasoning levels | 20 | 80 |
| Spark proposal | 4 reasoning levels | 20 | 80 |

The analysis reports GPT-5.5 coordinator tokens, Spark leaf tokens, total implementation tokens, quality, and efficiency. Official Spark-assisted rows use per-event model attribution from Codex JSONL usage events.

Primary paper:

- [Spark mode efficiency white paper](papers/spark-mode-efficiency-white-paper.md)

Key assets:

- Experiment plan: `plans/experiments/spark-mode-efficiency-direct-vs-proposal.md`
- Run log: `plans/experiments/spark-mode-efficiency-run-log.md`
- Main config: `configs/spark_mode_efficiency_main.yaml`
- Extension configs: `configs/spark_mode_efficiency_low_medium_extension.yaml`, `configs/spark_mode_efficiency_high_extension.yaml`, `configs/spark_mode_efficiency_xhigh_extension.yaml`
- Analysis script: `scripts/analyze_spark_mode_efficiency.py`

## Harness Architecture

The harness is config-driven. Experiment configs select the benchmark template, hidden cases, prompt templates, scoring profile, model names, reasoning levels, topology, repeat counts, and parallelism. The orchestrator expands those configs into measured run records and executes each run in an isolated workspace.

Core modules:

| Module | Responsibility |
| --- | --- |
| `harness.matrix` | Load, validate, summarize, and expand experiment configs into deterministic run records |
| `harness.preflight` | Check environment readiness, config paths, prompt rendering, and hidden-case isolation before spending model quota |
| `harness.prompt_rendering` | Render implementation prompts, judge prompts, and Codex config files from run records |
| `harness.orchestrator` | Create run directories/workspaces, schedule implementation and judge phases, resume runs, rerun failed phases, and write aggregate outputs |
| `harness.codex_runner` | Build and run `codex exec --json` commands, capture JSONL/stderr, handle timeouts, and extract final responses |
| `harness.hidden_runner` | Run hidden RuleLedger checks from outside measured implementation workspaces |
| `harness.jsonl_usage` | Parse Codex JSONL usage events and attribute implementation tokens by model when available |
| `harness.scoring` | Compute quality scores from public checks, hidden results, performance, judge output, and minimality |
| `harness.report_data` | Collect result rows and write aggregate report data, CSV, and SQLite artifacts |
| `harness.validation` | Validate completed runs, reports, hidden-test privacy, judge JSON, and artifact completeness |

Important conventions:

- Every measured run starts from a frozen benchmark template.
- Hidden cases are never copied into implementation workspaces or prompts.
- Measured agents must not invoke nested Codex runs or other AI services.
- Raw evidence is preserved under `runs/`.
- Generated run outputs should normally stay out of commits unless a specific experiment artifact is being intentionally published.

## Install and Use

Prerequisites:

- Python 3.12+
- Node.js/npm
- Codex CLI available as `codex`, or set `CODEX_BIN` to the executable path

Install local test and report dependencies:

```powershell
python -m pip install -r requirements-dev.txt
npm install
npm run install:report-browser
```

Run the repository tests:

```powershell
python -m pytest -q
```

Dry-run the RuleLedger v3 sanity matrix without spending model quota:

```powershell
.\scripts\run_experiment.ps1 -Config configs\ruleledger_v3_sanity.yaml -DryRun -NoReport
```

Run a measured RuleLedger v3 sanity sweep:

```powershell
.\scripts\run_experiment.ps1 -Config configs\ruleledger_v3_sanity.yaml -Jobs 1 -JudgeJobs 1
```

Use the explicit config for any larger run, for example `configs/ruleledger_v3_paper_50.yaml` or `configs/spark_mode_efficiency_main.yaml`. Full measured experiment configs can consume substantial model quota, so start with `-DryRun`, small sanity configs, and explicit `-Jobs` / `-JudgeJobs` settings.

The Spark analysis command used for the published paper is recorded in [the Spark white paper](papers/spark-mode-efficiency-white-paper.md).
