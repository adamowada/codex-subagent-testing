from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ruleledger_oracle import (
    SEED,
    evaluate_raw_events,
    export_ledger_report,
    normalize_event,
    parse_event_line,
    summarize_raw_events,
)


ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "hidden_tests" / "cases"
GENERATED_AT = "2026-05-19T00:00:00.000Z"

CATEGORY_WEIGHTS = {
    "parse_validation": 0.15,
    "normalization": 0.20,
    "state_reduction": 0.35,
    "reporting": 0.15,
    "immutability": 0.05,
    "parity": 0.10,
}


def main() -> None:
    CASES_DIR.mkdir(parents=True, exist_ok=True)

    files = {
        "parse_validation.json": parse_validation_cases(),
        "normalization.json": normalization_cases(),
        "state_reduction.json": state_reduction_cases(),
        "reporting.json": reporting_cases(),
        "immutability.json": immutability_cases(),
        "parity.json": parity_cases(),
    }

    manifest_files = {}
    for filename, cases in files.items():
        payload = {
            "schema_version": 1,
            "seed": SEED,
            "generated_at": GENERATED_AT,
            "cases": cases,
        }
        path = CASES_DIR / filename
        write_json(path, payload)
        manifest_files[filename] = {
            "case_count": len(cases),
            "sha256": sha256(path),
        }

    manifest = {
        "schema_version": 1,
        "seed": SEED,
        "generated_at": GENERATED_AT,
        "category_weights": CATEGORY_WEIGHTS,
        "files": manifest_files,
    }
    write_json(CASES_DIR / "manifest.json", manifest)


def parse_validation_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    for case_id, line in [
        ("parse.empty-line", "   "),
        ("parse.invalid-json", "{not-json"),
        ("parse.non-object-array", '["evt_1"]'),
        ("parse.non-object-null", "null"),
    ]:
        cases.append(
            {
                "id": case_id,
                "category": "parse_validation",
                "operation": "parse_line",
                "languages": ["typescript", "python"],
                "points": 1,
                "input": {"line": line},
                "expected": parse_event_line(line),
            }
        )

    invalid_events = [
        (
            "normalize.missing-id",
            {
                "account_id": "acct_hidden",
                "type": "account_opened",
                "timestamp": "2026-01-01T00:00:00Z",
            },
        ),
        (
            "normalize.blank-account",
            {
                "id": "evt_blank_account",
                "account_id": "   ",
                "type": "account_opened",
                "timestamp": "2026-01-01T00:00:00Z",
            },
        ),
        (
            "normalize.invalid-type",
            {
                "id": "evt_bad_type",
                "account_id": "acct_hidden",
                "type": "subscription_started",
                "timestamp": "2026-01-01T00:00:00Z",
            },
        ),
        (
            "normalize.invalid-plan",
            {
                "id": "evt_bad_plan",
                "account_id": "acct_hidden",
                "type": "account_opened",
                "timestamp": "2026-01-01T00:00:00Z",
                "plan": "gold",
            },
        ),
        (
            "normalize.invalid-timestamp",
            {
                "id": "evt_bad_timestamp",
                "account_id": "acct_hidden",
                "type": "account_opened",
                "timestamp": "2026-13-99T99:99:99Z",
            },
        ),
        (
            "normalize.missing-timestamp",
            {
                "id": "evt_missing_timestamp",
                "account_id": "acct_hidden",
                "type": "account_opened",
            },
        ),
        (
            "normalize.invalid-amount",
            {
                "id": "evt_bad_amount",
                "account_id": "acct_hidden",
                "type": "payment_succeeded",
                "timestamp": "2026-01-01T00:00:00Z",
                "amount": "10.999",
            },
        ),
        (
            "normalize.invalid-usage",
            {
                "id": "evt_bad_usage",
                "account_id": "acct_hidden",
                "type": "usage_recorded",
                "timestamp": "2026-01-01T00:00:00Z",
                "usage": -1,
            },
        ),
        (
            "normalize.non-string-usage",
            {
                "id": "evt_usage_string",
                "account_id": "acct_hidden",
                "type": "usage_recorded",
                "timestamp": "2026-01-01T00:00:00Z",
                "usage": "5",
            },
        ),
        (
            "normalize.fractional-usage",
            {
                "id": "evt_usage_fraction",
                "account_id": "acct_hidden",
                "type": "usage_recorded",
                "timestamp": "2026-01-01T00:00:00Z",
                "usage": 1.5,
            },
        ),
    ]

    for case_id, raw_event in invalid_events:
        expected = normalize_event(raw_event)
        cases.append(
            {
                "id": case_id,
                "category": "parse_validation",
                "operation": "normalize_event",
                "match": "normalize_error",
                "languages": ["typescript", "python"],
                "points": 1,
                "input": {"raw_event": raw_event},
                "expected": {
                    "ok": False,
                    "error": expected["error"],
                    "issues": expected["issues"],
                },
            }
        )

    return cases


