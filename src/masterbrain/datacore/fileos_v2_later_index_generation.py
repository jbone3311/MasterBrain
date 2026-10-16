"""Shared, historical FileOS v2 later-run index generation; never activate."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from email_brain.auth import Principal
from email_brain.store import AccessDenied, Conflict, NotFound
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.fileos_v2_later_run_completion import FileOSV2LaterRunCompleter
from masterbrain.datacore.persistence import (
    _IDENTITY,
    INDEX_CHUNKER_VERSION,
    MAX_GENERATION_CHUNKS,
    MAX_GENERATION_TEXT_BYTES,
    DataCoreStore,
    SearchHit,
    _canonical_digest,
    _search_fileos_generation,
    deterministic_chunks,
)


@dataclass(frozen=True, slots=True)
class FileOSV2LaterIndexGeneration:
    generation_id: str
    source_id: str
    run_id: UUID
    attempt_id: UUID
    item_count: int
    document_count: int
    chunk_count: int
    plan_sha256: str
    ready_at: datetime
    recorded: bool
    current_read_active: bool = False


@dataclass(frozen=True, slots=True)
class FileOSV2LaterSearchPreview:
    source_id: str
    run_id: UUID
    candidate_generation_id: str
    active_v1_generation_id: str | None
    review_flags: dict[str, bool]
    active_v1_hits: tuple[SearchHit, ...]
    candidate_hits: tuple[SearchHit, ...]
    candidate_visibility: str = "historical_preview"


class FileOSV2LaterSearchReviewer:
    """Human-only comparison; a ready generation is never a current source."""

    def __init__(self, core: DataCoreStore) -> None:
        self.core = core
        self.runs = FileOSV2LaterRunCompleter(core)

    def preview(
        self, principal: Principal, source_id: str, generation_id: str,
        query: str, *, limit: int = 10,
    ) -> FileOSV2LaterSearchPreview:
        if principal.client_kind != "human":
            raise AccessDenied("human FileOS later transition review required")
        ctx = principal.context
        for scope in (
            "brain.fileos.transition.review", "brain.search", "brain.evidence.read"
        ):
            self.core.store.require(ctx, scope)
        if (
            not isinstance(source_id, str) or not _IDENTITY.fullmatch(source_id)
            or not isinstance(generation_id, str)
            or not _IDENTITY.fullmatch(generation_id)
            or not isinstance(query, str) or not query.strip()
            or len(query) > 500 or "\x00" in query
            or not isinstance(limit, int) or isinstance(limit, bool)
            or not 1 <= limit <= 50
        ):
            raise ValueError("invalid FileOS v2 later search preview")
        if ctx.source_ids is not None and source_id not in ctx.source_ids:
            raise NotFound()
        with self.core.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:fileos-source:{source_id}",),
            )
            candidate = conn.execute(
                "SELECT g.id,g.v2_later_run_id,g.v2_later_run_sha256,"
                "r.attempt_id,r.baseline_completion_id,r.root_binding_sha256 "
                "FROM brain_index_generations g "
                "JOIN brain_index_generation_receipts ready "
                "ON ready.tenant_id=g.tenant_id AND ready.generation_id=g.id "
                "AND ready.ready_at IS NOT NULL "
                "JOIN brain_fileos_v2_later_run_completions r "
                "ON r.tenant_id=g.tenant_id AND r.id=g.v2_later_run_id "
                "AND r.attempt_id=g.v2_later_attempt_id "
                "AND r.run_sha256=g.v2_later_run_sha256 "
                "WHERE g.tenant_id=%s AND g.id=%s AND g.source_id=%s "
                "AND g.basis_kind='v2_later'",
                (ctx.tenant_id, generation_id, source_id),
            ).fetchone()
            if candidate is None:
                raise NotFound()
            run = self.runs._saved(
                conn, candidate["v2_later_run_id"], candidate["attempt_id"],
                None, None,
            )
            baseline = conn.execute(
                "SELECT c.prior_run_id,s.prior_actor_id,s.prior_observed_at "
                "FROM brain_fileos_v2_baseline_completions c "
                "JOIN brain_fileos_v2_staged_inventories s "
                "ON s.tenant_id=c.tenant_id AND s.id=c.stage_id "
                "WHERE c.id=%s", (candidate["baseline_completion_id"],),
            ).fetchone()
            latest = conn.execute(
                "SELECT actor_id,run_id,observed_at,root_binding_sha256 "
                "FROM brain_fileos_run_receipts WHERE source_id=%s "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            source = conn.execute(
                "SELECT root_binding_sha256,status FROM brain_sources "
                "WHERE id=%s AND kind='fileos'", (source_id,),
            ).fetchone()
            if (
                run is None or run.run_sha256 != candidate["v2_later_run_sha256"]
                or baseline is None or latest is None or source is None
                or source["status"] != "active"
                or latest["actor_id"] != baseline["prior_actor_id"]
                or latest["run_id"] != baseline["prior_run_id"]
                or latest["observed_at"] != baseline["prior_observed_at"]
                or latest["root_binding_sha256"] != candidate["root_binding_sha256"]
                or source["root_binding_sha256"] != candidate["root_binding_sha256"]
            ):
                raise Conflict("FileOS v2 later search basis requires review")
            active = conn.execute(
                "SELECT a.generation_id,g.basis_kind FROM brain_index_activations a "
                "JOIN brain_index_generations g ON g.tenant_id=a.tenant_id "
                "AND g.id=a.generation_id WHERE a.source_id=%s "
                "ORDER BY a.activated_at DESC,a.idempotency_key DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            if active is not None and active["basis_kind"] != "v1":
                raise Conflict("FileOS v2 later current policy requires review")
            active_id = active["generation_id"] if active else None
            active_hits = (
                _search_fileos_generation(conn, ctx.tenant_id, active_id, query, limit)
                if active_id is not None else []
            )
            candidate_hits = _search_fileos_generation(
                conn, ctx.tenant_id, generation_id, query, limit
            )
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_search_preview",
                "index_generation", generation_id,
            )
            return FileOSV2LaterSearchPreview(
                source_id, run.run_id, generation_id, active_id,
                dict(run.review_flags), tuple(active_hits), tuple(candidate_hits),
            )


class FileOSV2LaterIndexBuilder:
    def __init__(self, core: DataCoreStore) -> None:
        self.core = core
        self.runs = FileOSV2LaterRunCompleter(core)

    def build(
        self,
        principal: Principal,
        run_id: UUID,
        *,
        code_revision: str,
        authorize: Callable[[], None] | None = None,
    ) -> FileOSV2LaterIndexGeneration:
        if principal.client_kind != "worker":
            raise AccessDenied("FileOS v2 later index worker required")
        ctx = principal.context
        for scope in (
            "brain.fileos.transition.index", "brain.document.publish", "brain.changes.read"
        ):
            self.core.store.require(ctx, scope)
        if (
            not isinstance(run_id, UUID)
            or not isinstance(code_revision, str)
            or not code_revision
            or len(code_revision) > 200
            or "\x00" in code_revision
        ):
            raise ValueError("invalid FileOS v2 later index request")
        if authorize is not None:
            authorize()
        with self.core.store.transaction(ctx) as conn:
            run = conn.execute(
                "SELECT r.id,r.attempt_id,r.preparation_id,r.packet_id,"
                "r.baseline_completion_id,r.source_id,r.root_binding_sha256,"
                "r.attempt_sha256,r.run_sha256,r.observed_at,"
                "p.hashed_count,p.policy_sha256,q.packet->'candidate'->'counts' "
                "AS observation_counts "
                "FROM brain_fileos_v2_later_run_completions r "
                "JOIN brain_fileos_v2_later_evidence_preparations p "
                "ON p.tenant_id=r.tenant_id AND p.id=r.preparation_id "
                "JOIN brain_fileos_v2_later_observation_packets q "
                "ON q.tenant_id=r.tenant_id AND q.id=r.packet_id "
                "WHERE r.id=%s", (run_id,),
            ).fetchone()
            if run is None:
                raise NotFound()
            source_id = run["source_id"]
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:fileos-source:{source_id}",),
            )
            inspected = self.runs._saved(conn, run_id, run["attempt_id"], None, None)
            if inspected is None or inspected.run_sha256 != run["run_sha256"]:
                raise Conflict("FileOS v2 later index run requires review")
            baseline = conn.execute(
                "SELECT c.prior_run_id,s.prior_actor_id,s.prior_observed_at "
                "FROM brain_fileos_v2_baseline_completions c "
                "JOIN brain_fileos_v2_staged_inventories s "
                "ON s.tenant_id=c.tenant_id AND s.id=c.stage_id WHERE c.id=%s",
                (run["baseline_completion_id"],),
            ).fetchone()
            latest = conn.execute(
                "SELECT actor_id,run_id,observed_at,root_binding_sha256 "
                "FROM brain_fileos_run_receipts WHERE source_id=%s "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            source = conn.execute(
                "SELECT root_binding_sha256 FROM brain_sources "
                "WHERE id=%s AND kind='fileos'", (source_id,),
            ).fetchone()
            if (
                baseline is None or latest is None or source is None
                or latest["actor_id"] != baseline["prior_actor_id"]
                or latest["run_id"] != baseline["prior_run_id"]
                or latest["observed_at"] != baseline["prior_observed_at"]
                or latest["root_binding_sha256"] != run["root_binding_sha256"]
                or source["root_binding_sha256"] != run["root_binding_sha256"]
            ):
                raise Conflict("FileOS v2 later index basis requires review")
            rows = conn.execute(
                "SELECT item_id,prepared_version_id,evidence_id,outcome,document_id "
                "FROM brain_fileos_v2_later_document_attempt_items "
                "WHERE attempt_id=%s AND kind='hashed' ORDER BY item_id",
                (run["attempt_id"],),
            ).fetchall()
            if len(rows) != run["hashed_count"] or len(rows) > 20000:
                raise Conflict("FileOS v2 later index item ledger is incomplete")
            document_ids = [row["document_id"] for row in rows if row["document_id"]]
            documents: dict[str, dict[str, Any]] = {}
            for offset in range(0, len(document_ids), 250):
                page = conn.execute(
                    "SELECT id,evidence_id,normalizer,body_sha256,body "
                    "FROM brain_normalized_documents WHERE id=ANY(%s)",
                    (document_ids[offset:offset + 250],),
                ).fetchall()
                documents.update((document["id"], document) for document in page)
            plan_items: list[dict[str, Any]] = []
            generated_chunks: list[dict[str, Any]] = []
            text_bytes = 0
            document_count = 0
            for row in rows:
                if row["evidence_id"] != stable_id("evidence", row["prepared_version_id"]):
                    raise Conflict("FileOS v2 later index evidence identity changed")
                document_id = row["document_id"]
                body_sha = None
                if row["outcome"] == "extracted":
                    document = documents.get(document_id) if document_id else None
                    if document is None or document["evidence_id"] != row["evidence_id"]:
                        raise Conflict("FileOS v2 later extracted document is missing")
                    body = document["body"]
                    text_bytes += len(body.encode())
                    if text_bytes > MAX_GENERATION_TEXT_BYTES:
                        raise ValueError("FileOS v2 later index text bound exceeded")
                    body_sha = hashlib.sha256(body.encode()).hexdigest()
                    if (
                        document["body_sha256"] != body_sha
                        or document_id != stable_id(
                            "document", row["prepared_version_id"],
                            document["normalizer"], body_sha,
                        )
                    ):
                        raise Conflict("FileOS v2 later document identity changed")
                    document_count += 1
                    for ordinal, (start, end, text) in enumerate(deterministic_chunks(body)):
                        chunk_sha = hashlib.sha256(text.encode()).hexdigest()
                        generated_chunks.append({
                            "document_id": document_id,
                            "id": stable_id("chunk", document_id, str(ordinal), chunk_sha),
                            "ordinal": ordinal,
                            "start_offset": start,
                            "end_offset": end,
                            "text": text,
                            "sha256": chunk_sha,
                        })
                        if len(generated_chunks) > MAX_GENERATION_CHUNKS:
                            raise ValueError("FileOS v2 later index chunk bound exceeded")
                elif document_id is not None:
                    raise Conflict("FileOS v2 later nonextracted item has a document")
                plan_items.append({
                    "item_id": row["item_id"],
                    "version_id": row["prepared_version_id"],
                    "evidence_id": row["evidence_id"],
                    "outcome": row["outcome"],
                    "document_id": document_id,
                    "body_sha256": body_sha,
                    "disposition": "indexed" if document_id else "not_indexed",
                })
            plan_sha = _canonical_digest({
                "basis_kind": "v2_later",
                "source_id": source_id,
                "run_id": str(run_id),
                "run_sha256": run["run_sha256"],
                "attempt_id": str(run["attempt_id"]),
                "attempt_sha256": run["attempt_sha256"],
                "policy_sha256": run["policy_sha256"],
                "observation_counts": run["observation_counts"],
                "code_revision": code_revision,
                "chunker_version": INDEX_CHUNKER_VERSION,
                "items": plan_items,
            })
            generation_id = stable_id(
                "index_generation_v2_later", source_id, str(run_id),
                str(run["attempt_id"]), INDEX_CHUNKER_VERSION, plan_sha,
            )
            existing = conn.execute(
                "SELECT g.basis_kind,g.v2_later_run_id,g.v2_later_attempt_id,"
                "g.plan_sha256,g.item_count,g.document_count,g.chunk_count,r.ready_at "
                "FROM brain_index_generations g "
                "LEFT JOIN brain_index_generation_receipts r "
                "ON r.tenant_id=g.tenant_id AND r.generation_id=g.id "
                "WHERE g.id=%s", (generation_id,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["basis_kind"] != "v2_later"
                    or existing["v2_later_run_id"] != run_id
                    or existing["v2_later_attempt_id"] != run["attempt_id"]
                    or existing["plan_sha256"] != plan_sha
                    or existing["item_count"] != len(rows)
                    or existing["document_count"] != document_count
                    or existing["chunk_count"] != len(generated_chunks)
                    or existing["ready_at"] is None
                ):
                    raise Conflict("FileOS v2 later index identity changed")
                self.core.store.audit(
                    conn, ctx, "brain.fileos_v2_later_index_replay",
                    "index_generation", generation_id,
                )
                return FileOSV2LaterIndexGeneration(
                    generation_id, source_id, run_id, run["attempt_id"],
                    len(rows), document_count, len(generated_chunks), plan_sha,
                    existing["ready_at"], False,
                )
            if authorize is not None:
                authorize()
            conn.execute(
                "INSERT INTO brain_index_generations(tenant_id,id,source_id,"
                "run_actor_id,run_id,observed_at,plan_sha256,code_revision,"
                "chunker_version,item_count,document_count,chunk_count,basis_kind,"
                "v2_later_run_id,v2_later_attempt_id,v2_later_run_sha256,"
                "v2_later_attempt_sha256,v2_later_observation_counts) VALUES ("
                "%s,%s,%s,NULL,NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id, generation_id, source_id, run["observed_at"],
                    plan_sha, code_revision, INDEX_CHUNKER_VERSION, len(rows),
                    document_count, len(generated_chunks), "v2_later", run_id,
                    run["attempt_id"], run["run_sha256"], run["attempt_sha256"],
                    Jsonb(run["observation_counts"]),
                ),
            )
            for item in plan_items:
                conn.execute(
                    "INSERT INTO brain_index_generation_items(tenant_id,generation_id,"
                    "source_id,item_id,version_id,outcome,disposition,evidence_id,document_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id, generation_id, source_id, item["item_id"],
                        item["version_id"], item["outcome"], item["disposition"],
                        item["evidence_id"], item["document_id"],
                    ),
                )
            for chunk in generated_chunks:
                conn.execute(
                    "INSERT INTO brain_index_generation_chunks(tenant_id,generation_id,"
                    "source_id,document_id,id,ordinal,start_offset,end_offset,text,sha256) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id, generation_id, source_id, chunk["document_id"],
                        chunk["id"], chunk["ordinal"], chunk["start_offset"],
                        chunk["end_offset"], chunk["text"], chunk["sha256"],
                    ),
                )
            if authorize is not None:
                authorize()
            receipt = conn.execute(
                "INSERT INTO brain_index_generation_receipts(tenant_id,generation_id,source_id) "
                "VALUES (%s,%s,%s) RETURNING ready_at",
                (ctx.tenant_id, generation_id, source_id),
            ).fetchone()
            assert receipt is not None
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_index_ready",
                "index_generation", generation_id,
            )
            return FileOSV2LaterIndexGeneration(
                generation_id, source_id, run_id, run["attempt_id"],
                len(rows), document_count, len(generated_chunks), plan_sha,
                receipt["ready_at"], True,
            )
