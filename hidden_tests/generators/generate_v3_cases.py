from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from ruleledger_v2_oracle import evaluate_case
except ModuleNotFoundError:
    from hidden_tests.generators.ruleledger_v2_oracle import evaluate_case


ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "hidden_tests" / "cases_v3"
SEED = 20260529
GENERATED_AT = "2026-05-29T00:00:00.000Z"

CATEGORY_WEIGHTS = {
    "fail_to_pass": 0.20,
    "pass_to_pass": 0.10,
    "localization": 0.25,
    "evolution": 0.20,
    "metamorphic": 0.10,
    "performance": 0.10,
    "parity": 0.05,
}


def main(cases_dir: Path = CASES_DIR) -> None:
    cases_dir = _validate_cases_dir(cases_dir)
    cases_dir.mkdir(parents=True, exist_ok=True)
    for stale_file in cases_dir.glob("*.json"):
        stale_file.unlink()

    files = {
        "compatibility.json": compatibility_cases(),
        "localization.json": localization_cases(),
        "reasoning_ladder.json": reasoning_ladder_cases(),
        "evolution.json": evolution_cases(),
        "metamorphic.json": metamorphic_cases(),
        "performance.json": performance_cases(),
        "parity.json": parity_cases(),
    }

    manifest_files = {}
    for filename, cases in files.items():
        payload = {
            "schema_version": 3,
            "benchmark": "ruleledger_v3",
            "seed": SEED,
            "generated_at": GENERATED_AT,
            "cases": cases,
        }
        path = cases_dir / filename
        write_json(path, payload)
        manifest_files[filename] = {
            "case_count": len(cases),
            "points": round(sum(float(case["points"]) for case in cases), 6),
            "sha256": sha256(path),
        }

    manifest = {
        "schema_version": 3,
        "benchmark": "ruleledger_v3",
        "seed": SEED,
        "generated_at": GENERATED_AT,
        "category_weights": CATEGORY_WEIGHTS,
        "files": manifest_files,
    }
    write_json(cases_dir / "manifest.json", manifest)


def compatibility_cases() -> list[dict[str, Any]]:
    raw_event = {
        "id": "evt_v3_compat_payment",
        "account_id": "acct_v3_compat",
        "type": "payment_succeeded",
        "timestamp": "2026-04-01T08:15:30-04:00",
        "effective_at": "2026-04-01T00:00:00Z",
        "recorded_at": "2026-04-01T12:15:31Z",
        "sequence": 4,
        "amount": "49.00",
        "currency": "usd",
        "invoice_id": "inv_v3_compat",
        "period_start": "2026-04-01T00:00:00Z",
        "period_end": "2026-05-01T00:00:00Z",
    }
    invalid_period_event = {
        "id": "evt_v3_compat_bad_period",
        "account_id": "acct_v3_bad_period",
        "type": "invoice_issued",
        "timestamp": "2026-02-15T00:00:00Z",
        "amount_cents": 19900,
        "currency": "usd",
        "invoice_id": "inv_bad_period",
        "period_start": "2026-02-01T00:00:00Z",
        "period_end": "2026-02-30T00:00:00Z",
    }
    archival_event = {
        "id": "evt_v3_archive_year_0001",
        "account_id": "acct_v3_archive",
        "type": "invoice_issued",
        "timestamp": "0001-01-01T00:00:00Z",
        "amount_cents": 100,
        "currency": "usd",
        "invoice_id": "inv_archive_0001",
        "period_start": "0001-01-01T00:00:00Z",
        "period_end": "0001-02-01T00:00:00Z",
    }
    summary = {
        "accountId": "acct_v3_report",
        "status": "active",
        "plan": "pro",
        "features": ["dashboard", "exports", "priority_support", "rules"],
        "usage": 12,
        "usageLimit": 10000,
        "overLimit": False,
        "totalPaidCents": 4900,
        "currency": "USD",
        "seats": 3,
        "couponCode": "SPRING,50",
        "couponActive": True,
        "invoiceIds": ["inv_a", "inv_b"],
        "lastInvoiceId": "inv_b",
        "lastPeriodStart": "2026-04-01T00:00:00.000Z",
        "lastPeriodEnd": "2026-05-01T00:00:00.000Z",
        "mergedFromAccountIds": [],
        "closedAt": None,
        "lastEventAt": "2026-04-01T00:00:00.000Z",
    }
    lexical_summaries = [
        {
            **summary,
            "accountId": account_id,
            "lastInvoiceId": f"inv_{account_id[-1]}",
            "invoiceIds": [f"inv_{account_id[-1]}"],
        }
        for account_id in ["acct_a", "acct_Z", "acct_2", "acct_10", "acct_A"]
    ]

    return [
        evaluated_case(
            "v3.compat.normalize_payment",
            "pass_to_pass",
            ["BT-001", "BL-001", "BL-002"],
            "normalize_event",
            {"raw_event": raw_event},
            points=1.0,
        ),
        evaluated_case(
            "v3.compat.invalid_optional_period_end",
            "pass_to_pass",
            ["BT-001", "BL-002", "PY-001"],
            "normalize_event",
            {"raw_event": invalid_period_event},
            points=1.5,
        ),
        evaluated_case(
            "v3.compat.normalize_archival_year_0001",
            "pass_to_pass",
            ["BT-001", "BL-002", "PY-001"],
            "normalize_event",
            {"raw_event": archival_event},
            points=1.5,
        ),
        evaluated_case(
            "v3.compat.report_csv_escaping",
            "pass_to_pass",
            ["RP-001", "RP-006", "PY-001"],
            "v2_export_report",
            {"summaries": [summary]},
            points=1.0,
        ),
        evaluated_case(
            "v3.compat.report_lexical_ordering",
            "pass_to_pass",
            ["RP-001", "RP-006", "PY-001"],
            "v2_export_report",
            {"summaries": lexical_summaries},
            points=1.5,
        ),
        evaluated_case(
            "v3.compat.proration_large_quantity_exactness",
            "pass_to_pass",
            ["BL-004", "BL-005", "BL-007", "PY-001"],
            "v2_calculate_proration",
            {
                "old_plan": "starter",
                "new_plan": "pro",
                "period_start": "2026-01-01T00:00:00Z",
                "period_end": "2026-02-01T00:00:00Z",
                "change_effective_at": "2026-01-02T00:00:01Z",
                "quantity": 100_000_000_007,
            },
            points=2.0,
        ),
        evaluated_case(
            "v3.compat.proration_large_quantity_downgrade_exactness",
            "pass_to_pass",
            ["BL-004", "BL-005", "BL-007", "PY-001"],
            "v2_calculate_proration",
            {
                "old_plan": "enterprise",
                "new_plan": "starter",
                "period_start": "2026-02-01T00:00:00Z",
                "period_end": "2026-03-01T00:00:00Z",
                "change_effective_at": "2026-02-14T12:00:00.001Z",
                "quantity": 100_000_000_019,
            },
            points=2.0,
        ),
    ]


