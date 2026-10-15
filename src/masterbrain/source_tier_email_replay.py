"""Worker-only point-in-time retained-MIME replay for one reviewed Email."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from email_brain.blobs import BlobError
from email_brain.domain.models import TenantContext
from email_brain.normalize import MAX_RAW_BYTES, PARSER_VERSION
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.datacore.email_text_derivation import prove_email_text_derivation
from masterbrain.datacore.persistence import EMAIL_NORMALIZER_VERSION

_REVIEW_ID = re.compile(r"^stier_[a-f0-9]{32}$")
_BASIS_SQL = (
    "SELECT r.id,r.evidence_id,r.document_id,r.source_version_id,"
    "r.source_sha256,r.document_sha256,r.source_quote,"
    "d.body,d.body_sha256,d.normalizer,"
    "e.source_version_id AS evidence_version_id,e.sha256 AS evidence_sha,"
    "e.storage AS evidence_storage,e.retained AS evidence_retained,"
    "v.sha256 AS version_sha,v.size_bytes,"
    "i.current_version_id,s.id AS source_id,s.kind AS source_kind,"
    "s.status AS source_status,b.account_id,b.legacy_version_id,"
    "mv.raw_sha256 AS legacy_sha,mv.parser_version,"
    "m.raw_sha256 AS current_sha,m.parser_version AS current_parser,"
    "m.deleted,m.quarantined,a.status AS account_status,ro.raw_size,"
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
    "JOIN brain_email_bridge_receipts b ON b.tenant_id=v.tenant_id "
    "AND b.version_id=v.id AND b.evidence_id=e.id AND b.document_id=d.id "
    "AND b.source_id=s.id AND b.normalizer=d.normalizer "
    "JOIN message_versions mv ON mv.tenant_id=b.tenant_id "
    "AND mv.id=b.legacy_version_id AND mv.account_id=b.account_id "
    "JOIN messages m ON m.tenant_id=mv.tenant_id AND m.id=mv.message_id "
    "AND m.account_id=mv.account_id "
    "JOIN mail_accounts a ON a.tenant_id=mv.tenant_id AND a.id=mv.account_id "
    "JOIN raw_objects ro ON ro.tenant_id=mv.tenant_id "
    "AND ro.account_id=mv.account_id AND ro.sha256=mv.raw_sha256 "
    "WHERE r.id=%s"
)


def _checked_basis(
    row: dict[str, Any] | None, ctx: TenantContext,
    expected_account_id: UUID | None,
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
        or row["evidence_storage"] != "inline"
        or row["evidence_retained"] is not True
        or row["source_version_id"] != row["evidence_version_id"]
        or row["source_version_id"] != row["current_version_id"]
        or row["source_sha256"] != row["evidence_sha"]
        or row["source_sha256"] != row["version_sha"]
        or row["source_sha256"] != row["legacy_sha"]
        or row["source_sha256"] != row["current_sha"]
        or row["document_sha256"] != row["body_sha256"]
        or row["normalizer"] != EMAIL_NORMALIZER_VERSION
        or row["parser_version"] != PARSER_VERSION
        or row["current_parser"] != PARSER_VERSION
        or type(row["size_bytes"]) is not int
        or not 0 < row["size_bytes"] <= MAX_RAW_BYTES
        or row["size_bytes"] != row["raw_size"]
        or row["source_quote"] not in row["body"]
        or hashlib.sha256(row["body"].encode("utf-8")).hexdigest()
        != row["document_sha256"]
    ):
        raise Conflict("source tier Email replay basis changed")
    return row


@dataclass(slots=True)
class SourceTierEmailReplayStore:
    store: Store

    def record_current_text_replay(
        self, ctx: TenantContext, review_id: str,
        *, expected_account_id: UUID | None = None,
        authorize: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Verify one current direct-parser Email and seal a digest-only receipt."""
        self.store.require(ctx, "brain.document.publish")
        self.store.require(ctx, "email.evidence.read")
        if ctx.identity is not None and ctx.identity.client_kind != "worker":
            raise AccessDenied("worker identity required")
        if type(review_id) is not str or _REVIEW_ID.fullmatch(review_id) is None:
            raise NotFound()
        if expected_account_id is not None and not isinstance(expected_account_id, UUID):
            raise ValueError("invalid_expected_account")
        with self.store.transaction(ctx) as conn:
            before = _checked_basis(
                conn.execute(_BASIS_SQL, (review_id,)).fetchone(), ctx, expected_account_id,
            )
        try:
            raw = self.store.load_raw(
                ctx, before["account_id"], before["source_sha256"],
            )
            proof = prove_email_text_derivation(
                raw,
                source_sha256=before["source_sha256"],
                source_size_bytes=before["size_bytes"],
                text=before["body"],
                text_sha256=before["document_sha256"],
                normalizer=before["normalizer"],
                parser_version=before["parser_version"],
            )
        except (BlobError, NotFound, ValueError, OSError, RuntimeError):
            raise Conflict("source tier Email retained bytes unavailable or changed") from None
        with self.store.transaction(ctx) as conn:
            after = _checked_basis(
                conn.execute(_BASIS_SQL + " FOR SHARE OF i,s,m", (review_id,)).fetchone(),
                ctx, expected_account_id,
            )
            if after != before:
                raise Conflict("source tier Email replay basis changed")
            if authorize is not None:
                authorize()
            conn.execute(
                "INSERT INTO knowledge_source_tier_email_replays(tenant_id,review_id,"
                "evidence_id,document_id,source_version_id,source_id,account_id,"
                "legacy_version_id,actor_id,source_sha256,source_size_bytes,"
                "text_sha256,normalizer,parser_version) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,review_id) DO NOTHING",
                (
                    ctx.tenant_id, review_id, after["evidence_id"], after["document_id"],
                    after["source_version_id"], after["source_id"], after["account_id"],
                    after["legacy_version_id"], ctx.actor_id, proof.source_sha256,
                    proof.source_size_bytes, proof.text_sha256, proof.normalizer,
                    after["parser_version"],
                ),
            )
            saved = conn.execute(
                "SELECT evidence_id,document_id,source_version_id,source_id,"
                "account_id,legacy_version_id,source_sha256,source_size_bytes,"
                "text_sha256,normalizer,parser_version "
                "FROM knowledge_source_tier_email_replays WHERE review_id=%s",
                (review_id,),
            ).fetchone()
            fields = (
                "evidence_id", "document_id", "source_version_id", "source_id",
                "account_id", "legacy_version_id", "source_sha256", "source_size_bytes",
                "text_sha256", "normalizer", "parser_version",
            )
            expected = (
                after["evidence_id"], after["document_id"], after["source_version_id"],
                after["source_id"], after["account_id"], after["legacy_version_id"],
                proof.source_sha256, proof.source_size_bytes, proof.text_sha256,
                proof.normalizer, after["parser_version"],
            )
            if saved is None or tuple(saved[field] for field in fields) != expected:
                raise Conflict("source tier Email replay receipt differs")
            self.store.audit(
                conn, ctx, "knowledge.source_tier_email_text_replayed", "stier", review_id,
            )
        return {
            "review_id": review_id,
            "worker_observed_text_replay": True,
            "source_effects": False,
            "financial_claim_approved": False,
        }
