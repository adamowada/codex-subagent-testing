from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Any, Iterable, Mapping

from harness.artifacts import (
    CODEX_IMPLEMENTATION_ARTIFACTS,
    CODEX_JUDGE_ARTIFACTS,
    PHASE_ARTIFACTS,
    phase_artifact_paths,
    validate_artifact,
    validate_experiment_outputs,
    validate_hidden_artifact_privacy,
    validate_phase_artifacts,
    validate_run_metadata,
)
from harness.codex_runner import (
    ProcessResult,
    build_implementation_command,
    build_judge_command,
    command_for_display,
    extract_final_response,
    iso_now,
    materialize_worktree_command,
    resolve_codex_bin,
    resolve_npm_bin,
    run_logged_command,
    run_process_to_files,
    write_process_result,
)
from harness.jsonl_usage import summarize_usage, write_usage_summary
from harness.matrix import (
    REPO_ROOT,
    expand_experiment_matrix,
    load_experiment_config,
    summarize_matrix,
)
from harness.preflight import run_preflight, write_preflight
from harness.prompt_rendering import render_codex_config, render_implementation_prompt, render_judge_prompt
from harness.report_data import write_results_outputs
from harness.scoring import compute_run_score, write_run_score
from harness.validation import validate_stage11, write_validation_report


RUNS_DIR_NAME = "runs"
DEFAULT_WORKSPACE_ROOT_NAME = "codex-subagent-testing-workspaces"
STATE_PHASES = [
    "prepared",
    "baseline_committed",
    "rendered",
    "implemented",
    "diff_captured",
    "public_tested",
    "hidden_tested",
    "judged",
    "usage_parsed",
    "scored",
]
COPY_IGNORE_PATTERNS = [
    "node_modules",
    "dist",
    "build",
    "coverage",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "*.pyc",
    "*.tsbuildinfo",
]
WORKTREE_GIT_EXCLUDE_PATTERNS = [*COPY_IGNORE_PATTERNS, "pytest-cache-files-*"]
LOG_LOCK = threading.Lock()


class OrchestrationError(RuntimeError):
    """Raised when shared infrastructure prevents orchestration."""


class StatusWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.payload: dict[str, Any] = {
            "schema_version": 1,
            "status": "running",
            "started_at": iso_now(),
            "updated_at": iso_now(),
            "runs": {},
        }

    def update_run(self, run_id: str, **values: Any) -> None:
        with self.lock:
            run_payload = self.payload["runs"].setdefault(run_id, {})
            run_payload.update(values)
            self.payload["updated_at"] = iso_now()
            self.write_locked()

    def update(self, **values: Any) -> None:
        with self.lock:
            self.payload.update(values)
            self.payload["updated_at"] = iso_now()
            self.write_locked()

    def write_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run(args)
    except OrchestrationError as exc:
        print(f"orchestration failed: {exc}", file=sys.stderr)
        return 2


