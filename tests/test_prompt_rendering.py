from __future__ import annotations

from pathlib import Path
import tomllib

import pytest

from harness.matrix import expand_experiment_matrix, load_experiment_config
from harness.prompt_rendering import (
    AGENT_SNIPPETS,
    build_template_context,
    render_codex_config,
    render_implementation_prompt,
    render_judge_prompt,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "configs" / "initial_experiment.yaml"


@pytest.fixture
def config() -> dict:
    return load_experiment_config(CONFIG_PATH)


@pytest.fixture
def runs(config: dict) -> list[dict]:
    return expand_experiment_matrix(config)


def test_configured_template_paths_exist(config: dict) -> None:
    paths = config["paths"]
    for relative_path in paths["prompt_templates"].values():
        assert (REPO_ROOT / relative_path).is_file(), relative_path
    assert (REPO_ROOT / paths["codex_config_template"]).is_file()

    for snippet in AGENT_SNIPPETS.values():
        assert (REPO_ROOT / snippet["path"]).is_file(), snippet["path"]


def test_rendering_succeeds_for_all_runs(runs: list[dict]) -> None:
    for run in runs:
        implementation_prompt = render_implementation_prompt(run, REPO_ROOT)
        judge_prompt = render_judge_prompt(run, REPO_ROOT)
        config_files = render_codex_config(run, REPO_ROOT)

        assert "Rendered Implementation Prompt" in implementation_prompt
        assert "Blind RuleLedger Judge" in judge_prompt
        assert "config.toml" in config_files
        tomllib.loads(config_files["config.toml"])


def test_rendering_is_deterministic(runs: list[dict]) -> None:
    run = _run(runs, "C1", "direct")

    assert render_implementation_prompt(run, REPO_ROOT) == render_implementation_prompt(run, REPO_ROOT)
    assert render_codex_config(run, REPO_ROOT) == render_codex_config(run, REPO_ROOT)


def test_c0_prompt_is_solo_only(runs: list[dict]) -> None:
    prompt = render_implementation_prompt(_run(runs, "C0", None), REPO_ROOT)

    assert "This is a solo implementation run" in prompt
    assert "Do not spawn subagents" in prompt
    assert "Assign exactly six Spark leaves" not in prompt
    assert "Sublead A:" not in prompt


def test_flat_prompt_contains_six_leaf_roles(runs: list[dict]) -> None:
    prompt = render_implementation_prompt(_run(runs, "C1", "direct"), REPO_ROOT)

    for role in [
        "TypeScript parser and normalizer",
        "TypeScript reducer, entitlements, and report",
        "Python parser and normalizer",
        "Python reducer, entitlements, and report",
        "Cross-language fixture and public-test writer",
        "Adversarial reviewer",
    ]:
        assert role in prompt


def test_c4_prompt_contains_sublead_ownership(runs: list[dict]) -> None:
    prompt = render_implementation_prompt(_run(runs, "C4", "direct"), REPO_ROOT)

    assert "Sublead A: TypeScript Implementation" in prompt
    assert "Sublead B: Python Implementation" in prompt
    assert "Sublead C: Parity, Fixtures, Public Tests, And Risk" in prompt
    assert "Each sublead coordinates six Spark xhigh leaves" in prompt


def test_direct_and_proposal_mode_text_is_distinct(runs: list[dict]) -> None:
    direct = render_implementation_prompt(_run(runs, "C1", "direct"), REPO_ROOT)
    proposal = render_implementation_prompt(_run(runs, "C1", "proposal"), REPO_ROOT)

    assert "Current mode: `direct`" in direct
    assert "may edit assigned implementation files" in direct
    assert "Current mode: `proposal`" in proposal
    assert "Spark leaves are read-only and must not edit files" in proposal


def test_every_implementation_prompt_has_safety_and_json_contract(runs: list[dict]) -> None:
    for run in runs:
        prompt = render_implementation_prompt(run, REPO_ROOT)
        assert "Do not invoke `codex`" in prompt
        assert "external AI" in prompt
        assert '"nested_codex_invoked": false' in prompt
        assert "Finish with strict JSON only" in prompt


def test_judge_prompt_does_not_reveal_topology(runs: list[dict]) -> None:
    forbidden = [
        "C0",
        "C1",
        "C2",
        "C3",
        "C4",
        "flat_spark",
        "depth2_subleads",
        "solo_gpt55",
        "Spark mode",
    ]

    for run in runs:
        prompt = render_judge_prompt(run, REPO_ROOT)
        for value in forbidden:
            assert value not in prompt


def test_codex_config_for_c0_has_no_subagent_templates(runs: list[dict]) -> None:
    config = tomllib.loads(render_codex_config(_run(runs, "C0", None), REPO_ROOT)["config.toml"])

    assert config["model"] == "gpt-5.5"
    assert config["model_reasoning_effort"] == "xhigh"
    assert config["agents"]["max_depth"] == 0
    assert config["agents"]["max_threads"] == 1
    assert set(config["agents"]) == {"max_depth", "max_threads"}


def test_codex_config_direct_mode_uses_writable_leaf_roles(runs: list[dict]) -> None:
    config = tomllib.loads(render_codex_config(_run(runs, "C1", "direct"), REPO_ROOT)["config.toml"])
    templates = config["agents"]

    assert templates["spark_direct_implementer"]["model"] == "gpt-5.3-codex-spark"
    assert templates["spark_direct_implementer"]["model_reasoning_effort"] == "xhigh"
    assert templates["spark_direct_implementer"]["sandbox"] == "workspace-write"
    assert templates["spark_direct_tester"]["sandbox"] == "workspace-write"
    assert templates["spark_adversary"]["sandbox"] == "read-only"
    assert "spark_proposal_implementer" not in templates


def test_codex_config_proposal_mode_uses_read_only_leaf_roles(runs: list[dict]) -> None:
    config = tomllib.loads(render_codex_config(_run(runs, "C1", "proposal"), REPO_ROOT)["config.toml"])
    templates = config["agents"]

    assert templates["spark_proposal_implementer"]["sandbox"] == "read-only"
    assert templates["spark_proposal_tester"]["sandbox"] == "read-only"
    assert templates["spark_adversary"]["sandbox"] == "read-only"
    assert "spark_direct_implementer" not in templates


def test_codex_config_c4_includes_medium_sublead_template(runs: list[dict]) -> None:
    config = tomllib.loads(render_codex_config(_run(runs, "C4", "direct"), REPO_ROOT)["config.toml"])
    templates = config["agents"]

    assert config["agents"]["max_depth"] == 2
    assert config["agents"]["max_threads"] >= 24
    assert templates["gpt55_medium_sublead"]["model"] == "gpt-5.5"
    assert templates["gpt55_medium_sublead"]["model_reasoning_effort"] == "medium"


def test_template_context_has_explicit_empty_values_for_c0(runs: list[dict]) -> None:
    context = build_template_context(_run(runs, "C0", None))

    assert context["spark_mode"] == "none"
    assert context["leaf_model"] == "none"
    assert context["leaf_count"] == "0"
    assert context["sublead_model"] == "none"
    assert context["sublead_count"] == "0"


def test_prompt_and_config_templates_do_not_reference_hidden_case_files() -> None:
    forbidden = [
        "hidden_tests/cases",
        "parse_validation.json",
        "normalization.json",
        "state_reduction.json",
        "reporting.json",
        "immutability.json",
        "parity.json",
    ]
    paths = [
        *(REPO_ROOT / "prompts").glob("*.md"),
        REPO_ROOT / "codex_templates" / "config.toml.j2",
        *(REPO_ROOT / "codex_templates" / "agents").glob("*.md"),
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        for value in forbidden:
            assert value not in text


def _run(runs: list[dict], cell_id: str, spark_mode: str | None) -> dict:
    return next(run for run in runs if run["cell_id"] == cell_id and run["spark_mode"] == spark_mode)
