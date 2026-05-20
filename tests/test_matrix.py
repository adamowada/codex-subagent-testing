from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from harness.matrix import (
    ExperimentConfigError,
    expand_experiment_matrix,
    load_experiment_config,
    summarize_matrix,
    validate_experiment_config,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "initial_experiment.yaml"
SOLO_REASONING_CONFIG_PATH = REPO_ROOT / "configs" / "c5_c7_solo_reasoning.yaml"
RULELEDGER_V2_CONFIG_PATH = REPO_ROOT / "configs" / "ruleledger_v2.yaml"
RULELEDGER_V2_PILOT_CONFIG_PATH = REPO_ROOT / "configs" / "ruleledger_v2_pilot.yaml"
SYNTHETIC_V2_CONFIG_PATH = REPO_ROOT / "tests" / "fixtures" / "stage14" / "ruleledger_v2_experiment.yaml"


@pytest.fixture
def config() -> dict:
    return load_experiment_config(CONFIG_PATH)


def test_initial_config_expands_to_45_runs(config: dict) -> None:
    runs = expand_experiment_matrix(config)

    assert len(runs) == 45
    assert runs[0]["run_id"] == "C0_r01"
    assert runs[-1]["run_id"] == "C4_proposal_r05"


def test_solo_reasoning_config_expands_to_c5_c7_only() -> None:
    runs = expand_experiment_matrix(load_experiment_config(SOLO_REASONING_CONFIG_PATH))

    assert len(runs) == 15
    assert runs[0]["run_id"] == "C5_r01"
    assert runs[-1]["run_id"] == "C7_r05"
    assert {run["cell_id"] for run in runs} == {"C5", "C6", "C7"}
    assert {run["topology"] for run in runs} == {"solo"}
    assert {run["spark_mode"] for run in runs} == {None}
    assert {run["leaf"] for run in runs} == {None}
    assert {
        run["cell_id"]: run["root"]["reasoning"]
        for run in runs
        if run["repeat_index"] == 1
    } == {"C5": "low", "C6": "medium", "C7": "high"}


def test_summary_counts_match_initial_matrix(config: dict) -> None:
    runs = expand_experiment_matrix(config)
    summary = summarize_matrix(runs)

    assert summary["by_cell"] == {
        "C0": 5,
        "C1": 10,
        "C2": 10,
        "C3": 10,
        "C4": 10,
    }
    assert summary["by_spark_mode"] == {"direct": 20, "none": 5, "proposal": 20}
    assert summary["by_benchmark_version"] == {"ruleledger_v1": 45}
    assert summary["benchmark_assets"]["template_path"] == "benchmark_template"
    assert summary["benchmark_assets"]["hidden_cases_path"] == "hidden_tests/cases"


def test_benchmark_asset_metadata_is_propagated_to_v1_runs(config: dict) -> None:
    runs = expand_experiment_matrix(config)

    assert runs[0]["benchmark"] == {
        "version": "ruleledger_v1",
        "template_path": "benchmark_template",
        "hidden_cases_path": "hidden_tests/cases",
        "scoring_path": "configs/scoring.yaml",
        "scoring_profile": "initial_quality_v1",
    }


def test_synthetic_v2_config_selects_separate_assets() -> None:
    config = load_experiment_config(SYNTHETIC_V2_CONFIG_PATH)
    runs = expand_experiment_matrix(config)

    assert len(runs) == 1
    assert runs[0]["benchmark"] == {
        "version": "ruleledger_v2",
        "template_path": "tests/fixtures/stage14/ruleledger_v2_template",
        "hidden_cases_path": "tests/fixtures/stage14/ruleledger_v2_cases",
        "scoring_path": "tests/fixtures/stage14/scoring_v2.yaml",
        "scoring_profile": "synthetic_quality_v2",
    }


def test_ruleledger_v2_config_selects_real_v2_starter_assets() -> None:
    config = load_experiment_config(RULELEDGER_V2_CONFIG_PATH)
    runs = expand_experiment_matrix(config)
    summary = summarize_matrix(runs)

    assert len(runs) == 1
    assert runs[0]["run_id"] == "V2C0_r01"
    assert runs[0]["benchmark"] == {
        "version": "ruleledger_v2",
        "template_path": "benchmark_template_v2",
        "hidden_cases_path": "hidden_tests/cases_v2",
        "scoring_path": "configs/scoring_v2.yaml",
        "scoring_profile": "starter_quality_v2",
    }
    assert runs[0]["scoring_weights"] == {
        "hidden_correctness": 0.55,
        "hidden_parity": 0.15,
        "performance": 0.10,
        "judge": 0.15,
        "minimality": 0.05,
    }
    assert summary["by_benchmark_version"] == {"ruleledger_v2": 1}
    assert summary["benchmark_assets"]["template_path"] == "benchmark_template_v2"


def test_ruleledger_v2_pilot_config_expands_to_calibration_runs() -> None:
    config = load_experiment_config(RULELEDGER_V2_PILOT_CONFIG_PATH)
    runs = expand_experiment_matrix(config)
    summary = summarize_matrix(runs)

    assert [run["run_id"] for run in runs] == ["V2P0_r01", "V2P1_proposal_r01"]
    assert [run["root"]["reasoning"] for run in runs] == ["low", "xhigh"]
    assert [run["topology"] for run in runs] == ["solo", "flat_spark"]
    assert [run["spark_mode"] for run in runs] == [None, "proposal"]
    assert runs[0]["leaf"] is None
    assert runs[1]["leaf"]["count"] == 6
    assert runs[1]["agents"]["max_threads"] == 7
    assert runs[1]["spark_mode_config"] == {"leaf_write_mode": "read-only", "proposal_only": True}
    assert runs[0]["benchmark"] == {
        "version": "ruleledger_v2",
        "template_path": "benchmark_template_v2",
        "hidden_cases_path": "hidden_tests/cases_v2",
        "scoring_path": "configs/scoring_v2.yaml",
        "scoring_profile": "starter_quality_v2",
    }
    assert summary["total_runs"] == 2
    assert summary["by_benchmark_version"] == {"ruleledger_v2": 2}
    assert summary["by_root_reasoning"] == {"low": 1, "xhigh": 1}
    assert summary["by_spark_mode"] == {"none": 1, "proposal": 1}


def test_c4_topology_resolves_to_eighteen_spark_leaves(config: dict) -> None:
    runs = expand_experiment_matrix(config)
    c4 = next(run for run in runs if run["cell_id"] == "C4")

    assert c4["root"]["model"] == "gpt-5.5"
    assert c4["root"]["reasoning"] == "xhigh"
    assert c4["subleads"]["count"] == 3
    assert c4["subleads"]["reasoning"] == "medium"
    assert c4["subleads"]["leaves_per_sublead"] == 6
    assert c4["leaf"]["model"] == "gpt-5.3-codex-spark"
    assert c4["leaf"]["count"] == 18
    assert c4["agents"]["max_depth"] == 2
    assert c4["agents"]["max_threads"] >= 24


def test_flat_cells_keep_expected_root_reasoning(config: dict) -> None:
    runs = expand_experiment_matrix(config)
    reasoning_by_cell = {
        run["cell_id"]: run["root"]["reasoning"]
        for run in runs
        if run["spark_mode"] in {None, "direct"}
    }

    assert reasoning_by_cell["C0"] == "xhigh"
    assert reasoning_by_cell["C1"] == "medium"
    assert reasoning_by_cell["C2"] == "high"
    assert reasoning_by_cell["C3"] == "xhigh"
    assert reasoning_by_cell["C4"] == "xhigh"


def test_all_spark_leaf_reasoning_is_xhigh(config: dict) -> None:
    runs = expand_experiment_matrix(config)

    for run in runs:
        leaf = run["leaf"]
        if leaf is None:
            continue
        assert set(leaf["reasoning_by_role"].values()) == {"xhigh"}


def test_duplicate_cell_ids_fail_validation(config: dict) -> None:
    candidate = copy.deepcopy(config)
    candidate["cells"][1]["id"] = "C0"

    with pytest.raises(ExperimentConfigError, match="duplicate cell id"):
        validate_experiment_config(candidate)


def test_non_spark_leaf_model_fails_validation(config: dict) -> None:
    candidate = copy.deepcopy(config)
    candidate["cells"][1]["leaf"]["model"] = "gpt-5.5"

    with pytest.raises(ExperimentConfigError, match="leaf.model"):
        validate_experiment_config(candidate)


def test_scoring_weights_must_sum_to_one(config: dict) -> None:
    candidate = copy.deepcopy(config)
    candidate["scoring"]["weights"]["hidden_tests"] = 0.44

    with pytest.raises(ExperimentConfigError, match="sum to 1.0"):
        validate_experiment_config(candidate)


def test_unknown_scoring_component_fails_validation(config: dict) -> None:
    candidate = copy.deepcopy(config)
    candidate["scoring"]["weights"] = {"hidden_tests": 0.95, "surprise": 0.05}

    with pytest.raises(ExperimentConfigError, match="unknown scoring component"):
        validate_experiment_config(candidate)


def test_scoring_path_cannot_escape_repository(config: dict, tmp_path: Path) -> None:
    candidate = copy.deepcopy(config)
    candidate["scoring"] = {"path": "../outside-scoring.yaml"}
    path = tmp_path / "experiment.yaml"
    path.write_text(json.dumps(candidate), encoding="utf-8")

    with pytest.raises(ExperimentConfigError, match="scoring.path"):
        load_experiment_config(path)


def test_judge_must_remain_gpt55_xhigh_read_only(config: dict) -> None:
    candidate = copy.deepcopy(config)
    candidate["judge"]["sandbox"] = "workspace-write"

    with pytest.raises(ExperimentConfigError, match="judge.sandbox"):
        validate_experiment_config(candidate)


def test_prompt_template_must_match_topology(config: dict) -> None:
    candidate = copy.deepcopy(config)
    candidate["cells"][1]["prompt_template"] = "solo"

    with pytest.raises(ExperimentConfigError, match="prompt_template"):
        validate_experiment_config(candidate)


def test_minimality_scoring_config_is_propagated_to_runs(config: dict) -> None:
    candidate = copy.deepcopy(config)
    candidate["scoring"]["weights"] = {"hidden_tests": 0.95, "minimality": 0.05}
    candidate["scoring"]["minimality"] = {"target_production_loc": 400, "penalty_window": 800}

    runs = expand_experiment_matrix(candidate)

    assert runs[0]["scoring_minimality"] == {"target_production_loc": 400, "penalty_window": 800}
