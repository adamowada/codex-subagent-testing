from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import sys

from harness.codex_runner import (
    command_for_display,
    extract_final_response,
    resolve_codex_bin,
    resolve_npm_bin,
    run_process_to_files,
)
from harness.hidden_runner import (
    JS_CASE_RUNNER,
    PY_CASE_RUNNER,
    PY_TIMEOUT_SECONDS,
    TS_TIMEOUT_SECONDS,
    build_result_payload,
    canonical,
    compare_case,
    run_command as run_hidden_command,
    run_language_case,
    run_parity_case,
    resolve_case_timeout,
    strip_runner_metadata,
)
from harness.orchestrator import (
    _public_tests_have_launch_errors,
    archive_failed_phase_artifacts,
    archive_phase_artifacts,
    phase_stale_after,
    run_public_tests,
)
from harness.preflight import _check_codex_version


def test_resolve_codex_bin_prefers_absolute_codex_bin(tmp_path: Path) -> None:
    executable = _fake_executable(tmp_path, "custom-codex")

    resolved = resolve_codex_bin({"CODEX_BIN": str(executable), "PATH": ""})

    assert resolved == str(executable)


def test_resolve_codex_bin_uses_supplied_path_for_command_names(tmp_path: Path) -> None:
    executable = _fake_executable(tmp_path, "codex")

    resolved = resolve_codex_bin({"CODEX_BIN": "codex", "PATH": str(tmp_path)})

    assert Path(resolved or "").resolve() == executable.resolve()


def test_resolve_npm_bin_prefers_windows_cmd_shim(tmp_path: Path) -> None:
    npm = _fake_executable(tmp_path, "npm")
    (tmp_path / "npm.ps1").write_text("Write-Output fake npm\n", encoding="utf-8")

    resolved = resolve_npm_bin({"PATH": str(tmp_path)})

    assert Path(resolved or "").resolve() == npm.resolve()


def test_resolve_npm_bin_honors_override(tmp_path: Path) -> None:
    custom = _fake_executable(tmp_path, "custom-npm")

    resolved = resolve_npm_bin({"NPM_BIN": str(custom), "PATH": ""})

    assert resolved == str(custom)


def test_command_for_display_masks_prompt() -> None:
    command = ["codex", "exec", "--json", "secret prompt"]

    assert command_for_display(command) == ["codex", "exec", "--json", "<prompt>"]


def test_run_process_to_files_captures_success_stdout_stderr_and_final_json(tmp_path: Path) -> None:
    stdout_path = tmp_path / "events.jsonl"
    stderr_path = tmp_path / "stderr.log"
    payload = {"status": "success", "changed_files": []}
    script = (
        "import json, sys; "
        "print(json.dumps({'type': 'message', 'message': {'content': "
        "[{'text': 'done ' + json.dumps("
        + repr(payload)
        + ")}]}})); "
        "print('warning from fake codex', file=sys.stderr)"
    )

    result = run_process_to_files(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout_seconds=10,
        command_display=["python", "-c", "<script>"],
    )
    final = extract_final_response(stdout_path)
    stderr = stderr_path.read_text(encoding="utf-8")

    assert result.returncode == 0
    assert not result.timed_out
    assert "warning from fake codex" in stderr
    assert final["parsed"]
    assert final["value"]["status"] == "success"


def test_hidden_runner_command_decodes_utf8_output_on_windows(tmp_path: Path) -> None:
    script = "import sys; sys.stdout.buffer.write('unicode: \\u271d'.encode('utf-8'))"

    result = run_hidden_command([sys.executable, "-c", script], tmp_path, timeout=15)

    assert result["returncode"] == 0
    assert "unicode: \u271d" in result["stdout"]


def test_hidden_runner_result_payload_summarizes_error_cases(tmp_path: Path) -> None:
    payload = build_result_payload(
        manifest={"seed": 1, "category_weights": {"normalization": 1.0}},
        worktree=tmp_path,
        started_at="2026-01-01T00:00:00.000Z",
        finished_at="2026-01-01T00:00:01.000Z",
        results=[
            {
                "id": "case-000000000001",
                "category": "normalization",
                "language": "typescript",
                "status": "error",
                "points_earned": 0.0,
                "points_possible": 1.0,
                "reason": "typescript_setup_failed",
            }
        ],
        ts_setup={"ok": False, "reason": "typescript_setup_failed"},
    )

    assert payload["summary"]["errors"] == 1
    assert payload["categories"]["normalization"]["errors"] == 1
    assert payload["languages"]["typescript"]["errors"] == 1
    assert payload["summary"]["score"] == 0.0


