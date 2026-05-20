from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
from typing import Any

try:
    from ruleledger_v2_oracle import (
        GENERATED_AT,
        SEED,
        calculate_plan_change_proration,
        evaluate_case,
        export_ledger_report,
        normalize_event,
        parse_event_line,
        performance_digest,
        summarize_raw_events,
    )
except ModuleNotFoundError:
    from hidden_tests.generators.ruleledger_v2_oracle import (
        GENERATED_AT,
        SEED,
        calculate_plan_change_proration,
        evaluate_case,
        export_ledger_report,
        normalize_event,
        parse_event_line,
        performance_digest,
        summarize_raw_events,
    )


ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "hidden_tests" / "cases_v2"

REQUIRED_CATEGORIES = (
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
)

CATEGORY_WEIGHTS = {
    "parse_validation": 0.08,
    "normalization": 0.10,
    "bitemporal_replay": 0.14,
    "lifecycle_precedence": 0.13,
    "billing_proration": 0.13,
    "account_merges": 0.11,
    "metamorphic_invariants": 0.13,
    "performance": 0.08,
    "reporting": 0.05,
    "parity": 0.05,
}


def main(cases_dir: Path = CASES_DIR) -> None:
    cases_dir = _validate_cases_dir(cases_dir)
    cases_dir.mkdir(parents=True, exist_ok=True)
    for stale_file in cases_dir.glob("*.json"):
        stale_file.unlink()

    files = {
        "parse_validation.json": parse_validation_cases(),
        "normalization.json": normalization_cases(),
        "bitemporal_replay.json": bitemporal_replay_cases(),
        "lifecycle_precedence.json": lifecycle_precedence_cases(),
        "billing_proration.json": billing_proration_cases(),
        "account_merges.json": account_merge_cases(),
        "metamorphic_invariants.json": metamorphic_invariant_cases(),
        "performance.json": performance_cases(),
        "reporting.json": reporting_cases(),
        "parity.json": parity_cases(),
    }

    manifest_files = {}
    for filename, cases in files.items():
        payload = {
            "schema_version": 2,
            "benchmark": "ruleledger_v2",
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
        "schema_version": 2,
        "benchmark": "ruleledger_v2",
        "seed": SEED,
        "generated_at": GENERATED_AT,
        "category_weights": CATEGORY_WEIGHTS,
        "files": manifest_files,
    }
    write_json(cases_dir / "manifest.json", manifest)


def parse_validation_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    parse_inputs = [
        ("parse.empty_line", "  ", ["BT-001"]),
        ("parse.invalid_json", "{not-json", ["BT-001"]),
        ("parse.non_object_array", '["evt"]', ["BT-001"]),
        ("parse.non_object_null", "null", ["BT-001"]),
    ]
    for case_id, line, rule_ids in parse_inputs:
        cases.append(
            case(
                case_id,
                "parse_validation",
                rule_ids,
                "parse_line",
                {"line": line},
                parse_event_line(line),
                points=1.0,
            )
        )

    invalid_events = [
        (
            "normalize.missing_recorded_timestamp",
            {
                "id": "evt_v2_missing_timestamp",
                "account_id": "acct_parse",
                "type": "account_opened",
            },
            ["BT-001"],
        ),
        (
            "normalize.invalid_sequence",
            {
                "id": "evt_v2_bad_sequence",
                "account_id": "acct_parse",
                "type": "account_opened",
                "timestamp": "2026-01-01T00:00:00Z",
                "sequence": -1,
            },
            ["OR-002"],
        ),
        (
            "normalize.invalid_currency",
            {
                "id": "evt_v2_bad_currency",
                "account_id": "acct_parse",
                "type": "payment_succeeded",
                "timestamp": "2026-01-01T00:00:00Z",
                "amount": "10.00",
                "currency": "US",
            },
            ["BL-002"],
        ),
        (
            "normalize.invalid_period_bounds",
            {
                "id": "evt_v2_bad_period",
                "account_id": "acct_parse",
                "type": "invoice_issued",
                "timestamp": "2026-01-01T00:00:00Z",
                "period_start": "2026-02-01T00:00:00Z",
                "period_end": "2026-01-01T00:00:00Z",
            },
            ["BL-003"],
        ),
        (
            "normalize.blank_merge_source",
            {
                "id": "evt_v2_blank_merge",
                "account_id": "acct_parse",
                "type": "account_merged",
                "timestamp": "2026-01-01T00:00:00Z",
                "merge_from_account_id": " ",
            },
            ["MG-001"],
        ),
        (
            "normalize.invalid_quantity",
            {
                "id": "evt_v2_bad_quantity",
                "account_id": "acct_parse",
                "type": "usage_recorded",
                "timestamp": "2026-01-01T00:00:00Z",
                "quantity": -5,
            },
            ["BL-007", "LC-010"],
        ),
    ]
    for case_id, raw_event, rule_ids in invalid_events:
        expected = normalize_event(raw_event)
        cases.append(
            case(
                case_id,
                "parse_validation",
                rule_ids,
                "normalize_event",
                {"raw_event": raw_event},
                {"ok": False, "error": expected["error"], "issues": expected["issues"]},
                points=1.0,
                match="normalize_error",
            )
        )
    return cases


