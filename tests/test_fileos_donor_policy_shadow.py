"""The FOS membership profile is shadow-only and does not change snapshot v1."""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

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
    assert {entry["locator"] for entry in result["errors"]} == {"external.txt", "internal.txt"}
    assert {entry["reason"] for entry in result["exclusions"]} == {"symlink_directory"}


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
    original_lstat = Path.lstat
    observations = 0

    def swap_before_recheck(candidate: Path):
        nonlocal observations
        if candidate == path:
            observations += 1
            if observations == 3:
                path.unlink()
                path.symlink_to(outside)
        return original_lstat(candidate)

    monkeypatch.setattr(Path, "lstat", swap_before_recheck)
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
    assert module.run_shadow(repo, 100)["ordinary_matches"] == 104


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
