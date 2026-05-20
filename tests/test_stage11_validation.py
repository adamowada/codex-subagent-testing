from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness.matrix import expand_experiment_matrix, load_experiment_config
from harness.orchestrator import write_experiment_metadata
from harness.preflight import PreflightCheck, run_preflight
from harness.report_data import write_results_outputs
from harness.validation import validate_stage11, write_validation_report


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "initial_experiment.yaml"
SOLO_REASONING_CONFIG_PATH = REPO_ROOT / "configs" / "c5_c7_solo_reasoning.yaml"
RULELEDGER_V2_CONFIG_PATH = REPO_ROOT / "configs" / "ruleledger_v2.yaml"
RULELEDGER_V2_PILOT_CONFIG_PATH = REPO_ROOT / "configs" / "ruleledger_v2_pilot.yaml"
RULELEDGER_V2_EXPERIMENT_CONFIG_PATH = REPO_ROOT / "configs" / "ruleledger_v2_experiment.yaml"
SYNTHETIC_V2_CONFIG_PATH = REPO_ROOT / "tests" / "fixtures" / "stage14" / "ruleledger_v2_experiment.yaml"


@pytest.fixture
def config() -> dict:
    return load_experiment_config(CONFIG_PATH)


@pytest.fixture
def runs(config: dict) -> list[dict]:
    return expand_experiment_matrix(config)


def test_stage11_static_contract_validates_matrix_scripts_and_pilot_selection(runs: list[dict]) -> None:
    payload = validate_stage11(
        config_path=CONFIG_PATH,
        repo_root=REPO_ROOT,
        run_preflight_check=False,
    )

    assert payload["status"] == "passed"
    assert payload["full_run_count"] == 45
    assert payload["selected_run_count"] == 45
    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["matrix_contract"]["status"] == "passed"
    assert checks["pilot_selection"]["data"]["run_ids"] == ["C0_r01", "C1_proposal_r01"]
    assert checks["script_contract"]["status"] == "passed"


def test_stage11_static_contract_accepts_solo_reasoning_config() -> None:
    payload = validate_stage11(
        config_path=SOLO_REASONING_CONFIG_PATH,
        repo_root=REPO_ROOT,
        run_preflight_check=False,
    )

    checks = {check["name"]: check for check in payload["checks"]}
    assert payload["status"] == "passed"
    assert payload["full_run_count"] == 15
    assert payload["selected_run_count"] == 15
    assert checks["matrix_contract"]["status"] == "passed"
    assert checks["pilot_selection"]["data"]["run_ids"] == ["C5_r01", "C6_r01"]


def test_stage11_static_contract_accepts_synthetic_v2_config() -> None:
    payload = validate_stage11(
        config_path=SYNTHETIC_V2_CONFIG_PATH,
        repo_root=REPO_ROOT,
        run_preflight_check=False,
    )

    assert payload["status"] == "passed"
    assert payload["full_run_count"] == 1
    assert payload["benchmark"]["version"] == "ruleledger_v2"


def test_stage11_static_contract_accepts_real_ruleledger_v2_config() -> None:
    payload = validate_stage11(
        config_path=RULELEDGER_V2_CONFIG_PATH,
        repo_root=REPO_ROOT,
        run_preflight_check=False,
    )

    assert payload["status"] == "passed"
    assert payload["full_run_count"] == 1
    assert payload["benchmark"] == {
        "version": "ruleledger_v2",
        "template_path": "benchmark_template_v2",
        "hidden_cases_path": "hidden_tests/cases_v2",
        "scoring_path": "configs/scoring_v2.yaml",
        "scoring_profile": "starter_quality_v2",
        "versions": {"ruleledger_v2": 1},
    }


def test_stage11_static_contract_accepts_ruleledger_v2_pilot_config() -> None:
    payload = validate_stage11(
        config_path=RULELEDGER_V2_PILOT_CONFIG_PATH,
        repo_root=REPO_ROOT,
        run_preflight_check=False,
    )

    checks = {check["name"]: check for check in payload["checks"]}
    assert payload["status"] == "passed"
    assert payload["full_run_count"] == 2
    assert payload["benchmark"] == {
        "version": "ruleledger_v2",
        "template_path": "benchmark_template_v2",
        "hidden_cases_path": "hidden_tests/cases_v2",
        "scoring_path": "configs/scoring_v2.yaml",
        "scoring_profile": "starter_quality_v2",
        "versions": {"ruleledger_v2": 2},
    }
    assert checks["pilot_selection"]["data"]["run_ids"] == ["V2P0_r01", "V2P1_proposal_r01"]


