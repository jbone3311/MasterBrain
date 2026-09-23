"""Fail-closed coverage checks before a FileOS inventory can be completed."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from masterbrain.datacore.fileos import fileos_inventory_policy, snapshot_tree
from masterbrain.datacore.persistence import (
    fileos_inventory_policy_sha256,
    fileos_mass_loss_requires_review,
    validate_fileos_completion_coverage,
)

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


@pytest.mark.parametrize(
    ("previous", "missing", "requires_review"),
    [
        (0, 0, False),
        (20, 9, False),
        (20, 10, True),
        (100, 49, False),
        (100, 50, True),
        (18, 10, True),
    ],
)
def test_mass_loss_threshold(previous: int, missing: int, requires_review: bool) -> None:
    assert fileos_mass_loss_requires_review(previous, missing) is requires_review


def test_policy_identity_is_stable_across_observations_but_detects_drift(
    tmp_path: Path,
) -> None:
    (tmp_path / "fictional.txt").write_bytes(b"fictional evidence")
    first = _manifest(tmp_path)
    assert first["policy"] == fileos_inventory_policy()
    later = snapshot_tree(
        tmp_path,
        source_id="coverage_test",
        observed_at=datetime(2026, 9, 24, tzinfo=UTC),
    )
    baseline = fileos_inventory_policy_sha256(first)
    assert baseline == fileos_inventory_policy_sha256(later)
    assert first["policy"]["policy_version"] == "fileos-inventory-policy-v1"
    for field, value in (
        ("exclude_patterns", ["fictional.txt"]),
        ("max_file_size_mb", 1),
        ("follow_file_symlinks", True),
    ):
        changed = _manifest(tmp_path)
        changed["policy"][field] = value
        assert fileos_inventory_policy_sha256(changed) != baseline


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("policy_version", "unknown-policy"),
        ("hash_algorithm", "md5"),
        ("follow_file_symlinks", 1),
        ("min_file_size", -1),
        ("max_file_size_mb", 0),
        ("include_extensions", [17]),
        ("exclude_patterns", ["bad\x00pattern"]),
    ],
)
def test_invalid_policy_cannot_complete(tmp_path: Path, field: str, value: object) -> None:
    manifest = _manifest(tmp_path)
    manifest["policy"][field] = value
    with pytest.raises(ValueError, match="inventory policy"):
        validate_fileos_completion_coverage(manifest)


def test_missing_or_extra_policy_field_cannot_complete(tmp_path: Path) -> None:
    missing = _manifest(tmp_path)
    del missing["policy"]["policy_version"]
    with pytest.raises(ValueError, match="inventory policy"):
        validate_fileos_completion_coverage(missing)
    extra = _manifest(tmp_path)
    extra["policy"]["unknown"] = True
    with pytest.raises(ValueError, match="inventory policy"):
        validate_fileos_completion_coverage(extra)
