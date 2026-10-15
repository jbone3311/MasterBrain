"""Point-in-time confined FileOS PDF byte-to-text replay without publication."""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from masterbrain.datacore.confined_files import (
    ConfinedFileChanged,
    ConfinedFileTooLarge,
    ConfinedFileUnavailable,
    read_confined_file,
)
from masterbrain.datacore.document_contract import (
    MAX_DOCUMENT_BYTES,
    PDF_TYPE,
    DocumentUnavailable,
    source_for,
)
from masterbrain.datacore.document_processor import DockerDocumentProcessor
from masterbrain.datacore.fileos import fileos_root_binding_sha256

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_PROCESSOR = re.compile(r"^sandbox-fileos-document-v1-[a-f0-9]{64}$")


class CurrentFileOSPdfUnavailable(ValueError):
    """A pinned PDF cannot be replayed exactly within the private boundary."""


@dataclass(frozen=True, slots=True)
class PdfDerivationProof:
    source_sha256: str
    source_size_bytes: int
    text_sha256: str
    normalizer: str
    page_count: int


def replay_current_fileos_pdf(
    root: Path, *, locator: str, version_id: str, root_binding_sha256: str,
    source_sha256: str, source_size_bytes: int, text: str, text_sha256: str,
    normalizer: str, processor: DockerDocumentProcessor,
) -> PdfDerivationProof:
    """Prove one current text-layer PDF projection, never OCR or issuer truth."""
    if (
        not isinstance(root, Path)
        or type(locator) is not str
        or PurePosixPath(locator).suffix.lower() != ".pdf"
        or type(source_size_bytes) is not int
        or not 0 < source_size_bytes <= MAX_DOCUMENT_BYTES
        or type(source_sha256) is not str
        or _SHA256.fullmatch(source_sha256) is None
        or type(text_sha256) is not str
        or _SHA256.fullmatch(text_sha256) is None
        or type(root_binding_sha256) is not str
        or _SHA256.fullmatch(root_binding_sha256) is None
        or type(text) is not str
        or not text
        or type(normalizer) is not str
        or _PROCESSOR.fullmatch(normalizer) is None
        or type(processor) is not DockerDocumentProcessor
        or processor.processor_version != normalizer
    ):
        raise CurrentFileOSPdfUnavailable("invalid_pdf_replay_basis")
    try:
        encoded = text.encode("utf-8", errors="strict")
        if not hmac.compare_digest(hashlib.sha256(encoded).hexdigest(), text_sha256):
            raise CurrentFileOSPdfUnavailable("text_digest_mismatch")
        if fileos_root_binding_sha256(root) != root_binding_sha256:
            raise CurrentFileOSPdfUnavailable("root_changed")
        opened = read_confined_file(
            root, locator, max_bytes=MAX_DOCUMENT_BYTES, capture_bytes=True,
        )
        if (
            opened.raw is None
            or opened.size_bytes != source_size_bytes
            or not hmac.compare_digest(opened.sha256, source_sha256)
        ):
            raise CurrentFileOSPdfUnavailable("source_changed")
        expected = source_for(
            opened.raw, version_id, locator, source_sha256, PDF_TYPE,
        )
        result = processor.extract(
            opened.raw, version_id=version_id, locator=locator,
            sha256=source_sha256, media_type=PDF_TYPE,
        )
        if (
            result.source != expected
            or result.status != "extracted"
            or result.reason != "bounded_pdf_v1"
            or result.scanner_status != "unscanned"
            or result.text != text
            or type(result.metadata.page_count) is not int
            or not 0 < result.metadata.page_count <= 40
        ):
            raise CurrentFileOSPdfUnavailable("pdf_derivation_mismatch")
        if fileos_root_binding_sha256(root) != root_binding_sha256:
            raise CurrentFileOSPdfUnavailable("root_changed")
        return PdfDerivationProof(
            source_sha256, source_size_bytes, text_sha256, normalizer,
            result.metadata.page_count,
        )
    except (
        ConfinedFileUnavailable, ConfinedFileChanged, ConfinedFileTooLarge,
        DocumentUnavailable, OSError, RuntimeError, UnicodeError, ValueError,
    ):
        raise CurrentFileOSPdfUnavailable("pdf_replay_unavailable") from None
