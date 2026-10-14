"""Transactional PostgreSQL persistence. All runtime access uses an authenticated context."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from email.errors import MessageError
from types import MappingProxyType
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from email_brain.attachments import Attachment, receive_attachments, reconcile
from email_brain.blobs import MAX_BLOB_BYTES, BlobError, BlobRef, EncryptedBlobStore
from email_brain.domain.models import TenantContext
from email_brain.normalize import MAX_RAW_BYTES as MAX_RAW_BYTES
from email_brain.normalize import PARSER_VERSION as PARSER_VERSION
from email_brain.normalize import NormalizedMessage, normalize
from email_brain.rules.active import classify, current_rules
from email_brain.schemas import CorrectionPayload, ProposalRequest, ReviewRequest, SearchRequest


class Conflict(Exception):
    """Retry requires reconciliation or a new idempotency key."""


class NotFound(Exception):
    """Missing and unauthorized identifiers are indistinguishable."""


class AccessDenied(Exception):
    """The principal has no current owner membership."""


class InventoryError(Exception):
    """A partial or contradictory inventory cannot authorize reconciliation."""


def prepare_mime(raw: bytes | None) -> tuple[NormalizedMessage | None, list[Attachment], bool]:
    if raw is None:
        return None, [], False
    if len(raw) > MAX_RAW_BYTES:
        raise ValueError("raw evidence exceeds durable storage limit")
    try:
        attachments = receive_attachments(raw)
        normalized = normalize(raw)
        # Python decoders can produce NUL or lone surrogates even when the source
        # MIME contains neither (e.g. UTF-7 or unicode_escape). Validate projections
        # before SQL so one poison part cannot repeatedly block a healthy page.
        values = [
            normalized.subject,
            normalized.sender,
            normalized.text,
            normalized.internet_message_id or "",
            *normalized.recipients,
        ]
        for attachment in attachments:
            values.extend(
                (
                    attachment.part_id,
                    attachment.original_filename,
                    attachment.safe_filename,
                    attachment.media_type,
                    attachment.status,
                    attachment.reason,
                    attachment.text,
                )
            )
        for value in values:
            if "\x00" in value:
                raise ValueError("projection contains NUL")
            value.encode("utf-8", errors="strict")
        return normalized, attachments, False
    except (ValueError, UnicodeError, RecursionError, MessageError):
        # Never store exception text: malformed headers can put content in diagnostics.
        return None, [], True


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


HELD_SOURCE_TOO_LARGE = "source_too_large"
MAX_PROVIDER_SIZE = 2**53 - 1  # Exact in interoperable JSON integer consumers.


@dataclass(frozen=True)
class IngestItem:
    event_key: str
    provider_id: str
    version: str
    received_at: datetime
    raw: bytes | None = None  # None is an explicit provider tombstone unless held.
    thread_id: str | None = None
    mailbox_ids: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    blob_id: str | None = None  # Provider blob identity of ``raw``; enables reuse.
    # A held message exists at the provider but its bytes were not retained because
    # they exceed the configured storage budget. It is accounted, not silently skipped.
    held_reason: str | None = None
    source_size: int | None = None
    exclusion_policy: str | None = None  # Opaque policy fingerprint; no source bytes.

    def __post_init__(self) -> None:
        if not all(0 < len(v) <= 1000 for v in (self.event_key, self.provider_id, self.version)):
            raise ValueError("event identifiers must contain 1..1000 characters")
        if self.received_at.tzinfo is None:
            raise ValueError("received_at must be timezone-aware")
        if self.thread_id is not None and not 0 < len(self.thread_id) <= 512:
            raise ValueError("invalid thread identifier")
        for values in (self.mailbox_ids, self.keywords):
            if len(values) > 100 or any(not 0 < len(v) <= 512 or "\x00" in v for v in values):
                raise ValueError("invalid provider metadata")
        if self.blob_id is not None and (
            not 0 < len(self.blob_id) <= 512 or "\x00" in self.blob_id
        ):
            raise ValueError("invalid blob identifier")
        if self.held_reason is not None and (
            self.held_reason != HELD_SOURCE_TOO_LARGE or self.raw is not None
        ):
            raise ValueError("held items carry a known reason and no retained bytes")
        if self.exclusion_policy is not None and (
            not re.fullmatch(r"[0-9a-f]{64}", self.exclusion_policy)
            or self.raw is not None or self.held_reason is not None
            or self.thread_id is not None or self.mailbox_ids or self.keywords
            or self.blob_id is not None or self.source_size is not None
        ):
            raise ValueError("excluded items carry only an opaque policy identity")
        if self.source_size is not None and (
            type(self.source_size) is not int or not 0 <= self.source_size <= MAX_PROVIDER_SIZE
        ):
            raise ValueError("invalid source size")

    @property
    def held(self) -> bool:
        return self.held_reason is not None


class Store:
    def __init__(
        self,
        dsn: str,
        *,
        blobs: EncryptedBlobStore | None = None,
        tenant_dsns: Mapping[UUID, str] | None = None,
    ) -> None:
        self.dsn = dsn
        self.blobs = blobs
        self.tenant_dsns = (
            MappingProxyType(dict(tenant_dsns)) if tenant_dsns is not None else None
        )
        if self.tenant_dsns is not None and not self.tenant_dsns:
            raise ValueError("tenant database routing requires at least one tenant")

    @property
    def max_raw_bytes(self) -> int:
        return MAX_BLOB_BYTES if self.blobs is not None else MAX_RAW_BYTES

    def stage_raw(
        self,
        ctx: TenantContext,
        account_id: UUID,
        items: Sequence[IngestItem],
        *,
        synthetic_only: bool = False,
    ) -> dict[str, BlobRef | None]:
        """Authorize, then stage immutable encrypted objects outside SQL transactions."""
        self.require(ctx, "email.ingest")
        if len(items) > 100:
            raise ValueError("bounded pages required")
        if any(i.raw is not None and len(i.raw) > self.max_raw_bytes for i in items):
            raise ValueError("raw evidence exceeds configured durable storage limit")
        if sum(len(i.raw) for i in items if i.raw is not None) > MAX_BLOB_BYTES:
            raise ValueError("ingestion page exceeds byte budget")
        sources = {hashlib.sha256(i.raw).hexdigest(): i.raw for i in items if i.raw is not None}
        if not sources:
            return {}
        with self.transaction(ctx) as conn:
            account = conn.execute(
                "SELECT provider_account_id,secret_ref FROM mail_accounts "
                "WHERE id=%s AND status='active'",
                (account_id,),
            ).fetchone()
            if not account:
                raise NotFound()
            if synthetic_only and (
                account["provider_account_id"] is not None
                or not account["secret_ref"].startswith("synthetic:")
            ):
                raise ValueError("unenrolled synthetic account required")
            rows = conn.execute(
                "SELECT sha256,blob_ref,raw_mime FROM raw_objects "
                "WHERE account_id=%s AND sha256=ANY(%s)",
                (account_id, list(sources)),
            ).fetchall()
        existing = {row["sha256"]: row for row in rows}
        staged: dict[str, BlobRef | None] = {}
        for sha, raw in sources.items():
            if sha in existing:
                saved = existing[sha]
                ref = BlobRef(**saved["blob_ref"]) if saved["blob_ref"] is not None else None
                if ref:
                    if self.blobs is None:
                        raise BlobError()
                    if self.blobs.get(ctx.tenant_id, account_id, ref) != raw:
                        raise BlobError()
                elif bytes(saved["raw_mime"]) != raw:
                    raise BlobError()
                staged[sha] = ref
            else:
                staged[sha] = self.blobs.put(ctx.tenant_id, account_id, raw) if self.blobs else None
        return staged

    def load_raw(self, ctx: TenantContext, account_id: UUID, sha: str) -> bytes:
        """Internal authorized read. Human exports resolve evidence first, never raw keys."""
        self.require(ctx, "email.evidence.read")
        return self._retained_raw(ctx, account_id, sha)

    def retained_blobs(
        self, ctx: TenantContext, account_id: UUID, provider_ids: Sequence[str]
    ) -> dict[str, tuple[str, str]]:
        """Provider blob identity and raw digest already retained for current projections.

        Ingest-scoped: lets a worker reuse retained bytes for a flag-only provider update
        instead of downloading the message again. Only messages whose projection recorded
        a blob identity qualify; quarantined or legacy rows fall back to a download.
        """
        self.require(ctx, "email.ingest")
        if not 0 < len(provider_ids) <= 100 or len(set(provider_ids)) != len(provider_ids):
            raise ValueError("1..100 distinct provider IDs required")
        with self.transaction(ctx) as conn:
            rows = conn.execute(
                "SELECT m.provider_message_id,m.provider_metadata->>'blob_id' AS blob_id,"
                "m.raw_sha256 FROM messages m JOIN raw_objects r ON r.tenant_id=m.tenant_id "
                "AND r.account_id=m.account_id AND r.sha256=m.raw_sha256 "
                "WHERE m.account_id=%s AND m.provider_message_id=ANY(%s) "
                "AND NOT m.quarantined AND m.provider_metadata ? 'blob_id'",
                (account_id, list(provider_ids)),
            ).fetchall()
        return {
            row["provider_message_id"]: (row["blob_id"], row["raw_sha256"])
            for row in rows
            if isinstance(row["blob_id"], str) and row["blob_id"]
        }

    def retained_raw_for_ingest(self, ctx: TenantContext, account_id: UUID, sha: str) -> bytes:
        """Ingest-scoped retained bytes for provider replay; never a human export path."""
        self.require(ctx, "email.ingest")
        return self._retained_raw(ctx, account_id, sha)

    def _retained_raw(self, ctx: TenantContext, account_id: UUID, sha: str) -> bytes:
        with self.transaction(ctx) as conn:
            row = conn.execute(
                "SELECT r.raw_mime,r.blob_ref FROM raw_objects r JOIN mail_accounts a "
                "ON a.tenant_id=r.tenant_id AND a.id=r.account_id "
                "WHERE r.account_id=%s AND r.sha256=%s AND a.status='active'",
                (account_id, sha),
            ).fetchone()
        if row is None:
            raise NotFound()
        if row["blob_ref"] is None:
            return bytes(row["raw_mime"])
        if self.blobs is None:
            raise BlobError()
        return self.blobs.get(ctx.tenant_id, account_id, BlobRef(**row["blob_ref"]))

    def object_inventory(self, ctx: TenantContext, account_id: UUID) -> dict[str, Any]:
        """Read-only operator/library report; never authorizes garbage collection."""
        self.require(ctx, "email.evidence.read")
        if self.blobs is None:
            raise BlobError()
        with self.transaction(ctx) as conn:
            if not conn.execute(
                "SELECT 1 FROM mail_accounts WHERE id=%s", (account_id,)
            ).fetchone():
                raise NotFound()
            rows = conn.execute(
                "SELECT blob_ref FROM raw_objects WHERE account_id=%s AND blob_ref IS NOT NULL "
                "ORDER BY sha256 LIMIT 10001",
                (account_id,),
            ).fetchall()
        if len(rows) > 10000:
            raise BlobError()
        referenced = {row["blob_ref"]["object_key"] for row in rows}
        present = set(self.blobs.object_keys(ctx.tenant_id, account_id))
        return {
            "referenced": len(referenced),
            "present": len(present),
            "missing": sorted(referenced - present),
            "unreferenced": sorted(present - referenced),
            "deletion_authorized": False,
            "snapshot_consistent": False,
        }

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

    def publish_message(
        self,
        conn: psycopg.Connection[dict[str, Any]],
        ctx: TenantContext,
        account_id: UUID,
        item: IngestItem,
        normalized: NormalizedMessage,
        attachments: list[Attachment],
        *,
        source_metadata_known: bool = True,
        parser_version: str | None = None,
    ) -> UUID:
        """Publish one parser-versioned projection inside the caller's account lock."""
        parser = PARSER_VERSION if parser_version is None else parser_version
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,100}", parser):
            raise ValueError("invalid parser provenance")
        assert item.raw is not None
        raw_hash = hashlib.sha256(item.raw).hexdigest()
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
            "deleted=false,quarantined=false,updated_at=now() RETURNING id",
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
                parser,
                item.received_at,
            ),
        ).fetchone()
        assert message is not None
        metadata: dict[str, Any] = (
            {"mailbox_ids": item.mailbox_ids, "keywords": item.keywords}
            if source_metadata_known
            else {"source_metadata": "unknown"}
        )
        if source_metadata_known and item.blob_id is not None:
            metadata["blob_id"] = item.blob_id
        conn.execute(
            "UPDATE messages SET provider_metadata=%s WHERE id=%s",
            (Jsonb(metadata), message["id"]),
        )
        snapshot = {
            "subject": normalized.subject,
            "sender": normalized.sender,
            "text": normalized.text,
            "truncated": normalized.truncated,
            "received_at": item.received_at.isoformat(),
            "parser_version": parser,
            "sender_rule_eligible": normalized.sender_rule_eligible,
        }
        created = conn.execute(
            "INSERT INTO message_versions(tenant_id,account_id,message_id,raw_sha256,"
            "provider_version,snapshot) VALUES (%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (tenant_id,message_id,raw_sha256,parser_version) DO NOTHING RETURNING id",
            (
                ctx.tenant_id,
                account_id,
                message["id"],
                raw_hash,
                item.version,
                Jsonb(snapshot),
            ),
        ).fetchone()
        version = conn.execute(
            "SELECT id,snapshot FROM message_versions WHERE message_id=%s AND raw_sha256=%s "
            "AND parser_version=%s",
            (message["id"], raw_hash, parser),
        ).fetchone()
        assert version is not None and item.raw is not None
        if created:
            self.record_attachments(conn, ctx, account_id, version["id"], attachments)
        else:
            # A parser version is an immutable contract, not a mutable label. Reject
            # drift atomically instead of linking new search text to old citations.
            if any(
                version["snapshot"].get(key) != snapshot[key]
                for key in ("subject", "sender", "text", "truncated", "parser_version")
            ):
                raise Conflict("parser output changed without a version change")
            if (
                version["snapshot"].get("sender_rule_eligible", False)
                is not snapshot["sender_rule_eligible"]
            ):
                raise Conflict("sender eligibility changed without a parser version change")
            existing = conn.execute(
                "SELECT part_id,original_filename,safe_filename,media_type,sha256,byte_size,"
                "status,reason,extracted_text FROM attachment_receipts WHERE evidence_id=%s "
                "ORDER BY part_id",
                (version["id"],),
            ).fetchall()
            expected = [
                {
                    "part_id": a.part_id,
                    "original_filename": a.original_filename,
                    "safe_filename": a.safe_filename,
                    "media_type": a.media_type,
                    "sha256": a.sha256,
                    "byte_size": a.byte_size,
                    "status": a.status,
                    "reason": a.reason,
                    "extracted_text": a.text,
                }
                for a in sorted(attachments, key=lambda a: a.part_id)
            ]
            if existing != expected:
                raise Conflict("attachment output changed without a parser version change")
        return UUID(str(version["id"]))

    @contextmanager
    def connection(
        self, tenant_id: UUID | None = None
    ) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        """Least-privileged connection; routed data use requires a bound tenant login."""
        if tenant_id is not None and self.tenant_dsns is None:
            raise AccessDenied("tenant database routing is not configured")
        dsn = self.dsn
        if self.tenant_dsns is not None and tenant_id is not None:
            if tenant_id not in self.tenant_dsns:
                raise AccessDenied("tenant database route unavailable")
            dsn = self.tenant_dsns[tenant_id]
        with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
            role = conn.execute(
                "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication, "
                "EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE c.relowner=r.oid AND n.nspname='public' "
                "AND c.relkind IN ('r','p','v','m','f')) AS owns "
                "FROM pg_roles r WHERE rolname=current_user"
            ).fetchone()
            if not role or any(
                role[key]
                for key in (
                    "rolsuper",
                    "rolbypassrls",
                    "rolcreatedb",
                    "rolcreaterole",
                    "rolreplication",
                    "owns",
                )
            ):
                raise AccessDenied("unsafe runtime database role")
            if self.tenant_dsns is not None:
                if tenant_id is None:
                    unsafe_lookup = conn.execute(
                        "SELECT current_user<>session_user OR "
                        "EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n "
                        "ON n.oid=c.relnamespace WHERE n.nspname='public' "
                        "AND c.relkind IN ('r','p','v','m','f') "
                        "AND has_table_privilege(session_user,c.oid,"
                        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')) "
                        "OR EXISTS(SELECT 1 FROM pg_auth_members m JOIN pg_roles r "
                        "ON r.oid=m.member WHERE r.rolname=session_user) AS unsafe"
                    ).fetchone()
                    if not unsafe_lookup or unsafe_lookup["unsafe"]:
                        raise AccessDenied("unsafe identity lookup database role")
                else:
                    bound = conn.execute(
                        "SELECT current_user=session_user "
                        "AND pg_has_role(session_user,'masterbrain_tenant_runtime','member') "
                        "AND public.masterbrain_tenant_login_allows(%s) AS allowed",
                        (tenant_id,),
                    ).fetchone()
                    if not bound or not bound["allowed"]:
                        raise AccessDenied("tenant database login is not bound")
            resolver = conn.execute(
                "SELECT to_regprocedure('public.resolve_external_identity(text,text,text)') "
                "IS NOT NULL AS present"
            ).fetchone()
            if resolver and resolver["present"]:
                direct_identity_read = conn.execute(
                    "SELECT has_table_privilege(current_user,"
                    "'public.external_identities','SELECT') OR "
                    "has_table_privilege(current_user,"
                    "'public.external_identity_sources','SELECT') AS allowed"
                ).fetchone()
                if not direct_identity_read or direct_identity_read["allowed"]:
                    raise AccessDenied("unsafe runtime identity-table grant")
            conn.execute("SELECT set_config('statement_timeout', '5000', true)")
            conn.execute("SELECT set_config('lock_timeout', '2000', true)")
            yield conn

    @staticmethod
    def resolve_identity(
        conn: psycopg.Connection[dict[str, Any]], issuer: str, subject: str, client_id: str
    ) -> dict[str, Any] | None:
        """Exact binding lookup after caller-side token verification; no table SELECT."""
        return conn.execute(
            "SELECT * FROM public.resolve_external_identity_v2(%s,%s,%s)",
            (issuer, subject, client_id),
        ).fetchone()

    @contextmanager
    def transaction(self, ctx: TenantContext) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        with self.connection(ctx.tenant_id if self.tenant_dsns is not None else None) as conn:
            if identity := ctx.identity:
                binding = self.resolve_identity(
                    conn, identity.issuer, identity.subject, identity.client_id
                )
                expiry_check = conn.execute(
                    "SELECT clock_timestamp() < %s AS valid", (identity.expires_at,)
                ).fetchone()
                if (
                    not binding
                    or binding["id"] != identity.binding_id
                    or binding["tenant_id"] != ctx.tenant_id
                    or binding["actor_id"] != ctx.actor_id
                    or binding["revision"] != identity.revision
                    or binding["client_kind"] != identity.client_kind
                    or not set(ctx.scopes).issubset(binding["scopes"])
                    or (
                        identity.client_kind == "assistant"
                        and any(scope.startswith("email.") for scope in binding["scopes"])
                    )
                    or (
                        identity.client_kind == "assistant"
                        and bool(
                            set(binding["scopes"])
                            & {
                                "brain.search", "knowledge.search", "knowledge.read",
                                "knowledge.changes.read",
                                "brain.evidence.read", "brain.content.read",
                                "brain.changes.read",
                            }
                        )
                        and not binding["source_ids"]
                    )
                    or (
                        ctx.source_ids
                        != (
                            frozenset(binding["source_ids"])
                            if identity.client_kind == "assistant" and binding["source_ids"]
                            else None
                        )
                    )
                    or not expiry_check
                    or not expiry_check["valid"]
                ):
                    raise AccessDenied("external identity is no longer authorized")
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
        *,
        lease_token: UUID | None = None,
        inventory_generation: UUID | None = None,
        inventory_total: int | None = None,
        synthetic_only: bool = False,
    ) -> int:
        if "email.ingest" not in ctx.scopes:
            raise AccessDenied("ingest scope required")
        if len(items) > 100 or not next_cursor or len(next_cursor) > 4000:
            raise ValueError("bounded pages and nonempty cursor required")
        if inventory_total is not None and (
            inventory_generation is None
            or type(inventory_total) is not int
            or not 0 <= inventory_total <= 2**31 - 1
        ):
            raise InventoryError("invalid inventory certificate")
        if inventory_generation is not None and len({item.provider_id for item in items}) != len(
            items
        ):
            raise ValueError("one event per provider ID per page required")
        if any(i.raw is not None and len(i.raw) > self.max_raw_bytes for i in items):
            raise ValueError("raw evidence exceeds configured durable storage limit")
        if sum(len(i.raw) for i in items if i.raw is not None) > MAX_BLOB_BYTES:
            raise ValueError("ingestion page exceeds byte budget")
        staged = self.stage_raw(ctx, account_id, items, synthetic_only=synthetic_only)
        prepared = [
            (
                item,
                *(
                    prepare_mime(item.raw)
                    if not item.held and item.exclusion_policy is None
                    and (item.raw is None or len(item.raw) <= MAX_RAW_BYTES)
                    else (None, [], item.exclusion_policy is None)
                ),
            )
            for item in items
        ]
        inserted = 0
        with self.transaction(ctx) as conn:
            # Serialize this account without granting UPDATE on account credentials/config.
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:{account_id}",),
            )
            account = conn.execute(
                "SELECT id,provider_account_id,secret_ref,read_scope_sha256 FROM mail_accounts "
                "WHERE id=%s AND status='active'",
                (account_id,),
            ).fetchone()
            if not account:
                raise NotFound()
            if synthetic_only and (
                account["provider_account_id"] is not None
                or not account["secret_ref"].startswith("synthetic:")
            ):
                raise ValueError("unenrolled synthetic account required")
            # All ingestion for an enrolled worker account is fenced, including
            # direct library calls. A stale process cannot bypass the worker lease.
            worker = conn.execute(
                "SELECT lease_token,provider_account_id,read_scope_sha256,"
                "lease_until>clock_timestamp() AS live "
                "FROM sync_workers WHERE account_id=%s FOR UPDATE",
                (account_id,),
            ).fetchone()
            if worker and (
                lease_token is None
                or worker["lease_token"] != lease_token
                or not worker["live"]
                or worker["provider_account_id"] != account["provider_account_id"]
                or worker["provider_account_id"] is None
            ):
                raise Conflict("worker lease is not current")
            if lease_token is not None and worker is None:
                raise Conflict("worker lease is missing")
            if any(item.exclusion_policy is not None for item in items) and (
                worker is None or lease_token is None
                or not account["read_scope_sha256"]
                or worker["read_scope_sha256"] != account["read_scope_sha256"]
                or any(
                    item.exclusion_policy != account["read_scope_sha256"]
                    for item in items if item.exclusion_policy is not None
                )
            ):
                raise Conflict("excluded event requires matching scoped worker")
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
                for item, _normalized, _attachments, _quarantined in prepared:
                    previous = conn.execute(
                        "SELECT event_hash FROM provider_events "
                        "WHERE account_id=%s AND event_key=%s",
                        (account_id, item.event_key),
                    ).fetchone()
                    if not previous or previous["event_hash"] != self._event_hash(item):
                        raise Conflict("page replay differs from committed content")
                return 0
            if inventory_generation is not None:
                for item in items:
                    conn.execute(
                        "INSERT INTO sync_inventory(tenant_id,account_id,generation,provider_id) "
                        "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (ctx.tenant_id, account_id, inventory_generation, item.provider_id),
                    )
                if inventory_total is not None:
                    count = conn.execute(
                        "SELECT count(*) AS n FROM sync_inventory "
                        "WHERE account_id=%s AND generation=%s",
                        (account_id, inventory_generation),
                    ).fetchone()
                    if not count or count["n"] != inventory_total:
                        raise InventoryError("incomplete inventory")
                    conn.execute(
                        "INSERT INTO sync_inventory_seals(tenant_id,account_id,generation,total) "
                        "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (ctx.tenant_id, account_id, inventory_generation, inventory_total),
                    )
            for item, normalized, attachments, quarantined in prepared:
                event_hash = self._event_hash(item)
                previous = conn.execute(
                    "SELECT event_hash FROM provider_events WHERE account_id=%s AND event_key=%s",
                    (account_id, item.event_key),
                ).fetchone()
                if previous:
                    if previous["event_hash"] != event_hash:
                        raise Conflict("event key reused with different content")
                    continue
                if item.exclusion_policy is not None:
                    event_kind, current_status = "exclude_message", "excluded"
                elif quarantined:
                    event_kind, current_status = "quarantine_message", "quarantined"
                elif normalized is not None:
                    event_kind, current_status = "upsert_message", "ready"
                else:
                    event_kind, current_status = "delete_message", "deleted"
                raw_hash = hashlib.sha256(item.raw).hexdigest() if item.raw is not None else None
                conn.execute(
                    "INSERT INTO provider_events(tenant_id,account_id,event_key,kind,"
                    "provider_object_id,provider_version,payload_ref,observed_at,event_hash) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        account_id,
                        item.event_key,
                        event_kind,
                        item.provider_id,
                        item.version,
                        raw_hash,
                        item.received_at,
                        event_hash,
                    ),
                )
                conn.execute(
                    "INSERT INTO message_sync_state"
                    "(tenant_id,account_id,provider_id,event_key,status) "
                    "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (tenant_id,account_id,provider_id) "
                    "DO UPDATE SET event_key=excluded.event_key,"
                    "status=excluded.status,updated_at=now()",
                    (
                        ctx.tenant_id,
                        account_id,
                        item.provider_id,
                        item.event_key,
                        current_status,
                    ),
                )
                if item.raw is not None:
                    ref = staged[str(raw_hash)]
                    conn.execute(
                        "INSERT INTO raw_objects(tenant_id,account_id,sha256,raw_mime,blob_ref) "
                        "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (
                            ctx.tenant_id,
                            account_id,
                            raw_hash,
                            None if ref else item.raw,
                            Jsonb(asdict(ref)) if ref else None,
                        ),
                    )
                if item.exclusion_policy is not None:
                    # Current projections are hidden without claiming provider deletion.
                    # Historical immutable evidence remains behind its existing grants.
                    conn.execute(
                        "UPDATE messages SET deleted=true,provider_version=%s,updated_at=now() "
                        "WHERE account_id=%s AND provider_message_id=%s",
                        (item.version, account_id, item.provider_id),
                    )
                    self.audit(conn, ctx, "ingest.excluded", "account", str(account_id))
                elif quarantined:
                    source_metadata: dict[str, Any] = {
                        "thread_id": item.thread_id,
                        "mailbox_ids": item.mailbox_ids,
                        "keywords": item.keywords,
                    }
                    if item.held:
                        reason = str(item.held_reason)
                        source_metadata["source_size"] = item.source_size
                    elif item.raw is not None and len(item.raw) > MAX_RAW_BYTES:
                        reason = "mime_too_large"
                    else:
                        reason = "mime_rejected"
                    conn.execute(
                        "INSERT INTO quarantine_receipts"
                        "(tenant_id,account_id,event_key,provider_id,"
                        "raw_sha256,reason,parser_version,source_metadata) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            ctx.tenant_id,
                            account_id,
                            item.event_key,
                            item.provider_id,
                            raw_hash,
                            reason,
                            PARSER_VERSION,
                            Jsonb(source_metadata),
                        ),
                    )
                    conn.execute(
                        "UPDATE messages SET quarantined=true,updated_at=now() "
                        "WHERE account_id=%s AND provider_message_id=%s",
                        (account_id, item.provider_id),
                    )
                    self.audit(conn, ctx, "ingest.quarantined", "account", str(account_id))
                elif normalized is None:
                    conn.execute(
                        "UPDATE messages SET deleted=true,provider_version=%s,updated_at=now() "
                        "WHERE account_id=%s AND provider_message_id=%s",
                        (item.version, account_id, item.provider_id),
                    )
                else:
                    self.publish_message(conn, ctx, account_id, item, normalized, attachments)
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
        payload: dict[str, Any] = {
            "id": item.provider_id,
            "version": item.version,
            "raw": hashlib.sha256(item.raw).hexdigest() if item.raw is not None else None,
            "thread": item.thread_id,
        }
        # Preserve hashes for pre-worker events with no provider membership snapshot.
        if item.mailbox_ids or item.keywords:
            payload.update(mailbox_ids=item.mailbox_ids, keywords=item.keywords)
        if item.held:
            payload.update(held=item.held_reason, source_size=item.source_size)
        if item.exclusion_policy is not None:
            payload["exclusion_policy"] = item.exclusion_policy
        return digest(payload)

    def quarantines(
        self, ctx: TenantContext, account_id: UUID, *, after: UUID | None = None, limit: int = 50
    ) -> dict[str, Any]:
        self.require(ctx, "email.evidence.read")
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("quarantine page limit must be 1..50")
        with self.transaction(ctx) as conn:
            if not conn.execute(
                "SELECT 1 FROM mail_accounts WHERE id=%s", (account_id,)
            ).fetchone():
                raise NotFound()
            rows = conn.execute(
                "SELECT q.id,q.provider_id,q.raw_sha256,q.reason,q.parser_version,q.recorded_at "
                "FROM quarantine_receipts q JOIN message_sync_state h "
                "ON h.tenant_id=q.tenant_id AND h.account_id=q.account_id "
                "AND h.provider_id=q.provider_id AND h.event_key=q.event_key "
                "WHERE q.account_id=%s AND h.status='quarantined' "
                "AND (%s::uuid IS NULL OR q.id>%s) ORDER BY q.id LIMIT %s",
                (account_id, after, after, limit + 1),
            ).fetchall()
            return {
                "results": rows[:limit],
                "next_after": rows[limit - 1]["id"] if len(rows) > limit else None,
                "limit": limit,
                "raw_access": False,
                "reprocessing": True,
                "retry_parser_version": PARSER_VERSION,
            }

    def sync_status(self, ctx: TenantContext, account_id: UUID) -> dict[str, Any]:
        self.require(ctx, "email.search")
        with self.transaction(ctx) as conn:
            if not conn.execute(
                "SELECT 1 FROM mail_accounts WHERE id=%s", (account_id,)
            ).fetchone():
                raise NotFound()
            worker = conn.execute(
                "SELECT last_outcome,paused,failures,next_attempt_at,updated_at "
                "FROM sync_workers WHERE account_id=%s",
                (account_id,),
            ).fetchone()
            counts = {"ready": 0, "quarantined": 0, "deleted": 0, "excluded": 0}
            for row in conn.execute(
                "SELECT status,count(*) AS n FROM message_sync_state "
                "WHERE account_id=%s GROUP BY status",
                (account_id,),
            ).fetchall():
                counts[row["status"]] = row["n"]
            return {
                "account_id": account_id,
                "worker": worker,
                "message_counts": counts,
                "review_required": bool(counts["quarantined"]),
                "mailbox_writes": False,
            }

    def search(self, ctx: TenantContext, request: SearchRequest) -> list[dict[str, Any]]:
        self.require(ctx, "email.search")
        with self.transaction(ctx) as conn:
            rows = conn.execute(
                "SELECT m.id,m.account_id,m.subject,m.sender,m.received_at,v.id AS evidence_id,"
                "(v.snapshot->'sender_rule_eligible' = 'true'::jsonb) AS sender_rule_eligible,"
                "left(m.clean_text,500) AS excerpt,"
                "ts_rank_cd(m.search_document,websearch_to_tsquery('simple',%s)) AS score "
                "FROM messages m JOIN message_versions v ON v.tenant_id=m.tenant_id "
                "AND v.message_id=m.id AND v.raw_sha256=m.raw_sha256 "
                "AND v.parser_version=m.parser_version "
                "WHERE NOT m.deleted AND NOT m.quarantined "
                "AND (%s::uuid IS NULL OR m.account_id=%s) "
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
                    "(v.snapshot->'sender_rule_eligible' = 'true'::jsonb) AS sender_rule_eligible,"
                    "left(a.extracted_text,500) AS excerpt,"
                    "ts_rank_cd(a.search_document,websearch_to_tsquery('simple',%s)) AS score "
                    "FROM attachment_receipts a JOIN message_versions v ON "
                    "v.tenant_id=a.tenant_id AND v.id=a.evidence_id "
                    "JOIN messages m ON m.tenant_id=v.tenant_id AND m.id=v.message_id "
                    "AND m.raw_sha256=v.raw_sha256 "
                    "AND v.parser_version=m.parser_version "
                    "WHERE a.status='extracted' AND NOT m.deleted AND NOT m.quarantined "
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
            if request.include_documents:
                documents = conn.execute(
                    "SELECT m.id,m.account_id,m.subject,m.sender,m.received_at,a.evidence_id,"
                    "a.id AS attachment_id,a.safe_filename,d.id AS document_id,d.revision,"
                    "d.processor_version,d.policy_version,d.status,d.reason,d.scanner_status,"
                    "(v.snapshot->'sender_rule_eligible' = 'true'::jsonb) AS sender_rule_eligible,"
                    "left(d.extracted_text,500) AS excerpt,"
                    "ts_rank_cd(d.search_document,websearch_to_tsquery('simple',%s)) AS score "
                    "FROM document_extractions d JOIN attachment_receipts a "
                    "ON a.tenant_id=d.tenant_id AND a.account_id=d.account_id "
                    "AND a.id=d.receipt_id "
                    "JOIN message_versions v ON v.tenant_id=a.tenant_id AND v.id=a.evidence_id "
                    "JOIN messages m ON m.tenant_id=v.tenant_id AND m.id=v.message_id "
                    "AND m.raw_sha256=v.raw_sha256 AND m.parser_version=v.parser_version "
                    "WHERE NOT m.deleted AND NOT m.quarantined "
                    "AND (%s::uuid IS NULL OR m.account_id=%s) "
                    "AND NOT EXISTS (SELECT 1 FROM document_extractions newer "
                    "WHERE newer.tenant_id=d.tenant_id AND newer.receipt_id=d.receipt_id "
                    "AND newer.revision>d.revision) "
                    "AND d.status IN ('extracted','partial') "
                    "AND d.search_document @@ websearch_to_tsquery('simple',%s) "
                    "ORDER BY score DESC,m.received_at DESC,d.id LIMIT %s",
                    (
                        request.query,
                        request.account_id,
                        request.account_id,
                        request.query,
                        request.limit,
                    ),
                ).fetchall()
                for row in documents:
                    row["result_type"] = "document"
                    row["untrusted_content"] = True
                rows.extend(documents)
            if request.include_attachments or request.include_documents:
                rows.sort(
                    key=lambda row: (
                        -row["score"],
                        -row["received_at"].timestamp(),
                        str(row.get("document_id", row.get("attachment_id", row["id"]))),
                    )
                )
                rows = rows[: request.limit]
            self.audit(conn, ctx, "search.read", "message")
            active = current_rules(conn)
            for row in rows:
                sender = row["sender"] if row.pop("sender_rule_eligible", False) is True else ""
                row["classification"] = classify(active["rules"], active["revision"], sender)
                row["citation"] = f"emailbrain://evidence/{row['evidence_id']}"
                if row.get("document_id"):
                    row["citation"] = f"emailbrain://document/{row['document_id']}"
                elif row.get("attachment_id"):
                    row["citation"] += f"#attachment={row['attachment_id']}"
            return rows

    def document_evidence(self, ctx: TenantContext, document_id: UUID) -> dict[str, Any]:
        self.require(ctx, "email.evidence.read")
        with self.transaction(ctx) as conn:
            row = conn.execute(
                "SELECT d.id,d.account_id,d.receipt_id,d.processor_version,d.policy_version,"
                "d.revision,d.created_at,d.status,d.reason,d.scanner_status,d.result,"
                "a.evidence_id,a.safe_filename FROM document_extractions d "
                "JOIN attachment_receipts a ON a.tenant_id=d.tenant_id "
                "AND a.account_id=d.account_id AND a.id=d.receipt_id WHERE d.id=%s",
                (document_id,),
            ).fetchone()
            if row is None:
                raise NotFound()
            result = row.pop("result")
            pages = []
            for page in result["pages"]:
                excerpt = page["text"][:2000]
                pages.append(
                    {
                        "number": page["number"],
                        "excerpt": excerpt,
                        "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
                        "offsets": [0, len(excerpt)],
                        "truncated": len(page["text"]) > len(excerpt),
                    }
                )
            row.update(
                {
                    "pages": pages,
                    "page_count": result["page_count"],
                    "source": result["source"],
                    "untrusted_content": True,
                    "citation": f"emailbrain://document/{document_id}",
                }
            )
            self.audit(conn, ctx, "document.evidence_read", "document_extraction", str(document_id))
            return row

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
            snapshot.pop("sender_rule_eligible", None)
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
