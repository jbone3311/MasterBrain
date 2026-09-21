"""Restricted pipe-only PDF child; never call on untrusted documents in the API."""

from __future__ import annotations

import hashlib
import logging
import sys
from email import policy
from email.message import Message
from email.parser import BytesParser
from io import BytesIO

from email_brain.attachments import receive_attachments
from email_brain.mime_sandbox import _resource_limits
from email_brain.pdf_contract import (
    MAX_MIME_BYTES,
    MAX_OUTPUT_BYTES,
    MAX_PAGE_CHARS,
    MAX_PAGE_STREAM_BYTES,
    MAX_PAGES,
    MAX_PDF_BYTES,
    MAX_REQUEST_BYTES,
    MAX_TOTAL_CHARS,
    MAX_TOTAL_STREAM_BYTES,
    PdfPage,
    PdfResult,
    PdfSource,
    PdfUnavailable,
    decode_request,
    decode_result,
    encode_result,
)


class _EncryptedPdf(Exception):
    pass


def _selected_pdf(raw: bytes, source: PdfSource) -> bytes:
    receipts = receive_attachments(raw, max_raw_bytes=MAX_MIME_BYTES)
    receipt = next((part for part in receipts if part.part_id == source.part_path), None)
    if (
        receipt is None
        or receipt.sha256 != source.part_sha256
        or receipt.media_type != "application/pdf"
        or receipt.status != "deferred"
        or receipt.reason not in {"isolated_extractor_required", "extraction_byte_limit"}
    ):
        raise PdfUnavailable()
    part: Message = BytesParser(policy=policy.default).parsebytes(raw)
    for component in source.part_path.split(".")[1:]:
        children = part.get_payload()
        index = int(component) - 1
        if not isinstance(children, list) or index >= len(children):
            raise PdfUnavailable()
        child = children[index]
        if not isinstance(child, Message):
            raise PdfUnavailable()
        part = child
    data = part.get_payload(decode=True)
    if (
        part.defects
        or not isinstance(data, bytes)
        or len(data) != receipt.byte_size
        or hashlib.sha256(data).hexdigest() != source.part_sha256
    ):
        raise PdfUnavailable()
    return data


def _extract(data: bytes, source: PdfSource) -> PdfResult:
    if len(data) > MAX_PDF_BYTES:
        return PdfResult(source, "deferred", "pdf_byte_limit", None)
    if not data.startswith(b"%PDF-"):
        return PdfResult(source, "failed", "invalid_pdf", None)
    # Lazy import: parent/API contract imports cannot load the optional PDF reader.
    import pypdf
    from pypdf.errors import PdfReadError

    if pypdf.__version__ != "6.19.0":
        raise PdfUnavailable()

    class NoDecryptReader(pypdf.PdfReader):
        # The pinned reader otherwise tries an empty password during construction.
        # Refuse before encryption metadata/decryption work; regression-tested hook.
        def _handle_encryption(self, password: str | bytes | None) -> None:
            raise _EncryptedPdf()

    try:
        reader = NoDecryptReader(BytesIO(data), strict=True)
        try:
            if reader.is_encrypted:
                return PdfResult(source, "deferred", "encrypted", None)
            if any(
                key in reader.root_object
                for key in ("/OpenAction", "/AA", "/Names", "/AcroForm", "/AF", "/Collection")
            ):
                return PdfResult(source, "deferred", "unsupported_features", None)
            count = len(reader.pages)
            if count > MAX_PAGES:
                return PdfResult(source, "deferred", "page_limit", None)
            if count == 0:
                return PdfResult(source, "failed", "invalid_pdf", None)
            pages: list[PdfPage] = []
            stream_bytes = chars = 0
            for number, page in enumerate(reader.pages, 1):
                if any(key in page for key in ("/AA", "/Annots", "/AF")):
                    return PdfResult(source, "deferred", "unsupported_features", count)
                content = page.get_contents()
                size = len(content.get_data()) if content is not None else 0
                stream_bytes += size
                if size > MAX_PAGE_STREAM_BYTES or stream_bytes > MAX_TOTAL_STREAM_BYTES:
                    return PdfResult(source, "deferred", "stream_limit", count)
                text = page.extract_text().replace("\x00", "").strip()
                text.encode("utf-8", errors="strict")
                chars += len(text)
                if len(text) > MAX_PAGE_CHARS or chars > MAX_TOTAL_CHARS:
                    return PdfResult(source, "deferred", "text_limit", count)
                pages.append(PdfPage(number, text))
            if not any(page.text for page in pages):
                return PdfResult(source, "deferred", "no_text", count)
            partial = any(not page.text for page in pages)
            return PdfResult(
                source,
                "partial" if partial else "extracted",
                "pages_without_text" if partial else "bounded_pdf_v1",
                count,
                tuple(pages),
            )
        finally:
            reader.close()
    except _EncryptedPdf:
        return PdfResult(source, "deferred", "encrypted", None)
    except PdfReadError:
        return PdfResult(source, "failed", "invalid_pdf", None)


def process_request(payload: bytes) -> bytes:
    """Pure child logic; tests use only authored synthetic bytes in-process."""
    try:
        raw, source = decode_request(payload)
        data = _selected_pdf(raw, source)
        result = _extract(data, source)
        response = encode_result(result)
        if len(response) > MAX_OUTPUT_BYTES:
            response = encode_result(PdfResult(source, "deferred", "text_limit", result.page_count))
        decode_result(response, source)
        return response
    except Exception:
        raise PdfUnavailable() from None


def main() -> int:
    try:
        _resource_limits()
        logging.disable(sys.maxsize)
        payload = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        response = process_request(payload)
        if len(response) > MAX_OUTPUT_BYTES:
            raise PdfUnavailable()
        sys.stdout.buffer.write(response)
        sys.stdout.buffer.flush()
        return 0
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