def test_stage11_static_contract_accepts_ruleledger_v2_full_config() -> None:
    payload = validate_stage11(
        config_path=RULELEDGER_V2_EXPERIMENT_CONFIG_PATH,
        repo_root=REPO_ROOT,
        run_preflight_check=False,
    )

    checks = {check["name"]: check for check in payload["checks"]}
    assert payload["status"] == "passed"
    assert payload["full_run_count"] == 18
    assert payload["benchmark"] == {
        "version": "ruleledger_v2",
        "template_path": "benchmark_template_v2",
        "hidden_cases_path": "hidden_tests/cases_v2",
        "scoring_path": "configs/scoring_v2.yaml",
        "scoring_profile": "starter_quality_v2",
        "versions": {"ruleledger_v2": 18},
    }
    assert checks["pilot_selection"]["data"]["run_ids"] == ["V2C0_r01", "V2C5_proposal_r01"]


def test_stage11_validates_synthetic_completed_pilot(
    config: dict,
    runs: list[dict],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = [runs[0], next(run for run in runs if run["run_id"] == "C1_proposal_r01")]
    _write_experiment_shell(tmp_path, config, runs, selected)
    for index, run in enumerate(selected, 1):
        _write_run_artifacts(tmp_path, run, quality=0.4 + index / 10)

    monkeypatch.setenv("CODEX_REPORT_PDF_RENDERER", "minimal")
    write_results_outputs(tmp_path, selected)

    payload = validate_stage11(
        config_path=CONFIG_PATH,
        repo_root=REPO_ROOT,
        experiment_dir=tmp_path,
        selected_runs=selected,
        preflight_result=_preflight_payload(),
    )
    write_validation_report(tmp_path / "validation.json", payload)

    assert payload["status"] == "warning"
    assert (tmp_path / "validation.json").exists()
    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["run_artifacts"]["status"] == "passed"
    assert checks["hidden_test_isolation"]["status"] == "passed"
    assert checks["report_outputs"]["status"] == "warning"
    assert checks["resume_contract"]["status"] == "passed"


def test_stage11_flags_hidden_case_copied_into_worktree(
    config: dict,
    runs: list[dict],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = [runs[0]]
    _write_experiment_shell(tmp_path, config, runs, selected)
    _write_run_artifacts(tmp_path, selected[0], quality=0.25)
    leak_source = REPO_ROOT / "hidden_tests" / "cases" / "parse_validation.json"
    leak_target = tmp_path / "runs" / "C0_r01" / "worktree" / "parse_validation.json"
    leak_target.write_text(leak_source.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setenv("CODEX_REPORT_PDF_RENDERER", "minimal")
    write_results_outputs(tmp_path, selected)

    payload = validate_stage11(
        config_path=CONFIG_PATH,
        repo_root=REPO_ROOT,
        experiment_dir=tmp_path,
        selected_runs=selected,
        preflight_result=_preflight_payload(),
    )

    assert payload["status"] == "failed"
    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["hidden_test_isolation"]["status"] == "failed"
    assert "hidden case filename" in checks["hidden_test_isolation"]["details"]


def test_stage11_allows_non_case_manifest_in_worktree(
    config: dict,
    runs: list[dict],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = [runs[0]]
    _write_experiment_shell(tmp_path, config, runs, selected)
    _write_run_artifacts(tmp_path, selected[0], quality=0.25)
    evidence_dir = tmp_path / "runs" / "C0_r01" / "worktree" / "judge_evidence"
    evidence_dir.mkdir()
    _write_json(evidence_dir / "manifest.json", {"schema_version": 1, "files": []})

    monkeypatch.setenv("CODEX_REPORT_PDF_RENDERER", "minimal")
    write_results_outputs(tmp_path, selected)

    payload = validate_stage11(
        config_path=CONFIG_PATH,
        repo_root=REPO_ROOT,
        experiment_dir=tmp_path,
        selected_runs=selected,
        preflight_result=_preflight_payload(),
    )

    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["hidden_test_isolation"]["status"] == "passed"


def test_stage11_v2_hidden_isolation_uses_selected_case_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = load_experiment_config(SYNTHETIC_V2_CONFIG_PATH)
    runs = expand_experiment_matrix(config)
    selected = [runs[0]]
    _write_experiment_shell(tmp_path, config, runs, selected, config_path=SYNTHETIC_V2_CONFIG_PATH)
    _write_run_artifacts(tmp_path, selected[0], quality=0.25)

    v1_case = REPO_ROOT / "hidden_tests" / "cases" / "parse_validation.json"
    run_worktree = tmp_path / "runs" / selected[0]["run_id"] / "worktree"
    (run_worktree / "parse_validation.json").write_text(v1_case.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setenv("CODEX_REPORT_PDF_RENDERER", "minimal")
    write_results_outputs(tmp_path, selected)

    payload = validate_stage11(
        config_path=SYNTHETIC_V2_CONFIG_PATH,
        repo_root=REPO_ROOT,
        experiment_dir=tmp_path,
        selected_runs=selected,
        preflight_result=_preflight_payload(config_path=SYNTHETIC_V2_CONFIG_PATH, benchmark=selected[0]["benchmark"]),
    )

    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["hidden_test_isolation"]["status"] == "passed"

    v2_case = REPO_ROOT / "tests" / "fixtures" / "stage14" / "ruleledger_v2_cases" / "v2_synthetic.json"
    (run_worktree / "v2_synthetic.json").write_text(v2_case.read_text(encoding="utf-8"), encoding="utf-8")

    payload = validate_stage11(
        config_path=SYNTHETIC_V2_CONFIG_PATH,
        repo_root=REPO_ROOT,
        experiment_dir=tmp_path,
        selected_runs=selected,
        preflight_result=_preflight_payload(config_path=SYNTHETIC_V2_CONFIG_PATH, benchmark=selected[0]["benchmark"]),
    )

    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["hidden_test_isolation"]["status"] == "failed"
    assert "v2_synthetic.json" in checks["hidden_test_isolation"]["details"]


def test_preflight_loads_synthetic_v2_assets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("harness.preflight._check_tool", lambda name: PreflightCheck(name, "passed", name))
    monkeypatch.setattr("harness.preflight._check_npm", lambda: PreflightCheck("npm", "passed", "npm"))
    monkeypatch.setattr(
        "harness.preflight._check_python_module",
        lambda name: PreflightCheck(name, "passed", name),
    )
    monkeypatch.setattr("harness.preflight.resolve_codex_bin", lambda: None)

    payload = run_preflight(
        config_path=SYNTHETIC_V2_CONFIG_PATH,
        repo_root=REPO_ROOT,
        require_codex=False,
    )

    checks = {check["name"]: check for check in payload["checks"]}
    assert payload["benchmark"]["version"] == "ruleledger_v2"
    assert checks["benchmark_template"]["status"] == "passed"
    assert checks["hidden_cases"]["status"] == "passed"
    assert checks["hidden_cases"]["data"]["benchmark"]["hidden_cases_path"].endswith("ruleledger_v2_cases")


def test_preflight_loads_real_ruleledger_v2_assets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("harness.preflight._check_tool", lambda name: PreflightCheck(name, "passed", name))
    monkeypatch.setattr("harness.preflight._check_npm", lambda: PreflightCheck("npm", "passed", "npm"))
    monkeypatch.setattr(
        "harness.preflight._check_python_module",
        lambda name: PreflightCheck("pytest", "passed", name),
    )
    monkeypatch.setattr("harness.preflight.resolve_codex_bin", lambda: None)

    payload = run_preflight(
        config_path=RULELEDGER_V2_CONFIG_PATH,
        repo_root=REPO_ROOT,
        require_codex=False,
    )

    checks = {check["name"]: check for check in payload["checks"]}
    assert payload["benchmark"]["version"] == "ruleledger_v2"
    assert checks["benchmark_template"]["status"] == "passed"
    assert checks["hidden_cases"]["status"] == "passed"
    assert checks["hidden_cases"]["data"]["benchmark"]["template_path"] == "benchmark_template_v2"
    assert checks["hidden_cases"]["data"]["benchmark"]["hidden_cases_path"].endswith("cases_v2")


def test_stage11_flags_preflight_benchmark_mismatch() -> None:
    payload = validate_stage11(
        config_path=SYNTHETIC_V2_CONFIG_PATH,
        repo_root=REPO_ROOT,
        preflight_result=_preflight_payload(),
    )

    checks = {check["name"]: check for check in payload["checks"]}
    assert payload["status"] == "failed"
    assert checks["preflight"]["status"] == "failed"
    assert "benchmark metadata" in checks["preflight"]["details"]


def test_stage11_warns_when_malformed_judge_output_is_scored(
    config: dict,
    runs: list[dict],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = [runs[0]]
    _write_experiment_shell(tmp_path, config, runs, selected)
    _write_run_artifacts(tmp_path, selected[0], quality=0.25)
    run_dir = tmp_path / "runs" / "C0_r01"
    _write_json(run_dir / "judge.json", {"parsed": False, "raw": "not json", "error": "no_json_object"})
    score = json.loads((run_dir / "score.json").read_text(encoding="utf-8"))
    score["component_scores"]["judge"] = 0.0
    score["warnings"] = ["judge output was not parsed as strict JSON"]
    _write_json(run_dir / "score.json", score)

    monkeypatch.setenv("CODEX_REPORT_PDF_RENDERER", "minimal")
    write_results_outputs(tmp_path, selected)

    payload = validate_stage11(
        config_path=CONFIG_PATH,
        repo_root=REPO_ROOT,
        experiment_dir=tmp_path,
        selected_runs=selected,
        preflight_result=_preflight_payload(),
    )

    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["judge_json"]["status"] == "warning"
    assert "scored as zero" in checks["judge_json"]["data"]["warnings"][0]


def _write_experiment_shell(
    experiment_dir: Path,
    config: dict,
    runs: list[dict],
    selected: list[dict],
    *,
    config_path: Path = CONFIG_PATH,
) -> None:
    args = SimpleNamespace(pilot=len(selected) == 2, dry_run=False, jobs=1, judge_jobs=1)
    write_experiment_metadata(
        experiment_dir=experiment_dir,
        config_path=config_path,
        config=config,
        all_runs=runs,
        selected_runs=selected,
        args=args,
    )
    _write_json(experiment_dir / "preflight.json", _preflight_payload(config_path=config_path))
    _write_json(
        experiment_dir / "status.json",
        {"schema_version": 1, "status": "completed", "runs": {}},
    )
    (experiment_dir / "orchestrator.log").write_text("completed\n", encoding="utf-8")


def _write_run_artifacts(experiment_dir: Path, run: dict, *, quality: float) -> None:
    run_dir = experiment_dir / "runs" / run["run_id"]
    worktree = run_dir / "worktree"
    config_dir = run_dir / "codex_config"
    worktree.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    (worktree / "src").mkdir()
    (worktree / "src" / "index.ts").write_text("export const ok = true;\n", encoding="utf-8")
    (run_dir / "rendered_prompt.md").write_text("implement\n", encoding="utf-8")
    (run_dir / "judge_prompt.md").write_text("judge\n", encoding="utf-8")
    (config_dir / "config.toml").write_text("model = \"gpt-5.5\"\n", encoding="utf-8")
    (run_dir / "events.jsonl").write_text('{"usage":{"input_tokens":10,"output_tokens":5}}\n', encoding="utf-8")
    (run_dir / "judge.events.jsonl").write_text(
        '{"usage":{"input_tokens":4,"output_tokens":4}}\n',
        encoding="utf-8",
    )
    for name in (
        "stderr.log",
        "judge.stderr.log",
        "typecheck.log",
        "public_ts.log",
        "public_py.log",
        "hidden-runner.log",
    ):
        (run_dir / name).write_text("", encoding="utf-8")
    (run_dir / "diff.patch").write_text("", encoding="utf-8")
    (run_dir / "diff-numstat.txt").write_text("5\t0\tsrc/index.ts\n", encoding="utf-8")

    for name in ("wall_time.json", "judge.wall_time.json"):
        _write_json(run_dir / name, _process_meta(run_dir / name, stdout=True))
    for name in ("typecheck.meta.json", "public_ts.meta.json", "public_py.meta.json", "hidden-runner.meta.json"):
        _write_json(run_dir / name, _process_meta(run_dir / name.replace(".meta.json", ".log"), stdout=False))

    _write_json(run_dir / "worktree.json", {"schema_version": 1, "path": str(worktree), "inside_repo": False})
    _write_json(
        run_dir / "metadata.json",
        {
            "schema_version": 1,
            "run_id": run["run_id"],
            "run": run,
            "benchmark": run.get("benchmark"),
            "worktree": str(worktree),
            "baseline_commit": "synthetic-baseline",
        },
    )
    _write_json(run_dir / "final_response.json", {"parsed": True, "value": {"status": "success"}})
    _write_json(
        run_dir / "hidden-results.json",
        {
            "schema_version": 1,
            "summary": {"score": quality},
            "categories": {"parity": {"score": quality}},
            "cases": [
                {
                    "id": "case-000000000001",
                    "category": "parity",
                    "language": "parity",
                    "status": "failed",
                    "points_earned": 0.0,
                    "points_possible": 1.0,
                    "reason": "output_mismatch",
                }
            ],
        },
    )
    _write_json(
        run_dir / "judge.json",
        {"parsed": True, "value": {"overall_score": quality}},
    )
    _write_json(
        run_dir / "usage.json",
        {
            "schema_version": 1,
            "implementation": _usage(15),
            "judge": _usage(8),
            "totals": {
                "implementation_tokens": 15,
                "judge_tokens": 8,
                "judge_inclusive_tokens": 23,
                "gpt55_implementation_tokens": 15,
                "gpt55_judge_tokens": 8,
                "gpt55_judge_inclusive_tokens": 23,
                "spark_implementation_tokens": 0,
            },
            "event_counts": {"implementation_usage_events": 1, "judge_usage_events": 1},
            "model_totals": {},
            "implementation_model_totals": {},
            "judge_model_totals": {},
            "unattributed": {"implementation_tokens": 0, "judge_tokens": 0},
            "attribution_method": "per_event_model",
            "warnings": [],
        },
    )
    _write_json(
        run_dir / "score.json",
        {
            "schema_version": 1,
            "run_id": run["run_id"],
            "cell_id": run["cell_id"],
            "spark_mode": run.get("spark_mode"),
            "component_scores": {
                "public_tests": quality,
                "hidden_tests": quality,
                "judge": quality,
                "typecheck": 1.0,
                "parity": quality,
                "minimality": 1.0,
            },
            "weights": run["scoring_weights"],
            "quality_score": quality,
            "efficiency": {
                "quality_per_gpt55_impl_token": quality / 15,
                "quality_per_judge_inclusive_gpt55_token": quality / 23,
                "quality_per_total_impl_token": quality / 15,
                "quality_per_wall_clock_minute": quality,
            },
            "diff_stats": {
                "changed_files": 1,
                "insertions": 5,
                "deletions": 0,
                "binary_files": 0,
                "production_loc": 5,
                "test_loc": 0,
            },
            "wall_time": {"implementation_elapsed_seconds": 60.0, "judge_elapsed_seconds": 12.0},
            "status": "partial",
            "warnings": [],
        },
    )
    _write_json(
        run_dir / "state.json",
        {
            "schema_version": 1,
            "phases": {
                phase: {"status": "completed"}
                for phase in [
                    "prepared",
                    "baseline_committed",
                    "rendered",
                    "implemented",
                    "diff_captured",
                    "public_tested",
                    "hidden_tested",
                    "judged",
                    "usage_parsed",
                    "scored",
                ]
            },
        },
    )


def _usage(total: int) -> dict[str, int]:
    return {
        "input_tokens": total,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": total,
    }


def _process_meta(path: Path, *, stdout: bool) -> dict:
    payload = {
        "command": ["test"],
        "command_display": ["test"],
        "cwd": str(path.parent),
        "started_at": "2026-05-19T00:00:00+00:00",
        "finished_at": "2026-05-19T00:00:01+00:00",
        "elapsed_seconds": 1.0,
        "returncode": 0,
        "timed_out": False,
    }
    if stdout:
        payload["stdout_path"] = str(path.with_suffix(".out"))
    else:
        payload["log_path"] = str(path)
    return payload


def _preflight_payload(
    *,
    config_path: Path = CONFIG_PATH,
    benchmark: dict | None = None,
) -> dict:
    if benchmark is None and config_path == CONFIG_PATH:
        benchmark = {
            "version": "ruleledger_v1",
            "template_path": "benchmark_template",
            "hidden_cases_path": "hidden_tests/cases",
            "scoring_path": "configs/scoring.yaml",
            "scoring_profile": "initial_quality_v1",
        }
    return {
        "schema_version": 1,
        "status": "passed",
        "repo_root": str(REPO_ROOT),
        "config_path": str(config_path),
        "benchmark": benchmark,
        "codex_bin": "codex",
        "checks": [{"name": "codex", "status": "passed"}],
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