def normalization_cases() -> list[dict[str, Any]]:
    raw_events = [
        (
            "normalization.defaults_effective_recorded",
            {
                "id": " evt_v2_defaults ",
                "account_id": " acct_norm ",
                "type": "account_opened",
                "timestamp": "2026-02-01T05:00:00-05:00",
                "plan": " starter ",
                "quantity": 2,
            },
            ["BT-001", "BT-002", "BT-003", "OR-002", "LC-002"],
        ),
        (
            "normalization.money_currency_invoice",
            {
                "id": "evt_v2_money",
                "account_id": "acct_norm",
                "type": "payment_succeeded",
                "timestamp": "2026-02-02T00:00:00Z",
                "amount": "001.05",
                "currency": "usd",
                "invoice_id": " inv_norm ",
            },
            ["BL-001", "BL-002"],
        ),
        (
            "normalization.amount_cents_negative_adjustment",
            {
                "id": "evt_v2_credit",
                "account_id": "acct_norm",
                "type": "invoice_issued",
                "timestamp": "2026-02-03T00:00:00Z",
                "amount_cents": -125,
                "currency": "eur",
            },
            ["BL-001", "BL-005"],
        ),
        (
            "normalization.period_fields",
            {
                "id": "evt_v2_period",
                "account_id": "acct_norm",
                "type": "invoice_issued",
                "timestamp": "2026-02-04T00:00:00Z",
                "period_start": "2026-02-01T00:00:00Z",
                "period_end": "2026-03-01T00:00:00Z",
            },
            ["BL-003"],
        ),
        (
            "normalization_correction_void_refs",
            {
                "id": "evt_v2_correction",
                "account_id": "acct_norm",
                "type": "event_corrected",
                "timestamp": "2026-02-05T00:00:00Z",
                "effective_at": "2026-02-01T00:00:00Z",
                "recorded_at": "2026-02-05T00:00:00Z",
                "sequence": 3,
                "correction_of": "evt_target",
                "quantity": 11,
            },
            ["CV-001", "CV-003"],
        ),
        (
            "normalization_merge_source",
            {
                "id": "evt_v2_merge",
                "account_id": "acct_dest",
                "type": "account_merged",
                "timestamp": "2026-02-06T00:00:00Z",
                "merge_from_account_id": "acct_source",
            },
            ["MG-001"],
        ),
    ]
    return [
        case(
            case_id,
            "normalization",
            rule_ids,
            "normalize_event",
            {"raw_event": raw_event},
            normalize_event(raw_event),
            points=1.0,
        )
        for case_id, raw_event, rule_ids in raw_events
    ]


