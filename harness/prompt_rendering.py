from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any, Mapping

from harness.matrix import REPO_ROOT, expand_experiment_matrix, load_experiment_config


PLACEHOLDER_PATTERN = re.compile(r"{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}")

AGENT_SNIPPETS = {
    "spark_direct_implementer": {
        "path": "codex_templates/agents/spark_direct_implementer.md",
        "model_key": "leaf_model",
        "reasoning_key": "spark_reasoning_implementer",
        "sandbox": "workspace-write",
        "description": "Spark direct implementer",
    },
    "spark_proposal_implementer": {
        "path": "codex_templates/agents/spark_proposal_implementer.md",
        "model_key": "leaf_model",
        "reasoning_key": "spark_reasoning_implementer",
        "sandbox": "read-only",
        "description": "Spark proposal implementer",
    },
    "spark_direct_tester": {
        "path": "codex_templates/agents/spark_direct_tester.md",
        "model_key": "leaf_model",
        "reasoning_key": "spark_reasoning_tester",
        "sandbox": "workspace-write",
        "description": "Spark direct tester",
    },
    "spark_proposal_tester": {
        "path": "codex_templates/agents/spark_proposal_tester.md",
        "model_key": "leaf_model",
        "reasoning_key": "spark_reasoning_tester",
        "sandbox": "read-only",
        "description": "Spark proposal tester",
    },
    "spark_adversary": {
        "path": "codex_templates/agents/spark_adversary.md",
        "model_key": "leaf_model",
        "reasoning_key": "spark_reasoning_adversary",
        "sandbox": "read-only",
        "description": "Spark adversarial reviewer",
    },
    "gpt55_medium_sublead": {
        "path": "codex_templates/agents/gpt55_medium_sublead.md",
        "model_key": "sublead_model",
        "reasoning_key": "sublead_reasoning",
        "sandbox": "workspace-write",
        "description": "GPT-5.5 medium sublead",
    },
}


class PromptRenderingError(ValueError):
    """Raised when prompt or config templates cannot be rendered safely."""


def render_implementation_prompt(
    run: Mapping[str, Any],
    repo_root: str | Path = REPO_ROOT,
) -> str:
    """Render the measured implementation prompt for one expanded run record."""

    root = Path(repo_root)
    context = build_template_context(run)
    common = _render_template_file(root, _required_str(run, "common_prompt_template_path"), context)
    task = _render_template_file(root, _required_str(run, "prompt_template_path"), context)

    text = "\n\n".join(
        [
            "# Rendered Implementation Prompt",
            _run_metadata_block(context),
            common.strip(),
            task.strip(),
        ]
    )
    return _final_text(text)


def render_judge_prompt(
    run: Mapping[str, Any],
    repo_root: str | Path = REPO_ROOT,
) -> str:
    """Render the blind judge prompt for one expanded run record."""

    root = Path(repo_root)
    context = build_template_context(run)
    judge = _required_mapping(run, "judge")
    prompt_key = _required_str(judge, "prompt_template")
    if prompt_key != "judge":
        raise PromptRenderingError(f"judge.prompt_template: expected 'judge', got {prompt_key!r}")

    judge_path = _required_str(run, "judge_prompt_template_path")
    text = _render_template_file(root, judge_path, context)
    return _final_text(text)


def render_codex_config(
    run: Mapping[str, Any],
    repo_root: str | Path = REPO_ROOT,
) -> dict[str, str]:
    """Render Codex config artifacts for one expanded run record.

    The returned mapping is keyed by repository-relative output paths for a run's
    future `codex_config/` directory.
    """

    root = Path(repo_root)
    context = build_template_context(run)
    rendered_snippets = _render_agent_snippets(run, root, context)
    context = dict(context)
    context["agent_templates"] = _agent_template_toml(rendered_snippets, context)

    config_path = _required_str(run, "codex_config_template_path")
    rendered = {
        "config.toml": _render_template_file(root, config_path, context),
    }
    for name, instructions in rendered_snippets.items():
        rendered[f"agents/{name}.toml"] = _agent_role_toml(instructions)

    return {path: _final_text(text) for path, text in rendered.items()}


