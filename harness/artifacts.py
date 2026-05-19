from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping


PHASE_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "prepared": ("worktree",),
    "baseline_committed": ("metadata.json",),
    "rendered": ("rendered_prompt.md", "judge_prompt.md", "codex_config/config.toml"),
    "implemented": ("events.jsonl", "stderr.log", "wall_time.json", "final_response.json"),
    "diff_captured": ("diff.patch", "diff-numstat.txt"),
    "public_tested": (
        "typecheck.log",
        "typecheck.meta.json",
        "public_ts.log",
        "public_ts.meta.json",
        "public_py.log",
        "public_py.meta.json",
    ),
    "hidden_tested": ("hidden-results.json", "hidden-runner.log", "hidden-runner.meta.json"),
    "judged": ("judge.events.jsonl", "judge.stderr.log", "judge.wall_time.json", "judge.json"),
    "usage_parsed": ("usage.json",),
    "scored": ("score.json",),
}

CODEX_IMPLEMENTATION_ARTIFACTS = PHASE_ARTIFACTS["implemented"]
CODEX_JUDGE_ARTIFACTS = PHASE_ARTIFACTS["judged"]

CORE_RUN_ARTIFACTS: tuple[str, ...] = (
    "metadata.json",
    "state.json",
    "rendered_prompt.md",
    "judge_prompt.md",
    "codex_config/config.toml",
    "events.jsonl",
    "stderr.log",
    "final_response.json",
    "wall_time.json",
    "diff.patch",
    "diff-numstat.txt",
    "typecheck.log",
    "typecheck.meta.json",
    "public_ts.log",
    "public_ts.meta.json",
    "public_py.log",
    "public_py.meta.json",
    "hidden-runner.log",
    "hidden-runner.meta.json",
    "hidden-results.json",
    "judge.events.jsonl",
    "judge.stderr.log",
    "judge.wall_time.json",
    "judge.json",
    "usage.json",
    "score.json",
)

OPTIONAL_RUN_ARTIFACTS: tuple[str, ...] = ("npm-ci.log", "npm-ci.meta.json")

EXPERIMENT_OUTPUT_ARTIFACTS: tuple[str, ...] = (
    "results/results.csv",
    "results/results.sqlite",
    "results/aggregate.json",
    "report/report.html",
    "report/report.pdf",
)

EXPERIMENT_METADATA_ARTIFACTS: tuple[str, ...] = (
    "experiment_metadata.json",
    "experiment-metadata.json",
    "resolved_config.json",
    "config.resolved.json",
    "matrix.json",
    "matrix-summary.json",
    "preflight.json",
    "orchestrator.log",
    "status.json",
)

JSON_WITH_SCHEMA_VERSION = {
    "metadata.json",
    "state.json",
    "hidden-results.json",
    "usage.json",
    "score.json",
    "experiment_metadata.json",
    "experiment-metadata.json",
    "preflight.json",
    "status.json",
}

PROCESS_METADATA_FIELDS = {
    "command",
    "command_display",
    "cwd",
    "started_at",
    "finished_at",
    "elapsed_seconds",
    "returncode",
    "timed_out",
}

FORBIDDEN_HIDDEN_RESULT_KEYS = {
    "input",
    "expected",
    "expected_output",
    "expected_outputs",
    "raw_event",
    "raw_events",
    "rawEvent",
    "rawEvents",
}

FORBIDDEN_HIDDEN_LOG_MARKERS = (
    '"input"',
    '"expected"',
    "raw_events",
    "raw_event",
    "expected_output",
)


def artifact_paths(run_dir: str | Path, names: Iterable[str]) -> list[Path]:
    root = Path(run_dir)
    return [root / name for name in names]


def phase_artifact_paths(run_dir: str | Path, phase: str) -> list[Path]:
    return artifact_paths(run_dir, PHASE_ARTIFACTS.get(phase, ()))


def validate_phase_artifacts(run_dir: str | Path, phase: str) -> list[str]:
    names = PHASE_ARTIFACTS.get(phase)
    if names is None:
        return []
    errors = validate_artifacts(Path(run_dir), names)
    if phase == "hidden_tested":
        errors.extend(validate_hidden_artifact_privacy(run_dir))
    return errors


