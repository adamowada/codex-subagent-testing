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
    issue_flat = " ".join(issue.split())
    architecture = (TEMPLATE_V3 / "docs" / "ruleledger_v3_architecture.md").read_text(encoding="utf-8")

    assert "docs/ruleledger_v3_issue_brief.md" in readme
    assert "docs/ruleledger_v3_architecture.md" in readme
    assert "Preserve all v1 and v2 public APIs" in issue
    assert "near-linear account aggregation" in issue
    assert "Recent Support Escalations" in issue
    assert "not a complete truth table" in issue_flat
    assert "Month-Close Reconciliation Drift" in issue
    assert "Backfill Import Drift" in issue
    assert "same imported ledger" in issue_flat
    assert "CSV exports, parity checks, and replay fingerprints" in issue_flat
    assert "identifiers that the operator saw in the older account history" in issue_flat
    assert "visible to audit before they belonged in the business view" in issue_flat
    assert "optional invoice dates are not always real dates" in issue_flat
    assert "cent-level rounding drift" in issue_flat
    assert "byte comparison is meaningful" in issue_flat
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


def test_v3_hidden_cases_include_module_ownership_pressure() -> None:
    _, cases = load_cases(CASES_V3_DIR)
    architecture_cases = [
        case
        for case in cases
        if case["category"] == "localization" and case["operation"] == "v3_architecture_contract"
    ]

    assert len(architecture_cases) == 1
    assert architecture_cases[0]["points"] >= 3.0
    assert architecture_cases[0]["expected"] == {
        "directRuntimeFacade": False,
        "modularized": True,
        "modules": {
            "billing": True,
            "normalize": True,
            "replay": True,
            "reporting": True,
        },
    }


def test_v3_hidden_cases_include_runtime_boundary_pressure() -> None:
    _, cases = load_cases(CASES_V3_DIR)
    runtime_cases = [
        case
        for case in cases
        if case["category"] == "localization"
        and case["operation"] == "v3_runtime_compatibility_contract"
    ]

    assert len(runtime_cases) == 1
    assert runtime_cases[0]["points"] >= 2.0
    assert runtime_cases[0]["expected"] == {
        "localImplementation": False,
        "runtimeDelegates": True,
    }


def test_v3_hidden_cases_include_large_quantity_proration_pressure() -> None:
    _, cases = load_cases(CASES_V3_DIR)
    proration_cases = [
        case
        for case in cases
        if case["category"] == "pass_to_pass"
        and case["id"]
        in {
            "v3.compat.proration_large_quantity_exactness",
            "v3.compat.proration_large_quantity_downgrade_exactness",
        }
    ]

    assert len(proration_cases) == 2
    cases_by_id = {case["id"]: case for case in proration_cases}

    upgrade = cases_by_id["v3.compat.proration_large_quantity_exactness"]
    assert upgrade["operation"] == "v2_calculate_proration"
    assert upgrade["input"]["quantity"] > 100_000_000_000
    assert upgrade["expected"]["newChargeCents"] == 474_193_365_475_248

    downgrade = cases_by_id["v3.compat.proration_large_quantity_downgrade_exactness"]
    assert downgrade["operation"] == "v2_calculate_proration"
    assert downgrade["input"]["old_plan"] == "enterprise"
    assert downgrade["input"]["new_plan"] == "starter"
    assert downgrade["expected"]["oldCreditCents"] == -1_030_535_713_658_930
    assert downgrade["expected"]["newChargeCents"] == 62_142_857_105_061
    assert downgrade["expected"]["netAdjustmentCents"] == -968_392_856_553_869


def test_v3_hidden_cases_include_archival_timestamp_pressure() -> None:
    _, cases = load_cases(CASES_V3_DIR)
    cases_by_id = {case["id"]: case for case in cases}

    archival = cases_by_id["v3.compat.normalize_archival_year_0001"]
    assert archival["operation"] == "normalize_event"
    assert archival["expected"]["ok"] is True
    assert archival["expected"]["value"]["timestamp"] == "0001-01-01T00:00:00.000Z"
    assert archival["expected"]["value"]["periodEnd"] == "0001-02-01T00:00:00.000Z"