def build_template_context(run: Mapping[str, Any]) -> dict[str, str]:
    """Return the explicit prompt/config template context for a run record."""

    root = _required_mapping(run, "root")
    agents = _required_mapping(run, "agents")
    timeouts = _required_mapping(run, "timeouts")
    judge = _required_mapping(run, "judge")

    spark_mode = run.get("spark_mode")
    spark_mode_name = str(spark_mode) if spark_mode else "none"
    spark_config = run.get("spark_mode_config") if spark_mode else None
    if spark_config is not None and not isinstance(spark_config, Mapping):
        raise PromptRenderingError("spark_mode_config: expected object when spark_mode is set")

    leaf = run.get("leaf")
    if leaf is not None and not isinstance(leaf, Mapping):
        raise PromptRenderingError("leaf: expected object or null")
    subleads = run.get("subleads")
    if subleads is not None and not isinstance(subleads, Mapping):
        raise PromptRenderingError("subleads: expected object or null")

    reasoning_by_role = leaf.get("reasoning_by_role", {}) if leaf else {}
    if not isinstance(reasoning_by_role, Mapping):
        raise PromptRenderingError("leaf.reasoning_by_role: expected object")

    proposal_only = bool(spark_config.get("proposal_only")) if spark_config else False
    leaf_write_mode = str(spark_config.get("leaf_write_mode")) if spark_config else "none"
    topology = _required_str(run, "topology")

    context = {
        "run_id": _required_str(run, "run_id"),
        "cell_id": _required_str(run, "cell_id"),
        "cell_name": _required_str(run, "cell_name"),
        "repeat_index": str(_required_int(run, "repeat_index")),
        "topology": topology,
        "spark_mode": spark_mode_name,
        "spark_mode_name": spark_mode_name,
        "proposal_only": _bool_text(proposal_only),
        "leaf_write_mode": leaf_write_mode,
        "root_model": _required_str(root, "model"),
        "root_reasoning": _required_str(root, "reasoning"),
        "sublead_model": str(subleads.get("model", "none")) if subleads else "none",
        "sublead_reasoning": str(subleads.get("reasoning", "none")) if subleads else "none",
        "sublead_count": str(subleads.get("count", 0)) if subleads else "0",
        "leaves_per_sublead": str(subleads.get("leaves_per_sublead", 0)) if subleads else "0",
        "leaf_model": str(leaf.get("model", "none")) if leaf else "none",
        "leaf_count": str(leaf.get("count", 0)) if leaf else "0",
        "spark_reasoning_implementer": str(reasoning_by_role.get("implementer", "none")),
        "spark_reasoning_tester": str(reasoning_by_role.get("tester", "none")),
        "spark_reasoning_adversary": str(reasoning_by_role.get("adversary", "none")),
        "agents_max_depth": str(_required_int(agents, "max_depth")),
        "agents_max_threads": str(_required_int(agents, "max_threads")),
        "implementation_timeout_seconds": str(_required_int(timeouts, "implementation_seconds")),
        "judge_timeout_seconds": str(_required_int(timeouts, "judge_seconds")),
        "judge_model": _required_str(judge, "model"),
        "judge_reasoning": _required_str(judge, "reasoning"),
        "judge_sandbox": _required_str(judge, "sandbox"),
    }
    context["flat_mode_guidance"] = (
        _flat_mode_guidance(spark_mode_name, leaf_write_mode, proposal_only)
        if topology == "flat_spark"
        else "Flat Spark guidance does not apply to this topology."
    )
    context["depth2_mode_guidance"] = (
        _depth2_mode_guidance(spark_mode_name, leaf_write_mode, proposal_only)
        if topology == "depth2_subleads"
        else "Depth-2 guidance does not apply to this topology."
    )
    return context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render prompts and Codex config for one run.")
    parser.add_argument(
        "config",
        nargs="?",
        default=str(REPO_ROOT / "configs" / "initial_experiment.yaml"),
        help="Path to the experiment config.",
    )
    parser.add_argument("--run-id", help="Run ID to render. Defaults to the first expanded run.")
    parser.add_argument(
        "--kind",
        choices=["implementation", "judge", "config"],
        default="implementation",
        help="Artifact kind to print.",
    )
    args = parser.parse_args(argv)

    config = load_experiment_config(args.config)
    runs = expand_experiment_matrix(config)
    if args.run_id:
        run = next((candidate for candidate in runs if candidate["run_id"] == args.run_id), None)
        if run is None:
            raise PromptRenderingError(f"run id {args.run_id!r} was not found")
    else:
        run = runs[0]

    if args.kind == "implementation":
        print(render_implementation_prompt(run), end="")
    elif args.kind == "judge":
        print(render_judge_prompt(run), end="")
    else:
        print(json.dumps(render_codex_config(run), indent=2, sort_keys=True))
    return 0


