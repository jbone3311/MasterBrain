"""Synthetic descriptor-boundary regressions for FileOS source bytes."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from masterbrain.datacore import confined_files
from masterbrain.datacore.confined_files import (
    ConfinedFileChanged,
    ConfinedFileTooLarge,
    ConfinedFileUnavailable,
    read_confined_file,
)
from masterbrain.datacore.extraction import (
    ExtractionStatus,
    extract_document_source_version,
    extract_source_version,
)
from masterbrain.datacore.fileos import snapshot_tree


def _item(locator: str, raw: bytes) -> dict[str, object]:
    return {
        "locator": locator,
        "version_id": "version_synthetic",
        "digest": {"algorithm": "sha256", "value": hashlib.sha256(raw).hexdigest()},
        "size_bytes": len(raw),
        "media_type": "application/pdf" if locator.endswith(".pdf") else "text/plain",
    }


def test_confined_reader_hashes_nested_and_empty_files(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "proof.txt").write_bytes(b"fictional proof")
    (nested / "empty.txt").write_bytes(b"")
    hashed = read_confined_file(tmp_path, "nested/proof.txt", max_bytes=100, capture_bytes=False)
    assert hashed.sha256 == hashlib.sha256(b"fictional proof").hexdigest()
    assert hashed.size_bytes == 15 and hashed.raw is None
    captured = read_confined_file(tmp_path, "nested/empty.txt", max_bytes=0, capture_bytes=True)
    assert captured.raw == b"" and captured.size_bytes == 0
    with pytest.raises(ConfinedFileTooLarge):
        read_confined_file(tmp_path, "nested/proof.txt", max_bytes=14, capture_bytes=False)


@pytest.mark.parametrize("locator", ["../outside.txt", "/absolute.txt", "a//b", "a/./b", "a\\b"])
def test_confined_reader_refuses_unsafe_locator(tmp_path: Path, locator: str) -> None:
    with pytest.raises(ConfinedFileUnavailable):
        read_confined_file(tmp_path, locator, max_bytes=100, capture_bytes=True)


def test_confined_reader_rejects_leaf_swap_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside secret must not be read")
    leaf = root / "proof.txt"
    leaf.write_bytes(b"fictional proof")
    original = confined_files._open_confined_descriptor
    calls = 0

    def swapped(candidate_root: Path, locator: str) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            leaf.unlink()
            leaf.symlink_to(outside)
        return original(candidate_root, locator)

    monkeypatch.setattr(confined_files, "_open_confined_descriptor", swapped)
    with pytest.raises(ConfinedFileUnavailable):
        read_confined_file(root, "proof.txt", max_bytes=100, capture_bytes=True)
    assert calls == 1


def test_confined_reader_rejects_ancestor_swap_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (nested / "proof.txt").write_bytes(b"fictional proof")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "proof.txt").write_bytes(b"outside secret must not be read")
    original = confined_files._open_confined_descriptor

    def swapped(candidate_root: Path, locator: str) -> int:
        nested.rename(root / "moved")
        nested.symlink_to(outside, target_is_directory=True)
        return original(candidate_root, locator)

    monkeypatch.setattr(confined_files, "_open_confined_descriptor", swapped)
    with pytest.raises(ConfinedFileUnavailable):
        read_confined_file(root, "nested/proof.txt", max_bytes=100, capture_bytes=True)


def test_confined_reader_refuses_rebound_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "proof.txt").write_bytes(b"outside secret")
    root = tmp_path / "root"
    root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ConfinedFileUnavailable):
        read_confined_file(root, "proof.txt", max_bytes=100, capture_bytes=True)


def test_confined_reader_rejects_root_ancestor_swap_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "parent"
    root = parent / "root"
    root.mkdir(parents=True)
    (root / "proof.txt").write_bytes(b"fictional proof")
    outside = tmp_path / "outside"
    (outside / "root").mkdir(parents=True)
    (outside / "root" / "proof.txt").write_bytes(b"outside secret")
    original = confined_files._open_confined_descriptor

    def swapped(candidate_root: Path, locator: str) -> int:
        parent.rename(tmp_path / "moved")
        parent.symlink_to(outside, target_is_directory=True)
        return original(candidate_root, locator)

    monkeypatch.setattr(confined_files, "_open_confined_descriptor", swapped)
    with pytest.raises(ConfinedFileUnavailable):
        read_confined_file(root, "proof.txt", max_bytes=100, capture_bytes=True)


def test_confined_reader_rejects_replacement_after_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    leaf = tmp_path / "proof.txt"
    leaf.write_bytes(b"fictional proof")
    original = confined_files._open_confined_descriptor
    calls = 0

    def replaced(candidate_root: Path, locator: str) -> int:
        nonlocal calls
        calls += 1
        if calls == 2:
            leaf.unlink()
            leaf.write_bytes(b"fabricated text")
        return original(candidate_root, locator)

    monkeypatch.setattr(confined_files, "_open_confined_descriptor", replaced)
    with pytest.raises(ConfinedFileChanged):
        read_confined_file(tmp_path, "proof.txt", max_bytes=100, capture_bytes=True)
    assert calls == 2


def test_confined_reader_rejects_mutation_during_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    leaf = tmp_path / "proof.txt"
    leaf.write_bytes(b"fictional proof")
    original = confined_files.os.read
    calls = 0

    def changed(descriptor: int, amount: int) -> bytes:
        nonlocal calls
        chunk = original(descriptor, amount)
        calls += 1
        if calls == 1:
            leaf.write_bytes(b"changed proof with more bytes")
        return chunk

    monkeypatch.setattr(confined_files.os, "read", changed)
    with pytest.raises(ConfinedFileChanged):
        read_confined_file(tmp_path, "proof.txt", max_bytes=100, capture_bytes=True)


@pytest.mark.parametrize("locator", ["proof.txt", "proof.pdf"])
def test_extractors_reject_leaf_swap_before_confined_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, locator: str
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    raw = b"synthetic source"
    leaf = root / locator
    leaf.write_bytes(raw)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside secret must not reach a parser")
    original = confined_files._open_confined_descriptor

    def swapped(candidate_root: Path, candidate_locator: str) -> int:
        leaf.unlink()
        leaf.symlink_to(outside)
        return original(candidate_root, candidate_locator)

    monkeypatch.setattr(confined_files, "_open_confined_descriptor", swapped)
    if locator.endswith(".pdf"):

        class ForbiddenProcessor:
            processor_version = "synthetic"

            def extract(self, *args: object, **kwargs: object) -> None:
                raise AssertionError("outside bytes reached document processor")

        result = extract_document_source_version(root, _item(locator, raw), ForbiddenProcessor())  # type: ignore[arg-type]
    else:
        result = extract_source_version(root, _item(locator, raw))
    assert (result.status, result.error_code) == (
        ExtractionStatus.FAILED,
        "source_unavailable",
    )


def test_snapshot_never_hashes_swapped_outside_leaf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    leaf = root / "proof.txt"
    leaf.write_bytes(b"fictional proof")
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside secret must not be hashed")
    original = confined_files._open_confined_descriptor

    def swapped(candidate_root: Path, locator: str) -> int:
        leaf.unlink()
        leaf.symlink_to(outside)
        return original(candidate_root, locator)

    monkeypatch.setattr(confined_files, "_open_confined_descriptor", swapped)
    manifest = snapshot_tree(
        root, source_id="files_safe", observed_at=datetime(2026, 9, 23, tzinfo=UTC)
    )
    assert manifest["items"] == []
    assert manifest["errors"] == [{"locator": "proof.txt", "code": "file_unreadable"}]
