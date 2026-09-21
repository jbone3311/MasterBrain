"""Bounded resumable read worker. Invoking this library with a real client is explicit.

No scheduler/enrollment/token discovery, no mailbox writes and no database transaction
held across network calls. Synthetic transports exercise the full workflow in tests.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from email_brain.blobs import BlobError
from email_brain.connectors.fastmail import (
    ProviderAuthRequired,
    ProviderThrottled,
    ProviderUnavailable,
)
from email_brain.connectors.jmap import (
    JmapReader,
    ProtocolError,
    ResyncRequired,
    id_list,
    identifier,
)
from email_brain.domain.models import TenantContext
from email_brain.normalize import MAX_RAW_BYTES
from email_brain.store import IngestItem, InventoryError, Store, digest
from email_brain.sync_store import Outcome, SyncStore

MAX_PAGE_BYTES = 16 * 1024 * 1024


class Checkpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal[1, 2] = 2
    generation: UUID
    phase: Literal["listing", "reconcile", "changes"]
    email_state: str = Field(min_length=1, max_length=512)
    query_state: str | None = Field(default=None, min_length=1, max_length=512)
    position: int = Field(default=0, ge=0, le=2**31 - 1)
    total: int | None = Field(default=None, ge=0, le=2**31 - 1)

    @model_validator(mode="after")
    def consistent(self) -> Checkpoint:
        identifier(self.email_state)
        if self.query_state is not None:
            identifier(self.query_state)
        if (
            self.phase == "listing"
            and self.position
            and (self.query_state is None or self.total is None or self.position >= self.total)
        ):
            raise ValueError("incomplete listing checkpoint")
        if self.phase in {"changes", "reconcile"} and (
            self.position or self.total is not None or self.query_state is not None
        ):
            raise ValueError("unexpected listing fields")
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
        self._page_limit = 1 if max_raw_bytes > MAX_RAW_BYTES else 8
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
            if self.monotonic() - started > 60:
                raise ProviderUnavailable("worker step deadline exceeded")
            self.jobs.renew(ctx, account_id, lease.token)

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
                page = reader.query_page(checkpoint.position, limit=self._page_limit)
                if checkpoint.query_state is not None and (
                    checkpoint.query_state != page.query_state or checkpoint.total != page.total
                ):
                    # Keep the original Email baseline: previously imported IDs
                    # may disappear during this restart and must be replayed as deletions.
                    next_checkpoint = Checkpoint(
                        generation=uuid4(),
                        phase="listing",
                        email_state=checkpoint.email_state,
                    )
                else:
                    items = self._fetch(
                        checkpoint, page.ids, (), lease.provider_account_id, heartbeat
                    )
                    inventory_generation = checkpoint.generation
                    if page.has_more:
                        next_checkpoint = Checkpoint(
                            generation=checkpoint.generation,
                            phase="listing",
                            email_state=checkpoint.email_state,
                            query_state=page.query_state,
                            position=page.position + len(page.ids),
                            total=page.total,
                        )
                    else:
                        inventory_total = page.total
                        next_checkpoint = Checkpoint(
                            generation=checkpoint.generation,
                            phase="reconcile",
                            email_state=checkpoint.email_state,
                        )
            elif checkpoint.phase == "reconcile":
                missing = self.jobs.reconciliation_candidates(
                    ctx, account_id, checkpoint.generation
                )
                items = self._fetch(checkpoint, (), missing, lease.provider_account_id, heartbeat)
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
                    changes = reader.changes(checkpoint.email_state, limit=self._page_limit)
                except ResyncRequired:
                    next_checkpoint = self._baseline(reader)
                else:
                    items = self._fetch(
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

    @staticmethod
    def _baseline(reader: JmapReader) -> Checkpoint:
        return Checkpoint(generation=uuid4(), phase="listing", email_state=reader.baseline_state())

    def _fetch(
        self,
        checkpoint: Checkpoint,
        ids: tuple[str, ...],
        deleted: tuple[str, ...],
        account: str,
        heartbeat: Callable[[], None],
    ) -> list[IngestItem]:
        heartbeat()
        rows, missing = (
            metadata_rows(self.client.metadata(list(ids)), ids, account) if ids else ({}, ())
        )
        items = []
        total_bytes = 0
        mailboxes: tuple[str, ...]
        keywords: tuple[str, ...]
        for key in ids + deleted:
            heartbeat()
            row = rows.get(key)
            if row is None:
                if key not in missing and key not in deleted:
                    raise ProtocolError("unaccounted message")
                version = digest({"missing": key})
                raw, thread, mailboxes, keywords = None, None, (), ()
                received = datetime(1970, 1, 1, tzinfo=UTC)
            else:
                blob = identifier(row.get("blobId"))
                thread = identifier(row.get("threadId"))
                mailboxes = true_keys(row.get("mailboxIds"))
                keywords = true_keys(row.get("keywords"))
                received_str = row.get("receivedAt")
                if not isinstance(received_str, str) or len(received_str) > 40:
                    raise ProtocolError("invalid receive timestamp")
                try:
                    received = datetime.fromisoformat(received_str.replace("Z", "+00:00"))
                except ValueError:
                    raise ProtocolError("invalid receive timestamp") from None
                if received.tzinfo is None:
                    raise ProtocolError("receive timestamp is not timezone aware")
                raw = self.client.download_blob(blob)
                if len(raw) > self._max_raw_bytes:
                    raise ProtocolError("message exceeds configured store byte limit")
                total_bytes += len(raw)
                if total_bytes > MAX_PAGE_BYTES:
                    raise ProtocolError("page byte budget exceeded; smaller batches required")
                version = digest(
                    {
                        "blob": blob,
                        "thread": thread,
                        "mailboxes": mailboxes,
                        "keywords": keywords,
                        "received": received.isoformat(),
                    }
                )
            event = digest({"checkpoint": checkpoint.encode(), "id": key, "version": version})
            items.append(
                IngestItem(event, key, version, received, raw, thread, mailboxes, keywords)
            )
        return items