def localization_cases() -> list[dict[str, Any]]:
    return [
        evaluated_case(
            "v3.localization.module_ownership",
            "localization",
            ["LC-010", "PY-001", "TS-001"],
            "v3_architecture_contract",
            {},
            points=3.0,
        ),
        evaluated_case(
            "v3.localization.runtime_compatibility_boundary",
            "localization",
            ["LC-010", "PY-001", "TS-001"],
            "v3_runtime_compatibility_contract",
            {},
            points=2.0,
        ),
    ]


def bitemporal_merge_chain_events() -> list[dict[str, Any]]:
    return [
        {
            "id": "evt_bt_final_open",
            "account_id": "acct_bt_final",
            "type": "account_opened",
            "timestamp": "2026-06-01T00:00:00Z",
            "plan": "starter",
            "quantity": 1,
        },
        {
            "id": "evt_bt_mid_open",
            "account_id": "acct_bt_mid",
            "type": "account_opened",
            "timestamp": "2026-06-01T00:00:01Z",
            "plan": "pro",
            "quantity": 2,
        },
        {
            "id": "evt_bt_source_open",
            "account_id": "acct_bt_source",
            "type": "account_opened",
            "timestamp": "2026-06-01T00:00:02Z",
            "plan": "free",
        },
        {
            "id": "evt_bt_final_currency",
            "account_id": "acct_bt_final",
            "type": "payment_succeeded",
            "timestamp": "2026-06-01T00:30:00Z",
            "amount_cents": 0,
            "currency": "usd",
        },
        {
            "id": "evt_bt_source_usage",
            "account_id": "acct_bt_source",
            "type": "usage_recorded",
            "timestamp": "2026-06-02T00:00:00Z",
            "usage": 9,
        },
        {
            "id": "evt_bt_source_payment",
            "account_id": "acct_bt_source",
            "type": "payment_succeeded",
            "timestamp": "2026-06-02T01:00:00Z",
            "amount_cents": 1200,
            "currency": "usd",
            "invoice_id": "inv_bt_original",
            "period_start": "2026-06-01T00:00:00Z",
            "period_end": "2026-07-01T00:00:00Z",
        },
        {
            "id": "evt_bt_merge_source_mid",
            "account_id": "acct_bt_mid",
            "type": "account_merged",
            "timestamp": "2026-06-03T00:00:00Z",
            "merge_from_account_id": "acct_bt_source",
        },
        {
            "id": "evt_bt_mid_usage",
            "account_id": "acct_bt_mid",
            "type": "usage_recorded",
            "timestamp": "2026-06-04T00:00:00Z",
            "usage": 4,
        },
        {
            "id": "evt_bt_merge_mid_final",
            "account_id": "acct_bt_final",
            "type": "account_merged",
            "timestamp": "2026-06-05T00:00:00Z",
            "merge_from_account_id": "acct_bt_mid",
        },
        {
            "id": "evt_bt_correct_source_usage",
            "account_id": "acct_bt_source",
            "type": "event_corrected",
            "timestamp": "2026-06-08T00:00:00Z",
            "recorded_at": "2026-06-08T00:00:00Z",
            "effective_at": "2026-06-02T00:00:00Z",
            "correction_of": "evt_bt_source_usage",
            "usage": 15,
        },
        {
            "id": "evt_bt_correct_source_payment",
            "account_id": "acct_bt_source",
            "type": "event_corrected",
            "timestamp": "2026-06-09T00:00:00Z",
            "recorded_at": "2026-06-09T00:00:00Z",
            "effective_at": "2026-06-02T01:00:00Z",
            "correction_of": "evt_bt_source_payment",
            "amount_cents": 4900,
            "currency": "usd",
            "invoice_id": "inv_bt_corrected",
            "period_start": "2026-06-01T00:00:00Z",
            "period_end": "2026-07-01T00:00:00Z",
        },
        {
            "id": "evt_bt_void_usage_correction",
            "account_id": "acct_bt_source",
            "type": "event_voided",
            "timestamp": "2026-06-10T00:00:00Z",
            "recorded_at": "2026-06-10T00:00:00Z",
            "effective_at": "2026-06-02T00:00:00Z",
            "voided_event_id": "evt_bt_correct_source_usage",
        },
        {
            "id": "evt_bt_source_late_usage",
            "account_id": "acct_bt_source",
            "type": "usage_recorded",
            "timestamp": "2026-06-11T00:00:00Z",
            "usage": 3,
        },
        {
            "id": "evt_bt_final_seat_delta",
            "account_id": "acct_bt_final",
            "type": "seat_delta_recorded",
            "timestamp": "2026-06-12T00:00:00Z",
            "seat_delta": 1,
        },
    ]


def corrected_merge_record_events() -> list[dict[str, Any]]:
    return [
        {
            "id": "evt_cm_final_open",
            "account_id": "acct_cm_final",
            "type": "account_opened",
            "timestamp": "2026-07-01T00:00:00Z",
            "plan": "starter",
            "quantity": 1,
        },
        {
            "id": "evt_cm_wrong_open",
            "account_id": "acct_cm_wrong",
            "type": "account_opened",
            "timestamp": "2026-07-01T00:00:01Z",
            "plan": "pro",
            "quantity": 2,
        },
        {
            "id": "evt_cm_true_open",
            "account_id": "acct_cm_true",
            "type": "account_opened",
            "timestamp": "2026-07-01T00:00:02Z",
            "plan": "enterprise",
            "quantity": 3,
        },
        {
            "id": "evt_cm_final_currency",
            "account_id": "acct_cm_final",
            "type": "payment_succeeded",
            "timestamp": "2026-07-01T01:00:00Z",
            "amount_cents": 0,
            "currency": "usd",
        },
        {
            "id": "evt_cm_wrong_usage",
            "account_id": "acct_cm_wrong",
            "type": "usage_recorded",
            "timestamp": "2026-07-02T00:00:00Z",
            "usage": 5,
        },
        {
            "id": "evt_cm_wrong_payment",
            "account_id": "acct_cm_wrong",
            "type": "payment_succeeded",
            "timestamp": "2026-07-02T01:00:00Z",
            "amount_cents": 1200,
            "currency": "usd",
            "invoice_id": "inv_cm_wrong",
            "period_start": "2026-07-01T00:00:00Z",
            "period_end": "2026-08-01T00:00:00Z",
        },
        {
            "id": "evt_cm_true_usage",
            "account_id": "acct_cm_true",
            "type": "usage_recorded",
            "timestamp": "2026-07-02T02:00:00Z",
            "usage": 17,
        },
        {
            "id": "evt_cm_true_payment",
            "account_id": "acct_cm_true",
            "type": "payment_succeeded",
            "timestamp": "2026-07-02T03:00:00Z",
            "amount_cents": 19900,
            "currency": "usd",
            "invoice_id": "inv_cm_true",
            "period_start": "2026-07-01T00:00:00Z",
            "period_end": "2026-08-01T00:00:00Z",
        },
        {
            "id": "evt_cm_merge_wrong",
            "account_id": "acct_cm_final",
            "type": "account_merged",
            "timestamp": "2026-07-03T00:00:00Z",
            "merge_from_account_id": "acct_cm_wrong",
        },
        {
            "id": "evt_cm_final_usage",
            "account_id": "acct_cm_final",
            "type": "usage_recorded",
            "timestamp": "2026-07-04T00:00:00Z",
            "usage": 2,
        },
        {
            "id": "evt_cm_final_seat_delta",
            "account_id": "acct_cm_final",
            "type": "seat_delta_recorded",
            "timestamp": "2026-07-04T01:00:00Z",
            "seat_delta": 1,
        },
        {
            "id": "evt_cm_correct_merge",
            "account_id": "acct_cm_final",
            "type": "event_corrected",
            "timestamp": "2026-07-05T00:00:00Z",
            "recorded_at": "2026-07-05T00:00:00Z",
            "effective_at": "2026-07-03T00:00:00Z",
            "correction_of": "evt_cm_merge_wrong",
            "merge_from_account_id": "acct_cm_true",
        },
        {
            "id": "evt_cm_void_merge_correction",
            "account_id": "acct_cm_final",
            "type": "event_voided",
            "timestamp": "2026-07-06T00:00:00Z",
            "recorded_at": "2026-07-06T00:00:00Z",
            "effective_at": "2026-07-03T00:00:00Z",
            "voided_event_id": "evt_cm_correct_merge",
        },
    ]