def normalization_cases() -> list[dict[str, Any]]:
    raw_events = [
        {
            "id": " evt_money_offset ",
            "account_id": " acct_norm ",
            "type": "payment_succeeded",
            "timestamp": "2026-02-03T04:05:06-05:00",
            "amount": "001.05",
        },
        {
            "id": "evt_coupon_case",
            "account_id": "acct_norm",
            "type": "coupon_applied",
            "timestamp": "2026-05-01T23:59:59+02:00",
            "coupon": " welcome50 ",
            "expires_at": "2026-06-01T00:00:00+02:00",
        },
        {
            "id": "evt_usage_zero",
            "account_id": "acct_norm",
            "type": "usage_recorded",
            "timestamp": "2026-03-01T00:00:00.123Z",
            "usage": 0,
        },
        {
            "id": "evt_plan_trim",
            "account_id": "acct_norm",
            "type": "account_opened",
            "timestamp": "2026-04-01T00:00:00Z",
            "plan": " enterprise ",
        },
        {
            "id": "evt_pay_zero",
            "account_id": "acct_norm",
            "type": "payment_succeeded",
            "timestamp": "2026-04-02T00:00:00Z",
            "amount": "0.00",
        },
    ]

    return [
        {
            "id": f"normalization.{index + 1}",
            "category": "normalization",
            "operation": "normalize_event",
            "languages": ["typescript", "python"],
            "points": 1,
            "input": {"raw_event": raw_event},
            "expected": normalize_event(raw_event),
        }
        for index, raw_event in enumerate(raw_events)
    ]