def bitemporal_replay_cases() -> list[dict[str, Any]]:
    late_arrival = [
        opened("evt_bt_open", "acct_bt", "starter", "2026-03-01T00:00:00Z"),
        {
            "id": "evt_bt_late_plan",
            "account_id": "acct_bt",
            "type": "plan_changed",
            "timestamp": "2026-03-10T00:00:00Z",
            "effective_at": "2026-03-02T00:00:00Z",
            "recorded_at": "2026-03-10T00:00:00Z",
            "plan": "pro",
        },
    ]
    correction_events = [
        opened("evt_bt_corr_open", "acct_bt_corr", "starter", "2026-03-01T00:00:00Z"),
        usage("evt_bt_usage", "acct_bt_corr", "2026-03-02T00:00:00Z", 10),
        {
            "id": "evt_bt_usage_corrected",
            "account_id": "acct_bt_corr",
            "type": "event_corrected",
            "timestamp": "2026-03-05T00:00:00Z",
            "effective_at": "2026-03-02T00:00:00Z",
            "recorded_at": "2026-03-05T00:00:00Z",
            "correction_of": "evt_bt_usage",
            "usage": 25,
        },
        {
            "id": "evt_bt_usage_voided",
            "account_id": "acct_bt_corr",
            "type": "event_voided",
            "timestamp": "2026-03-06T00:00:00Z",
            "effective_at": "2026-03-02T00:00:00Z",
            "recorded_at": "2026-03-06T00:00:00Z",
            "voided_event_id": "evt_bt_usage",
        },
    ]
    duplicate_tie = [
        opened("evt_bt_dup_open", "acct_bt_dup", "starter", "2026-03-01T00:00:00Z"),
        usage("evt_same", "acct_bt_dup", "2026-03-02T00:00:00Z", 5),
        usage("evt_same", "acct_bt_dup", "2026-03-03T00:00:00Z", 50),
        usage("evt_tie_b", "acct_bt_dup", "2026-03-04T00:00:00Z", 7, sequence=2),
        usage("evt_tie_a", "acct_bt_dup", "2026-03-04T00:00:00Z", 3, sequence=1),
    ]
    cases = [
        reduce_case(
            "bitemporal.late_arrival_before_recorded_at",
            "bitemporal_replay",
            ["BT-004", "BT-005", "BT-006"],
            late_arrival,
            as_of="2026-03-05T00:00:00Z",
            points=2.0,
        ),
        reduce_case(
            "bitemporal.late_arrival_after_recorded_at",
            "bitemporal_replay",
            ["BT-004", "BT-005", "OR-001"],
            late_arrival,
            as_of="2026-03-11T00:00:00Z",
            points=2.0,
        ),
        reduce_case(
            "bitemporal.separate_business_and_audit_cutoffs",
            "bitemporal_replay",
            ["BT-004", "BT-005"],
            late_arrival,
            business_as_of="2026-03-03T00:00:00Z",
            audit_as_of="2026-03-11T00:00:00Z",
            points=2.0,
        ),
        reduce_case(
            "bitemporal.correction_then_void_visibility",
            "bitemporal_replay",
            ["CV-002", "CV-005", "CV-006"],
            correction_events,
            as_of="2026-03-05T12:00:00Z",
            points=2.0,
        ),
        reduce_case(
            "bitemporal.duplicate_and_sequence_order",
            "bitemporal_replay",
            ["OR-001", "OR-002", "OR-003", "OR-004"],
            duplicate_tie,
            as_of="2026-03-10T00:00:00Z",
            points=2.0,
        ),
    ]
    return cases


