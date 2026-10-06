"""The FOS membership profile is shadow-only and does not change snapshot v1."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import sqlite3
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from masterbrain.datacore import confined_files
from masterbrain.datacore import fileos_donor_shadow as shadow
from masterbrain.datacore.fileos import INVENTORY_POLICY_VERSION, snapshot_tree
from masterbrain.datacore.persistence import validate_fileos_manifest


def test_donor_membership_is_distinct_from_publishable_v1(tmp_path: Path) -> None:
    files = {
        ".Investor Letters/letter.txt": b"hidden evidence",
        ".db/child.txt": b"dot-directory evidence",
        "metadata.db": b"database evidence",
        "_SYSTEM/state.json": b"operational",
        ".trashes/old.txt": b"junk directory",
        "_status.html": b"status",
        "~$draft.docx": b"lock",
    }
    for locator, data in files.items():
        path = tmp_path / locator
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_bytes(data)
    result = shadow.scan_donor_policy_shadow(tmp_path)
    assert result["publishable"] is False
    assert [row["locator"] for row in result["rows"]] == [
        ".Investor Letters/letter.txt",
        ".db/child.txt",
        "metadata.db",
    ]
    assert {entry["reason"] for entry in result["exclusions"]} == {
        "donor_junk_dir",
        "donor_junk_file",
        "donor_operational_dir",
    }
    assert not result["errors"]
    with pytest.raises((KeyError, ValueError, TypeError)):
        validate_fileos_manifest(result)
    assert INVENTORY_POLICY_VERSION == "fileos-inventory-policy-v1"


def test_distinct_case_and_normalization_siblings_remain_distinct(tmp_path: Path) -> None:
    payloads = {
        "Ledger.txt": b"fictional uppercase record",
        "ledger.txt": b"fictional lowercase record",
        "caf\u00e9.txt": b"fictional composed record",
        "cafe\u0301.txt": b"fictional decomposed record",
    }
    for locator, payload in payloads.items():
        (tmp_path / locator).write_bytes(payload)
    if (
        {entry.name for entry in tmp_path.iterdir()} != set(payloads)
        or any(
            (tmp_path / locator).read_bytes() != payload
            for locator, payload in payloads.items()
        )
    ):
        pytest.skip("this filesystem cannot represent the distinct filename pairs")

    profile = shadow.scan_donor_policy_shadow(tmp_path)
    manifest = snapshot_tree(
        tmp_path, source_id="fictional_fileos", observed_at=datetime(2026, 10, 6, tzinfo=UTC)
    )
    assert profile["errors"] == []
    assert manifest["errors"] == []
    assert {row["locator"] for row in profile["rows"]} == set(payloads)
    assert {item["locator"] for item in manifest["items"]} == set(payloads)
    assert len({item["item_id"] for item in manifest["items"]}) == len(payloads)
    for locator, payload in payloads.items():
        expected_sha = hashlib.sha256(payload).hexdigest()
        assert next(row for row in profile["rows"] if row["locator"] == locator)[
            "sha256"
        ] == expected_sha
        assert next(item for item in manifest["items"] if item["locator"] == locator)[
            "digest"
        ]["value"] == expected_sha


def test_metadata_only_never_reads_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "report.txt").write_bytes(b"fictional")

    def unexpected_read(*args: object, **kwargs: object) -> None:
        raise AssertionError("metadata-only shadow read bytes")

    monkeypatch.setattr(shadow, "read_confined_file", unexpected_read)
    result = shadow.scan_donor_policy_shadow(tmp_path, metadata_only=True)
    assert result["rows"] == [
        {"locator": "report.txt", "size_bytes": 9, "sha256": None, "state": "no_hash"}
    ]


def test_dataless_flag_is_metadata_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "placeholder.txt").write_bytes(b"fictional")
    monkeypatch.setattr(shadow, "_is_dataless", lambda _info: True)
    monkeypatch.setattr(
        shadow, "read_confined_file", lambda *args, **kwargs: pytest.fail("dataless read")
    )
    result = shadow.scan_donor_policy_shadow(tmp_path)
    assert result["rows"][0]["state"] == "dataless"
    assert result["rows"][0]["sha256"] is None


def test_symlinks_are_skipped_without_outside_read(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "ordinary.txt").write_bytes(b"safe")
    (root / "internal.txt").symlink_to(root / "ordinary.txt")
    (root / "external.txt").symlink_to(tmp_path / "outside.txt")
    (tmp_path / "outside.txt").write_bytes(b"outside")
    (root / "folder-link").symlink_to(tmp_path, target_is_directory=True)
    result = shadow.scan_donor_policy_shadow(root)
    assert [row["locator"] for row in result["rows"]] == ["ordinary.txt"]
    assert {entry["locator"] for entry in result["errors"]} == {
        "external.txt", "folder-link", "internal.txt"
    }
    assert {entry["code"] for entry in result["errors"]} == {"symlink_skipped"}
    assert result["exclusions"] == []


def test_symlink_target_type_is_never_queried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_bytes(b"outside")
    (root / "file-link").symlink_to(outside / "secret.txt")
    (root / "dir-link").symlink_to(outside, target_is_directory=True)
    (root / "dangling-link").symlink_to(tmp_path / "missing")
    (root / "ordinary.txt").write_bytes(b"inside")
    real_scandir = os.scandir

    class GuardedEntry:
        def __init__(self, entry: os.DirEntry[str]) -> None:
            self.entry = entry
            self.name = entry.name

        def is_symlink(self) -> bool:
            return self.entry.is_symlink()

        def is_dir(self, *, follow_symlinks: bool = True) -> bool:
            if follow_symlinks:
                raise AssertionError("shadow followed a directory-entry target")
            if self.entry.is_symlink():
                raise AssertionError("shadow queried a symlink target type")
            return self.entry.is_dir(follow_symlinks=False)

    @contextmanager
    def guarded_scandir(directory: int):
        with real_scandir(directory) as entries:
            yield (GuardedEntry(entry) for entry in entries)

    monkeypatch.setattr(shadow.os, "scandir", guarded_scandir)
    result = shadow.scan_donor_policy_shadow(root)
    assert result["rows"] == [
        {
            "locator": "ordinary.txt",
            "size_bytes": 6,
            "sha256": hashlib.sha256(b"inside").hexdigest(),
            "state": "hashed",
        }
    ]
    assert result["exclusions"] == []
    assert result["errors"] == [
        {"locator": "dangling-link", "code": "symlink_skipped"},
        {"locator": "dir-link", "code": "symlink_skipped"},
        {"locator": "file-link", "code": "symlink_skipped"},
    ]


def test_directory_replaced_by_link_after_listing_is_a_coverage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    child = root / "child"
    child.mkdir(parents=True)
    (child / "inside.txt").write_bytes(b"inside")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_bytes(b"outside")
    real_classify = shadow.classify_dir

    def swap_after_listing(name: str) -> str:
        if name == "child":
            child.rename(root / "moved")
            child.symlink_to(outside, target_is_directory=True)
        return real_classify(name)

    monkeypatch.setattr(shadow, "classify_dir", swap_after_listing)
    result = shadow.scan_donor_policy_shadow(root)
    assert result["rows"] == []
    assert result["exclusions"] == []
    assert result["errors"] == [{"locator": "child", "code": "symlink_skipped"}]


def test_special_leaf_keeps_nonregular_exclusion_without_open(tmp_path: Path) -> None:
    special = tmp_path / "named-pipe"
    os.mkfifo(special)
    result = shadow.scan_donor_policy_shadow(tmp_path, metadata_only=True)
    assert result["rows"] == []
    assert result["errors"] == []
    assert result["exclusions"] == [
        {"locator": "named-pipe", "reason": "not_regular"}
    ]


def test_oversize_sparse_file_is_not_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "over.bin"
    with path.open("wb") as out:
        out.truncate(shadow.DONOR_HASH_LIMIT + 1)
    if path.stat().st_size != shadow.DONOR_HASH_LIMIT + 1:
        pytest.skip("sparse-file boundary unavailable")
    monkeypatch.setattr(
        shadow, "read_confined_file", lambda *args, **kwargs: pytest.fail("oversize read")
    )
    result = shadow.scan_donor_policy_shadow(tmp_path)
    assert result["rows"] == [
        {
            "locator": "over.bin",
            "size_bytes": shadow.DONOR_HASH_LIMIT + 1,
            "sha256": None,
            "state": "oversize",
        }
    ]


def test_hash_race_is_visible_not_a_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "report.txt"
    path.write_bytes(b"before")
    real_read = shadow.read_confined_file

    def change_after_read(*args: object, **kwargs: object):
        read = real_read(*args, **kwargs)
        path.write_bytes(b"after a different length")
        return read

    monkeypatch.setattr(shadow, "read_confined_file", change_after_read)
    result = shadow.scan_donor_policy_shadow(tmp_path)
    assert result["rows"] == []
    assert result["errors"] == [{"locator": "report.txt", "code": "changed_during_scan"}]


def test_metadata_only_symlink_swap_never_follows_outside(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    path = root / "report.txt"
    path.write_bytes(b"original")
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside")
    original_stat = os.stat
    observations = 0

    def swap_before_recheck(
        candidate: str | bytes | os.PathLike[str] | os.PathLike[bytes], *args, **kwargs
    ):
        nonlocal observations
        if candidate == "report.txt" and kwargs.get("dir_fd") is not None:
            observations += 1
            if observations == 2:
                path.unlink()
                path.symlink_to(outside)
        return original_stat(candidate, *args, **kwargs)

    monkeypatch.setattr(confined_files.os, "stat", swap_before_recheck)
    result = shadow.scan_donor_policy_shadow(root, metadata_only=True)
    assert result["rows"] == []
    assert result["errors"] == [{"locator": "report.txt", "code": "changed_during_scan"}]


def test_root_identity_swap_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "report.txt").write_bytes(b"fictional")
    original_lstat = Path.lstat
    observations = 0

    def changed_root_stat(candidate: Path):
        nonlocal observations
        result = original_lstat(candidate)
        if candidate == tmp_path:
            observations += 1
            if observations == 2:
                return SimpleNamespace(
                    st_mode=result.st_mode, st_dev=result.st_dev, st_ino=result.st_ino + 1
                )
        return result

    monkeypatch.setattr(Path, "lstat", changed_root_stat)
    result = shadow.scan_donor_policy_shadow(tmp_path)
    assert {error["code"] for error in result["errors"]} == {"root_changed_during_scan"}


def test_metadata_shadow_does_not_catalog_swapped_outside_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "inside.txt").write_bytes(b"fictional")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "external.txt").write_bytes(b"outside metadata")

    real_open = shadow._open_shadow_directory

    def swapped_open(candidate: Path, relative: str, identity: tuple[int, int]) -> int:
        root.rename(tmp_path / "moved")
        root.symlink_to(outside, target_is_directory=True)
        return real_open(candidate, relative, identity)

    monkeypatch.setattr(shadow, "_open_shadow_directory", swapped_open)
    result = shadow.scan_donor_policy_shadow(root, metadata_only=True)
    assert result["rows"] == []
    assert result["errors"] == [{"locator": ".", "code": "root_changed_during_scan"}]


def test_unreadable_directory_is_a_coverage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    unreadable = root / "unreadable"
    unreadable.mkdir()

    real_open = shadow._open_shadow_directory

    def refused_open(candidate: Path, relative: str, identity: tuple[int, int]) -> int:
        if relative == "unreadable":
            raise shadow.ConfinedFileUnavailable()
        return real_open(candidate, relative, identity)

    monkeypatch.setattr(shadow, "_open_shadow_directory", refused_open)
    result = shadow.scan_donor_policy_shadow(root)
    assert result["rows"] == []
    assert result["errors"] == [
        {"locator": "unreadable", "code": "directory_unreadable"}
    ]
    assert result["publishable"] is False


def test_descendant_symlink_swap_does_not_enumerate_outside_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    child = root / "child"
    child.mkdir(parents=True)
    (child / "inside.txt").write_bytes(b"inside")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "_status.html").write_bytes(b"outside")
    real_open = shadow._open_shadow_directory
    real_scandir = os.scandir

    def confined_scandir(directory: int):
        info = os.fstat(directory)
        assert (info.st_dev, info.st_ino) != (outside.stat().st_dev, outside.stat().st_ino)
        return real_scandir(directory)

    def swapped_open(candidate: Path, relative: str, identity: tuple[int, int]) -> int:
        if relative == "child":
            child.rename(root / "moved")
            child.symlink_to(outside, target_is_directory=True)
        return real_open(candidate, relative, identity)

    monkeypatch.setattr(shadow, "_open_shadow_directory", swapped_open)
    monkeypatch.setattr(shadow.os, "scandir", confined_scandir)
    result = shadow.scan_donor_policy_shadow(root)
    assert result["rows"] == []
    assert result["exclusions"] == []
    assert result["errors"] == [
        {"locator": "child", "code": "directory_unreadable"}
    ]


def test_nested_ancestor_swap_does_not_enumerate_outside_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    grandchild = root / "child" / "grandchild"
    grandchild.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "_status.html").write_bytes(b"outside")
    real_open = shadow._open_shadow_directory
    real_scandir = os.scandir

    def confined_scandir(directory: int):
        info = os.fstat(directory)
        assert (info.st_dev, info.st_ino) != (outside.stat().st_dev, outside.stat().st_ino)
        return real_scandir(directory)

    def swapped_open(candidate: Path, relative: str, identity: tuple[int, int]) -> int:
        if relative == "child/grandchild":
            (root / "child").rename(root / "moved")
            (root / "child").symlink_to(outside, target_is_directory=True)
        return real_open(candidate, relative, identity)

    monkeypatch.setattr(shadow, "_open_shadow_directory", swapped_open)
    monkeypatch.setattr(shadow.os, "scandir", confined_scandir)
    result = shadow.scan_donor_policy_shadow(root)
    assert result["rows"] == []
    assert result["exclusions"] == []
    assert result["errors"] == [
        {"locator": "child/grandchild", "code": "directory_unreadable"}
    ]


def test_open_child_moved_before_listing_is_uncertain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    child = root / "child"
    child.mkdir(parents=True)
    (child / "inside.txt").write_bytes(b"inside")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "_status.html").write_bytes(b"outside")
    child_info = child.stat()
    real_scandir = os.scandir

    def moved_before_listing(directory: int):
        info = os.fstat(directory)
        if (info.st_dev, info.st_ino) == (child_info.st_dev, child_info.st_ino):
            child.rename(root / "moved")
            child.symlink_to(outside, target_is_directory=True)
        assert (info.st_dev, info.st_ino) != (outside.stat().st_dev, outside.stat().st_ino)
        return real_scandir(directory)

    monkeypatch.setattr(shadow.os, "scandir", moved_before_listing)
    result = shadow.scan_donor_policy_shadow(root)
    assert result["rows"] == []
    assert result["exclusions"] == []
    assert result["errors"] == [
        {"locator": "child", "code": "directory_unreadable"}
    ]


def test_comparator_does_not_hide_shadow_coverage_error(tmp_path: Path) -> None:
    module = _comparator_module()
    result = shadow.scan_donor_policy_shadow(tmp_path)
    result["errors"].append({"locator": "unreadable", "code": "directory_unreadable"})
    assert module.compare_rows({}, result) == [
        {"locator": "unreadable", "code": "shadow_directory_unreadable"}
    ]


def test_invalid_mode_and_record_budget_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "one.txt").write_bytes(b"x")
    with pytest.raises(ValueError, match="boolean"):
        shadow.scan_donor_policy_shadow(tmp_path, metadata_only=1)  # type: ignore[arg-type]
    monkeypatch.setattr(shadow, "MAX_SHADOW_RECORDS", 0)
    with pytest.raises(ValueError, match="record limit"):
        shadow.scan_donor_policy_shadow(tmp_path)


def test_existing_snapshot_policy_is_unchanged(tmp_path: Path) -> None:
    (tmp_path / "metadata.db").write_bytes(b"fictional")
    from datetime import UTC, datetime

    current = snapshot_tree(
        tmp_path, source_id="still-v1", observed_at=datetime(2026, 9, 30, tzinfo=UTC)
    )
    assert current["policy"]["policy_version"] == INVENTORY_POLICY_VERSION
    assert current["items"] == []


def test_live_pinned_donor_policy_parity() -> None:
    repo = Path(__file__).resolve().parents[2] / "FOS-Master"
    if not repo.is_dir():
        pytest.skip("pinned donor checkout is not present on this runner")
    module = _comparator_module()
    result = module.run_shadow(repo, 100)
    assert result["ordinary_matches"] == 104
    assert result["candidate_hashed_matches"] == 104
    assert result["candidate_metadata_only_matches"] == 104
    assert result["transition_prior_matches"] == 106
    assert result["transition_policy_gaps"] == 6


def test_transition_stress_bound_fails_before_donor_load(tmp_path: Path) -> None:
    module = _comparator_module()
    with pytest.raises(ValueError, match="v1 manifest capacity"):
        module.run_shadow(tmp_path / "not-a-donor", 9995)


def _comparator_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "fileos_donor_policy_shadow.py"
    spec = importlib.util.spec_from_file_location("fileos_donor_policy_shadow", script)
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(script.parent))
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(script.parent))


def test_live_pinned_donor_size_boundary_and_deferred_state(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2] / "FOS-Master"
    if not repo.is_dir():
        pytest.skip("pinned donor checkout is not present on this runner")
    module = _comparator_module()
    scanner = module.load_pinned_scanner(repo)
    just_over_v1 = tmp_path / "over-v1.bin"
    over_donor = tmp_path / "over-donor.bin"
    with just_over_v1.open("wb") as out:
        out.truncate(100 * 1024**2 + 1)
    with over_donor.open("wb") as out:
        out.truncate(shadow.DONOR_HASH_LIMIT + 1)
    with sqlite3.connect(":memory:") as conn:
        scanner.ensure_schema(conn)
        module.donor_scan(scanner, tmp_path, conn)
        result = shadow.scan_donor_policy_shadow(tmp_path)
        assert module.compare_rows(module.donor_rows(conn), result, allow_deferred=True) == []
        assert {row["locator"]: row["state"] for row in result["rows"]} == {
            "over-v1.bin": "hashed",
            "over-donor.bin": "oversize",
        }
        assert module.compare_rows(module.donor_rows(conn), result) == [
            {"locator": "over-donor.bin", "code": "unverified_hashless"}
        ]