def multi_view_replay_events() -> list[dict[str, Any]]:
    return [
        {
            "id": "evt_mv_dest_open",
            "account_id": "acct_mv_dest",
            "type": "account_opened",
            "timestamp": "2026-08-01T00:00:00Z",
            "plan": "starter",
            "quantity": 2,
        },
        {
            "id": "evt_mv_mid_open",
            "account_id": "acct_mv_mid",
            "type": "account_opened",
            "timestamp": "2026-08-01T00:00:01Z",
            "plan": "pro",
            "quantity": 1,
        },
        {
            "id": "evt_mv_source_open",
            "account_id": "acct_mv_source",
            "type": "account_opened",
            "timestamp": "2026-08-01T00:00:02Z",
            "plan": "enterprise",
            "quantity": 4,
        },
        {
            "id": "evt_mv_dest_currency",
            "account_id": "acct_mv_dest",
            "type": "payment_succeeded",
            "timestamp": "2026-08-01T01:00:00Z",
            "amount_cents": 0,
            "currency": "usd",
        },
        {
            "id": "evt_mv_source_usage",
            "account_id": "acct_mv_source",
            "type": "usage_recorded",
            "timestamp": "2026-08-02T00:00:00Z",
            "recorded_at": "2026-08-02T00:00:00Z",
            "sequence": 0,
            "usage": 11,
        },
        {
            "id": "evt_mv_source_usage",
            "account_id": "acct_mv_source",
            "type": "usage_recorded",
            "timestamp": "2026-08-02T00:00:00Z",
            "recorded_at": "2026-08-02T00:05:00Z",
            "sequence": 9,
            "usage": 99,
        },
        {
            "id": "evt_mv_source_invoice",
            "account_id": "acct_mv_source",
            "type": "invoice_issued",
            "timestamp": "2026-08-02T02:00:00Z",
            "amount_cents": 19900,
            "currency": "usd",
            "invoice_id": "inv_mv_original",
            "period_start": "2026-08-01T00:00:00Z",
            "period_end": "2026-09-01T00:00:00Z",
        },
        {
            "id": "evt_mv_merge_source_mid",
            "account_id": "acct_mv_mid",
            "type": "account_merged",
            "timestamp": "2026-08-03T00:00:00Z",
            "merge_from_account_id": "acct_mv_source",
        },
        {
            "id": "evt_mv_mid_usage",
            "account_id": "acct_mv_mid",
            "type": "usage_recorded",
            "timestamp": "2026-08-04T00:00:00Z",
            "usage": 5,
        },
        {
            "id": "evt_mv_merge_mid_dest",
            "account_id": "acct_mv_dest",
            "type": "account_merged",
            "timestamp": "2026-08-05T00:00:00Z",
            "merge_from_account_id": "acct_mv_mid",
        },
        {
            "id": "evt_mv_dest_coupon",
            "account_id": "acct_mv_dest",
            "type": "coupon_applied",
            "timestamp": "2026-08-06T00:00:00Z",
            "coupon": "ledger,view",
            "expires_at": "2026-09-01T00:00:00Z",
        },
        {
            "id": "evt_mv_correct_usage",
            "account_id": "acct_mv_source",
            "type": "event_corrected",
            "timestamp": "2026-08-07T00:00:00Z",
            "recorded_at": "2026-08-07T00:00:00Z",
            "effective_at": "2026-08-02T00:00:00Z",
            "correction_of": "evt_mv_source_usage",
            "usage": 17,
        },
        {
            "id": "evt_mv_correct_invoice",
            "account_id": "acct_mv_source",
            "type": "event_corrected",
            "timestamp": "2026-08-08T00:00:00Z",
            "recorded_at": "2026-08-08T00:00:00Z",
            "effective_at": "2026-08-02T02:00:00Z",
            "correction_of": "evt_mv_source_invoice",
            "amount_cents": 24900,
            "currency": "usd",
            "invoice_id": "inv_mv_corrected",
            "period_start": "2026-08-01T00:00:00Z",
            "period_end": "2026-09-01T00:00:00Z",
        },
        {
            "id": "evt_mv_source_late_usage",
            "account_id": "acct_mv_source",
            "type": "usage_recorded",
            "timestamp": "2026-08-09T00:00:00Z",
            "usage": 3,
        },
        {
            "id": "evt_mv_dest_seat_delta",
            "account_id": "acct_mv_dest",
            "type": "seat_delta_recorded",
            "timestamp": "2026-08-10T00:00:00Z",
            "seat_delta": 2,
        },
        {
            "id": "evt_mv_void_usage_correction",
            "account_id": "acct_mv_source",
            "type": "event_voided",
            "timestamp": "2026-08-11T00:00:00Z",
            "recorded_at": "2026-08-11T00:00:00Z",
            "effective_at": "2026-08-02T00:00:00Z",
            "voided_event_id": "evt_mv_correct_usage",
        },
    ]


