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
const docsDir = join(here, "..", "docs");
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

function readSemanticsExamples() {
  return JSON.parse(readFileSync(join(fixturesDir, "public_semantics_examples.json"), "utf8"));
}

function normalizeRawEvents(rawEvents) {
  return rawEvents.map((raw) => {
    const normalized = normalizeEvent(raw);
    assert.equal(normalized.ok, true, JSON.stringify(normalized, null, 2));
    return normalized.value;
  });
}

function replayOrder(events) {
  return [...events]
    .sort(
      (a, b) =>
        a.effectiveAt.localeCompare(b.effectiveAt) ||
        a.recordedAt.localeCompare(b.recordedAt) ||
        a.sequence - b.sequence ||
        a.id.localeCompare(b.id)
    )
    .map((event) => event.id);
}

function halfAwayFromZero(value) {
  const numeric = Number(value);
  return Math.sign(numeric) * Math.floor(Math.abs(numeric) + 0.5);
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

test("public semantics examples reference documented hard-mode rule ids", () => {
  const semantics = readFileSync(join(docsDir, "ruleledger_v2_semantics.md"), "utf8");
  const fixture = readSemanticsExamples();
  const concepts = fixture.examples.map((example) => example.concept).sort();

  assert.equal(fixture.semantics_document, "docs/ruleledger_v2_semantics.md");
  assert.deepEqual(concepts, ["account_merge", "bitemporal", "correction_void", "csv_parity", "proration"]);

  for (const example of fixture.examples) {
    assert.ok(example.rule_ids.length > 0, example.id);
    for (const ruleId of example.rule_ids) {
      assert.ok(semantics.includes(`### ${ruleId}:`), `${example.id} references missing ${ruleId}`);
    }
  }
});

test("bitemporal public semantics example has deterministic replay and summary", () => {
  const example = readSemanticsExamples().examples.find((candidate) => candidate.id === "public.bitemporal_late_arrival");
  const events = normalizeRawEvents(example.raw_events);
  const states = reduceAccountState(events);
  const summaries = states.map((state) => summarizeAccount(state, example.as_of));

  assert.deepEqual(replayOrder(events), example.expected_replay_order);
  assert.deepEqual(summaries, [example.expected_summary]);
});

test("correction, void, and merge public semantics examples expose lineage fields", () => {
  const examples = readSemanticsExamples().examples;
  const correction = examples.find((candidate) => candidate.id === "public.correction_void_lineage");
  const normalizedCorrectionEvents = normalizeRawEvents(correction.raw_events);
  const normalizedById = Object.fromEntries(normalizedCorrectionEvents.map((event) => [event.id, event]));

  for (const [eventId, expectedFields] of Object.entries(correction.expected_normalized_fields)) {
    for (const [field, expectedValue] of Object.entries(expectedFields)) {
      assert.deepEqual(normalizedById[eventId][field], expectedValue);
    }
  }

  const merge = examples.find((candidate) => candidate.id === "public.account_merge_lineage");
  const normalizedMerge = normalizeEvent(merge.raw_event);
  assert.equal(normalizedMerge.ok, true);
  for (const [field, expectedValue] of Object.entries(merge.expected_normalized_fields)) {
    assert.deepEqual(normalizedMerge.value[field], expectedValue);
  }
});

test("proration public semantics example documents half-away-from-zero rounding", () => {
  const example = readSemanticsExamples().examples.find(
    (candidate) => candidate.id === "public.proration_half_away_from_zero"
  );

  for (const rounding of example.rounding_examples) {
    assert.equal(halfAwayFromZero(rounding.value), rounding.expected);
  }

  const calc = example.calculation;
  assert.equal(
    halfAwayFromZero((calc.full_period_amount_cents * calc.active_ms) / calc.period_ms),
    calc.expected_prorated_amount_cents
  );
});

test("CSV public semantics example matches stable v2 report contract", () => {
  const example = readSemanticsExamples().examples.find((candidate) => candidate.id === "public.csv_parity_contract");
  const expected = readFileSync(join(fixturesDir, example.expected_report_fixture), "utf8");

  assert.equal(exportLedgerReport(example.summaries), expected);
});
