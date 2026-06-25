# Spark Mode Efficiency Run Log

## Experiment

Plan: `plans/experiments/spark-mode-efficiency-direct-vs-proposal.md`

Configs:

- Pilot: `configs/spark_mode_efficiency_pilot.yaml`
- Main: `configs/spark_mode_efficiency_main.yaml`
- Xhigh extension: `configs/spark_mode_efficiency_xhigh_extension.yaml`
- High extension: `configs/spark_mode_efficiency_high_extension.yaml`

Concurrency targets:

- Pilot, main, and xhigh extension: implementation jobs 5, judge jobs 4
- High extension: implementation jobs 7, judge jobs 6

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

`efe4089` added the first final white paper and phase-aware analysis.

The xhigh extension added:

- `configs/spark_mode_efficiency_xhigh_extension.yaml`.
- Analysis support for combining main xhigh plus extension xhigh runs while
  excluding pilot xhigh rows from the 20-vs-20 comparison.
- `-WorkspaceRoot` support in `scripts/run_experiment.ps1` and failed
  implementation refresh support for moving reruns to the active workspace
  root, which avoids Windows path-length failures during repair.

The high extension added:

- `configs/spark_mode_efficiency_high_extension.yaml`.
- Analysis support for combining main high plus extension high runs while
  excluding pilot high rows from the 20-vs-20 comparison.
- A focused high direct/proposal section in the white paper that compares the
  combined high Spark-assisted cells against the historical 50-run high
  GPT-only baseline.

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
- Remaining issue at that checkpoint: staged judge reruns hit a Codex usage
  limit, and `SME7_proposal_r02` still needed implementation repair.

Final pilot repair:

- Directory:
  `runs/20260624T023048-spark_mode_efficiency_pilot-pilot`
- Result: failed implementation and judge phases were rerun successfully.
- Final validation status: `passed`.
- Pilot rows: 24.

## Main Run

Initial main run:

- Directory:
  `runs/20260624T053702-spark_mode_efficiency_main-main`
- Command:
  `.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_main.yaml -Jobs 5 -JudgeJobs 4 -ExperimentName main -StudyId spark-mode-efficiency -BatchId main -BatchSequence 2`
- Result: all 40 implementation runs completed, but 19 judge outputs failed
  JSON parsing and were preserved as failed judged phases.
- Validation status at this checkpoint: `warning`.

Main repair:

- Command:
  `.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_main.yaml -Jobs 5 -JudgeJobs 4 -Resume 20260624T053702-spark_mode_efficiency_main-main -RerunFailed`
- Result: failed judged phases reran successfully.
- Final validation status: `passed`.
- Main rows: 40.
- Main report:
  `runs/20260624T053702-spark_mode_efficiency_main-main/report/report.html`
- Main PDF:
  `runs/20260624T053702-spark_mode_efficiency_main-main/report/report.pdf`

## Xhigh Extension

Dry run:

- Directory:
  `runs/20260624T105934-spark_mode_efficiency_xhigh_extension-xhigh_extension_dry_run`
- Result: preflight passed and selected 30 runs: 15 xhigh direct and 15 xhigh
  proposal.

Measured extension:

- Directory:
  `runs/20260624T105944-spark_mode_efficiency_xhigh_extension-xhigh_extension`
- Command:
  `.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_xhigh_extension.yaml -Jobs 5 -JudgeJobs 4 -ExperimentName xhigh_extension -StudyId spark-mode-efficiency -BatchId xhigh-extension -BatchSequence 3`
- Result: initial run completed 30 implementations and judges, but validation
  warned because judge JSON parse failures were preserved. Five proposal runs
  also hit the Codex usage limit during implementation and scored zero until
  repair.

Extension repair:

- First resume exposed a Windows path-length failure while refreshing the five
  failed proposal worktrees.
- The harness was updated so failed implementation refresh can move to the
  active workspace root, and `scripts/run_experiment.ps1` now exposes
  `-WorkspaceRoot`.
- After the usage-limit reset, the repair command succeeded:
  `.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_xhigh_extension.yaml -Jobs 5 -JudgeJobs 4 -WorkspaceRoot C:\cstws -Resume 20260624T105944-spark_mode_efficiency_xhigh_extension-xhigh_extension -RerunFailed`
