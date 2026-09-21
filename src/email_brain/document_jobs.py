"""Separate, source-bound PDF approvals. No mailbox writes or in-process parser."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.pdf_contract import PdfResult, PdfSource, decode_result, encode_result, source_for
from email_brain.recovery_jobs import LeaseLost, _account_lock, _owners
from email_brain.store import AccessDenied, Conflict, NotFound, Store

POLICY = "synthetic-unscanned-pdf-v1"
_VERSION = re.compile(r"sandbox-pdf-v1-[a-f0-9]{64}\Z", re.ASCII)
_TERMINAL = frozenset({"completed", "cancelled", "expired", "failed", "stale", "revoked"})
_FIELDS = (
    "id",
    "account_id",
    "receipt_id",
    "processor_version",
    "policy_version",
    "status",
    "attempts",
    "created_at",
    "expires_at",
    "retry_at",
    "completed_at",
    "extraction_id",
    "outcome",
)


class PdfProcessor(Protocol):
    @property
    def processor_version(self) -> str: ...

    def extract(self, raw: bytes, *, part_path: str, part_sha256: str) -> PdfResult: ...


def _public(row: dict[str, Any]) -> dict[str, Any]:
    return {**{key: row[key] for key in _FIELDS}, "mailbox_effects": False}


def _source(
    conn: psycopg.Connection[dict[str, Any]], account: UUID, receipt: UUID
) -> dict[str, Any] | None:
    return conn.execute(
        "SELECT a.part_id,a.sha256,v.raw_sha256,s.event_key "
        "FROM attachment_receipts a JOIN message_versions v "
        "ON v.tenant_id=a.tenant_id AND v.account_id=a.account_id AND v.id=a.evidence_id "
        "JOIN messages m ON m.tenant_id=v.tenant_id AND m.id=v.message_id "
        "AND m.raw_sha256=v.raw_sha256 AND m.parser_version=v.parser_version "
        "JOIN message_sync_state s ON s.tenant_id=m.tenant_id AND s.account_id=m.account_id "
        "AND s.provider_id=m.provider_message_id "
        "JOIN mail_accounts c ON c.tenant_id=m.tenant_id AND c.id=m.account_id "
        "WHERE a.account_id=%s AND a.id=%s AND a.media_type='application/pdf' "
        "AND a.status='deferred' AND a.reason IN "
        "('isolated_extractor_required','extraction_byte_limit') "
        "AND NOT m.deleted AND NOT m.quarantined AND s.status='ready' "
        "AND c.status='active' AND c.provider_account_id IS NULL "
        "AND c.secret_ref LIKE 'synthetic:%%'",
        (account, receipt),
    ).fetchone()


class DocumentJobs:
    def __init__(self, store: Store, processor_version: str | None = None) -> None:
        if processor_version is not None and (
            type(processor_version) is not str or not _VERSION.fullmatch(processor_version)
        ):
            raise ValueError("invalid document processor")
        self.store, self.processor_version = store, processor_version

    @staticmethod
    def _human(principal: Principal) -> TenantContext:
        if principal.client_kind != "human":
            raise AccessDenied("human approval required")
        for scope in ("email.review", "email.evidence.read"):
            Store.require(principal.context, scope)
        return principal.context

    @staticmethod
    def _account(conn: psycopg.Connection[dict[str, Any]], account: UUID) -> dict[str, Any]:
        row = conn.execute(
            "SELECT id,status,provider_account_id,secret_ref FROM mail_accounts WHERE id=%s",
            (account,),
        ).fetchone()
        if row is None:
            raise NotFound()
        return row

    def capabilities(self, ctx: TenantContext, account: UUID) -> dict[str, Any]:
        self.store.require(ctx, "email.evidence.read")
        with self.store.transaction(ctx) as conn:
            row = self._account(conn, account)
        return {
            "enabled": bool(
                self.processor_version
                and row["status"] == "active"
                and row["provider_account_id"] is None
                and row["secret_ref"].startswith("synthetic:")
            ),
            "processor_version": self.processor_version,
            "policy_version": POLICY,
            "scanner_status": "unscanned",
            "worker_online": None,
            "mailbox_effects": False,
        }

    def enqueue(
        self,
        principal: Principal,
        account: UUID,
        receipt: UUID,
        processor: str,
        policy: str,
        key: UUID,
    ) -> dict[str, Any]:
        ctx = self._human(principal)
        if not isinstance(key, UUID):
            raise ValueError("UUID idempotency key required")
        if (
            self.processor_version is None
            or processor != self.processor_version
            or policy != POLICY
        ):
            raise Conflict("document processing unavailable or policy/processor changed")
        try:
            with self.store.transaction(ctx) as conn:
                _account_lock(conn, ctx.tenant_id, account)
                self._account(conn, account)
                if not _owners(conn, account, ctx.actor_id, ctx.actor_id):
                    raise AccessDenied()
                old = conn.execute(
                    "SELECT * FROM document_jobs WHERE actor_id=%s AND idempotency_key=%s",
                    (ctx.actor_id, key),
                ).fetchone()
                if old:
                    if (
                        old["account_id"],
                        old["receipt_id"],
                        old["processor_version"],
                        old["policy_version"],
                    ) != (account, receipt, processor, policy):
                        raise Conflict("document idempotency key reused")
                    return _public(old)
                source = _source(conn, account, receipt)
                if source is None:
                    raise NotFound()
                count = conn.execute(
                    "SELECT count(*) AS n FROM document_jobs WHERE account_id=%s "
                    "AND status IN ('queued','running','retry_wait')",
                    (account,),
                ).fetchone()
                if count is None or count["n"] >= 100:
                    raise Conflict("document queue is full")
                row = conn.execute(
                    "INSERT INTO document_jobs(tenant_id,account_id,receipt_id,source_event_key,"
                    "actor_id,idempotency_key,processor_version,policy_version) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                    (
                        ctx.tenant_id,
                        account,
                        receipt,
                        source["event_key"],
                        ctx.actor_id,
                        key,
                        processor,
                        policy,
                    ),
                ).fetchone()
                assert row is not None
                self.store.audit(conn, ctx, "document.job_enqueued", "document_job", str(row["id"]))
                return _public(row)
        except psycopg.errors.UniqueViolation:
            raise Conflict("document idempotency key reused") from None

    def get(self, ctx: TenantContext, account: UUID, job: UUID) -> dict[str, Any]:
        self.store.require(ctx, "email.evidence.read")
        with self.store.transaction(ctx) as conn:
            self._account(conn, account)
            row = conn.execute(
                "SELECT * FROM document_jobs WHERE account_id=%s AND id=%s",
                (account, job),
            ).fetchone()
            if row is None:
                raise NotFound()
            self.store.audit(conn, ctx, "document.job_read", "document_job", str(job))
            return _public(row)

    def list(
        self,
        ctx: TenantContext,
        account: UUID,
        *,
        limit: int = 50,
        after: UUID | None = None,
    ) -> dict[str, Any]:
        self.store.require(ctx, "email.evidence.read")
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("limit must be 1..50")
        if after is not None and not isinstance(after, UUID):
            raise ValueError("cursor must be UUID")
        with self.store.transaction(ctx) as conn:
            self._account(conn, account)
            anchor = None
            if after is not None:
                anchor = conn.execute(
                    "SELECT created_at,id FROM document_jobs WHERE account_id=%s AND id=%s",
                    (account, after),
                ).fetchone()
                if anchor is None:
                    raise NotFound()
            rows = conn.execute(
                "SELECT * FROM document_jobs WHERE account_id=%s "
                "AND (%s::timestamptz IS NULL OR (created_at,id)<(%s,%s)) "
                "ORDER BY created_at DESC,id DESC LIMIT %s",
                (
                    account,
                    anchor["created_at"] if anchor else None,
                    anchor["created_at"] if anchor else None,
                    after,
                    limit + 1,
                ),
            ).fetchall()
            self.store.audit(conn, ctx, "document.jobs_read", "account", str(account))
            return {
                "results": [_public(row) for row in rows[:limit]],
                "limit": limit,
                "next_after": rows[limit - 1]["id"] if len(rows) > limit else None,
                "mailbox_effects": False,
            }

    def _terminal(
        self,
        conn: psycopg.Connection[dict[str, Any]],
        ctx: TenantContext,
        job: UUID,
        status: str,
        outcome: str,
        *,
        lease_token: UUID | None = None,
    ) -> dict[str, Any]:
        row = conn.execute(
            "UPDATE document_jobs SET status=%s,outcome=%s,completed_at=clock_timestamp(),"
            "lease_token=NULL,lease_until=NULL,retry_at=NULL WHERE id=%s "
            "AND (%s::uuid IS NULL OR (lease_token=%s AND lease_until>clock_timestamp())) "
            "RETURNING *",
            (status, outcome, job, lease_token, lease_token),
        ).fetchone()
        if row is None:
            raise LeaseLost()
        self.store.audit(conn, ctx, "document.job_" + status, "document_job", str(job))
        return row

    def cancel(self, principal: Principal, account: UUID, job: UUID) -> dict[str, Any]:
        ctx = self._human(principal)
        with self.store.transaction(ctx) as conn:
            self._account(conn, account)
            row = conn.execute(
                "SELECT * FROM document_jobs WHERE account_id=%s AND id=%s FOR UPDATE",
                (account, job),
            ).fetchone()
            if row is None:
                raise NotFound()
            if row["status"] not in _TERMINAL:
                row = self._terminal(conn, ctx, job, "cancelled", "cancelled")
            return _public(row)

    def _validity(
        self,
        conn: psycopg.Connection[dict[str, Any]],
        ctx: TenantContext,
        row: dict[str, Any],
    ) -> tuple[str, str] | None:
        _account_lock(conn, ctx.tenant_id, row["account_id"])
        if not _owners(conn, row["account_id"], row["actor_id"], ctx.actor_id):
            return "revoked", "authorization_revoked"
        source = _source(conn, row["account_id"], row["receipt_id"])
        if source is None or source["event_key"] != row["source_event_key"]:
            return "stale", "source_changed"
        clock = conn.execute(
            "SELECT expires_at>clock_timestamp() AS approved FROM document_jobs WHERE id=%s",
            (row["id"],),
        ).fetchone()
        if clock is None or not clock["approved"]:
            return "expired", "approval_expired"
        return None

    def _claim(self, ctx: TenantContext, account: UUID) -> dict[str, Any] | None:
        with self.store.transaction(ctx) as conn:
            self._account(conn, account)
            row = conn.execute(
                "SELECT * FROM document_jobs WHERE account_id=%s AND processor_version=%s "
                "AND policy_version=%s AND status IN ('queued','running','retry_wait') "
                "AND (expires_at<=clock_timestamp() OR status='queued' OR "
                "(status='running' AND lease_until<=clock_timestamp()) OR "
                "(status='retry_wait' AND retry_at<=clock_timestamp())) "
                "ORDER BY created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED",
                (account, self.processor_version, POLICY),
            ).fetchone()
            if row is None:
                return None
            invalid = self._validity(conn, ctx, row)
            if invalid:
                return self._terminal(conn, ctx, row["id"], *invalid)
            if row["attempts"] >= 3:
                return self._terminal(conn, ctx, row["id"], "failed", "attempts_exhausted")
            claimed = conn.execute(
                "UPDATE document_jobs SET status='running',attempts=attempts+1,lease_token=%s,"
                "lease_until=clock_timestamp()+interval '120 seconds',worker_actor_id=%s,"
                "retry_at=NULL,outcome=NULL WHERE id=%s "
                "AND expires_at>clock_timestamp() RETURNING *",
                (uuid4(), ctx.actor_id, row["id"]),
            ).fetchone()
            if claimed is None:
                return self._terminal(conn, ctx, row["id"], "expired", "approval_expired")
            self.store.audit(conn, ctx, "document.job_claimed", "document_job", str(row["id"]))
            return claimed

    def _fence(
        self,
        conn: psycopg.Connection[dict[str, Any]],
        ctx: TenantContext,
        claimed: dict[str, Any],
    ) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM document_jobs WHERE id=%s AND account_id=%s FOR UPDATE",
            (claimed["id"], claimed["account_id"]),
        ).fetchone()
        if (
            row is None
            or row["status"] != "running"
            or row["lease_token"] != claimed["lease_token"]
            or row["worker_actor_id"] != ctx.actor_id
            or row["processor_version"] != self.processor_version
            or row["policy_version"] != POLICY
            or self._validity(conn, ctx, row)
        ):
            raise LeaseLost()
        clock = conn.execute(
            "SELECT lease_until>clock_timestamp() AS leased FROM document_jobs WHERE id=%s",
            (row["id"],),
        ).fetchone()
        if clock is None or not clock["leased"]:
            raise LeaseLost()
        source = _source(conn, row["account_id"], row["receipt_id"])
        if source is None:
            raise LeaseLost()
        return source

    def _cached(
        self,
        conn: psycopg.Connection[dict[str, Any]],
        row: dict[str, Any],
    ) -> dict[str, Any] | None:
        return conn.execute(
            "SELECT id FROM document_extractions WHERE account_id=%s AND receipt_id=%s "
            "AND processor_version=%s AND policy_version=%s",
            (row["account_id"], row["receipt_id"], row["processor_version"], POLICY),
        ).fetchone()

    def _complete(
        self,
        conn: psycopg.Connection[dict[str, Any]],
        ctx: TenantContext,
        row: dict[str, Any],
        extraction: UUID,
    ) -> dict[str, Any]:
        self._fence(conn, ctx, row)
        completed = conn.execute(
            "UPDATE document_jobs SET status='completed',outcome='result_saved',extraction_id=%s,"
            "completed_at=clock_timestamp(),lease_token=NULL,lease_until=NULL,retry_at=NULL "
            "WHERE id=%s AND lease_token=%s AND expires_at>clock_timestamp() "
            "AND lease_until>clock_timestamp() RETURNING *",
            (extraction, row["id"], row["lease_token"]),
        ).fetchone()
        if completed is None:
            raise LeaseLost()
        self.store.audit(conn, ctx, "document.job_completed", "document_job", str(row["id"]))
        return _public(completed)

    def _failed(self, ctx: TenantContext, claimed: dict[str, Any]) -> dict[str, Any] | None:
        try:
            with self.store.transaction(ctx) as conn:
                row = conn.execute(
                    "SELECT *,lease_until>clock_timestamp() AS leased FROM document_jobs "
                    "WHERE id=%s FOR UPDATE",
                    (claimed["id"],),
                ).fetchone()
                if row is None:
                    return None
                if (
                    row["status"] != "running"
                    or row["lease_token"] != claimed["lease_token"]
                    or not row["leased"]
                ):
                    return _public(row)
                invalid = self._validity(conn, ctx, row)
                if invalid:
                    return _public(
                        self._terminal(
                            conn, ctx, row["id"], *invalid, lease_token=row["lease_token"]
                        )
                    )
                if row["attempts"] >= 3:
                    return _public(
                        self._terminal(
                            conn,
                            ctx,
                            row["id"],
                            "failed",
                            "infrastructure_unavailable",
                            lease_token=row["lease_token"],
                        )
                    )
                retry = conn.execute(
                    "UPDATE document_jobs SET status='retry_wait',"
                    "outcome='infrastructure_unavailable',lease_token=NULL,lease_until=NULL,"
                    "retry_at=clock_timestamp()+attempts*interval '60 seconds' "
                    "WHERE id=%s AND lease_token=%s AND lease_until>clock_timestamp() "
                    "AND expires_at>clock_timestamp() RETURNING *",
                    (row["id"], row["lease_token"]),
                ).fetchone()
                if retry is None:
                    return None
                self.store.audit(conn, ctx, "document.job_retry", "document_job", str(row["id"]))
                return _public(retry)
        except (AccessDenied, LeaseLost):
            return None

    def run_once(
        self,
        worker: Principal,
        account: UUID,
        processor: PdfProcessor,
    ) -> dict[str, Any] | None:
        ctx = worker.context
        if worker.client_kind != "worker":
            raise AccessDenied("worker principal required")
        self.store.require(ctx, "email.document.process")
        version = self.processor_version
        if version is None or processor.processor_version != version:
            raise Conflict("configured document processor differs")
        row = self._claim(ctx, account)
        if row is None:
            return None
        if row["status"] != "running":
            return _public(row)
        try:
            with self.store.transaction(ctx) as conn:
                source = self._fence(conn, ctx, row)
                cached = self._cached(conn, row)
                if cached:
                    return self._complete(conn, ctx, row, cached["id"])
            owner = TenantContext(
                ctx.tenant_id, row["actor_id"], frozenset({"email.evidence.read"}), uuid4()
            )
            raw = self.store.load_raw(owner, account, source["raw_sha256"])
            identity = PdfSource(source["raw_sha256"], source["part_id"], source["sha256"])
            if source_for(raw, source["part_id"], source["sha256"]) != identity:
                raise LeaseLost()
            with self.store.transaction(ctx) as conn:
                self._fence(conn, ctx, row)
            if processor.processor_version != version or self.processor_version != version:
                raise LeaseLost()
            result = processor.extract(
                raw, part_path=source["part_id"], part_sha256=source["sha256"]
            )
            payload = encode_result(result)
            decode_result(payload, identity)
            if processor.processor_version != version or self.processor_version != version:
                raise LeaseLost()
            with self.store.transaction(ctx) as conn:
                self._fence(conn, ctx, row)
                cached = self._cached(conn, row)
                if cached is None:
                    cached = conn.execute(
                        "INSERT INTO document_extractions(tenant_id,account_id,receipt_id,"
                        "processor_version,policy_version,revision,result) "
                        "SELECT %s,%s,%s,%s,%s,coalesce(max(revision),0)+1,%s "
                        "FROM document_extractions WHERE account_id=%s AND receipt_id=%s "
                        "RETURNING id",
                        (
                            ctx.tenant_id,
                            account,
                            row["receipt_id"],
                            version,
                            POLICY,
                            Jsonb(json.loads(payload)),
                            account,
                            row["receipt_id"],
                        ),
                    ).fetchone()
                    assert cached is not None
                return self._complete(conn, ctx, row, cached["id"])
        except Exception:
            return self._failed(ctx, row)
