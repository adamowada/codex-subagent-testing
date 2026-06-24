from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORICAL_GLOB = "runs/*ruleledger_v3_paper_50*measured"
NUMERIC_FIELDS = (
    "quality_score",
    "hidden_correctness",
    "hidden_parity",
    "performance",
    "judge",
    "implementation_tokens",
    "gpt55_implementation_tokens",
    "spark_implementation_tokens",
    "judge_tokens",
    "judge_inclusive_tokens",
    "quality_per_gpt55_impl_token",
    "quality_per_total_impl_token",
    "implementation_elapsed_seconds",
    "changed_files",
    "production_loc",
    "test_loc",
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    experiment_dirs = [_resolve_path(path) for path in args.experiment_dir]
    historical_dirs = (
        [_resolve_path(path) for path in args.historical_dir]
        if args.historical_dir
        else sorted(REPO_ROOT.glob(DEFAULT_HISTORICAL_GLOB))
    )
    rows = []
    for directory in historical_dirs:
        rows.extend(read_results(directory, source="historical"))
    for directory in experiment_dirs:
        rows.extend(read_results(directory, source=_experiment_source(directory)))

    output_dir = _resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = build_summary(rows)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_summary_csv(output_dir / "summary.csv", summary["groups"])
    write_summary_csv(output_dir / "phase_summary.csv", summary["phase_groups"])
    (output_dir / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
    print(f"Wrote Spark mode analysis to {output_dir}")
    print(f"Rows analyzed: {summary['row_count']}")
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Spark mode efficiency experiment results.")
    parser.add_argument(
        "--experiment-dir",
        action="append",
        default=[],
        help="Experiment directory containing results/results.csv. May be repeated.",
    )
    parser.add_argument(
        "--historical-dir",
        action="append",
        default=[],
        help="Historical baseline experiment directory. Defaults to all measured RuleLedger v3 paper batches.",
    )
    parser.add_argument(
        "--output-dir",
        default="runs/analysis/spark_mode_efficiency",
        help="Directory for derived analysis outputs.",
    )
    return parser.parse_args(argv)


def read_results(experiment_dir: Path, *, source: str) -> list[dict[str, Any]]:
    path = experiment_dir / "results" / "results.csv"
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            normalized = dict(row)
            normalized["experiment_dir"] = str(experiment_dir)
            normalized["source"] = source
            normalized["cohort"] = _cohort(normalized)
            normalized["analysis_mode"] = _analysis_mode(normalized)
            for field in NUMERIC_FIELDS:
                normalized[field] = _float_or_none(normalized.get(field))
            rows.append(normalized)
    return rows


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    group_summaries = summarize_groups(rows, cohort_key=lambda row: str(row.get("cohort") or "unknown"))
    phase_group_summaries = summarize_groups(rows, cohort_key=_phase_cohort)
    return {
        "schema_version": 1,
        "row_count": len(rows),
        "groups": group_summaries,
        "phase_groups": phase_group_summaries,
        "direct_vs_proposal": direct_proposal_deltas(group_summaries, cohort="spark_assisted"),
        "main_direct_vs_proposal": direct_proposal_deltas(phase_group_summaries, cohort="main_spark_assisted"),
        "pilot_direct_vs_proposal": direct_proposal_deltas(phase_group_summaries, cohort="pilot_spark_assisted"),
        "bridge_vs_historical": bridge_deltas(group_summaries),
        "main_spark_vs_historical": spark_historical_deltas(phase_group_summaries),
        "sources": sorted({str(row.get("source")) for row in rows}),
    }


def summarize_groups(
    rows: list[dict[str, Any]],
    *,
    cohort_key: Any,
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(cohort_key(row) or "unknown"),
            str(row.get("root_reasoning") or "unknown"),
            str(row.get("analysis_mode") or "unknown"),
        )
        groups[key].append(row)
    return [
        summarize_group(cohort=cohort, reasoning=reasoning, mode=mode, rows=group_rows)
        for (cohort, reasoning, mode), group_rows in sorted(groups.items())
    ]


def summarize_group(*, cohort: str, reasoning: str, mode: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cohort": cohort,
        "root_reasoning": reasoning,
        "mode": mode,
        "runs": len(rows),
        "status_counts": _counts(str(row.get("status") or "") for row in rows),
        "usage_attribution_methods": _counts(str(row.get("usage_attribution_method") or "") for row in rows),
        "quality": _stats(_numbers(rows, "quality_score")),
        "hidden_correctness": _stats(_numbers(rows, "hidden_correctness")),
        "hidden_parity": _stats(_numbers(rows, "hidden_parity")),
        "performance": _stats(_numbers(rows, "performance")),
        "judge": _stats(_numbers(rows, "judge")),
        "implementation_tokens": _stats(_numbers(rows, "implementation_tokens")),
        "gpt55_implementation_tokens": _stats(_numbers(rows, "gpt55_implementation_tokens")),
        "spark_implementation_tokens": _stats(_numbers(rows, "spark_implementation_tokens")),
        "quality_per_gpt55_impl_token": _stats(_numbers(rows, "quality_per_gpt55_impl_token")),
        "quality_per_total_impl_token": _stats(_numbers(rows, "quality_per_total_impl_token")),
        "implementation_elapsed_seconds": _stats(_numbers(rows, "implementation_elapsed_seconds")),
        "changed_files": _stats(_numbers(rows, "changed_files")),
        "production_loc": _stats(_numbers(rows, "production_loc")),
        "test_loc": _stats(_numbers(rows, "test_loc")),
    }


def direct_proposal_deltas(groups: list[dict[str, Any]], *, cohort: str) -> list[dict[str, Any]]:
    by_reasoning: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for group in groups:
        if group["cohort"] != cohort:
            continue
        by_reasoning[group["root_reasoning"]][group["mode"]] = group

    deltas = []
    for reasoning, modes in sorted(by_reasoning.items()):
        direct = modes.get("direct")
        proposal = modes.get("proposal")
        if not direct or not proposal:
            continue
        deltas.append(
            {
                "root_reasoning": reasoning,
                "quality_mean_delta_proposal_minus_direct": _delta_mean(proposal, direct, "quality"),
                "gpt55_token_mean_delta_proposal_minus_direct": _delta_mean(
                    proposal,
                    direct,
                    "gpt55_implementation_tokens",
                ),
                "spark_token_mean_delta_proposal_minus_direct": _delta_mean(
                    proposal,
                    direct,
                    "spark_implementation_tokens",
                ),
                "quality_per_gpt55_token_delta_proposal_minus_direct": _delta_mean(
                    proposal,
                    direct,
                    "quality_per_gpt55_impl_token",
                ),
            }
        )
    return deltas


def spark_historical_deltas(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {(group["cohort"], group["root_reasoning"], group["mode"]): group for group in groups}
    deltas = []
    for group in groups:
        if group["cohort"] != "main_spark_assisted":
            continue
        historical = by_key.get(("historical_solo", group["root_reasoning"], "solo"))
        if not historical:
            continue
        deltas.append(
            {
                "root_reasoning": group["root_reasoning"],
                "mode": group["mode"],
                "main_quality_mean": group["quality"]["mean"],
                "historical_quality_mean": historical["quality"]["mean"],
                "quality_mean_delta_main_minus_historical": _delta_mean(group, historical, "quality"),
                "main_gpt55_tokens_mean": group["gpt55_implementation_tokens"]["mean"],
                "historical_gpt55_tokens_mean": historical["gpt55_implementation_tokens"]["mean"],
                "gpt55_token_mean_delta_main_minus_historical": _delta_mean(
                    group,
                    historical,
                    "gpt55_implementation_tokens",
                ),
                "main_total_impl_tokens_mean": group["implementation_tokens"]["mean"],
                "historical_total_impl_tokens_mean": historical["implementation_tokens"]["mean"],
                "total_impl_token_mean_delta_main_minus_historical": _delta_mean(
                    group,
                    historical,
                    "implementation_tokens",
                ),
                "main_quality_per_total_token_mean": group["quality_per_total_impl_token"]["mean"],
                "historical_quality_per_total_token_mean": historical["quality_per_total_impl_token"]["mean"],
            }
        )
    return sorted(deltas, key=lambda item: (item["root_reasoning"], item["mode"]))


def bridge_deltas(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {(group["cohort"], group["root_reasoning"]): group for group in groups}
    deltas = []
    for reasoning in sorted({group["root_reasoning"] for group in groups}):
        bridge = by_key.get(("bridge_solo", reasoning))
        historical = by_key.get(("historical_solo", reasoning))
        if not bridge or not historical:
            continue
        deltas.append(
            {
                "root_reasoning": reasoning,
                "bridge_quality_mean": bridge["quality"]["mean"],
                "historical_quality_mean": historical["quality"]["mean"],
                "quality_mean_delta_bridge_minus_historical": _delta_mean(bridge, historical, "quality"),
                "bridge_gpt55_tokens_mean": bridge["gpt55_implementation_tokens"]["mean"],
                "historical_gpt55_tokens_mean": historical["gpt55_implementation_tokens"]["mean"],
            }
        )
    return deltas


def write_summary_csv(path: Path, groups: list[dict[str, Any]]) -> None:
    columns = [
        "cohort",
        "root_reasoning",
        "mode",
        "runs",
        "quality_mean",
        "quality_sd",
        "hidden_correctness_mean",
        "performance_mean",
        "judge_mean",
        "gpt55_implementation_tokens_mean",
        "spark_implementation_tokens_mean",
        "quality_per_gpt55_impl_token_mean",
        "quality_per_total_impl_token_mean",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for group in groups:
            writer.writerow(
                {
                    "cohort": group["cohort"],
                    "root_reasoning": group["root_reasoning"],
                    "mode": group["mode"],
                    "runs": group["runs"],
                    "quality_mean": group["quality"]["mean"],
                    "quality_sd": group["quality"]["sd"],
                    "hidden_correctness_mean": group["hidden_correctness"]["mean"],
                    "performance_mean": group["performance"]["mean"],
                    "judge_mean": group["judge"]["mean"],
                    "gpt55_implementation_tokens_mean": group["gpt55_implementation_tokens"]["mean"],
                    "spark_implementation_tokens_mean": group["spark_implementation_tokens"]["mean"],
                    "quality_per_gpt55_impl_token_mean": group["quality_per_gpt55_impl_token"]["mean"],
                    "quality_per_total_impl_token_mean": group["quality_per_total_impl_token"]["mean"],
                }
            )


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Spark Mode Efficiency Analysis Summary",
        "",
        f"Rows analyzed: {summary['row_count']}",
        "",
        "## Pooled Group Summary",
        "",
    ]
    _append_group_table(lines, summary["groups"])
    main_groups = [group for group in summary["phase_groups"] if group["cohort"] == "main_spark_assisted"]
    lines.extend(["", "## Official Main Spark-Assisted Summary", ""])
    _append_group_table(lines, main_groups)
    lines.extend(["", "## Pooled Proposal Minus Direct", ""])
    if summary["direct_vs_proposal"]:
        _append_direct_delta_table(lines, summary["direct_vs_proposal"])
    else:
        lines.append("No complete direct/proposal pairs available.")
    lines.extend(["", "## Main Proposal Minus Direct", ""])
    if summary["main_direct_vs_proposal"]:
        _append_direct_delta_table(lines, summary["main_direct_vs_proposal"])
    else:
        lines.append("No complete direct/proposal pairs available.")
    lines.extend(["", "## Bridge Minus Historical", ""])
    if summary["bridge_vs_historical"]:
        lines.append("| Reasoning | Bridge quality | Historical quality | Delta |")
        lines.append("|---|---:|---:|---:|")
        for item in summary["bridge_vs_historical"]:
            lines.append(
                "| {reasoning} | {bridge} | {historical} | {delta} |".format(
                    reasoning=item["root_reasoning"],
                    bridge=_fmt(item["bridge_quality_mean"]),
                    historical=_fmt(item["historical_quality_mean"]),
                    delta=_fmt(item["quality_mean_delta_bridge_minus_historical"]),
                )
            )
    else:
        lines.append("No bridge/historical pairs available.")
    lines.extend(["", "## Main Spark Minus Historical", ""])
    if summary["main_spark_vs_historical"]:
        lines.append(
            "| Reasoning | Mode | Main quality | Historical quality | Quality delta | Main total tokens | Historical total tokens |"
        )
        lines.append("|---|---|---:|---:|---:|---:|---:|")
        for item in summary["main_spark_vs_historical"]:
            lines.append(
                "| {reasoning} | {mode} | {main_quality} | {historical_quality} | {delta} | {main_tokens} | {historical_tokens} |".format(
                    reasoning=item["root_reasoning"],
                    mode=item["mode"],
                    main_quality=_fmt(item["main_quality_mean"]),
                    historical_quality=_fmt(item["historical_quality_mean"]),
                    delta=_fmt(item["quality_mean_delta_main_minus_historical"]),
                    main_tokens=_fmt(item["main_total_impl_tokens_mean"], decimals=0),
                    historical_tokens=_fmt(item["historical_total_impl_tokens_mean"], decimals=0),
                )
            )
    else:
        lines.append("No main Spark/historical pairs available.")
    return "\n".join(lines) + "\n"


def _append_group_table(lines: list[str], groups: list[dict[str, Any]]) -> None:
    lines.append(
        "| Cohort | Reasoning | Mode | Runs | Quality mean | GPT tokens mean | Spark tokens mean | Quality/GPT token |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---:|")
    for group in groups:
        lines.append(
            "| {cohort} | {reasoning} | {mode} | {runs} | {quality} | {gpt} | {spark} | {eff} |".format(
                cohort=group["cohort"],
                reasoning=group["root_reasoning"],
                mode=group["mode"],
                runs=group["runs"],
                quality=_fmt(group["quality"]["mean"]),
                gpt=_fmt(group["gpt55_implementation_tokens"]["mean"], decimals=0),
                spark=_fmt(group["spark_implementation_tokens"]["mean"], decimals=0),
                eff=_fmt(group["quality_per_gpt55_impl_token"]["mean"], decimals=10),
            )
        )


def _append_direct_delta_table(lines: list[str], deltas: list[dict[str, Any]]) -> None:
    lines.append("| Reasoning | Quality delta | GPT token delta | Spark token delta | Efficiency delta |")
    lines.append("|---|---:|---:|---:|---:|")
    for item in deltas:
        lines.append(
            "| {reasoning} | {quality} | {gpt} | {spark} | {eff} |".format(
                reasoning=item["root_reasoning"],
                quality=_fmt(item["quality_mean_delta_proposal_minus_direct"]),
                gpt=_fmt(item["gpt55_token_mean_delta_proposal_minus_direct"], decimals=0),
                spark=_fmt(item["spark_token_mean_delta_proposal_minus_direct"], decimals=0),
                eff=_fmt(item["quality_per_gpt55_token_delta_proposal_minus_direct"], decimals=10),
            )
        )


def _cohort(row: dict[str, Any]) -> str:
    cell_id = str(row.get("cell_id") or "")
    spark_mode = str(row.get("spark_mode") or "none")
    if cell_id.startswith("V3P"):
        return "historical_solo"
    if cell_id.startswith("SMEB"):
        return "bridge_solo"
    if spark_mode in {"direct", "proposal"}:
        return "spark_assisted"
    return "other"


def _phase_cohort(row: dict[str, Any]) -> str:
    cohort = str(row.get("cohort") or _cohort(row))
    source = str(row.get("source") or "")
    if cohort == "spark_assisted" and source in {"main", "pilot"}:
        return f"{source}_spark_assisted"
    return cohort


def _analysis_mode(row: dict[str, Any]) -> str:
    cohort = _cohort(row)
    if cohort in {"historical_solo", "bridge_solo"}:
        return "solo"
    return str(row.get("spark_mode") or "none")


def _experiment_source(path: Path) -> str:
    name = path.name.lower()
    if "pilot" in name:
        return "pilot"
    if "main" in name:
        return "main"
    return "experiment"


def _numbers(rows: Iterable[dict[str, Any]], key: str) -> list[float]:
    values = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "sd": None, "min": None, "max": None}
    return {
        "n": len(values),
        "mean": round(mean(values), 12),
        "median": round(median(values), 12),
        "sd": round(stdev(values), 12) if len(values) > 1 else 0.0,
        "min": round(min(values), 12),
        "max": round(max(values), 12),
    }


def _counts(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _delta_mean(left: dict[str, Any], right: dict[str, Any], metric: str) -> float | None:
    left_mean = left[metric]["mean"]
    right_mean = right[metric]["mean"]
    if left_mean is None or right_mean is None:
        return None
    return round(float(left_mean) - float(right_mean), 12)


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _fmt(value: Any, *, decimals: int = 6) -> str:
    if value is None:
        return "n/a"
    number = float(value)
    if decimals == 0:
        return f"{number:,.0f}"
    return f"{number:.{decimals}f}".rstrip("0").rstrip(".") or "0"


def _resolve_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


if __name__ == "__main__":
    raise SystemExit(main())
