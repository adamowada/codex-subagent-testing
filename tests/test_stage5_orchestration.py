from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.codex_runner import build_implementation_command, build_judge_command
from harness.jsonl_usage import parse_usage_events, summarize_usage
from harness.matrix import expand_experiment_matrix, load_experiment_config
from harness.orchestrator import OrchestrationError, resolve_experiment_dir, select_runs, validate_resume_target
from harness.report_data import write_results_outputs


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "initial_experiment.yaml"


@pytest.fixture
def config() -> dict:
    return load_experiment_config(CONFIG_PATH)


@pytest.fixture
def runs(config: dict) -> list[dict]:
    return expand_experiment_matrix(config)


def test_pilot_selection_chooses_c0_and_c1_proposal(runs: list[dict]) -> None:
    selected = select_runs(runs, pilot=True)

    assert [run["run_id"] for run in selected] == ["C0_r01", "C1_proposal_r01"]


def test_run_id_selection_preserves_matrix_order(runs: list[dict]) -> None:
    selected = select_runs(runs, run_ids=["C2_proposal_r03", "C0_r02"])

    assert [run["run_id"] for run in selected] == ["C0_r02", "C2_proposal_r03"]


def test_experiment_directory_name_is_safe_and_unique(config: dict, tmp_path: Path) -> None:
    first = resolve_experiment_dir(
        runs_root=tmp_path,
        config=config,
        pilot=True,
        experiment_name="smoke test",
        resume=None,
    )
    first.mkdir(parents=True)
    second = resolve_experiment_dir(
        runs_root=tmp_path,
        config=config,
        pilot=True,
        experiment_name="smoke test",
        resume=None,
    )

    assert first != second
    assert " " not in first.name
    assert "pilot" in first.name


def test_resume_rejects_matrix_drift(config: dict, runs: list[dict], tmp_path: Path) -> None:
    selected = select_runs(runs, pilot=True)
    (tmp_path / "config.resolved.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (tmp_path / "matrix.json").write_text(json.dumps(selected, indent=2), encoding="utf-8")

    with pytest.raises(OrchestrationError, match="matrix drift"):
        validate_resume_target(tmp_path, config, runs[:1])


def test_implementation_command_contains_run_settings(runs: list[dict]) -> None:
    run = next(candidate for candidate in runs if candidate["run_id"] == "C4_direct_r01")
    command = build_implementation_command("codex", run, "prompt text")

    assert "--json" in command
    assert "--sandbox" in command
    assert "workspace-write" in command
    assert "--model" in command
    assert "gpt-5.5" in command
    assert "model_reasoning_effort=xhigh" in command
    assert "agents.max_depth=2" in command
    assert "agents.max_threads=24" in command
    assert command[-1] == "prompt text"


def test_judge_command_is_read_only_xhigh(runs: list[dict]) -> None:
    command = build_judge_command("codex", runs[0], "judge prompt")

    assert "read-only" in command
    assert "model_reasoning_effort=xhigh" in command
    assert command[-1] == "judge prompt"


def test_usage_parser_reads_turn_completed_usage(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
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

    assert len(events) == 1
    assert events[0]["input_tokens"] == 10
    assert events[0]["cached_input_tokens"] == 3
    assert events[0]["output_tokens"] == 5
    assert events[0]["reasoning_output_tokens"] == 2
    assert events[0]["total_tokens"] == 15


def test_usage_summary_marks_mixed_unattributed_runs_best_effort(runs: list[dict], tmp_path: Path) -> None:
    run = next(candidate for candidate in runs if candidate["run_id"] == "C1_direct_r01")
    impl = tmp_path / "events.jsonl"
    judge = tmp_path / "judge.events.jsonl"
    impl.write_text(json.dumps({"usage": {"input_tokens": 20, "output_tokens": 10}}) + "\n", encoding="utf-8")
    judge.write_text(json.dumps({"usage": {"input_tokens": 5, "output_tokens": 5}}) + "\n", encoding="utf-8")

    summary = summarize_usage(implementation_events_path=impl, judge_events_path=judge, run=run)

    assert summary["totals"]["implementation_tokens"] == 30
    assert summary["totals"]["judge_tokens"] == 10
    assert summary["attribution_method"] == "best_effort_total_as_gpt55_upper_bound"
    assert summary["warnings"]


def test_report_outputs_are_written_for_missing_scores(runs: list[dict], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    selected = select_runs(runs, pilot=True)
    monkeypatch.setenv("CODEX_REPORT_PDF_RENDERER", "minimal")

    outputs = write_results_outputs(tmp_path, selected)

    for path in outputs.values():
        assert Path(path).exists(), path

    aggregate = json.loads(Path(outputs["aggregate_json"]).read_text(encoding="utf-8"))
    assert aggregate["total_runs"] == 2