def _render_agent_snippets(
    run: Mapping[str, Any],
    repo_root: Path,
    context: Mapping[str, str],
) -> dict[str, str]:
    names = _selected_agent_snippets(run)
    rendered: dict[str, str] = {}
    for name in names:
        snippet = AGENT_SNIPPETS[name]
        rendered[name] = _render_template_file(repo_root, str(snippet["path"]), context)
    return rendered


def _selected_agent_snippets(run: Mapping[str, Any]) -> list[str]:
    topology = _required_str(run, "topology")
    mode = run.get("spark_mode")

    if topology == "solo":
        return []
    if mode == "direct":
        spark = ["spark_direct_implementer", "spark_direct_tester", "spark_adversary"]
    elif mode == "proposal":
        spark = ["spark_proposal_implementer", "spark_proposal_tester", "spark_adversary"]
    else:
        raise PromptRenderingError(f"spark_mode: expected direct or proposal for {topology}, got {mode!r}")

    if topology == "flat_spark":
        return spark
    if topology == "depth2_subleads":
        return ["gpt55_medium_sublead", *spark]
    raise PromptRenderingError(f"topology: unsupported topology {topology!r}")


def _agent_template_toml(
    rendered_snippets: Mapping[str, str],
    context: Mapping[str, str],
) -> str:
    if not rendered_snippets:
        return "# No custom subagent templates are available for this solo run."

    blocks: list[str] = []
    for name in rendered_snippets:
        snippet = AGENT_SNIPPETS[name]
        model = context[str(snippet["model_key"])]
        reasoning = context[str(snippet["reasoning_key"])]
        sandbox = _snippet_sandbox(name, context)
        description = str(snippet["description"])
        blocks.append(
            "\n".join(
                [
                    f"[agents.{_toml_key(name)}]",
                    f'description = "{_toml_escape(description)}"',
                    f'model = "{_toml_escape(model)}"',
                    f'model_reasoning_effort = "{_toml_escape(reasoning)}"',
                    f'sandbox = "{_toml_escape(sandbox)}"',
                    f'config_file = "agents/{_toml_escape(name)}.toml"',
                ]
            )
        )
    return "\n\n".join(blocks)


def _agent_role_toml(instructions: str) -> str:
    text = _final_text(instructions)
    if "'''" not in text:
        return f"instructions = '''\n{text}'''\n"
    return f"instructions = {json.dumps(text)}\n"


def _snippet_sandbox(name: str, context: Mapping[str, str]) -> str:
    if name == "spark_adversary" or name.startswith("spark_proposal_"):
        return "read-only"
    if name.startswith("spark_direct_"):
        return context["leaf_write_mode"]
    return str(AGENT_SNIPPETS[name]["sandbox"])


def _render_template_file(
    repo_root: Path,
    relative_path: str,
    context: Mapping[str, str],
) -> str:
    path = _repo_file(repo_root, relative_path)
    return _render_text(path.read_text(encoding="utf-8"), context, str(path))