def test_hidden_runner_strips_rule_ids_from_language_payload() -> None:
    assert strip_runner_metadata(
        {
            "id": "case.private",
            "category": "normalization",
            "languages": ["typescript"],
            "points": 1,
            "rule_ids": ["BT-001"],
            "timeout_seconds": {"typescript": 45, "python": 45},
            "match": "exact",
            "operation": "normalize_event",
            "input": {"raw_event": {"id": "evt"}},
            "expected": {"ok": True},
        }
    ) == {
        "operation": "normalize_event",
        "input": {"raw_event": {"id": "evt"}},
    }


def test_hidden_runner_resolves_case_level_timeouts() -> None:
    assert resolve_case_timeout({}, "typescript") == TS_TIMEOUT_SECONDS
    assert resolve_case_timeout({}, "python") == PY_TIMEOUT_SECONDS
    assert resolve_case_timeout({"timeout_seconds": 45}, "typescript") == 45
    assert resolve_case_timeout({"timeout_seconds": 0.5}, "python") == 0.5
    assert resolve_case_timeout({"timeout_seconds": {"typescript": 35, "python": 40}}, "typescript") == 35
    assert resolve_case_timeout({"timeout_seconds": {"typescript": 35, "python": 40}}, "python") == 40
    assert resolve_case_timeout({"timeout_seconds": {"typescript": 0, "python": "slow"}}, "typescript") == TS_TIMEOUT_SECONDS


def test_hidden_runner_timeout_is_scored_case_failure(tmp_path: Path) -> None:
    runner = tmp_path / "slow_case_runner.py"
    runner.write_text(
        "import json, sys, time\n"
        "json.load(sys.stdin)\n"
        "time.sleep(5)\n"
        "print('{\"ok\":true,\"value\":null}', end='')\n",
        encoding="utf-8",
    )
    case = {
        "id": "performance.timeout.private",
        "category": "performance",
        "languages": ["python"],
        "points": 2.0,
        "operation": "v2_performance_digest",
        "timeout_seconds": {"python": 1},
        "input": {"raw_events": []},
        "expected": {},
    }

    result = run_language_case("python", case, tmp_path, runner, None)

    assert result["status"] == "failed"
    assert result["reason"] == "timeout"
    assert result["points_earned"] == 0.0
    assert result["points_possible"] == 2.0
    assert result["id"].startswith("case-")


def test_hidden_runner_executes_v2_operations_in_synthetic_worktree(tmp_path: Path) -> None:
    worktree = _write_synthetic_v2_worktree(tmp_path)
    js_runner, py_runner = _write_hidden_case_runners(tmp_path)
    raw_events = _synthetic_raw_events()
    summaries = [_synthetic_summary()]
    report = _synthetic_report(summaries)
    as_of = "2026-01-20T00:00:00Z"
    view_input = {
        "as_of": as_of,
        "business_as_of": "2026-01-18T00:00:00Z",
        "audit_as_of": "2026-01-19T00:00:00Z",
    }
    proration = {
        "oldPlan": "starter",
        "newPlan": "pro",
        "quantity": 2,
        "netAdjustmentCents": 42,
    }

    cases = [
        (
            "v2_reduce_and_summarize",
            {"raw_events": raw_events, **view_input},
            summaries,
        ),
        (
            "v2_reduce_and_evaluate",
            {"raw_events": raw_events, "account_id": "acct_a", **view_input},
            {
                "active": True,
                "features": ["dashboard", "exports"],
                "usageLimit": 1000,
                "overLimit": False,
                "couponActive": False,
            },
        ),
        (
            "v2_export_report",
            {"summaries": summaries},
            report,
        ),
        (
            "v2_calculate_proration",
            {
                "old_plan": "starter",
                "new_plan": "pro",
                "period_start": "2026-01-01T00:00:00Z",
                "period_end": "2026-02-01T00:00:00Z",
                "change_effective_at": "2026-01-15T00:00:00Z",
                "quantity": 2,
            },
            proration,
        ),
        (
            "v2_metamorphic",
            {
                "baseline": raw_events,
                "variants": [{"name": "reversed", "raw_events": list(reversed(raw_events))}],
                "target_account_id": "acct_a",
                **view_input,
            },
            {"baseline": summaries, "variants": [{"name": "reversed", "value": summaries, "equivalent": True}]},
        ),
        (
            "v2_performance_digest",
            {"raw_events": raw_events, **view_input},
            _synthetic_performance_digest(raw_events, summaries, report),
        ),
    ]

    for language, runner, setup in (("typescript", js_runner, {"ok": True}), ("python", py_runner, None)):
        for operation, input_payload, expected in cases:
            case = _hidden_case(f"synthetic.{language}.{operation}", operation, input_payload, expected)
            result = run_language_case(language, case, worktree, runner, setup)
            assert result["status"] == "passed", result

    parity_case = _hidden_case(
        "synthetic.parity.v2",
        "v2_parity",
        {"raw_events": raw_events, **view_input},
        {"summaries": summaries, "report": report},
        category="parity",
        languages=["parity"],
        points=2.0,
    )

    parity_result = run_parity_case(parity_case, worktree, js_runner, py_runner, {"ok": True})

    assert parity_result["status"] == "passed", parity_result
    assert parity_result["points_earned"] == 2.0


