"""Receive and account for attachments without filesystem placement or binary execution.

Factory intake patterns: retain receipts, link duplicates, distinguish deferred from
success, and only index actual extracted content. See docs/FACTORY_INTAKE_REVIEW.md.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from email import policy
from email.message import Message
from email.parser import BytesParser
from pathlib import PurePosixPath

from email_brain.calendar_attachment import CalendarInvalid, CalendarUnsupported, extract_calendar
from email_brain.normalize import MAX_RAW_BYTES, validate_raw_budget

MAX_ATTACHMENTS = 64
MAX_TEXT_BYTES = 262144
MAX_DEPTH = 20
MAX_PARTS = 1000
MAX_EXTRACTED_CHARS = 20000


@dataclass(frozen=True)
class Attachment:
    part_id: str
    original_filename: str
    safe_filename: str
    media_type: str
    sha256: str
    byte_size: int
    status: str
    reason: str
    text: str = ""


def safe_name(value: str) -> str:
    name = PurePosixPath(value.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._")[:120]
    return name or "attachment"


def _classify(part: Message, path: str) -> Attachment:
    media_type = part.get_content_type()
    default_name = f"calendar-{path}.ics" if media_type == "text/calendar" else f"attachment-{path}"
    filename = str(part.get_filename() or default_name).replace("\x00", "")[:1000]
    raw = part.get_payload(decode=True)
    if not isinstance(raw, bytes):
        # Nested emails/containers are retained as source MIME and deferred, not recursed.
        raw = part.as_bytes(policy=policy.default)
    base = Attachment(
        part_id=path,
        original_filename=filename,
        safe_filename=safe_name(filename),
        media_type=media_type,
        sha256=hashlib.sha256(raw).hexdigest(),
        byte_size=len(raw),
        status="pending",
        reason="received",
    )
    suffix = PurePosixPath(safe_name(filename)).suffix.lower()
    if raw.startswith((b"MZ", b"\x7fELF", b"#!")) or suffix in {
        ".exe",
        ".dll",
        ".js",
        ".sh",
        ".bat",
        ".ps1",
        ".com",
        ".scr",
    }:
        return replace(base, status="deferred", reason="active_content_quarantined")
    if media_type.startswith("image/") and part.get_content_disposition() == "inline":
        return replace(base, status="skipped", reason="inline_image_not_ocr_enabled")
    if len(raw) > MAX_TEXT_BYTES:
        return replace(base, status="deferred", reason="extraction_byte_limit")
    if media_type == "text/calendar":
        if suffix not in {"", ".ics"}:
            return replace(base, status="deferred", reason="type_mismatch_or_binary")
        charset = (part.get_content_charset() or "utf-8").lower()
        if charset not in {"utf-8", "us-ascii"}:
            return replace(base, status="deferred", reason="calendar_unsupported_charset")
        if part.defects or (charset == "us-ascii" and not raw.isascii()):
            return replace(base, status="failed", reason="calendar_invalid")
        mime_method = part.get_param("method")
        if mime_method is not None and not isinstance(mime_method, str):
            return replace(base, status="failed", reason="calendar_invalid")
        try:
            text = extract_calendar(raw, mime_method=mime_method)
        except CalendarUnsupported:
            return replace(base, status="deferred", reason="calendar_unsupported")
        except CalendarInvalid:
            return replace(base, status="failed", reason="calendar_invalid")
        if len(text) > MAX_EXTRACTED_CHARS:
            return replace(base, status="deferred", reason="extraction_character_limit")
        return replace(base, status="extracted", reason="bounded_calendar_v1", text=text)
    if media_type not in {"text/plain", "text/csv", "text/markdown"}:
        return replace(base, status="deferred", reason="isolated_extractor_required")
    if suffix not in {"", ".txt", ".csv", ".md"} or b"\x00" in raw:
        return replace(base, status="deferred", reason="type_mismatch_or_binary")
    if raw.startswith((b"PK\x03\x04", b"%PDF", b"\xd0\xcf\x11\xe0")):
        return replace(base, status="deferred", reason="type_mismatch_or_binary")
    try:
        text = raw.decode(part.get_content_charset() or "utf-8", errors="strict")
    except (UnicodeError, LookupError):
        return replace(base, status="failed", reason="invalid_text_encoding")
    if len(text) > MAX_EXTRACTED_CHARS:
        return replace(base, status="deferred", reason="extraction_character_limit")
    return replace(base, status="extracted", reason="bounded_text_v1", text=text)


def receive_attachments(raw: bytes, *, max_raw_bytes: int = MAX_RAW_BYTES) -> list[Attachment]:
    validate_raw_budget(max_raw_bytes)
    if not isinstance(raw, bytes) or not raw or len(raw) > max_raw_bytes:
        raise ValueError("MIME byte limit")
    root = BytesParser(policy=policy.default).parsebytes(raw)
    results: list[Attachment] = []
    stack: list[tuple[Message, str, int]] = [(root, "1", 0)]
    count = 0
    while stack:
        part, path, depth = stack.pop()
        count += 1
        if depth > MAX_DEPTH or count > MAX_PARTS:
            raise ValueError("MIME complexity limit")
        if (
            part.get_filename() is not None
            or part.get_content_disposition() in {"attachment", "inline"}
            or (path != "1" and part.get_content_type() == "message/rfc822")
            or part.get_content_type() == "text/calendar"
        ):
            if len(results) >= MAX_ATTACHMENTS:
                raise ValueError("attachment count limit")
            results.append(_classify(part, path))
            continue
        payload = part.get_payload()
        if isinstance(payload, list):
            stack.extend(
                (child, f"{path}.{index}", depth + 1)
                for index, child in reversed(list(enumerate(payload, start=1)))
                if isinstance(child, Message)
            )
    return results


def reconcile(statuses: list[str]) -> dict[str, int | bool]:
    counts: dict[str, int | bool] = {
        state: statuses.count(state)
        for state in ("extracted", "failed", "skipped", "deferred", "pending")
    }
    counts["total"] = len(statuses)
    counts["unaccounted"] = len(statuses) - sum(int(v) for k, v in counts.items() if k != "total")
    counts["ready"] = all(
        counts[key] == 0 for key in ("failed", "deferred", "pending", "unaccounted")
    )
    return counts
