"""Human-only, source-bound message reading. No HTML rendering or binary execution."""

from __future__ import annotations

import hashlib
from email import policy
from email.errors import MessageError
from email.message import EmailMessage, Message
from email.parser import BytesParser
from typing import Any
from uuid import UUID

from email_brain.attachments import MAX_DEPTH, MAX_PARTS
from email_brain.auth import Principal
from email_brain.blobs import MAX_BLOB_BYTES, BlobError
from email_brain.normalize import MAX_RAW_BYTES, body_text
from email_brain.store import AccessDenied, Conflict, NotFound, Store

MAX_BODY_CHARS = 2 * MAX_RAW_BYTES
MAX_HEADERS = 100
MAX_HEADER_CHARS = 4000
MAX_HEADER_TOTAL = 65536


class ReaderUnavailable(Exception):
    def __init__(self) -> None:
        super().__init__("message reader unavailable")


def parse_small(raw: bytes) -> EmailMessage:
    """Never increase the ordinary API's MIME budget to parse an external object."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_RAW_BYTES:
        raise ReaderUnavailable()
    try:
        mail = BytesParser(policy=policy.default).parsebytes(raw)
        if not isinstance(mail, EmailMessage):
            raise ReaderUnavailable()
        stack: list[tuple[Message, int]] = [(mail, 0)]
        count = 0
        while stack:
            part, depth = stack.pop()
            count += 1
            if depth > MAX_DEPTH or count > MAX_PARTS:
                raise ReaderUnavailable()
            # A nested message/container is not part of the visible selected body.
            if part.get_content_maintype() == "message" or part.get_filename() is not None:
                continue
            payload = part.get_payload()
            if isinstance(payload, list):
                for child in payload:
                    if not isinstance(child, Message):
                        raise ReaderUnavailable()
                    stack.append((child, depth + 1))
        return mail
    except (ValueError, UnicodeError, RecursionError, MessageError):
        raise ReaderUnavailable() from None


def decoded_body(mail: EmailMessage) -> str:
    try:
        value = body_text(mail)
        if len(value) > MAX_BODY_CHARS:
            raise ReaderUnavailable()
        value.encode("utf-8", errors="strict")
        return value
    except (ValueError, UnicodeError, RecursionError, MessageError):
        raise ReaderUnavailable() from None


def header_view(mail: EmailMessage) -> tuple[list[dict[str, str]], bool]:
    """Bound metadata separately; the original download retains every header byte."""
    headers: list[dict[str, str]] = []
    remaining = MAX_HEADER_TOTAL
    truncated = False
    try:
        for name, value in mail.items():
            if len(headers) == MAX_HEADERS or remaining <= 0:
                truncated = True
                break
            name = str(name).replace("\x00", "")
            value = str(value).replace("\x00", "")
            name.encode("utf-8", errors="strict")
            value.encode("utf-8", errors="strict")
            bounded_name = name[:100]
            bounded_value = value[: min(MAX_HEADER_CHARS, remaining)]
            truncated |= name != bounded_name or value != bounded_value
            headers.append({"name": bounded_name, "value": bounded_value})
            remaining -= len(bounded_value)
        return headers, truncated
    except (ValueError, UnicodeError, RecursionError, MessageError):
        raise ReaderUnavailable() from None


def attachment_bytes(mail: EmailMessage, receipt: dict[str, Any]) -> bytes:
    try:
        components = receipt["part_id"].split(".")
        if components[0] != "1" or not 1 <= len(components) <= MAX_DEPTH + 1:
            raise ReaderUnavailable()
        part: Message = mail
        for component in components[1:]:
            if not component.isascii() or not component.isdecimal() or len(component) > 4:
                raise ReaderUnavailable()
            children = part.get_payload()
            index = int(component) - 1
            if not isinstance(children, list) or not 0 <= index < len(children):
                raise ReaderUnavailable()
            child = children[index]
            if not isinstance(child, Message):
                raise ReaderUnavailable()
            part = child
        # Nested MIME must be exported as the original, not reserialized as a leaf.
        if part.is_multipart():
            raise Conflict("download the original for nested attachments")
        data = part.get_payload(decode=True)
        if (
            part.defects
            or not isinstance(data, bytes)
            or len(data) > MAX_RAW_BYTES
            or len(data) != receipt["byte_size"]
            or hashlib.sha256(data).hexdigest() != receipt["sha256"]
        ):
            raise ReaderUnavailable()
        return data
    except (ValueError, UnicodeError, RecursionError, MessageError):
        raise ReaderUnavailable() from None


class MessageReader:
    def __init__(self, store: Store) -> None:
        self.store = store

    def _source(self, principal: Principal, evidence_id: UUID) -> dict[str, Any]:
        if principal.client_kind != "human":
            raise AccessDenied()
        self.store.require(principal.context, "email.evidence.read")
        with self.store.transaction(principal.context) as conn:
            row = conn.execute(
                "SELECT v.id,v.message_id,v.account_id,v.raw_sha256,v.snapshot,r.raw_size "
                "FROM message_versions v JOIN mail_accounts a "
                "ON a.tenant_id=v.tenant_id AND a.id=v.account_id "
                "JOIN raw_objects r ON r.tenant_id=v.tenant_id AND r.account_id=v.account_id "
                "AND r.sha256=v.raw_sha256 WHERE v.id=%s AND a.status='active'",
                (evidence_id,),
            ).fetchone()
            if row is None:
                raise NotFound()
            row["attachments"] = conn.execute(
                "SELECT id,part_id,safe_filename,media_type,sha256,byte_size,status,reason,"
                "scanner_status FROM attachment_receipts WHERE evidence_id=%s "
                "ORDER BY part_id LIMIT 64",
                (evidence_id,),
            ).fetchall()
            return row

    def _raw(self, principal: Principal, source: dict[str, Any]) -> bytes:
        if not 0 < source["raw_size"] <= MAX_BLOB_BYTES:
            raise BlobError()
        raw = self.store.load_raw(principal.context, source["account_id"], source["raw_sha256"])
        if (
            len(raw) != source["raw_size"]
            or hashlib.sha256(raw).hexdigest() != source["raw_sha256"]
        ):
            raise BlobError()
        return raw

    def _finish(self, principal: Principal, evidence_id: UUID, event: str) -> None:
        # Recheck live mapping/membership/account after filesystem reads and parsing.
        with self.store.transaction(principal.context) as conn:
            if not conn.execute(
                "SELECT 1 FROM message_versions v JOIN mail_accounts a "
                "ON a.tenant_id=v.tenant_id AND a.id=v.account_id "
                "WHERE v.id=%s AND a.status='active'",
                (evidence_id,),
            ).fetchone():
                raise NotFound()
            self.store.audit(conn, principal.context, event, "evidence", str(evidence_id))

    def read(self, principal: Principal, evidence_id: UUID) -> dict[str, Any]:
        source = self._source(principal, evidence_id)
        raw = self._raw(principal, source)
        small = len(raw) <= MAX_RAW_BYTES
        headers: list[dict[str, str]] = []
        headers_truncated = True
        snapshot = source["snapshot"]
        if small:
            mail = parse_small(raw)
            text = decoded_body(mail)
            headers, headers_truncated = header_view(mail)
        else:
            text = snapshot["text"]
        result = {
            "id": source["id"],
            "message_id": source["message_id"],
            "account_id": source["account_id"],
            "raw_sha256": source["raw_sha256"],
            "raw_size": source["raw_size"],
            "subject": snapshot["subject"],
            "sender": snapshot["sender"],
            "received_at": snapshot["received_at"],
            "body": text,
            "body_source": "original_mime" if small else "stored_projection",
            "body_complete": small or snapshot.get("truncated") is False,
            "headers": headers,
            "headers_truncated": headers_truncated,
            "attachments": [
                {
                    **part,
                    "download_available": small
                    and not part["media_type"].startswith(("message/", "multipart/")),
                }
                for part in source["attachments"]
            ],
            "untrusted_content": True,
            "mailbox_effects": False,
        }
        self._finish(principal, evidence_id, "message.read")
        return result

    def download(
        self,
        principal: Principal,
        evidence_id: UUID,
        receipt_id: UUID | None = None,
    ) -> tuple[bytes, str]:
        source = self._source(principal, evidence_id)
        receipt = None
        if receipt_id is not None:
            receipt = next((p for p in source["attachments"] if p["id"] == receipt_id), None)
            if receipt is None:
                raise NotFound()
            if source["raw_size"] > MAX_RAW_BYTES:
                raise Conflict("download the original for large MIME")
        raw = self._raw(principal, source)
        if receipt is None:
            data, name, event = raw, f"message-{evidence_id}.eml", "message.original_export"
        else:
            data = attachment_bytes(parse_small(raw), receipt)
            name, event = f"attachment-{receipt_id}.bin", "message.attachment_export"
        self._finish(principal, evidence_id, event)
        return data, name
