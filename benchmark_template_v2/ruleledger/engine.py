"""Starter implementation for the RuleLedger v2 benchmark.

Measured agents should complete this module so it matches the TypeScript
implementation in src/index.ts.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
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
    "trial_started",
    "trial_ended",
    "plan_changed",
    "account_paused",
    "account_resumed",
    "account_cancelled",
    "account_reactivated",
    "payment_succeeded",
    "payment_failed",
    "payment_recovered",
    "coupon_applied",
    "usage_recorded",
    "account_closed",
    "invoice_issued",
    "account_merged",
    "event_corrected",
    "event_voided",
    "seat_delta_recorded",
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

    timestamp = _normalize_timestamp(raw_timestamp, issues, "invalid_timestamp")
    effective_at = _normalize_optional_timestamp(raw, "effective_at", issues, "invalid_effective_at") or timestamp
    recorded_at = _normalize_optional_timestamp(raw, "recorded_at", issues, "invalid_recorded_at") or timestamp
    sequence = _read_optional_integer(raw, "sequence", issues, "invalid_sequence", minimum=0, default=0)

    normalized: dict[str, Any] = {
        "id": event_id or "",
        "accountId": account_id or "",
        "type": event_type,
        "timestamp": timestamp or "",
        "effectiveAt": effective_at or "",
        "recordedAt": recorded_at or "",
        "sequence": sequence,
    }

    plan = raw.get("plan")
    if isinstance(plan, str):
        plan = plan.strip()
        if plan in PLAN_NAMES:
            normalized["plan"] = plan
        else:
            issues.append("invalid_plan")

    if "amount_cents" in raw:
        amount_cents = _read_integer_value(raw.get("amount_cents"))
        if amount_cents is None:
            issues.append("invalid_amount_cents")
        else:
            normalized["amountCents"] = amount_cents
    elif "amount" in raw:
        amount_cents = _parse_money_to_cents(raw.get("amount"))
        if amount_cents is None:
            issues.append("invalid_amount")
        else:
            normalized["amountCents"] = amount_cents

    currency = _normalize_currency(raw.get("currency")) if "currency" in raw else None
    if "currency" in raw and currency is None:
        issues.append("invalid_currency")
    elif currency is not None:
        normalized["currency"] = currency

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
        usage = _read_integer_value(raw.get("usage"), minimum=0)
        if usage is None:
            issues.append("invalid_usage")
        else:
            normalized["usage"] = usage

    quantity = _read_optional_integer(raw, "quantity", issues, "invalid_quantity", minimum=0)
    if quantity is not None:
        normalized["quantity"] = quantity

    seat_delta = _read_optional_integer(raw, "seat_delta", issues, "invalid_seat_delta")
    if seat_delta is not None:
        normalized["seatDelta"] = seat_delta

    _copy_optional_id(raw, normalized, "merge_from_account_id", "mergeFromAccountId", issues)
    _copy_optional_id(raw, normalized, "correction_of", "correctionOf", issues)
    _copy_optional_id(raw, normalized, "voided_event_id", "voidedEventId", issues)
    _copy_optional_id(raw, normalized, "invoice_id", "invoiceId", issues)
    _copy_optional_timestamp(raw, normalized, "period_start", "periodStart", issues, "invalid_period_start")
    _copy_optional_timestamp(raw, normalized, "period_end", "periodEnd", issues, "invalid_period_end")

    if issues:
        return {"ok": False, "error": "invalid_event", "issues": issues, "raw": raw}

    return {"ok": True, "value": normalized}


def reduce_account_state(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    seen_event_ids: set[str] = set()

    for event in sorted(events, key=_replay_sort_key):
        if event["id"] in seen_event_ids:
            continue
        seen_event_ids.add(event["id"])

        state = _get_or_create_state(states, event["accountId"])

        if event["type"] == "account_opened":
            state["plan"] = event.get("plan", state["plan"])
            if state["status"] != "closed":
                state["status"] = "active"

        if event["type"] == "trial_started" and state["status"] != "closed":
            state["status"] = "trialing"

        if event["type"] == "trial_ended" and state["status"] == "trialing":
            state["status"] = "active"

        if event["type"] == "plan_changed":
            state["plan"] = event.get("plan", state["plan"])
            if state["status"] == "pending":
                state["status"] = "active"

        if event["type"] == "account_paused" and state["status"] != "closed":
            state["status"] = "paused"

        if event["type"] == "account_resumed" and state["status"] == "paused":
            state["status"] = "active"

        if event["type"] == "account_cancelled" and state["status"] != "closed":
            state["status"] = "cancelled"

        if event["type"] == "account_reactivated" and state["status"] == "cancelled":
            state["status"] = "active"

        if event["type"] in {"payment_succeeded", "payment_recovered"}:
            state["totalPaidCents"] += event.get("amountCents", 0)
            if state["status"] == "past_due":
                state["status"] = "active"

        if event["type"] == "payment_failed":
            state["failedPayments"] += 1
            if state["status"] in {"active", "trialing"}:
                state["status"] = "past_due"

        if event["type"] == "coupon_applied":
            state["couponCode"] = event.get("couponCode", state["couponCode"])
            state["couponExpiresAt"] = event.get("couponExpiresAt", state["couponExpiresAt"])

        if event["type"] == "usage_recorded":
            state["usage"] += event.get("usage", event.get("quantity", 0))

        if event["type"] == "account_closed":
            state["status"] = "closed"
            state["closedAt"] = event["effectiveAt"]

        if "seatDelta" in event:
            state["seats"] = max(0, state["seats"] + event["seatDelta"])
        elif event["type"] == "account_opened" and "quantity" in event:
            state["seats"] = max(1, event["quantity"])

        if "currency" in event:
            state["currency"] = event["currency"]

        if "invoiceId" in event:
            _add_unique(state["invoiceIds"], event["invoiceId"])
            state["lastInvoiceId"] = event["invoiceId"]
        if "periodStart" in event:
            state["lastPeriodStart"] = event["periodStart"]
        if "periodEnd" in event:
            state["lastPeriodEnd"] = event["periodEnd"]
        if "mergeFromAccountId" in event:
            _add_unique(state["mergedFromAccountIds"], event["mergeFromAccountId"])

        state["lastEventAt"] = event["effectiveAt"]

    return sorted(states.values(), key=lambda state: state["accountId"])


def evaluate_entitlements(state: dict[str, Any], as_of: str | None = None) -> dict[str, Any]:
    plan = PLAN_DEFINITIONS[state["plan"]]
    coupon_active = (
        state["status"] != "closed"
        and state["couponCode"] is not None
        and state["couponExpiresAt"] is not None
        and (as_of is None or state["couponExpiresAt"] >= as_of)
    )

    if state["status"] == "closed":
        return {
            "active": False,
            "features": [],
            "usageLimit": 0,
            "overLimit": state["usage"] > 0,
            "couponActive": False,
        }

    return {
        "active": state["status"] in {"active", "trialing", "past_due"},
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
        "currency": state["currency"],
        "seats": state["seats"],
        "couponCode": state["couponCode"],
        "couponActive": entitlements["couponActive"],
        "invoiceIds": list(state["invoiceIds"]),
        "lastInvoiceId": state["lastInvoiceId"],
        "lastPeriodStart": state["lastPeriodStart"],
        "lastPeriodEnd": state["lastPeriodEnd"],
        "mergedFromAccountIds": list(state["mergedFromAccountIds"]),
        "closedAt": state["closedAt"],
        "lastEventAt": state["lastEventAt"],
    }


def export_ledger_report(summaries: list[dict[str, Any]]) -> str:
    header = [
        "account_id",
        "status",
        "plan",
        "total_paid_cents",
        "currency",
        "seats",
        "usage",
        "usage_limit",
        "over_limit",
        "coupon_code",
        "coupon_active",
        "invoice_ids",
        "last_invoice_id",
        "last_period_start",
        "last_period_end",
        "merged_from_account_ids",
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
                summary["currency"] or "",
                str(summary["seats"]),
                str(summary["usage"]),
                str(summary["usageLimit"]),
                str(summary["overLimit"]).lower(),
                summary["couponCode"] or "",
                str(summary["couponActive"]).lower(),
                "|".join(summary["invoiceIds"]),
                summary["lastInvoiceId"] or "",
                summary["lastPeriodStart"] or "",
                summary["lastPeriodEnd"] or "",
                "|".join(summary["mergedFromAccountIds"]),
                summary["closedAt"] or "",
                summary["lastEventAt"] or "",
            ]
        )

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(rows)
    return output.getvalue()


def normalize_event_v2(raw: dict[str, Any]) -> dict[str, Any]:
    return normalize_event(raw)


def reduce_account_state_v2(events: list[dict[str, Any]], view: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return reduce_account_state(_filter_events_for_view(events, view))


def evaluate_entitlements_v2(state: dict[str, Any], view: dict[str, Any] | None = None) -> dict[str, Any]:
    return evaluate_entitlements(state, _view_cutoff(view))


def summarize_account_v2(state: dict[str, Any], view: dict[str, Any] | None = None) -> dict[str, Any]:
    return summarize_account(state, _view_cutoff(view))


def export_ledger_report_v2(summaries: list[dict[str, Any]]) -> str:
    return export_ledger_report(summaries)


def calculate_plan_change_proration_v2(input_payload: dict[str, Any]) -> dict[str, Any]:
    quantity = input_payload.get("quantity", 1)
    period_start = _normalize_required_timestamp(input_payload["period_start"])
    period_end = _normalize_required_timestamp(input_payload["period_end"])
    change_effective_at = _normalize_required_timestamp(input_payload["change_effective_at"])
    start_ms = _timestamp_ms(period_start)
    end_ms = _timestamp_ms(period_end)
    change_ms = _timestamp_ms(change_effective_at)
    if end_ms <= start_ms or change_ms < start_ms or change_ms > end_ms:
        raise ValueError("invalid_proration_input")
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 0:
        raise ValueError("invalid_proration_input")

    period_ms = end_ms - start_ms
    remaining_ms = end_ms - change_ms
    old_full = PLAN_DEFINITIONS[input_payload["old_plan"]]["price_cents"]
    new_full = PLAN_DEFINITIONS[input_payload["new_plan"]]["price_cents"]
    old_credit = -_round_half_away_from_zero(old_full * quantity * remaining_ms, period_ms)
    new_charge = _round_half_away_from_zero(new_full * quantity * remaining_ms, period_ms)
    return {
        "oldPlan": input_payload["old_plan"],
        "newPlan": input_payload["new_plan"],
        "quantity": quantity,
        "periodStart": period_start,
        "periodEnd": period_end,
        "changeEffectiveAt": change_effective_at,
        "oldCreditCents": old_credit,
        "newChargeCents": new_charge,
        "netAdjustmentCents": old_credit + new_charge,
    }


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


def _read_optional_string(raw: dict[str, Any], field: str, issues: list[str]) -> str | None:
    if field not in raw:
        return None
    value = raw.get(field)
    if not isinstance(value, str):
        issues.append(f"invalid_{field}")
        return None
    trimmed = value.strip()
    if trimmed == "":
        issues.append(f"blank_{field}")
        return None
    return trimmed


def _normalize_timestamp(value: str | None, issues: list[str], issue_code: str) -> str | None:
    if value is None:
        return None

    candidate = value.strip()
    if _has_timezone(candidate):
        candidate = candidate.replace("Z", "+00:00").replace("z", "+00:00")
    else:
        candidate = f"{candidate}+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        issues.append(issue_code)
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _normalize_optional_timestamp(
    raw: dict[str, Any],
    field: str,
    issues: list[str],
    issue_code: str,
) -> str | None:
    if field not in raw:
        return None
    value = _read_optional_string(raw, field, issues)
    if value is None:
        return None
    return _normalize_timestamp(value, issues, issue_code)


def _copy_optional_timestamp(
    raw: dict[str, Any],
    normalized: dict[str, Any],
    raw_field: str,
    normalized_field: str,
    issues: list[str],
    issue_code: str,
) -> None:
    value = _normalize_optional_timestamp(raw, raw_field, issues, issue_code)
    if value is not None:
        normalized[normalized_field] = value


def _read_optional_integer(
    raw: dict[str, Any],
    field: str,
    issues: list[str],
    issue_code: str,
    *,
    minimum: int | None = None,
    default: int | None = None,
) -> int | None:
    if field not in raw:
        return default
    value = _read_integer_value(raw.get(field), minimum=minimum)
    if value is None:
        issues.append(issue_code)
        return default
    return value


def _read_integer_value(value: Any, *, minimum: int | None = None) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    if minimum is not None and value < minimum:
        return None
    return value


def _parse_money_to_cents(value: Any) -> int | None:
    if not isinstance(value, str):
        return None

    trimmed = value.strip()
    if re.fullmatch(r"-?\d+\.\d{2}", trimmed) is None:
        return None

    dollars, cents = trimmed.split(".")
    sign = -1 if dollars.startswith("-") else 1
    return int(dollars) * 100 + sign * int(cents)


def _normalize_currency(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip().upper()
    if re.fullmatch(r"[A-Z]{3}", trimmed) is None:
        return None
    return trimmed


def _copy_optional_id(
    raw: dict[str, Any],
    normalized: dict[str, Any],
    raw_field: str,
    normalized_field: str,
    issues: list[str],
) -> None:
    value = _read_optional_string(raw, raw_field, issues)
    if value is not None:
        normalized[normalized_field] = value


def _replay_sort_key(event: dict[str, Any]) -> tuple[str, str, int, str]:
    return (
        event["effectiveAt"],
        event["recordedAt"],
        event["sequence"],
        event["id"],
    )


def _add_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _filter_events_for_view(events: list[dict[str, Any]], view: dict[str, Any] | None) -> list[dict[str, Any]]:
    if view is None:
        return events
    business_as_of = view.get("businessAsOf") or view.get("business_as_of") or view.get("asOf") or view.get("as_of")
    audit_as_of = view.get("auditAsOf") or view.get("audit_as_of") or view.get("asOf") or view.get("as_of")
    filtered = []
    for event in events:
        if audit_as_of is not None and event["recordedAt"] > audit_as_of:
            continue
        if business_as_of is not None and event["effectiveAt"] > business_as_of:
            continue
        filtered.append(event)
    return filtered


def _view_cutoff(view: dict[str, Any] | None) -> str | None:
    if view is None:
        return None
    return view.get("businessAsOf") or view.get("business_as_of") or view.get("asOf") or view.get("as_of")


def _normalize_required_timestamp(value: str) -> str:
    issues: list[str] = []
    normalized = _normalize_timestamp(value, issues, "invalid_timestamp")
    if normalized is None or issues:
        raise ValueError("invalid_timestamp")
    return normalized


def _timestamp_ms(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return int(parsed.timestamp() * 1000)


def _round_half_away_from_zero(numerator: int, denominator: int) -> int:
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return sign * quotient


def _has_timezone(value: str) -> bool:
    return re.search(r"(?:Z|z|[+-]\d{2}:\d{2})$", value) is not None


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
        "currency": None,
        "seats": 1,
        "couponCode": None,
        "couponExpiresAt": None,
        "invoiceIds": [],
        "lastInvoiceId": None,
        "lastPeriodStart": None,
        "lastPeriodEnd": None,
        "mergedFromAccountIds": [],
        "closedAt": None,
        "lastEventAt": None,
    }
    states[account_id] = state
    return state
