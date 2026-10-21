"""Current-source, human-reviewed document authority; not byte verification."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from uuid import UUID

from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.datacore.contracts import stable_id
from masterbrain.knowledge_schema import SourceTierReviewWrite

_EVIDENCE_ID = re.compile(r"^evidence_[a-f0-9]{32}$")
_REVIEW_ID = re.compile(r"^stier_[a-f0-9]{32}$")
_PAGE = 25


class SourceTierReviews:
    def __init__(self, store: Store) -> None:
        self.store = store

    def publish(
        self, ctx: TenantContext, evidence_id: str, body: SourceTierReviewWrite,
        idempotency_key: UUID,
    ) -> dict[str, Any]:
        self.store.require(ctx, "knowledge.review")
        self.store.require(ctx, "brain.content.read")
        if ctx.identity is not None and ctx.identity.client_kind != "human":
            raise AccessDenied("human identity required")
        if not _EVIDENCE_ID.fullmatch(evidence_id):
            raise NotFound()
        if not isinstance(body, SourceTierReviewWrite) or body.evidence_id != evidence_id:
            raise ValueError("source tier review subject mismatch")
        if not isinstance(idempotency_key, UUID):
            raise ValueError("UUID idempotency key required")
        payload = body.model_dump(mode="json")
        request_sha = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        review_id = stable_id(
            "stier", str(ctx.tenant_id), str(ctx.actor_id), str(idempotency_key),
        )
        allowed = sorted(ctx.source_ids) if ctx.source_ids is not None else None
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:stier:{ctx.actor_id}:{idempotency_key}",),
            )
            basis = conn.execute(
                "SELECT 1 FROM brain_normalized_documents d "
                "JOIN brain_evidence e ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id "
                "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
                "AND v.id=e.source_version_id "
                "JOIN brain_source_items i ON i.tenant_id=v.tenant_id "
                "AND i.id=v.item_id AND i.source_id=v.source_id "
                "JOIN brain_sources s ON s.tenant_id=i.tenant_id AND s.id=i.source_id "
                "WHERE e.id=%s AND d.id=%s AND d.body_sha256=%s "
                "AND e.source_version_id=%s AND e.sha256=%s AND v.sha256=%s "
                "AND i.current_version_id=v.id AND s.status='active' "
                "AND NOT public.brain_email_evidence_is_excluded(e.tenant_id,e.id) "
                "AND (%s::text[] IS NULL OR s.id=ANY(%s::text[])) "
                "AND strpos(d.body,%s)>0 FOR SHARE OF i,s",
                (evidence_id, body.document_id, body.document_sha256,
                 body.source_version_id, body.source_sha256, body.source_sha256,
                 allowed, allowed, body.source_quote),
            ).fetchone()
            if basis is None:
                raise NotFound()
            prior = conn.execute(
                "SELECT id,request_sha256 FROM knowledge_source_tier_reviews "
                "WHERE reviewer_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if prior["request_sha256"] != request_sha:
                    raise Conflict("source tier review idempotency key reused")
                return {"object_id": prior["id"], "changed": False,
                        "review_kind": "human_metadata_classification"}
            conn.execute(
                "INSERT INTO knowledge_source_tier_reviews(tenant_id,id,evidence_id,"
                "source_version_id,source_sha256,document_id,document_sha256,"
                "source_tier,authority_kind,source_quote,reviewer_id,idempotency_key,"
                "request_sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, review_id, evidence_id, body.source_version_id,
                 body.source_sha256, body.document_id, body.document_sha256,
                 body.source_tier, body.authority_kind, body.source_quote,
                 ctx.actor_id, idempotency_key, request_sha),
            )
            self.store.audit(
                conn, ctx, "knowledge.source_tier_reviewed", "stier", review_id,
            )
        return {"object_id": review_id, "changed": True,
                "review_kind": "human_metadata_classification"}

    def current_for_evidence(
        self, ctx: TenantContext, evidence_id: str, *, after: str | None = None,
    ) -> dict[str, Any]:
        """Page current reviews newest first; tier counts cover every page.

        Reviews are append-only and cannot be withdrawn, so a reader must be able
        to reach older ones and see disagreement without paging through them.
        """
        self.store.require(ctx, "knowledge.search")
        self.store.require(ctx, "brain.content.read")
        if not _EVIDENCE_ID.fullmatch(evidence_id) or (
            after is not None and (not isinstance(after, str) or not _REVIEW_ID.fullmatch(after))
        ):
            raise NotFound()
        allowed = sorted(ctx.source_ids) if ctx.source_ids is not None else None
        visible = (
            "WITH visible AS (SELECT r.id,r.evidence_id,r.source_version_id,r.source_sha256,"
            "r.document_id,r.document_sha256,r.source_tier,r.authority_kind,"
            "r.recorded_at FROM knowledge_source_tier_reviews r "
            "JOIN brain_evidence e ON e.tenant_id=r.tenant_id AND e.id=r.evidence_id "
            "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
            "AND v.id=e.source_version_id "
            "JOIN brain_source_items i ON i.tenant_id=v.tenant_id "
            "AND i.id=v.item_id AND i.source_id=v.source_id "
            "JOIN brain_sources s ON s.tenant_id=i.tenant_id AND s.id=i.source_id "
            "JOIN brain_normalized_documents d ON d.tenant_id=r.tenant_id "
            "AND d.id=r.document_id AND d.evidence_id=e.id "
            "WHERE r.evidence_id=%s AND r.source_version_id=v.id "
            "AND r.source_sha256=e.sha256 AND e.sha256=v.sha256 "
            "AND r.document_sha256=d.body_sha256 "
            "AND i.current_version_id=v.id AND s.status='active' "
            "AND NOT public.brain_email_evidence_is_excluded(e.tenant_id,e.id) "
            "AND (%s::text[] IS NULL OR s.id=ANY(%s::text[])) "
            "AND strpos(d.body,r.source_quote)>0) "
        )
        basis = (evidence_id, allowed, allowed)
        with self.store.transaction(ctx) as conn:
            counts = {
                row["source_tier"]: row["n"] for row in conn.execute(
                    visible + "SELECT source_tier,count(*)::integer AS n "
                    "FROM visible GROUP BY source_tier", basis,
                ).fetchall()
            }
            if after is None:
                rows = conn.execute(
                    visible + "SELECT * FROM visible "
                    "ORDER BY recorded_at DESC,id DESC LIMIT %s", (*basis, _PAGE + 1),
                ).fetchall()
            else:
                rows = conn.execute(
                    visible + "SELECT * FROM visible WHERE (recorded_at,id)<("
                    "SELECT recorded_at,id FROM visible WHERE id=%s) "
                    "ORDER BY recorded_at DESC,id DESC LIMIT %s",
                    (*basis, after, _PAGE + 1),
                ).fetchall()
                if not rows and not conn.execute(
                    visible + "SELECT 1 FROM visible WHERE id=%s", (*basis, after),
                ).fetchone():
                    raise NotFound()
            self.store.audit(
                conn, ctx, "knowledge.source_tier_reviews_read", "evidence", evidence_id,
            )
        page = [dict(row) for row in rows[:_PAGE]]
        more = len(rows) > _PAGE
        return {
            "evidence_id": evidence_id,
            "reviews": page,
            "truncated": more,
            "next_cursor": page[-1]["id"] if more else None,
            "tier_counts": {tier: counts.get(tier, 0) for tier in ("T1", "T2", "T3")},
            "meaning": "human_metadata_classification_not_byte_attestation_or_financial_truth",
            "untrusted_content": True,
        }
