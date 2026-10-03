"""Bounded resumable read worker. Invoking this library with a real client is explicit.

No scheduler/enrollment/token discovery, no mailbox writes and no database transaction
held across network calls. Synthetic transports exercise the full workflow in tests.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from email_brain.blobs import BlobError
from email_brain.connectors.fastmail import (
    BlobTooLarge,
    ControlTooLarge,
    ProviderAuthRequired,
    ProviderThrottled,
    ProviderUnavailable,
)
from email_brain.connectors.jmap import (
    AnchorNotFound,
    JmapReader,
    ProtocolError,
    ResyncRequired,
    id_list,
    identifier,
)
from email_brain.domain.models import TenantContext
from email_brain.normalize import MAX_RAW_BYTES
from email_brain.store import (
    HELD_SOURCE_TOO_LARGE,
    MAX_PROVIDER_SIZE,
    Conflict,
    IngestItem,
    InventoryError,
    NotFound,
    Store,
    digest,
)
from email_brain.sync_store import Outcome, SyncStore

MAX_PAGE_BYTES = 16 * 1024 * 1024
# Listing pages are bounded by IDs, bytes and time; a page commits what it fetched.
LISTING_LIMIT = 50
LISTING_SECONDS = 40
STEP_SECONDS = 60
MAX_CHANGES = 16


class Checkpoint(BaseModel):
    """Versioned durable position. Version 3 lists by anchor; version 2 by position."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal[1, 2, 3] = 3
    generation: UUID
    phase: Literal["listing", "reconcile", "changes"]
    email_state: str = Field(min_length=1, max_length=512)
    query_state: str | None = Field(default=None, min_length=1, max_length=512)
    position: int = Field(default=0, ge=0, le=2**31 - 1)
    total: int | None = Field(default=None, ge=0, le=2**31 - 1)
    anchor: str | None = Field(default=None, min_length=1, max_length=512)
    listed: int = Field(default=0, ge=0, le=2**31 - 1)

    @model_validator(mode="after")
    def consistent(self) -> Checkpoint:
        identifier(self.email_state)
        if self.query_state is not None:
            identifier(self.query_state)
        if self.anchor is not None:
            identifier(self.anchor)
        positional = self.position or self.total is not None or self.query_state is not None
        anchored = self.anchor is not None or self.listed
        if self.phase != "listing" and (positional or anchored):
            raise ValueError("unexpected listing fields")
        if self.phase == "listing":
            if self.schema_version == 3:
                if positional or (self.anchor is None) != (self.listed == 0):
                    raise ValueError("inconsistent anchored listing checkpoint")
            elif anchored or (
                self.position
                and (self.query_state is None or self.total is None or self.position >= self.total)
            ):
                raise ValueError("incomplete listing checkpoint")
        return self

    def encode(self) -> str:
        value = self.model_dump_json()
        if len(value) > 4000:
            raise ProtocolError("checkpoint exceeds storage limit")
        return value


class ReadClient(Protocol):
    def discover(self) -> str: ...
    def reader(self) -> JmapReader: ...
    def metadata(self, ids: list[str]) -> dict[str, Any]: ...
    def download_blob(self, blob_id: str) -> bytes: ...


def metadata_rows(
    data: dict[str, Any], requested: tuple[str, ...], account: str
) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
    if data.get("accountId") != account:
        raise ProtocolError("metadata account mismatch")
    identifier(data.get("state"))
    rows = data.get("list")
    missing = id_list(data.get("notFound"))
    if not isinstance(rows, list) or len(rows) > 100:
        raise ProtocolError("invalid metadata list")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ProtocolError("invalid metadata row")
        key = identifier(row.get("id"))
        if key in result:
            raise ProtocolError("duplicate metadata row")
        result[key] = row
    if set(result) & set(missing) or set(result) | set(missing) != set(requested):
        raise ProtocolError("metadata does not account for requested IDs")
    return result, missing


def true_keys(value: Any) -> tuple[str, ...]:
    if (
        not isinstance(value, dict)
        or len(value) > 100
        or any(v is not True for v in value.values())
    ):
        raise ProtocolError("invalid provider membership map")
    return tuple(sorted(identifier(key) for key in value))


def message_size(value: Any) -> int | None:
    """JMAP ``size`` when the provider reports it; absent metadata is not an error."""
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= MAX_PROVIDER_SIZE:
        raise ProtocolError("invalid message size")
    return value


