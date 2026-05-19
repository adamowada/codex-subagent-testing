from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


KNOWN_COMPONENTS = {"public_tests", "hidden_tests", "judge", "typecheck", "parity", "minimality"}
DEFAULT_MINIMALITY_TARGET_PRODUCTION_LOC = 500
DEFAULT_MINIMALITY_PENALTY_WINDOW = 1000

PUBLIC_COMMANDS = {
    "typecheck": "typecheck.meta.json",
    "public_ts": "public_ts.meta.json",
    "public_py": "public_py.meta.json",
}


def compute_run_score(run_dir: str | Path, run: Mapping[str, Any]) -> dict[str, Any]:
    run_path = Path(run_dir)
    warnings: list[str] = []
    weights = _weights(run, warnings)
    typecheck_score = _command_score(
        _read_json(run_path / PUBLIC_COMMANDS["typecheck"], warnings, "typecheck metadata"),
        "typecheck",
        warnings,
    )
    public_ts_score = _command_score(
        _read_json(run_path / PUBLIC_COMMANDS["public_ts"], warnings, "public TypeScript metadata"),
        "public TypeScript tests",
        warnings,
    )
    public_py_score = _command_score(
        _read_json(run_path / PUBLIC_COMMANDS["public_py"], warnings, "public Python metadata"),
        "public Python tests",
        warnings,
    )
    public_test_score = (public_ts_score + public_py_score) / 2.0
    hidden_results = _read_json(run_path / "hidden-results.json", warnings, "hidden results")
    hidden_score = _hidden_score(hidden_results, warnings)
    parity_score = _hidden_category_score(hidden_results, "parity")
    judge_score = _judge_score(_read_json(run_path / "judge.json", warnings, "judge output"), warnings)
    usage = _read_json(run_path / "usage.json", warnings, "usage summary")
    diff_stats = _diff_stats(run_path / "diff-numstat.txt", warnings)
    wall_time = _wall_time(run_path, warnings)

    component_scores = {
        "public_tests": round(public_test_score, 6),
        "hidden_tests": round(hidden_score, 6),
        "judge": round(judge_score, 6),
        "typecheck": round(typecheck_score, 6),
        "parity": round(parity_score, 6),
    }
    if "minimality" in weights:
        component_scores["minimality"] = round(_minimality_score(diff_stats, run, warnings), 6)

    quality_score = 0.0
    for name, weight in weights.items():
        if name not in KNOWN_COMPONENTS:
            warnings.append(f"unknown scoring component {name!r}; contribution treated as 0.0")
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
        "status": _status(run_path, component_scores, weights, warnings),
        "warnings": warnings,
    }


