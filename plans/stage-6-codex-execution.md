# Stage 6 Plan: Codex Execution

## Goal

Turn each expanded experiment run record into auditable `codex exec --json` subprocess executions for implementation and judging.

Stage 6 is complete when the harness can:

- Resolve a working Codex executable through `CODEX_BIN` or `PATH`.
- Launch measured implementation runs with the configured root model, reasoning effort, agent depth, agent threads, sandbox mode, timeout, and rendered prompt.
- Launch judge runs with GPT-5.5 xhigh in read-only mode and a rendered judge prompt.
- Capture raw JSONL stdout, stderr, wall-clock metadata, exit code, timeout status, and final-response extraction for every Codex invocation.
- Preserve partial evidence for failed or timed-out runs.
- Prevent nested Codex or external AI invocation from being part of the measured task contract.

This stage is the measurement boundary. Earlier stages prepare run records, prompts, configs, and isolated worktrees. Stage 6 executes them while preserving enough raw evidence that later stages can test, score, audit, resume, and report without guessing.

## Non-Goals

- Do not edit locked top-level source-of-truth documents.
- Do not change benchmark task behavior, public tests, hidden tests, hidden case payloads, or scoring rules.
- Do not copy hidden tests or hidden expected outputs into implementation prompts, judge prompts, starter projects, run worktrees, or Codex logs.
- Do not run nested Codex from inside a measured implementation workspace.
- Do not build final scoring or reporting logic in this stage, except for producing the execution artifacts they consume.
- Do not discard failed runs, malformed JSONL, malformed final responses, stderr logs, or timed-out process evidence.
- Do not require manual per-run launch steps.

## Inputs

Stage 6 consumes:

- Expanded run records from `harness.matrix.expand_experiment_matrix`.
- Per-run worktrees prepared from `benchmark_template/`.
- Per-run `metadata.json` with run ID, topology, model, reasoning, timeouts, and baseline commit.
- `rendered_prompt.md` from Stage 4 prompt rendering.
- `judge_prompt.md` from Stage 4 prompt rendering.
- `codex_config/` from Stage 4 config rendering.
- Experiment-level CLI settings from Stage 5 orchestration, especially `--jobs`, `--judge-jobs`, `--resume`, and `--rerun-failed`.
- `CODEX_BIN`, when the default `codex` command is not usable.

Stage 6 should treat the run record as authoritative for model, reasoning, depth, threads, sandbox, and timeout settings. The rendered config is preserved as an artifact and should agree with the command-line overrides.

## Outputs

For each implementation run, Stage 6 writes:

```text
events.jsonl
stderr.log
wall_time.json
final_response.json
state.json
```

For each judge run, Stage 6 writes:

```text
judge.events.jsonl
judge.stderr.log
judge.wall_time.json
judge.json
state.json
```

The broader orchestration pipeline may write additional artifacts before and after Stage 6, such as prompts, configs, diffs, public test logs, hidden test output, usage summaries, scores, and reports. Stage 6 owns the Codex subprocess evidence.

## Executable Resolution

Codex resolution should be deterministic and user-correctable:

1. If `CODEX_BIN` is set, use it.
2. If `CODEX_BIN` is an absolute path and exists, use that exact path.
3. If `CODEX_BIN` is a command name or relative value, resolve it through `PATH` when possible.
4. If `CODEX_BIN` is unset, resolve `codex` through `PATH`.
5. If no executable can be resolved, fail preflight before measured runs begin.

The failure message should include the Windows-friendly instruction:

```powershell
$env:CODEX_BIN = "path\to\working\codex"
```

Preflight should also run:

```text
<codex_bin> --version
```

and record stdout, stderr, return code, and selected executable path in `preflight.json`.

## Implementation Command Contract

Each measured implementation run should execute:

```text
codex exec --json
  --cd <run_worktree>
  --sandbox workspace-write
  --ask-for-approval never
  --model <root_model>
  -c model_reasoning_effort=<root_reasoning>
  -c agents.max_threads=<agents.max_threads>
  -c agents.max_depth=<agents.max_depth>
  <rendered_prompt>
```

