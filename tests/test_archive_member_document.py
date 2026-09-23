from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import ANY, Mock
from uuid import uuid4

import pytest

from email_brain.synthetic_formats import WORD_TYPE, docx_bytes, pdf_bytes, xlsx_bytes
from masterbrain.datacore.archive_contract import source_for as archive_source_for
from masterbrain.datacore.archive_member_contract import decode_result, encode_request
from masterbrain.datacore.archive_member_document import (
    extract_archive_member_document,
    publish_extracted_archive_member_document,
)
from masterbrain.datacore.archive_member_worker import process_request
from masterbrain.datacore.archive_worker import inventory_archive
from masterbrain.datacore.document_contract import CONTRACT, PDF_TYPE, DocumentUnavailable
from masterbrain.datacore.document_contract import source_for as document_source_for
from masterbrain.datacore.document_worker import extract_document
from masterbrain.datacore.extraction import ExtractionStatus
from masterbrain.datacore.persistence import ArchiveMemberTargetRecord


class LocalArchiveProcessor:
    def read(self, raw, *, source, target):
        return decode_result(process_request(encode_request(raw, source, target)), source, target)


class DirectDocumentProcessor:
    processor_version = CONTRACT + "-synthetic-unit"

    def extract(self, raw, *, version_id, locator, sha256, media_type):
        return extract_document(
            raw, document_source_for(raw, version_id, locator, sha256, media_type)
        )


class MustNotRun:
    processor_version = "must-not-run"

    def read(self, raw, *, source, target):
        raise AssertionError("ineligible member reached archive worker")

    def extract(self, raw, *, version_id, locator, sha256, media_type):
        raise AssertionError("ineligible member reached document worker")


def fixture(name: str, content: bytes) -> tuple[bytes, ArchiveMemberTargetRecord]:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(name, content)
        archive.writestr("sibling.txt", b"sibling content must remain unread")
    raw = output.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    source = archive_source_for(
        raw, "version_" + digest[:32], "bundle.zip", digest, "application/zip"
    )
    member = next(item for item in inventory_archive(raw, source).members if item.locator == name)
    return raw, ArchiveMemberTargetRecord(
        "archive_inventory_" + "b" * 32,
        "sandbox-fileos-archive-v1-" + "a" * 64,
        "files_archive_documents",
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
    "name,raw,marker,expected_format",
    [
        ("nested/report.pdf", pdf_bytes(("archive pdf proof",)), "archive pdf proof", "pdf"),
        ("memo.docx", docx_bytes("archive word proof"), "archive word proof", "docx"),
        (
            "tables/rent.xlsx",
            xlsx_bytes("Archive Atlas", 2450, 3, "archivedsheetproof"),
            "archivedsheetproof",
            "xlsx",
        ),
    ],
)
def test_exact_document_member_crosses_both_workers_without_sibling(
    tmp_path: Path, name: str, raw: bytes, marker: str, expected_format: str
) -> None:
    archive, target = fixture(name, raw)
    (tmp_path / "bundle.zip").write_bytes(archive)
    result = extract_archive_member_document(
        tmp_path, target, LocalArchiveProcessor(), DirectDocumentProcessor()
    )
    assert result.status is ExtractionStatus.EXTRACTED
    assert marker in result.text and "sibling content" not in result.text
    assert result.metadata["format"] == expected_format
    assert result.metadata["extractor_version"] == CONTRACT + "-synthetic-unit"


def test_unsupported_and_over_limit_refuse_before_either_worker(tmp_path: Path) -> None:
    _, unsupported = fixture("image.png", b"not an accepted document")
    result = extract_archive_member_document(tmp_path, unsupported, MustNotRun(), MustNotRun())
    assert result.status is ExtractionStatus.UNSUPPORTED

    _, document = fixture("report.pdf", pdf_bytes(("small",)))
    result = extract_archive_member_document(
        tmp_path,
        replace(document, member_size_bytes=8 * 1024 * 1024 + 1),
        MustNotRun(),
        MustNotRun(),
    )
    assert result.status is ExtractionStatus.DEFERRED
    assert result.error_code == "document_byte_limit"


def test_archive_and_document_worker_faults_fail_closed(tmp_path: Path) -> None:
    archive, target = fixture("memo.docx", docx_bytes("fault proof"))
    (tmp_path / "bundle.zip").write_bytes(archive)
    missing = extract_archive_member_document(
        tmp_path / "missing", target, LocalArchiveProcessor(), DirectDocumentProcessor()
    )
    assert missing.status is ExtractionStatus.FAILED
    assert missing.error_code == "member_unavailable"

    class FailedDocumentProcessor(DirectDocumentProcessor):
        def extract(self, raw, *, version_id, locator, sha256, media_type):
            raise DocumentUnavailable()

    failed = extract_archive_member_document(
        tmp_path, target, LocalArchiveProcessor(), FailedDocumentProcessor()
    )
    assert failed.status is ExtractionStatus.FAILED
    assert failed.error_code == "document_processor_unavailable"


def test_media_identity_mismatch_cannot_cross_document_boundary(tmp_path: Path) -> None:
    archive, target = fixture("memo.docx", docx_bytes("identity proof"))
    (tmp_path / "bundle.zip").write_bytes(archive)
    result = extract_archive_member_document(
        tmp_path,
        replace(target, member_media_type=PDF_TYPE),
        LocalArchiveProcessor(),
        DirectDocumentProcessor(),
    )
    assert result.status is ExtractionStatus.FAILED
    assert result.error_code == "document_processor_unavailable"
    assert target.member_media_type == WORD_TYPE


def test_publication_wrapper_accepts_only_complete_bound_document_result(tmp_path: Path) -> None:
    archive, target = fixture("memo.docx", docx_bytes("publication proof"))
    (tmp_path / "bundle.zip").write_bytes(archive)
    extraction = extract_archive_member_document(
        tmp_path, target, LocalArchiveProcessor(), DirectDocumentProcessor()
    )
    core = Mock()
    key = uuid4()
    published = object()
    core.publish_archive_member_document.return_value = published
    assert (
        publish_extracted_archive_member_document(
            core,
            object(),
            target,
            extraction,
            code_revision="unit-v1",
            idempotency_key=key,
        )
        is published
    )
    core.publish_archive_member_document.assert_called_once_with(
        ANY,
        target,
        extraction.text,
        CONTRACT + "-synthetic-unit",
        "docx",
        "unit-v1",
        key,
    )
    with pytest.raises(ValueError):
        publish_extracted_archive_member_document(
            core,
            object(),
            target,
            replace(extraction, metadata={**extraction.metadata, "format": "pdf"}),
            code_revision="unit-v1",
            idempotency_key=key,
        )