def integrated_incident_events(*, noise_accounts: int = 0) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        {
            "id": "evt_inc_dest_open",
            "account_id": "acct_inc_10",
            "type": "account_opened",
            "timestamp": "2026-09-01T00:00:00Z",
            "plan": "starter",
            "quantity": 1,
        },
        {
            "id": "evt_inc_mid_open",
            "account_id": "acct_inc_2",
            "type": "account_opened",
            "timestamp": "2026-09-01T00:00:01Z",
            "plan": "pro",
            "quantity": 2,
        },
        {
            "id": "evt_inc_source_open",
            "account_id": "acct_inc_A",
            "type": "account_opened",
            "timestamp": "2026-09-01T00:00:02Z",
            "plan": "enterprise",
            "quantity": 3,
        },
        {
            "id": "evt_inc_archive_open",
            "account_id": "acct_inc_archive",
            "type": "account_opened",
            "timestamp": "0001-01-01T00:00:00Z",
            "plan": "starter",
            "quantity": 1,
        },
        {
            "id": "evt_inc_archive_invoice",
            "account_id": "acct_inc_archive",
            "type": "invoice_issued",
            "timestamp": "0001-01-02T00:00:00Z",
            "amount_cents": 1200,
            "currency": "usd",
            "invoice_id": "inv_inc_archive",
            "period_start": "0001-01-01T00:00:00Z",
            "period_end": "0001-02-01T00:00:00Z",
        },
        {
            "id": "evt_inc_dest_currency",
            "account_id": "acct_inc_10",
            "type": "payment_succeeded",
            "timestamp": "2026-09-01T01:00:00Z",
            "amount_cents": 0,
            "currency": "usd",
        },
        {
            "id": "evt_inc_source_usage",
            "account_id": "acct_inc_A",
            "type": "usage_recorded",
            "timestamp": "2026-09-02T00:00:00Z",
            "recorded_at": "2026-09-02T00:00:00Z",
            "sequence": 0,
            "usage": 12,
        },
        {
            "id": "evt_inc_source_usage",
            "account_id": "acct_inc_A",
            "type": "usage_recorded",
            "timestamp": "2026-09-02T00:00:00Z",
            "recorded_at": "2026-09-02T00:05:00Z",
            "sequence": 9,
            "usage": 99,
        },
        {
            "id": "evt_inc_source_invoice",
            "account_id": "acct_inc_A",
            "type": "payment_succeeded",
            "timestamp": "2026-09-02T02:00:00Z",
            "amount_cents": 19900,
            "currency": "usd",
            "invoice_id": "inv_inc_original",
            "period_start": "2026-09-01T00:00:00Z",
            "period_end": "2026-10-01T00:00:00Z",
        },
        {
            "id": "evt_inc_source_coupon",
            "account_id": "acct_inc_A",
            "type": "coupon_applied",
            "timestamp": "2026-09-02T03:00:00Z",
            "coupon": "month,close",
            "expires_at": "2026-10-01T00:00:00Z",
        },
        {
            "id": "evt_inc_merge_source_mid",
            "account_id": "acct_inc_2",
            "type": "account_merged",
            "timestamp": "2026-09-03T00:00:00Z",
            "merge_from_account_id": "acct_inc_A",
        },
        {
            "id": "evt_inc_mid_usage",
            "account_id": "acct_inc_2",
            "type": "usage_recorded",
            "timestamp": "2026-09-04T00:00:00Z",
            "usage": 4,
        },
        {
            "id": "evt_inc_merge_mid_dest",
            "account_id": "acct_inc_10",
            "type": "account_merged",
            "timestamp": "2026-09-05T00:00:00Z",
            "merge_from_account_id": "acct_inc_2",
        },
        {
            "id": "evt_inc_correct_usage",
            "account_id": "acct_inc_A",
            "type": "event_corrected",
            "timestamp": "2026-09-07T00:00:00Z",
            "recorded_at": "2026-09-07T00:00:00Z",
            "effective_at": "2026-09-02T00:00:00Z",
            "correction_of": "evt_inc_source_usage",
            "usage": 18,
        },
        {
            "id": "evt_inc_correct_invoice",
            "account_id": "acct_inc_A",
            "type": "event_corrected",
            "timestamp": "2026-09-08T00:00:00Z",
            "recorded_at": "2026-09-08T00:00:00Z",
            "effective_at": "2026-09-02T02:00:00Z",
            "correction_of": "evt_inc_source_invoice",
            "amount_cents": 24900,
            "currency": "usd",
            "invoice_id": "inv_inc_corrected",
            "period_start": "2026-09-01T00:00:00Z",
            "period_end": "2026-10-01T00:00:00Z",
        },
        {
            "id": "evt_inc_late_plan",
            "account_id": "acct_inc_10",
            "type": "plan_changed",
            "timestamp": "2026-09-09T00:00:00Z",
            "recorded_at": "2026-09-09T00:00:00Z",
            "effective_at": "2026-09-04T00:00:00Z",
            "plan": "pro",
        },
        {
            "id": "evt_inc_void_usage_correction",
            "account_id": "acct_inc_A",
            "type": "event_voided",
            "timestamp": "2026-09-10T00:00:00Z",
            "recorded_at": "2026-09-10T00:00:00Z",
            "effective_at": "2026-09-02T00:00:00Z",
            "voided_event_id": "evt_inc_correct_usage",
        },
        {
            "id": "evt_inc_source_late_usage",
            "account_id": "acct_inc_A",
            "type": "usage_recorded",
            "timestamp": "2026-09-11T00:00:00Z",
            "usage": 5,
        },
        {
            "id": "evt_inc_dest_seat_delta",
            "account_id": "acct_inc_10",
            "type": "seat_delta_recorded",
            "timestamp": "2026-09-12T00:00:00Z",
            "seat_delta": 2,
        },
    ]

    for account_index in range(noise_accounts):
        account_id = f"acct_inc_noise_{account_index:04d}"
        events.append(
            {
                "id": f"evt_inc_noise_open_{account_index:04d}",
                "account_id": account_id,
                "type": "account_opened",
                "timestamp": "2026-09-01T00:00:00Z",
                "plan": "starter" if account_index % 2 else "free",
                "quantity": 1 + (account_index % 3),
            }
        )
        for usage_index in range(8):
            events.append(
                {
                    "id": f"evt_inc_noise_usage_{account_index:04d}_{usage_index:02d}",
                    "account_id": account_id,
                    "type": "usage_recorded",
                    "timestamp": f"2026-09-{2 + usage_index:02d}T00:00:00Z",
                    "usage": (account_index + usage_index) % 13,
                }
            )
        events.append(
            {
                "id": f"evt_inc_noise_invoice_{account_index:04d}",
                "account_id": account_id,
                "type": "invoice_issued",
                "timestamp": "2026-09-10T00:00:00Z",
                "amount_cents": 1200 if account_index % 2 else 0,
                "currency": "usd",
                "invoice_id": f"inv_inc_noise_{account_index:04d}",
                "period_start": "2026-09-01T00:00:00Z",
                "period_end": "2026-10-01T00:00:00Z",
            }
        )

    return events