def test_hidden_runner_scores_unsupported_v2_operations_as_case_failures(tmp_path: Path) -> None:
    worktree = _write_synthetic_v2_worktree(tmp_path, include_proration=False)
    js_runner, _ = _write_hidden_case_runners(tmp_path)
    case = _hidden_case(
        "synthetic.unsupported.proration",
        "v2_calculate_proration",
        {
            "old_plan": "starter",
            "new_plan": "pro",
            "period_start": "2026-01-01T00:00:00Z",
            "period_end": "2026-02-01T00:00:00Z",
            "change_effective_at": "2026-01-15T00:00:00Z",
        },
        {"unused": True},
    )

    result = run_language_case("typescript", case, worktree, js_runner, {"ok": True})

    assert result["status"] == "failed"
    assert result["reason"] == "unsupported_operation"
    assert result["points_earned"] == 0.0


def test_hidden_runner_parity_does_not_pass_identical_runner_failures(tmp_path: Path) -> None:
    worktree = _write_synthetic_v2_worktree(tmp_path)
    js_runner, py_runner = _write_hidden_case_runners(tmp_path)
    case = {
        "id": "synthetic.parity.unsupported",
        "category": "parity",
        "languages": ["parity"],
        "points": 2.0,
        "operation": "v2_missing_operation",
        "input": {},
    }

    result = run_parity_case(case, worktree, js_runner, py_runner, {"ok": True})

    assert result["status"] == "failed"
    assert result["reason"] == "unsupported_operation"
    assert result["points_earned"] == 0.0


def test_hidden_runner_parity_expected_output_takes_precedence(tmp_path: Path) -> None:
    worktree = _write_synthetic_v2_worktree(tmp_path)
    js_runner, py_runner = _write_hidden_case_runners(tmp_path)
    case = _hidden_case(
        "synthetic.parity.expected_error",
        "v2_missing_operation",
        {},
        {"ok": False, "error": "unsupported_operation", "operation": "v2_missing_operation"},
        category="parity",
        languages=["parity"],
        points=2.0,
    )

    result = run_parity_case(case, worktree, js_runner, py_runner, {"ok": True})

    assert result["status"] == "passed"
    assert result["points_earned"] == 2.0


def test_hidden_runner_sanitizes_unexpected_measured_error_reasons() -> None:
    case = {"expected": {"ok": True}}

    assert compare_case(case, {"ok": False, "error": "unsupported_operation"}) == (
        False,
        "unsupported_operation",
    )
    assert compare_case(case, {"ok": False, "error": "secret raw event payload"}) == (
        False,
        "operation_failed",
    )


def test_run_process_to_files_records_timeout_and_partial_output(tmp_path: Path) -> None:
    stdout_path = tmp_path / "events.jsonl"
    stderr_path = tmp_path / "stderr.log"
    script = "import time; print('started', flush=True); time.sleep(30)"

    result = run_process_to_files(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout_seconds=1,
    )

    stdout = stdout_path.read_text(encoding="utf-8")
    stderr = stderr_path.read_text(encoding="utf-8")

    assert result.timed_out
    assert "started" in stdout
    assert "TIMEOUT" in stderr


