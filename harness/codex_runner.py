from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import tomllib
from typing import Any, Mapping


FINAL_JSON_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
KILL_WAIT_SECONDS = 15


@dataclass(frozen=True)
class ProcessResult:
    command: list[str]
    command_display: list[str]
    cwd: str
    started_at: str
    finished_at: str
    elapsed_seconds: float
    returncode: int | None
    timed_out: bool
    stdout_path: str | None = None
    stderr_path: str | None = None
    log_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_codex_bin(env: Mapping[str, str] | None = None) -> str | None:
    """Return the Codex executable selected by CODEX_BIN or PATH."""

    environment = env if env is not None else os.environ
    path = environment.get("PATH")
    configured = environment.get("CODEX_BIN")
    if configured:
        candidate = Path(configured)
        if candidate.is_absolute() and candidate.exists():
            return str(candidate)
        resolved = shutil.which(configured, path=path)
        return resolved or configured
    return shutil.which("codex", path=path)


def resolve_npm_bin(env: Mapping[str, str] | None = None) -> str | None:
    """Return an npm executable path that Python can launch on this platform."""

    environment = env if env is not None else os.environ
    path = environment.get("PATH")
    configured = environment.get("NPM_BIN")
    if configured:
        candidate = Path(configured)
        if candidate.is_absolute() and candidate.exists():
            return str(candidate)
        resolved = shutil.which(configured, path=path)
        return resolved or configured
    return shutil.which("npm.cmd", path=path) or shutil.which("npm", path=path)


def build_implementation_command(
    codex_bin: str,
    run: Mapping[str, Any],
    prompt: str,
    *,
    config_dir: str | Path | None = None,
) -> list[str]:
    root = _mapping(run, "root")
    agents = _mapping(run, "agents")
    rendered = _rendered_config_values(config_dir)
    model = str(rendered.get("model", root["model"]))
    reasoning = str(rendered.get("model_reasoning_effort", root["reasoning"]))
    sandbox = str(rendered.get("sandbox", "workspace-write"))
    ask_for_approval = str(rendered.get("ask_for_approval", "never"))

    return [
        codex_bin,
        "--ask-for-approval",
        ask_for_approval,
        "exec",
        "--json",
        "--cd",
        "<run_worktree>",
        "--sandbox",
        sandbox,
        "--model",
        model,
        *_config_override_args(
            [
                f"model_reasoning_effort={_toml_value(reasoning)}",
                f"agents.max_threads={int(rendered.get('agents.max_threads', agents['max_threads']))}",
                f"agents.max_depth={_codex_cli_agent_depth(rendered.get('agents.max_depth', agents['max_depth']))}",
                *_agent_override_values(rendered, config_dir),
            ]
        ),
        prompt,
    ]


def build_judge_command(codex_bin: str, run: Mapping[str, Any], prompt: str) -> list[str]:
    judge = _mapping(run, "judge")
    return [
        codex_bin,
        "--ask-for-approval",
        "never",
        "exec",
        "--json",
        "--cd",
        "<run_worktree>",
        "--sandbox",
        str(judge.get("sandbox", "read-only")),
        "--model",
        str(judge["model"]),
        "-c",
        f"model_reasoning_effort={judge['reasoning']}",
        prompt,
    ]


def materialize_worktree_command(command: list[str], worktree: Path) -> list[str]:
    return [str(worktree) if part == "<run_worktree>" else part for part in command]


def command_for_display(command: list[str]) -> list[str]:
    if not command:
        return []
    display = list(command)
    if len(display) > 1:
        display[-1] = "<prompt>"
    return display


def run_process_to_files(
    command: list[str],
    *,
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: int,
    env: Mapping[str, str] | None = None,
    command_display: list[str] | None = None,
) -> ProcessResult:
    """Run a process while streaming stdout and stderr into artifact files."""

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = iso_now()
    started = time.monotonic()
    timed_out = False
    returncode: int | None

    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file:
        with stderr_path.open("w", encoding="utf-8", errors="replace") as stderr_file:
            try:
                process = subprocess.Popen(
                    command,
                    cwd=cwd,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=dict(env) if env is not None else None,
                )
                try:
                    returncode = process.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    process.kill()
                    stderr_file.write("\nTIMEOUT\n")
                    try:
                        returncode = process.wait(timeout=KILL_WAIT_SECONDS)
                    except subprocess.TimeoutExpired:
                        returncode = None
                        stderr_file.write(
                            f"process_error:TimeoutExpired: process did not exit within {KILL_WAIT_SECONDS}s after kill\n"
                        )
            except OSError as exc:
                stderr_file.write(f"process_error:{exc.__class__.__name__}: {exc}\n")
                returncode = None

    finished_at = iso_now()
    return ProcessResult(
        command=command,
        command_display=command_display or command_for_display(command),
        cwd=str(cwd),
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=round(time.monotonic() - started, 6),
        returncode=returncode,
        timed_out=timed_out,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
    )