def reasoning_ladder_cases() -> list[dict[str, Any]]:
    raw_events = [
        {
            "id": "evt_open_primary",
            "account_id": "acct_v3_main",
            "type": "account_opened",
            "timestamp": "2026-01-01T00:00:00Z",
            "plan": "starter",
            "quantity": 2,
        },
        {
            "id": "evt_open_source",
            "account_id": "acct_v3_source",
            "type": "account_opened",
            "timestamp": "2026-01-01T00:00:00Z",
            "plan": "free",
        },
        {
            "id": "evt_source_usage",
            "account_id": "acct_v3_source",
            "type": "usage_recorded",
            "timestamp": "2026-01-02T00:00:00Z",
            "usage": 10,
        },
        {
            "id": "evt_merge_source",
            "account_id": "acct_v3_main",
            "type": "account_merged",
            "timestamp": "2026-01-03T00:00:00Z",
            "merge_from_account_id": "acct_v3_source",
        },
        {
            "id": "evt_late_plan",
            "account_id": "acct_v3_main",
            "type": "plan_changed",
            "timestamp": "2026-01-08T00:00:00Z",
            "effective_at": "2026-01-04T00:00:00Z",
            "recorded_at": "2026-01-08T00:00:00Z",
            "plan": "pro",
        },
        {
            "id": "evt_correct_usage",
            "account_id": "acct_v3_main",
            "type": "event_corrected",
            "timestamp": "2026-01-09T00:00:00Z",
            "effective_at": "2026-01-02T00:00:00Z",
            "recorded_at": "2026-01-09T00:00:00Z",
            "correction_of": "evt_source_usage",
            "usage": 14,
        },
    ]

    return [
        evaluated_case(
            "v3.reasoning.audit_before_late_plan",
            "fail_to_pass",
            ["BT-004", "BT-005", "MG-002"],
            "v2_reduce_and_summarize",
            {
                "raw_events": raw_events,
                "business_as_of": "2026-01-10T00:00:00Z",
                "audit_as_of": "2026-01-07T23:59:59Z",
            },
            points=2.0,
        ),
        evaluated_case(
            "v3.reasoning.audit_after_correction",
            "localization",
            ["CV-002", "CV-003", "MG-005", "PY-001"],
            "v2_reduce_and_summarize",
            {
                "raw_events": raw_events,
                "business_as_of": "2026-01-10T00:00:00Z",
                "audit_as_of": "2026-01-10T00:00:00Z",
            },
            points=2.0,
        ),
        evaluated_case(
            "v3.reasoning.merge_chain_audit_before_source_operations",
            "fail_to_pass",
            ["BT-004", "BT-005", "MG-002", "MG-005"],
            "v2_reduce_and_summarize",
            {
                "raw_events": bitemporal_merge_chain_events(),
                "business_as_of": "2026-06-13T00:00:00Z",
                "audit_as_of": "2026-06-07T23:59:59Z",
            },
            points=2.5,
        ),
        evaluated_case(
            "v3.reasoning.merge_chain_after_source_corrections",
            "localization",
            ["BT-004", "BT-005", "CV-002", "MG-005", "PY-001"],
            "v2_reduce_and_summarize",
            {
                "raw_events": bitemporal_merge_chain_events(),
                "business_as_of": "2026-06-09T12:00:00Z",
                "audit_as_of": "2026-06-09T12:00:00Z",
            },
            points=2.5,
        ),
        evaluated_case(
            "v3.reasoning.corrected_merge_record_retargets_lineage",
            "fail_to_pass",
            ["BT-004", "BT-005", "CV-002", "MG-005"],
            "v2_reduce_and_summarize",
            {
                "raw_events": corrected_merge_record_events(),
                "business_as_of": "2026-07-07T00:00:00Z",
                "audit_as_of": "2026-07-05T12:00:00Z",
            },
            points=3.0,
        ),
        evaluated_case(
            "v3.reasoning.multi_view_before_void_summary",
            "fail_to_pass",
            ["BT-004", "BT-005", "CV-001", "CV-002", "MG-005", "RP-001"],
            "v2_reduce_and_summarize",
            {
                "raw_events": multi_view_replay_events(),
                "business_as_of": "2026-08-12T00:00:00Z",
                "audit_as_of": "2026-08-10T12:00:00Z",
            },
            points=3.0,
        ),
        evaluated_case(
            "v3.reasoning.integrated_incident_month_close_summary",
            "fail_to_pass",
            ["BT-004", "BT-005", "CV-001", "CV-002", "MG-005", "RP-001"],
            "v2_reduce_and_summarize",
            {
                "raw_events": integrated_incident_events(),
                "business_as_of": "2026-09-12T00:00:00Z",
                "audit_as_of": "2026-09-09T12:00:00Z",
            },
            points=3.5,
        ),
    ]


