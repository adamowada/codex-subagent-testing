from __future__ import annotations

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
from harness.hidden_runner import run_command as run_hidden_command
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
