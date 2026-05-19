from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from harness.artifacts import validate_artifact
from harness.jsonl_usage import parse_usage_events, parse_usage_file, summarize_usage
from harness.matrix import expand_experiment_matrix, load_experiment_config


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "initial_experiment.yaml"


class Stage8UsageParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_experiment_config(CONFIG_PATH)
        self.runs = expand_experiment_matrix(self.config)

    def test_parser_reads_supported_usage_shapes_and_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            _write_jsonl(
                path,
                [
                    {"usage": {"prompt_tokens": 10, "completion_tokens": 5}},
                    {
                        "turn": {
                            "usage": {
                                "input_tokens": 20,
                                "output_tokens": 8,
                                "input_tokens_details": {"cached_tokens": 6},
                            },
                            "model": "gpt-5.5",
                        }
                    },
                    {
                        "type": "turn.completed",
                        "turn": {
                            "completed": {
                                "usage": {
                                    "input_tokens": 7,
                                    "output_tokens": 3,
                                    "output_tokens_details": {"reasoning_tokens": 2},
                                },
                                "model": "gpt-5.3-codex-spark",
                            }
                        },
                    },
                ],
            )

            events = parse_usage_events(path)

        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["input_tokens"], 10)
        self.assertEqual(events[0]["output_tokens"], 5)
        self.assertEqual(events[1]["cached_input_tokens"], 6)
        self.assertEqual(events[1]["model"], "gpt-5.5")
        self.assertEqual(events[2]["reasoning_output_tokens"], 2)
        self.assertEqual(events[2]["model"], "gpt-5.3-codex-spark")

    def test_parse_result_warns_for_malformed_and_non_object_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            path.write_text('{"usage": {"input_tokens": 1, "output_tokens": 1}}\nnot-json\n[]\n', encoding="utf-8")

            result = parse_usage_file(path, label="Implementation")

        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.malformed_lines, 1)
        self.assertEqual(result.non_object_lines, 1)
        self.assertIn("Implementation JSONL skipped 1 malformed line(s).", result.warnings)
        self.assertIn("Implementation JSONL skipped 1 non-object line(s).", result.warnings)

    def test_summary_uses_exact_per_event_model_attribution(self) -> None:
        run = next(candidate for candidate in self.runs if candidate["run_id"] == "C1_direct_r01")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            impl = root / "events.jsonl"
            judge = root / "judge.events.jsonl"
            _write_jsonl(
                impl,
                [
                    {"model": "gpt-5.5", "usage": {"input_tokens": 10, "output_tokens": 5}},
                    {
                        "model": "gpt-5.3-codex-spark",
                        "usage": {"input_tokens": 20, "output_tokens": 10},
                    },
                ],
            )
            _write_jsonl(judge, [{"usage": {"input_tokens": 5, "output_tokens": 5}}])

            summary = summarize_usage(implementation_events_path=impl, judge_events_path=judge, run=run)

        self.assertEqual(summary["attribution_method"], "per_event_model")
        self.assertEqual(summary["totals"]["implementation_tokens"], 45)
        self.assertEqual(summary["totals"]["gpt55_implementation_tokens"], 15)
        self.assertEqual(summary["totals"]["spark_implementation_tokens"], 30)
        self.assertEqual(summary["totals"]["gpt55_judge_tokens"], 10)
        self.assertEqual(summary["totals"]["gpt55_judge_inclusive_tokens"], 25)

    def test_summary_warns_for_missing_jsonl_files(self) -> None:
        run = next(candidate for candidate in self.runs if candidate["run_id"] == "C0_r01")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = summarize_usage(
                implementation_events_path=root / "events.jsonl",
                judge_events_path=root / "judge.events.jsonl",
                run=run,
            )

        self.assertEqual(summary["totals"]["implementation_tokens"], 0)
        self.assertEqual(summary["totals"]["judge_tokens"], 0)
        self.assertEqual(summary["event_counts"]["implementation_usage_events"], 0)
        self.assertEqual(summary["attribution_method"], "unattributed_total")
        self.assertTrue(any("Implementation JSONL file is missing" in warning for warning in summary["warnings"]))
        self.assertTrue(any("Judge JSONL file is missing" in warning for warning in summary["warnings"]))

    def test_summary_marks_partial_model_attribution_as_best_effort(self) -> None:
        run = next(candidate for candidate in self.runs if candidate["run_id"] == "C1_direct_r01")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            impl = root / "events.jsonl"
            judge = root / "judge.events.jsonl"
            _write_jsonl(
                impl,
                [
                    {"model": "gpt-5.3-codex-spark", "usage": {"input_tokens": 5, "output_tokens": 5}},
                    {"usage": {"input_tokens": 20, "output_tokens": 10}},
                ],
            )
            _write_jsonl(judge, [{"usage": {"input_tokens": 1, "output_tokens": 1}}])

            summary = summarize_usage(implementation_events_path=impl, judge_events_path=judge, run=run)

        self.assertEqual(summary["attribution_method"], "partial_per_event_model_with_gpt55_upper_bound")
        self.assertEqual(summary["totals"]["gpt55_implementation_tokens"], 40)
        self.assertEqual(summary["totals"]["spark_implementation_tokens"], 10)
        self.assertEqual(summary["unattributed"]["implementation_tokens"], 30)
        self.assertTrue(any("some usage events only" in warning for warning in summary["warnings"]))

    def test_usage_artifact_validation_rejects_incomplete_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "usage.json"
            path.write_text('{"schema_version": 1}\n', encoding="utf-8")

            errors = validate_artifact(path)

        self.assertTrue(any("usage artifact missing key" in error for error in errors))


def _write_jsonl(path: Path, events: list[object]) -> None:
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