def run_logged_command(
    command: list[str],
    *,
    cwd: Path,
    log_path: Path,
    timeout_seconds: int,
    env: Mapping[str, str] | None = None,
) -> ProcessResult:
    """Run a command and write combined stdout/stderr into one log file."""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = iso_now()
    started = time.monotonic()
    timed_out = False
    returncode: int | None

    with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=dict(env) if env is not None else None,
            )
            try:
                returncode = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                log_file.write("\nTIMEOUT\n")
                try:
                    returncode = process.wait(timeout=KILL_WAIT_SECONDS)
                except subprocess.TimeoutExpired:
                    returncode = None
                    log_file.write(
                        f"process_error:TimeoutExpired: process did not exit within {KILL_WAIT_SECONDS}s after kill\n"
                    )
        except OSError as exc:
            log_file.write(f"process_error:{exc.__class__.__name__}: {exc}\n")
            returncode = None

    finished_at = iso_now()
    return ProcessResult(
        command=command,
        command_display=list(command),
        cwd=str(cwd),
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=round(time.monotonic() - started, 6),
        returncode=returncode,
        timed_out=timed_out,
        log_path=str(log_path),
    )


def write_process_result(path: Path, result: ProcessResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def extract_final_response(events_path: Path) -> dict[str, Any]:
    """Best-effort extraction of the final strict JSON response from Codex JSONL."""

    if not events_path.exists():
        return {"parsed": False, "raw": "", "error": "events_file_missing"}

    candidates: list[str] = []
    for line in events_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        candidates.extend(_collect_text_candidates(event))

    for raw in reversed(candidates):
        parsed = _parse_json_object_from_text(raw)
        if parsed["parsed"]:
            return parsed

    return {
        "parsed": False,
        "raw": candidates[-1] if candidates else "",
        "error": "no_strict_json_object_found",
    }


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _mapping(parent: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise TypeError(f"{key}: expected object")
    return value


def _rendered_config_values(config_dir: str | Path | None) -> dict[str, Any]:
    if config_dir is None:
        return {}

    config_path = Path(config_dir) / "config.toml"
    if not config_path.exists():
        return {}

    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    values: dict[str, Any] = {}
    for key in ("model", "model_reasoning_effort", "sandbox", "ask_for_approval"):
        if key in payload:
            values[key] = payload[key]

    agents = payload.get("agents")
    if isinstance(agents, Mapping):
        for key in ("max_threads", "max_depth"):
            if key in agents:
                values[f"agents.{key}"] = agents[key]
        for name, role in agents.items():
            if name in {"max_threads", "max_depth"} or not isinstance(role, Mapping):
                continue
            prefix = f"agents.{name}"
            for key in ("description", "model", "model_reasoning_effort", "sandbox", "config_file"):
                if key in role:
                    values[f"{prefix}.{key}"] = role[key]
    return values


def _agent_override_values(rendered: Mapping[str, Any], config_dir: str | Path | None) -> list[str]:
    if config_dir is None:
        return []

    overrides: list[str] = []
    config_root = Path(config_dir).resolve()
    prefixes = sorted(
        {
            ".".join(key.split(".")[:2])
            for key in rendered
            if key.startswith("agents.") and key.count(".") >= 2
        }
    )
    for prefix in prefixes:
        for field in ("description", "model", "model_reasoning_effort", "sandbox", "config_file"):
            key = f"{prefix}.{field}"
            if key not in rendered:
                continue
            value = rendered[key]
            if field == "config_file":
                value = str((config_root / str(value)).resolve())
            overrides.append(f"{key}={_toml_value(value)}")
    return overrides


def _config_override_args(overrides: list[str]) -> list[str]:
    args: list[str] = []
    for override in overrides:
        args.extend(["-c", override])
    return args


def _codex_cli_agent_depth(value: Any) -> int:
    return max(1, int(value))


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return json.dumps(str(value))


def _collect_text_candidates(value: Any) -> list[str]:
    candidates: list[str] = []
    if isinstance(value, str):
        if "{" in value and "}" in value:
            candidates.append(value)
        return candidates
    if isinstance(value, list):
        for item in value:
            candidates.extend(_collect_text_candidates(item))
        return candidates
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"text", "content", "message", "output", "response"}:
                candidates.extend(_collect_text_candidates(item))
            elif isinstance(item, (dict, list)):
                candidates.extend(_collect_text_candidates(item))
        return candidates
    return candidates


def _parse_json_object_from_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        candidates = list(_json_object_candidates(stripped))
        if not candidates:
            return {"parsed": False, "raw": text, "error": "no_json_object"}
        last_error = "no_json_object"
        for candidate in reversed(candidates):
            try:
                value = json.loads(candidate)
            except json.JSONDecodeError as exc:
                last_error = f"json_decode_error:{exc.msg}"
                continue
            return {"parsed": True, "raw": candidate, "value": value}
        return {"parsed": False, "raw": text, "error": last_error}
    return {"parsed": True, "raw": stripped, "value": value}


def _json_object_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    stack = 0
    start: int | None = None
    in_string = False
    escaped = False

    for index, character in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue

        if character == '"':
            in_string = True
            continue
        if character == "{":
            if stack == 0:
                start = index
            stack += 1
            continue
        if character == "}" and stack:
            stack -= 1
            if stack == 0 and start is not None:
                candidates.append(text[start : index + 1])
                start = None

    if not candidates:
        match = FINAL_JSON_PATTERN.search(text)
        if match:
            candidates.append(match.group(0))
    return candidates
