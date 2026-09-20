"""Transactional PostgreSQL persistence. All runtime access uses an authenticated context."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from email_brain.attachments import Attachment, receive_attachments, reconcile
from email_brain.domain.models import TenantContext
from email_brain.normalize import PARSER_VERSION, normalize
from email_brain.schemas import CorrectionPayload, ProposalRequest, ReviewRequest, SearchRequest


class Conflict(Exception):
    """Retry requires reconciliation or a new idempotency key."""


class NotFound(Exception):
    """Missing and unauthorized identifiers are indistinguishable."""


class AccessDenied(Exception):
    """The principal has no current owner membership."""


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


@dataclass(frozen=True)
class IngestItem:
    event_key: str
    provider_id: str
    version: str
    received_at: datetime
    raw: bytes | None = None  # None is an explicit provider tombstone.
    thread_id: str | None = None

    def __post_init__(self) -> None:
        if not all(0 < len(v) <= 1000 for v in (self.event_key, self.provider_id, self.version)):
            raise ValueError("event identifiers must contain 1..1000 characters")
        if self.received_at.tzinfo is None:
            raise ValueError("received_at must be timezone-aware")


class Store:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    @staticmethod
    def require(ctx: TenantContext, scope: str) -> None:
        if scope not in ctx.scopes:
            raise AccessDenied("scope denied")

    @staticmethod
    def record_attachments(
        conn: psycopg.Connection[dict[str, Any]],
        ctx: TenantContext,
        account_id: UUID,
        evidence_id: UUID,
        attachments: list[Attachment],
    ) -> None:
        for attachment in attachments:
            duplicate = conn.execute(
                "SELECT id FROM attachment_receipts WHERE account_id=%s AND sha256=%s "
                "ORDER BY received_at,id LIMIT 1",
                (account_id, attachment.sha256),
            ).fetchone()
            receipt = conn.execute(
                "INSERT INTO attachment_receipts(tenant_id,account_id,evidence_id,part_id,"
                "original_filename,safe_filename,media_type,sha256,byte_size,status,reason,"
                "extracted_text,duplicate_of) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,evidence_id,part_id) DO NOTHING RETURNING id",
                (
                    ctx.tenant_id,
                    account_id,
                    evidence_id,
                    attachment.part_id,
                    attachment.original_filename,
                    attachment.safe_filename,
                    attachment.media_type,
                    attachment.sha256,
                    attachment.byte_size,
                    attachment.status,
                    attachment.reason,
                    attachment.text,
                    duplicate["id"] if duplicate else None,
                ),
            ).fetchone()
            if receipt:
                conn.execute(
                    "INSERT INTO intake_events(tenant_id,receipt_id,actor_id,state,reason,sha256) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        receipt["id"],
                        ctx.actor_id,
                        attachment.status,
                        attachment.reason,
                        attachment.sha256,
                    ),
                )

    @contextmanager
    def transaction(self, ctx: TenantContext) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as conn:
            role = conn.execute(
                "SELECT rolsuper, rolbypassrls, "
                "EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE c.relowner=r.oid AND n.nspname='public' AND c.relkind='r') AS owns "
                "FROM pg_roles r WHERE rolname=current_user"
            ).fetchone()
            if not role or role["rolsuper"] or role["rolbypassrls"] or role["owns"]:
                raise AccessDenied("unsafe runtime database role")
            conn.execute("SELECT set_config('statement_timeout', '5000', true)")
            conn.execute("SELECT set_config('lock_timeout', '2000', true)")
            conn.execute(
                "SELECT set_config('email_brain.tenant_id', %s, true)", (str(ctx.tenant_id),)
            )
            conn.execute(
                "SELECT set_config('email_brain.actor_id', %s, true)", (str(ctx.actor_id),)
            )
            membership = conn.execute(
                "SELECT 1 FROM tenant_memberships WHERE tenant_id=%s AND user_id=%s "
                "AND role='owner'",
                (ctx.tenant_id, ctx.actor_id),
            ).fetchone()
            if not membership:
                raise AccessDenied("owner membership required in bootstrap")
            yield conn

    @staticmethod
    def audit(
        conn: psycopg.Connection[dict[str, Any]],
        ctx: TenantContext,
        event: str,
        resource: str,
        identifier: str | None = None,
    ) -> None:
        conn.execute(
            "INSERT INTO audit_events(tenant_id,actor_id,request_id,event_type,"
            "resource_type,resource_id,outcome) VALUES (%s,%s,%s,%s,%s,%s,'ok')",
            (ctx.tenant_id, ctx.actor_id, ctx.request_id, event, resource, identifier),
        )

    def ingest_page(
        self,
        ctx: TenantContext,
        account_id: UUID,
        expected_cursor: str | None,
        next_cursor: str,
        items: Sequence[IngestItem],
    ) -> int:
        if "email.ingest" not in ctx.scopes:
            raise AccessDenied("ingest scope required")
        if len(items) > 100 or not next_cursor or len(next_cursor) > 4000:
            raise ValueError("bounded pages and nonempty cursor required")
        # Parsing failure aborts the page; a future quarantine worker can durably record it.
        prepared = [(item, normalize(item.raw) if item.raw is not None else None) for item in items]
        inserted = 0
        with self.transaction(ctx) as conn:
            account = conn.execute(
                "SELECT id FROM mail_accounts WHERE id=%s AND status='active' FOR UPDATE",
                (account_id,),
            ).fetchone()
            if not account:
                raise NotFound()
            cursor = conn.execute(
                "SELECT opaque_cursor FROM sync_cursors WHERE account_id=%s AND scope='email'",
                (account_id,),
            ).fetchone()
            current = cursor["opaque_cursor"] if cursor else None
            if current != expected_cursor:
                # A retry of an already-committed whole page is a no-op only if every
                # event hash agrees. An empty page can safely be acknowledged as well.
                if current != next_cursor:
                    raise Conflict("stale sync cursor")
                for item, _normalized in prepared:
                    previous = conn.execute(
                        "SELECT event_hash FROM provider_events "
                        "WHERE account_id=%s AND event_key=%s",
                        (account_id, item.event_key),
                    ).fetchone()
                    if not previous or previous["event_hash"] != self._event_hash(item):
                        raise Conflict("page replay differs from committed content")
                return 0
            for item, normalized in prepared:
                event_hash = self._event_hash(item)
                previous = conn.execute(
                    "SELECT event_hash FROM provider_events WHERE account_id=%s AND event_key=%s",
                    (account_id, item.event_key),
                ).fetchone()
                if previous:
                    if previous["event_hash"] != event_hash:
                        raise Conflict("event key reused with different content")
                    continue
                raw_hash = normalized.raw_sha256 if normalized else None
                conn.execute(
                    "INSERT INTO provider_events(tenant_id,account_id,event_key,kind,"
                    "provider_object_id,provider_version,payload_ref,observed_at,event_hash) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        account_id,
                        item.event_key,
                        "upsert_message" if normalized else "delete_message",
                        item.provider_id,
                        item.version,
                        raw_hash,
                        item.received_at,
                        event_hash,
                    ),
                )
                if normalized is None:
                    conn.execute(
                        "UPDATE messages SET deleted=true,provider_version=%s,updated_at=now() "
                        "WHERE account_id=%s AND provider_message_id=%s",
                        (item.version, account_id, item.provider_id),
                    )
                else:
                    conn.execute(
                        "INSERT INTO raw_objects(tenant_id,account_id,sha256,raw_mime) "
                        "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (ctx.tenant_id, account_id, raw_hash, item.raw),
                    )
                    message = conn.execute(
                        "INSERT INTO messages(tenant_id,account_id,provider_message_id,"
                        "provider_version,provider_thread_id,internet_message_id,subject,sender,"
                        "recipients,clean_text,raw_sha256,parser_version,received_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT (tenant_id,account_id,provider_message_id) DO UPDATE SET "
                        "provider_version=excluded.provider_version,"
                        "provider_thread_id=excluded.provider_thread_id,"
                        "internet_message_id=excluded.internet_message_id,subject=excluded.subject,"
                        "sender=excluded.sender,recipients=excluded.recipients,"
                        "clean_text=excluded.clean_text,raw_sha256=excluded.raw_sha256,"
                        "parser_version=excluded.parser_version,received_at=excluded.received_at,"
                        "deleted=false,updated_at=now() RETURNING id",
                        (
                            ctx.tenant_id,
                            account_id,
                            item.provider_id,
                            item.version,
                            item.thread_id,
                            normalized.internet_message_id,
                            normalized.subject,
                            normalized.sender,
                            Jsonb(list(normalized.recipients)),
                            normalized.text,
                            raw_hash,
                            PARSER_VERSION,
                            item.received_at,
                        ),
                    ).fetchone()
                    assert message is not None
                    snapshot = {
                        "subject": normalized.subject,
                        "sender": normalized.sender,
                        "text": normalized.text,
                        "truncated": normalized.truncated,
                        "received_at": item.received_at.isoformat(),
                        "parser_version": PARSER_VERSION,
                    }
                    conn.execute(
                        "INSERT INTO message_versions(tenant_id,account_id,message_id,raw_sha256,"
                        "provider_version,snapshot) VALUES (%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT (tenant_id,message_id,raw_sha256) DO NOTHING",
                        (
                            ctx.tenant_id,
                            account_id,
                            message["id"],
                            raw_hash,
                            item.version,
                            Jsonb(snapshot),
                        ),
                    )
                    version = conn.execute(
                        "SELECT id FROM message_versions WHERE message_id=%s AND raw_sha256=%s",
                        (message["id"], raw_hash),
                    ).fetchone()
                    assert version is not None and item.raw is not None
                    self.record_attachments(
                        conn, ctx, account_id, version["id"], receive_attachments(item.raw)
                    )
                inserted += 1
            conn.execute(
                "INSERT INTO sync_cursors(tenant_id,account_id,scope,cursor_kind,opaque_cursor) "
                "VALUES (%s,%s,'email','provider',%s) ON CONFLICT (tenant_id,account_id,scope) "
                "DO UPDATE SET opaque_cursor=excluded.opaque_cursor,"
                "generation=sync_cursors.generation+1,"
                "updated_at=now()",
                (ctx.tenant_id, account_id, next_cursor),
            )
            self.audit(conn, ctx, "sync.page_committed", "account", str(account_id))
        return inserted

    @staticmethod
    def _event_hash(item: IngestItem) -> str:
        return digest(
            {
                "id": item.provider_id,
                "version": item.version,
                "raw": hashlib.sha256(item.raw).hexdigest() if item.raw is not None else None,
                "thread": item.thread_id,
            }
        )

    def search(self, ctx: TenantContext, request: SearchRequest) -> list[dict[str, Any]]:
        self.require(ctx, "email.search")
        with self.transaction(ctx) as conn:
            rows = conn.execute(
                "SELECT m.id,m.account_id,m.subject,m.sender,m.received_at,v.id AS evidence_id,"
                "left(m.clean_text,500) AS excerpt,"
                "ts_rank_cd(m.search_document,websearch_to_tsquery('simple',%s)) AS score "
                "FROM messages m JOIN message_versions v ON v.tenant_id=m.tenant_id "
                "AND v.message_id=m.id AND v.raw_sha256=m.raw_sha256 "
                "WHERE NOT m.deleted AND (%s::uuid IS NULL OR m.account_id=%s) "
                "AND m.search_document @@ websearch_to_tsquery('simple',%s) "
                "ORDER BY score DESC,m.received_at DESC,m.id LIMIT %s",
                (
                    request.query,
                    request.account_id,
                    request.account_id,
                    request.query,
                    request.limit,
                ),
            ).fetchall()
            for row in rows:
                row["result_type"] = "message"
            if request.include_attachments:
                attachment_rows = conn.execute(
                    "SELECT m.id,m.account_id,m.subject,m.sender,m.received_at,"
                    "a.evidence_id,a.id AS attachment_id,a.safe_filename,"
                    "left(a.extracted_text,500) AS excerpt,"
                    "ts_rank_cd(a.search_document,websearch_to_tsquery('simple',%s)) AS score "
                    "FROM attachment_receipts a JOIN message_versions v ON "
                    "v.tenant_id=a.tenant_id AND v.id=a.evidence_id "
                    "JOIN messages m ON m.tenant_id=v.tenant_id AND m.id=v.message_id "
                    "AND m.raw_sha256=v.raw_sha256 "
                    "WHERE a.status='extracted' AND NOT m.deleted "
                    "AND (%s::uuid IS NULL OR m.account_id=%s) "
                    "AND a.search_document @@ websearch_to_tsquery('simple',%s) "
                    "ORDER BY score DESC,m.received_at DESC,a.id LIMIT %s",
                    (
                        request.query,
                        request.account_id,
                        request.account_id,
                        request.query,
                        request.limit,
                    ),
                ).fetchall()
                for row in attachment_rows:
                    row["result_type"] = "attachment"
                rows.extend(attachment_rows)
                rows.sort(
                    key=lambda row: (
                        -row["score"],
                        -row["received_at"].timestamp(),
                        str(row.get("attachment_id", row["id"])),
                    )
                )
                rows = rows[: request.limit]
            self.audit(conn, ctx, "search.read", "message")
            for row in rows:
                row["citation"] = f"emailbrain://evidence/{row['evidence_id']}"
                if row.get("attachment_id"):
                    row["citation"] += f"#attachment={row['attachment_id']}"
            return rows

    def evidence(self, ctx: TenantContext, evidence_id: UUID) -> dict[str, Any]:
        self.require(ctx, "email.evidence.read")
        with self.transaction(ctx) as conn:
            row = conn.execute(
                "SELECT id,message_id,account_id,raw_sha256,snapshot FROM message_versions "
                "WHERE id=%s",
                (evidence_id,),
            ).fetchone()
            if not row:
                raise NotFound()
            snapshot = row.pop("snapshot")
            excerpt = snapshot.pop("text")[:4000]
            row.update(snapshot)
            row.update(
                {
                    "excerpt": excerpt,
                    "offsets": [0, len(excerpt)],
                    "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
                    "citation": f"emailbrain://evidence/{evidence_id}",
                    "untrusted_content": True,
                }
            )
            attachments = conn.execute(
                "SELECT id,part_id,safe_filename,media_type,sha256,byte_size,status,reason,"
                "scanner_status,duplicate_of,left(extracted_text,2000) AS excerpt "
                "FROM attachment_receipts WHERE evidence_id=%s ORDER BY part_id LIMIT 64",
                (evidence_id,),
            ).fetchall()
            row["attachments"] = attachments
            row["attachment_accounting"] = reconcile([a["status"] for a in attachments])
            self.audit(conn, ctx, "evidence.read", "evidence", str(evidence_id))
            return row

    def propose(self, ctx: TenantContext, request: ProposalRequest, key: UUID) -> dict[str, Any]:
        self.require(ctx, "email.proposal.create")
        request_hash = digest(request.model_dump(mode="json"))
        with self.transaction(ctx) as conn:
            # Unique index serializes concurrent equal keys; no check-then-insert race.
            row = conn.execute(
                "INSERT INTO proposals(tenant_id,actor_id,idempotency_key,request_hash,kind,"
                "payload,reason,source) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,actor_id,idempotency_key) DO NOTHING RETURNING *",
                (
                    ctx.tenant_id,
                    ctx.actor_id,
                    key,
                    request_hash,
                    request.payload.kind,
                    Jsonb(request.payload.model_dump(mode="json")),
                    request.reason,
                    request.source,
                ),
            ).fetchone()
            if row is None:
                existing = conn.execute(
                    "SELECT * FROM proposals WHERE tenant_id=%s AND actor_id=%s "
                    "AND idempotency_key=%s",
                    (ctx.tenant_id, ctx.actor_id, key),
                ).fetchone()
                assert existing is not None
                if existing["request_hash"] != request_hash:
                    raise Conflict("idempotency key reused")
                return existing
            evidence_ids = set(request.evidence_ids)
            if isinstance(request.payload, CorrectionPayload):
                if not conn.execute(
                    "SELECT 1 FROM messages WHERE id=%s", (request.payload.message_id,)
                ).fetchone():
                    raise NotFound()
            for evidence_id in evidence_ids:
                if not conn.execute(
                    "SELECT 1 FROM message_versions WHERE id=%s", (evidence_id,)
                ).fetchone():
                    raise NotFound()
                conn.execute(
                    "INSERT INTO proposal_evidence(tenant_id,proposal_id,evidence_id) "
                    "VALUES (%s,%s,%s)",
                    (ctx.tenant_id, row["id"], evidence_id),
                )
            self.audit(conn, ctx, "proposal.created", "proposal", str(row["id"]))
            return row

    def proposals(self, ctx: TenantContext, limit: int = 50) -> list[dict[str, Any]]:
        self.require(ctx, "email.proposal.read")
        with self.transaction(ctx) as conn:
            rows = conn.execute(
                "SELECT * FROM proposals ORDER BY created_at DESC,id LIMIT %s", (min(limit, 50),)
            ).fetchall()
            self.audit(conn, ctx, "proposal.list", "proposal")
            return rows

    def review(
        self, ctx: TenantContext, proposal_id: UUID, request: ReviewRequest
    ) -> dict[str, Any]:
        self.require(ctx, "email.review")
        with self.transaction(ctx) as conn:
            row = conn.execute("SELECT * FROM proposals WHERE id=%s FOR UPDATE", (proposal_id,))
            previous = row.fetchone()
            if not previous:
                raise NotFound()
            if previous["version"] != request.expected_version or previous["status"] != "pending":
                raise Conflict("proposal is no longer pending at the expected version")
            reviewed = conn.execute(
                "UPDATE proposals SET status=%s,version=version+1,reviewed_by=%s,reviewed_at=now() "
                "WHERE id=%s RETURNING *",
                (request.decision, ctx.actor_id, proposal_id),
            ).fetchone()
            assert reviewed is not None
            self.audit(conn, ctx, f"proposal.{request.decision}", "proposal", str(proposal_id))
            return reviewed
