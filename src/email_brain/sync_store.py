"""Database-clock leases and content-free worker telemetry; no network operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from email_brain.connectors.jmap import ScopedMailWindow
from email_brain.domain.models import TenantContext
from email_brain.store import Conflict, InventoryError, NotFound, Store

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

    def reconciliation_candidates(
        self, ctx: TenantContext, account_id: UUID, generation: UUID
    ) -> tuple[str, ...]:
        """A complete inventory certificate is required before inferring absence."""
        self.store.require(ctx, "email.ingest")
        with self.store.transaction(ctx) as conn:
            seal = conn.execute(
                "SELECT 1 FROM sync_inventory_seals WHERE account_id=%s AND generation=%s",
                (account_id, generation),
            ).fetchone()
            if not seal:
                raise InventoryError("uncertified inventory cannot reconcile")
            rows = conn.execute(
                "SELECT h.provider_id FROM message_sync_state h WHERE h.account_id=%s "
                "AND h.status<>'deleted' AND NOT EXISTS (SELECT 1 FROM sync_inventory i "
                "WHERE i.tenant_id=h.tenant_id AND i.account_id=h.account_id "
                "AND i.provider_id=h.provider_id AND i.generation=%s) "
                "ORDER BY h.provider_id LIMIT 8",
                (account_id, generation),
            ).fetchall()
            return tuple(row["provider_id"] for row in rows)

    def retained_blobs(
        self, ctx: TenantContext, account_id: UUID, provider_ids: tuple[str, ...]
    ) -> dict[str, tuple[str, str]]:
        """Blob identity and digest already retained for these messages, if any."""
        return self.store.retained_blobs(ctx, account_id, provider_ids)

    def retained_raw(self, ctx: TenantContext, account_id: UUID, sha: str) -> bytes:
        return self.store.retained_raw_for_ingest(ctx, account_id, sha)

    def acquire(
        self, ctx: TenantContext, account_id: UUID, *, scope: ScopedMailWindow | None = None
    ) -> Lease | None:
        self.store.require(ctx, "email.ingest")
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:{account_id}",),
            )
            account = conn.execute(
                "SELECT provider_account_id,read_scope_sha256 FROM mail_accounts WHERE id=%s "
                "AND provider='fastmail' AND status='active'",
                (account_id,),
            ).fetchone()
            if not account or not account["provider_account_id"]:
                raise NotFound("active enrolled account required")
            scope_sha256 = scope.fingerprint() if scope is not None else None
            if account["read_scope_sha256"] != scope_sha256:
                raise InventoryError("worker scope does not match enrolled account")
            conn.execute(
                "INSERT INTO sync_workers(tenant_id,account_id,read_scope_sha256) "
                "VALUES (%s,%s,%s) "
                "ON CONFLICT DO NOTHING",
                (ctx.tenant_id, account_id, scope_sha256),
            )
            token = uuid4()
            worker = conn.execute(
                "UPDATE sync_workers SET lease_token=%s,provider_account_id=%s,"
                "read_scope_sha256=%s,scope_claim_token=%s,"
                "lease_until=clock_timestamp()+make_interval(secs=>%s),updated_at=now() "
                "WHERE account_id=%s AND NOT paused AND lease_until<=clock_timestamp() "
                "AND next_attempt_at<=clock_timestamp() RETURNING failures",
                (
                    token, account["provider_account_id"], scope_sha256,
                    token if scope is not None else None, LEASE_SECONDS, account_id,
                ),
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
                "UPDATE sync_workers SET lease_token=NULL,scope_claim_token=NULL,"
                "lease_until=clock_timestamp(),"
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
