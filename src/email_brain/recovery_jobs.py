"""Durable human approvals and fenced worker recovery; no Docker/API coupling."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import psycopg

from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.recovery import MimeProcessor, Recovery
from email_brain.store import AccessDenied, Conflict, NotFound, Store

_PARSER = re.compile(r"sandbox-mime-v1-[a-f0-9]{64}\Z", re.ASCII)
_APPROVAL_SCOPES = frozenset({"email.evidence.read", "email.review"})
_TERMINAL = frozenset({"completed", "cancelled", "expired", "failed", "stale", "revoked"})
_PUBLIC = (
    "id",
    "account_id",
    "receipt_id",
    "parser_version",
    "status",
    "attempts",
    "created_at",
    "expires_at",
    "retry_at",
    "completed_at",
    "attempt_id",
    "outcome",
)


class LeaseLost(Exception):
    """Approval, ownership, source state or lease no longer authorizes publication."""


def _public(row: dict[str, Any]) -> dict[str, Any]:
    return {**{key: row[key] for key in _PUBLIC}, "mailbox_effects": False}


def _account_lock(conn: psycopg.Connection[dict[str, Any]], tenant: UUID, account: UUID) -> None:
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"{tenant}:{account}",))


def _owners(
    conn: psycopg.Connection[dict[str, Any]],
    account: UUID,
    requester: UUID,
    worker: UUID,
) -> bool:
    row = conn.execute(
        "SELECT public.lock_recovery_owners(%s,%s,%s) AS allowed",
        (account, requester, worker),
    ).fetchone()
    return bool(row and row["allowed"])


def _source(conn: psycopg.Connection[dict[str, Any]], row: dict[str, Any]) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM quarantine_receipts q JOIN message_sync_state s "
            "ON s.tenant_id=q.tenant_id AND s.account_id=q.account_id "
            "AND s.provider_id=q.provider_id "
            "WHERE q.account_id=%s AND q.id=%s AND q.event_key=s.event_key "
            "AND (s.status='quarantined' OR (s.status='ready' AND EXISTS "
            "(SELECT 1 FROM recovery_attempts a WHERE a.tenant_id=q.tenant_id "
            "AND a.receipt_id=q.id AND a.parser_version=%s)))",
            (row["account_id"], row["receipt_id"], row["parser_version"]),
        ).fetchone()
        is not None
    )


def _clock(conn: psycopg.Connection[dict[str, Any]], job: UUID) -> dict[str, Any]:
    row = conn.execute(
        "SELECT expires_at>clock_timestamp() AS approved, "
        "lease_until>clock_timestamp() AS leased FROM recovery_jobs WHERE id=%s",
        (job,),
    ).fetchone()
    if row is None:
        raise LeaseLost()
    return row


@dataclass(frozen=True)
class _JobFence:
    store: Store
    worker: TenantContext
    job_id: UUID
    account_id: UUID
    actor_id: UUID
    receipt_id: UUID
    parser_version: str
    lease_token: UUID

    def check(self, conn: psycopg.Connection[dict[str, Any]]) -> None:
        row = conn.execute(
            "SELECT * FROM recovery_jobs WHERE id=%s AND account_id=%s FOR UPDATE",
            (self.job_id, self.account_id),
        ).fetchone()
        if (
            row is None
            or row["tenant_id"] != self.worker.tenant_id
            or row["actor_id"] != self.actor_id
            or row["receipt_id"] != self.receipt_id
            or row["parser_version"] != self.parser_version
            or row["status"] != "running"
            or row["lease_token"] != self.lease_token
            or row["worker_actor_id"] != self.worker.actor_id
            or frozenset(row["approval_scopes"]) != _APPROVAL_SCOPES
        ):
            raise LeaseLost()
        # Protect cached-attempt completion too. Provider ingestion uses the same
        # account lock; no locks survive either short Recovery transaction.
        _account_lock(conn, self.worker.tenant_id, self.account_id)
        if not _owners(conn, self.account_id, self.actor_id, self.worker.actor_id):
            raise LeaseLost()
        if not _source(conn, row):
            raise LeaseLost()
        current = _clock(conn, self.job_id)
        if not current["approved"] or not current["leased"]:
            raise LeaseLost()

    def complete(self, conn: psycopg.Connection[dict[str, Any]], attempt: dict[str, Any]) -> None:
        self.check(conn)
        if (
            attempt["receipt_id"] != self.receipt_id
            or attempt["parser_version"] != self.parser_version
        ):
            raise LeaseLost()
        row = conn.execute(
            "UPDATE recovery_jobs SET status='completed',attempt_id=%s,outcome=%s,"
            "completed_at=clock_timestamp(),lease_token=NULL,lease_until=NULL,retry_at=NULL "
            "WHERE id=%s AND status='running' AND lease_token=%s "
            "AND expires_at>clock_timestamp() AND lease_until>clock_timestamp() RETURNING id",
            (attempt["id"], attempt["outcome"], self.job_id, self.lease_token),
        ).fetchone()
        if row is None:
            raise LeaseLost()
        self.store.audit(
            conn, self.worker, "recovery.job_completed", "recovery_job", str(self.job_id)
        )


class RecoveryJobs:
    def __init__(self, store: Store, parser_version: str | None = None) -> None:
        if parser_version is not None and (
            not isinstance(parser_version, str) or not _PARSER.fullmatch(parser_version)
        ):
            raise ValueError("invalid configured recovery parser")
        self.store, self.parser_version = store, parser_version

    @staticmethod
    def _human(principal: Principal) -> TenantContext:
        if principal.client_kind != "human":
            raise AccessDenied("human approval required")
        for scope in _APPROVAL_SCOPES:
            Store.require(principal.context, scope)
        return principal.context

    @staticmethod
    def _account(
        conn: psycopg.Connection[dict[str, Any]],
        account: UUID,
        *,
        active: bool = False,
    ) -> dict[str, Any]:
        row = conn.execute("SELECT id,status FROM mail_accounts WHERE id=%s", (account,)).fetchone()
        if row is None or (active and row["status"] != "active"):
            raise NotFound()
        return row

    def capabilities(self, ctx: TenantContext, account: UUID) -> dict[str, Any]:
        self.store.require(ctx, "email.evidence.read")
        with self.store.transaction(ctx) as conn:
            row = self._account(conn, account)
        return {
            "enabled": self.parser_version is not None and row["status"] == "active",
            "parser_version": self.parser_version,
            "worker_online": None,
            "mailbox_effects": False,
        }

    def enqueue(
        self,
        principal: Principal,
        account: UUID,
        receipt: UUID,
        parser: str,
        key: UUID,
    ) -> dict[str, Any]:
        ctx = self._human(principal)
        if not isinstance(key, UUID):
            raise ValueError("UUID idempotency key required")
        try:
            with self.store.transaction(ctx) as conn:
                _account_lock(conn, ctx.tenant_id, account)
                self._account(conn, account, active=True)
                if self.parser_version is None or parser != self.parser_version:
                    raise Conflict("isolated processing unavailable or parser changed")
                previous = conn.execute(
                    "SELECT * FROM recovery_jobs WHERE actor_id=%s AND idempotency_key=%s",
                    (ctx.actor_id, key),
                ).fetchone()
                if previous:
                    if (
                        previous["account_id"],
                        previous["receipt_id"],
                        previous["parser_version"],
                    ) != (
                        account,
                        receipt,
                        parser,
                    ):
                        raise Conflict("job idempotency key reused")
                    return _public(previous)
                source = Recovery.receipt(conn, account, receipt)
                Recovery.current(source)
                count = conn.execute(
                    "SELECT count(*) AS n FROM recovery_jobs WHERE account_id=%s "
                    "AND status IN ('queued','running','retry_wait')",
                    (account,),
                ).fetchone()
                if count is None or count["n"] >= 100:
                    raise Conflict("account recovery queue is full")
                row = conn.execute(
                    "INSERT INTO recovery_jobs(tenant_id,account_id,receipt_id,actor_id,"
                    "idempotency_key,parser_version) VALUES (%s,%s,%s,%s,%s,%s) RETURNING *",
                    (ctx.tenant_id, account, receipt, ctx.actor_id, key, parser),
                ).fetchone()
                assert row is not None
                self.store.audit(conn, ctx, "recovery.job_enqueued", "recovery_job", str(row["id"]))
                return _public(row)
        except psycopg.errors.UniqueViolation:
            raise Conflict("job idempotency key reused") from None

    def get(self, ctx: TenantContext, account: UUID, job: UUID) -> dict[str, Any]:
        self.store.require(ctx, "email.evidence.read")
        with self.store.transaction(ctx) as conn:
            self._account(conn, account)
            row = conn.execute(
                "SELECT * FROM recovery_jobs WHERE id=%s AND account_id=%s",
                (job, account),
            ).fetchone()
            if row is None:
                raise NotFound()
            return _public(row)

    def list(
        self,
        ctx: TenantContext,
        account: UUID,
        *,
        limit: int = 50,
        after: UUID | None = None,
    ) -> dict[str, Any]:
        """Bounded live history; the cursor must belong to this tenant and account."""
        self.store.require(ctx, "email.evidence.read")
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("history limit must be 1..50")
        if after is not None and not isinstance(after, UUID):
            raise ValueError("history cursor must be a UUID")
        with self.store.transaction(ctx) as conn:
            self._account(conn, account)
            if after is None:
                rows = conn.execute(
                    "SELECT * FROM recovery_jobs WHERE account_id=%s "
                    "ORDER BY created_at DESC,id DESC LIMIT %s",
                    (account, limit + 1),
                ).fetchall()
            else:
                anchor = conn.execute(
                    "SELECT created_at,id FROM recovery_jobs WHERE account_id=%s AND id=%s",
                    (account, after),
                ).fetchone()
                if anchor is None:
                    raise NotFound()
                rows = conn.execute(
                    "SELECT * FROM recovery_jobs WHERE account_id=%s "
                    "AND (created_at,id)<(%s,%s) ORDER BY created_at DESC,id DESC LIMIT %s",
                    (account, anchor["created_at"], after, limit + 1),
                ).fetchall()
            self.store.audit(conn, ctx, "recovery.jobs_read", "account", str(account))
            return {
                "results": [_public(row) for row in rows[:limit]],
                "next_after": rows[limit - 1]["id"] if len(rows) > limit else None,
                "limit": limit,
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
            "UPDATE recovery_jobs SET status=%s,outcome=%s,completed_at=clock_timestamp(),"
            "lease_token=NULL,lease_until=NULL,retry_at=NULL WHERE id=%s "
            "AND (%s::uuid IS NULL OR (lease_token=%s AND lease_until>clock_timestamp())) "
            "RETURNING *",
            (status, outcome, job, lease_token, lease_token),
        ).fetchone()
        if row is None:
            raise LeaseLost()
        self.store.audit(conn, ctx, "recovery.job_" + status, "recovery_job", str(job))
        return row

    def cancel(self, principal: Principal, account: UUID, job: UUID) -> dict[str, Any]:
        ctx = self._human(principal)
        with self.store.transaction(ctx) as conn:
            self._account(conn, account)
            row = conn.execute(
                "SELECT * FROM recovery_jobs WHERE id=%s AND account_id=%s FOR UPDATE",
                (job, account),
            ).fetchone()
            if row is None:
                raise NotFound()
            if row["status"] not in _TERMINAL:
                row = self._terminal(conn, ctx, job, "cancelled", "cancelled")
            return _public(row)

    def _claim(self, ctx: TenantContext, account: UUID) -> dict[str, Any] | None:
        with self.store.transaction(ctx) as conn:
            self._account(conn, account)
            row = conn.execute(
                "SELECT * FROM recovery_jobs WHERE account_id=%s AND parser_version=%s "
                "AND status IN ('queued','running','retry_wait') AND "
                "(expires_at<=clock_timestamp() OR status='queued' OR "
                "(status='running' AND lease_until<=clock_timestamp()) OR "
                "(status='retry_wait' AND retry_at<=clock_timestamp())) "
                "ORDER BY created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED",
                (account, self.parser_version),
            ).fetchone()
            if row is None:
                return None
            _account_lock(conn, ctx.tenant_id, account)
            approved = _clock(conn, row["id"])["approved"]
            if not approved:
                return self._terminal(conn, ctx, row["id"], "expired", "approval_expired")
            if row["attempts"] >= 3:
                return self._terminal(conn, ctx, row["id"], "failed", "attempts_exhausted")
            if not _owners(conn, account, row["actor_id"], ctx.actor_id):
                return self._terminal(conn, ctx, row["id"], "revoked", "authorization_revoked")
            if not _source(conn, row):
                return self._terminal(conn, ctx, row["id"], "stale", "source_changed")
            claimed = conn.execute(
                "UPDATE recovery_jobs SET status='running',attempts=attempts+1,lease_token=%s,"
                "lease_until=clock_timestamp()+interval '120 seconds',worker_actor_id=%s,"
                "retry_at=NULL,outcome=NULL WHERE id=%s "
                "AND expires_at>clock_timestamp() RETURNING *",
                (uuid4(), ctx.actor_id, row["id"]),
            ).fetchone()
            if claimed is None:
                return self._terminal(conn, ctx, row["id"], "expired", "approval_expired")
            self.store.audit(conn, ctx, "recovery.job_claimed", "recovery_job", str(row["id"]))
            return claimed

    def _failed(self, ctx: TenantContext, row: dict[str, Any]) -> dict[str, Any] | None:
        # Do not let a revoked worker mutate or inspect even its formerly leased job.
        try:
            with self.store.transaction(ctx) as conn:
                current = conn.execute(
                    "SELECT * FROM recovery_jobs WHERE id=%s AND account_id=%s FOR UPDATE",
                    (row["id"], row["account_id"]),
                ).fetchone()
                if current is None:
                    return None
                if current["status"] != "running" or current["lease_token"] != row["lease_token"]:
                    return _public(current)
                _account_lock(conn, ctx.tenant_id, row["account_id"])
                authorized = _owners(conn, row["account_id"], row["actor_id"], ctx.actor_id)
                source_current = _source(conn, current) if authorized else False
                timing = _clock(conn, row["id"])
                if not timing["leased"]:
                    return _public(current)
                if not timing["approved"]:
                    current = self._terminal(
                        conn,
                        ctx,
                        row["id"],
                        "expired",
                        "approval_expired",
                        lease_token=row["lease_token"],
                    )
                elif not authorized:
                    current = self._terminal(
                        conn,
                        ctx,
                        row["id"],
                        "revoked",
                        "authorization_revoked",
                        lease_token=row["lease_token"],
                    )
                elif not source_current:
                    current = self._terminal(
                        conn,
                        ctx,
                        row["id"],
                        "stale",
                        "source_changed",
                        lease_token=row["lease_token"],
                    )
                elif current["attempts"] >= 3:
                    current = self._terminal(
                        conn,
                        ctx,
                        row["id"],
                        "failed",
                        "infrastructure_unavailable",
                        lease_token=row["lease_token"],
                    )
                else:
                    current = conn.execute(
                        "UPDATE recovery_jobs SET status='retry_wait',"
                        "outcome='infrastructure_unavailable',lease_token=NULL,lease_until=NULL,"
                        "retry_at=clock_timestamp()+attempts*interval '60 seconds' "
                        "WHERE id=%s AND lease_token=%s AND lease_until>clock_timestamp() "
                        "AND expires_at>clock_timestamp() RETURNING *",
                        (row["id"], row["lease_token"]),
                    ).fetchone()
                    if current is None:
                        raise LeaseLost()
                    self.store.audit(
                        conn, ctx, "recovery.job_retry", "recovery_job", str(row["id"])
                    )
                return _public(current)
        except (AccessDenied, LeaseLost):
            return None

    def run_once(
        self,
        worker: Principal,
        account: UUID,
        processor: MimeProcessor,
    ) -> dict[str, Any] | None:
        if worker.client_kind != "worker":
            raise AccessDenied("worker principal required")
        ctx = worker.context
        self.store.require(ctx, "email.process")
        if self.parser_version is None or processor.parser_version != self.parser_version:
            raise Conflict("configured processor differs from job channel")
        expected_limit = processor.max_raw_bytes
        recovery = Recovery(self.store, processor=processor)
        row = self._claim(ctx, account)
        if row is None:
            return None
        if row["status"] != "running":
            return _public(row)
        approved = Principal(
            TenantContext(
                ctx.tenant_id, row["actor_id"], frozenset(row["approval_scopes"]), uuid4()
            ),
            "human",
        )
        fence = _JobFence(
            self.store,
            ctx,
            row["id"],
            account,
            row["actor_id"],
            row["receipt_id"],
            row["parser_version"],
            row["lease_token"],
        )
        try:
            if (
                processor.parser_version != self.parser_version
                or processor.max_raw_bytes != expected_limit
            ):
                raise LeaseLost()
            recovery._retry(
                approved, account, row["receipt_id"], row["parser_version"], fence=fence
            )
        except Exception:
            return self._failed(ctx, row)
        with self.store.transaction(ctx) as conn:
            completed = conn.execute(
                "SELECT * FROM recovery_jobs WHERE id=%s", (row["id"],)
            ).fetchone()
            return _public(completed) if completed else None