def test_v3_hidden_cases_include_support_escalation_pressure() -> None:
    _, cases = load_cases(CASES_V3_DIR)
    cases_by_id = {case["id"]: case for case in cases}

    invalid_period = cases_by_id["v3.compat.invalid_optional_period_end"]
    assert invalid_period["operation"] == "normalize_event"
    assert invalid_period["expected"]["ok"] is False
    assert "invalid_period_end" in invalid_period["expected"]["issues"]

    lexical_report = cases_by_id["v3.compat.report_lexical_ordering"]
    rows = lexical_report["expected"].splitlines()
    account_ids = [row.split(",", maxsplit=1)[0] for row in rows[1:]]
    assert account_ids == ["acct_10", "acct_2", "acct_A", "acct_Z", "acct_a"]

    merge_correction = cases_by_id["v3.parity.merge_source_correction_report"]
    assert merge_correction["operation"] == "v2_parity"
    assert merge_correction["expected"]["summaries"] == [
        {
            "accountId": "acct_support_dest",
            "status": "active",
            "plan": "starter",
            "features": ["dashboard", "exports"],
            "usage": 8,
            "usageLimit": 1000,
            "overLimit": False,
            "totalPaidCents": 4900,
            "currency": "USD",
            "seats": 3,
            "couponCode": None,
            "couponActive": False,
            "invoiceIds": ["inv_support_corrected"],
            "lastInvoiceId": "inv_support_corrected",
            "lastPeriodStart": "2026-05-01T00:00:00.000Z",
            "lastPeriodEnd": "2026-06-01T00:00:00.000Z",
            "mergedFromAccountIds": ["acct_support_source"],
            "closedAt": None,
            "lastEventAt": "2026-05-03T00:00:00.000Z",
        }
    ]
    assert "inv_support_corrected" in merge_correction["expected"]["report"]


def test_v3_hidden_cases_include_bitemporal_merge_chain_pressure() -> None:
    _, cases = load_cases(CASES_V3_DIR)
    cases_by_id = {case["id"]: case for case in cases}

    before_ops = cases_by_id["v3.reasoning.merge_chain_audit_before_source_operations"]
    assert before_ops["operation"] == "v2_reduce_and_summarize"
    assert before_ops["input"]["business_as_of"] == "2026-06-13T00:00:00Z"
    assert before_ops["input"]["audit_as_of"] == "2026-06-07T23:59:59Z"
    assert before_ops["expected"][0]["accountId"] == "acct_bt_final"
    assert before_ops["expected"][0]["usage"] == 13
    assert before_ops["expected"][0]["totalPaidCents"] == 1200
    assert before_ops["expected"][0]["invoiceIds"] == ["inv_bt_original"]
    assert before_ops["expected"][0]["mergedFromAccountIds"] == [
        "acct_bt_source",
        "acct_bt_mid",
    ]

    after_corrections = cases_by_id["v3.reasoning.merge_chain_after_source_corrections"]
    assert after_corrections["operation"] == "v2_reduce_and_summarize"
    assert after_corrections["input"]["audit_as_of"] == "2026-06-09T12:00:00Z"
    assert after_corrections["expected"][0]["usage"] == 19
    assert after_corrections["expected"][0]["totalPaidCents"] == 4900
    assert after_corrections["expected"][0]["invoiceIds"] == ["inv_bt_corrected"]

    after_void = cases_by_id["v3.evolution.merge_chain_void_retracts_source_correction"]
    assert after_void["operation"] == "v2_parity"
    assert after_void["input"]["audit_as_of"] == "2026-06-13T00:00:00Z"
    assert after_void["expected"]["summaries"][0]["usage"] == 7
    assert after_void["expected"]["summaries"][0]["seats"] == 5
    assert after_void["expected"]["summaries"][0]["totalPaidCents"] == 4900
    assert "acct_bt_source|acct_bt_mid" in after_void["expected"]["report"]


