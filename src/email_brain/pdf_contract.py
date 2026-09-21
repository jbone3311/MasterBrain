"""Closed source-bound PDF pipe contract; safe to import without a PDF reader."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from email_brain.mime_sandbox import _invalid_constant, _json_budget, _unique_object

CONTRACT = "sandbox-pdf-v1"
MAX_MIME_BYTES = 16 * 1024 * 1024
MAX_REQUEST_BYTES = 24 * 1024 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_PDF_BYTES = 4 * 1024 * 1024
MAX_PAGES = 40
MAX_PAGE_CHARS = 20000
MAX_TOTAL_CHARS = 100000
MAX_PAGE_STREAM_BYTES = 2 * 1024 * 1024
MAX_TOTAL_STREAM_BYTES = 8 * 1024 * 1024
_HASH = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_PATH = re.compile(r"1(?:\.[1-9][0-9]{0,3}){0,20}\Z", re.ASCII)
_OUTCOMES = {
    "bounded_pdf_v1": "extracted",
    "pages_without_text": "partial",
    "no_text": "deferred",
    "encrypted": "deferred",
    "unsupported_features": "deferred",
    "pdf_byte_limit": "deferred",
    "page_limit": "deferred",
    "stream_limit": "deferred",
    "text_limit": "deferred",
    "invalid_pdf": "failed",
}


class PdfUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("pdf_processing_unavailable")


@dataclass(frozen=True)
class PdfSource:
    raw_sha256: str
    part_path: str
    part_sha256: str

    def __post_init__(self) -> None:
        if (
            type(self.raw_sha256) is not str
            or not _HASH.fullmatch(self.raw_sha256)
            or type(self.part_sha256) is not str
            or not _HASH.fullmatch(self.part_sha256)
            or type(self.part_path) is not str
            or not _PATH.fullmatch(self.part_path)
        ):
            raise PdfUnavailable()


@dataclass(frozen=True)
class PdfPage:
    number: int
    text: str


@dataclass(frozen=True)
class PdfResult:
    source: PdfSource
    status: str
    reason: str
    page_count: int | None
    pages: tuple[PdfPage, ...] = ()
    scanner_status: str = "unscanned"


def source_for(raw: bytes, part_path: str, part_sha256: str) -> PdfSource:
    if (
        type(raw) is not bytes
        or not 0 < len(raw) <= MAX_MIME_BYTES
        or type(part_path) is not str
        or not _PATH.fullmatch(part_path)
        or type(part_sha256) is not str
        or not _HASH.fullmatch(part_sha256)
    ):
        raise PdfUnavailable()
    return PdfSource(hashlib.sha256(raw).hexdigest(), part_path, part_sha256)


def _fields(value: Any, expected: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise PdfUnavailable()
    return value


def _load(payload: bytes, limit: int) -> dict[str, Any]:
    try:
        if type(payload) is not bytes or not 0 < len(payload) <= limit:
            raise PdfUnavailable()
        text = payload.decode("utf-8", errors="strict")
        _json_budget(text)
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        if type(value) is not dict:
            raise PdfUnavailable()
        return value
    except Exception:
        raise PdfUnavailable() from None


def _dump(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode()


def encode_request(raw: bytes, part_path: str, part_sha256: str) -> bytes:
    source = source_for(raw, part_path, part_sha256)
    return _dump(
        {
            "contract_version": CONTRACT,
            **asdict(source),
            "raw_base64": base64.b64encode(raw).decode("ascii"),
        }
    )


def decode_request(payload: bytes) -> tuple[bytes, PdfSource]:
    try:
        value = _fields(
            _load(payload, MAX_REQUEST_BYTES),
            {"contract_version", "raw_sha256", "part_path", "part_sha256", "raw_base64"},
        )
        if value["contract_version"] != CONTRACT or type(value["raw_base64"]) is not str:
            raise PdfUnavailable()
        encoded = value["raw_base64"]
        if len(encoded) > 4 * ((MAX_MIME_BYTES + 2) // 3):
            raise PdfUnavailable()
        raw = base64.b64decode(encoded, validate=True)
        if base64.b64encode(raw).decode("ascii") != encoded:
            raise PdfUnavailable()
        source = source_for(raw, value["part_path"], value["part_sha256"])
        if value["raw_sha256"] != source.raw_sha256:
            raise PdfUnavailable()
        return raw, source
    except Exception:
        raise PdfUnavailable() from None


def encode_result(result: PdfResult) -> bytes:
    return _dump({"contract_version": CONTRACT, **asdict(result)})


def decode_result(payload: bytes, source: PdfSource) -> PdfResult:
    """Treat the entire child response as untrusted; no persistence side effects."""
    try:
        value = _fields(
            _load(payload, MAX_OUTPUT_BYTES),
            {
                "contract_version",
                "source",
                "status",
                "reason",
                "page_count",
                "pages",
                "scanner_status",
            },
        )
        if (
            type(source) is not PdfSource
            or _fields(value["source"], {"raw_sha256", "part_path", "part_sha256"})
            != asdict(source)
            or value["contract_version"] != CONTRACT
            or value["scanner_status"] != "unscanned"
            or type(value["reason"]) is not str
            or value["reason"] not in _OUTCOMES
            or value["status"] != _OUTCOMES[value["reason"]]
        ):
            raise PdfUnavailable()
        count, items = value["page_count"], value["pages"]
        if count is not None and (type(count) is not int or not 1 <= count <= MAX_PAGES):
            raise PdfUnavailable()
        if type(items) is not list or len(items) > MAX_PAGES:
            raise PdfUnavailable()
        pages: list[PdfPage] = []
        for index, item in enumerate(items, 1):
            page = _fields(item, {"number", "text"})
            text = page["text"]
            if (
                type(page["number"]) is not int
                or page["number"] != index
                or type(text) is not str
                or len(text) > MAX_PAGE_CHARS
                or "\x00" in text
                or text != text.strip()
            ):
                raise PdfUnavailable()
            text.encode("utf-8", errors="strict")
            pages.append(PdfPage(index, text))
        if sum(len(page.text) for page in pages) > MAX_TOTAL_CHARS:
            raise PdfUnavailable()
        if value["status"] in {"extracted", "partial"}:
            if count is None or len(pages) != count or not any(p.text for p in pages):
                raise PdfUnavailable()
            partial = any(not p.text for p in pages)
            if partial != (value["status"] == "partial"):
                raise PdfUnavailable()
        elif pages:
            raise PdfUnavailable()
        if value["reason"] == "no_text" and count is None:
            raise PdfUnavailable()
        if value["reason"] in {"encrypted", "pdf_byte_limit", "page_limit"} and count is not None:
            raise PdfUnavailable()
        return PdfResult(source, value["status"], value["reason"], count, tuple(pages))
    except Exception:
        raise PdfUnavailable() from None
