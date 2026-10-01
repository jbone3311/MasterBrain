"""Build private FileOS v2 lexical generations in the shared DataCore index.

The generation is an immutable historical derivative. PostgreSQL refuses its
activation until a later, separately reviewed current-visibility decision.
"""

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
from masterbrain.datacore.persistence import (
    INDEX_CHUNKER_VERSION,
    MAX_GENERATION_CHUNKS,
    MAX_GENERATION_TEXT_BYTES,
    DataCoreStore,
    _canonical_digest,
    deterministic_chunks,
)


@dataclass(frozen=True, slots=True)
class FileOSV2IndexGeneration:
    generation_id: str
    source_id: str
    completion_id: UUID
    attempt_id: UUID
    item_count: int
    document_count: int
    chunk_count: int
    plan_sha256: str
    ready_at: datetime
    recorded: bool


class FileOSV2IndexBuilder:
    def __init__(self, core: DataCoreStore) -> None:
        self.core = core

    def build(
        self,
        principal: Principal,
        completion_id: UUID,
        attempt_id: UUID,
        *,
        code_revision: str,
        authorize: Callable[[], None] | None = None,
    ) -> FileOSV2IndexGeneration:
        if principal.client_kind != "worker":
            raise AccessDenied("FileOS v2 index worker required")
        ctx = principal.context
        for scope in (
            "brain.fileos.transition.index",
            "brain.document.publish",
            "brain.changes.read",
        ):
            self.core.store.require(ctx, scope)
        if (
            not isinstance(completion_id, UUID)
            or not isinstance(attempt_id, UUID)
            or not isinstance(code_revision, str)
            or not code_revision
            or len(code_revision) > 200
            or "\x00" in code_revision
        ):
            raise ValueError("invalid FileOS v2 index request")
        if authorize is not None:
            authorize()
        with self.core.store.transaction(ctx) as conn:
            basis = conn.execute(
                "SELECT a.id AS attempt_id,a.attempt_sha256,a.ready,a.counts AS attempt_counts,"
                "c.id AS completion_id,c.stage_id,c.source_id,c.completion_sha256,"
                "c.policy_sha256,c.counts AS stage_counts,c.hashed_count,"
                "c.fresh_observed_at,c.prior_run_id,c.root_binding_sha256,"
                "s.prior_actor_id,s.prior_observed_at "
                "FROM brain_fileos_v2_document_attempts a "
                "JOIN brain_fileos_v2_baseline_completions c "
                "ON c.tenant_id=a.tenant_id AND c.id=a.completion_id "
                "JOIN brain_fileos_v2_staged_inventories s "
                "ON s.tenant_id=c.tenant_id AND s.id=c.stage_id "
                "WHERE a.tenant_id=%s AND a.id=%s AND a.completion_id=%s",
                (ctx.tenant_id, attempt_id, completion_id),
            ).fetchone()
            if basis is None:
                raise NotFound()
            source_id = basis["source_id"]
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:fileos-source:{source_id}",),
            )
            # The source lock is also taken by new v1 completions and the SQL
            # generation guard. A read-time match is not future root attestation.
            latest = conn.execute(
                "SELECT actor_id,run_id,observed_at,root_binding_sha256 "
                "FROM brain_fileos_run_receipts "
                "WHERE tenant_id=%s AND source_id=%s "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (ctx.tenant_id, source_id),
            ).fetchone()
            source = conn.execute(
                "SELECT root_binding_sha256 FROM brain_sources "
                "WHERE tenant_id=%s AND id=%s AND kind='fileos'",
                (ctx.tenant_id, source_id),
            ).fetchone()
            if (
                not basis["ready"]
                or latest is None
                or source is None
                or latest["actor_id"] != basis["prior_actor_id"]
                or latest["run_id"] != basis["prior_run_id"]
                or latest["observed_at"] != basis["prior_observed_at"]
                or latest["root_binding_sha256"] != basis["root_binding_sha256"]
                or source["root_binding_sha256"] != basis["root_binding_sha256"]
            ):
                raise Conflict("FileOS v2 index basis requires review")
            rows = conn.execute(
                "SELECT i.item_id,i.prepared_version_id,i.evidence_id,i.outcome,"
                "i.document_id,d.normalizer,d.body_sha256,d.body "
                "FROM brain_fileos_v2_document_attempt_items i "
                "LEFT JOIN brain_normalized_documents d ON d.tenant_id=i.tenant_id "
                "AND d.id=i.document_id AND d.evidence_id=i.evidence_id "
                "WHERE i.tenant_id=%s AND i.attempt_id=%s ORDER BY i.item_id",
                (ctx.tenant_id, attempt_id),
            ).fetchall()
            if len(rows) != basis["hashed_count"] or basis["hashed_count"] > 20000:
                raise Conflict("FileOS v2 index item ledger is incomplete")
            plan_items: list[dict[str, Any]] = []
            generated_chunks: list[dict[str, Any]] = []
            text_bytes = 0
            document_count = 0
            for row in rows:
                if row["evidence_id"] != stable_id("evidence", row["prepared_version_id"]):
                    raise Conflict("FileOS v2 index evidence identity changed")
                document_id = row["document_id"]
                body_sha = None
                if row["outcome"] == "extracted":
                    if document_id is None or row["body"] is None:
                        raise Conflict("FileOS v2 extracted document is missing")
                    body = row["body"]
                    text_bytes += len(body.encode())
                    if text_bytes > MAX_GENERATION_TEXT_BYTES:
                        raise ValueError("FileOS v2 index text bound exceeded")
                    body_sha = hashlib.sha256(body.encode()).hexdigest()
                    if (
                        row["body_sha256"] != body_sha
                        or document_id != stable_id(
                            "document", row["prepared_version_id"],
                            row["normalizer"], body_sha,
                        )
                    ):
                        raise Conflict("FileOS v2 normalized document identity changed")
                    document_count += 1
                    for ordinal, (start, end, text) in enumerate(deterministic_chunks(body)):
                        chunk_sha = hashlib.sha256(text.encode()).hexdigest()
                        generated_chunks.append(
                            {
                                "document_id": document_id,
                                "id": stable_id("chunk", document_id, str(ordinal), chunk_sha),
                                "ordinal": ordinal,
                                "start_offset": start,
                                "end_offset": end,
                                "text": text,
                                "sha256": chunk_sha,
                            }
                        )
                        if len(generated_chunks) > MAX_GENERATION_CHUNKS:
                            raise ValueError("FileOS v2 index chunk bound exceeded")
                elif document_id is not None:
                    raise Conflict("FileOS v2 nonextracted item has a document")
                plan_items.append(
                    {
                        "item_id": row["item_id"],
                        "version_id": row["prepared_version_id"],
                        "evidence_id": row["evidence_id"],
                        "outcome": row["outcome"],
                        "document_id": document_id,
                        "body_sha256": body_sha,
                        "disposition": "indexed" if document_id is not None else "not_indexed",
                    }
                )
            plan_sha = _canonical_digest(
                {
                    "basis_kind": "v2",
                    "source_id": source_id,
                    "completion_id": str(completion_id),
                    "completion_sha256": basis["completion_sha256"],
                    "attempt_id": str(attempt_id),
                    "attempt_sha256": basis["attempt_sha256"],
                    "policy_sha256": basis["policy_sha256"],
                    "stage_counts": basis["stage_counts"],
                    "code_revision": code_revision,
                    "chunker_version": INDEX_CHUNKER_VERSION,
                    "items": plan_items,
                }
            )
            generation_id = stable_id(
                "index_generation_v2", source_id, str(completion_id),
                str(attempt_id), INDEX_CHUNKER_VERSION, plan_sha,
            )
            existing = conn.execute(
                "SELECT g.basis_kind,g.v2_completion_id,g.v2_attempt_id,g.plan_sha256,"
                "g.item_count,g.document_count,g.chunk_count,r.ready_at "
                "FROM brain_index_generations g "
                "LEFT JOIN brain_index_generation_receipts r "
                "ON r.tenant_id=g.tenant_id AND r.generation_id=g.id "
                "WHERE g.tenant_id=%s AND g.id=%s",
                (ctx.tenant_id, generation_id),
            ).fetchone()
            if existing is not None:
                if (
                    existing["basis_kind"] != "v2"
                    or existing["v2_completion_id"] != completion_id
                    or existing["v2_attempt_id"] != attempt_id
                    or existing["plan_sha256"] != plan_sha
                    or existing["item_count"] != len(rows)
                    or existing["document_count"] != document_count
                    or existing["chunk_count"] != len(generated_chunks)
                    or existing["ready_at"] is None
                ):
                    raise Conflict("FileOS v2 index generation identity changed")
                self.core.store.audit(
                    conn, ctx, "brain.fileos_v2_index_replay", "index_generation", generation_id,
                )
                return FileOSV2IndexGeneration(
                    generation_id, source_id, completion_id, attempt_id,
                    len(rows), document_count, len(generated_chunks), plan_sha,
                    existing["ready_at"], False,
                )
            if authorize is not None:
                authorize()
            conn.execute(
                "INSERT INTO brain_index_generations(tenant_id,id,source_id,run_actor_id,"
                "run_id,observed_at,plan_sha256,code_revision,chunker_version,item_count,"
                "document_count,chunk_count,basis_kind,v2_stage_id,v2_completion_id,"
                "v2_attempt_id,v2_completion_sha256,v2_attempt_sha256,v2_policy_sha256,"
                "v2_stage_counts) VALUES (%s,%s,%s,NULL,NULL,%s,%s,%s,%s,%s,%s,%s,"
                "%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id, generation_id, source_id, basis["fresh_observed_at"],
                    plan_sha, code_revision, INDEX_CHUNKER_VERSION, len(rows),
                    document_count, len(generated_chunks), "v2", basis["stage_id"],
                    completion_id, attempt_id, basis["completion_sha256"],
                    basis["attempt_sha256"], basis["policy_sha256"],
                    Jsonb(basis["stage_counts"]),
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
                conn, ctx, "brain.fileos_v2_index_ready", "index_generation", generation_id,
            )
            return FileOSV2IndexGeneration(
                generation_id, source_id, completion_id, attempt_id,
                len(rows), document_count, len(generated_chunks), plan_sha,
                receipt["ready_at"], True,
            )
