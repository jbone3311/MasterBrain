"""Nonpublishing row-layout proof for one exact retained Email XLSX part."""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass

from email_brain.pdf_contract import MAX_MIME_BYTES
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.document_contract import SHEET_TYPE, source_for
from masterbrain.datacore.email_xlsx_derivation import _selected_xlsx
from masterbrain.datacore.xlsx_tables import (
    projection_layout_sha256,
    require_indexed_text_digest,
)
from masterbrain.datacore.xlsx_tables_processor import DockerXlsxTableProcessor

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_PART_PATH = re.compile(r"^1(?:\.[1-9][0-9]{0,3}){0,20}$")
_NORMALIZER = re.compile(r"^sandbox-fileos-document-v1-([a-f0-9]{64})$")


class EmailAttachmentXlsxTableUnavailable(ValueError):
    def __init__(self) -> None:
        super().__init__("email_attachment_xlsx_table_unavailable")


@dataclass(frozen=True, slots=True)
class EmailAttachmentXlsxTableProof:
    raw_sha256: str
    raw_size_bytes: int
    part_path: str
    part_sha256: str
    text_sha256: str
    table_processor_version: str
    row_layout_sha256: str
    sheet_count: int
    row_count: int
    cell_count: int


def prove_email_attachment_xlsx_table_derivation(
    raw_mime: bytes, *, raw_sha256: str, raw_size_bytes: int,
    part_path: str, part_sha256: str, text_sha256: str,
    normalizer: str, processor: DockerXlsxTableProcessor,
) -> EmailAttachmentXlsxTableProof:
    """Reacquire one MIME part; bind physical rows to its indexed text digest."""
    image = _NORMALIZER.fullmatch(normalizer) if type(normalizer) is str else None
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
        or type(text_sha256) is not str
        or _SHA256.fullmatch(text_sha256) is None
        or image is None
        or type(processor) is not DockerXlsxTableProcessor
        or processor.processor_version != "sandbox-xlsx-tables-v1-" + image.group(1)
    ):
        raise EmailAttachmentXlsxTableUnavailable()
    try:
        document = _selected_xlsx(raw_mime, part_path, part_sha256)
        version_id = stable_id("version", raw_sha256, part_path, part_sha256)
        expected = source_for(document, version_id, "attachment.xlsx", part_sha256, SHEET_TYPE)
        projection = processor.extract(
            document, version_id=version_id, locator="attachment.xlsx",
            sha256=part_sha256, media_type=SHEET_TYPE,
        )
        if projection.source != expected:
            raise EmailAttachmentXlsxTableUnavailable()
        require_indexed_text_digest(projection, text_sha256)
        return EmailAttachmentXlsxTableProof(
            raw_sha256, raw_size_bytes, part_path, part_sha256, text_sha256,
            processor.processor_version, projection_layout_sha256(projection),
            len(projection.sheets), sum(len(sheet.rows) for sheet in projection.sheets),
            projection.cell_count,
        )
    except Exception:
        raise EmailAttachmentXlsxTableUnavailable() from None
