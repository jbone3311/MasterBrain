#!/usr/bin/env python3
"""Repository quality gate for Factory/CI; not a production-launch certificate."""

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
    "docs/PRD.md",
    "docs/API_MCP_SPEC.md",
    "docs/IMPLEMENTATION_STATUS.md",
    "docs/OPEN_QUESTIONS.md",
    "docs/LOCAL_DEVELOPMENT.md",
)
FORBIDDEN_SUFFIXES = {".eml", ".mbox", ".pst", ".ost", ".sqlite", ".db"}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    if missing:
        fail(f"missing required files: {', '.join(missing)}")

    # Inspect versioned content, including hidden folders; never scan generated venvs.
    tracked = (
        subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True)
        .stdout.decode()
        .split("\0")
    )
    forbidden = [
        name for name in tracked if name and Path(name).suffix.lower() in FORBIDDEN_SUFFIXES
    ]
    if forbidden:
        fail(f"forbidden private-data file types present: {forbidden}")

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        env=environment,
        check=False,
    )
    if completed.returncode:
        fail("tests failed")

    print(
        "PASS: repository quality gate; production launch gates remain in IMPLEMENTATION_STATUS.md"
    )


if __name__ == "__main__":
    main()
