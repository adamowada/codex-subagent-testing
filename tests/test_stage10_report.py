from __future__ import annotations

import csv
import json
from pathlib import Path
import sqlite3

import pytest

from harness.report_data import aggregate_rows, collect_result_rows, render_html_report, write_results_outputs


def test_report_contains_required_sections_and_primary_ranking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs = [
        _run("C0_r01", "C0", None, quality=0.9, gpt55_tokens=900, topology="solo"),
        _run("C1_direct_r01", "C1", "direct", quality=0.8, gpt55_tokens=400),
        _run("C1_proposal_r01", "C1", "proposal", quality=0.7, gpt55_tokens=700),
        _run("C4_direct_r01", "C4", "direct", quality=0.5, gpt55_tokens=1000),
    ]
    for run in runs:
        _write_run_artifacts(tmp_path, run)

    monkeypatch.setenv("CODEX_REPORT_PDF_RENDERER", "minimal")
    outputs = write_results_outputs(tmp_path, runs)

    aggregate = json.loads(Path(outputs["aggregate_json"]).read_text(encoding="utf-8"))
    html = Path(outputs["report_html"]).read_text(encoding="utf-8")
    pdf_bytes = Path(outputs["report_pdf"]).read_bytes()

    assert aggregate["schema_version"] == 2
    assert aggregate["benchmark"]["version"] == "ruleledger_v1"
    assert aggregate["rankings"]["primary_by_run_group"][0]["group_id"] == "C1:direct"
    assert aggregate["direct_proposal_deltas"]["C1"]["direct_minus_proposal"]["quality_mean"] == pytest.approx(0.1)
    assert aggregate["report_generation"]["pdf"]["renderer"] == "minimal"
    assert pdf_bytes.startswith(b"%PDF-1.4")
    for section in [
        "Abstract",
        "Methods",
        "Benchmark Task",
        "Experiment Matrix",
        "Results",
        "Direct Edit Versus Proposal-Only Comparison",
        "C4 Stress-Test Analysis",
        "Token Attribution Notes",
        "Limitations",
        "Appendix: Per-Run Rows And Artifact Paths",
    ]:
        assert section in html
    assert "C1 direct" in html
    assert "ruleledger_v1" in html
    assert "quality_per_gpt55_impl_token" in html


def test_report_omits_c4_section_when_c4_is_not_selected() -> None:
    runs = [
        _run("C5_r01", "C5", None, quality=0.7, gpt55_tokens=500, topology="solo"),
        _run("C6_r01", "C6", None, quality=0.8, gpt55_tokens=600, topology="solo"),
    ]
    rows = []
    for run in runs:
        rows.append(
            {
                "run_id": run["run_id"],
                "cell_id": run["cell_id"],
                "cell_name": run["cell_name"],
                "topology": run["topology"],
                "spark_mode": "none",
                "repeat_index": run["repeat_index"],
                "quality_score": run["quality"],
                "hidden_tests": run["quality"],
                "gpt55_implementation_tokens": run["gpt55_tokens"],
                "quality_per_gpt55_impl_token": float(run["quality"]) / float(run["gpt55_tokens"]),
                "implementation_elapsed_seconds": 120.0,
                "failure_phase": "",
                "artifact_status": "complete",
                "root_model": "gpt-5.5",
                "root_reasoning": run["root"]["reasoning"],
                "max_depth": 0,
                "max_threads": 1,
            }
        )

    html = render_html_report(rows, aggregate_rows(rows))

    assert "C4 Stress-Test Analysis" not in html


