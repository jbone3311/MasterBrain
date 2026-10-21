"""Prepare later FileOS v2 hashed evidence without current-read authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from psycopg import Connection

from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.datacore.fileos_v2_completed_preview import _locked_later_observation
from masterbrain.datacore.fileos_v2_later_coverage import FileOSV2LaterCoverageStore
from masterbrain.datacore.fileos_v2_later_packets import _load_packet
from masterbrain.datacore.fileos_v2_preparation import _ensure_hashed_evidence
from masterbrain.datacore.persistence import (
    DataCoreStore,
    _canonical_digest,
    _fileos_v2_staged_rows,
)

PREPARATION_VERSION = "masterbrain-fileos-v2-later-evidence-preparation-v1"


@dataclass(frozen=True, slots=True)
class FileOSV2LaterEvidencePreparation:
    preparation_id: UUID
    closure_id: UUID
    packet_id: UUID
    source_id: str
    hashed_count: int
    matched_rows_sha256: str
    preparation_sha256: str
    prepared_observed_at: datetime
    prepared_at: datetime
    recorded: bool
    publishable: bool = False
    absence_authorized: bool = False


def _preparation_sha(
    preparation_id: UUID,
    closure_id: UUID,
    packet_id: UUID,
    completion_id: UUID,
    source_id: str,
    packet_sha256: str,
    closure_sha256: str,
    policy_sha256: str,
    matched_rows_sha256: str,
    root_binding_sha256: str,
    hashed_count: int,
    prepared_observed_at: datetime,
) -> str:
    return _canonical_digest({
        "version": PREPARATION_VERSION,
        "preparation_id": str(preparation_id),
        "closure_id": str(closure_id),
        "packet_id": str(packet_id),
        "completion_id": str(completion_id),
        "source_id": source_id,
        "packet_sha256": packet_sha256,
        "closure_sha256": closure_sha256,
        "policy_sha256": policy_sha256,
        "matched_rows_sha256": matched_rows_sha256,
        "root_binding_sha256": root_binding_sha256,
        "hashed_count": hashed_count,
        "prepared_observed_at": prepared_observed_at.astimezone(UTC).isoformat(),
    })


class FileOSV2LaterEvidencePreparer:
    def __init__(self, core: DataCoreStore) -> None:
        self.core = core
        self.coverage = FileOSV2LaterCoverageStore(core)

    def _inspect_locked(
        self, conn: Connection[dict[str, Any]], preparation_id: UUID
    ) -> FileOSV2LaterEvidencePreparation:
        saved = conn.execute(
            "SELECT id,actor_id,closure_id,packet_id,completion_id,source_id,"
            "root_binding_sha256,packet_sha256,closure_sha256,policy_sha256,"
            "matched_rows_sha256,packet_observed_at,prepared_observed_at,"
            "hashed_count,preparation_sha256,prepared_at "
            "FROM brain_fileos_v2_later_evidence_preparations WHERE id=%s",
            (preparation_id,),
        ).fetchone()
        if saved is None:
            raise NotFound()
        coverage = self.coverage._inspect_locked(conn, saved["closure_id"])
        packet_row, _ = _load_packet(conn, saved["packet_id"])
        try:
            candidate = packet_row["packet"]["candidate"]
            rows = sorted(
                _fileos_v2_staged_rows(candidate, saved["source_id"]),
                key=lambda row: row[1],
            )
            expected_hashed = [row for row in rows if row[0] == "hashed"]
            prepared = conn.execute(
                "SELECT r.locator,r.item_id,r.candidate_version_id,"
                "r.prepared_version_id,r.evidence_id,r.sha256,r.size_bytes,"
                "r.media_type,v.source_id AS version_source,v.item_id AS version_item,"
                "v.sha256 AS version_sha,v.size_bytes AS version_size,"
                "v.media_type AS version_media,v.metadata,e.source_version_id,"
                "e.sha256 AS evidence_sha,e.storage,e.retained "
                "FROM brain_fileos_v2_later_prepared_rows r "
                "JOIN brain_source_versions v ON v.tenant_id=r.tenant_id "
                "AND v.id=r.prepared_version_id "
                "JOIN brain_evidence e ON e.tenant_id=r.tenant_id "
                "AND e.id=r.evidence_id "
                "WHERE r.preparation_id=%s ORDER BY r.locator COLLATE \"C\"",
                (preparation_id,),
            ).fetchall()
            policy_sha = _canonical_digest(candidate["policy"])
            if (
                saved["packet_id"] != packet_row["id"]
                or saved["closure_sha256"] != coverage.closure_sha256
                or coverage.packet_id != saved["packet_id"]
                or saved["completion_id"] != packet_row["completion_id"]
                or saved["source_id"] != packet_row["source_id"]
                or saved["root_binding_sha256"] != packet_row["root_binding_sha256"]
                or saved["packet_sha256"] != packet_row["packet_sha256"]
                or saved["packet_observed_at"] != packet_row["observed_at"]
                or saved["policy_sha256"] != policy_sha
                or saved["matched_rows_sha256"] != _canonical_digest(rows)
                or saved["hashed_count"] != len(expected_hashed)
                or len(prepared) != len(expected_hashed)
                or saved["preparation_sha256"] != _preparation_sha(
                    saved["id"], saved["closure_id"], saved["packet_id"],
                    saved["completion_id"], saved["source_id"],
                    saved["packet_sha256"], saved["closure_sha256"],
                    saved["policy_sha256"], saved["matched_rows_sha256"],
                    saved["root_binding_sha256"], saved["hashed_count"],
                    saved["prepared_observed_at"],
                )
            ):
                raise ValueError("preparation identity")
            for expected, item in zip(expected_hashed, prepared, strict=True):
                _, locator, item_id, version_id, sha, size, media, _ = expected
                if (
                    item_id is None or version_id is None or sha is None
                    or size is None or media is None
                ):
                    raise ValueError("hashed row identity")
                if (
                    item["locator"] != locator
                    or item["item_id"] != item_id
                    or item["candidate_version_id"] != version_id
                    or item["prepared_version_id"] != stable_id(
                        "fileos_v2_version", version_id, policy_sha
                    )
                    or item["evidence_id"] != stable_id(
                        "evidence", item["prepared_version_id"]
                    )
                    or item["sha256"] != sha
                    or item["size_bytes"] != size
                    or item["media_type"] != media
                    or item["version_source"] != saved["source_id"]
                    or item["version_item"] != item_id
                    or item["version_sha"] != sha
                    or item["version_size"] != size
                    or item["version_media"] != media
                    or item["metadata"] != {
                        "inventory_policy_sha256": policy_sha,
                        "candidate_version_id": version_id,
                    }
                    or item["source_version_id"] != item["prepared_version_id"]
                    or item["evidence_sha"] != sha
                    or item["storage"] != "source_bound"
                    or item["retained"] is not False
                ):
                    raise ValueError("prepared row identity")
        except (KeyError, TypeError, ValueError) as exc:
            raise Conflict("FileOS v2 later evidence integrity requires review") from exc
        return FileOSV2LaterEvidencePreparation(
            preparation_id=saved["id"],
            closure_id=saved["closure_id"],
            packet_id=saved["packet_id"],
            source_id=saved["source_id"],
            hashed_count=saved["hashed_count"],
            matched_rows_sha256=saved["matched_rows_sha256"],
            preparation_sha256=saved["preparation_sha256"],
            prepared_observed_at=saved["prepared_observed_at"],
            prepared_at=saved["prepared_at"],
            recorded=False,
        )

    def inspect(
        self, ctx: TenantContext, preparation_id: UUID
    ) -> FileOSV2LaterEvidencePreparation:
        self.core.store.require(ctx, "brain.changes.read")
        if not isinstance(preparation_id, UUID):
            raise ValueError("invalid FileOS v2 later evidence identity")
        with self.core.store.transaction(ctx) as conn:
            result = self._inspect_locked(conn, preparation_id)
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_evidence_read",
                "fileos_v2_later_evidence_preparation", str(preparation_id),
            )
            return result

    def prepare(
        self, principal: Principal, closure_id: UUID, preparation_id: UUID, root: Path
    ) -> FileOSV2LaterEvidencePreparation:
        if principal.client_kind != "worker":
            raise AccessDenied("FileOS v2 later evidence worker required")
        ctx = principal.context
        for scope in (
            "brain.fileos.transition.prepare", "brain.source.ingest", "brain.changes.read"
        ):
            self.core.store.require(ctx, scope)
        if (
            not isinstance(closure_id, UUID)
            or not isinstance(preparation_id, UUID)
            or not isinstance(root, Path)
        ):
            raise ValueError("invalid FileOS v2 later evidence request")
        with self.core.store.transaction(ctx) as conn:
            existing = conn.execute(
                "SELECT id,actor_id,closure_id,root_binding_sha256 "
                "FROM brain_fileos_v2_later_evidence_preparations "
                "WHERE id=%s OR closure_id=%s",
                (preparation_id, closure_id),
            ).fetchone()
            if existing is not None:
                if (
                    existing["id"] != preparation_id
                    or existing["actor_id"] != ctx.actor_id
                    or existing["closure_id"] != closure_id
                    or fileos_root_binding_sha256(root)
                    != existing["root_binding_sha256"]
                ):
                    raise Conflict("FileOS v2 later evidence identity changed")
                result = self._inspect_locked(conn, preparation_id)
                self.core.store.audit(
                    conn, ctx, "brain.fileos_v2_later_evidence_replay",
                    "fileos_v2_later_evidence_preparation", str(preparation_id),
                )
                return result
            coverage = self.coverage._inspect_locked(conn, closure_id)
            closure_row = conn.execute(
                "SELECT packet_id,closure_sha256 FROM "
                "brain_fileos_v2_later_coverage_closures WHERE id=%s",
                (closure_id,),
            ).fetchone()
            assert closure_row is not None
            packet_row, _ = _load_packet(conn, closure_row["packet_id"])
            completion, fresh, _preview, observed_at = _locked_later_observation(
                ctx, conn, packet_row["completion_id"], root
            )
            candidate = packet_row["packet"]["candidate"]
            try:
                rows = sorted(
                    _fileos_v2_staged_rows(candidate, packet_row["source_id"]),
                    key=lambda row: row[1],
                )
                fresh_rows = sorted(
                    _fileos_v2_staged_rows(fresh, packet_row["source_id"]),
                    key=lambda row: row[1],
                )
                if (
                    completion["id"] != packet_row["completion_id"]
                    or closure_row["closure_sha256"] != coverage.closure_sha256
                    or fresh["policy"] != candidate["policy"]
                    or fresh["root_binding"] != candidate["root_binding"]
                    or fresh_rows != rows
                    or candidate["counts"]["errors"] != 0
                    or fresh["counts"]["errors"] != 0
                    or observed_at <= packet_row["observed_at"]
                ):
                    raise ValueError("later observation drift")
            except (KeyError, TypeError, ValueError) as exc:
                raise Conflict("FileOS v2 later evidence source changed") from exc
            policy_sha = _canonical_digest(candidate["policy"])
            rows_sha = _canonical_digest(rows)
            hashed_count = candidate["counts"]["hashed"]
            for kind, locator, item_id, version_id, sha, size, media, _reason in rows:
                if kind != "hashed":
                    continue
                if (
                    item_id is None or version_id is None or sha is None
                    or size is None or media is None
                ):
                    raise Conflict("FileOS v2 later evidence row requires review")
                prepared_version_id, evidence_id = _ensure_hashed_evidence(
                    conn, ctx.tenant_id, packet_row["source_id"], locator, item_id,
                    version_id, sha, size, media, policy_sha, observed_at,
                )
                conn.execute(
                    "INSERT INTO brain_fileos_v2_later_prepared_rows(tenant_id,"
                    "preparation_id,source_id,locator,item_id,candidate_version_id,"
                    "prepared_version_id,evidence_id,sha256,size_bytes,media_type) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id, preparation_id, packet_row["source_id"],
                        locator, item_id, version_id, prepared_version_id, evidence_id,
                        sha, size, media,
                    ),
                )
            digest = _preparation_sha(
                preparation_id, closure_id, packet_row["id"], completion["id"],
                packet_row["source_id"], packet_row["packet_sha256"],
                coverage.closure_sha256, policy_sha, rows_sha,
                packet_row["root_binding_sha256"], hashed_count, observed_at,
            )
            inserted = conn.execute(
                "INSERT INTO brain_fileos_v2_later_evidence_preparations(tenant_id,id,"
                "actor_id,closure_id,packet_id,completion_id,source_id,"
                "root_binding_sha256,packet_sha256,closure_sha256,policy_sha256,"
                "matched_rows_sha256,packet_observed_at,prepared_observed_at,"
                "hashed_count,preparation_sha256) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING prepared_at",
                (
                    ctx.tenant_id, preparation_id, ctx.actor_id, closure_id,
                    packet_row["id"], completion["id"], packet_row["source_id"],
                    packet_row["root_binding_sha256"], packet_row["packet_sha256"],
                    coverage.closure_sha256, policy_sha, rows_sha,
                    packet_row["observed_at"], observed_at, hashed_count, digest,
                ),
            ).fetchone()
            assert inserted is not None
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_evidence_prepared",
                "fileos_v2_later_evidence_preparation", str(preparation_id),
            )
            return FileOSV2LaterEvidencePreparation(
                preparation_id=preparation_id,
                closure_id=closure_id,
                packet_id=packet_row["id"],
                source_id=packet_row["source_id"],
                hashed_count=hashed_count,
                matched_rows_sha256=rows_sha,
                preparation_sha256=digest,
                prepared_observed_at=observed_at,
                prepared_at=inserted["prepared_at"],
                recorded=True,
            )
