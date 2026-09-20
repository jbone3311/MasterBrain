#!/usr/bin/env python3
"""Fast, dependency-free repository gate for Factory and CI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md",
    "PRODUCT.md",
    "AGENTS.md",
    "docs/SECURITY.md",
    "docs/ARCHITECTURE.md",
    "docs/DATA_MODEL.md",
    "docs/DECISIONS.md",
    "docs/FACTORY_HANDOFF.md",
    "migrations/0001_core.sql",
)
FORBIDDEN_SUFFIXES = {".eml", ".mbox", ".pst", ".ost", ".sqlite", ".db"}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    if missing:
        fail(f"missing required files: {', '.join(missing)}")

    forbidden = [
        path.relative_to(ROOT)
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix.lower() in FORBIDDEN_SUFFIXES
        and not any(part.startswith(".") for part in path.relative_to(ROOT).parts)
    ]
    if forbidden:
        fail(f"forbidden private-data file types present: {forbidden}")

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT,
        env=environment,
        check=False,
    )
    if completed.returncode:
        fail("unit tests failed")

    print("PASS: repository deployment gate")


if __name__ == "__main__":
    main()
