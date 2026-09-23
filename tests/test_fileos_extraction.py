from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.extraction import ExtractionStatus, extract_source_version


def item(locator: str, raw: bytes, *, size: int | None = None) -> dict[str, object]:
    digest = hashlib.sha256(raw).hexdigest()
    item_id = stable_id("item", "files_test", locator)
    return {
        "item_id": item_id,
        "version_id": stable_id("version", item_id, digest, str(len(raw))),
        "locator": locator,
        "observed_at": datetime(2026, 9, 22, tzinfo=UTC).isoformat(),
        "digest": {"algorithm": "sha256", "value": digest},
        "size_bytes": len(raw) if size is None else size,
        "media_type": "text/plain",
        "metadata": {},
    }


@pytest.mark.parametrize(
    ("encoding", "prefix"),
    [("utf-8-sig", "café"), ("utf-16", "café"), ("utf-32", "café")],
)
def test_unicode_boms_and_newlines_are_deterministic(
    tmp_path: Path, encoding: str, prefix: str
) -> None:
    raw = f"{prefix}\r\nsecond".encode(encoding)
    (tmp_path / "note.txt").write_bytes(raw)
    result = extract_source_version(tmp_path, item("note.txt", raw))
    assert result.status is ExtractionStatus.EXTRACTED
    assert result.text == "café\nsecond"
    assert result.metadata.get("encoding_uncertain") is not True


def test_latin1_is_recovered_but_labeled_uncertain(tmp_path: Path) -> None:
    raw = "café résumé".encode("latin-1")
    (tmp_path / "note.md").write_bytes(raw)
    result = extract_source_version(tmp_path, item("note.md", raw))
    assert result.text == "café résumé"
    assert result.metadata["encoding_uncertain"] is True


def test_html_drops_active_content_and_separates_table_cells(tmp_path: Path) -> None:
    raw = (
        b"<html><head><title>secret</title></head><body><script>alert(1)</script>"
        b"<style>bad{}</style><h1>Heading</h1><table><tr><th>Date</th><th>Amount</th>"
        b"</tr><tr><td>2026-01-01</td><td>100.00</td></tr></table></body></html>"
    )
    (tmp_path / "page.html").write_bytes(raw)
    result = extract_source_version(tmp_path, item("page.html", raw))
    assert result.status is ExtractionStatus.EXTRACTED
    assert "secret" not in result.text and "alert" not in result.text and "bad" not in result.text
    assert "Date Amount" in result.text
    assert "2026-01-01 100.00" in result.text


def test_csv_preserves_embedded_newline_and_counts_shape(tmp_path: Path) -> None:
    raw = b'name,note\r\nAlice,"Line1\r\nLine2"\r\nBob,ok\r\n'
    (tmp_path / "data.csv").write_bytes(raw)
    result = extract_source_version(tmp_path, item("data.csv", raw))
    assert result.status is ExtractionStatus.EXTRACTED
    assert 'Alice,"Line1\nLine2"' in result.text
    assert result.metadata["row_count"] == 2
    assert result.metadata["column_count"] == 2


@pytest.mark.parametrize(
    ("name", "raw", "status", "code"),
    [
        ("empty.txt", b"", ExtractionStatus.EMPTY, None),
        ("binary.txt", b"a\x00b", ExtractionStatus.FAILED, "nul_text"),
        ("image.png", b"png", ExtractionStatus.UNSUPPORTED, "unsupported_type"),
    ],
)
def test_every_input_gets_an_explicit_outcome(
    tmp_path: Path,
    name: str,
    raw: bytes,
    status: ExtractionStatus,
    code: str | None,
) -> None:
    (tmp_path / name).write_bytes(raw)
    result = extract_source_version(tmp_path, item(name, raw))
    assert (result.status, result.error_code) == (status, code)


def test_hash_size_oversize_traversal_and_symlink_fail_closed(tmp_path: Path) -> None:
    raw = b"original"
    path = tmp_path / "note.txt"
    path.write_bytes(raw)
    changed = item("note.txt", raw)
    path.write_bytes(b"modified")
    assert extract_source_version(tmp_path, changed).status is ExtractionStatus.CHANGED

    path.write_bytes(raw)
    wrong_size = item("note.txt", raw, size=len(raw) + 1)
    assert extract_source_version(tmp_path, wrong_size).status is ExtractionStatus.CHANGED
    assert extract_source_version(tmp_path, item("note.txt", raw), max_bytes=2).status is (
        ExtractionStatus.DEFERRED
    )
    with pytest.raises(ValueError, match="unsafe"):
        extract_source_version(tmp_path, item("../escape.txt", raw))

    target = tmp_path / "target.txt"
    target.write_bytes(raw)
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    symlinked = extract_source_version(tmp_path, item("link.txt", raw))
    assert (symlinked.status, symlinked.error_code) == (
        ExtractionStatus.FAILED,
        "symlink_refused",
    )