def evolution_cases() -> list[dict[str, Any]]:
    raw_events = [
        {
            "id": "evt_evo_open",
            "account_id": "acct_v3_evo",
            "type": "account_opened",
            "timestamp": "2026-01-01T00:00:00Z",
            "plan": "starter",
        },
        {
            "id": "evt_evo_usage",
            "account_id": "acct_v3_evo",
            "type": "usage_recorded",
            "timestamp": "2026-01-02T00:00:00Z",
            "usage": 4,
        },
        {
            "id": "evt_evo_void",
            "account_id": "acct_v3_evo",
            "type": "event_voided",
            "timestamp": "2026-01-03T00:00:00Z",
            "voided_event_id": "evt_evo_usage",
        },
        {
            "id": "evt_evo_reactivate_usage",
            "account_id": "acct_v3_evo",
            "type": "event_corrected",
            "timestamp": "2026-01-04T00:00:00Z",
            "effective_at": "2026-01-02T00:00:00Z",
            "recorded_at": "2026-01-04T00:00:00Z",
            "correction_of": "evt_evo_usage",
            "usage": 9,
        },
        {
            "id": "evt_evo_close",
            "account_id": "acct_v3_evo",
            "type": "account_closed",
            "timestamp": "2026-01-05T00:00:00Z",
        },
        {
            "id": "evt_evo_reopen_attempt",
            "account_id": "acct_v3_evo",
            "type": "account_reactivated",
            "timestamp": "2026-01-06T00:00:00Z",
        },
    ]

    return [
        evaluated_case(
            "v3.evolution.before_correction",
            "evolution",
            ["CV-002", "CV-005", "LC-007"],
            "v2_reduce_and_summarize",
            {"raw_events": raw_events, "audit_as_of": "2026-01-03T12:00:00Z"},
            points=1.5,
        ),
        evaluated_case(
            "v3.evolution.after_reactivation_and_close",
            "evolution",
            ["CV-006", "LC-007"],
            "v2_reduce_and_summarize",
            {"raw_events": raw_events, "audit_as_of": "2026-01-07T00:00:00Z"},
            points=1.5,
        ),
        evaluated_case(
            "v3.evolution.audit_visible_duplicate",
            "evolution",
            ["BT-004", "BT-006", "OR-003"],
            "v2_reduce_and_summarize",
            {
                "raw_events": [
                    {
                        "id": "evt_dup_open",
                        "account_id": "acct_v3_dup",
                        "type": "account_opened",
                        "timestamp": "2026-01-01T00:00:00Z",
                        "plan": "starter",
                    },
                    {
                        "id": "evt_dup_usage",
                        "account_id": "acct_v3_dup",
                        "type": "usage_recorded",
                        "timestamp": "2026-01-02T00:00:00Z",
                        "effective_at": "2026-01-02T00:00:00Z",
                        "recorded_at": "2026-01-10T00:00:00Z",
                        "sequence": 1,
                        "usage": 100,
                    },
                    {
                        "id": "evt_dup_usage",
                        "account_id": "acct_v3_dup",
                        "type": "usage_recorded",
                        "timestamp": "2026-01-02T00:00:00Z",
                        "effective_at": "2026-01-02T00:00:00Z",
                        "recorded_at": "2026-01-02T00:00:00Z",
                        "sequence": 0,
                        "usage": 7,
                    },
                ],
                "audit_as_of": "2026-01-03T00:00:00Z",
            },
            points=2.0,
        ),
        evaluated_case(
            "v3.evolution.chain_merge_correction",
            "evolution",
            ["CV-002", "MG-002", "MG-005", "OR-001"],
            "v2_reduce_and_summarize",
            {
                "raw_events": [
                    {
                        "id": "evt_chain_dest_open",
                        "account_id": "acct_v3_chain_dest",
                        "type": "account_opened",
                        "timestamp": "2026-02-01T00:00:00Z",
                        "plan": "starter",
                        "quantity": 2,
                    },
                    {
                        "id": "evt_chain_source_open",
                        "account_id": "acct_v3_chain_source",
                        "type": "account_opened",
                        "timestamp": "2026-02-01T00:00:00Z",
                        "plan": "pro",
                        "quantity": 1,
                    },
                    {
                        "id": "evt_chain_parent_open",
                        "account_id": "acct_v3_chain_parent",
                        "type": "account_opened",
                        "timestamp": "2026-02-01T00:00:00Z",
                        "plan": "enterprise",
                        "quantity": 1,
                    },
                    {
                        "id": "evt_chain_source_usage",
                        "account_id": "acct_v3_chain_source",
                        "type": "usage_recorded",
                        "timestamp": "2026-02-02T00:00:00Z",
                        "usage": 10,
                    },
                    {
                        "id": "evt_chain_source_invoice",
                        "account_id": "acct_v3_chain_source",
                        "type": "invoice_issued",
                        "timestamp": "2026-02-02T12:00:00Z",
                        "amount_cents": 4900,
                        "currency": "usd",
                        "invoice_id": "inv_chain_source",
                        "period_start": "2026-02-01T00:00:00Z",
                        "period_end": "2026-03-01T00:00:00Z",
                    },
                    {
                        "id": "evt_chain_merge_source",
                        "account_id": "acct_v3_chain_dest",
                        "type": "account_merged",
                        "timestamp": "2026-02-03T00:00:00Z",
                        "merge_from_account_id": "acct_v3_chain_source",
                    },
                    {
                        "id": "evt_chain_merge_dest",
                        "account_id": "acct_v3_chain_parent",
                        "type": "account_merged",
                        "timestamp": "2026-02-04T00:00:00Z",
                        "merge_from_account_id": "acct_v3_chain_dest",
                    },
                    {
                        "id": "evt_chain_post_source_usage",
                        "account_id": "acct_v3_chain_source",
                        "type": "usage_recorded",
                        "timestamp": "2026-02-05T00:00:00Z",
                        "usage": 4,
                    },
                    {
                        "id": "evt_chain_correct_source_usage",
                        "account_id": "acct_v3_chain_source",
                        "type": "event_corrected",
                        "timestamp": "2026-02-06T00:00:00Z",
                        "correction_of": "evt_chain_source_usage",
                        "effective_at": "2026-02-02T00:00:00Z",
                        "recorded_at": "2026-02-06T00:00:00Z",
                        "usage": 15,
                    },
                    {
                        "id": "evt_chain_dest_seats",
                        "account_id": "acct_v3_chain_dest",
                        "type": "seat_delta_recorded",
                        "timestamp": "2026-02-07T00:00:00Z",
                        "seat_delta": 2,
                    },
                    {
                        "id": "evt_chain_post_source_invoice",
                        "account_id": "acct_v3_chain_source",
                        "type": "invoice_issued",
                        "timestamp": "2026-02-08T00:00:00Z",
                        "amount_cents": 19900,
                        "currency": "usd",
                        "invoice_id": "inv_chain_after",
                        "period_start": "2026-03-01T00:00:00Z",
                        "period_end": "2026-04-01T00:00:00Z",
                    },
                ],
                "business_as_of": "2026-02-09T00:00:00Z",
                "audit_as_of": "2026-02-09T00:00:00Z",
            },
            points=2.5,
        ),
        evaluated_case(
            "v3.evolution.merge_chain_void_retracts_source_correction",
            "evolution",
            ["BT-004", "CV-002", "MG-002", "MG-005", "RP-001"],
            "v2_parity",
            {
                "raw_events": bitemporal_merge_chain_events(),
                "business_as_of": "2026-06-13T00:00:00Z",
                "audit_as_of": "2026-06-13T00:00:00Z",
            },
            points=3.0,
        ),
        evaluated_case(
            "v3.evolution.voided_merge_correction_removes_lineage",
            "evolution",
            ["BT-004", "CV-002", "MG-005", "RP-001"],
            "v2_parity",
            {
                "raw_events": corrected_merge_record_events(),
                "business_as_of": "2026-07-07T00:00:00Z",
                "audit_as_of": "2026-07-06T12:00:00Z",
            },
            points=3.0,
        ),
        evaluated_case(
            "v3.evolution.multi_view_after_void_parity",
            "evolution",
            ["BT-004", "CV-002", "CV-006", "MG-005", "RP-001", "RP-006"],
            "v2_parity",
            {
                "raw_events": multi_view_replay_events(),
                "business_as_of": "2026-08-12T00:00:00Z",
                "audit_as_of": "2026-08-12T00:00:00Z",
            },
            points=3.0,
        ),
        evaluated_case(
            "v3.evolution.integrated_incident_final_parity",
            "evolution",
            ["BT-004", "CV-002", "CV-006", "MG-005", "RP-001", "RP-006"],
            "v2_parity",
            {
                "raw_events": integrated_incident_events(),
                "business_as_of": "2026-09-13T00:00:00Z",
                "audit_as_of": "2026-09-13T00:00:00Z",
            },
            points=4.0,
        ),
    ]


