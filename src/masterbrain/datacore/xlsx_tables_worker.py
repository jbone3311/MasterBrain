"""Restricted pipe-only XLSX table projector, never invoked from a public API."""

from __future__ import annotations

import logging
import sys

from email_brain.mime_sandbox import _resource_limits
from masterbrain.datacore.document_contract import (
    MAX_REQUEST_BYTES,
    DocumentUnavailable,
    decode_request,
)
from masterbrain.datacore.xlsx_tables import (
    MAX_OUTPUT_BYTES,
    XlsxTableProjection,
    decode_projection,
    encode_projection,
    project_xlsx_tables,
)


def process_request(payload: bytes) -> bytes:
    """Decode the existing source-bound input; emit only validated table rows."""
    try:
        raw, source = decode_request(payload)
        if source.format != "xlsx":
            raise DocumentUnavailable()
        result = project_xlsx_tables(raw, source)
        response = encode_projection(result)
        if len(response) > MAX_OUTPUT_BYTES:
            response = encode_projection(XlsxTableProjection(source, "deferred", "text_limit"))
        decode_projection(response, source)
        return response
    except Exception:
        raise DocumentUnavailable() from None


def main() -> int:
    try:
        _resource_limits()
        logging.disable(sys.maxsize)
        payload = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        response = process_request(payload)
        sys.stdout.buffer.write(response)
        sys.stdout.buffer.flush()
        return 0
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