def test_missing_score_rows_remain_visible_with_attribution_warnings(tmp_path: Path) -> None:
    runs = [_run("C1_direct_r01", "C1", "direct", quality=0.0, gpt55_tokens=0)]
    run_dir = tmp_path / "runs" / "C1_direct_r01"
    run_dir.mkdir(parents=True)
    _write_json(
        run_dir / "usage.json",
        {
            "schema_version": 1,
            "totals": {
                "implementation_tokens": 100,
                "judge_tokens": 25,
                "gpt55_implementation_tokens": 100,
            },
            "attribution_method": "best_effort_total_as_gpt55_upper_bound",
            "warnings": ["Implementation JSONL did not expose per-model attribution."],
        },
    )

    rows = collect_result_rows(tmp_path, runs)
    aggregate = aggregate_rows(rows)
    html = render_html_report(rows, aggregate)

    assert rows[0]["status"] == "missing_score"
    assert rows[0]["artifact_status"] == "missing_score"
    assert aggregate["token_attribution"]["best_effort_runs"] == 1
    assert "missing_score" in html
    assert "best_effort_total_as_gpt55_upper_bound" in html
    assert "Implementation JSONL did not expose per-model attribution." in html


def test_failure_rate_counts_preserved_failed_phases() -> None:
    rows = [
        {"run_id": "ok", "status": "partial", "artifact_status": "complete", "failure_phase": ""},
        {"run_id": "failed", "status": "partial", "artifact_status": "complete", "failure_phase": "judged"},
        {"run_id": "missing", "status": "missing_score", "artifact_status": "missing_score", "failure_phase": ""},
    ]

    aggregate = aggregate_rows(rows)

    assert aggregate["failure_rate"] == pytest.approx(2 / 3)


