from __future__ import annotations

import copy
from pathlib import Path
import unittest

from harness.matrix import (
    ExperimentConfigError,
    expand_experiment_matrix,
    load_experiment_config,
    summarize_matrix,
    validate_experiment_config,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "initial_experiment.yaml"


class ExperimentMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_experiment_config(CONFIG_PATH)

    def test_initial_config_expands_to_45_runs(self) -> None:
        runs = expand_experiment_matrix(self.config)

        self.assertEqual(len(runs), 45)
        self.assertEqual(runs[0]["run_id"], "C0_r01")
        self.assertEqual(runs[-1]["run_id"], "C4_proposal_r05")

    def test_summary_counts_match_initial_matrix(self) -> None:
        runs = expand_experiment_matrix(self.config)
        summary = summarize_matrix(runs)

        self.assertEqual(
            summary["by_cell"],
            {
                "C0": 5,
                "C1": 10,
                "C2": 10,
                "C3": 10,
                "C4": 10,
            },
        )
        self.assertEqual(summary["by_spark_mode"], {"direct": 20, "none": 5, "proposal": 20})

    def test_c4_topology_resolves_to_eighteen_spark_leaves(self) -> None:
        runs = expand_experiment_matrix(self.config)
        c4 = next(run for run in runs if run["cell_id"] == "C4")

        self.assertEqual(c4["root"]["model"], "gpt-5.5")
        self.assertEqual(c4["root"]["reasoning"], "xhigh")
        self.assertEqual(c4["subleads"]["count"], 3)
        self.assertEqual(c4["subleads"]["reasoning"], "medium")
        self.assertEqual(c4["subleads"]["leaves_per_sublead"], 6)
        self.assertEqual(c4["leaf"]["model"], "gpt-5.3-codex-spark")
        self.assertEqual(c4["leaf"]["count"], 18)
        self.assertEqual(c4["agents"]["max_depth"], 2)
        self.assertGreaterEqual(c4["agents"]["max_threads"], 24)

    def test_flat_cells_keep_expected_root_reasoning(self) -> None:
        runs = expand_experiment_matrix(self.config)
        reasoning_by_cell = {
            run["cell_id"]: run["root"]["reasoning"]
            for run in runs
            if run["spark_mode"] in {None, "direct"}
        }

        self.assertEqual(reasoning_by_cell["C0"], "xhigh")
        self.assertEqual(reasoning_by_cell["C1"], "medium")
        self.assertEqual(reasoning_by_cell["C2"], "high")
        self.assertEqual(reasoning_by_cell["C3"], "xhigh")
        self.assertEqual(reasoning_by_cell["C4"], "xhigh")

    def test_all_spark_leaf_reasoning_is_xhigh(self) -> None:
        runs = expand_experiment_matrix(self.config)

        for run in runs:
            leaf = run["leaf"]
            if leaf is None:
                continue
            self.assertEqual(set(leaf["reasoning_by_role"].values()), {"xhigh"})

    def test_duplicate_cell_ids_fail_validation(self) -> None:
        config = copy.deepcopy(self.config)
        config["cells"][1]["id"] = "C0"

        with self.assertRaisesRegex(ExperimentConfigError, "duplicate cell id"):
            validate_experiment_config(config)

    def test_non_spark_leaf_model_fails_validation(self) -> None:
        config = copy.deepcopy(self.config)
        config["cells"][1]["leaf"]["model"] = "gpt-5.5"

        with self.assertRaisesRegex(ExperimentConfigError, "leaf.model"):
            validate_experiment_config(config)

    def test_scoring_weights_must_sum_to_one(self) -> None:
        config = copy.deepcopy(self.config)
        config["scoring"]["weights"]["hidden_tests"] = 0.44

        with self.assertRaisesRegex(ExperimentConfigError, "sum to 1.0"):
            validate_experiment_config(config)

    def test_unknown_scoring_component_fails_validation(self) -> None:
        config = copy.deepcopy(self.config)
        config["scoring"]["weights"] = {"hidden_tests": 0.95, "surprise": 0.05}

        with self.assertRaisesRegex(ExperimentConfigError, "unknown scoring component"):
            validate_experiment_config(config)

    def test_minimality_scoring_config_is_propagated_to_runs(self) -> None:
        config = copy.deepcopy(self.config)
        config["scoring"]["weights"] = {"hidden_tests": 0.95, "minimality": 0.05}
        config["scoring"]["minimality"] = {"target_production_loc": 400, "penalty_window": 800}

        runs = expand_experiment_matrix(config)

        self.assertEqual(
            runs[0]["scoring_minimality"],
            {"target_production_loc": 400, "penalty_window": 800},
        )


if __name__ == "__main__":
    unittest.main()
