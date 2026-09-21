"""Human-triggered recovery from retained MIME, with no provider or model access."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Protocol
from uuid import UUID

import psycopg

from email_brain import store as persistence
from email_brain.attachments import Attachment
from email_brain.auth import Principal
from email_brain.mime_sandbox import validate_prepared
from email_brain.normalize import NormalizedMessage
from email_brain.store import AccessDenied, Conflict, IngestItem, NotFound, Store


class RecoveryUnavailable(Exception):
    """Unexpected parser failure; no content or parser exception crosses the boundary."""


class MimeProcessor(Protocol):
    """Trusted worker injection; never selected by an email or HTTP request."""

    @property
    def parser_version(self) -> str: ...

    @property
    def max_raw_bytes(self) -> int: ...

    def prepare(self, raw: bytes) -> tuple[NormalizedMessage | None, list[Attachment], bool]: ...


class RecoveryFence(Protocol):
    """Internal durable-grant fence; never supplied by a request or MIME payload."""

    def check(self, conn: psycopg.Connection[dict[str, Any]]) -> None: ...

    def complete(
        self, conn: psycopg.Connection[dict[str, Any]], attempt: dict[str, Any]
    ) -> None: ...


class Recovery:
    def __init__(self, store: Store, *, processor: MimeProcessor | None = None) -> None:
        self.store = store
        self.processor = processor
        self._processor_version: str | None = None
        self._processor_limit = persistence.MAX_RAW_BYTES
        if processor is not None:
            version, limit = processor.parser_version, processor.max_raw_bytes
            if (
                not isinstance(version, str)
                or not re.fullmatch(r"sandbox-mime-v1-[a-f0-9]{64}", version)
                or type(limit) is not int
                or not 1 <= limit <= 16 * 1024 * 1024
            ):
                raise ValueError("invalid isolated MIME processor contract")
            self._processor_version, self._processor_limit = version, limit

    @property
    def parser_version(self) -> str:
        return self._processor_version or persistence.PARSER_VERSION

    @staticmethod
    def attempt(
        conn: psycopg.Connection[dict[str, Any]], receipt_id: UUID, parser: str
    ) -> dict[str, Any] | None:
        return conn.execute(
            "SELECT id,receipt_id,parser_version,outcome,evidence_id,recorded_at "
            "FROM recovery_attempts WHERE receipt_id=%s AND parser_version=%s",
            (receipt_id, parser),
        ).fetchone()

    @staticmethod
    def receipt(
        conn: psycopg.Connection[dict[str, Any]], account_id: UUID, receipt_id: UUID
    ) -> dict[str, Any]:
        row = conn.execute(
            "SELECT q.*,e.provider_version,e.observed_at,h.event_key AS current_event,"
            "h.status FROM quarantine_receipts q "
            "JOIN mail_accounts a ON a.tenant_id=q.tenant_id AND a.id=q.account_id "
            "JOIN provider_events e ON e.tenant_id=q.tenant_id AND e.account_id=q.account_id "
            "AND e.event_key=q.event_key "
            "JOIN message_sync_state h ON h.tenant_id=q.tenant_id "
            "AND h.account_id=q.account_id AND h.provider_id=q.provider_id "
            "WHERE q.id=%s AND q.account_id=%s AND a.status='active'",
            (receipt_id, account_id),
        ).fetchone()
        if row is None:
            raise NotFound()
        return row

    @staticmethod
    def current(row: dict[str, Any]) -> None:
        if row["current_event"] != row["event_key"] or row["status"] != "quarantined":
            raise Conflict("receipt is no longer the current quarantine")

    @staticmethod
    def result(attempt: dict[str, Any]) -> dict[str, Any]:
        return {**attempt, "historical_outcome": True, "mailbox_effects": False}

    def retry(
        self, principal: Principal, account_id: UUID, receipt_id: UUID, parser: str
    ) -> dict[str, Any]:
        return self._retry(principal, account_id, receipt_id, parser)

    def _retry(
        self,
        principal: Principal,
        account_id: UUID,
        receipt_id: UUID,
        parser: str,
        *,
        fence: RecoveryFence | None = None,
    ) -> dict[str, Any]:
        if principal.client_kind != "human":
            raise AccessDenied("human required")
        ctx = principal.context
        self.store.require(ctx, "email.review")
        self.store.require(ctx, "email.evidence.read")
        if parser != self.parser_version:
            raise Conflict("deployed parser version changed; refresh before retrying")
        with self.store.transaction(ctx) as conn:
            if fence is not None:
                fence.check(conn)
            row = self.receipt(conn, account_id, receipt_id)
            cached = self.attempt(conn, receipt_id, parser)
            if cached:
                self.store.audit(conn, ctx, "recovery.read", "recovery", str(cached["id"]))
                if fence is not None:
                    fence.complete(conn, cached)
                return self.result(cached)
            self.current(row)

        # No open SQL transaction while processing untrusted data. Revalidate below.
        raw = self.store.load_raw(ctx, account_id, row["raw_sha256"])
        limit = self._processor_limit if self.processor else persistence.MAX_RAW_BYTES
        if len(raw) > limit:
            raise Conflict("retained message exceeds the current parser budget")
        valid = (
            raw is not None
            and len(raw) <= limit
            and hashlib.sha256(raw).hexdigest() == row["raw_sha256"]
        )
        attachments: list[Attachment] = []
        normalized, rejected = None, True
        if valid:
            try:
                if self.processor is None:
                    normalized, attachments, rejected = persistence.prepare_mime(raw)
                else:
                    # Contract/image binding cannot change midway through an approved retry.
                    if (
                        self.processor.parser_version != parser
                        or self.processor.max_raw_bytes != limit
                    ):
                        raise RecoveryUnavailable()
                    normalized, attachments, rejected = validate_prepared(
                        self.processor.prepare(raw), raw
                    )
                    if (
                        self.processor.parser_version != parser
                        or self.processor.max_raw_bytes != limit
                    ):
                        raise RecoveryUnavailable()
            except Exception:
                raise RecoveryUnavailable() from None
        outcome = "integrity_failed" if not valid else "mime_rejected"
        with self.store.transaction(ctx) as conn:
            if fence is not None:
                fence.check(conn)
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"{ctx.tenant_id}:{account_id}",),
            )
            current = self.receipt(conn, account_id, receipt_id)
            cached = self.attempt(conn, receipt_id, parser)
            if cached:
                self.store.audit(conn, ctx, "recovery.read", "recovery", str(cached["id"]))
                if fence is not None:
                    fence.complete(conn, cached)
                return self.result(cached)
            self.current(current)
            evidence_id = None
            if valid and not rejected and normalized is not None:
                metadata = current["source_metadata"] or {}
                item = IngestItem(
                    current["event_key"],
                    current["provider_id"],
                    current["provider_version"],
                    current["observed_at"],
                    raw,
                    metadata.get("thread_id"),
                    tuple(metadata.get("mailbox_ids", ())),
                    tuple(metadata.get("keywords", ())),
                )
                evidence_id = self.store.publish_message(
                    conn,
                    ctx,
                    account_id,
                    item,
                    normalized,
                    attachments,
                    source_metadata_known=current["source_metadata"] is not None,
                    parser_version=parser,
                )
                conn.execute(
                    "UPDATE message_sync_state SET status='ready',updated_at=now() "
                    "WHERE account_id=%s AND provider_id=%s AND event_key=%s",
                    (account_id, current["provider_id"], current["event_key"]),
                )
                outcome = "recovered"
            attempt = conn.execute(
                "INSERT INTO recovery_attempts(tenant_id,account_id,receipt_id,actor_id,"
                "parser_version,outcome,evidence_id) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING id,receipt_id,parser_version,outcome,evidence_id,recorded_at",
                (ctx.tenant_id, account_id, receipt_id, ctx.actor_id, parser, outcome, evidence_id),
            ).fetchone()
            assert attempt is not None
            self.store.audit(conn, ctx, "recovery." + outcome, "recovery", str(attempt["id"]))
            if fence is not None:
                fence.complete(conn, attempt)
            return self.result(attempt)
