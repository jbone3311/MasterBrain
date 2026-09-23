"""Explicit real two-image archive-document checks; not ordinary discovery."""

from __future__ import annotations

import hashlib
import io
import os
import zipfile
from pathlib import Path

import pytest

from email_brain.synthetic_formats import docx_bytes, pdf_bytes, xlsx_bytes
from masterbrain.datacore.archive_contract import CONTRACT as ARCHIVE_CONTRACT
from masterbrain.datacore.archive_contract import source_for
from masterbrain.datacore.archive_member_document import extract_archive_member_document
from masterbrain.datacore.archive_member_processor import DockerArchiveMemberProcessor
from masterbrain.datacore.archive_worker import inventory_archive
from masterbrain.datacore.document_contract import CONTRACT as DOCUMENT_CONTRACT
from masterbrain.datacore.document_processor import DockerDocumentProcessor
from masterbrain.datacore.extraction import ExtractionStatus
from masterbrain.datacore.persistence import ArchiveMemberTargetRecord


@pytest.fixture
def processors() -> tuple[DockerArchiveMemberProcessor, DockerDocumentProcessor, str, str]:
    archive_image = os.environ.get("MASTERBRAIN_ARCHIVE_IMAGE_ID")
    document_image = os.environ.get("MASTERBRAIN_DOCUMENT_IMAGE_ID")
    if not archive_image or not document_image:
        pytest.fail("explicit archive-document checks require both approved prebuilt images")
    return (
        DockerArchiveMemberProcessor(archive_image),
        DockerDocumentProcessor(document_image),
        archive_image,
        document_image,
    )


def fixture(
    root: Path, name: str, content: bytes, archive_image: str
) -> tuple[bytes, ArchiveMemberTargetRecord]:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, content)
        for index in range(64):
            archive.writestr(
                f"unrelated/sibling-{index:02d}.txt",
                f"sibling-secret-{index:02d}".encode(),
            )
    raw = output.getvalue()
    (root / "bundle.zip").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    source = source_for(
        raw,
        "version_" + digest[:32],
        "bundle.zip",
        digest,
        "application/zip",
    )
    member = next(item for item in inventory_archive(raw, source).members if item.locator == name)
    return raw, ArchiveMemberTargetRecord(
        "archive_inventory_" + digest[:32],
        ARCHIVE_CONTRACT + "-" + archive_image.removeprefix("sha256:"),
        "files_archive_document_container",
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


@pytest.mark.parametrize(
    "name,content,marker,expected_format",
    [
        (
            "nested/report.pdf",
            pdf_bytes(("two container pdf proof",)),
            "two container pdf proof",
            "pdf",
        ),
        (
            "nested/memo.docx",
            docx_bytes("two container word proof"),
            "two container word proof",
            "docx",
        ),
        (
            "nested/ledger.xlsx",
            xlsx_bytes("Two Container Atlas", 7300, 11, "twocontainersheetproof"),
            "twocontainersheetproof",
            "xlsx",
        ),
    ],
    ids=["pdf", "docx", "xlsx"],
)
def test_actual_archive_document_chain_is_exact_and_source_preserving(
    processors: tuple[DockerArchiveMemberProcessor, DockerDocumentProcessor, str, str],
    tmp_path: Path,
    name: str,
    content: bytes,
    marker: str,
    expected_format: str,
) -> None:
    archive_processor, document_processor, archive_image, document_image = processors
    raw, target = fixture(tmp_path, name, content, archive_image)
    source = tmp_path / "bundle.zip"
    before = source.stat()

    result = extract_archive_member_document(
        tmp_path, target, archive_processor, document_processor
    )

    assert result.status is ExtractionStatus.EXTRACTED
    assert result.error_code is None and result.metadata["format"] == expected_format
    assert marker in result.text and "sibling-secret" not in result.text
    assert result.metadata["extractor_version"] == (
        DOCUMENT_CONTRACT + "-" + document_image.removeprefix("sha256:")
    )
    assert source.read_bytes() == raw
    assert source.stat().st_mtime_ns == before.st_mtime_ns


def test_actual_chain_rejects_member_identity_substitution(
    processors: tuple[DockerArchiveMemberProcessor, DockerDocumentProcessor, str, str],
    tmp_path: Path,
) -> None:
    archive_processor, document_processor, archive_image, _ = processors
    raw, target = fixture(
        tmp_path, "nested/report.pdf", pdf_bytes(("identity bound proof",)), archive_image
    )
    substituted = ArchiveMemberTargetRecord(
        target.inventory_id,
        target.inventory_processor_version,
        target.source_id,
        target.item_id,
        target.source_version_id,
        target.source_locator,
        target.source_sha256,
        target.source_size_bytes,
        target.source_media_type,
        target.member_locator,
        "0" * 64,
        target.member_size_bytes,
        target.member_media_type,
        target.member_depth,
        target.member_parent_locator,
    )

    result = extract_archive_member_document(
        tmp_path, substituted, archive_processor, document_processor
    )

    assert result.status is ExtractionStatus.FAILED
    assert result.error_code == "member_unavailable" and not result.text
    assert (tmp_path / "bundle.zip").read_bytes() == raw
