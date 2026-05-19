import json
from pathlib import Path
import unittest

from ruleledger.engine import (
    export_ledger_report,
    normalize_event,
    parse_event_line,
    reduce_account_state,
    summarize_account,
)


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class RuleLedgerPublicTests(unittest.TestCase):
    def test_parse_event_line_returns_structured_results_without_throwing(self):
        self.assertEqual(
            parse_event_line('{"id":"evt_1"}'),
            {"ok": True, "value": {"id": "evt_1"}},
        )
        self.assertEqual(
            parse_event_line("{not-json"),
            {"ok": False, "error": "invalid_json", "line": "{not-json"},
        )

    def test_normalize_event_trims_timestamps_and_money(self):
        result = normalize_event(
            {
                "id": " evt_pay ",
                "account_id": " acct_1 ",
                "type": "payment_succeeded",
                "timestamp": "2026-02-03T04:05:06-05:00",
                "amount": "12.34",
            }
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["value"]["id"], "evt_pay")
        self.assertEqual(result["value"]["accountId"], "acct_1")
        self.assertEqual(result["value"]["timestamp"], "2026-02-03T09:05:06.000Z")
        self.assertEqual(result["value"]["amountCents"], 1234)

    def test_shared_public_fixture_reduces_to_expected_summary(self):
        events = []
        for line in (FIXTURES_DIR / "public_events.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parsed = parse_event_line(line)
            self.assertTrue(parsed["ok"])
            normalized = normalize_event(parsed["value"])
            self.assertTrue(normalized["ok"], json.dumps(normalized, indent=2))
            events.append(normalized["value"])

        states = reduce_account_state(events)
        summaries = [summarize_account(state, "2026-01-10T00:00:00.000Z") for state in states]
        expected = json.loads((FIXTURES_DIR / "public_expected_summary.json").read_text(encoding="utf-8"))

        self.assertEqual(summaries, expected)

    def test_export_ledger_report_writes_stable_csv_with_trailing_newline(self):
        csv = export_ledger_report(
            [
                {
                    "accountId": "acct_b",
                    "status": "closed",
                    "plan": "free",
                    "features": [],
                    "usage": 0,
                    "usageLimit": 0,
                    "overLimit": False,
                    "totalPaidCents": 0,
                    "couponCode": None,
                    "couponActive": False,
                    "closedAt": "2026-01-02T00:00:00.000Z",
                    "lastEventAt": "2026-01-02T00:00:00.000Z",
                },
                {
                    "accountId": "acct_a",
                    "status": "active",
                    "plan": "starter",
                    "features": ["dashboard", "exports"],
                    "usage": 25,
                    "usageLimit": 1000,
                    "overLimit": False,
                    "totalPaidCents": 1200,
                    "couponCode": "SAVE10",
                    "couponActive": True,
                    "closedAt": None,
                    "lastEventAt": "2026-01-01T00:00:00.000Z",
                },
            ]
        )

        self.assertEqual(
            csv,
            "\n".join(
                [
                    "account_id,status,plan,total_paid_cents,usage,usage_limit,over_limit,coupon_code,coupon_active,closed_at,last_event_at",
                    "acct_a,active,starter,1200,25,1000,false,SAVE10,true,,2026-01-01T00:00:00.000Z",
                    "acct_b,closed,free,0,0,0,false,,false,2026-01-02T00:00:00.000Z,2026-01-02T00:00:00.000Z",
                    "",
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
