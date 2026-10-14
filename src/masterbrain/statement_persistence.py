"""Private worker projection from current DataCore text to immutable proposals.

No API, source effect, or reviewed KnowledgeCore assertion is created here.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Any
from uuid import UUID

from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.datacore.contracts import (
    Digest,
    EvidenceRef,
    EvidenceStorage,
    SourceKind,
    stable_id,
)
from masterbrain.statement_candidates import (
    StatementCandidate,
    StatementRow,
    project_streetbeat_candidate,
)

_ID = re.compile(r"^[a-z][a-z0-9_-]{0,127}$")
_SCALE = Decimal("0.000000000001")


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    with localcontext() as ctx:
        ctx.prec = 50
        return format(value.quantize(_SCALE), "f")


def _row_payload(row: StatementRow | dict[str, Any], ordinal: int) -> dict[str, Any]:
    if isinstance(row, StatementRow):
        return {
            "ordinal": ordinal, "row_type": row.row_type, "description": row.description,
            "symbol": row.symbol, "line_date": row.line_date.isoformat() if row.line_date else None,
            "quantity": _decimal_text(row.quantity), "price": _decimal_text(row.price),
            "amount": _decimal_text(row.amount), "cost_basis": _decimal_text(row.cost_basis),
            "unrealized": _decimal_text(row.unrealized), "currency": row.currency,
            "text_start": row.text_start, "text_end": row.text_end,
        }
    return {
        "ordinal": ordinal, "row_type": row["row_type"], "description": row["description"],
        "symbol": row["symbol"],
        "line_date": row["line_date"].isoformat() if row["line_date"] else None,
        "quantity": _decimal_text(row["quantity"]), "price": _decimal_text(row["price"]),
        "amount": _decimal_text(row["amount"]), "cost_basis": _decimal_text(row["cost_basis"]),
        "unrealized": _decimal_text(row["unrealized"]), "currency": row["currency"],
        "text_start": row["text_start"], "text_end": row["text_end"],
    }


def _rows_sha256(rows: list[dict[str, Any]]) -> str:
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(slots=True)
class StatementProposalStore:
    store: Store

    def project_current_document(
        self, ctx: TenantContext, document_id: str, idempotency_key: UUID,
    ) -> dict[str, Any]:
        """Record one historical, nonpublishing proposal under a worker tenant."""
        self.store.require(ctx, "brain.document.publish")
        if ctx.identity is not None and ctx.identity.client_kind != "worker":
            raise AccessDenied("worker identity required")
        if not isinstance(document_id, str) or not _ID.fullmatch(document_id):
            raise ValueError("invalid_statement_document")
        if not isinstance(idempotency_key, UUID):
            raise ValueError("invalid_statement_request")

        with self.store.transaction(ctx) as conn:
            row = conn.execute(
                "SELECT d.id,d.evidence_id,d.body,d.body_sha256,e.source_version_id,"
                "e.sha256 AS evidence_sha,e.storage,e.retained,v.sha256 AS source_sha,"
                "s.id AS source_id,s.kind AS source_kind,s.status AS source_status,"
                "i.current_version_id FROM brain_normalized_documents d "
                "JOIN brain_evidence e ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id "
                "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
                "AND v.id=e.source_version_id "
                "JOIN brain_source_items i ON i.tenant_id=v.tenant_id "
                "AND i.id=v.item_id AND i.source_id=v.source_id "
                "JOIN brain_sources s ON s.tenant_id=i.tenant_id AND s.id=i.source_id "
                "WHERE d.id=%s FOR SHARE OF i,s",
                (document_id,),
            ).fetchone()
            if row is None or (
                ctx.source_ids is not None and row["source_id"] not in ctx.source_ids
            ):
                raise NotFound()
            if (
                row["current_version_id"] != row["source_version_id"]
                or row["source_status"] != "active"
                or row["evidence_sha"] != row["source_sha"]
            ):
                raise Conflict("statement source is not current")
            body: str = row["body"]
            if hashlib.sha256(body.encode("utf-8")).hexdigest() != row["body_sha256"]:
                raise Conflict("statement text digest changed")
            evidence = EvidenceRef(
                evidence_id=row["evidence_id"], source_version_id=row["source_version_id"],
                digest=Digest("sha256", row["evidence_sha"]),
                storage=EvidenceStorage(row["storage"]), retained=row["retained"],
            )
            candidate = project_streetbeat_candidate(
                body, source_kind=SourceKind(row["source_kind"]), evidence=evidence,
                text_digest=Digest("sha256", row["body_sha256"]),
            )
            return self._record(conn, ctx, document_id, idempotency_key, row, candidate)

    def _record(
        self, conn: Any, ctx: TenantContext, document_id: str, idempotency_key: UUID,
        source: dict[str, Any], candidate: StatementCandidate,
    ) -> dict[str, Any]:
        proposal_id = stable_id(
            "statement", document_id, candidate.transform_version, candidate.text_digest.value,
        )
        rows = [_row_payload(item, ordinal) for ordinal, item in enumerate(candidate.rows)]
        rows_sha = _rows_sha256(rows)
        request_sha = hashlib.sha256(
            f"{document_id}\0{candidate.transform_version}\0{candidate.text_digest.value}".encode()
        ).hexdigest()
        inserted = conn.execute(
            "INSERT INTO knowledge_statement_proposals(tenant_id,id,document_id,evidence_id,"
            "source_version_id,source_id,source_kind,recipe,donor_commit,transform_version,"
            "text_sha256,source_sha256,account_number,period,status,coverage_errors,row_count,"
            "rows_sha256,expected,actual,delta) VALUES "
            "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT DO NOTHING RETURNING id",
            (
                ctx.tenant_id, proposal_id, document_id, candidate.evidence.evidence_id,
                candidate.evidence.source_version_id, source["source_id"],
                candidate.source_kind.value, candidate.recipe, candidate.donor_commit,
                candidate.transform_version, candidate.text_digest.value,
                candidate.evidence.digest.value, candidate.account_number, candidate.period,
                candidate.status.value, list(candidate.coverage_errors), len(rows), rows_sha,
                candidate.expected, candidate.actual, candidate.delta,
            ),
        ).fetchone()
        if inserted is not None:
            for item in rows:
                conn.execute(
                    "INSERT INTO knowledge_statement_rows(tenant_id,proposal_id,ordinal,"
                    "row_type,description,symbol,line_date,quantity,price,amount,cost_basis,"
                    "unrealized,currency,text_start,text_end) VALUES "
                    "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id, proposal_id, item["ordinal"], item["row_type"],
                        item["description"], item["symbol"], item["line_date"],
                        item["quantity"], item["price"], item["amount"],
                        item["cost_basis"], item["unrealized"], item["currency"],
                        item["text_start"], item["text_end"],
                    ),
                )
        saved = conn.execute(
            "SELECT document_id,evidence_id,source_version_id,source_id,source_kind,recipe,"
            "donor_commit,transform_version,text_sha256,source_sha256,account_number,period,"
            "status,coverage_errors,row_count,rows_sha256,expected,actual,delta "
            "FROM knowledge_statement_proposals WHERE id=%s",
            (proposal_id,),
        ).fetchone()
        if saved is None or (
            saved["document_id"], saved["evidence_id"], saved["source_version_id"],
            saved["source_id"], saved["source_kind"], saved["recipe"], saved["donor_commit"],
            saved["transform_version"], saved["text_sha256"], saved["source_sha256"],
            saved["account_number"], saved["period"], saved["status"],
            tuple(saved["coverage_errors"]), saved["row_count"], saved["rows_sha256"],
            saved["expected"], saved["actual"], saved["delta"],
        ) != (
            document_id, candidate.evidence.evidence_id, candidate.evidence.source_version_id,
            source["source_id"], candidate.source_kind.value, candidate.recipe,
            candidate.donor_commit, candidate.transform_version, candidate.text_digest.value,
            candidate.evidence.digest.value, candidate.account_number, candidate.period,
            candidate.status.value, candidate.coverage_errors, len(rows), rows_sha,
            candidate.expected, candidate.actual, candidate.delta,
        ):
            raise Conflict("statement proposal replay differs")
        saved_rows = conn.execute(
            "SELECT ordinal,row_type,description,symbol,line_date,quantity,price,amount,"
            "cost_basis,unrealized,currency,text_start,text_end "
            "FROM knowledge_statement_rows WHERE proposal_id=%s ORDER BY ordinal",
            (proposal_id,),
        ).fetchall()
        if len(saved_rows) != len(rows) or _rows_sha256([
            _row_payload(item, item["ordinal"]) for item in saved_rows
        ]) != rows_sha:
            raise Conflict("statement proposal rows differ")
        conn.execute(
            "INSERT INTO knowledge_statement_receipts(tenant_id,actor_id,idempotency_key,"
            "request_sha256,proposal_id) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (ctx.tenant_id, ctx.actor_id, idempotency_key, request_sha, proposal_id),
        )
        receipt = conn.execute(
            "SELECT request_sha256,proposal_id FROM knowledge_statement_receipts "
            "WHERE actor_id=%s AND idempotency_key=%s",
            (ctx.actor_id, idempotency_key),
        ).fetchone()
        if receipt is None or (receipt["request_sha256"], receipt["proposal_id"]) != (
            request_sha, proposal_id,
        ):
            raise Conflict("statement request key was reused")
        self.store.audit(
            conn, ctx, "knowledge.statement_proposal", "statement_proposal", proposal_id
        )
        return {
            "proposal_id": proposal_id, "status": candidate.status.value,
            "row_count": len(rows), "coverage_errors": candidate.coverage_errors,
            "source_effects": False, "reviewed": False,
        }
