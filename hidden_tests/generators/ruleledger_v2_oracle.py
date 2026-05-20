from __future__ import annotations

from datetime import datetime, timezone
from fractions import Fraction
import csv
import hashlib
import io
import json
import re
from typing import Any

try:
    from ruleledger_v2_semantics import V2_CSV_HEADER, V2_SUMMARY_FIELDS
except ModuleNotFoundError:
    from hidden_tests.generators.ruleledger_v2_semantics import V2_CSV_HEADER, V2_SUMMARY_FIELDS


SEED = 20260520
GENERATED_AT = "2026-05-20T00:00:00.000Z"

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

EVENT_TYPES = {
    "account_opened",
    "trial_started",
    "trial_ended",
    "plan_changed",
    "account_paused",
    "account_resumed",
    "account_cancelled",
    "account_reactivated",
    "account_closed",
    "payment_succeeded",
    "payment_failed",
    "payment_recovered",
    "coupon_applied",
    "usage_recorded",
    "seat_delta_recorded",
    "invoice_issued",
    "account_merged",
    "event_corrected",
    "event_voided",
}

PLAN_NAMES = set(PLAN_DEFINITIONS)
CORRECTION_TYPES = {"event_corrected", "event_voided"}


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
    elif "plan" in raw and plan is not None:
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
    elif "coupon" in raw and coupon is not None:
        issues.append("invalid_coupon")

    expires_at = raw.get("expires_at")
    if isinstance(expires_at, str) and expires_at.strip():
        normalized["couponExpiresAt"] = _normalize_timestamp(
            expires_at,
            issues,
            "invalid_coupon_expiration",
        )
    elif "expires_at" in raw and expires_at is not None:
        issues.append("invalid_coupon_expiration")

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

    if normalized.get("periodStart") and normalized.get("periodEnd"):
        if normalized["periodEnd"] <= normalized["periodStart"]:
            issues.append("invalid_period_bounds")

    if issues:
        return {"ok": False, "error": "invalid_event", "issues": issues, "raw": raw}

    return {"ok": True, "value": normalized}


