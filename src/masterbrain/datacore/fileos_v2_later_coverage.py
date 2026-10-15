"""Historical, exact-row FileOS v2 coverage closure; no current authority."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound
from masterbrain.datacore.fileos_v2_later_packets import _load_packet
from masterbrain.datacore.persistence import (
    DataCoreStore,
    _canonical_digest,
    _fileos_v2_staged_rows,
)

CLOSURE_VERSION = "masterbrain-fileos-v2-later-coverage-v1"
MAX_CLOSURE_BYTES = 16 * 1024 * 1024


def _coverage(packet: dict[str, Any], packet_sha256: str) -> dict[str, Any]:
    """Project every observed row and every prior classification exactly once."""
    candidate = packet["candidate"]
    preview = packet["preview"]
    source_id = packet["source_id"]
    current = _fileos_v2_staged_rows(candidate, source_id)
    current_rows = [
        {
            "kind": kind,
            "locator": locator,
            "item_id": item_id,
            "candidate_version_id": version_id,
            "sha256": sha256,
            "size_bytes": size,
            "media_type": media,
            "reason": reason,
        }
        for kind, locator, item_id, version_id, sha256, size, media, reason
        in sorted(current, key=lambda row: row[1])
    ]
    prior_rows = sorted(preview["prior_rows"], key=lambda row: row["locator"])
    if (
        len(current_rows) != sum(candidate["counts"].values())
        or len(prior_rows) != sum(preview["counts"].values())
        or len({row["locator"] for row in prior_rows}) != len(prior_rows)
    ):
        raise ValueError("FileOS v2 later coverage is not closed")
    return {
        "closure_version": CLOSURE_VERSION,
        "publishable": False,
        "absence_authorized": False,
        "requires_review": True,
        "packet_sha256": packet_sha256,
        "source_id": source_id,
        "root_binding_sha256": packet["root_binding_sha256"],
        "observed_at": candidate["observed_at"],
        "current_counts": candidate["counts"],
        "prior_classification_counts": preview["counts"],
        "blockers": preview["blockers"],
        "current_rows": current_rows,
        "prior_rows": prior_rows,
    }


@dataclass(frozen=True, slots=True)
class FileOSV2LaterCoverage:
    closure_id: UUID
    packet_id: UUID
    source_id: str
    observed_at: datetime
    current_counts: dict[str, int]
    prior_classification_counts: dict[str, int]
    blockers: tuple[str, ...]
    closure_sha256: str
    sealed_at: datetime
    recorded: bool
    publishable: bool = False
    absence_authorized: bool = False


class FileOSV2LaterCoverageStore:
    def __init__(self, core: DataCoreStore) -> None:
        self.core = core

    def _inspect_locked(
        self, conn: Connection[dict[str, Any]], closure_id: UUID
    ) -> FileOSV2LaterCoverage:
        row = conn.execute(
            "SELECT id,actor_id,packet_id,completion_id,source_id,packet_sha256,"
            "observed_at,closure_sha256,closure,sealed_at "
            "FROM brain_fileos_v2_later_coverage_closures WHERE id=%s",
            (closure_id,),
        ).fetchone()
        if row is None:
            raise NotFound()
        packet_row, _ = _load_packet(conn, row["packet_id"])
        try:
            expected = _coverage(packet_row["packet"], packet_row["packet_sha256"])
            if (
                row["completion_id"] != packet_row["completion_id"]
                or row["source_id"] != packet_row["source_id"]
                or row["packet_sha256"] != packet_row["packet_sha256"]
                or row["observed_at"] != packet_row["observed_at"]
                or row["closure"] != expected
                or row["closure_sha256"] != _canonical_digest(expected)
            ):
                raise ValueError("closure mismatch")
        except (KeyError, TypeError, ValueError) as exc:
            raise Conflict("FileOS v2 later coverage integrity requires review") from exc
        return FileOSV2LaterCoverage(
            closure_id=row["id"],
            packet_id=row["packet_id"],
            source_id=row["source_id"],
            observed_at=row["observed_at"],
            current_counts=dict(expected["current_counts"]),
            prior_classification_counts=dict(expected["prior_classification_counts"]),
            blockers=tuple(expected["blockers"]),
            closure_sha256=row["closure_sha256"],
            sealed_at=row["sealed_at"],
            recorded=False,
        )

    def inspect(self, ctx: TenantContext, closure_id: UUID) -> FileOSV2LaterCoverage:
        self.core.store.require(ctx, "brain.changes.read")
        if not isinstance(closure_id, UUID):
            raise ValueError("invalid FileOS v2 later coverage identity")
        with self.core.store.transaction(ctx) as conn:
            result = self._inspect_locked(conn, closure_id)
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_coverage_read",
                "fileos_v2_later_coverage", str(closure_id),
            )
            return result

    def seal(
        self, principal: Principal, packet_id: UUID, closure_id: UUID
    ) -> FileOSV2LaterCoverage:
        if principal.client_kind != "worker":
            raise AccessDenied("FileOS v2 later coverage worker required")
        ctx = principal.context
        for scope in ("brain.fileos.transition.verify", "brain.changes.read"):
            self.core.store.require(ctx, scope)
        if not isinstance(packet_id, UUID) or not isinstance(closure_id, UUID):
            raise ValueError("invalid FileOS v2 later coverage request")
        with self.core.store.transaction(ctx) as conn:
            existing = conn.execute(
                "SELECT id,actor_id,packet_id FROM brain_fileos_v2_later_coverage_closures "
                "WHERE id=%s OR packet_id=%s",
                (closure_id, packet_id),
            ).fetchone()
            if existing is not None:
                if (
                    existing["id"] != closure_id
                    or existing["actor_id"] != ctx.actor_id
                    or existing["packet_id"] != packet_id
                ):
                    raise Conflict("FileOS v2 later coverage identity changed")
                result = self._inspect_locked(conn, closure_id)
                self.core.store.audit(
                    conn, ctx, "brain.fileos_v2_later_coverage_replay",
                    "fileos_v2_later_coverage", str(closure_id),
                )
                return result
            packet_row, _ = _load_packet(conn, packet_id)
            try:
                closure = _coverage(packet_row["packet"], packet_row["packet_sha256"])
                encoded = json.dumps(
                    closure, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False,
                ).encode("utf-8")
            except (KeyError, TypeError, ValueError) as exc:
                raise Conflict("FileOS v2 later coverage requires review") from exc
            if len(encoded) > MAX_CLOSURE_BYTES:
                raise Conflict("FileOS v2 later coverage size requires review")
            digest = _canonical_digest(closure)
            inserted = conn.execute(
                "INSERT INTO brain_fileos_v2_later_coverage_closures(tenant_id,id,"
                "actor_id,packet_id,completion_id,source_id,packet_sha256,"
                "observed_at,closure_sha256,closure) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING sealed_at",
                (
                    ctx.tenant_id, closure_id, ctx.actor_id, packet_id,
                    packet_row["completion_id"], packet_row["source_id"],
                    packet_row["packet_sha256"], packet_row["observed_at"],
                    digest, Jsonb(closure),
                ),
            ).fetchone()
            assert inserted is not None
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_coverage_sealed",
                "fileos_v2_later_coverage", str(closure_id),
            )
            return FileOSV2LaterCoverage(
                closure_id=closure_id,
                packet_id=packet_id,
                source_id=packet_row["source_id"],
                observed_at=packet_row["observed_at"],
                current_counts=dict(closure["current_counts"]),
                prior_classification_counts=dict(closure["prior_classification_counts"]),
                blockers=tuple(closure["blockers"]),
                closure_sha256=digest,
                sealed_at=inserted["sealed_at"],
                recorded=True,
            )
