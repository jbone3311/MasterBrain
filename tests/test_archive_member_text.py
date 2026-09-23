from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import replace
from pathlib import Path

from masterbrain.datacore.archive_contract import source_for
from masterbrain.datacore.archive_member_contract import decode_result, encode_request
from masterbrain.datacore.archive_member_text import extract_archive_member_text
from masterbrain.datacore.archive_member_worker import process_request
from masterbrain.datacore.archive_worker import inventory_archive
from masterbrain.datacore.extraction import ExtractionStatus
from masterbrain.datacore.persistence import ArchiveMemberTargetRecord


class LocalProcessor:
    def read(self, raw, *, source, target):
        return decode_result(process_request(encode_request(raw, source, target)), source, target)


class MustNotRead:
    def read(self, raw, *, source, target):
        raise AssertionError("ineligible member must not enter the isolated reader")


def fixture(name: str, content: bytes) -> tuple[bytes, ArchiveMemberTargetRecord]:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(name, content)
        archive.writestr("sibling.txt", b"must not be normalized")
    raw = output.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    source = source_for(raw, "version_" + digest[:32], "bundle.zip", digest, "application/zip")
    member = next(item for item in inventory_archive(raw, source).members if item.locator == name)
    return raw, ArchiveMemberTargetRecord(
        "archive_inventory_" + "b" * 32,
        "sandbox-fileos-archive-v1-" + "a" * 64,
        "files_archive_text",
        "item_parent",
        source.version_id,
        source.locator,
        source.sha256,
        source.size_bytes,
        source.media_type,
        member.locator,
        member.sha256,
        member.observed_size,
        member.media_hint,
        member.depth,
        member.parent_locator,
    )


def test_exact_member_text_is_normalized_without_sibling_bytes(tmp_path: Path) -> None:
    raw, target = fixture("notes/proof.md", b"  one archive member proof  ")
    (tmp_path / "bundle.zip").write_bytes(raw)
    result = extract_archive_member_text(tmp_path, target, LocalProcessor())
    assert result.status is ExtractionStatus.EXTRACTED
    assert result.text == "one archive member proof"
    assert "sibling" not in result.text
    assert result.metadata["extractor_version"] == "fileos-text-v1"


def test_html_member_uses_existing_deterministic_normalizer(tmp_path: Path) -> None:
    raw, target = fixture("page.html", b"<h1>Proof</h1><script>secret</script><p>Body</p>")
    (tmp_path / "bundle.zip").write_bytes(raw)
    result = extract_archive_member_text(tmp_path, target, LocalProcessor())
    assert result.status is ExtractionStatus.EXTRACTED
    assert result.text == "Proof\nBody" and "secret" not in result.text


def test_unsupported_and_over_text_limit_defer_before_member_read(tmp_path: Path) -> None:
    _, binary = fixture("image.bin", b"binary")
    unsupported = extract_archive_member_text(tmp_path, binary, MustNotRead())
    assert unsupported.status is ExtractionStatus.UNSUPPORTED

    _, text = fixture("large.txt", b"small fixture")
    deferred = extract_archive_member_text(
        tmp_path, replace(text, member_size_bytes=1_048_577), MustNotRead()
    )
    assert deferred.status is ExtractionStatus.DEFERRED
    assert deferred.error_code == "member_text_byte_limit"
