from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.codex_runner import ProcessResult, build_implementation_command, build_judge_command
from harness.jsonl_usage import parse_usage_events, summarize_usage
from harness.matrix import expand_experiment_matrix, load_experiment_config
from harness.orchestrator import (
    OrchestrationError,
    capture_diff,
    configure_worktree_git_excludes,
    initialize_git_baseline,
    prepare_judge_evidence,
    run_hidden_tests,
    resolve_experiment_dir,
    run_parallel,
    select_runs,
    validate_resume_target,
)
from harness.prompt_rendering import render_codex_config
from harness.report_data import write_results_outputs


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "initial_experiment.yaml"
SOLO_REASONING_CONFIG_PATH = REPO_ROOT / "configs" / "c5_c7_solo_reasoning.yaml"
RULELEDGER_V2_PILOT_CONFIG_PATH = REPO_ROOT / "configs" / "ruleledger_v2_pilot.yaml"


@pytest.fixture
def config() -> dict:
    return load_experiment_config(CONFIG_PATH)


@pytest.fixture
def runs(config: dict) -> list[dict]:
    return expand_experiment_matrix(config)


def test_pilot_selection_chooses_c0_and_c1_proposal(runs: list[dict]) -> None:
    selected = select_runs(runs, pilot=True)

    assert [run["run_id"] for run in selected] == ["C0_r01", "C1_proposal_r01"]


def test_pilot_selection_handles_solo_only_matrix() -> None:
    solo_runs = expand_experiment_matrix(load_experiment_config(SOLO_REASONING_CONFIG_PATH))

    selected = select_runs(solo_runs, pilot=True)

    assert [run["run_id"] for run in selected] == ["C5_r01", "C6_r01"]


def test_pilot_selection_uses_v2_calibration_runs() -> None:
    v2_runs = expand_experiment_matrix(load_experiment_config(RULELEDGER_V2_PILOT_CONFIG_PATH))

    selected = select_runs(v2_runs, pilot=True)

    assert [run["run_id"] for run in selected] == ["V2P0_r01", "V2P1_proposal_r01"]
    assert [run["root"]["reasoning"] for run in selected] == ["low", "xhigh"]
    assert [run["spark_mode"] for run in selected] == [None, "proposal"]


def test_run_id_selection_preserves_matrix_order(runs: list[dict]) -> None:
    selected = select_runs(runs, run_ids=["C2_proposal_r03", "C0_r02"])

    assert [run["run_id"] for run in selected] == ["C0_r02", "C2_proposal_r03"]


def test_run_parallel_prints_incremental_progress(capsys: pytest.CaptureFixture[str]) -> None:
    runs = [{"run_id": "R1"}, {"run_id": "R2"}]

    failures = run_parallel(runs, max_workers=1, label="implementation", worker=lambda run: None)

    output = capsys.readouterr().out
    assert failures == []
    assert "implementation started: R1" in output
    assert "implementation 1/2 completed: R1" in output
    assert "implementation started: R2" in output
    assert "implementation 2/2 completed: R2" in output


def test_run_parallel_prints_failure_progress(capsys: pytest.CaptureFixture[str]) -> None:
    runs = [{"run_id": "R1"}]

    def fail(_: dict) -> None:
        raise RuntimeError("boom")

    failures = run_parallel(runs, max_workers=1, label="judge", worker=fail)

    output = capsys.readouterr().out
    assert failures == [{"run_id": "R1", "phase": "judge", "error": "boom"}]
    assert "judge started: R1" in output
    assert "judge 1/1 failed: R1" in output
    assert "boom" in output


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

    assert command[:4] == ["codex", "--ask-for-approval", "never", "exec"]
    assert "--json" in command
    assert "--sandbox" in command
    assert "workspace-write" in command
    assert "--model" in command
    assert "gpt-5.5" in command
    assert 'model_reasoning_effort="xhigh"' in command
    assert "agents.max_depth=2" in command
    assert "agents.max_threads=24" in command
    assert command[-1] == "prompt text"


def test_solo_command_preserves_configured_zero_agent_depth(runs: list[dict]) -> None:
    command = build_implementation_command("codex", runs[0], "prompt text")

    assert "agents.max_depth=0" in command


