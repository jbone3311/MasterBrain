"""Point-in-time confined FileOS XLSX rows, without publication or effects."""

from __future__ import annotations

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
    SHEET_TYPE,
    DocumentUnavailable,
    source_for,
)
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.datacore.xlsx_tables import (
    projection_layout_sha256,
    require_indexed_text_digest,
)
from masterbrain.datacore.xlsx_tables_processor import DockerXlsxTableProcessor

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_DOCUMENT_NORMALIZER = re.compile(r"^sandbox-fileos-document-v1-([a-f0-9]{64})$")


class CurrentFileOSXlsxTableUnavailable(ValueError):
    def __init__(self) -> None:
        super().__init__("current_fileos_xlsx_table_unavailable")


@dataclass(frozen=True, slots=True)
class XlsxTableReplayProof:
    source_sha256: str
    source_size_bytes: int
    text_sha256: str
    table_processor_version: str
    row_layout_sha256: str
    sheet_count: int
    row_count: int
    cell_count: int


def replay_current_fileos_xlsx_tables(
    root: Path, *, locator: str, version_id: str, root_binding_sha256: str,
    source_sha256: str, source_size_bytes: int, text_sha256: str,
    normalizer: str, processor: DockerXlsxTableProcessor,
) -> XlsxTableReplayProof:
    """Reacquire one exact XLSX and bind its rows to an indexed text digest."""
    image = _DOCUMENT_NORMALIZER.fullmatch(normalizer) if type(normalizer) is str else None
    if (
        not isinstance(root, Path)
        or type(locator) is not str
        or PurePosixPath(locator).suffix.lower() != ".xlsx"
        or type(source_size_bytes) is not int
        or not 0 < source_size_bytes <= MAX_DOCUMENT_BYTES
        or type(source_sha256) is not str
        or _SHA256.fullmatch(source_sha256) is None
        or type(text_sha256) is not str
        or _SHA256.fullmatch(text_sha256) is None
        or type(root_binding_sha256) is not str
        or _SHA256.fullmatch(root_binding_sha256) is None
        or image is None
        or type(processor) is not DockerXlsxTableProcessor
        or processor.processor_version != "sandbox-xlsx-tables-v1-" + image.group(1)
    ):
        raise CurrentFileOSXlsxTableUnavailable()
    try:
        if fileos_root_binding_sha256(root) != root_binding_sha256:
            raise CurrentFileOSXlsxTableUnavailable()
        opened = read_confined_file(
            root, locator, max_bytes=MAX_DOCUMENT_BYTES, capture_bytes=True,
        )
        if (
            opened.raw is None
            or opened.size_bytes != source_size_bytes
            or not hmac.compare_digest(opened.sha256, source_sha256)
        ):
            raise CurrentFileOSXlsxTableUnavailable()
        expected = source_for(
            opened.raw, version_id, locator, source_sha256, SHEET_TYPE,
        )
        projection = processor.extract(
            opened.raw, version_id=version_id, locator=locator,
            sha256=source_sha256, media_type=SHEET_TYPE,
        )
        if (
            projection.source != expected
            or projection.status != "extracted"
            or projection.reason != "bounded_xlsx_tables_v1"
        ):
            raise CurrentFileOSXlsxTableUnavailable()
        require_indexed_text_digest(projection, text_sha256)
        if fileos_root_binding_sha256(root) != root_binding_sha256:
            raise CurrentFileOSXlsxTableUnavailable()
        return XlsxTableReplayProof(
            source_sha256, source_size_bytes, text_sha256,
            processor.processor_version,
            projection_layout_sha256(projection),
            len(projection.sheets),
            sum(len(sheet.rows) for sheet in projection.sheets),
            projection.cell_count,
        )
    except (
        ConfinedFileUnavailable, ConfinedFileChanged, ConfinedFileTooLarge,
        DocumentUnavailable, OSError, RuntimeError, UnicodeError, ValueError,
    ):
        raise CurrentFileOSXlsxTableUnavailable() from None
