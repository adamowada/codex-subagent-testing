from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any


SEED = 20260519
GRACE_PERIOD_DAYS = 7

PLAN_DEFINITIONS: dict[str, dict[str, Any]] = {
    "free": {
        "priceCents": 0,
        "features": ["dashboard"],
        "usageLimit": 100,
    },
    "starter": {
        "priceCents": 1200,
        "features": ["dashboard", "exports"],
        "usageLimit": 1000,
    },
    "pro": {
        "priceCents": 4900,
        "features": ["dashboard", "exports", "priority_support", "rules"],
        "usageLimit": 10000,
    },
    "enterprise": {
        "priceCents": 19900,
        "features": ["audit_log", "dashboard", "exports", "priority_support", "rules", "sso"],
        "usageLimit": 100000,
    },
}

COUPON_DEFINITIONS: dict[str, dict[str, int]] = {
    "SAVE10": {"discountPercent": 10},
    "WELCOME50": {"discountPercent": 50},
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

    if isinstance(raw.get("plan"), str):
        plan = raw["plan"].strip()
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

    if isinstance(raw.get("coupon"), str) and raw["coupon"].strip():
        normalized["couponCode"] = raw["coupon"].strip().upper()

    if isinstance(raw.get("expires_at"), str) and raw["expires_at"].strip():
        normalized["couponExpiresAt"] = _normalize_timestamp(
            raw["expires_at"],
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
    seen_event_ids: set[str] = set()

    for event in sorted(events, key=lambda item: (item["timestamp"], item["id"])):
        if event["id"] in seen_event_ids:
            continue
        seen_event_ids.add(event["id"])

        state = _get_or_create_state(states, event["accountId"])

        if state["status"] == "closed":
            state["lastEventAt"] = event["timestamp"]
            continue

        if event["type"] in {"account_opened", "plan_changed"}:
            state["plan"] = event.get("plan", state["plan"])
            state["status"] = "active"

        if event["type"] == "payment_succeeded":
            state["totalPaidCents"] += event.get("amountCents", 0)
            state["failedPayments"] = 0
            state["status"] = "active"
            state["lastFailedPaymentAt"] = None

        if event["type"] == "payment_failed":
            state["failedPayments"] += 1
            state["status"] = "past_due"
            state["lastFailedPaymentAt"] = event["timestamp"]

        if event["type"] == "coupon_applied":
            state["couponCode"] = event.get("couponCode", state["couponCode"])
            state["couponExpiresAt"] = event.get("couponExpiresAt", state["couponExpiresAt"])

        if event["type"] == "usage_recorded":
            state["usage"] += event.get("usage", 0)

        if event["type"] == "account_closed":
            state["status"] = "closed"
            state["closedAt"] = event["timestamp"]

        state["lastEventAt"] = event["timestamp"]

    return sorted(states.values(), key=lambda state: state["accountId"])


def evaluate_entitlements(state: dict[str, Any], as_of: str | None = None) -> dict[str, Any]:
    plan = PLAN_DEFINITIONS[state["plan"]]
    coupon_active = _coupon_active(state, as_of)

    if state["status"] == "closed":
        return {
            "active": False,
            "features": [],
            "usageLimit": 0,
            "overLimit": state["usage"] > 0,
            "couponActive": False,
        }

    active = state["status"] == "active"
    if state["status"] == "past_due":
        active = _within_grace_period(state, as_of)

    return {
        "active": active,
        "features": list(plan["features"]),
        "usageLimit": plan["usageLimit"],
        "overLimit": state["usage"] > plan["usageLimit"],
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
    rows = [
        [
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
    ]

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


def normalize_many(raw_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for raw_event in raw_events:
        result = normalize_event(raw_event)
        if not result["ok"]:
            raise ValueError(f"invalid oracle fixture: {result}")
        normalized.append(result["value"])
    return normalized


def summarize_raw_events(raw_events: list[dict[str, Any]], as_of: str | None = None) -> list[dict[str, Any]]:
    return [summarize_account(state, as_of) for state in reduce_account_state(normalize_many(raw_events))]


def evaluate_raw_events(
    raw_events: list[dict[str, Any]],
    account_id: str,
    as_of: str | None = None,
) -> dict[str, Any]:
    states = reduce_account_state(normalize_many(raw_events))
    for state in states:
        if state["accountId"] == account_id:
            return evaluate_entitlements(state, as_of)
    raise ValueError(f"missing account in oracle fixture: {account_id}")


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
        "lastFailedPaymentAt": None,
    }
    states[account_id] = state
    return state


def _coupon_active(state: dict[str, Any], as_of: str | None) -> bool:
    if state["couponCode"] is None or state["couponExpiresAt"] is None:
        return False
    if as_of is None:
        return True
    return state["couponExpiresAt"] >= as_of


def _within_grace_period(state: dict[str, Any], as_of: str | None) -> bool:
    failed_at = state.get("lastFailedPaymentAt") or state.get("lastEventAt")
    if failed_at is None or as_of is None:
        return False

    failed_dt = datetime.fromisoformat(failed_at.replace("Z", "+00:00"))
    as_of_dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    return as_of_dt <= failed_dt + timedelta(days=GRACE_PERIOD_DAYS)
