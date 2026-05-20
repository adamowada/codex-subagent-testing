from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from harness.codex_runner import resolve_codex_bin, resolve_npm_bin
from harness.hidden_runner import load_cases
from harness.matrix import (
    REPO_ROOT,
    benchmark_metadata,
    expand_experiment_matrix,
    load_experiment_config,
    summarize_matrix,
)
from harness.prompt_rendering import (
    render_codex_config,
    render_implementation_prompt,
    render_judge_prompt,
)


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: str
    details: str = ""
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_preflight(
    *,
    config_path: str | Path,
    repo_root: str | Path = REPO_ROOT,
    require_codex: bool = True,
) -> dict[str, Any]:
    """Run environment and harness checks before measured jobs start."""

    root = Path(repo_root)
    checks: list[PreflightCheck] = []
    config: dict[str, Any] | None = None
    runs: list[dict[str, Any]] = []
    config_file = Path(config_path)
    if not config_file.is_absolute():
        config_file = root / config_file

    checks.append(_check_path(config_file, "experiment_config_file"))
    checks.append(_check_path(root / "prompts", "prompts", directory=True))
    checks.append(_check_path(root / "codex_templates", "codex_templates", directory=True))

    for tool in ["git", "node"]:
        checks.append(_check_tool(tool))
    checks.append(_check_npm())

    checks.append(
        PreflightCheck(
            "python",
            "passed",
            sys.executable,
            {"version": sys.version.split()[0]},
        )
    )
    checks.append(_check_python_module("pytest"))

    try:
        config = load_experiment_config(config_file)
        runs = expand_experiment_matrix(config)
    except Exception as exc:
        checks.append(PreflightCheck("experiment_config", "failed", str(exc)))
    else:
        benchmark = benchmark_metadata(config)
        checks.append(_check_path(root / benchmark["template_path"], "benchmark_template", directory=True))
        checks.append(_check_path(root / benchmark["hidden_cases_path"] / "manifest.json", "hidden_manifest"))
        if benchmark["scoring_path"]:
            checks.append(_check_path(root / benchmark["scoring_path"], "scoring_config"))
        checks.append(
            PreflightCheck(
                "experiment_config",
                "passed",
                f"expanded {len(runs)} runs",
                {
                    "summary": summarize_matrix(runs),
                    "benchmark": benchmark,
                },
            )
        )

    if runs:
        try:
            sample_runs = _sample_runs(runs)
            for run in sample_runs:
                render_implementation_prompt(run, root)
                render_judge_prompt(run, root)
                config_files = render_codex_config(run, root)
                if "config.toml" not in config_files:
                    raise ValueError("rendered config missing config.toml")
        except Exception as exc:
            checks.append(PreflightCheck("prompt_rendering", "failed", str(exc)))
        else:
            checks.append(
                PreflightCheck(
                    "prompt_rendering",
                    "passed",
                    f"rendered {len(sample_runs)} sample run(s)",
                )
            )

    if config is not None:
        benchmark = benchmark_metadata(config)
        try:
            manifest, cases = load_cases(root / benchmark["hidden_cases_path"])
        except Exception as exc:
            checks.append(PreflightCheck("hidden_cases", "failed", str(exc)))
        else:
            checks.append(
                PreflightCheck(
                    "hidden_cases",
                    "passed",
                    f"loaded {len(cases)} hidden case definitions",
                    {
                        "benchmark": benchmark,
                        "seed": manifest.get("seed"),
                        "files": sorted(manifest.get("files", {})),
                        "case_count": len(cases),
                    },
                )
            )

    codex_bin = resolve_codex_bin()
    if codex_bin is None:
        status = "failed" if require_codex else "warning"
        checks.append(
            PreflightCheck(
                "codex",
                status,
                'Codex executable not found. Set $env:CODEX_BIN = "path\\to\\working\\codex".',
            )
        )
    else:
        codex_check = _check_codex_version(codex_bin)
        if codex_check.status == "failed" and not require_codex:
            codex_check = PreflightCheck("codex", "warning", codex_check.details, codex_check.data)
        checks.append(codex_check)

    failed = [check for check in checks if check.status == "failed"]
    warnings = [check for check in checks if check.status == "warning"]
    status = "failed" if failed else "warning" if warnings else "passed"
    return {
        "schema_version": 1,
        "status": status,
        "repo_root": str(root),
        "config_path": str(Path(config_path)),
        "benchmark": benchmark_metadata(config) if config is not None else None,
        "codex_bin": codex_bin,
        "checks": [check.to_dict() for check in checks],
    }


def write_preflight(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _check_path(path: Path, name: str, *, directory: bool = False) -> PreflightCheck:
    if directory:
        ok = path.is_dir()
        expected = "directory"
    else:
        ok = path.is_file()
        expected = "file"
    return PreflightCheck(
        name,
        "passed" if ok else "failed",
        str(path) if ok else f"expected {expected}: {path}",
    )


def _check_tool(name: str) -> PreflightCheck:
    resolved = shutil.which(name)
    if resolved is None:
        return PreflightCheck(name, "failed", f"{name} was not found on PATH")
    return PreflightCheck(name, "passed", resolved)


def _check_npm() -> PreflightCheck:
    resolved = resolve_npm_bin()
    if resolved is None:
        return PreflightCheck("npm", "failed", "npm was not found on PATH")

    try:
        completed = subprocess.run(
            [resolved, "--version"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=15,
            check=False,
        )
    except Exception as exc:
        return PreflightCheck("npm", "failed", f"failed to run {resolved!r}: {exc}", {"npm_bin": resolved})

    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        return PreflightCheck(
            "npm",
            "failed",
            details or f"{resolved!r} exited with {completed.returncode}",
            {
                "npm_bin": resolved,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
        )

    return PreflightCheck(
        "npm",
        "passed",
        completed.stdout.strip() or resolved,
        {
            "npm_bin": resolved,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
    )


def _check_python_module(name: str) -> PreflightCheck:
    completed = subprocess.run(
        [sys.executable, "-m", name, "--version"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=15,
        check=False,
    )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        return PreflightCheck(name, "failed", details or f"python module {name!r} is unavailable")
    return PreflightCheck(name, "passed", (completed.stdout or completed.stderr).strip())


def _check_codex_version(codex_bin: str) -> PreflightCheck:
    try:
        completed = subprocess.run(
            [codex_bin, "--version"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=15,
            check=False,
        )
    except Exception as exc:
        return PreflightCheck(
            "codex",
            "failed",
            f"failed to run {codex_bin!r}: {exc}",
            {"codex_bin": codex_bin},
        )

    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        return PreflightCheck(
            "codex",
            "failed",
            details or f"{codex_bin!r} exited with {completed.returncode}",
            {
                "codex_bin": codex_bin,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
        )

    return PreflightCheck(
        "codex",
        "passed",
        completed.stdout.strip() or codex_bin,
        {
            "codex_bin": codex_bin,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
    )


def _sample_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sample: list[dict[str, Any]] = []
    if runs:
        sample.append(runs[0])
    spark = next((run for run in runs if run.get("spark_mode") == "proposal"), None)
    if spark is not None and spark not in sample:
        sample.append(spark)
    c4 = next((run for run in runs if run.get("cell_id") == "C4"), None)
    if c4 is not None and c4 not in sample:
        sample.append(c4)
    return sample