def state_reduction_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    summary_fixtures = [
        (
            "state.sort-dedupe",
            "2026-01-05T00:00:00.000Z",
            [
                event("evt_open_late", "acct_sort", "account_opened", "2026-01-02T00:00:00Z", plan="pro"),
                event("evt_pay", "acct_sort", "payment_succeeded", "2026-01-03T00:00:00Z", amount="20.00"),
                event("evt_open_early", "acct_sort", "account_opened", "2026-01-01T00:00:00Z", plan="starter"),
                event("evt_pay", "acct_sort", "payment_succeeded", "2026-01-04T00:00:00Z", amount="999.00"),
            ],
        ),
        (
            "state.coupon-boundary-inclusive",
            "2026-06-01T00:00:00.000Z",
            [
                event("evt_open_coupon", "acct_coupon", "account_opened", "2026-05-01T00:00:00Z", plan="starter"),
                event(
                    "evt_coupon",
                    "acct_coupon",
                    "coupon_applied",
                    "2026-05-02T00:00:00Z",
                    coupon="save10",
                    expires_at="2026-06-01T00:00:00Z",
                ),
            ],
        ),
        (
            "state.coupon-expired",
            "2026-06-01T00:00:00.001Z",
            [
                event("evt_open_coupon_exp", "acct_coupon_exp", "account_opened", "2026-05-01T00:00:00Z", plan="starter"),
                event(
                    "evt_coupon_exp",
                    "acct_coupon_exp",
                    "coupon_applied",
                    "2026-05-02T00:00:00Z",
                    coupon="save10",
                    expires_at="2026-06-01T00:00:00Z",
                ),
            ],
        ),
        (
            "state.closed-entitlements",
            "2026-07-01T00:00:00.000Z",
            [
                event("evt_open_closed", "acct_closed", "account_opened", "2026-05-01T00:00:00Z", plan="enterprise"),
                event(
                    "evt_coupon_closed",
                    "acct_closed",
                    "coupon_applied",
                    "2026-05-02T00:00:00Z",
                    coupon="welcome50",
                    expires_at="2026-12-31T00:00:00Z",
                ),
                event("evt_usage_closed", "acct_closed", "usage_recorded", "2026-05-03T00:00:00Z", usage=25),
                event("evt_close", "acct_closed", "account_closed", "2026-05-04T00:00:00Z"),
            ],
        ),
        (
            "state.closed-precedence",
            "2026-07-01T00:00:00.000Z",
            [
                event("evt_open_precedence", "acct_closed_precedence", "account_opened", "2026-05-01T00:00:00Z", plan="starter"),
                event("evt_close_precedence", "acct_closed_precedence", "account_closed", "2026-05-02T00:00:00Z"),
                event("evt_plan_after_close", "acct_closed_precedence", "plan_changed", "2026-05-03T00:00:00Z", plan="enterprise"),
                event("evt_payment_after_close", "acct_closed_precedence", "payment_succeeded", "2026-05-04T00:00:00Z", amount="199.00"),
                event("evt_usage_after_close", "acct_closed_precedence", "usage_recorded", "2026-05-05T00:00:00Z", usage=999),
            ],
        ),
        (
            "state.usage-over-limit",
            "2026-08-01T00:00:00.000Z",
            [
                event("evt_open_usage", "acct_usage", "account_opened", "2026-05-01T00:00:00Z", plan="free"),
                event("evt_usage_1", "acct_usage", "usage_recorded", "2026-05-02T00:00:00Z", usage=60),
                event("evt_usage_2", "acct_usage", "usage_recorded", "2026-05-03T00:00:00Z", usage=41),
            ],
        ),
        (
            "state.payment-recovery",
            "2026-09-01T00:00:00.000Z",
            [
                event("evt_open_recover", "acct_recover", "account_opened", "2026-05-01T00:00:00Z", plan="starter"),
                event("evt_fail_recover", "acct_recover", "payment_failed", "2026-05-02T00:00:00Z"),
                event("evt_pay_recover", "acct_recover", "payment_succeeded", "2026-05-03T00:00:00Z", amount="12.00"),
            ],
        ),
    ]

    for case_id, as_of, raw_events in summary_fixtures:
        cases.append(
            {
                "id": case_id,
                "category": "state_reduction",
                "operation": "reduce_and_summarize",
                "languages": ["typescript", "python"],
                "points": 2,
                "input": {"raw_events": raw_events, "as_of": as_of},
                "expected": summarize_raw_events(raw_events, as_of),
            }
        )

    grace_events = [
        event("evt_open_grace", "acct_grace", "account_opened", "2026-04-01T00:00:00Z", plan="pro"),
        event("evt_failed_grace", "acct_grace", "payment_failed", "2026-04-10T00:00:00Z"),
    ]
    for case_id, as_of in [
        ("state.failed-payment-grace-inclusive", "2026-04-17T00:00:00.000Z"),
        ("state.failed-payment-grace-expired", "2026-04-17T00:00:00.001Z"),
    ]:
        cases.append(
            {
                "id": case_id,
                "category": "state_reduction",
                "operation": "reduce_and_evaluate",
                "languages": ["typescript", "python"],
                "points": 2,
                "input": {
                    "raw_events": grace_events,
                    "account_id": "acct_grace",
                    "as_of": as_of,
                },
                "expected": evaluate_raw_events(grace_events, "acct_grace", as_of),
            }
        )

    return cases