def test_v2_report_includes_category_performance_and_root_spread(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs = [
        _run(
            "V2C0_r01",
            "V2C0",
            None,
            quality=0.65,
            gpt55_tokens=1000,
            topology="solo",
            benchmark_version="ruleledger_v2",
            scoring_profile="starter_quality_v2",
            root_reasoning="xhigh",
            components={
                "public_tests": 1.0,
                "hidden_tests": 0.7,
                "hidden_correctness": 0.6,
                "hidden_parity": 0.5,
                "performance": 0.75,
                "judge": 0.8,
                "typecheck": 1.0,
                "parity": 0.5,
                "minimality": 1.0,
            },
            hidden_category_scores={
                "normalization": 1.0,
                "bitemporal_replay": 0.2,
                "parity": 0.5,
                "performance": 0.75,
            },
            hidden_results={
                "schema_version": 1,
                "cases": [
                    {"category": "performance", "status": "passed", "reason": "ok"},
                    {"category": "performance", "status": "failed", "reason": "timeout"},
                ],
            },
        ),
        _run(
            "V2C1_r01",
            "V2C1",
            None,
            quality=0.45,
            gpt55_tokens=900,
            topology="solo",
            benchmark_version="ruleledger_v2",
            scoring_profile="starter_quality_v2",
            root_reasoning="medium",
            components={
                "public_tests": 1.0,
                "hidden_tests": 0.5,
                "hidden_correctness": 0.4,
                "hidden_parity": 0.5,
                "performance": 0.5,
                "judge": 0.6,
                "typecheck": 0.0,
                "parity": 0.5,
                "minimality": 1.0,
            },
            hidden_category_scores={
                "normalization": 1.0,
                "bitemporal_replay": 0.6,
                "parity": 0.5,
                "performance": 0.5,
            },
            hidden_results={
                "schema_version": 1,
                "cases": [
                    {"category": "performance", "status": "passed", "reason": "ok"},
                    {"category": "performance", "status": "passed", "reason": "ok"},
                ],
            },
        ),
    ]
    for run in runs:
        _write_run_artifacts(tmp_path, run)

    rows = collect_result_rows(tmp_path, runs)
    assert rows[0]["performance_pass_rate"] == 0.5
    assert rows[0]["performance_timeout_rate"] == 0.5
    assert rows[0]["category_saturation"]["saturated"] == ["normalization"]

    monkeypatch.setenv("CODEX_REPORT_PDF_RENDERER", "minimal")
    outputs = write_results_outputs(tmp_path, runs)
    aggregate = json.loads(Path(outputs["aggregate_json"]).read_text(encoding="utf-8"))
    html = Path(outputs["report_html"]).read_text(encoding="utf-8")

    assert aggregate["v2"]["runs"] == 2
    assert aggregate["v2"]["category_means"]["normalization"] == 1.0
    assert aggregate["v2"]["category_saturation"]["saturated"] == ["normalization"]
    assert aggregate["v2"]["performance"]["score_mean"] == pytest.approx(0.625)
    assert aggregate["v2"]["performance"]["pass_rate_mean"] == pytest.approx(0.75)
    assert aggregate["v2"]["performance"]["timeout_rate_mean"] == pytest.approx(0.25)
    assert aggregate["v2"]["spread_by_root_reasoning"]["xhigh"]["hidden_correctness_mean"] == 0.6
    assert "V2 Scoring Profile" in html
    assert "Hidden Category Calibration" in html
    assert "Performance And Timeout Behavior" in html
    assert "public_tests_gate" in html
    assert "typecheck_gate" in html

    with Path(outputs["results_csv"]).open(encoding="utf-8", newline="") as handle:
        csv_columns = next(csv.reader(handle))
    assert "hidden_correctness" in csv_columns
    assert "performance_pass_rate" in csv_columns

    with sqlite3.connect(outputs["results_sqlite"]) as connection:
        sqlite_columns = {row[1] for row in connection.execute("PRAGMA table_info(results)")}
    assert {"hidden_correctness", "performance_pass_rate", "hidden_category_scores"} <= sqlite_columns


def test_mixed_benchmark_reports_are_labeled_instead_of_silent() -> None:
    rows = [
        {
            "run_id": "C0_r01",
            "cell_id": "C0",
            "spark_mode": "none",
            "benchmark_version": "ruleledger_v1",
            "quality_score": 0.8,
            "hidden_tests": 0.8,
            "gpt55_implementation_tokens": 100,
            "quality_per_gpt55_impl_token": 0.008,
            "artifact_status": "complete",
            "failure_phase": "",
        },
        {
            "run_id": "V2C0_r01",
            "cell_id": "V2C0",
            "spark_mode": "none",
            "benchmark_version": "ruleledger_v2",
            "quality_score": 0.7,
            "hidden_tests": 0.7,
            "hidden_correctness": 0.6,
            "performance": 0.5,
            "gpt55_implementation_tokens": 100,
            "quality_per_gpt55_impl_token": 0.007,
            "artifact_status": "complete",
            "failure_phase": "",
        },
    ]

    aggregate = aggregate_rows(rows)
    html = render_html_report(rows, aggregate)

    assert aggregate["cross_version"]["mode"] == "mixed_versions_labeled"
    assert aggregate["rankings"]["primary_by_run_group"][0]["group_id"].startswith("ruleledger_v1/")
    assert "Cross-Version Selection" in html


def test_pdf_renderer_disables_browser_header_footer() -> None:
    renderer = Path(__file__).resolve().parents[1] / "scripts" / "render_report_pdf.mjs"

    assert "displayHeaderFooter: false" in renderer.read_text(encoding="utf-8")


def _run(
    run_id: str,
    cell_id: str,
    spark_mode: str | None,
    *,
    quality: float,
    gpt55_tokens: int,
    topology: str = "flat_spark",
    benchmark_version: str = "ruleledger_v1",
    scoring_profile: str = "initial_quality_v1",
    root_reasoning: str | None = None,
    components: dict[str, float] | None = None,
    hidden_category_scores: dict[str, float] | None = None,
    hidden_results: dict[str, object] | None = None,
) -> dict[str, object]:
    run: dict[str, object] = {
        "run_id": run_id,
        "cell_id": cell_id,
        "cell_name": f"{cell_id}_cell",
        "repeat_index": 1,
        "topology": topology,
        "spark_mode": spark_mode,
        "root": {"model": "gpt-5.5", "reasoning": root_reasoning or ("xhigh" if cell_id in {"C0", "C4"} else "medium")},
        "agents": {"max_depth": 0 if topology == "solo" else 1, "max_threads": 1 if topology == "solo" else 8},
        "benchmark": {
            "version": benchmark_version,
            "template_path": "benchmark_template_v2" if benchmark_version == "ruleledger_v2" else "benchmark_template",
            "hidden_cases_path": "hidden_tests/cases_v2" if benchmark_version == "ruleledger_v2" else "hidden_tests/cases",
            "scoring_path": "configs/scoring_v2.yaml" if benchmark_version == "ruleledger_v2" else "configs/scoring.yaml",
            "scoring_profile": scoring_profile,
        },
        "quality": quality,
        "gpt55_tokens": gpt55_tokens,
        "components": components or {},
        "hidden_category_scores": hidden_category_scores or {},
        "hidden_results": hidden_results or {},
    }
    if topology != "solo":
        run["leaf"] = {
            "model": "gpt-5.3-codex-spark",
            "count": 6,
            "reasoning_by_role": {"implementer": "xhigh", "tester": "xhigh", "adversary": "xhigh"},
        }
    return run


def _write_run_artifacts(experiment_dir: Path, run: dict[str, object]) -> None:
    run_dir = experiment_dir / "runs" / str(run["run_id"])
    run_dir.mkdir(parents=True)
    quality = float(run["quality"])
    gpt55_tokens = int(run["gpt55_tokens"])
    implementation_tokens = max(gpt55_tokens, 1)
    components = run.get("components") if isinstance(run.get("components"), dict) else {}
    if not components:
        components = {
            "public_tests": quality,
            "hidden_tests": quality,
            "judge": quality,
            "typecheck": 1.0,
            "parity": quality,
            "minimality": 0.0,
        }
    hidden_category_scores = run.get("hidden_category_scores") if isinstance(run.get("hidden_category_scores"), dict) else {}
    hidden_results = run.get("hidden_results") if isinstance(run.get("hidden_results"), dict) else {}
    _write_json(
        run_dir / "score.json",
        {
            "schema_version": 1,
            "status": "partial",
            "quality_score": quality,
            "component_scores": components,
            "hidden_category_scores": hidden_category_scores,
            "performance_summary": {
                "category": "performance",
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "pass_rate": None,
                "timeout_rate": None,
            },
            "gate_scores": {
                "public_tests": components.get("public_tests", 0.0),
                "typecheck": components.get("typecheck", 0.0),
            },
            "efficiency": {
                "quality_per_gpt55_impl_token": round(quality / implementation_tokens, 12),
                "quality_per_judge_inclusive_gpt55_token": round(quality / (implementation_tokens + 100), 12),
                "quality_per_total_impl_token": round(quality / implementation_tokens, 12),
                "quality_per_wall_clock_minute": quality,
            },
            "diff_stats": {
                "changed_files": 2,
                "insertions": 120,
                "deletions": 10,
                "binary_files": 0,
                "production_loc": 90,
                "test_loc": 30,
            },
            "wall_time": {"implementation_elapsed_seconds": 120.0, "judge_elapsed_seconds": 20.0},
            "warnings": [],
        },
    )
    if hidden_results:
        _write_json(run_dir / "hidden-results.json", hidden_results)
    _write_json(
        run_dir / "usage.json",
        {
            "schema_version": 1,
            "implementation": {"total_tokens": implementation_tokens},
            "judge": {"total_tokens": 100},
            "totals": {
                "implementation_tokens": implementation_tokens,
                "judge_tokens": 100,
                "gpt55_implementation_tokens": gpt55_tokens,
            },
            "attribution_method": "per_event_model",
            "warnings": [],
        },
    )
    _write_json(run_dir / "state.json", {"schema_version": 1, "phases": {}})


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")
