from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from harness.codex_runner import resolve_npm_bin


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES_DIR = REPO_ROOT / "hidden_tests" / "cases"
TS_TIMEOUT_SECONDS = 20
PY_TIMEOUT_SECONDS = 20
NPM_TIMEOUT_SECONDS = 120
SAFE_ACTUAL_ERROR_REASONS = {"missing_account", "normalization_failed", "unsupported_operation"}


JS_CASE_RUNNER = r"""
import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function stableJson(value) {
  return stableStringify(value);
}

function stableStringify(value) {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(",")}]`;
  }
  const keys = Object.keys(value).sort();
  return `{${keys.map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(",")}}`;
}

function sha256Text(value) {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function pickFunction(mod, names) {
  for (const name of names) {
    if (typeof mod[name] === "function") {
      return { name, fn: mod[name] };
    }
  }
  return null;
}

function viewFromInput(input) {
  const asOf = input.as_of;
  const businessAsOf = input.business_as_of ?? input.as_of;
  const auditAsOf = input.audit_as_of ?? input.as_of;
  return {
    asOf,
    businessAsOf,
    auditAsOf,
    as_of: asOf,
    business_as_of: businessAsOf,
    audit_as_of: auditAsOf
  };
}

function focusSummaries(summaries, accountId) {
  if (accountId === undefined || accountId === null) {
    return summaries;
  }
  return summaries.filter((summary) => summary.accountId === accountId);
}

function normalizeOne(mod, rawEvent, preferV2 = false) {
  const names = preferV2 ? ["normalizeEventV2", "normalizeEvent"] : ["normalizeEvent", "normalizeEventV2"];
  const normalizer = pickFunction(mod, names);
  if (normalizer === null) {
    return { ok: false, error: "unsupported_operation", operation: "normalize_event" };
  }
  return normalizer.fn(rawEvent);
}

function normalizeMany(mod, rawEvents, preferV2 = false) {
  const events = [];
  for (const rawEvent of rawEvents) {
    const normalized = normalizeOne(mod, rawEvent, preferV2);
    if (!normalized || normalized.ok !== true) {
      return { ok: false, error: "normalization_failed", result: normalized };
    }
    events.push(normalized.value);
  }
  return { ok: true, value: events };
}

function pipeline(mod, rawEvents, asOf) {
  const events = normalizeMany(mod, rawEvents);
  if (!events.ok) {
    return events;
  }
  const reducer = pickFunction(mod, ["reduceAccountState"]);
  const summarizer = pickFunction(mod, ["summarizeAccount"]);
  if (reducer === null || summarizer === null) {
    return { ok: false, error: "unsupported_operation", operation: "reduce_and_summarize" };
  }
  const states = reducer.fn(events.value);
  return { ok: true, value: states.map((state) => summarizer.fn(state, asOf)) };
}

function evaluatePipeline(mod, rawEvents, accountId, asOf) {
  const events = normalizeMany(mod, rawEvents);
  if (!events.ok) {
    return events;
  }
  const reducer = pickFunction(mod, ["reduceAccountState"]);
  const evaluator = pickFunction(mod, ["evaluateEntitlements"]);
  if (reducer === null || evaluator === null) {
    return { ok: false, error: "unsupported_operation", operation: "reduce_and_evaluate" };
  }
  const states = reducer.fn(events.value);
  const state = states.find((candidate) => candidate.accountId === accountId);
  if (state === undefined) {
    return { ok: false, error: "missing_account" };
  }
  return { ok: true, value: evaluator.fn(state, asOf) };
}

function reduceV2States(mod, events, input) {
  const reducer = pickFunction(mod, ["reduceAccountStateV2", "reduceAccountState"]);
  if (reducer === null) {
    return { ok: false, error: "unsupported_operation", operation: "v2_reduce_and_summarize" };
  }
  const view = viewFromInput(input);
  const states = reducer.name.endsWith("V2") ? reducer.fn(events, view) : reducer.fn(events);
  return { ok: true, value: states };
}

function summarizeV2State(mod, state, input) {
  const summarizer = pickFunction(mod, ["summarizeAccountV2", "summarizeAccount"]);
  if (summarizer === null) {
    return { ok: false, error: "unsupported_operation", operation: "v2_summarize_account" };
  }
  const view = viewFromInput(input);
  const value = summarizer.name.endsWith("V2")
    ? summarizer.fn(state, view)
    : summarizer.fn(state, view.businessAsOf ?? view.asOf);
  return { ok: true, value };
}

function evaluateV2State(mod, state, input) {
  const evaluator = pickFunction(mod, ["evaluateEntitlementsV2", "evaluateEntitlements"]);
  if (evaluator === null) {
    return { ok: false, error: "unsupported_operation", operation: "v2_evaluate_entitlements" };
  }
  const view = viewFromInput(input);
  const value = evaluator.name.endsWith("V2")
    ? evaluator.fn(state, view)
    : evaluator.fn(state, view.businessAsOf ?? view.asOf);
  return { ok: true, value };
}

function v2SummaryPipeline(mod, input) {
  const events = normalizeMany(mod, input.raw_events, true);
  if (!events.ok) {
    return events;
  }
  const states = reduceV2States(mod, events.value, input);
  if (!states.ok) {
    return states;
  }
  const summaries = [];
  for (const state of states.value) {
    const summary = summarizeV2State(mod, state, input);
    if (!summary.ok) {
      return summary;
    }
    summaries.push(summary.value);
  }
  return { ok: true, value: summaries };
}

function v2EvaluatePipeline(mod, input) {
  const events = normalizeMany(mod, input.raw_events, true);
  if (!events.ok) {
    return events;
  }
  const states = reduceV2States(mod, events.value, input);
  if (!states.ok) {
    return states;
  }
  const state = states.value.find((candidate) => candidate.accountId === input.account_id);
  if (state === undefined) {
    return { ok: false, error: "missing_account" };
  }
  return evaluateV2State(mod, state, input);
}

function exportV2Report(mod, summaries) {
  const reporter = pickFunction(mod, ["exportLedgerReportV2", "exportLedgerReport"]);
  if (reporter === null) {
    return { ok: false, error: "unsupported_operation", operation: "v2_export_report" };
  }
  return { ok: true, value: reporter.fn(summaries) };
}

function calculateV2Proration(mod, input) {
  const calculator = pickFunction(mod, ["calculatePlanChangeProrationV2", "calculatePlanChangeProration"]);
  if (calculator === null) {
    return { ok: false, error: "unsupported_operation", operation: "v2_calculate_proration" };
  }
  if (calculator.fn.length >= 5) {
    return {
      ok: true,
      value: calculator.fn(
        input.old_plan,
        input.new_plan,
        input.period_start,
        input.period_end,
        input.change_effective_at,
        input.quantity ?? 1
      )
    };
  }
  return { ok: true, value: calculator.fn(input) };
}

function v2Metamorphic(mod, input) {
  const baseline = v2SummaryPipeline(mod, { ...input, raw_events: input.baseline });
  if (!baseline.ok) {
    return baseline;
  }
  const baselineFocus = focusSummaries(baseline.value, input.target_account_id);
  const variants = [];
  for (const variant of input.variants) {
    const result = v2SummaryPipeline(mod, { ...input, raw_events: variant.raw_events });
    if (!result.ok) {
      variants.push({ name: variant.name, value: result, equivalent: false });
      continue;
    }
    const focus = focusSummaries(result.value, input.target_account_id);
    variants.push({
      name: variant.name,
      value: focus,
      equivalent: stableJson(focus) === stableJson(baselineFocus)
    });
  }
  return { ok: true, value: { baseline: baselineFocus, variants } };
}

function v2PerformanceDigest(mod, input) {
  const summaries = v2SummaryPipeline(mod, input);
  if (!summaries.ok) {
    return summaries;
  }
  const report = exportV2Report(mod, summaries.value);
  if (!report.ok) {
    return report;
  }
  return {
    ok: true,
    value: {
      eventCount: input.raw_events.length,
      summaryCount: summaries.value.length,
      firstAccountId: summaries.value.length > 0 ? summaries.value[0].accountId : null,
      lastAccountId: summaries.value.length > 0 ? summaries.value[summaries.value.length - 1].accountId : null,
      totalUsage: summaries.value.reduce((total, summary) => total + summary.usage, 0),
      totalPaidCents: summaries.value.reduce((total, summary) => total + summary.totalPaidCents, 0),
      summarySha256: sha256Text(stableJson(summaries.value)),
      reportSha256: sha256Text(report.value)
    }
  };
}

function v2ParityPayload(mod, input) {
  const summaries = v2SummaryPipeline(mod, input);
  if (!summaries.ok) {
    return summaries;
  }
  const report = exportV2Report(mod, summaries.value);
  if (!report.ok) {
    return report;
  }
  return { ok: true, value: { summaries: summaries.value, report: report.value } };
}

async function main() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  const payload = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  const moduleUrl = pathToFileURL(resolve(payload.worktree, "dist", "index.js")).href;
  const mod = await import(`${moduleUrl}?hiddenRunner=${Date.now()}-${Math.random()}`);
  const operation = payload.case.operation;
  const input = payload.case.input;

  if (operation === "parse_line") {
    return mod.parseEventLine(input.line);
  }
  if (operation === "normalize_event") {
    return normalizeOne(mod, input.raw_event);
  }
  if (operation === "reduce_and_summarize") {
    const result = pipeline(mod, input.raw_events, input.as_of);
    return result.ok ? result.value : result;
  }
  if (operation === "reduce_and_evaluate") {
    const result = evaluatePipeline(mod, input.raw_events, input.account_id, input.as_of);
    return result.ok ? result.value : result;
  }
  if (operation === "export_report") {
    return mod.exportLedgerReport(input.summaries);
  }
  if (operation === "immutability_repeatability") {
    const rawEvents = deepClone(input.raw_events);
    const before = stableJson(rawEvents);
    const first = pipeline(mod, rawEvents, input.as_of);
    const after = stableJson(rawEvents);
    const second = pipeline(mod, deepClone(input.raw_events), input.as_of);
    return {
      summaries: first.ok ? first.value : first,
      repeatable: stableJson(first) === stableJson(second),
      inputUnchanged: before === after
    };
  }
  if (operation === "v2_reduce_and_summarize") {
    const result = v2SummaryPipeline(mod, input);
    return result.ok ? result.value : result;
  }
  if (operation === "v2_reduce_and_evaluate") {
    const result = v2EvaluatePipeline(mod, input);
    return result.ok ? result.value : result;
  }
  if (operation === "v2_export_report") {
    const result = exportV2Report(mod, input.summaries);
    return result.ok ? result.value : result;
  }
  if (operation === "v2_calculate_proration") {
    const result = calculateV2Proration(mod, input);
    return result.ok ? result.value : result;
  }
  if (operation === "v2_metamorphic") {
    const result = v2Metamorphic(mod, input);
    return result.ok ? result.value : result;
  }
  if (operation === "v2_performance_digest") {
    const result = v2PerformanceDigest(mod, input);
    return result.ok ? result.value : result;
  }
  if (operation === "v2_parity") {
    const result = v2ParityPayload(mod, input);
    return result.ok ? result.value : result;
  }
  return { ok: false, error: "unsupported_operation", operation };
}

try {
  const value = await main();
  process.stdout.write(JSON.stringify({ ok: true, value }));
} catch (error) {
  process.stdout.write(JSON.stringify({
    ok: false,
    error: "exception",
    message: error instanceof Error ? error.message : String(error)
  }));
}
"""


