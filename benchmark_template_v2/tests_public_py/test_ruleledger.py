import json
from pathlib import Path

from ruleledger.engine import (
    export_ledger_report,
    normalize_event,
    parse_event_line,
    reduce_account_state,
    summarize_account,
)


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