def write_run_score(path: str | Path, payload: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _weights(run: Mapping[str, Any], warnings: list[str]) -> dict[str, float]:
    raw = run.get("scoring_weights", {})
    if not isinstance(raw, Mapping):
        warnings.append("run scoring_weights is missing or not an object; quality_score will be 0.0")
        return {}
    weights: dict[str, float] = {}
    for key, value in raw.items():
        name = str(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            warnings.append(f"scoring weight {name!r} is not numeric; contribution skipped")
            continue
        if value < 0:
            warnings.append(f"scoring weight {name!r} is negative; contribution skipped")
            continue
        weights[name] = float(value)
    total = sum(weights.values())
    if weights and abs(total - 1.0) > 0.000001:
        warnings.append(f"scoring weights sum to {total:.6f}, expected 1.0")
    return weights


def _command_score(payload: Mapping[str, Any], label: str, warnings: list[str]) -> float:
    if not payload:
        return 0.0
    if "returncode" not in payload:
        warnings.append(f"{label} metadata is missing returncode")
    return 1.0 if payload.get("returncode") == 0 and not payload.get("timed_out") else 0.0


def _hidden_score(payload: Mapping[str, Any], warnings: list[str]) -> float:
    summary = payload.get("summary", {}) if isinstance(payload, Mapping) else {}
    if payload and not isinstance(summary, Mapping):
        warnings.append("hidden results summary is not an object")
        return 0.0
    return _normalized_score(summary.get("score", summary.get("point_score", 0.0)))


def _hidden_category_score(payload: Mapping[str, Any], category: str) -> float:
    categories = payload.get("categories", {}) if isinstance(payload, Mapping) else {}
    bucket = categories.get(category, {}) if isinstance(categories, Mapping) else {}
    return _normalized_score(bucket.get("score", 0.0)) if isinstance(bucket, Mapping) else 0.0


def _judge_score(payload: Mapping[str, Any], warnings: list[str]) -> float:
    value = payload.get("value", payload) if isinstance(payload, Mapping) else {}
    if not isinstance(value, Mapping):
        if payload:
            warnings.append("judge output value is not an object")
        return 0.0
    if payload.get("parsed") is False:
        warnings.append("judge output was not parsed as strict JSON")
        return 0.0

    if isinstance(value.get("overall_score"), (int, float)):
        return _normalized_score(value["overall_score"])

    keys = ["correctness_score", "parity_score", "maintainability_score", "test_evidence_score"]
    scores = [_normalized_score(value.get(key)) for key in keys if isinstance(value.get(key), (int, float))]
    if payload and not scores:
        warnings.append("judge output does not contain numeric score fields")
    return sum(scores) / len(scores) if scores else 0.0


def _diff_stats(path: Path, warnings: list[str]) -> dict[str, Any]:
    stats = {
        "changed_files": 0,
        "insertions": 0,
        "deletions": 0,
        "binary_files": 0,
        "production_loc": 0,
        "test_loc": 0,
        "unclassified_loc": 0,
        "unclassified_files": 0,
    }
    if not path.exists():
        warnings.append(f"missing artifact: {path.name}")
        return stats

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            warnings.append(f"diff numstat skipped malformed line: {line[:120]}")
            continue
        stats["changed_files"] += 1
        if parts[0] == "-" or parts[1] == "-":
            stats["binary_files"] += 1
            continue
        insertions = _safe_int(parts[0])
        stats["insertions"] += insertions
        stats["deletions"] += _safe_int(parts[1])
        diff_path = _numstat_path(parts[2:])
        category = _classify_diff_path(diff_path)
        if category == "production":
            stats["production_loc"] += insertions
        elif category == "test":
            stats["test_loc"] += insertions
        elif category == "excluded":
            continue
        else:
            stats["unclassified_loc"] += insertions
            stats["unclassified_files"] += 1
            warnings.append(f"diff path {diff_path!r} was not classified as production or test LOC")
    return stats


def _wall_time(run_path: Path, warnings: list[str]) -> dict[str, float]:
    implementation = _read_json(run_path / "wall_time.json", warnings, "implementation wall time")
    judge = _read_json(run_path / "judge.wall_time.json", warnings, "judge wall time")
    return {
        "implementation_elapsed_seconds": _safe_float(implementation.get("elapsed_seconds", 0.0)),
        "judge_elapsed_seconds": _safe_float(judge.get("elapsed_seconds", 0.0)),
    }


def _status(
    run_path: Path,
    component_scores: Mapping[str, float],
    weights: Mapping[str, float],
    warnings: list[str],
) -> str:
    state = _read_json(run_path / "state.json", warnings, "run state")
    phases = state.get("phases", {}) if isinstance(state, Mapping) else {}
    if isinstance(phases, Mapping):
        failed = [
            name
            for name, phase in phases.items()
            if isinstance(phase, Mapping) and phase.get("status") == "failed"
        ]
        if any(name in {"prepared", "baseline_committed", "rendered"} for name in failed):
            return "failed"
        if failed:
            return "partial"
    weighted_components = [name for name in weights if name in KNOWN_COMPONENTS]
    if weighted_components and all(component_scores.get(name, 0.0) >= 1.0 for name in weighted_components):
        return "passed"
    return "partial"


def _read_json(path: Path, warnings: list[str] | None = None, label: str | None = None) -> dict[str, Any]:
    if not path.exists():
        if warnings is not None:
            warnings.append(f"missing artifact: {path.name}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        if warnings is not None:
            warnings.append(f"malformed JSON artifact: {path.name}")
        return {}
    if not isinstance(value, dict):
        if warnings is not None:
            warnings.append(f"{label or path.name} JSON artifact is not an object")
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


def _normalized_score(value: Any) -> float:
    return max(0.0, min(_safe_float(value), 1.0))


def _ratio(numerator: float, denominator: int | float | None) -> float | None:
    if denominator is None or denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 12)


def _numstat_path(parts: list[str]) -> str:
    text = "\t".join(parts).strip()
    if " => " in text:
        return text.split(" => ", 1)[1].strip("{}")
    return text


def _classify_diff_path(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    lowered = normalized.lower()
    parts = [part for part in lowered.split("/") if part]
    filename = parts[-1] if parts else lowered

    excluded_dirs = {
        "node_modules",
        "dist",
        "build",
        "coverage",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        "runs",
    }
    if any(part in excluded_dirs for part in parts):
        return "excluded"
    if filename in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "uv.lock"}:
        return "excluded"
    if any(part in {"tests", "test", "__tests__", "tests_public_py", "tests_public_ts"} for part in parts):
        return "test"
    if filename.endswith(
        (".test.ts", ".test.tsx", ".test.js", ".test.jsx", ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx")
    ):
        return "test"
    if filename.startswith("test_") and filename.endswith(".py"):
        return "test"
    if filename.endswith("_test.py"):
        return "test"
    if any(part in {"src", "lib", "ruleledger"} for part in parts) and filename.endswith(
        (".py", ".ts", ".tsx", ".js", ".jsx")
    ):
        return "production"
    if len(parts) == 1 and filename.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
        return "production"
    return None


def _minimality_score(diff_stats: Mapping[str, Any], run: Mapping[str, Any], warnings: list[str]) -> float:
    config = run.get("scoring_minimality", {})
    if not isinstance(config, Mapping):
        warnings.append("scoring_minimality is not an object; using default minimality settings")
        config = {}
    target = _positive_float(config.get("target_production_loc"), DEFAULT_MINIMALITY_TARGET_PRODUCTION_LOC)
    penalty_window = _positive_float(config.get("penalty_window"), DEFAULT_MINIMALITY_PENALTY_WINDOW)
    production_loc = _safe_float(diff_stats.get("production_loc"))
    excess = max(0.0, production_loc - target)
    return round(max(0.0, min(1.0, 1.0 - (excess / penalty_window))), 6)


def _positive_float(value: Any, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value) if value > 0 else default