Rules:

- Use the resolved Codex executable instead of a hard-coded `codex` string.
- Replace `<run_worktree>` with the absolute path to the per-run implementation workspace.
- Pass the full rendered prompt as the final argument.
- Use `workspace-write` so the measured implementation can edit the copied starter project.
- Use `--ask-for-approval never` so measured runs are noninteractive and reproducible.
- Use root model and root reasoning from the run record.
- Use `agents.max_threads` and `agents.max_depth` from the run record.
- Use the run-specific implementation timeout.
- Stream stdout to `events.jsonl`.
- Stream stderr to `stderr.log`.
- Write process metadata to `wall_time.json`.
- Extract the final strict JSON response into `final_response.json` on a best-effort basis.

The command display stored in metadata or logs should mask the prompt body as `<prompt>` so logs remain readable.

## Judge Command Contract

Each judge run should execute:

```text
codex exec --json
  --cd <run_worktree>
  --sandbox read-only
  --ask-for-approval never
  --model gpt-5.5
  -c model_reasoning_effort=xhigh
  <judge_prompt>
```

Rules:

- Use the resolved Codex executable.
- Use the same run worktree that contains the measured implementation result.
- Use read-only sandboxing.
- Use the judge model, reasoning effort, and sandbox from the config-rendered run record, with GPT-5.5 xhigh as the initial experiment default.
- Use the run-specific judge timeout.
- Stream stdout to `judge.events.jsonl`.
- Stream stderr to `judge.stderr.log`.
- Write process metadata to `judge.wall_time.json`.
- Extract the judge's final strict JSON response into `judge.json` on a best-effort basis.

The judge must not modify files. If a future Codex CLI behavior allows writes despite read-only sandboxing, the harness should detect unexpected post-judge worktree changes and record an infrastructure warning.

## JSONL Capture

Codex stdout is the canonical event stream. Stage 6 must preserve it exactly enough for later usage parsing and forensic review.

Requirements:

- Write one stdout stream per Codex invocation.
- Do not parse-and-rewrite the JSONL file during execution.
- Use UTF-8 with replacement for invalid bytes rather than failing artifact capture.
- Preserve malformed lines. Later parsers can skip malformed lines, but raw evidence should remain.
- Do not mix implementation and judge events in the same file.
- Do not merge stderr into JSONL stdout.

Expected usage events include `turn.completed.usage`, but the parser should be tolerant of schema variants such as top-level `usage`, nested `turn.usage`, or nested `completed.usage`.

## Stderr Capture

Stderr is not noise in this benchmark. It can contain CLI warnings, sandbox errors, auth failures, rate limit messages, or model routing failures.

Requirements:

- Write implementation stderr to `stderr.log`.
- Write judge stderr to `judge.stderr.log`.
- Preserve stderr even when stdout is empty or malformed.
- Preserve stderr for process launch failures.
- Do not redact ordinary stderr unless it includes credentials. If credential-like content appears, record a clear redaction marker and treat it as an infrastructure risk.

## Wall-Time Metadata

Each Codex invocation should write a process result JSON object with:

- Full materialized command.
- Display command with prompt replaced by `<prompt>`.
- Working directory.
- UTC start time.
- UTC finish time.
- Elapsed seconds.
- Return code.
- Timeout boolean.
- Stdout artifact path.
- Stderr artifact path.

The metadata should be machine-readable and stable across platforms. Use ISO 8601 UTC timestamps.

## Final Response Extraction

Implementation and judge prompts both require strict JSON final responses. Stage 6 should still be tolerant because malformed final responses are measured outcomes.

Extraction behavior:

1. Read events JSONL after Codex exits or times out.
2. Collect likely text fields from parsed JSON events.
3. Search candidates in reverse order.
4. Try to parse the entire candidate as JSON.
5. If that fails, try to extract the last JSON object substring.
6. Write a wrapper object that records whether parsing succeeded.

