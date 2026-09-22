"""Tenant-isolated persistence for shared DataCore source observations."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any, Literal, cast
from uuid import UUID

from psycopg.types.json import Jsonb

from email_brain.domain.models import TenantContext
from email_brain.store import Conflict, NotFound, Store
from masterbrain.datacore.archive_contract import (
    ArchiveResult,
    ArchiveUnavailable,
)
from masterbrain.datacore.archive_contract import decode_result as decode_archive_result
from masterbrain.datacore.archive_contract import encode_result as encode_archive_result
from masterbrain.datacore.contracts import (
    Digest,
    SourceItemVersion,
    SourceKind,
    SourceRef,
    stable_id,
)
from masterbrain.datacore.fileos import SNAPSHOT_VERSION

MAX_MANIFEST_ITEMS = 10_000
MAX_NORMALIZED_BYTES = 1_048_576
CHUNK_CHARACTERS = 1_000
NORMALIZER_VERSION = "plain-text-v1"
EMAIL_NORMALIZER_VERSION = "email-message-v1"
EMAIL_ATTACHMENT_NORMALIZER_VERSION = "email-attachment-text-v1"
EMAIL_DOCUMENT_NORMALIZER_PREFIX = "email-pdf-v1"
FILEOS_TEXT_EXTRACTOR_VERSION = "fileos-text-v1"
INDEX_CHUNKER_VERSION = "deterministic-chunks-v1"
MAX_GENERATION_TEXT_BYTES = 64 * 1_048_576
MAX_GENERATION_CHUNKS = 100_000
_IDENTITY = re.compile(r"^[a-z][a-z0-9_-]{0,127}$")
_ARCHIVE_PROCESSOR = re.compile(r"^sandbox-fileos-archive-v1-[a-f0-9]{64}$")
_ARCHIVE_TEXT_SUFFIXES = frozenset({".txt", ".md", ".html", ".htm", ".csv"})


@dataclass(frozen=True, slots=True)
class ImportResult:
    source_id: str
    observed_items: int
    new_versions: int
    unchanged_versions: int


@dataclass(frozen=True, slots=True)
class PublishedDocument:
    document_id: str
    evidence_id: str
    chunks: int
    changed: bool


@dataclass(frozen=True, slots=True)
class EmailBridgeResult:
    source_id: str
    item_id: str
    version_id: str
    evidence_id: str
    document_id: str
    chunks: int
    changed: bool


@dataclass(frozen=True, slots=True)
class EmailAttachmentBridgeResult:
    source_id: str
    item_id: str
    version_id: str
    evidence_id: str
    part_id: str
    document_id: str | None
    chunks: int
    outcome: str
    changed: bool


@dataclass(frozen=True, slots=True)
class EmailDocumentBridgeResult:
    source_id: str
    item_id: str
    version_id: str
    evidence_id: str
    document_id: str
    chunks: int
    extraction_status: str
    changed: bool


@dataclass(frozen=True, slots=True)
class SearchHit:
    chunk_id: str
    document_id: str
    evidence_id: str
    source_id: str
    locator: str
    excerpt: str
    rank: float


@dataclass(frozen=True, slots=True)
class EmailFamilySearch:
    messages: tuple[SearchHit, ...]
    attachments: tuple[SearchHit, ...]
    documents: tuple[SearchHit, ...]


@dataclass(frozen=True, slots=True)
class FileOSRunReceipt:
    run_id: UUID
    source_id: str
    observed_at: datetime
    completed_at: datetime
    item_count: int
    outcomes: dict[str, int]
    published_documents: int
    recorded: bool


@dataclass(frozen=True, slots=True)
class IndexGeneration:
    generation_id: str
    source_id: str
    run_id: UUID
    item_count: int
    document_count: int
    chunk_count: int
    plan_sha256: str
    ready_at: datetime
    recorded: bool


@dataclass(frozen=True, slots=True)
class IndexActivation:
    source_id: str
    generation_id: str
    previous_generation_id: str | None
    activated_at: datetime
    recorded: bool


@dataclass(frozen=True, slots=True)
class ArchiveInventoryRecord:
    inventory_id: str
    source_id: str
    item_id: str
    source_version_id: str
    processor_version: str
    member_count: int
    skipped_count: int
    changed: bool


@dataclass(frozen=True, slots=True)
class ArchiveMemberTargetRecord:
    inventory_id: str
    inventory_processor_version: str
    source_id: str
    item_id: str
    source_version_id: str
    source_locator: str
    source_sha256: str
    source_size_bytes: int
    source_media_type: str
    member_locator: str
    member_sha256: str
    member_size_bytes: int
    member_media_type: str
    member_depth: int
    member_parent_locator: str | None


@dataclass(frozen=True, slots=True)
class ArchiveMemberTextRecord:
    inventory_id: str
    member_locator: str
    source_id: str
    item_id: str
    version_id: str
    evidence_id: str
    document_id: str
    chunks: int
    changed: bool


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def fileos_manifest_sha256(manifest: Mapping[str, Any]) -> str:
    """Canonical digest shared by intake and whole-run receipts."""
    _manifest_items(manifest)
    return _canonical_digest(manifest)


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 100:
        raise ValueError("invalid observed timestamp")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _manifest_items(
    manifest: Mapping[str, Any],
) -> tuple[SourceRef, datetime, list[SourceItemVersion]]:
    if manifest.get("manifest_version") != SNAPSHOT_VERSION:
        raise ValueError("unsupported snapshot manifest")
    raw_source = manifest.get("source")
    if not isinstance(raw_source, Mapping):
        raise ValueError("missing source")
    source_id = raw_source.get("source_id")
    kind = raw_source.get("kind")
    if not isinstance(source_id, str) or kind != SourceKind.FILEOS.value:
        raise ValueError("invalid FileOS source")
    source = SourceRef(source_id, SourceKind.FILEOS, source_id)
    observed_at = _parse_time(manifest.get("observed_at"))
    raw_items = manifest.get("items")
    if not isinstance(raw_items, list) or len(raw_items) > MAX_MANIFEST_ITEMS:
        raise ValueError("snapshot item bound exceeded")
    items: list[SourceItemVersion] = []
    locators: set[str] = set()
    identities: set[str] = set()
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            raise ValueError("invalid snapshot item")
        digest = raw.get("digest")
        metadata = raw.get("metadata", {})
        if not isinstance(digest, Mapping) or not isinstance(metadata, Mapping):
            raise ValueError("invalid snapshot item fields")
        item = SourceItemVersion(
            cast(str, raw.get("item_id")),
            cast(str, raw.get("version_id")),
            source,
            cast(str, raw.get("locator")),
            _parse_time(raw.get("observed_at")),
            Digest(cast(str, digest.get("algorithm")), cast(str, digest.get("value"))),
            cast(int, raw.get("size_bytes")),
            cast(str, raw.get("media_type")),
            cast(Mapping[str, Any], metadata),
        )
        expected_item = stable_id("item", source_id, item.locator)
        expected_version = stable_id(
            "version", expected_item, item.content.value, str(item.size_bytes)
        )
        if item.item_id != expected_item or item.version_id != expected_version:
            raise ValueError("snapshot identity does not match content")
        if item.observed_at != observed_at:
            raise ValueError("mixed snapshot observation times")
        if item.locator in locators or item.item_id in identities:
            raise ValueError("duplicate snapshot item")
        locators.add(item.locator)
        identities.add(item.item_id)
        items.append(item)
    counts = manifest.get("counts")
    if not isinstance(counts, Mapping) or counts.get("items") != len(items):
        raise ValueError("snapshot count does not match items")
    return source, observed_at, items


def validate_fileos_manifest(manifest: Mapping[str, Any]) -> tuple[str, int]:
    """Validate a complete snapshot without persisting it or exposing its locators."""
    source, _, items = _manifest_items(manifest)
    return source.source_id, len(items)


def deterministic_chunks(
    text: str, limit: int = CHUNK_CHARACTERS
) -> Iterator[tuple[int, int, str]]:
    """Yield exact, stable character ranges with a soft whitespace boundary."""
    if limit < 32 or limit > 2_000:
        raise ValueError("invalid chunk limit")
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + limit // 2, end)
            if boundary > start:
                end = boundary + 1
        yield start, end, text[start:end]
        start = end


class DataCoreStore:
    """Shared DataCore repository layered on the existing secure SQL connection."""

    def __init__(self, store: Store) -> None:
        self.store = store

    def email_bridge_plan(
        self,
        ctx: TenantContext,
        account_id: UUID,
        *,
        after: UUID | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Preview bounded current Email versions for explicit bridge operation."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        if not isinstance(account_id, UUID) or (after is not None and not isinstance(after, UUID)):
            raise ValueError("invalid Email bridge plan identity")
        if not 1 <= limit <= 100:
            raise ValueError("invalid Email bridge plan limit")
        with self.store.transaction(ctx) as conn:
            if not conn.execute(
                "SELECT 1 FROM mail_accounts WHERE id=%s", (account_id,)
            ).fetchone():
                raise NotFound()
            anchor = None
            if after is not None:
                anchor = conn.execute(
                    "SELECT recorded_at,id FROM message_versions WHERE account_id=%s AND id=%s",
                    (account_id, after),
                ).fetchone()
                if not anchor:
                    raise NotFound()
            rows = conn.execute(
                "SELECT v.id AS legacy_version_id,v.recorded_at,"
                "(b.legacy_version_id IS NOT NULL) AS already_bridged "
                "FROM message_versions v JOIN messages m ON m.tenant_id=v.tenant_id "
                "AND m.account_id=v.account_id AND m.id=v.message_id "
                "AND m.raw_sha256=v.raw_sha256 AND m.parser_version=v.parser_version "
                "LEFT JOIN brain_email_bridge_receipts b ON b.tenant_id=v.tenant_id "
                "AND b.legacy_version_id=v.id WHERE v.account_id=%s "
                "AND NOT m.deleted AND NOT m.quarantined "
                "AND (%s::timestamptz IS NULL OR (v.recorded_at,v.id)>(%s,%s)) "
                "ORDER BY v.recorded_at,v.id LIMIT %s",
                (
                    account_id,
                    anchor["recorded_at"] if anchor else None,
                    anchor["recorded_at"] if anchor else None,
                    after,
                    limit + 1,
                ),
            ).fetchall()
            self.store.audit(conn, ctx, "brain.email_bridge_plan", "mail_account", str(account_id))
        page = rows[:limit]
        return {
            "account_id": str(account_id),
            "results": [
                {
                    "legacy_version_id": str(row["legacy_version_id"]),
                    "recorded_at": row["recorded_at"].isoformat(),
                    "already_bridged": row["already_bridged"],
                }
                for row in page
            ],
            "next_cursor": (
                str(page[-1]["legacy_version_id"]) if len(rows) > limit and page else None
            ),
            "limit": limit,
            "source_effects": False,
            "data_effects": False,
        }

    def email_part_bridge_plan(
        self,
        ctx: TenantContext,
        account_id: UUID,
        kind: Literal["attachment", "document"],
        *,
        after: UUID | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Preview bounded current Email attachment or approved-document bridges."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        if (
            not isinstance(account_id, UUID)
            or kind not in {"attachment", "document"}
            or (after is not None and not isinstance(after, UUID))
        ):
            raise ValueError("invalid Email part bridge plan identity")
        if not 1 <= limit <= 100:
            raise ValueError("invalid Email part bridge plan limit")
        with self.store.transaction(ctx) as conn:
            if not conn.execute(
                "SELECT 1 FROM mail_accounts WHERE id=%s", (account_id,)
            ).fetchone():
                raise NotFound()
            anchor = None
            if after is not None:
                table = "attachment_receipts" if kind == "attachment" else "document_extractions"
                anchor = conn.execute(
                    f"SELECT {'received_at' if kind == 'attachment' else 'created_at'} "
                    f"AS created_at,id FROM {table} WHERE account_id=%s AND id=%s",
                    (account_id, after),
                ).fetchone()
                if not anchor:
                    raise NotFound()
            if kind == "attachment":
                rows = conn.execute(
                    "SELECT a.id AS legacy_id,a.evidence_id AS legacy_parent_version_id,"
                    "a.received_at AS created_at,a.status AS state,"
                    "(ab.legacy_attachment_id IS NOT NULL) AS already_bridged "
                    "FROM attachment_receipts a JOIN message_versions mv ON "
                    "mv.tenant_id=a.tenant_id AND mv.account_id=a.account_id "
                    "AND mv.id=a.evidence_id JOIN messages m ON m.tenant_id=mv.tenant_id "
                    "AND m.account_id=mv.account_id AND m.id=mv.message_id "
                    "AND m.raw_sha256=mv.raw_sha256 AND m.parser_version=mv.parser_version "
                    "JOIN brain_email_bridge_receipts eb ON eb.tenant_id=mv.tenant_id "
                    "AND eb.account_id=mv.account_id AND eb.legacy_version_id=mv.id "
                    "JOIN brain_source_items pi ON pi.tenant_id=eb.tenant_id "
                    "AND pi.id=eb.item_id AND pi.current_version_id=eb.version_id "
                    "LEFT JOIN brain_email_attachment_bridge_receipts ab ON "
                    "ab.tenant_id=a.tenant_id AND ab.account_id=a.account_id "
                    "AND ab.legacy_attachment_id=a.id WHERE a.account_id=%s "
                    "AND NOT m.deleted AND NOT m.quarantined "
                    "AND (%s::timestamptz IS NULL OR (a.received_at,a.id)>(%s,%s)) "
                    "ORDER BY a.received_at,a.id LIMIT %s",
                    (
                        account_id,
                        anchor["created_at"] if anchor else None,
                        anchor["created_at"] if anchor else None,
                        after,
                        limit + 1,
                    ),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT d.id AS legacy_id,a.evidence_id AS legacy_parent_version_id,"
                    "d.receipt_id AS legacy_attachment_id,d.created_at,d.status AS state,"
                    "(db.legacy_extraction_id IS NOT NULL) AS already_bridged "
                    "FROM document_extractions d JOIN attachment_receipts a ON "
                    "a.tenant_id=d.tenant_id AND a.account_id=d.account_id "
                    "AND a.id=d.receipt_id JOIN message_versions mv ON "
                    "mv.tenant_id=a.tenant_id AND mv.account_id=a.account_id "
                    "AND mv.id=a.evidence_id JOIN messages m ON m.tenant_id=mv.tenant_id "
                    "AND m.account_id=mv.account_id AND m.id=mv.message_id "
                    "AND m.raw_sha256=mv.raw_sha256 AND m.parser_version=mv.parser_version "
                    "JOIN brain_email_bridge_receipts eb ON eb.tenant_id=mv.tenant_id "
                    "AND eb.account_id=mv.account_id AND eb.legacy_version_id=mv.id "
                    "JOIN brain_source_items pi ON pi.tenant_id=eb.tenant_id "
                    "AND pi.id=eb.item_id AND pi.current_version_id=eb.version_id "
                    "JOIN brain_email_attachment_bridge_receipts ab ON "
                    "ab.tenant_id=d.tenant_id AND ab.account_id=d.account_id "
                    "AND ab.legacy_attachment_id=d.receipt_id "
                    "JOIN brain_source_items ai ON ai.tenant_id=ab.tenant_id "
                    "AND ai.id=ab.item_id AND ai.current_version_id=ab.version_id "
                    "LEFT JOIN brain_email_document_bridge_receipts db ON "
                    "db.tenant_id=d.tenant_id AND db.legacy_extraction_id=d.id "
                    "WHERE d.account_id=%s AND NOT m.deleted AND NOT m.quarantined "
                    "AND d.status IN ('extracted','partial') AND EXISTS (SELECT 1 "
                    "FROM document_jobs j WHERE j.tenant_id=d.tenant_id "
                    "AND j.account_id=d.account_id AND j.receipt_id=d.receipt_id "
                    "AND j.extraction_id=d.id AND j.processor_version=d.processor_version "
                    "AND j.policy_version=d.policy_version AND j.status='completed' "
                    "AND j.outcome='result_saved') AND (%s::timestamptz IS NULL "
                    "OR (d.created_at,d.id)>(%s,%s)) ORDER BY d.created_at,d.id LIMIT %s",
                    (
                        account_id,
                        anchor["created_at"] if anchor else None,
                        anchor["created_at"] if anchor else None,
                        after,
                        limit + 1,
                    ),
                ).fetchall()
            self.store.audit(
                conn, ctx, "brain.email_part_bridge_plan", "mail_account", str(account_id)
            )
        page = rows[:limit]
        results = []
        for row in page:
            result = {
                f"legacy_{kind}_id": str(row["legacy_id"]),
                "legacy_parent_version_id": str(row["legacy_parent_version_id"]),
                "created_at": row["created_at"].isoformat(),
                "state": row["state"],
                "already_bridged": row["already_bridged"],
            }
            if kind == "document":
                result["legacy_attachment_id"] = str(row["legacy_attachment_id"])
            results.append(result)
        return {
            "account_id": str(account_id),
            "kind": kind,
            "results": results,
            "next_cursor": str(page[-1]["legacy_id"]) if len(rows) > limit and page else None,
            "limit": limit,
            "source_effects": False,
            "data_effects": False,
        }

    @staticmethod
    def _email_bridge_result(row: Mapping[str, Any], *, changed: bool) -> EmailBridgeResult:
        return EmailBridgeResult(
            source_id=row["source_id"],
            item_id=row["item_id"],
            version_id=row["version_id"],
            evidence_id=row["evidence_id"],
            document_id=row["document_id"],
            chunks=row["chunk_count"],
            changed=changed,
        )

    def bridge_current_email_version(
        self,
        ctx: TenantContext,
        legacy_version_id: UUID,
        idempotency_key: UUID,
        *,
        code_revision: str,
        expected_account_id: UUID | None = None,
    ) -> EmailBridgeResult:
        """Map one current immutable Email version into shared DataCore primitives."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        if not code_revision or len(code_revision) > 200 or "\x00" in code_revision:
            raise ValueError("invalid bridge code revision")
        request_hash = _canonical_digest(
            {
                "legacy_version_id": str(legacy_version_id),
                "normalizer": EMAIL_NORMALIZER_VERSION,
                "code_revision": code_revision,
            }
        )
        receipt_columns = (
            "source_id,item_id,version_id,evidence_id,document_id,chunk_count,request_hash"
        )
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:email-bridge:{legacy_version_id}",),
            )
            legacy_identity = None
            if expected_account_id is not None:
                legacy_identity = conn.execute(
                    "SELECT account_id FROM message_versions WHERE id=%s",
                    (legacy_version_id,),
                ).fetchone()
                if not legacy_identity:
                    raise NotFound()
                if legacy_identity["account_id"] != expected_account_id:
                    raise Conflict("Email evidence is outside the sealed batch account")
            receipt = conn.execute(
                f"SELECT {receipt_columns} FROM brain_email_bridge_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise Conflict("idempotency key reused for a different Email bridge")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.email_bridge_replayed",
                    "message_version",
                    str(legacy_version_id),
                )
                return self._email_bridge_result(receipt, changed=False)

            prior = conn.execute(
                f"SELECT {receipt_columns} FROM brain_email_bridge_receipts "
                "WHERE legacy_version_id=%s",
                (legacy_version_id,),
            ).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise Conflict("Email evidence was bridged with different provenance")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.email_bridge_replayed",
                    "message_version",
                    str(legacy_version_id),
                )
                return self._email_bridge_result(prior, changed=False)

            if legacy_identity is None:
                legacy_identity = conn.execute(
                    "SELECT account_id FROM message_versions WHERE id=%s",
                    (legacy_version_id,),
                ).fetchone()
                if not legacy_identity:
                    raise NotFound()
            # Serialize against Email ingestion's account lock so a version cannot
            # become historical between the visibility check and bridge commit.
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:{legacy_identity['account_id']}",),
            )
            row = conn.execute(
                "SELECT v.id AS legacy_version_id,v.account_id,v.message_id,v.raw_sha256,"
                "v.provider_version,v.snapshot,v.parser_version,v.recorded_at,"
                "m.raw_sha256 AS current_raw_sha256,m.parser_version AS current_parser_version,"
                "m.subject,m.sender,m.clean_text,m.received_at,m.deleted,m.quarantined,"
                "a.provider,octet_length(r.raw_mime) AS raw_size "
                "FROM message_versions v JOIN messages m ON m.tenant_id=v.tenant_id "
                "AND m.account_id=v.account_id AND m.id=v.message_id "
                "JOIN mail_accounts a ON a.tenant_id=v.tenant_id AND a.id=v.account_id "
                "JOIN raw_objects r ON r.tenant_id=v.tenant_id AND r.account_id=v.account_id "
                "AND r.sha256=v.raw_sha256 WHERE v.id=%s",
                (legacy_version_id,),
            ).fetchone()
            if not row:
                raise NotFound()
            if row["deleted"] or row["quarantined"]:
                raise Conflict("Email evidence is not currently visible")
            if (
                row["raw_sha256"] != row["current_raw_sha256"]
                or row["parser_version"] != row["current_parser_version"]
            ):
                raise Conflict("only the current Email evidence version can be bridged")
            snapshot = row["snapshot"]
            if not isinstance(snapshot, dict):
                raise Conflict("Email evidence snapshot is invalid")
            subject, sender, body = (
                snapshot.get("subject"),
                snapshot.get("sender"),
                snapshot.get("text"),
            )
            if (
                not all(isinstance(value, str) for value in (subject, sender, body))
                or snapshot.get("parser_version") != row["parser_version"]
                or (subject, sender, body) != (row["subject"], row["sender"], row["clean_text"])
                or any(
                    isinstance(value, str) and "\x00" in value for value in (subject, sender, body)
                )
            ):
                raise Conflict("Email projection no longer matches immutable evidence")
            subject = cast(str, subject)
            sender = cast(str, sender)
            body = cast(str, body)
            normalized = f"Subject: {subject}\nFrom: {sender}\n\n{body}"
            if len(normalized.encode()) > MAX_NORMALIZED_BYTES:
                raise ValueError("normalized Email evidence exceeds its safe bound")

            account_id = UUID(str(row["account_id"]))
            message_id = UUID(str(row["message_id"]))
            source_id = stable_id("email", str(account_id))
            item_id = stable_id("emailitem", str(message_id))
            version_id = stable_id(
                "emailversion",
                str(legacy_version_id),
                row["raw_sha256"],
                row["parser_version"],
            )
            evidence_id = stable_id("evidence", version_id)
            locator = f"message/{message_id}"
            observed_at = row["received_at"]
            metadata = {
                "legacy_version_id": str(legacy_version_id),
                "parser_version": row["parser_version"],
                "provider": row["provider"],
                "truncated": bool(snapshot.get("truncated", False)),
            }
            conn.execute(
                "INSERT INTO brain_sources(tenant_id,id,kind,display_name) "
                "VALUES (%s,%s,'email',%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (ctx.tenant_id, source_id, f"Email source {source_id[-8:]}"),
            )
            source = conn.execute(
                "SELECT kind FROM brain_sources WHERE id=%s FOR UPDATE", (source_id,)
            ).fetchone()
            if not source or source["kind"] != "email":
                raise Conflict("Email source identity has a different kind")
            conn.execute(
                "INSERT INTO brain_source_items(tenant_id,source_id,id,locator,current_version_id,"
                "first_seen_at,last_seen_at) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    source_id,
                    item_id,
                    locator,
                    version_id,
                    observed_at,
                    observed_at,
                ),
            )
            item = conn.execute(
                "SELECT source_id,locator FROM brain_source_items WHERE id=%s FOR UPDATE",
                (item_id,),
            ).fetchone()
            if not item or (item["source_id"], item["locator"]) != (source_id, locator):
                raise Conflict("Email source item identity changed")
            conn.execute(
                "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
                "sha256,size_bytes,media_type,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,"
                "'message/rfc822',%s) ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    source_id,
                    item_id,
                    version_id,
                    observed_at,
                    row["raw_sha256"],
                    row["raw_size"],
                    Jsonb(metadata),
                ),
            )
            version = conn.execute(
                "SELECT source_id,item_id,sha256,size_bytes,media_type,metadata "
                "FROM brain_source_versions WHERE id=%s",
                (version_id,),
            ).fetchone()
            expected_version = {
                "source_id": source_id,
                "item_id": item_id,
                "sha256": row["raw_sha256"],
                "size_bytes": row["raw_size"],
                "media_type": "message/rfc822",
                "metadata": metadata,
            }
            if version != expected_version:
                raise Conflict("Email source version identity changed")
            conn.execute(
                "UPDATE brain_source_items SET first_seen_at=least(first_seen_at,%s),"
                "last_seen_at=greatest(last_seen_at,%s),current_version_id=%s WHERE id=%s",
                (observed_at, observed_at, version_id, item_id),
            )
            conn.execute(
                "INSERT INTO brain_evidence(tenant_id,id,source_version_id,sha256,"
                "storage,retained) "
                "VALUES (%s,%s,%s,%s,'inline',true) ON CONFLICT DO NOTHING",
                (ctx.tenant_id, evidence_id, version_id, row["raw_sha256"]),
            )

            body_sha = hashlib.sha256(normalized.encode()).hexdigest()
            document_id = stable_id("document", version_id, EMAIL_NORMALIZER_VERSION, body_sha)
            conn.execute(
                "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
                "body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    document_id,
                    evidence_id,
                    EMAIL_NORMALIZER_VERSION,
                    body_sha,
                    normalized,
                ),
            )
            chunks = list(deterministic_chunks(normalized))
            for ordinal, (start, end, chunk) in enumerate(chunks):
                chunk_sha = hashlib.sha256(chunk.encode()).hexdigest()
                chunk_id = stable_id("chunk", document_id, str(ordinal), chunk_sha)
                conn.execute(
                    "INSERT INTO brain_chunks(tenant_id,id,document_id,ordinal,start_offset,"
                    "end_offset,text,sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        chunk_id,
                        document_id,
                        ordinal,
                        start,
                        end,
                        chunk,
                        chunk_sha,
                    ),
                )
            config_sha = _canonical_digest(
                {"chunk_characters": CHUNK_CHARACTERS, "fields": ["subject", "sender", "text"]}
            )
            provenance_id = stable_id("provenance", document_id, code_revision, config_sha)
            conn.execute(
                "INSERT INTO brain_provenance(tenant_id,id,output_id,transform,transform_version,"
                "code_revision,configuration_sha256,created_at) VALUES (%s,%s,%s,"
                "'bridge_email_message',%s,%s,%s,clock_timestamp())",
                (
                    ctx.tenant_id,
                    provenance_id,
                    document_id,
                    EMAIL_NORMALIZER_VERSION,
                    code_revision,
                    config_sha,
                ),
            )
            conn.execute(
                "INSERT INTO brain_provenance_inputs(tenant_id,provenance_id,input_id,ordinal) "
                "VALUES (%s,%s,%s,0)",
                (ctx.tenant_id, provenance_id, evidence_id),
            )
            for kind in ("source_version_added", "document_published"):
                changed_id = version_id if kind == "source_version_added" else document_id
                change_id = stable_id("change", kind, changed_id)
                conn.execute(
                    "INSERT INTO brain_change_events(tenant_id,id,source_id,item_id,"
                    "version_id,kind) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, change_id, source_id, item_id, version_id, kind),
                )
            conn.execute(
                "INSERT INTO brain_email_bridge_receipts(tenant_id,actor_id,idempotency_key,"
                "account_id,legacy_version_id,source_id,item_id,version_id,evidence_id,"
                "document_id,chunk_count,normalizer,code_revision,request_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    ctx.actor_id,
                    idempotency_key,
                    account_id,
                    legacy_version_id,
                    source_id,
                    item_id,
                    version_id,
                    evidence_id,
                    document_id,
                    len(chunks),
                    EMAIL_NORMALIZER_VERSION,
                    code_revision,
                    request_hash,
                ),
            )
            self.store.audit(
                conn, ctx, "brain.email_bridge_recorded", "message_version", str(legacy_version_id)
            )
            return EmailBridgeResult(
                source_id,
                item_id,
                version_id,
                evidence_id,
                document_id,
                len(chunks),
                True,
            )

    @staticmethod
    def _email_attachment_bridge_result(
        row: Mapping[str, Any], *, changed: bool
    ) -> EmailAttachmentBridgeResult:
        return EmailAttachmentBridgeResult(
            source_id=row["source_id"],
            item_id=row["item_id"],
            version_id=row["version_id"],
            evidence_id=row["evidence_id"],
            part_id=row["part_id"],
            document_id=row["document_id"],
            chunks=row["chunk_count"],
            outcome=row["outcome"],
            changed=changed,
        )

    def bridge_email_attachment(
        self,
        ctx: TenantContext,
        legacy_attachment_id: UUID,
        idempotency_key: UUID,
        *,
        code_revision: str,
        expected_account_id: UUID | None = None,
    ) -> EmailAttachmentBridgeResult:
        """Map one immutable Email attachment occurrence without reading its bytes."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        if (
            not code_revision
            or len(code_revision) > 200
            or "\x00" in code_revision
            or (expected_account_id is not None and not isinstance(expected_account_id, UUID))
        ):
            raise ValueError("invalid attachment bridge code revision")
        request_hash = _canonical_digest(
            {
                "legacy_attachment_id": str(legacy_attachment_id),
                "normalizer": EMAIL_ATTACHMENT_NORMALIZER_VERSION,
                "code_revision": code_revision,
            }
        )
        receipt_columns = (
            "source_id,item_id,version_id,evidence_id,part_id,document_id,chunk_count,"
            "outcome,request_hash"
        )
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:email-attachment-bridge:{legacy_attachment_id}",),
            )
            if expected_account_id is not None:
                sealed_identity = conn.execute(
                    "SELECT account_id FROM attachment_receipts WHERE id=%s",
                    (legacy_attachment_id,),
                ).fetchone()
                if not sealed_identity:
                    raise NotFound()
                if sealed_identity["account_id"] != expected_account_id:
                    raise Conflict("attachment is outside the sealed batch account")
            receipt = conn.execute(
                f"SELECT {receipt_columns} FROM brain_email_attachment_bridge_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise Conflict("idempotency key reused for a different attachment bridge")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.email_attachment_bridge_replayed",
                    "attachment_receipt",
                    str(legacy_attachment_id),
                )
                return self._email_attachment_bridge_result(receipt, changed=False)
            prior = conn.execute(
                f"SELECT {receipt_columns} FROM brain_email_attachment_bridge_receipts "
                "WHERE legacy_attachment_id=%s",
                (legacy_attachment_id,),
            ).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise Conflict("Email attachment was bridged with different provenance")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.email_attachment_bridge_replayed",
                    "attachment_receipt",
                    str(legacy_attachment_id),
                )
                return self._email_attachment_bridge_result(prior, changed=False)

            identity = conn.execute(
                "SELECT account_id FROM attachment_receipts WHERE id=%s",
                (legacy_attachment_id,),
            ).fetchone()
            if not identity:
                raise NotFound()
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:{identity['account_id']}",),
            )
            row = conn.execute(
                "SELECT a.id AS legacy_attachment_id,a.account_id,a.evidence_id AS "
                "legacy_parent_version_id,a.part_id AS legacy_part_path,a.safe_filename,"
                "a.media_type,a.sha256,a.byte_size,a.status,a.reason,a.extracted_text,"
                "mv.message_id,mv.raw_sha256,mv.parser_version,m.received_at,m.deleted,"
                "m.quarantined,m.raw_sha256 AS current_raw_sha256,"
                "m.parser_version AS current_parser_version,b.source_id,b.item_id AS "
                "parent_item_id,b.version_id AS parent_version_id,b.evidence_id AS "
                "parent_evidence_id FROM attachment_receipts a JOIN message_versions mv "
                "ON mv.tenant_id=a.tenant_id AND mv.account_id=a.account_id "
                "AND mv.id=a.evidence_id JOIN messages m ON m.tenant_id=mv.tenant_id "
                "AND m.account_id=mv.account_id AND m.id=mv.message_id "
                "JOIN brain_email_bridge_receipts b ON b.tenant_id=mv.tenant_id "
                "AND b.account_id=mv.account_id AND b.legacy_version_id=mv.id "
                "JOIN brain_evidence pe ON pe.tenant_id=b.tenant_id "
                "AND pe.id=b.evidence_id JOIN brain_source_versions pv "
                "ON pv.tenant_id=pe.tenant_id AND pv.id=pe.source_version_id "
                "JOIN brain_source_items pi ON pi.tenant_id=pv.tenant_id "
                "AND pi.id=pv.item_id AND pi.current_version_id=pv.id WHERE a.id=%s",
                (legacy_attachment_id,),
            ).fetchone()
            if not row:
                raise Conflict("attachment parent is not bridged and current")
            if row["deleted"] or row["quarantined"]:
                raise Conflict("attachment parent is not currently visible")
            if (
                row["raw_sha256"] != row["current_raw_sha256"]
                or row["parser_version"] != row["current_parser_version"]
            ):
                raise Conflict("attachment parent evidence is historical")
            if (
                not isinstance(row["legacy_part_path"], str)
                or not 1 <= len(row["legacy_part_path"]) <= 200
                or "\x00" in row["legacy_part_path"]
                or not isinstance(row["safe_filename"], str)
                or len(row["safe_filename"]) > 120
                or "\x00" in row["safe_filename"]
            ):
                raise Conflict("attachment metadata is outside the shared contract")
            extracted_text = row["extracted_text"]
            if not isinstance(extracted_text, str) or "\x00" in extracted_text:
                raise Conflict("attachment extraction is invalid")
            if row["status"] != "extracted" and extracted_text:
                raise Conflict("attachment extraction status is inconsistent")
            if len(extracted_text.encode()) > MAX_NORMALIZED_BYTES:
                raise ValueError("attachment extraction exceeds its safe bound")

            account_id = UUID(str(row["account_id"]))
            source_id = row["source_id"]
            item_id = stable_id("attachmentitem", str(legacy_attachment_id))
            version_id = stable_id(
                "attachmentversion",
                str(legacy_attachment_id),
                row["sha256"],
                str(row["byte_size"]),
            )
            evidence_id = stable_id("evidence", version_id)
            part_id = stable_id("part", row["parent_evidence_id"], str(legacy_attachment_id))
            locator = f"attachment/{legacy_attachment_id}"
            metadata = {
                "legacy_attachment_id": str(legacy_attachment_id),
                "legacy_parent_version_id": str(row["legacy_parent_version_id"]),
                "part_path": row["legacy_part_path"],
                "safe_filename": row["safe_filename"],
                "status": row["status"],
                "reason": row["reason"],
            }
            conn.execute(
                "INSERT INTO brain_source_items(tenant_id,source_id,id,locator,"
                "current_version_id,first_seen_at,last_seen_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    source_id,
                    item_id,
                    locator,
                    version_id,
                    row["received_at"],
                    row["received_at"],
                ),
            )
            saved_item = conn.execute(
                "SELECT source_id,locator FROM brain_source_items WHERE id=%s FOR UPDATE",
                (item_id,),
            ).fetchone()
            if not saved_item or (saved_item["source_id"], saved_item["locator"]) != (
                source_id,
                locator,
            ):
                raise Conflict("attachment item identity changed")
            conn.execute(
                "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
                "sha256,size_bytes,media_type,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    source_id,
                    item_id,
                    version_id,
                    row["received_at"],
                    row["sha256"],
                    row["byte_size"],
                    row["media_type"],
                    Jsonb(metadata),
                ),
            )
            saved_version = conn.execute(
                "SELECT source_id,item_id,sha256,size_bytes,media_type,metadata "
                "FROM brain_source_versions WHERE id=%s",
                (version_id,),
            ).fetchone()
            if saved_version != {
                "source_id": source_id,
                "item_id": item_id,
                "sha256": row["sha256"],
                "size_bytes": row["byte_size"],
                "media_type": row["media_type"],
                "metadata": metadata,
            }:
                raise Conflict("attachment version identity changed")
            conn.execute(
                "INSERT INTO brain_evidence(tenant_id,id,source_version_id,sha256,storage,"
                "retained) VALUES (%s,%s,%s,%s,'source_bound',false) ON CONFLICT DO NOTHING",
                (ctx.tenant_id, evidence_id, version_id, row["sha256"]),
            )
            saved_evidence = conn.execute(
                "SELECT source_version_id,sha256,storage,retained FROM brain_evidence WHERE id=%s",
                (evidence_id,),
            ).fetchone()
            if saved_evidence != {
                "source_version_id": version_id,
                "sha256": row["sha256"],
                "storage": "source_bound",
                "retained": False,
            }:
                raise Conflict("attachment evidence identity changed")
            conn.execute(
                "INSERT INTO brain_parts(tenant_id,id,parent_evidence_id,evidence_id,part_path,"
                "media_type,sha256,size_bytes,status,reason) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    part_id,
                    row["parent_evidence_id"],
                    evidence_id,
                    row["legacy_part_path"],
                    row["media_type"],
                    row["sha256"],
                    row["byte_size"],
                    row["status"],
                    row["reason"],
                ),
            )

            document_id: str | None = None
            chunks: list[tuple[int, int, str]] = []
            normalizer: str | None = None
            if row["status"] == "extracted" and extracted_text:
                normalizer = EMAIL_ATTACHMENT_NORMALIZER_VERSION
                body_sha = hashlib.sha256(extracted_text.encode()).hexdigest()
                document_id = stable_id("document", version_id, normalizer, body_sha)
                conn.execute(
                    "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
                    "body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, document_id, evidence_id, normalizer, body_sha, extracted_text),
                )
                chunks = list(deterministic_chunks(extracted_text))
                for ordinal, (start, end, chunk) in enumerate(chunks):
                    chunk_sha = hashlib.sha256(chunk.encode()).hexdigest()
                    chunk_id = stable_id("chunk", document_id, str(ordinal), chunk_sha)
                    conn.execute(
                        "INSERT INTO brain_chunks(tenant_id,id,document_id,ordinal,start_offset,"
                        "end_offset,text,sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            ctx.tenant_id,
                            chunk_id,
                            document_id,
                            ordinal,
                            start,
                            end,
                            chunk,
                            chunk_sha,
                        ),
                    )
                config_sha = _canonical_digest(
                    {"chunk_characters": CHUNK_CHARACTERS, "source": "attachment_receipt"}
                )
                provenance_id = stable_id("provenance", document_id, code_revision, config_sha)
                conn.execute(
                    "INSERT INTO brain_provenance(tenant_id,id,output_id,transform,"
                    "transform_version,code_revision,configuration_sha256,created_at) "
                    "VALUES (%s,%s,%s,'bridge_email_attachment_text',%s,%s,%s,"
                    "clock_timestamp())",
                    (
                        ctx.tenant_id,
                        provenance_id,
                        document_id,
                        normalizer,
                        code_revision,
                        config_sha,
                    ),
                )
                conn.execute(
                    "INSERT INTO brain_provenance_inputs(tenant_id,provenance_id,input_id,"
                    "ordinal) VALUES (%s,%s,%s,0)",
                    (ctx.tenant_id, provenance_id, evidence_id),
                )
            changes = [("source_version_added", version_id)]
            if document_id is not None:
                changes.append(("document_published", document_id))
            for kind, changed_id in changes:
                change_id = stable_id("change", kind, changed_id)
                conn.execute(
                    "INSERT INTO brain_change_events(tenant_id,id,source_id,item_id,version_id,"
                    "kind) VALUES (%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, change_id, source_id, item_id, version_id, kind),
                )
            conn.execute(
                "INSERT INTO brain_email_attachment_bridge_receipts(tenant_id,actor_id,"
                "idempotency_key,account_id,legacy_parent_version_id,legacy_attachment_id,"
                "parent_evidence_id,source_id,item_id,version_id,evidence_id,part_id,document_id,"
                "chunk_count,outcome,normalizer,code_revision,request_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    ctx.actor_id,
                    idempotency_key,
                    account_id,
                    row["legacy_parent_version_id"],
                    legacy_attachment_id,
                    row["parent_evidence_id"],
                    source_id,
                    item_id,
                    version_id,
                    evidence_id,
                    part_id,
                    document_id,
                    len(chunks),
                    row["status"],
                    normalizer,
                    code_revision,
                    request_hash,
                ),
            )
            self.store.audit(
                conn,
                ctx,
                "brain.email_attachment_bridge_recorded",
                "attachment_receipt",
                str(legacy_attachment_id),
            )
            return EmailAttachmentBridgeResult(
                source_id,
                item_id,
                version_id,
                evidence_id,
                part_id,
                document_id,
                len(chunks),
                row["status"],
                True,
            )

    @staticmethod
    def _email_document_bridge_result(
        row: Mapping[str, Any], *, changed: bool
    ) -> EmailDocumentBridgeResult:
        return EmailDocumentBridgeResult(
            source_id=row["source_id"],
            item_id=row["item_id"],
            version_id=row["version_id"],
            evidence_id=row["evidence_id"],
            document_id=row["document_id"],
            chunks=row["chunk_count"],
            extraction_status=row["extraction_status"],
            changed=changed,
        )

    def bridge_email_document_extraction(
        self,
        ctx: TenantContext,
        legacy_extraction_id: UUID,
        idempotency_key: UUID,
        *,
        code_revision: str,
        expected_account_id: UUID | None = None,
    ) -> EmailDocumentBridgeResult:
        """Publish one approved legacy PDF derivative on existing attachment evidence."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        if (
            not code_revision
            or len(code_revision) > 200
            or "\x00" in code_revision
            or (expected_account_id is not None and not isinstance(expected_account_id, UUID))
        ):
            raise ValueError("invalid document bridge code revision")
        request_hash = _canonical_digest(
            {
                "legacy_extraction_id": str(legacy_extraction_id),
                "bridge_contract": "email-document-bridge-v1",
                "code_revision": code_revision,
            }
        )
        receipt_columns = (
            "source_id,item_id,version_id,evidence_id,document_id,chunk_count,"
            "extraction_status,request_hash"
        )
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:email-document-bridge:{legacy_extraction_id}",),
            )
            if expected_account_id is not None:
                sealed_identity = conn.execute(
                    "SELECT account_id FROM document_extractions WHERE id=%s",
                    (legacy_extraction_id,),
                ).fetchone()
                if not sealed_identity:
                    raise NotFound()
                if sealed_identity["account_id"] != expected_account_id:
                    raise Conflict("document is outside the sealed batch account")
            receipt = conn.execute(
                f"SELECT {receipt_columns} FROM brain_email_document_bridge_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise Conflict("idempotency key reused for a different document bridge")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.email_document_bridge_replayed",
                    "document_extraction",
                    str(legacy_extraction_id),
                )
                return self._email_document_bridge_result(receipt, changed=False)
            prior = conn.execute(
                f"SELECT {receipt_columns} FROM brain_email_document_bridge_receipts "
                "WHERE legacy_extraction_id=%s",
                (legacy_extraction_id,),
            ).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise Conflict("Email document was bridged with different provenance")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.email_document_bridge_replayed",
                    "document_extraction",
                    str(legacy_extraction_id),
                )
                return self._email_document_bridge_result(prior, changed=False)

            identity = conn.execute(
                "SELECT account_id FROM document_extractions WHERE id=%s",
                (legacy_extraction_id,),
            ).fetchone()
            if not identity:
                raise NotFound()
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:{identity['account_id']}",),
            )
            row = conn.execute(
                "SELECT d.id AS legacy_extraction_id,d.account_id,d.receipt_id AS "
                "legacy_attachment_id,d.processor_version,d.policy_version,d.revision AS "
                "extraction_revision,d.status AS extraction_status,d.extracted_text,d.result,"
                "approval.id AS legacy_approval_job_id,a.evidence_id AS "
                "legacy_parent_version_id,mv.raw_sha256,mv.parser_version,m.deleted,"
                "m.quarantined,m.raw_sha256 AS current_raw_sha256,m.parser_version AS "
                "current_parser_version,ab.source_id,ab.item_id,ab.version_id,ab.evidence_id "
                "FROM document_extractions d JOIN attachment_receipts a ON "
                "a.tenant_id=d.tenant_id AND a.account_id=d.account_id AND a.id=d.receipt_id "
                "JOIN brain_email_attachment_bridge_receipts ab ON ab.tenant_id=d.tenant_id "
                "AND ab.account_id=d.account_id AND ab.legacy_attachment_id=d.receipt_id "
                "JOIN message_versions mv ON mv.tenant_id=a.tenant_id "
                "AND mv.account_id=a.account_id AND mv.id=a.evidence_id "
                "JOIN messages m ON m.tenant_id=mv.tenant_id AND m.account_id=mv.account_id "
                "AND m.id=mv.message_id JOIN brain_source_items ai ON "
                "ai.tenant_id=ab.tenant_id AND ai.id=ab.item_id "
                "AND ai.current_version_id=ab.version_id "
                "JOIN brain_email_bridge_receipts eb ON eb.tenant_id=mv.tenant_id "
                "AND eb.account_id=mv.account_id AND eb.legacy_version_id=mv.id "
                "JOIN brain_source_items pi ON pi.tenant_id=eb.tenant_id "
                "AND pi.id=eb.item_id AND pi.current_version_id=eb.version_id "
                "JOIN LATERAL (SELECT j.id FROM document_jobs j WHERE "
                "j.tenant_id=d.tenant_id AND j.account_id=d.account_id "
                "AND j.receipt_id=d.receipt_id AND j.extraction_id=d.id "
                "AND j.processor_version=d.processor_version "
                "AND j.policy_version=d.policy_version AND j.status='completed' "
                "AND j.outcome='result_saved' ORDER BY j.created_at,j.id LIMIT 1) approval "
                "ON true WHERE d.id=%s",
                (legacy_extraction_id,),
            ).fetchone()
            if not row:
                raise Conflict(
                    "document extraction is not approved on a bridged current attachment"
                )
            if row["deleted"] or row["quarantined"]:
                raise Conflict("document parent is not currently visible")
            if (
                row["raw_sha256"] != row["current_raw_sha256"]
                or row["parser_version"] != row["current_parser_version"]
            ):
                raise Conflict("document parent evidence is historical")
            text = row["extracted_text"]
            if (
                row["extraction_status"] not in {"extracted", "partial"}
                or not isinstance(text, str)
                or not text
                or "\x00" in text
                or len(text.encode()) > MAX_NORMALIZED_BYTES
            ):
                raise Conflict("document extraction is outside the shared text contract")
            normalizer = (
                f"{EMAIL_DOCUMENT_NORMALIZER_PREFIX}:{row['processor_version']}:"
                f"{row['policy_version']}"
            )
            if len(normalizer) > 200:
                raise Conflict("document extractor identity is outside the shared contract")
            result_sha = _canonical_digest(row["result"])
            body_sha = hashlib.sha256(text.encode()).hexdigest()
            document_id = stable_id("document", row["version_id"], normalizer, body_sha)
            conn.execute(
                "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
                "body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, document_id, row["evidence_id"], normalizer, body_sha, text),
            )
            chunks = list(deterministic_chunks(text))
            for ordinal, (start, end, chunk) in enumerate(chunks):
                chunk_sha = hashlib.sha256(chunk.encode()).hexdigest()
                chunk_id = stable_id("chunk", document_id, str(ordinal), chunk_sha)
                conn.execute(
                    "INSERT INTO brain_chunks(tenant_id,id,document_id,ordinal,start_offset,"
                    "end_offset,text,sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        chunk_id,
                        document_id,
                        ordinal,
                        start,
                        end,
                        chunk,
                        chunk_sha,
                    ),
                )
            config_sha = _canonical_digest(
                {
                    "chunk_characters": CHUNK_CHARACTERS,
                    "source": "document_extractions",
                    "processor_version": row["processor_version"],
                    "policy_version": row["policy_version"],
                    "extraction_revision": row["extraction_revision"],
                    "extraction_status": row["extraction_status"],
                    "result_sha256": result_sha,
                }
            )
            provenance_id = stable_id("provenance", document_id, code_revision, config_sha)
            conn.execute(
                "INSERT INTO brain_provenance(tenant_id,id,output_id,transform,"
                "transform_version,code_revision,configuration_sha256,created_at) "
                "VALUES (%s,%s,%s,'bridge_email_document_extraction',%s,%s,%s,"
                "clock_timestamp())",
                (
                    ctx.tenant_id,
                    provenance_id,
                    document_id,
                    normalizer,
                    code_revision,
                    config_sha,
                ),
            )
            conn.execute(
                "INSERT INTO brain_provenance_inputs(tenant_id,provenance_id,input_id,ordinal) "
                "VALUES (%s,%s,%s,0)",
                (ctx.tenant_id, provenance_id, row["evidence_id"]),
            )
            change_id = stable_id("change", "document_published", document_id)
            conn.execute(
                "INSERT INTO brain_change_events(tenant_id,id,source_id,item_id,version_id,kind) "
                "VALUES (%s,%s,%s,%s,%s,'document_published')",
                (
                    ctx.tenant_id,
                    change_id,
                    row["source_id"],
                    row["item_id"],
                    row["version_id"],
                ),
            )
            conn.execute(
                "INSERT INTO brain_email_document_bridge_receipts(tenant_id,actor_id,"
                "idempotency_key,account_id,legacy_attachment_id,legacy_extraction_id,"
                "legacy_approval_job_id,source_id,item_id,version_id,evidence_id,document_id,"
                "chunk_count,extraction_status,extraction_revision,processor_version,"
                "policy_version,normalizer,result_sha256,code_revision,request_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    ctx.actor_id,
                    idempotency_key,
                    row["account_id"],
                    row["legacy_attachment_id"],
                    legacy_extraction_id,
                    row["legacy_approval_job_id"],
                    row["source_id"],
                    row["item_id"],
                    row["version_id"],
                    row["evidence_id"],
                    document_id,
                    len(chunks),
                    row["extraction_status"],
                    row["extraction_revision"],
                    row["processor_version"],
                    row["policy_version"],
                    normalizer,
                    result_sha,
                    code_revision,
                    request_hash,
                ),
            )
            self.store.audit(
                conn,
                ctx,
                "brain.email_document_bridge_recorded",
                "document_extraction",
                str(legacy_extraction_id),
            )
            return EmailDocumentBridgeResult(
                row["source_id"],
                row["item_id"],
                row["version_id"],
                row["evidence_id"],
                document_id,
                len(chunks),
                row["extraction_status"],
                True,
            )

    @staticmethod
    def _archive_inventory_record(
        row: Mapping[str, Any], *, changed: bool
    ) -> ArchiveInventoryRecord:
        return ArchiveInventoryRecord(
            row["id"],
            row["source_id"],
            row["item_id"],
            row["source_version_id"],
            row["processor_version"],
            row["member_count"],
            row["skipped_count"],
            changed,
        )

    def record_archive_inventory(
        self,
        ctx: TenantContext,
        result: ArchiveResult,
        processor_version: str,
        idempotency_key: UUID,
    ) -> ArchiveInventoryRecord:
        """Persist one accepted hash-only archive manifest; never publish child evidence."""
        self.store.require(ctx, "brain.source.ingest")
        if (
            not isinstance(result, ArchiveResult)
            or not isinstance(processor_version, str)
            or not _ARCHIVE_PROCESSOR.fullmatch(processor_version)
            or not isinstance(idempotency_key, UUID)
            or result.status not in {"complete", "partial"}
        ):
            raise ValueError("invalid accepted archive inventory")
        try:
            validated = decode_archive_result(encode_archive_result(result), result.source)
        except ArchiveUnavailable:
            raise ValueError("invalid accepted archive inventory") from None
        if validated != result or result.format not in {"zip", "tar"}:
            raise ValueError("invalid accepted archive inventory")
        result_data = asdict(result)
        result_sha = _canonical_digest(result_data)
        request_hash = _canonical_digest(
            {
                "contract": "archive-inventory-persistence-v1",
                "processor_version": processor_version,
                "result_sha256": result_sha,
            }
        )
        inventory_id = stable_id(
            "archive_inventory", result.source.version_id, processor_version, result_sha
        )
        columns = (
            "id,source_id,item_id,source_version_id,processor_version,member_count,"
            "skipped_count,result_sha256"
        )
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:archive:{result.source.version_id}:{processor_version}",),
            )
            receipt = conn.execute(
                "SELECT r.request_hash,i." + columns.replace(",", ",i.") + " "
                "FROM brain_archive_inventory_receipts r JOIN brain_archive_inventories i "
                "ON i.tenant_id=r.tenant_id AND i.id=r.inventory_id "
                "WHERE r.actor_id=%s AND r.idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise Conflict("idempotency key reused for a different archive inventory")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.archive_inventory_replayed",
                    "source_version",
                    result.source.version_id,
                )
                return self._archive_inventory_record(receipt, changed=False)

            source = conn.execute(
                "SELECT v.source_id,v.item_id,v.sha256,v.size_bytes,v.media_type,i.locator,"
                "i.current_version_id,s.kind FROM brain_source_versions v "
                "JOIN brain_source_items i ON i.tenant_id=v.tenant_id AND i.source_id=v.source_id "
                "AND i.id=v.item_id JOIN brain_sources s ON s.tenant_id=v.tenant_id "
                "AND s.id=v.source_id WHERE v.id=%s FOR UPDATE OF i",
                (result.source.version_id,),
            ).fetchone()
            expected = result.source
            if not source:
                raise NotFound()
            if source["kind"] != SourceKind.FILEOS.value:
                raise Conflict("archive parent is not a FileOS source version")
            if source["current_version_id"] != expected.version_id:
                raise Conflict("archive parent source version is historical")
            if (
                source["sha256"],
                source["size_bytes"],
                source["media_type"],
                source["locator"],
            ) != (expected.sha256, expected.size_bytes, expected.media_type, expected.locator):
                raise Conflict("archive parent identity does not match immutable source")

            prior = conn.execute(
                f"SELECT {columns} FROM brain_archive_inventories "
                "WHERE source_version_id=%s AND processor_version=%s",
                (expected.version_id, processor_version),
            ).fetchone()
            if prior:
                if prior["result_sha256"] != result_sha:
                    raise Conflict("archive processor produced a different manifest")
                conn.execute(
                    "INSERT INTO brain_archive_inventory_receipts(tenant_id,actor_id,"
                    "idempotency_key,request_hash,inventory_id) VALUES (%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        ctx.actor_id,
                        idempotency_key,
                        request_hash,
                        prior["id"],
                    ),
                )
                self.store.audit(
                    conn,
                    ctx,
                    "brain.archive_inventory_replayed",
                    "source_version",
                    expected.version_id,
                )
                return self._archive_inventory_record(prior, changed=False)

            conn.execute(
                "INSERT INTO brain_archive_inventories(tenant_id,id,source_id,item_id,"
                "source_version_id,processor_version,result_sha256,archive_format,status,"
                "reason,member_count,skipped_count,file_count,total_uncompressed_bytes) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    inventory_id,
                    source["source_id"],
                    source["item_id"],
                    expected.version_id,
                    processor_version,
                    result_sha,
                    result.format,
                    result.status,
                    result.reason,
                    len(result.members),
                    len(result.skipped),
                    result.file_count,
                    result.total_uncompressed_bytes,
                ),
            )
            for ordinal, member in enumerate(result.members):
                conn.execute(
                    "INSERT INTO brain_archive_members(tenant_id,inventory_id,ordinal,locator,"
                    "sha256,declared_size,observed_size,media_hint,depth,parent_locator,"
                    "is_container) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        inventory_id,
                        ordinal,
                        member.locator,
                        member.sha256,
                        member.declared_size,
                        member.observed_size,
                        member.media_hint,
                        member.depth,
                        member.parent_locator,
                        member.is_container,
                    ),
                )
            for ordinal, skipped in enumerate(result.skipped):
                conn.execute(
                    "INSERT INTO brain_archive_skips(tenant_id,inventory_id,ordinal,locator,"
                    "reason,depth,parent_locator) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        inventory_id,
                        ordinal,
                        skipped.locator,
                        skipped.reason,
                        skipped.depth,
                        skipped.parent_locator,
                    ),
                )
            conn.execute(
                "INSERT INTO brain_archive_inventory_receipts(tenant_id,actor_id,"
                "idempotency_key,request_hash,inventory_id) VALUES (%s,%s,%s,%s,%s)",
                (ctx.tenant_id, ctx.actor_id, idempotency_key, request_hash, inventory_id),
            )
            self.store.audit(
                conn,
                ctx,
                "brain.archive_inventory_recorded",
                "source_version",
                expected.version_id,
            )
            return ArchiveInventoryRecord(
                inventory_id,
                source["source_id"],
                source["item_id"],
                expected.version_id,
                processor_version,
                len(result.members),
                len(result.skipped),
                True,
            )

    def archive_member_target(
        self, ctx: TenantContext, inventory_id: str, member_locator: str
    ) -> ArchiveMemberTargetRecord:
        """Resolve one current, accepted, non-container member through forced RLS."""
        self.store.require(ctx, "brain.source.ingest")
        if (
            not isinstance(inventory_id, str)
            or not re.fullmatch(r"archive_inventory_[a-f0-9]{32}", inventory_id)
            or not isinstance(member_locator, str)
            or not 1 <= len(member_locator) <= 1024
            or "\x00" in member_locator
            or "\\" in member_locator
        ):
            raise ValueError("invalid archive member selection")
        with self.store.transaction(ctx) as conn:
            row = conn.execute(
                "SELECT a.id AS inventory_id,a.processor_version,a.source_id,a.item_id,"
                "a.source_version_id,i.locator AS source_locator,v.sha256 AS source_sha256,"
                "v.size_bytes AS source_size_bytes,v.media_type AS source_media_type,"
                "m.locator AS member_locator,m.sha256 AS member_sha256,"
                "m.observed_size AS member_size_bytes,m.media_hint AS member_media_type,"
                "m.depth AS member_depth,"
                "m.parent_locator AS member_parent_locator "
                "FROM brain_archive_inventories a JOIN brain_archive_members m "
                "ON m.tenant_id=a.tenant_id AND m.inventory_id=a.id "
                "JOIN brain_source_versions v ON v.tenant_id=a.tenant_id "
                "AND v.id=a.source_version_id JOIN brain_source_items i "
                "ON i.tenant_id=v.tenant_id AND i.source_id=v.source_id AND i.id=v.item_id "
                "WHERE a.id=%s AND m.locator=%s AND NOT m.is_container "
                "AND a.status IN ('complete','partial') "
                "AND i.current_version_id=a.source_version_id",
                (inventory_id, member_locator),
            ).fetchone()
            if not row:
                raise NotFound()
            self.store.audit(
                conn,
                ctx,
                "brain.archive_member_selected",
                "archive_inventory",
                inventory_id,
            )
            return ArchiveMemberTargetRecord(
                row["inventory_id"],
                row["processor_version"],
                row["source_id"],
                row["item_id"],
                row["source_version_id"],
                row["source_locator"],
                row["source_sha256"],
                row["source_size_bytes"],
                row["source_media_type"],
                row["member_locator"],
                row["member_sha256"],
                row["member_size_bytes"],
                row["member_media_type"],
                row["member_depth"],
                row["member_parent_locator"],
            )

    @staticmethod
    def _archive_member_text_record(
        row: Mapping[str, Any], *, changed: bool
    ) -> ArchiveMemberTextRecord:
        return ArchiveMemberTextRecord(
            row["inventory_id"],
            row["member_locator"],
            row["source_id"],
            row["item_id"],
            row["version_id"],
            row["evidence_id"],
            row["document_id"],
            row["chunk_count"],
            changed,
        )

    def publish_archive_member_text(
        self,
        ctx: TenantContext,
        target: ArchiveMemberTargetRecord,
        text: str,
        normalizer: str,
        code_revision: str,
        idempotency_key: UUID,
    ) -> ArchiveMemberTextRecord:
        """Publish one already-read archive member as distinct derived evidence."""
        self.store.require(ctx, "brain.source.ingest")
        self.store.require(ctx, "brain.document.publish")
        if (
            not isinstance(target, ArchiveMemberTargetRecord)
            or not isinstance(text, str)
            or not text
            or "\x00" in text
            or len(text.encode()) > MAX_NORMALIZED_BYTES
            or target.member_size_bytes > MAX_NORMALIZED_BYTES
            or PurePosixPath(target.member_locator).suffix.lower() not in _ARCHIVE_TEXT_SUFFIXES
            or normalizer != FILEOS_TEXT_EXTRACTOR_VERSION
            or not isinstance(code_revision, str)
            or not 1 <= len(code_revision) <= 200
            or "\x00" in code_revision
            or not isinstance(idempotency_key, UUID)
        ):
            raise ValueError("invalid archive member text publication")
        body_sha = hashlib.sha256(text.encode()).hexdigest()
        request_hash = _canonical_digest(
            {
                "contract": "archive-member-text-v1",
                "target": asdict(target),
                "body_sha256": body_sha,
                "normalizer": normalizer,
                "code_revision": code_revision,
            }
        )
        columns = (
            "inventory_id,member_locator,source_id,item_id,version_id,evidence_id,"
            "document_id,chunk_count,request_hash"
        )
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:archive-member:{target.inventory_id}:{target.member_locator}",),
            )
            receipt = conn.execute(
                f"SELECT {columns} FROM brain_archive_member_text_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise Conflict("idempotency key reused for different archive member text")
                self.store.audit(
                    conn,
                    ctx,
                    "brain.archive_member_text_replayed",
                    "archive_inventory",
                    target.inventory_id,
                )
                return self._archive_member_text_record(receipt, changed=False)

            prior = conn.execute(
                f"SELECT actor_id,idempotency_key,{columns} "
                "FROM brain_archive_member_text_receipts "
                "WHERE inventory_id=%s AND member_locator=%s AND normalizer=%s "
                "ORDER BY created_at,actor_id,idempotency_key LIMIT 1",
                (target.inventory_id, target.member_locator, normalizer),
            ).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise Conflict("archive member text was published with different provenance")
                conn.execute(
                    "INSERT INTO brain_archive_member_text_receipts(tenant_id,actor_id,"
                    "idempotency_key,inventory_id,member_locator,parent_source_version_id,"
                    "parent_evidence_id,source_id,item_id,version_id,evidence_id,document_id,"
                    "normalizer,chunk_count,code_revision,request_hash) SELECT %s,%s,%s,"
                    "inventory_id,member_locator,parent_source_version_id,parent_evidence_id,"
                    "source_id,item_id,version_id,evidence_id,document_id,normalizer,chunk_count,"
                    "code_revision,request_hash FROM brain_archive_member_text_receipts "
                    "WHERE tenant_id=%s AND actor_id=%s AND idempotency_key=%s",
                    (
                        ctx.tenant_id,
                        ctx.actor_id,
                        idempotency_key,
                        ctx.tenant_id,
                        prior["actor_id"],
                        prior["idempotency_key"],
                    ),
                )
                self.store.audit(
                    conn,
                    ctx,
                    "brain.archive_member_text_replayed",
                    "archive_inventory",
                    target.inventory_id,
                )
                return self._archive_member_text_record(prior, changed=False)

            row = conn.execute(
                "SELECT a.id AS inventory_id,a.processor_version,a.source_id,a.item_id AS "
                "parent_item_id,a.source_version_id,v.observed_at,v.sha256 AS source_sha256,"
                "v.size_bytes AS source_size_bytes,v.media_type AS source_media_type,"
                "i.locator AS source_locator,i.current_version_id,e.id AS parent_evidence_id,"
                "m.locator AS member_locator,m.sha256 AS member_sha256,"
                "m.observed_size AS member_size_bytes,m.media_hint AS member_media_type,"
                "m.depth AS member_depth,m.parent_locator AS member_parent_locator,"
                "m.is_container FROM brain_archive_inventories a "
                "JOIN brain_archive_members m ON m.tenant_id=a.tenant_id "
                "AND m.inventory_id=a.id JOIN brain_source_versions v "
                "ON v.tenant_id=a.tenant_id AND v.id=a.source_version_id "
                "JOIN brain_source_items i ON i.tenant_id=v.tenant_id "
                "AND i.source_id=v.source_id AND i.id=v.item_id "
                "JOIN brain_evidence e ON e.tenant_id=v.tenant_id "
                "AND e.source_version_id=v.id WHERE a.id=%s AND m.locator=%s "
                "FOR UPDATE OF i",
                (target.inventory_id, target.member_locator),
            ).fetchone()
            if not row or row["is_container"]:
                raise NotFound()
            actual = ArchiveMemberTargetRecord(
                row["inventory_id"],
                row["processor_version"],
                row["source_id"],
                row["parent_item_id"],
                row["source_version_id"],
                row["source_locator"],
                row["source_sha256"],
                row["source_size_bytes"],
                row["source_media_type"],
                row["member_locator"],
                row["member_sha256"],
                row["member_size_bytes"],
                row["member_media_type"],
                row["member_depth"],
                row["member_parent_locator"],
            )
            if row["current_version_id"] != target.source_version_id or actual != target:
                raise Conflict("archive member parent or identity is no longer current")

            item_id = stable_id("archiveitem", target.inventory_id, target.member_locator)
            version_id = stable_id(
                "archiveversion",
                target.inventory_id,
                target.inventory_processor_version,
                target.member_locator,
                target.member_sha256,
                str(target.member_size_bytes),
            )
            evidence_id = stable_id("evidence", version_id)
            document_id = stable_id("document", version_id, normalizer, body_sha)
            locator = f"archive-member/{item_id}"
            metadata = {
                "derived_from": target.source_version_id,
                "inventory_id": target.inventory_id,
                "member_locator": target.member_locator,
                "inventory_processor": target.inventory_processor_version,
            }
            conn.execute(
                "INSERT INTO brain_source_items(tenant_id,source_id,id,locator,"
                "current_version_id,first_seen_at,last_seen_at) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    target.source_id,
                    item_id,
                    locator,
                    version_id,
                    row["observed_at"],
                    row["observed_at"],
                ),
            )
            saved_item = conn.execute(
                "SELECT source_id,locator,current_version_id FROM brain_source_items "
                "WHERE id=%s FOR UPDATE",
                (item_id,),
            ).fetchone()
            if saved_item != {
                "source_id": target.source_id,
                "locator": locator,
                "current_version_id": version_id,
            }:
                raise Conflict("archive member child item identity changed")
            conn.execute(
                "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
                "sha256,size_bytes,media_type,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (
                    ctx.tenant_id,
                    target.source_id,
                    item_id,
                    version_id,
                    row["observed_at"],
                    target.member_sha256,
                    target.member_size_bytes,
                    target.member_media_type,
                    Jsonb(metadata),
                ),
            )
            saved_version = conn.execute(
                "SELECT source_id,item_id,sha256,size_bytes,media_type,metadata "
                "FROM brain_source_versions WHERE id=%s",
                (version_id,),
            ).fetchone()
            if saved_version != {
                "source_id": target.source_id,
                "item_id": item_id,
                "sha256": target.member_sha256,
                "size_bytes": target.member_size_bytes,
                "media_type": target.member_media_type,
                "metadata": metadata,
            }:
                raise Conflict("archive member child version identity changed")
            conn.execute(
                "INSERT INTO brain_evidence(tenant_id,id,source_version_id,sha256,storage,"
                "retained) VALUES (%s,%s,%s,%s,'source_bound',false) "
                "ON CONFLICT DO NOTHING",
                (ctx.tenant_id, evidence_id, version_id, target.member_sha256),
            )
            saved_evidence = conn.execute(
                "SELECT source_version_id,sha256,storage,retained FROM brain_evidence WHERE id=%s",
                (evidence_id,),
            ).fetchone()
            if saved_evidence != {
                "source_version_id": version_id,
                "sha256": target.member_sha256,
                "storage": "source_bound",
                "retained": False,
            }:
                raise Conflict("archive member child evidence identity changed")
            conn.execute(
                "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
                "body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, document_id, evidence_id, normalizer, body_sha, text),
            )
            chunks = list(deterministic_chunks(text))
            for ordinal, (start, end, chunk) in enumerate(chunks):
                chunk_sha = hashlib.sha256(chunk.encode()).hexdigest()
                conn.execute(
                    "INSERT INTO brain_chunks(tenant_id,id,document_id,ordinal,start_offset,"
                    "end_offset,text,sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        stable_id("chunk", document_id, str(ordinal), chunk_sha),
                        document_id,
                        ordinal,
                        start,
                        end,
                        chunk,
                        chunk_sha,
                    ),
                )
            config_sha = _canonical_digest(
                {
                    "contract": "archive-member-text-v1",
                    "inventory_processor": target.inventory_processor_version,
                    "member_read_contract": "sandbox-fileos-archive-member-v1",
                    "normalizer": normalizer,
                    "chunk_characters": CHUNK_CHARACTERS,
                }
            )
            provenance_id = stable_id("provenance", document_id, code_revision, config_sha)
            conn.execute(
                "INSERT INTO brain_provenance(tenant_id,id,output_id,transform,"
                "transform_version,code_revision,configuration_sha256,created_at) "
                "VALUES (%s,%s,%s,'archive_member_text',%s,%s,%s,clock_timestamp())",
                (
                    ctx.tenant_id,
                    provenance_id,
                    document_id,
                    normalizer,
                    code_revision,
                    config_sha,
                ),
            )
            for ordinal, input_id in enumerate((row["parent_evidence_id"], target.inventory_id)):
                conn.execute(
                    "INSERT INTO brain_provenance_inputs(tenant_id,provenance_id,input_id,"
                    "ordinal) VALUES (%s,%s,%s,%s)",
                    (ctx.tenant_id, provenance_id, input_id, ordinal),
                )
            conn.execute(
                "INSERT INTO brain_change_events(tenant_id,id,source_id,item_id,version_id,kind) "
                "VALUES (%s,%s,%s,%s,%s,'document_published')",
                (
                    ctx.tenant_id,
                    stable_id("change", "document_published", document_id),
                    target.source_id,
                    item_id,
                    version_id,
                ),
            )
            conn.execute(
                "INSERT INTO brain_archive_member_text_receipts(tenant_id,actor_id,"
                "idempotency_key,inventory_id,member_locator,parent_source_version_id,"
                "parent_evidence_id,source_id,item_id,version_id,evidence_id,document_id,"
                "normalizer,chunk_count,code_revision,request_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    ctx.actor_id,
                    idempotency_key,
                    target.inventory_id,
                    target.member_locator,
                    target.source_version_id,
                    row["parent_evidence_id"],
                    target.source_id,
                    item_id,
                    version_id,
                    evidence_id,
                    document_id,
                    normalizer,
                    len(chunks),
                    code_revision,
                    request_hash,
                ),
            )
            self.store.audit(
                conn,
                ctx,
                "brain.archive_member_text_published",
                "archive_inventory",
                target.inventory_id,
            )
            return ArchiveMemberTextRecord(
                target.inventory_id,
                target.member_locator,
                target.source_id,
                item_id,
                version_id,
                evidence_id,
                document_id,
                len(chunks),
                True,
            )

    def import_fileos_snapshot(
        self,
        ctx: TenantContext,
        manifest: Mapping[str, Any],
        idempotency_key: UUID,
    ) -> ImportResult:
        self.store.require(ctx, "brain.source.ingest")
        source, observed_at, items = _manifest_items(manifest)
        request_hash = _canonical_digest(manifest)
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:{ctx.actor_id}:{idempotency_key}",),
            )
            receipt = conn.execute(
                "SELECT request_hash,result FROM brain_import_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if receipt:
                if receipt["request_hash"] != request_hash:
                    raise Conflict("idempotency key reused for a different snapshot")
                return ImportResult(**receipt["result"])
            conn.execute(
                "INSERT INTO brain_sources(tenant_id,id,kind,display_name) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,id) DO NOTHING",
                (ctx.tenant_id, source.source_id, source.kind.value, source.display_name),
            )
            saved_source = conn.execute(
                "SELECT kind FROM brain_sources WHERE id=%s FOR UPDATE", (source.source_id,)
            ).fetchone()
            if not saved_source or saved_source["kind"] != source.kind.value:
                raise Conflict("source identity has a different kind")

            new_versions = 0
            for item in items:
                conn.execute(
                    "INSERT INTO brain_source_items(tenant_id,source_id,id,locator,"
                    "current_version_id,"
                    "first_seen_at,last_seen_at) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (tenant_id,id) DO NOTHING",
                    (
                        ctx.tenant_id,
                        source.source_id,
                        item.item_id,
                        item.locator,
                        item.version_id,
                        observed_at,
                        observed_at,
                    ),
                )
                saved_item = conn.execute(
                    "SELECT source_id,locator FROM brain_source_items WHERE id=%s FOR UPDATE",
                    (item.item_id,),
                ).fetchone()
                if not saved_item or (saved_item["source_id"], saved_item["locator"]) != (
                    source.source_id,
                    item.locator,
                ):
                    raise Conflict("source item identity changed")
                inserted = conn.execute(
                    "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
                    "sha256,size_bytes,media_type,metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (tenant_id,id) DO NOTHING RETURNING id",
                    (
                        ctx.tenant_id,
                        source.source_id,
                        item.item_id,
                        item.version_id,
                        item.observed_at,
                        item.content.value,
                        item.size_bytes,
                        item.media_type,
                        Jsonb(dict(item.metadata)),
                    ),
                ).fetchone()
                saved_version = conn.execute(
                    "SELECT source_id,item_id,sha256,size_bytes,media_type,metadata "
                    "FROM brain_source_versions WHERE id=%s",
                    (item.version_id,),
                ).fetchone()
                if not saved_version or saved_version != {
                    "source_id": source.source_id,
                    "item_id": item.item_id,
                    "sha256": item.content.value,
                    "size_bytes": item.size_bytes,
                    "media_type": item.media_type,
                    "metadata": dict(item.metadata),
                }:
                    raise Conflict("source version identity changed")
                conn.execute(
                    "UPDATE brain_source_items SET first_seen_at=least(first_seen_at,%s),"
                    "last_seen_at=greatest(last_seen_at,%s),"
                    "current_version_id=CASE WHEN %s>=last_seen_at THEN %s "
                    "ELSE current_version_id END "
                    "WHERE id=%s",
                    (observed_at, observed_at, observed_at, item.version_id, item.item_id),
                )
                evidence_id = stable_id("evidence", item.version_id)
                conn.execute(
                    "INSERT INTO brain_evidence(tenant_id,id,source_version_id,sha256,"
                    "storage,retained) "
                    "VALUES (%s,%s,%s,%s,'source_bound',false) ON CONFLICT DO NOTHING",
                    (ctx.tenant_id, evidence_id, item.version_id, item.content.value),
                )
                if inserted:
                    new_versions += 1
                    change_id = stable_id("change", "source_version_added", item.version_id)
                    conn.execute(
                        "INSERT INTO brain_change_events(tenant_id,id,source_id,item_id,"
                        "version_id,kind) "
                        "VALUES (%s,%s,%s,%s,%s,'source_version_added')",
                        (
                            ctx.tenant_id,
                            change_id,
                            source.source_id,
                            item.item_id,
                            item.version_id,
                        ),
                    )
            result = ImportResult(
                source.source_id, len(items), new_versions, len(items) - new_versions
            )
            conn.execute(
                "INSERT INTO brain_import_receipts(tenant_id,actor_id,idempotency_key,"
                "request_hash,result) "
                "VALUES (%s,%s,%s,%s,%s)",
                (ctx.tenant_id, ctx.actor_id, idempotency_key, request_hash, Jsonb(asdict(result))),
            )
            return result

    def complete_fileos_run(
        self,
        ctx: TenantContext,
        manifest: Mapping[str, Any],
        run_id: UUID,
        *,
        outcomes: Mapping[str, int],
        item_outcomes: Mapping[str, str],
        published_documents: int,
        code_revision: str,
        document_processor_version: str | None,
    ) -> FileOSRunReceipt:
        """Append a completion receipt only after every snapshot item is accounted."""
        self.store.require(ctx, "brain.document.publish")
        source, observed_at, items = _manifest_items(manifest)
        allowed = {"extracted", "empty", "unsupported", "deferred", "changed", "failed"}
        counts = dict(sorted(outcomes.items()))
        items_by_id = {item.item_id: item for item in items}
        item_results = dict(sorted(item_outcomes.items()))
        calculated: dict[str, int] = {}
        for outcome in item_results.values():
            calculated[outcome] = calculated.get(outcome, 0) + 1
        if (
            not isinstance(run_id, UUID)
            or (not counts and bool(items))
            or not set(counts) <= allowed
            or any(type(value) is not int or value <= 0 for value in counts.values())
            or set(item_results) != set(items_by_id)
            or not set(item_results.values()) <= allowed
            or dict(sorted(calculated.items())) != counts
            or sum(counts.values()) != len(items)
            or type(published_documents) is not int
            or not 0 <= published_documents <= len(items)
            or published_documents != counts.get("extracted", 0)
        ):
            raise ValueError("invalid FileOS completion counts")
        for descriptor in (code_revision, FILEOS_TEXT_EXTRACTOR_VERSION):
            if not descriptor or len(descriptor) > 200 or "\x00" in descriptor:
                raise ValueError("invalid FileOS completion provenance")
        if document_processor_version is not None and (
            not document_processor_version
            or len(document_processor_version) > 200
            or "\x00" in document_processor_version
        ):
            raise ValueError("invalid document processor provenance")
        manifest_hash = _canonical_digest(manifest)
        expected = {
            "source_id": source.source_id,
            "observed_at": observed_at,
            "manifest_sha256": manifest_hash,
            "code_revision": code_revision,
            "text_extractor_version": FILEOS_TEXT_EXTRACTOR_VERSION,
            "document_processor_version": document_processor_version,
            "item_count": len(items),
            "outcomes": counts,
            "published_documents": published_documents,
        }
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:fileos-source:{source.source_id}",),
            )
            imported = conn.execute(
                "SELECT request_hash,result FROM brain_import_receipts "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, run_id),
            ).fetchone()
            if (
                not imported
                or imported["request_hash"] != manifest_hash
                or imported["result"].get("source_id") != source.source_id
                or imported["result"].get("observed_items") != len(items)
            ):
                raise Conflict("FileOS completion is not bound to its intake")
            existing = conn.execute(
                "SELECT source_id,observed_at,manifest_sha256,code_revision,"
                "text_extractor_version,document_processor_version,item_count,outcomes,"
                "published_documents,completed_at "
                "FROM brain_fileos_run_receipts WHERE actor_id=%s AND run_id=%s",
                (ctx.actor_id, run_id),
            ).fetchone()
            previous = conn.execute(
                "SELECT actor_id,run_id,observed_at,manifest_sha256 "
                "FROM brain_fileos_run_receipts WHERE source_id=%s "
                "AND NOT (actor_id=%s AND run_id=%s) "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source.source_id, ctx.actor_id, run_id),
            ).fetchone()
            if previous and observed_at <= previous["observed_at"]:
                raise Conflict("FileOS completion observation is not newer")
            recorded = existing is None
            if existing:
                completed_at = existing.pop("completed_at")
                if existing != expected:
                    raise Conflict("FileOS completion receipt changed")
            else:
                row = conn.execute(
                    "INSERT INTO brain_fileos_run_receipts(tenant_id,actor_id,run_id,source_id,"
                    "observed_at,manifest_sha256,code_revision,text_extractor_version,"
                    "document_processor_version,item_count,outcomes,published_documents) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                    "RETURNING completed_at",
                    (
                        ctx.tenant_id,
                        ctx.actor_id,
                        run_id,
                        source.source_id,
                        observed_at,
                        manifest_hash,
                        code_revision,
                        FILEOS_TEXT_EXTRACTOR_VERSION,
                        document_processor_version,
                        len(items),
                        Jsonb(counts),
                        published_documents,
                    ),
                ).fetchone()
                assert row is not None
                completed_at = row["completed_at"]
            for item_id, outcome in item_results.items():
                item = items_by_id[item_id]
                conn.execute(
                    "INSERT INTO brain_fileos_run_items(tenant_id,actor_id,run_id,source_id,"
                    "observed_at,item_id,version_id,outcome) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT DO NOTHING",
                    (
                        ctx.tenant_id,
                        ctx.actor_id,
                        run_id,
                        source.source_id,
                        observed_at,
                        item_id,
                        item.version_id,
                        outcome,
                    ),
                )
            saved_items = conn.execute(
                "SELECT item_id,version_id,outcome FROM brain_fileos_run_items "
                "WHERE actor_id=%s AND run_id=%s ORDER BY item_id",
                (ctx.actor_id, run_id),
            ).fetchall()
            expected_items = [
                {
                    "item_id": item_id,
                    "version_id": items_by_id[item_id].version_id,
                    "outcome": outcome,
                }
                for item_id, outcome in item_results.items()
            ]
            if saved_items != expected_items:
                raise Conflict("FileOS run item ledger changed")
            if previous:
                missing = conn.execute(
                    "SELECT old.item_id,old.version_id FROM brain_fileos_run_items old "
                    "LEFT JOIN brain_fileos_run_items current ON current.tenant_id=old.tenant_id "
                    "AND current.actor_id=%s AND current.run_id=%s "
                    "AND current.item_id=old.item_id "
                    "WHERE old.actor_id=%s AND old.run_id=%s AND current.item_id IS NULL "
                    "ORDER BY old.item_id",
                    (ctx.actor_id, run_id, previous["actor_id"], previous["run_id"]),
                ).fetchall()
                for missing_item in missing:
                    event_id = stable_id(
                        "absence", str(run_id), missing_item["item_id"], missing_item["version_id"]
                    )
                    conn.execute(
                        "INSERT INTO brain_fileos_absence_events(tenant_id,id,source_id,item_id,"
                        "version_id,previous_actor_id,previous_run_id,observed_actor_id,"
                        "observed_run_id,observed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT DO NOTHING",
                        (
                            ctx.tenant_id,
                            event_id,
                            source.source_id,
                            missing_item["item_id"],
                            missing_item["version_id"],
                            previous["actor_id"],
                            previous["run_id"],
                            ctx.actor_id,
                            run_id,
                            observed_at,
                        ),
                    )
            return FileOSRunReceipt(
                run_id,
                source.source_id,
                observed_at,
                completed_at,
                len(items),
                counts,
                published_documents,
                recorded,
            )

    def fileos_freshness(self, ctx: TenantContext, source_id: str) -> dict[str, Any]:
        """Return the latest complete run, never an in-progress or partial prefix."""
        self.store.require(ctx, "brain.changes.read")
        if not _IDENTITY.fullmatch(source_id):
            raise NotFound()
        with self.store.transaction(ctx) as conn:
            if not conn.execute("SELECT 1 FROM brain_sources WHERE id=%s", (source_id,)).fetchone():
                raise NotFound()
            row = conn.execute(
                "SELECT run_id,observed_at,completed_at,item_count,outcomes,"
                "published_documents,code_revision,"
                "text_extractor_version,document_processor_version "
                "FROM brain_fileos_run_receipts WHERE source_id=%s "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            self.store.audit(conn, ctx, "brain.fileos_freshness_read", "brain_source", source_id)
        return {
            "source_id": source_id,
            "status": "complete" if row else "no_completed_run",
            "latest_complete_run": row,
            "partial_runs_included": False,
        }

    def current_coverage(
        self,
        ctx: TenantContext,
        *,
        after: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Summarize bounded current-search coverage for registered sources."""
        self.store.require(ctx, "brain.changes.read")
        if after is not None and not _IDENTITY.fullmatch(after):
            raise NotFound()
        if not 1 <= limit <= 50:
            raise ValueError("invalid coverage limit")
        with self.store.transaction(ctx) as conn:
            generated = conn.execute("SELECT clock_timestamp() AS generated_at").fetchone()
            assert generated is not None
            if (
                after is not None
                and not conn.execute("SELECT 1 FROM brain_sources WHERE id=%s", (after,)).fetchone()
            ):
                raise NotFound()
            rows = conn.execute(
                "WITH current_parents AS ("
                "SELECT eb.tenant_id,eb.source_id,eb.evidence_id,eb.created_at "
                "FROM brain_email_bridge_receipts eb JOIN message_versions mv ON "
                "mv.tenant_id=eb.tenant_id AND mv.account_id=eb.account_id "
                "AND mv.id=eb.legacy_version_id JOIN messages m ON "
                "m.tenant_id=mv.tenant_id AND m.account_id=mv.account_id "
                "AND m.id=mv.message_id AND m.raw_sha256=mv.raw_sha256 "
                "AND m.parser_version=mv.parser_version JOIN brain_source_items pi ON "
                "pi.tenant_id=eb.tenant_id AND pi.id=eb.item_id "
                "AND pi.current_version_id=eb.version_id "
                "WHERE NOT m.deleted AND NOT m.quarantined), current_attachments AS ("
                "SELECT ab.tenant_id,ab.source_id,ab.legacy_attachment_id,ab.item_id,"
                "ab.version_id,ab.evidence_id,ab.created_at FROM current_parents p "
                "JOIN brain_email_attachment_bridge_receipts ab ON "
                "ab.tenant_id=p.tenant_id AND ab.parent_evidence_id=p.evidence_id "
                "JOIN brain_source_items ai ON ai.tenant_id=ab.tenant_id "
                "AND ai.id=ab.item_id AND ai.current_version_id=ab.version_id), "
                "current_documents AS (SELECT db.tenant_id,db.source_id,db.created_at "
                "FROM current_attachments a JOIN brain_email_document_bridge_receipts db ON "
                "db.tenant_id=a.tenant_id "
                "AND db.legacy_attachment_id=a.legacy_attachment_id "
                "AND db.source_id=a.source_id AND db.item_id=a.item_id "
                "AND db.version_id=a.version_id AND db.evidence_id=a.evidence_id), "
                "selected AS (SELECT id,kind,status,created_at FROM brain_sources "
                "WHERE (%s::text IS NULL OR id>%s) ORDER BY id LIMIT %s) "
                "SELECT s.id AS source_id,s.kind,s.status AS configured_status,"
                "s.created_at AS registered_at,a.generation_id,a.activated_at,"
                "g.run_actor_id,g.run_id,g.observed_at AS generation_observed_at,"
                "g.item_count,g.document_count,g.chunk_count,lr.actor_id AS latest_run_actor_id,"
                "lr.run_id AS latest_run_id,lr.observed_at AS latest_run_observed_at,"
                "lr.completed_at AS latest_run_completed_at,"
                "COALESCE((SELECT count(*) FROM current_parents p "
                "WHERE p.source_id=s.id),0)::integer AS email_message_count,"
                "(SELECT max(p.created_at) FROM current_parents p "
                "WHERE p.source_id=s.id) AS latest_message_bridge_at,"
                "COALESCE((SELECT count(*) FROM current_attachments ea "
                "WHERE ea.source_id=s.id),0)::integer AS email_attachment_count,"
                "(SELECT max(ea.created_at) FROM current_attachments ea "
                "WHERE ea.source_id=s.id) AS latest_attachment_bridge_at,"
                "COALESCE((SELECT count(*) FROM current_documents ed "
                "WHERE ed.source_id=s.id),0)::integer AS email_document_count,"
                "(SELECT max(ed.created_at) FROM current_documents ed "
                "WHERE ed.source_id=s.id) AS latest_document_bridge_at "
                "FROM selected s LEFT JOIN LATERAL (SELECT generation_id,activated_at "
                "FROM brain_index_activations WHERE source_id=s.id "
                "ORDER BY activated_at DESC,idempotency_key DESC LIMIT 1) a "
                "ON s.kind='fileos' LEFT JOIN brain_index_generations g "
                "ON g.id=a.generation_id AND g.source_id=s.id LEFT JOIN LATERAL ("
                "SELECT actor_id,run_id,observed_at,completed_at "
                "FROM brain_fileos_run_receipts WHERE source_id=s.id "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1) lr "
                "ON s.kind='fileos' ORDER BY s.id",
                (after, after, limit + 1),
            ).fetchall()
            self.store.audit(conn, ctx, "brain.current_coverage_read", "brain_source", "registered")
        page = rows[:limit]
        results: list[dict[str, Any]] = []
        for row in page:
            common = {
                "source_id": row["source_id"],
                "kind": row["kind"],
                "configured_status": row["configured_status"],
                "registered_at": row["registered_at"],
            }
            if row["kind"] == "fileos":
                generation = None
                if row["generation_id"] is not None:
                    generation = {
                        "generation_id": row["generation_id"],
                        "activated_at": row["activated_at"],
                        "observed_at": row["generation_observed_at"],
                        "item_count": row["item_count"],
                        "document_count": row["document_count"],
                        "chunk_count": row["chunk_count"],
                    }
                latest_run = None
                if row["latest_run_id"] is not None:
                    latest_run = {
                        "run_id": row["latest_run_id"],
                        "observed_at": row["latest_run_observed_at"],
                        "completed_at": row["latest_run_completed_at"],
                    }
                results.append(
                    {
                        **common,
                        "coverage": "active_generation_only",
                        "status": ("search_ready" if generation else "no_active_generation"),
                        "active_generation": generation,
                        "latest_complete_run": latest_run,
                        "latest_completion_is_active": bool(
                            generation
                            and row["latest_run_id"] == row["run_id"]
                            and row["latest_run_actor_id"] == row["run_actor_id"]
                        ),
                    }
                )
            else:
                counts = {
                    "messages": row["email_message_count"],
                    "attachments": row["email_attachment_count"],
                    "documents": row["email_document_count"],
                }
                results.append(
                    {
                        **common,
                        "coverage": "explicit_bridges_only",
                        "status": (
                            "current_evidence_available"
                            if any(counts.values())
                            else "no_current_bridged_evidence"
                        ),
                        "current_counts": counts,
                        "latest_current_bridge_at": {
                            "messages": row["latest_message_bridge_at"],
                            "attachments": row["latest_attachment_bridge_at"],
                            "documents": row["latest_document_bridge_at"],
                        },
                    }
                )
        return {
            "generated_at": generated["generated_at"],
            "complete": False,
            "semantics": "registered_sources_and_explicit_bridges_only",
            "results": results,
            "next_cursor": page[-1]["source_id"] if len(rows) > limit and page else None,
            "limit": limit,
        }

    def fileos_inventory(self, ctx: TenantContext, source_id: str) -> dict[str, Any]:
        """Summarize membership and newly observed absence for the latest complete run."""
        self.store.require(ctx, "brain.changes.read")
        if not _IDENTITY.fullmatch(source_id):
            raise NotFound()
        with self.store.transaction(ctx) as conn:
            source = conn.execute(
                "SELECT 1 FROM brain_sources WHERE id=%s AND kind='fileos'", (source_id,)
            ).fetchone()
            if not source:
                raise NotFound()
            latest = conn.execute(
                "SELECT actor_id,run_id,observed_at,completed_at,item_count "
                "FROM brain_fileos_run_receipts WHERE source_id=%s "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            if latest:
                absence = conn.execute(
                    "SELECT count(*) AS n FROM brain_fileos_absence_events "
                    "WHERE source_id=%s AND observed_actor_id=%s AND observed_run_id=%s",
                    (source_id, latest["actor_id"], latest["run_id"]),
                ).fetchone()
                assert absence is not None
                result = {
                    "source_id": source_id,
                    "status": "complete",
                    "run_id": latest["run_id"],
                    "observed_at": latest["observed_at"],
                    "completed_at": latest["completed_at"],
                    "present_items": latest["item_count"],
                    "newly_absent_items": absence["n"],
                    "absent_evidence_retained": True,
                    "search_visibility_changed": False,
                }
            else:
                result = {
                    "source_id": source_id,
                    "status": "no_completed_run",
                    "run_id": None,
                    "observed_at": None,
                    "completed_at": None,
                    "present_items": None,
                    "newly_absent_items": None,
                    "absent_evidence_retained": True,
                    "search_visibility_changed": False,
                }
            self.store.audit(conn, ctx, "brain.fileos_inventory_read", "brain_source", source_id)
            return result

    def fileos_rebuild_preview(
        self,
        ctx: TenantContext,
        source_id: str,
        *,
        after: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Verify a bounded page of current deterministic index artifacts without writes."""
        self.store.require(ctx, "brain.changes.read")
        if (
            not _IDENTITY.fullmatch(source_id)
            or (after is not None and not _IDENTITY.fullmatch(after))
            or not 1 <= limit <= 50
        ):
            raise ValueError("invalid FileOS rebuild preview request")
        with self.store.transaction(ctx) as conn:
            source = conn.execute(
                "SELECT 1 FROM brain_sources WHERE id=%s AND kind='fileos'", (source_id,)
            ).fetchone()
            if not source:
                raise NotFound()
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:fileos-source:{source_id}",),
            )
            latest = conn.execute(
                "SELECT actor_id,run_id,observed_at,item_count "
                "FROM brain_fileos_run_receipts WHERE source_id=%s "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            if not latest:
                self.store.audit(
                    conn, ctx, "brain.fileos_rebuild_preview", "brain_source", source_id
                )
                return {
                    "source_id": source_id,
                    "status": "no_completed_run",
                    "run_id": None,
                    "observed_at": None,
                    "total_items": None,
                    "results": [],
                    "next_cursor": None,
                    "source_effects": False,
                    "data_effects": False,
                }
            if (
                after is not None
                and not conn.execute(
                    "SELECT 1 FROM brain_fileos_run_items "
                    "WHERE actor_id=%s AND run_id=%s AND item_id=%s",
                    (latest["actor_id"], latest["run_id"], after),
                ).fetchone()
            ):
                raise NotFound()
            rows = conn.execute(
                "SELECT ri.item_id,ri.version_id,ri.outcome,e.id AS evidence_id,"
                "d.id AS document_id,d.normalizer,d.body_sha256,d.body "
                "FROM brain_fileos_run_items ri "
                "JOIN brain_evidence e ON e.tenant_id=ri.tenant_id "
                "AND e.source_version_id=ri.version_id "
                "LEFT JOIN LATERAL (SELECT nd.id,nd.normalizer,nd.body_sha256,nd.body "
                "FROM brain_normalized_documents nd WHERE nd.tenant_id=ri.tenant_id "
                "AND nd.evidence_id=e.id ORDER BY nd.created_at DESC,nd.id DESC LIMIT 1) d "
                "ON true WHERE ri.actor_id=%s AND ri.run_id=%s AND ri.item_id>%s "
                "ORDER BY ri.item_id LIMIT %s",
                (latest["actor_id"], latest["run_id"], after or "", limit + 1),
            ).fetchall()
            has_more = len(rows) > limit
            page = rows[:limit]
            document_ids = [row["document_id"] for row in page if row["document_id"]]
            chunk_rows = (
                conn.execute(
                    "SELECT document_id,id,ordinal,start_offset,end_offset,text,sha256 "
                    "FROM brain_chunks WHERE document_id=ANY(%s) "
                    "ORDER BY document_id,ordinal",
                    (document_ids,),
                ).fetchall()
                if document_ids
                else []
            )
            chunks_by_document: dict[str, list[dict[str, Any]]] = {}
            for chunk in chunk_rows:
                chunks_by_document.setdefault(chunk["document_id"], []).append(chunk)
            results: list[dict[str, Any]] = []
            for row in page:
                document_id = row["document_id"]
                if document_id is None:
                    disposition = "source_reprocess_required"
                    expected_chunks = None
                    stored_chunks = 0
                else:
                    body = row["body"]
                    body_sha = hashlib.sha256(body.encode()).hexdigest()
                    expected_document_id = stable_id(
                        "document", row["version_id"], row["normalizer"], body_sha
                    )
                    expected = [
                        {
                            "document_id": document_id,
                            "id": stable_id(
                                "chunk",
                                document_id,
                                str(ordinal),
                                hashlib.sha256(text.encode()).hexdigest(),
                            ),
                            "ordinal": ordinal,
                            "start_offset": start,
                            "end_offset": end,
                            "text": text,
                            "sha256": hashlib.sha256(text.encode()).hexdigest(),
                        }
                        for ordinal, (start, end, text) in enumerate(deterministic_chunks(body))
                    ]
                    stored = chunks_by_document.get(document_id, [])
                    valid = (
                        row["body_sha256"] == body_sha
                        and document_id == expected_document_id
                        and stored == expected
                    )
                    disposition = "verified" if valid else "rebuild_required"
                    expected_chunks = len(expected)
                    stored_chunks = len(stored)
                results.append(
                    {
                        "item_id": row["item_id"],
                        "version_id": row["version_id"],
                        "evidence_id": row["evidence_id"],
                        "document_id": document_id,
                        "source_outcome": row["outcome"],
                        "disposition": disposition,
                        "expected_chunks": expected_chunks,
                        "stored_chunks": stored_chunks,
                    }
                )
            self.store.audit(conn, ctx, "brain.fileos_rebuild_preview", "brain_source", source_id)
            return {
                "source_id": source_id,
                "status": "complete",
                "run_id": latest["run_id"],
                "observed_at": latest["observed_at"],
                "total_items": latest["item_count"],
                "results": results,
                "next_cursor": page[-1]["item_id"] if has_more else None,
                "source_effects": False,
                "data_effects": False,
            }

    def build_fileos_index_generation(
        self,
        ctx: TenantContext,
        source_id: str,
        expected_run_id: UUID,
        *,
        code_revision: str,
    ) -> IndexGeneration:
        """Build one immutable lexical generation from normalized evidence."""
        self.store.require(ctx, "brain.document.publish")
        if (
            not _IDENTITY.fullmatch(source_id)
            or not isinstance(expected_run_id, UUID)
            or not code_revision
            or len(code_revision) > 200
            or "\x00" in code_revision
        ):
            raise ValueError("invalid index generation request")
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:fileos-source:{source_id}",),
            )
            run = conn.execute(
                "SELECT actor_id,run_id,observed_at,item_count "
                "FROM brain_fileos_run_receipts WHERE source_id=%s "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            if not run:
                raise NotFound()
            if run["run_id"] != expected_run_id:
                raise Conflict("index generation is not bound to the latest complete run")
            rows = conn.execute(
                "SELECT ri.item_id,ri.version_id,ri.outcome,e.id AS evidence_id,"
                "d.id AS document_id,d.normalizer,d.body_sha256,d.body "
                "FROM brain_fileos_run_items ri JOIN brain_evidence e "
                "ON e.tenant_id=ri.tenant_id AND e.source_version_id=ri.version_id "
                "LEFT JOIN LATERAL (SELECT nd.id,nd.normalizer,nd.body_sha256,nd.body "
                "FROM brain_normalized_documents nd WHERE nd.tenant_id=ri.tenant_id "
                "AND nd.evidence_id=e.id ORDER BY nd.created_at DESC,nd.id DESC LIMIT 1) d "
                "ON true WHERE ri.actor_id=%s AND ri.run_id=%s ORDER BY ri.item_id",
                (run["actor_id"], expected_run_id),
            ).fetchall()
            if len(rows) != run["item_count"]:
                raise Conflict("completed inventory ledger is incomplete")
            plan_items: list[dict[str, Any]] = []
            generated_chunks: list[dict[str, Any]] = []
            total_text_bytes = 0
            document_count = 0
            for row in rows:
                if row["evidence_id"] != stable_id("evidence", row["version_id"]):
                    raise Conflict("evidence identity changed")
                document_id = row["document_id"]
                disposition = "not_indexed"
                body_sha: str | None = None
                if document_id is not None:
                    body = row["body"]
                    encoded = body.encode()
                    total_text_bytes += len(encoded)
                    if total_text_bytes > MAX_GENERATION_TEXT_BYTES:
                        raise ValueError("index generation text bound exceeded")
                    body_sha = hashlib.sha256(encoded).hexdigest()
                    if row["body_sha256"] != body_sha or document_id != stable_id(
                        "document", row["version_id"], row["normalizer"], body_sha
                    ):
                        raise Conflict("normalized document identity changed")
                    disposition = "indexed"
                    document_count += 1
                    for ordinal, (start, end, text) in enumerate(deterministic_chunks(body)):
                        chunk_sha = hashlib.sha256(text.encode()).hexdigest()
                        generated_chunks.append(
                            {
                                "document_id": document_id,
                                "id": stable_id("chunk", document_id, str(ordinal), chunk_sha),
                                "ordinal": ordinal,
                                "start_offset": start,
                                "end_offset": end,
                                "text": text,
                                "sha256": chunk_sha,
                            }
                        )
                        if len(generated_chunks) > MAX_GENERATION_CHUNKS:
                            raise ValueError("index generation chunk bound exceeded")
                elif row["outcome"] == "extracted":
                    raise Conflict("completed extraction is missing its document")
                plan_items.append(
                    {
                        "item_id": row["item_id"],
                        "version_id": row["version_id"],
                        "outcome": row["outcome"],
                        "evidence_id": row["evidence_id"],
                        "document_id": document_id,
                        "body_sha256": body_sha,
                        "disposition": disposition,
                    }
                )
            plan_sha = _canonical_digest(
                {
                    "source_id": source_id,
                    "run_actor_id": str(run["actor_id"]),
                    "run_id": str(expected_run_id),
                    "observed_at": run["observed_at"].isoformat(),
                    "code_revision": code_revision,
                    "chunker_version": INDEX_CHUNKER_VERSION,
                    "items": plan_items,
                }
            )
            generation_id = stable_id(
                "index_generation",
                source_id,
                str(expected_run_id),
                INDEX_CHUNKER_VERSION,
                plan_sha,
            )
            existing = conn.execute(
                "SELECT g.run_id,g.item_count,g.document_count,g.chunk_count,g.plan_sha256,"
                "r.ready_at FROM brain_index_generations g "
                "LEFT JOIN brain_index_generation_receipts r ON r.generation_id=g.id "
                "WHERE g.id=%s",
                (generation_id,),
            ).fetchone()
            expected = {
                "run_id": expected_run_id,
                "item_count": len(rows),
                "document_count": document_count,
                "chunk_count": len(generated_chunks),
                "plan_sha256": plan_sha,
            }
            if existing:
                ready_at = existing.pop("ready_at")
                if ready_at is None or existing != expected:
                    raise Conflict("index generation identity changed")
                return IndexGeneration(
                    generation_id,
                    source_id,
                    expected_run_id,
                    len(rows),
                    document_count,
                    len(generated_chunks),
                    plan_sha,
                    ready_at,
                    False,
                )
            conn.execute(
                "INSERT INTO brain_index_generations(tenant_id,id,source_id,run_actor_id,"
                "run_id,observed_at,plan_sha256,code_revision,chunker_version,item_count,"
                "document_count,chunk_count) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id,
                    generation_id,
                    source_id,
                    run["actor_id"],
                    expected_run_id,
                    run["observed_at"],
                    plan_sha,
                    code_revision,
                    INDEX_CHUNKER_VERSION,
                    len(rows),
                    document_count,
                    len(generated_chunks),
                ),
            )
            for item in plan_items:
                conn.execute(
                    "INSERT INTO brain_index_generation_items(tenant_id,generation_id,"
                    "source_id,item_id,version_id,outcome,disposition,evidence_id,document_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        generation_id,
                        source_id,
                        item["item_id"],
                        item["version_id"],
                        item["outcome"],
                        item["disposition"],
                        item["evidence_id"],
                        item["document_id"],
                    ),
                )
            for chunk in generated_chunks:
                conn.execute(
                    "INSERT INTO brain_index_generation_chunks(tenant_id,generation_id,"
                    "source_id,document_id,id,ordinal,start_offset,end_offset,text,sha256) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        generation_id,
                        source_id,
                        chunk["document_id"],
                        chunk["id"],
                        chunk["ordinal"],
                        chunk["start_offset"],
                        chunk["end_offset"],
                        chunk["text"],
                        chunk["sha256"],
                    ),
                )
            receipt = conn.execute(
                "INSERT INTO brain_index_generation_receipts(tenant_id,generation_id,source_id) "
                "VALUES (%s,%s,%s) RETURNING ready_at",
                (ctx.tenant_id, generation_id, source_id),
            ).fetchone()
            assert receipt is not None
            return IndexGeneration(
                generation_id,
                source_id,
                expected_run_id,
                len(rows),
                document_count,
                len(generated_chunks),
                plan_sha,
                receipt["ready_at"],
                True,
            )

    def activate_fileos_index_generation(
        self,
        ctx: TenantContext,
        source_id: str,
        generation_id: str,
        idempotency_key: UUID,
    ) -> IndexActivation:
        """Append an activation receipt; reactivating an older generation is rollback."""
        self.store.require(ctx, "brain.index.activate")
        if (
            not _IDENTITY.fullmatch(source_id)
            or not _IDENTITY.fullmatch(generation_id)
            or not isinstance(idempotency_key, UUID)
        ):
            raise ValueError("invalid index activation request")
        request_hash = _canonical_digest({"source_id": source_id, "generation_id": generation_id})
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:fileos-source:{source_id}",),
            )
            existing = conn.execute(
                "SELECT source_id,generation_id,previous_generation_id,request_hash,"
                "activated_at FROM brain_index_activations "
                "WHERE actor_id=%s AND idempotency_key=%s",
                (ctx.actor_id, idempotency_key),
            ).fetchone()
            if existing:
                if (
                    existing["request_hash"] != request_hash
                    or existing["source_id"] != source_id
                    or existing["generation_id"] != generation_id
                ):
                    raise Conflict("index activation key reused")
                return IndexActivation(
                    source_id,
                    generation_id,
                    existing["previous_generation_id"],
                    existing["activated_at"],
                    False,
                )
            ready = conn.execute(
                "SELECT 1 FROM brain_index_generation_receipts "
                "WHERE generation_id=%s AND source_id=%s",
                (generation_id, source_id),
            ).fetchone()
            if not ready:
                raise NotFound()
            previous = conn.execute(
                "SELECT generation_id FROM brain_index_activations WHERE source_id=%s "
                "ORDER BY activated_at DESC,idempotency_key DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            previous_id = previous["generation_id"] if previous else None
            row = conn.execute(
                "INSERT INTO brain_index_activations(tenant_id,actor_id,idempotency_key,"
                "source_id,generation_id,previous_generation_id,request_hash) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING activated_at",
                (
                    ctx.tenant_id,
                    ctx.actor_id,
                    idempotency_key,
                    source_id,
                    generation_id,
                    previous_id,
                    request_hash,
                ),
            ).fetchone()
            assert row is not None
            return IndexActivation(source_id, generation_id, previous_id, row["activated_at"], True)

    def fileos_index_status(self, ctx: TenantContext, source_id: str) -> dict[str, Any]:
        """Return the active immutable index generation without exposing content."""
        self.store.require(ctx, "brain.changes.read")
        if not _IDENTITY.fullmatch(source_id):
            raise NotFound()
        with self.store.transaction(ctx) as conn:
            if not conn.execute(
                "SELECT 1 FROM brain_sources WHERE id=%s AND kind='fileos'", (source_id,)
            ).fetchone():
                raise NotFound()
            row = conn.execute(
                "SELECT a.generation_id,a.previous_generation_id,a.activated_at,g.run_id,"
                "g.observed_at,g.item_count,g.document_count,g.chunk_count,g.plan_sha256,"
                "g.chunker_version FROM brain_index_activations a "
                "JOIN brain_index_generations g ON g.id=a.generation_id "
                "WHERE a.source_id=%s ORDER BY a.activated_at DESC,a.idempotency_key DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            self.store.audit(conn, ctx, "brain.fileos_index_status", "brain_source", source_id)
            return {
                "source_id": source_id,
                "status": "active" if row else "no_active_generation",
                "active_generation": row,
            }

    def search_fileos_active(
        self, ctx: TenantContext, source_id: str, query: str, *, limit: int = 10
    ) -> list[SearchHit]:
        """Search only the source's append-only active index generation."""
        self.store.require(ctx, "brain.search")
        if (
            not _IDENTITY.fullmatch(source_id)
            or not query.strip()
            or len(query) > 500
            or "\x00" in query
            or not 1 <= limit <= 50
        ):
            raise ValueError("invalid active FileOS search")
        with self.store.transaction(ctx) as conn:
            active = conn.execute(
                "SELECT generation_id FROM brain_index_activations WHERE source_id=%s "
                "ORDER BY activated_at DESC,idempotency_key DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            if not active:
                raise NotFound()
            rows = conn.execute(
                "SELECT c.id AS chunk_id,c.document_id,i.evidence_id,i.source_id,si.locator,"
                "ts_headline('simple',c.text,plainto_tsquery('simple',%s),"
                "'MaxWords=35,MinWords=10') AS excerpt,"
                "ts_rank_cd(c.search_vector,plainto_tsquery('simple',%s)) AS rank "
                "FROM brain_index_generation_chunks c "
                "JOIN brain_index_generation_items i ON i.tenant_id=c.tenant_id "
                "AND i.generation_id=c.generation_id AND i.document_id=c.document_id "
                "JOIN brain_source_items si ON si.tenant_id=i.tenant_id "
                "AND si.source_id=i.source_id AND si.id=i.item_id "
                "WHERE c.generation_id=%s "
                "AND c.search_vector @@ plainto_tsquery('simple',%s) "
                "ORDER BY rank DESC,c.id LIMIT %s",
                (query, query, active["generation_id"], query, limit),
            ).fetchall()
            self.store.audit(conn, ctx, "brain.fileos_active_search", "brain_source", source_id)
            return [SearchHit(**row) for row in rows]

    def search_current_fileos(
        self, ctx: TenantContext, query: str, *, limit: int = 10
    ) -> list[SearchHit]:
        """Search the newest activated generation of every authorized FileOS source."""
        self.store.require(ctx, "brain.search")
        if not query.strip() or len(query) > 500 or "\x00" in query or not 1 <= limit <= 50:
            raise ValueError("invalid current FileOS search")
        with self.store.transaction(ctx) as conn:
            rows = conn.execute(
                "WITH active AS (SELECT DISTINCT ON (source_id) source_id,generation_id "
                "FROM brain_index_activations ORDER BY source_id,activated_at DESC,"
                "idempotency_key DESC) "
                "SELECT c.id AS chunk_id,c.document_id,i.evidence_id,i.source_id,si.locator,"
                "ts_headline('simple',c.text,plainto_tsquery('simple',%s),"
                "'MaxWords=35,MinWords=10') AS excerpt,"
                "ts_rank_cd(c.search_vector,plainto_tsquery('simple',%s)) AS rank "
                "FROM active a JOIN brain_index_generation_chunks c "
                "ON c.source_id=a.source_id AND c.generation_id=a.generation_id "
                "JOIN brain_index_generation_items i ON i.tenant_id=c.tenant_id "
                "AND i.generation_id=c.generation_id AND i.document_id=c.document_id "
                "JOIN brain_source_items si ON si.tenant_id=i.tenant_id "
                "AND si.source_id=i.source_id AND si.id=i.item_id "
                "WHERE c.search_vector @@ plainto_tsquery('simple',%s) "
                "ORDER BY rank DESC,c.id LIMIT %s",
                (query, query, query, limit),
            ).fetchall()
            self.store.audit(
                conn, ctx, "brain.current_fileos_search", "brain_index", "fileos_active"
            )
            return [SearchHit(**row) for row in rows]

    def search_current_email(
        self, ctx: TenantContext, query: str, *, limit: int = 10
    ) -> list[SearchHit]:
        """Search explicitly bridged Email evidence still current in both layers."""
        self.store.require(ctx, "brain.search")
        if not query.strip() or len(query) > 500 or "\x00" in query or not 1 <= limit <= 50:
            raise ValueError("invalid current Email search")
        with self.store.transaction(ctx) as conn:
            rows = conn.execute(
                "SELECT c.id AS chunk_id,c.document_id,e.id AS evidence_id,v.source_id,"
                "i.locator,ts_headline('simple',c.text,plainto_tsquery('simple',%s),"
                "'MaxWords=35,MinWords=10') AS excerpt,"
                "ts_rank_cd(c.search_vector,plainto_tsquery('simple',%s)) AS rank "
                "FROM brain_chunks c JOIN brain_normalized_documents d "
                "ON d.tenant_id=c.tenant_id AND d.id=c.document_id "
                "JOIN brain_evidence e ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id "
                "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
                "AND v.id=e.source_version_id JOIN brain_source_items i "
                "ON i.tenant_id=v.tenant_id AND i.id=v.item_id "
                "AND i.current_version_id=v.id JOIN brain_sources s "
                "ON s.tenant_id=v.tenant_id AND s.id=v.source_id AND s.kind='email' "
                "JOIN brain_email_bridge_receipts b ON b.tenant_id=v.tenant_id "
                "AND b.version_id=v.id AND b.evidence_id=e.id AND b.document_id=d.id "
                "JOIN message_versions mv ON mv.tenant_id=b.tenant_id "
                "AND mv.account_id=b.account_id AND mv.id=b.legacy_version_id "
                "JOIN messages m ON m.tenant_id=mv.tenant_id AND m.account_id=mv.account_id "
                "AND m.id=mv.message_id AND m.raw_sha256=mv.raw_sha256 "
                "AND m.parser_version=mv.parser_version "
                "WHERE NOT m.deleted AND NOT m.quarantined "
                "AND c.search_vector @@ plainto_tsquery('simple',%s) "
                "ORDER BY rank DESC,c.id LIMIT %s",
                (query, query, query, limit),
            ).fetchall()
            self.store.audit(
                conn, ctx, "brain.current_email_search", "brain_index", "email_bridged"
            )
            return [SearchHit(**row) for row in rows]

    def search_current_email_family(
        self,
        ctx: TenantContext,
        query: str,
        *,
        message_limit: int = 10,
        attachment_limit: int = 10,
        document_limit: int = 10,
    ) -> EmailFamilySearch:
        """Search current bridged Email representations with independent ranks."""
        self.store.require(ctx, "brain.search")
        limits = (message_limit, attachment_limit, document_limit)
        if (
            not query.strip()
            or len(query) > 500
            or "\x00" in query
            or any(not 1 <= limit <= 25 for limit in limits)
        ):
            raise ValueError("invalid current Email family search")
        with self.store.transaction(ctx) as conn:
            rows = conn.execute(
                "WITH current_parents AS ("
                "SELECT eb.tenant_id,eb.account_id,eb.legacy_version_id,eb.source_id,"
                "eb.item_id,eb.version_id,eb.evidence_id,eb.document_id,pi.locator "
                "FROM brain_email_bridge_receipts eb JOIN message_versions mv ON "
                "mv.tenant_id=eb.tenant_id AND mv.account_id=eb.account_id "
                "AND mv.id=eb.legacy_version_id JOIN messages m ON "
                "m.tenant_id=mv.tenant_id AND m.account_id=mv.account_id "
                "AND m.id=mv.message_id AND m.raw_sha256=mv.raw_sha256 "
                "AND m.parser_version=mv.parser_version JOIN brain_source_items pi ON "
                "pi.tenant_id=eb.tenant_id AND pi.id=eb.item_id "
                "AND pi.current_version_id=eb.version_id "
                "WHERE NOT m.deleted AND NOT m.quarantined), family AS ("
                "SELECT 'message'::text AS result_kind,c.id AS chunk_id,c.document_id,"
                "p.evidence_id,p.source_id,p.locator,c.text,c.search_vector "
                "FROM current_parents p JOIN brain_normalized_documents d ON "
                "d.tenant_id=p.tenant_id AND d.id=p.document_id "
                "JOIN brain_chunks c ON c.tenant_id=d.tenant_id AND c.document_id=d.id "
                "UNION ALL SELECT 'attachment',c.id,c.document_id,ab.evidence_id,"
                "ab.source_id,ai.locator,c.text,c.search_vector FROM current_parents p "
                "JOIN brain_email_attachment_bridge_receipts ab ON "
                "ab.tenant_id=p.tenant_id AND ab.parent_evidence_id=p.evidence_id "
                "JOIN brain_source_items ai ON ai.tenant_id=ab.tenant_id "
                "AND ai.id=ab.item_id AND ai.current_version_id=ab.version_id "
                "JOIN brain_normalized_documents d ON d.tenant_id=ab.tenant_id "
                "AND d.id=ab.document_id JOIN brain_chunks c ON c.tenant_id=d.tenant_id "
                "AND c.document_id=d.id UNION ALL SELECT 'document',c.id,c.document_id,"
                "db.evidence_id,db.source_id,ai.locator,c.text,c.search_vector "
                "FROM current_parents p JOIN brain_email_attachment_bridge_receipts ab "
                "ON ab.tenant_id=p.tenant_id AND ab.parent_evidence_id=p.evidence_id "
                "JOIN brain_email_document_bridge_receipts db ON db.tenant_id=ab.tenant_id "
                "AND db.legacy_attachment_id=ab.legacy_attachment_id "
                "AND db.source_id=ab.source_id AND db.item_id=ab.item_id "
                "AND db.version_id=ab.version_id AND db.evidence_id=ab.evidence_id "
                "JOIN brain_source_items ai ON ai.tenant_id=db.tenant_id "
                "AND ai.id=db.item_id AND ai.current_version_id=db.version_id "
                "JOIN brain_normalized_documents d ON d.tenant_id=db.tenant_id "
                "AND d.id=db.document_id JOIN brain_chunks c ON c.tenant_id=d.tenant_id "
                "AND c.document_id=d.id), matches AS (SELECT result_kind,chunk_id,"
                "document_id,evidence_id,source_id,locator,"
                "ts_headline('simple',text,plainto_tsquery('simple',%s),"
                "'MaxWords=35,MinWords=10') AS excerpt,"
                "ts_rank_cd(search_vector,plainto_tsquery('simple',%s)) AS rank "
                "FROM family WHERE search_vector @@ plainto_tsquery('simple',%s)), "
                "ranked AS (SELECT *,row_number() OVER (PARTITION BY result_kind "
                "ORDER BY rank DESC,chunk_id) AS result_ordinal FROM matches) "
                "SELECT result_kind,chunk_id,document_id,evidence_id,source_id,locator,"
                "excerpt,rank FROM ranked WHERE "
                "(result_kind='message' AND result_ordinal<=%s) OR "
                "(result_kind='attachment' AND result_ordinal<=%s) OR "
                "(result_kind='document' AND result_ordinal<=%s) "
                "ORDER BY CASE result_kind WHEN 'message' THEN 1 WHEN 'attachment' THEN 2 "
                "ELSE 3 END,rank DESC,chunk_id",
                (query, query, query, message_limit, attachment_limit, document_limit),
            ).fetchall()
            self.store.audit(
                conn, ctx, "brain.current_email_family_search", "brain_index", "email_family"
            )
        buckets: dict[str, list[SearchHit]] = {
            "message": [],
            "attachment": [],
            "document": [],
        }
        for row in rows:
            kind = row.pop("result_kind")
            buckets[kind].append(SearchHit(**row))
        return EmailFamilySearch(
            tuple(buckets["message"]),
            tuple(buckets["attachment"]),
            tuple(buckets["document"]),
        )

    def publish_text(
        self,
        ctx: TenantContext,
        source_version_id: str,
        text: str,
        *,
        code_revision: str,
        normalizer: str = NORMALIZER_VERSION,
    ) -> PublishedDocument:
        self.store.require(ctx, "brain.document.publish")
        if not text or "\x00" in text or len(text.encode()) > MAX_NORMALIZED_BYTES:
            raise ValueError("normalized text is empty or exceeds its safe bound")
        for descriptor in (normalizer, code_revision):
            if not descriptor or len(descriptor) > 200 or "\x00" in descriptor:
                raise ValueError("invalid publication descriptor")
        body_sha = hashlib.sha256(text.encode()).hexdigest()
        document_id = stable_id("document", source_version_id, normalizer, body_sha)
        evidence_id = stable_id("evidence", source_version_id)
        with self.store.transaction(ctx) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:publish:{document_id}",),
            )
            version = conn.execute(
                "SELECT source_id,item_id FROM brain_source_versions WHERE id=%s",
                (source_version_id,),
            ).fetchone()
            if not version:
                raise NotFound()
            existing = conn.execute(
                "SELECT id FROM brain_normalized_documents WHERE id=%s", (document_id,)
            ).fetchone()
            if existing:
                count = conn.execute(
                    "SELECT count(*) AS n FROM brain_chunks WHERE document_id=%s", (document_id,)
                ).fetchone()
                assert count is not None
                return PublishedDocument(document_id, evidence_id, count["n"], False)
            conn.execute(
                "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
                "body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
                (ctx.tenant_id, document_id, evidence_id, normalizer, body_sha, text),
            )
            chunks = list(deterministic_chunks(text))
            for ordinal, (start, end, chunk) in enumerate(chunks):
                chunk_sha = hashlib.sha256(chunk.encode()).hexdigest()
                chunk_id = stable_id("chunk", document_id, str(ordinal), chunk_sha)
                conn.execute(
                    "INSERT INTO brain_chunks(tenant_id,id,document_id,ordinal,start_offset,"
                    "end_offset,"
                    "text,sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, chunk_id, document_id, ordinal, start, end, chunk, chunk_sha),
                )
            config_sha = _canonical_digest({"chunk_characters": CHUNK_CHARACTERS})
            provenance_id = stable_id("provenance", document_id, code_revision, config_sha)
            conn.execute(
                "INSERT INTO brain_provenance(tenant_id,id,output_id,transform,transform_version,"
                "code_revision,configuration_sha256,created_at) "
                "VALUES (%s,%s,%s,'normalize_text',%s,%s,%s,clock_timestamp())",
                (
                    ctx.tenant_id,
                    provenance_id,
                    document_id,
                    normalizer,
                    code_revision,
                    config_sha,
                ),
            )
            conn.execute(
                "INSERT INTO brain_provenance_inputs(tenant_id,provenance_id,input_id,ordinal) "
                "VALUES (%s,%s,%s,0)",
                (ctx.tenant_id, provenance_id, evidence_id),
            )
            change_id = stable_id("change", "document_published", document_id)
            conn.execute(
                "INSERT INTO brain_change_events(tenant_id,id,source_id,item_id,version_id,kind) "
                "VALUES (%s,%s,%s,%s,%s,'document_published')",
                (
                    ctx.tenant_id,
                    change_id,
                    version["source_id"],
                    version["item_id"],
                    source_version_id,
                ),
            )
            return PublishedDocument(document_id, evidence_id, len(chunks), True)

    def search(self, ctx: TenantContext, query: str, *, limit: int = 10) -> list[SearchHit]:
        self.store.require(ctx, "brain.search")
        if not query.strip() or len(query) > 500 or not 1 <= limit <= 50 or "\x00" in query:
            raise ValueError("invalid search request")
        with self.store.transaction(ctx) as conn:
            rows = conn.execute(
                "SELECT c.id AS chunk_id,c.document_id,d.evidence_id,v.source_id,i.locator,"
                "ts_headline('simple',c.text,plainto_tsquery('simple',%s),"
                "'MaxWords=35,MinWords=10') AS excerpt,"
                "ts_rank_cd(c.search_vector,plainto_tsquery('simple',%s)) AS rank "
                "FROM brain_chunks c JOIN brain_normalized_documents d ON "
                "d.tenant_id=c.tenant_id AND d.id=c.document_id "
                "JOIN brain_evidence e ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id "
                "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
                "AND v.id=e.source_version_id JOIN brain_source_items i ON "
                "i.tenant_id=v.tenant_id AND i.id=v.item_id "
                "WHERE c.search_vector @@ plainto_tsquery('simple',%s) "
                "ORDER BY rank DESC,c.id LIMIT %s",
                (query, query, query, limit),
            ).fetchall()
            self.store.audit(conn, ctx, "brain.search", "query")
        return [SearchHit(**row) for row in rows]

    def evidence(self, ctx: TenantContext, evidence_id: str) -> dict[str, Any]:
        self.store.require(ctx, "brain.evidence.read")
        if not _IDENTITY.fullmatch(evidence_id):
            raise NotFound()
        with self.store.transaction(ctx) as conn:
            row = conn.execute(
                "SELECT e.id,e.sha256,e.storage,e.retained,e.created_at,"
                "v.id AS source_version_id,v.observed_at,v.size_bytes,v.media_type,"
                "v.source_id,i.id AS source_item_id,i.locator,s.kind AS source_kind,"
                "d.id AS document_id,d.normalizer,d.created_at AS indexed_at,"
                "(SELECT count(*) FROM brain_chunks c WHERE c.tenant_id=e.tenant_id "
                "AND c.document_id=d.id) AS chunk_count "
                "FROM brain_evidence e JOIN brain_source_versions v ON "
                "v.tenant_id=e.tenant_id AND v.id=e.source_version_id "
                "JOIN brain_source_items i ON i.tenant_id=v.tenant_id AND i.id=v.item_id "
                "JOIN brain_sources s ON s.tenant_id=v.tenant_id AND s.id=v.source_id "
                "LEFT JOIN LATERAL (SELECT nd.id,nd.normalizer,nd.created_at "
                "FROM brain_normalized_documents nd WHERE nd.tenant_id=e.tenant_id "
                "AND nd.evidence_id=e.id ORDER BY nd.created_at DESC,nd.id DESC LIMIT 1) d "
                "ON true WHERE e.id=%s",
                (evidence_id,),
            ).fetchone()
            if not row:
                raise NotFound()
            self.store.audit(conn, ctx, "brain.evidence_read", "brain_evidence", evidence_id)
            return {**row, "original_content_available": False, "untrusted_content": True}

    def evidence_content(
        self, ctx: TenantContext, evidence_id: str, *, max_chars: int = 4000
    ) -> dict[str, Any]:
        self.store.require(ctx, "brain.content.read")
        if not _IDENTITY.fullmatch(evidence_id) or not 1 <= max_chars <= 16_000:
            raise ValueError("invalid evidence content request")
        with self.store.transaction(ctx) as conn:
            row = conn.execute(
                "SELECT d.id AS document_id,d.body,d.body_sha256,d.normalizer,d.created_at "
                "FROM brain_normalized_documents d WHERE d.evidence_id=%s "
                "ORDER BY d.created_at DESC,d.id DESC LIMIT 1",
                (evidence_id,),
            ).fetchone()
            if not row:
                raise NotFound()
            body = row.pop("body")
            self.store.audit(conn, ctx, "brain.content_read", "brain_evidence", evidence_id)
            return {
                **row,
                "evidence_id": evidence_id,
                "content": body[:max_chars],
                "truncated": len(body) > max_chars,
                "returned_chars": min(len(body), max_chars),
                "untrusted_content": True,
            }

    def changes(
        self,
        ctx: TenantContext,
        *,
        after: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        self.store.require(ctx, "brain.changes.read")
        if after is not None and not _IDENTITY.fullmatch(after):
            raise NotFound()
        if not 1 <= limit <= 50:
            raise ValueError("invalid change limit")
        with self.store.transaction(ctx) as conn:
            anchor = None
            if after is not None:
                anchor = conn.execute(
                    "SELECT recorded_at,id FROM brain_change_events WHERE id=%s", (after,)
                ).fetchone()
                if not anchor:
                    raise NotFound()
            rows = conn.execute(
                "SELECT id,source_id,item_id,version_id,kind,recorded_at "
                "FROM brain_change_events WHERE (%s::timestamptz IS NULL OR "
                "(recorded_at,id)>(%s,%s)) ORDER BY recorded_at,id LIMIT %s",
                (
                    anchor["recorded_at"] if anchor else None,
                    anchor["recorded_at"] if anchor else None,
                    after,
                    limit + 1,
                ),
            ).fetchall()
            self.store.audit(conn, ctx, "brain.changes_read", "change_feed")
        page = rows[:limit]
        return {
            "results": page,
            "next_cursor": page[-1]["id"] if len(rows) > limit and page else None,
            "limit": limit,
        }