- Final validation status: `passed`.
- Extension rows: 30.
- Extension report:
  `runs/20260624T105944-spark_mode_efficiency_xhigh_extension-xhigh_extension/report/report.html`
- Extension PDF:
  `runs/20260624T105944-spark_mode_efficiency_xhigh_extension-xhigh_extension/report/report.pdf`

## High Extension

Superseded run:

- Directory:
  `runs/20260624T204314-spark_mode_efficiency_high_extension-high_extension`
- Result: completed and validated under the earlier 5/4 concurrency setting,
  but was superseded when the experiment objective changed to implementation
  jobs 7 and judge jobs 6.
- Official analysis excludes this superseded run.

Dry run for official 7/6 setting:

- Directory:
  `runs/20260624T220400-spark_mode_efficiency_high_extension-high_extension_j7_j6_dry_run`
- Result: preflight passed and selected 30 runs: 15 high direct and 15 high
  proposal.

Measured high extension:

- Directory:
  `runs/20260624T220413-spark_mode_efficiency_high_extension-high_extension_j7_j6`
- Command:
  `.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_high_extension.yaml -Jobs 7 -JudgeJobs 6 -WorkspaceRoot C:\cstws -ExperimentName high_extension_j7_j6 -StudyId spark-mode-efficiency -BatchId high-extension-j7-j6 -BatchSequence 4 -BatchNotes "Spark mode efficiency high extension: 15 additional high direct and 15 additional high proposal runs with implementation jobs 7 and judge jobs 6."`
- Initial result: the run selected 30 configured runs, but the first attempt
  hit the Codex usage limit before all implementation and judge phases could
  complete.
- First resume attempt before the usage-limit reset preserved quota failures
  and left validation at `warning`.

High extension repair:

- After the usage-limit reset, the failed phases reran successfully:
  `.\scripts\run_experiment.ps1 -Config configs/spark_mode_efficiency_high_extension.yaml -Jobs 7 -JudgeJobs 6 -WorkspaceRoot C:\cstws -Resume 20260624T220413-spark_mode_efficiency_high_extension-high_extension_j7_j6 -RerunFailed`
- Final validation status: `passed`.
- Extension rows: 30.
- Extension report:
  `runs/20260624T220413-spark_mode_efficiency_high_extension-high_extension_j7_j6/report/report.html`
- Extension PDF:
  `runs/20260624T220413-spark_mode_efficiency_high_extension-high_extension_j7_j6/report/report.pdf`

## Analysis and Reporting

Final analysis command:

```powershell
python scripts\analyze_spark_mode_efficiency.py --experiment-dir runs\20260624T023048-spark_mode_efficiency_pilot-pilot --experiment-dir runs\20260624T053702-spark_mode_efficiency_main-main --experiment-dir runs\20260624T105944-spark_mode_efficiency_xhigh_extension-xhigh_extension --experiment-dir runs\20260624T220413-spark_mode_efficiency_high_extension-high_extension_j7_j6 --output-dir runs\analysis\spark_mode_efficiency_final
```

Final analysis artifacts:

- `runs/analysis/spark_mode_efficiency_final/summary.json`
- `runs/analysis/spark_mode_efficiency_final/summary.csv`
- `runs/analysis/spark_mode_efficiency_final/phase_summary.csv`
- `runs/analysis/spark_mode_efficiency_final/summary.md`

Rows analyzed: 324.

White paper:

- `papers/spark-mode-efficiency-white-paper.md`

Headline result:

- Direct edit is the better default for Spark leaves.
- Direct edit wins quality and implementation-token efficiency at low, medium,
  and high root reasoning.
- In the 20-run-per-mode high comparison, direct is higher quality:
  `0.711964` versus `0.652004`, and uses about `1.06M` fewer total
  implementation tokens per run.
- Combined high direct is only slightly above the historical 50-run high
  GPT-only mean (`0.696050`) and is worse on total-token efficiency, so
  GPT-only high remains the cleaner total-token baseline.
- In the 20-run-per-mode xhigh comparison, direct is slightly higher quality:
  `0.733897` versus `0.714206`.
- Xhigh proposal uses fewer GPT and total implementation tokens than xhigh
  direct, but spends more Spark tokens.
- Both combined xhigh Spark-assisted modes trail the historical 50-run xhigh
  GPT-only mean (`0.755057`).