def lifecycle_precedence_cases() -> list[dict[str, Any]]:
    cases = [
        reduce_case(
            "lifecycle.trial_payment_failure_recovery",
            "lifecycle_precedence",
            ["LC-003", "LC-008", "PY-001"],
            [
                opened("evt_lc_open", "acct_lc", "starter", "2026-04-01T00:00:00Z"),
                event("evt_lc_trial", "acct_lc", "trial_started", "2026-04-02T00:00:00Z"),
                event("evt_lc_fail", "acct_lc", "payment_failed", "2026-04-03T00:00:00Z"),
                event("evt_lc_recover", "acct_lc", "payment_recovered", "2026-04-04T00:00:00Z"),
            ],
            as_of="2026-04-05T00:00:00Z",
            points=2.0,
        ),
        reduce_case(
            "lifecycle.pause_plan_change_resume",
            "lifecycle_precedence",
            ["LC-004", "LC-005"],
            [
                opened("evt_lc_pause_open", "acct_pause", "starter", "2026-04-01T00:00:00Z"),
                event("evt_lc_pause", "acct_pause", "account_paused", "2026-04-02T00:00:00Z"),
                plan_changed("evt_lc_pause_plan", "acct_pause", "2026-04-03T00:00:00Z", "enterprise"),
                event("evt_lc_resume", "acct_pause", "account_resumed", "2026-04-04T00:00:00Z"),
            ],
            as_of="2026-04-05T00:00:00Z",
            points=2.0,
        ),
        reduce_case(
            "lifecycle.cancel_reactivate",
            "lifecycle_precedence",
            ["LC-006"],
            [
                opened("evt_lc_cancel_open", "acct_cancel", "pro", "2026-04-01T00:00:00Z"),
                event("evt_lc_cancel", "acct_cancel", "account_cancelled", "2026-04-02T00:00:00Z"),
                event("evt_lc_reactivate", "acct_cancel", "account_reactivated", "2026-04-03T00:00:00Z"),
            ],
            as_of="2026-04-04T00:00:00Z",
            points=1.5,
        ),
        reduce_case(
            "lifecycle.close_is_terminal",
            "lifecycle_precedence",
            ["LC-007"],
            [
                opened("evt_lc_close_open", "acct_closed", "starter", "2026-04-01T00:00:00Z"),
                event("evt_lc_close", "acct_closed", "account_closed", "2026-04-02T00:00:00Z"),
                event("evt_lc_reopen_attempt", "acct_closed", "account_reactivated", "2026-04-03T00:00:00Z"),
                plan_changed("evt_lc_closed_plan", "acct_closed", "2026-04-04T00:00:00Z", "enterprise"),
            ],
            as_of="2026-04-05T00:00:00Z",
            points=2.0,
        ),
        reduce_case(
            "lifecycle.usage_coupon_and_seats",
            "lifecycle_precedence",
            ["LC-009", "LC-010", "LC-011"],
            [
                opened("evt_lc_seat_open", "acct_seats", "pro", "2026-04-01T00:00:00Z", quantity=3),
                coupon("evt_lc_coupon", "acct_seats", "2026-04-02T00:00:00Z", "save10", "2026-04-30T00:00:00Z"),
                usage("evt_lc_usage", "acct_seats", "2026-04-03T00:00:00Z", 120),
                seat_delta("evt_lc_seat_delta", "acct_seats", "2026-04-04T00:00:00Z", -1),
            ],
            as_of="2026-04-10T00:00:00Z",
            points=2.0,
        ),
    ]
    return cases


def billing_proration_cases() -> list[dict[str, Any]]:
    inputs = [
        (
            "billing.mid_month_upgrade_one_seat",
            {
                "old_plan": "starter",
                "new_plan": "pro",
                "period_start": "2026-05-01T00:00:00Z",
                "period_end": "2026-06-01T00:00:00Z",
                "change_effective_at": "2026-05-16T12:00:00Z",
                "quantity": 1,
            },
            ["BL-003", "BL-004", "BL-005", "BL-006"],
        ),
        (
            "billing.downgrade_three_seats",
            {
                "old_plan": "enterprise",
                "new_plan": "pro",
                "period_start": "2026-05-01T00:00:00Z",
                "period_end": "2026-06-01T00:00:00Z",
                "change_effective_at": "2026-05-20T00:00:00Z",
                "quantity": 3,
            },
            ["BL-004", "BL-006", "BL-007"],
        ),
        (
            "billing.half_away_rounding_boundary",
            {
                "old_plan": "starter",
                "new_plan": "pro",
                "period_start": "2026-01-01T00:00:00Z",
                "period_end": "2026-01-03T00:00:00Z",
                "change_effective_at": "2026-01-02T00:00:00Z",
                "quantity": 1,
            },
            ["BL-004", "BL-005"],
        ),
    ]
    cases = [
        case(
            case_id,
            "billing_proration",
            rule_ids,
            "v2_calculate_proration",
            input_payload,
            calculate_plan_change_proration(
                input_payload["old_plan"],
                input_payload["new_plan"],
                input_payload["period_start"],
                input_payload["period_end"],
                input_payload["change_effective_at"],
                input_payload["quantity"],
            ),
            points=2.0,
        )
        for case_id, input_payload, rule_ids in inputs
    ]
    cases.append(
        reduce_case(
            "billing.invoice_metadata_summary",
            "billing_proration",
            ["BL-001", "BL-002", "BL-003", "RP-001"],
            [
                opened("evt_bill_open", "acct_bill", "pro", "2026-05-01T00:00:00Z", quantity=2),
                {
                    "id": "evt_bill_invoice",
                    "account_id": "acct_bill",
                    "type": "invoice_issued",
                    "timestamp": "2026-05-01T00:00:00Z",
                    "amount_cents": 9800,
                    "currency": "usd",
                    "invoice_id": "inv_bill_001",
                    "period_start": "2026-05-01T00:00:00Z",
                    "period_end": "2026-06-01T00:00:00Z",
                },
                payment("evt_bill_pay", "acct_bill", "2026-05-02T00:00:00Z", 9800, currency="usd"),
            ],
            as_of="2026-05-03T00:00:00Z",
            points=2.0,
        )
    )
    return cases


