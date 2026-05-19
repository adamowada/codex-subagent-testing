"""Starter implementation for the RuleLedger benchmark.

Measured agents should complete this module so it matches the TypeScript
implementation in src/index.ts.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any


PLAN_DEFINITIONS: dict[str, dict[str, Any]] = {
    "free": {
        "price_cents": 0,
        "features": ["dashboard"],
        "usage_limit": 100,
    },
    "starter": {
        "price_cents": 1200,
        "features": ["dashboard", "exports"],
        "usage_limit": 1000,
    },
    "pro": {
        "price_cents": 4900,
        "features": ["dashboard", "exports", "priority_support", "rules"],
        "usage_limit": 10000,
    },
    "enterprise": {
        "price_cents": 19900,
        "features": ["audit_log", "dashboard", "exports", "priority_support", "rules", "sso"],
        "usage_limit": 100000,
    },
}

COUPON_DEFINITIONS: dict[str, dict[str, int]] = {
    "SAVE10": {"discount_percent": 10},
    "WELCOME50": {"discount_percent": 50},
}

EVENT_TYPES = {
    "account_opened",
    "plan_changed",
    "payment_succeeded",
    "payment_failed",
    "coupon_applied",
    "usage_recorded",
    "account_closed",
}

PLAN_NAMES = set(PLAN_DEFINITIONS)


def parse_event_line(line: str) -> dict[str, Any]:
    if line.strip() == "":
        return {"ok": False, "error": "empty_line", "line": line}

    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid_json", "line": line}

    if not isinstance(parsed, dict):
        return {"ok": False, "error": "non_object_json", "line": line}

    return {"ok": True, "value": parsed}


def normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    event_id = _read_required_string(raw, "id", issues)
    account_id = _read_required_string(raw, "account_id", issues)
    raw_type = _read_required_string(raw, "type", issues)
    raw_timestamp = _read_required_string(raw, "timestamp", issues)

    event_type = "account_opened"
    if raw_type is not None:
        if raw_type in EVENT_TYPES:
            event_type = raw_type
        else:
            issues.append("invalid_type")

    timestamp = _normalize_timestamp(raw_timestamp, issues, "timestamp")
    normalized: dict[str, Any] = {
        "id": event_id or "",
        "accountId": account_id or "",
        "type": event_type,
        "timestamp": timestamp or "",
    }

    plan = raw.get("plan")
    if isinstance(plan, str):
        plan = plan.strip()
        if plan in PLAN_NAMES:
            normalized["plan"] = plan
        else:
            issues.append("invalid_plan")

    if "amount" in raw:
        amount_cents = _parse_money_to_cents(raw.get("amount"))
        if amount_cents is None:
            issues.append("invalid_amount")
        else:
            normalized["amountCents"] = amount_cents

    coupon = raw.get("coupon")
    if isinstance(coupon, str) and coupon.strip():
        normalized["couponCode"] = coupon.strip().upper()

    expires_at = raw.get("expires_at")
    if isinstance(expires_at, str) and expires_at.strip():
        normalized["couponExpiresAt"] = _normalize_timestamp(
            expires_at,
            issues,
            "invalid_coupon_expiration",
        )

    if "usage" in raw:
        usage = raw.get("usage")
        if isinstance(usage, int) and usage >= 0:
            normalized["usage"] = usage
        else:
            issues.append("invalid_usage")

    if issues:
        return {"ok": False, "error": "invalid_event", "issues": issues, "raw": raw}

    return {"ok": True, "value": normalized}


def reduce_account_state(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}

    for event in events:
        state = _get_or_create_state(states, event["accountId"])

        if event["type"] in {"account_opened", "plan_changed"}:
            state["plan"] = event.get("plan", state["plan"])
            if state["status"] != "closed":
                state["status"] = "active"

        if event["type"] == "payment_succeeded":
            state["totalPaidCents"] += event.get("amountCents", 0)
            if state["status"] != "closed":
                state["status"] = "active"

        if event["type"] == "payment_failed":
            state["failedPayments"] += 1
            if state["status"] != "closed":
                state["status"] = "past_due"

        if event["type"] == "usage_recorded":
            state["usage"] += event.get("usage", 0)

        if event["type"] == "account_closed":
            state["status"] = "closed"
            state["closedAt"] = event["timestamp"]

        state["lastEventAt"] = event["timestamp"]

    return sorted(states.values(), key=lambda state: state["accountId"])


def evaluate_entitlements(state: dict[str, Any], as_of: str | None = None) -> dict[str, Any]:
    plan = PLAN_DEFINITIONS[state["plan"]]
    coupon_active = (
        state["couponCode"] is not None
        and state["couponExpiresAt"] is not None
        and (as_of is None or state["couponExpiresAt"] >= as_of)
    )

    if state["status"] == "closed":
        return {
            "active": False,
            "features": [],
            "usageLimit": 0,
            "overLimit": state["usage"] > 0,
            "couponActive": coupon_active,
        }

    return {
        "active": state["status"] == "active",
        "features": list(plan["features"]),
        "usageLimit": plan["usage_limit"],
        "overLimit": state["usage"] > plan["usage_limit"],
        "couponActive": coupon_active,
    }


def summarize_account(state: dict[str, Any], as_of: str | None = None) -> dict[str, Any]:
    entitlements = evaluate_entitlements(state, as_of)
    return {
        "accountId": state["accountId"],
        "status": state["status"],
        "plan": state["plan"],
        "features": entitlements["features"],
        "usage": state["usage"],
        "usageLimit": entitlements["usageLimit"],
        "overLimit": entitlements["overLimit"],
        "totalPaidCents": state["totalPaidCents"],
        "couponCode": state["couponCode"],
        "couponActive": entitlements["couponActive"],
        "closedAt": state["closedAt"],
        "lastEventAt": state["lastEventAt"],
    }


def export_ledger_report(summaries: list[dict[str, Any]]) -> str:
    header = [
        "account_id",
        "status",
        "plan",
        "total_paid_cents",
        "usage",
        "usage_limit",
        "over_limit",
        "coupon_code",
        "coupon_active",
        "closed_at",
        "last_event_at",
    ]
    rows = [header]

    for summary in sorted(summaries, key=lambda row: row["accountId"]):
        rows.append(
            [
                summary["accountId"],
                summary["status"],
                summary["plan"],
                str(summary["totalPaidCents"]),
                str(summary["usage"]),
                str(summary["usageLimit"]),
                str(summary["overLimit"]).lower(),
                summary["couponCode"] or "",
                str(summary["couponActive"]).lower(),
                summary["closedAt"] or "",
                summary["lastEventAt"] or "",
            ]
        )

    return "\n".join(",".join(row) for row in rows) + "\n"


def _read_required_string(raw: dict[str, Any], field: str, issues: list[str]) -> str | None:
    value = raw.get(field)
    if not isinstance(value, str):
        issues.append(f"missing_{field}")
        return None

    trimmed = value.strip()
    if trimmed == "":
        issues.append(f"blank_{field}")
        return None

    return trimmed


def _normalize_timestamp(value: str | None, issues: list[str], issue_code: str) -> str | None:
    if value is None:
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        issues.append(issue_code)
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_money_to_cents(value: Any) -> int | None:
    if not isinstance(value, str):
        return None

    trimmed = value.strip()
    if re.fullmatch(r"\d+\.\d{2}", trimmed) is None:
        return None

    dollars, cents = trimmed.split(".")
    return int(dollars) * 100 + int(cents)


def _get_or_create_state(states: dict[str, dict[str, Any]], account_id: str) -> dict[str, Any]:
    if account_id in states:
        return states[account_id]

    state = {
        "accountId": account_id,
        "status": "active",
        "plan": "free",
        "totalPaidCents": 0,
        "failedPayments": 0,
        "usage": 0,
        "couponCode": None,
        "couponExpiresAt": None,
        "closedAt": None,
        "lastEventAt": None,
    }
    states[account_id] = state
    return state