def normalize_many(raw_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw_event in raw_events:
        result = normalize_event(raw_event)
        if not result["ok"]:
            raise ValueError(f"invalid v2 oracle fixture: {result}")
        normalized.append(result["value"])
    return normalized


def summarize_raw_events(
    raw_events: list[dict[str, Any]],
    as_of: str | None = None,
    *,
    business_as_of: str | None = None,
    audit_as_of: str | None = None,
) -> list[dict[str, Any]]:
    return [
        summarize_account(state, business_as_of or as_of)
        for state in reduce_account_state(
            normalize_many(raw_events),
            as_of=as_of,
            business_as_of=business_as_of,
            audit_as_of=audit_as_of,
        )
    ]


def evaluate_raw_events(
    raw_events: list[dict[str, Any]],
    account_id: str,
    as_of: str | None = None,
    *,
    business_as_of: str | None = None,
    audit_as_of: str | None = None,
) -> dict[str, Any]:
    states = reduce_account_state(
        normalize_many(raw_events),
        as_of=as_of,
        business_as_of=business_as_of,
        audit_as_of=audit_as_of,
    )
    for state in states:
        if state["accountId"] == account_id:
            return evaluate_entitlements(state, business_as_of or as_of)
    raise ValueError(f"missing account in v2 oracle fixture: {account_id}")


def reduce_account_state(
    events: list[dict[str, Any]],
    as_of: str | None = None,
    *,
    business_as_of: str | None = None,
    audit_as_of: str | None = None,
) -> list[dict[str, Any]]:
    business_cutoff = _normalize_cutoff(business_as_of or as_of)
    audit_cutoff = _normalize_cutoff(audit_as_of or as_of)
    active_events = _active_events_for_view(events, business_cutoff, audit_cutoff)

    states: dict[str, dict[str, Any]] = {}
    aliases: dict[str, str] = {}

    for event in sorted(active_events, key=_replay_sort_key):
        if event["type"] == "account_merged":
            _apply_account_merge(states, aliases, event)
            continue

        account_id = _canonical_account(event["accountId"], aliases)
        event = {**event, "accountId": account_id}
        state = _get_or_create_state(states, account_id)
        _apply_event(state, event)

    return sorted(states.values(), key=lambda state: state["accountId"])


def evaluate_entitlements(state: dict[str, Any], as_of: str | None = None) -> dict[str, Any]:
    plan = PLAN_DEFINITIONS[state["plan"]]
    active = state["status"] in {"active", "trialing"}
    cutoff = _normalize_cutoff(as_of) or state.get("lastEventAt")
    coupon_active = (
        active
        and state["couponCode"] is not None
        and state["couponExpiresAt"] is not None
        and (cutoff is None or state["couponExpiresAt"] >= cutoff)
    )

    usage_limit = plan["usageLimit"] if active else 0
    return {
        "active": active,
        "features": list(plan["features"]) if active else [],
        "usageLimit": usage_limit,
        "overLimit": state["usage"] > usage_limit,
        "couponActive": coupon_active,
    }


def summarize_account(state: dict[str, Any], as_of: str | None = None) -> dict[str, Any]:
    entitlements = evaluate_entitlements(state, as_of)
    summary = {
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
    return {field: summary[field] for field in V2_SUMMARY_FIELDS}


def export_ledger_report(summaries: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(V2_CSV_HEADER)
    for summary in sorted(summaries, key=lambda row: row["accountId"]):
        writer.writerow([_csv_value(summary, field) for field in V2_CSV_HEADER])
    return output.getvalue()


def calculate_proration(full_period_minor_units: int, active_ms: int, period_ms: int, quantity: int = 1) -> int:
    if period_ms <= 0:
        raise ValueError("period_ms must be greater than zero")
    if active_ms < 0:
        raise ValueError("active_ms must be non-negative")
    if quantity < 0:
        raise ValueError("quantity must be non-negative")
    return round_half_away_from_zero(Fraction(full_period_minor_units * quantity * active_ms, period_ms))


def calculate_plan_change_proration(
    old_plan: str,
    new_plan: str,
    period_start: str,
    period_end: str,
    change_effective_at: str,
    quantity: int = 1,
) -> dict[str, Any]:
    start = _parse_canonical_timestamp(_normalize_required_cutoff(period_start))
    end = _parse_canonical_timestamp(_normalize_required_cutoff(period_end))
    change = _parse_canonical_timestamp(_normalize_required_cutoff(change_effective_at))
    if end <= start:
        raise ValueError("period_end must be greater than period_start")
    if change < start or change > end:
        raise ValueError("change_effective_at must be within the period")

    period_ms = _milliseconds_between(start, end)
    remaining_ms = _milliseconds_between(change, end)
    old_full = PLAN_DEFINITIONS[old_plan]["priceCents"]
    new_full = PLAN_DEFINITIONS[new_plan]["priceCents"]
    old_credit = -calculate_proration(old_full, remaining_ms, period_ms, quantity)
    new_charge = calculate_proration(new_full, remaining_ms, period_ms, quantity)
    return {
        "oldPlan": old_plan,
        "newPlan": new_plan,
        "quantity": quantity,
        "periodStart": _normalize_required_cutoff(period_start),
        "periodEnd": _normalize_required_cutoff(period_end),
        "changeEffectiveAt": _normalize_required_cutoff(change_effective_at),
        "oldCreditCents": old_credit,
        "newChargeCents": new_charge,
        "netAdjustmentCents": old_credit + new_charge,
    }


def round_half_away_from_zero(value: Fraction) -> int:
    sign = -1 if value < 0 else 1
    absolute = abs(value)
    quotient = absolute.numerator // absolute.denominator
    remainder = absolute.numerator % absolute.denominator
    if remainder * 2 >= absolute.denominator:
        quotient += 1
    return sign * quotient


def evaluate_case(case: dict[str, Any]) -> Any:
    operation = case["operation"]
    input_payload = case["input"]

    if operation == "parse_line":
        return parse_event_line(input_payload["line"])
    if operation == "normalize_event":
        return normalize_event(input_payload["raw_event"])
    if operation == "v2_reduce_and_summarize":
        return summarize_raw_events(
            input_payload["raw_events"],
            input_payload.get("as_of"),
            business_as_of=input_payload.get("business_as_of"),
            audit_as_of=input_payload.get("audit_as_of"),
        )
    if operation == "v2_reduce_and_evaluate":
        return evaluate_raw_events(
            input_payload["raw_events"],
            input_payload["account_id"],
            input_payload.get("as_of"),
            business_as_of=input_payload.get("business_as_of"),
            audit_as_of=input_payload.get("audit_as_of"),
        )
    if operation == "v2_export_report":
        return export_ledger_report(input_payload["summaries"])
    if operation == "v2_calculate_proration":
        return calculate_plan_change_proration(
            input_payload["old_plan"],
            input_payload["new_plan"],
            input_payload["period_start"],
            input_payload["period_end"],
            input_payload["change_effective_at"],
            input_payload.get("quantity", 1),
        )
    if operation == "v2_metamorphic":
        return evaluate_metamorphic(input_payload)
    if operation == "v2_performance_digest":
        return performance_digest(
            input_payload["raw_events"],
            input_payload.get("as_of"),
            business_as_of=input_payload.get("business_as_of"),
            audit_as_of=input_payload.get("audit_as_of"),
        )
    if operation == "v2_parity":
        summaries = summarize_raw_events(
            input_payload["raw_events"],
            input_payload.get("as_of"),
            business_as_of=input_payload.get("business_as_of"),
            audit_as_of=input_payload.get("audit_as_of"),
        )
        return {"summaries": summaries, "report": export_ledger_report(summaries)}

    raise ValueError(f"unsupported v2 oracle operation: {operation}")


def evaluate_metamorphic(input_payload: dict[str, Any]) -> dict[str, Any]:
    target_account_id = input_payload.get("target_account_id")
    baseline = summarize_raw_events(
        input_payload["baseline"],
        input_payload.get("as_of"),
        business_as_of=input_payload.get("business_as_of"),
        audit_as_of=input_payload.get("audit_as_of"),
    )
    baseline_focus = _focus_summaries(baseline, target_account_id)
    variants = []
    for variant in input_payload["variants"]:
        value = summarize_raw_events(
            variant["raw_events"],
            input_payload.get("as_of"),
            business_as_of=input_payload.get("business_as_of"),
            audit_as_of=input_payload.get("audit_as_of"),
        )
        focus = _focus_summaries(value, target_account_id)
        variants.append(
            {
                "name": variant["name"],
                "value": focus,
                "equivalent": _canonical_json(focus) == _canonical_json(baseline_focus),
            }
        )
    return {"baseline": baseline_focus, "variants": variants}


def performance_digest(
    raw_events: list[dict[str, Any]],
    as_of: str | None = None,
    *,
    business_as_of: str | None = None,
    audit_as_of: str | None = None,
) -> dict[str, Any]:
    summaries = summarize_raw_events(
        raw_events,
        as_of,
        business_as_of=business_as_of,
        audit_as_of=audit_as_of,
    )
    report = export_ledger_report(summaries)
    return {
        "eventCount": len(raw_events),
        "summaryCount": len(summaries),
        "firstAccountId": summaries[0]["accountId"] if summaries else None,
        "lastAccountId": summaries[-1]["accountId"] if summaries else None,
        "totalUsage": sum(summary["usage"] for summary in summaries),
        "totalPaidCents": sum(summary["totalPaidCents"] for summary in summaries),
        "summarySha256": hashlib.sha256(_canonical_json(summaries).encode("utf-8")).hexdigest(),
        "reportSha256": hashlib.sha256(report.encode("utf-8")).hexdigest(),
    }


def _active_events_for_view(
    events: list[dict[str, Any]],
    business_cutoff: str | None,
    audit_cutoff: str | None,
) -> list[dict[str, Any]]:
    visible = [event for event in events if audit_cutoff is None or event["recordedAt"] <= audit_cutoff]
    deduped: dict[str, dict[str, Any]] = {}
    for event in sorted(visible, key=_replay_sort_key):
        deduped.setdefault(event["id"], event)

    ordered = list(deduped.values())
    by_id = {event["id"]: event for event in ordered}
    correction_targets = {
        event["id"]: event["correctionOf"]
        for event in ordered
        if event["type"] == "event_corrected" and event.get("correctionOf") in by_id
    }
    operations_by_target: dict[str, list[dict[str, Any]]] = {}
    for event in ordered:
        target_id = _operation_target_id(event, correction_targets)
        if target_id is not None and target_id in by_id:
            operations_by_target.setdefault(target_id, []).append(event)

    active: list[dict[str, Any]] = []
    for event in ordered:
        if event["type"] in CORRECTION_TYPES:
            continue
        final_event = event
        is_active = True
        for operation in sorted(operations_by_target.get(event["id"], []), key=_operation_sort_key):
            if operation["type"] == "event_corrected":
                final_event = _replacement_event(event, operation)
                is_active = True
            if operation["type"] == "event_voided":
                is_active = False
        if is_active:
            active.append(final_event)

    return [event for event in active if business_cutoff is None or event["effectiveAt"] <= business_cutoff]


def _operation_target_id(event: dict[str, Any], correction_targets: dict[str, str]) -> str | None:
    if event["type"] == "event_corrected":
        return event.get("correctionOf")
    if event["type"] == "event_voided":
        target_id = event.get("voidedEventId")
        if target_id in correction_targets:
            return correction_targets[target_id]
        return target_id
    return None


def _replacement_event(target: dict[str, Any], correction: dict[str, Any]) -> dict[str, Any]:
    replacement = dict(target)
    replacement_fields = {
        "timestamp",
        "effectiveAt",
        "recordedAt",
        "sequence",
        "plan",
        "amountCents",
        "currency",
        "couponCode",
        "couponExpiresAt",
        "usage",
        "quantity",
        "seatDelta",
        "mergeFromAccountId",
        "invoiceId",
        "periodStart",
        "periodEnd",
    }
    for field in replacement_fields:
        if field in correction:
            replacement[field] = correction[field]
    replacement["id"] = target["id"]
    replacement["type"] = target["type"]
    replacement["accountId"] = target["accountId"]
    return replacement


def _apply_event(state: dict[str, Any], event: dict[str, Any]) -> None:
    event_type = event["type"]

    if event_type == "account_opened" and state["status"] != "closed":
        if "plan" in event:
            state["plan"] = event["plan"]
            state["_explicitPlan"] = True
        if "quantity" in event:
            state["seats"] = max(1, event["quantity"])
        elif state["seats"] == 0:
            state["seats"] = 1
        state["status"] = "active"
        state["_explicitStatus"] = True

    elif event_type == "trial_started" and state["status"] not in {"closed", "cancelled", "paused"}:
        state["status"] = "trialing"
        state["_explicitStatus"] = True

    elif event_type == "trial_ended" and state["status"] == "trialing":
        state["status"] = "active"
        state["_explicitStatus"] = True

    elif event_type == "plan_changed" and state["status"] != "closed":
        if "plan" in event:
            state["plan"] = event["plan"]
            state["_explicitPlan"] = True

    elif event_type == "account_paused" and state["status"] != "closed":
        state["status"] = "paused"
        state["_explicitStatus"] = True

    elif event_type == "account_resumed" and state["status"] == "paused":
        state["status"] = "active"
        state["_explicitStatus"] = True

    elif event_type == "account_cancelled" and state["status"] != "closed":
        state["status"] = "cancelled"
        state["_explicitStatus"] = True

    elif event_type == "account_reactivated" and state["status"] == "cancelled":
        state["status"] = "active"
        state["_explicitStatus"] = True

    elif event_type == "account_closed":
        state["status"] = "closed"
        state["closedAt"] = event["effectiveAt"]
        state["_explicitStatus"] = True

    elif event_type == "payment_failed":
        state["failedPayments"] += 1
        if state["status"] in {"active", "trialing"}:
            state["status"] = "past_due"
            state["_explicitStatus"] = True

    elif event_type == "payment_recovered" and state["status"] == "past_due":
        state["status"] = "active"
        state["_explicitStatus"] = True

    elif event_type == "payment_succeeded":
        state["totalPaidCents"] += event.get("amountCents", 0)
        if state["status"] in {"past_due", "pending"}:
            state["status"] = "active"
            state["_explicitStatus"] = True

    elif event_type == "coupon_applied":
        state["couponCode"] = event.get("couponCode", state["couponCode"])
        state["couponExpiresAt"] = event.get("couponExpiresAt", state["couponExpiresAt"])

    elif event_type == "usage_recorded":
        state["usage"] += event.get("usage", event.get("quantity", 0))

    if "seatDelta" in event:
        state["seats"] = max(0, state["seats"] + event["seatDelta"])

    if "currency" in event:
        state["currency"] = event["currency"]

    if "invoiceId" in event:
        _add_unique(state["invoiceIds"], event["invoiceId"])
        state["lastInvoiceId"] = event["invoiceId"]
    if "periodStart" in event:
        state["lastPeriodStart"] = event["periodStart"]
    if "periodEnd" in event:
        state["lastPeriodEnd"] = event["periodEnd"]

    state["lastEventAt"] = event["effectiveAt"]


def _apply_account_merge(states: dict[str, dict[str, Any]], aliases: dict[str, str], event: dict[str, Any]) -> None:
    if not event.get("mergeFromAccountId"):
        return
    destination_id = _canonical_account(event["accountId"], aliases)
    source_id = _canonical_account(event["mergeFromAccountId"], aliases)
    if source_id == destination_id:
        return

    destination = _get_or_create_state(states, destination_id)
    source = states.get(source_id)
    if source is not None:
        destination["totalPaidCents"] += source["totalPaidCents"]
        destination["usage"] += source["usage"]
        destination["failedPayments"] += source["failedPayments"]
        destination["seats"] += source["seats"]
        if destination["couponCode"] is None:
            destination["couponCode"] = source["couponCode"]
            destination["couponExpiresAt"] = source["couponExpiresAt"]
        if not destination["_explicitPlan"] and source["_explicitPlan"]:
            destination["plan"] = source["plan"]
            destination["_explicitPlan"] = True
        if not destination["_explicitStatus"] and source["_explicitStatus"]:
            destination["status"] = source["status"]
            destination["_explicitStatus"] = True
        for invoice_id in source["invoiceIds"]:
            _add_unique(destination["invoiceIds"], invoice_id)
        destination["lastInvoiceId"] = destination["lastInvoiceId"] or source["lastInvoiceId"]
        destination["lastPeriodStart"] = destination["lastPeriodStart"] or source["lastPeriodStart"]
        destination["lastPeriodEnd"] = destination["lastPeriodEnd"] or source["lastPeriodEnd"]
        for lineage_id in source["mergedFromAccountIds"]:
            _add_unique(destination["mergedFromAccountIds"], lineage_id)
        del states[source_id]

    _add_unique(destination["mergedFromAccountIds"], source_id)
    aliases[source_id] = destination_id
    for alias, canonical_id in list(aliases.items()):
        if canonical_id == source_id:
            aliases[alias] = destination_id
    destination["lastEventAt"] = event["effectiveAt"]


def _get_or_create_state(states: dict[str, dict[str, Any]], account_id: str) -> dict[str, Any]:
    if account_id not in states:
        states[account_id] = {
            "accountId": account_id,
            "status": "pending",
            "plan": "free",
            "features": [],
            "usage": 0,
            "usageLimit": 0,
            "overLimit": False,
            "totalPaidCents": 0,
            "failedPayments": 0,
            "currency": None,
            "seats": 0,
            "couponCode": None,
            "couponExpiresAt": None,
            "couponActive": False,
            "invoiceIds": [],
            "lastInvoiceId": None,
            "lastPeriodStart": None,
            "lastPeriodEnd": None,
            "mergedFromAccountIds": [],
            "closedAt": None,
            "lastEventAt": None,
            "_explicitPlan": False,
            "_explicitStatus": False,
        }
    return states[account_id]


def _focus_summaries(summaries: list[dict[str, Any]], target_account_id: str | None) -> list[dict[str, Any]]:
    if target_account_id is None:
        return summaries
    return [summary for summary in summaries if summary["accountId"] == target_account_id]


def _csv_value(summary: dict[str, Any], header: str) -> str:
    field = {
        "account_id": "accountId",
        "status": "status",
        "plan": "plan",
        "total_paid_cents": "totalPaidCents",
        "currency": "currency",
        "seats": "seats",
        "usage": "usage",
        "usage_limit": "usageLimit",
        "over_limit": "overLimit",
        "coupon_code": "couponCode",
        "coupon_active": "couponActive",
        "invoice_ids": "invoiceIds",
        "last_invoice_id": "lastInvoiceId",
        "last_period_start": "lastPeriodStart",
        "last_period_end": "lastPeriodEnd",
        "merged_from_account_ids": "mergedFromAccountIds",
        "closed_at": "closedAt",
        "last_event_at": "lastEventAt",
    }[header]
    value = summary.get(field)
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    return str(value)


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
    return value


def _read_integer_value(value: Any, *, minimum: int | None = None) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    if minimum is not None and value < minimum:
        return None
    return value


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


def _normalize_optional_timestamp(
    raw: dict[str, Any],
    field: str,
    issues: list[str],
    issue_code: str,
) -> str | None:
    if field not in raw:
        return None
    value = raw.get(field)
    if not isinstance(value, str) or value.strip() == "":
        issues.append(issue_code)
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
    if raw_field not in raw:
        return
    value = raw.get(raw_field)
    if not isinstance(value, str) or value.strip() == "":
        issues.append(issue_code)
        return
    normalized_value = _normalize_timestamp(value, issues, issue_code)
    if normalized_value is not None:
        normalized[normalized_field] = normalized_value


def _copy_optional_id(
    raw: dict[str, Any],
    normalized: dict[str, Any],
    raw_field: str,
    normalized_field: str,
    issues: list[str],
) -> None:
    if raw_field not in raw:
        return
    value = raw.get(raw_field)
    if not isinstance(value, str) or value.strip() == "":
        issues.append(f"invalid_{raw_field}")
        return
    normalized[normalized_field] = value.strip()


def _parse_money_to_cents(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if re.fullmatch(r"-?\d+\.\d{2}", trimmed) is None:
        return None
    sign = -1 if trimmed.startswith("-") else 1
    unsigned = trimmed[1:] if sign == -1 else trimmed
    dollars, cents = unsigned.split(".")
    return sign * (int(dollars) * 100 + int(cents))


def _normalize_currency(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip().upper()
    if re.fullmatch(r"[A-Z]{3}", trimmed) is None:
        return None
    return trimmed


def _normalize_cutoff(value: str | None) -> str | None:
    if value is None:
        return None
    return _normalize_required_cutoff(value)


def _normalize_required_cutoff(value: str) -> str:
    issues: list[str] = []
    normalized = _normalize_timestamp(value, issues, "invalid_cutoff")
    if normalized is None:
        raise ValueError(f"invalid cutoff timestamp: {value}")
    return normalized


def _parse_canonical_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _milliseconds_between(start: datetime, end: datetime) -> int:
    delta = end - start
    return ((delta.days * 24 * 60 * 60) + delta.seconds) * 1000 + (delta.microseconds // 1000)


def _replay_sort_key(event: dict[str, Any]) -> tuple[str, str, int, str]:
    return (event["effectiveAt"], event["recordedAt"], event["sequence"], event["id"])


def _operation_sort_key(event: dict[str, Any]) -> tuple[str, int, str]:
    return (event["recordedAt"], event["sequence"], event["id"])


def _canonical_account(account_id: str, aliases: dict[str, str]) -> str:
    seen: set[str] = set()
    current = account_id
    while current in aliases and current not in seen:
        seen.add(current)
        current = aliases[current]
    return current


def _add_unique(values: list[str], value: str | None) -> None:
    if value is not None and value not in values:
        values.append(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
