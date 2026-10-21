"""Private selected project-artifact proposals from the current dossier format."""

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
from masterbrain.knowledge_schema import (
    ArtifactProposalReviewRequest,
    ProjectArtifactLinkWrite,
)
from masterbrain.librarian_dossier_intake import (
    DossierMarkdownInspection,
    DossierProposalStageRequest,
)
from masterbrain.project_artifacts import ProjectArtifactLinks
from masterbrain.project_dossier_markdown import _quote_label

_BATCH_ID = re.compile(r"^kabatch_[a-f0-9]{32}$")


def _canonical_link(raw: dict[str, Any]) -> tuple[ProjectArtifactLinkWrite, dict[str, Any]]:
    if "reviewed" in raw:
        raise ValueError("artifact proposal cannot claim review")
    try:
        link = ProjectArtifactLinkWrite.model_validate(raw)
    except ValidationError as exc:
        raise ValueError("invalid project artifact proposal") from exc
    return link, link.model_dump(mode="json")


def _expected_link_line(
    claimed_id: str, link: ProjectArtifactLinkWrite, artifact_kind: str,
) -> str:
    return (
        f"- artifact link `{claimed_id}`: `{link.relation}` "
        f"({link.assertion_status}) to {artifact_kind} "
        f"evidence `{link.artifact_evidence_id}`; reviewed basis "
        f"{_quote_label(link.source_quote)}; "
        f"citation `{link.basis_evidence_id}`."
    )


