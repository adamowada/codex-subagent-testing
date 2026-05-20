from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import shutil
import sqlite3
from statistics import mean, median, stdev
import subprocess
from typing import Any, Callable, Iterable, Mapping, Sequence

from harness.matrix import (
    DEFAULT_BENCHMARK_TEMPLATE_PATH,
    DEFAULT_BENCHMARK_VERSION,
    DEFAULT_HIDDEN_CASES_PATH,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
PRIMARY_METRIC = "quality_per_gpt55_impl_token"

RESULT_COLUMNS = [
    "run_id",
    "cell_id",
    "cell_name",
    "topology",
    "spark_mode",
    "repeat_index",
    "benchmark_version",
    "benchmark_template_path",
    "hidden_cases_path",
    "scoring_path",
    "scoring_profile",
    "status",
    "quality_score",
    "public_tests",
    "hidden_tests",
    "judge",
    "typecheck",
    "parity",
    "minimality",
    "implementation_tokens",
    "gpt55_implementation_tokens",
    "judge_tokens",
    "quality_per_gpt55_impl_token",
    "quality_per_judge_inclusive_gpt55_token",
    "quality_per_total_impl_token",
    "quality_per_wall_clock_minute",
    "implementation_elapsed_seconds",
    "changed_files",
    "insertions",
    "deletions",
    "binary_files",
    "production_loc",
    "test_loc",
    "root_model",
    "root_reasoning",
    "leaf_model",
    "leaf_count",
    "leaf_reasoning",
    "sublead_model",
    "sublead_count",
    "sublead_reasoning",
    "max_depth",
    "max_threads",
    "usage_attribution_method",
    "usage_warnings",
    "score_warnings",
    "failure_phase",
    "artifact_status",
    "run_dir",
]

APPENDIX_COLUMNS = [
    "run_id",
    "cell_id",
    "spark_mode",
    "repeat_index",
    "benchmark_version",
    "status",
    "quality_score",
    "hidden_tests",
    "judge",
    "typecheck",
    "parity",
    "gpt55_implementation_tokens",
    "quality_per_gpt55_impl_token",
    "implementation_elapsed_seconds",
    "usage_attribution_method",
    "artifact_status",
    "run_dir",
]


def collect_result_rows(experiment_dir: str | Path, runs: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    root = Path(experiment_dir)
    rows: list[dict[str, Any]] = []
    for run in runs:
        run_id = str(run["run_id"])
        run_dir = root / "runs" / run_id
        score_path = run_dir / "score.json"
        usage_path = run_dir / "usage.json"
        score = _read_json(score_path)
        usage = _read_json(usage_path)
        state = _read_json(run_dir / "state.json")
        totals = usage.get("totals", {}) if isinstance(usage.get("totals"), Mapping) else {}
        components = score.get("component_scores", {}) if isinstance(score.get("component_scores"), Mapping) else {}
        efficiency = score.get("efficiency", {}) if isinstance(score.get("efficiency"), Mapping) else {}
        diff_stats = score.get("diff_stats", {}) if isinstance(score.get("diff_stats"), Mapping) else {}
        wall_time = score.get("wall_time", {}) if isinstance(score.get("wall_time"), Mapping) else {}
        root_config = run.get("root") if isinstance(run.get("root"), Mapping) else {}
        leaf_config = run.get("leaf") if isinstance(run.get("leaf"), Mapping) else {}
        sublead_config = run.get("subleads") if isinstance(run.get("subleads"), Mapping) else {}
        agent_config = run.get("agents") if isinstance(run.get("agents"), Mapping) else {}
        benchmark = _run_benchmark_metadata(run)
        usage_warnings = _string_list(usage.get("warnings"))
        score_warnings = _string_list(score.get("warnings"))
        rows.append(
            {
                "run_id": run_id,
                "cell_id": run.get("cell_id"),
                "cell_name": run.get("cell_name"),
                "topology": run.get("topology"),
                "spark_mode": run.get("spark_mode") or "none",
                "repeat_index": run.get("repeat_index"),
                "benchmark_version": benchmark["version"],
                "benchmark_template_path": benchmark["template_path"],
                "hidden_cases_path": benchmark["hidden_cases_path"],
                "scoring_path": benchmark["scoring_path"],
                "scoring_profile": benchmark["scoring_profile"],
                "status": score.get("status", "missing_score"),
                "quality_score": score.get("quality_score", 0.0),
                "public_tests": components.get("public_tests", 0.0),
                "hidden_tests": components.get("hidden_tests", 0.0),
                "judge": components.get("judge", 0.0),
                "typecheck": components.get("typecheck", 0.0),
                "parity": components.get("parity", 0.0),
                "minimality": components.get("minimality", 0.0),
                "implementation_tokens": totals.get("implementation_tokens", 0),
                "gpt55_implementation_tokens": totals.get("gpt55_implementation_tokens", 0),
                "judge_tokens": totals.get("judge_tokens", 0),
                "quality_per_gpt55_impl_token": efficiency.get("quality_per_gpt55_impl_token"),
                "quality_per_judge_inclusive_gpt55_token": efficiency.get(
                    "quality_per_judge_inclusive_gpt55_token"
                ),
                "quality_per_total_impl_token": efficiency.get("quality_per_total_impl_token"),
                "quality_per_wall_clock_minute": efficiency.get("quality_per_wall_clock_minute"),
                "implementation_elapsed_seconds": wall_time.get("implementation_elapsed_seconds", 0.0),
                "changed_files": diff_stats.get("changed_files", 0),
                "insertions": diff_stats.get("insertions", 0),
                "deletions": diff_stats.get("deletions", 0),
                "binary_files": diff_stats.get("binary_files", 0),
                "production_loc": diff_stats.get("production_loc", 0),
                "test_loc": diff_stats.get("test_loc", 0),
                "root_model": root_config.get("model"),
                "root_reasoning": root_config.get("reasoning"),
                "leaf_model": leaf_config.get("model") if leaf_config else "",
                "leaf_count": leaf_config.get("count", "") if leaf_config else "",
                "leaf_reasoning": _reasoning_summary(leaf_config.get("reasoning_by_role")),
                "sublead_model": sublead_config.get("model") if sublead_config else "",
                "sublead_count": sublead_config.get("count", "") if sublead_config else "",
                "sublead_reasoning": sublead_config.get("reasoning", "") if sublead_config else "",
                "max_depth": agent_config.get("max_depth", ""),
                "max_threads": agent_config.get("max_threads", ""),
                "usage_attribution_method": usage.get("attribution_method", "missing_usage"),
                "usage_warnings": _join_warnings(usage_warnings),
                "score_warnings": _join_warnings(score_warnings),
                "failure_phase": _failure_phase(state),
                "artifact_status": _artifact_status(score_path=score_path, usage_path=usage_path),
                "run_dir": str(run_dir),
            }
        )
    return sorted(rows, key=_row_sort_key)


def write_results_outputs(experiment_dir: str | Path, runs: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    root = Path(experiment_dir)
    rows = collect_result_rows(root, runs)
    results_dir = root / "results"
    report_dir = root / "report"
    results_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    csv_path = results_dir / "results.csv"
    sqlite_path = results_dir / "results.sqlite"
    aggregate_path = results_dir / "aggregate.json"
    html_path = report_dir / "report.html"
    pdf_path = report_dir / "report.pdf"

    aggregate = aggregate_rows(rows)
    write_results_csv(csv_path, rows)
    write_results_sqlite(sqlite_path, rows)
    write_html_report(html_path, rows, aggregate)
    pdf_result = render_pdf_report(html_path, pdf_path, rows, aggregate)
    aggregate["report_generation"] = {"pdf": pdf_result}
    aggregate_path.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_html_report(html_path, rows, aggregate)

    return {
        "results_csv": str(csv_path),
        "results_sqlite": str(sqlite_path),
        "aggregate_json": str(aggregate_path),
        "report_html": str(html_path),
        "report_pdf": str(pdf_path),
    }


def write_results_csv(path: str | Path, rows: list[Mapping[str, Any]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column)) for column in RESULT_COLUMNS})


def write_results_sqlite(path: str | Path, rows: list[Mapping[str, Any]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(output)
    try:
        connection.execute("DROP TABLE IF EXISTS results")
        columns_sql = ", ".join(f"{column} TEXT" for column in RESULT_COLUMNS)
        connection.execute(f"CREATE TABLE results ({columns_sql})")
        placeholders = ", ".join("?" for _ in RESULT_COLUMNS)
        connection.executemany(
            f"INSERT INTO results ({', '.join(RESULT_COLUMNS)}) VALUES ({placeholders})",
            [[_sqlite_value(row.get(column)) for column in RESULT_COLUMNS] for row in rows],
        )
        connection.commit()
    finally:
        connection.close()


def aggregate_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_cell = _aggregate_groups(rows, lambda row: str(row.get("cell_id") or "unknown"))
    by_spark_mode = _aggregate_groups(rows, lambda row: str(row.get("spark_mode") or "none"))
    by_run_group = _aggregate_groups(rows, _run_group_id)
    direct_proposal = _direct_proposal_deltas(rows)

    return {
        "schema_version": 2,
        "generated_at": _utc_now(),
        "primary_metric": PRIMARY_METRIC,
        "benchmark": _benchmark_summary(rows),
        "total_runs": len(rows),
        "by_cell": by_cell,
        "by_spark_mode": by_spark_mode,
        "by_run_group": by_run_group,
        "direct_proposal_deltas": direct_proposal,
        "failure_rate": _failure_rate(rows),
        "best_run": _best_run(rows, PRIMARY_METRIC),
        "rankings": {
            "primary_by_run_group": _rank_groups(by_run_group, "quality_per_gpt55_impl_token_mean"),
            "quality_by_run_group": _rank_groups(by_run_group, "quality_mean"),
            "hidden_tests_by_run_group": _rank_groups(by_run_group, "hidden_mean"),
        },
        "token_attribution": _token_attribution_summary(rows),
    }


def write_html_report(path: str | Path, rows: list[Mapping[str, Any]], aggregate: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html_report(rows, aggregate), encoding="utf-8")


def render_pdf_report(
    html_path: str | Path,
    pdf_path: str | Path,
    rows: list[Mapping[str, Any]],
    aggregate: Mapping[str, Any],
) -> dict[str, Any]:
    """Render report HTML to PDF with Playwright when available.

    The fallback keeps the experiment output contract intact in minimal
    environments while making the renderer status explicit in aggregate.json.
    """

    html_output = Path(html_path)
    pdf_output = Path(pdf_path)
    renderer_env = str(_env_value("CODEX_REPORT_PDF_RENDERER") or "").lower()
    if renderer_env == "minimal":
        write_minimal_pdf(pdf_output, _pdf_lines(rows, aggregate))
        return {"renderer": "minimal", "status": "ok", "reason": "CODEX_REPORT_PDF_RENDERER=minimal"}

    node_bin = shutil.which("node")
    script_path = REPO_ROOT / "scripts" / "render_report_pdf.mjs"
    if node_bin and script_path.exists():
        completed = subprocess.run(
            [node_bin, str(script_path), str(html_output), str(pdf_output)],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=120,
        )
        if completed.returncode == 0 and pdf_output.exists():
            return {"renderer": "playwright", "status": "ok"}
        reason = (completed.stderr or completed.stdout or "renderer exited without a PDF").strip()
    else:
        missing = "node" if not node_bin else str(script_path)
        reason = f"missing PDF renderer dependency: {missing}"

    write_minimal_pdf(pdf_output, _pdf_lines(rows, aggregate))
    return {
        "renderer": "minimal_fallback",
        "status": "fallback",
        "reason": reason[:1000],
    }


def render_html_report(rows: list[Mapping[str, Any]], aggregate: Mapping[str, Any]) -> str:
    sorted_rows = sorted(rows, key=_row_sort_key)
    by_run_group = aggregate.get("by_run_group", {})
    group_items = _group_chart_items(by_run_group) if isinstance(by_run_group, Mapping) else []
    rankings = aggregate.get("rankings", {}) if isinstance(aggregate.get("rankings"), Mapping) else {}
    primary_rankings = rankings.get("primary_by_run_group", []) if isinstance(rankings, Mapping) else []
    top_group = primary_rankings[0] if isinstance(primary_rankings, list) and primary_rankings else None
    token_attribution = (
        aggregate.get("token_attribution", {}) if isinstance(aggregate.get("token_attribution"), Mapping) else {}
    )
    c4_section = _c4_section(group_items)

    sections = [
        _html_document_start(),
        "<main>",
        _title_section(aggregate),
        _abstract_section(aggregate, top_group),
        _methods_section(aggregate),
        _benchmark_task_section(),
        _experiment_matrix_section(group_items),
        _results_section(group_items, aggregate),
        _direct_proposal_section(aggregate),
        c4_section,
        _token_attribution_section(token_attribution),
        _limitations_section(),
        _appendix_section(sorted_rows),
        "</main>",
        "</body>",
        "</html>",
    ]
    return "\n".join(sections)


def write_minimal_pdf(path: str | Path, lines: list[str]) -> None:
    """Write a small valid PDF without external dependencies."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    text_commands = ["BT", "/F1 11 Tf", "50 760 Td"]
    for index, line in enumerate(lines[:42]):
        if index:
            text_commands.append("0 -16 Td")
        text_commands.append(f"({_pdf_escape(line[:100])}) Tj")
    text_commands.append("ET")
    stream = "\n".join(text_commands).encode("ascii", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(content))
        content.extend(f"{number} 0 obj\n".encode("ascii"))
        content.extend(obj)
        content.extend(b"\nendobj\n")
    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    output.write_bytes(bytes(content))


def _aggregate_groups(
    rows: list[Mapping[str, Any]],
    key_func: Callable[[Mapping[str, Any]], str],
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        groups.setdefault(key_func(row), []).append(row)
    return {key: _aggregate_bucket(value) for key, value in sorted(groups.items(), key=lambda item: _group_sort_key(item[0]))}


def _aggregate_bucket(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "runs": len(rows),
        "cell_id": _common_value(rows, "cell_id"),
        "cell_name": _common_value(rows, "cell_name"),
        "topology": _common_value(rows, "topology"),
        "spark_mode": _common_value(rows, "spark_mode"),
        "benchmark_version": _common_value(rows, "benchmark_version"),
        "scoring_profile": _common_value(rows, "scoring_profile"),
        "root_model": _common_value(rows, "root_model"),
        "root_reasoning": _common_value(rows, "root_reasoning"),
        "leaf_model": _common_value(rows, "leaf_model"),
        "leaf_count": _common_value(rows, "leaf_count"),
        "leaf_reasoning": _common_value(rows, "leaf_reasoning"),
        "sublead_model": _common_value(rows, "sublead_model"),
        "sublead_count": _common_value(rows, "sublead_count"),
        "sublead_reasoning": _common_value(rows, "sublead_reasoning"),
        "max_depth": _common_value(rows, "max_depth"),
        "max_threads": _common_value(rows, "max_threads"),
        "quality_mean": _mean_metric(rows, "quality_score"),
        "quality_median": _median_metric(rows, "quality_score"),
        "quality_stdev": _stdev_metric(rows, "quality_score"),
        "public_mean": _mean_metric(rows, "public_tests"),
        "hidden_mean": _mean_metric(rows, "hidden_tests"),
        "judge_mean": _mean_metric(rows, "judge"),
        "typecheck_mean": _mean_metric(rows, "typecheck"),
        "parity_mean": _mean_metric(rows, "parity"),
        "minimality_mean": _mean_metric(rows, "minimality"),
        "implementation_tokens_mean": _mean_metric(rows, "implementation_tokens"),
        "gpt55_impl_tokens_mean": _mean_metric(rows, "gpt55_implementation_tokens"),
        "judge_tokens_mean": _mean_metric(rows, "judge_tokens"),
        "quality_per_gpt55_impl_token_mean": _mean_present_metric(rows, "quality_per_gpt55_impl_token"),
        "quality_per_judge_inclusive_gpt55_token_mean": _mean_present_metric(
            rows,
            "quality_per_judge_inclusive_gpt55_token",
        ),
        "quality_per_total_impl_token_mean": _mean_present_metric(rows, "quality_per_total_impl_token"),
        "quality_per_wall_clock_minute_mean": _mean_present_metric(rows, "quality_per_wall_clock_minute"),
        "implementation_elapsed_seconds_mean": _mean_metric(rows, "implementation_elapsed_seconds"),
        "changed_files_mean": _mean_metric(rows, "changed_files"),
        "production_loc_mean": _mean_metric(rows, "production_loc"),
        "test_loc_mean": _mean_metric(rows, "test_loc"),
        "failure_rate": _failure_rate(rows),
        "status_counts": dict(sorted(Counter(str(row.get("status")) for row in rows).items())),
        "best_run_by_quality": _best_run(rows, "quality_score"),
        "best_run_by_primary_efficiency": _best_run(rows, PRIMARY_METRIC),
    }


def _failure_rate(rows: Sequence[Mapping[str, Any]]) -> float:
    if not rows:
        return 0.0
    failures = sum(1 for row in rows if _row_has_measured_failure(row))
    return round(failures / len(rows), 6)


def _row_has_measured_failure(row: Mapping[str, Any]) -> bool:
    status = str(row.get("status") or "")
    artifact_status = str(row.get("artifact_status") or "")
    failure_phase = str(row.get("failure_phase") or "").strip()
    if failure_phase:
        return True
    if status in {"failed", "missing_score"}:
        return True
    return artifact_status not in {"", "complete"}


def _best_run(rows: Sequence[Mapping[str, Any]], metric: str) -> dict[str, Any] | None:
    if not rows:
        return None
    best = max(rows, key=lambda row: _float(row.get(metric)))
    return {
        "run_id": best.get("run_id"),
        "cell_id": best.get("cell_id"),
        "spark_mode": best.get("spark_mode"),
        "quality_score": best.get("quality_score"),
        "quality_per_gpt55_impl_token": best.get("quality_per_gpt55_impl_token"),
        "status": best.get("status"),
    }


def _rank_groups(groups: Mapping[str, Mapping[str, Any]], metric: str) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for group_id, bucket in groups.items():
        ranked.append(
            {
                "rank": 0,
                "group_id": group_id,
                "cell_id": bucket.get("cell_id"),
                "cell_name": bucket.get("cell_name"),
                "spark_mode": bucket.get("spark_mode"),
                "metric": metric,
                "value": bucket.get(metric),
                "runs": bucket.get("runs"),
            }
        )
    ranked.sort(key=lambda item: (-_float(item.get("value")), _group_sort_key(str(item.get("group_id")))))
    for index, item in enumerate(ranked, 1):
        item["rank"] = index
    return ranked


def _direct_proposal_deltas(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_cell_mode: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        cell_id = str(row.get("cell_id") or "unknown")
        mode = str(row.get("spark_mode") or "none")
        if mode in {"direct", "proposal"}:
            by_cell_mode.setdefault((cell_id, mode), []).append(row)

    deltas: dict[str, Any] = {}
    cell_ids = sorted({cell for cell, mode in by_cell_mode if mode in {"direct", "proposal"}})
    for cell_id in cell_ids:
        direct_rows = by_cell_mode.get((cell_id, "direct"), [])
        proposal_rows = by_cell_mode.get((cell_id, "proposal"), [])
        if not direct_rows or not proposal_rows:
            continue
        direct = _aggregate_bucket(direct_rows)
        proposal = _aggregate_bucket(proposal_rows)
        deltas[cell_id] = {
            "direct": direct,
            "proposal": proposal,
            "direct_minus_proposal": {
                "quality_mean": _delta(direct, proposal, "quality_mean"),
                "hidden_mean": _delta(direct, proposal, "hidden_mean"),
                "gpt55_impl_tokens_mean": _delta(direct, proposal, "gpt55_impl_tokens_mean"),
                "implementation_tokens_mean": _delta(direct, proposal, "implementation_tokens_mean"),
                "implementation_elapsed_seconds_mean": _delta(
                    direct,
                    proposal,
                    "implementation_elapsed_seconds_mean",
                ),
                "failure_rate": _delta(direct, proposal, "failure_rate"),
                "quality_per_gpt55_impl_token_mean": _delta(
                    direct,
                    proposal,
                    "quality_per_gpt55_impl_token_mean",
                ),
            },
        }
    return deltas


def _token_attribution_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    methods = Counter(str(row.get("usage_attribution_method") or "unknown") for row in rows)
    warning_rows = [row for row in rows if str(row.get("usage_warnings") or "").strip()]
    best_effort_rows = [
        row
        for row in rows
        if any(marker in str(row.get("usage_attribution_method") or "") for marker in ("best_effort", "partial"))
    ]
    warning_messages = Counter()
    for row in warning_rows:
        for warning in str(row.get("usage_warnings") or "").split(" | "):
            warning = warning.strip()
            if warning:
                warning_messages[warning] += 1
    return {
        "methods": dict(sorted(methods.items())),
        "runs_with_usage_warnings": len(warning_rows),
        "best_effort_runs": len(best_effort_rows),
        "warning_counts": dict(warning_messages.most_common(10)),
    }


def _html_document_start() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Codex Subagent Experiment Report</title>
  <style>
    @page { size: Letter; margin: 0.55in; }
    :root {
      color-scheme: light;
      --ink: #17202a;
      --muted: #5f6b7a;
      --line: #d7dee8;
      --soft: #f4f7fb;
      --blue: #3267d6;
      --green: #147d64;
      --amber: #a05a00;
      --red: #b42318;
    }
    body {
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: #ffffff;
      font-size: 13px;
      line-height: 1.45;
    }
    main { max-width: 1080px; margin: 0 auto; padding: 32px 28px 48px; }
    h1 { font-size: 30px; line-height: 1.1; margin: 0 0 8px; }
    h2 { font-size: 19px; margin: 28px 0 8px; padding-top: 10px; border-top: 1px solid var(--line); }
    h3 { font-size: 15px; margin: 18px 0 8px; }
    p { margin: 7px 0; }
    code { background: var(--soft); border: 1px solid var(--line); padding: 1px 4px; border-radius: 4px; }
    table { border-collapse: collapse; width: 100%; margin: 8px 0 14px; font-size: 12px; }
    th, td { border: 1px solid var(--line); padding: 6px 7px; text-align: left; vertical-align: top; }
    th { background: var(--soft); font-weight: 700; }
    .lede { color: var(--muted); max-width: 850px; font-size: 14px; }
    .kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: 18px 0; }
    .kpi { border: 1px solid var(--line); background: #fbfcfe; padding: 10px; border-radius: 6px; }
    .kpi-label { color: var(--muted); font-size: 11px; text-transform: uppercase; }
    .kpi-value { display: block; font-size: 19px; font-weight: 700; margin-top: 3px; }
    .chart-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
    .chart { break-inside: avoid; border: 1px solid var(--line); border-radius: 6px; padding: 10px; background: #ffffff; }
    .chart h3 { margin-top: 0; }
    .bar-row { display: grid; grid-template-columns: 150px 1fr 88px; gap: 8px; align-items: center; margin: 7px 0; }
    .bar-label { overflow-wrap: anywhere; color: var(--ink); }
    .bar-track { height: 12px; background: var(--soft); border-radius: 999px; overflow: hidden; border: 1px solid var(--line); }
    .bar-fill { height: 100%; background: var(--blue); border-radius: 999px; min-width: 1px; }
    .bar-fill.green { background: var(--green); }
    .bar-fill.amber { background: var(--amber); }
    .bar-fill.red { background: var(--red); }
    .metric { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
    .pill { display: inline-block; border: 1px solid var(--line); border-radius: 999px; padding: 1px 7px; background: var(--soft); }
    .note { color: var(--muted); font-size: 12px; }
    .warning { color: var(--amber); font-weight: 700; }
    .appendix { font-size: 10px; }
    .appendix th, .appendix td { padding: 4px; }
    @media print {
      main { padding: 0; }
      h2 { break-after: avoid; }
      .chart, table { break-inside: avoid; }
      .appendix { font-size: 8.5px; }
    }
  </style>
</head>
<body>"""


def _title_section(aggregate: Mapping[str, Any]) -> str:
    top = _top_primary(aggregate)
    benchmark = aggregate.get("benchmark") if isinstance(aggregate.get("benchmark"), Mapping) else {}
    benchmark_version = benchmark.get("version") or "unknown"
    scoring_profile = benchmark.get("scoring_profile") or "unknown"
    top_text = "No primary ranking is available yet."
    if top:
        top_text = (
            f"Top primary-efficiency group: <strong>{_escape(str(top.get('group_id')))}</strong> "
            f"with {_fmt_efficiency(top.get('value'))} quality per GPT-5.5 implementation token."
        )
    return f"""<section>
  <h1>Codex Subagent Topology Benchmark</h1>
  <p class="lede">Quality, token efficiency, wall-clock time, and failure behavior across Codex subagent topologies on benchmark {_escape(str(benchmark_version))}.</p>
  <div class="kpis">
    <div class="kpi"><span class="kpi-label">Runs</span><span class="kpi-value">{_escape(str(aggregate.get('total_runs', 0)))}</span></div>
    <div class="kpi"><span class="kpi-label">Benchmark</span><span class="kpi-value">{_escape(str(benchmark_version))}</span></div>
    <div class="kpi"><span class="kpi-label">Scoring</span><span class="kpi-value">{_escape(str(scoring_profile))}</span></div>
    <div class="kpi"><span class="kpi-label">Failure Rate</span><span class="kpi-value">{_fmt_percent(aggregate.get('failure_rate'))}</span></div>
    <div class="kpi"><span class="kpi-label">Primary Metric</span><span class="kpi-value">GPT-5.5 Eff.</span></div>
    <div class="kpi"><span class="kpi-label">Generated</span><span class="kpi-value">{_escape(str(aggregate.get('generated_at', '')))}</span></div>
  </div>
  <p>{top_text}</p>
</section>"""


def _abstract_section(aggregate: Mapping[str, Any], top_group: Any) -> str:
    top_sentence = "The primary ranking is unavailable until scored runs have nonzero GPT-5.5 usage."
    if isinstance(top_group, Mapping):
        top_sentence = (
            f"The highest ranked run group by primary efficiency is {_escape(str(top_group.get('group_id')))}, "
            f"at {_fmt_efficiency(top_group.get('value'))} quality per GPT-5.5 implementation token."
        )
    return f"""<section>
  <h2>Abstract</h2>
  <p>This report summarizes {int(_float(aggregate.get('total_runs')))} measured Codex implementation runs on the mixed-language RuleLedger benchmark. It compares the configured Codex topologies using a primary metric of implementation quality per GPT-5.5 implementation token.</p>
  <p>{top_sentence} Partial and failed runs remain visible because they are part of the measurement.</p>
</section>"""


def _methods_section(aggregate: Mapping[str, Any]) -> str:
    benchmark = aggregate.get("benchmark") if isinstance(aggregate.get("benchmark"), Mapping) else {}
    template_path = benchmark.get("template_path") or "unknown"
    hidden_cases_path = benchmark.get("hidden_cases_path") or "unknown"
    scoring_path = benchmark.get("scoring_path") or "unknown"
    scoring_profile = benchmark.get("scoring_profile") or "unknown"
    return f"""<section>
  <h2>Methods</h2>
  <p>Each measured run starts from the same frozen starter project and writes artifacts into a run-specific directory. Implementation and judge runs are launched through <code>codex exec --json</code>, preserving JSONL events, stderr logs, prompts, rendered config, diffs, test logs, judge output, usage summaries, metadata, and scores.</p>
  <p>Selected assets: template <code>{_escape(str(template_path))}</code>, hidden cases <code>{_escape(str(hidden_cases_path))}</code>, scoring profile <code>{_escape(str(scoring_profile))}</code> from <code>{_escape(str(scoring_path))}</code>.</p>
  <p>Hidden tests stay outside implementation workspaces and are not copied into prompts, worktrees, report rows, or appendices. Scoring is computed before this report from configured component weights, and this report consumes <code>score.json</code> plus <code>usage.json</code> rather than reparsing raw logs.</p>
</section>"""


def _benchmark_task_section() -> str:
    return """<section>
  <h2>Benchmark Task</h2>
  <p>RuleLedger models subscription account events. Agents implement matching TypeScript and Python surfaces for parsing, validation, normalization, state reduction, entitlement evaluation, account summaries, deterministic CSV reporting, and cross-language parity.</p>
  <p>Public tests are visible and intentionally incomplete. Hidden tests are frozen before measured runs and remain private; the report uses normalized hidden-test scores only.</p>
</section>"""


def _experiment_matrix_section(group_items: list[dict[str, Any]]) -> str:
    rows = []
    for item in group_items:
        bucket = item["bucket"]
        rows.append(
            "<tr>"
            f"<td>{_escape(item['label'])}</td>"
            f"<td>{_escape(str(bucket.get('runs', '')))}</td>"
            f"<td>{_escape(str(bucket.get('topology', '')))}</td>"
            f"<td>{_escape(str(bucket.get('root_model', '')))} / {_escape(str(bucket.get('root_reasoning', '')))}</td>"
            f"<td>{_escape(str(bucket.get('spark_mode', '')))}</td>"
            f"<td>{_escape(str(bucket.get('leaf_count', '')))}</td>"
            f"<td>{_escape(str(bucket.get('sublead_count', '')))}</td>"
            f"<td>{_escape(str(bucket.get('max_depth', '')))} / {_escape(str(bucket.get('max_threads', '')))}</td>"
            "</tr>"
        )
    body = "\n".join(rows) or '<tr><td colspan="8">No run groups available.</td></tr>'
    return f"""<section>
  <h2>Experiment Matrix</h2>
  <table>
    <thead><tr><th>Group</th><th>Runs</th><th>Topology</th><th>Root</th><th>Spark Mode</th><th>Leaves</th><th>Subleads</th><th>Depth / Threads</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</section>"""


def _results_section(group_items: list[dict[str, Any]], aggregate: Mapping[str, Any]) -> str:
    return f"""<section>
  <h2>Results</h2>
  <p>The primary ranking uses <code>{PRIMARY_METRIC}</code>. Scores are normalized from 0.0 to 1.0; token-efficiency values are shown as quality per token.</p>
  <div class="chart-grid">
    {_bar_chart("Primary Metric By Cell", group_items, "quality_per_gpt55_impl_token_mean", _fmt_efficiency)}
    {_bar_chart("Hidden-Test Score By Cell", group_items, "hidden_mean", _fmt_score, "green")}
    {_bar_chart("GPT-5.5 Implementation Tokens By Cell", group_items, "gpt55_impl_tokens_mean", _fmt_number, "amber")}
    {_bar_chart("Wall-Clock Time By Cell", group_items, "implementation_elapsed_seconds_mean", _fmt_seconds)}
    {_bar_chart("Failure Rate By Cell", group_items, "failure_rate", _fmt_percent, "red")}
    {_bar_chart("Mean Quality Score By Cell", group_items, "quality_mean", _fmt_score, "green")}
  </div>
  {_ranking_table(aggregate)}
</section>"""


def _direct_proposal_section(aggregate: Mapping[str, Any]) -> str:
    deltas = aggregate.get("direct_proposal_deltas", {})
    if not isinstance(deltas, Mapping) or not deltas:
        return """<section>
  <h2>Direct Edit Versus Proposal-Only Comparison</h2>
  <p>No matching direct/proposal run pairs are available in this selection.</p>
</section>"""

    rows = []
    for cell_id, payload in sorted(deltas.items(), key=lambda item: _group_sort_key(str(item[0]))):
        if not isinstance(payload, Mapping):
            continue
        delta = payload.get("direct_minus_proposal", {})
        if not isinstance(delta, Mapping):
            continue
        rows.append(
            "<tr>"
            f"<td>{_escape(str(cell_id))}</td>"
            f"<td>{_fmt_score(delta.get('quality_mean'))}</td>"
            f"<td>{_fmt_score(delta.get('hidden_mean'))}</td>"
            f"<td>{_fmt_efficiency(delta.get('quality_per_gpt55_impl_token_mean'))}</td>"
            f"<td>{_fmt_number(delta.get('gpt55_impl_tokens_mean'))}</td>"
            f"<td>{_fmt_seconds(delta.get('implementation_elapsed_seconds_mean'))}</td>"
            f"<td>{_fmt_percent(delta.get('failure_rate'))}</td>"
            "</tr>"
        )
    body = "\n".join(rows)
    return f"""<section>
  <h2>Direct Edit Versus Proposal-Only Comparison</h2>
  <p>Values are direct-edit means minus proposal-only means within the same cell. Positive quality deltas favor direct edit; positive token and time deltas mean direct edit used more resources.</p>
  <table>
    <thead><tr><th>Cell</th><th>Quality Delta</th><th>Hidden Delta</th><th>Primary Metric Delta</th><th>GPT-5.5 Token Delta</th><th>Time Delta</th><th>Failure-Rate Delta</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</section>"""


def _c4_section(group_items: list[dict[str, Any]]) -> str:
    c4_items = [item for item in group_items if str(item.get("label", "")).startswith("C4")]
    if not c4_items:
        return ""

    c4_rows = []
    for item in c4_items:
        bucket = item["bucket"]
        c4_rows.append(
            "<tr>"
            f"<td>{_escape(item['label'])}</td>"
            f"<td>{_fmt_score(bucket.get('quality_mean'))}</td>"
            f"<td>{_fmt_score(bucket.get('hidden_mean'))}</td>"
            f"<td>{_fmt_efficiency(bucket.get('quality_per_gpt55_impl_token_mean'))}</td>"
            f"<td>{_fmt_number(bucket.get('gpt55_impl_tokens_mean'))}</td>"
            f"<td>{_fmt_percent(bucket.get('failure_rate'))}</td>"
            "</tr>"
        )
    table = ""
    if c4_rows:
        table = (
            "<table><thead><tr><th>Group</th><th>Quality</th><th>Hidden</th><th>Primary Metric</th>"
            "<th>GPT-5.5 Tokens</th><th>Failure Rate</th></tr></thead><tbody>"
            + "\n".join(c4_rows)
            + "</tbody></table>"
        )
    return f"""<section>
  <h2>C4 Stress-Test Analysis</h2>
  <p>C4 is intentionally a coordination stress test: a GPT-5.5 xhigh root lead coordinates three GPT-5.5 medium subleads, and those subleads coordinate eighteen Spark xhigh leaves. This exceeds the documented default guidance and is evaluated as a high-coordination topology, not merely a larger flat Spark variant.</p>
  <p>Direct-edit C4 can expose merge and conflict hazards. Proposal-only C4 can expose root-lead and sublead integration bottlenecks. The useful question is whether any added coverage offsets the extra coordination and token cost.</p>
  {table}
</section>"""


def _token_attribution_section(token_attribution: Mapping[str, Any]) -> str:
    methods = token_attribution.get("methods", {}) if isinstance(token_attribution.get("methods"), Mapping) else {}
    method_rows = "\n".join(
        f"<tr><td>{_escape(str(method))}</td><td>{_escape(str(count))}</td></tr>"
        for method, count in sorted(methods.items())
    )
    if not method_rows:
        method_rows = '<tr><td colspan="2">No usage attribution data available.</td></tr>'

    warnings = token_attribution.get("warning_counts", {})
    warning_rows = ""
    if isinstance(warnings, Mapping):
        warning_rows = "\n".join(
            f"<tr><td>{_escape(str(message))}</td><td>{_escape(str(count))}</td></tr>"
            for message, count in warnings.items()
        )
    if not warning_rows:
        warning_rows = '<tr><td colspan="2">No usage-attribution warnings.</td></tr>'

    return f"""<section>
  <h2>Token Attribution Notes</h2>
  <p>Token totals are preserved even when mixed-agent JSONL cannot fully attribute usage to GPT-5.5 versus Spark. Best-effort or upper-bound attribution is labeled here instead of being hidden in raw JSON.</p>
  <p><span class="pill">Runs with attribution warnings: {_escape(str(token_attribution.get('runs_with_usage_warnings', 0)))}</span> <span class="pill">Best-effort runs: {_escape(str(token_attribution.get('best_effort_runs', 0)))}</span></p>
  <h3>Attribution Methods</h3>
  <table><thead><tr><th>Method</th><th>Runs</th></tr></thead><tbody>{method_rows}</tbody></table>
  <h3>Warnings</h3>
  <table><thead><tr><th>Warning</th><th>Runs</th></tr></thead><tbody>{warning_rows}</tbody></table>
</section>"""


def _limitations_section() -> str:
    return """<section>
  <h2>Limitations</h2>
  <p>The benchmark is contrived but structured, so results should be interpreted as evidence about this task family rather than all coding work. Five repeats per group may still leave meaningful variance. GPT-5.5 judge scores are a useful blind review signal but not ground truth.</p>
  <p>Token attribution can be best effort for mixed-agent runs, and wall-clock time depends on local and service conditions. Coordination-heavy cells should be interpreted as stress tests rather than default deployment guidance.</p>
</section>"""


def _appendix_section(rows: list[Mapping[str, Any]]) -> str:
    header = "".join(f"<th>{_escape(column)}</th>" for column in APPENDIX_COLUMNS)
    body_rows = []
    for row in rows:
        body_rows.append(
            "<tr>"
            + "".join(f"<td>{_escape(_display_value(row.get(column)))}</td>" for column in APPENDIX_COLUMNS)
            + "</tr>"
        )
    body = "\n".join(body_rows) or f'<tr><td colspan="{len(APPENDIX_COLUMNS)}">No run rows available.</td></tr>'
    return f"""<section>
  <h2>Appendix: Per-Run Rows And Artifact Paths</h2>
  <p class="note">Every selected run is listed, including partial, failed, and missing-score rows.</p>
  <table class="appendix">
    <thead><tr>{header}</tr></thead>
    <tbody>{body}</tbody>
  </table>
</section>"""


def _bar_chart(
    title: str,
    items: list[dict[str, Any]],
    metric: str,
    formatter: Callable[[Any], str],
    color: str = "",
) -> str:
    values = [_float(item["bucket"].get(metric)) for item in items]
    max_value = max(values, default=0.0)
    rows = []
    for item in items:
        value = _float(item["bucket"].get(metric))
        width = 0.0 if max_value <= 0 else min(100.0, (value / max_value) * 100.0)
        rows.append(
            f"""<div class="bar-row">
  <div class="bar-label">{_escape(item['label'])}</div>
  <div class="bar-track"><div class="bar-fill {color}" style="width: {width:.3f}%"></div></div>
  <div class="metric">{formatter(item['bucket'].get(metric))}</div>
</div>"""
        )
    body = "\n".join(rows) or '<p class="note">No data.</p>'
    return f'<div class="chart"><h3>{_escape(title)}</h3>{body}</div>'


def _ranking_table(aggregate: Mapping[str, Any]) -> str:
    rankings = aggregate.get("rankings", {}) if isinstance(aggregate.get("rankings"), Mapping) else {}
    primary = rankings.get("primary_by_run_group", []) if isinstance(rankings, Mapping) else []
    if not isinstance(primary, list) or not primary:
        return "<h3>Primary Ranking</h3><p>No primary ranking is available.</p>"
    rows = []
    for item in primary:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            "<tr>"
            f"<td>{_escape(str(item.get('rank')))}</td>"
            f"<td>{_escape(str(item.get('group_id')))}</td>"
            f"<td>{_escape(str(item.get('cell_name')))}</td>"
            f"<td>{_escape(str(item.get('spark_mode')))}</td>"
            f"<td>{_fmt_efficiency(item.get('value'))}</td>"
            f"<td>{_escape(str(item.get('runs')))}</td>"
            "</tr>"
        )
    body = "\n".join(rows)
    return f"""<h3>Primary Ranking</h3>
<table>
  <thead><tr><th>Rank</th><th>Group</th><th>Cell</th><th>Spark Mode</th><th>Quality Per GPT-5.5 Impl Token</th><th>Runs</th></tr></thead>
  <tbody>{body}</tbody>
</table>"""


def _group_chart_items(groups: Mapping[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for group_id, bucket in sorted(groups.items(), key=lambda item: _group_sort_key(str(item[0]))):
        if isinstance(bucket, Mapping):
            items.append({"label": _group_label(str(group_id), bucket), "bucket": bucket})
    return items


def _top_primary(aggregate: Mapping[str, Any]) -> Mapping[str, Any] | None:
    rankings = aggregate.get("rankings", {}) if isinstance(aggregate.get("rankings"), Mapping) else {}
    primary = rankings.get("primary_by_run_group", []) if isinstance(rankings, Mapping) else []
    if isinstance(primary, list) and primary and isinstance(primary[0], Mapping):
        return primary[0]
    return None


def _common_value(rows: Sequence[Mapping[str, Any]], key: str) -> Any:
    values = [row.get(key) for row in rows if row.get(key) not in {None, ""}]
    if not values:
        return ""
    first = values[0]
    if all(value == first for value in values):
        return first
    return "mixed"


def _run_benchmark_metadata(run: Mapping[str, Any]) -> dict[str, str]:
    benchmark = run.get("benchmark") if isinstance(run.get("benchmark"), Mapping) else {}
    return {
        "version": str(benchmark.get("version") or DEFAULT_BENCHMARK_VERSION),
        "template_path": str(benchmark.get("template_path") or DEFAULT_BENCHMARK_TEMPLATE_PATH),
        "hidden_cases_path": str(benchmark.get("hidden_cases_path") or DEFAULT_HIDDEN_CASES_PATH),
        "scoring_path": str(benchmark.get("scoring_path") or ""),
        "scoring_profile": str(benchmark.get("scoring_profile") or ""),
    }


def _benchmark_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    key_map = {
        "version": "benchmark_version",
        "template_path": "benchmark_template_path",
        "hidden_cases_path": "hidden_cases_path",
        "scoring_path": "scoring_path",
        "scoring_profile": "scoring_profile",
    }
    summary: dict[str, Any] = {}
    for output_key, row_key in key_map.items():
        values = [str(row.get(row_key)) for row in rows if row.get(row_key) not in {None, ""}]
        unique = sorted(set(values))
        summary[output_key] = unique[0] if len(unique) == 1 else "mixed" if unique else ""
    versions = [str(row.get("benchmark_version")) for row in rows if row.get("benchmark_version") not in {None, ""}]
    summary["versions"] = {version: versions.count(version) for version in sorted(set(versions))}
    return summary


def _mean_metric(rows: Sequence[Mapping[str, Any]], key: str) -> float:
    values = [_float(row.get(key)) for row in rows]
    return round(mean(values), 6) if values else 0.0


def _mean_present_metric(rows: Sequence[Mapping[str, Any]], key: str) -> float | None:
    values = [_float(row.get(key)) for row in rows if row.get(key) is not None and row.get(key) != ""]
    return round(mean(values), 12) if values else None


def _median_metric(rows: Sequence[Mapping[str, Any]], key: str) -> float:
    values = [_float(row.get(key)) for row in rows]
    return round(median(values), 6) if values else 0.0


def _stdev_metric(rows: Sequence[Mapping[str, Any]], key: str) -> float:
    values = [_float(row.get(key)) for row in rows]
    return round(stdev(values), 6) if len(values) > 1 else 0.0


def _delta(left: Mapping[str, Any], right: Mapping[str, Any], key: str) -> float | None:
    left_value = left.get(key)
    right_value = right.get(key)
    if left_value is None or right_value is None:
        return None
    return round(_float(left_value) - _float(right_value), 12)


def _run_group_id(row: Mapping[str, Any]) -> str:
    cell_id = str(row.get("cell_id") or "unknown")
    mode = str(row.get("spark_mode") or "none")
    if mode == "none":
        return cell_id
    return f"{cell_id}:{mode}"


def _group_label(group_id: str, bucket: Mapping[str, Any]) -> str:
    mode = bucket.get("spark_mode")
    if mode and mode != "none":
        return f"{bucket.get('cell_id') or group_id} {mode}"
    return str(bucket.get("cell_id") or group_id)


def _row_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        _cell_sort_value(str(row.get("cell_id") or "")),
        _mode_sort_value(str(row.get("spark_mode") or "none")),
        _safe_int(row.get("repeat_index")),
        str(row.get("run_id") or ""),
    )


def _group_sort_key(group_id: str) -> tuple[Any, ...]:
    if ":" in group_id:
        cell, mode = group_id.split(":", 1)
    else:
        cell, mode = group_id, "none"
    return (_cell_sort_value(cell), _mode_sort_value(mode), group_id)


def _cell_sort_value(value: str) -> tuple[int, str]:
    if value.startswith("C") and value[1:].isdigit():
        return (int(value[1:]), value)
    return (9999, value)


def _mode_sort_value(value: str) -> int:
    return {"none": 0, "direct": 1, "proposal": 2}.get(value, 9)


def _artifact_status(*, score_path: Path, usage_path: Path) -> str:
    missing = []
    if not score_path.exists():
        missing.append("score")
    if not usage_path.exists():
        missing.append("usage")
    return "complete" if not missing else "missing_" + "_".join(missing)


def _failure_phase(state: Mapping[str, Any]) -> str:
    phases = state.get("phases", {}) if isinstance(state, Mapping) else {}
    if not isinstance(phases, Mapping):
        return ""
    failed = [name for name, payload in phases.items() if isinstance(payload, Mapping) and payload.get("status") == "failed"]
    return ",".join(str(name) for name in failed)


def _reasoning_summary(value: Any) -> str:
    if not isinstance(value, Mapping) or not value:
        return ""
    values = {str(item) for item in value.values()}
    if len(values) == 1:
        return next(iter(values))
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _join_warnings(warnings: Sequence[str]) -> str:
    return " | ".join(warning.replace("\n", " ").strip() for warning in warnings if warning.strip())


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return "" if value is None else value


def _sqlite_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _float(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _display_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return _fmt_number(value)
    return str(value)


def _fmt_number(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    number = _float(value)
    if abs(number) >= 1000:
        return f"{number:,.0f}"
    if abs(number) >= 10:
        return f"{number:,.2f}"
    return f"{number:.6f}".rstrip("0").rstrip(".") or "0"


def _fmt_score(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    return f"{_float(value):.3f}"


def _fmt_efficiency(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    return f"{_float(value):.9f}".rstrip("0").rstrip(".") or "0"


def _fmt_percent(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    return f"{_float(value) * 100.0:.1f}%"


def _fmt_seconds(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    seconds = _float(value)
    if seconds >= 3600:
        return f"{seconds / 3600.0:.2f} h"
    if seconds >= 60:
        return f"{seconds / 60.0:.2f} min"
    return f"{seconds:.1f} s"


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_lines(rows: list[Mapping[str, Any]], aggregate: Mapping[str, Any]) -> list[str]:
    benchmark = aggregate.get("benchmark") if isinstance(aggregate.get("benchmark"), Mapping) else {}
    lines = [
        "Codex Subagent Experiment Report",
        f"Benchmark: {benchmark.get('version', 'unknown')}",
        f"Scoring profile: {benchmark.get('scoring_profile', 'unknown')}",
        f"Total runs: {aggregate.get('total_runs', 0)}",
        f"Failure rate: {aggregate.get('failure_rate', 0.0)}",
        f"Primary metric: {PRIMARY_METRIC}",
        "",
        "Cell summaries:",
    ]
    by_run_group = aggregate.get("by_run_group", {})
    if isinstance(by_run_group, Mapping):
        for group_id, bucket in by_run_group.items():
            if isinstance(bucket, Mapping):
                lines.append(
                    f"{group_id}: runs={bucket.get('runs')} quality={bucket.get('quality_mean')} primary={bucket.get('quality_per_gpt55_impl_token_mean')}"
                )
    lines.append("")
    lines.append("Per-run quality:")
    for row in rows[:25]:
        lines.append(f"{row.get('run_id')}: quality={row.get('quality_score')} status={row.get('status')}")
    return lines


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _env_value(name: str) -> str | None:
    try:
        import os
    except ImportError:
        return None
    return os.environ.get(name)