Example successful shape:

```json
{
  "parsed": true,
  "raw": "{\"status\":\"success\"}",
  "value": {
    "status": "success"
  }
}
```

Example failed shape:

```json
{
  "parsed": false,
  "raw": "last observed text",
  "error": "no_strict_json_object_found"
}
```

Downstream scoring can decide how much malformed output hurts the run. Stage 6 only preserves and normalizes enough evidence.

## Timeout Handling

Timeouts are expected measurement outcomes, especially for stress cells.

Requirements:

- Use `timeouts.implementation_seconds` for implementation runs.
- Use `timeouts.judge_seconds` for judge runs.
- On timeout, kill the process.
- Wait briefly for process termination after kill.
- Mark the phase as failed or timed out in `state.json`.
- Keep all partial stdout, stderr, and metadata files.
- Continue with later phases when meaningful. For example, a timed-out implementation can still have a diff, public test results, hidden test results, and judge output if files were changed.

Timeouts should not delete the run directory or block unrelated runs.

## Process Failure Handling

Stage 6 should distinguish infrastructure failures from measured failures.

Infrastructure failures before measured runs should stop the experiment:

- Codex executable cannot be found.
- `codex --version` cannot run.
- Experiment config cannot expand.
- Prompt rendering fails.
- Run worktree cannot be prepared.

Per-run failures should be recorded and the scheduler should continue:

- Codex returns nonzero.
- Codex times out.
- Codex emits malformed JSONL.
- Codex emits no strict final JSON.
- Judge returns malformed JSON.
- Judge times out.

If the process cannot be spawned because of an `OSError`, write a stderr artifact with a `process_error` marker and mark the phase failed.

## State And Resume Semantics

Stage 6 should update `state.json` for each run.

Implementation phase:

- `completed` when Codex exits with return code `0` and does not time out.
- `failed` when Codex returns nonzero, times out, or cannot spawn.

Judge phase:

- `completed` when Codex exits with return code `0`, does not time out, and `judge.json` parses successfully.
- `failed` when Codex returns nonzero, times out, cannot spawn, or produces malformed judge JSON.

Resume behavior:

- Skip completed phases when the required artifact exists.
- Skip failed phases when the required artifact exists unless `--rerun-failed` is set.
- With `--rerun-failed`, rerun failed Codex phases and preserve older evidence by archiving or using a clearly named rerun path before overwriting.
- Never silently overwrite a complete experiment directory.

## Parallel Scheduling

Implementation and judge scheduling are separate:

- Implementation jobs use `parallelism.implementation_jobs`, overridden by `--jobs`.
- Judge jobs use `parallelism.judge_jobs`, overridden by `--judge-jobs`.
- Submission order should be deterministic.
- Aggregation should sort by run ID or matrix order, not completion order.
- Each worker should write only its own run directory, plus status updates guarded by a lock.

Stage 6 should not share mutable in-memory run state across workers except through the scheduler and synchronized status writer.

## Nested Codex And External AI Prohibition

The measured implementation prompt must explicitly prohibit:

- `codex`
- `codex exec`
- Nested Codex processes
- External AI services
- Other AI agent processes
- Deeper agent trees than the configured topology permits

This is partly a prompt contract and partly an audit concern.

Recommended safeguards:

- Keep the prohibition in `prompts/task_common.md`.
- Ensure rendered prompts preserve the prohibition verbatim.
- Avoid exposing `CODEX_BIN` as an instruction to the measured agent.
- Run implementation workspaces from isolated starter copies.
- Consider scanning `events.jsonl`, `stderr.log`, and `diff.patch` for obvious nested invocation attempts and recording a warning. Do not make this scan the only enforcement mechanism.

## Codex Config Handling

Stage 4 renders `codex_config/config.toml` and agent role snippets. Stage 6 command-line flags remain authoritative because they are explicit in the measured command contract.

The harness should verify consistency between:

- Run record root model.
- Run record root reasoning.
- Run record agent max depth.
- Run record agent max threads.
- Rendered config values.
- Command-line values passed to `codex exec`.

If Codex CLI supports an explicit config path flag in the target environment, Stage 6 may add it only if tests prove it does not change the existing command contract. Otherwise, preserve the rendered config as an audit artifact and rely on `-c` command overrides for measured execution.

## Security And Isolation

Stage 6 should preserve benchmark isolation:

- Implementation runs get only the copied starter worktree as their working directory.
- Hidden tests remain outside implementation worktrees.
- Judge runs are read-only.
- No hidden case payloads are written to implementation prompts, judge prompts, stderr logs, or Codex config.
- Measured implementation worktrees should not be reused across runs.
- Environment variables passed to Codex should be minimal and should not include benchmark secrets.

If future work adds explicit environment shaping, preserve ordinary PATH behavior needed by Codex, Node, npm, Python, and git.

## Current Code Touchpoints

Expected implementation modules:

- `harness.codex_runner.resolve_codex_bin`
- `harness.codex_runner.build_implementation_command`
- `harness.codex_runner.build_judge_command`
- `harness.codex_runner.materialize_worktree_command`
- `harness.codex_runner.command_for_display`
- `harness.codex_runner.run_process_to_files`
- `harness.codex_runner.extract_final_response`
- `harness.preflight.run_preflight`
- `harness.orchestrator.run_implementation_and_tests`
- `harness.orchestrator.run_judge`
- `harness.orchestrator.run_parallel`

The tests should prefer command construction, fake process execution, temporary directories, and synthetic JSONL over real Codex launches.

## Test Plan

Add or maintain tests that do not require a real Codex account or network access:

- `resolve_codex_bin` prefers `CODEX_BIN` when set.
- `resolve_codex_bin` falls back to `codex` from `PATH`.
- Preflight fails clearly when Codex is required and not found.
- Preflight downgrades missing Codex to warning during dry-run mode.
- Implementation command includes `exec`, `--json`, `--cd`, `workspace-write`, `--ask-for-approval never`, root model, root reasoning, max depth, max threads, and prompt.
- Judge command includes `exec`, `--json`, `--cd`, `read-only`, `--ask-for-approval never`, judge model, judge reasoning, and prompt.
- Worktree placeholder is replaced with the absolute run worktree path.
- Display command masks the prompt as `<prompt>`.
- `run_process_to_files` writes stdout, stderr, return code, and timing metadata for a successful subprocess.
- `run_process_to_files` records timeout status and preserves partial output.
- `run_process_to_files` records process launch errors without raising uncaught exceptions.
- Final response extraction succeeds for strict JSON in the last text event.
- Final response extraction returns a structured failure when JSON is absent or malformed.
- Resume skips completed implementation and judge phases when artifacts exist.
- Resume does not rerun failed phases unless `--rerun-failed` is set.
- Per-run implementation failures do not stop unrelated scheduled runs.
- Judge malformed JSON marks only the judge phase failed.

Optional integration tests can use a tiny fake Codex executable that writes synthetic JSONL and stderr, then exits with a controlled return code.

## Acceptance Checklist

- Preflight records the selected Codex executable or a clear `CODEX_BIN` failure.
- Implementation commands are generated from run records, not hard-coded cell IDs.
- Judge commands are generated from judge config, with GPT-5.5 xhigh as the default initial experiment setting.
- Every Codex invocation writes raw JSONL and stderr artifacts.
- Every Codex invocation writes wall-time metadata.
- Final response extraction writes structured parsed or failed JSON.
- Timeouts preserve partial artifacts.
- Failed per-run Codex invocations are recorded without stopping unrelated runs.
- Rendered prompts preserve the nested Codex and external AI prohibition.
- Hidden tests remain outside implementation workspaces.
- Unit tests cover command construction, executable resolution, timeout handling, JSON extraction, and resume behavior without requiring real Codex execution.