def retry_delay(failures: int, retry_after: int | None, jitter: float) -> int:
    """A floor, exponential cap, and bounded jitter; never spin on Retry-After: 0."""
    base = min(3600, 5 * 2 ** min(max(failures, 0), 10))
    return max(min(retry_after or 0, 3600), min(3600, int(base * (1 + jitter))))


class ReadWorker:
    def __init__(
        self,
        store: Store,
        client: ReadClient,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        jitter: Callable[[], float] | None = None,
        authorize: Callable[[], None] | None = None,
    ) -> None:
        import random

        max_raw_bytes = getattr(store, "max_raw_bytes", MAX_RAW_BYTES)
        if type(max_raw_bytes) is not int or not MAX_RAW_BYTES <= max_raw_bytes <= MAX_PAGE_BYTES:
            raise ValueError("store raw byte limit must be an integer between 1 and 16 MiB")
        self._max_raw_bytes = max_raw_bytes
        # A change page cannot be split, so its size keeps the worst case within budget.
        self._changes_limit = max(1, min(MAX_CHANGES, MAX_PAGE_BYTES // max_raw_bytes))
        self.store = store
        self.jobs = SyncStore(store)
        self.client = client
        self.monotonic = monotonic
        self.jitter = jitter or random.random
        self.authorize = authorize or (lambda: None)

    def step(self, ctx: TenantContext, account_id: UUID) -> str:
        self.authorize()
        lease = self.jobs.acquire(ctx, account_id)
        if lease is None:
            return "not_due"
        started = self.monotonic()

        def heartbeat() -> None:
            self.authorize()
            if self.monotonic() - started > STEP_SECONDS:
                raise ProviderUnavailable("worker step deadline exceeded")
            self.jobs.renew(ctx, account_id, lease.token)

        def listing_budget_spent() -> bool:
            return self.monotonic() - started > LISTING_SECONDS

        try:
            checkpoint = Checkpoint.model_validate_json(lease.cursor) if lease.cursor else None
            heartbeat()
            if self.client.discover() != lease.provider_account_id:
                raise ProtocolError("configured provider account mismatch")
            heartbeat()
            reader = self.client.reader()
            items: list[IngestItem] = []
            inventory_generation = None
            inventory_total = None
            outcome: Outcome = "progress"
            if checkpoint is None or checkpoint.schema_version == 1:
                next_checkpoint = self._baseline(reader)
            elif checkpoint.phase == "listing":
                if checkpoint.schema_version != 3:
                    # Positional listings restart as anchored ones; the Email baseline
                    # is preserved so any deletion meanwhile is replayed later.
                    next_checkpoint = self._relist(checkpoint)
                else:
                    try:
                        page = reader.query_page(checkpoint.anchor, limit=LISTING_LIMIT)
                    except AnchorNotFound:
                        next_checkpoint = self._relist(checkpoint)
                    else:
                        items, consumed = self._fetch(
                            ctx,
                            account_id,
                            checkpoint,
                            page.ids,
                            (),
                            lease.provider_account_id,
                            heartbeat,
                            partial=listing_budget_spent,
                        )
                        inventory_generation = checkpoint.generation
                        listed = checkpoint.listed + consumed
                        if consumed < len(page.ids) or page.has_more:
                            anchor = page.ids[consumed - 1] if consumed else checkpoint.anchor
                            next_checkpoint = Checkpoint(
                                generation=checkpoint.generation,
                                phase="listing",
                                email_state=checkpoint.email_state,
                                anchor=anchor,
                                listed=listed,
                            )
                        else:
                            # Every ID listed in this generation is durable before the
                            # seal; the certificate is the worker's own count, because
                            # the provider total moves while the mailbox changes.
                            inventory_total = listed
                            next_checkpoint = Checkpoint(
                                generation=checkpoint.generation,
                                phase="reconcile",
                                email_state=checkpoint.email_state,
                            )
            elif checkpoint.phase == "reconcile":
                missing = self.jobs.reconciliation_candidates(
                    ctx, account_id, checkpoint.generation
                )
                items, _ = self._fetch(
                    ctx, account_id, checkpoint, (), missing, lease.provider_account_id, heartbeat
                )
                next_checkpoint = (
                    checkpoint
                    if missing
                    else Checkpoint(
                        generation=checkpoint.generation,
                        phase="changes",
                        email_state=checkpoint.email_state,
                    )
                )
            else:
                try:
                    changes = reader.changes(checkpoint.email_state, limit=self._changes_limit)
                except ResyncRequired:
                    next_checkpoint = self._baseline(reader)
                else:
                    items, _ = self._fetch(
                        ctx,
                        account_id,
                        checkpoint,
                        changes.created + changes.updated,
                        changes.destroyed,
                        lease.provider_account_id,
                        heartbeat,
                    )
                    next_checkpoint = Checkpoint(
                        generation=checkpoint.generation,
                        phase="changes",
                        email_state=changes.next_state,
                    )
                    outcome = "progress" if changes.has_more else "caught_up"
            heartbeat()
            inserted = self.store.ingest_page(
                ctx,
                account_id,
                lease.cursor,
                next_checkpoint.encode(),
                items,
                lease_token=lease.token,
                inventory_generation=inventory_generation,
                inventory_total=inventory_total,
            )
            self.jobs.finish(
                ctx,
                account_id,
                lease.token,
                outcome,
                inserted,
                delay=60 if outcome == "caught_up" else 0,
            )
            return outcome
        except ProviderAuthRequired:
            self.jobs.finish(ctx, account_id, lease.token, "auth_required")
            return "auth_required"
        except ResyncRequired:
            # Rebuilding after cursor expiry requires an inventory diff before
            # declaring completion; never leave old missing messages searchable
            # while reporting a successful fresh sync.
            self.jobs.finish(ctx, account_id, lease.token, "resync_required")
            return "resync_required"
        except (ProviderUnavailable, ProviderThrottled, BlobError) as error:
            # Unavailable evidence storage must not become a permanent MIME pause.
            # Staging failures leave the cursor unchanged; retry remains bounded.
            delay = retry_delay(
                lease.failures,
                error.retry_after_seconds if isinstance(error, ProviderThrottled) else None,
                min(1.0, max(0.0, self.jitter())),
            )
            self.jobs.finish(ctx, account_id, lease.token, "retry", delay=delay)
            return "retry"
        except (ProtocolError, ValidationError, InventoryError):
            self.jobs.finish(ctx, account_id, lease.token, "protocol_error")
            return "protocol_error"
        except (ValueError, RecursionError, UnicodeError):
            # Parsing errors never advance the checkpoint or leak content to telemetry.
            self.jobs.finish(ctx, account_id, lease.token, "parse_error")
            return "parse_error"
        except Conflict:
            # A replaced or expired lease cannot record an outcome; another worker
            # owns the account now. Any other conflict is a durable protocol pause.
            try:
                self.jobs.finish(ctx, account_id, lease.token, "protocol_error")
            except Conflict:
                return "lease_lost"
            return "protocol_error"

    @staticmethod
    def _baseline(reader: JmapReader) -> Checkpoint:
        return Checkpoint(generation=uuid4(), phase="listing", email_state=reader.baseline_state())

    @staticmethod
    def _relist(checkpoint: Checkpoint) -> Checkpoint:
        return Checkpoint(generation=uuid4(), phase="listing", email_state=checkpoint.email_state)

    def _metadata_rows(
        self, ids: tuple[str, ...], account: str, heartbeat: Callable[[], None]
    ) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
        """Split only a byte-overflowing metadata response; keep the page atomic."""
        if not ids:
            return {}, ()
        heartbeat()
        try:
            return metadata_rows(self.client.metadata(list(ids)), ids, account)
        except ControlTooLarge:
            if len(ids) == 1:
                # One provider row cannot be divided. Do not silently omit it.
                raise
            middle = len(ids) // 2
            left, left_missing = self._metadata_rows(ids[:middle], account, heartbeat)
            right, right_missing = self._metadata_rows(ids[middle:], account, heartbeat)
            return {**left, **right}, left_missing + right_missing

    def _fetch(
        self,
        ctx: TenantContext,
        account_id: UUID,
        checkpoint: Checkpoint,
        ids: tuple[str, ...],
        deleted: tuple[str, ...],
        account: str,
        heartbeat: Callable[[], None],
        *,
        partial: Callable[[], bool] | None = None,
    ) -> tuple[list[IngestItem], int]:
        """Build ingest items for ``ids`` plus tombstones for ``deleted``.

        With ``partial`` the page may stop early once the byte or time budget is spent;
        the returned count says how many of ``ids`` (a prefix) were included. Without it
        every ID is included or the page fails as a whole.
        """
        heartbeat()
        rows, missing = self._metadata_rows(ids, account, heartbeat)
        retained: Mapping[str, tuple[str, str]] = (
            self.jobs.retained_blobs(ctx, account_id, ids) if ids else {}
        )
        items = []
        total_bytes = 0
        consumed = 0
        mailboxes: tuple[str, ...]
        keywords: tuple[str, ...]

        def tombstone(key: str) -> IngestItem:
            version = digest({"missing": key})
            return IngestItem(
                digest({"checkpoint": checkpoint.encode(), "id": key, "version": version}),
                key,
                version,
                datetime(1970, 1, 1, tzinfo=UTC),
            )

        for key in ids:
            heartbeat()
            row = rows.get(key)
            if row is None:
                if key not in missing:
                    raise ProtocolError("unaccounted message")
                items.append(tombstone(key))
                consumed += 1
                continue
            blob = identifier(row.get("blobId"))
            thread = identifier(row.get("threadId"))
            mailboxes = true_keys(row.get("mailboxIds"))
            keywords = true_keys(row.get("keywords"))
            size = message_size(row.get("size"))
            received_str = row.get("receivedAt")
            if not isinstance(received_str, str) or len(received_str) > 40:
                raise ProtocolError("invalid receive timestamp")
            try:
                received = datetime.fromisoformat(received_str.replace("Z", "+00:00"))
            except ValueError:
                raise ProtocolError("invalid receive timestamp") from None
            if received.tzinfo is None:
                raise ProtocolError("receive timestamp is not timezone aware")
            expected = min(size, self._max_raw_bytes) if size is not None else self._max_raw_bytes
            if (
                partial is not None
                and consumed
                and (total_bytes + expected > MAX_PAGE_BYTES or partial())
            ):
                break
            raw = self._raw(ctx, account_id, key, blob, size, retained)
            version_fields = {
                "blob": blob,
                "thread": thread,
                "mailboxes": mailboxes,
                "keywords": keywords,
                "received": received.isoformat(),
            }
            if raw is None:
                # Held: the provider has the message, but its bytes exceed the retained
                # storage budget. A raised budget yields a new version and a fresh try.
                version = digest({**version_fields, "held_limit": self._max_raw_bytes})
                held_reason: str | None = HELD_SOURCE_TOO_LARGE
            else:
                total_bytes += len(raw)
                if total_bytes > MAX_PAGE_BYTES:
                    raise ProtocolError("page byte budget exceeded; smaller batches required")
                version = digest(version_fields)
                held_reason = None
            event = digest({"checkpoint": checkpoint.encode(), "id": key, "version": version})
            items.append(
                IngestItem(
                    event,
                    key,
                    version,
                    received,
                    raw,
                    thread,
                    mailboxes,
                    keywords,
                    blob_id=blob,
                    held_reason=held_reason,
                    source_size=size,
                )
            )
            consumed += 1
        if partial is None and consumed != len(ids):
            raise ProtocolError("page fetch did not account for every ID")
        for key in deleted:
            heartbeat()
            items.append(tombstone(key))
        return items, consumed

    def _raw(
        self,
        ctx: TenantContext,
        account_id: UUID,
        key: str,
        blob: str,
        size: int | None,
        retained: Mapping[str, tuple[str, str]],
    ) -> bytes | None:
        """Retained bytes for an unchanged blob, a bounded download, or ``None`` when held."""
        if size is not None and size > self._max_raw_bytes:
            return None
        known = retained.get(key)
        if known is not None and known[0] == blob:
            try:
                raw = self.jobs.retained_raw(ctx, account_id, known[1])
            except (BlobError, NotFound):
                raw = None  # Fall back to the provider; ingestion re-verifies the digest.
            # JMAP blob identities are immutable, but a reported size that disagrees
            # with the retained bytes means the provider changed them: download again.
            if (
                raw is not None
                and len(raw) <= self._max_raw_bytes
                and (size is None or len(raw) == size)
            ):
                return raw
        try:
            raw = self.client.download_blob(blob)
        except BlobTooLarge:
            return None
        if len(raw) > self._max_raw_bytes:
            return None
        return raw
