"""Restricted pipe-only worker for one hash-bound archive member."""

from __future__ import annotations

import logging
import sys

from email_brain.mime_sandbox import _resource_limits
from masterbrain.datacore.archive_contract import ArchiveUnavailable
from masterbrain.datacore.archive_member_contract import (
    MAX_MEMBER_BYTES,
    MAX_OUTPUT_BYTES,
    MAX_REQUEST_BYTES,
    ArchiveMemberResult,
    decode_request,
    decode_result,
    encode_result,
)
from masterbrain.datacore.archive_worker import read_archive_member


def process_request(payload: bytes) -> bytes:
    try:
        archive, source, target = decode_request(payload)
        raw = read_archive_member(
            archive,
            source,
            locator=target.locator,
            sha256=target.sha256,
            size_bytes=target.size_bytes,
            depth=target.depth,
            parent_locator=target.parent_locator,
        )
        if len(raw) > MAX_MEMBER_BYTES:
            result = ArchiveMemberResult(
                source, target, "deferred", "member_output_limit", b""
            )
        else:
            result = ArchiveMemberResult(
                source, target, "read", "hash_bound_archive_member_v1", raw
            )
        response = encode_result(result)
        if len(response) > MAX_OUTPUT_BYTES:
            raise ArchiveUnavailable()
        decode_result(response, source, target)
        return response
    except Exception:
        raise ArchiveUnavailable() from None


def main() -> int:
    try:
        _resource_limits()
        logging.disable(sys.maxsize)
        payload = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        response = process_request(payload)
        if len(response) > MAX_OUTPUT_BYTES:
            raise ArchiveUnavailable()
        sys.stdout.buffer.write(response)
        sys.stdout.buffer.flush()
        return 0
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