def test_v3_hidden_cases_include_corrected_merge_record_pressure() -> None:
    _, cases = load_cases(CASES_V3_DIR)
    cases_by_id = {case["id"]: case for case in cases}

    after_correction = cases_by_id["v3.reasoning.corrected_merge_record_retargets_lineage"]
    assert after_correction["operation"] == "v2_reduce_and_summarize"
    assert after_correction["input"]["audit_as_of"] == "2026-07-05T12:00:00Z"
    assert after_correction["expected"][0]["accountId"] == "acct_cm_final"
    assert after_correction["expected"][0]["usage"] == 19
    assert after_correction["expected"][0]["seats"] == 5
    assert after_correction["expected"][0]["totalPaidCents"] == 19900
    assert after_correction["expected"][0]["invoiceIds"] == ["inv_cm_true"]
    assert after_correction["expected"][0]["mergedFromAccountIds"] == ["acct_cm_true"]
    assert after_correction["expected"][1]["accountId"] == "acct_cm_wrong"

    after_void = cases_by_id["v3.evolution.voided_merge_correction_removes_lineage"]
    assert after_void["operation"] == "v2_parity"
    assert after_void["input"]["audit_as_of"] == "2026-07-06T12:00:00Z"
    assert [row["accountId"] for row in after_void["expected"]["summaries"]] == [
        "acct_cm_final",
        "acct_cm_true",
        "acct_cm_wrong",
    ]
    assert after_void["expected"]["summaries"][0]["usage"] == 2
    assert after_void["expected"]["summaries"][0]["seats"] == 2
    assert after_void["expected"]["summaries"][0]["totalPaidCents"] == 0
    assert after_void["expected"]["summaries"][0]["mergedFromAccountIds"] == []
    assert "acct_cm_final,active,starter,0,USD,2,2" in after_void["expected"]["report"]
    assert "acct_cm_true,active,enterprise,19900,USD,3,17" in after_void["expected"]["report"]


def test_v3_hidden_cases_include_multi_view_replay_pressure() -> None:
    _, cases = load_cases(CASES_V3_DIR)
    cases_by_id = {case["id"]: case for case in cases}

    before_void = cases_by_id["v3.reasoning.multi_view_before_void_summary"]
    assert before_void["operation"] == "v2_reduce_and_summarize"
    assert before_void["input"]["audit_as_of"] == "2026-08-10T12:00:00Z"
    assert before_void["expected"][0]["accountId"] == "acct_mv_dest"
    assert before_void["expected"][0]["usage"] == 25
    assert before_void["expected"][0]["invoiceIds"] == ["inv_mv_corrected"]
    assert before_void["expected"][0]["mergedFromAccountIds"] == [
        "acct_mv_source",
        "acct_mv_mid",
    ]

    after_void = cases_by_id["v3.evolution.multi_view_after_void_parity"]
    assert after_void["operation"] == "v2_parity"
    assert after_void["input"]["audit_as_of"] == "2026-08-12T00:00:00Z"
    assert after_void["expected"]["summaries"][0]["usage"] == 8
    assert "acct_mv_dest,active,starter,0,USD,9,8" in after_void["expected"]["report"]
    assert '"LEDGER,VIEW"' in after_void["expected"]["report"]

    metamorphic = cases_by_id["v3.metamorphic.multi_view_replay_equivalence"]
    assert metamorphic["operation"] == "v2_metamorphic"
    assert metamorphic["expected"]["baseline"][0]["usage"] == 8
    assert {
        variant["name"]: variant["equivalent"]
        for variant in metamorphic["expected"]["variants"]
    } == {
        "reverse_import_order": True,
        "unrelated_ledger_noise": True,
    }


