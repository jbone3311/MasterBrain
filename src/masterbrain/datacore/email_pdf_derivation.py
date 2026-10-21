"""Nonpublishing proof of one retained Email attachment PDF text layer."""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass

from email_brain.document_jobs import POLICY
from email_brain.pdf_contract import MAX_MIME_BYTES, MAX_PAGES, MAX_TOTAL_CHARS, PdfUnavailable
from email_brain.pdf_contract import source_for as pdf_source_for
from email_brain.pdf_processor import DockerPdfProcessor
from masterbrain.datacore.persistence import EMAIL_DOCUMENT_NORMALIZER_PREFIX

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_PROCESSOR = re.compile(r"^sandbox-pdf-v1-[a-f0-9]{64}$")


class EmailAttachmentPdfUnavailable(ValueError):
    def __init__(self) -> None:
        super().__init__("email_attachment_pdf_derivation_unavailable")


@dataclass(frozen=True, slots=True)
class EmailAttachmentPdfProof:
    raw_sha256: str
    raw_size_bytes: int
    part_path: str
    part_sha256: str
    text_sha256: str
    normalizer: str
    page_count: int


def prove_email_attachment_pdf_derivation(
    raw_mime: bytes, *, raw_sha256: str, raw_size_bytes: int,
    part_path: str, part_sha256: str, text: str, text_sha256: str,
    normalizer: str, processor: DockerPdfProcessor,
) -> EmailAttachmentPdfProof:
    """Re-extract one exact part; never publish or claim visual completeness."""
    try:
        if (
            type(raw_mime) is not bytes
            or type(raw_size_bytes) is not int
            or not 0 < raw_size_bytes <= MAX_MIME_BYTES
            or len(raw_mime) != raw_size_bytes
            or type(raw_sha256) is not str
            or _SHA256.fullmatch(raw_sha256) is None
            or not hmac.compare_digest(hashlib.sha256(raw_mime).hexdigest(), raw_sha256)
            or type(text) is not str
            or not text
            or "\x00" in text
            or len(text) > MAX_TOTAL_CHARS + MAX_PAGES - 1
            or type(text_sha256) is not str
            or _SHA256.fullmatch(text_sha256) is None
            or not hmac.compare_digest(
                hashlib.sha256(text.encode("utf-8", errors="strict")).hexdigest(),
                text_sha256,
            )
            or type(processor) is not DockerPdfProcessor
            or _PROCESSOR.fullmatch(processor.processor_version) is None
            or type(normalizer) is not str
            or normalizer != (
                f"{EMAIL_DOCUMENT_NORMALIZER_PREFIX}:"
                f"{processor.processor_version}:{POLICY}"
            )
        ):
            raise EmailAttachmentPdfUnavailable()
        expected = pdf_source_for(raw_mime, part_path, part_sha256)
        if expected.raw_sha256 != raw_sha256:
            raise EmailAttachmentPdfUnavailable()
        result = processor.extract(
            raw_mime, part_path=part_path, part_sha256=part_sha256,
        )
        if (
            result.source != expected
            or result.status != "extracted"
            or result.reason != "bounded_pdf_v1"
            or result.scanner_status != "unscanned"
            or type(result.page_count) is not int
            or not 0 < result.page_count <= MAX_PAGES
            or len(result.pages) != result.page_count
            or any(not page.text for page in result.pages)
            or "\n".join(page.text for page in result.pages) != text
        ):
            raise EmailAttachmentPdfUnavailable()
        return EmailAttachmentPdfProof(
            raw_sha256, raw_size_bytes, part_path, part_sha256,
            text_sha256, normalizer, result.page_count,
        )
    except (PdfUnavailable, UnicodeError, ValueError, TypeError, RuntimeError):
        raise EmailAttachmentPdfUnavailable() from None
