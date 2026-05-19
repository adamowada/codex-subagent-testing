from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from harness.codex_runner import build_implementation_command, build_judge_command
from harness.jsonl_usage import parse_usage_events, summarize_usage
from harness.matrix import expand_experiment_matrix, load_experiment_config
from harness.orchestrator import OrchestrationError, resolve_experiment_dir, select_runs, validate_resume_target
from harness.report_data import write_results_outputs


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "initial_experiment.yaml"


class Stage5OrchestrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_experiment_config(CONFIG_PATH)
        self.runs = expand_experiment_matrix(self.config)

    def test_pilot_selection_chooses_c0_and_c1_proposal(self) -> None:
        selected = select_runs(self.runs, pilot=True)

        self.assertEqual([run["run_id"] for run in selected], ["C0_r01", "C1_proposal_r01"])

    def test_run_id_selection_preserves_matrix_order(self) -> None:
        selected = select_runs(self.runs, run_ids=["C2_proposal_r03", "C0_r02"])

        self.assertEqual([run["run_id"] for run in selected], ["C0_r02", "C2_proposal_r03"])

    def test_experiment_directory_name_is_safe_and_unique(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            first = resolve_experiment_dir(
                runs_root=runs_root,
                config=self.config,
                pilot=True,
                experiment_name="smoke test",
                resume=None,
            )
            first.mkdir(parents=True)
            second = resolve_experiment_dir(
                runs_root=runs_root,
                config=self.config,
                pilot=True,
                experiment_name="smoke test",
                resume=None,
            )

        self.assertNotEqual(first, second)
        self.assertNotIn(" ", first.name)
        self.assertIn("pilot", first.name)

    def test_resume_rejects_matrix_drift(self) -> None:
        selected = select_runs(self.runs, pilot=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            experiment_dir = Path(temp_dir)
            (experiment_dir / "config.resolved.json").write_text(
                json.dumps(self.config, indent=2),
                encoding="utf-8",
            )
            (experiment_dir / "matrix.json").write_text(
                json.dumps(selected, indent=2),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(OrchestrationError, "matrix drift"):
                validate_resume_target(experiment_dir, self.config, self.runs[:1])

    def test_implementation_command_contains_run_settings(self) -> None:
        run = next(candidate for candidate in self.runs if candidate["run_id"] == "C4_direct_r01")
        command = build_implementation_command("codex", run, "prompt text")

        self.assertIn("--json", command)
        self.assertIn("--sandbox", command)
        self.assertIn("workspace-write", command)
        self.assertIn("--model", command)
        self.assertIn("gpt-5.5", command)
        self.assertIn("model_reasoning_effort=xhigh", command)
        self.assertIn("agents.max_depth=2", command)
        self.assertIn("agents.max_threads=24", command)
        self.assertEqual(command[-1], "prompt text")

    def test_judge_command_is_read_only_xhigh(self) -> None:
        run = self.runs[0]
        command = build_judge_command("codex", run, "judge prompt")

        self.assertIn("read-only", command)
        self.assertIn("model_reasoning_effort=xhigh", command)
        self.assertEqual(command[-1], "judge prompt")

    def test_usage_parser_reads_turn_completed_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 10,
                            "cached_input_tokens": 3,
                            "output_tokens": 5,
                            "reasoning_output_tokens": 2,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            events = parse_usage_events(path)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["input_tokens"], 10)
        self.assertEqual(events[0]["cached_input_tokens"], 3)
        self.assertEqual(events[0]["output_tokens"], 5)
        self.assertEqual(events[0]["reasoning_output_tokens"], 2)
        self.assertEqual(events[0]["total_tokens"], 15)

    def test_usage_summary_marks_mixed_unattributed_runs_best_effort(self) -> None:
        run = next(candidate for candidate in self.runs if candidate["run_id"] == "C1_direct_r01")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            impl = root / "events.jsonl"
            judge = root / "judge.events.jsonl"
            impl.write_text(json.dumps({"usage": {"input_tokens": 20, "output_tokens": 10}}) + "\n", encoding="utf-8")
            judge.write_text(json.dumps({"usage": {"input_tokens": 5, "output_tokens": 5}}) + "\n", encoding="utf-8")

            summary = summarize_usage(implementation_events_path=impl, judge_events_path=judge, run=run)

        self.assertEqual(summary["totals"]["implementation_tokens"], 30)
        self.assertEqual(summary["totals"]["judge_tokens"], 10)
        self.assertEqual(summary["attribution_method"], "best_effort_total_as_gpt55_upper_bound")
        self.assertTrue(summary["warnings"])

    def test_report_outputs_are_written_for_missing_scores(self) -> None:
        selected = select_runs(self.runs, pilot=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            experiment_dir = Path(temp_dir)
            outputs = write_results_outputs(experiment_dir, selected)

            for path in outputs.values():
                self.assertTrue(Path(path).exists(), path)

            aggregate = json.loads(Path(outputs["aggregate_json"]).read_text(encoding="utf-8"))

        self.assertEqual(aggregate["total_runs"], 2)


if __name__ == "__main__":
    unittest.main()
