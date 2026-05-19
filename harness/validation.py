from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping, Sequence

from harness.artifacts import (
    CORE_RUN_ARTIFACTS,
    validate_artifact,
    validate_artifacts,
    validate_experiment_outputs,
    validate_hidden_artifact_privacy,
    validate_run_metadata,
)
from harness.matrix import REPO_ROOT, expand_experiment_matrix, load_experiment_config, summarize_matrix
from harness.preflight import run_preflight
from harness.report_data import PRIMARY_METRIC


PILOT_RUN_IDS = ["C0_r01", "C1_proposal_r01"]
EXPECTED_FULL_RUN_COUNT = 45
REPORT_OUTPUTS = (
    "results/results.csv",
    "results/results.sqlite",
    "results/aggregate.json",
    "report/report.html",
    "report/report.pdf",
)
SCRIPT_CONTRACTS = {
    "scripts/run_pilot.ps1": "--pilot",
    "scripts/run_experiment.ps1": "--jobs",
}
SKIP_WORKTREE_SCAN_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "__pycache__",
    ".pytest_cache",
}


@dataclass(frozen=True)
class Stage11Check:
    name: str
    status: str
    details: str = ""
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_stage11(
    *,
    config_path: str | Path,
    repo_root: str | Path = REPO_ROOT,
    experiment_dir: str | Path | None = None,
    selected_runs: Sequence[Mapping[str, Any]] | None = None,
    require_codex: bool = False,
    require_report_outputs: bool = True,
    run_preflight_check: bool = True,
    preflight_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the Stage 11 benchmark acceptance contract.

    The validator is intentionally evidence-oriented. It does not rerun measured
    agents or judges; it checks configuration, preflight results, preserved
    artifacts, hidden-test privacy, report outputs, and resume compatibility.
    """

    root = Path(repo_root).resolve()
    config_file = _resolve_path(config_path, root)
    experiment_path = Path(experiment_dir).resolve() if experiment_dir is not None else None
    checks: list[Stage11Check] = []

    try:
        config = load_experiment_config(config_file)
        all_runs = expand_experiment_matrix(config)
    except Exception as exc:
        checks.append(_failed("experiment_config", str(exc)))
        return _payload(
            root=root,
            config_path=config_file,
            experiment_dir=experiment_path,
            all_runs=[],
            selected=[],
            checks=checks,
        )

    selected = _selected_runs(experiment_path, selected_runs, all_runs)

    checks.append(_matrix_contract_check(all_runs))
    checks.append(_pilot_selection_check(all_runs))
    checks.append(_script_contract_check(root))

    if run_preflight_check:
        checks.append(
            _preflight_check(
                config_path=config_file,
                repo_root=root,
                require_codex=require_codex,
                preflight_result=preflight_result,
                experiment_dir=experiment_path,
            )
        )

    if experiment_path is not None:
        checks.extend(
            _experiment_checks(
                experiment_dir=experiment_path,
                config=config,
                selected_runs=selected,
                require_report_outputs=require_report_outputs,
                repo_root=root,
            )
        )

    return _payload(
        root=root,
        config_path=config_file,
        experiment_dir=experiment_path,
        all_runs=all_runs,
        selected=selected,
        checks=checks,
    )


def write_validation_report(path: str | Path, payload: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    payload = validate_stage11(
        config_path=args.config,
        repo_root=args.repo_root,
        experiment_dir=args.experiment_dir,
        require_codex=args.require_codex,
        require_report_outputs=not args.allow_missing_report,
        run_preflight_check=not args.skip_preflight,
    )
    if args.output:
        write_validation_report(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if payload["status"] == "failed" else 0


def _experiment_checks(
    *,
    experiment_dir: Path,
    config: Mapping[str, Any],
    selected_runs: Sequence[Mapping[str, Any]],
    require_report_outputs: bool,
    repo_root: Path,
) -> list[Stage11Check]:
    checks = [
        _experiment_metadata_check(experiment_dir, config, selected_runs),
        _run_artifacts_check(experiment_dir, selected_runs),
        _hidden_isolation_check(experiment_dir, selected_runs, repo_root),
        _judge_json_check(experiment_dir, selected_runs),
        _resume_contract_check(experiment_dir, config, selected_runs),
    ]
    if require_report_outputs:
        checks.append(_report_outputs_check(experiment_dir, selected_runs))
    else:
        checks.append(_warning("report_outputs", "report output validation skipped"))
    return checks


def _matrix_contract_check(runs: Sequence[Mapping[str, Any]]) -> Stage11Check:
    summary = summarize_matrix(list(runs))
    if len(runs) != EXPECTED_FULL_RUN_COUNT:
        return _failed(
            "matrix_contract",
            f"expected {EXPECTED_FULL_RUN_COUNT} full runs, got {len(runs)}",
            summary,
        )
    return _passed("matrix_contract", f"expanded {len(runs)} runs", summary)


def _pilot_selection_check(runs: Sequence[Mapping[str, Any]]) -> Stage11Check:
    selected: list[str] = []
    c0 = next((run for run in runs if run.get("cell_id") == "C0"), None)
    c1_proposal = next(
        (run for run in runs if run.get("cell_id") == "C1" and run.get("spark_mode") == "proposal"),
        None,
    )
    if c0 is not None:
        selected.append(str(c0.get("run_id")))
    if c1_proposal is not None:
        selected.append(str(c1_proposal.get("run_id")))
    if selected != PILOT_RUN_IDS:
        return _failed("pilot_selection", f"expected {PILOT_RUN_IDS}, got {selected}")
    return _passed("pilot_selection", "pilot selects solo and proposal Spark runs", {"run_ids": selected})


def _script_contract_check(repo_root: Path) -> Stage11Check:
    missing: list[str] = []
    malformed: list[str] = []
    for relative_path, required_text in SCRIPT_CONTRACTS.items():
        path = repo_root / relative_path
        if not path.exists():
            missing.append(relative_path)
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if required_text not in text:
            malformed.append(f"{relative_path}: missing {required_text!r}")

    if missing or malformed:
        details = []
        if missing:
            details.append(f"missing scripts: {', '.join(missing)}")
        details.extend(malformed)
        return _failed("script_contract", "; ".join(details))
    return _passed("script_contract", "pilot and experiment scripts expose expected orchestration flags")


def _preflight_check(
    *,
    config_path: Path,
    repo_root: Path,
    require_codex: bool,
    preflight_result: Mapping[str, Any] | None,
    experiment_dir: Path | None,
) -> Stage11Check:
    result: Mapping[str, Any] | None = preflight_result
    if result is None and experiment_dir is not None:
        loaded = _read_json(experiment_dir / "preflight.json")
        if isinstance(loaded, Mapping) and loaded:
            result = loaded
    if result is None:
        result = run_preflight(config_path=config_path, repo_root=repo_root, require_codex=require_codex)

    status = result.get("status")
    details = f"preflight status: {status}"
    data = {
        "status": status,
        "codex_bin": result.get("codex_bin"),
        "failed_checks": _check_names(result, "failed"),
        "warning_checks": _check_names(result, "warning"),
    }
    if status == "failed":
        return _failed("preflight", details, data)
    if status == "warning":
        return _warning("preflight", details, data)
    return _passed("preflight", details, data)


def _experiment_metadata_check(
    experiment_dir: Path,
    config: Mapping[str, Any],
    selected_runs: Sequence[Mapping[str, Any]],
) -> Stage11Check:
    errors: list[str] = []
    for name in (
        "experiment_metadata.json",
        "resolved_config.json",
        "matrix.json",
        "matrix-summary.json",
        "status.json",
        "orchestrator.log",
        "preflight.json",
    ):
        errors.extend(validate_artifact(experiment_dir / name))

    resolved_config = _read_json(experiment_dir / "resolved_config.json")
    if resolved_config and _json_sha256(resolved_config) != _json_sha256(config):
        errors.append("resolved_config.json does not match selected config")

    matrix = _read_json_any(experiment_dir / "matrix.json")
    if isinstance(matrix, list):
        matrix_ids = [str(run.get("run_id")) for run in matrix if isinstance(run, Mapping)]
        selected_ids = [str(run["run_id"]) for run in selected_runs]
        if matrix_ids != selected_ids:
            errors.append(f"matrix run IDs do not match selected runs: {matrix_ids} != {selected_ids}")
    else:
        errors.append("matrix.json is not a run list")

    metadata = _read_json(experiment_dir / "experiment_metadata.json")
    if metadata:
        count = metadata.get("selected_run_count")
        if count != len(selected_runs):
            errors.append(f"experiment_metadata.selected_run_count expected {len(selected_runs)}, got {count}")

    if errors:
        return _failed("experiment_metadata", _join_errors(errors), {"error_count": len(errors)})
    return _passed("experiment_metadata", "experiment metadata and matrix are consistent")


def _run_artifacts_check(experiment_dir: Path, selected_runs: Sequence[Mapping[str, Any]]) -> Stage11Check:
    errors: list[str] = []
    warnings: list[str] = []
    for run in selected_runs:
        run_id = str(run["run_id"])
        run_dir = experiment_dir / "runs" / run_id
        if not run_dir.exists():
            errors.append(f"{run_id}: missing run directory")
            continue
        metadata_errors = validate_run_metadata(run_dir, run)
        errors.extend(f"{run_id}: {error}" for error in metadata_errors)
        artifact_errors = validate_artifacts(run_dir, CORE_RUN_ARTIFACTS)
        errors.extend(f"{run_id}: {error}" for error in artifact_errors)

        state = _read_json(run_dir / "state.json")
        phases = state.get("phases", {}) if isinstance(state, Mapping) else {}
        failed_phases = [
            name
            for name, phase in phases.items()
            if isinstance(phase, Mapping) and phase.get("status") == "failed"
        ]
        if failed_phases:
            warnings.append(f"{run_id}: failed phases preserved: {', '.join(sorted(failed_phases))}")

    if errors:
        return _failed(
            "run_artifacts",
            _join_errors(errors),
            {"error_count": len(errors), "warning_count": len(warnings), "warnings": warnings[:20]},
        )
    if warnings:
        return _warning(
            "run_artifacts",
            "run artifacts are valid with preserved failed phases",
            {"warning_count": len(warnings), "warnings": warnings[:20]},
        )
    return _passed("run_artifacts", f"validated artifacts for {len(selected_runs)} run(s)")


def _hidden_isolation_check(
    experiment_dir: Path,
    selected_runs: Sequence[Mapping[str, Any]],
    repo_root: Path,
) -> Stage11Check:
    errors: list[str] = []
    hidden_index = _hidden_case_index(repo_root / "hidden_tests" / "cases")
    for run in selected_runs:
        run_id = str(run["run_id"])
        run_dir = experiment_dir / "runs" / run_id
        worktree = run_dir / "worktree"
        if not worktree.exists():
            errors.append(f"{run_id}: missing implementation worktree")
            continue
        errors.extend(f"{run_id}: {error}" for error in _worktree_hidden_leak_errors(worktree, hidden_index))
        privacy_errors = validate_hidden_artifact_privacy(run_dir)
        errors.extend(f"{run_id}: {error}" for error in privacy_errors)

    if errors:
        return _failed("hidden_test_isolation", _join_errors(errors), {"error_count": len(errors)})
    return _passed(
        "hidden_test_isolation",
        f"validated hidden-test isolation for {len(selected_runs)} run(s)",
    )


def _judge_json_check(experiment_dir: Path, selected_runs: Sequence[Mapping[str, Any]]) -> Stage11Check:
    errors: list[str] = []
    warnings: list[str] = []
    for run in selected_runs:
        run_id = str(run["run_id"])
        judge_path = experiment_dir / "runs" / run_id / "judge.json"
        judge = _read_json(judge_path)
        if not judge:
            errors.append(f"{run_id}: missing or malformed judge.json")
            continue
        if judge.get("parsed") is not True:
            errors.append(f"{run_id}: judge.json final response did not parse as strict JSON")
            continue
        value = judge.get("value")
        if not isinstance(value, Mapping):
            errors.append(f"{run_id}: judge.json value is not an object")
        elif not _judge_has_numeric_score(value):
            warnings.append(f"{run_id}: judge.json has no recognized numeric score field")

    if errors:
        return _failed(
            "judge_json",
            _join_errors(errors),
            {"error_count": len(errors), "warning_count": len(warnings), "warnings": warnings[:20]},
        )
    if warnings:
        return _warning("judge_json", "judge JSON parsed with scoring warnings", {"warnings": warnings[:20]})
    return _passed("judge_json", f"validated parsed judge JSON for {len(selected_runs)} run(s)")


def _resume_contract_check(
    experiment_dir: Path,
    config: Mapping[str, Any],
    selected_runs: Sequence[Mapping[str, Any]],
) -> Stage11Check:
    errors: list[str] = []
    existing_config = _read_json(experiment_dir / "resolved_config.json")
    if existing_config and _json_sha256(existing_config) != _json_sha256(config):
        errors.append("resume config drift detected")

    matrix = _read_json_any(experiment_dir / "matrix.json")
    if isinstance(matrix, list):
        existing_ids = [run.get("run_id") for run in matrix if isinstance(run, Mapping)]
        selected_ids = [run["run_id"] for run in selected_runs]
        if existing_ids != selected_ids:
            errors.append("resume matrix drift detected")
    else:
        errors.append("resume matrix is missing or malformed")

    for run in selected_runs:
        run_dir = experiment_dir / "runs" / str(run["run_id"])
        if (run_dir / "metadata.json").exists():
            errors.extend(validate_run_metadata(run_dir, run))

    if errors:
        return _failed("resume_contract", _join_errors(errors), {"error_count": len(errors)})
    return _passed("resume_contract", "resume config, matrix, and run metadata are compatible")


def _report_outputs_check(experiment_dir: Path, selected_runs: Sequence[Mapping[str, Any]]) -> Stage11Check:
    errors = validate_experiment_outputs(experiment_dir)
    aggregate = _read_json(experiment_dir / "results" / "aggregate.json")
    if aggregate:
        if aggregate.get("primary_metric") != PRIMARY_METRIC:
            errors.append(f"aggregate primary_metric expected {PRIMARY_METRIC!r}")
        if aggregate.get("total_runs") != len(selected_runs):
            errors.append(f"aggregate total_runs expected {len(selected_runs)}, got {aggregate.get('total_runs')}")
        rankings = aggregate.get("rankings")
        if not isinstance(rankings, Mapping) or "primary_by_run_group" not in rankings:
            errors.append("aggregate rankings.primary_by_run_group is missing")

    csv_path = experiment_dir / "results" / "results.csv"
    csv_rows = _csv_data_row_count(csv_path)
    if csv_rows is not None and csv_rows != len(selected_runs):
        errors.append(f"results.csv expected {len(selected_runs)} data rows, got {csv_rows}")

    sqlite_path = experiment_dir / "results" / "results.sqlite"
    sqlite_rows = _sqlite_result_count(sqlite_path)
    if sqlite_rows is not None and sqlite_rows != len(selected_runs):
        errors.append(f"results.sqlite expected {len(selected_runs)} result rows, got {sqlite_rows}")

    pdf_path = experiment_dir / "report" / "report.pdf"
    if pdf_path.exists() and not pdf_path.read_bytes().startswith(b"%PDF-"):
        errors.append(f"report PDF does not start with a PDF header: {pdf_path}")

    if errors:
        return _failed("report_outputs", _join_errors(errors), {"error_count": len(errors)})
    return _passed("report_outputs", "CSV, SQLite, aggregate JSON, HTML, and PDF outputs validate")


def _selected_runs(
    experiment_dir: Path | None,
    selected_runs: Sequence[Mapping[str, Any]] | None,
    all_runs: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if selected_runs is not None:
        return list(selected_runs)
    if experiment_dir is not None:
        matrix = _read_json_any(experiment_dir / "matrix.json")
        if isinstance(matrix, list) and all(isinstance(run, Mapping) for run in matrix):
            return list(matrix)
    return list(all_runs)


def _hidden_case_index(cases_dir: Path) -> dict[str, Any]:
    files = [path for path in cases_dir.glob("*.json") if path.is_file()]
    by_size: dict[int, set[str]] = {}
    names: set[str] = set()
    for path in files:
        names.add(path.name)
        by_size.setdefault(path.stat().st_size, set()).add(_sha256_file(path))
    return {"names": names, "hashes_by_size": by_size}


def _worktree_hidden_leak_errors(worktree: Path, hidden_index: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    hidden_names = hidden_index.get("names", set())
    hashes_by_size = hidden_index.get("hashes_by_size", {})
    for path in _iter_worktree_files(worktree):
        relative = path.relative_to(worktree)
        lower_parts = {part.lower() for part in relative.parts}
        if "hidden_tests" in lower_parts:
            errors.append(f"worktree contains hidden_tests path: {relative}")
            continue
        if path.name in hidden_names:
            errors.append(f"worktree contains hidden case filename: {relative}")
            continue
        possible_hashes = hashes_by_size.get(path.stat().st_size)
        if possible_hashes and _sha256_file(path) in possible_hashes:
            errors.append(f"worktree contains file matching hidden case contents: {relative}")
    return errors


def _iter_worktree_files(root: Path) -> Iterable[Path]:
    stack = [root]
    while stack:
        current = stack.pop()
        for child in current.iterdir():
            if child.is_dir():
                if child.name not in SKIP_WORKTREE_SCAN_DIRS:
                    stack.append(child)
            elif child.is_file():
                yield child


def _payload(
    *,
    root: Path,
    config_path: Path,
    experiment_dir: Path | None,
    all_runs: Sequence[Mapping[str, Any]],
    selected: Sequence[Mapping[str, Any]],
    checks: Sequence[Stage11Check],
) -> dict[str, Any]:
    failed = [check for check in checks if check.status == "failed"]
    warnings = [check for check in checks if check.status == "warning"]
    status = "failed" if failed else "warning" if warnings else "passed"
    return {
        "schema_version": 1,
        "stage": 11,
        "status": status,
        "repo_root": str(root),
        "config_path": str(config_path),
        "experiment_dir": str(experiment_dir) if experiment_dir is not None else None,
        "full_run_count": len(all_runs),
        "selected_run_count": len(selected),
        "checks": [check.to_dict() for check in checks],
    }


def _passed(name: str, details: str = "", data: dict[str, Any] | None = None) -> Stage11Check:
    return Stage11Check(name, "passed", details, data)


def _warning(name: str, details: str = "", data: dict[str, Any] | None = None) -> Stage11Check:
    return Stage11Check(name, "warning", details, data)


def _failed(name: str, details: str = "", data: dict[str, Any] | None = None) -> Stage11Check:
    return Stage11Check(name, "failed", details, data)


def _resolve_path(path_value: str | Path, repo_root: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return repo_root / path


def _read_json(path: Path) -> dict[str, Any]:
    value = _read_json_any(path)
    return value if isinstance(value, dict) else {}


def _read_json_any(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_names(preflight: Mapping[str, Any], status: str) -> list[str]:
    checks = preflight.get("checks")
    if not isinstance(checks, list):
        return []
    return [
        str(check.get("name"))
        for check in checks
        if isinstance(check, Mapping) and check.get("status") == status
    ]


def _judge_has_numeric_score(value: Mapping[str, Any]) -> bool:
    if isinstance(value.get("overall_score"), (int, float)) and not isinstance(value.get("overall_score"), bool):
        return True
    for key in ("correctness_score", "parity_score", "maintainability_score", "test_evidence_score"):
        if isinstance(value.get(key), (int, float)) and not isinstance(value.get(key), bool):
            return True
    return False


def _csv_data_row_count(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return sum(1 for _ in csv.DictReader(handle))
    except OSError:
        return None


def _sqlite_result_count(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        connection = sqlite3.connect(path)
        try:
            row = connection.execute("SELECT COUNT(*) FROM results").fetchone()
            return int(row[0]) if row else None
        finally:
            connection.close()
    except sqlite3.Error:
        return None


def _join_errors(errors: Sequence[str]) -> str:
    if len(errors) <= 5:
        return "; ".join(errors)
    shown = "; ".join(errors[:5])
    return f"{shown}; ... {len(errors) - 5} more"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the Stage 11 benchmark acceptance contract.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Repository root. Defaults to this checkout.")
    parser.add_argument("--config", default="configs/initial_experiment.yaml", help="Experiment config path.")
    parser.add_argument("--experiment-dir", help="Optional experiment directory to validate.")
    parser.add_argument("--require-codex", action="store_true", help="Fail preflight when Codex is unavailable.")
    parser.add_argument("--skip-preflight", action="store_true", help="Do not run or load preflight validation.")
    parser.add_argument(
        "--allow-missing-report",
        action="store_true",
        help="Do not require CSV, SQLite, HTML, and PDF report outputs.",
    )
    parser.add_argument("--output", help="Optional path to write validation JSON.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
