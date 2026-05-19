from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


PUBLIC_COMMANDS = {
    "typecheck": "typecheck.meta.json",
    "public_ts": "public_ts.meta.json",
    "public_py": "public_py.meta.json",
}


def compute_run_score(run_dir: str | Path, run: Mapping[str, Any]) -> dict[str, Any]:
    run_path = Path(run_dir)
    weights = _weights(run)
    typecheck_score = _command_score(run_path / PUBLIC_COMMANDS["typecheck"])
    public_ts_score = _command_score(run_path / PUBLIC_COMMANDS["public_ts"])
    public_py_score = _command_score(run_path / PUBLIC_COMMANDS["public_py"])
    public_test_score = (public_ts_score + public_py_score) / 2.0
    hidden_score = _hidden_score(run_path / "hidden-results.json")
    parity_score = _hidden_category_score(run_path / "hidden-results.json", "parity")
    judge_score = _judge_score(run_path / "judge.json")
    usage = _read_json(run_path / "usage.json")
    diff_stats = _diff_stats(run_path / "diff-numstat.txt")
    wall_time = _wall_time(run_path)

    component_scores = {
        "public_tests": round(public_test_score, 6),
        "hidden_tests": round(hidden_score, 6),
        "judge": round(judge_score, 6),
        "typecheck": round(typecheck_score, 6),
        "parity": round(parity_score, 6),
    }

    quality_score = 0.0
    for name, weight in weights.items():
        quality_score += component_scores.get(name, 0.0) * float(weight)
    quality_score = round(quality_score, 6)

    totals = usage.get("totals", {}) if isinstance(usage, Mapping) else {}
    implementation_tokens = _safe_int(totals.get("implementation_tokens"))
    gpt55_impl_tokens = _safe_int(totals.get("gpt55_implementation_tokens"))
    gpt55_judge_inclusive_tokens = _safe_int(totals.get("gpt55_judge_inclusive_tokens"))
    wall_minutes = max(wall_time.get("implementation_elapsed_seconds", 0.0) / 60.0, 0.0)

    return {
        "schema_version": 1,
        "run_id": run.get("run_id"),
        "cell_id": run.get("cell_id"),
        "spark_mode": run.get("spark_mode"),
        "component_scores": component_scores,
        "weights": weights,
        "quality_score": quality_score,
        "efficiency": {
            "quality_per_gpt55_impl_token": _ratio(quality_score, gpt55_impl_tokens),
            "quality_per_judge_inclusive_gpt55_token": _ratio(quality_score, gpt55_judge_inclusive_tokens),
            "quality_per_total_impl_token": _ratio(quality_score, implementation_tokens),
            "quality_per_wall_clock_minute": _ratio(quality_score, wall_minutes),
        },
        "diff_stats": diff_stats,
        "wall_time": wall_time,
        "status": _status(run_path, component_scores),
    }


def write_run_score(path: str | Path, payload: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _weights(run: Mapping[str, Any]) -> dict[str, float]:
    raw = run.get("scoring_weights", {})
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): float(value) for key, value in raw.items()}


def _command_score(path: Path) -> float:
    payload = _read_json(path)
    if not payload:
        return 0.0
    return 1.0 if payload.get("returncode") == 0 and not payload.get("timed_out") else 0.0


def _hidden_score(path: Path) -> float:
    payload = _read_json(path)
    summary = payload.get("summary", {}) if isinstance(payload, Mapping) else {}
    return _safe_float(summary.get("score", summary.get("point_score", 0.0)))


def _hidden_category_score(path: Path, category: str) -> float:
    payload = _read_json(path)
    categories = payload.get("categories", {}) if isinstance(payload, Mapping) else {}
    bucket = categories.get(category, {}) if isinstance(categories, Mapping) else {}
    return _safe_float(bucket.get("score", 0.0)) if isinstance(bucket, Mapping) else 0.0


def _judge_score(path: Path) -> float:
    payload = _read_json(path)
    value = payload.get("value", payload) if isinstance(payload, Mapping) else {}
    if not isinstance(value, Mapping):
        return 0.0

    if isinstance(value.get("overall_score"), (int, float)):
        return _safe_float(value["overall_score"])

    keys = ["correctness_score", "parity_score", "maintainability_score", "test_evidence_score"]
    scores = [_safe_float(value.get(key)) for key in keys if isinstance(value.get(key), (int, float))]
    return sum(scores) / len(scores) if scores else 0.0


def _diff_stats(path: Path) -> dict[str, Any]:
    stats = {
        "changed_files": 0,
        "insertions": 0,
        "deletions": 0,
        "binary_files": 0,
    }
    if not path.exists():
        return stats

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        stats["changed_files"] += 1
        if parts[0] == "-" or parts[1] == "-":
            stats["binary_files"] += 1
            continue
        stats["insertions"] += _safe_int(parts[0])
        stats["deletions"] += _safe_int(parts[1])
    return stats


def _wall_time(run_path: Path) -> dict[str, float]:
    implementation = _read_json(run_path / "wall_time.json")
    judge = _read_json(run_path / "judge.wall_time.json")
    return {
        "implementation_elapsed_seconds": _safe_float(implementation.get("elapsed_seconds", 0.0)),
        "judge_elapsed_seconds": _safe_float(judge.get("elapsed_seconds", 0.0)),
    }


def _status(run_path: Path, component_scores: Mapping[str, float]) -> str:
    state = _read_json(run_path / "state.json")
    phases = state.get("phases", {}) if isinstance(state, Mapping) else {}
    if isinstance(phases, Mapping):
        failed = [
            name
            for name, phase in phases.items()
            if isinstance(phase, Mapping) and phase.get("status") == "failed"
        ]
        if failed:
            return "partial"
    if all(value >= 1.0 for value in component_scores.values()):
        return "passed"
    return "partial"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _safe_float(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _ratio(numerator: float, denominator: int | float | None) -> float | None:
    if denominator is None or denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 12)
