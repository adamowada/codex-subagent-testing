from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any, Callable, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ORIGINAL_DIR = REPO_ROOT / "runs" / "20260629T224027-gpt55_direct_quality_frontier-gpt55_frontier_j7_j6"
DEFAULT_EXTENSION_DIR = (
    REPO_ROOT
    / "runs"
    / "20260630T061938-gpt55_direct_quality_frontier_50-gpt55_frontier_50_r21_r50_j7_j6"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "analysis" / "gpt55_direct_quality_frontier_50"
CELL_LABELS = {
    "GQF0": "high root + high leaves",
    "GQF1": "xhigh root + high leaves",
    "GQF2": "high root + xhigh leaves",
    "GQF3": "xhigh root + xhigh leaves",
}
NUMERIC_FIELDS = (
    "quality_score",
    "hidden_tests",
    "hidden_correctness",
    "hidden_parity",
    "performance",
    "judge",
    "minimality",
    "implementation_tokens",
    "gpt55_implementation_tokens",
    "root_implementation_tokens",
    "leaf_implementation_tokens",
    "judge_tokens",
    "gpt55_judge_inclusive_tokens",
    "quality_per_gpt55_impl_token",
    "quality_per_judge_inclusive_gpt55_token",
    "quality_per_wall_clock_minute",
    "implementation_elapsed_seconds",
    "production_loc",
    "test_loc",
    "changed_files",
)
SUMMARY_FIELDS = (
    "quality_score",
    "hidden_correctness",
    "hidden_tests",
    "performance",
    "judge",
    "minimality",
    "gpt55_implementation_tokens",
    "root_implementation_tokens",
    "leaf_implementation_tokens",
    "judge_tokens",
    "quality_per_gpt55_impl_token",
    "implementation_elapsed_seconds",
    "production_loc",
    "test_loc",
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    original_dir = _resolve_path(args.original_dir)
    extension_dir = _resolve_path(args.extension_dir)
    output_dir = _resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    rows.extend(read_results(original_dir, cohort="original_20"))
    rows.extend(read_results(extension_dir, cohort="extension_30"))
    summary = build_summary(rows, bootstrap_iterations=args.bootstrap_iterations, seed=args.seed)

    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_cell_summary_csv(output_dir / "cell_summary.csv", summary["pooled_cells"])
    (output_dir / "summary.md").write_text(render_markdown(summary), encoding="utf-8")

    print(f"Wrote GPT-5.5 frontier 50-run analysis to {output_dir}")
    print(f"Rows analyzed: {summary['row_count']}")
    print(f"Validation status: {summary['validation']['status']}")
    return 0 if summary["validation"]["status"] == "passed" else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze the pooled GPT-5.5 direct quality frontier runs.")
    parser.add_argument("--original-dir", default=str(DEFAULT_ORIGINAL_DIR))
    parser.add_argument("--extension-dir", default=str(DEFAULT_EXTENSION_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=1729)
    return parser.parse_args(argv)


def read_results(experiment_dir: Path, *, cohort: str) -> list[dict[str, Any]]:
    path = experiment_dir / "results" / "results.csv"
    if not path.exists():
        raise FileNotFoundError(f"missing results CSV: {path}")
    rows = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            normalized = dict(row)
            normalized["experiment_dir"] = str(experiment_dir)
            normalized["cohort"] = cohort
            normalized["cell_label"] = CELL_LABELS.get(str(row.get("cell_id")), str(row.get("cell_id")))
            for field in NUMERIC_FIELDS:
                normalized[field] = _float_or_none(normalized.get(field))
            rows.append(normalized)
    return rows


def build_summary(rows: list[dict[str, Any]], *, bootstrap_iterations: int, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    validation = validate_rows(rows)
    pooled_cells = summarize_cells(rows, bootstrap_iterations=bootstrap_iterations, rng=rng)
    cohort_cells = summarize_cohort_cells(rows)
    pairwise = pairwise_deltas(rows, bootstrap_iterations=bootstrap_iterations, rng=rng)
    factorial = factorial_effects(rows, bootstrap_iterations=bootstrap_iterations, rng=rng)
    top_runs = sorted(
        (
            {
                "run_id": row["run_id"],
                "cell_id": row["cell_id"],
                "cell_label": row["cell_label"],
                "quality_score": row["quality_score"],
                "hidden_correctness": row["hidden_correctness"],
                "gpt55_implementation_tokens": row["gpt55_implementation_tokens"],
            }
            for row in rows
        ),
        key=lambda item: float(item["quality_score"] or 0.0),
        reverse=True,
    )[:10]
    return {
        "schema_version": 1,
        "row_count": len(rows),
        "bootstrap_iterations": bootstrap_iterations,
        "bootstrap_seed": seed,
        "validation": validation,
        "pooled_cells": pooled_cells,
        "cohort_cells": cohort_cells,
        "pairwise_quality_deltas": pairwise,
        "factorial_quality_effects": factorial,
        "top_quality_runs": top_runs,
        "sources": sorted({str(row["experiment_dir"]) for row in rows}),
    }


def validate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    by_cell = Counter(str(row.get("cell_id")) for row in rows)
    by_cohort_cell = Counter((str(row.get("cohort")), str(row.get("cell_id"))) for row in rows)
    duplicate_ids = sorted(run_id for run_id, count in Counter(str(row.get("run_id")) for row in rows).items() if count > 1)
    if duplicate_ids:
        errors.append(f"duplicate run ids: {', '.join(duplicate_ids[:10])}")
    for cell_id in CELL_LABELS:
        if by_cell[cell_id] != 50:
            errors.append(f"{cell_id}: expected 50 pooled rows, found {by_cell[cell_id]}")
        if by_cohort_cell[("original_20", cell_id)] != 20:
            errors.append(f"{cell_id}: expected 20 original rows, found {by_cohort_cell[('original_20', cell_id)]}")
        if by_cohort_cell[("extension_30", cell_id)] != 30:
            errors.append(f"{cell_id}: expected 30 extension rows, found {by_cohort_cell[('extension_30', cell_id)]}")
    for row in rows:
        if row.get("artifact_status") != "complete":
            errors.append(f"{row.get('run_id')}: artifact_status={row.get('artifact_status')}")
        if row.get("failure_phase"):
            errors.append(f"{row.get('run_id')}: failure_phase={row.get('failure_phase')}")
        if row.get("usage_warnings"):
            warnings.append(f"{row.get('run_id')}: usage_warnings={row.get('usage_warnings')}")
        if _as_float(row.get("quality_score")) <= 0:
            errors.append(f"{row.get('run_id')}: non-positive quality_score={row.get('quality_score')}")
    return {
        "status": "failed" if errors else "warning" if warnings else "passed",
        "errors": errors,
        "warnings": warnings,
        "by_cell": dict(sorted(by_cell.items())),
        "by_cohort_cell": {f"{cohort}:{cell}": count for (cohort, cell), count in sorted(by_cohort_cell.items())},
    }


def summarize_cells(
    rows: list[dict[str, Any]],
    *,
    bootstrap_iterations: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_cell[str(row["cell_id"])].append(row)
    return [
        summarize_group(cell_rows, bootstrap_iterations=bootstrap_iterations, rng=rng)
        for _cell_id, cell_rows in sorted(by_cell.items())
    ]


def summarize_cohort_cells(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["cohort"]), str(row["cell_id"]))].append(row)
    return [
        summarize_group(group_rows, bootstrap_iterations=0, rng=random.Random(0))
        | {"cohort": cohort}
        for (cohort, _cell_id), group_rows in sorted(groups.items())
    ]


def summarize_group(
    rows: list[dict[str, Any]],
    *,
    bootstrap_iterations: int,
    rng: random.Random,
) -> dict[str, Any]:
    first = rows[0]
    quality_values = _numbers(rows, "quality_score")
    summary: dict[str, Any] = {
        "cell_id": first["cell_id"],
        "cell_label": first["cell_label"],
        "root_reasoning": first["root_reasoning"],
        "leaf_reasoning": first["leaf_reasoning"],
        "runs": len(rows),
        "status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in rows).items())),
        "quality": _stats(quality_values),
        "quality_top_quartile_mean": round(mean(sorted(quality_values, reverse=True)[: max(1, len(quality_values) // 4)]), 6),
        "quality_bottom_quartile_mean": round(mean(sorted(quality_values)[: max(1, len(quality_values) // 4)]), 6),
    }
    if bootstrap_iterations:
        summary["quality_bootstrap_ci95"] = _bootstrap_mean_ci(quality_values, bootstrap_iterations, rng)
    for field in SUMMARY_FIELDS:
        summary[field] = _stats(_numbers(rows, field))
    return summary


def pairwise_deltas(
    rows: list[dict[str, Any]],
    *,
    bootstrap_iterations: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_cell[str(row["cell_id"])].append(row)
    comparisons = []
    cell_ids = sorted(CELL_LABELS)
    for left_index, left in enumerate(cell_ids):
        for right in cell_ids[left_index + 1 :]:
            left_values = _numbers(by_cell[left], "quality_score")
            right_values = _numbers(by_cell[right], "quality_score")
            deltas = _bootstrap_delta_values(left_values, right_values, bootstrap_iterations, rng)
            comparisons.append(
                {
                    "left_cell": left,
                    "left_label": CELL_LABELS[left],
                    "right_cell": right,
                    "right_label": CELL_LABELS[right],
                    "delta_left_minus_right": round(mean(left_values) - mean(right_values), 6),
                    "bootstrap_ci95": _percentile_interval(deltas),
                    "probability_left_greater": round(sum(1 for delta in deltas if delta > 0) / len(deltas), 4),
                }
            )
    return comparisons


def factorial_effects(
    rows: list[dict[str, Any]],
    *,
    bootstrap_iterations: int,
    rng: random.Random,
) -> dict[str, Any]:
    groups = {
        "root_xhigh": [row for row in rows if row["root_reasoning"] == "xhigh"],
        "root_high": [row for row in rows if row["root_reasoning"] == "high"],
        "leaf_xhigh": [row for row in rows if row["leaf_reasoning"] == "xhigh"],
        "leaf_high": [row for row in rows if row["leaf_reasoning"] == "high"],
        "matched_xhigh_root_effect_high_leaves": [
            row for row in rows if row["cell_id"] in {"GQF0", "GQF1"}
        ],
        "matched_xhigh_root_effect_xhigh_leaves": [
            row for row in rows if row["cell_id"] in {"GQF2", "GQF3"}
        ],
        "matched_xhigh_leaf_effect_high_root": [
            row for row in rows if row["cell_id"] in {"GQF0", "GQF2"}
        ],
        "matched_xhigh_leaf_effect_xhigh_root": [
            row for row in rows if row["cell_id"] in {"GQF1", "GQF3"}
        ],
    }

    return {
        "root_xhigh_minus_high": _effect(
            groups["root_xhigh"],
            groups["root_high"],
            bootstrap_iterations=bootstrap_iterations,
            rng=rng,
        ),
        "leaf_xhigh_minus_high": _effect(
            groups["leaf_xhigh"],
            groups["leaf_high"],
            bootstrap_iterations=bootstrap_iterations,
            rng=rng,
        ),
        "xhigh_root_minus_high_root_with_high_leaves": _effect(
            [row for row in groups["matched_xhigh_root_effect_high_leaves"] if row["cell_id"] == "GQF1"],
            [row for row in groups["matched_xhigh_root_effect_high_leaves"] if row["cell_id"] == "GQF0"],
            bootstrap_iterations=bootstrap_iterations,
            rng=rng,
        ),
        "xhigh_root_minus_high_root_with_xhigh_leaves": _effect(
            [row for row in groups["matched_xhigh_root_effect_xhigh_leaves"] if row["cell_id"] == "GQF3"],
            [row for row in groups["matched_xhigh_root_effect_xhigh_leaves"] if row["cell_id"] == "GQF2"],
            bootstrap_iterations=bootstrap_iterations,
            rng=rng,
        ),
        "xhigh_leaves_minus_high_leaves_with_high_root": _effect(
            [row for row in groups["matched_xhigh_leaf_effect_high_root"] if row["cell_id"] == "GQF2"],
            [row for row in groups["matched_xhigh_leaf_effect_high_root"] if row["cell_id"] == "GQF0"],
            bootstrap_iterations=bootstrap_iterations,
            rng=rng,
        ),
        "xhigh_leaves_minus_high_leaves_with_xhigh_root": _effect(
            [row for row in groups["matched_xhigh_leaf_effect_xhigh_root"] if row["cell_id"] == "GQF3"],
            [row for row in groups["matched_xhigh_leaf_effect_xhigh_root"] if row["cell_id"] == "GQF1"],
            bootstrap_iterations=bootstrap_iterations,
            rng=rng,
        ),
    }


def _effect(
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
    *,
    bootstrap_iterations: int,
    rng: random.Random,
) -> dict[str, Any]:
    left = _numbers(left_rows, "quality_score")
    right = _numbers(right_rows, "quality_score")
    deltas = _bootstrap_delta_values(left, right, bootstrap_iterations, rng)
    return {
        "delta": round(mean(left) - mean(right), 6),
        "bootstrap_ci95": _percentile_interval(deltas),
        "probability_positive": round(sum(1 for delta in deltas if delta > 0) / len(deltas), 4),
    }


def write_cell_summary_csv(path: Path, groups: list[dict[str, Any]]) -> None:
    columns = [
        "cell_id",
        "cell_label",
        "runs",
        "quality_mean",
        "quality_ci95_low",
        "quality_ci95_high",
        "quality_median",
        "quality_stdev",
        "hidden_correctness_mean",
        "hidden_tests_mean",
        "performance_mean",
        "judge_mean",
        "gpt55_implementation_tokens_mean",
        "root_implementation_tokens_mean",
        "leaf_implementation_tokens_mean",
        "quality_per_gpt55_impl_token_mean",
        "implementation_elapsed_seconds_mean",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for group in groups:
            quality_ci = group["quality_bootstrap_ci95"]
            writer.writerow(
                {
                    "cell_id": group["cell_id"],
                    "cell_label": group["cell_label"],
                    "runs": group["runs"],
                    "quality_mean": group["quality"]["mean"],
                    "quality_ci95_low": quality_ci["low"],
                    "quality_ci95_high": quality_ci["high"],
                    "quality_median": group["quality"]["median"],
                    "quality_stdev": group["quality"]["sd"],
                    "hidden_correctness_mean": group["hidden_correctness"]["mean"],
                    "hidden_tests_mean": group["hidden_tests"]["mean"],
                    "performance_mean": group["performance"]["mean"],
                    "judge_mean": group["judge"]["mean"],
                    "gpt55_implementation_tokens_mean": group["gpt55_implementation_tokens"]["mean"],
                    "root_implementation_tokens_mean": group["root_implementation_tokens"]["mean"],
                    "leaf_implementation_tokens_mean": group["leaf_implementation_tokens"]["mean"],
                    "quality_per_gpt55_impl_token_mean": group["quality_per_gpt55_impl_token"]["mean"],
                    "implementation_elapsed_seconds_mean": group["implementation_elapsed_seconds"]["mean"],
                }
            )


def render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# GPT-5.5 Direct Quality Frontier 50-Run Analysis",
        "",
        f"Rows analyzed: {summary['row_count']}",
        f"Validation: {summary['validation']['status']}",
        "",
        "## Pooled Cell Summary",
        "",
        "| Cell | Configuration | Runs | Quality mean | 95% bootstrap CI | Hidden correctness | Judge | GPT-5.5 impl tokens | Quality/token |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for group in summary["pooled_cells"]:
        quality_ci = group["quality_bootstrap_ci95"]
        lines.append(
            "| {cell} | {label} | {runs} | {quality} | [{low}, {high}] | {hidden} | {judge} | {tokens} | {eff} |".format(
                cell=group["cell_id"],
                label=group["cell_label"],
                runs=group["runs"],
                quality=_fmt(group["quality"]["mean"]),
                low=_fmt(quality_ci["low"]),
                high=_fmt(quality_ci["high"]),
                hidden=_fmt(group["hidden_correctness"]["mean"]),
                judge=_fmt(group["judge"]["mean"]),
                tokens=_fmt(group["gpt55_implementation_tokens"]["mean"], decimals=0),
                eff=_fmt_sci(group["quality_per_gpt55_impl_token"]["mean"]),
            )
        )
    lines.extend(
        [
            "",
            "## Original 20 vs Extension 30",
            "",
            "| Cohort | Cell | Runs | Quality mean | Hidden correctness | GPT-5.5 impl tokens |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for group in summary["cohort_cells"]:
        lines.append(
            "| {cohort} | {cell} | {runs} | {quality} | {hidden} | {tokens} |".format(
                cohort=group["cohort"],
                cell=group["cell_id"],
                runs=group["runs"],
                quality=_fmt(group["quality"]["mean"]),
                hidden=_fmt(group["hidden_correctness"]["mean"]),
                tokens=_fmt(group["gpt55_implementation_tokens"]["mean"], decimals=0),
            )
        )
    lines.extend(
        [
            "",
            "## Pairwise Quality Deltas",
            "",
            "| Comparison | Mean delta | 95% bootstrap CI | P(left > right) |",
            "|---|---:|---:|---:|",
        ]
    )
    for item in summary["pairwise_quality_deltas"]:
        ci = item["bootstrap_ci95"]
        lines.append(
            "| {left} minus {right} | {delta} | [{low}, {high}] | {prob} |".format(
                left=item["left_cell"],
                right=item["right_cell"],
                delta=_fmt(item["delta_left_minus_right"]),
                low=_fmt(ci["low"]),
                high=_fmt(ci["high"]),
                prob=_fmt(item["probability_left_greater"], decimals=4),
            )
        )
    lines.extend(["", "## Factorial Quality Effects", ""])
    lines.append("| Effect | Mean delta | 95% bootstrap CI | Probability positive |")
    lines.append("|---|---:|---:|---:|")
    for name, effect in summary["factorial_quality_effects"].items():
        ci = effect["bootstrap_ci95"]
        lines.append(
            "| {name} | {delta} | [{low}, {high}] | {prob} |".format(
                name=name,
                delta=_fmt(effect["delta"]),
                low=_fmt(ci["low"]),
                high=_fmt(ci["high"]),
                prob=_fmt(effect["probability_positive"], decimals=4),
            )
        )
    return "\n".join(lines) + "\n"


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "sd": None, "min": None, "max": None}
    return {
        "n": len(values),
        "mean": _round_metric(mean(values)),
        "median": _round_metric(median(values)),
        "sd": _round_metric(stdev(values)) if len(values) > 1 else 0.0,
        "min": _round_metric(min(values)),
        "max": _round_metric(max(values)),
    }


def _bootstrap_mean_ci(values: list[float], iterations: int, rng: random.Random) -> dict[str, float]:
    sampled = [mean(rng.choice(values) for _ in values) for _ in range(iterations)]
    return _percentile_interval(sampled)


def _bootstrap_delta_values(
    left: list[float],
    right: list[float],
    iterations: int,
    rng: random.Random,
) -> list[float]:
    if not left or not right:
        raise ValueError("cannot bootstrap empty groups")
    return [
        mean(rng.choice(left) for _ in left) - mean(rng.choice(right) for _ in right)
        for _ in range(iterations)
    ]


def _percentile_interval(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    if not ordered:
        return {"low": math.nan, "high": math.nan}
    low_index = max(0, int(0.025 * len(ordered)) - 1)
    high_index = min(len(ordered) - 1, int(0.975 * len(ordered)))
    return {"low": round(ordered[low_index], 6), "high": round(ordered[high_index], 6)}


def _numbers(rows: Iterable[Mapping[str, Any]], field: str) -> list[float]:
    return [value for row in rows if (value := _float_or_none(row.get(field))) is not None]


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float:
    parsed = _float_or_none(value)
    return parsed if parsed is not None else math.nan


def _fmt(value: Any, *, decimals: int = 3) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return f"{float(value):.{decimals}f}"


def _fmt_sci(value: Any, *, decimals: int = 3) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return f"{float(value):.{decimals}e}"


def _round_metric(value: float) -> float:
    if value and abs(value) < 0.0001:
        return float(f"{value:.12g}")
    return round(value, 6)


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


if __name__ == "__main__":
    raise SystemExit(main())
