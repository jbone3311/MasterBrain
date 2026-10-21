"""Immutable private later-observation packets; never FileOS current authority."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound
from masterbrain.datacore.fileos_v2_completed_preview import _locked_later_observation
from masterbrain.datacore.fileos_v2_consecutive_preview import (
    preview_fileos_v2_consecutive_observations,
)
from masterbrain.datacore.persistence import (
    DataCoreStore,
    _canonical_digest,
    _fileos_v2_staged_rows,
)

PACKET_VERSION = "masterbrain-fileos-v2-later-observation-packet-v1"
MAX_PACKET_BYTES = 16 * 1024 * 1024
_FIELDS = frozenset({
    "packet_version", "publishable", "absence_authorized", "requires_review",
    "completion_id", "source_id", "root_binding_sha256",
    "baseline_completion_sha256", "candidate", "preview",
})


@dataclass(frozen=True, slots=True)
class FileOSV2LaterPacket:
    packet_id: UUID
    completion_id: UUID
    source_id: str
    observed_at: datetime
    candidate_counts: dict[str, int]
    classification_counts: dict[str, int]
    blockers: tuple[str, ...]
    packet_sha256: str
    recorded_at: datetime
    recorded: bool
    publishable: bool = False
    absence_authorized: bool = False


def _load_packet(
    conn: Connection[dict[str, Any]],
    packet_id: UUID,
) -> tuple[dict[str, Any], FileOSV2LaterPacket]:
    row = conn.execute(
        "SELECT id,actor_id,completion_id,source_id,root_binding_sha256,"
        "baseline_completion_sha256,observed_at,packet_sha256,packet,recorded_at "
        "FROM brain_fileos_v2_later_observation_packets WHERE id=%s",
        (packet_id,),
    ).fetchone()
    if row is None:
        raise NotFound()
    completion = conn.execute(
        "SELECT stage_id,completion_sha256 FROM brain_fileos_v2_baseline_completions "
        "WHERE id=%s AND source_id=%s",
        (row["completion_id"], row["source_id"]),
    ).fetchone()
    if completion is None:
        raise Conflict("FileOS v2 later packet integrity requires review")
    stage = conn.execute(
        "SELECT packet_id FROM brain_fileos_v2_staged_inventories WHERE id=%s",
        (completion["stage_id"],),
    ).fetchone()
    original = conn.execute(
        "SELECT packet FROM brain_fileos_transition_packets WHERE id=%s",
        (stage["packet_id"],),
    ).fetchone() if stage else None
    saved = row["packet"]
    try:
        if (
            not isinstance(saved, Mapping)
            or set(saved) != _FIELDS
            or saved["packet_version"] != PACKET_VERSION
            or saved["publishable"] is not False
            or saved["absence_authorized"] is not False
            or saved["requires_review"] is not True
            or saved["completion_id"] != str(row["completion_id"])
            or saved["source_id"] != row["source_id"]
            or saved["root_binding_sha256"] != row["root_binding_sha256"]
            or saved["baseline_completion_sha256"] != row["baseline_completion_sha256"]
            or completion["completion_sha256"] != row["baseline_completion_sha256"]
            or _canonical_digest(saved) != row["packet_sha256"]
            or original is None
            or not isinstance(original["packet"], Mapping)
        ):
            raise ValueError("packet shape or digest")
        candidate, preview = saved["candidate"], saved["preview"]
        prior = original["packet"]["candidate"]
        if not isinstance(candidate, Mapping) or not isinstance(preview, Mapping):
            raise ValueError("packet observations")
        _fileos_v2_staged_rows(candidate, row["source_id"])
        if (
            datetime.fromisoformat(candidate["observed_at"]) != row["observed_at"]
            or candidate["root_binding"]["sha256"] != row["root_binding_sha256"]
            or preview_fileos_v2_consecutive_observations(prior, candidate) != preview
        ):
            raise ValueError("packet classification")
    except (KeyError, TypeError, ValueError) as exc:
        raise Conflict("FileOS v2 later packet integrity requires review") from exc
    return row, FileOSV2LaterPacket(
        packet_id=row["id"],
        completion_id=row["completion_id"],
        source_id=row["source_id"],
        observed_at=row["observed_at"],
        candidate_counts=dict(candidate["counts"]),
        classification_counts=dict(preview["counts"]),
        blockers=tuple(preview["blockers"]),
        packet_sha256=row["packet_sha256"],
        recorded_at=row["recorded_at"],
        recorded=False,
    )


class FileOSV2LaterPacketStore:
    def __init__(self, core: DataCoreStore) -> None:
        self.core = core

    def inspect(self, ctx: TenantContext, packet_id: UUID) -> FileOSV2LaterPacket:
        self.core.store.require(ctx, "brain.changes.read")
        if not isinstance(packet_id, UUID):
            raise ValueError("invalid FileOS v2 later packet identity")
        with self.core.store.transaction(ctx) as conn:
            _, result = _load_packet(conn, packet_id)
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_packet_read",
                "fileos_v2_later_observation_packet", str(packet_id),
            )
            return result

    def record(
        self, principal: Principal, completion_id: UUID, packet_id: UUID, root: Path
    ) -> FileOSV2LaterPacket:
        if principal.client_kind != "worker":
            raise AccessDenied("FileOS v2 later packet worker required")
        ctx = principal.context
        for scope in (
            "brain.fileos.transition.verify", "brain.changes.read", "brain.source.ingest"
        ):
            self.core.store.require(ctx, scope)
        if (
            not isinstance(completion_id, UUID)
            or not isinstance(packet_id, UUID)
            or not isinstance(root, Path)
        ):
            raise ValueError("invalid FileOS v2 later packet request")
        with self.core.store.transaction(ctx) as conn:
            existing = conn.execute(
                "SELECT actor_id,completion_id FROM brain_fileos_v2_later_observation_packets "
                "WHERE id=%s", (packet_id,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["actor_id"] != ctx.actor_id
                    or existing["completion_id"] != completion_id
                ):
                    raise Conflict("FileOS v2 later packet identity changed")
                _, result = _load_packet(conn, packet_id)
                self.core.store.audit(
                    conn, ctx, "brain.fileos_v2_later_packet_replay",
                    "fileos_v2_later_observation_packet", str(packet_id),
                )
                return result
            completion, candidate, preview, observed_at = _locked_later_observation(
                ctx, conn, completion_id, root
            )
            packet = {
                "packet_version": PACKET_VERSION,
                "publishable": False,
                "absence_authorized": False,
                "requires_review": True,
                "completion_id": str(completion_id),
                "source_id": completion["source_id"],
                "root_binding_sha256": completion["root_binding_sha256"],
                "baseline_completion_sha256": completion["completion_sha256"],
                "candidate": candidate,
                "preview": preview,
            }
            encoded = json.dumps(
                packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
            if len(encoded) > MAX_PACKET_BYTES:
                raise Conflict("FileOS v2 later packet size requires review")
            packet_sha256 = _canonical_digest(packet)
            inserted = conn.execute(
                "INSERT INTO brain_fileos_v2_later_observation_packets(tenant_id,id,"
                "actor_id,completion_id,source_id,root_binding_sha256,"
                "baseline_completion_sha256,observed_at,packet_sha256,packet) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING recorded_at",
                (
                    ctx.tenant_id, packet_id, ctx.actor_id, completion_id,
                    completion["source_id"], completion["root_binding_sha256"],
                    completion["completion_sha256"], observed_at, packet_sha256,
                    Jsonb(packet),
                ),
            ).fetchone()
            assert inserted is not None
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_packet_record",
                "fileos_v2_later_observation_packet", str(packet_id),
            )
            return FileOSV2LaterPacket(
                packet_id=packet_id,
                completion_id=completion_id,
                source_id=completion["source_id"],
                observed_at=observed_at,
                candidate_counts=dict(candidate["counts"]),
                classification_counts=dict(preview["counts"]),
                blockers=tuple(preview["blockers"]),
                packet_sha256=packet_sha256,
                recorded_at=inserted["recorded_at"],
                recorded=True,
            )
