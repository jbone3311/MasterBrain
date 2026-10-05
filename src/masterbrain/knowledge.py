"""Reviewed, append-only KnowledgeCore persistence and retrieval."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC
from typing import Any
from uuid import UUID

import psycopg

from email_brain.domain.models import TenantContext
from email_brain.store import Conflict, NotFound, Store
from masterbrain.datacore.contracts import stable_id
from masterbrain.knowledge_schema import (
    ClaimWrite,
    CommitmentWrite,
    CorrectionWrite,
    DueCommitmentsRequest,
    EntityWrite,
    EventWrite,
    KnowledgeAssertion,
    KnowledgeVisibility,
    ProjectWrite,
    RelationshipWrite,
    TimelineRequest,
)

_ID = re.compile(r"^[a-z]+_[a-f0-9]{32}$")
_TABLES = {
    "entity": "knowledge_entities",
    "relationship": "knowledge_relationships",
    "claim": "knowledge_claims",
    "project": "knowledge_projects",
    "event": "knowledge_events",
    "commitment": "knowledge_commitments",
    "correction": "knowledge_corrections",
}


def _visible_assertion_sql(alias: str, kind_sql: str, id_sql: str) -> str:
    """Closed SQL fragment for an assertion's full direct-source grant set."""
    return (
        "(allowed.sources IS NULL OR ("
        "EXISTS (SELECT 1 FROM knowledge_evidence ke "
        f"WHERE ke.tenant_id={alias}.tenant_id AND ke.target_kind={kind_sql} "
        f"AND ke.target_id={id_sql}) AND NOT EXISTS ("
        "SELECT 1 FROM knowledge_evidence ke "
        "JOIN brain_evidence e ON e.tenant_id=ke.tenant_id "
        "AND e.id=ke.evidence_id "
        "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
        "AND v.id=e.source_version_id "
        f"WHERE ke.tenant_id={alias}.tenant_id AND ke.target_kind={kind_sql} "
        f"AND ke.target_id={id_sql} "
        "AND v.source_id<>ALL(allowed.sources))))"
    )


_VISIBLE_REPLACEMENT = _visible_assertion_sql("r", "r.object_kind", "r.object_id")
_VISIBLE_CORRECTION = _visible_assertion_sql("c", "'correction'", "c.id")
_UNSUPERSEDED_SQL = (
    "k.object_kind<>'correction' AND NOT EXISTS ("
    "SELECT 1 FROM knowledge_corrections c "
    "JOIN knowledge_search_documents r ON r.tenant_id=c.tenant_id "
    "AND r.object_kind=c.target_kind AND r.object_id=c.replacement_id "
    "WHERE c.tenant_id=k.tenant_id AND c.target_kind=k.object_kind "
    "AND c.target_id=k.object_id AND "
    + _VISIBLE_CORRECTION + " AND " + _VISIBLE_REPLACEMENT + ") "
    + " ".join(
        "AND (k.object_kind<>'" + kind + "' OR NOT EXISTS ("
        "SELECT 1 FROM " + table + " s WHERE s.tenant_id=k.tenant_id "
        "AND s.supersedes_id=k.object_id AND "
        + _visible_assertion_sql("s", "'" + kind + "'", "s.id") + "))"
        for kind, table in _TABLES.items() if kind != "correction"
    )
)

# A timeline event may refer to a separately source-protected project. A hidden
# project-linked successor must not suppress a visible predecessor in that read.
_TIMELINE_UNSUPERSEDED_SQL = (
    "NOT EXISTS (SELECT 1 FROM knowledge_events s "
    "LEFT JOIN knowledge_projects sp ON sp.tenant_id=s.tenant_id "
    "AND sp.id=s.project_id "
    "WHERE s.tenant_id=ev.tenant_id AND s.supersedes_id=ev.id "
    "AND s.recorded_at<=allowed.cutoff "
    "AND " + _visible_assertion_sql("s", "'event'", "s.id")
    + " AND (s.project_id IS NULL OR "
    + _visible_assertion_sql("sp", "'project'", "sp.id") + ")) "
    "AND NOT EXISTS (SELECT 1 FROM knowledge_corrections c "
    "JOIN knowledge_events r ON r.tenant_id=c.tenant_id "
    "AND r.id=c.replacement_id "
    "LEFT JOIN knowledge_projects rp ON rp.tenant_id=r.tenant_id "
    "AND rp.id=r.project_id "
    "WHERE c.tenant_id=ev.tenant_id AND c.target_kind='event' "
    "AND c.target_id=ev.id AND c.recorded_at<=allowed.cutoff "
    "AND r.recorded_at<=allowed.cutoff AND "
    + _visible_assertion_sql("c", "'correction'", "c.id") + " AND "
    + _visible_assertion_sql("r", "'event'", "r.id")
    + " AND (r.project_id IS NULL OR "
    + _visible_assertion_sql("rp", "'project'", "rp.id") + "))"
)


