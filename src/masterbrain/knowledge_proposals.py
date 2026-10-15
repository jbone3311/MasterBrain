"""Private, explicitly reviewed KnowledgeCore proposal batches (ADR-186)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from psycopg.types.json import Jsonb
from pydantic import TypeAdapter, ValidationError

from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.datacore.contracts import stable_id
from masterbrain.knowledge import KnowledgeCore
from masterbrain.knowledge_schema import (
    CommitmentWrite,
    EventWrite,
    KnowledgeAssertion,
    KnowledgeProposalReviewRequest,
    KnowledgeProposalStageRequest,
    ProjectWrite,
)

_ASSERTION: TypeAdapter[KnowledgeAssertion] = TypeAdapter(KnowledgeAssertion)
_BATCH_ID = re.compile(r"^kbatch_[a-f0-9]{32}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_IMPORT_TABLES = {
    "project": "knowledge_projects",
    "event": "knowledge_events",
    "commitment": "knowledge_commitments",
}


def _sha(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _canonical(raw: dict[str, Any]) -> tuple[KnowledgeAssertion, dict[str, Any]]:
    if "reviewed" in raw:
        raise ValueError("proposal cannot claim review")
    try:
        assertion = _ASSERTION.validate_python({**raw, "reviewed": True})
    except ValidationError as exc:
        raise ValueError("invalid source-stated proposal") from exc
    payload = assertion.model_dump(mode="json")
    payload.pop("reviewed")
    return assertion, payload


@dataclass(slots=True)
class KnowledgeProposalBatches:
    store: Store

    @staticmethod
    def _human(ctx: TenantContext) -> None:
        if ctx.identity is not None and ctx.identity.client_kind != "human":
            raise AccessDenied("human identity required")

    @staticmethod
    def _visible_basis(
        conn: Any, ctx: TenantContext, assertion: KnowledgeAssertion,
        required_quote_evidence_id: str | None = None,
    ) -> None:
        """All evidence must be current, granted and unexcluded; quote exact in one."""
        evidence_ids = list(assertion.evidence_ids)
        allowed = sorted(ctx.source_ids) if ctx.source_ids is not None else None
        rows = conn.execute(
            "SELECT e.id, EXISTS (SELECT 1 FROM brain_normalized_documents d "
            "WHERE d.tenant_id=e.tenant_id AND d.evidence_id=e.id "
            "AND position(%s in d.body)>0) AS quote_matches "
            "FROM brain_evidence e "
            "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
            "AND v.id=e.source_version_id "
            "JOIN brain_source_items i ON i.tenant_id=v.tenant_id AND i.id=v.item_id "
            "AND i.source_id=v.source_id "
            "JOIN brain_sources s ON s.tenant_id=i.tenant_id AND s.id=i.source_id "
            "WHERE e.id=ANY(%s) AND i.current_version_id=v.id AND s.status='active' "
            "AND NOT public.brain_email_evidence_is_excluded(e.tenant_id,e.id) "
            "AND (%s::text[] IS NULL OR s.id=ANY(%s::text[]))",
            (assertion.source_quote, evidence_ids, allowed, allowed),
        ).fetchall()
        if {row["id"] for row in rows} != set(evidence_ids):
            raise NotFound()
        if not any(row["quote_matches"] for row in rows):
            raise ValueError("proposal quote lacks an exact source span")
        if required_quote_evidence_id is not None and not any(
            row["id"] == required_quote_evidence_id and row["quote_matches"]
            for row in rows
        ):
            raise ValueError("imported quote lacks its cited source span")
        if isinstance(assertion, ProjectWrite):
            for alias in assertion.aliases:
                matched = conn.execute(
                    "SELECT EXISTS (SELECT 1 FROM brain_normalized_documents d "
                    "WHERE d.tenant_id=%s AND d.evidence_id=%s "
                    "AND position(%s in d.body)>0) AS matched",
                    (ctx.tenant_id, alias.evidence_id, alias.source_quote),
                ).fetchone()
                if not matched or not matched["matched"]:
                    raise ValueError("proposal alias quote lacks an exact source span")

    def stage(
        self, ctx: TenantContext, body: KnowledgeProposalStageRequest,
        idempotency_key: UUID, *, import_context_sha256: str | None = None,
        import_claims: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        self.store.require(ctx, "knowledge.review")
        self._human(ctx)
        if not isinstance(idempotency_key, UUID):
            raise ValueError("UUID idempotency key required")
        if (import_context_sha256 is None) != (import_claims is None):
            raise ValueError("incomplete import binding")
        if import_context_sha256 is not None and (
            not isinstance(import_context_sha256, str)
            or not _SHA256.fullmatch(import_context_sha256)
            or not isinstance(import_claims, list)
            or len(import_claims) != len(body.proposals)
        ):
            raise ValueError("invalid import binding")
        parsed = [_canonical(raw) for raw in body.proposals]
        payloads = [payload for _, payload in parsed]
        request_sha = (
            _sha(payloads) if import_context_sha256 is None
            else _sha({"proposals": payloads,
                       "import_context_sha256": import_context_sha256})
        )
        batch_id = stable_id(
            "kbatch", str(ctx.tenant_id), str(ctx.actor_id), str(idempotency_key)
        )
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:kbatch:{ctx.actor_id}:{idempotency_key}",),
            )
            prior = conn.execute(
                "SELECT request_sha256,row_count,import_context_sha256 "
                "FROM knowledge_proposal_batches "
                "WHERE proposer_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if (prior["request_sha256"] != request_sha
                        or prior["row_count"] != len(parsed)
                        or prior["import_context_sha256"] != import_context_sha256):
                    raise Conflict("proposal batch idempotency key reused")
                self._rows(conn, ctx, batch_id)
                return {"batch_id": batch_id, "batch_sha256": request_sha,
                        "row_count": len(parsed), "changed": False, "reviewed": False}
            for ordinal, (assertion, _) in enumerate(parsed):
                claimed_id = citation_id = table = None
                if import_claims is not None:
                    claimed_id, citation_id = import_claims[ordinal]
                    table = _IMPORT_TABLES.get(assertion.kind)
                    if (table is None or citation_id not in assertion.evidence_ids
                            or not re.fullmatch(
                                rf"^{assertion.kind}_[a-f0-9]{{32}}", claimed_id,
                            )):
                        raise ValueError("invalid imported proposal claim")
                self._visible_basis(conn, ctx, assertion, citation_id)
                if table is not None and claimed_id is not None:
                    existing = conn.execute(
                        f"SELECT 1 FROM public.{table} "
                        "WHERE tenant_id=%s AND id=%s LIMIT 1",
                        (ctx.tenant_id, claimed_id),
                    ).fetchone()
                    if existing is not None:
                        raise Conflict("imported claim already exists")
                    if isinstance(assertion, (EventWrite, CommitmentWrite)):
                        project = conn.execute(
                            "SELECT 1 FROM public.knowledge_projects "
                            "WHERE tenant_id=%s AND id=%s LIMIT 1",
                            (ctx.tenant_id, assertion.project_id),
                        ).fetchone()
                        if project is None:
                            raise NotFound()
            conn.execute(
                "INSERT INTO knowledge_proposal_batches(tenant_id,id,proposer_id,"
                "idempotency_key,request_sha256,row_count,import_context_sha256) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, batch_id, ctx.actor_id, idempotency_key,
                 request_sha, len(parsed), import_context_sha256),
            )
            for ordinal, (assertion, payload) in enumerate(parsed):
                proposal_id = stable_id("kproposal", batch_id, str(ordinal))
                conn.execute(
                    "INSERT INTO knowledge_proposals(tenant_id,id,batch_id,ordinal,"
                    "payload,payload_sha256,evidence_count) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, proposal_id, batch_id, ordinal,
                     Jsonb(payload), _sha(payload), len(assertion.evidence_ids)),
                )
                for position, evidence_id in enumerate(assertion.evidence_ids):
                    conn.execute(
                        "INSERT INTO knowledge_proposal_evidence(tenant_id,proposal_id,"
                        "ordinal,evidence_id) VALUES (%s,%s,%s,%s)",
                        (ctx.tenant_id, proposal_id, position, evidence_id),
                    )
            self.store.audit(conn, ctx, "knowledge.proposal_batch_staged", "batch", batch_id)
        return {"batch_id": batch_id, "batch_sha256": request_sha,
                "row_count": len(parsed), "changed": True, "reviewed": False}

    @staticmethod
    def _rows(
        conn: Any, ctx: TenantContext, batch_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        header = conn.execute(
            "SELECT id,request_sha256,row_count,import_context_sha256 "
            "FROM knowledge_proposal_batches "
            "WHERE id=%s", (batch_id,),
        ).fetchone()
        if header is None:
            raise NotFound()
        rows = conn.execute(
            "SELECT p.id,p.ordinal,p.payload,p.payload_sha256,p.evidence_count,"
            "d.decision,d.reason,d.object_kind,d.object_id "
            "FROM knowledge_proposals p LEFT JOIN knowledge_proposal_decisions d "
            "ON d.tenant_id=p.tenant_id AND d.proposal_id=p.id "
            "WHERE p.batch_id=%s ORDER BY p.ordinal", (batch_id,),
        ).fetchall()
        if len(rows) != header["row_count"] or [r["ordinal"] for r in rows] != list(
            range(header["row_count"])
        ):
            raise Conflict("proposal batch is incomplete")
        payloads = []
        for row in rows:
            try:
                assertion, payload = _canonical(row["payload"])
            except ValueError as exc:
                raise Conflict("proposal payload is invalid") from exc
            if _sha(payload) != row["payload_sha256"]:
                raise Conflict("proposal digest mismatch")
            evidence_rows = conn.execute(
                "SELECT evidence_id FROM knowledge_proposal_evidence "
                "WHERE proposal_id=%s ORDER BY ordinal", (row["id"],),
            ).fetchall()
            if [item["evidence_id"] for item in evidence_rows] != list(assertion.evidence_ids):
                raise Conflict("proposal evidence mismatch")
            KnowledgeProposalBatches._visible_basis(conn, ctx, assertion)
            payloads.append(payload)
        expected_sha = (
            _sha(payloads) if header["import_context_sha256"] is None
            else _sha({"proposals": payloads,
                       "import_context_sha256": header["import_context_sha256"]})
        )
        if expected_sha != header["request_sha256"]:
            raise Conflict("proposal batch digest mismatch")
        return header, rows

    def preview(self, ctx: TenantContext, batch_id: str) -> dict[str, Any]:
        self.store.require(ctx, "knowledge.review")
        self.store.require(ctx, "brain.content.read")
        self._human(ctx)
        if not isinstance(batch_id, str) or not _BATCH_ID.fullmatch(batch_id):
            raise NotFound()
        with self.store.transaction(ctx) as conn:
            header, rows = self._rows(conn, ctx, batch_id)
            self.store.audit(conn, ctx, "knowledge.proposal_batch_read", "batch", batch_id)
            result = {
                "batch_id": batch_id, "batch_sha256": header["request_sha256"],
                "row_count": header["row_count"], "reviewed": False,
                "untrusted_content": True,
                "proposals": [
                    {"proposal_id": row["id"], "ordinal": row["ordinal"],
                     "assertion": row["payload"],
                     "status": row["decision"] or "proposed",
                     "reason": row["reason"], "object_kind": row["object_kind"],
                     "object_id": row["object_id"]}
                    for row in rows
                ],
            }
            if header["import_context_sha256"] is not None:
                result["import_context_sha256"] = header["import_context_sha256"]
            return result

    def review(
        self, ctx: TenantContext, batch_id: str,
        body: KnowledgeProposalReviewRequest, idempotency_key: UUID,
    ) -> dict[str, Any]:
        self.store.require(ctx, "knowledge.review")
        self._human(ctx)
        if not isinstance(batch_id, str) or not _BATCH_ID.fullmatch(batch_id):
            raise NotFound()
        if not isinstance(idempotency_key, UUID):
            raise ValueError("UUID idempotency key required")
        decisions = sorted(
            (item.model_dump() for item in body.decisions),
            key=lambda item: item["proposal_id"],
        )
        request_sha = _sha({"batch_id": batch_id, "batch_sha256": body.batch_sha256,
                            "decisions": decisions})
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:kbatch-review:{batch_id}",),
            )
            header, rows = self._rows(conn, ctx, batch_id)
            if header["request_sha256"] != body.batch_sha256:
                raise Conflict("proposal batch changed")
            if {item["proposal_id"] for item in decisions} != {row["id"] for row in rows}:
                raise ValueError("every proposal requires an explicit decision")
            prior = conn.execute(
                "SELECT batch_id,request_sha256,approved_count,rejected_count "
                "FROM knowledge_proposal_review_receipts "
                "WHERE reviewer_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if prior["batch_id"] != batch_id or prior["request_sha256"] != request_sha:
                    raise Conflict("proposal review idempotency key reused")
                return {"batch_id": batch_id, "approved": prior["approved_count"],
                        "rejected": prior["rejected_count"], "changed": False}
            if any(row["decision"] is not None for row in rows):
                raise Conflict("proposal batch was already decided")
            by_id = {row["id"]: row for row in rows}
            approved = rejected = 0
            knowledge = KnowledgeCore(self.store)
            for item in decisions:
                row = by_id[item["proposal_id"]]
                object_kind = object_id = publication_key = None
                if item["decision"] == "approved":
                    assertion, _ = _canonical(row["payload"])
                    publication_key = uuid5(NAMESPACE_URL, "knowledge-proposal:" + row["id"])
                    result = knowledge._publish_in_transaction(
                        conn, ctx, assertion, publication_key,
                    )
                    object_kind, object_id = result.object_kind, result.object_id
                    approved += 1
                else:
                    rejected += 1
                conn.execute(
                    "INSERT INTO knowledge_proposal_decisions(tenant_id,batch_id,"
                    "proposal_id,decision,reviewer_id,reason,publication_key,"
                    "object_kind,object_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, batch_id, row["id"], item["decision"], ctx.actor_id,
                     item["reason"], publication_key, object_kind, object_id),
                )
            conn.execute(
                "INSERT INTO knowledge_proposal_review_receipts(tenant_id,reviewer_id,"
                "idempotency_key,batch_id,request_sha256,approved_count,rejected_count) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, ctx.actor_id, idempotency_key, batch_id,
                 request_sha, approved, rejected),
            )
            self.store.audit(conn, ctx, "knowledge.proposal_batch_reviewed", "batch", batch_id)
            return {"batch_id": batch_id, "approved": approved,
                    "rejected": rejected, "changed": True}
