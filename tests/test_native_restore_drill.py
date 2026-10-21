"""Safety contract for the opt-in native synthetic restore runner."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "native_restore_drill.py"


def test_native_drill_requires_explicit_opt_in() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, timeout=10, check=False,
    )
    assert result.returncode == 2
    assert b"--run-disposable" in result.stderr


def test_native_drill_refuses_ambient_postgres_configuration() -> None:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    environment["PGDATABASE"] = "not-a-disposable-database"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--run-disposable"],
        capture_output=True, timeout=10, check=False, env=environment,
    )
    assert result.returncode == 1
    response = json.loads(result.stdout)
    assert response == {
        "status": "failed", "synthetic_only": True,
        "detail": "ambient PostgreSQL settings are forbidden for this disposable drill",
    }


def test_native_drill_has_no_existing_database_or_archive_arguments() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--run-disposable", "--dsn", "production"],
        capture_output=True, timeout=10, check=False,
    )
    assert result.returncode == 2
    assert b"unrecognized arguments" in result.stderr
