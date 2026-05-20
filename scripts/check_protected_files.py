#!/usr/bin/env python3
"""Fail if locked source-of-truth documents changed unexpectedly."""

from __future__ import annotations

import hashlib
import pathlib
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

PROTECTED_FILE_HASHES = {
    "AGENTS.md": "14f70718e9c17f898c718eebe6dd9310c0944cffb7c9692f5d919b806b1b75ea",
    "LICENSE": "9de22418cb252f9166b7bb76133212f3205de2d878947dd952f9d52dd61c3534",
    "PLANS.md": "9c0024ba8eaa80b3547c0c698aa486491a239cbe3e0347c4a796801cbcb6dc1b",
    "README.md": "e967db88c98f2e47b7fc03c37e443e495ed37a2818cac8ab7194781d953b5eaf",
}


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    failures: list[str] = []

    for relative_path, expected_hash in PROTECTED_FILE_HASHES.items():
        path = REPO_ROOT / relative_path
        if not path.exists():
            failures.append(f"{relative_path}: missing")
            continue

        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            failures.append(
                f"{relative_path}: changed\n"
                f"  expected: {expected_hash}\n"
                f"  actual:   {actual_hash}"
            )

    if failures:
        print("Protected source-of-truth files changed unexpectedly.", file=sys.stderr)
        print("", file=sys.stderr)
        for failure in failures:
            print(failure, file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "These files are locked: AGENTS.md, LICENSE, PLANS.md, README.md.",
            file=sys.stderr,
        )
        print(
            "Only update them, and then update this guard, when the user gives clear instructions.",
            file=sys.stderr,
        )
        return 1

    print("Protected source-of-truth files are unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