def account_merge_cases() -> list[dict[str, Any]]:
    cases = [
        reduce_case(
            "merge.simple_source_suppressed",
            "account_merges",
            ["MG-001", "MG-002", "MG-003", "MG-004"],
            [
                opened("evt_merge_src_open", "acct_src", "starter", "2026-06-01T00:00:00Z"),
                usage("evt_merge_src_usage", "acct_src", "2026-06-02T00:00:00Z", 40),
                opened("evt_merge_dst_open", "acct_dst", "pro", "2026-06-01T00:00:00Z"),
                event(
                    "evt_merge",
                    "acct_dst",
                    "account_merged",
                    "2026-06-03T00:00:00Z",
                    merge_from_account_id="acct_src",
                ),
            ],
            as_of="2026-06-04T00:00:00Z",
            points=2.0,
        ),
        reduce_case(
            "merge.post_merge_source_event_redirected",
            "account_merges",
            ["MG-005", "LC-010"],
            [
                opened("evt_merge_post_src_open", "acct_src_post", "starter", "2026-06-01T00:00:00Z"),
                opened("evt_merge_post_dst_open", "acct_dst_post", "pro", "2026-06-01T00:00:00Z"),
                event(
                    "evt_merge_post",
                    "acct_dst_post",
                    "account_merged",
                    "2026-06-02T00:00:00Z",
                    merge_from_account_id="acct_src_post",
                ),
                usage("evt_merge_post_usage", "acct_src_post", "2026-06-03T00:00:00Z", 33),
            ],
            as_of="2026-06-04T00:00:00Z",
            points=2.0,
        ),
        reduce_case(
            "merge.multi_hop_lineage",
            "account_merges",
            ["MG-002", "MG-004"],
            [
                opened("evt_merge_a_open", "acct_a", "starter", "2026-06-01T00:00:00Z"),
                opened("evt_merge_b_open", "acct_b", "pro", "2026-06-01T00:00:00Z"),
                opened("evt_merge_c_open", "acct_c", "enterprise", "2026-06-01T00:00:00Z"),
                event("evt_merge_ab", "acct_b", "account_merged", "2026-06-02T00:00:00Z", merge_from_account_id="acct_a"),
                event("evt_merge_bc", "acct_c", "account_merged", "2026-06-03T00:00:00Z", merge_from_account_id="acct_b"),
            ],
            as_of="2026-06-04T00:00:00Z",
            points=2.0,
        ),
        reduce_case(
            "merge.duplicate_event_ids_across_lineage",
            "account_merges",
            ["OR-003", "MG-002"],
            [
                opened("evt_merge_dup_src_open", "acct_dup_src", "starter", "2026-06-01T00:00:00Z"),
                usage("evt_shared_dup", "acct_dup_src", "2026-06-02T00:00:00Z", 10),
                opened("evt_merge_dup_dst_open", "acct_dup_dst", "pro", "2026-06-01T00:00:00Z"),
                usage("evt_shared_dup", "acct_dup_dst", "2026-06-02T01:00:00Z", 100),
                event(
                    "evt_merge_dup",
                    "acct_dup_dst",
                    "account_merged",
                    "2026-06-03T00:00:00Z",
                    merge_from_account_id="acct_dup_src",
                ),
            ],
            as_of="2026-06-04T00:00:00Z",
            points=2.0,
        ),
    ]
    return cases


