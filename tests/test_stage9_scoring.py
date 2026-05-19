from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from harness.artifacts import validate_artifact
from harness.scoring import compute_run_score, write_run_score


class Stage9ScoringTests(unittest.TestCase):
    def test_score_combines_components_and_efficiency_metrics(self) -> None:
        run = _run(
            {
                "public_tests": 0.15,
                "hidden_tests": 0.45,
                "judge": 0.25,
                "typecheck": 0.10,
                "parity": 0.05,
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            _write_json(run_dir / "typecheck.meta.json", {"returncode": 0, "timed_out": False})
            _write_json(run_dir / "public_ts.meta.json", {"returncode": 0, "timed_out": False})
            _write_json(run_dir / "public_py.meta.json", {"returncode": 1, "timed_out": False})
            _write_json(
                run_dir / "hidden-results.json",
                {
                    "summary": {"score": 0.8},
                    "categories": {"parity": {"score": 0.6}},
                },
            )
            _write_json(
                run_dir / "judge.json",
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
                run_dir / "usage.json",
                {
                    "totals": {
                        "implementation_tokens": 1000,
                        "gpt55_implementation_tokens": 500,
                        "gpt55_judge_inclusive_tokens": 800,
                    }
                },
            )
            _write_json(run_dir / "wall_time.json", {"elapsed_seconds": 120})
            _write_json(run_dir / "judge.wall_time.json", {"elapsed_seconds": 30})
            _write_json(run_dir / "state.json", {"phases": {}})
            (run_dir / "diff-numstat.txt").write_text(
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

            score = compute_run_score(run_dir, run)
            score_path = run_dir / "score.json"
            write_run_score(score_path, score)

            self.assertEqual(validate_artifact(score_path), [])

        self.assertEqual(score["component_scores"]["public_tests"], 0.5)
        self.assertEqual(score["component_scores"]["hidden_tests"], 0.8)
        self.assertEqual(score["component_scores"]["judge"], 0.75)
        self.assertEqual(score["component_scores"]["typecheck"], 1.0)
        self.assertEqual(score["component_scores"]["parity"], 0.6)
        self.assertEqual(score["quality_score"], 0.7525)
        self.assertEqual(score["efficiency"]["quality_per_gpt55_impl_token"], 0.001505)
        self.assertEqual(score["efficiency"]["quality_per_judge_inclusive_gpt55_token"], 0.000940625)
        self.assertEqual(score["efficiency"]["quality_per_total_impl_token"], 0.0007525)
        self.assertEqual(score["efficiency"]["quality_per_wall_clock_minute"], 0.37625)
        self.assertEqual(score["diff_stats"]["changed_files"], 5)
        self.assertEqual(score["diff_stats"]["insertions"], 128)
        self.assertEqual(score["diff_stats"]["deletions"], 11)
        self.assertEqual(score["diff_stats"]["binary_files"], 1)
        self.assertEqual(score["diff_stats"]["production_loc"], 120)
        self.assertEqual(score["diff_stats"]["test_loc"], 5)
        self.assertEqual(score["diff_stats"]["unclassified_loc"], 3)
        self.assertEqual(score["status"], "partial")
        self.assertTrue(any("README.md" in warning for warning in score["warnings"]))

    def test_missing_and_malformed_artifacts_score_as_zero_with_warnings(self) -> None:
        run = _run({"hidden_tests": 1.0, "mystery": 0.2})
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            _write_json(run_dir / "hidden-results.json", {"summary": {"point_score": 0.25}})
            _write_json(run_dir / "wall_time.json", {"elapsed_seconds": 0})
            _write_json(run_dir / "judge.wall_time.json", {"elapsed_seconds": 0})
            _write_json(run_dir / "state.json", {"phases": {"judged": {"status": "failed"}}})
            (run_dir / "judge.json").write_text("{not-json", encoding="utf-8")
            (run_dir / "diff-numstat.txt").write_text("", encoding="utf-8")

            score = compute_run_score(run_dir, run)

        self.assertEqual(score["component_scores"]["hidden_tests"], 0.25)
        self.assertEqual(score["component_scores"]["judge"], 0.0)
        self.assertEqual(score["quality_score"], 0.25)
        self.assertIsNone(score["efficiency"]["quality_per_total_impl_token"])
        self.assertEqual(score["status"], "partial")
        self.assertTrue(any("unknown scoring component 'mystery'" in warning for warning in score["warnings"]))
        self.assertTrue(any("malformed JSON artifact: judge.json" in warning for warning in score["warnings"]))
        self.assertTrue(any("missing artifact: usage.json" in warning for warning in score["warnings"]))
        self.assertTrue(any("scoring weights sum to 1.200000" in warning for warning in score["warnings"]))

    def test_minimality_component_uses_configured_loc_threshold(self) -> None:
        run = _run(
            {"minimality": 1.0},
            scoring_minimality={"target_production_loc": 10, "penalty_window": 10},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            _write_json(run_dir / "wall_time.json", {"elapsed_seconds": 0})
            _write_json(run_dir / "judge.wall_time.json", {"elapsed_seconds": 0})
            _write_json(run_dir / "state.json", {"phases": {}})
            (run_dir / "diff-numstat.txt").write_text("15\t0\tsrc/index.ts\n", encoding="utf-8")

            score = compute_run_score(run_dir, run)

        self.assertEqual(score["component_scores"]["minimality"], 0.5)
        self.assertEqual(score["quality_score"], 0.5)


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


if __name__ == "__main__":
    unittest.main()