def _visible_commitment_sql(alias: str) -> str:
    """Require direct and referenced-object source grants before due paging."""
    parts = [_visible_assertion_sql(alias, "'commitment'", f"{alias}.id")]
    for column, table, related_alias, kind in (
        ("project_id", "knowledge_projects", "kp", "project"),
        ("owner_entity_id", "knowledge_entities", "ko", "entity"),
        ("counterparty_entity_id", "knowledge_entities", "kc", "entity"),
    ):
        parts.append(
            f"({alias}.{column} IS NULL OR EXISTS (SELECT 1 FROM {table} {related_alias} "
            f"WHERE {related_alias}.tenant_id={alias}.tenant_id "
            f"AND {related_alias}.id={alias}.{column} AND "
            + _visible_assertion_sql(related_alias, f"'{kind}'", f"{related_alias}.id")
            + "))"
        )
    return " AND ".join(parts)


_DUE_UNSUPERSEDED_SQL = (
    "NOT EXISTS (SELECT 1 FROM knowledge_commitments s "
    "WHERE s.tenant_id=cm.tenant_id AND s.supersedes_id=cm.id "
    "AND s.recorded_at<=allowed.cutoff AND "
    + _visible_commitment_sql("s") + ") "
    "AND NOT EXISTS (SELECT 1 FROM knowledge_corrections c "
    "JOIN knowledge_commitments r ON r.tenant_id=c.tenant_id "
    "AND r.id=c.replacement_id "
    "WHERE c.tenant_id=cm.tenant_id AND c.target_kind='commitment' "
    "AND c.target_id=cm.id AND c.recorded_at<=allowed.cutoff "
    "AND r.recorded_at<=allowed.cutoff AND "
    + _visible_assertion_sql("c", "'correction'", "c.id") + " AND "
    + _visible_commitment_sql("r") + ")"
)


@dataclass(frozen=True, slots=True)
class KnowledgeResult:
    object_kind: str
    object_id: str
    changed: bool


@dataclass(frozen=True, slots=True)
class KnowledgeHit:
    object_kind: str
    object_id: str
    title: str
    excerpt: str
    rank: float
    evidence_ids: tuple[str, ...]


def _digest(assertion: KnowledgeAssertion) -> str:
    value = assertion.model_dump(mode="json")
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _normalized_alias(value: str) -> str:
    return " ".join(value.casefold().split())