def metamorphic_invariant_cases() -> list[dict[str, Any]]:
    base = [
        opened("evt_meta_open", "acct_meta", "starter", "2026-07-01T00:00:00Z"),
        usage("evt_meta_usage_a", "acct_meta", "2026-07-02T00:00:00Z", 40),
        usage("evt_meta_usage_b", "acct_meta", "2026-07-03T00:00:00Z", 60),
        payment("evt_meta_pay", "acct_meta", "2026-07-04T00:00:00Z", 1200),
    ]
    cases = [
        metamorphic_case(
            "metamorphic.shuffled_equivalent_input",
            ["OR-001", "PY-001"],
            base,
            [{"name": "shuffled", "raw_events": [base[2], base[0], base[3], base[1]]}],
            target_account_id="acct_meta",
        ),
        metamorphic_case(
            "metamorphic.unrelated_account_injection",
            ["LC-010"],
            base,
            [
                {
                    "name": "with_unrelated",
                    "raw_events": base + [opened("evt_meta_other_open", "acct_other", "enterprise", "2026-07-01T00:00:00Z")],
                }
            ],
            target_account_id="acct_meta",
        ),
        metamorphic_case(
            "metamorphic.duplicate_idempotent_event",
            ["OR-003"],
            base,
            [{"name": "duplicated_payment", "raw_events": base + [dict(base[-1])]}],
            target_account_id="acct_meta",
        ),
        metamorphic_case(
            "metamorphic.split_usage_batches",
            ["LC-010"],
            [opened("evt_meta_split_open", "acct_split", "starter", "2026-07-01T00:00:00Z"), usage("evt_meta_split_usage", "acct_split", "2026-07-02T00:00:00Z", 100)],
            [
                {
                    "name": "split",
                    "raw_events": [
                        opened("evt_meta_split_open", "acct_split", "starter", "2026-07-01T00:00:00Z"),
                        usage("evt_meta_split_usage_a", "acct_split", "2026-07-02T00:00:00Z", 40),
                        usage("evt_meta_split_usage_b", "acct_split", "2026-07-02T01:00:00Z", 60),
                    ],
                }
            ],
            target_account_id="acct_split",
        ),
        metamorphic_case(
            "metamorphic.normalization_stability",
            ["BT-001", "BT-002", "BT-003"],
            [opened(" evt_meta_norm_open ", " acct_norm_stable ", "starter", "2026-07-01T05:00:00-05:00")],
            [
                {
                    "name": "canonical",
                    "raw_events": [
                        opened(
                            "evt_meta_norm_open",
                            "acct_norm_stable",
                            "starter",
                            "2026-07-01T10:00:00.000Z",
                        )
                    ],
                }
            ],
            target_account_id="acct_norm_stable",
        ),
    ]
    return cases


def performance_cases() -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    many_accounts = []
    for account_index in range(100):
        account_id = f"acct_perf_{account_index:03d}"
        many_accounts.append(opened(f"evt_perf_open_{account_index:03d}", account_id, "starter", "2026-08-01T00:00:00Z"))
        for event_index in range(100):
            usage_value = rng.randint(0, 9)
            many_accounts.append(
                usage(
                    f"evt_perf_usage_{account_index:03d}_{event_index:03d}",
                    account_id,
                    f"2026-08-{(event_index % 28) + 1:02d}T{event_index % 24:02d}:00:00Z",
                    usage_value,
                )
            )

    long_history = [opened("evt_perf_long_open", "acct_perf_long", "pro", "2026-09-01T00:00:00Z")]
    for event_index in range(10000):
        long_history.append(
            usage(
                f"evt_perf_long_usage_{event_index:05d}",
                "acct_perf_long",
                f"2026-09-{(event_index % 28) + 1:02d}T{event_index % 24:02d}:00:00Z",
                event_index % 5,
                sequence=event_index % 7,
            )
        )

    return [
        case(
            "performance.many_accounts_10k_events",
            "performance",
            ["OR-001", "LC-010", "RP-002"],
            "v2_performance_digest",
            {"raw_events": many_accounts, "as_of": "2026-09-01T00:00:00Z"},
            performance_digest(many_accounts, "2026-09-01T00:00:00Z"),
            points=3.0,
        ),
        case(
            "performance.single_account_long_history_10k_events",
            "performance",
            ["OR-001", "LC-010"],
            "v2_performance_digest",
            {"raw_events": long_history, "as_of": "2026-10-01T00:00:00Z"},
            performance_digest(long_history, "2026-10-01T00:00:00Z"),
            points=3.0,
        ),
    ]