def validate_artifacts(root: str | Path, names: Iterable[str]) -> list[str]:
    errors: list[str] = []
    base = Path(root)
    for name in names:
        errors.extend(validate_artifact(base / name))
    return errors


def validate_artifact(path: str | Path) -> list[str]:
    artifact = Path(path)
    if not artifact.exists():
        return [f"missing artifact: {artifact}"]
    if artifact.name in {"worktree", "codex_config"}:
        return [] if artifact.is_dir() else [f"expected directory artifact: {artifact}"]
    if artifact.is_dir():
        return []
    if artifact.suffix == ".json":
        return _validate_json_artifact(artifact)
    if artifact.suffix == ".jsonl":
        return _validate_jsonl_artifact(artifact)
    try:
        artifact.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [f"unreadable artifact {artifact}: {exc}"]
    return []


def run_metadata_matches(run_dir: str | Path, run: Mapping[str, Any]) -> bool:
    metadata = read_json(Path(run_dir) / "metadata.json")
    if not isinstance(metadata, Mapping):
        return False
    return metadata.get("run_id") == run.get("run_id") and metadata.get("run") == run


def validate_run_metadata(run_dir: str | Path, run: Mapping[str, Any]) -> list[str]:
    metadata_path = Path(run_dir) / "metadata.json"
    errors = validate_artifact(metadata_path)
    if errors:
        return errors
    if not run_metadata_matches(run_dir, run):
        return [f"metadata does not match resolved run record: {metadata_path}"]
    return []


def validate_experiment_outputs(experiment_dir: str | Path) -> list[str]:
    return validate_artifacts(experiment_dir, EXPERIMENT_OUTPUT_ARTIFACTS)


def validate_hidden_artifact_privacy(run_dir: str | Path) -> list[str]:
    root = Path(run_dir)
    errors: list[str] = []
    hidden_results = root / "hidden-results.json"
    payload = read_json(hidden_results)
    if payload:
        errors.extend(_find_forbidden_hidden_keys(payload))
    elif hidden_results.exists():
        errors.append(f"hidden result JSON is not parseable: {hidden_results}")

    log_path = root / "hidden-runner.log"
    if log_path.exists():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        for marker in FORBIDDEN_HIDDEN_LOG_MARKERS:
            if marker in text:
                errors.append(f"hidden runner log contains private marker {marker!r}: {log_path}")
    return errors


def read_json(path: str | Path) -> Any:
    artifact = Path(path)
    if not artifact.exists():
        return None
    try:
        return json.loads(artifact.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _validate_json_artifact(path: Path) -> list[str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid JSON artifact {path}: {exc.msg}"]
    except OSError as exc:
        return [f"unreadable JSON artifact {path}: {exc}"]

    errors: list[str] = []
    if path.name in JSON_WITH_SCHEMA_VERSION:
        if not isinstance(value, Mapping) or value.get("schema_version") is None:
            errors.append(f"JSON artifact is missing schema_version: {path}")
    if path.name.endswith(".meta.json") or path.name in {"wall_time.json", "judge.wall_time.json"}:
        if not isinstance(value, Mapping):
            errors.append(f"process metadata artifact is not an object: {path}")
        else:
            missing = sorted(PROCESS_METADATA_FIELDS - set(value))
            if missing:
                errors.append(f"process metadata artifact missing fields {missing}: {path}")
            if "log_path" not in value and "stdout_path" not in value:
                errors.append(f"process metadata artifact missing output path: {path}")
    return errors


def _validate_jsonl_artifact(path: Path) -> list[str]:
    try:
        path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [f"unreadable JSONL artifact {path}: {exc}"]
    return []


def _find_forbidden_hidden_keys(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if key_text in FORBIDDEN_HIDDEN_RESULT_KEYS:
                errors.append(f"hidden result contains private key {child_path}")
            errors.extend(_find_forbidden_hidden_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_find_forbidden_hidden_keys(child, f"{path}[{index}]"))
    return errors