def test_v3_hidden_cases_include_integrated_incident_pressure() -> None:
    _, cases = load_cases(CASES_V3_DIR)
    cases_by_id = {case["id"]: case for case in cases}

    before_corrections = cases_by_id["v3.reasoning.integrated_incident_lineage_before_corrections"]
    assert before_corrections["operation"] == "v2_reduce_and_summarize"
    assert before_corrections["input"]["business_as_of"] == "2026-09-06T00:00:00Z"
    assert before_corrections["input"]["audit_as_of"] == "2026-09-06T00:00:00Z"
    assert len(before_corrections["input"]["raw_events"]) == 17
    assert before_corrections["expected"][0]["accountId"] == "acct_inc_10"
    assert before_corrections["expected"][0]["usage"] == 16
    assert before_corrections["expected"][0]["totalPaidCents"] == 19900
    assert before_corrections["expected"][0]["invoiceIds"] == ["inv_inc_original"]
    assert before_corrections["expected"][0]["mergedFromAccountIds"] == [
        "acct_inc_A",
        "acct_inc_2",
    ]

    invoice_correction = cases_by_id["v3.reasoning.integrated_incident_invoice_correction_account"]
    assert invoice_correction["operation"] == "v2_reduce_and_summarize"
    assert invoice_correction["input"]["business_as_of"] == "2026-09-09T12:00:00Z"
    assert invoice_correction["input"]["audit_as_of"] == "2026-09-09T12:00:00Z"
    assert len(invoice_correction["expected"]) == 1
    assert invoice_correction["expected"][0]["usage"] == 22
    assert invoice_correction["expected"][0]["plan"] == "pro"
    assert invoice_correction["expected"][0]["seats"] == 6
    assert invoice_correction["expected"][0]["totalPaidCents"] == 24900
    assert invoice_correction["expected"][0]["invoiceIds"] == ["inv_inc_corrected"]

    month_close = cases_by_id["v3.reasoning.integrated_incident_month_close_summary"]
    assert month_close["operation"] == "v2_reduce_and_summarize"
    assert month_close["input"]["business_as_of"] == "2026-09-12T00:00:00Z"
    assert month_close["input"]["audit_as_of"] == "2026-09-09T12:00:00Z"
    assert len(month_close["input"]["raw_events"]) == 19
    assert month_close["expected"][0]["accountId"] == "acct_inc_10"
    assert month_close["expected"][0]["usage"] == 22
    assert month_close["expected"][0]["seats"] == 6
    assert month_close["expected"][0]["totalPaidCents"] == 24900
    assert month_close["expected"][0]["couponCode"] == "MONTH,CLOSE"
    assert month_close["expected"][0]["mergedFromAccountIds"] == [
        "acct_inc_A",
        "acct_inc_2",
    ]
    assert month_close["expected"][1]["lastEventAt"] == "0001-01-02T00:00:00.000Z"

    voided_usage = cases_by_id["v3.evolution.integrated_incident_voided_usage_account"]
    assert voided_usage["operation"] == "v2_reduce_and_summarize"
    assert voided_usage["input"]["audit_as_of"] == "2026-09-11T12:00:00Z"
    assert len(voided_usage["expected"]) == 1
    assert voided_usage["expected"][0]["usage"] == 9
    assert voided_usage["expected"][0]["seats"] == 6
    assert voided_usage["expected"][0]["lastEventAt"] == "2026-09-11T00:00:00.000Z"

    final_account = cases_by_id["v3.evolution.integrated_incident_final_account"]
    assert final_account["operation"] == "v2_reduce_and_summarize"
    assert final_account["input"]["audit_as_of"] == "2026-09-13T00:00:00Z"
    assert len(final_account["expected"]) == 1
    assert final_account["expected"][0]["usage"] == 9
    assert final_account["expected"][0]["seats"] == 8
    assert final_account["expected"][0]["lastEventAt"] == "2026-09-12T00:00:00.000Z"

    final_parity = cases_by_id["v3.evolution.integrated_incident_final_parity"]
    assert final_parity["operation"] == "v2_parity"
    assert final_parity["input"]["audit_as_of"] == "2026-09-13T00:00:00Z"
    assert final_parity["expected"]["summaries"][0]["usage"] == 9
    assert final_parity["expected"]["summaries"][0]["seats"] == 8
    assert final_parity["expected"]["summaries"][0]["totalPaidCents"] == 24900
    assert '"MONTH,CLOSE"' in final_parity["expected"]["report"]
    assert "acct_inc_archive,active,starter" in final_parity["expected"]["report"]

    metamorphic = cases_by_id["v3.metamorphic.integrated_incident_replay_equivalence"]
    assert metamorphic["operation"] == "v2_metamorphic"
    assert metamorphic["expected"]["baseline"][0]["usage"] == 9
    assert {
        variant["name"]: variant["equivalent"]
        for variant in metamorphic["expected"]["variants"]
    } == {
        "reverse_import_order": True,
        "unrelated_backfill_noise": True,
    }

    digest = cases_by_id["v3.performance.integrated_incident_digest_10k"]
    assert digest["operation"] == "v2_performance_digest"
    assert len(digest["input"]["raw_events"]) == 10019
    assert digest["expected"]["summaryCount"] == 1002
    assert digest["expected"]["totalPaidCents"] == 24900
    assert digest["expected"]["totalUsage"] == 48024

    parity = cases_by_id["v3.parity.integrated_incident_summary_report"]
    assert parity["operation"] == "v2_parity"
    assert parity["expected"]["summaries"] == final_parity["expected"]["summaries"]
    assert parity["expected"]["report"] == final_parity["expected"]["report"]


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
