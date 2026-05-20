from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]

ALLOWED_INITIAL_MODELS = {"gpt-5.5", "gpt-5.3-codex-spark"}
VALID_REASONING = {"none", "minimal", "low", "medium", "high", "xhigh"}
INITIAL_SPARK_MODEL = "gpt-5.3-codex-spark"
INITIAL_GPT55_MODEL = "gpt-5.5"
INITIAL_SPARK_REASONING = "xhigh"
SCORING_COMPONENTS = {"public_tests", "hidden_tests", "judge", "typecheck", "parity", "minimality"}
REQUIRED_PROMPT_TEMPLATE_KEYS = {
    "common",
    "solo",
    "flat_spark",
    "depth2_subleads",
    "judge",
}
REQUIRED_SPARK_MODES = {"direct", "proposal"}


class ExperimentConfigError(ValueError):
    """Raised when an experiment configuration cannot be used safely."""


def load_experiment_config(path: str | Path) -> dict[str, Any]:
    """Load an experiment config and resolve referenced scoring config."""

    config_path = Path(path)
    config = _load_mapping_file(config_path)
    scoring = config.get("scoring")

    if isinstance(scoring, Mapping) and isinstance(scoring.get("path"), str):
        scoring_path = _repo_path(scoring["path"])
        scoring_config = _load_mapping_file(scoring_path)
        resolved_scoring = copy.deepcopy(scoring_config)
        for key, value in scoring.items():
            if key != "path":
                resolved_scoring[key] = value
        resolved_scoring["path"] = scoring["path"]

        config = copy.deepcopy(config)
        config["scoring"] = resolved_scoring

    return config


