"""Reviewed, append-only KnowledgeCore persistence and retrieval."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
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
    EntityWrite,
    EventWrite,
    KnowledgeAssertion,
    ProjectWrite,
    RelationshipWrite,
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
        with self.store.transaction(ctx) as conn:
            row = conn.execute(f"SELECT * FROM {table} WHERE id=%s", (object_id,)).fetchone()
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
        self, ctx: TenantContext, query: str, *, limit: int = 10, kinds: list[str] | None = None
    ) -> list[KnowledgeHit]:
        self.store.require(ctx, "knowledge.search")
        selected = kinds or []
        if not query.strip() or len(query) > 500 or not 1 <= limit <= 50:
            raise ValueError("invalid knowledge search")
        if any(kind not in _TABLES for kind in selected) or len(set(selected)) != len(selected):
            raise ValueError("invalid knowledge kinds")
        allowed_sources = sorted(ctx.source_ids) if ctx.source_ids is not None else None
        with self.store.transaction(ctx) as conn:
            rows = conn.execute(
                "SELECT k.object_kind,k.object_id,k.title,"
                "ts_headline('simple',k.body,plainto_tsquery('simple',%s),"
                "'MaxWords=35,MinWords=10,StartSel=\"\",StopSel=\"\"') AS excerpt,"
                "ts_rank_cd(k.search_vector,plainto_tsquery('simple',%s)) AS rank "
                "FROM knowledge_search_documents k WHERE k.search_vector @@ "
                "plainto_tsquery('simple',%s) "
                "AND (cardinality(%s::text[])=0 OR k.object_kind=ANY(%s)) "
                "AND (%s::text[] IS NULL OR ("
                "EXISTS (SELECT 1 FROM knowledge_evidence ke "
                "WHERE ke.tenant_id=k.tenant_id AND ke.target_kind=k.object_kind "
                "AND ke.target_id=k.object_id) AND NOT EXISTS ("
                "SELECT 1 FROM knowledge_evidence ke "
                "JOIN brain_evidence e ON e.tenant_id=ke.tenant_id "
                "AND e.id=ke.evidence_id JOIN brain_source_versions v "
                "ON v.tenant_id=e.tenant_id AND v.id=e.source_version_id "
                "WHERE ke.tenant_id=k.tenant_id AND ke.target_kind=k.object_kind "
                "AND ke.target_id=k.object_id AND v.source_id<>ALL(%s::text[])))) "
                "ORDER BY rank DESC,k.object_kind,k.object_id LIMIT %s",
                (
                    query, query, query, selected, selected, allowed_sources,
                    allowed_sources, limit,
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

    def changes(
        self, ctx: TenantContext, *, after: str | None = None, limit: int = 25
    ) -> dict[str, Any]:
        self.store.require(ctx, "knowledge.changes.read")
        if after is not None and not re.fullmatch(r"kchange_[a-f0-9]{32}", after):
            raise NotFound()
        if not 1 <= limit <= 50:
            raise ValueError("invalid change limit")
        with self.store.transaction(ctx) as conn:
            anchor = None
            if after:
                anchor = conn.execute(
                    "SELECT recorded_at,id FROM knowledge_change_events WHERE id=%s", (after,)
                ).fetchone()
                if not anchor:
                    raise NotFound()
            rows = conn.execute(
                "SELECT id,object_kind,object_id,recorded_at FROM knowledge_change_events "
                "WHERE (%s::timestamptz IS NULL OR (recorded_at,id)>(%s,%s)) "
                "ORDER BY recorded_at,id LIMIT %s",
                (
                    anchor["recorded_at"] if anchor else None,
                    anchor["recorded_at"] if anchor else None,
                    after,
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
