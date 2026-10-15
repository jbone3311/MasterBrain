"""Reviewed, source-scoped links from projects to exact evidence occurrences."""

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
from masterbrain.knowledge_schema import (
    ProjectArtifactLinkWrite,
    ProjectArtifactPageRequest,
    ProjectIdentity,
)

_PROJECT_ID = re.compile(r"^project_[a-f0-9]{32}$")


def _current_evidence_sql(evidence_id_sql: str, *, quote: bool = False) -> str:
    """Closed SQL fragment; source grants and currentness precede pagination."""
    normalized = (
        "JOIN brain_normalized_documents d ON d.tenant_id=e.tenant_id "
        "AND d.evidence_id=e.id " if quote else ""
    )
    quote_check = "AND position(l.source_quote IN d.body)>0 " if quote else ""
    return (
        "EXISTS (SELECT 1 FROM brain_evidence e "
        "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
        "AND v.id=e.source_version_id "
        "JOIN brain_source_items i ON i.tenant_id=v.tenant_id "
        "AND i.id=v.item_id AND i.source_id=v.source_id "
        "JOIN brain_sources s ON s.tenant_id=i.tenant_id AND s.id=i.source_id "
        + normalized
        + f"WHERE e.tenant_id=l.tenant_id AND e.id={evidence_id_sql} "
        "AND i.current_version_id=v.id AND s.status='active' "
        "AND NOT public.brain_email_evidence_is_excluded(e.tenant_id,e.id) "
        "AND (allowed.sources IS NULL OR s.id=ANY(allowed.sources)) "
        + quote_check + ")"
    )


_LINK_VISIBLE = (
    _visible_assertion_sql("p", "'project'", "p.id")
    + " AND " + _current_evidence_sql("l.artifact_evidence_id")
    + " AND " + _current_evidence_sql("l.basis_evidence_id", quote=True)
)

_ARTIFACT_FROM_SQL = (
    "FROM knowledge_project_artifacts l "
    "JOIN knowledge_projects p ON p.tenant_id=l.tenant_id AND p.id=l.project_id "
    "JOIN brain_evidence ae ON ae.tenant_id=l.tenant_id "
    "AND ae.id=l.artifact_evidence_id "
    "JOIN brain_source_versions av ON av.tenant_id=ae.tenant_id "
    "AND av.id=ae.source_version_id "
    "JOIN brain_sources artifact_source ON artifact_source.tenant_id=av.tenant_id "
    "AND artifact_source.id=av.source_id CROSS JOIN allowed "
)
_ARTIFACT_WHERE_SQL = (
    "WHERE l.project_id=%s AND l.recorded_at<=allowed.cutoff "
    "AND p.recorded_at<=allowed.cutoff AND " + _LINK_VISIBLE
)
_ARTIFACT_COMMON_SQL = (
    "WITH allowed AS (SELECT %s::text[] AS sources, %s::timestamptz AS cutoff) "
)


def visible_project_artifact_rows(
    conn: Any, allowed: list[str] | None, cutoff: datetime, project_id: str,
    limit: int, *, anchor: tuple[datetime, str] | None = None,
    include_quote: bool = False,
) -> list[Any]:
    """Return current-authorized link history before the independent limit."""
    cursor_sql = " AND (l.recorded_at,l.id)<(%s,%s)" if anchor else ""
    rows = conn.execute(
        _ARTIFACT_COMMON_SQL + "SELECT l.id,l.artifact_evidence_id,l.basis_evidence_id,"
        "l.relation,l.assertion_status,l.observed_at,l.recorded_at,"
        + ("l.source_quote," if include_quote else "")
        + "artifact_source.kind AS artifact_source_kind "
        + _ARTIFACT_FROM_SQL + _ARTIFACT_WHERE_SQL + cursor_sql
        + " ORDER BY l.recorded_at DESC,l.id DESC LIMIT %s",
        (allowed, cutoff, project_id, *(anchor or ()), limit),
    ).fetchall()
    return list(rows)