def validate_experiment_config(config: Mapping[str, Any]) -> None:
    """Validate the initial experiment definition.

    The checks intentionally encode the initial benchmark contract from
    PLANS.md. Future experiments can loosen these constraints by adding an
    explicit schema version or model allowlist.
    """

    errors: list[str] = []

    if config.get("schema_version") != 1:
        errors.append("schema_version: expected 1")

    experiment = _mapping(config, "experiment", errors)
    repeat_count = _positive_int(experiment, "repeat_count", "experiment.repeat_count", errors)
    experiment_id = experiment.get("id")
    if not isinstance(experiment_id, str) or not experiment_id:
        errors.append("experiment.id: expected non-empty string")
    elif not _is_filesystem_safe_id(experiment_id):
        errors.append("experiment.id: expected filesystem-safe identifier")
    strict_initial_contract = experiment_id == "initial_subagent_topology"

    parallelism = _mapping(config, "parallelism", errors)
    _positive_int(parallelism, "implementation_jobs", "parallelism.implementation_jobs", errors)
    _positive_int(parallelism, "judge_jobs", "parallelism.judge_jobs", errors)

    timeouts = _mapping(config, "timeouts", errors)
    _positive_int(timeouts, "implementation_seconds", "timeouts.implementation_seconds", errors)
    _positive_int(timeouts, "judge_seconds", "timeouts.judge_seconds", errors)

    paths = _mapping(config, "paths", errors)
    prompt_templates = _mapping(paths, "prompt_templates", errors, prefix="paths")
    _validate_prompt_templates(prompt_templates, errors)
    _relative_path(paths.get("codex_config_template"), "paths.codex_config_template", errors)

    models = _mapping(config, "models", errors)
    if models.get("gpt55") != INITIAL_GPT55_MODEL:
        errors.append("models.gpt55: expected gpt-5.5")
    if models.get("spark") != INITIAL_SPARK_MODEL:
        errors.append("models.spark: expected gpt-5.3-codex-spark")

    spark_modes = _mapping(config, "spark_modes", errors)
    _validate_spark_mode_definitions(spark_modes, errors)

    scoring = _mapping(config, "scoring", errors)
    _validate_scoring(scoring, errors)

    judge = _mapping(config, "judge", errors)
    if judge.get("model") != INITIAL_GPT55_MODEL:
        errors.append(f"judge.model: expected {INITIAL_GPT55_MODEL}")
    _validate_reasoning(judge.get("reasoning"), "judge.reasoning", errors)
    if judge.get("reasoning") != "xhigh":
        errors.append("judge.reasoning: expected xhigh")
    if judge.get("sandbox") != "read-only":
        errors.append("judge.sandbox: expected read-only")
    _validate_prompt_template_reference(
        judge.get("prompt_template"),
        prompt_templates,
        "judge.prompt_template",
        errors,
    )

    cells = _list(config, "cells", errors)
    cell_ids: set[str] = set()
    expanded_count = 0

    for index, cell_value in enumerate(cells):
        path = f"cells[{index}]"
        if not isinstance(cell_value, Mapping):
            errors.append(f"{path}: expected object")
            continue

        cell = cell_value
        cell_id = cell.get("id")
        if not isinstance(cell_id, str) or not cell_id:
            errors.append(f"{path}.id: expected non-empty string")
            cell_id = f"<invalid-{index}>"
        elif cell_id in cell_ids:
            errors.append(f"{path}.id: duplicate cell id {cell_id}")
        else:
            cell_ids.add(cell_id)

        repeats = _positive_int(cell, "repeats", f"{path}.repeats", errors)
        if repeats is None and repeat_count is not None:
            repeats = repeat_count

        topology = cell.get("topology")
        if topology not in {"solo", "flat_spark", "depth2_subleads"}:
            errors.append(f"{path}.topology: unknown topology {topology!r}")

        _validate_prompt_template_reference(
            cell.get("prompt_template"),
            prompt_templates,
            f"{path}.prompt_template",
            errors,
        )
        expected_prompt = {
            "solo": "solo",
            "flat_spark": "flat_spark",
            "depth2_subleads": "depth2_subleads",
        }.get(str(topology))
        if expected_prompt is not None and cell.get("prompt_template") != expected_prompt:
            errors.append(f"{path}.prompt_template: {topology} requires {expected_prompt}")

        modes = _cell_spark_modes(cell, path, spark_modes, errors)
        if strict_initial_contract and cell_id == "C0" and modes:
            errors.append(f"{path}.spark_modes: C0 must not define Spark modes")
        if strict_initial_contract and cell_id in {"C1", "C2", "C3", "C4"} and set(modes) != REQUIRED_SPARK_MODES:
            errors.append(f"{path}.spark_modes: {cell_id} must include direct and proposal")

        root = _mapping(cell, "root", errors, prefix=path)
        if root.get("model") != INITIAL_GPT55_MODEL:
            errors.append(f"{path}.root.model: expected {INITIAL_GPT55_MODEL}")
        _validate_reasoning(root.get("reasoning"), f"{path}.root.reasoning", errors)
        if strict_initial_contract:
            _validate_initial_root_reasoning(cell_id, root.get("reasoning"), path, errors)

        agents = _mapping(cell, "agents", errors, prefix=path)
        max_depth = _positive_int(agents, "max_depth", f"{path}.agents.max_depth", errors, allow_zero=True)
        max_threads = _positive_int(agents, "max_threads", f"{path}.agents.max_threads", errors)

        breadth = 1
        if topology == "solo":
            if max_depth != 0:
                errors.append(f"{path}.agents.max_depth: solo requires max_depth=0")
        elif topology == "flat_spark":
            if max_depth != 1:
                errors.append(f"{path}.agents.max_depth: flat_spark requires max_depth=1")
            leaf = _mapping(cell, "leaf", errors, prefix=path)
            leaf_count = _positive_int(leaf, "count", f"{path}.leaf.count", errors)
            _validate_leaf(leaf, path, errors)
            if leaf_count is not None:
                breadth += leaf_count
                if strict_initial_contract and cell_id in {"C1", "C2", "C3"} and leaf_count != 6:
                    errors.append(f"{path}.leaf.count: {cell_id} requires exactly 6 Spark leaves")
        elif topology == "depth2_subleads":
            if max_depth != 2:
                errors.append(f"{path}.agents.max_depth: depth2_subleads requires max_depth=2")
            subleads = _mapping(cell, "subleads", errors, prefix=path)
            sublead_count = _positive_int(subleads, "count", f"{path}.subleads.count", errors)
            leaves_per_sublead = _positive_int(
                subleads,
                "leaves_per_sublead",
                f"{path}.subleads.leaves_per_sublead",
                errors,
            )
            _validate_model(subleads.get("model"), f"{path}.subleads.model", errors)
            _validate_reasoning(subleads.get("reasoning"), f"{path}.subleads.reasoning", errors)
            if strict_initial_contract and cell_id == "C4":
                if subleads.get("model") != INITIAL_GPT55_MODEL:
                    errors.append(f"{path}.subleads.model: C4 requires gpt-5.5")
                if subleads.get("reasoning") != "medium":
                    errors.append(f"{path}.subleads.reasoning: C4 requires medium")
                if sublead_count != 3:
                    errors.append(f"{path}.subleads.count: C4 requires exactly 3 subleads")
                if leaves_per_sublead != 6:
                    errors.append(f"{path}.subleads.leaves_per_sublead: C4 requires exactly 6 leaves")
            leaf = _mapping(cell, "leaf", errors, prefix=path)
            _validate_leaf(leaf, path, errors)
            if sublead_count is not None and leaves_per_sublead is not None:
                leaf_total = sublead_count * leaves_per_sublead
                breadth += sublead_count + leaf_total
                if strict_initial_contract and cell_id == "C4" and leaf_total != 18:
                    errors.append(f"{path}.leaf.count: C4 requires exactly 18 Spark leaves")

        if max_threads is not None and max_threads < breadth:
            errors.append(
                f"{path}.agents.max_threads: expected at least {breadth} for configured breadth"
            )
        if strict_initial_contract and cell_id == "C4" and max_threads is not None and max_threads < 24:
            errors.append(f"{path}.agents.max_threads: C4 requires at least 24")

        if repeats is not None:
            expanded_count += repeats * (len(modes) if modes else 1)

    if strict_initial_contract:
        expected_cells = {"C0", "C1", "C2", "C3", "C4"}
        if cell_ids and cell_ids != expected_cells:
            errors.append(f"cells: expected exactly {sorted(expected_cells)}, got {sorted(cell_ids)}")
        if expanded_count and expanded_count != 45:
            errors.append(f"cells: expected expansion to 45 implementation runs, got {expanded_count}")

    if errors:
        raise ExperimentConfigError("\n".join(errors))


