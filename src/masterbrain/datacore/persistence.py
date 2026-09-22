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
FILEOS_TEXT_EXTRACTOR_VERSION = "fileos-text-v1"
INDEX_CHUNKER_VERSION = "deterministic-chunks-v1"
MAX_GENERATION_TEXT_BYTES = 64 * 1_048_576
MAX_GENERATION_CHUNKS = 100_000
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
            if after is not None and not conn.execute(
                "SELECT 1 FROM brain_fileos_run_items "
                "WHERE actor_id=%s AND run_id=%s AND item_id=%s",
                (latest["actor_id"], latest["run_id"], after),
            ).fetchone():
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
                        for ordinal, (start, end, text) in enumerate(
                            deterministic_chunks(body)
                        )
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
            self.store.audit(
                conn, ctx, "brain.fileos_rebuild_preview", "brain_source", source_id
            )
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
                    if (
                        row["body_sha256"] != body_sha
                        or document_id
                        != stable_id(
                            "document", row["version_id"], row["normalizer"], body_sha
                        )
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
        request_hash = _canonical_digest(
            {"source_id": source_id, "generation_id": generation_id}
        )
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
            return IndexActivation(
                source_id, generation_id, previous_id, row["activated_at"], True
            )

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
                "JOIN brain_source_items si ON si.tenant_id=i.tenant_id AND si.id=i.item_id "
                "WHERE c.generation_id=%s "
                "AND c.search_vector @@ plainto_tsquery('simple',%s) "
                "ORDER BY rank DESC,c.id LIMIT %s",
                (query, query, active["generation_id"], query, limit),
            ).fetchall()
            self.store.audit(
                conn, ctx, "brain.fileos_active_search", "brain_source", source_id
            )
            return [SearchHit(**row) for row in rows]

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