PY_CASE_RUNNER = r"""
from __future__ import annotations

import copy
import hashlib
import importlib
import inspect
import json
import sys


def deep_clone(value):
    return json.loads(json.dumps(value))


def stable_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_module(worktree):
    sys.path.insert(0, worktree)
    for name in list(sys.modules):
        if name == "ruleledger" or name.startswith("ruleledger."):
            del sys.modules[name]
    return importlib.import_module("ruleledger.engine")


def pick_function(mod, names):
    for name in names:
        value = getattr(mod, name, None)
        if callable(value):
            return name, value
    return None, None


def accepts_positional(function, count):
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return True
    positional = 0
    for parameter in signature.parameters.values():
        if parameter.kind == inspect.Parameter.VAR_POSITIONAL:
            return True
        if parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            positional += 1
    return positional >= count


def view_from_input(input_payload):
    as_of = input_payload.get("as_of")
    requested_business_as_of = input_payload.get("business_as_of")
    requested_audit_as_of = input_payload.get("audit_as_of")
    business_as_of = requested_business_as_of if requested_business_as_of is not None else as_of
    audit_as_of = requested_audit_as_of if requested_audit_as_of is not None else as_of
    return {
        "asOf": as_of,
        "businessAsOf": business_as_of,
        "auditAsOf": audit_as_of,
        "as_of": as_of,
        "business_as_of": business_as_of,
        "audit_as_of": audit_as_of,
    }


def focus_summaries(summaries, account_id):
    if account_id is None:
        return summaries
    return [summary for summary in summaries if summary.get("accountId") == account_id]


def normalize_one(mod, raw_event, prefer_v2=False):
    names = ("normalize_event_v2", "normalize_event") if prefer_v2 else ("normalize_event", "normalize_event_v2")
    _, normalizer = pick_function(mod, names)
    if normalizer is None:
        return {"ok": False, "error": "unsupported_operation", "operation": "normalize_event"}
    return normalizer(raw_event)


def normalize_many(mod, raw_events, prefer_v2=False):
    events = []
    for raw_event in raw_events:
        normalized = normalize_one(mod, raw_event, prefer_v2)
        if not normalized or normalized.get("ok") is not True:
            return {"ok": False, "error": "normalization_failed", "result": normalized}
        events.append(normalized["value"])
    return {"ok": True, "value": events}


def pipeline(mod, raw_events, as_of):
    events = normalize_many(mod, raw_events)
    if not events.get("ok"):
        return events
    _, reducer = pick_function(mod, ("reduce_account_state",))
    _, summarizer = pick_function(mod, ("summarize_account",))
    if reducer is None or summarizer is None:
        return {"ok": False, "error": "unsupported_operation", "operation": "reduce_and_summarize"}
    states = reducer(events["value"])
    return {"ok": True, "value": [summarizer(state, as_of) for state in states]}


def evaluate_pipeline(mod, raw_events, account_id, as_of):
    events = normalize_many(mod, raw_events)
    if not events.get("ok"):
        return events
    _, reducer = pick_function(mod, ("reduce_account_state",))
    _, evaluator = pick_function(mod, ("evaluate_entitlements",))
    if reducer is None or evaluator is None:
        return {"ok": False, "error": "unsupported_operation", "operation": "reduce_and_evaluate"}
    states = reducer(events["value"])
    for state in states:
        if state.get("accountId") == account_id:
            return {"ok": True, "value": evaluator(state, as_of)}
    return {"ok": False, "error": "missing_account"}


def reduce_v2_states(mod, events, input_payload):
    name, reducer = pick_function(mod, ("reduce_account_state_v2", "reduce_account_state"))
    if reducer is None:
        return {"ok": False, "error": "unsupported_operation", "operation": "v2_reduce_and_summarize"}
    view = view_from_input(input_payload)
    states = reducer(events, view) if name.endswith("_v2") and accepts_positional(reducer, 2) else reducer(events)
    return {"ok": True, "value": states}


def summarize_v2_state(mod, state, input_payload):
    name, summarizer = pick_function(mod, ("summarize_account_v2", "summarize_account"))
    if summarizer is None:
        return {"ok": False, "error": "unsupported_operation", "operation": "v2_summarize_account"}
    view = view_from_input(input_payload)
    value = (
        summarizer(state, view)
        if name.endswith("_v2") and accepts_positional(summarizer, 2)
        else summarizer(state, view["businessAsOf"] if view["businessAsOf"] is not None else view["asOf"])
    )
    return {"ok": True, "value": value}


def evaluate_v2_state(mod, state, input_payload):
    name, evaluator = pick_function(mod, ("evaluate_entitlements_v2", "evaluate_entitlements"))
    if evaluator is None:
        return {"ok": False, "error": "unsupported_operation", "operation": "v2_evaluate_entitlements"}
    view = view_from_input(input_payload)
    value = (
        evaluator(state, view)
        if name.endswith("_v2") and accepts_positional(evaluator, 2)
        else evaluator(state, view["businessAsOf"] if view["businessAsOf"] is not None else view["asOf"])
    )
    return {"ok": True, "value": value}


def v2_summary_pipeline(mod, input_payload):
    events = normalize_many(mod, input_payload["raw_events"], prefer_v2=True)
    if not events.get("ok"):
        return events
    states = reduce_v2_states(mod, events["value"], input_payload)
    if not states.get("ok"):
        return states
    summaries = []
    for state in states["value"]:
        summary = summarize_v2_state(mod, state, input_payload)
        if not summary.get("ok"):
            return summary
        summaries.append(summary["value"])
    return {"ok": True, "value": summaries}


def v2_evaluate_pipeline(mod, input_payload):
    events = normalize_many(mod, input_payload["raw_events"], prefer_v2=True)
    if not events.get("ok"):
        return events
    states = reduce_v2_states(mod, events["value"], input_payload)
    if not states.get("ok"):
        return states
    for state in states["value"]:
        if state.get("accountId") == input_payload["account_id"]:
            return evaluate_v2_state(mod, state, input_payload)
    return {"ok": False, "error": "missing_account"}


def export_v2_report(mod, summaries):
    _, reporter = pick_function(mod, ("export_ledger_report_v2", "export_ledger_report"))
    if reporter is None:
        return {"ok": False, "error": "unsupported_operation", "operation": "v2_export_report"}
    return {"ok": True, "value": reporter(summaries)}


def calculate_v2_proration(mod, input_payload):
    _, calculator = pick_function(mod, ("calculate_plan_change_proration_v2", "calculate_plan_change_proration"))
    if calculator is None:
        return {"ok": False, "error": "unsupported_operation", "operation": "v2_calculate_proration"}
    if accepts_positional(calculator, 6):
        return {
            "ok": True,
            "value": calculator(
                input_payload["old_plan"],
                input_payload["new_plan"],
                input_payload["period_start"],
                input_payload["period_end"],
                input_payload["change_effective_at"],
                input_payload.get("quantity", 1),
            ),
        }
    if accepts_positional(calculator, 5):
        return {
            "ok": True,
            "value": calculator(
                input_payload["old_plan"],
                input_payload["new_plan"],
                input_payload["period_start"],
                input_payload["period_end"],
                input_payload["change_effective_at"],
            ),
        }
    return {"ok": True, "value": calculator(input_payload)}


def v2_metamorphic(mod, input_payload):
    baseline = v2_summary_pipeline(mod, {**input_payload, "raw_events": input_payload["baseline"]})
    if not baseline.get("ok"):
        return baseline
    baseline_focus = focus_summaries(baseline["value"], input_payload.get("target_account_id"))
    variants = []
    for variant in input_payload["variants"]:
        result = v2_summary_pipeline(mod, {**input_payload, "raw_events": variant["raw_events"]})
        if not result.get("ok"):
            variants.append({"name": variant["name"], "value": result, "equivalent": False})
            continue
        focus = focus_summaries(result["value"], input_payload.get("target_account_id"))
        variants.append(
            {
                "name": variant["name"],
                "value": focus,
                "equivalent": stable_json(focus) == stable_json(baseline_focus),
            }
        )
    return {"ok": True, "value": {"baseline": baseline_focus, "variants": variants}}


def v2_performance_digest(mod, input_payload):
    summaries = v2_summary_pipeline(mod, input_payload)
    if not summaries.get("ok"):
        return summaries
    report = export_v2_report(mod, summaries["value"])
    if not report.get("ok"):
        return report
    return {
        "ok": True,
        "value": {
            "eventCount": len(input_payload["raw_events"]),
            "summaryCount": len(summaries["value"]),
            "firstAccountId": summaries["value"][0]["accountId"] if summaries["value"] else None,
            "lastAccountId": summaries["value"][-1]["accountId"] if summaries["value"] else None,
            "totalUsage": sum(summary["usage"] for summary in summaries["value"]),
            "totalPaidCents": sum(summary["totalPaidCents"] for summary in summaries["value"]),
            "summarySha256": sha256_text(stable_json(summaries["value"])),
            "reportSha256": sha256_text(report["value"]),
        },
    }


def v2_parity_payload(mod, input_payload):
    summaries = v2_summary_pipeline(mod, input_payload)
    if not summaries.get("ok"):
        return summaries
    report = export_v2_report(mod, summaries["value"])
    if not report.get("ok"):
        return report
    return {"ok": True, "value": {"summaries": summaries["value"], "report": report["value"]}}


def main():
    payload = json.load(sys.stdin)
    mod = load_module(payload["worktree"])
    case = payload["case"]
    operation = case["operation"]
    input_payload = case["input"]

    if operation == "parse_line":
        return mod.parse_event_line(input_payload["line"])
    if operation == "normalize_event":
        return normalize_one(mod, input_payload["raw_event"])
    if operation == "reduce_and_summarize":
        result = pipeline(mod, input_payload["raw_events"], input_payload.get("as_of"))
        return result["value"] if result.get("ok") else result
    if operation == "reduce_and_evaluate":
        result = evaluate_pipeline(
            mod,
            input_payload["raw_events"],
            input_payload["account_id"],
            input_payload.get("as_of"),
        )
        return result["value"] if result.get("ok") else result
    if operation == "export_report":
        return mod.export_ledger_report(input_payload["summaries"])
    if operation == "immutability_repeatability":
        raw_events = deep_clone(input_payload["raw_events"])
        before = stable_json(raw_events)
        first = pipeline(mod, raw_events, input_payload.get("as_of"))
        after = stable_json(raw_events)
        second = pipeline(mod, deep_clone(input_payload["raw_events"]), input_payload.get("as_of"))
        return {
            "summaries": first["value"] if first.get("ok") else first,
            "repeatable": stable_json(first) == stable_json(second),
            "inputUnchanged": before == after,
        }
    if operation == "v2_reduce_and_summarize":
        result = v2_summary_pipeline(mod, input_payload)
        return result["value"] if result.get("ok") else result
    if operation == "v2_reduce_and_evaluate":
        result = v2_evaluate_pipeline(mod, input_payload)
        return result["value"] if result.get("ok") else result
    if operation == "v2_export_report":
        result = export_v2_report(mod, input_payload["summaries"])
        return result["value"] if result.get("ok") else result
    if operation == "v2_calculate_proration":
        result = calculate_v2_proration(mod, input_payload)
        return result["value"] if result.get("ok") else result
    if operation == "v2_metamorphic":
        result = v2_metamorphic(mod, input_payload)
        return result["value"] if result.get("ok") else result
    if operation == "v2_performance_digest":
        result = v2_performance_digest(mod, input_payload)
        return result["value"] if result.get("ok") else result
    if operation == "v2_parity":
        result = v2_parity_payload(mod, input_payload)
        return result["value"] if result.get("ok") else result
    return {"ok": False, "error": "unsupported_operation", "operation": operation}


try:
    print(json.dumps({"ok": True, "value": main()}, separators=(",", ":")), end="")
except Exception as exc:
    print(json.dumps({"ok": False, "error": "exception", "message": str(exc)}, separators=(",", ":")), end="")
"""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    worktree = args.worktree.resolve()
    out_path = args.out.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not worktree.exists() or not worktree.is_dir():
        print(f"worktree does not exist: {worktree}", file=sys.stderr)
        write_infrastructure_failure(out_path, worktree, "missing_worktree")
        return 2

    try:
        manifest, cases = load_cases(args.cases_dir.resolve())
    except Exception as exc:
        print(f"failed to load hidden cases: {exc}", file=sys.stderr)
        write_infrastructure_failure(out_path, worktree, "case_load_failed")
        return 2

    started_at = iso_now()
    try:
        with tempfile.TemporaryDirectory(prefix="ruleledger-hidden-") as temp_dir:
            temp_path = Path(temp_dir)
            js_runner = temp_path / "ts_case_runner.mjs"
            py_runner = temp_path / "py_case_runner.py"
            js_runner.write_text(JS_CASE_RUNNER, encoding="utf-8")
            py_runner.write_text(PY_CASE_RUNNER, encoding="utf-8")

            ts_setup = setup_typescript(worktree, install=not args.no_install)
            results = []

            for case in cases:
                languages = case.get("languages", [])
                if "parity" in languages:
                    results.append(run_parity_case(case, worktree, js_runner, py_runner, ts_setup))
                    continue

                if "typescript" in languages:
                    results.append(run_language_case("typescript", case, worktree, js_runner, ts_setup))
                if "python" in languages:
                    results.append(run_language_case("python", case, worktree, py_runner, None))
    except Exception as exc:
        print(f"hidden runner infrastructure failure: {exc}", file=sys.stderr)
        write_infrastructure_failure(out_path, worktree, "runner_infrastructure_failed")
        return 2

    finished_at = iso_now()
    payload = build_result_payload(
        manifest=manifest,
        worktree=worktree,
        started_at=started_at,
        finished_at=finished_at,
        results=results,
        ts_setup=ts_setup,
    )
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RuleLedger hidden tests against an implementation worktree.")
    parser.add_argument("--worktree", required=True, type=Path, help="Copied implementation workspace to score.")
    parser.add_argument("--out", required=True, type=Path, help="Path to write hidden-results.json.")
    parser.add_argument("--cases-dir", default=DEFAULT_CASES_DIR, type=Path, help="Hidden cases directory.")
    parser.add_argument("--no-install", action="store_true", help="Do not run npm ci if TypeScript dependencies are missing.")
    return parser.parse_args(argv)


