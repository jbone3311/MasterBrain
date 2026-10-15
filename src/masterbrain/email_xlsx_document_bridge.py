"""Human review and worker-only publication of a synthetic Email XLSX result."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import psycopg

from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.recovery_jobs import _account_lock, _owners
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.document_contract import MAX_CELLS, MAX_SHEETS, MAX_TEXT_CHARS
from masterbrain.datacore.persistence import (
    CHUNK_CHARACTERS,
    MAX_NORMALIZED_BYTES,
    _canonical_digest,
    deterministic_chunks,
)
from masterbrain.email_xlsx_approvals import _VERSION
from masterbrain.email_xlsx_results import _APPROVAL_ID, _current

BRIDGE_CODE_REVISION = "email-xlsx-document-bridge-v2"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_REVIEW_ID = re.compile(r"^xrev_[a-f0-9]{32}$")


def _public(row: dict[str, Any], *, changed: bool) -> dict[str, Any]:
    return {
        **{field: row[field] for field in (
            "source_id", "item_id", "version_id", "evidence_id",
            "document_id", "chunk_count", "approval_id",
        )},
        "changed": changed,
        "mailbox_effects": False,
    }


@dataclass(slots=True)
class EmailXlsxDocumentBridge:
    store: Store

    @staticmethod
    def _basis(
        conn: psycopg.Connection[dict[str, Any]], ctx: TenantContext,
        approval_id: str,
    ) -> dict[str, Any]:
        identity = conn.execute(
            "SELECT account_id,processor_version FROM "
            "brain_email_xlsx_extraction_approvals WHERE id=%s", (approval_id,),
        ).fetchone()
        if identity is None or _VERSION.fullmatch(identity["processor_version"]) is None:
            raise NotFound()
        _account_lock(conn, ctx.tenant_id, identity["account_id"])
        approval = _current(conn, approval_id, ctx, identity["processor_version"])
        if not _owners(conn, approval["account_id"], approval["actor_id"], ctx.actor_id):
            raise AccessDenied("Email XLSX owner authorization changed")
        return approval

    def inspect(
        self, principal: Principal, approval_id: str,
        *, offset: int = 0, max_chars: int = 4000,
    ) -> dict[str, Any]:
        """Read a bounded page of untrusted text before human authorization."""
        if principal.client_kind != "human":
            raise AccessDenied("human document review required")
        ctx = principal.context
        self.store.require(ctx, "email.review")
        self.store.require(ctx, "email.evidence.read")
        if (
            type(approval_id) is not str or _APPROVAL_ID.fullmatch(approval_id) is None
            or type(offset) is not int or not 0 <= offset <= MAX_TEXT_CHARS
            or type(max_chars) is not int or not 1 <= max_chars <= 16000
        ):
            raise ValueError("invalid Email XLSX inspection request")
        with self.store.transaction(ctx) as conn:
            self._basis(conn, ctx, approval_id)
            result = conn.execute(
                "SELECT text_sha256,sheet_count,cell_count,extracted_text FROM "
                "brain_email_xlsx_extraction_results WHERE approval_id=%s",
                (approval_id,),
            ).fetchone()
            if result is None:
                raise Conflict("approved Email XLSX extraction is not complete")
            text = result["extracted_text"]
            next_offset = offset + max_chars if offset + max_chars < len(text) else None
            self.store.audit(
                conn, ctx, "brain.email_xlsx_result_inspected", "xlsx_approval", approval_id,
            )
            return {
                "approval_id": approval_id, "text_sha256": result["text_sha256"],
                "sheet_count": result["sheet_count"], "cell_count": result["cell_count"],
                "text": text[offset:offset + max_chars], "offset": offset,
                "next_offset": next_offset, "total_chars": len(text),
                "untrusted_content": True, "mailbox_effects": False,
            }

    def review(
        self, principal: Principal, approval_id: str, idempotency_key: UUID,
        *, expected_text_sha256: str, expected_sheet_count: int,
        expected_cell_count: int,
    ) -> dict[str, Any]:
        """Seal a one-hour human intent; do not publish the document."""
        if principal.client_kind != "human":
            raise AccessDenied("human document review required")
        ctx = principal.context
        self.store.require(ctx, "email.review")
        self.store.require(ctx, "email.evidence.read")
        if (
            type(approval_id) is not str or _APPROVAL_ID.fullmatch(approval_id) is None
            or not isinstance(idempotency_key, UUID)
            or type(expected_text_sha256) is not str
            or _SHA256.fullmatch(expected_text_sha256) is None
            or type(expected_sheet_count) is not int
            or not 1 <= expected_sheet_count <= MAX_SHEETS
            or type(expected_cell_count) is not int
            or not 1 <= expected_cell_count <= MAX_CELLS
        ):
            raise ValueError("invalid Email XLSX review request")
        request_hash = _canonical_digest({
            "approval_id": approval_id, "code_revision": BRIDGE_CODE_REVISION,
            "contract": "email-xlsx-publication-review-v1",
            "expected_text_sha256": expected_text_sha256,
            "expected_sheet_count": expected_sheet_count,
            "expected_cell_count": expected_cell_count,
        })
        review_id = stable_id(
            "xrev", str(ctx.tenant_id), str(ctx.actor_id), str(idempotency_key),
        )
        try:
            with self.store.transaction(ctx) as conn:
                approval = self._basis(conn, ctx, approval_id)
                result = conn.execute(
                    "SELECT text_sha256,sheet_count,cell_count FROM "
                    "brain_email_xlsx_extraction_results WHERE approval_id=%s",
                    (approval_id,),
                ).fetchone()
                if result is None:
                    raise Conflict("approved Email XLSX extraction is not complete")
                if (
                    result["text_sha256"] != expected_text_sha256
                    or result["sheet_count"] != expected_sheet_count
                    or result["cell_count"] != expected_cell_count
                ):
                    raise Conflict("Email XLSX reviewed result identity changed")
                prior = conn.execute(
                    "SELECT id,request_hash FROM brain_email_xlsx_publication_reviews "
                    "WHERE actor_id=%s AND idempotency_key=%s",
                    (ctx.actor_id, idempotency_key),
                ).fetchone()
                if prior is None:
                    prior = conn.execute(
                        "SELECT id,request_hash FROM brain_email_xlsx_publication_reviews "
                        "WHERE approval_id=%s", (approval_id,),
                    ).fetchone()
                if prior is not None:
                    if prior["request_hash"] != request_hash:
                        raise Conflict("Email XLSX result already reviewed differently")
                    return {
                        "review_id": prior["id"], "approval_id": approval_id,
                        **result, "changed": False, "document_published": False,
                    }
                conn.execute(
                    "INSERT INTO brain_email_xlsx_publication_reviews("
                    "tenant_id,id,actor_id,idempotency_key,approval_id,account_id,"
                    "text_sha256,sheet_count,cell_count,code_revision,request_hash) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id, review_id, ctx.actor_id, idempotency_key,
                        approval_id, approval["account_id"], expected_text_sha256,
                        expected_sheet_count, expected_cell_count, BRIDGE_CODE_REVISION,
                        request_hash,
                    ),
                )
                self.store.audit(
                    conn, ctx, "brain.email_xlsx_publication_reviewed",
                    "xlsx_approval", approval_id,
                )
                return {
                    "review_id": review_id, "approval_id": approval_id,
                    **result, "changed": True, "document_published": False,
                }
        except psycopg.errors.UniqueViolation:
            raise Conflict("Email XLSX publication review already exists") from None

    def publish(
        self, ctx: TenantContext, review_id: str, idempotency_key: UUID,
        *, expected_account_id: UUID | None = None,
        authorize: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Worker publishes only the exact unexpired human-reviewed result."""
        for scope in ("brain.source.ingest", "brain.document.publish", "email.evidence.read"):
            self.store.require(ctx, scope)
        if ctx.identity is not None and ctx.identity.client_kind != "worker":
            raise AccessDenied("worker identity required")
        if (
            type(review_id) is not str or _REVIEW_ID.fullmatch(review_id) is None
            or not isinstance(idempotency_key, UUID)
        ):
            raise ValueError("invalid Email XLSX publication request")
        try:
            with self.store.transaction(ctx) as conn:
                review = conn.execute(
                    "SELECT * FROM brain_email_xlsx_publication_reviews WHERE id=%s",
                    (review_id,),
                ).fetchone()
                if review is None:
                    raise NotFound()
                if review["code_revision"] != BRIDGE_CODE_REVISION:
                    raise Conflict("Email XLSX review has a different bridge revision")
                if expected_account_id is not None and review["account_id"] != expected_account_id:
                    raise AccessDenied("Email XLSX review belongs to another account")
                approval = self._basis(conn, ctx, review["approval_id"])
                clock = conn.execute("SELECT clock_timestamp() AS now").fetchone()
                assert clock is not None
                if review["expires_at"] <= clock["now"]:
                    raise Conflict("Email XLSX publication review expired")
                if (
                    review["account_id"] != approval["account_id"]
                    or not _owners(
                        conn, approval["account_id"], review["actor_id"], ctx.actor_id,
                    )
                ):
                    raise AccessDenied("Email XLSX reviewer authorization changed")
                result = conn.execute(
                    "SELECT * FROM brain_email_xlsx_extraction_results "
                    "WHERE approval_id=%s", (review["approval_id"],),
                ).fetchone()
                if result is None or any(
                    result[field] != review[field]
                    for field in ("text_sha256", "sheet_count", "cell_count")
                ):
                    raise Conflict("Email XLSX reviewed result identity changed")
                if authorize is not None:
                    authorize()
                request_hash = _canonical_digest({
                    "review_id": review_id, "code_revision": review["code_revision"],
                    "contract": "email-xlsx-document-bridge-v2",
                })
                receipt = conn.execute(
                    "SELECT source_id,item_id,version_id,evidence_id,document_id,"
                    "chunk_count,request_hash,approval_id,review_id FROM "
                    "brain_email_xlsx_document_bridge_receipts "
                    "WHERE actor_id=%s AND idempotency_key=%s",
                    (ctx.actor_id, idempotency_key),
                ).fetchone()
                if receipt is not None:
                    if receipt["request_hash"] != request_hash:
                        raise Conflict("Email XLSX bridge idempotency key reused")
                    return _public(receipt, changed=False)
                prior = conn.execute(
                    "SELECT source_id,item_id,version_id,evidence_id,document_id,"
                    "chunk_count,request_hash,approval_id,review_id FROM "
                    "brain_email_xlsx_document_bridge_receipts WHERE approval_id=%s",
                    (review["approval_id"],),
                ).fetchone()
                if prior is not None:
                    if prior["review_id"] != review_id:
                        raise Conflict("Email XLSX result was published under another review")
                    return _public(prior, changed=False)
                occurrence = conn.execute(
                    "SELECT ab.source_id,ab.item_id,ab.version_id,ab.evidence_id "
                    "FROM brain_email_attachment_bridge_receipts ab "
                    "WHERE ab.account_id=%s AND ab.legacy_attachment_id=%s "
                    "AND ab.legacy_parent_version_id=%s AND ab.source_id=%s",
                    (
                        approval["account_id"], approval["attachment_id"],
                        approval["parent_version_id"], approval["source_id"],
                    ),
                ).fetchone()
                if occurrence is None:
                    raise Conflict("Email XLSX attachment occurrence changed")
                text = result["extracted_text"]
                if (
                    type(text) is not str or not text or "\x00" in text
                    or len(text.encode("utf-8")) > MAX_NORMALIZED_BYTES
                    or hashlib.sha256(text.encode("utf-8")).hexdigest()
                    != result["text_sha256"]
                ):
                    raise Conflict("Email XLSX result fails shared text contract")
                normalizer = (
                    f"email-xlsx-v1:{result['processor_version']}:"
                    f"{approval['policy_version']}"
                )
                if len(normalizer) > 200:
                    raise Conflict("Email XLSX normalizer is outside shared contract")
                document_id = stable_id(
                    "document", occurrence["version_id"], normalizer,
                    result["text_sha256"],
                )
                if conn.execute(
                    "SELECT 1 FROM brain_normalized_documents WHERE id=%s",
                    (document_id,),
                ).fetchone():
                    raise Conflict("Email XLSX derivative already exists")
                chunks = list(deterministic_chunks(text))
                if not 1 <= len(chunks) <= 512:
                    raise Conflict("Email XLSX chunk count is outside shared contract")
                conn.execute(
                    "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,"
                    "normalizer,body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id, document_id, occurrence["evidence_id"],
                        normalizer, result["text_sha256"], text,
                    ),
                )
                for ordinal, (start, end, chunk) in enumerate(chunks):
                    chunk_sha = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
                    conn.execute(
                        "INSERT INTO brain_chunks(tenant_id,id,document_id,ordinal,"
                        "start_offset,end_offset,text,sha256) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            ctx.tenant_id,
                            stable_id("chunk", document_id, str(ordinal), chunk_sha),
                            document_id, ordinal, start, end, chunk, chunk_sha,
                        ),
                    )
                configuration_sha256 = _canonical_digest({
                    "approval_id": review["approval_id"], "review_id": review_id,
                    "chunk_characters": CHUNK_CHARACTERS,
                    "processor_version": result["processor_version"],
                    "policy_version": approval["policy_version"],
                    "text_sha256": result["text_sha256"],
                })
                provenance_id = stable_id(
                    "provenance", document_id, review["code_revision"],
                    configuration_sha256,
                )
                conn.execute(
                    "INSERT INTO brain_provenance(tenant_id,id,output_id,transform,"
                    "transform_version,code_revision,configuration_sha256,created_at) "
                    "VALUES (%s,%s,%s,'bridge_email_xlsx_result',%s,%s,%s,clock_timestamp())",
                    (
                        ctx.tenant_id, provenance_id, document_id, normalizer,
                        review["code_revision"], configuration_sha256,
                    ),
                )
                conn.execute(
                    "INSERT INTO brain_provenance_inputs(tenant_id,provenance_id,"
                    "input_id,ordinal) VALUES (%s,%s,%s,0)",
                    (ctx.tenant_id, provenance_id, occurrence["evidence_id"]),
                )
                conn.execute(
                    "INSERT INTO brain_change_events(tenant_id,id,source_id,item_id,"
                    "version_id,kind) VALUES (%s,%s,%s,%s,%s,'document_published')",
                    (
                        ctx.tenant_id,
                        stable_id("change", "document_published", document_id),
                        occurrence["source_id"], occurrence["item_id"],
                        occurrence["version_id"],
                    ),
                )
                conn.execute(
                    "INSERT INTO brain_email_xlsx_document_bridge_receipts("
                    "tenant_id,actor_id,idempotency_key,approval_id,account_id,"
                    "attachment_id,source_id,item_id,version_id,evidence_id,"
                    "document_id,normalizer,text_sha256,chunk_count,code_revision,"
                    "request_hash,review_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id, ctx.actor_id, idempotency_key,
                        review["approval_id"], approval["account_id"],
                        approval["attachment_id"], occurrence["source_id"],
                        occurrence["item_id"], occurrence["version_id"],
                        occurrence["evidence_id"], document_id, normalizer,
                        result["text_sha256"], len(chunks), review["code_revision"],
                        request_hash, review_id,
                    ),
                )
                self.store.audit(
                    conn, ctx, "brain.email_xlsx_document_published",
                    "xlsx_review", review_id,
                )
                return _public({
                    **occurrence, "approval_id": review["approval_id"],
                    "document_id": document_id, "chunk_count": len(chunks),
                }, changed=True)
        except psycopg.errors.UniqueViolation:
            raise Conflict("Email XLSX derivative already published") from None