class KnowledgeCore:
    def __init__(self, store: Store) -> None:
        self.store = store

    @staticmethod
    def _require_object(
        conn: psycopg.Connection[dict[str, Any]], kind: str, object_id: str
    ) -> None:
        table = _TABLES[kind]
        row = conn.execute(f"SELECT 1 FROM {table} WHERE id=%s", (object_id,)).fetchone()
        if not row:
            raise NotFound()

    @staticmethod
    def _evidence_ids(assertion: KnowledgeAssertion) -> list[str]:
        return list(assertion.evidence_ids)

    def publish(
        self,
        ctx: TenantContext,
        assertion: KnowledgeAssertion,
        idempotency_key: UUID,
    ) -> KnowledgeResult:
        self.store.require(ctx, "knowledge.review")
        if not isinstance(idempotency_key, UUID):
            raise ValueError("UUID idempotency key required")
        kind = assertion.kind
        object_id = stable_id(kind, str(ctx.tenant_id), str(ctx.actor_id), str(idempotency_key))
        request_hash = _digest(assertion)
        evidence_ids = self._evidence_ids(assertion)
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:knowledge:{ctx.actor_id}:{idempotency_key}",),
            )
            old = conn.execute(
                "SELECT request_hash,object_kind,object_id FROM knowledge_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if old:
                if old["request_hash"] != request_hash:
                    raise Conflict("knowledge idempotency key reused")
                return KnowledgeResult(old["object_kind"], old["object_id"], False)
            rows = conn.execute(
                "SELECT id FROM brain_evidence WHERE id=ANY(%s)", (evidence_ids,)
            ).fetchall()
            if {row["id"] for row in rows} != set(evidence_ids):
                raise NotFound()
            supersedes = getattr(assertion, "supersedes_id", None)
            if supersedes is not None:
                if not supersedes.startswith(kind + "_"):
                    raise ValueError("supersedes identity has the wrong kind")
                self._require_object(conn, kind, supersedes)

            title, body = self._insert(conn, ctx, object_id, assertion)
            for evidence_id in evidence_ids:
                conn.execute(
                    "INSERT INTO knowledge_evidence(tenant_id,target_kind,target_id,evidence_id,"
                    "stance,locator) VALUES (%s,%s,%s,%s,'supports','{}')",
                    (ctx.tenant_id, kind, object_id, evidence_id),
                )
            conn.execute(
                "INSERT INTO knowledge_search_documents(tenant_id,object_kind,object_id,"
                "title,body) "
                "VALUES (%s,%s,%s,%s,%s)",
                (ctx.tenant_id, kind, object_id, title, body),
            )
            change_id = stable_id("kchange", kind, object_id)
            conn.execute(
                "INSERT INTO knowledge_change_events(tenant_id,id,object_kind,object_id) "
                "VALUES (%s,%s,%s,%s)",
                (ctx.tenant_id, change_id, kind, object_id),
            )
            conn.execute(
                "INSERT INTO knowledge_receipts(tenant_id,actor_id,idempotency_key,request_hash,"
                "object_kind,object_id) VALUES (%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, ctx.actor_id, idempotency_key, request_hash, kind, object_id),
            )
            self.store.audit(conn, ctx, "knowledge.published", kind, object_id)
            return KnowledgeResult(kind, object_id, True)

    def _insert(
        self,
        conn: psycopg.Connection[dict[str, Any]],
        ctx: TenantContext,
        object_id: str,
        assertion: KnowledgeAssertion,
    ) -> tuple[str, str]:
        if isinstance(assertion, EntityWrite):
            conn.execute(
                "INSERT INTO knowledge_entities(tenant_id,id,entity_type,name,confidence,"
                "source_quote,observed_at,valid_from,valid_to,supersedes_id,reviewer_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    object_id,
                    assertion.entity_type,
                    assertion.name,
                    assertion.confidence,
                    assertion.source_quote,
                    assertion.observed_at,
                    assertion.valid_from,
                    assertion.valid_to,
                    assertion.supersedes_id,
                    ctx.actor_id,
                ),
            )
            for alias in assertion.aliases:
                normalized = _normalized_alias(alias)
                conn.execute(
                    "INSERT INTO knowledge_entity_aliases(tenant_id,id,entity_id,alias,"
                    "normalized_alias) VALUES (%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        stable_id("alias", object_id, normalized),
                        object_id,
                        alias,
                        normalized,
                    ),
                )
            return assertion.name, " ".join([assertion.name, *assertion.aliases])
        if isinstance(assertion, RelationshipWrite):
            self._require_object(conn, "entity", assertion.subject_entity_id)
            self._require_object(conn, "entity", assertion.object_entity_id)
            conn.execute(
                "INSERT INTO knowledge_relationships(tenant_id,id,subject_entity_id,predicate,"
                "object_entity_id,assertion_status,confidence,source_quote,observed_at,valid_from,"
                "valid_to,supersedes_id,reviewer_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    object_id,
                    assertion.subject_entity_id,
                    assertion.predicate,
                    assertion.object_entity_id,
                    assertion.assertion_status,
                    assertion.confidence,
                    assertion.source_quote,
                    assertion.observed_at,
                    assertion.valid_from,
                    assertion.valid_to,
                    assertion.supersedes_id,
                    ctx.actor_id,
                ),
            )
            title = assertion.predicate.replace("_", " ")
            return title, f"{assertion.subject_entity_id} {title} {assertion.object_entity_id}"
        if isinstance(assertion, ClaimWrite):
            self._require_object(conn, "entity", assertion.subject_entity_id)
            conn.execute(
                "INSERT INTO knowledge_claims(tenant_id,id,subject_entity_id,predicate,value,"
                "value_type,assertion_status,confidence,source_quote,observed_at,valid_from,"
                "valid_to,supersedes_id,reviewer_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    object_id,
                    assertion.subject_entity_id,
                    assertion.predicate,
                    assertion.value,
                    assertion.value_type,
                    assertion.assertion_status,
                    assertion.confidence,
                    assertion.source_quote,
                    assertion.observed_at,
                    assertion.valid_from,
                    assertion.valid_to,
                    assertion.supersedes_id,
                    ctx.actor_id,
                ),
            )
            return assertion.predicate.replace("_", " "), assertion.value
        if isinstance(assertion, ProjectWrite):
            conn.execute(
                "INSERT INTO knowledge_projects(tenant_id,id,title,description,state,confidence,"
                "source_quote,observed_at,valid_from,valid_to,supersedes_id,reviewer_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    object_id,
                    assertion.title,
                    assertion.description,
                    assertion.state,
                    assertion.confidence,
                    assertion.source_quote,
                    assertion.observed_at,
                    assertion.valid_from,
                    assertion.valid_to,
                    assertion.supersedes_id,
                    ctx.actor_id,
                ),
            )
            return assertion.title, f"{assertion.state} {assertion.description}"
        if isinstance(assertion, EventWrite):
            if assertion.project_id:
                self._require_object(conn, "project", assertion.project_id)
            conn.execute(
                "INSERT INTO knowledge_events(tenant_id,id,event_type,title,description,starts_at,"
                "ends_at,project_id,confidence,source_quote,observed_at,valid_from,valid_to,"
                "supersedes_id,reviewer_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    object_id,
                    assertion.event_type,
                    assertion.title,
                    assertion.description,
                    assertion.starts_at,
                    assertion.ends_at,
                    assertion.project_id,
                    assertion.confidence,
                    assertion.source_quote,
                    assertion.observed_at,
                    assertion.valid_from,
                    assertion.valid_to,
                    assertion.supersedes_id,
                    ctx.actor_id,
                ),
            )
            return assertion.title, f"{assertion.event_type} {assertion.description}"
        if isinstance(assertion, CommitmentWrite):
            for entity_id in (assertion.owner_entity_id, assertion.counterparty_entity_id):
                if entity_id:
                    self._require_object(conn, "entity", entity_id)
            if assertion.project_id:
                self._require_object(conn, "project", assertion.project_id)
            conn.execute(
                "INSERT INTO knowledge_commitments(tenant_id,id,description,state,owner_entity_id,"
                "counterparty_entity_id,project_id,due_at,confidence,source_quote,observed_at,"
                "valid_from,valid_to,supersedes_id,reviewer_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    object_id,
                    assertion.description,
                    assertion.state,
                    assertion.owner_entity_id,
                    assertion.counterparty_entity_id,
                    assertion.project_id,
                    assertion.due_at,
                    assertion.confidence,
                    assertion.source_quote,
                    assertion.observed_at,
                    assertion.valid_from,
                    assertion.valid_to,
                    assertion.supersedes_id,
                    ctx.actor_id,
                ),
            )
            return "commitment", f"{assertion.state} {assertion.description}"
        assert isinstance(assertion, CorrectionWrite)
        self._require_object(conn, assertion.target_kind, assertion.target_id)
        self._require_object(conn, assertion.target_kind, assertion.replacement_id)
        conn.execute(
            "INSERT INTO knowledge_corrections(tenant_id,id,target_kind,target_id,replacement_id,"
            "reason,source_quote,observed_at,reviewer_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                ctx.tenant_id,
                object_id,
                assertion.target_kind,
                assertion.target_id,
                assertion.replacement_id,
                assertion.reason,
                assertion.source_quote,
                assertion.observed_at,
                ctx.actor_id,
            ),
        )
        return "correction", assertion.reason

    def get(self, ctx: TenantContext, kind: str, object_id: str) -> dict[str, Any]:
        self.store.require(ctx, "knowledge.read")
        if (
            kind not in _TABLES
            or not _ID.fullmatch(object_id)
            or not object_id.startswith(kind + "_")
        ):
            raise NotFound()
        table = _TABLES[kind]
        allowed_sources = sorted(ctx.source_ids) if ctx.source_ids is not None else None
        with self.store.transaction(ctx) as conn:
            row = conn.execute(
                f"SELECT k.* FROM {table} k WHERE k.id=%s "
                "AND (%s::text[] IS NULL OR ("
                "EXISTS (SELECT 1 FROM knowledge_evidence ke "
                "WHERE ke.tenant_id=k.tenant_id AND ke.target_kind=%s "
                "AND ke.target_id=k.id) AND NOT EXISTS ("
                "SELECT 1 FROM knowledge_evidence ke JOIN brain_evidence e "
                "ON e.tenant_id=ke.tenant_id AND e.id=ke.evidence_id "
                "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
                "AND v.id=e.source_version_id WHERE ke.tenant_id=k.tenant_id "
                "AND ke.target_kind=%s AND ke.target_id=k.id "
                "AND v.source_id<>ALL(%s::text[]))))",
                (object_id, allowed_sources, kind, kind, allowed_sources),
            ).fetchone()
            if not row:
                raise NotFound()
            evidence = conn.execute(
                "SELECT evidence_id,stance,locator FROM knowledge_evidence "
                "WHERE target_kind=%s AND target_id=%s ORDER BY evidence_id",
                (kind, object_id),
            ).fetchall()
            self.store.audit(conn, ctx, "knowledge.read", kind, object_id)
            return {**row, "kind": kind, "evidence": evidence, "untrusted_content": True}

    def search(
        self, ctx: TenantContext, query: str, *, limit: int = 10,
        kinds: list[str] | None = None, visibility: KnowledgeVisibility = "retained",
    ) -> list[KnowledgeHit]:
        self.store.require(ctx, "knowledge.search")
        selected = kinds or []
        if not query.strip() or len(query) > 500 or not 1 <= limit <= 50:
            raise ValueError("invalid knowledge search")
        if any(kind not in _TABLES for kind in selected) or len(set(selected)) != len(selected):
            raise ValueError("invalid knowledge kinds")
        if visibility not in {"retained", "unsuperseded"}:
            raise ValueError("invalid knowledge visibility")
        allowed_sources = sorted(ctx.source_ids) if ctx.source_ids is not None else None
        visibility_sql = (
            " AND (" + _UNSUPERSEDED_SQL + ")"
            if visibility == "unsuperseded" else ""
        )
        with self.store.transaction(ctx) as conn:
            rows = conn.execute(
                "WITH allowed AS (SELECT %s::text[] AS sources) "
                "SELECT k.object_kind,k.object_id,k.title,"
                "ts_headline('simple',k.body,plainto_tsquery('simple',%s),"
                "'MaxWords=35,MinWords=10,StartSel=\"\",StopSel=\"\"') AS excerpt,"
                "ts_rank_cd(k.search_vector,plainto_tsquery('simple',%s)) AS rank "
                "FROM knowledge_search_documents k CROSS JOIN allowed "
                "WHERE k.search_vector @@ "
                "plainto_tsquery('simple',%s) "
                "AND (cardinality(%s::text[])=0 OR k.object_kind=ANY(%s)) "
                "AND " + _visible_assertion_sql("k", "k.object_kind", "k.object_id")
                + visibility_sql + " ORDER BY rank DESC,k.object_kind,k.object_id LIMIT %s",
                (
                    allowed_sources, query, query, query, selected, selected,
                    limit,
                ),
            ).fetchall()
            hits: list[KnowledgeHit] = []
            for row in rows:
                evidence = conn.execute(
                    "SELECT evidence_id FROM knowledge_evidence WHERE target_kind=%s "
                    "AND target_id=%s ORDER BY evidence_id",
                    (row["object_kind"], row["object_id"]),
                ).fetchall()
                hits.append(
                    KnowledgeHit(
                        row["object_kind"],
                        row["object_id"],
                        row["title"],
                        row["excerpt"],
                        row["rank"],
                        tuple(item["evidence_id"] for item in evidence),
                    )
                )
            self.store.audit(conn, ctx, "knowledge.search", "query")
            return hits

    def timeline(self, ctx: TenantContext, request: TimelineRequest) -> dict[str, Any]:
        """Page reviewed occurrence-dated events under a recorded-time cutoff."""
        self.store.require(ctx, "knowledge.search")
        if not isinstance(request, TimelineRequest):
            raise ValueError("invalid timeline request")
        allowed_sources = sorted(ctx.source_ids) if ctx.source_ids is not None else None
        visibility_sql = (
            " AND (" + _TIMELINE_UNSUPERSEDED_SQL + ")"
            if request.visibility == "unsuperseded" else ""
        )
        from_sql = (
            "FROM knowledge_events ev "
            "LEFT JOIN knowledge_projects p ON p.tenant_id=ev.tenant_id "
            "AND p.id=ev.project_id CROSS JOIN allowed "
        )
        project_sql = "AND ev.project_id=%s " if request.project_id is not None else ""
        where_sql = (
            "WHERE ev.starts_at>=%s AND ev.starts_at<%s "
            "AND ev.recorded_at<=allowed.cutoff "
            + project_sql
            + "AND " + _visible_assertion_sql("ev", "'event'", "ev.id") + " "
            + "AND (ev.project_id IS NULL OR "
            + _visible_assertion_sql("p", "'project'", "p.id") + ")"
            + visibility_sql
        )
        with self.store.transaction(ctx) as conn:
            clock = conn.execute("SELECT transaction_timestamp() AS now").fetchone()
            if clock is None:
                raise RuntimeError("timeline database clock unavailable")
            now = clock["now"]
            cutoff_at = (
                request.recorded_cutoff_at.astimezone(UTC)
                if request.recorded_cutoff_at else now
            )
            if cutoff_at > now:
                raise ValueError("invalid future timeline cutoff")
            params: tuple[Any, ...] = (
                request.start.astimezone(UTC), request.end.astimezone(UTC),
                *((request.project_id,) if request.project_id is not None else ()),
            )
            anchor = None
            if request.after is not None:
                anchor = conn.execute(
                    "WITH allowed AS (SELECT %s::text[] AS sources, "
                    "%s::timestamptz AS cutoff) "
                    "SELECT ev.starts_at,ev.id " + from_sql + where_sql + " AND ev.id=%s",
                    (allowed_sources, cutoff_at, *params, request.after),
                ).fetchone()
                if anchor is None:
                    raise NotFound()
            cursor_sql = (
                " AND (ev.starts_at,ev.id)>(%s,%s)" if anchor is not None else ""
            )
            rows = conn.execute(
                "WITH allowed AS (SELECT %s::text[] AS sources, "
                "%s::timestamptz AS cutoff) "
                "SELECT ev.id,ev.event_type,ev.title,ev.starts_at,ev.ends_at,"
                "ev.project_id " + from_sql + where_sql + cursor_sql
                + " ORDER BY ev.starts_at,ev.id LIMIT %s",
                (
                    allowed_sources, cutoff_at, *params,
                    *((anchor["starts_at"], anchor["id"]) if anchor else ()),
                    request.limit + 1,
                ),
            ).fetchall()
            page = rows[:request.limit]
            evidence_by_event: dict[str, list[str]] = {row["id"]: [] for row in page}
            if page:
                evidence_rows = conn.execute(
                    "SELECT target_id,evidence_id FROM knowledge_evidence "
                    "WHERE target_kind='event' AND target_id=ANY(%s) "
                    "ORDER BY target_id,evidence_id",
                    (list(evidence_by_event),),
                ).fetchall()
                for evidence in evidence_rows:
                    evidence_by_event[evidence["target_id"]].append(evidence["evidence_id"])
            self.store.audit(conn, ctx, "knowledge.timeline_read", "event_window")
        return {
            "results": [
                {
                    "object_kind": "event",
                    "object_id": row["id"],
                    "event_type": row["event_type"],
                    "title": row["title"],
                    "starts_at": row["starts_at"],
                    "ends_at": row["ends_at"],
                    "project_id": row["project_id"],
                    "evidence_ids": evidence_by_event[row["id"]],
                }
                for row in page
            ],
            "next_cursor": page[-1]["id"] if len(rows) > request.limit and page else None,
            "recorded_cutoff_at": cutoff_at,
            "limit": request.limit,
            "visibility": request.visibility,
            "coverage": {
                "undated_events": "excluded",
                "source_freshness": "not_asserted",
                "interpretation": "reviewed_assertions",
            },
            "untrusted_content": True,
        }

    def commitments_due(
        self, ctx: TenantContext, request: DueCommitmentsRequest
    ) -> dict[str, Any]:
        """Page reviewed due dates without treating them as source freshness."""
        self.store.require(ctx, "knowledge.search")
        if not isinstance(request, DueCommitmentsRequest):
            raise ValueError("invalid due request")
        allowed_sources = sorted(ctx.source_ids) if ctx.source_ids is not None else None
        visibility_sql = (
            " AND (" + _DUE_UNSUPERSEDED_SQL + ")"
            if request.visibility == "unsuperseded" else ""
        )
        project_sql = "AND cm.project_id=%s " if request.project_id is not None else ""
        state_sql = "AND cm.state=%s " if request.state is not None else ""
        where_sql = (
            "WHERE cm.due_at>=%s AND cm.due_at<%s "
            "AND cm.recorded_at<=allowed.cutoff "
            + project_sql + state_sql
            + "AND (" + _visible_commitment_sql("cm") + ")"
            + visibility_sql
        )
        with self.store.transaction(ctx) as conn:
            clock = conn.execute("SELECT transaction_timestamp() AS now").fetchone()
            if clock is None:
                raise RuntimeError("due database clock unavailable")
            now = clock["now"]
            cutoff_at = (
                request.recorded_cutoff_at.astimezone(UTC)
                if request.recorded_cutoff_at else now
            )
            if cutoff_at > now:
                raise ValueError("invalid future due cutoff")
            params: tuple[Any, ...] = (
                request.start.astimezone(UTC), request.end.astimezone(UTC),
                *((request.project_id,) if request.project_id is not None else ()),
                *((request.state,) if request.state is not None else ()),
            )
            common_sql = (
                "WITH allowed AS (SELECT %s::text[] AS sources, "
                "%s::timestamptz AS cutoff) "
            )
            from_sql = "FROM knowledge_commitments cm CROSS JOIN allowed "
            anchor = None
            if request.after is not None:
                anchor = conn.execute(
                    common_sql + "SELECT cm.due_at,cm.id " + from_sql
                    + where_sql + " AND cm.id=%s",
                    (allowed_sources, cutoff_at, *params, request.after),
                ).fetchone()
                if anchor is None:
                    raise NotFound()
            cursor_sql = " AND (cm.due_at,cm.id)>(%s,%s)" if anchor else ""
            rows = conn.execute(
                common_sql
                + "SELECT cm.id,cm.description,cm.state,cm.due_at,"
                "cm.project_id,cm.owner_entity_id,cm.counterparty_entity_id "
                + from_sql + where_sql + cursor_sql
                + " ORDER BY cm.due_at,cm.id LIMIT %s",
                (
                    allowed_sources, cutoff_at, *params,
                    *((anchor["due_at"], anchor["id"]) if anchor else ()),
                    request.limit + 1,
                ),
            ).fetchall()
            page = rows[:request.limit]
            evidence_by_commitment: dict[str, list[str]] = {
                row["id"]: [] for row in page
            }
            if page:
                evidence_rows = conn.execute(
                    "SELECT target_id,evidence_id FROM knowledge_evidence "
                    "WHERE target_kind='commitment' AND target_id=ANY(%s) "
                    "ORDER BY target_id,evidence_id",
                    (list(evidence_by_commitment),),
                ).fetchall()
                for evidence in evidence_rows:
                    evidence_by_commitment[evidence["target_id"]].append(
                        evidence["evidence_id"]
                    )
            self.store.audit(conn, ctx, "knowledge.commitments_due_read", "due_window")
        return {
            "results": [
                {
                    "object_kind": "commitment",
                    "object_id": row["id"],
                    "summary": row["description"][:300],
                    "summary_truncated": len(row["description"]) > 300,
                    "state": row["state"],
                    "due_at": row["due_at"],
                    "project_id": row["project_id"],
                    "owner_entity_id": row["owner_entity_id"],
                    "counterparty_entity_id": row["counterparty_entity_id"],
                    "evidence_ids": evidence_by_commitment[row["id"]],
                }
                for row in page
            ],
            "next_cursor": page[-1]["id"] if len(rows) > request.limit and page else None,
            "recorded_cutoff_at": cutoff_at,
            "limit": request.limit,
            "visibility": request.visibility,
            "state_filter": request.state,
            "coverage": {
                "undated_commitments": "excluded",
                "source_freshness": "not_asserted",
                "interpretation": "reviewed_assertions",
            },
            "untrusted_content": True,
        }

    def changes(
        self, ctx: TenantContext, *, after: str | None = None, limit: int = 25
    ) -> dict[str, Any]:
        self.store.require(ctx, "knowledge.changes.read")
        if after is not None and not re.fullmatch(r"kchange_[a-f0-9]{32}", after):
            raise NotFound()
        if not 1 <= limit <= 50:
            raise ValueError("invalid change limit")
        allowed_sources = sorted(ctx.source_ids) if ctx.source_ids is not None else None
        with self.store.transaction(ctx) as conn:
            anchor = None
            if after:
                anchor = conn.execute(
                    "SELECT c.recorded_at,c.id FROM knowledge_change_events c WHERE c.id=%s "
                    "AND (%s::text[] IS NULL OR ("
                    "EXISTS (SELECT 1 FROM knowledge_evidence ke "
                    "WHERE ke.tenant_id=c.tenant_id AND ke.target_kind=c.object_kind "
                    "AND ke.target_id=c.object_id) AND NOT EXISTS ("
                    "SELECT 1 FROM knowledge_evidence ke JOIN brain_evidence e "
                    "ON e.tenant_id=ke.tenant_id AND e.id=ke.evidence_id "
                    "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
                    "AND v.id=e.source_version_id WHERE ke.tenant_id=c.tenant_id "
                    "AND ke.target_kind=c.object_kind AND ke.target_id=c.object_id "
                    "AND v.source_id<>ALL(%s::text[]))))",
                    (after, allowed_sources, allowed_sources),
                ).fetchone()
                if not anchor:
                    raise NotFound()
            rows = conn.execute(
                "SELECT c.id,c.object_kind,c.object_id,c.recorded_at "
                "FROM knowledge_change_events c "
                "WHERE (%s::timestamptz IS NULL OR (c.recorded_at,c.id)>(%s,%s)) "
                "AND (%s::text[] IS NULL OR ("
                "EXISTS (SELECT 1 FROM knowledge_evidence ke "
                "WHERE ke.tenant_id=c.tenant_id AND ke.target_kind=c.object_kind "
                "AND ke.target_id=c.object_id) AND NOT EXISTS ("
                "SELECT 1 FROM knowledge_evidence ke JOIN brain_evidence e "
                "ON e.tenant_id=ke.tenant_id AND e.id=ke.evidence_id "
                "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
                "AND v.id=e.source_version_id WHERE ke.tenant_id=c.tenant_id "
                "AND ke.target_kind=c.object_kind AND ke.target_id=c.object_id "
                "AND v.source_id<>ALL(%s::text[])))) "
                "ORDER BY c.recorded_at,c.id LIMIT %s",
                (
                    anchor["recorded_at"] if anchor else None,
                    anchor["recorded_at"] if anchor else None,
                    after,
                    allowed_sources,
                    allowed_sources,
                    limit + 1,
                ),
            ).fetchall()
            self.store.audit(conn, ctx, "knowledge.changes_read", "change_feed")
        page = rows[:limit]
        return {
            "results": page,
            "next_cursor": page[-1]["id"] if len(rows) > limit and page else None,
            "limit": limit,
        }
