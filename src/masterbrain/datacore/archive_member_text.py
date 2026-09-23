"""Explicit bounded text normalization for one hash-bound archive member."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from uuid import UUID

from email_brain.domain.models import TenantContext
from masterbrain.datacore.archive_contract import ArchiveUnavailable
from masterbrain.datacore.archive_member import (
    ArchiveMemberProcessor,
    read_persisted_archive_member,
)
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.extraction import (
    EXTRACTOR_VERSION,
    MAX_SOURCE_BYTES,
    SUPPORTED_SUFFIXES,
    ExtractionResult,
    ExtractionStatus,
    _extract_bytes,
)
from masterbrain.datacore.persistence import (
    ArchiveMemberTargetRecord,
    ArchiveMemberTextRecord,
    DataCoreStore,
)


def archive_member_version_id(target: ArchiveMemberTargetRecord) -> str:
    return stable_id(
        "archiveversion",
        target.inventory_id,
        target.inventory_processor_version,
        target.member_locator,
        target.member_sha256,
        str(target.member_size_bytes),
    )


def extract_archive_member_text(
    root: Path,
    target: ArchiveMemberTargetRecord,
    processor: ArchiveMemberProcessor,
) -> ExtractionResult:
    """Read and normalize one eligible member; never retain or publish its raw bytes."""
    version_id = archive_member_version_id(target)
    suffix = PurePosixPath(target.member_locator).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        return ExtractionResult(
            version_id,
            target.member_locator,
            ExtractionStatus.UNSUPPORTED,
            error_code="unsupported_type",
            metadata={"suffix": suffix or "none"},
        )
    if target.member_size_bytes > MAX_SOURCE_BYTES:
        return ExtractionResult(
            version_id,
            target.member_locator,
            ExtractionStatus.DEFERRED,
            error_code="member_text_byte_limit",
            metadata={"size_bytes": target.member_size_bytes},
        )
    try:
        result = read_persisted_archive_member(root, target, processor)
    except ArchiveUnavailable:
        return ExtractionResult(
            version_id,
            target.member_locator,
            ExtractionStatus.FAILED,
            error_code="member_unavailable",
        )
    if result.status != "read" or result.scanner_status != "unscanned":
        return ExtractionResult(
            version_id,
            target.member_locator,
            ExtractionStatus.DEFERRED,
            error_code="member_not_read",
        )
    status, text, error, metadata = _extract_bytes(target.member_locator, version_id, result.raw)
    if metadata.get("extractor_version") not in {None, EXTRACTOR_VERSION}:
        return ExtractionResult(
            version_id,
            target.member_locator,
            ExtractionStatus.FAILED,
            error_code="normalizer_identity_mismatch",
        )
    return ExtractionResult(version_id, target.member_locator, status, text, error, metadata)


def publish_extracted_archive_member_text(
    core: DataCoreStore,
    ctx: TenantContext,
    target: ArchiveMemberTargetRecord,
    extraction: ExtractionResult,
    *,
    code_revision: str,
    idempotency_key: UUID,
) -> ArchiveMemberTextRecord:
    """Publish only the exact successful output of this bounded normalizer contract."""
    if (
        extraction.version_id != archive_member_version_id(target)
        or extraction.locator != target.member_locator
        or extraction.status is not ExtractionStatus.EXTRACTED
        or not extraction.text
        or extraction.error_code is not None
        or extraction.metadata.get("extractor_version") != EXTRACTOR_VERSION
    ):
        raise ValueError("archive member text is not an accepted extraction")
    return core.publish_archive_member_text(
        ctx,
        target,
        extraction.text,
        EXTRACTOR_VERSION,
        code_revision,
        idempotency_key,
    )
