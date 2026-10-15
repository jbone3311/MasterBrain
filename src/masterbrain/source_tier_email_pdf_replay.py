"""Worker-only current reviewed Email attachment PDF text-layer replay."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from email_brain.blobs import BlobError
from email_brain.domain.models import TenantContext
from email_brain.pdf_contract import MAX_MIME_BYTES, MAX_PDF_BYTES
from email_brain.pdf_processor import DockerPdfProcessor
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.datacore.email_pdf_derivation import (
    EmailAttachmentPdfUnavailable,
    prove_email_attachment_pdf_derivation,
)
from masterbrain.datacore.persistence import EMAIL_DOCUMENT_NORMALIZER_PREFIX

_REVIEW_ID = re.compile(r"^stier_[a-f0-9]{32}$")
_NORMALIZER = re.compile(
    r"^email-pdf-v1:sandbox-pdf-v1-[a-f0-9]{64}:synthetic-unscanned-pdf-v1$"
)
_BASIS_SQL = (
    "SELECT r.id,r.evidence_id,r.document_id,r.source_version_id,"
    "r.source_sha256,r.document_sha256,r.source_quote,"
    "d.body,d.body_sha256,d.normalizer,"
    "e.source_version_id AS evidence_version_id,e.sha256 AS evidence_sha,"
    "e.storage AS evidence_storage,e.retained AS evidence_retained,"
    "v.sha256 AS version_sha,v.size_bytes AS part_version_size,v.media_type,"
    "i.current_version_id,s.id AS source_id,s.kind AS source_kind,"
    "s.status AS source_status,ab.account_id,ab.legacy_parent_version_id,"
    "ab.legacy_attachment_id,ab.parent_evidence_id,"
    "bp.part_path,bp.sha256 AS part_sha,bp.size_bytes AS part_size,"
    "bp.media_type AS part_media_type,bp.status AS part_status,"
    "db.legacy_extraction_id,db.processor_version,db.policy_version,"
    "db.extraction_status,db.extraction_revision,db.result_sha256,"
    "ar.part_id AS legacy_part_path,ar.sha256 AS legacy_part_sha,"
    "ar.byte_size AS legacy_part_size,ar.media_type AS legacy_part_media_type,"
    "ar.status AS legacy_part_status,"
    "de.extracted_text,de.status AS extraction_result_status,"
    "de.reason AS extraction_reason,de.revision AS extraction_result_revision,"
    "de.processor_version AS extraction_processor_version,"
    "de.policy_version AS extraction_policy_version,"
    "jsonb_array_length(de.result->'pages') AS extraction_page_count,"
    "dj.status AS job_status,dj.outcome AS job_outcome,"
    "mv.raw_sha256 AS parent_raw_sha,mv.parser_version AS parent_parser,"
    "m.raw_sha256 AS current_raw_sha,m.parser_version AS current_parser,"
    "m.deleted,m.quarantined,a.status AS account_status,ro.raw_size,"
    "pi.current_version_id AS parent_current_version_id,"
    "eb.version_id AS parent_bridge_version_id,"
    "public.brain_email_evidence_is_excluded(e.tenant_id,e.id) AS excluded "
    "FROM knowledge_source_tier_reviews r "
    "JOIN brain_normalized_documents d ON d.tenant_id=r.tenant_id "
    "AND d.id=r.document_id "
    "JOIN brain_evidence e ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id "
    "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
    "AND v.id=e.source_version_id "
    "JOIN brain_source_items i ON i.tenant_id=v.tenant_id "
    "AND i.id=v.item_id AND i.source_id=v.source_id "
    "JOIN brain_sources s ON s.tenant_id=i.tenant_id AND s.id=i.source_id "
    "JOIN brain_email_attachment_bridge_receipts ab ON ab.tenant_id=e.tenant_id "
    "AND ab.evidence_id=e.id AND ab.version_id=v.id AND ab.item_id=i.id "
    "AND ab.source_id=s.id "
    "JOIN brain_parts bp ON bp.tenant_id=ab.tenant_id AND bp.id=ab.part_id "
    "AND bp.evidence_id=e.id AND bp.parent_evidence_id=ab.parent_evidence_id "
    "JOIN brain_email_document_bridge_receipts db ON db.tenant_id=d.tenant_id "
    "AND db.document_id=d.id AND db.evidence_id=e.id AND db.version_id=v.id "
    "AND db.source_id=s.id AND db.item_id=i.id "
    "AND db.legacy_attachment_id=ab.legacy_attachment_id "
    "JOIN attachment_receipts ar ON ar.tenant_id=ab.tenant_id "
    "AND ar.id=ab.legacy_attachment_id AND ar.account_id=ab.account_id "
    "AND ar.evidence_id=ab.legacy_parent_version_id "
    "JOIN document_extractions de ON de.tenant_id=db.tenant_id "
    "AND de.id=db.legacy_extraction_id AND de.receipt_id=ar.id "
    "AND de.account_id=ar.account_id "
    "JOIN document_jobs dj ON dj.tenant_id=db.tenant_id "
    "AND dj.id=db.legacy_approval_job_id AND dj.extraction_id=de.id "
    "AND dj.receipt_id=ar.id AND dj.processor_version=de.processor_version "
    "AND dj.policy_version=de.policy_version "
    "JOIN message_versions mv ON mv.tenant_id=ar.tenant_id "
    "AND mv.id=ar.evidence_id AND mv.account_id=ar.account_id "
    "JOIN messages m ON m.tenant_id=mv.tenant_id AND m.id=mv.message_id "
    "AND m.account_id=mv.account_id "
    "JOIN mail_accounts a ON a.tenant_id=mv.tenant_id AND a.id=mv.account_id "
    "JOIN raw_objects ro ON ro.tenant_id=mv.tenant_id "
    "AND ro.account_id=mv.account_id AND ro.sha256=mv.raw_sha256 "
    "JOIN brain_email_bridge_receipts eb ON eb.tenant_id=mv.tenant_id "
    "AND eb.legacy_version_id=mv.id AND eb.account_id=mv.account_id "
    "AND eb.evidence_id=ab.parent_evidence_id "
    "JOIN brain_source_items pi ON pi.tenant_id=eb.tenant_id "
    "AND pi.id=eb.item_id AND pi.current_version_id=eb.version_id "
    "WHERE r.id=%s"
)


def _checked_basis(
    row: dict[str, Any] | None, ctx: TenantContext, expected_account_id: UUID | None,
    processor_version: str,
) -> dict[str, Any]:
    if row is None or (ctx.source_ids is not None and row["source_id"] not in ctx.source_ids):
        raise NotFound()
    if expected_account_id is not None and row["account_id"] != expected_account_id:
        raise NotFound()
    if (
        row["source_kind"] != "email"
        or row["source_status"] != "active"
        or row["account_status"] != "active"
        or row["deleted"] is not False
        or row["quarantined"] is not False
        or row["excluded"] is not False
        or row["evidence_storage"] != "source_bound"
        or row["evidence_retained"] is not False
        or row["source_version_id"] != row["evidence_version_id"]
        or row["source_version_id"] != row["current_version_id"]
        or row["source_sha256"] != row["evidence_sha"]
        or row["source_sha256"] != row["version_sha"]
        or row["source_sha256"] != row["part_sha"]
        or row["source_sha256"] != row["legacy_part_sha"]
        or row["document_sha256"] != row["body_sha256"]
        or row["normalizer"] != (
            f"{EMAIL_DOCUMENT_NORMALIZER_PREFIX}:{processor_version}:"
            f"{row['policy_version']}"
        )
        or _NORMALIZER.fullmatch(row["normalizer"]) is None
        or row["processor_version"] != processor_version
        or row["processor_version"] != row["extraction_processor_version"]
        or row["policy_version"] != row["extraction_policy_version"]
        or row["extraction_status"] != "extracted"
        or row["extraction_result_status"] != "extracted"
        or row["extraction_reason"] != "bounded_pdf_v1"
        or row["extraction_revision"] != row["extraction_result_revision"]
        or row["job_status"] != "completed"
        or row["job_outcome"] != "result_saved"
        or row["media_type"] != "application/pdf"
        or row["part_media_type"] != "application/pdf"
        or row["legacy_part_media_type"] != "application/pdf"
        or row["part_status"] != "deferred"
        or row["legacy_part_status"] != "deferred"
        or row["part_path"] != row["legacy_part_path"]
        or row["part_size"] != row["legacy_part_size"]
        or row["part_size"] != row["part_version_size"]
        or type(row["part_size"]) is not int
        or not 0 < row["part_size"] <= MAX_PDF_BYTES
        or row["legacy_parent_version_id"] is None
        or row["parent_current_version_id"] != row["parent_bridge_version_id"]
        or row["parent_raw_sha"] != row["current_raw_sha"]
        or row["parent_parser"] != row["current_parser"]
        or type(row["raw_size"]) is not int
        or not 0 < row["raw_size"] <= MAX_MIME_BYTES
        or row["extracted_text"] != row["body"]
        or row["source_quote"] not in row["body"]
        or hashlib.sha256(row["body"].encode("utf-8")).hexdigest()
        != row["document_sha256"]
    ):
        raise Conflict("source tier Email PDF replay basis changed")
    return row


@dataclass(slots=True)
class SourceTierEmailPdfReplayStore:
    store: Store
    processor: DockerPdfProcessor

    def record_current_pdf_replay(
        self, ctx: TenantContext, review_id: str, *,
        expected_account_id: UUID | None = None,
        authorize: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Re-read one retained MIME/part and seal a digest-only review receipt."""
        self.store.require(ctx, "brain.document.publish")
        self.store.require(ctx, "email.evidence.read")
        if ctx.identity is not None and ctx.identity.client_kind != "worker":
            raise AccessDenied("worker identity required")
        if type(review_id) is not str or _REVIEW_ID.fullmatch(review_id) is None:
            raise NotFound()
        if expected_account_id is not None and not isinstance(expected_account_id, UUID):
            raise ValueError("invalid_expected_account")
        if type(self.processor) is not DockerPdfProcessor:
            raise ValueError("invalid_pdf_processor")
        processor_version = self.processor.processor_version
        with self.store.transaction(ctx) as conn:
            before = _checked_basis(
                conn.execute(_BASIS_SQL, (review_id,)).fetchone(), ctx,
                expected_account_id, processor_version,
            )
        try:
            raw = self.store.load_raw(
                ctx, before["account_id"], before["parent_raw_sha"],
            )
            proof = prove_email_attachment_pdf_derivation(
                raw,
                raw_sha256=before["parent_raw_sha"],
                raw_size_bytes=before["raw_size"],
                part_path=before["part_path"],
                part_sha256=before["part_sha"],
                text=before["body"],
                text_sha256=before["document_sha256"],
                normalizer=before["normalizer"],
                processor=self.processor,
            )
        except (BlobError, EmailAttachmentPdfUnavailable, NotFound, OSError, RuntimeError):
            raise Conflict("source tier Email PDF retained bytes unavailable or changed") from None
        with self.store.transaction(ctx) as conn:
            after = _checked_basis(
                conn.execute(
                    _BASIS_SQL + " FOR SHARE OF i,s,pi,m", (review_id,),
                ).fetchone(), ctx, expected_account_id, processor_version,
            )
            if after != before:
                raise Conflict("source tier Email PDF replay basis changed")
            if authorize is not None:
                authorize()
            conn.execute(
                "INSERT INTO knowledge_source_tier_email_pdf_replays(tenant_id,review_id,"
                "evidence_id,document_id,source_version_id,source_id,account_id,"
                "parent_version_id,legacy_attachment_id,legacy_extraction_id,actor_id,"
                "raw_sha256,raw_size_bytes,part_path,part_sha256,part_size_bytes,"
                "text_sha256,normalizer,result_sha256,page_count) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,review_id) DO NOTHING",
                (
                    ctx.tenant_id, review_id, after["evidence_id"], after["document_id"],
                    after["source_version_id"], after["source_id"], after["account_id"],
                    after["legacy_parent_version_id"], after["legacy_attachment_id"],
                    after["legacy_extraction_id"], ctx.actor_id,
                    proof.raw_sha256, proof.raw_size_bytes, proof.part_path,
                    proof.part_sha256, after["part_size"], proof.text_sha256,
                    proof.normalizer, after["result_sha256"], proof.page_count,
                ),
            )
            saved = conn.execute(
                "SELECT evidence_id,document_id,source_version_id,source_id,account_id,"
                "parent_version_id,legacy_attachment_id,legacy_extraction_id,raw_sha256,"
                "raw_size_bytes,part_path,part_sha256,part_size_bytes,text_sha256,"
                "normalizer,result_sha256,page_count "
                "FROM knowledge_source_tier_email_pdf_replays WHERE review_id=%s",
                (review_id,),
            ).fetchone()
            fields = (
                "evidence_id", "document_id", "source_version_id", "source_id",
                "account_id", "parent_version_id", "legacy_attachment_id",
                "legacy_extraction_id", "raw_sha256", "raw_size_bytes", "part_path",
                "part_sha256", "part_size_bytes", "text_sha256", "normalizer",
                "result_sha256", "page_count",
            )
            expected = (
                after["evidence_id"], after["document_id"], after["source_version_id"],
                after["source_id"], after["account_id"], after["legacy_parent_version_id"],
                after["legacy_attachment_id"], after["legacy_extraction_id"],
                proof.raw_sha256, proof.raw_size_bytes, proof.part_path,
                proof.part_sha256, after["part_size"], proof.text_sha256,
                proof.normalizer, after["result_sha256"], proof.page_count,
            )
            if saved is None or tuple(saved[field] for field in fields) != expected:
                raise Conflict("source tier Email PDF replay receipt differs")
            self.store.audit(
                conn, ctx, "knowledge.source_tier_email_pdf_replayed", "stier", review_id,
            )
        return {
            "review_id": review_id,
            "worker_observed_pdf_text_replay": True,
            "source_effects": False,
            "financial_claim_approved": False,
        }