def reporting_cases() -> list[dict[str, Any]]:
    summaries = [
        {
            "accountId": "acct_report_z",
            "status": "closed",
            "plan": "free",
            "features": [],
            "usage": 0,
            "usageLimit": 0,
            "overLimit": False,
            "totalPaidCents": 0,
            "currency": None,
            "seats": 0,
            "couponCode": None,
            "couponActive": False,
            "invoiceIds": [],
            "lastInvoiceId": None,
            "lastPeriodStart": None,
            "lastPeriodEnd": None,
            "mergedFromAccountIds": [],
            "closedAt": "2026-10-01T00:00:00.000Z",
            "lastEventAt": "2026-10-01T00:00:00.000Z",
        },
        {
            "accountId": "acct_report_a",
            "status": "active",
            "plan": "enterprise",
            "features": ["audit_log", "dashboard", "exports", "priority_support", "rules", "sso"],
            "usage": 5,
            "usageLimit": 100000,
            "overLimit": False,
            "totalPaidCents": 19900,
            "currency": "USD",
            "seats": 4,
            "couponCode": "SAVE10",
            "couponActive": True,
            "invoiceIds": ["inv_report_1", "inv_report_2"],
            "lastInvoiceId": "inv_report_2",
            "lastPeriodStart": "2026-10-01T00:00:00.000Z",
            "lastPeriodEnd": "2026-11-01T00:00:00.000Z",
            "mergedFromAccountIds": ["acct_old_a", "acct_old_b"],
            "closedAt": None,
            "lastEventAt": "2026-10-02T00:00:00.000Z",
        },
    ]
    escaping_summaries = [
        {
            **summaries[1],
            "accountId": "acct_report_quote",
            "couponCode": 'SAVE,"10"',
            "invoiceIds": ["inv,comma", 'inv"quote'],
            "mergedFromAccountIds": ["acct\nline"],
        }
    ]
    return [
        case(
            "reporting.header_row_order_and_nulls",
            "reporting",
            ["RP-001", "RP-002", "RP-003", "RP-004", "RP-005"],
            "v2_export_report",
            {"summaries": summaries},
            export_ledger_report(summaries),
            points=2.0,
        ),
        case(
            "reporting.csv_escaping",
            "reporting",
            ["RP-006"],
            "v2_export_report",
            {"summaries": escaping_summaries},
            export_ledger_report(escaping_summaries),
            points=2.0,
        ),
        reduce_case(
            "reporting.summary_to_csv_contract",
            "reporting",
            ["RP-001", "RP-002", "PY-001"],
            [
                opened("evt_report_open", "acct_report_pipeline", "enterprise", "2026-10-01T00:00:00Z"),
                payment("evt_report_pay", "acct_report_pipeline", "2026-10-02T00:00:00Z", 19900, currency="usd"),
                usage("evt_report_usage", "acct_report_pipeline", "2026-10-03T00:00:00Z", 7),
            ],
            as_of="2026-10-04T00:00:00Z",
            points=1.0,
        ),
    ]


def parity_cases() -> list[dict[str, Any]]:
    cases = [
        parity_case(
            "parity.bitemporal_merge_report",
            [
                opened("evt_parity_src_open", "acct_parity_src", "starter", "2026-11-01T00:00:00Z"),
                usage("evt_parity_src_usage", "acct_parity_src", "2026-11-02T00:00:00Z", 25),
                opened("evt_parity_dst_open", "acct_parity_dst", "pro", "2026-11-01T00:00:00Z"),
                event("evt_parity_merge", "acct_parity_dst", "account_merged", "2026-11-03T00:00:00Z", merge_from_account_id="acct_parity_src"),
                payment("evt_parity_pay", "acct_parity_dst", "2026-11-04T00:00:00Z", 4900, currency="usd"),
            ],
            ["MG-002", "RP-001", "PY-001"],
        ),
        parity_case(
            "parity.correction_void_csv",
            [
                opened("evt_parity_corr_open", "acct_parity_corr", "starter", "2026-11-01T00:00:00Z"),
                usage("evt_parity_usage", "acct_parity_corr", "2026-11-02T00:00:00Z", 10),
                {
                    "id": "evt_parity_correct",
                    "account_id": "acct_parity_corr",
                    "type": "event_corrected",
                    "timestamp": "2026-11-03T00:00:00Z",
                    "effective_at": "2026-11-02T00:00:00Z",
                    "recorded_at": "2026-11-03T00:00:00Z",
                    "correction_of": "evt_parity_usage",
                    "usage": 12,
                },
            ],
            ["CV-002", "CV-003", "PY-001"],
        ),
    ]
    return cases


