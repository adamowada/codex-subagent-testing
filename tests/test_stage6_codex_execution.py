from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest

from harness.codex_runner import (
    command_for_display,
    extract_final_response,
    resolve_codex_bin,
    run_process_to_files,
)
from harness.orchestrator import archive_failed_phase_artifacts
from harness.preflight import _check_codex_version


class Stage6CodexExecutionTests(unittest.TestCase):
    def test_resolve_codex_bin_prefers_absolute_codex_bin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = _fake_executable(Path(temp_dir), "custom-codex")

            resolved = resolve_codex_bin({"CODEX_BIN": str(executable), "PATH": ""})

        self.assertEqual(resolved, str(executable))

    def test_resolve_codex_bin_uses_supplied_path_for_command_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = _fake_executable(Path(temp_dir), "codex")

            resolved = resolve_codex_bin({"CODEX_BIN": "codex", "PATH": temp_dir})

        self.assertEqual(Path(resolved or "").resolve(), executable.resolve())

    def test_command_for_display_masks_prompt(self) -> None:
        command = ["codex", "exec", "--json", "secret prompt"]

        self.assertEqual(command_for_display(command), ["codex", "exec", "--json", "<prompt>"])

    def test_run_process_to_files_captures_success_stdout_stderr_and_final_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stdout_path = root / "events.jsonl"
            stderr_path = root / "stderr.log"
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
                cwd=root,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                timeout_seconds=10,
                command_display=["python", "-c", "<script>"],
            )
            final = extract_final_response(stdout_path)
            stderr = stderr_path.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0)
        self.assertFalse(result.timed_out)
        self.assertIn("warning from fake codex", stderr)
        self.assertTrue(final["parsed"])
        self.assertEqual(final["value"]["status"], "success")

    def test_run_process_to_files_records_timeout_and_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stdout_path = root / "events.jsonl"
            stderr_path = root / "stderr.log"
            script = "import time; print('started', flush=True); time.sleep(30)"

            result = run_process_to_files(
                [sys.executable, "-c", script],
                cwd=root,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                timeout_seconds=1,
            )

            stdout = stdout_path.read_text(encoding="utf-8")
            stderr = stderr_path.read_text(encoding="utf-8")

        self.assertTrue(result.timed_out)
        self.assertIn("started", stdout)
        self.assertIn("TIMEOUT", stderr)

    def test_run_process_to_files_records_launch_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stdout_path = root / "events.jsonl"
            stderr_path = root / "stderr.log"
            missing = root / "missing-executable"

            result = run_process_to_files(
                [str(missing)],
                cwd=root,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                timeout_seconds=1,
            )
            stderr = stderr_path.read_text(encoding="utf-8")

        self.assertIsNone(result.returncode)
        self.assertFalse(result.timed_out)
        self.assertIn("process_error", stderr)

    def test_extract_final_response_uses_last_parseable_json_object(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            events_path = Path(temp_dir) / "events.jsonl"
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

        self.assertTrue(final["parsed"])
        self.assertEqual(final["value"], {"status": "success"})

    def test_check_codex_version_records_stdout_stderr_and_returncode(self) -> None:
        check = _check_codex_version(sys.executable)

        self.assertEqual(check.status, "passed")
        self.assertIsNotNone(check.data)
        assert check.data is not None
        self.assertEqual(check.data["returncode"], 0)
        self.assertIn("stdout", check.data)
        self.assertIn("stderr", check.data)

    def test_failed_phase_artifacts_are_archived_before_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
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

            self.assertFalse((run_dir / "events.jsonl").exists())
            self.assertFalse((run_dir / "stderr.log").exists())
            self.assertEqual((archive_dir / "events.jsonl").read_text(encoding="utf-8"), "old events\n")
            self.assertEqual((archive_dir / "stderr.log").read_text(encoding="utf-8"), "old stderr\n")


def _fake_executable(directory: Path, name: str) -> Path:
    if os.name == "nt":
        path = directory / f"{name}.cmd"
        path.write_text("@echo fake codex\n", encoding="utf-8")
        return path

    path = directory / name
    path.write_text("#!/bin/sh\necho fake codex\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


if __name__ == "__main__":
    unittest.main()
