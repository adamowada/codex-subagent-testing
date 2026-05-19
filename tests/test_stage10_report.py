from __future__ import annotations

import json
from pathlib import Path

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
    ]
    for run in runs:
        _write_run_artifacts(tmp_path, run)

    monkeypatch.setenv("CODEX_REPORT_PDF_RENDERER", "minimal")
    outputs = write_results_outputs(tmp_path, runs)

    aggregate = json.loads(Path(outputs["aggregate_json"]).read_text(encoding="utf-8"))
    html = Path(outputs["report_html"]).read_text(encoding="utf-8")
    pdf_bytes = Path(outputs["report_pdf"]).read_bytes()

    assert aggregate["schema_version"] == 2
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
    assert "quality_per_gpt55_impl_token" in html


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
) -> dict[str, object]:
    run: dict[str, object] = {
        "run_id": run_id,
        "cell_id": cell_id,
        "cell_name": f"{cell_id}_cell",
        "repeat_index": 1,
        "topology": topology,
        "spark_mode": spark_mode,
        "root": {"model": "gpt-5.5", "reasoning": "xhigh" if cell_id in {"C0", "C4"} else "medium"},
        "agents": {"max_depth": 0 if topology == "solo" else 1, "max_threads": 1 if topology == "solo" else 8},
        "quality": quality,
        "gpt55_tokens": gpt55_tokens,
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
    _write_json(
        run_dir / "score.json",
        {
            "schema_version": 1,
            "status": "partial",
            "quality_score": quality,
            "component_scores": {
                "public_tests": quality,
                "hidden_tests": quality,
                "judge": quality,
                "typecheck": 1.0,
                "parity": quality,
                "minimality": 0.0,
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
