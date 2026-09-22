from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from masterbrain.datacore.fileos import snapshot_tree
from masterbrain.datacore.persistence import MAX_MANIFEST_ITEMS, deterministic_chunks


def test_deterministic_chunks_are_exact_and_reassemble() -> None:
    text = ("alpha beta gamma " * 180) + "end"
    first = list(deterministic_chunks(text, 80))
    assert first == list(deterministic_chunks(text, 80))
    assert "".join(chunk for _, _, chunk in first) == text
    assert all(text[start:end] == chunk and 0 < len(chunk) <= 80 for start, end, chunk in first)


@pytest.mark.parametrize("limit", [0, 31, 2001])
def test_chunk_bounds_fail_closed(limit: int) -> None:
    with pytest.raises(ValueError):
        list(deterministic_chunks("text", limit))


def test_snapshot_bound_is_documented_and_finite(tmp_path: Path) -> None:
    (tmp_path / "one.txt").write_text("one", encoding="utf-8")
    manifest = snapshot_tree(
        tmp_path, source_id="files_test", observed_at=datetime(2026, 9, 22, tzinfo=UTC)
    )
    assert manifest["counts"]["items"] < MAX_MANIFEST_ITEMS
