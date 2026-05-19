# AGENTS.md

## Purpose

This repository builds a controlled benchmark harness for testing Codex subagent coding topologies. The main product is an orchestration script that runs a 45-run experiment, scores the results, and generates a PDF report.

## Working Principles

- Keep benchmark runs reproducible. Every measured run must start from the same frozen starter project and write artifacts into a run-specific directory.
- Keep hidden tests hidden. Hidden cases live outside implementation workspaces and must not be copied into prompts, starter projects, or run worktrees.
- Do not invoke nested Codex runs from inside a measured Codex run. The outer harness calls `codex exec --json`; the measured agent should never call `codex`, `codex exec`, another AI service, or another agent process.
- Prefer configuration over hard-coded experiment logic. New topologies, model choices, reasoning levels, role mixes, and write modes should be expressible through experiment config.
- Preserve raw evidence. Keep JSONL events, stderr logs, prompts, rendered configs, diffs, test logs, judge output, metadata, and scores for every run.
- Treat C4 as an intentional stress test. It exceeds documented default guidance by using a GPT-5.5 xhigh root lead, three GPT-5.5 medium subleads, and eighteen Spark xhigh leaves.

## Editing Guidelines

- Use `apply_patch` for manual edits.
- Keep files ASCII unless a file already uses non-ASCII or a specific format requires it.
- Do not rewrite generated artifacts by hand. Update the generator or template instead.
- Do not commit run outputs unless explicitly requested. `runs/` should be treated as generated experiment output.
- Avoid adding large dependencies unless they materially improve reproducibility or reporting.
- Keep scripts cross-platform where practical, but prioritize the current Windows PowerShell workflow.

## Locked Source-Of-Truth Documents

`AGENTS.md`, `LICENSE`, `PLANS.md`, and `README.md` are locked source-of-truth documents. Do not edit any of these files unless the user clearly and specifically instructs you to change them.

## Planning Documents

Incremental planning documents belong in `plans/`. Use that directory for follow-up implementation notes, revised stage plans, experiment design notes, and planning artifacts that are not meant to replace the locked top-level source-of-truth documents. Do not scatter temporary or follow-up planning notes into the repository root.

## Expected Commands

The implementation should eventually expose these commands:

```powershell
.\scripts\run_experiment.ps1 -Jobs 3
```

This command should run the full initial experiment and produce a report.

```powershell
.\scripts\run_pilot.ps1
```

This command should run a small smoke test before the full experiment.

Until those commands exist, inspect the available scripts and configs before assuming command names.

## Codex Harness Rules

- Use `codex exec --json` for measured implementation and judge runs.
- Parse `turn.completed.usage` from JSONL for token metrics.
- Track implementation-only GPT-5.5 token usage separately from judge-inclusive usage when possible.
- If mixed-agent JSONL does not expose per-model attribution, record total usage and clearly mark GPT-5.5/Spark split as best effort.
- Support a `CODEX_BIN` override so the harness can use a working Codex executable path if the default `codex` command is unavailable.

## Benchmark Rules

- The benchmark project must include both TypeScript and Python implementation surfaces.
- Public tests are visible and intentionally incomplete.
- Hidden tests are exhaustive, frozen before measured runs, and unavailable in source.
- Partial runs are scored based on the tests and judge results they earn.
- Spark leaves are always leaves. They may be direct editors or proposal-only workers depending on the experiment cell mode.
- Initial Spark reasoning is `xhigh` for every Spark leaf, but the harness must allow future per-role reasoning changes.

## Reporting Rules

- Generate both HTML and PDF reports.
- The PDF should be readable by a non-academic audience while keeping an academic-paper structure.
- Include methodology, experiment matrix, aggregate results, per-cell comparisons, token-efficiency metrics, and limitations.
- Do not hide failed runs. Failures are part of the measurement.
