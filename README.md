# Codex Subagent Topology Benchmark

## Introduction

## Methods

This project is designed to compare different ways of using Codex subagents for coding work. The goal is not just to see which setup writes the most code, but which setup produces the most correct, useful code for the amount of scarce GPT-5.5 usage it consumes.

The experiment uses a contrived benchmark project called RuleLedger. RuleLedger is intentionally mixed-language: agents must implement matching TypeScript and Python modules that parse subscription event logs, normalize messy records, apply pricing and account-state rules, and export deterministic summaries. The task is complex enough to require real coordination, but structured enough that subagents can be assigned clear pieces of work.

Each experiment run starts from the same clean starter project. Codex is launched through `codex exec --json`, and the run output is saved as machine-readable JSONL along with logs, diffs, timing data, test results, and judge results. Runs are isolated from each other so that one topology cannot accidentally benefit from another topology's work.

The first experiment compares five v1 cells. One is a solo GPT-5.5 xhigh baseline. Three use a GPT-5.5 lead at medium, high, or xhigh reasoning with six Spark xhigh leaf subagents. The final cell is a stress test: a GPT-5.5 xhigh root lead coordinates three GPT-5.5 medium subleads, and each sublead coordinates six Spark xhigh leaves. Spark leaves are tested in two modes: direct edit mode and proposal-only mode.

The repository also contains a harder RuleLedger v2 path. V2 has a separate starter template, hidden case directory, scoring profile, pilot config, and full readiness matrix. It adds bitemporal business/audit views, lifecycle precedence, account merges, proration, performance cases, category-level reporting, and v2-specific public hooks while keeping the v1 experiment intact.

Quality is measured with visible public tests, hidden tests, typechecking, code-diff metrics, and a separate blind GPT-5.5 xhigh judge. The hidden tests are created once and kept outside the implementation workspaces so implementation agents cannot read them. Partial runs still receive whatever score they earn.

The primary comparison metric is quality per implementation-only GPT-5.5 token. The harness also tracks judge-inclusive GPT-5.5 cost, total token usage, best-effort Spark usage, wall-clock time, code quantity, failure rate, and direct-edit versus proposal-only differences. Reports label benchmark version and avoid silently ranking v1 and v2 scores together.

## Commands

Run the initial v1 experiment:

```powershell
.\scripts\run_experiment.ps1 -Jobs 3
```

Run the default pilot smoke test:

```powershell
.\scripts\run_pilot.ps1
```

Run the v2 pilot:

```powershell
.\scripts\run_pilot.ps1 -Config configs\ruleledger_v2_pilot.yaml -Jobs 1 -JudgeJobs 1
```

Dry-run the full v2 readiness matrix:

```powershell
.\scripts\run_experiment.ps1 -Config configs\ruleledger_v2_experiment.yaml -Jobs 3 -JudgeJobs 1 -DryRun
```

Remove `-DryRun` only after the v2 pilot has produced real calibration evidence and the local Codex executable is available.
