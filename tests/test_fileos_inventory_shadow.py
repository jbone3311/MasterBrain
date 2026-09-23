"""Synthetic-only contracts for the FileOS scanner shadow comparator."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fileos_inventory_shadow.py"
SPEC = importlib.util.spec_from_file_location("fileos_inventory_shadow", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
shadow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shadow)


def _manifest(*items: tuple[str, int, str], errors: list[dict[str, str]] | None = None) -> dict:
    return {
        "items": [
            {"locator": locator, "size_bytes": size, "digest": {"value": sha}}
            for locator, size, sha in items
        ],
        "errors": [] if errors is None else errors,
    }


def test_common_digest_and_size_must_match(tmp_path: Path) -> None:
    rows = {"report.txt": {"size_bytes": 3, "sha256": "abc"}}
    assert shadow.compare_inventory(tmp_path, rows, _manifest(("report.txt", 3, "abc"))) == {
        "common": 1,
        "differences": [],
    }
    mismatch = shadow.compare_inventory(tmp_path, rows, _manifest(("report.txt", 3, "other")))
    assert mismatch["differences"] == [{"locator": "report.txt", "code": "common_sha256_mismatch"}]
    mismatch = shadow.compare_inventory(tmp_path, rows, _manifest(("report.txt", 4, "abc")))
    assert mismatch["differences"] == [{"locator": "report.txt", "code": "common_size_mismatch"}]


def test_known_policy_difference_is_reason_coded(tmp_path: Path) -> None:
    rows = {
        ".db/child.txt": {"size_bytes": 1, "sha256": "a"},
        "metadata.db": {"size_bytes": 1, "sha256": "b"},
    }
    actual = shadow.compare_inventory(
        tmp_path, rows, _manifest(("~$draft.docx", 1, "c"), ("_SYSTEM/state.json", 1, "d"))
    )
    assert actual["differences"] == [
        {"locator": ".db/child.txt", "code": "shared_dedupe_exclusion"},
        {"locator": "_SYSTEM/state.json", "code": "donor_operational"},
        {"locator": "metadata.db", "code": "shared_dedupe_exclusion"},
        {"locator": "~$draft.docx", "code": "donor_junk_file"},
    ]


def test_unexplained_and_hashless_are_not_equivalent(tmp_path: Path) -> None:
    rows = {
        "lost.txt": {"size_bytes": 1, "sha256": "a"},
        "nohash.txt": {"size_bytes": 1, "sha256": None},
    }
    manifest = _manifest(("nohash.txt", 1, "b"), ("unexpected.txt", 1, "c"))
    actual = shadow.compare_inventory(tmp_path, rows, manifest)
    assert actual["differences"] == [
        {"locator": "lost.txt", "code": "unexplained_donor_only"},
        {"locator": "nohash.txt", "code": "unexpected_donor_hashless"},
        {"locator": "unexpected.txt", "code": "unexplained_shared_only"},
    ]
    deferred = shadow.compare_inventory(tmp_path, rows, manifest, allow_hashless=True)
    assert {difference["code"] for difference in deferred["differences"]} == {
        "unexplained_donor_only",
        "donor_hash_deferred",
        "unexplained_shared_only",
    }


def test_snapshot_errors_remain_visible(tmp_path: Path) -> None:
    actual = shadow.compare_inventory(
        tmp_path,
        {},
        _manifest(errors=[{"locator": "inaccessible", "code": "directory_unreadable"}]),
    )
    assert actual["differences"] == [
        {"locator": "inaccessible", "code": "shared_directory_unreadable"}
    ]


def test_fixture_is_fictional_and_bound_to_requested_size(tmp_path: Path) -> None:
    root = tmp_path / "synthetic"
    root.mkdir()
    shadow.make_synthetic_tree(root, 100)
    assert len(list(root.rglob("record_*.txt"))) == 100
    assert (root / ".Investor Letters" / "2026" / "letter.txt").is_file()
    assert shadow.baseline_expected() == sorted(
        shadow.baseline_expected(), key=lambda diff: (diff["locator"], diff["code"])
    )
    with pytest.raises(ValueError):
        shadow.make_synthetic_tree(tmp_path, 99)


def test_shadow_refuses_file_backed_donor_database(tmp_path: Path) -> None:
    class Scanner:
        pass

    with sqlite3.connect(tmp_path / "synthetic.sqlite") as conn:
        with pytest.raises(ValueError, match="in-memory"):
            shadow.donor_scan(Scanner(), tmp_path, conn)


def test_live_pinned_donor_full_inventory_shadow() -> None:
    repo = Path(__file__).resolve().parents[2] / "FOS-Master"
    if not repo.is_dir():
        pytest.skip("pinned donor checkout is not present on this runner")
    result = shadow.run_shadow(repo, 100)
    assert result["baseline_common"] == 102
    assert result["changed_updated"] == 1
    assert result["single_removed"] == 1
    assert result["mass_prune_refused"] == result["mass_retained_vs_snapshot"]
    assert result["symlink_policy_differences"] == 2