def run(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    config_path = _resolve_path(args.config, repo_root)
    runs_root = _resolve_path(args.runs_root, repo_root)
    config = load_experiment_config(config_path)
    all_runs = expand_experiment_matrix(config)
    selected_runs = select_runs(all_runs, pilot=args.pilot, run_ids=args.run_id)
    if not selected_runs:
        raise OrchestrationError("no runs selected")

    experiment_dir = resolve_experiment_dir(
        runs_root=runs_root,
        config=config,
        pilot=args.pilot,
        experiment_name=args.experiment_name,
        resume=args.resume,
    )
    experiment_dir.mkdir(parents=True, exist_ok=True)
    workspace_root = resolve_workspace_root(args.workspace_root, repo_root)
    workspace_root.mkdir(parents=True, exist_ok=True)
    if args.resume:
        validate_resume_target(experiment_dir, config, selected_runs)
    status = StatusWriter(experiment_dir / "status.json")
    log_path = experiment_dir / "orchestrator.log"
    _append_log(log_path, f"started {iso_now()}")
    _append_log(log_path, f"experiment_dir={experiment_dir}")
    _append_log(log_path, f"workspace_root={workspace_root}")

    preflight = run_preflight(
        config_path=config_path,
        repo_root=repo_root,
        require_codex=not args.dry_run,
    )
    write_preflight(experiment_dir / "preflight.json", preflight)
    if preflight["status"] == "failed":
        status.update(status="failed", failure="preflight failed")
        raise OrchestrationError("preflight failed; see preflight.json")

    write_experiment_metadata(
        experiment_dir=experiment_dir,
        config_path=config_path,
        config=config,
        all_runs=all_runs,
        selected_runs=selected_runs,
        args=args,
        workspace_root=workspace_root,
    )
    status.update(
        status="dry_run" if args.dry_run else "running",
        experiment_dir=str(experiment_dir),
        selected_runs=len(selected_runs),
    )

    print(f"Experiment directory: {experiment_dir}")
    print(f"Selected runs: {len(selected_runs)}")
    print(json.dumps(summarize_matrix(selected_runs), indent=2, sort_keys=True))

    if args.dry_run:
        status.update(status="completed", finished_at=iso_now(), dry_run=True)
        print("Dry run complete; no Codex jobs were launched.")
        return 0

    codex_bin = resolve_codex_bin()
    if codex_bin is None:
        raise OrchestrationError('Codex executable not found. Set $env:CODEX_BIN = "path\\to\\working\\codex".')

    for run_record in selected_runs:
        prepare_run(
            repo_root=repo_root,
            experiment_dir=experiment_dir,
            workspace_root=workspace_root,
            run=run_record,
            rerun_failed=args.rerun_failed,
            status=status,
            log_path=log_path,
        )

    implementation_failures = run_parallel(
        selected_runs,
        max_workers=args.jobs,
        label="implementation",
        worker=lambda run_record: run_implementation_and_tests(
            repo_root=repo_root,
            experiment_dir=experiment_dir,
            run=run_record,
            codex_bin=codex_bin,
            rerun_failed=args.rerun_failed,
            status=status,
            log_path=log_path,
        ),
    )

    judge_failures = run_parallel(
        selected_runs,
        max_workers=args.judge_jobs,
        label="judge",
        worker=lambda run_record: run_judge(
            experiment_dir=experiment_dir,
            run=run_record,
            codex_bin=codex_bin,
            rerun_failed=args.rerun_failed,
            status=status,
            log_path=log_path,
        ),
    )

    for run_record in selected_runs:
        parse_usage_and_score(
            experiment_dir,
            run_record,
            status,
            log_path,
            rerun_failed=args.rerun_failed,
        )

    outputs = {}
    if not args.no_report:
        outputs = write_results_outputs(experiment_dir, selected_runs)
        output_errors = validate_experiment_outputs(experiment_dir)
        if output_errors:
            status.update(status="failed", failure="experiment output validation failed")
            raise OrchestrationError(_format_artifact_errors("experiment output validation failed", output_errors))
        status.update(report_outputs=outputs)

    validation = validate_stage11(
        config_path=config_path,
        repo_root=repo_root,
        experiment_dir=experiment_dir,
        selected_runs=selected_runs,
        require_codex=not args.dry_run,
        require_report_outputs=not args.no_report,
        preflight_result=preflight,
    )
    write_validation_report(experiment_dir / "validation.json", validation)
    if validation["status"] == "failed":
        status.update(status="failed", failure="stage 11 validation failed")
        validation_errors = [
            f"{check['name']}: {check.get('details', '')}"
            for check in validation.get("checks", [])
            if check.get("status") == "failed"
        ]
        raise OrchestrationError(_format_artifact_errors("stage 11 validation failed", validation_errors))
    status.update(stage11_validation=validation["status"])

    status.update(
        status="completed",
        finished_at=iso_now(),
        implementation_failures=implementation_failures,
        judge_failures=judge_failures,
    )
    _append_log(log_path, f"completed {iso_now()}")
    print(f"Completed experiment artifacts under: {experiment_dir}")
    if outputs:
        print(f"Report HTML: {outputs['report_html']}")
        print(f"Report PDF: {outputs['report_pdf']}")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or resume the Codex subagent benchmark experiment.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Repository root. Defaults to this checkout.")
    parser.add_argument("--config", default="configs/initial_experiment.yaml", help="Experiment config path.")
    parser.add_argument("--runs-root", default="runs", help="Directory for generated experiment outputs.")
    parser.add_argument(
        "--workspace-root",
        help=(
            "Directory for measured implementation worktrees. Defaults to a temp-root outside this repository "
            "so hidden tests are not reachable through run worktree parent traversal."
        ),
    )
    parser.add_argument("--experiment-name", help="Optional suffix for a new experiment directory.")
    parser.add_argument("--resume", help="Existing experiment directory to resume.")
    parser.add_argument("--jobs", type=int, default=None, help="Implementation job parallelism.")
    parser.add_argument("--judge-jobs", type=int, default=None, help="Judge job parallelism.")
    parser.add_argument("--run-id", action="append", help="Specific run ID to include. May be repeated.")
    parser.add_argument("--pilot", action="store_true", help="Run the two-run pilot subset.")
    parser.add_argument("--rerun-failed", action="store_true", help="Rerun failed Codex phases.")
    parser.add_argument("--no-report", action="store_true", help="Skip experiment-level report output generation.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and write plan artifacts without launching Codex.")
    args = parser.parse_args(argv)

    config = load_experiment_config(_resolve_path(args.config, Path(args.repo_root).resolve()))
    parallelism = config.get("parallelism", {})
    if args.jobs is None:
        args.jobs = int(parallelism.get("implementation_jobs", 1))
    if args.judge_jobs is None:
        args.judge_jobs = int(parallelism.get("judge_jobs", 1))
    if args.jobs <= 0:
        parser.error("--jobs must be positive")
    if args.judge_jobs <= 0:
        parser.error("--judge-jobs must be positive")
    return args


def select_runs(
    runs: list[dict[str, Any]],
    *,
    pilot: bool = False,
    run_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    if run_ids:
        wanted = set(run_ids)
        selected = [run for run in runs if run["run_id"] in wanted]
        missing = sorted(wanted - {run["run_id"] for run in selected})
        if missing:
            raise OrchestrationError(f"unknown run id(s): {', '.join(missing)}")
        return selected

    if not pilot:
        return list(runs)

    c0 = next((run for run in runs if run.get("cell_id") == "C0"), None)
    c1_proposal = next((run for run in runs if run.get("cell_id") == "C1" and run.get("spark_mode") == "proposal"), None)
    if c0 is None or c1_proposal is None:
        raise OrchestrationError("pilot selection requires one C0 run and one C1 proposal run")
    return [c0, c1_proposal]


def resolve_experiment_dir(
    *,
    runs_root: Path,
    config: Mapping[str, Any],
    pilot: bool,
    experiment_name: str | None,
    resume: str | None,
) -> Path:
    if resume:
        path = Path(resume)
        if not path.is_absolute():
            path = runs_root / path
        if not path.exists():
            raise OrchestrationError(f"resume directory does not exist: {path}")
        return path.resolve()

    experiment = config.get("experiment", {})
    experiment_id = experiment.get("id", "experiment") if isinstance(experiment, Mapping) else "experiment"
    name_parts = [iso_now().replace(":", "").replace("-", "")[:15]]
    if pilot:
        name_parts.append("pilot")
    name_parts.append(str(experiment_id))
    if experiment_name:
        name_parts.append(experiment_name)
    base_name = _safe_name("-".join(name_parts))
    runs_root.mkdir(parents=True, exist_ok=True)

    candidate = runs_root / base_name
    suffix = 1
    while candidate.exists():
        suffix += 1
        candidate = runs_root / f"{base_name}-{suffix:02d}"
    return candidate.resolve()


def write_experiment_metadata(
    *,
    experiment_dir: Path,
    config_path: Path,
    config: Mapping[str, Any],
    all_runs: list[dict[str, Any]],
    selected_runs: list[dict[str, Any]],
    args: argparse.Namespace,
    workspace_root: Path | None = None,
) -> None:
    payload = {
        "schema_version": 1,
        "created_at": iso_now(),
        "config_path": str(config_path),
        "pilot": bool(args.pilot),
        "dry_run": bool(args.dry_run),
        "jobs": args.jobs,
        "judge_jobs": args.judge_jobs,
        "workspace_root": str(workspace_root) if workspace_root is not None else None,
        "selected_run_count": len(selected_runs),
        "full_run_count": len(all_runs),
        "matrix_summary": summarize_matrix(selected_runs),
        "config_sha256": _json_sha256(config),
    }
    _write_json(experiment_dir / "experiment-metadata.json", payload)
    _write_json(experiment_dir / "experiment_metadata.json", payload)
    _write_json(experiment_dir / "config.resolved.json", config)
    _write_json(experiment_dir / "resolved_config.json", config)
    _write_json(experiment_dir / "matrix.json", selected_runs)
    _write_json(experiment_dir / "matrix-summary.json", summarize_matrix(selected_runs))


def validate_resume_target(
    experiment_dir: Path,
    config: Mapping[str, Any],
    selected_runs: list[dict[str, Any]],
) -> None:
    existing_config = _read_json_first(experiment_dir, ["resolved_config.json", "config.resolved.json"])
    if existing_config:
        existing_hash = _json_sha256(existing_config)
        current_hash = _json_sha256(config)
        if existing_hash != current_hash:
            raise OrchestrationError(
                "resume config drift detected; start a new experiment directory for changed config"
            )

    existing_matrix = _read_json_any(experiment_dir / "matrix.json")
    if isinstance(existing_matrix, list):
        existing_ids = [run.get("run_id") for run in existing_matrix if isinstance(run, Mapping)]
        selected_ids = [run["run_id"] for run in selected_runs]
        if existing_ids != selected_ids:
            raise OrchestrationError(
                "resume matrix drift detected; selected run IDs do not match existing experiment"
            )

    for run in selected_runs:
        run_dir = run_directory(experiment_dir, run)
        if (run_dir / "metadata.json").exists():
            errors = validate_run_metadata(run_dir, run)
            if errors:
                raise OrchestrationError(_format_artifact_errors("resume metadata drift detected", errors))


def prepare_run(
    *,
    repo_root: Path,
    experiment_dir: Path,
    workspace_root: Path,
    run: Mapping[str, Any],
    rerun_failed: bool,
    status: StatusWriter,
    log_path: Path,
) -> None:
    run_dir = run_directory(experiment_dir, run)
    worktree = worktree_directory(experiment_dir, run, workspace_root)
    state = load_state(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    status.update_run(str(run["run_id"]), phase="preparing")

    if not phase_completed(state, "prepared", phase_artifact_paths(run_dir, "prepared")):
        if worktree.exists():
            if rerun_failed:
                _archive_path(worktree)
            else:
                raise OrchestrationError(f"worktree exists but prepared phase is incomplete: {worktree}")
        copy_benchmark_template(repo_root / "benchmark_template", worktree)
        write_worktree_pointer(run_dir, worktree, repo_root)
        mark_phase(run_dir, "prepared", "completed", {"worktree": str(worktree)})
        _append_log(log_path, f"{run['run_id']} prepared worktree")

    metadata_path = run_dir / "metadata.json"
    if phase_completed(load_state(run_dir), "baseline_committed", phase_artifact_paths(run_dir, "baseline_committed")):
        errors = validate_run_metadata(run_dir, run)
        if errors:
            raise OrchestrationError(_format_artifact_errors("run metadata validation failed", errors))
    else:
        baseline_sha = initialize_git_baseline(worktree)
        metadata = run_metadata(run, run_dir, worktree, baseline_sha)
        _write_json(metadata_path, metadata)
        mark_phase(run_dir, "baseline_committed", "completed", {"baseline_sha": baseline_sha})
        _append_log(log_path, f"{run['run_id']} baseline {baseline_sha}")

    if not phase_completed(load_state(run_dir), "rendered", phase_artifact_paths(run_dir, "rendered")):
        render_artifacts(repo_root, run_dir, run)
        mark_phase(run_dir, "rendered", "completed", {"rendered_at": iso_now()})
    status.update_run(str(run["run_id"]), phase="prepared")


def run_implementation_and_tests(
    *,
    repo_root: Path,
    experiment_dir: Path,
    run: Mapping[str, Any],
    codex_bin: str,
    rerun_failed: bool,
    status: StatusWriter,
    log_path: Path,
) -> None:
    run_dir = run_directory(experiment_dir, run)
    worktree = worktree_path(run_dir)
    state = load_state(run_dir)
    status.update_run(str(run["run_id"]), phase="implementation")

    implementation_reran = False
    if should_run_phase(state, "implemented", run_dir / "events.jsonl", rerun_failed):
        archived_to = archive_failed_phase_artifacts(
            run_dir,
            "implemented",
            CODEX_IMPLEMENTATION_ARTIFACTS,
            state,
            rerun_failed,
        )
        prompt = (run_dir / "rendered_prompt.md").read_text(encoding="utf-8")
        command = materialize_worktree_command(
            build_implementation_command(codex_bin, run, prompt, config_dir=run_dir / "codex_config"),
            worktree,
        )
        display_command = command_for_display(command)
        _append_log(log_path, f"{run['run_id']} implementation command={json.dumps(display_command)}")
        result = run_process_to_files(
            command,
            cwd=worktree,
            stdout_path=run_dir / "events.jsonl",
            stderr_path=run_dir / "stderr.log",
            timeout_seconds=int(run["timeouts"]["implementation_seconds"]),
            command_display=display_command,
        )
        write_process_result(run_dir / "wall_time.json", result)
        final_response = extract_final_response(run_dir / "events.jsonl")
        _write_json(run_dir / "final_response.json", final_response)
        phase_data = {
            "returncode": result.returncode,
            "timed_out": result.timed_out,
            "elapsed_seconds": result.elapsed_seconds,
            "stdout_path": result.stdout_path,
            "stderr_path": result.stderr_path,
            "final_response_parsed": final_response.get("parsed"),
        }
        if archived_to is not None:
            phase_data["previous_artifacts_archived_to"] = archived_to
        mark_phase(
            run_dir,
            "implemented",
            "completed" if result.returncode == 0 and not result.timed_out else "failed",
            phase_data,
        )
        _append_log(
            log_path,
            (
                f"{run['run_id']} implementation returncode={result.returncode} "
                f"timeout={result.timed_out} elapsed={result.elapsed_seconds} "
                f"stdout={result.stdout_path} stderr={result.stderr_path}"
            ),
        )
        implementation_reran = True

    state = load_state(run_dir)
    diff_stale = implementation_reran or phase_stale_after(state, "diff_captured", "implemented")
    if diff_stale or should_run_phase(state, "diff_captured", run_dir / "diff.patch", rerun_failed):
        archived_to = (
            archive_phase_artifacts(run_dir, "diff_captured", PHASE_ARTIFACTS["diff_captured"])
            if diff_stale
            else None
        )
        capture_diff(run_dir, worktree)
        phase_data = {"captured_at": iso_now()}
        if archived_to is not None:
            phase_data["previous_artifacts_archived_to"] = archived_to
            phase_data["rerun_reason"] = "implemented_reran"
        mark_phase(run_dir, "diff_captured", "completed", phase_data)

    state = load_state(run_dir)
    public_stale = implementation_reran or phase_stale_after(state, "public_tested", "implemented")
    public_repair = rerun_failed and _public_tests_have_launch_errors(run_dir)
    if public_stale or public_repair or should_run_phase(state, "public_tested", run_dir / "typecheck.meta.json", rerun_failed):
        archived_to = (
            archive_phase_artifacts(run_dir, "public_tested", PHASE_ARTIFACTS["public_tested"])
            if public_stale or public_repair
            else None
        )
        public_results = run_public_tests(worktree, run_dir, run)
        public_launch_errors = _results_have_launch_errors(public_results.values())
        phase_data = {
            "tested_at": iso_now(),
            "returncodes": {name: result.returncode for name, result in public_results.items()},
        }
        if archived_to is not None:
            phase_data["previous_artifacts_archived_to"] = archived_to
            phase_data["rerun_reason"] = "implemented_reran" if public_stale else "launch_error_repair"
        mark_phase(run_dir, "public_tested", "failed" if public_launch_errors else "completed", phase_data)

    state = load_state(run_dir)
    hidden_stale = implementation_reran or phase_stale_after(state, "hidden_tested", "implemented")
    if hidden_stale or should_run_phase(state, "hidden_tested", run_dir / "hidden-results.json", rerun_failed):
        archived_to = (
            archive_phase_artifacts(run_dir, "hidden_tested", PHASE_ARTIFACTS["hidden_tested"])
            if hidden_stale
            else None
        )
        run_hidden_tests(repo_root, worktree, run_dir, run)
        hidden_meta = _read_json(run_dir / "hidden-runner.meta.json")
        privacy_errors = validate_hidden_artifact_privacy(run_dir)
        hidden_completed = hidden_meta.get("returncode") == 0 and not privacy_errors
        phase_data = {
            "tested_at": iso_now(),
            "returncode": hidden_meta.get("returncode"),
        }
        if archived_to is not None:
            phase_data["previous_artifacts_archived_to"] = archived_to
            phase_data["rerun_reason"] = "implemented_reran"
        if privacy_errors:
            phase_data["privacy_errors"] = privacy_errors
            _append_log(
                log_path,
                _format_artifact_errors(f"{run['run_id']} hidden artifact privacy validation failed", privacy_errors),
            )
        mark_phase(
            run_dir,
            "hidden_tested",
            "completed" if hidden_completed else "failed",
            phase_data,
        )
    status.update_run(str(run["run_id"]), phase="implementation_complete")


def run_judge(
    *,
    experiment_dir: Path,
    run: Mapping[str, Any],
    codex_bin: str,
    rerun_failed: bool,
    status: StatusWriter,
    log_path: Path,
) -> None:
    run_dir = run_directory(experiment_dir, run)
    worktree = worktree_path(run_dir)
    state = load_state(run_dir)
    status.update_run(str(run["run_id"]), phase="judge")

    judge_stale = any(
        phase_stale_after(state, "judged", upstream)
        for upstream in ("diff_captured", "public_tested", "hidden_tested")
    )
    if not judge_stale and not should_run_phase(state, "judged", run_dir / "judge.events.jsonl", rerun_failed):
        return

    if judge_stale:
        archived_to = archive_phase_artifacts(run_dir, "judged", CODEX_JUDGE_ARTIFACTS)
    else:
        archived_to = archive_failed_phase_artifacts(
            run_dir,
            "judged",
            CODEX_JUDGE_ARTIFACTS,
            state,
            rerun_failed,
        )
    prepare_judge_evidence(run_dir, worktree)
    prompt = (run_dir / "judge_prompt.md").read_text(encoding="utf-8")
    command = materialize_worktree_command(build_judge_command(codex_bin, run, prompt), worktree)
    display_command = command_for_display(command)
    _append_log(log_path, f"{run['run_id']} judge command={json.dumps(display_command)}")
    result = run_process_to_files(
        command,
        cwd=worktree,
        stdout_path=run_dir / "judge.events.jsonl",
        stderr_path=run_dir / "judge.stderr.log",
        timeout_seconds=int(run["timeouts"]["judge_seconds"]),
        command_display=display_command,
    )
    write_process_result(run_dir / "judge.wall_time.json", result)
    judge_json = extract_final_response(run_dir / "judge.events.jsonl")
    _write_json(run_dir / "judge.json", judge_json)
    phase_data = {
        "returncode": result.returncode,
        "timed_out": result.timed_out,
        "elapsed_seconds": result.elapsed_seconds,
        "stdout_path": result.stdout_path,
        "stderr_path": result.stderr_path,
        "parsed": judge_json.get("parsed"),
    }
    if archived_to is not None:
        phase_data["previous_artifacts_archived_to"] = archived_to
        if judge_stale:
            phase_data["rerun_reason"] = "upstream_artifacts_reran"
    mark_phase(
        run_dir,
        "judged",
        "completed" if result.returncode == 0 and not result.timed_out and judge_json.get("parsed") else "failed",
        phase_data,
    )
    _append_log(
        log_path,
        (
            f"{run['run_id']} judge returncode={result.returncode} "
            f"timeout={result.timed_out} elapsed={result.elapsed_seconds} "
            f"stdout={result.stdout_path} stderr={result.stderr_path}"
        ),
    )
    status.update_run(str(run["run_id"]), phase="judged")


def parse_usage_and_score(
    experiment_dir: Path,
    run: Mapping[str, Any],
    status: StatusWriter,
    log_path: Path,
    *,
    rerun_failed: bool = False,
) -> None:
    run_dir = run_directory(experiment_dir, run)
    state = load_state(run_dir)
    usage_regenerated = False
    usage_stale = any(phase_stale_after(state, "usage_parsed", upstream) for upstream in ("implemented", "judged"))
    if usage_stale or should_run_phase(state, "usage_parsed", run_dir / "usage.json", rerun_failed):
        archived_to = (
            archive_phase_artifacts(run_dir, "usage_parsed", PHASE_ARTIFACTS["usage_parsed"])
            if usage_stale
            else None
        )
        usage = summarize_usage(
            implementation_events_path=run_dir / "events.jsonl",
            judge_events_path=run_dir / "judge.events.jsonl",
            run=run,
        )
        write_usage_summary(run_dir / "usage.json", usage)
        phase_data = {"parsed_at": iso_now()}
        if archived_to is not None:
            phase_data["previous_artifacts_archived_to"] = archived_to
            phase_data["rerun_reason"] = "codex_events_reran"
        mark_phase(run_dir, "usage_parsed", "completed", phase_data)
        usage_regenerated = True

    state = load_state(run_dir)
    score_stale = any(
        phase_stale_after(state, "scored", upstream)
        for upstream in ("diff_captured", "public_tested", "hidden_tested", "judged", "usage_parsed")
    )
    if usage_regenerated or score_stale or should_run_phase(state, "scored", run_dir / "score.json", rerun_failed):
        archived_to = (
            archive_phase_artifacts(run_dir, "scored", PHASE_ARTIFACTS["scored"])
            if score_stale
            else None
        )
        score = compute_run_score(run_dir, run)
        write_run_score(run_dir / "score.json", score)
        phase_data = {"quality_score": score.get("quality_score")}
        if archived_to is not None:
            phase_data["previous_artifacts_archived_to"] = archived_to
            phase_data["rerun_reason"] = "score_inputs_reran"
        mark_phase(run_dir, "scored", "completed", phase_data)
        _append_log(log_path, f"{run['run_id']} scored quality={score.get('quality_score')}")
        status.update_run(str(run["run_id"]), phase="scored", quality_score=score.get("quality_score"))


def run_parallel(
    runs: list[dict[str, Any]],
    *,
    max_workers: int,
    label: str,
    worker: Any,
) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_run = {executor.submit(worker, run): run for run in runs}
        for future in as_completed(future_to_run):
            run = future_to_run[future]
            try:
                future.result()
            except Exception as exc:
                failures.append({"run_id": str(run["run_id"]), "phase": label, "error": str(exc)})
    return failures


def copy_benchmark_template(source: Path, destination: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            for pattern in COPY_IGNORE_PATTERNS:
                if fnmatch.fnmatch(name, pattern):
                    ignored.add(name)
        return ignored

    shutil.copytree(source, destination, ignore=ignore)


def initialize_git_baseline(worktree: Path) -> str:
    commands = [
        ["git", "init"],
        ["git", "config", "user.email", "codex-harness@example.invalid"],
        ["git", "config", "user.name", "Codex Harness"],
    ]
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=worktree,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise OrchestrationError(f"git command failed in {worktree}: {' '.join(command)}\n{completed.stderr}")
    configure_worktree_git_excludes(worktree)
    for command in (["git", "add", "."], ["git", "commit", "-m", "baseline"]):
        completed = subprocess.run(
            command,
            cwd=worktree,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise OrchestrationError(f"git command failed in {worktree}: {' '.join(command)}\n{completed.stderr}")
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=worktree,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise OrchestrationError(f"failed to read baseline commit in {worktree}: {completed.stderr}")
    return completed.stdout.strip()


def render_artifacts(repo_root: Path, run_dir: Path, run: Mapping[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "rendered_prompt.md").write_text(render_implementation_prompt(run, repo_root), encoding="utf-8")
    (run_dir / "judge_prompt.md").write_text(render_judge_prompt(run, repo_root), encoding="utf-8")
    config_files = render_codex_config(run, repo_root)
    config_dir = run_dir / "codex_config"
    for relative_path, contents in config_files.items():
        path = config_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")


def run_public_tests(worktree: Path, run_dir: Path, run: Mapping[str, Any]) -> dict[str, ProcessResult]:
    results: dict[str, ProcessResult] = {}
    npm = resolve_npm_bin() or "npm"
    if (worktree / "package.json").exists() and not _typescript_dependency_present(worktree):
        npm_ci = run_logged_command(
            [npm, "ci"],
            cwd=worktree,
            log_path=run_dir / "npm-ci.log",
            timeout_seconds=180,
        )
        write_process_result(run_dir / "npm-ci.meta.json", npm_ci)
        results["npm_ci"] = npm_ci

    commands = [
        ("typecheck", [npm, "run", "typecheck"], "typecheck.log"),
        ("public_ts", [npm, "run", "test:public"], "public_ts.log"),
        ("public_py", [sys.executable, "-m", "pytest", "-q", "tests_public_py"], "public_py.log"),
    ]
    timeout = int(run["timeouts"]["implementation_seconds"])
    for name, command, log_name in commands:
        result = run_logged_command(
            command,
            cwd=worktree,
            log_path=run_dir / log_name,
            timeout_seconds=min(timeout, 600),
        )
        write_process_result(run_dir / f"{name}.meta.json", result)
        results[name] = result
    return results


def run_hidden_tests(repo_root: Path, worktree: Path, run_dir: Path, run: Mapping[str, Any]) -> None:
    command = [
        sys.executable,
        "-m",
        "harness.hidden_runner",
        "--worktree",
        str(worktree),
        "--out",
        str(run_dir / "hidden-results.json"),
    ]
    result = run_logged_command(
        command,
        cwd=Path(tempfile.gettempdir()),
        log_path=run_dir / "hidden-runner.log",
        timeout_seconds=min(int(run["timeouts"]["implementation_seconds"]), 900),
        env=_pythonpath_env(repo_root),
    )
    write_process_result(run_dir / "hidden-runner.meta.json", result)


def capture_diff(run_dir: Path, worktree: Path) -> None:
    metadata = _read_json(run_dir / "metadata.json")
    baseline = metadata.get("baseline_commit", "HEAD")
    configure_worktree_git_excludes(worktree)
    subprocess.run(
        ["git", "add", "--intent-to-add", "."],
        cwd=worktree,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    diff = subprocess.run(
        ["git", "diff", "--patch", "--binary", str(baseline), "--"],
        cwd=worktree,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    (run_dir / "diff.patch").write_text(diff.stdout, encoding="utf-8", errors="replace")
    numstat = subprocess.run(
        ["git", "diff", "--numstat", str(baseline), "--"],
        cwd=worktree,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    (run_dir / "diff-numstat.txt").write_text(numstat.stdout, encoding="utf-8", errors="replace")


def configure_worktree_git_excludes(worktree: Path) -> None:
    exclude_path = worktree / ".git" / "info" / "exclude"
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude_path.read_text(encoding="utf-8", errors="replace") if exclude_path.exists() else ""
    existing_patterns = {line.strip() for line in existing.splitlines() if line.strip() and not line.startswith("#")}
    additions = [pattern for pattern in WORKTREE_GIT_EXCLUDE_PATTERNS if pattern not in existing_patterns]
    if not additions:
        return

    prefix = "" if not existing or existing.endswith("\n") else "\n"
    block = "# Codex subagent benchmark generated artifacts\n" + "\n".join(additions) + "\n"
    exclude_path.write_text(existing + prefix + block, encoding="utf-8")


def run_metadata(run: Mapping[str, Any], run_dir: Path, worktree: Path, baseline_sha: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run": run,
        "run_id": run["run_id"],
        "cell_id": run["cell_id"],
        "cell_name": run["cell_name"],
        "repeat_index": run["repeat_index"],
        "topology": run["topology"],
        "spark_mode": run.get("spark_mode"),
        "root": run["root"],
        "subleads": run.get("subleads"),
        "leaf": run.get("leaf"),
        "agents": run["agents"],
        "timeouts": run["timeouts"],
        "run_dir": str(run_dir),
        "worktree": str(worktree),
        "baseline_commit": baseline_sha,
        "created_at": iso_now(),
    }


def should_run_phase(state: Mapping[str, Any], phase: str, required_artifact: Path, rerun_failed: bool) -> bool:
    phases = state.get("phases", {}) if isinstance(state, Mapping) else {}
    phase_state = phases.get(phase, {}) if isinstance(phases, Mapping) else {}
    if isinstance(phase_state, Mapping):
        if phase_state.get("status") == "completed":
            errors = validate_phase_artifacts(required_artifact.parent, phase)
            if not errors and required_artifact.exists():
                return False
            if phase == "usage_parsed":
                return True
            raise OrchestrationError(_format_artifact_errors(f"completed phase has invalid artifacts: {phase}", errors))
        if phase_state.get("status") == "failed" and required_artifact.exists() and not rerun_failed:
            return False
    return True


def phase_stale_after(state: Mapping[str, Any], phase: str, upstream_phase: str) -> bool:
    phase_updated = _phase_updated_at(state, phase)
    upstream_updated = _phase_updated_at(state, upstream_phase)
    return phase_updated is not None and upstream_updated is not None and upstream_updated > phase_updated


def archive_phase_artifacts(run_dir: Path, phase: str, artifact_names: Iterable[str]) -> str | None:
    existing = [run_dir / name for name in artifact_names if (run_dir / name).exists()]
    if not existing:
        return None

    archive_dir = _unique_archive_dir(run_dir / "reruns", phase)
    for source in existing:
        target = archive_dir / source.relative_to(run_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
    return str(archive_dir)


def archive_failed_phase_artifacts(
    run_dir: Path,
    phase: str,
    artifact_names: Iterable[str],
    state: Mapping[str, Any],
    rerun_failed: bool,
) -> str | None:
    if not rerun_failed:
        return None

    phases = state.get("phases", {}) if isinstance(state, Mapping) else {}
    phase_state = phases.get(phase, {}) if isinstance(phases, Mapping) else {}
    if not isinstance(phase_state, Mapping) or phase_state.get("status") != "failed":
        return None

    return archive_phase_artifacts(run_dir, phase, artifact_names)


def phase_completed(state: Mapping[str, Any], phase: str, artifacts: Iterable[Path]) -> bool:
    phases = state.get("phases", {}) if isinstance(state, Mapping) else {}
    phase_state = phases.get(phase, {}) if isinstance(phases, Mapping) else {}
    paths = list(artifacts)
    return (
        isinstance(phase_state, Mapping)
        and phase_state.get("status") == "completed"
        and all(not validate_artifact(path) for path in paths)
    )


def mark_phase(run_dir: Path, phase: str, status: str, data: Mapping[str, Any] | None = None) -> None:
    state = load_state(run_dir)
    phases = state.setdefault("phases", {})
    phases[phase] = {
        "status": status,
        "updated_at": iso_now(),
        "data": dict(data or {}),
    }
    state["updated_at"] = iso_now()
    _write_json(run_dir / "state.json", state)


def load_state(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "state.json"
    if not path.exists():
        return {
            "schema_version": 1,
            "created_at": iso_now(),
            "updated_at": iso_now(),
            "phases": {phase: {"status": "pending"} for phase in STATE_PHASES},
        }
    return _read_json(path)


def _phase_updated_at(state: Mapping[str, Any], phase: str) -> str | None:
    phases = state.get("phases", {}) if isinstance(state, Mapping) else {}
    phase_state = phases.get(phase, {}) if isinstance(phases, Mapping) else {}
    updated_at = phase_state.get("updated_at") if isinstance(phase_state, Mapping) else None
    return updated_at if isinstance(updated_at, str) else None


def run_directory(experiment_dir: Path, run: Mapping[str, Any]) -> Path:
    return experiment_dir / RUNS_DIR_NAME / str(run["run_id"])


def resolve_workspace_root(workspace_root: str | os.PathLike[str] | None, repo_root: Path) -> Path:
    if workspace_root:
        path = Path(workspace_root)
        if not path.is_absolute():
            path = repo_root / path
    else:
        path = Path(tempfile.gettempdir()) / DEFAULT_WORKSPACE_ROOT_NAME
    resolved = path.resolve()
    if _is_relative_to(resolved, repo_root):
        raise OrchestrationError(
            f"workspace root must be outside the repository so hidden tests are not parent-reachable: {resolved}"
        )
    return resolved


def worktree_directory(experiment_dir: Path, run: Mapping[str, Any], workspace_root: Path) -> Path:
    return workspace_root / experiment_dir.name / RUNS_DIR_NAME / str(run["run_id"]) / "worktree"


def write_worktree_pointer(run_dir: Path, worktree: Path, repo_root: Path) -> None:
    _write_json(
        run_dir / "worktree.json",
        {
            "schema_version": 1,
            "path": str(worktree),
            "inside_repo": _is_relative_to(worktree.resolve(), repo_root.resolve()),
        },
    )


def worktree_path(run_dir: Path) -> Path:
    metadata = _read_json(run_dir / "metadata.json")
    worktree = metadata.get("worktree")
    if isinstance(worktree, str) and worktree:
        return Path(worktree)
    pointer = _read_json(run_dir / "worktree.json")
    pointer_path = pointer.get("path")
    if isinstance(pointer_path, str) and pointer_path:
        return Path(pointer_path)
    return run_dir / "worktree"


def prepare_judge_evidence(run_dir: Path, worktree: Path) -> None:
    evidence_dir = worktree / "judge_evidence"
    if evidence_dir.exists():
        shutil.rmtree(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for name in (
        "typecheck.log",
        "typecheck.meta.json",
        "public_ts.log",
        "public_ts.meta.json",
        "public_py.log",
        "public_py.meta.json",
        "hidden-results.json",
        "diff.patch",
        "diff-numstat.txt",
        "stderr.log",
        "final_response.json",
        "wall_time.json",
        "hidden-runner.meta.json",
        "hidden-runner.log",
    ):
        source = run_dir / name
        if not source.exists() or source.is_dir():
            continue
        target = evidence_dir / name
        shutil.copy2(source, target)
        copied.append(name)

    _write_json(
        evidence_dir / "evidence-manifest.json",
        {
            "schema_version": 1,
            "description": "Blind judge evidence bundle. Source files are in the workspace root.",
            "files": copied,
        },
    )


def _typescript_dependency_present(worktree: Path) -> bool:
    return (worktree / "node_modules" / ".bin" / "tsc").exists() or (
        worktree / "node_modules" / ".bin" / "tsc.cmd"
    ).exists()


def _public_tests_have_launch_errors(run_dir: Path) -> bool:
    names = ("npm-ci.meta.json", "typecheck.meta.json", "public_ts.meta.json", "public_py.meta.json")
    return any(_metadata_has_launch_error(run_dir / name) for name in names)


def _metadata_has_launch_error(path: Path) -> bool:
    meta = _read_json(path)
    return bool(meta) and meta.get("returncode") is None and not meta.get("timed_out")


def _results_have_launch_errors(results: Iterable[ProcessResult]) -> bool:
    return any(result.returncode is None and not result.timed_out for result in results)


def _archive_path(path: Path) -> Path:
    archive = path.with_name(f"{path.name}.archive-{iso_now().replace(':', '').replace('-', '')}")
    path.rename(archive)
    return archive


def _unique_archive_dir(parent: Path, phase: str) -> Path:
    timestamp = iso_now().replace(":", "").replace("-", "")
    candidate = parent / f"{phase}-{timestamp}"
    suffix = 1
    while candidate.exists():
        suffix += 1
        candidate = parent / f"{phase}-{timestamp}-{suffix:02d}"
    candidate.mkdir(parents=True)
    return candidate


def _append_log(path: Path, line: str) -> None:
    with LOG_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _read_json_first(root: Path, names: Iterable[str]) -> dict[str, Any]:
    for name in names:
        value = _read_json(root / name)
        if value:
            return value
    return {}


def _read_json_any(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _resolve_path(path_value: str | os.PathLike[str], repo_root: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return repo_root / path


def _pythonpath_env(repo_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(repo_root) if not existing else str(repo_root) + os.pathsep + existing
    return env


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _safe_name(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in value)
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe.strip("-") or "experiment"


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _format_artifact_errors(title: str, errors: Iterable[str]) -> str:
    details = list(errors)
    if not details:
        return title
    return title + ": " + "; ".join(details)


if __name__ == "__main__":
    raise SystemExit(main())
