"""Exact-project, source-stated reviewed facts with source-scoped paging."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.datacore.contracts import stable_id
from masterbrain.knowledge import _visible_assertion_sql
from masterbrain.knowledge_schema import ProjectFactPageRequest, ProjectFactWrite

_PROJECT_ID = re.compile(r"^project_[a-f0-9]{32}$")


def _fact_evidence_visible_sql(fact_alias: str) -> str:
    """Every frozen evidence ID is current, active, unexcluded and granted."""
    return (
        "NOT EXISTS (SELECT 1 FROM unnest(" + fact_alias + ".evidence_ids) AS fid(id) "
        "WHERE NOT EXISTS (SELECT 1 FROM brain_evidence e "
        "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
        "AND v.id=e.source_version_id "
        "JOIN brain_source_items i ON i.tenant_id=v.tenant_id "
        "AND i.id=v.item_id AND i.source_id=v.source_id "
        "JOIN brain_sources source ON source.tenant_id=i.tenant_id "
        "AND source.id=i.source_id "
        "WHERE e.tenant_id=" + fact_alias + ".tenant_id AND e.id=fid.id "
        "AND i.current_version_id=v.id AND source.status='active' "
        "AND NOT public.brain_email_evidence_is_excluded(e.tenant_id,e.id) "
        "AND (allowed.sources IS NULL OR source.id=ANY(allowed.sources)))) "
        "AND EXISTS (SELECT 1 FROM brain_normalized_documents doc "
        "WHERE doc.tenant_id=" + fact_alias + ".tenant_id "
        "AND doc.evidence_id=" + fact_alias + ".quote_evidence_id "
        "AND position(" + fact_alias + ".source_quote IN doc.body)>0)"
    )


_FACT_COMMON = "WITH allowed AS (SELECT %s::text[] AS sources, %s::timestamptz AS cutoff) "
_FACT_FROM = (
    "FROM knowledge_project_facts f "
    "JOIN knowledge_projects p ON p.tenant_id=f.tenant_id AND p.id=f.project_id "
    "CROSS JOIN allowed "
)
_FACT_VISIBLE = (
    _visible_assertion_sql("p", "'project'", "p.id")
    + " AND " + _fact_evidence_visible_sql("f")
)
_FACT_UNSUPERSEDED = (
    "NOT EXISTS (SELECT 1 FROM knowledge_project_facts s "
    "WHERE s.tenant_id=f.tenant_id AND s.supersedes_id=f.id "
    "AND s.recorded_at<=allowed.cutoff AND " + _fact_evidence_visible_sql("s") + ")"
)


def visible_project_fact_rows(
    conn: Any, allowed: list[str] | None, cutoff: datetime, project_id: str,
    limit: int, *, visibility: str = "unsuperseded",
    anchor: tuple[datetime, str] | None = None,
) -> list[Any]:
    """Filter complete source sets and review-chain effects before the limit."""
    if visibility not in ("retained", "unsuperseded"):
        raise ValueError("invalid fact visibility")
    chain_sql = " AND " + _FACT_UNSUPERSEDED if visibility == "unsuperseded" else ""
    cursor_sql = " AND (f.recorded_at,f.id)<(%s,%s)" if anchor else ""
    rows = conn.execute(
        _FACT_COMMON + "SELECT f.id,f.project_id,f.predicate,f.value,f.value_type,"
        "f.assertion_status,f.derivation,f.confidence,f.evidence_ids,"
        "f.quote_evidence_id,f.observed_at,f.valid_from,f.valid_to,f.recorded_at "
        + _FACT_FROM + "WHERE f.project_id=%s AND f.recorded_at<=allowed.cutoff "
        "AND p.recorded_at<=allowed.cutoff AND " + _FACT_VISIBLE
        + chain_sql + cursor_sql
        + " ORDER BY f.recorded_at DESC,f.id DESC LIMIT %s",
        (allowed, cutoff, project_id, *(anchor or ()), limit),
    ).fetchall()
    return list(rows)


def compact_project_fact(row: Any) -> dict[str, Any]:
    """Return a bounded interpretation, not a quote or certified source body."""
    return {
        "object_kind": "project_fact",
        "object_id": row["id"],
        "project_id": row["project_id"],
        "predicate": row["predicate"],
        "value_preview": row["value"][:300],
        "value_truncated": len(row["value"]) > 300,
        "value_type": row["value_type"],
        "assertion_status": row["assertion_status"],
        "derivation": row["derivation"],
        "confidence": row["confidence"],
        "evidence_ids": row["evidence_ids"],
        "quote_evidence_id": row["quote_evidence_id"],
        "observed_at": row["observed_at"],
        "valid_from": row["valid_from"],
        "valid_to": row["valid_to"],
        "recorded_at": row["recorded_at"],
    }


@dataclass(slots=True)
class ProjectFacts:
    store: Store

    def publish(
        self, ctx: TenantContext, project_id: str, body: ProjectFactWrite,
        idempotency_key: UUID,
    ) -> dict[str, Any]:
        self.store.require(ctx, "knowledge.review")
        self.store.require(ctx, "brain.content.read")
        if ctx.identity is not None and ctx.identity.client_kind != "human":
            raise AccessDenied("human identity required")
        if not isinstance(idempotency_key, UUID):
            raise ValueError("UUID idempotency key required")
        if not isinstance(project_id, str) or not _PROJECT_ID.fullmatch(project_id):
            raise NotFound()
        if not isinstance(body, ProjectFactWrite) or body.project_id != project_id:
            raise ValueError("project fact subject mismatch")
        allowed = sorted(ctx.source_ids) if ctx.source_ids is not None else None
        payload = body.model_dump(mode="json")
        request_sha = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        fact_id = stable_id(
            "pfact", str(ctx.tenant_id), str(ctx.actor_id), str(idempotency_key)
        )
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:pfact:{ctx.actor_id}:{idempotency_key}",),
            )
            project = conn.execute(
                "WITH allowed AS (SELECT %s::text[] AS sources) "
                "SELECT 1 FROM knowledge_projects p CROSS JOIN allowed "
                "WHERE p.id=%s AND " + _visible_assertion_sql("p", "'project'", "p.id"),
                (allowed, project_id),
            ).fetchone()
            if project is None:
                raise NotFound()
            matched: set[str] = set()
            for evidence_id in body.evidence_ids:
                row = conn.execute(
                    "SELECT e.id, EXISTS (SELECT 1 FROM brain_normalized_documents d "
                    "WHERE d.tenant_id=e.tenant_id AND d.evidence_id=e.id "
                    "AND position(%s IN d.body)>0) AS quote_matches "
                    "FROM brain_evidence e "
                    "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
                    "AND v.id=e.source_version_id "
                    "JOIN brain_source_items i ON i.tenant_id=v.tenant_id "
                    "AND i.id=v.item_id AND i.source_id=v.source_id "
                    "JOIN brain_sources source ON source.tenant_id=i.tenant_id "
                    "AND source.id=i.source_id "
                    "WHERE e.id=%s AND i.current_version_id=v.id "
                    "AND source.status='active' "
                    "AND NOT public.brain_email_evidence_is_excluded(e.tenant_id,e.id) "
                    "AND (%s::text[] IS NULL OR source.id=ANY(%s::text[]))",
                    (body.source_quote, evidence_id, allowed, allowed),
                ).fetchone()
                if row is None:
                    raise NotFound()
                if row["quote_matches"]:
                    matched.add(evidence_id)
            if body.quote_evidence_id not in matched:
                raise ValueError("project fact quote lacks an exact source span")
            if body.supersedes_id is not None:
                prior_fact = conn.execute(
                    "WITH allowed AS (SELECT %s::text[] AS sources) "
                    "SELECT f.project_id,f.predicate,f.value_type "
                    "FROM knowledge_project_facts f CROSS JOIN allowed "
                    "WHERE f.id=%s AND " + _fact_evidence_visible_sql("f"),
                    (allowed, body.supersedes_id),
                ).fetchone()
                if (prior_fact is None or prior_fact["project_id"] != project_id
                    or prior_fact["predicate"] != body.predicate
                    or prior_fact["value_type"] != body.value_type):
                    raise NotFound()
            prior = conn.execute(
                "SELECT request_sha256,fact_id FROM knowledge_project_fact_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if prior["request_sha256"] != request_sha:
                    raise Conflict("project fact idempotency key reused")
                return {"object_id": prior["fact_id"], "changed": False, "reviewed": True}
            conn.execute(
                "INSERT INTO knowledge_project_facts(tenant_id,id,project_id,predicate,"
                "value,value_type,assertion_status,confidence,derivation,evidence_ids,"
                "quote_evidence_id,source_quote,observed_at,valid_from,valid_to,"
                "supersedes_id,reviewer_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, fact_id, project_id, body.predicate, body.value,
                 body.value_type, body.assertion_status, body.confidence,
                 body.derivation, body.evidence_ids, body.quote_evidence_id,
                 body.source_quote, body.observed_at, body.valid_from, body.valid_to,
                 body.supersedes_id, ctx.actor_id),
            )
            conn.execute(
                "INSERT INTO knowledge_project_fact_receipts(tenant_id,actor_id,"
                "idempotency_key,request_sha256,fact_id) VALUES (%s,%s,%s,%s,%s)",
                (ctx.tenant_id, ctx.actor_id, idempotency_key, request_sha, fact_id),
            )
            self.store.audit(conn, ctx, "knowledge.project_fact_published", "pfact", fact_id)
        return {"object_id": fact_id, "changed": True, "reviewed": True}

    def page(
        self, ctx: TenantContext, project_id: str, request: ProjectFactPageRequest,
    ) -> dict[str, Any]:
        self.store.require(ctx, "knowledge.search")
        if (not isinstance(project_id, str) or not _PROJECT_ID.fullmatch(project_id)
                or not isinstance(request, ProjectFactPageRequest)):
            raise NotFound()
        allowed = sorted(ctx.source_ids) if ctx.source_ids is not None else None
        with self.store.transaction(ctx) as conn:
            clock = conn.execute("SELECT transaction_timestamp() AS now").fetchone()
            if clock is None:
                raise RuntimeError("project fact database clock unavailable")
            now = clock["now"]
            cutoff = (
                request.recorded_cutoff_at.astimezone(UTC)
                if request.recorded_cutoff_at else now
            )
            if cutoff > now:
                raise ValueError("invalid future project fact cutoff")
            project = conn.execute(
                _FACT_COMMON + "SELECT 1 FROM knowledge_projects p CROSS JOIN allowed "
                "WHERE p.id=%s AND p.recorded_at<=allowed.cutoff AND "
                + _visible_assertion_sql("p", "'project'", "p.id"),
                (allowed, cutoff, project_id),
            ).fetchone()
            if project is None:
                raise NotFound()
            anchor = None
            if request.after is not None:
                chain_sql = (
                    " AND " + _FACT_UNSUPERSEDED
                    if request.visibility == "unsuperseded" else ""
                )
                anchor = conn.execute(
                    _FACT_COMMON + "SELECT f.recorded_at,f.id " + _FACT_FROM
                    + "WHERE f.project_id=%s AND f.recorded_at<=allowed.cutoff "
                    "AND p.recorded_at<=allowed.cutoff AND " + _FACT_VISIBLE
                    + chain_sql + " AND f.id=%s",
                    (allowed, cutoff, project_id, request.after),
                ).fetchone()
                if anchor is None:
                    raise NotFound()
            rows = visible_project_fact_rows(
                conn, allowed, cutoff, project_id, request.limit + 1,
                visibility=request.visibility,
                anchor=(anchor["recorded_at"], anchor["id"]) if anchor else None,
            )
            self.store.audit(conn, ctx, "knowledge.project_facts_read", "project", project_id)
        page = rows[:request.limit]
        return {
            "project_id": project_id,
            "results": [compact_project_fact(row) for row in page],
            "next_cursor": page[-1]["id"] if len(rows) > request.limit and page else None,
            "recorded_cutoff_at": cutoff,
            "limit": request.limit,
            "visibility": request.visibility,
            "coverage": "current_authorized_source_stated_reviewed_facts",
            "untrusted_content": True,
        }
