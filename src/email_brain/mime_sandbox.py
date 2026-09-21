"""Strict pipe-only MIME worker contract; process isolation is the runner's job.

The optional larger parser budget is confined to this opt-in worker. It performs
text-only normalization and attachment accounting, never binary extraction or I/O.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import asdict
from email.errors import MessageError
from typing import Any

from email_brain.attachments import (
    MAX_ATTACHMENTS,
    MAX_DEPTH,
    MAX_EXTRACTED_CHARS,
    MAX_TEXT_BYTES,
    Attachment,
    receive_attachments,
    safe_name,
)
from email_brain.normalize import MAX_TEXT_CHARS, NormalizedMessage, normalize

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
CONTRACT_VERSION = "sandbox-mime-v1"
_SHA = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_PART = re.compile(r"1(?:\.[1-9][0-9]{0,3}){0,20}\Z", re.ASCII)
_MEDIA = re.compile(r"[a-z0-9!#$%&'*+.^_`|~-]+/[a-z0-9!#$%&'*+.^_`|~-]+\Z", re.ASCII)
_REASONS = {
    "extracted": {"bounded_text_v1", "bounded_calendar_v1"},
    "deferred": {
        "active_content_quarantined",
        "extraction_byte_limit",
        "type_mismatch_or_binary",
        "calendar_unsupported_charset",
        "calendar_unsupported",
        "extraction_character_limit",
        "isolated_extractor_required",
    },
    "failed": {"calendar_invalid", "invalid_text_encoding"},
    "skipped": {"inline_image_not_ocr_enabled"},
}
_NORMALIZED_FIELDS = {
    "subject",
    "sender",
    "recipients",
    "internet_message_id",
    "text",
    "raw_sha256",
    "truncated",
}
_ATTACHMENT_FIELDS = {
    "part_id",
    "original_filename",
    "safe_filename",
    "media_type",
    "sha256",
    "byte_size",
    "status",
    "reason",
    "text",
}


class MimeUnavailable(Exception):
    """Infrastructure/contract failure, never a durable parsing rejection."""

    def __init__(self) -> None:
        super().__init__("isolated MIME processing unavailable")


def _text(value: Any, limit: int) -> str:
    if type(value) is not str or len(value) > limit or "\x00" in value:
        raise MimeUnavailable()
    value.encode("utf-8", errors="strict")
    return value


def _fields(value: Any, expected: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise MimeUnavailable()
    return value


def _normalized(value: Any, digest: str) -> NormalizedMessage:
    value = _fields(value, _NORMALIZED_FIELDS)
    recipients = value["recipients"]
    if not isinstance(recipients, list) or len(recipients) > 100:
        raise MimeUnavailable()
    text = _text(value["text"], MAX_TEXT_CHARS)
    if (
        type(value["raw_sha256"]) is not str
        or value["raw_sha256"] != digest
        or type(value["truncated"]) is not bool
        or (value["truncated"] and len(text) != MAX_TEXT_CHARS)
    ):
        raise MimeUnavailable()
    message_id = value["internet_message_id"]
    return NormalizedMessage(
        subject=_text(value["subject"], 2000),
        sender=_text(value["sender"], 320),
        recipients=tuple(_text(item, 320) for item in recipients),
        internet_message_id=None if message_id is None else _text(message_id, 1000),
        text=text,
        raw_sha256=digest,
        truncated=value["truncated"],
    )


def _attachment(value: Any) -> Attachment:
    value = _fields(value, _ATTACHMENT_FIELDS)
    fields = {
        name: _text(value[name], limit)
        for name, limit in (
            ("part_id", 101),
            ("original_filename", 1000),
            ("safe_filename", 120),
            ("media_type", 255),
            ("sha256", 64),
            ("status", 16),
            ("reason", 64),
            ("text", MAX_EXTRACTED_CHARS),
        )
    }
    if (
        not _PART.fullmatch(fields["part_id"])
        or len(fields["part_id"].split(".")) > MAX_DEPTH + 1
        or any(int(index) > 1000 for index in fields["part_id"].split("."))
        or fields["safe_filename"] != safe_name(fields["original_filename"])
        or not _MEDIA.fullmatch(fields["media_type"])
        or not _SHA.fullmatch(fields["sha256"])
        or type(value["byte_size"]) is not int
        or not 0 <= value["byte_size"] <= MAX_INPUT_BYTES
        or fields["reason"] not in _REASONS.get(fields["status"], set())
        or (fields["status"] != "extracted" and fields["text"] != "")
        or (fields["status"] == "extracted" and value["byte_size"] > MAX_TEXT_BYTES)
        or (fields["reason"] == "extraction_byte_limit" and value["byte_size"] <= MAX_TEXT_BYTES)
        or (
            fields["reason"]
            in {
                "calendar_invalid",
                "calendar_unsupported",
                "calendar_unsupported_charset",
            }
            and fields["media_type"] != "text/calendar"
        )
        or (
            fields["reason"] == "inline_image_not_ocr_enabled"
            and not fields["media_type"].startswith("image/")
        )
        or (
            fields["reason"] == "invalid_text_encoding"
            and fields["media_type"] not in {"text/plain", "text/csv", "text/markdown"}
        )
        or (fields["reason"] == "bounded_calendar_v1" and fields["media_type"] != "text/calendar")
        or (
            fields["reason"] == "bounded_text_v1"
            and fields["media_type"] not in {"text/plain", "text/csv", "text/markdown"}
        )
    ):
        raise MimeUnavailable()
    return Attachment(**fields, byte_size=value["byte_size"])


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MimeUnavailable()
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise MimeUnavailable()


def _validate_parts(attachments: list[Attachment]) -> None:
    parts: set[str] = set()
    for attachment in attachments:
        part = attachment.part_id
        if part in parts or any(
            prior.startswith(part + ".") or part.startswith(prior + ".") for prior in parts
        ):
            raise MimeUnavailable()
        parts.add(part)


def validate_prepared(
    result: object,
    raw: bytes,
) -> tuple[NormalizedMessage | None, list[Attachment], bool]:
    """Validate injected processor values before caching or publishing an outcome.

    Check types, collection lengths and string budgets before copying/serializing.
    Never asdict/deepcopy an unchecked processor-provided dataclass graph.
    """
    try:
        if (
            type(raw) is not bytes
            or len(raw) > MAX_INPUT_BYTES
            or type(result) is not tuple
            or len(result) != 3
        ):
            raise MimeUnavailable()
        normalized, attachments, rejected = result
        if (
            type(rejected) is not bool
            or type(attachments) is not list
            or len(attachments) > MAX_ATTACHMENTS
        ):
            raise MimeUnavailable()
        if rejected:
            if normalized is not None or attachments:
                raise MimeUnavailable()
            return None, [], True
        if not raw or type(normalized) is not NormalizedMessage:
            raise MimeUnavailable()
        if type(normalized.recipients) is not tuple or len(normalized.recipients) > 100:
            raise MimeUnavailable()
        normalized_values = {name: getattr(normalized, name) for name in _NORMALIZED_FIELDS}
        normalized_values["recipients"] = list(normalized.recipients)
        digest = hashlib.sha256(raw).hexdigest()
        verified_normalized = _normalized(normalized_values, digest)
        verified_attachments: list[Attachment] = []
        for attachment in attachments:
            if type(attachment) is not Attachment:
                raise MimeUnavailable()
            values = {name: getattr(attachment, name) for name in _ATTACHMENT_FIELDS}
            verified_attachments.append(_attachment(values))
        _validate_parts(verified_attachments)
        # Values are now bounded plain scalars; JSON escaping has a bounded
        # amplification, but still must fit the same response contract budget.
        if len(_encode(digest, verified_normalized, verified_attachments)) > MAX_OUTPUT_BYTES:
            raise MimeUnavailable()
        return verified_normalized, verified_attachments, False
    except (ValueError, TypeError, UnicodeError, RecursionError, AttributeError):
        raise MimeUnavailable() from None


def _json_budget(text: str) -> None:
    """Bound allocation before JSON decoding; syntax is still checked by json.loads.

    Valid envelopes need at most 68 containers and about 1500 separators. Quoted
    source text can contain arbitrary JSON-looking punctuation without penalty.
    """
    quoted, escaped = False, False
    depth, containers, separators = 0, 0, 0
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            containers += 1
            if depth > 8 or containers > 256:
                raise MimeUnavailable()
        elif char in "]}":
            depth -= 1
            if depth < 0:
                raise MimeUnavailable()
        elif char in ",:":
            separators += 1
            if separators > 4096:
                raise MimeUnavailable()


def decode_response(
    payload: bytes,
    raw: bytes,
) -> tuple[NormalizedMessage | None, list[Attachment], bool]:
    """Validate untrusted worker output before any persistence or publication."""
    try:
        if (
            not isinstance(raw, bytes)
            or len(raw) > MAX_INPUT_BYTES
            or not isinstance(payload, bytes)
            or not 0 < len(payload) <= MAX_OUTPUT_BYTES
        ):
            raise MimeUnavailable()
        text = payload.decode("utf-8", errors="strict")
        _json_budget(text)
        value = _fields(
            json.loads(
                text,
                object_pairs_hook=_unique_object,
                parse_constant=_invalid_constant,
            ),
            {"contract_version", "raw_sha256", "outcome", "normalized", "attachments"},
        )
        digest = hashlib.sha256(raw).hexdigest()
        if value["contract_version"] != CONTRACT_VERSION or value["raw_sha256"] != digest:
            raise MimeUnavailable()
        if value["outcome"] == "rejected":
            if value["normalized"] is not None or value["attachments"] != []:
                raise MimeUnavailable()
            return None, [], True
        if value["outcome"] != "parsed" or not raw:
            raise MimeUnavailable()
        normalized = _normalized(value["normalized"], digest)
        items = value["attachments"]
        if not isinstance(items, list) or len(items) > MAX_ATTACHMENTS:
            raise MimeUnavailable()
        attachments = [_attachment(item) for item in items]
        _validate_parts(attachments)
        return normalized, attachments, False
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise MimeUnavailable() from None


def _encode(
    digest: str, normalized: NormalizedMessage | None, attachments: list[Attachment]
) -> bytes:
    return json.dumps(
        {
            "contract_version": CONTRACT_VERSION,
            "raw_sha256": digest,
            "outcome": "parsed" if normalized is not None else "rejected",
            "normalized": asdict(normalized) if normalized is not None else None,
            "attachments": [asdict(item) for item in attachments],
        },
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("ascii")


def process_raw(raw: bytes) -> bytes:
    """Pure worker implementation; only deterministic MIME errors become rejection."""
    if not isinstance(raw, bytes) or len(raw) > MAX_INPUT_BYTES:
        raise MimeUnavailable()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        try:
            attachments = receive_attachments(raw, max_raw_bytes=MAX_INPUT_BYTES)
            normalized = normalize(raw, max_raw_bytes=MAX_INPUT_BYTES)
        except (ValueError, UnicodeError, RecursionError, MessageError):
            return _encode(digest, None, [])
        # Match the ordinary ingestion path's deterministic Unicode rejection.
        # Other malformed worker output is infrastructure/contract failure, not
        # permission to cache an immutable parsing rejection.
        try:
            values = [
                normalized.subject,
                normalized.sender,
                normalized.text,
                normalized.internet_message_id or "",
                *normalized.recipients,
            ]
            for attachment in attachments:
                values.extend(
                    [
                        attachment.original_filename,
                        attachment.safe_filename,
                        attachment.media_type,
                        attachment.text,
                    ]
                )
            for value in values:
                if "\x00" in value:
                    raise ValueError("unpublishable source Unicode")
                value.encode("utf-8", errors="strict")
        except (ValueError, UnicodeError):
            return _encode(digest, None, [])
        response = _encode(digest, normalized, attachments)
        decode_response(response, raw)
        return response
    except Exception:
        raise MimeUnavailable() from None


def _resource_limits() -> None:
    if sys.platform != "linux":
        raise MimeUnavailable()
    import resource

    for limit, value in (
        (resource.RLIMIT_CPU, 10),
        (resource.RLIMIT_AS, 512 * 1024 * 1024),
        (resource.RLIMIT_FSIZE, 0),
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_NOFILE, 64),
    ):
        resource.setrlimit(limit, (value, value))


def main() -> int:
    try:
        _resource_limits()
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        response = process_raw(raw)
        if len(response) > MAX_OUTPUT_BYTES:
            raise MimeUnavailable()
        sys.stdout.buffer.write(response)
        sys.stdout.buffer.flush()
        return 0
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