@dataclass(slots=True)
class ProjectArtifactLinks:
    store: Store

    def publish(
        self, ctx: TenantContext, project_id: ProjectIdentity,
        body: ProjectArtifactLinkWrite, idempotency_key: UUID,
    ) -> dict[str, Any]:
        self._validate_publish(ctx, project_id, idempotency_key)
        with self.store.transaction(ctx) as conn:
            return self._publish_in_transaction(
                conn, ctx, project_id, body, idempotency_key,
            )

    def _validate_publish(
        self, ctx: TenantContext, project_id: ProjectIdentity,
        idempotency_key: UUID,
    ) -> None:
        self._validate_actor_project(ctx, project_id)
        if not isinstance(idempotency_key, UUID):
            raise ValueError("UUID idempotency key required")

    def _validate_actor_project(
        self, ctx: TenantContext, project_id: ProjectIdentity,
    ) -> None:
        self.store.require(ctx, "knowledge.review")
        self.store.require(ctx, "brain.content.read")
        if ctx.identity is not None and ctx.identity.client_kind != "human":
            raise AccessDenied("human identity required")
        if not isinstance(project_id, str) or not _PROJECT_ID.fullmatch(project_id):
            raise NotFound()

    def _validate_basis_in_transaction(
        self, conn: Any, ctx: TenantContext, project_id: ProjectIdentity,
        body: ProjectArtifactLinkWrite,
    ) -> str:
        """Recheck the exact project and both current evidence occurrences."""
        self._validate_actor_project(ctx, project_id)
        allowed = sorted(ctx.source_ids) if ctx.source_ids is not None else None
        project = conn.execute(
            "WITH allowed AS (SELECT %s::text[] AS sources) "
            "SELECT 1 FROM knowledge_projects p CROSS JOIN allowed "
            "WHERE p.id=%s AND " + _visible_assertion_sql("p", "'project'", "p.id"),
            (allowed, project_id),
        ).fetchone()
        if project is None:
            raise NotFound()
        # Verify both exact evidence identities independently. The quote may
        # come from a parent email rather than the linked attachment itself.
        artifact_kind: str | None = None
        for evidence_id, quote in (
            (body.artifact_evidence_id, None),
            (body.basis_evidence_id, body.source_quote),
        ):
            match = conn.execute(
                "SELECT e.id,s.kind AS source_kind, "
                "EXISTS (SELECT 1 FROM brain_normalized_documents d "
                "WHERE d.tenant_id=e.tenant_id AND d.evidence_id=e.id "
                "AND position(%s in d.body)>0) AS quote_matches "
                "FROM brain_evidence e "
                "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
                "AND v.id=e.source_version_id "
                "JOIN brain_source_items i ON i.tenant_id=v.tenant_id "
                "AND i.id=v.item_id AND i.source_id=v.source_id "
                "JOIN brain_sources s ON s.tenant_id=i.tenant_id AND s.id=i.source_id "
                "WHERE e.id=%s AND i.current_version_id=v.id AND s.status='active' "
                "AND NOT public.brain_email_evidence_is_excluded(e.tenant_id,e.id) "
                "AND (%s::text[] IS NULL OR s.id=ANY(%s::text[]))",
                (quote or "", evidence_id, allowed, allowed),
            ).fetchone()
            if match is None:
                raise NotFound()
            if quote is None:
                artifact_kind = str(match["source_kind"])
            elif not match["quote_matches"]:
                raise ValueError("project artifact quote lacks an exact source span")
        if artifact_kind is None:
            raise RuntimeError("artifact evidence kind unavailable")
        return artifact_kind

    def _publish_in_transaction(
        self, conn: Any, ctx: TenantContext, project_id: ProjectIdentity,
        body: ProjectArtifactLinkWrite, idempotency_key: UUID,
    ) -> dict[str, Any]:
        """Publish under the caller's transaction for later atomic batch review."""
        self._validate_publish(ctx, project_id, idempotency_key)
        payload = {"project_id": project_id, **body.model_dump(mode="json")}
        request_sha = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        link_id = stable_id(
            "partifact", str(ctx.tenant_id), str(ctx.actor_id), str(idempotency_key)
        )
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"{ctx.tenant_id}:partifact:{ctx.actor_id}:{idempotency_key}",),
        )
        self._validate_basis_in_transaction(conn, ctx, project_id, body)
        prior = conn.execute(
            "SELECT request_sha256,link_id FROM knowledge_project_artifact_receipts "
            "WHERE actor_id=%s AND idempotency_key=%s",
            (ctx.actor_id, idempotency_key),
        ).fetchone()
        if prior is not None:
            if prior["request_sha256"] != request_sha:
                raise Conflict("project artifact idempotency key reused")
            return {"object_id": prior["link_id"], "changed": False, "reviewed": True}
        conn.execute(
            "INSERT INTO knowledge_project_artifacts(tenant_id,id,project_id,"
            "artifact_evidence_id,basis_evidence_id,relation,assertion_status,"
            "source_quote,observed_at,reviewer_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (ctx.tenant_id, link_id, project_id, body.artifact_evidence_id,
             body.basis_evidence_id, body.relation, body.assertion_status,
             body.source_quote, body.observed_at, ctx.actor_id),
        )
        conn.execute(
            "INSERT INTO knowledge_project_artifact_receipts(tenant_id,actor_id,"
            "idempotency_key,request_sha256,link_id) VALUES (%s,%s,%s,%s,%s)",
            (ctx.tenant_id, ctx.actor_id, idempotency_key, request_sha, link_id),
        )
        self.store.audit(
            conn, ctx, "knowledge.project_artifact_published", "partifact", link_id,
        )
        return {"object_id": link_id, "changed": True, "reviewed": True}

    def page(
        self, ctx: TenantContext, project_id: ProjectIdentity,
        request: ProjectArtifactPageRequest,
    ) -> dict[str, Any]:
        self.store.require(ctx, "knowledge.search")
        if (not isinstance(project_id, str) or not _PROJECT_ID.fullmatch(project_id)
                or not isinstance(request, ProjectArtifactPageRequest)):
            raise NotFound()
        allowed = sorted(ctx.source_ids) if ctx.source_ids is not None else None
        with self.store.transaction(ctx) as conn:
            clock = conn.execute("SELECT transaction_timestamp() AS now").fetchone()
            if clock is None:
                raise RuntimeError("project artifact database clock unavailable")
            now = clock["now"]
            cutoff = (
                request.recorded_cutoff_at.astimezone(UTC)
                if request.recorded_cutoff_at else now
            )
            if cutoff > now:
                raise ValueError("invalid future project artifact cutoff")
            project = conn.execute(
                _ARTIFACT_COMMON_SQL + "SELECT 1 FROM knowledge_projects p CROSS JOIN allowed "
                "WHERE p.id=%s AND p.recorded_at<=allowed.cutoff AND "
                + _visible_assertion_sql("p", "'project'", "p.id"),
                (allowed, cutoff, project_id),
            ).fetchone()
            if project is None:
                raise NotFound()
            anchor = None
            if request.after is not None:
                anchor = conn.execute(
                    _ARTIFACT_COMMON_SQL + "SELECT l.recorded_at,l.id "
                    + _ARTIFACT_FROM_SQL + _ARTIFACT_WHERE_SQL
                    + " AND l.id=%s",
                    (allowed, cutoff, project_id, request.after),
                ).fetchone()
                if anchor is None:
                    raise NotFound()
            rows = visible_project_artifact_rows(
                conn, allowed, cutoff, project_id, request.limit + 1,
                anchor=(anchor["recorded_at"], anchor["id"]) if anchor else None,
            )
            self.store.audit(conn, ctx, "knowledge.project_artifacts_read", "project", project_id)
        page = rows[:request.limit]
        return {
            "project_id": project_id,
            "results": [
                {"object_kind": "project_artifact", "object_id": row["id"],
                 "artifact_evidence_id": row["artifact_evidence_id"],
                 "basis_evidence_id": row["basis_evidence_id"],
                 "artifact_source_kind": row["artifact_source_kind"],
                 "relation": row["relation"],
                 "assertion_status": row["assertion_status"],
                 "observed_at": row["observed_at"],
                 "recorded_at": row["recorded_at"]}
                for row in page
            ],
            "next_cursor": page[-1]["id"] if len(rows) > request.limit and page else None,
            "recorded_cutoff_at": cutoff,
            "limit": request.limit,
            "coverage": "current_authorized_evidence_reviewed_link_history",
            "untrusted_content": True,
        }
