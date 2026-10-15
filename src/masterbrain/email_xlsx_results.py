"""Private, synthetic-only worker for one approved retained Email XLSX."""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import psycopg

from email_brain.blobs import BlobError
from email_brain.domain.models import TenantContext
from email_brain.pdf_contract import MAX_MIME_BYTES
from email_brain.recovery_jobs import _account_lock, _owners
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.document_contract import (
    MAX_CELLS,
    MAX_SHEETS,
    MAX_TEXT_CHARS,
    SHEET_TYPE,
    DocumentUnavailable,
    source_for,
)
from masterbrain.datacore.document_processor import DockerDocumentProcessor
from masterbrain.datacore.email_xlsx_derivation import (
    EmailAttachmentXlsxUnavailable,
    _selected_xlsx,
)
from masterbrain.email_xlsx_approvals import _BASIS_SQL, POLICY

_APPROVAL_ID = re.compile(r"^xapp_[a-f0-9]{32}$")
_MATCH_FIELDS = (
    ("account_id", "account_id"),
    ("attachment_id", "attachment_id"),
    ("parent_version_id", "parent_version_id"),
    ("source_id", "source_id"),
    ("source_event_key", "source_event_key"),
    ("raw_sha256", "raw_sha256"),
    ("raw_size_bytes", "raw_size_bytes"),
    ("part_path", "part_path"),
    ("part_sha256", "part_sha256"),
    ("part_size_bytes", "part_size_bytes"),
)


def _current(
    conn: psycopg.Connection[dict[str, Any]], approval_id: str,
    ctx: TenantContext, processor_version: str,
) -> dict[str, Any]:
    approval = conn.execute(
        "SELECT *,expires_at>clock_timestamp() AS unexpired "
        "FROM brain_email_xlsx_extraction_approvals WHERE id=%s",
        (approval_id,),
    ).fetchone()
    if approval is None or (
        ctx.source_ids is not None and approval["source_id"] not in ctx.source_ids
    ):
        raise NotFound()
    if (
        approval["unexpired"] is not True
        or approval["policy_version"] != POLICY
        or approval["processor_version"] != processor_version
    ):
        raise Conflict("Email XLSX approval expired or processor changed")
    basis = conn.execute(
        _BASIS_SQL, (approval["account_id"], approval["attachment_id"]),
    ).fetchone()
    if basis is None or any(
        approval[approval_field] != basis[basis_field]
        for approval_field, basis_field in _MATCH_FIELDS
    ):
        raise Conflict("Email XLSX approval source changed")
    return approval


