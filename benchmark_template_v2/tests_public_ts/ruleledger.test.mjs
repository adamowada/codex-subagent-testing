import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  exportLedgerReport,
  normalizeEvent,
  parseEventLine,
  reduceAccountState,
  summarizeAccount
} from "../dist/index.js";

const here = dirname(fileURLToPath(import.meta.url));
const fixturesDir = join(here, "..", "fixtures");

function readFixtureEvents() {
  return readFileSync(join(fixturesDir, "public_events_v2.jsonl"), "utf8")
    .split(/\r?\n/)
    .filter((line) => line.trim() !== "")
    .map((line) => {
      const parsed = parseEventLine(line);
      assert.equal(parsed.ok, true);
      const normalized = normalizeEvent(parsed.value);
      assert.equal(normalized.ok, true, JSON.stringify(normalized, null, 2));
      return normalized.value;
    });
}

test("parseEventLine returns structured results without throwing", () => {
  assert.deepEqual(parseEventLine('{"id":"evt_1"}'), {
    ok: true,
    value: { id: "evt_1" }
  });

  assert.deepEqual(parseEventLine("{not-json"), {
    ok: false,
    error: "invalid_json",
    line: "{not-json"
  });
});

test("normalizeEvent exposes all v2 raw fields as deterministic camelCase", () => {
  const result = normalizeEvent({
    id: " evt_all ",
    account_id: " acct_v2 ",
    type: "payment_succeeded",
    timestamp: "2026-02-03T04:05:06-05:00",
    effective_at: "2026-02-01T00:00:00Z",
    recorded_at: "2026-02-03T09:05:07Z",
    sequence: 12,
    amount: "12.34",
    currency: "usd",
    quantity: 5,
    seat_delta: -1,
    merge_from_account_id: " acct_old ",
    correction_of: " evt_before ",
    voided_event_id: " evt_voided ",
    invoice_id: " inv_123 ",
    period_start: "2026-02-01T00:00:00Z",
    period_end: "2026-03-01T00:00:00Z"
  });

  assert.equal(result.ok, true);
  assert.deepEqual(result.value, {
    id: "evt_all",
    accountId: "acct_v2",
    type: "payment_succeeded",
    timestamp: "2026-02-03T09:05:06.000Z",
    effectiveAt: "2026-02-01T00:00:00.000Z",
    recordedAt: "2026-02-03T09:05:07.000Z",
    sequence: 12,
    amountCents: 1234,
    currency: "USD",
    quantity: 5,
    seatDelta: -1,
    mergeFromAccountId: "acct_old",
    correctionOf: "evt_before",
    voidedEventId: "evt_voided",
    invoiceId: "inv_123",
    periodStart: "2026-02-01T00:00:00.000Z",
    periodEnd: "2026-03-01T00:00:00.000Z"
  });
});

test("amount_cents, currency, and default bitemporal fields normalize visibly", () => {
  const result = normalizeEvent({
    id: "evt_minor",
    account_id: "acct_v2",
    type: "invoice_issued",
    timestamp: "2026-01-01T12:00:00Z",
    amount_cents: 4900,
    currency: "eur"
  });

  assert.equal(result.ok, true);
  assert.equal(result.value.amountCents, 4900);
  assert.equal(result.value.currency, "EUR");
  assert.equal(result.value.effectiveAt, "2026-01-01T12:00:00.000Z");
  assert.equal(result.value.recordedAt, "2026-01-01T12:00:00.000Z");
  assert.equal(result.value.sequence, 0);
});

test("reduceAccountState replays a tiny bitemporal event set deterministically", () => {
  const rawEvents = [
    {
      id: "evt_plan",
      account_id: "acct_order",
      type: "plan_changed",
      timestamp: "2026-01-05T00:00:00Z",
      effective_at: "2026-01-02T00:00:00Z",
      recorded_at: "2026-01-05T00:00:00Z",
      sequence: 2,
      plan: "pro"
    },
    {
      id: "evt_open",
      account_id: "acct_order",
      type: "account_opened",
      timestamp: "2026-01-01T00:00:00Z",
      effective_at: "2026-01-01T00:00:00Z",
      recorded_at: "2026-01-01T00:00:00Z",
      sequence: 1,
      plan: "starter"
    }
  ];

  const events = rawEvents.map((raw) => {
    const result = normalizeEvent(raw);
    assert.equal(result.ok, true);
    return result.value;
  });
  const [state] = reduceAccountState(events);

  assert.equal(state.plan, "pro");
  assert.equal(state.lastEventAt, "2026-01-02T00:00:00.000Z");
});

test("shared public fixture reduces to the expected deterministic v2 summary", () => {
  const events = readFixtureEvents();
  const states = reduceAccountState(events);
  const summaries = states.map((state) => summarizeAccount(state, "2026-01-15T00:00:00.000Z"));
  const expected = JSON.parse(readFileSync(join(fixturesDir, "public_expected_summary_v2.json"), "utf8"));

  assert.deepEqual(summaries, expected);
});

test("exportLedgerReport writes stable v2 CSV with a trailing newline", () => {
  const events = readFixtureEvents();
  const states = reduceAccountState(events);
  const summaries = states.map((state) => summarizeAccount(state, "2026-01-15T00:00:00.000Z"));
  const expected = readFileSync(join(fixturesDir, "public_expected_report_v2.csv"), "utf8");

  assert.equal(exportLedgerReport(summaries), expected);
});
