# Spark Mode Efficiency Run Log

## Experiment

Plan: `plans/experiments/spark-mode-efficiency-direct-vs-proposal.md`

Configs:

- Pilot: `configs/spark_mode_efficiency_pilot.yaml`
- Main: `configs/spark_mode_efficiency_main.yaml`

Concurrency target:

- Implementation jobs: 5
- Judge jobs: 4

## Implementation Checkpoints

`116addc` added staged Spark orchestration support:

- `staged_spark` topology.
- Pilot and main experiment configs.
- Staged prompt template.
- Separate root planning, Spark leaf, and root integration invocations.
- Combined model-attributed implementation JSONL for exact GPT/Spark usage.

`f0041e9` fixed Windows command-line length failures by writing staged prompts
into temporary workspace files and passing a short prompt that asks the model to
read the file.

`b81cd43` fixed Windows rerun failures by allocating unique Spark leaf worktree
directories instead of deleting previous leaf worktrees that may still contain
locked Git object files.

`073733e` added `scripts/analyze_spark_mode_efficiency.py` for derived
historical baseline, bridge, pilot, and main summaries.

## Pilot Runs

Dry run:

- Directory:
  `runs/20260624T022916-spark_mode_efficiency_pilot-dry_run`
- Result: preflight passed.

Initial pilot:

- Directory:
  `runs/20260624T023048-spark_mode_efficiency_pilot-pilot`
- Result: completed, but all staged Spark implementation phases failed.
- Cause: Windows command-line length limit. Every staged Codex command received
  the full rendered prompt as a command-line argument and exited with
  `The command line is too long.`
- Resolution: `f0041e9`.

Staged smoke after command-line fix:

- Directory:
  `runs/20260624T030017-spark_mode_efficiency_pilot-staged_smoke_after_prompt_file_fix`
- Selected run: `SME0_direct_r01`
- Result: staged Spark run completed with exact per-model implementation usage.
- Quality: `0.453189`
- Usage attribution: `per_event_model`

First pilot resume:

- Command intent: resume failed staged cells in the pilot directory.
- Result: failed during implementation before artifacts were regenerated.
- Cause: previous Spark leaf worktrees under the temp workspace contained locked
  `.git/objects` files, and the rerun attempted to delete/reuse those
  directories.
- Resolution: `b81cd43`.

Second pilot resume:

- Directory:
  `runs/20260624T023048-spark_mode_efficiency_pilot-pilot`
- Result: staged Spark implementation artifacts regenerated and exact
  per-model usage recorded.
- Remaining issue: staged judge reruns hit a Codex usage limit. The judge phase
  is failed for staged cells, and staged judge contribution is currently zero.
- Required next action: after the usage-limit reset, run the pilot again with
  `-Resume 20260624T023048-spark_mode_efficiency_pilot-pilot -RerunFailed` to
  rerun failed staged judges and the one failed staged implementation
  (`SME7_proposal_r02`).

## Current Pilot Status

As of the second pilot resume:

- GPT-only bridge runs completed and scored.
- 15 of 16 staged Spark implementation runs completed and scored from public
  and hidden evidence.
- `SME7_proposal_r02` hit usage limit during root integration and remains an
  implementation failure until rerun.
- All staged judge runs hit usage limit during judge rerun and remain failed
  until rerun.
- Pilot validation status is `warning`, not final-passed.

Do not treat the pilot as finalized until failed staged implementation/judge
phases are rerun after the usage-limit reset.
