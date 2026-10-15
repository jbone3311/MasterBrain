"""Private, synthetic-only project-fact proposals from the current dossier format."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from psycopg.types.json import Jsonb
from pydantic import ValidationError

from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.datacore.contracts import stable_id
from masterbrain.knowledge_proposals import _sha
from masterbrain.knowledge_schema import FactProposalReviewRequest, ProjectFactWrite
from masterbrain.librarian_dossier_intake import (
    DossierMarkdownInspection,
    DossierProposalStageRequest,
)
from masterbrain.project_dossier_markdown import _quote_label
from masterbrain.project_facts import ProjectFacts, _markdown_json_text

_BATCH_ID = re.compile(r"^kfbatch_[a-f0-9]{32}$")


def _canonical_fact(raw: dict[str, Any]) -> tuple[ProjectFactWrite, dict[str, Any]]:
    if "reviewed" in raw:
        raise ValueError("fact proposal cannot claim review")
    try:
        fact = ProjectFactWrite.model_validate({**raw, "reviewed": True})
    except ValidationError as exc:
        raise ValueError("invalid source-stated project fact proposal") from exc
    payload = fact.model_dump(mode="json")
    payload.pop("reviewed")
    return fact, payload


def _expected_fact_line(claimed_id: str, fact: ProjectFactWrite) -> str:
    if (fact.supersedes_id is not None or fact.valid_from is not None
            or fact.valid_to is not None):
        raise ValueError("unrendered fact import fields are not supported")
    return (
        f"- fact `{claimed_id}`: `{fact.predicate}` = "
        f"{_markdown_json_text(fact.value)} ({fact.assertion_status}; "
        f"source-stated); {_quote_label(fact.source_quote)}; "
        f"citation `{fact.quote_evidence_id}`."
    )


@dataclass(slots=True)
class FactProposalBatches:
    store: Store

    def _human(self, ctx: TenantContext) -> None:
        self.store.require(ctx, "knowledge.review")
        self.store.require(ctx, "brain.content.read")
        if ctx.identity is not None and ctx.identity.client_kind != "human":
            raise AccessDenied("human identity required")

    def stage(
        self, ctx: TenantContext, body: DossierProposalStageRequest,
        idempotency_key: UUID,
    ) -> dict[str, Any]:
        self._human(ctx)
        if not isinstance(idempotency_key, UUID):
            raise ValueError("UUID idempotency key required")
        inventory = DossierMarkdownInspection(self.store).inspect(ctx, body.markdown)
        by_id = {row["claimed_id"]: row for row in inventory["candidates"]}
        seen: set[str] = set()
        parsed: list[tuple[str, ProjectFactWrite, dict[str, Any]]] = []
        claims: list[tuple[str, str]] = []
        for selected in body.selections:
            if selected.claimed_id in seen:
                raise ValueError("duplicate fact selection")
            seen.add(selected.claimed_id)
            candidate = by_id.get(selected.claimed_id)
            if candidate is None or candidate["kind"] != "fact":
                raise ValueError("unsupported fact selection")
            fact, payload = _canonical_fact(selected.assertion)
            cited_id = candidate["claimed_citation_ids"][0]
            if (fact.project_id != inventory["claimed_project_id"]
                    or fact.quote_evidence_id != cited_id
                    or _expected_fact_line(selected.claimed_id, fact)
                    != candidate["untrusted_line"]):
                raise ValueError("fact line does not match proposed assertion")
            parsed.append((selected.claimed_id, fact, payload))
            claims.append((selected.claimed_id, cited_id))
        context_sha = _sha({
            "format": inventory["format"],
            "markdown_sha256": hashlib.sha256(body.markdown.encode("utf-8")).hexdigest(),
            "claims": claims,
        })
        payloads = [payload for _, _, payload in parsed]
        request_sha = _sha({"proposals": payloads, "import_context_sha256": context_sha})
        batch_id = stable_id(
            "kfbatch", str(ctx.tenant_id), str(ctx.actor_id), str(idempotency_key),
        )
        facts = ProjectFacts(self.store)
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:kfbatch:{ctx.actor_id}:{idempotency_key}",),
            )
            prior = conn.execute(
                "SELECT request_sha256,row_count,import_context_sha256 "
                "FROM knowledge_fact_proposal_batches "
                "WHERE proposer_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if (prior["request_sha256"] != request_sha
                        or prior["row_count"] != len(parsed)
                        or prior["import_context_sha256"] != context_sha):
                    raise Conflict("fact proposal batch idempotency key reused")
                self._rows(conn, ctx, batch_id)
                return {
                    "batch_id": batch_id, "batch_sha256": request_sha,
                    "row_count": len(parsed), "import_context_sha256": context_sha,
                    "changed": False, "reviewed": False,
                }
            for claimed_id, fact, _ in parsed:
                facts._validate_basis_in_transaction(conn, ctx, fact.project_id, fact)
                if conn.execute(
                    "SELECT 1 FROM knowledge_project_facts WHERE id=%s LIMIT 1",
                    (claimed_id,),
                ).fetchone() is not None:
                    raise Conflict("imported fact claim already exists")
            conn.execute(
                "INSERT INTO knowledge_fact_proposal_batches(tenant_id,id,proposer_id,"
                "idempotency_key,request_sha256,import_context_sha256,row_count) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, batch_id, ctx.actor_id, idempotency_key,
                 request_sha, context_sha, len(parsed)),
            )
            for ordinal, (claimed_id, fact, payload) in enumerate(parsed):
                proposal_id = stable_id("kfproposal", batch_id, str(ordinal))
                conn.execute(
                    "INSERT INTO knowledge_fact_proposals(tenant_id,id,batch_id,ordinal,"
                    "claimed_id,payload,payload_sha256,quote_evidence_id,evidence_count) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, proposal_id, batch_id, ordinal, claimed_id,
                     Jsonb(payload), _sha(payload), fact.quote_evidence_id,
                     len(fact.evidence_ids)),
                )
                for position, evidence_id in enumerate(fact.evidence_ids):
                    conn.execute(
                        "INSERT INTO knowledge_fact_proposal_evidence(tenant_id,"
                        "proposal_id,ordinal,evidence_id) VALUES (%s,%s,%s,%s)",
                        (ctx.tenant_id, proposal_id, position, evidence_id),
                    )
            self.store.audit(conn, ctx, "knowledge.fact_proposal_batch_staged", "batch")
        return {
            "batch_id": batch_id, "batch_sha256": request_sha,
            "row_count": len(parsed), "import_context_sha256": context_sha,
            "changed": True, "reviewed": False,
        }

    def _rows(
        self, conn: Any, ctx: TenantContext, batch_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        header = conn.execute(
            "SELECT id,request_sha256,import_context_sha256,row_count "
            "FROM knowledge_fact_proposal_batches WHERE id=%s", (batch_id,),
        ).fetchone()
        if header is None:
            raise NotFound()
        rows = conn.execute(
            "SELECT p.id,p.ordinal,p.claimed_id,p.payload,p.payload_sha256,"
            "p.quote_evidence_id,p.evidence_count,d.decision,d.reason,d.fact_id "
            "FROM knowledge_fact_proposals p "
            "LEFT JOIN knowledge_fact_proposal_decisions d "
            "ON d.tenant_id=p.tenant_id AND d.proposal_id=p.id "
            "WHERE p.batch_id=%s ORDER BY p.ordinal", (batch_id,),
        ).fetchall()
        if len(rows) != header["row_count"] or [r["ordinal"] for r in rows] != list(
            range(header["row_count"])
        ):
            raise Conflict("fact proposal batch is incomplete")
        payloads = []
        facts = ProjectFacts(self.store)
        for row in rows:
            try:
                fact, payload = _canonical_fact(row["payload"])
            except ValueError as exc:
                raise Conflict("fact proposal payload is invalid") from exc
            if (_sha(payload) != row["payload_sha256"]
                    or fact.quote_evidence_id != row["quote_evidence_id"]):
                raise Conflict("fact proposal digest or citation mismatch")
            evidence_rows = conn.execute(
                "SELECT evidence_id FROM knowledge_fact_proposal_evidence "
                "WHERE proposal_id=%s ORDER BY ordinal", (row["id"],),
            ).fetchall()
            if ([item["evidence_id"] for item in evidence_rows] != fact.evidence_ids
                    or len(evidence_rows) != row["evidence_count"]):
                raise Conflict("fact proposal evidence mismatch")
            facts._validate_basis_in_transaction(conn, ctx, fact.project_id, fact)
            payloads.append(payload)
        expected = _sha({
            "proposals": payloads,
            "import_context_sha256": header["import_context_sha256"],
        })
        if expected != header["request_sha256"]:
            raise Conflict("fact proposal batch digest mismatch")
        return header, rows

    def preview(self, ctx: TenantContext, batch_id: str) -> dict[str, Any]:
        self._human(ctx)
        if not isinstance(batch_id, str) or not _BATCH_ID.fullmatch(batch_id):
            raise NotFound()
        with self.store.transaction(ctx) as conn:
            header, rows = self._rows(conn, ctx, batch_id)
            self.store.audit(conn, ctx, "knowledge.fact_proposal_batch_read", "batch")
        return {
            "batch_id": batch_id, "batch_sha256": header["request_sha256"],
            "import_context_sha256": header["import_context_sha256"],
            "row_count": header["row_count"], "reviewed": False,
            "untrusted_content": True,
            "proposals": [
                {"proposal_id": row["id"], "ordinal": row["ordinal"],
                 "claimed_id": row["claimed_id"], "assertion": row["payload"],
                 "status": row["decision"] or "proposed", "reason": row["reason"],
                 "object_kind": "project_fact" if row["fact_id"] else None,
                 "object_id": row["fact_id"]}
                for row in rows
            ],
        }

    def review(
        self, ctx: TenantContext, batch_id: str,
        body: FactProposalReviewRequest, idempotency_key: UUID,
    ) -> dict[str, Any]:
        self._human(ctx)
        if not isinstance(batch_id, str) or not _BATCH_ID.fullmatch(batch_id):
            raise NotFound()
        if not isinstance(idempotency_key, UUID):
            raise ValueError("UUID idempotency key required")
        decisions = sorted(
            (item.model_dump() for item in body.decisions),
            key=lambda item: item["proposal_id"],
        )
        request_sha = _sha({
            "batch_id": batch_id, "batch_sha256": body.batch_sha256,
            "decisions": decisions,
        })
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:kfbatch-review:{batch_id}",),
            )
            header, rows = self._rows(conn, ctx, batch_id)
            if header["request_sha256"] != body.batch_sha256:
                raise Conflict("fact proposal batch changed")
            if {item["proposal_id"] for item in decisions} != {row["id"] for row in rows}:
                raise ValueError("every fact proposal requires a decision")
            prior = conn.execute(
                "SELECT batch_id,request_sha256,approved_count,rejected_count "
                "FROM knowledge_fact_proposal_review_receipts "
                "WHERE reviewer_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if prior["batch_id"] != batch_id or prior["request_sha256"] != request_sha:
                    raise Conflict("fact proposal review idempotency key reused")
                return {"batch_id": batch_id, "approved": prior["approved_count"],
                        "rejected": prior["rejected_count"], "changed": False}
            if any(row["decision"] is not None for row in rows):
                raise Conflict("fact proposal batch was already decided")
            by_id = {row["id"]: row for row in rows}
            approved = rejected = 0
            facts = ProjectFacts(self.store)
            for item in decisions:
                row = by_id[item["proposal_id"]]
                publication_key = fact_id = None
                if item["decision"] == "approved":
                    if conn.execute(
                        "SELECT 1 FROM knowledge_project_facts WHERE id=%s LIMIT 1",
                        (row["claimed_id"],),
                    ).fetchone() is not None:
                        raise Conflict("imported fact claim already exists")
                    fact, _ = _canonical_fact(row["payload"])
                    publication_key = uuid5(
                        NAMESPACE_URL, "knowledge-fact-proposal:" + row["id"],
                    )
                    result = facts._publish_in_transaction(
                        conn, ctx, fact.project_id, fact, publication_key,
                    )
                    fact_id = result["object_id"]
                    approved += 1
                else:
                    rejected += 1
                conn.execute(
                    "INSERT INTO knowledge_fact_proposal_decisions(tenant_id,batch_id,"
                    "proposal_id,decision,reviewer_id,reason,publication_key,fact_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, batch_id, row["id"], item["decision"],
                     ctx.actor_id, item["reason"], publication_key, fact_id),
                )
            conn.execute(
                "INSERT INTO knowledge_fact_proposal_review_receipts(tenant_id,"
                "reviewer_id,idempotency_key,batch_id,request_sha256,"
                "approved_count,rejected_count) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, ctx.actor_id, idempotency_key, batch_id,
                 request_sha, approved, rejected),
            )
            self.store.audit(conn, ctx, "knowledge.fact_proposal_batch_reviewed", "batch")
        return {"batch_id": batch_id, "approved": approved,
                "rejected": rejected, "changed": True}
