"""Database-clock leases and content-free worker telemetry; no network operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from email_brain.domain.models import TenantContext
from email_brain.store import Conflict, NotFound, Store

Outcome = Literal[
    "progress",
    "caught_up",
    "retry",
    "auth_required",
    "protocol_error",
    "parse_error",
    "resync_required",
]
LEASE_SECONDS = 90


@dataclass(frozen=True)
class Lease:
    token: UUID
    provider_account_id: str
    cursor: str | None
    failures: int


class SyncStore:
    def __init__(self, store: Store) -> None:
        self.store = store

    def acquire(self, ctx: TenantContext, account_id: UUID) -> Lease | None:
        self.store.require(ctx, "email.ingest")
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:{account_id}",),
            )
            account = conn.execute(
                "SELECT provider_account_id FROM mail_accounts WHERE id=%s "
                "AND provider='fastmail' AND status='active'",
                (account_id,),
            ).fetchone()
            if not account or not account["provider_account_id"]:
                raise NotFound("active enrolled account required")
            conn.execute(
                "INSERT INTO sync_workers(tenant_id,account_id) VALUES (%s,%s) "
                "ON CONFLICT DO NOTHING",
                (ctx.tenant_id, account_id),
            )
            token = uuid4()
            worker = conn.execute(
                "UPDATE sync_workers SET lease_token=%s,"
                "lease_until=clock_timestamp()+make_interval(secs=>%s),updated_at=now() "
                "WHERE account_id=%s AND NOT paused AND lease_until<=clock_timestamp() "
                "AND next_attempt_at<=clock_timestamp() RETURNING failures",
                (token, LEASE_SECONDS, account_id),
            ).fetchone()
            if not worker:
                return None
            cursor = conn.execute(
                "SELECT opaque_cursor FROM sync_cursors WHERE account_id=%s AND scope='email'",
                (account_id,),
            ).fetchone()
            return Lease(
                token,
                account["provider_account_id"],
                cursor["opaque_cursor"] if cursor else None,
                worker["failures"],
            )

    def renew(self, ctx: TenantContext, account_id: UUID, token: UUID) -> None:
        self.store.require(ctx, "email.ingest")
        with self.store.transaction(ctx) as conn:
            row = conn.execute(
                "UPDATE sync_workers SET lease_until=clock_timestamp()+make_interval(secs=>%s) "
                "WHERE account_id=%s AND lease_token=%s AND lease_until>clock_timestamp() "
                "AND NOT paused RETURNING account_id",
                (LEASE_SECONDS, account_id, token),
            ).fetchone()
            if not row:
                raise Conflict("worker lease expired or replaced")

    def finish(
        self,
        ctx: TenantContext,
        account_id: UUID,
        token: UUID,
        outcome: Outcome,
        count: int = 0,
        delay: int = 0,
    ) -> None:
        self.store.require(ctx, "email.ingest")
        if not 0 <= delay <= 86400 or not 0 <= count <= 100:
            raise ValueError("invalid worker result")
        failed = outcome not in {"progress", "caught_up"}
        paused = outcome in {"auth_required", "protocol_error", "parse_error", "resync_required"}
        with self.store.transaction(ctx) as conn:
            row = conn.execute(
                "UPDATE sync_workers SET lease_token=NULL,lease_until='-infinity',"
                "next_attempt_at=clock_timestamp()+make_interval(secs=>%s),"
                "failures=CASE WHEN %s THEN least(failures+1,1000) ELSE 0 END,"
                "paused=%s,last_outcome=%s,updated_at=now() WHERE account_id=%s "
                "AND lease_token=%s AND lease_until>clock_timestamp() RETURNING account_id",
                (delay, failed, paused, outcome, account_id, token),
            ).fetchone()
            if not row:
                raise Conflict("worker lease expired or replaced")
            conn.execute(
                "INSERT INTO sync_runs(tenant_id,account_id,request_id,outcome,event_count) "
                "VALUES (%s,%s,%s,%s,%s)",
                (ctx.tenant_id, account_id, ctx.request_id, outcome, count),
            )
            self.store.audit(conn, ctx, f"sync.{outcome}", "account", str(account_id))
