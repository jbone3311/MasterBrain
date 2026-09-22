from __future__ import annotations

import hashlib
from pathlib import Path

from masterbrain.datacore.dedup import DEFAULT_CONFIG, compare_files, file_hash, find_duplicates


def test_hash_matches_sha256(tmp_path: Path) -> None:
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"MasterBrain parity\n")
    assert file_hash(sample) == hashlib.sha256(sample.read_bytes()).hexdigest()


def test_duplicate_contract_and_exclusions(tmp_path: Path) -> None:
    (tmp_path / "alpha.txt").write_text("same content", encoding="utf-8")
    (tmp_path / "alpha_copy.txt").write_text("same content", encoding="utf-8")
    (tmp_path / "unique.txt").write_text("unique", encoding="utf-8")
    hidden = tmp_path / ".git"
    hidden.mkdir()
    (hidden / "ignored.txt").write_text("same content", encoding="utf-8")

    result = find_duplicates(tmp_path, DEFAULT_CONFIG.copy())

    assert result["total_files"] == 3
    assert result["duplicate_groups"] == 1
    assert result["duplicate_files"] == 1
    assert result["wasted_bytes"] == len(b"same content")
    assert result["errors"] == []


def test_compare_contract(tmp_path: Path) -> None:
    first = tmp_path / "report.txt"
    second = tmp_path / "report_copy.txt"
    first.write_text("hello world", encoding="utf-8")
    second.write_text("hello world", encoding="utf-8")

    result = compare_files(first, second, DEFAULT_CONFIG.copy())

    assert result["identical"] is True
    assert result["same_size"] is True
    assert result["content_similarity"] == 1.0
