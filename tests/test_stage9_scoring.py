from __future__ import annotations

import json
from pathlib import Path

from harness.artifacts import validate_artifact
from harness.scoring import compute_run_score, write_run_score


def test_score_combines_components_and_efficiency_metrics(tmp_path: Path) -> None:
    run = _run(
        {
            "public_tests": 0.15,
            "hidden_tests": 0.45,
            "judge": 0.25,
            "typecheck": 0.10,
            "parity": 0.05,
        }
    )
    _write_json(tmp_path / "typecheck.meta.json", {"returncode": 0, "timed_out": False})
    _write_json(tmp_path / "public_ts.meta.json", {"returncode": 0, "timed_out": False})
    _write_json(tmp_path / "public_py.meta.json", {"returncode": 1, "timed_out": False})
    _write_json(
        tmp_path / "hidden-results.json",
        {
            "summary": {"score": 0.8},
            "categories": {"parity": {"score": 0.6}},
        },
    )
    _write_json(
        tmp_path / "judge.json",
        {
            "parsed": True,
            "value": {
                "correctness_score": 0.6,
                "parity_score": 0.8,
                "maintainability_score": 0.7,
                "test_evidence_score": 0.9,
            },
        },
    )
    _write_json(
        tmp_path / "usage.json",
        {
            "totals": {
                "implementation_tokens": 1000,
                "gpt55_implementation_tokens": 500,
                "gpt55_judge_inclusive_tokens": 800,
            }
        },
    )
    _write_json(tmp_path / "wall_time.json", {"elapsed_seconds": 120})
    _write_json(tmp_path / "judge.wall_time.json", {"elapsed_seconds": 30})
    _write_json(tmp_path / "state.json", {"phases": {}})
    (tmp_path / "diff-numstat.txt").write_text(
        "\n".join(
            [
                "100\t10\tsrc/index.ts",
                "20\t0\truleledger/engine.py",
                "5\t1\ttests_public_py/test_ruleledger.py",
                "3\t0\tREADME.md",
                "-\t-\tassets/logo.png",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    score = compute_run_score(tmp_path, run)
    score_path = tmp_path / "score.json"
    write_run_score(score_path, score)

    assert validate_artifact(score_path) == []
    assert score["component_scores"]["public_tests"] == 0.5
    assert score["component_scores"]["hidden_tests"] == 0.8
    assert score["component_scores"]["judge"] == 0.75
    assert score["component_scores"]["typecheck"] == 1.0
    assert score["component_scores"]["parity"] == 0.6
    assert score["quality_score"] == 0.7525
    assert score["efficiency"]["quality_per_gpt55_impl_token"] == 0.001505
    assert score["efficiency"]["quality_per_judge_inclusive_gpt55_token"] == 0.000940625
    assert score["efficiency"]["quality_per_total_impl_token"] == 0.0007525
    assert score["efficiency"]["quality_per_wall_clock_minute"] == 0.37625
    assert score["diff_stats"]["changed_files"] == 5
    assert score["diff_stats"]["insertions"] == 128
    assert score["diff_stats"]["deletions"] == 11
    assert score["diff_stats"]["binary_files"] == 1
    assert score["diff_stats"]["production_loc"] == 120
    assert score["diff_stats"]["test_loc"] == 5
    assert score["diff_stats"]["unclassified_loc"] == 3
    assert score["status"] == "partial"
    assert any("README.md" in warning for warning in score["warnings"])


def test_missing_and_malformed_artifacts_score_as_zero_with_warnings(tmp_path: Path) -> None:
    run = _run({"hidden_tests": 1.0, "mystery": 0.2})
    _write_json(tmp_path / "hidden-results.json", {"summary": {"point_score": 0.25}})
    _write_json(tmp_path / "wall_time.json", {"elapsed_seconds": 0})
    _write_json(tmp_path / "judge.wall_time.json", {"elapsed_seconds": 0})
    _write_json(tmp_path / "state.json", {"phases": {"judged": {"status": "failed"}}})
    (tmp_path / "judge.json").write_text("{not-json", encoding="utf-8")
    (tmp_path / "diff-numstat.txt").write_text("", encoding="utf-8")

    score = compute_run_score(tmp_path, run)

    assert score["component_scores"]["hidden_tests"] == 0.25
    assert score["component_scores"]["judge"] == 0.0
    assert score["quality_score"] == 0.25
    assert score["efficiency"]["quality_per_total_impl_token"] is None
    assert score["status"] == "partial"
    assert any("unknown scoring component 'mystery'" in warning for warning in score["warnings"])
    assert any("malformed JSON artifact: judge.json" in warning for warning in score["warnings"])
    assert any("missing artifact: usage.json" in warning for warning in score["warnings"])
    assert any("scoring weights sum to 1.200000" in warning for warning in score["warnings"])


def test_minimality_component_uses_configured_loc_threshold(tmp_path: Path) -> None:
    run = _run(
        {"minimality": 1.0},
        scoring_minimality={"target_production_loc": 10, "penalty_window": 10},
    )
    _write_json(tmp_path / "wall_time.json", {"elapsed_seconds": 0})
    _write_json(tmp_path / "judge.wall_time.json", {"elapsed_seconds": 0})
    _write_json(tmp_path / "state.json", {"phases": {}})
    (tmp_path / "diff-numstat.txt").write_text("15\t0\tsrc/index.ts\n", encoding="utf-8")

    score = compute_run_score(tmp_path, run)

    assert score["component_scores"]["minimality"] == 0.5
    assert score["quality_score"] == 0.5


def _run(weights: dict[str, float], *, scoring_minimality: dict[str, float] | None = None) -> dict[str, object]:
    return {
        "run_id": "R1",
        "cell_id": "C1",
        "spark_mode": "direct",
        "scoring_weights": weights,
        "scoring_minimality": scoring_minimality or {},
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")