def test_run_process_to_files_records_launch_errors(tmp_path: Path) -> None:
    stdout_path = tmp_path / "events.jsonl"
    stderr_path = tmp_path / "stderr.log"
    missing = tmp_path / "missing-executable"

    result = run_process_to_files(
        [str(missing)],
        cwd=tmp_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout_seconds=1,
    )
    stderr = stderr_path.read_text(encoding="utf-8")

    assert result.returncode is None
    assert not result.timed_out
    assert "process_error" in stderr


def test_extract_final_response_uses_last_parseable_json_object(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(
        json.dumps(
            {
                "type": "message",
                "content": 'draft {"status": "wrong"} final {"status": "success"}',
            }
        )
        + "\n",
        encoding="utf-8",
    )

    final = extract_final_response(events_path)

    assert final["parsed"]
    assert final["value"] == {"status": "success"}


def test_check_codex_version_records_stdout_stderr_and_returncode() -> None:
    check = _check_codex_version(sys.executable)

    assert check.status == "passed"
    assert check.data is not None
    assert check.data["returncode"] == 0
    assert "stdout" in check.data
    assert "stderr" in check.data


def test_failed_phase_artifacts_are_archived_before_rerun(tmp_path: Path) -> None:
    run_dir = tmp_path
    (run_dir / "events.jsonl").write_text("old events\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("old stderr\n", encoding="utf-8")
    state = {"phases": {"implemented": {"status": "failed"}}}

    archived = archive_failed_phase_artifacts(
        run_dir,
        "implemented",
        ["events.jsonl", "stderr.log", "missing.json"],
        state,
        True,
    )

    assert archived is not None
    archive_dir = Path(archived)
    assert not (run_dir / "events.jsonl").exists()
    assert not (run_dir / "stderr.log").exists()
    assert (archive_dir / "events.jsonl").read_text(encoding="utf-8") == "old events\n"
    assert (archive_dir / "stderr.log").read_text(encoding="utf-8") == "old stderr\n"


def test_completed_phase_artifacts_can_be_archived_for_stale_rerun(tmp_path: Path) -> None:
    (tmp_path / "score.json").write_text("old score\n", encoding="utf-8")

    archived = archive_phase_artifacts(tmp_path, "scored", ["score.json"])

    assert archived is not None
    assert not (tmp_path / "score.json").exists()
    assert (Path(archived) / "score.json").read_text(encoding="utf-8") == "old score\n"


def test_public_test_launch_errors_are_repairable(tmp_path: Path) -> None:
    (tmp_path / "typecheck.meta.json").write_text(
        json.dumps({"returncode": None, "timed_out": False}),
        encoding="utf-8",
    )

    assert _public_tests_have_launch_errors(tmp_path)


def test_run_public_tests_uses_launchable_npm_cmd_from_path(tmp_path: Path, monkeypatch) -> None:
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    npm = _fake_npm_cmd(tools_dir)
    (tools_dir / "npm.ps1").write_text("Write-Output wrong npm shim\n", encoding="utf-8")
    monkeypatch.delenv("NPM_BIN", raising=False)
    monkeypatch.setenv("PATH", str(tools_dir))

    worktree = tmp_path / "worktree"
    (worktree / "node_modules" / ".bin").mkdir(parents=True)
    (worktree / "node_modules" / ".bin" / "tsc").write_text("fake tsc\n", encoding="utf-8")
    (worktree / "tests_public_py").mkdir(parents=True)
    (worktree / "package.json").write_text('{"scripts":{}}\n', encoding="utf-8")
    (worktree / "tests_public_py" / "test_smoke.py").write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
    run_dir = tmp_path / "run"

    results = run_public_tests(worktree, run_dir, {"timeouts": {"implementation_seconds": 30}})

    typecheck_meta = json.loads((run_dir / "typecheck.meta.json").read_text(encoding="utf-8"))
    public_ts_meta = json.loads((run_dir / "public_ts.meta.json").read_text(encoding="utf-8"))
    assert Path(typecheck_meta["command"][0]).resolve() == npm.resolve()
    assert Path(public_ts_meta["command"][0]).resolve() == npm.resolve()
    assert typecheck_meta["returncode"] == 0
    assert public_ts_meta["returncode"] == 0
    assert results["public_py"].returncode == 0


def test_phase_stale_after_detects_newer_upstream_phase() -> None:
    state = {
        "phases": {
            "implemented": {"updated_at": "2026-05-19T21:08:23+00:00"},
            "public_tested": {"updated_at": "2026-05-19T21:04:40+00:00"},
            "hidden_tested": {"updated_at": "2026-05-19T21:09:00+00:00"},
        }
    }

    assert phase_stale_after(state, "public_tested", "implemented")
    assert not phase_stale_after(state, "hidden_tested", "implemented")


def _write_hidden_case_runners(tmp_path: Path) -> tuple[Path, Path]:
    runners = tmp_path / "hidden-runners"
    runners.mkdir()
    js_runner = runners / "ts_case_runner.mjs"
    py_runner = runners / "py_case_runner.py"
    js_runner.write_text(JS_CASE_RUNNER, encoding="utf-8")
    py_runner.write_text(PY_CASE_RUNNER, encoding="utf-8")
    return js_runner, py_runner


def _write_synthetic_v2_worktree(tmp_path: Path, *, include_proration: bool = True) -> Path:
    worktree = tmp_path / "synthetic-v2-worktree"
    (worktree / "dist").mkdir(parents=True)
    (worktree / "ruleledger").mkdir(parents=True)
    (worktree / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")
    (worktree / "ruleledger" / "__init__.py").write_text("", encoding="utf-8")
    (worktree / "dist" / "index.js").write_text(_synthetic_ts_module(include_proration), encoding="utf-8")
    (worktree / "ruleledger" / "engine.py").write_text(_synthetic_py_module(include_proration), encoding="utf-8")
    return worktree


def _synthetic_ts_module(include_proration: bool) -> str:
    proration = (
        """
export function calculatePlanChangeProrationV2(input) {
  return {
    oldPlan: input.old_plan,
    newPlan: input.new_plan,
    quantity: input.quantity ?? 1,
    netAdjustmentCents: 42
  };
}
"""
        if include_proration
        else ""
    )
    return (
        r"""
const FEATURES = {
  starter: ["dashboard", "exports"],
  pro: ["dashboard", "exports", "rules"]
};
const LIMITS = { starter: 1000, pro: 10000 };

function iso(value) {
  return new Date(value).toISOString();
}

function freshState(accountId) {
  return {
    accountId,
    status: "active",
    plan: "starter",
    totalPaidCents: 0,
    usage: 0,
    currency: null,
    seats: 1,
    invoiceIds: [],
    lastInvoiceId: null,
    lastPeriodStart: null,
    lastPeriodEnd: null,
    mergedFromAccountIds: [],
    closedAt: null,
    lastEventAt: null
  };
}

function addUnique(values, value) {
  if (!values.includes(value)) {
    values.push(value);
  }
}

function assertViewAliases(view) {
  if (
    view.asOf !== "2026-01-20T00:00:00Z" ||
    view.as_of !== "2026-01-20T00:00:00Z" ||
    view.businessAsOf !== "2026-01-18T00:00:00Z" ||
    view.business_as_of !== "2026-01-18T00:00:00Z" ||
    view.auditAsOf !== "2026-01-19T00:00:00Z" ||
    view.audit_as_of !== "2026-01-19T00:00:00Z"
  ) {
    throw new Error("missing view aliases");
  }
}

export function normalizeEvent(raw) {
  const normalized = {
    id: String(raw.id),
    accountId: String(raw.account_id),
    type: String(raw.type),
    timestamp: iso(raw.timestamp),
    effectiveAt: iso(raw.effective_at ?? raw.timestamp),
    recordedAt: iso(raw.recorded_at ?? raw.timestamp),
    sequence: Number(raw.sequence ?? 0)
  };
  if (raw.plan !== undefined) normalized.plan = raw.plan;
  if (raw.usage !== undefined) normalized.usage = Number(raw.usage);
  if (raw.amount_cents !== undefined) normalized.amountCents = Number(raw.amount_cents);
  if (raw.currency !== undefined) normalized.currency = String(raw.currency).toUpperCase();
  if (raw.quantity !== undefined) normalized.quantity = Number(raw.quantity);
  if (raw.invoice_id !== undefined) normalized.invoiceId = String(raw.invoice_id);
  if (raw.period_start !== undefined) normalized.periodStart = iso(raw.period_start);
  if (raw.period_end !== undefined) normalized.periodEnd = iso(raw.period_end);
  return { ok: true, value: normalized };
}

export const normalizeEventV2 = normalizeEvent;

export function reduceAccountStateV2(events, view) {
  assertViewAliases(view);
  const states = new Map();
  const sorted = [...events].sort((left, right) =>
    `${left.accountId}|${left.effectiveAt}|${left.sequence}|${left.id}`.localeCompare(
      `${right.accountId}|${right.effectiveAt}|${right.sequence}|${right.id}`
    )
  );
  for (const event of sorted) {
    const state = states.get(event.accountId) ?? freshState(event.accountId);
    states.set(event.accountId, state);
    if (event.type === "account_opened" || event.type === "plan_changed") {
      state.plan = event.plan ?? state.plan;
      state.status = "active";
    }
    if (event.type === "account_opened" && event.quantity !== undefined) {
      state.seats = Math.max(1, event.quantity);
    }
    if (event.type === "usage_recorded") {
      state.usage += event.usage ?? 0;
    }
    if (event.type === "payment_succeeded") {
      state.totalPaidCents += event.amountCents ?? 0;
      state.currency = event.currency ?? state.currency;
    }
    if (event.invoiceId !== undefined) {
      addUnique(state.invoiceIds, event.invoiceId);
      state.lastInvoiceId = event.invoiceId;
    }
    if (event.periodStart !== undefined) state.lastPeriodStart = event.periodStart;
    if (event.periodEnd !== undefined) state.lastPeriodEnd = event.periodEnd;
    state.lastEventAt = event.effectiveAt;
  }
  return [...states.values()].sort((left, right) => left.accountId.localeCompare(right.accountId));
}

export function summarizeAccountV2(state, view) {
  const usageLimit = LIMITS[state.plan];
  return {
    accountId: state.accountId,
    status: state.status,
    plan: state.plan,
    features: FEATURES[state.plan],
    usage: state.usage,
    usageLimit,
    overLimit: state.usage > usageLimit,
    totalPaidCents: state.totalPaidCents,
    currency: state.currency,
    seats: state.seats,
    couponCode: null,
    couponActive: false,
    invoiceIds: state.invoiceIds,
    lastInvoiceId: state.lastInvoiceId,
    lastPeriodStart: state.lastPeriodStart,
    lastPeriodEnd: state.lastPeriodEnd,
    mergedFromAccountIds: state.mergedFromAccountIds,
    closedAt: state.closedAt,
    lastEventAt: state.lastEventAt
  };
}

export function evaluateEntitlementsV2(state, view) {
  const usageLimit = LIMITS[state.plan];
  return {
    active: state.status !== "closed",
    features: FEATURES[state.plan],
    usageLimit,
    overLimit: state.usage > usageLimit,
    couponActive: false
  };
}

export function exportLedgerReportV2(summaries) {
  const rows = [...summaries]
    .sort((left, right) => left.accountId.localeCompare(right.accountId))
    .map((summary) => `${summary.accountId},${summary.usage},${summary.totalPaidCents}`);
  return "account_id,usage,total_paid_cents\n" + rows.join("\n") + "\n";
}
"""
        + proration
    )


def _synthetic_py_module(include_proration: bool) -> str:
    proration = (
        '''
def calculate_plan_change_proration_v2(input_payload):
    return {
        "oldPlan": input_payload["old_plan"],
        "newPlan": input_payload["new_plan"],
        "quantity": input_payload.get("quantity", 1),
        "netAdjustmentCents": 42,
    }
'''
        if include_proration
        else ""
    )
    return (
        '''
FEATURES = {
    "starter": ["dashboard", "exports"],
    "pro": ["dashboard", "exports", "rules"],
}
LIMITS = {"starter": 1000, "pro": 10000}


def _iso(value):
    if value.endswith("Z") and "." not in value:
        return value[:-1] + ".000Z"
    return value


def _fresh_state(account_id):
    return {
        "accountId": account_id,
        "status": "active",
        "plan": "starter",
        "totalPaidCents": 0,
        "usage": 0,
        "currency": None,
        "seats": 1,
        "invoiceIds": [],
        "lastInvoiceId": None,
        "lastPeriodStart": None,
        "lastPeriodEnd": None,
        "mergedFromAccountIds": [],
        "closedAt": None,
        "lastEventAt": None,
    }


def _add_unique(values, value):
    if value not in values:
        values.append(value)


def _assert_view_aliases(view):
    expected = {
        "asOf": "2026-01-20T00:00:00Z",
        "as_of": "2026-01-20T00:00:00Z",
        "businessAsOf": "2026-01-18T00:00:00Z",
        "business_as_of": "2026-01-18T00:00:00Z",
        "auditAsOf": "2026-01-19T00:00:00Z",
        "audit_as_of": "2026-01-19T00:00:00Z",
    }
    if {key: view.get(key) for key in expected} != expected:
        raise AssertionError("missing view aliases")


def normalize_event_v2(raw):
    normalized = {
        "id": str(raw["id"]),
        "accountId": str(raw["account_id"]),
        "type": str(raw["type"]),
        "timestamp": _iso(raw["timestamp"]),
        "effectiveAt": _iso(raw.get("effective_at", raw["timestamp"])),
        "recordedAt": _iso(raw.get("recorded_at", raw["timestamp"])),
        "sequence": int(raw.get("sequence", 0)),
    }
    if "plan" in raw:
        normalized["plan"] = raw["plan"]
    if "usage" in raw:
        normalized["usage"] = int(raw["usage"])
    if "amount_cents" in raw:
        normalized["amountCents"] = int(raw["amount_cents"])
    if "currency" in raw:
        normalized["currency"] = str(raw["currency"]).upper()
    if "quantity" in raw:
        normalized["quantity"] = int(raw["quantity"])
    if "invoice_id" in raw:
        normalized["invoiceId"] = str(raw["invoice_id"])
    if "period_start" in raw:
        normalized["periodStart"] = _iso(raw["period_start"])
    if "period_end" in raw:
        normalized["periodEnd"] = _iso(raw["period_end"])
    return {"ok": True, "value": normalized}


normalize_event = normalize_event_v2


def reduce_account_state_v2(events, view):
    _assert_view_aliases(view)
    states = {}
    sorted_events = sorted(
        events,
        key=lambda event: (
            event.get("accountId", ""),
            event.get("effectiveAt", ""),
            event.get("sequence", 0),
            event.get("id", ""),
        ),
    )
    for event in sorted_events:
        state = states.setdefault(event["accountId"], _fresh_state(event["accountId"]))
        if event["type"] in {"account_opened", "plan_changed"}:
            state["plan"] = event.get("plan", state["plan"])
            state["status"] = "active"
        if event["type"] == "account_opened" and "quantity" in event:
            state["seats"] = max(1, event["quantity"])
        if event["type"] == "usage_recorded":
            state["usage"] += event.get("usage", 0)
        if event["type"] == "payment_succeeded":
            state["totalPaidCents"] += event.get("amountCents", 0)
            state["currency"] = event.get("currency", state["currency"])
        if "invoiceId" in event:
            _add_unique(state["invoiceIds"], event["invoiceId"])
            state["lastInvoiceId"] = event["invoiceId"]
        if "periodStart" in event:
            state["lastPeriodStart"] = event["periodStart"]
        if "periodEnd" in event:
            state["lastPeriodEnd"] = event["periodEnd"]
        state["lastEventAt"] = event["effectiveAt"]
    return [states[key] for key in sorted(states)]


def summarize_account_v2(state, view):
    usage_limit = LIMITS[state["plan"]]
    return {
        "accountId": state["accountId"],
        "status": state["status"],
        "plan": state["plan"],
        "features": FEATURES[state["plan"]],
        "usage": state["usage"],
        "usageLimit": usage_limit,
        "overLimit": state["usage"] > usage_limit,
        "totalPaidCents": state["totalPaidCents"],
        "currency": state["currency"],
        "seats": state["seats"],
        "couponCode": None,
        "couponActive": False,
        "invoiceIds": state["invoiceIds"],
        "lastInvoiceId": state["lastInvoiceId"],
        "lastPeriodStart": state["lastPeriodStart"],
        "lastPeriodEnd": state["lastPeriodEnd"],
        "mergedFromAccountIds": state["mergedFromAccountIds"],
        "closedAt": state["closedAt"],
        "lastEventAt": state["lastEventAt"],
    }


def evaluate_entitlements_v2(state, view):
    usage_limit = LIMITS[state["plan"]]
    return {
        "active": state["status"] != "closed",
        "features": FEATURES[state["plan"]],
        "usageLimit": usage_limit,
        "overLimit": state["usage"] > usage_limit,
        "couponActive": False,
    }


def export_ledger_report_v2(summaries):
    rows = [
        f'{summary["accountId"]},{summary["usage"]},{summary["totalPaidCents"]}'
        for summary in sorted(summaries, key=lambda item: item["accountId"])
    ]
    return "account_id,usage,total_paid_cents\\n" + "\\n".join(rows) + "\\n"
'''
        + proration
    )


def _synthetic_raw_events() -> list[dict[str, object]]:
    return [
        {
            "id": "evt_open",
            "account_id": "acct_a",
            "type": "account_opened",
            "timestamp": "2026-01-01T00:00:00Z",
            "plan": "starter",
            "quantity": 2,
        },
        {
            "id": "evt_usage",
            "account_id": "acct_a",
            "type": "usage_recorded",
            "timestamp": "2026-01-02T00:00:00Z",
            "usage": 7,
        },
        {
            "id": "evt_payment",
            "account_id": "acct_a",
            "type": "payment_succeeded",
            "timestamp": "2026-01-03T00:00:00Z",
            "amount_cents": 1200,
            "currency": "usd",
            "invoice_id": "inv_1",
            "period_start": "2026-01-01T00:00:00Z",
            "period_end": "2026-02-01T00:00:00Z",
        },
    ]


def _synthetic_summary() -> dict[str, object]:
    return {
        "accountId": "acct_a",
        "status": "active",
        "plan": "starter",
        "features": ["dashboard", "exports"],
        "usage": 7,
        "usageLimit": 1000,
        "overLimit": False,
        "totalPaidCents": 1200,
        "currency": "USD",
        "seats": 2,
        "couponCode": None,
        "couponActive": False,
        "invoiceIds": ["inv_1"],
        "lastInvoiceId": "inv_1",
        "lastPeriodStart": "2026-01-01T00:00:00.000Z",
        "lastPeriodEnd": "2026-02-01T00:00:00.000Z",
        "mergedFromAccountIds": [],
        "closedAt": None,
        "lastEventAt": "2026-01-03T00:00:00.000Z",
    }


def _synthetic_report(summaries: list[dict[str, object]]) -> str:
    rows = ["account_id,usage,total_paid_cents"]
    for summary in sorted(summaries, key=lambda item: str(item["accountId"])):
        rows.append(f'{summary["accountId"]},{summary["usage"]},{summary["totalPaidCents"]}')
    return "\n".join(rows) + "\n"


def _synthetic_performance_digest(
    raw_events: list[dict[str, object]],
    summaries: list[dict[str, object]],
    report: str,
) -> dict[str, object]:
    return {
        "eventCount": len(raw_events),
        "summaryCount": len(summaries),
        "firstAccountId": summaries[0]["accountId"],
        "lastAccountId": summaries[-1]["accountId"],
        "totalUsage": sum(int(summary["usage"]) for summary in summaries),
        "totalPaidCents": sum(int(summary["totalPaidCents"]) for summary in summaries),
        "summarySha256": hashlib.sha256(canonical(summaries).encode("utf-8")).hexdigest(),
        "reportSha256": hashlib.sha256(report.encode("utf-8")).hexdigest(),
    }


def _hidden_case(
    case_id: str,
    operation: str,
    input_payload: dict[str, object],
    expected: object,
    *,
    category: str = "synthetic",
    languages: list[str] | None = None,
    points: float = 1.0,
) -> dict[str, object]:
    return {
        "id": case_id,
        "category": category,
        "languages": languages or ["typescript", "python"],
        "points": points,
        "operation": operation,
        "input": input_payload,
        "expected": expected,
    }


def _fake_executable(directory: Path, name: str) -> Path:
    if os.name == "nt":
        path = directory / f"{name}.cmd"
        path.write_text("@echo fake codex\n", encoding="utf-8")
        return path

    path = directory / name
    path.write_text("#!/bin/sh\necho fake codex\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _fake_npm_cmd(directory: Path) -> Path:
    path = directory / "npm.cmd"
    if os.name == "nt":
        path.write_text("@echo fake npm %*\r\n@exit /B 0\r\n", encoding="utf-8")
        return path

    path.write_text("#!/bin/sh\necho fake npm \"$@\"\nexit 0\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path
