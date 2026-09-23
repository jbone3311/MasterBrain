"""Two-boundary OCR for one hash-bound archive image member."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import UUID

from email_brain.domain.models import TenantContext
from masterbrain.datacore.archive_contract import ArchiveUnavailable
from masterbrain.datacore.archive_member import (
    ArchiveMemberProcessor,
    read_persisted_archive_member,
)
from masterbrain.datacore.archive_member_text import archive_member_version_id
from masterbrain.datacore.extraction import ExtractionResult, ExtractionStatus
from masterbrain.datacore.image_ocr_contract import (
    CONTRACT,
    MAX_IMAGE_BYTES,
    MAX_PIXELS,
    MAX_TEXT_BYTES,
    MAX_TEXT_CHARS,
    ImageOcrResult,
    ImageOcrUnavailable,
    decode_result,
    encode_result,
    source_for,
)
from masterbrain.datacore.persistence import (
    MAX_NORMALIZED_BYTES,
    ArchiveMemberTargetRecord,
    ArchiveMemberTextRecord,
    DataCoreStore,
)

IMAGE_SUFFIX_FORMAT = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".tif": "tiff",
    ".tiff": "tiff",
    ".bmp": "bmp",
    ".gif": "gif",
    ".webp": "webp",
}
_IMAGE_PROCESSOR_VERSION = re.compile(
    rf"{re.escape(CONTRACT)}-[a-f0-9]{{64}}\Z", re.ASCII
)


class ImageOcrProcessor(Protocol):
    @property
    def processor_version(self) -> str: ...

    def extract(
        self, raw: bytes, *, suffix: str, sha256: str, format: str
    ) -> ImageOcrResult: ...


def extract_archive_member_image_ocr(
    root: Path,
    target: ArchiveMemberTargetRecord,
    archive_processor: ArchiveMemberProcessor,
    image_processor: ImageOcrProcessor,
) -> ExtractionResult:
    """Read one exact member and OCR it in the separate image worker."""
    version_id = archive_member_version_id(target)
    suffix = PurePosixPath(target.member_locator).suffix.lower()
    image_format = IMAGE_SUFFIX_FORMAT.get(suffix)
    if image_format is None:
        return ExtractionResult(
            version_id,
            target.member_locator,
            ExtractionStatus.UNSUPPORTED,
            error_code="unsupported_image_type",
            metadata={"suffix": suffix or "none"},
        )
    if target.member_size_bytes > MAX_IMAGE_BYTES:
        return ExtractionResult(
            version_id,
            target.member_locator,
            ExtractionStatus.DEFERRED,
            error_code="image_byte_limit",
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
            suffix=suffix,
            sha256=target.member_sha256,
            format=image_format,
        )
        extracted = image_processor.extract(
            member.raw,
            suffix=suffix,
            sha256=target.member_sha256,
            format=image_format,
        )
        # Revalidate even an in-process test implementation as untrusted worker output.
        extracted = decode_result(encode_result(extracted), expected)
        processor_version = image_processor.processor_version
        if not processor_version or len(processor_version) > 200 or "\x00" in processor_version:
            raise ImageOcrUnavailable()
    except Exception:
        return ExtractionResult(
            version_id,
            target.member_locator,
            ExtractionStatus.FAILED,
            error_code="image_processor_unavailable",
        )

    if extracted.reason == "bounded_image_ocr_v1":
        status = ExtractionStatus.EXTRACTED
    elif extracted.reason == "empty_ocr":
        status = ExtractionStatus.EMPTY
    elif extracted.status == "deferred":
        status = ExtractionStatus.DEFERRED
    else:
        status = ExtractionStatus.FAILED
    metadata: dict[str, str | int | bool] = {
        "extractor_version": processor_version,
        "format": image_format,
        "image_reason": extracted.reason,
        "truncated": extracted.truncated,
    }
    for key, value in (
        ("detected_format", extracted.detected_format),
        ("width", extracted.width),
        ("height", extracted.height),
        ("mode", extracted.mode),
        ("frame_count", extracted.frame_count),
    ):
        if value is not None:
            metadata[key] = value
    return ExtractionResult(
        version_id,
        target.member_locator,
        status,
        extracted.text,
        (
            None
            if status in {ExtractionStatus.EXTRACTED, ExtractionStatus.EMPTY}
            else extracted.reason
        ),
        metadata,
    )


def publish_extracted_archive_member_image_ocr(
    core: DataCoreStore,
    ctx: TenantContext,
    target: ArchiveMemberTargetRecord,
    extraction: ExtractionResult,
    *,
    code_revision: str,
    idempotency_key: UUID,
) -> ArchiveMemberTextRecord:
    """Publish only a complete, nonempty result from the isolated image contract."""
    suffix = (
        PurePosixPath(target.member_locator).suffix.lower()
        if isinstance(target, ArchiveMemberTargetRecord)
        else ""
    )
    expected_format = IMAGE_SUFFIX_FORMAT.get(suffix)
    metadata = extraction.metadata
    required_metadata = {
        "extractor_version",
        "format",
        "image_reason",
        "truncated",
        "detected_format",
        "width",
        "height",
        "mode",
        "frame_count",
    }
    processor = metadata.get("extractor_version")
    image_format = metadata.get("format")
    detected_format = metadata.get("detected_format")
    width = metadata.get("width")
    height = metadata.get("height")
    mode = metadata.get("mode")
    frame_count = metadata.get("frame_count")
    truncated = metadata.get("truncated")
    if (
        not isinstance(target, ArchiveMemberTargetRecord)
        or extraction.version_id != archive_member_version_id(target)
        or extraction.locator != target.member_locator
        or extraction.status is not ExtractionStatus.EXTRACTED
        or type(extraction.text) is not str
        or not extraction.text
        or "\x00" in extraction.text
        or extraction.text != extraction.text.strip()
        or len(extraction.text) > MAX_TEXT_CHARS
        or len(extraction.text.encode()) > min(MAX_TEXT_BYTES, MAX_NORMALIZED_BYTES)
        or extraction.error_code is not None
        or type(target.member_size_bytes) is not int
        or not 0 < target.member_size_bytes <= MAX_IMAGE_BYTES
        or set(metadata) != required_metadata
        or type(processor) is not str
        or not _IMAGE_PROCESSOR_VERSION.fullmatch(processor)
        or type(image_format) is not str
        or type(detected_format) is not str
        or image_format != expected_format
        or detected_format != expected_format
        or metadata.get("image_reason") != "bounded_image_ocr_v1"
        or type(width) is not int
        or type(height) is not int
        or not 1 <= width <= MAX_PIXELS
        or not 1 <= height <= MAX_PIXELS
        or width * height > MAX_PIXELS
        or type(mode) is not str
        or not 1 <= len(mode) <= 16
        or "\x00" in mode
        or type(frame_count) is not int
        or frame_count != 1
        or type(truncated) is not bool
    ):
        raise ValueError("archive member image OCR is not an accepted extraction")
    return core.publish_archive_member_image_ocr(
        ctx,
        target,
        extraction.text,
        processor,
        image_format,
        detected_format,
        width,
        height,
        mode,
        frame_count,
        truncated,
        code_revision,
        idempotency_key,
    )
