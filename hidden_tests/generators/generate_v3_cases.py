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
            "v3.compat.report_csv_escaping",
            "pass_to_pass",
            ["RP-001", "RP-006", "PY-001"],
            "v2_export_report",
            {"summaries": [summary]},
            points=1.0,
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
        )
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
    return [
        evaluated_case(
            "v3.parity.summary_and_report",
            "parity",
            ["PY-001", "RP-001", "RP-006"],
            "v2_parity",
            {"raw_events": raw_events, "as_of": "2026-03-15T00:00:00Z"},
            points=1.0,
        )
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
