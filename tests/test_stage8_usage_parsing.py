from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.artifacts import validate_artifact
from harness.jsonl_usage import parse_usage_events, parse_usage_file, summarize_usage
from harness.matrix import expand_experiment_matrix, load_experiment_config


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "initial_experiment.yaml"


@pytest.fixture
def runs() -> list[dict]:
    return expand_experiment_matrix(load_experiment_config(CONFIG_PATH))


def test_parser_reads_supported_usage_shapes_and_aliases(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
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

    assert len(events) == 3
    assert events[0]["input_tokens"] == 10
    assert events[0]["output_tokens"] == 5
    assert events[1]["cached_input_tokens"] == 6
    assert events[1]["model"] == "gpt-5.5"
    assert events[2]["reasoning_output_tokens"] == 2
    assert events[2]["model"] == "gpt-5.3-codex-spark"


def test_parse_result_warns_for_malformed_and_non_object_lines(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"usage": {"input_tokens": 1, "output_tokens": 1}}\nnot-json\n[]\n', encoding="utf-8")

    result = parse_usage_file(path, label="Implementation")

    assert len(result.events) == 1
    assert result.malformed_lines == 1
    assert result.non_object_lines == 1
    assert "Implementation JSONL skipped 1 malformed line(s)." in result.warnings
    assert "Implementation JSONL skipped 1 non-object line(s)." in result.warnings


def test_parser_preserves_total_tokens_only_usage_events(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    _write_jsonl(path, [{"usage": {"total_tokens": 42}}])

    events = parse_usage_events(path)

    assert len(events) == 1
    assert events[0]["input_tokens"] == 0
    assert events[0]["output_tokens"] == 0
    assert events[0]["total_tokens"] == 42


def test_parser_prefers_split_tokens_when_total_tokens_is_also_present(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    _write_jsonl(path, [{"usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 99}}])

    events = parse_usage_events(path)

    assert events[0]["total_tokens"] == 15


def test_summary_uses_exact_per_event_model_attribution(runs: list[dict], tmp_path: Path) -> None:
    run = next(candidate for candidate in runs if candidate["run_id"] == "C1_direct_r01")
    impl = tmp_path / "events.jsonl"
    judge = tmp_path / "judge.events.jsonl"
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

    assert summary["attribution_method"] == "per_event_model"
    assert summary["totals"]["implementation_tokens"] == 45
    assert summary["totals"]["gpt55_implementation_tokens"] == 15
    assert summary["totals"]["spark_implementation_tokens"] == 30
    assert summary["totals"]["gpt55_judge_tokens"] == 10
    assert summary["totals"]["gpt55_judge_inclusive_tokens"] == 25


def test_summary_warns_for_missing_jsonl_files(runs: list[dict], tmp_path: Path) -> None:
    run = next(candidate for candidate in runs if candidate["run_id"] == "C0_r01")

    summary = summarize_usage(
        implementation_events_path=tmp_path / "events.jsonl",
        judge_events_path=tmp_path / "judge.events.jsonl",
        run=run,
    )

    assert summary["totals"]["implementation_tokens"] == 0
    assert summary["totals"]["judge_tokens"] == 0
    assert summary["event_counts"]["implementation_usage_events"] == 0
    assert summary["attribution_method"] == "unattributed_total"
    assert any("Implementation JSONL file is missing" in warning for warning in summary["warnings"])
    assert any("Judge JSONL file is missing" in warning for warning in summary["warnings"])


def test_summary_marks_partial_model_attribution_as_best_effort(runs: list[dict], tmp_path: Path) -> None:
    run = next(candidate for candidate in runs if candidate["run_id"] == "C1_direct_r01")
    impl = tmp_path / "events.jsonl"
    judge = tmp_path / "judge.events.jsonl"
    _write_jsonl(
        impl,
        [
            {"model": "gpt-5.3-codex-spark", "usage": {"input_tokens": 5, "output_tokens": 5}},
            {"usage": {"input_tokens": 20, "output_tokens": 10}},
        ],
    )
    _write_jsonl(judge, [{"usage": {"input_tokens": 1, "output_tokens": 1}}])

    summary = summarize_usage(implementation_events_path=impl, judge_events_path=judge, run=run)

    assert summary["attribution_method"] == "partial_per_event_model_with_gpt55_upper_bound"
    assert summary["totals"]["gpt55_implementation_tokens"] == 40
    assert summary["totals"]["spark_implementation_tokens"] == 10
    assert summary["unattributed"]["implementation_tokens"] == 30
    assert any("some usage events only" in warning for warning in summary["warnings"])


def test_usage_artifact_validation_rejects_incomplete_summary(tmp_path: Path) -> None:
    path = tmp_path / "usage.json"
    path.write_text('{"schema_version": 1}\n', encoding="utf-8")

    errors = validate_artifact(path)

    assert any("usage artifact missing key" in error for error in errors)


def _write_jsonl(path: Path, events: list[object]) -> None:
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