def test_implementation_command_uses_rendered_agent_config(runs: list[dict], tmp_path: Path) -> None:
    run = next(candidate for candidate in runs if candidate["run_id"] == "C1_direct_r01")
    config_dir = tmp_path / "codex_config"
    for relative_path, contents in render_codex_config(run, REPO_ROOT).items():
        path = config_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    command = build_implementation_command("codex", run, "prompt text", config_dir=config_dir)

    assert "agents.spark_direct_implementer.config_file" in "\n".join(command)
    assert "spark_direct_implementer.toml" in "\n".join(command)
    assert "agents.spark_direct_implementer.sandbox=\"workspace-write\"" in command


def test_judge_command_is_read_only_xhigh(runs: list[dict]) -> None:
    command = build_judge_command("codex", runs[0], "judge prompt")

    assert command[:4] == ["codex", "--ask-for-approval", "never", "exec"]
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


def test_capture_diff_includes_untracked_files(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    run_dir = tmp_path / "run"
    (worktree / "src").mkdir(parents=True)
    (worktree / "src" / "existing.ts").write_text("export const before = true;\n", encoding="utf-8")
    baseline = initialize_git_baseline(worktree)
    (run_dir).mkdir()
    (run_dir / "metadata.json").write_text(json.dumps({"baseline_commit": baseline}), encoding="utf-8")

    (worktree / "src" / "new_file.ts").write_text("export const after = true;\n", encoding="utf-8")
    (worktree / "dist").mkdir()
    (worktree / "dist" / "index.js").write_text("generated\n", encoding="utf-8")
    (worktree / "node_modules").mkdir()
    (worktree / "node_modules" / "package.js").write_text("generated\n", encoding="utf-8")
    capture_diff(run_dir, worktree)

    diff = (run_dir / "diff.patch").read_text(encoding="utf-8")
    numstat = (run_dir / "diff-numstat.txt").read_text(encoding="utf-8")
    assert "src/new_file.ts" in diff
    assert "src/new_file.ts" in numstat
    assert "dist/index.js" not in diff
    assert "node_modules/package.js" not in diff


def test_configure_worktree_git_excludes_is_idempotent(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / "README.md").write_text("baseline\n", encoding="utf-8")
    initialize_git_baseline(worktree)

    configure_worktree_git_excludes(worktree)
    configure_worktree_git_excludes(worktree)

    exclude_text = (worktree / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert exclude_text.count("node_modules") == 1
    assert "pytest-cache-files-*" in exclude_text


def test_prepare_judge_evidence_copies_sanitized_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    run_dir.mkdir()
    (run_dir / "hidden-results.json").write_text(
        json.dumps({"schema_version": 1, "summary": {"score": 0.5}, "cases": []}),
        encoding="utf-8",
    )
    (run_dir / "public_py.log").write_text("public output\n", encoding="utf-8")
    (run_dir / "metadata.json").write_text(json.dumps({"cell_id": "C4"}), encoding="utf-8")

    prepare_judge_evidence(run_dir, worktree)

    evidence = worktree / "judge_evidence"
    assert (evidence / "hidden-results.json").exists()
    assert (evidence / "public_py.log").read_text(encoding="utf-8") == "public output\n"
    assert (evidence / "evidence-manifest.json").exists()
    assert not (evidence / "manifest.json").exists()
    assert not (evidence / "metadata.json").exists()


def test_hidden_runner_outer_timeout_uses_implementation_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_logged_command(command, *, cwd, log_path, timeout_seconds, env=None):
        captured["timeout_seconds"] = timeout_seconds
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("hidden runner log\n", encoding="utf-8")
        return ProcessResult(
            command=list(command),
            command_display=list(command),
            cwd=str(cwd),
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            elapsed_seconds=1.0,
            returncode=0,
            timed_out=False,
            log_path=str(log_path),
        )

    monkeypatch.setattr("harness.orchestrator.run_logged_command", fake_run_logged_command)
    run_hidden_tests(
        REPO_ROOT,
        tmp_path / "worktree",
        tmp_path / "run",
        {
            "timeouts": {"implementation_seconds": 1800},
            "benchmark": {"hidden_cases_path": "hidden_tests/cases_v2"},
        },
    )

    assert captured["timeout_seconds"] == 1800