def reporting_cases() -> list[dict[str, Any]]:
    summaries = [
        {
            "accountId": "acct_z",
            "status": "active",
            "plan": "pro",
            "features": ["dashboard", "exports", "priority_support", "rules"],
            "usage": 10000,
            "usageLimit": 10000,
            "overLimit": False,
            "totalPaidCents": 4900,
            "couponCode": None,
            "couponActive": False,
            "closedAt": None,
            "lastEventAt": "2026-03-01T00:00:00.000Z",
        },
        {
            "accountId": "acct_a",
            "status": "closed",
            "plan": "enterprise",
            "features": [],
            "usage": 1,
            "usageLimit": 0,
            "overLimit": True,
            "totalPaidCents": 19900,
            "couponCode": "WELCOME50",
            "couponActive": False,
            "closedAt": "2026-04-01T00:00:00.000Z",
            "lastEventAt": "2026-04-01T00:00:00.000Z",
        },
        {
            "accountId": "acct_m",
            "status": "past_due",
            "plan": "starter",
            "features": ["dashboard", "exports"],
            "usage": 1001,
            "usageLimit": 1000,
            "overLimit": True,
            "totalPaidCents": 1200,
            "couponCode": "SAVE10",
            "couponActive": True,
            "closedAt": None,
            "lastEventAt": "2026-03-15T00:00:00.000Z",
        },
    ]

    return [
        {
            "id": "report.csv-stable-format",
            "category": "reporting",
            "operation": "export_report",
            "languages": ["typescript", "python"],
            "points": 2,
            "input": {"summaries": summaries},
            "expected": export_ledger_report(summaries),
        }
    ]


def immutability_cases() -> list[dict[str, Any]]:
    raw_events = [
        event("evt_open_immut", "acct_immut", "account_opened", "2026-10-01T00:00:00Z", plan="starter"),
        event("evt_usage_immut", "acct_immut", "usage_recorded", "2026-10-02T00:00:00Z", usage=10),
        event("evt_coupon_immut", "acct_immut", "coupon_applied", "2026-10-03T00:00:00Z", coupon="save10", expires_at="2026-12-01T00:00:00Z"),
    ]
    as_of = "2026-11-01T00:00:00.000Z"

    return [
        {
            "id": "immutability.repeatable-pipeline",
            "category": "immutability",
            "operation": "immutability_repeatability",
            "languages": ["typescript", "python"],
            "points": 1,
            "input": {"raw_events": raw_events, "as_of": as_of},
            "expected": {
                "summaries": summarize_raw_events(raw_events, as_of),
                "repeatable": True,
                "inputUnchanged": True,
            },
        }
    ]


def parity_cases() -> list[dict[str, Any]]:
    return [
        {
            "id": "parity.shared-complex-fixture",
            "category": "parity",
            "operation": "reduce_and_summarize",
            "languages": ["parity"],
            "points": 3,
            "input": {
                "raw_events": [
                    event("evt_open_p1", "acct_parity_a", "account_opened", "2026-01-01T00:00:00Z", plan="starter"),
                    event("evt_coupon_p1", "acct_parity_a", "coupon_applied", "2026-01-02T00:00:00Z", coupon="save10", expires_at="2026-03-01T00:00:00Z"),
                    event("evt_usage_p1", "acct_parity_a", "usage_recorded", "2026-01-03T00:00:00Z", usage=50),
                    event("evt_open_p2", "acct_parity_b", "account_opened", "2026-01-01T00:00:00Z", plan="free"),
                    event("evt_fail_p2", "acct_parity_b", "payment_failed", "2026-01-04T00:00:00Z"),
                ],
                "as_of": "2026-02-01T00:00:00.000Z",
            },
        }
    ]


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


def write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
