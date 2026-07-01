from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ORIGINAL_DIR = REPO_ROOT / "runs" / "20260629T224027-gpt55_direct_quality_frontier-gpt55_frontier_j7_j6"
DEFAULT_EXTENSION_DIR = (
    REPO_ROOT
    / "runs"
    / "20260630T061938-gpt55_direct_quality_frontier_50-gpt55_frontier_50_r21_r50_j7_j6"
)
DEFAULT_THREE_LEAF_DIR = (
    REPO_ROOT
    / "runs"
    / "20260701T051040-gpt55_direct_quality_frontier_3leaf_50-gpt55_frontier_3leaf_50_j7_j6"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "analysis" / "gpt55_direct_quality_frontier_leaf_count_50"

CELL_LABELS = {
    "GQF0": "6 leaves: high root + high leaves",
    "GQF1": "6 leaves: xhigh root + high leaves",
    "GQF2": "6 leaves: high root + xhigh leaves",
    "GQF3": "6 leaves: xhigh root + xhigh leaves",
    "GQ3L0": "3 leaves: high root + xhigh leaves",
    "GQ3L1": "3 leaves: high root + high leaves",
    "GQ3L2": "3 leaves: xhigh root + xhigh leaves",
    "GQ3L3": "3 leaves: xhigh root + high leaves",
}

EXPECTED_COUNTS = {
    ("six_leaf_original_20", "GQF0"): 20,
    ("six_leaf_original_20", "GQF1"): 20,
    ("six_leaf_original_20", "GQF2"): 20,
    ("six_leaf_original_20", "GQF3"): 20,
    ("six_leaf_extension_30", "GQF0"): 30,
    ("six_leaf_extension_30", "GQF1"): 30,
    ("six_leaf_extension_30", "GQF2"): 30,
    ("six_leaf_extension_30", "GQF3"): 30,
    ("three_leaf_50", "GQ3L0"): 50,
    ("three_leaf_50", "GQ3L1"): 50,
    ("three_leaf_50", "GQ3L2"): 50,
    ("three_leaf_50", "GQ3L3"): 50,
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
    "leaf_count",
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

MATCHED_COMPARISONS = (
    {
        "comparison_id": "high_high",
        "label": "high root + high leaves",
        "three_leaf_cell": "GQ3L1",
        "six_leaf_cell": "GQF0",
    },
    {
        "comparison_id": "high_xhigh",
        "label": "high root + xhigh leaves",
        "three_leaf_cell": "GQ3L0",
        "six_leaf_cell": "GQF2",
    },
    {
        "comparison_id": "xhigh_high",
        "label": "xhigh root + high leaves",
        "three_leaf_cell": "GQ3L3",
        "six_leaf_cell": "GQF1",
    },
    {
        "comparison_id": "xhigh_xhigh",
        "label": "xhigh root + xhigh leaves",
        "three_leaf_cell": "GQ3L2",
        "six_leaf_cell": "GQF3",
    },
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = _resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    rows.extend(read_results(_resolve_path(args.original_dir), cohort="six_leaf_original_20", leaf_family="six_leaf"))
    rows.extend(read_results(_resolve_path(args.extension_dir), cohort="six_leaf_extension_30", leaf_family="six_leaf"))
    rows.extend(read_results(_resolve_path(args.three_leaf_dir), cohort="three_leaf_50", leaf_family="three_leaf"))

    summary = build_summary(rows, bootstrap_iterations=args.bootstrap_iterations, seed=args.seed)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_cell_summary_csv(output_dir / "cell_summary.csv", summary["cell_summaries"])
    write_leaf_count_comparison_csv(output_dir / "leaf_count_comparisons.csv", summary["leaf_count_comparisons"])
    (output_dir / "summary.md").write_text(render_markdown(summary), encoding="utf-8")

    print(f"Wrote GPT-5.5 leaf-count frontier analysis to {output_dir}")
    print(f"Rows analyzed: {summary['row_count']}")
    print(f"Validation status: {summary['validation']['status']}")
    return 0 if summary["validation"]["status"] == "passed" else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze GPT-5.5 frontier quality across six-leaf and three-leaf cells.")
    parser.add_argument("--original-dir", default=str(DEFAULT_ORIGINAL_DIR))
    parser.add_argument("--extension-dir", default=str(DEFAULT_EXTENSION_DIR))
    parser.add_argument("--three-leaf-dir", default=str(DEFAULT_THREE_LEAF_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--bootstrap-iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=815)
    return parser.parse_args(argv)


def read_results(experiment_dir: Path, *, cohort: str, leaf_family: str) -> list[dict[str, Any]]:
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
            normalized["leaf_family"] = leaf_family
            normalized["cell_label"] = CELL_LABELS.get(str(row.get("cell_id")), str(row.get("cell_id")))
            normalized["reasoning_pair"] = f"{row.get('root_reasoning')}/{row.get('leaf_reasoning')}"
            for field in NUMERIC_FIELDS:
                normalized[field] = _float_or_none(normalized.get(field))
            rows.append(normalized)
    return rows


def build_summary(rows: list[dict[str, Any]], *, bootstrap_iterations: int, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    validation = validate_rows(rows)
    cell_summaries = summarize_groups(rows, key=lambda row: str(row["cell_id"]), bootstrap_iterations=bootstrap_iterations, rng=rng)
    family_summaries = summarize_groups(
        rows,
        key=lambda row: str(row["leaf_family"]),
        bootstrap_iterations=bootstrap_iterations,
        rng=rng,
    )
    root_family_summaries = summarize_groups(
        rows,
        key=lambda row: f"{row['root_reasoning']}:{row['leaf_family']}",
        bootstrap_iterations=bootstrap_iterations,
        rng=rng,
    )
    leaf_count_comparisons = matched_leaf_count_comparisons(rows, bootstrap_iterations=bootstrap_iterations, rng=rng)
    hypothesis_tests = grouped_leaf_count_effects(rows, bootstrap_iterations=bootstrap_iterations, rng=rng)
    top_runs = sorted(
        (
            {
                "run_id": row["run_id"],
                "cell_id": row["cell_id"],
                "cell_label": row["cell_label"],
                "quality_score": row["quality_score"],
                "hidden_correctness": row["hidden_correctness"],
                "judge": row["judge"],
                "gpt55_implementation_tokens": row["gpt55_implementation_tokens"],
            }
            for row in rows
        ),
        key=lambda item: float(item["quality_score"] or 0.0),
        reverse=True,
    )[:15]
    return {
        "schema_version": 1,
        "row_count": len(rows),
        "bootstrap_iterations": bootstrap_iterations,
        "bootstrap_seed": seed,
        "validation": validation,
        "cell_summaries": cell_summaries,
        "family_summaries": family_summaries,
        "root_family_summaries": root_family_summaries,
        "leaf_count_comparisons": leaf_count_comparisons,
        "hypothesis_tests": hypothesis_tests,
        "top_quality_runs": top_runs,
        "sources": sorted({str(row["experiment_dir"]) for row in rows}),
    }


def validate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    by_cohort_cell = Counter((str(row.get("cohort")), str(row.get("cell_id"))) for row in rows)
    by_cell = Counter(str(row.get("cell_id")) for row in rows)
    duplicate_ids = sorted(run_id for run_id, count in Counter(str(row.get("run_id")) for row in rows).items() if count > 1)
    if duplicate_ids:
        errors.append(f"duplicate run ids: {', '.join(duplicate_ids[:10])}")
    for key, expected in EXPECTED_COUNTS.items():
        actual = by_cohort_cell[key]
        if actual != expected:
            errors.append(f"{key[0]}:{key[1]} expected {expected} rows, found {actual}")
    for cell_id, expected in {
        "GQF0": 50,
        "GQF1": 50,
        "GQF2": 50,
        "GQF3": 50,
        "GQ3L0": 50,
        "GQ3L1": 50,
        "GQ3L2": 50,
        "GQ3L3": 50,
    }.items():
        if by_cell[cell_id] != expected:
            errors.append(f"{cell_id}: expected {expected} pooled rows, found {by_cell[cell_id]}")
    for row in rows:
        if row.get("artifact_status") != "complete":
            errors.append(f"{row.get('run_id')}: artifact_status={row.get('artifact_status')}")
        if row.get("failure_phase"):
            errors.append(f"{row.get('run_id')}: failure_phase={row.get('failure_phase')}")
        if row.get("usage_warnings"):
            warnings.append(f"{row.get('run_id')}: usage_warnings={row.get('usage_warnings')}")
        if row.get("score_warnings"):
            warnings.append(f"{row.get('run_id')}: score_warnings={row.get('score_warnings')}")
        if _as_float(row.get("quality_score")) <= 0:
            errors.append(f"{row.get('run_id')}: non-positive quality_score={row.get('quality_score')}")
    return {
        "status": "failed" if errors else "warning" if warnings else "passed",
        "errors": errors,
        "warnings": warnings,
        "by_cell": dict(sorted(by_cell.items())),
        "by_cohort_cell": {f"{cohort}:{cell}": count for (cohort, cell), count in sorted(by_cohort_cell.items())},
    }


def summarize_groups(
    rows: list[dict[str, Any]],
    *,
    key: Any,
    bootstrap_iterations: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(key(row))].append(row)
    return [
        summarize_group(group_id, group_rows, bootstrap_iterations=bootstrap_iterations, rng=rng)
        for group_id, group_rows in sorted(groups.items())
    ]


def summarize_group(
    group_id: str,
    rows: list[dict[str, Any]],
    *,
    bootstrap_iterations: int,
    rng: random.Random,
) -> dict[str, Any]:
    first = rows[0]
    quality_values = _numbers(rows, "quality_score")
    summary: dict[str, Any] = {
        "group_id": group_id,
        "cell_id": first.get("cell_id") if len({row.get("cell_id") for row in rows}) == 1 else "mixed",
        "cell_label": first.get("cell_label") if len({row.get("cell_id") for row in rows}) == 1 else "mixed",
        "leaf_family": first.get("leaf_family") if len({row.get("leaf_family") for row in rows}) == 1 else "mixed",
        "leaf_count": _same_or_mixed(_numbers(rows, "leaf_count")),
        "root_reasoning": first.get("root_reasoning") if len({row.get("root_reasoning") for row in rows}) == 1 else "mixed",
        "leaf_reasoning": first.get("leaf_reasoning") if len({row.get("leaf_reasoning") for row in rows}) == 1 else "mixed",
        "runs": len(rows),
        "status_counts": dict(sorted(Counter(str(row.get("status") or "") for row in rows).items())),
        "quality": _stats(quality_values),
        "quality_top_quartile_mean": round(mean(sorted(quality_values, reverse=True)[: max(1, len(quality_values) // 4)]), 6),
    }
    if bootstrap_iterations:
        summary["quality_bootstrap_ci95"] = _bootstrap_mean_ci(quality_values, bootstrap_iterations, rng)
    for field in SUMMARY_FIELDS:
        summary[field] = _stats(_numbers(rows, field))
    return summary


def matched_leaf_count_comparisons(
    rows: list[dict[str, Any]],
    *,
    bootstrap_iterations: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_cell[str(row["cell_id"])].append(row)
    comparisons = []
    for spec in MATCHED_COMPARISONS:
        three = by_cell[spec["three_leaf_cell"]]
        six = by_cell[spec["six_leaf_cell"]]
        comparisons.append(
            _comparison(
                comparison_id=spec["comparison_id"],
                label=spec["label"],
                left_label="3 leaves",
                right_label="6 leaves",
                left_rows=three,
                right_rows=six,
                bootstrap_iterations=bootstrap_iterations,
                rng=rng,
            )
            | {
                "three_leaf_cell": spec["three_leaf_cell"],
                "six_leaf_cell": spec["six_leaf_cell"],
            }
        )
    return comparisons


def grouped_leaf_count_effects(
    rows: list[dict[str, Any]],
    *,
    bootstrap_iterations: int,
    rng: random.Random,
) -> dict[str, Any]:
    def pick(*, family: str, root: str | None = None, leaf: str | None = None) -> list[dict[str, Any]]:
        selected = [row for row in rows if row["leaf_family"] == family]
        if root is not None:
            selected = [row for row in selected if row["root_reasoning"] == root]
        if leaf is not None:
            selected = [row for row in selected if row["leaf_reasoning"] == leaf]
        return selected

    return {
        "three_minus_six_all": _comparison(
            comparison_id="three_minus_six_all",
            label="3 leaves minus 6 leaves, all cells",
            left_label="3 leaves",
            right_label="6 leaves",
            left_rows=pick(family="three_leaf"),
            right_rows=pick(family="six_leaf"),
            bootstrap_iterations=bootstrap_iterations,
            rng=rng,
        ),
        "three_minus_six_high_roots": _comparison(
            comparison_id="three_minus_six_high_roots",
            label="3 leaves minus 6 leaves, high roots",
            left_label="3 leaves",
            right_label="6 leaves",
            left_rows=pick(family="three_leaf", root="high"),
            right_rows=pick(family="six_leaf", root="high"),
            bootstrap_iterations=bootstrap_iterations,
            rng=rng,
        ),
        "three_minus_six_xhigh_roots": _comparison(
            comparison_id="three_minus_six_xhigh_roots",
            label="3 leaves minus 6 leaves, xhigh roots",
            left_label="3 leaves",
            right_label="6 leaves",
            left_rows=pick(family="three_leaf", root="xhigh"),
            right_rows=pick(family="six_leaf", root="xhigh"),
            bootstrap_iterations=bootstrap_iterations,
            rng=rng,
        ),
        "three_leaf_xhigh_root_minus_high_root": _comparison(
            comparison_id="three_leaf_xhigh_root_minus_high_root",
            label="3-leaf xhigh roots minus 3-leaf high roots",
            left_label="xhigh roots",
            right_label="high roots",
            left_rows=pick(family="three_leaf", root="xhigh"),
            right_rows=pick(family="three_leaf", root="high"),
            bootstrap_iterations=bootstrap_iterations,
            rng=rng,
        ),
    }


def _comparison(
    *,
    comparison_id: str,
    label: str,
    left_label: str,
    right_label: str,
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
    bootstrap_iterations: int,
    rng: random.Random,
) -> dict[str, Any]:
    left_quality = _numbers(left_rows, "quality_score")
    right_quality = _numbers(right_rows, "quality_score")
    quality_deltas = _bootstrap_delta_values(left_quality, right_quality, bootstrap_iterations, rng)
    left_tokens = _numbers(left_rows, "gpt55_implementation_tokens")
    right_tokens = _numbers(right_rows, "gpt55_implementation_tokens")
    left_eff = _numbers(left_rows, "quality_per_gpt55_impl_token")
    right_eff = _numbers(right_rows, "quality_per_gpt55_impl_token")
    return {
        "comparison_id": comparison_id,
        "label": label,
        "left_label": left_label,
        "right_label": right_label,
        "left_runs": len(left_rows),
        "right_runs": len(right_rows),
        "quality_delta_left_minus_right": round(mean(left_quality) - mean(right_quality), 6),
        "quality_ci95": _percentile_interval(quality_deltas),
        "probability_quality_positive": round(sum(1 for delta in quality_deltas if delta > 0) / len(quality_deltas), 4),
        "gpt55_impl_token_delta_left_minus_right": round(mean(left_tokens) - mean(right_tokens), 2),
        "gpt55_impl_token_ratio_left_over_right": round(mean(left_tokens) / mean(right_tokens), 4),
        "quality_per_token_delta_left_minus_right": _round_metric(mean(left_eff) - mean(right_eff)),
        "left_quality_mean": _round_metric(mean(left_quality)),
        "right_quality_mean": _round_metric(mean(right_quality)),
        "left_tokens_mean": _round_metric(mean(left_tokens)),
        "right_tokens_mean": _round_metric(mean(right_tokens)),
    }


def write_cell_summary_csv(path: Path, groups: list[dict[str, Any]]) -> None:
    columns = [
        "group_id",
        "cell_id",
        "cell_label",
        "leaf_family",
        "leaf_count",
        "root_reasoning",
        "leaf_reasoning",
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
            ci = group["quality_bootstrap_ci95"]
            writer.writerow(
                {
                    "group_id": group["group_id"],
                    "cell_id": group["cell_id"],
                    "cell_label": group["cell_label"],
                    "leaf_family": group["leaf_family"],
                    "leaf_count": group["leaf_count"],
                    "root_reasoning": group["root_reasoning"],
                    "leaf_reasoning": group["leaf_reasoning"],
                    "runs": group["runs"],
                    "quality_mean": group["quality"]["mean"],
                    "quality_ci95_low": ci["low"],
                    "quality_ci95_high": ci["high"],
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


def write_leaf_count_comparison_csv(path: Path, comparisons: list[dict[str, Any]]) -> None:
    columns = [
        "comparison_id",
        "label",
        "three_leaf_cell",
        "six_leaf_cell",
        "quality_delta_left_minus_right",
        "quality_ci95_low",
        "quality_ci95_high",
        "probability_quality_positive",
        "left_quality_mean",
        "right_quality_mean",
        "gpt55_impl_token_delta_left_minus_right",
        "gpt55_impl_token_ratio_left_over_right",
        "quality_per_token_delta_left_minus_right",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for item in comparisons:
            ci = item["quality_ci95"]
            writer.writerow(
                {
                    "comparison_id": item["comparison_id"],
                    "label": item["label"],
                    "three_leaf_cell": item["three_leaf_cell"],
                    "six_leaf_cell": item["six_leaf_cell"],
                    "quality_delta_left_minus_right": item["quality_delta_left_minus_right"],
                    "quality_ci95_low": ci["low"],
                    "quality_ci95_high": ci["high"],
                    "probability_quality_positive": item["probability_quality_positive"],
                    "left_quality_mean": item["left_quality_mean"],
                    "right_quality_mean": item["right_quality_mean"],
                    "gpt55_impl_token_delta_left_minus_right": item["gpt55_impl_token_delta_left_minus_right"],
                    "gpt55_impl_token_ratio_left_over_right": item["gpt55_impl_token_ratio_left_over_right"],
                    "quality_per_token_delta_left_minus_right": item["quality_per_token_delta_left_minus_right"],
                }
            )


def render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# GPT-5.5 Direct Quality Frontier Leaf-Count Analysis",
        "",
        f"Rows analyzed: {summary['row_count']}",
        f"Validation: {summary['validation']['status']}",
        "",
        "## Cell Summary",
        "",
        "| Cell | Configuration | Runs | Quality mean | 95% bootstrap CI | Hidden correctness | Judge | GPT-5.5 impl tokens | Quality/token |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for group in sorted(summary["cell_summaries"], key=lambda item: (str(item["leaf_family"]), str(item["cell_id"]))):
        ci = group["quality_bootstrap_ci95"]
        lines.append(
            "| {cell} | {label} | {runs} | {quality} | [{low}, {high}] | {hidden} | {judge} | {tokens} | {eff} |".format(
                cell=group["cell_id"],
                label=group["cell_label"],
                runs=group["runs"],
                quality=_fmt(group["quality"]["mean"]),
                low=_fmt(ci["low"]),
                high=_fmt(ci["high"]),
                hidden=_fmt(group["hidden_correctness"]["mean"]),
                judge=_fmt(group["judge"]["mean"]),
                tokens=_fmt(group["gpt55_implementation_tokens"]["mean"], decimals=0),
                eff=_fmt_sci(group["quality_per_gpt55_impl_token"]["mean"]),
            )
        )
    lines.extend(
        [
            "",
            "## Matched 3-Leaf vs 6-Leaf Comparisons",
            "",
            "| Reasoning pair | 3-leaf cell | 6-leaf cell | Quality delta | 95% bootstrap CI | P(delta > 0) | Token ratio |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for item in summary["leaf_count_comparisons"]:
        ci = item["quality_ci95"]
        lines.append(
            "| {label} | {three} | {six} | {delta} | [{low}, {high}] | {prob} | {ratio} |".format(
                label=item["label"],
                three=item["three_leaf_cell"],
                six=item["six_leaf_cell"],
                delta=_fmt_signed(item["quality_delta_left_minus_right"]),
                low=_fmt_signed(ci["low"]),
                high=_fmt_signed(ci["high"]),
                prob=_fmt(item["probability_quality_positive"], decimals=4),
                ratio=_fmt(item["gpt55_impl_token_ratio_left_over_right"], decimals=3),
            )
        )
    lines.extend(
        [
            "",
            "## Hypothesis Tests",
            "",
            "| Effect | Quality delta | 95% bootstrap CI | P(delta > 0) | Token ratio |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for item in summary["hypothesis_tests"].values():
        ci = item["quality_ci95"]
        lines.append(
            "| {label} | {delta} | [{low}, {high}] | {prob} | {ratio} |".format(
                label=item["label"],
                delta=_fmt_signed(item["quality_delta_left_minus_right"]),
                low=_fmt_signed(ci["low"]),
                high=_fmt_signed(ci["high"]),
                prob=_fmt(item["probability_quality_positive"], decimals=4),
                ratio=_fmt(item["gpt55_impl_token_ratio_left_over_right"], decimals=3),
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


def _bootstrap_delta_values(left: list[float], right: list[float], iterations: int, rng: random.Random) -> list[float]:
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


def _same_or_mixed(values: list[float]) -> int | str:
    rounded = {int(value) for value in values}
    if len(rounded) == 1:
        return next(iter(rounded))
    return "mixed"


def _fmt(value: Any, *, decimals: int = 3) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return f"{float(value):.{decimals}f}"


def _fmt_signed(value: Any, *, decimals: int = 3) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return f"{float(value):+.{decimals}f}"


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
