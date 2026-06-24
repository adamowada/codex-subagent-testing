import json
from pathlib import Path

from ruleledger.engine import (
    calculate_plan_change_proration_v2,
    export_ledger_report,
    export_ledger_report_v2,
    normalize_event,
    normalize_event_v2,
    parse_event_line,
    reduce_account_state,
    reduce_account_state_v2,
    summarize_account,
    summarize_account_v2,
)


DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _read_fixture_events():
    events = []
    for line in (FIXTURES_DIR / "public_events_v2.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parsed = parse_event_line(line)
        assert parsed["ok"]
        normalized = normalize_event(parsed["value"])
        assert normalized["ok"], json.dumps(normalized, indent=2)
        events.append(normalized["value"])
    return events


def _read_semantics_examples():
    return json.loads((FIXTURES_DIR / "public_semantics_examples.json").read_text(encoding="utf-8"))


def _normalize_raw_events(raw_events):
    events = []
    for raw_event in raw_events:
        normalized = normalize_event(raw_event)
        assert normalized["ok"], json.dumps(normalized, indent=2)
        events.append(normalized["value"])
    return events


def _replay_order(events):
    return [
        event["id"]
        for event in sorted(
            events,
            key=lambda event: (event["effectiveAt"], event["recordedAt"], event["sequence"], event["id"]),
        )
    ]


def _half_away_from_zero_rational(numerator, denominator):
    sign = -1 if numerator < 0 else 1
    quotient, remainder = divmod(abs(numerator), denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return sign * quotient


def _half_away_from_zero_decimal(value):
    sign = -1 if value.startswith("-") else 1
    whole, _, fractional = value.lstrip("-").partition(".")
    denominator = 10 ** len(fractional)
    numerator = int(whole) * denominator + int(fractional or "0")
    return sign * _half_away_from_zero_rational(numerator, denominator)


def test_parse_event_line_returns_structured_results_without_throwing():
    assert parse_event_line('{"id":"evt_1"}') == {"ok": True, "value": {"id": "evt_1"}}
    assert parse_event_line("{not-json") == {"ok": False, "error": "invalid_json", "line": "{not-json"}


def test_normalize_event_exposes_all_v2_raw_fields_as_deterministic_camel_case():
    result = normalize_event(
        {
            "id": " evt_all ",
            "account_id": " acct_v2 ",
            "type": "payment_succeeded",
            "timestamp": "2026-02-03T04:05:06-05:00",
            "effective_at": "2026-02-01T00:00:00Z",
            "recorded_at": "2026-02-03T09:05:07Z",
            "sequence": 12,
            "amount": "12.34",
            "currency": "usd",
            "quantity": 5,
            "seat_delta": -1,
            "merge_from_account_id": " acct_old ",
            "correction_of": " evt_before ",
            "voided_event_id": " evt_voided ",
            "invoice_id": " inv_123 ",
            "period_start": "2026-02-01T00:00:00Z",
            "period_end": "2026-03-01T00:00:00Z",
        }
    )

    assert result["ok"]
    assert result["value"] == {
        "id": "evt_all",
        "accountId": "acct_v2",
        "type": "payment_succeeded",
        "timestamp": "2026-02-03T09:05:06.000Z",
        "effectiveAt": "2026-02-01T00:00:00.000Z",
        "recordedAt": "2026-02-03T09:05:07.000Z",
        "sequence": 12,
        "amountCents": 1234,
        "currency": "USD",
        "quantity": 5,
        "seatDelta": -1,
        "mergeFromAccountId": "acct_old",
        "correctionOf": "evt_before",
        "voidedEventId": "evt_voided",
        "invoiceId": "inv_123",
        "periodStart": "2026-02-01T00:00:00.000Z",
        "periodEnd": "2026-03-01T00:00:00.000Z",
    }


def test_amount_cents_currency_and_default_bitemporal_fields_normalize_visibly():
    result = normalize_event(
        {
            "id": "evt_minor",
            "account_id": "acct_v2",
            "type": "invoice_issued",
            "timestamp": "2026-01-01T12:00:00Z",
            "amount_cents": 4900,
            "currency": "eur",
        }
    )

    assert result["ok"]
    assert result["value"]["amountCents"] == 4900
    assert result["value"]["currency"] == "EUR"
    assert result["value"]["effectiveAt"] == "2026-01-01T12:00:00.000Z"
    assert result["value"]["recordedAt"] == "2026-01-01T12:00:00.000Z"
    assert result["value"]["sequence"] == 0


def test_v2_normalization_accepts_documented_lifecycle_and_negative_credit_values():
    result = normalize_event_v2(
        {
            "id": "evt_credit",
            "account_id": "acct_v2",
            "type": "payment_recovered",
            "timestamp": "2026-01-02T00:00:00Z",
            "amount_cents": -250,
            "currency": "usd",
        }
    )

    assert result["ok"], json.dumps(result, indent=2)
    assert result["value"]["type"] == "payment_recovered"
    assert result["value"]["amountCents"] == -250


def test_reduce_account_state_replays_tiny_bitemporal_event_set_deterministically():
    raw_events = [
        {
            "id": "evt_plan",
            "account_id": "acct_order",
            "type": "plan_changed",
            "timestamp": "2026-01-05T00:00:00Z",
            "effective_at": "2026-01-02T00:00:00Z",
            "recorded_at": "2026-01-05T00:00:00Z",
            "sequence": 2,
            "plan": "pro",
        },
        {
            "id": "evt_open",
            "account_id": "acct_order",
            "type": "account_opened",
            "timestamp": "2026-01-01T00:00:00Z",
            "effective_at": "2026-01-01T00:00:00Z",
            "recorded_at": "2026-01-01T00:00:00Z",
            "sequence": 1,
            "plan": "starter",
        },
    ]

    events = []
    for raw_event in raw_events:
        result = normalize_event(raw_event)
        assert result["ok"]
        events.append(result["value"])
    state = reduce_account_state(events)[0]

    assert state["plan"] == "pro"
    assert state["lastEventAt"] == "2026-01-02T00:00:00.000Z"


def test_shared_public_fixture_reduces_to_expected_deterministic_v2_summary():
    states = reduce_account_state(_read_fixture_events())
    summaries = [summarize_account(state, "2026-01-15T00:00:00.000Z") for state in states]
    expected = json.loads((FIXTURES_DIR / "public_expected_summary_v2.json").read_text(encoding="utf-8"))

    assert summaries == expected


def test_export_ledger_report_writes_stable_v2_csv_with_trailing_newline():
    states = reduce_account_state(_read_fixture_events())
    summaries = [summarize_account(state, "2026-01-15T00:00:00.000Z") for state in states]
    expected = (FIXTURES_DIR / "public_expected_report_v2.csv").read_text(encoding="utf-8")

    assert export_ledger_report(summaries) == expected


def test_public_semantics_examples_reference_documented_hard_mode_rule_ids():
    semantics = (DOCS_DIR / "ruleledger_v2_semantics.md").read_text(encoding="utf-8")
    fixture = _read_semantics_examples()
    concepts = sorted(example["concept"] for example in fixture["examples"])

    assert fixture["semantics_document"] == "docs/ruleledger_v2_semantics.md"
    assert concepts == ["account_merge", "bitemporal", "correction_void", "csv_parity", "proration"]

    for example in fixture["examples"]:
        assert example["rule_ids"], example["id"]
        for rule_id in example["rule_ids"]:
            assert f"### {rule_id}:" in semantics, f"{example['id']} references missing {rule_id}"


def test_bitemporal_public_semantics_example_has_deterministic_replay_and_summary():
    example = next(
        candidate for candidate in _read_semantics_examples()["examples"] if candidate["id"] == "public.bitemporal_late_arrival"
    )
    events = _normalize_raw_events(example["raw_events"])
    states = reduce_account_state(events)
    summaries = [summarize_account(state, example["as_of"]) for state in states]

    assert _replay_order(events) == example["expected_replay_order"]
    assert summaries == [example["expected_summary"]]


def test_correction_void_and_merge_public_semantics_examples_expose_lineage_fields():
    examples = _read_semantics_examples()["examples"]
    correction = next(candidate for candidate in examples if candidate["id"] == "public.correction_void_lineage")
    normalized_by_id = {event["id"]: event for event in _normalize_raw_events(correction["raw_events"])}

    for event_id, expected_fields in correction["expected_normalized_fields"].items():
        for field, expected_value in expected_fields.items():
            assert normalized_by_id[event_id][field] == expected_value

    merge = next(candidate for candidate in examples if candidate["id"] == "public.account_merge_lineage")
    normalized_merge = normalize_event(merge["raw_event"])
    assert normalized_merge["ok"]
    for field, expected_value in merge["expected_normalized_fields"].items():
        assert normalized_merge["value"][field] == expected_value


def test_proration_public_semantics_example_documents_half_away_from_zero_rounding():
    example = next(
        candidate
        for candidate in _read_semantics_examples()["examples"]
        if candidate["id"] == "public.proration_half_away_from_zero"
    )

    for rounding in example["rounding_examples"]:
        assert _half_away_from_zero_decimal(rounding["value"]) == rounding["expected"]

    calc = example["calculation"]
    assert (
        _half_away_from_zero_rational(
            calc["full_period_amount_cents"] * calc["active_ms"],
            calc["period_ms"],
        )
        == calc["expected_prorated_amount_cents"]
    )


def test_csv_public_semantics_example_matches_stable_v2_report_contract():
    example = next(candidate for candidate in _read_semantics_examples()["examples"] if candidate["id"] == "public.csv_parity_contract")
    expected = (FIXTURES_DIR / example["expected_report_fixture"]).read_text(encoding="utf-8")

    assert export_ledger_report(example["summaries"]) == expected


def test_v2_hooks_expose_separate_view_cutoffs_proration_and_csv_escaping():
    raw_events = [
        {
            "id": "evt_open",
            "account_id": "acct_hook",
            "type": "account_opened",
            "timestamp": "2026-01-01T00:00:00Z",
            "effective_at": "2026-01-01T00:00:00Z",
            "recorded_at": "2026-01-01T00:00:00Z",
            "plan": "starter",
        },
        {
            "id": "evt_future",
            "account_id": "acct_hook",
            "type": "plan_changed",
            "timestamp": "2026-01-02T00:00:00Z",
            "effective_at": "2026-02-01T00:00:00Z",
            "recorded_at": "2026-01-02T00:00:00Z",
            "plan": "pro",
        },
    ]
    events = _normalize_raw_events(raw_events)
    states = reduce_account_state_v2(
        events,
        {
            "businessAsOf": "2026-01-15T00:00:00.000Z",
            "auditAsOf": "2026-02-15T00:00:00.000Z",
        },
    )
    summary = summarize_account_v2(states[0], {"businessAsOf": "2026-01-15T00:00:00.000Z"})

    assert summary["plan"] == "starter"
    escaped = export_ledger_report_v2([{**summary, "couponCode": 'SAVE,"10'}])
    assert '"SAVE,""10"' in escaped

    assert calculate_plan_change_proration_v2(
        {
            "old_plan": "starter",
            "new_plan": "pro",
            "period_start": "2026-01-01T00:00:00Z",
            "period_end": "2026-02-01T00:00:00Z",
            "change_effective_at": "2026-01-16T12:00:00Z",
            "quantity": 1,
        }
    ) == {
        "oldPlan": "starter",
        "newPlan": "pro",
        "quantity": 1,
        "periodStart": "2026-01-01T00:00:00.000Z",
        "periodEnd": "2026-02-01T00:00:00.000Z",
        "changeEffectiveAt": "2026-01-16T12:00:00.000Z",
        "oldCreditCents": -600,
        "newChargeCents": 2450,
        "netAdjustmentCents": 1850,
    }