def _render_text(text: str, context: Mapping[str, str], source: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise PromptRenderingError(f"{source}: unknown template variable {key!r}")
        return context[key]

    return PLACEHOLDER_PATTERN.sub(replace, normalized)


def _repo_file(repo_root: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise PromptRenderingError(f"{relative_path}: expected repository-relative path")
    resolved = repo_root / path
    if not resolved.exists():
        raise PromptRenderingError(f"{resolved}: template file does not exist")
    if not resolved.is_file():
        raise PromptRenderingError(f"{resolved}: expected file")
    return resolved


def _run_metadata_block(context: Mapping[str, str]) -> str:
    lines = [
        "## Run Metadata",
        "",
        "```text",
        f"run_id: {context['run_id']}",
        f"cell_id: {context['cell_id']}",
        f"cell_name: {context['cell_name']}",
        f"repeat_index: {context['repeat_index']}",
        f"topology: {context['topology']}",
        f"spark_mode: {context['spark_mode']}",
        f"proposal_only: {context['proposal_only']}",
        f"leaf_write_mode: {context['leaf_write_mode']}",
        f"root_model: {context['root_model']}",
        f"root_reasoning: {context['root_reasoning']}",
        f"sublead_model: {context['sublead_model']}",
        f"sublead_reasoning: {context['sublead_reasoning']}",
        f"sublead_count: {context['sublead_count']}",
        f"leaves_per_sublead: {context['leaves_per_sublead']}",
        f"leaf_model: {context['leaf_model']}",
        f"leaf_count: {context['leaf_count']}",
        f"agents_max_depth: {context['agents_max_depth']}",
        f"agents_max_threads: {context['agents_max_threads']}",
        f"implementation_timeout_seconds: {context['implementation_timeout_seconds']}",
        "```",
    ]
    return "\n".join(lines)


def _flat_mode_guidance(mode: str, leaf_write_mode: str, proposal_only: bool) -> str:
    if mode == "direct" and not proposal_only:
        return (
            "Direct mode is active. Spark implementer leaves may edit assigned implementation files, "
            "and the Spark tester leaf may edit assigned visible tests or fixtures. Their leaf write "
            f"mode is `{leaf_write_mode}`. The adversarial reviewer remains read-only."
        )
    if mode == "proposal" and proposal_only:
        return (
            "Proposal mode is active. Spark leaves are read-only and must not edit files. They should "
            "return proposed patches, findings, test ideas, and integration notes for the root lead "
            "to apply."
        )
    raise PromptRenderingError(f"flat Spark run has inconsistent mode settings: {mode!r}")


def _depth2_mode_guidance(mode: str, leaf_write_mode: str, proposal_only: bool) -> str:
    if mode == "direct" and not proposal_only:
        return (
            "Direct mode is active. Spark implementer and tester leaves may edit only within their "
            f"assigned scope using `{leaf_write_mode}`. Adversarial leaves remain read-only. Subleads "
            "must coordinate file ownership through the root lead."
        )
    if mode == "proposal" and proposal_only:
        return (
            "Proposal mode is active. Spark leaves are read-only and must not edit files. Subleads "
            "collect proposals from leaves, decide what to recommend, and let the root lead integrate "
            "accepted changes."
        )
    raise PromptRenderingError(f"depth-2 run has inconsistent mode settings: {mode!r}")


def _required_mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise PromptRenderingError(f"{key}: expected object")
    return value


def _required_str(parent: Mapping[str, Any], key: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value:
        raise PromptRenderingError(f"{key}: expected non-empty string")
    return value


def _required_int(parent: Mapping[str, Any], key: str) -> int:
    value = parent.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise PromptRenderingError(f"{key}: expected integer")
    return value


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _final_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip() + "\n"


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _toml_key(value: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        return value
    return f'"{_toml_escape(value)}"'


if __name__ == "__main__":
    raise SystemExit(main())
