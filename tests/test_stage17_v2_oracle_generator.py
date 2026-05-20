from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_DIR = REPO_ROOT / "hidden_tests" / "generators"
ORACLE_PATH = GENERATOR_DIR / "ruleledger_v2_oracle.py"
GENERATOR_PATH = GENERATOR_DIR / "generate_v2_cases.py"
CASES_V2_DIR = REPO_ROOT / "hidden_tests" / "cases_v2"
SEMANTICS_PATH = REPO_ROOT / "benchmark_template_v2" / "docs" / "ruleledger_v2_semantics.md"
CONFIG_PATH = REPO_ROOT / "configs" / "ruleledger_v2.yaml"

REQUIRED_CATEGORIES = {
    "parse_validation",
    "normalization",
    "bitemporal_replay",
    "lifecycle_precedence",
    "billing_proration",
    "account_merges",
    "metamorphic_invariants",
    "performance",
    "reporting",
    "parity",
}


def test_v2_oracle_is_private_and_independent_from_starter() -> None:
    source = ORACLE_PATH.read_text(encoding="utf-8")

    assert ORACLE_PATH.exists()
    assert "benchmark_template_v2" not in source
    assert "ruleledger.engine" not in source
    assert "../benchmark_template" not in source


def test_v2_oracle_handles_core_hard_mode_behaviors() -> None:
    oracle = _load_module("ruleledger_v2_oracle_test_core", ORACLE_PATH)
    events = [
        {
            "id": "evt_open",
            "account_id": "acct_core",
            "type": "account_opened",
            "timestamp": "2026-01-01T00:00:00Z",
            "plan": "starter",
        },
        {
            "id": "evt_late",
            "account_id": "acct_core",
            "type": "plan_changed",
            "timestamp": "2026-01-10T00:00:00Z",
            "effective_at": "2026-01-02T00:00:00Z",
            "recorded_at": "2026-01-10T00:00:00Z",
            "plan": "pro",
        },
    ]

    before_recording = oracle.summarize_raw_events(events, as_of="2026-01-05T00:00:00Z")
    after_recording = oracle.summarize_raw_events(events, as_of="2026-01-11T00:00:00Z")
    proration = oracle.calculate_plan_change_proration(
        "starter",
        "pro",
        "2026-02-01T00:00:00Z",
        "2026-03-01T00:00:00Z",
        "2026-02-15T00:00:00Z",
        2,
    )
    report = oracle.export_ledger_report(
        [
            {
                "accountId": "acct_report",
                "status": "active",
                "plan": "starter",
                "features": ["dashboard", "exports"],
                "usage": 1,
                "usageLimit": 1000,
                "overLimit": False,
                "totalPaidCents": 1200,
                "currency": "USD",
                "seats": 1,
                "couponCode": 'SAVE,"10"',
                "couponActive": True,
                "invoiceIds": ["inv,1"],
                "lastInvoiceId": "inv,1",
                "lastPeriodStart": "2026-02-01T00:00:00.000Z",
                "lastPeriodEnd": "2026-03-01T00:00:00.000Z",
                "mergedFromAccountIds": [],
                "closedAt": None,
                "lastEventAt": "2026-02-01T00:00:00.000Z",
            }
        ]
    )

    assert before_recording[0]["plan"] == "starter"
    assert after_recording[0]["plan"] == "pro"
    assert proration["oldCreditCents"] < 0
    assert proration["newChargeCents"] > 0
    assert '"SAVE,""10"""' in report

    corrected_after_void = oracle.summarize_raw_events(
        [
            {
                "id": "evt_cv_open",
                "account_id": "acct_cv",
                "type": "account_opened",
                "timestamp": "2026-01-01T00:00:00Z",
                "plan": "starter",
            },
            {
                "id": "evt_cv_usage",
                "account_id": "acct_cv",
                "type": "usage_recorded",
                "timestamp": "2026-01-02T00:00:00Z",
                "usage": 5,
            },
            {
                "id": "evt_cv_void",
                "account_id": "acct_cv",
                "type": "event_voided",
                "timestamp": "2026-01-03T00:00:00Z",
                "voided_event_id": "evt_cv_usage",
            },
            {
                "id": "evt_cv_correct",
                "account_id": "acct_cv",
                "type": "event_corrected",
                "timestamp": "2026-01-04T00:00:00Z",
                "effective_at": "2026-01-02T00:00:00Z",
                "recorded_at": "2026-01-04T00:00:00Z",
                "correction_of": "evt_cv_usage",
                "usage": 8,
            },
        ],
        as_of="2026-01-05T00:00:00Z",
    )
    post_merge_source_event = oracle.summarize_raw_events(
        [
            {
                "id": "evt_src_open",
                "account_id": "acct_src",
                "type": "account_opened",
                "timestamp": "2026-01-01T00:00:00Z",
                "plan": "starter",
            },
            {
                "id": "evt_dst_open",
                "account_id": "acct_dst",
                "type": "account_opened",
                "timestamp": "2026-01-01T00:00:00Z",
                "plan": "pro",
            },
            {
                "id": "evt_merge",
                "account_id": "acct_dst",
                "type": "account_merged",
                "timestamp": "2026-01-02T00:00:00Z",
                "merge_from_account_id": "acct_src",
            },
            {
                "id": "evt_source_usage_after_merge",
                "account_id": "acct_src",
                "type": "usage_recorded",
                "timestamp": "2026-01-03T00:00:00Z",
                "usage": 7,
            },
        ],
        as_of="2026-01-04T00:00:00Z",
    )

    assert corrected_after_void[0]["usage"] == 8
    assert len(post_merge_source_event) == 1
    assert post_merge_source_event[0]["accountId"] == "acct_dst"
    assert post_merge_source_event[0]["usage"] == 7
    assert post_merge_source_event[0]["mergedFromAccountIds"] == ["acct_src"]


