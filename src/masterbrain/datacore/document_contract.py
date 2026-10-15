"""Closed source-bound pipe contract for isolated FileOS document extraction."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any

from email_brain.mime_sandbox import _invalid_constant, _json_budget, _unique_object

CONTRACT = "sandbox-fileos-document-v1"
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_REQUEST_BYTES = 12 * 1024 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_TEXT_CHARS = 200_000
MAX_PAGES = 40
MAX_SHEETS = 20
MAX_PARAGRAPHS = 2_000
MAX_TABLES = 100
MAX_ROWS_PER_SHEET = 2_000
MAX_COLUMNS = 100
MAX_CELLS = 20_000
MAX_ZIP_MEMBERS = 500
MAX_ZIP_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_ZIP_RATIO = 200

PDF_TYPE = "application/pdf"
WORD_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SHEET_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_HASH = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_VERSION = re.compile(r"(?:version|archiveversion)_[a-f0-9]{32}\Z", re.ASCII)
_FORMATS = {
    (".pdf", PDF_TYPE): "pdf",
    (".docx", WORD_TYPE): "docx",
    (".xlsx", SHEET_TYPE): "xlsx",
}
_OUTCOMES = {
    "bounded_pdf_v1": "extracted",
    "bounded_docx_v1": "extracted",
    "bounded_xlsx_v1": "extracted",
    "empty_document": "deferred",
    "pages_without_text": "deferred",
    "encrypted": "deferred",
    "unsupported_features": "deferred",
    "document_byte_limit": "deferred",
    "page_limit": "deferred",
    "structure_limit": "deferred",
    "text_limit": "deferred",
    "invalid_document": "failed",
}


class DocumentUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("document_processing_unavailable")


def _locator(value: object) -> str:
    if type(value) is not str or not 1 <= len(value) <= 1024 or "\x00" in value or "\\" in value:
        raise DocumentUnavailable()
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) != value or value.endswith("/"):
        raise DocumentUnavailable()
    return value


@dataclass(frozen=True, slots=True)
class DocumentSource:
    version_id: str
    locator: str
    sha256: str
    size_bytes: int
    media_type: str
    format: str

    def __post_init__(self) -> None:
        suffix = PurePosixPath(_locator(self.locator)).suffix.lower()
        if (
            type(self.version_id) is not str
            or not _VERSION.fullmatch(self.version_id)
            or type(self.sha256) is not str
            or not _HASH.fullmatch(self.sha256)
            or type(self.size_bytes) is not int
            or not 0 < self.size_bytes <= MAX_DOCUMENT_BYTES
            or type(self.media_type) is not str
            or _FORMATS.get((suffix, self.media_type)) != self.format
        ):
            raise DocumentUnavailable()


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    title: str | None = None
    author: str | None = None
    page_count: int | None = None
    paragraph_count: int | None = None
    table_count: int | None = None
    sheet_count: int | None = None
    cell_count: int | None = None


@dataclass(frozen=True, slots=True)
class DocumentResult:
    source: DocumentSource
    status: str
    reason: str
    text: str = ""
    metadata: DocumentMetadata = DocumentMetadata()
    scanner_status: str = "unscanned"


def source_for(
    raw: bytes, version_id: str, locator: str, sha256: str, media_type: str
) -> DocumentSource:
    try:
        suffix = PurePosixPath(_locator(locator)).suffix.lower()
        source = DocumentSource(
            version_id,
            locator,
            sha256,
            len(raw),
            media_type,
            _FORMATS[(suffix, media_type)],
        )
        if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != sha256:
            raise DocumentUnavailable()
        return source
    except Exception:
        raise DocumentUnavailable() from None


def _fields(value: Any, expected: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise DocumentUnavailable()
    return value


def _load(payload: bytes, limit: int) -> dict[str, Any]:
    try:
        if type(payload) is not bytes or not 0 < len(payload) <= limit:
            raise DocumentUnavailable()
        text = payload.decode("utf-8", errors="strict")
        _json_budget(text)
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        if type(value) is not dict:
            raise DocumentUnavailable()
        return value
    except Exception:
        raise DocumentUnavailable() from None


def _dump(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode()


def encode_request(
    raw: bytes, version_id: str, locator: str, sha256: str, media_type: str
) -> bytes:
    source = source_for(raw, version_id, locator, sha256, media_type)
    return _dump(
        {
            "contract_version": CONTRACT,
            "source": asdict(source),
            "raw_base64": base64.b64encode(raw).decode("ascii"),
        }
    )


def decode_request(payload: bytes) -> tuple[bytes, DocumentSource]:
    try:
        value = _fields(
            _load(payload, MAX_REQUEST_BYTES), {"contract_version", "source", "raw_base64"}
        )
        if value["contract_version"] != CONTRACT or type(value["raw_base64"]) is not str:
            raise DocumentUnavailable()
        encoded = value["raw_base64"]
        if len(encoded) > 4 * ((MAX_DOCUMENT_BYTES + 2) // 3):
            raise DocumentUnavailable()
        raw = base64.b64decode(encoded, validate=True)
        if base64.b64encode(raw).decode("ascii") != encoded:
            raise DocumentUnavailable()
        source_data = _fields(
            value["source"],
            {"version_id", "locator", "sha256", "size_bytes", "media_type", "format"},
        )
        source = source_for(
            raw,
            source_data["version_id"],
            source_data["locator"],
            source_data["sha256"],
            source_data["media_type"],
        )
        if asdict(source) != source_data:
            raise DocumentUnavailable()
        return raw, source
    except Exception:
        raise DocumentUnavailable() from None


def encode_result(result: DocumentResult) -> bytes:
    return _dump({"contract_version": CONTRACT, **asdict(result)})


def _optional_text(value: object, limit: int) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not 1 <= len(value) <= limit or "\x00" in value:
        raise DocumentUnavailable()
    value.encode("utf-8", errors="strict")
    return value


def _optional_count(value: object, limit: int) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= limit:
        raise DocumentUnavailable()
    return value


def decode_result(payload: bytes, source: DocumentSource) -> DocumentResult:
    """Treat the entire isolated-child response as untrusted."""
    try:
        value = _fields(
            _load(payload, MAX_OUTPUT_BYTES),
            {
                "contract_version",
                "source",
                "status",
                "reason",
                "text",
                "metadata",
                "scanner_status",
            },
        )
        source_data = _fields(
            value["source"],
            {"version_id", "locator", "sha256", "size_bytes", "media_type", "format"},
        )
        if (
            type(source) is not DocumentSource
            or source_data != asdict(source)
            or value["contract_version"] != CONTRACT
            or value["scanner_status"] != "unscanned"
            or type(value["reason"]) is not str
            or value["reason"] not in _OUTCOMES
            or value["status"] != _OUTCOMES[value["reason"]]
            or type(value["text"]) is not str
        ):
            raise DocumentUnavailable()
        text = value["text"]
        if len(text) > MAX_TEXT_CHARS or "\x00" in text or text != text.strip():
            raise DocumentUnavailable()
        text.encode("utf-8", errors="strict")
        if (value["status"] == "extracted") != bool(text):
            raise DocumentUnavailable()
        metadata_data = _fields(
            value["metadata"],
            {
                "title",
                "author",
                "page_count",
                "paragraph_count",
                "table_count",
                "sheet_count",
                "cell_count",
            },
        )
        metadata = DocumentMetadata(
            title=_optional_text(metadata_data["title"], 300),
            author=_optional_text(metadata_data["author"], 300),
            page_count=_optional_count(metadata_data["page_count"], MAX_PAGES),
            paragraph_count=_optional_count(metadata_data["paragraph_count"], MAX_PARAGRAPHS),
            table_count=_optional_count(metadata_data["table_count"], MAX_TABLES),
            sheet_count=_optional_count(metadata_data["sheet_count"], MAX_SHEETS),
            cell_count=_optional_count(metadata_data["cell_count"], MAX_CELLS),
        )
        expected_reason = f"bounded_{source.format}_v1"
        if value["status"] == "extracted" and value["reason"] != expected_reason:
            raise DocumentUnavailable()
        return DocumentResult(source, value["status"], value["reason"], text, metadata)
    except Exception:
        raise DocumentUnavailable() from None
