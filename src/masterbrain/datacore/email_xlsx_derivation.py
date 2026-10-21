"""Nonpublishing proof that one retained Email XLSX uses shared DataCore extraction.

This private operator primitive accepts only exact parent MIME and attachment
identities. It does not grant an Email document bridge or publish search text.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from email import policy
from email.message import Message
from email.parser import BytesParser
from pathlib import PurePosixPath

from email_brain.attachments import receive_attachments
from email_brain.pdf_contract import MAX_MIME_BYTES
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.document_contract import (
    MAX_CELLS,
    MAX_DOCUMENT_BYTES,
    MAX_SHEETS,
    MAX_TEXT_CHARS,
    SHEET_TYPE,
    source_for,
)
from masterbrain.datacore.document_processor import DockerDocumentProcessor

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_PART_PATH = re.compile(r"^1(?:\.[1-9][0-9]{0,3}){0,20}$")
_PROCESSOR = re.compile(r"^sandbox-fileos-document-v1-[a-f0-9]{64}$")


class EmailAttachmentXlsxUnavailable(ValueError):
    def __init__(self) -> None:
        super().__init__("email_attachment_xlsx_derivation_unavailable")


@dataclass(frozen=True, slots=True)
class EmailAttachmentXlsxProof:
    raw_sha256: str
    raw_size_bytes: int
    part_path: str
    part_sha256: str
    text_sha256: str
    processor_version: str
    sheet_count: int
    cell_count: int


def _selected_xlsx(raw_mime: bytes, part_path: str, part_sha256: str) -> bytes:
    receipts = receive_attachments(raw_mime, max_raw_bytes=MAX_MIME_BYTES)
    receipt = next((item for item in receipts if item.part_id == part_path), None)
    if (
        receipt is None
        or receipt.sha256 != part_sha256
        or receipt.media_type != SHEET_TYPE
        or PurePosixPath(receipt.safe_filename).suffix.lower() != ".xlsx"
        or receipt.status != "deferred"
        or receipt.reason not in {"isolated_extractor_required", "extraction_byte_limit"}
    ):
        raise EmailAttachmentXlsxUnavailable()
    part: Message = BytesParser(policy=policy.default).parsebytes(raw_mime)
    for component in part_path.split(".")[1:]:
        children = part.get_payload()
        index = int(component) - 1
        if not isinstance(children, list) or index >= len(children):
            raise EmailAttachmentXlsxUnavailable()
        child = children[index]
        if not isinstance(child, Message):
            raise EmailAttachmentXlsxUnavailable()
        part = child
    data = part.get_payload(decode=True)
    if (
        part.defects
        or not isinstance(data, bytes)
        or not 0 < len(data) <= MAX_DOCUMENT_BYTES
        or len(data) != receipt.byte_size
        or not hmac.compare_digest(hashlib.sha256(data).hexdigest(), part_sha256)
    ):
        raise EmailAttachmentXlsxUnavailable()
    return data


def prove_email_attachment_xlsx_derivation(
    raw_mime: bytes, *, raw_sha256: str, raw_size_bytes: int,
    part_path: str, part_sha256: str, text: str, text_sha256: str,
    processor: DockerDocumentProcessor,
) -> EmailAttachmentXlsxProof:
    """Re-extract exact XLSX bytes in the pinned worker; retain no source text."""
    try:
        if (
            type(raw_mime) is not bytes
            or type(raw_size_bytes) is not int
            or not 0 < raw_size_bytes <= MAX_MIME_BYTES
            or len(raw_mime) != raw_size_bytes
            or type(raw_sha256) is not str
            or _SHA256.fullmatch(raw_sha256) is None
            or not hmac.compare_digest(hashlib.sha256(raw_mime).hexdigest(), raw_sha256)
            or type(part_path) is not str
            or _PART_PATH.fullmatch(part_path) is None
            or type(part_sha256) is not str
            or _SHA256.fullmatch(part_sha256) is None
            or type(text) is not str
            or not text
            or "\x00" in text
            or len(text) > MAX_TEXT_CHARS
            or type(text_sha256) is not str
            or _SHA256.fullmatch(text_sha256) is None
            or not hmac.compare_digest(
                hashlib.sha256(text.encode("utf-8", errors="strict")).hexdigest(), text_sha256
            )
            or type(processor) is not DockerDocumentProcessor
            or _PROCESSOR.fullmatch(processor.processor_version) is None
        ):
            raise EmailAttachmentXlsxUnavailable()
        document = _selected_xlsx(raw_mime, part_path, part_sha256)
        version_id = stable_id("version", raw_sha256, part_path, part_sha256)
        expected = source_for(document, version_id, "attachment.xlsx", part_sha256, SHEET_TYPE)
        result = processor.extract(
            document,
            version_id=version_id,
            locator="attachment.xlsx",
            sha256=part_sha256,
            media_type=SHEET_TYPE,
        )
        if (
            result.source != expected
            or result.status != "extracted"
            or result.reason != "bounded_xlsx_v1"
            or result.scanner_status != "unscanned"
            or result.text != text
            or type(result.metadata.sheet_count) is not int
            or not 0 < result.metadata.sheet_count <= MAX_SHEETS
            or type(result.metadata.cell_count) is not int
            or not 0 < result.metadata.cell_count <= MAX_CELLS
        ):
            raise EmailAttachmentXlsxUnavailable()
        return EmailAttachmentXlsxProof(
            raw_sha256, raw_size_bytes, part_path, part_sha256,
            text_sha256, processor.processor_version,
            result.metadata.sheet_count, result.metadata.cell_count,
        )
    except Exception:
        raise EmailAttachmentXlsxUnavailable() from None