def expand_experiment_matrix(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Expand a validated experiment config into deterministic run records."""

    validate_experiment_config(config)

    paths = config["paths"]
    prompt_templates = paths["prompt_templates"]
    spark_modes = config["spark_modes"]
    scoring = config["scoring"]
    scoring_weights = scoring["weights"]
    scoring_minimality = scoring.get("minimality", {})
    timeouts = config["timeouts"]
    judge = config["judge"]

    runs: list[dict[str, Any]] = []
    for cell in config["cells"]:
        cell_id = cell["id"]
        modes = list(cell.get("spark_modes") or [])
        repeats = int(cell["repeats"])

        mode_values: list[str | None] = modes if modes else [None]
        for mode in mode_values:
            for repeat_index in range(1, repeats + 1):
                run_id = _run_id(cell_id, mode, repeat_index)
                prompt_template_key = cell["prompt_template"]

                record = {
                    "run_id": run_id,
                    "cell_id": cell_id,
                    "cell_name": cell["name"],
                    "repeat_index": repeat_index,
                    "topology": cell["topology"],
                    "spark_mode": mode,
                    "spark_mode_config": copy.deepcopy(spark_modes[mode]) if mode else None,
                    "prompt_template": prompt_template_key,
                    "prompt_template_path": prompt_templates[prompt_template_key],
                    "common_prompt_template_path": prompt_templates["common"],
                    "codex_config_template_path": paths["codex_config_template"],
                    "root": copy.deepcopy(cell["root"]),
                    "subleads": copy.deepcopy(cell.get("subleads")),
                    "leaf": _expanded_leaf(cell),
                    "agents": copy.deepcopy(cell["agents"]),
                    "timeouts": copy.deepcopy(timeouts),
                    "judge": copy.deepcopy(judge),
                    "judge_prompt_template_path": prompt_templates[judge["prompt_template"]],
                    "scoring_weights": copy.deepcopy(scoring_weights),
                    "scoring_minimality": copy.deepcopy(scoring_minimality),
                }
                runs.append(record)

    return runs


def summarize_matrix(runs: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Return compact counts useful for preflight and smoke tests."""

    by_cell = Counter(str(run["cell_id"]) for run in runs)
    by_mode = Counter(str(run["spark_mode"] or "none") for run in runs)
    by_topology = Counter(str(run["topology"]) for run in runs)
    by_root_model = Counter(str(run["root"]["model"]) for run in runs)
    by_root_reasoning = Counter(str(run["root"]["reasoning"]) for run in runs)

    return {
        "total_runs": len(runs),
        "by_cell": dict(sorted(by_cell.items())),
        "by_spark_mode": dict(sorted(by_mode.items())),
        "by_topology": dict(sorted(by_topology.items())),
        "by_root_model": dict(sorted(by_root_model.items())),
        "by_root_reasoning": dict(sorted(by_root_reasoning.items())),
    }


def select_pilot_runs(runs: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Choose a small representative smoke-test subset for any valid matrix."""

    if not runs:
        return []

    selected: list[Mapping[str, Any]] = []
    selected_ids: set[str] = set()

    def add(run: Mapping[str, Any] | None) -> None:
        if run is None:
            return
        run_id = str(run.get("run_id"))
        if run_id not in selected_ids:
            selected.append(run)
            selected_ids.add(run_id)

    add(next((run for run in runs if run.get("cell_id") == "C0"), None))
    if not selected:
        add(runs[0])

    add(next((run for run in runs if run.get("spark_mode") == "proposal"), None))
    if len(selected) < 2:
        first_cell = selected[0].get("cell_id") if selected else None
        add(next((run for run in runs if run.get("cell_id") != first_cell), None))
    if len(selected) < 2:
        add(next((run for run in runs if str(run.get("run_id")) not in selected_ids), None))

    return selected[:2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and summarize an experiment matrix.")
    parser.add_argument(
        "config",
        nargs="?",
        default=str(REPO_ROOT / "configs" / "initial_experiment.yaml"),
        help="Path to the experiment config.",
    )
    parser.add_argument(
        "--runs",
        action="store_true",
        help="Print expanded run records instead of a compact summary.",
    )
    args = parser.parse_args(argv)

    config = load_experiment_config(args.config)
    runs = expand_experiment_matrix(config)
    payload: Any
    if args.runs:
        payload = runs
    else:
        payload = {
            "config": str(Path(args.config)),
            "summary": summarize_matrix(runs),
            "first_run_id": runs[0]["run_id"],
            "last_run_id": runs[-1]["run_id"],
        }

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _load_mapping_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ExperimentConfigError(f"{path}: file does not exist")

    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ExperimentConfigError(
                f"{path}: PyYAML is not installed, so this file must be JSON-compatible YAML: {exc}"
            ) from exc
    else:
        loaded = yaml.safe_load(text)

    if not isinstance(loaded, dict):
        raise ExperimentConfigError(f"{path}: expected top-level object")
    return loaded


def _repo_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _mapping(
    parent: Mapping[str, Any],
    key: str,
    errors: list[str],
    *,
    prefix: str | None = None,
) -> Mapping[str, Any]:
    value = parent.get(key)
    path = f"{prefix}.{key}" if prefix else key
    if not isinstance(value, Mapping):
        errors.append(f"{path}: expected object")
        return {}
    return value


def _list(parent: Mapping[str, Any], key: str, errors: list[str]) -> list[Any]:
    value = parent.get(key)
    if not isinstance(value, list):
        errors.append(f"{key}: expected list")
        return []
    return value


def _positive_int(
    parent: Mapping[str, Any],
    key: str,
    path: str,
    errors: list[str],
    *,
    allow_zero: bool = False,
) -> int | None:
    value = parent.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"{path}: expected integer")
        return None
    if allow_zero:
        if value < 0:
            errors.append(f"{path}: expected non-negative integer")
            return None
    elif value <= 0:
        errors.append(f"{path}: expected positive integer")
        return None
    return value


def _number(
    parent: Mapping[str, Any],
    key: str,
    path: str,
    errors: list[str],
    *,
    must_be_positive: bool = False,
) -> float | None:
    value = parent.get(key)
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        errors.append(f"{path}: expected number")
        return None
    if must_be_positive and value <= 0:
        errors.append(f"{path}: expected positive number")
        return None
    if not must_be_positive and value < 0:
        errors.append(f"{path}: expected non-negative number")
        return None
    return float(value)


def _validate_prompt_templates(prompt_templates: Mapping[str, Any], errors: list[str]) -> None:
    missing = REQUIRED_PROMPT_TEMPLATE_KEYS - set(prompt_templates)
    if missing:
        errors.append(f"paths.prompt_templates: missing keys {sorted(missing)}")
    for key, value in prompt_templates.items():
        _relative_path(value, f"paths.prompt_templates.{key}", errors)


def _relative_path(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value:
        errors.append(f"{path}: expected non-empty relative path string")
        return
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        errors.append(f"{path}: expected repository-relative path without parent traversal")


def _validate_spark_mode_definitions(
    spark_modes: Mapping[str, Any],
    errors: list[str],
) -> None:
    for mode_name, value in spark_modes.items():
        path = f"spark_modes.{mode_name}"
        if not isinstance(value, Mapping):
            errors.append(f"{path}: expected object")
            continue
        if value.get("leaf_write_mode") not in {"workspace-write", "read-only"}:
            errors.append(f"{path}.leaf_write_mode: expected workspace-write or read-only")
        if not isinstance(value.get("proposal_only"), bool):
            errors.append(f"{path}.proposal_only: expected boolean")
    direct = spark_modes.get("direct")
    proposal = spark_modes.get("proposal")
    if isinstance(direct, Mapping) and direct.get("proposal_only") is not False:
        errors.append("spark_modes.direct.proposal_only: expected false")
    if isinstance(direct, Mapping) and direct.get("leaf_write_mode") != "workspace-write":
        errors.append("spark_modes.direct.leaf_write_mode: expected workspace-write")
    if isinstance(proposal, Mapping) and proposal.get("proposal_only") is not True:
        errors.append("spark_modes.proposal.proposal_only: expected true")
    if isinstance(proposal, Mapping) and proposal.get("leaf_write_mode") != "read-only":
        errors.append("spark_modes.proposal.leaf_write_mode: expected read-only")


def _validate_scoring(scoring: Mapping[str, Any], errors: list[str]) -> None:
    weights = scoring.get("weights")
    if not isinstance(weights, Mapping):
        errors.append("scoring.weights: expected object")
        return

    total = 0.0
    for key, value in weights.items():
        path = f"scoring.weights.{key}"
        if key not in SCORING_COMPONENTS:
            errors.append(f"{path}: unknown scoring component")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{path}: expected number")
            continue
        if value < 0:
            errors.append(f"{path}: expected non-negative number")
            continue
        total += float(value)

    if abs(total - 1.0) > 0.000001:
        errors.append(f"scoring.weights: expected weights to sum to 1.0, got {total:.6f}")

    minimality = scoring.get("minimality")
    if minimality is not None:
        if not isinstance(minimality, Mapping):
            errors.append("scoring.minimality: expected object")
            return
        _number(minimality, "target_production_loc", "scoring.minimality.target_production_loc", errors)
        _number(
            minimality,
            "penalty_window",
            "scoring.minimality.penalty_window",
            errors,
            must_be_positive=True,
        )


def _validate_model(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or value not in ALLOWED_INITIAL_MODELS:
        errors.append(f"{path}: expected one of {sorted(ALLOWED_INITIAL_MODELS)}")


def _validate_reasoning(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or value not in VALID_REASONING:
        errors.append(f"{path}: expected one of {sorted(VALID_REASONING)}")


def _validate_prompt_template_reference(
    value: Any,
    prompt_templates: Mapping[str, Any],
    path: str,
    errors: list[str],
) -> None:
    if not isinstance(value, str) or value not in prompt_templates:
        errors.append(f"{path}: expected one of {sorted(prompt_templates)}")


def _validate_initial_root_reasoning(
    cell_id: str,
    reasoning: Any,
    path: str,
    errors: list[str],
) -> None:
    expected = {
        "C0": "xhigh",
        "C1": "medium",
        "C2": "high",
        "C3": "xhigh",
        "C4": "xhigh",
    }.get(cell_id)
    if expected is not None and reasoning != expected:
        errors.append(f"{path}.root.reasoning: {cell_id} requires {expected}")


def _validate_leaf(leaf: Mapping[str, Any], path: str, errors: list[str]) -> None:
    if leaf.get("model") != INITIAL_SPARK_MODEL:
        errors.append(f"{path}.leaf.model: expected {INITIAL_SPARK_MODEL}")

    reasoning_by_role = leaf.get("reasoning_by_role")
    if not isinstance(reasoning_by_role, Mapping) or not reasoning_by_role:
        errors.append(f"{path}.leaf.reasoning_by_role: expected non-empty object")
        return
    required_roles = {"implementer", "tester", "adversary"}
    if set(reasoning_by_role) != required_roles:
        errors.append(f"{path}.leaf.reasoning_by_role: expected exactly {sorted(required_roles)}")

    for role, reasoning in reasoning_by_role.items():
        role_path = f"{path}.leaf.reasoning_by_role.{role}"
        _validate_reasoning(reasoning, role_path, errors)
        if reasoning != INITIAL_SPARK_REASONING:
            errors.append(f"{role_path}: initial Spark reasoning must be xhigh")


def _cell_spark_modes(
    cell: Mapping[str, Any],
    path: str,
    spark_modes: Mapping[str, Any],
    errors: list[str],
) -> list[str]:
    value = cell.get("spark_modes")
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"{path}.spark_modes: expected list")
        return []

    modes: list[str] = []
    for mode in value:
        if not isinstance(mode, str):
            errors.append(f"{path}.spark_modes: expected mode names as strings")
            continue
        if mode not in spark_modes:
            errors.append(f"{path}.spark_modes: unknown Spark mode {mode!r}")
            continue
        modes.append(mode)
    return modes


def _expanded_leaf(cell: Mapping[str, Any]) -> dict[str, Any] | None:
    leaf = cell.get("leaf")
    if not isinstance(leaf, Mapping):
        return None

    expanded = copy.deepcopy(dict(leaf))
    subleads = cell.get("subleads")
    if "count" not in expanded and isinstance(subleads, Mapping):
        expanded["count"] = int(subleads["count"]) * int(subleads["leaves_per_sublead"])
    return expanded


def _run_id(cell_id: str, mode: str | None, repeat_index: int) -> str:
    suffix = f"r{repeat_index:02d}"
    if mode is None:
        return f"{cell_id}_{suffix}"
    return f"{cell_id}_{mode}_{suffix}"


def _is_filesystem_safe_id(value: str) -> bool:
    return all(character.isalnum() or character in {"_", "-"} for character in value)


if __name__ == "__main__":
    raise SystemExit(main())