@dataclass(slots=True)
class ArtifactProposalBatches:
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
        project_id = inventory["claimed_project_id"]
        by_id = {row["claimed_id"]: row for row in inventory["candidates"]}
        seen: set[str] = set()
        parsed: list[tuple[str, ProjectArtifactLinkWrite, dict[str, Any], dict[str, Any]]] = []
        for selected in body.selections:
            if selected.claimed_id in seen:
                raise ValueError("duplicate artifact selection")
            seen.add(selected.claimed_id)
            candidate = by_id.get(selected.claimed_id)
            if candidate is None or candidate["kind"] != "artifact link":
                raise ValueError("unsupported artifact selection")
            link, payload = _canonical_link(selected.assertion)
            if candidate["claimed_citation_ids"] != [link.basis_evidence_id]:
                raise ValueError("artifact basis citation mismatch")
            parsed.append((selected.claimed_id, link, payload, candidate))
        batch_id = stable_id(
            "kabatch", str(ctx.tenant_id), str(ctx.actor_id), str(idempotency_key),
        )
        links = ProjectArtifactLinks(self.store)
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:kabatch:{ctx.actor_id}:{idempotency_key}",),
            )
            claims: list[tuple[str, str, str, str]] = []
            for claimed_id, link, _, candidate in parsed:
                artifact_kind = links._validate_basis_in_transaction(
                    conn, ctx, project_id, link,
                )
                if (_expected_link_line(claimed_id, link, artifact_kind)
                        != candidate["untrusted_line"]):
                    raise ValueError("artifact line does not match proposed assertion")
                if conn.execute(
                    "SELECT 1 FROM knowledge_project_artifacts WHERE id=%s LIMIT 1",
                    (claimed_id,),
                ).fetchone() is not None:
                    raise Conflict("imported artifact claim already exists")
                if conn.execute(
                    "SELECT 1 FROM knowledge_artifact_proposals p "
                    "JOIN knowledge_artifact_proposal_decisions d "
                    "ON d.tenant_id=p.tenant_id AND d.proposal_id=p.id "
                    "WHERE p.claimed_id=%s AND d.decision='approved' LIMIT 1",
                    (claimed_id,),
                ).fetchone() is not None:
                    raise Conflict("imported artifact claim was already approved")
                claims.append((claimed_id, link.artifact_evidence_id,
                               link.basis_evidence_id, artifact_kind))
            context_sha = _sha({
                "format": inventory["format"],
                "markdown_sha256": hashlib.sha256(body.markdown.encode("utf-8")).hexdigest(),
                "project_id": project_id,
                "claims": claims,
            })
            payloads = [payload for _, _, payload, _ in parsed]
            request_sha = _sha({
                "proposals": payloads,
                "import_context_sha256": context_sha,
            })
            prior = conn.execute(
                "SELECT request_sha256,row_count,import_context_sha256 "
                "FROM knowledge_artifact_proposal_batches "
                "WHERE proposer_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if (prior["request_sha256"] != request_sha
                        or prior["row_count"] != len(parsed)
                        or prior["import_context_sha256"] != context_sha):
                    raise Conflict("artifact proposal batch idempotency key reused")
                self._rows(conn, ctx, batch_id)
                return {
                    "batch_id": batch_id, "batch_sha256": request_sha,
                    "row_count": len(parsed), "import_context_sha256": context_sha,
                    "changed": False, "reviewed": False,
                }
            conn.execute(
                "INSERT INTO knowledge_artifact_proposal_batches(tenant_id,id,proposer_id,"
                "idempotency_key,request_sha256,import_context_sha256,row_count) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, batch_id, ctx.actor_id, idempotency_key,
                 request_sha, context_sha, len(parsed)),
            )
            for ordinal, (claimed_id, link, payload, _) in enumerate(parsed):
                proposal_id = stable_id("kaproposal", batch_id, str(ordinal))
                conn.execute(
                    "INSERT INTO knowledge_artifact_proposals(tenant_id,id,batch_id,"
                    "ordinal,claimed_id,project_id,payload,payload_sha256,"
                    "artifact_evidence_id,basis_evidence_id,artifact_source_kind) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, proposal_id, batch_id, ordinal, claimed_id,
                     project_id, Jsonb(payload), _sha(payload), link.artifact_evidence_id,
                     link.basis_evidence_id, claims[ordinal][3]),
                )
            self.store.audit(conn, ctx, "knowledge.artifact_proposal_batch_staged", "batch")
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
            "FROM knowledge_artifact_proposal_batches WHERE id=%s", (batch_id,),
        ).fetchone()
        if header is None:
            raise NotFound()
        rows = conn.execute(
            "SELECT p.id,p.ordinal,p.claimed_id,p.project_id,p.payload,p.payload_sha256,"
            "p.artifact_evidence_id,p.basis_evidence_id,p.artifact_source_kind,"
            "d.decision,d.reason,d.link_id "
            "FROM knowledge_artifact_proposals p "
            "LEFT JOIN knowledge_artifact_proposal_decisions d "
            "ON d.tenant_id=p.tenant_id AND d.proposal_id=p.id "
            "WHERE p.batch_id=%s ORDER BY p.ordinal", (batch_id,),
        ).fetchall()
        if len(rows) != header["row_count"] or [r["ordinal"] for r in rows] != list(
            range(header["row_count"])
        ):
            raise Conflict("artifact proposal batch is incomplete")
        payloads = []
        links = ProjectArtifactLinks(self.store)
        for row in rows:
            try:
                link, payload = _canonical_link(row["payload"])
            except ValueError as exc:
                raise Conflict("artifact proposal payload is invalid") from exc
            if (_sha(payload) != row["payload_sha256"]
                    or link.artifact_evidence_id != row["artifact_evidence_id"]
                    or link.basis_evidence_id != row["basis_evidence_id"]):
                raise Conflict("artifact proposal digest or citation mismatch")
            kind = links._validate_basis_in_transaction(
                conn, ctx, row["project_id"], link,
            )
            if kind != row["artifact_source_kind"]:
                raise Conflict("artifact proposal source kind changed")
            payloads.append(payload)
        expected = _sha({
            "proposals": payloads,
            "import_context_sha256": header["import_context_sha256"],
        })
        if expected != header["request_sha256"]:
            raise Conflict("artifact proposal batch digest mismatch")
        return header, rows

    def preview(self, ctx: TenantContext, batch_id: str) -> dict[str, Any]:
        self._human(ctx)
        if not isinstance(batch_id, str) or not _BATCH_ID.fullmatch(batch_id):
            raise NotFound()
        with self.store.transaction(ctx) as conn:
            header, rows = self._rows(conn, ctx, batch_id)
            self.store.audit(conn, ctx, "knowledge.artifact_proposal_batch_read", "batch")
        return {
            "batch_id": batch_id, "batch_sha256": header["request_sha256"],
            "import_context_sha256": header["import_context_sha256"],
            "row_count": header["row_count"], "reviewed": False,
            "untrusted_content": True,
            "proposals": [
                {"proposal_id": row["id"], "ordinal": row["ordinal"],
                 "claimed_id": row["claimed_id"], "project_id": row["project_id"],
                 "assertion": row["payload"],
                 "artifact_source_kind": row["artifact_source_kind"],
                 "status": row["decision"] or "proposed", "reason": row["reason"],
                 "object_kind": "project_artifact" if row["link_id"] else None,
                 "object_id": row["link_id"]}
                for row in rows
            ],
        }

    def review(
        self, ctx: TenantContext, batch_id: str,
        body: ArtifactProposalReviewRequest, idempotency_key: UUID,
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
                (f"{ctx.tenant_id}:kabatch-review:{batch_id}",),
            )
            header, rows = self._rows(conn, ctx, batch_id)
            if header["request_sha256"] != body.batch_sha256:
                raise Conflict("artifact proposal batch changed")
            if {item["proposal_id"] for item in decisions} != {row["id"] for row in rows}:
                raise ValueError("every artifact proposal requires a decision")
            prior = conn.execute(
                "SELECT batch_id,request_sha256,approved_count,rejected_count "
                "FROM knowledge_artifact_proposal_review_receipts "
                "WHERE reviewer_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if prior["batch_id"] != batch_id or prior["request_sha256"] != request_sha:
                    raise Conflict("artifact proposal review idempotency key reused")
                return {"batch_id": batch_id, "approved": prior["approved_count"],
                        "rejected": prior["rejected_count"], "changed": False}
            if any(row["decision"] is not None for row in rows):
                raise Conflict("artifact proposal batch was already decided")
            by_id = {row["id"]: row for row in rows}
            approved = rejected = 0
            links = ProjectArtifactLinks(self.store)
            for item in decisions:
                row = by_id[item["proposal_id"]]
                publication_key = link_id = None
                if item["decision"] == "approved":
                    if conn.execute(
                        "SELECT 1 FROM knowledge_project_artifacts WHERE id=%s LIMIT 1",
                        (row["claimed_id"],),
                    ).fetchone() is not None:
                        raise Conflict("imported artifact claim already exists")
                    conn.execute(
                        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                        (f"{ctx.tenant_id}:kaclaim:{row['claimed_id']}",),
                    )
                    if conn.execute(
                        "SELECT 1 FROM knowledge_artifact_proposals p "
                        "JOIN knowledge_artifact_proposal_decisions d "
                        "ON d.tenant_id=p.tenant_id AND d.proposal_id=p.id "
                        "WHERE p.claimed_id=%s AND d.decision='approved' LIMIT 1",
                        (row["claimed_id"],),
                    ).fetchone() is not None:
                        raise Conflict("imported artifact claim was already approved")
                    link, _ = _canonical_link(row["payload"])
                    publication_key = uuid5(
                        NAMESPACE_URL, "knowledge-artifact-proposal:" + row["id"],
                    )
                    result = links._publish_in_transaction(
                        conn, ctx, row["project_id"], link, publication_key,
                    )
                    link_id = result["object_id"]
                    approved += 1
                else:
                    rejected += 1
                conn.execute(
                    "INSERT INTO knowledge_artifact_proposal_decisions(tenant_id,batch_id,"
                    "proposal_id,decision,reviewer_id,reason,publication_key,link_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, batch_id, row["id"], item["decision"],
                     ctx.actor_id, item["reason"], publication_key, link_id),
                )
            conn.execute(
                "INSERT INTO knowledge_artifact_proposal_review_receipts(tenant_id,"
                "reviewer_id,idempotency_key,batch_id,request_sha256,"
                "approved_count,rejected_count) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, ctx.actor_id, idempotency_key, batch_id,
                 request_sha, approved, rejected),
            )
            self.store.audit(conn, ctx, "knowledge.artifact_proposal_batch_reviewed", "batch")
        return {"batch_id": batch_id, "approved": approved,
                "rejected": rejected, "changed": True}
