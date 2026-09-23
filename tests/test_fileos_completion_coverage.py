"""Fail-closed coverage checks before a FileOS inventory can be completed."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

import masterbrain.datacore.fileos as fileos_module
from masterbrain.datacore.fileos import (
    fileos_inventory_policy,
    fileos_root_binding_sha256,
    snapshot_tree,
)
from masterbrain.datacore.persistence import (
    fileos_inventory_policy_sha256,
    fileos_manifest_root_binding_sha256,
    fileos_mass_loss_requires_review,
    fileos_missing_locator_is_excluded,
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


def test_exclusion_ledger_accounts_for_policy_size_type_and_directory(tmp_path: Path) -> None:
    (tmp_path / ".db").mkdir()
    (tmp_path / ".db" / "nested.txt").write_bytes(b"fictional")
    (tmp_path / "large.txt").write_bytes(b"x" * (1_048_576 + 1))
    (tmp_path / "wrong.bin").write_bytes(b"fictional")
    (tmp_path / "kept.txt").write_bytes(b"fictional")
    policy = {
        "min_file_size": 0,
        "max_file_size_mb": 1,
        "include_extensions": [".txt"],
        "exclude_patterns": [".db"],
    }
    manifest = snapshot_tree(
        tmp_path, source_id="coverage_test", observed_at=OBSERVED, config=policy
    )
    assert manifest["exclusions"] == [
        {"locator": ".db", "kind": "directory", "reason": "policy_path"},
        {"locator": "large.txt", "kind": "file", "reason": "above_max_size"},
        {"locator": "wrong.bin", "kind": "file", "reason": "extension_filtered"},
    ]
    assert manifest["counts"]["excluded"] == 3
    assert [item["locator"] for item in manifest["items"]] == ["kept.txt"]
    validate_fileos_completion_coverage(manifest)
    assert fileos_missing_locator_is_excluded(
        ".db/nested.txt", {"large.txt", "wrong.bin"}, {".db"}, set()
    )
    assert not fileos_missing_locator_is_excluded(
        "genuinely-gone.txt", {"large.txt", "wrong.bin"}, {".db"}, set()
    )
    assert fileos_missing_locator_is_excluded("link.txt", set(), set(), {"link.txt"})


def test_min_size_and_no_follow_directory_have_exclusion_records(tmp_path: Path) -> None:
    (tmp_path / "small.txt").write_bytes(b"x")
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "fictional.txt").write_bytes(b"fictional")
    (tmp_path / "linked").symlink_to(real_dir, target_is_directory=True)
    manifest = snapshot_tree(
        tmp_path,
        source_id="coverage_test",
        observed_at=OBSERVED,
        config={"min_file_size": 2, "exclude_patterns": []},
    )
    assert manifest["exclusions"] == [
        {"locator": "linked", "kind": "directory", "reason": "symlink_directory"},
        {"locator": "small.txt", "kind": "file", "reason": "below_min_size"},
    ]
    validate_fileos_completion_coverage(manifest)


@pytest.mark.parametrize("defect", ["missing", "count", "duplicate", "overlap", "reason", "order"])
def test_malformed_exclusion_ledger_blocks_completion(tmp_path: Path, defect: str) -> None:
    (tmp_path / "kept.txt").write_bytes(b"fictional")
    (tmp_path / "bad.bin").write_bytes(b"fictional")
    manifest = snapshot_tree(
        tmp_path,
        source_id="coverage_test",
        observed_at=OBSERVED,
        config={"include_extensions": [".txt"], "exclude_patterns": []},
    )
    if defect == "missing":
        del manifest["exclusions"]
    elif defect == "count":
        manifest["counts"]["excluded"] = 0
    elif defect == "duplicate":
        manifest["exclusions"].append(manifest["exclusions"][0].copy())
        manifest["counts"]["excluded"] = 2
    elif defect == "overlap":
        manifest["exclusions"][0]["locator"] = "kept.txt"
    elif defect == "reason":
        manifest["exclusions"][0]["reason"] = "untrusted"
    else:
        manifest["exclusions"].append(
            {"locator": "a.bin", "kind": "file", "reason": "extension_filtered"}
        )
        manifest["counts"]["excluded"] = 2
    with pytest.raises(ValueError, match="exclusion coverage"):
        validate_fileos_completion_coverage(manifest)


def test_exclusion_ledger_overflow_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a.bin").write_bytes(b"fictional")
    (tmp_path / "b.bin").write_bytes(b"fictional")
    monkeypatch.setattr(fileos_module, "MAX_SNAPSHOT_EXCLUSIONS", 1)
    manifest = snapshot_tree(
        tmp_path,
        source_id="coverage_test",
        observed_at=OBSERVED,
        config={"include_extensions": [".txt"], "exclude_patterns": []},
    )
    assert manifest["counts"]["excluded"] == 2
    assert manifest["errors"] == [{"locator": ".", "code": "exclusion_ledger_overflow"}]
    with pytest.raises(ValueError, match="coverage"):
        validate_fileos_completion_coverage(manifest)


def test_root_binding_is_stable_for_alias_and_distinct_for_other_roots(tmp_path: Path) -> None:
    first = tmp_path / "first"
    other = tmp_path / "other"
    first.mkdir()
    other.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(first, target_is_directory=True)
    first_hash = fileos_root_binding_sha256(first)
    assert first_hash == fileos_root_binding_sha256(alias)
    assert first_hash != fileos_root_binding_sha256(other)
    manifest = _manifest(first)
    assert fileos_manifest_root_binding_sha256(manifest) == first_hash


def test_root_binding_changes_if_directory_is_replaced_at_same_path(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    original_hash = fileos_root_binding_sha256(root)
    root.rename(tmp_path / "old_root")
    root.mkdir()
    assert fileos_root_binding_sha256(root) != original_hash


@pytest.mark.parametrize("defect", ["missing", "version", "digest", "extra"])
def test_invalid_root_binding_refuses_completion(tmp_path: Path, defect: str) -> None:
    manifest = _manifest(tmp_path)
    if defect == "missing":
        del manifest["root_binding"]
    elif defect == "version":
        manifest["root_binding"]["version"] = "fileos-root-binding-v0"
    elif defect == "digest":
        manifest["root_binding"]["sha256"] = "A" * 64
    else:
        manifest["root_binding"]["path"] = str(tmp_path)
    with pytest.raises(ValueError, match="root binding"):
        validate_fileos_completion_coverage(manifest)


def test_root_change_during_scan_refuses_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = fileos_module.fileos_root_binding_sha256
    calls = 0

    def changed(root: Path) -> str:
        nonlocal calls
        calls += 1
        return original(root) if calls == 1 else "0" * 64

    monkeypatch.setattr(fileos_module, "fileos_root_binding_sha256", changed)
    manifest = _manifest(tmp_path)
    assert manifest["errors"] == [{"locator": ".", "code": "root_changed_during_scan"}]
    with pytest.raises(ValueError, match="coverage"):
        validate_fileos_completion_coverage(manifest)
