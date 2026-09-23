"""Regression and live-donor parity for the extracted FileOS classifier."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from masterbrain.datacore import fileos_junk_filter as shared

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fileos_junk_parity.py"
SPEC = importlib.util.spec_from_file_location("fileos_junk_parity", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
parity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parity)


def test_extracted_module_differs_only_by_two_type_comments() -> None:
    source = Path(shared.__file__ or "")
    text = source.read_text(encoding="utf-8")
    assert text.count("  # type: ignore[assignment]") == 2
    restored = text.replace("  # type: ignore[assignment]", "")
    assert hashlib.sha256(restored.encode()).hexdigest() == parity.PINNED_SOURCE_SHA256


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        (".Investor Letters/2026/Q1.pdf", "hidden_content"),
        (".trashes/old.pdf", "junk_dir"),
        ("_SYSTEM/state.json", "operational"),
        ("~$draft.docx", "junk_file"),
        (".~lock.foo.odt#", "junk_file"),
        ("_status.html", "junk_file"),
        ("metadata.db", None),
        (".db/child.txt", "hidden_content"),
    ],
)
def test_donor_inventory_policy_regression(path: str, reason: str | None) -> None:
    assert shared.path_skip_reason(path) == reason


def test_3000_synthetic_paths_have_stable_categories() -> None:
    paths = parity.corpus()
    assert len(paths) == 3000
    assert len(set(paths)) == 3000
    assert sum(shared.path_skip_reason(path) is None for path in paths) > 300
    assert sum(shared.path_skip_reason(path) == "hidden_content" for path in paths) > 300
    assert sum(shared.path_skip_reason(path) == "junk_dir" for path in paths) > 300
    assert sum(shared.path_skip_reason(path) == "operational" for path in paths) > 300


def test_parity_harness_reports_a_changed_classifier() -> None:
    altered = ModuleType("altered_donor")
    altered.is_junk_file = lambda _name: True  # type: ignore[attr-defined]
    altered.path_skip_reason = shared.path_skip_reason  # type: ignore[attr-defined]
    altered.is_junk_dir = shared.is_junk_dir  # type: ignore[attr-defined]
    altered.is_operational_dir = shared.is_operational_dir  # type: ignore[attr-defined]
    altered.classify_dir = shared.classify_dir  # type: ignore[attr-defined]
    altered.prune_dirs = shared.prune_dirs  # type: ignore[attr-defined]
    assert parity.compare(altered, ["ordinary/report.txt"]) == [
        {"path": "ordinary/report.txt", "contract": "file", "donor": True, "shared": False}
    ]


def test_live_pinned_donor_classifier_parity() -> None:
    donor_repo = Path(__file__).resolve().parents[2] / "FOS-Master"
    if not donor_repo.is_dir():
        pytest.skip("pinned FOS-Master checkout not available")
    assert parity.compare(parity.load_donor(donor_repo), parity.corpus()) == []
