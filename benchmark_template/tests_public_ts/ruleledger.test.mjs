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

test("normalizeEvent trims strings, normalizes timestamps, and converts money", () => {
  const result = normalizeEvent({
    id: " evt_pay ",
    account_id: " acct_1 ",
    type: "payment_succeeded",
    timestamp: "2026-02-03T04:05:06-05:00",
    amount: "12.34"
  });

  assert.equal(result.ok, true);
  assert.equal(result.value.id, "evt_pay");
  assert.equal(result.value.accountId, "acct_1");
  assert.equal(result.value.timestamp, "2026-02-03T09:05:06.000Z");
  assert.equal(result.value.amountCents, 1234);
});

test("shared public fixture reduces to the expected deterministic summary", () => {
  const lines = readFileSync(join(fixturesDir, "public_events.jsonl"), "utf8")
    .split(/\r?\n/)
    .filter((line) => line.trim() !== "");

  const events = lines.map((line) => {
    const parsed = parseEventLine(line);
    assert.equal(parsed.ok, true);
    const normalized = normalizeEvent(parsed.value);
    assert.equal(normalized.ok, true, JSON.stringify(normalized, null, 2));
    return normalized.value;
  });

  const states = reduceAccountState(events);
  const summaries = states.map((state) => summarizeAccount(state, "2026-01-10T00:00:00.000Z"));
  const expected = JSON.parse(readFileSync(join(fixturesDir, "public_expected_summary.json"), "utf8"));

  assert.deepEqual(summaries, expected);
});

test("exportLedgerReport writes stable CSV with a trailing newline", () => {
  const csv = exportLedgerReport([
    {
      accountId: "acct_b",
      status: "closed",
      plan: "free",
      features: [],
      usage: 0,
      usageLimit: 0,
      overLimit: false,
      totalPaidCents: 0,
      couponCode: null,
      couponActive: false,
      closedAt: "2026-01-02T00:00:00.000Z",
      lastEventAt: "2026-01-02T00:00:00.000Z"
    },
    {
      accountId: "acct_a",
      status: "active",
      plan: "starter",
      features: ["dashboard", "exports"],
      usage: 25,
      usageLimit: 1000,
      overLimit: false,
      totalPaidCents: 1200,
      couponCode: "SAVE10",
      couponActive: true,
      closedAt: null,
      lastEventAt: "2026-01-01T00:00:00.000Z"
    }
  ]);

  assert.equal(
    csv,
    [
      "account_id,status,plan,total_paid_cents,usage,usage_limit,over_limit,coupon_code,coupon_active,closed_at,last_event_at",
      "acct_a,active,starter,1200,25,1000,false,SAVE10,true,,2026-01-01T00:00:00.000Z",
      "acct_b,closed,free,0,0,0,false,,false,2026-01-02T00:00:00.000Z,2026-01-02T00:00:00.000Z",
      ""
    ].join("\n")
  );
});
