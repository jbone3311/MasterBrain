"""Human-only approval of one synthetic Email XLSX extraction attempt.

An approval does not run the worker or publish a document. PDF document jobs
remain a separate, incompatible contract.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from uuid import UUID

import psycopg

from email_brain.auth import Principal
from email_brain.recovery_jobs import _account_lock, _owners
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.datacore.contracts import stable_id

POLICY = "synthetic-unscanned-xlsx-v1"
_VERSION = re.compile(r"^sandbox-fileos-document-v1-[a-f0-9]{64}$")

_BASIS_SQL = (
    "SELECT ar.account_id,ar.id AS attachment_id,ar.evidence_id AS parent_version_id,"
    "ar.part_id AS part_path,ar.sha256 AS part_sha256,"
    "ar.byte_size AS part_size_bytes,mv.raw_sha256,ro.raw_size AS raw_size_bytes,"
    "ms.event_key AS source_event_key,s.id AS source_id "
    "FROM attachment_receipts ar JOIN message_versions mv "
    "ON mv.tenant_id=ar.tenant_id AND mv.account_id=ar.account_id "
    "AND mv.id=ar.evidence_id JOIN messages m ON m.tenant_id=mv.tenant_id "
    "AND m.account_id=mv.account_id AND m.id=mv.message_id "
    "JOIN message_sync_state ms ON ms.tenant_id=m.tenant_id "
    "AND ms.account_id=m.account_id AND ms.provider_id=m.provider_message_id "
    "JOIN mail_accounts a ON a.tenant_id=mv.tenant_id AND a.id=mv.account_id "
    "JOIN raw_objects ro ON ro.tenant_id=mv.tenant_id AND ro.account_id=mv.account_id "
    "AND ro.sha256=mv.raw_sha256 "
    "JOIN brain_email_attachment_bridge_receipts ab ON ab.tenant_id=ar.tenant_id "
    "AND ab.account_id=ar.account_id AND ab.legacy_attachment_id=ar.id "
    "AND ab.legacy_parent_version_id=mv.id "
    "JOIN brain_source_items ai ON ai.tenant_id=ab.tenant_id AND ai.id=ab.item_id "
    "AND ai.current_version_id=ab.version_id "
    "JOIN brain_sources s ON s.tenant_id=ab.tenant_id AND s.id=ab.source_id "
    "AND s.id=ai.source_id "
    "JOIN brain_email_bridge_receipts eb ON eb.tenant_id=mv.tenant_id "
    "AND eb.account_id=mv.account_id AND eb.legacy_version_id=mv.id "
    "AND eb.evidence_id=ab.parent_evidence_id "
    "JOIN brain_source_items pi ON pi.tenant_id=eb.tenant_id AND pi.id=eb.item_id "
    "AND pi.current_version_id=eb.version_id "
    "WHERE ar.account_id=%s AND ar.id=%s "
    "AND ar.media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' "
    "AND right(lower(ar.safe_filename),5)='.xlsx' "
    "AND ar.status='deferred' AND ar.reason IN "
    "('isolated_extractor_required','extraction_byte_limit') "
    "AND ar.byte_size BETWEEN 1 AND 8388608 "
    "AND ro.raw_size BETWEEN 1 AND 16777216 "
    "AND m.raw_sha256=mv.raw_sha256 AND m.parser_version=mv.parser_version "
    "AND NOT m.deleted AND NOT m.quarantined AND ms.status='ready' "
    "AND a.status='active' AND a.provider_account_id IS NULL "
    "AND a.secret_ref LIKE 'synthetic:%%' "
    "AND s.kind='email' AND s.status='active' "
    "AND NOT public.brain_email_evidence_is_excluded(ab.tenant_id,ab.evidence_id) "
    "FOR SHARE OF ai,pi,s,m,ms"
)


class EmailXlsxApprovals:
    def __init__(self, store: Store, processor_version: str) -> None:
        if type(processor_version) is not str or _VERSION.fullmatch(processor_version) is None:
            raise ValueError("invalid XLSX processor version")
        self.store, self.processor_version = store, processor_version

    def approve(
        self, principal: Principal, account_id: UUID, attachment_id: UUID,
        idempotency_key: UUID,
    ) -> dict[str, Any]:
        """Seal exact current synthetic attachment bytes for a later worker."""
        if principal.client_kind != "human":
            raise AccessDenied("human approval required")
        ctx = principal.context
        self.store.require(ctx, "email.review")
        self.store.require(ctx, "email.evidence.read")
        if not all(isinstance(value, UUID) for value in (
            account_id, attachment_id, idempotency_key,
        )):
            raise ValueError("UUID account, attachment and idempotency key required")
        request_sha256 = hashlib.sha256(json.dumps(
            [str(account_id), str(attachment_id), self.processor_version, POLICY],
            separators=(",", ":"),
        ).encode()).hexdigest()
        approval_id = stable_id(
            "xapp", str(ctx.tenant_id), str(ctx.actor_id), str(idempotency_key),
        )
        try:
            with self.store.transaction(ctx) as conn:
                _account_lock(conn, ctx.tenant_id, account_id)
                if not _owners(conn, account_id, ctx.actor_id, ctx.actor_id):
                    raise AccessDenied()
                basis = conn.execute(_BASIS_SQL, (account_id, attachment_id)).fetchone()
                if basis is None or (
                    ctx.source_ids is not None and basis["source_id"] not in ctx.source_ids
                ):
                    raise NotFound()
                prior = conn.execute(
                    "SELECT id,request_sha256 FROM brain_email_xlsx_extraction_approvals "
                    "WHERE actor_id=%s AND idempotency_key=%s",
                    (ctx.actor_id, idempotency_key),
                ).fetchone()
                if prior is not None:
                    if prior["request_sha256"] != request_sha256:
                        raise Conflict("XLSX approval idempotency key reused")
                    return {"approval_id": prior["id"], "changed": False,
                            "mailbox_effects": False, "document_published": False}
                conn.execute(
                    "INSERT INTO brain_email_xlsx_extraction_approvals("
                    "tenant_id,id,actor_id,idempotency_key,account_id,parent_version_id,"
                    "attachment_id,source_id,source_event_key,raw_sha256,raw_size_bytes,"
                    "part_path,part_sha256,part_size_bytes,processor_version,policy_version,"
                    "request_sha256) VALUES ("
                    "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id, approval_id, ctx.actor_id, idempotency_key,
                        account_id, basis["parent_version_id"], attachment_id,
                        basis["source_id"], basis["source_event_key"],
                        basis["raw_sha256"], basis["raw_size_bytes"],
                        basis["part_path"], basis["part_sha256"],
                        basis["part_size_bytes"], self.processor_version, POLICY,
                        request_sha256,
                    ),
                )
                self.store.audit(
                    conn, ctx, "brain.email_xlsx_extraction_approved",
                    "xlsx_approval", approval_id,
                )
            return {"approval_id": approval_id, "changed": True,
                    "mailbox_effects": False, "document_published": False}
        except psycopg.errors.UniqueViolation:
            raise Conflict("XLSX approval idempotency key reused") from None
