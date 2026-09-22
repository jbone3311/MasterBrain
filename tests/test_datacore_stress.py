from __future__ import annotations

from pathlib import Path

import pytest

from masterbrain.datacore import dedup


def test_three_thousand_file_scan_has_exact_groups(tmp_path: Path) -> None:
    pairs = 75
    for index in range(pairs):
        payload = f"duplicate-{index}-" + ("x" * 200)
        for offset in (0, 11):
            folder = tmp_path / f"batch-{(index + offset) % 30}"
            folder.mkdir(exist_ok=True)
            (folder / f"copy-{offset}-{index}.dat").write_text(payload, encoding="utf-8")
    for index in range(3000 - pairs * 2):
        folder = tmp_path / f"batch-{index % 30}"
        folder.mkdir(exist_ok=True)
        (folder / f"unique-{index}.dat").write_text(
            f"unique-{index}-{index * 104729}", encoding="utf-8"
        )
    result = dedup.find_duplicates(tmp_path, dedup.DEFAULT_CONFIG.copy())
    assert result["total_files"] == 3000
    assert result["duplicate_groups"] == pairs
    assert result["duplicate_files"] == pairs
    assert result["errors"] == []


def test_hash_collision_with_different_sizes_is_not_counted_as_savings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    first.write_bytes(b"a")
    second.write_bytes(b"different-size")
    monkeypatch.setattr(dedup, "file_hash", lambda *_args, **_kwargs: "f" * 64)
    result = dedup.find_duplicates(tmp_path, dedup.DEFAULT_CONFIG.copy())
    assert result["duplicate_groups"] == 1
    assert result["wasted_bytes"] == 0
    assert result["duplicates"][0]["size_mismatch"] is True
    assert result["duplicates"][0]["sizes_seen"] == [1, 14]


def test_hash_failure_is_visible_not_silently_dropped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    good = tmp_path / "good.txt"
    bad = tmp_path / "bad.txt"
    good.write_text("good", encoding="utf-8")
    bad.write_text("bad", encoding="utf-8")
    original = dedup.file_hash

    def fail_one(path: Path, algorithm: str = "sha256") -> str:
        if Path(path) == bad:
            raise PermissionError("synthetic denied")
        return original(path, algorithm)

    monkeypatch.setattr(dedup, "file_hash", fail_one)
    result = dedup.find_duplicates(tmp_path, dedup.DEFAULT_CONFIG.copy())
    assert result["total_files"] == 2
    assert result["unique_files"] == 1
    assert result["errors"] == [{"path": str(bad), "error": "synthetic denied"}]


def test_component_exclusions_do_not_false_positive(tmp_path: Path) -> None:
    allowed = tmp_path / "Client.db_Archive"
    allowed.mkdir()
    allowed_file = allowed / "PRICE_INDEX_2026.txt"
    allowed_file.write_text("allowed", encoding="utf-8")
    excluded = tmp_path / "actual.db"
    excluded.write_text("excluded", encoding="utf-8")
    result = dedup.find_duplicates(tmp_path, dedup.DEFAULT_CONFIG.copy())
    assert result["total_files"] == 1
    assert result["unique_files"] == 1
