from __future__ import annotations

import csv
import html
import json
from pathlib import Path
import sqlite3
from statistics import mean, median, stdev
from typing import Any, Iterable, Mapping


RESULT_COLUMNS = [
    "run_id",
    "cell_id",
    "cell_name",
    "topology",
    "spark_mode",
    "repeat_index",
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
    "run_dir",
]


def collect_result_rows(experiment_dir: str | Path, runs: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    root = Path(experiment_dir)
    rows: list[dict[str, Any]] = []
    for run in runs:
        run_id = str(run["run_id"])
        run_dir = root / "runs" / run_id
        score = _read_json(run_dir / "score.json")
        usage = _read_json(run_dir / "usage.json")
        totals = usage.get("totals", {}) if isinstance(usage.get("totals"), Mapping) else {}
        components = score.get("component_scores", {}) if isinstance(score.get("component_scores"), Mapping) else {}
        efficiency = score.get("efficiency", {}) if isinstance(score.get("efficiency"), Mapping) else {}
        diff_stats = score.get("diff_stats", {}) if isinstance(score.get("diff_stats"), Mapping) else {}
        wall_time = score.get("wall_time", {}) if isinstance(score.get("wall_time"), Mapping) else {}
        rows.append(
            {
                "run_id": run_id,
                "cell_id": run.get("cell_id"),
                "cell_name": run.get("cell_name"),
                "topology": run.get("topology"),
                "spark_mode": run.get("spark_mode") or "none",
                "repeat_index": run.get("repeat_index"),
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
                "run_dir": str(run_dir),
            }
        )
    return rows


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

    write_results_csv(csv_path, rows)
    write_results_sqlite(sqlite_path, rows)
    aggregate = aggregate_rows(rows)
    aggregate_path.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_html_report(html_path, rows, aggregate)
    write_minimal_pdf(pdf_path, _pdf_lines(rows, aggregate))

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
            writer.writerow(row)


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
    by_cell: dict[str, list[Mapping[str, Any]]] = {}
    by_mode: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        by_cell.setdefault(str(row.get("cell_id")), []).append(row)
        by_mode.setdefault(str(row.get("spark_mode")), []).append(row)

    return {
        "schema_version": 1,
        "total_runs": len(rows),
        "by_cell": {key: _aggregate_bucket(value) for key, value in sorted(by_cell.items())},
        "by_spark_mode": {key: _aggregate_bucket(value) for key, value in sorted(by_mode.items())},
        "failure_rate": _failure_rate(rows),
        "best_run": _best_run(rows),
    }


def write_html_report(path: str | Path, rows: list[Mapping[str, Any]], aggregate: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    body_rows = "\n".join(
        "<tr>"
        + "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in RESULT_COLUMNS[:14])
        + "</tr>"
        for row in rows
    )
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Codex Subagent Experiment Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; color: #202124; }}
    h1, h2 {{ margin-bottom: 0.35rem; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
    th, td {{ border: 1px solid #d0d7de; padding: 6px; text-align: left; }}
    th {{ background: #f6f8fa; }}
    code {{ background: #f6f8fa; padding: 1px 4px; }}
  </style>
</head>
<body>
  <h1>Codex Subagent Experiment Report</h1>
  <p>Total runs: {html.escape(str(aggregate.get("total_runs", 0)))}</p>
  <h2>Aggregate Results</h2>
  <pre>{html.escape(json.dumps(aggregate, indent=2, sort_keys=True))}</pre>
  <h2>Per-Run Rows</h2>
  <table>
    <thead><tr>{''.join(f'<th>{html.escape(column)}</th>' for column in RESULT_COLUMNS[:14])}</tr></thead>
    <tbody>{body_rows}</tbody>
  </table>
</body>
</html>
"""
    output.write_text(html_text, encoding="utf-8")


def write_minimal_pdf(path: str | Path, lines: list[str]) -> None:
    """Write a small valid PDF without external dependencies.

    Stage 10 can replace this with the styled Playwright renderer; Stage 5 only
    needs a durable PDF artifact for the end-to-end pipeline.
    """

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


def _aggregate_bucket(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    quality = [_float(row.get("quality_score")) for row in rows]
    hidden = [_float(row.get("hidden_tests")) for row in rows]
    tokens = [_float(row.get("gpt55_implementation_tokens")) for row in rows]
    return {
        "runs": len(rows),
        "quality_mean": round(mean(quality), 6) if quality else 0.0,
        "quality_median": round(median(quality), 6) if quality else 0.0,
        "quality_stdev": round(stdev(quality), 6) if len(quality) > 1 else 0.0,
        "hidden_mean": round(mean(hidden), 6) if hidden else 0.0,
        "gpt55_impl_tokens_mean": round(mean(tokens), 6) if tokens else 0.0,
        "failure_rate": _failure_rate(rows),
    }


def _failure_rate(rows: list[Mapping[str, Any]]) -> float:
    if not rows:
        return 0.0
    failures = sum(1 for row in rows if row.get("status") not in {"passed", "partial"})
    return round(failures / len(rows), 6)


def _best_run(rows: list[Mapping[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    best = max(rows, key=lambda row: _float(row.get("quality_score")))
    return {
        "run_id": best.get("run_id"),
        "cell_id": best.get("cell_id"),
        "quality_score": best.get("quality_score"),
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


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


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_lines(rows: list[Mapping[str, Any]], aggregate: Mapping[str, Any]) -> list[str]:
    lines = [
        "Codex Subagent Experiment Report",
        f"Total runs: {aggregate.get('total_runs', 0)}",
        f"Failure rate: {aggregate.get('failure_rate', 0.0)}",
        "",
        "Cell summaries:",
    ]
    by_cell = aggregate.get("by_cell", {})
    if isinstance(by_cell, Mapping):
        for cell_id, bucket in by_cell.items():
            if isinstance(bucket, Mapping):
                lines.append(
                    f"{cell_id}: runs={bucket.get('runs')} quality_mean={bucket.get('quality_mean')} hidden_mean={bucket.get('hidden_mean')}"
                )
    lines.append("")
    lines.append("Per-run quality:")
    for row in rows[:25]:
        lines.append(f"{row.get('run_id')}: quality={row.get('quality_score')} status={row.get('status')}")
    return lines