def metamorphic_cases() -> list[dict[str, Any]]:
    baseline = [
        {
            "id": "evt_meta_open",
            "account_id": "acct_v3_meta",
            "type": "account_opened",
            "timestamp": "2026-01-01T00:00:00Z",
            "plan": "pro",
        },
        {
            "id": "evt_meta_usage_a",
            "account_id": "acct_v3_meta",
            "type": "usage_recorded",
            "timestamp": "2026-01-02T00:00:00Z",
            "usage": 3,
        },
        {
            "id": "evt_meta_usage_b",
            "account_id": "acct_v3_meta",
            "type": "usage_recorded",
            "timestamp": "2026-01-03T00:00:00Z",
            "usage": 5,
        },
        {
            "id": "evt_meta_invoice",
            "account_id": "acct_v3_meta",
            "type": "invoice_issued",
            "timestamp": "2026-01-04T00:00:00Z",
            "amount_cents": 4900,
            "currency": "usd",
            "invoice_id": "inv_meta",
            "period_start": "2026-01-01T00:00:00Z",
            "period_end": "2026-02-01T00:00:00Z",
        },
    ]
    shuffled = [baseline[2], baseline[0], baseline[3], baseline[1]]
    unrelated = [
        *baseline,
        {
            "id": "evt_meta_unrelated_open",
            "account_id": "acct_v3_other",
            "type": "account_opened",
            "timestamp": "2026-01-01T00:00:00Z",
            "plan": "free",
        },
        {
            "id": "evt_meta_unrelated_usage",
            "account_id": "acct_v3_other",
            "type": "usage_recorded",
            "timestamp": "2026-01-02T00:00:00Z",
            "usage": 999,
        },
    ]

    return [
        evaluated_case(
            "v3.metamorphic.replay_equivalence",
            "metamorphic",
            ["OR-001", "OR-003", "PY-001"],
            "v2_metamorphic",
            {
                "baseline": baseline,
                "variants": [
                    {"name": "shuffled_input", "raw_events": shuffled},
                    {"name": "unrelated_account_injection", "raw_events": unrelated},
                ],
                "target_account_id": "acct_v3_meta",
                "as_of": "2026-01-15T00:00:00Z",
            },
            points=2.0,
        ),
        evaluated_case(
            "v3.metamorphic.multi_view_replay_equivalence",
            "metamorphic",
            ["OR-001", "OR-002", "CV-001", "CV-002", "MG-005", "PY-001"],
            "v2_metamorphic",
            {
                "baseline": multi_view_replay_events(),
                "variants": [
                    {
                        "name": "reverse_import_order",
                        "raw_events": list(reversed(multi_view_replay_events())),
                    },
                    {
                        "name": "unrelated_ledger_noise",
                        "raw_events": [
                            *multi_view_replay_events(),
                            {
                                "id": "evt_mv_noise_open",
                                "account_id": "acct_mv_noise",
                                "type": "account_opened",
                                "timestamp": "2026-08-01T00:00:00Z",
                                "plan": "free",
                            },
                            {
                                "id": "evt_mv_noise_usage",
                                "account_id": "acct_mv_noise",
                                "type": "usage_recorded",
                                "timestamp": "2026-08-02T00:00:00Z",
                                "usage": 500,
                            },
                        ],
                    },
                ],
                "target_account_id": "acct_mv_dest",
                "business_as_of": "2026-08-12T00:00:00Z",
                "audit_as_of": "2026-08-12T00:00:00Z",
            },
            points=2.5,
        ),
        evaluated_case(
            "v3.metamorphic.integrated_incident_replay_equivalence",
            "metamorphic",
            ["OR-001", "OR-002", "CV-001", "CV-002", "MG-005", "PY-001"],
            "v2_metamorphic",
            {
                "baseline": integrated_incident_events(),
                "variants": [
                    {
                        "name": "reverse_import_order",
                        "raw_events": list(reversed(integrated_incident_events())),
                    },
                    {
                        "name": "unrelated_backfill_noise",
                        "raw_events": integrated_incident_events(noise_accounts=3),
                    },
                ],
                "target_account_id": "acct_inc_10",
                "business_as_of": "2026-09-13T00:00:00Z",
                "audit_as_of": "2026-09-13T00:00:00Z",
            },
            points=3.0,
        ),
    ]


def performance_cases() -> list[dict[str, Any]]:
    raw_events = []
    account_count = 500
    events_per_account = 20
    for account_index in range(account_count):
        account_id = f"acct_perf_{account_index:04d}"
        raw_events.append(
            {
                "id": f"evt_perf_open_{account_index:04d}",
                "account_id": account_id,
                "type": "account_opened",
                "timestamp": "2026-02-01T00:00:00Z",
                "plan": "starter" if account_index % 2 else "pro",
            }
        )
        for usage_index in range(events_per_account - 1):
            day = 2 + (usage_index % 20)
            raw_events.append(
                {
                    "id": f"evt_perf_usage_{account_index:04d}_{usage_index:02d}",
                    "account_id": account_id,
                    "type": "usage_recorded",
                    "timestamp": f"2026-02-{day:02d}T00:00:00Z",
                    "usage": usage_index + 1,
                }
            )

    complex_events = []
    complex_account_count = 1000
    for account_index in range(complex_account_count):
        dest_id = f"acct_perf_chain_dest_{account_index:04d}"
        source_id = f"acct_perf_chain_source_{account_index:04d}"
        complex_events.extend(
            [
                {
                    "id": f"evt_perf_chain_dest_open_{account_index:04d}",
                    "account_id": dest_id,
                    "type": "account_opened",
                    "timestamp": "2026-03-01T00:00:00Z",
                    "plan": "starter",
                    "quantity": 2,
                },
                {
                    "id": f"evt_perf_chain_source_open_{account_index:04d}",
                    "account_id": source_id,
                    "type": "account_opened",
                    "timestamp": "2026-03-01T00:00:00Z",
                    "plan": "pro",
                    "quantity": 1,
                },
                {
                    "id": f"evt_perf_chain_source_usage_a_{account_index:04d}",
                    "account_id": source_id,
                    "type": "usage_recorded",
                    "timestamp": "2026-03-02T00:00:00Z",
                    "usage": account_index % 17,
                },
                {
                    "id": f"evt_perf_chain_source_usage_b_{account_index:04d}",
                    "account_id": source_id,
                    "type": "usage_recorded",
                    "timestamp": "2026-03-03T00:00:00Z",
                    "usage": 3,
                },
                {
                    "id": f"evt_perf_chain_dest_usage_{account_index:04d}",
                    "account_id": dest_id,
                    "type": "usage_recorded",
                    "timestamp": "2026-03-04T00:00:00Z",
                    "usage": 2,
                },
                {
                    "id": f"evt_perf_chain_merge_{account_index:04d}",
                    "account_id": dest_id,
                    "type": "account_merged",
                    "timestamp": "2026-03-05T00:00:00Z",
                    "merge_from_account_id": source_id,
                },
                {
                    "id": f"evt_perf_chain_correct_a_{account_index:04d}",
                    "account_id": source_id,
                    "type": "event_corrected",
                    "timestamp": "2026-03-06T00:00:00Z",
                    "correction_of": f"evt_perf_chain_source_usage_a_{account_index:04d}",
                    "effective_at": "2026-03-02T00:00:00Z",
                    "recorded_at": "2026-03-06T00:00:00Z",
                    "usage": 5 + (account_index % 11),
                },
                {
                    "id": f"evt_perf_chain_void_b_{account_index:04d}",
                    "account_id": source_id,
                    "type": "event_voided",
                    "timestamp": "2026-03-07T00:00:00Z",
                    "voided_event_id": f"evt_perf_chain_source_usage_b_{account_index:04d}",
                },
                {
                    "id": f"evt_perf_chain_post_source_usage_{account_index:04d}",
                    "account_id": source_id,
                    "type": "usage_recorded",
                    "timestamp": "2026-03-08T00:00:00Z",
                    "usage": 4,
                },
                {
                    "id": f"evt_perf_chain_invoice_{account_index:04d}",
                    "account_id": source_id,
                    "type": "invoice_issued",
                    "timestamp": "2026-03-09T00:00:00Z",
                    "amount_cents": 4900,
                    "currency": "usd",
                    "invoice_id": f"inv_perf_chain_{account_index:04d}",
                    "period_start": "2026-03-01T00:00:00Z",
                    "period_end": "2026-04-01T00:00:00Z",
                },
                {
                    "id": f"evt_perf_chain_dest_seats_{account_index:04d}",
                    "account_id": dest_id,
                    "type": "seat_delta_recorded",
                    "timestamp": "2026-03-10T00:00:00Z",
                    "seat_delta": 1,
                },
            ]
        )

    return [
        evaluated_case(
            "v3.performance.digest_10k_events",
            "performance",
            ["OR-001", "RP-002"],
            "v2_performance_digest",
            {
                "raw_events": raw_events,
                "as_of": "2026-02-25T00:00:00Z",
            },
            points=2.0,
            timeout_seconds={"typescript": 60, "python": 60},
        ),
        evaluated_case(
            "v3.performance.merge_correction_digest_11k",
            "performance",
            ["CV-002", "MG-005", "OR-001", "RP-002"],
            "v2_performance_digest",
            {
                "raw_events": complex_events,
                "business_as_of": "2026-03-15T00:00:00Z",
                "audit_as_of": "2026-03-15T00:00:00Z",
            },
            points=3.0,
            timeout_seconds={"typescript": 90, "python": 90},
        ),
        evaluated_case(
            "v3.performance.integrated_incident_digest_10k",
            "performance",
            ["BT-004", "CV-002", "MG-005", "OR-001", "RP-002"],
            "v2_performance_digest",
            {
                "raw_events": integrated_incident_events(noise_accounts=1000),
                "business_as_of": "2026-09-13T00:00:00Z",
                "audit_as_of": "2026-09-13T00:00:00Z",
            },
            points=3.5,
            timeout_seconds={"typescript": 120, "python": 120},
        ),
    ]


