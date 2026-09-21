"""Append-only structured memory, reviewed publication and independent change cursors."""

from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.memory_extract import extract
from email_brain.memory_schema import MemoryWrite
from email_brain.store import AccessDenied, Conflict, NotFound, Store, digest

Connection = psycopg.Connection[dict[str, Any]]
# Public fields are explicit: no actor IDs, request hashes or internal object paths.
SELECT = (
    "SELECT r.id AS cursor,r.record_id,r.revision,r.evidence_id,r.source_quote,"
    "r.parent_trip_id,r.payload,r.recorded_at,"
    "(NOT m.deleted AND NOT m.quarantined AND m.raw_sha256=v.raw_sha256 "
    "AND m.parser_version=v.parser_version) AS source_current "
    "FROM memory_revisions r JOIN message_versions v ON v.tenant_id=r.tenant_id "
    "AND v.id=r.evidence_id JOIN messages m ON m.tenant_id=v.tenant_id AND m.id=v.message_id "
)


class Memory:
    def __init__(self, store: Store) -> None:
        self.store = store

    def human(self, principal: Principal) -> TenantContext:
        if principal.client_kind != "human":
            raise AccessDenied()
        self.store.require(principal.context, "email.review")
        self.store.require(principal.context, "email.evidence.read")
        return principal.context

    @staticmethod
    def account(conn: Connection, account: UUID) -> None:
        if not conn.execute(
            "SELECT 1 FROM mail_accounts WHERE id=%s AND status='active'", (account,)
        ).fetchone():
            raise NotFound()

    @staticmethod
    def source(conn: Connection, account: UUID, evidence: UUID) -> dict[str, Any]:
        row = conn.execute(
            "SELECT v.snapshot FROM message_versions v JOIN messages m "
            "ON m.tenant_id=v.tenant_id AND m.id=v.message_id "
            "WHERE v.account_id=%s AND v.id=%s AND NOT m.deleted AND NOT m.quarantined "
            "AND m.raw_sha256=v.raw_sha256 AND m.parser_version=v.parser_version",
            (account, evidence),
        ).fetchone()
        if row is None:
            raise NotFound()
        return dict(row["snapshot"])

    @staticmethod
    def public(row: dict[str, Any]) -> dict[str, Any]:
        return {
            **row,
            "citation": f"emailbrain://evidence/{row['evidence_id']}",
            "trust": "owner_reviewed_email_claim",
            "live_verified": False,
        }

    def candidate(self, principal: Principal, account: UUID, evidence: UUID) -> dict[str, Any]:
        ctx = self.human(principal)
        with self.store.transaction(ctx) as conn:
            self.account(conn, account)
            source = self.source(conn, account, evidence)
            result = extract(source["text"] if not source.get("truncated", True) else "")
            self.store.audit(conn, ctx, "memory.candidate", "evidence", str(evidence))
            return {
                **result,
                "account_id": account,
                "evidence_id": evidence,
                "untrusted_content": True,
                "published": False,
            }

    def publish(
        self, principal: Principal, account: UUID, record: UUID, request: MemoryWrite, key: UUID
    ) -> dict[str, Any]:
        ctx = self.human(principal)
        request = MemoryWrite.model_validate(request.model_dump(mode="json"))
        request_hash = digest(
            {"account": account, "record": record, "request": request.model_dump(mode="json")}
        )
        with self.store.transaction(ctx) as conn:
            # Same lock as ingestion/recovery; prevent source replacement during publication.
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:{account}",),
            )
            self.account(conn, account)
            authority = conn.execute(
                "SELECT lock_recovery_owners(%s,%s,%s) AS allowed",
                (account, ctx.actor_id, ctx.actor_id),
            ).fetchone()
            if not authority or not authority["allowed"]:
                raise AccessDenied()
            # Assign the stream sequence only after acquiring the commit-order lock.
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"memory:{ctx.tenant_id}",)
            )
            receipt = conn.execute(
                "SELECT request_hash,result_revision,changed FROM memory_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, key),
            ).fetchone()
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise Conflict()
                saved = conn.execute(
                    SELECT + "WHERE r.account_id=%s AND r.revision=%s",
                    (account, receipt["result_revision"]),
                ).fetchone()
                assert saved is not None
                self.store.audit(conn, ctx, "memory.replay", "memory", str(record))
                return {"record": self.public(saved), "changed": receipt["changed"]}
            source = self.source(conn, account, request.evidence_id)
            if request.source_quote not in source["text"]:
                raise Conflict("source quote does not match retained text")
            existing = conn.execute(
                "SELECT kind FROM memory_records WHERE account_id=%s AND id=%s",
                (account, record),
            ).fetchone()
            current = conn.execute(
                SELECT + "WHERE r.account_id=%s AND r.record_id=%s "
                "ORDER BY r.revision DESC LIMIT 1",
                (account, record),
            ).fetchone()
            if (current["revision"] if current else 0) != request.expected_revision:
                raise Conflict()
            if existing and existing["kind"] != request.payload.kind:
                raise Conflict("record kind is immutable")
            if request.parent_trip_id:
                parent = conn.execute(
                    "SELECT 1 FROM memory_records WHERE account_id=%s AND id=%s AND kind='trip'",
                    (account, request.parent_trip_id),
                ).fetchone()
                if not parent:
                    raise NotFound()
            payload = request.payload.model_dump(mode="json")
            changed = current is None or any(
                (
                    current["payload"] != payload,
                    current["evidence_id"] != request.evidence_id,
                    current["source_quote"] != request.source_quote,
                    current["parent_trip_id"] != request.parent_trip_id,
                )
            )
            if changed:
                if not existing:
                    # An ID already assigned in another account cannot be repurposed.
                    if conn.execute(
                        "SELECT 1 FROM memory_records WHERE id=%s", (record,)
                    ).fetchone():
                        raise Conflict()
                    conn.execute(
                        "INSERT INTO memory_records(tenant_id,account_id,id,kind) "
                        "VALUES (%s,%s,%s,%s)",
                        (ctx.tenant_id, account, record, request.payload.kind),
                    )
                next_row = conn.execute(
                    "SELECT coalesce(max(revision),0)+1 AS next FROM memory_revisions"
                ).fetchone()
                assert next_row is not None
                revision = next_row["next"]
                conn.execute(
                    "INSERT INTO memory_revisions(tenant_id,account_id,record_id,revision,"
                    "actor_id,evidence_id,source_quote,parent_trip_id,payload) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        account,
                        record,
                        revision,
                        ctx.actor_id,
                        request.evidence_id,
                        request.source_quote,
                        request.parent_trip_id,
                        Jsonb(payload),
                    ),
                )
                current = conn.execute(
                    SELECT + "WHERE r.account_id=%s AND r.revision=%s", (account, revision)
                ).fetchone()
            assert current is not None
            conn.execute(
                "INSERT INTO memory_receipts(tenant_id,actor_id,idempotency_key,request_hash,"
                "result_revision,changed) VALUES (%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, ctx.actor_id, key, request_hash, current["revision"], changed),
            )
            self.store.audit(
                conn,
                ctx,
                "memory.publish" if changed else "memory.unchanged",
                "memory",
                str(record),
            )
            return {"record": self.public(current), "changed": changed}

    def records(
        self, ctx: TenantContext, account: UUID, *, after: UUID | None = None, limit: int = 25
    ) -> dict[str, Any]:
        self.store.require(ctx, "email.evidence.read")
        self.page_limit(limit)
        with self.store.transaction(ctx) as conn:
            self.account(conn, account)
            if (
                after
                and not conn.execute(
                    "SELECT 1 FROM memory_records WHERE account_id=%s AND id=%s", (account, after)
                ).fetchone()
            ):
                raise NotFound()
            rows = conn.execute(
                SELECT + "WHERE r.account_id=%s AND (%s::uuid IS NULL OR r.record_id>%s) "
                "AND NOT EXISTS (SELECT 1 FROM memory_revisions n WHERE n.record_id=r.record_id "
                "AND n.tenant_id=r.tenant_id AND n.revision>r.revision) "
                "ORDER BY r.record_id LIMIT %s",
                (account, after, after, limit + 1),
            ).fetchall()
            self.store.audit(conn, ctx, "memory.list", "account", str(account))
            return {
                "results": [self.public(r) for r in rows[:limit]],
                "next_after": rows[limit - 1]["record_id"] if len(rows) > limit else None,
                "snapshot_consistent": False,
            }

    def get(
        self, ctx: TenantContext, account: UUID, record: UUID, *, at: UUID | None = None
    ) -> dict[str, Any]:
        self.store.require(ctx, "email.evidence.read")
        with self.store.transaction(ctx) as conn:
            self.account(conn, account)
            row = conn.execute(
                SELECT + "WHERE r.account_id=%s AND r.record_id=%s "
                "AND (%s::uuid IS NULL OR r.id=%s) "
                "ORDER BY r.revision DESC LIMIT 1",
                (account, record, at, at),
            ).fetchone()
            if row is None:
                raise NotFound()
            self.store.audit(conn, ctx, "memory.read", "memory", str(record))
            return self.public(row)

    @staticmethod
    def page_limit(limit: int) -> None:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("page limit must be 1..50")

    def changes(
        self, ctx: TenantContext, account: UUID, *, after: UUID | None = None, limit: int = 25
    ) -> dict[str, Any]:
        self.store.require(ctx, "email.evidence.read")
        self.page_limit(limit)
        with self.store.transaction(ctx) as conn:
            self.account(conn, account)
            revision = 0
            if after:
                anchor = conn.execute(
                    "SELECT revision FROM memory_revisions WHERE account_id=%s AND id=%s",
                    (account, after),
                ).fetchone()
                if not anchor:
                    raise NotFound()
                revision = anchor["revision"]
            rows = conn.execute(
                "SELECT id AS cursor,record_id,revision,recorded_at,payload->>'kind' AS kind "
                "FROM memory_revisions WHERE account_id=%s AND revision>%s "
                "ORDER BY revision LIMIT %s",
                (account, revision, limit + 1),
            ).fetchall()
            page = rows[:limit]
            self.store.audit(conn, ctx, "memory.changes", "account", str(account))
            return {
                "changes": page,
                "next_cursor": page[-1]["cursor"] if page else after,
                "has_more": len(rows) > limit,
                "consumed": False,
                "scope": "reviewed_memory_only",
            }

    def summary(self, ctx: TenantContext, account: UUID) -> dict[str, Any]:
        self.store.require(ctx, "email.evidence.read")
        with self.store.transaction(ctx) as conn:
            self.account(conn, account)
            buckets = conn.execute(
                "SELECT CASE WHEN payload->>'kind'='bill' THEN 'bills' ELSE 'travel' END AS bucket,"
                "max(revision) AS revision,max(recorded_at) AS last_changed_at "
                "FROM memory_revisions WHERE account_id=%s GROUP BY 1 ORDER BY 1",
                (account,),
            ).fetchall()
            checked = conn.execute(
                "SELECT max(recorded_at) AS last_checked_at,"
                "coalesce(max(recorded_at)>=clock_timestamp()-interval '15 minutes',false) "
                "AS checked_recently FROM sync_runs WHERE account_id=%s AND outcome='caught_up'",
                (account,),
            ).fetchone()
            assert checked is not None
            worker = conn.execute(
                "SELECT last_outcome,paused FROM sync_workers WHERE account_id=%s", (account,)
            ).fetchone()
            latest = conn.execute(
                "SELECT id FROM memory_revisions WHERE account_id=%s "
                "ORDER BY revision DESC LIMIT 1",
                (account,),
            ).fetchone()
            self.store.audit(conn, ctx, "memory.summary", "account", str(account))
            known = {r["bucket"]: r for r in buckets}
            return {
                "account_id": account,
                "buckets": [
                    known.get(name, {"bucket": name, "revision": 0, "last_changed_at": None})
                    for name in ("travel", "bills")
                ],
                "latest_cursor": latest["id"] if latest else None,
                **checked,
                "worker": worker,
                "freshness_threshold_seconds": 900,
                "needs_refresh": not checked["checked_recently"]
                or not worker
                or worker["paused"]
                or worker["last_outcome"] != "caught_up",
                "interpretation_coverage": "partial_manual_review",
                "all_mail_interpreted": False,
                "live_verified": False,
            }
