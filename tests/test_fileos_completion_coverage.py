"""Fail-closed coverage checks before a FileOS inventory can be completed."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from masterbrain.datacore.fileos import snapshot_tree
from masterbrain.datacore.persistence import validate_fileos_completion_coverage

OBSERVED = datetime(2026, 9, 23, tzinfo=UTC)


def _manifest(root: Path) -> dict:
    return snapshot_tree(root, source_id="coverage_test", observed_at=OBSERVED)


def test_complete_snapshot_and_intentional_no_follow_skip(tmp_path: Path) -> None:
    (tmp_path / "kept.txt").write_bytes(b"fictional evidence")
    manifest = _manifest(tmp_path)
    validate_fileos_completion_coverage(manifest)
    (tmp_path / "link.txt").symlink_to(tmp_path / "kept.txt")
    skipped = _manifest(tmp_path)
    assert skipped["errors"] == [{"locator": "link.txt", "code": "symlink_skipped"}]
    validate_fileos_completion_coverage(skipped)


@pytest.mark.parametrize(
    "code",
    [
        "directory_unreadable",
        "file_unreadable",
        "changed_during_scan",
        "symlink_outside_root",
        "unrecognized_error",
    ],
)
def test_uncertain_coverage_blocks_completion(tmp_path: Path, code: str) -> None:
    manifest = _manifest(tmp_path)
    manifest["errors"] = [{"locator": "fictional.txt", "code": code}]
    manifest["counts"]["errors"] = 1
    with pytest.raises(ValueError, match="coverage"):
        validate_fileos_completion_coverage(manifest)


@pytest.mark.parametrize("defect", ["missing", "count", "duplicate", "overlap", "policy"])
def test_malformed_coverage_ledger_blocks_completion(tmp_path: Path, defect: str) -> None:
    (tmp_path / "kept.txt").write_bytes(b"fictional evidence")
    manifest = _manifest(tmp_path)
    manifest["errors"] = [{"locator": "link.txt", "code": "symlink_skipped"}]
    manifest["counts"]["errors"] = 1
    if defect == "missing":
        del manifest["errors"]
    elif defect == "count":
        manifest["counts"]["errors"] = 0
    elif defect == "duplicate":
        manifest["errors"].append(manifest["errors"][0].copy())
        manifest["counts"]["errors"] = 2
    elif defect == "overlap":
        manifest["errors"][0]["locator"] = "kept.txt"
    else:
        manifest["policy"]["follow_file_symlinks"] = True
    with pytest.raises(ValueError, match="coverage"):
        validate_fileos_completion_coverage(manifest)
