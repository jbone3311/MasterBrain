"""Two-boundary extraction for one hash-bound archive PDF or Office member."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path, PurePosixPath

from masterbrain.datacore.archive_contract import ArchiveUnavailable
from masterbrain.datacore.archive_member import (
    ArchiveMemberProcessor,
    read_persisted_archive_member,
)
from masterbrain.datacore.archive_member_text import archive_member_version_id
from masterbrain.datacore.document_contract import (
    MAX_DOCUMENT_BYTES,
    DocumentUnavailable,
    decode_result,
    encode_result,
    source_for,
)
from masterbrain.datacore.extraction import (
    DOCUMENT_SUFFIXES,
    DocumentProcessor,
    ExtractionResult,
    ExtractionStatus,
)
from masterbrain.datacore.persistence import ArchiveMemberTargetRecord


def extract_archive_member_document(
    root: Path,
    target: ArchiveMemberTargetRecord,
    archive_processor: ArchiveMemberProcessor,
    document_processor: DocumentProcessor,
) -> ExtractionResult:
    """Read one exact member and normalize it in the separate document worker."""
    version_id = archive_member_version_id(target)
    suffix = PurePosixPath(target.member_locator).suffix.lower()
    if suffix not in DOCUMENT_SUFFIXES:
        return ExtractionResult(
            version_id,
            target.member_locator,
            ExtractionStatus.UNSUPPORTED,
            error_code="unsupported_document_type",
            metadata={"suffix": suffix or "none"},
        )
    if target.member_size_bytes > MAX_DOCUMENT_BYTES:
        return ExtractionResult(
            version_id,
            target.member_locator,
            ExtractionStatus.DEFERRED,
            error_code="document_byte_limit",
            metadata={"size_bytes": target.member_size_bytes},
        )
    try:
        member = read_persisted_archive_member(root, target, archive_processor)
    except ArchiveUnavailable:
        return ExtractionResult(
            version_id,
            target.member_locator,
            ExtractionStatus.FAILED,
            error_code="member_unavailable",
        )
    if member.status != "read" or member.scanner_status != "unscanned":
        return ExtractionResult(
            version_id,
            target.member_locator,
            ExtractionStatus.DEFERRED,
            error_code="member_not_read",
        )
    try:
        expected = source_for(
            member.raw,
            version_id,
            target.member_locator,
            target.member_sha256,
            target.member_media_type,
        )
        extracted = document_processor.extract(
            member.raw,
            version_id=version_id,
            locator=target.member_locator,
            sha256=target.member_sha256,
            media_type=target.member_media_type,
        )
        # Revalidate even an in-process test implementation as untrusted worker output.
        extracted = decode_result(encode_result(extracted), expected)
        processor_version = document_processor.processor_version
        if not processor_version or len(processor_version) > 200 or "\x00" in processor_version:
            raise DocumentUnavailable()
    except (DocumentUnavailable, KeyError, TypeError, ValueError):
        return ExtractionResult(
            version_id,
            target.member_locator,
            ExtractionStatus.FAILED,
            error_code="document_processor_unavailable",
        )
    status = {
        "extracted": ExtractionStatus.EXTRACTED,
        "deferred": ExtractionStatus.DEFERRED,
        "failed": ExtractionStatus.FAILED,
    }[extracted.status]
    metadata = {
        key: value for key, value in asdict(extracted.metadata).items() if value is not None
    }
    metadata.update(
        {
            "extractor_version": processor_version,
            "format": extracted.source.format,
            "document_reason": extracted.reason,
        }
    )
    return ExtractionResult(
        version_id,
        target.member_locator,
        status,
        extracted.text,
        None if status is ExtractionStatus.EXTRACTED else extracted.reason,
        metadata,
    )