@dataclass(slots=True)
class EmailXlsxResults:
    store: Store
    processor: DockerDocumentProcessor

    def record(
        self, ctx: TenantContext, approval_id: str,
        *, authorize: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Recheck, isolate extraction, then seal only complete XLSX text."""
        self.store.require(ctx, "email.document.process")
        self.store.require(ctx, "email.evidence.read")
        if ctx.identity is not None and ctx.identity.client_kind != "worker":
            raise AccessDenied("worker identity required")
        if type(approval_id) is not str or _APPROVAL_ID.fullmatch(approval_id) is None:
            raise NotFound()
        if type(self.processor) is not DockerDocumentProcessor:
            raise ValueError("invalid XLSX processor")
        processor_version = self.processor.processor_version
        with self.store.transaction(ctx) as conn:
            identity = conn.execute(
                "SELECT account_id FROM brain_email_xlsx_extraction_approvals WHERE id=%s",
                (approval_id,),
            ).fetchone()
            if identity is None:
                raise NotFound()
            _account_lock(conn, ctx.tenant_id, identity["account_id"])
            before = _current(conn, approval_id, ctx, processor_version)
            if not _owners(
                conn, before["account_id"], before["actor_id"], ctx.actor_id,
            ):
                raise AccessDenied("Email XLSX owner authorization changed")
            if authorize is not None:
                authorize()
            prior = conn.execute(
                "SELECT text_sha256,sheet_count,cell_count "
                "FROM brain_email_xlsx_extraction_results WHERE approval_id=%s",
                (approval_id,),
            ).fetchone()
            if prior is not None:
                return {
                    "approval_id": approval_id,
                    "text_sha256": prior["text_sha256"],
                    "sheet_count": prior["sheet_count"],
                    "cell_count": prior["cell_count"],
                    "changed": False,
                    "document_published": False,
                    "mailbox_effects": False,
                }
        try:
            raw = self.store.load_raw(ctx, before["account_id"], before["raw_sha256"])
            if (
                type(raw) is not bytes
                or not 0 < len(raw) <= MAX_MIME_BYTES
                or len(raw) != before["raw_size_bytes"]
                or not hmac.compare_digest(
                    hashlib.sha256(raw).hexdigest(), before["raw_sha256"],
                )
            ):
                raise EmailAttachmentXlsxUnavailable()
            document = _selected_xlsx(raw, before["part_path"], before["part_sha256"])
            version_id = stable_id(
                "version", before["raw_sha256"], before["part_path"],
                before["part_sha256"],
            )
            expected = source_for(
                document, version_id, "attachment.xlsx", before["part_sha256"], SHEET_TYPE,
            )
            result = self.processor.extract(
                document, version_id=version_id, locator="attachment.xlsx",
                sha256=before["part_sha256"], media_type=SHEET_TYPE,
            )
            text = result.text
            sheet_count, cell_count = result.metadata.sheet_count, result.metadata.cell_count
            if (
                result.source != expected
                or result.status != "extracted"
                or result.reason != "bounded_xlsx_v1"
                or result.scanner_status != "unscanned"
                or type(text) is not str
                or not text
                or len(text) > MAX_TEXT_CHARS
                or len(text.encode("utf-8", errors="strict")) > 1048576
                or type(sheet_count) is not int
                or not 0 < sheet_count <= MAX_SHEETS
                or type(cell_count) is not int
                or not 0 < cell_count <= MAX_CELLS
            ):
                raise DocumentUnavailable()
            text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        except (
            BlobError, EmailAttachmentXlsxUnavailable, DocumentUnavailable,
            OSError, RuntimeError, UnicodeError, ValueError,
        ):
            raise Conflict("Email XLSX extraction unavailable or changed") from None
        try:
            with self.store.transaction(ctx) as conn:
                _account_lock(conn, ctx.tenant_id, before["account_id"])
                if not _owners(
                    conn, before["account_id"], before["actor_id"], ctx.actor_id,
                ):
                    raise AccessDenied("Email XLSX owner authorization changed")
                after = _current(conn, approval_id, ctx, processor_version)
                if after != before:
                    raise Conflict("Email XLSX approval changed during extraction")
                if authorize is not None:
                    authorize()
                conn.execute(
                    "INSERT INTO brain_email_xlsx_extraction_results("
                    "tenant_id,approval_id,worker_actor_id,account_id,parent_version_id,"
                    "attachment_id,raw_sha256,part_path,part_sha256,processor_version,"
                    "text_sha256,extracted_text,sheet_count,cell_count) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id, approval_id, ctx.actor_id, before["account_id"],
                        before["parent_version_id"], before["attachment_id"],
                        before["raw_sha256"], before["part_path"],
                        before["part_sha256"], processor_version, text_sha256,
                        text, sheet_count, cell_count,
                    ),
                )
                self.store.audit(
                    conn, ctx, "brain.email_xlsx_extraction_recorded",
                    "xlsx_approval", approval_id,
                )
        except psycopg.errors.UniqueViolation:
            raise Conflict("Email XLSX extraction already recorded") from None
        return {
            "approval_id": approval_id,
            "text_sha256": text_sha256,
            "sheet_count": sheet_count,
            "cell_count": cell_count,
            "changed": True,
            "document_published": False,
            "mailbox_effects": False,
        }
