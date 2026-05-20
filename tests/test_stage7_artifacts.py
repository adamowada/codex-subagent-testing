from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness.artifacts import (
    CORE_RUN_ARTIFACTS,
    EXPERIMENT_OUTPUT_ARTIFACTS,
    PHASE_ARTIFACTS,
    phase_artifact_paths,
    validate_experiment_outputs,
    validate_hidden_artifact_privacy,
    validate_phase_artifacts,
    validate_run_metadata,
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


@pytest.fixture
def config() -> dict:
    return load_experiment_config(CONFIG_PATH)


@pytest.fixture
def runs(config: dict) -> list[dict]:
    return expand_experiment_matrix(config)


def test_contract_names_include_stage7_core_outputs() -> None:
    for name in [
        "worktree.json",
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
        assert name in CORE_RUN_ARTIFACTS

    assert EXPERIMENT_OUTPUT_ARTIFACTS == (
        "results/results.csv",
        "results/results.sqlite",
        "results/aggregate.json",
        "report/report.html",
        "report/report.pdf",
    )
    assert "implemented" in PHASE_ARTIFACTS
    assert "judged" in PHASE_ARTIFACTS


def test_rendered_artifacts_validate_for_solo_and_spark_runs(runs: list[dict], tmp_path: Path) -> None:
    selected = [
        next(run for run in runs if run["run_id"] == "C0_r01"),
        next(run for run in runs if run["run_id"] == "C4_direct_r01"),
    ]
    for run in selected:
        run_dir = tmp_path / run["run_id"]
        render_artifacts(REPO_ROOT, run_dir, run)

        assert validate_phase_artifacts(run_dir, "rendered") == []


def test_completed_phase_with_corrupt_json_artifact_is_not_skipped(tmp_path: Path) -> None:
    run_dir = tmp_path
    (run_dir / "events.jsonl").write_text('{"type":"event"}\n', encoding="utf-8")
    (run_dir / "stderr.log").write_text("", encoding="utf-8")
    (run_dir / "wall_time.json").write_text("{not-json", encoding="utf-8")
    (run_dir / "final_response.json").write_text(
        json.dumps({"parsed": False, "error": "no_strict_json_object_found"}),
        encoding="utf-8",
    )
    state = {"phases": {"implemented": {"status": "completed"}}}

    with pytest.raises(OrchestrationError, match="invalid JSON artifact"):
        should_run_phase(state, "implemented", run_dir / "events.jsonl", rerun_failed=False)


def test_phase_completed_requires_artifact_validation(tmp_path: Path) -> None:
    score_path = tmp_path / "score.json"
    score_path.write_text("{}", encoding="utf-8")
    state = {"phases": {"scored": {"status": "completed"}}}

    assert not phase_completed(state, "scored", [score_path])


def test_hidden_result_privacy_validation_flags_private_payload_keys(tmp_path: Path) -> None:
    (tmp_path / "hidden-results.json").write_text(
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
    (tmp_path / "hidden-runner.log").write_text("completed\n", encoding="utf-8")

    errors = validate_hidden_artifact_privacy(tmp_path)

    assert any("private key" in error for error in errors)


def test_hidden_result_artifact_rejects_descriptive_case_metadata(tmp_path: Path) -> None:
    path = tmp_path / "hidden-results.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "summary": {"score": 0.0},
                "cases": [
                    {
                        "id": "parse.invalid-json",
                        "category": "parse_validation",
                        "language": "python",
                        "operation": "parse_line",
                        "source_file": "parse_validation.json",
                        "status": "failed",
                        "points_earned": 0.0,
                        "points_possible": 1.0,
                        "reason": "output_mismatch",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    errors = validate_phase_artifacts(tmp_path, "hidden_tested")

    assert any("id is not opaque" in error for error in errors)
    assert any("operation" in error for error in errors)
    assert any("source_file" in error for error in errors)


def test_experiment_metadata_writes_stable_aliases_and_resume_reads_them(
    config: dict,
    runs: list[dict],
    tmp_path: Path,
) -> None:
    selected = runs[:2]
    args = SimpleNamespace(pilot=True, dry_run=True, jobs=1, judge_jobs=1)
    write_experiment_metadata(
        experiment_dir=tmp_path,
        config_path=CONFIG_PATH,
        config=config,
        all_runs=runs,
        selected_runs=selected,
        args=args,
    )
    (tmp_path / "config.resolved.json").unlink()

    validate_resume_target(tmp_path, config, selected)

    assert (tmp_path / "experiment_metadata.json").exists()
    assert (tmp_path / "experiment-metadata.json").exists()
    assert (tmp_path / "resolved_config.json").exists()
    metadata = json.loads((tmp_path / "experiment_metadata.json").read_text(encoding="utf-8"))
    assert metadata["benchmark"]["version"] == "ruleledger_v1"


def test_run_metadata_validation_accepts_defaulted_benchmark_for_legacy_run(tmp_path: Path) -> None:
    run = {"run_id": "legacy_r01"}
    (tmp_path / "metadata.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": "legacy_r01",
                "run": run,
                "benchmark": {
                    "version": "ruleledger_v1",
                    "template_path": "benchmark_template",
                    "hidden_cases_path": "hidden_tests/cases",
                    "scoring_path": "",
                    "scoring_profile": "",
                },
            }
        ),
        encoding="utf-8",
    )

    assert validate_run_metadata(tmp_path, run) == []


def test_experiment_outputs_validate_after_report_generation(
    runs: list[dict],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = runs[:2]
    monkeypatch.setenv("CODEX_REPORT_PDF_RENDERER", "minimal")
    write_results_outputs(tmp_path, selected)

    errors = validate_experiment_outputs(tmp_path)

    assert errors == []


def test_phase_artifact_paths_are_rooted_in_run_dir() -> None:
    run_dir = Path("runs") / "experiment" / "runs" / "C0_r01"

    paths = phase_artifact_paths(run_dir, "judged")

    assert paths[0] == run_dir / "judge.events.jsonl"
