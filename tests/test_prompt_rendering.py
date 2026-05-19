from __future__ import annotations

from pathlib import Path
import tomllib
import unittest

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


class PromptRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_experiment_config(CONFIG_PATH)
        self.runs = expand_experiment_matrix(self.config)

    def test_configured_template_paths_exist(self) -> None:
        paths = self.config["paths"]
        for relative_path in paths["prompt_templates"].values():
            self.assertTrue((REPO_ROOT / relative_path).is_file(), relative_path)
        self.assertTrue((REPO_ROOT / paths["codex_config_template"]).is_file())

        for snippet in AGENT_SNIPPETS.values():
            self.assertTrue((REPO_ROOT / snippet["path"]).is_file(), snippet["path"])

    def test_rendering_succeeds_for_all_runs(self) -> None:
        for run in self.runs:
            with self.subTest(run_id=run["run_id"]):
                implementation_prompt = render_implementation_prompt(run, REPO_ROOT)
                judge_prompt = render_judge_prompt(run, REPO_ROOT)
                config_files = render_codex_config(run, REPO_ROOT)

                self.assertIn("Rendered Implementation Prompt", implementation_prompt)
                self.assertIn("Blind RuleLedger Judge", judge_prompt)
                self.assertIn("config.toml", config_files)
                tomllib.loads(config_files["config.toml"])

    def test_rendering_is_deterministic(self) -> None:
        run = self._run("C1", "direct")

        self.assertEqual(
            render_implementation_prompt(run, REPO_ROOT),
            render_implementation_prompt(run, REPO_ROOT),
        )
        self.assertEqual(render_codex_config(run, REPO_ROOT), render_codex_config(run, REPO_ROOT))

    def test_c0_prompt_is_solo_only(self) -> None:
        prompt = render_implementation_prompt(self._run("C0", None), REPO_ROOT)

        self.assertIn("This is a solo implementation run", prompt)
        self.assertIn("Do not spawn subagents", prompt)
        self.assertNotIn("Assign exactly six Spark leaves", prompt)
        self.assertNotIn("Sublead A:", prompt)

    def test_flat_prompt_contains_six_leaf_roles(self) -> None:
        prompt = render_implementation_prompt(self._run("C1", "direct"), REPO_ROOT)

        for role in [
            "TypeScript parser and normalizer",
            "TypeScript reducer, entitlements, and report",
            "Python parser and normalizer",
            "Python reducer, entitlements, and report",
            "Cross-language fixture and public-test writer",
            "Adversarial reviewer",
        ]:
            self.assertIn(role, prompt)

    def test_c4_prompt_contains_sublead_ownership(self) -> None:
        prompt = render_implementation_prompt(self._run("C4", "direct"), REPO_ROOT)

        self.assertIn("Sublead A: TypeScript Implementation", prompt)
        self.assertIn("Sublead B: Python Implementation", prompt)
        self.assertIn("Sublead C: Parity, Fixtures, Public Tests, And Risk", prompt)
        self.assertIn("Each sublead coordinates six Spark xhigh leaves", prompt)

    def test_direct_and_proposal_mode_text_is_distinct(self) -> None:
        direct = render_implementation_prompt(self._run("C1", "direct"), REPO_ROOT)
        proposal = render_implementation_prompt(self._run("C1", "proposal"), REPO_ROOT)

        self.assertIn("Current mode: `direct`", direct)
        self.assertIn("may edit assigned implementation files", direct)
        self.assertIn("Current mode: `proposal`", proposal)
        self.assertIn("Spark leaves are read-only and must not edit files", proposal)

    def test_every_implementation_prompt_has_safety_and_json_contract(self) -> None:
        for run in self.runs:
            with self.subTest(run_id=run["run_id"]):
                prompt = render_implementation_prompt(run, REPO_ROOT)
                self.assertIn("Do not invoke `codex`", prompt)
                self.assertIn("external AI", prompt)
                self.assertIn('"nested_codex_invoked": false', prompt)
                self.assertIn("Finish with strict JSON only", prompt)

    def test_judge_prompt_does_not_reveal_topology(self) -> None:
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

        for run in self.runs:
            with self.subTest(run_id=run["run_id"]):
                prompt = render_judge_prompt(run, REPO_ROOT)
                for value in forbidden:
                    self.assertNotIn(value, prompt)

    def test_codex_config_for_c0_has_no_subagent_templates(self) -> None:
        config = tomllib.loads(render_codex_config(self._run("C0", None), REPO_ROOT)["config.toml"])

        self.assertEqual(config["model"], "gpt-5.5")
        self.assertEqual(config["model_reasoning_effort"], "xhigh")
        self.assertEqual(config["agents"]["max_depth"], 0)
        self.assertEqual(config["agents"]["max_threads"], 1)
        self.assertNotIn("templates", config["agents"])

    def test_codex_config_direct_mode_uses_writable_leaf_roles(self) -> None:
        config = tomllib.loads(render_codex_config(self._run("C1", "direct"), REPO_ROOT)["config.toml"])
        templates = {template["name"]: template for template in config["agents"]["templates"]}

        self.assertEqual(templates["spark_direct_implementer"]["model"], "gpt-5.3-codex-spark")
        self.assertEqual(templates["spark_direct_implementer"]["model_reasoning_effort"], "xhigh")
        self.assertEqual(templates["spark_direct_implementer"]["sandbox"], "workspace-write")
        self.assertEqual(templates["spark_direct_tester"]["sandbox"], "workspace-write")
        self.assertEqual(templates["spark_adversary"]["sandbox"], "read-only")
        self.assertNotIn("spark_proposal_implementer", templates)

    def test_codex_config_proposal_mode_uses_read_only_leaf_roles(self) -> None:
        config = tomllib.loads(render_codex_config(self._run("C1", "proposal"), REPO_ROOT)["config.toml"])
        templates = {template["name"]: template for template in config["agents"]["templates"]}

        self.assertEqual(templates["spark_proposal_implementer"]["sandbox"], "read-only")
        self.assertEqual(templates["spark_proposal_tester"]["sandbox"], "read-only")
        self.assertEqual(templates["spark_adversary"]["sandbox"], "read-only")
        self.assertNotIn("spark_direct_implementer", templates)

    def test_codex_config_c4_includes_medium_sublead_template(self) -> None:
        config = tomllib.loads(render_codex_config(self._run("C4", "direct"), REPO_ROOT)["config.toml"])
        templates = {template["name"]: template for template in config["agents"]["templates"]}

        self.assertEqual(config["agents"]["max_depth"], 2)
        self.assertGreaterEqual(config["agents"]["max_threads"], 24)
        self.assertEqual(templates["gpt55_medium_sublead"]["model"], "gpt-5.5")
        self.assertEqual(templates["gpt55_medium_sublead"]["model_reasoning_effort"], "medium")

    def test_template_context_has_explicit_empty_values_for_c0(self) -> None:
        context = build_template_context(self._run("C0", None))

        self.assertEqual(context["spark_mode"], "none")
        self.assertEqual(context["leaf_model"], "none")
        self.assertEqual(context["leaf_count"], "0")
        self.assertEqual(context["sublead_model"], "none")
        self.assertEqual(context["sublead_count"], "0")

    def test_prompt_and_config_templates_do_not_reference_hidden_case_files(self) -> None:
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
            with self.subTest(path=str(path)):
                for value in forbidden:
                    self.assertNotIn(value, text)

    def _run(self, cell_id: str, spark_mode: str | None) -> dict:
        return next(
            run
            for run in self.runs
            if run["cell_id"] == cell_id and run["spark_mode"] == spark_mode
        )


if __name__ == "__main__":
    unittest.main()
