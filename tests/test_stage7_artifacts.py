from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from harness.artifacts import (
    CORE_RUN_ARTIFACTS,
    EXPERIMENT_OUTPUT_ARTIFACTS,
    PHASE_ARTIFACTS,
    phase_artifact_paths,
    validate_experiment_outputs,
    validate_hidden_artifact_privacy,
    validate_phase_artifacts,
)
from harness.matrix import expand_experiment_matrix, load_experiment_config
from harness.orchestrator import (
    OrchestrationError,
    phase_completed,
    render_artifacts,
    should_run_phase,
    validate_resume_target,
    write_experiment_metadata,
)
from harness.report_data import write_results_outputs


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "initial_experiment.yaml"


class Stage7ArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_experiment_config(CONFIG_PATH)
        self.runs = expand_experiment_matrix(self.config)

    def test_contract_names_include_stage7_core_outputs(self) -> None:
        for name in [
            "metadata.json",
            "rendered_prompt.md",
            "codex_config/config.toml",
            "events.jsonl",
            "stderr.log",
            "final_response.json",
            "wall_time.json",
            "public_ts.log",
            "typecheck.log",
            "public_py.log",
            "hidden-results.json",
            "judge.events.jsonl",
            "judge.stderr.log",
            "judge.json",
            "diff.patch",
            "diff-numstat.txt",
            "usage.json",
            "score.json",
        ]:
            self.assertIn(name, CORE_RUN_ARTIFACTS)

        self.assertEqual(
            EXPERIMENT_OUTPUT_ARTIFACTS,
            (
                "results/results.csv",
                "results/results.sqlite",
                "results/aggregate.json",
                "report/report.html",
                "report/report.pdf",
            ),
        )
        self.assertIn("implemented", PHASE_ARTIFACTS)
        self.assertIn("judged", PHASE_ARTIFACTS)

    def test_rendered_artifacts_validate_for_solo_and_spark_runs(self) -> None:
        selected = [
            next(run for run in self.runs if run["run_id"] == "C0_r01"),
            next(run for run in self.runs if run["run_id"] == "C4_direct_r01"),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            for run in selected:
                with self.subTest(run_id=run["run_id"]):
                    run_dir = Path(temp_dir) / run["run_id"]
                    render_artifacts(REPO_ROOT, run_dir, run)

                    self.assertEqual(validate_phase_artifacts(run_dir, "rendered"), [])

    def test_completed_phase_with_corrupt_json_artifact_is_not_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "events.jsonl").write_text('{"type":"event"}\n', encoding="utf-8")
            (run_dir / "stderr.log").write_text("", encoding="utf-8")
            (run_dir / "wall_time.json").write_text("{not-json", encoding="utf-8")
            (run_dir / "final_response.json").write_text(
                json.dumps({"parsed": False, "error": "no_strict_json_object_found"}),
                encoding="utf-8",
            )
            state = {"phases": {"implemented": {"status": "completed"}}}

            with self.assertRaisesRegex(OrchestrationError, "invalid JSON artifact"):
                should_run_phase(state, "implemented", run_dir / "events.jsonl", rerun_failed=False)

    def test_phase_completed_requires_artifact_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            score_path = run_dir / "score.json"
            score_path.write_text("{}", encoding="utf-8")
            state = {"phases": {"scored": {"status": "completed"}}}

            self.assertFalse(phase_completed(state, "scored", [score_path]))

    def test_hidden_result_privacy_validation_flags_private_payload_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            (run_dir / "hidden-results.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "cases": [
                            {
                                "id": "opaque-001",
                                "category": "normalization",
                                "input": {"raw_event": {"secret": True}},
                                "expected": {"ok": True},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "hidden-runner.log").write_text("completed\n", encoding="utf-8")

            errors = validate_hidden_artifact_privacy(run_dir)

        self.assertTrue(any("private key" in error for error in errors))

    def test_experiment_metadata_writes_stable_aliases_and_resume_reads_them(self) -> None:
        selected = self.runs[:2]
        args = SimpleNamespace(pilot=True, dry_run=True, jobs=1, judge_jobs=1)
        with tempfile.TemporaryDirectory() as temp_dir:
            experiment_dir = Path(temp_dir)
            write_experiment_metadata(
                experiment_dir=experiment_dir,
                config_path=CONFIG_PATH,
                config=self.config,
                all_runs=self.runs,
                selected_runs=selected,
                args=args,
            )
            (experiment_dir / "config.resolved.json").unlink()

            validate_resume_target(experiment_dir, self.config, selected)

            self.assertTrue((experiment_dir / "experiment_metadata.json").exists())
            self.assertTrue((experiment_dir / "experiment-metadata.json").exists())
            self.assertTrue((experiment_dir / "resolved_config.json").exists())

    def test_experiment_outputs_validate_after_report_generation(self) -> None:
        selected = self.runs[:2]
        with tempfile.TemporaryDirectory() as temp_dir:
            experiment_dir = Path(temp_dir)
            write_results_outputs(experiment_dir, selected)

            errors = validate_experiment_outputs(experiment_dir)

        self.assertEqual(errors, [])

    def test_phase_artifact_paths_are_rooted_in_run_dir(self) -> None:
        run_dir = Path("runs") / "experiment" / "runs" / "C0_r01"

        paths = phase_artifact_paths(run_dir, "judged")

        self.assertEqual(paths[0], run_dir / "judge.events.jsonl")


if __name__ == "__main__":
    unittest.main()
