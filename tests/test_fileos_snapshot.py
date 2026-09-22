from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from masterbrain.datacore.fileos import snapshot_tree

NOW = datetime(2026, 9, 22, 12, tzinfo=UTC)


def snapshot(root: Path, **kwargs: object) -> dict[str, object]:
    return snapshot_tree(root, source_id="files_test", observed_at=NOW, **kwargs)


def test_snapshot_is_deterministic_sorted_and_portable(tmp_path: Path) -> None:
    (tmp_path / "z.txt").write_text("z", encoding="utf-8")
    folder = tmp_path / "a"
    folder.mkdir()
    (folder / "empty.bin").write_bytes(b"")
    (folder / "report.txt").write_text("report", encoding="utf-8")

    first = snapshot(tmp_path)
    second = snapshot(tmp_path)

    assert first == second
    assert first["counts"] == {"items": 3, "excluded": 0, "errors": 0}
    items = first["items"]
    assert isinstance(items, list)
    assert [item["locator"] for item in items] == ["a/empty.bin", "a/report.txt", "z.txt"]
    assert str(tmp_path) not in str(first)


def test_snapshot_preserves_item_identity_but_versions_content(tmp_path: Path) -> None:
    path = tmp_path / "report.txt"
    path.write_text("one", encoding="utf-8")
    first = snapshot(tmp_path)["items"][0]
    path.write_text("two-two", encoding="utf-8")
    second = snapshot(tmp_path)["items"][0]
    assert first["item_id"] == second["item_id"]
    assert first["version_id"] != second["version_id"]
    assert first["digest"] != second["digest"]


def test_snapshot_uses_donor_exclusions_and_bounds(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_text("keep", encoding="utf-8")
    (tmp_path / "metadata.db").write_text("excluded", encoding="utf-8")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "ignored.txt").write_text("ignored", encoding="utf-8")
    result = snapshot(tmp_path, config={
        "hash_algorithm": "sha256",
        "min_file_size": 0,
        "max_file_size_mb": 100,
        "exclude_patterns": [".db", "__pycache__"],
        "include_extensions": [".txt"],
    })
    assert result["counts"] == {"items": 1, "excluded": 2, "errors": 0}
    assert result["items"][0]["locator"] == "keep.txt"


def test_snapshot_skips_symlinks_by_default(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("same", encoding="utf-8")
    os.symlink(target, tmp_path / "link.txt")
    result = snapshot(tmp_path)
    assert result["counts"] == {"items": 1, "excluded": 0, "errors": 1}
    assert result["errors"] == [{"locator": "link.txt", "code": "symlink_skipped"}]


def test_snapshot_can_follow_internal_file_symlink_but_never_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "target.txt"
    target.write_text("inside", encoding="utf-8")
    os.symlink(target, root / "inside-link.txt")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    os.symlink(outside, root / "outside-link.txt")
    result = snapshot(root, follow_file_symlinks=True)
    assert [item["locator"] for item in result["items"]] == ["inside-link.txt", "target.txt"]
    assert result["errors"] == [
        {"locator": "outside-link.txt", "code": "symlink_outside_root"}
    ]


def test_snapshot_detects_mid_scan_change(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "changing.txt"
    path.write_text("before", encoding="utf-8")

    def mutate(candidate: Path, algorithm: str = "sha256") -> str:
        candidate.write_text("after-change", encoding="utf-8")
        return "0" * 64

    monkeypatch.setattr("masterbrain.datacore.fileos.file_hash", mutate)
    result = snapshot(tmp_path)
    assert result["items"] == []
    assert result["errors"] == [{"locator": "changing.txt", "code": "changed_during_scan"}]


def test_snapshot_does_not_modify_source_tree(tmp_path: Path) -> None:
    (tmp_path / "one.txt").write_text("one", encoding="utf-8")
    before = sorted(
        (path.relative_to(tmp_path).as_posix(), path.read_bytes())
        for path in tmp_path.rglob("*")
        if path.is_file()
    )
    snapshot(tmp_path)
    after = sorted(
        (path.relative_to(tmp_path).as_posix(), path.read_bytes())
        for path in tmp_path.rglob("*")
        if path.is_file()
    )
    assert after == before


def test_snapshot_rejects_naive_time_and_invalid_source(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        snapshot_tree(tmp_path, source_id="Bad Source", observed_at=NOW)
    with pytest.raises(ValueError):
        snapshot_tree(tmp_path, source_id="files_test", observed_at=datetime(2026, 9, 22))
