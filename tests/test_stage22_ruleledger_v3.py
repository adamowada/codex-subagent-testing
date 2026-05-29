from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Any

from harness.hidden_runner import load_cases


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = REPO_ROOT / "plans" / "stage-22-ruleledger-v3.md"
GENERATOR_DIR = REPO_ROOT / "hidden_tests" / "generators"
GENERATOR_PATH = GENERATOR_DIR / "generate_v3_cases.py"
CASES_V3_DIR = REPO_ROOT / "hidden_tests" / "cases_v3"
TEMPLATE_V3 = REPO_ROOT / "benchmark_template_v3"

REQUIRED_CATEGORIES = {
    "evolution",
    "fail_to_pass",
    "pass_to_pass",
    "localization",
    "metamorphic",
    "performance",
    "parity",
}


def test_v3_plan_records_public_benchmark_design_basis() -> None:
    text = PLAN_PATH.read_text(encoding="utf-8")

    assert "SWE-Bench Pro" in text
    assert "SWE-CI" in text
    assert "SWE-fficiency" in text
    assert "ProgramBench" in text
    assert "low`, `medium`, `high`, and `xhigh`" in text
    assert "fail-to-pass" in text
    assert "pass-to-pass" in text


def test_v3_template_exposes_issue_and_architecture_docs() -> None:
    readme = (TEMPLATE_V3 / "README.md").read_text(encoding="utf-8")
    issue = (TEMPLATE_V3 / "docs" / "ruleledger_v3_issue_brief.md").read_text(encoding="utf-8")
    architecture = (TEMPLATE_V3 / "docs" / "ruleledger_v3_architecture.md").read_text(encoding="utf-8")

    assert "docs/ruleledger_v3_issue_brief.md" in readme
    assert "docs/ruleledger_v3_architecture.md" in readme
    assert "Preserve all v1 and v2 public APIs" in issue
    assert "near-linear account aggregation" in issue
    assert "src/replay.ts" in architecture
    assert "ruleledger/replay.py" in architecture


def test_v3_template_has_multi_file_module_boundaries() -> None:
    ts_files = {path.name for path in (TEMPLATE_V3 / "src").glob("*.ts")}
    py_files = {path.name for path in (TEMPLATE_V3 / "ruleledger").glob("*.py")}

    assert {
        "billing.ts",
        "domain.ts",
        "index.ts",
        "normalize.ts",
        "replay.ts",
        "report.ts",
        "runtime.ts",
    }.issubset(ts_files)
    assert {
        "__init__.py",
        "_runtime.py",
        "billing.py",
        "domain.py",
        "engine.py",
        "normalize.py",
        "replay.py",
        "reporting.py",
    }.issubset(py_files)

    index_text = (TEMPLATE_V3 / "src" / "index.ts").read_text(encoding="utf-8")
    engine_text = (TEMPLATE_V3 / "ruleledger" / "engine.py").read_text(encoding="utf-8")
    assert "export * from \"./normalize.js\"" in index_text
    assert "from .normalize import" in engine_text
    assert "from .replay import" in engine_text


def test_generate_v3_cases_is_byte_deterministic(tmp_path: Path) -> None:
    generator = _load_module("generate_v3_cases_test_determinism", GENERATOR_PATH)
    cases_dir = tmp_path / "cases_v3"

    cases_dir.mkdir()
    (cases_dir / "stale.json").write_text("stale\n", encoding="utf-8")
    generator.main(cases_dir)
    first_snapshot = _snapshot(cases_dir)
    generator.main(cases_dir)
    second_snapshot = _snapshot(cases_dir)

    assert "stale.json" not in first_snapshot
    assert first_snapshot == second_snapshot


def test_checked_in_v3_cases_match_generator_output(tmp_path: Path) -> None:
    generator = _load_module("generate_v3_cases_test_checked_in", GENERATOR_PATH)
    cases_dir = tmp_path / "cases_v3"

    generator.main(cases_dir)

    assert _snapshot(cases_dir) == _snapshot(CASES_V3_DIR)


def test_generate_v3_cases_cli_supports_safe_output_directory(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cli_cases_v3"

    completed = subprocess.run(
        [sys.executable, str(GENERATOR_PATH), "--cases-dir", str(cases_dir)],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    assert _snapshot(cases_dir) == _snapshot(CASES_V3_DIR)


def test_v3_hidden_manifest_loads_required_categories_without_payload_leakage() -> None:
    manifest, cases = load_cases(CASES_V3_DIR)

    assert manifest["schema_version"] == 3
    assert manifest["benchmark"] == "ruleledger_v3"
    assert set(manifest["category_weights"]) == REQUIRED_CATEGORIES
    assert {case["category"] for case in cases} == REQUIRED_CATEGORIES
    assert all(case["points"] > 0 for case in cases)


def test_v3_performance_case_is_large_enough_to_exercise_algorithmic_shape() -> None:
    payload = json.loads((CASES_V3_DIR / "performance.json").read_text(encoding="utf-8"))
    event_counts = [
        len(case["input"]["raw_events"])
        for case in payload["cases"]
        if case["category"] == "performance"
    ]

    assert event_counts
    assert min(event_counts) >= 10_000


def _load_module(name: str, path: Path) -> ModuleType:
    if str(GENERATOR_DIR) not in sys.path:
        sys.path.insert(0, str(GENERATOR_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _snapshot(path: Path) -> dict[str, bytes]:
    return {
        str(file.relative_to(path)): file.read_bytes()
        for file in sorted(path.glob("*.json"))
    }
