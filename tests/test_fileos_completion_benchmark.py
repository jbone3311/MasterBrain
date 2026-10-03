"""Refusal checks for the opt-in synthetic FileOS performance audit."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/benchmark_fileos_v1_completion.py"
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}


@pytest.mark.parametrize("dsn", ["dbname=postgres", "dbname=email_brain_test"])
def test_benchmark_refuses_non_disposable_database_before_connecting(dsn):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--admin-dsn", dsn],
        capture_output=True,
        text=True,
        check=False,
        env=ENV,
    )
    assert result.returncode != 0
    assert "benchmark refused" in result.stderr


def test_benchmark_cli_never_echoes_unsafe_dsn():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--admin-dsn", "dbname=postgres password=fictional-secret"],
        capture_output=True,
        text=True,
        check=False,
        env=ENV,
    )
    assert result.returncode != 0
    assert "fictional-secret" not in result.stdout + result.stderr


@pytest.mark.parametrize("rows", [0, 3001])
def test_benchmark_refuses_out_of_bound_row_count_before_connecting(rows):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--admin-dsn", "dbname=email_brain_test_benchmark_absent",
         "--rows", str(rows)],
        capture_output=True,
        text=True,
        check=False,
        env=ENV,
    )
    assert result.returncode != 0
    assert "benchmark refused" in result.stderr