def test_generate_v2_cases_is_byte_deterministic(tmp_path: Path) -> None:
    generator = _load_module("generate_v2_cases_test_determinism", GENERATOR_PATH)
    cases_dir = tmp_path / "cases_v2"

    cases_dir.mkdir()
    (cases_dir / "stale.json").write_text("stale\n", encoding="utf-8")
    generator.main(cases_dir)
    first_snapshot = _snapshot(cases_dir)
    generator.main(cases_dir)
    second_snapshot = _snapshot(cases_dir)

    assert "stale.json" not in first_snapshot
    assert first_snapshot == second_snapshot


def test_checked_in_cases_v2_match_generator_output(tmp_path: Path) -> None:
    generator = _load_module("generate_v2_cases_test_checked_in", GENERATOR_PATH)
    cases_dir = tmp_path / "cases_v2"

    generator.main(cases_dir)

    assert _snapshot(cases_dir) == _snapshot(CASES_V2_DIR)


def test_generate_v2_cases_cli_supports_safe_output_directory(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cli_cases_v2"

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
    assert _snapshot(cases_dir) == _snapshot(CASES_V2_DIR)


def test_generate_v2_cases_cli_rejects_unscoped_output_directory(tmp_path: Path) -> None:
    unsafe_dir = tmp_path / "unsafe_output"
    unsafe_dir.mkdir()
    sentinel = unsafe_dir / "sentinel.json"
    sentinel.write_text('{"keep": true}\n', encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(GENERATOR_PATH), "--cases-dir", str(unsafe_dir)],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=60,
    )

    assert completed.returncode != 0
    assert "output directory name must include 'cases'" in completed.stderr
    assert sentinel.exists()


def test_cases_v2_manifest_matches_generated_files() -> None:
    manifest = _read_json(CASES_V2_DIR / "manifest.json")

    assert manifest["schema_version"] == 2
    assert manifest["benchmark"] == "ruleledger_v2"
    assert manifest["seed"] == 20260520
    assert set(manifest["category_weights"]) == REQUIRED_CATEGORIES

    for filename, metadata in manifest["files"].items():
        path = CASES_V2_DIR / filename
        payload = _read_json(path)
        points = sum(float(case["points"]) for case in payload["cases"])

        assert path.exists(), filename
        assert metadata["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert metadata["case_count"] == len(payload["cases"])
        assert metadata["points"] == points


def test_generated_v2_cases_cover_required_categories_and_documented_rules() -> None:
    semantics = SEMANTICS_PATH.read_text(encoding="utf-8")
    manifest = _read_json(CASES_V2_DIR / "manifest.json")
    categories: set[str] = set()
    operations: set[str] = set()
    performance_event_counts: list[int] = []

    for case in _iter_cases(manifest):
        categories.add(case["category"])
        operations.add(case["operation"])
        assert case["points"] > 0
        assert case["rule_ids"], case["id"]
        assert case["expected"] is not None
        for rule_id in case["rule_ids"]:
            assert f"### {rule_id}:" in semantics
        if case["category"] == "performance":
            performance_event_counts.append(len(case["input"]["raw_events"]))

    assert categories == REQUIRED_CATEGORIES
    assert {
        "parse_line",
        "normalize_event",
        "v2_reduce_and_summarize",
        "v2_calculate_proration",
        "v2_export_report",
        "v2_metamorphic",
        "v2_performance_digest",
        "v2_parity",
    }.issubset(operations)
    assert performance_event_counts
    assert min(performance_event_counts) >= 10_000


def test_v2_oracle_reproduces_every_generated_expected_output() -> None:
    oracle = _load_module("ruleledger_v2_oracle_test_generated", ORACLE_PATH)
    manifest = _read_json(CASES_V2_DIR / "manifest.json")

    for case in _iter_cases(manifest):
        actual = oracle.evaluate_case(case)
        if case.get("match") == "normalize_error":
            assert actual["ok"] is False, case["id"]
            assert actual["error"] == case["expected"]["error"], case["id"]
            assert sorted(actual["issues"]) == sorted(case["expected"]["issues"]), case["id"]
        else:
            assert actual == case["expected"], case["id"]


def test_ruleledger_v2_config_uses_generated_cases_v2() -> None:
    config = _read_json(CONFIG_PATH)

    assert config["paths"]["hidden_cases"] == "hidden_tests/cases_v2"


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


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_cases(manifest: dict[str, Any]):
    for filename in sorted(manifest["files"]):
        payload = _read_json(CASES_V2_DIR / filename)
        yield from payload["cases"]