def parity_cases() -> list[dict[str, Any]]:
    raw_events = [
        {
            "id": "evt_parity_open",
            "account_id": "acct_v3_parity",
            "type": "account_opened",
            "timestamp": "2026-03-01T00:00:00Z",
            "plan": "enterprise",
        },
        {
            "id": "evt_parity_coupon",
            "account_id": "acct_v3_parity",
            "type": "coupon_applied",
            "timestamp": "2026-03-02T00:00:00Z",
            "coupon": "save10",
            "expires_at": "2026-04-01T00:00:00Z",
        },
        {
            "id": "evt_parity_invoice",
            "account_id": "acct_v3_parity",
            "type": "invoice_issued",
            "timestamp": "2026-03-03T00:00:00Z",
            "amount_cents": 19900,
            "currency": "usd",
            "invoice_id": "inv_v3_parity",
            "period_start": "2026-03-01T00:00:00Z",
            "period_end": "2026-04-01T00:00:00Z",
        },
    ]
    merge_source_events = [
        {
            "id": "evt_support_dest_open",
            "account_id": "acct_support_dest",
            "type": "account_opened",
            "timestamp": "2026-05-01T00:00:00Z",
            "plan": "starter",
            "quantity": 1,
        },
        {
            "id": "evt_support_source_open",
            "account_id": "acct_support_source",
            "type": "account_opened",
            "timestamp": "2026-05-01T00:00:00Z",
            "plan": "pro",
            "quantity": 2,
        },
        {
            "id": "evt_support_dest_currency",
            "account_id": "acct_support_dest",
            "type": "payment_succeeded",
            "timestamp": "2026-05-01T06:00:00Z",
            "amount_cents": 0,
            "currency": "usd",
        },
        {
            "id": "evt_support_source_payment",
            "account_id": "acct_support_source",
            "type": "payment_succeeded",
            "timestamp": "2026-05-02T00:00:00Z",
            "amount_cents": 1200,
            "currency": "usd",
            "invoice_id": "inv_support_original",
            "period_start": "2026-05-01T00:00:00Z",
            "period_end": "2026-06-01T00:00:00Z",
        },
        {
            "id": "evt_support_source_usage",
            "account_id": "acct_support_source",
            "type": "usage_recorded",
            "timestamp": "2026-05-02T12:00:00Z",
            "usage": 8,
        },
        {
            "id": "evt_support_merge",
            "account_id": "acct_support_dest",
            "type": "account_merged",
            "timestamp": "2026-05-03T00:00:00Z",
            "merge_from_account_id": "acct_support_source",
        },
        {
            "id": "evt_support_correct_payment",
            "account_id": "acct_support_source",
            "type": "event_corrected",
            "timestamp": "2026-05-04T00:00:00Z",
            "recorded_at": "2026-05-04T00:00:00Z",
            "effective_at": "2026-05-02T00:00:00Z",
            "correction_of": "evt_support_source_payment",
            "amount_cents": 4900,
            "currency": "usd",
            "invoice_id": "inv_support_corrected",
            "period_start": "2026-05-01T00:00:00Z",
            "period_end": "2026-06-01T00:00:00Z",
        },
    ]
    return [
        evaluated_case(
            "v3.parity.summary_and_report",
            "parity",
            ["PY-001", "RP-001", "RP-006"],
            "v2_parity",
            {"raw_events": raw_events, "as_of": "2026-03-15T00:00:00Z"},
            points=1.0,
        ),
        evaluated_case(
            "v3.parity.merge_source_correction_report",
            "parity",
            ["CV-002", "MG-002", "MG-005", "RP-001", "PY-001"],
            "v2_parity",
            {
                "raw_events": merge_source_events,
                "business_as_of": "2026-05-05T00:00:00Z",
                "audit_as_of": "2026-05-05T00:00:00Z",
            },
            points=2.0,
        ),
        evaluated_case(
            "v3.parity.integrated_incident_summary_report",
            "parity",
            ["BT-004", "CV-002", "MG-005", "RP-001", "RP-006", "PY-001"],
            "v2_parity",
            {
                "raw_events": integrated_incident_events(),
                "business_as_of": "2026-09-13T00:00:00Z",
                "audit_as_of": "2026-09-13T00:00:00Z",
            },
            points=2.5,
        ),
    ]


def evaluated_case(
    case_id: str,
    category: str,
    rule_ids: list[str],
    operation: str,
    input_payload: dict[str, Any],
    *,
    points: float,
    languages: list[str] | None = None,
    timeout_seconds: dict[str, int] | None = None,
) -> dict[str, Any]:
    case_payload: dict[str, Any] = {
        "id": case_id,
        "category": category,
        "rule_ids": rule_ids,
        "languages": languages or ["typescript", "python"],
        "operation": operation,
        "input": input_payload,
        "points": points,
    }
    if timeout_seconds is not None:
        case_payload["timeout_seconds"] = timeout_seconds
    case_payload["expected"] = evaluate_case(case_payload)
    return case_payload


def _validate_cases_dir(cases_dir: Path) -> Path:
    output_dir = cases_dir.resolve()
    if output_dir == CASES_DIR.resolve():
        return output_dir
    if "cases" not in output_dir.name.lower():
        raise ValueError(
            f"{cases_dir}: output directory name must include 'cases' so stale JSON cleanup is scoped safely"
        )
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"{cases_dir}: output path exists and is not a directory")
    if output_dir.exists():
        unexpected = [
            child.name
            for child in output_dir.iterdir()
            if child.is_dir() or child.suffix.lower() != ".json"
        ]
        if unexpected:
            shown = ", ".join(sorted(unexpected)[:5])
            raise ValueError(
                f"{cases_dir}: output directory contains non-case entries and will not be cleaned: {shown}"
            )
    return output_dir


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic RuleLedger v3 hidden cases.")
    parser.add_argument("--cases-dir", type=Path, default=CASES_DIR)
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        main(args.cases_dir)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from None
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