def reduce_case(
    case_id: str,
    category: str,
    rule_ids: list[str],
    raw_events: list[dict[str, Any]],
    *,
    as_of: str | None = None,
    business_as_of: str | None = None,
    audit_as_of: str | None = None,
    points: float,
) -> dict[str, Any]:
    input_payload: dict[str, Any] = {"raw_events": raw_events}
    if as_of is not None:
        input_payload["as_of"] = as_of
    if business_as_of is not None:
        input_payload["business_as_of"] = business_as_of
    if audit_as_of is not None:
        input_payload["audit_as_of"] = audit_as_of
    return case(
        case_id,
        category,
        rule_ids,
        "v2_reduce_and_summarize",
        input_payload,
        summarize_raw_events(raw_events, as_of, business_as_of=business_as_of, audit_as_of=audit_as_of),
        points=points,
    )


def metamorphic_case(
    case_id: str,
    rule_ids: list[str],
    baseline: list[dict[str, Any]],
    variants: list[dict[str, Any]],
    *,
    target_account_id: str | None = None,
) -> dict[str, Any]:
    input_payload: dict[str, Any] = {"baseline": baseline, "variants": variants}
    if target_account_id is not None:
        input_payload["target_account_id"] = target_account_id
    metadata_case = {
        "operation": "v2_metamorphic",
        "input": input_payload,
    }
    return case(
        case_id,
        "metamorphic_invariants",
        rule_ids,
        "v2_metamorphic",
        input_payload,
        evaluate_case(metadata_case),
        points=2.0,
    )


def parity_case(case_id: str, raw_events: list[dict[str, Any]], rule_ids: list[str]) -> dict[str, Any]:
    input_payload = {"raw_events": raw_events, "as_of": "2026-12-01T00:00:00Z"}
    metadata_case = {"operation": "v2_parity", "input": input_payload}
    return case(
        case_id,
        "parity",
        rule_ids,
        "v2_parity",
        input_payload,
        evaluate_case(metadata_case),
        points=2.0,
        languages=["parity"],
    )


def case(
    case_id: str,
    category: str,
    rule_ids: list[str],
    operation: str,
    input_payload: dict[str, Any],
    expected: Any,
    *,
    points: float,
    languages: list[str] | None = None,
    match: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": case_id,
        "category": category,
        "rule_ids": rule_ids,
        "operation": operation,
        "languages": languages or ["typescript", "python"],
        "points": points,
        "input": input_payload,
        "expected": expected,
    }
    if match is not None:
        payload["match"] = match
    return payload


def event(
    event_id: str,
    account_id: str,
    event_type: str,
    timestamp: str,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "id": event_id,
        "account_id": account_id,
        "type": event_type,
        "timestamp": timestamp,
    }
    payload.update(extra)
    return payload


def opened(event_id: str, account_id: str, plan: str, timestamp: str, *, quantity: int | None = None) -> dict[str, Any]:
    payload = event(event_id, account_id, "account_opened", timestamp, plan=plan)
    if quantity is not None:
        payload["quantity"] = quantity
    return payload


def plan_changed(event_id: str, account_id: str, timestamp: str, plan: str) -> dict[str, Any]:
    return event(event_id, account_id, "plan_changed", timestamp, plan=plan)


def usage(
    event_id: str,
    account_id: str,
    timestamp: str,
    value: int,
    *,
    sequence: int | None = None,
) -> dict[str, Any]:
    payload = event(event_id, account_id, "usage_recorded", timestamp, usage=value)
    if sequence is not None:
        payload["sequence"] = sequence
    return payload


def payment(
    event_id: str,
    account_id: str,
    timestamp: str,
    amount_cents: int,
    *,
    currency: str = "usd",
) -> dict[str, Any]:
    return event(
        event_id,
        account_id,
        "payment_succeeded",
        timestamp,
        amount_cents=amount_cents,
        currency=currency,
    )


def coupon(event_id: str, account_id: str, timestamp: str, code: str, expires_at: str) -> dict[str, Any]:
    return event(event_id, account_id, "coupon_applied", timestamp, coupon=code, expires_at=expires_at)


def seat_delta(event_id: str, account_id: str, timestamp: str, delta: int) -> dict[str, Any]:
    return event(event_id, account_id, "seat_delta_recorded", timestamp, seat_delta=delta)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic RuleLedger v2 hidden cases.")
    parser.add_argument(
        "--cases-dir",
        default=CASES_DIR,
        type=Path,
        help="Directory to write generated v2 hidden case JSON files.",
    )
    return parser.parse_args(argv)


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


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        main(args.cases_dir)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from None
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
