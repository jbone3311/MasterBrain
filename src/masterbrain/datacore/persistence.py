"""Tenant-isolated persistence for shared DataCore source observations."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from psycopg.types.json import Jsonb

from email_brain.domain.models import TenantContext
from email_brain.store import Conflict, NotFound, Store
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
_IDENTITY = re.compile(r"^[a-z][a-z0-9_-]{0,127}$")


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
class SearchHit:
    chunk_id: str
    document_id: str
    evidence_id: str
    source_id: str
    locator: str
    excerpt: str
    rank: float


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


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