def load_cases(cases_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = cases_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = []
    manifest_files = set(manifest.get("files", {}))
    actual_files = {path.name for path in cases_dir.glob("*.json") if path.name != "manifest.json"}

    missing = sorted(manifest_files - actual_files)
    unexpected = sorted(actual_files - manifest_files)
    if missing:
        raise ValueError(f"case files missing from directory: {', '.join(missing)}")
    if unexpected:
        raise ValueError(f"case files missing from manifest: {', '.join(unexpected)}")

    for filename in sorted(manifest_files):
        path = cases_dir / filename
        expected_file = manifest["files"][filename]
        actual_hash = sha256(path)
        if actual_hash != expected_file.get("sha256"):
            raise ValueError(f"case file hash mismatch: {path.name}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        for case in payload.get("cases", []):
            case = dict(case)
            case["source_file"] = path.name
            cases.append(case)

    if not cases:
        raise ValueError(f"no hidden cases found in {cases_dir}")

    return manifest, cases


def setup_typescript(worktree: Path, install: bool) -> dict[str, Any]:
    if not (worktree / "package.json").exists():
        return {"ok": False, "reason": "missing_package_json"}

    npm = resolve_npm_bin()
    if npm is None:
        return {"ok": False, "reason": "missing_npm"}

    if install and not typescript_dependency_present(worktree) and (worktree / "package-lock.json").exists():
        install_result = run_command([npm, "ci"], cwd=worktree, timeout=NPM_TIMEOUT_SECONDS)
        if install_result["returncode"] != 0:
            return {
                "ok": False,
                "reason": "npm_ci_failed",
                "returncode": install_result["returncode"],
                "stderr_tail": tail(install_result["stderr"]),
            }

    build_result = run_command([npm, "run", "build"], cwd=worktree, timeout=NPM_TIMEOUT_SECONDS)
    if build_result["returncode"] != 0:
        return {
            "ok": False,
            "reason": "typescript_build_failed",
            "returncode": build_result["returncode"],
            "stderr_tail": tail(build_result["stderr"]),
        }

    if not (worktree / "dist" / "index.js").exists():
        return {"ok": False, "reason": "missing_dist_index"}

    return {"ok": True}


def typescript_dependency_present(worktree: Path) -> bool:
    if (worktree / "node_modules" / ".bin" / "tsc").exists():
        return True
    if (worktree / "node_modules" / ".bin" / "tsc.cmd").exists():
        return True
    return False


def run_language_case(
    language: str,
    case: dict[str, Any],
    worktree: Path,
    runner: Path,
    setup: dict[str, Any] | None,
) -> dict[str, Any]:
    points = float(case.get("points", 1))

    if setup is not None and not setup.get("ok"):
        return case_result(case, language, "error", 0.0, points, setup.get("reason", "language_setup_failed"))

    actual = execute_case(language, case, worktree, runner)
    if not actual.get("ok"):
        reason = actual.get("error", "execution_failed")
        status = "failed" if reason == "timeout" else "error"
        return case_result(case, language, status, 0.0, points, reason)

    passed, reason = compare_case(case, actual.get("value"))
    return case_result(case, language, "passed" if passed else "failed", points if passed else 0.0, points, reason)


def run_parity_case(
    case: dict[str, Any],
    worktree: Path,
    js_runner: Path,
    py_runner: Path,
    ts_setup: dict[str, Any],
) -> dict[str, Any]:
    points = float(case.get("points", 1))
    if not ts_setup.get("ok"):
        return case_result(case, "parity", "error", 0.0, points, ts_setup.get("reason", "typescript_setup_failed"))

    ts_actual = execute_case("typescript", case, worktree, js_runner)
    py_actual = execute_case("python", case, worktree, py_runner)
    if not ts_actual.get("ok"):
        reason = "typescript_timeout" if ts_actual.get("error") == "timeout" else "typescript_execution_failed"
        status = "failed" if ts_actual.get("error") == "timeout" else "error"
        return case_result(case, "parity", status, 0.0, points, reason)
    if not py_actual.get("ok"):
        reason = "python_timeout" if py_actual.get("error") == "timeout" else "python_execution_failed"
        status = "failed" if py_actual.get("error") == "timeout" else "error"
        return case_result(case, "parity", status, 0.0, points, reason)

    if canonical(ts_actual.get("value")) != canonical(py_actual.get("value")):
        return case_result(case, "parity", "failed", 0.0, points, "parity_mismatch")

    if "expected" in case:
        passed, reason = compare_case(case, ts_actual.get("value"))
        return case_result(case, "parity", "passed" if passed else "failed", points if passed else 0.0, points, reason)

    error_reason = sanitized_actual_error_reason(ts_actual.get("value"))
    if error_reason is not None:
        return case_result(case, "parity", "failed", 0.0, points, error_reason)

    return case_result(case, "parity", "passed", points, points, "ok")


def execute_case(language: str, case: dict[str, Any], worktree: Path, runner: Path) -> dict[str, Any]:
    command = ["node", str(runner)] if language == "typescript" else [sys.executable, str(runner)]
    timeout = resolve_case_timeout(case, language)
    payload = json.dumps({"worktree": str(worktree), "case": strip_runner_metadata(case)}, separators=(",", ":"))

    try:
        completed = subprocess.run(
            command,
            cwd=runner.parent,
            env=runner_env(),
            input=payload,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except OSError as exc:
        return {"ok": False, "error": f"process_error:{exc.__class__.__name__}"}

    if completed.returncode != 0:
        return {"ok": False, "error": "nonzero_exit", "stderr_tail": tail(completed.stderr)}

    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid_runner_json"}


def strip_runner_metadata(case: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in case.items()
        if key
        not in {
            "id",
            "expected",
            "source_file",
            "category",
            "languages",
            "points",
            "rule_ids",
            "timeout_seconds",
            "match",
        }
    }


def resolve_case_timeout(case: dict[str, Any], language: str) -> int | float:
    default = TS_TIMEOUT_SECONDS if language == "typescript" else PY_TIMEOUT_SECONDS
    metadata = case.get("timeout_seconds")
    if isinstance(metadata, (int, float)) and not isinstance(metadata, bool) and metadata > 0:
        return metadata
    if isinstance(metadata, dict):
        value = metadata.get(language)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            return value
    return default


def compare_case(case: dict[str, Any], actual: Any) -> tuple[bool, str]:
    expected = case.get("expected")
    match = case.get("match", "exact")

    if match == "normalize_error":
        if not isinstance(actual, dict):
            return False, "actual_not_object"
        if actual.get("ok") is not False:
            return False, "expected_normalize_failure"
        if actual.get("error") != expected.get("error"):
            return False, "normalize_error_code_mismatch"
        actual_issues = sorted(actual.get("issues", []))
        expected_issues = sorted(expected.get("issues", []))
        if actual_issues != expected_issues:
            return False, "normalize_issues_mismatch"
        return True, "ok"

    if canonical(actual) == canonical(expected):
        return True, "ok"

    error_reason = sanitized_actual_error_reason(actual)
    if error_reason is not None:
        return False, error_reason

    return False, "output_mismatch"


def sanitized_actual_error_reason(actual: Any) -> str | None:
    if not isinstance(actual, dict) or actual.get("ok") is not False or not isinstance(actual.get("error"), str):
        return None
    reason = actual["error"]
    return reason if reason in SAFE_ACTUAL_ERROR_REASONS else "operation_failed"


def case_result(
    case: dict[str, Any],
    language: str,
    status: str,
    earned: float,
    possible: float,
    reason: str,
) -> dict[str, Any]:
    return {
        "id": opaque_case_id(case),
        "category": case["category"],
        "language": language,
        "status": status,
        "points_earned": earned,
        "points_possible": possible,
        "reason": reason,
    }


def build_result_payload(
    manifest: dict[str, Any],
    worktree: Path,
    started_at: str,
    finished_at: str,
    results: list[dict[str, Any]],
    ts_setup: dict[str, Any],
) -> dict[str, Any]:
    categories = summarize_by(results, "category")
    languages = summarize_by(results, "language")
    weights = manifest.get("category_weights", {})
    weighted_score = compute_weighted_score(categories, weights)

    passed = sum(1 for result in results if result["status"] == "passed")
    failed = sum(1 for result in results if result["status"] == "failed")
    errors = sum(1 for result in results if result["status"] == "error")
    points_earned = sum(result["points_earned"] for result in results)
    points_possible = sum(result["points_possible"] for result in results)

    return {
        "schema_version": 1,
        "seed": manifest.get("seed"),
        "started_at": started_at,
        "finished_at": finished_at,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "points_earned": round(points_earned, 6),
            "points_possible": round(points_possible, 6),
            "point_score": round(points_earned / points_possible, 6) if points_possible else 0.0,
            "score": round(weighted_score, 6),
        },
        "categories": categories,
        "languages": languages,
        "typescript_setup": ts_setup,
        "cases": results,
    }


def write_infrastructure_failure(out_path: Path, worktree: Path, reason: str) -> None:
    now = iso_now()
    payload = {
        "schema_version": 1,
        "started_at": now,
        "finished_at": now,
        "summary": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 1,
            "points_earned": 0.0,
            "points_possible": 0.0,
            "point_score": 0.0,
            "score": 0.0,
        },
        "categories": {},
        "languages": {},
        "typescript_setup": {"ok": False, "reason": reason},
        "cases": [],
        "infrastructure_error": reason,
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def summarize_by(results: list[dict[str, Any]], key: str) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for result in results:
        name = result[key]
        bucket = summary.setdefault(
            name,
            {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "points_earned": 0.0,
                "points_possible": 0.0,
                "score": 0.0,
            },
        )
        bucket["total"] += 1
        status_key = "errors" if result["status"] == "error" else result["status"]
        bucket[status_key] += 1
        bucket["points_earned"] += result["points_earned"]
        bucket["points_possible"] += result["points_possible"]

    for bucket in summary.values():
        possible = bucket["points_possible"]
        bucket["points_earned"] = round(bucket["points_earned"], 6)
        bucket["points_possible"] = round(possible, 6)
        bucket["score"] = round(bucket["points_earned"] / possible, 6) if possible else 0.0

    return summary


def compute_weighted_score(categories: dict[str, Any], weights: dict[str, Any]) -> float:
    if not weights:
        earned = sum(bucket["points_earned"] for bucket in categories.values())
        possible = sum(bucket["points_possible"] for bucket in categories.values())
        return earned / possible if possible else 0.0

    total = 0.0
    weight_sum = 0.0
    for category, weight in weights.items():
        numeric_weight = float(weight)
        weight_sum += numeric_weight
        total += categories.get(category, {"score": 0.0})["score"] * numeric_weight
    return total / weight_sum if weight_sum else 0.0


def run_command(command: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=runner_env(),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": -1,
            "stdout": exc.stdout or "",
            "stderr": "timeout",
        }
    except OSError as exc:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"{exc.__class__.__name__}: {exc}",
        }

    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def opaque_case_id(case: dict[str, Any]) -> str:
    raw = str(case.get("id", "unknown")).encode("utf-8", errors="replace")
    return "case-" + hashlib.sha256(raw).hexdigest()[:12]


def runner_env() -> dict[str, str]:
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTEST_CURRENT_TEST"):
        env.pop(name, None)
    return env


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def tail(text: str, limit: int = 1200) -> str:
    return text[-limit:] if len(text) > limit else text


if __name__ == "__main__":
    raise SystemExit(main())
