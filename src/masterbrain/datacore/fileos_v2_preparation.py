"""Prepare hashed FileOS v2 evidence without publishing a completed baseline.

FOS-Master 218d5caec2f20b9047fd3eb8e027dc671acf0c15 remains unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from psycopg.types.json import Jsonb

from email_brain.auth import Principal
from email_brain.store import AccessDenied, Conflict
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.datacore.fileos_donor_candidate import build_fileos_donor_candidate
from masterbrain.datacore.fileos_transition_approval import _load_plan
from masterbrain.datacore.fileos_v2_baseline import _verification_sha
from masterbrain.datacore.persistence import (
    DataCoreStore,
    _canonical_digest,
    _fileos_v2_staged_rows,
)

PREPARATION_VERSION = "masterbrain-fileos-v2-evidence-preparation-v1"


@dataclass(frozen=True, slots=True)
class FileOSV2EvidencePreparation:
    preparation_id: UUID
    verification_id: UUID
    stage_id: UUID
    source_id: str
    hashed_count: int
    preparation_sha256: str
    prepared_observed_at: datetime
    prepared_at: datetime
    recorded: bool


def _preparation_sha(
    preparation_id: UUID,
    verification_id: UUID,
    stage_id: UUID,
    source_id: str,
    prior_run_id: UUID,
    plan_sha256: str,
    matched_rows_sha256: str,
    prepared_observed_at: datetime,
    hashed_count: int,
) -> str:
    return _canonical_digest(
        {
            "version": PREPARATION_VERSION,
            "preparation_id": str(preparation_id),
            "verification_id": str(verification_id),
            "stage_id": str(stage_id),
            "source_id": source_id,
            "prior_run_id": str(prior_run_id),
            "plan_sha256": plan_sha256,
            "matched_rows_sha256": matched_rows_sha256,
            "prepared_observed_at": prepared_observed_at.astimezone(UTC).isoformat(),
            "hashed_count": hashed_count,
        }
    )


class FileOSV2EvidencePreparer:
    def __init__(self, core: DataCoreStore) -> None:
        self.core = core

    def prepare(
        self,
        principal: Principal,
        stage_id: UUID,
        approval_id: UUID,
        verification_id: UUID,
        preparation_id: UUID,
        root: Path,
    ) -> FileOSV2EvidencePreparation:
        if principal.client_kind != "worker":
            raise AccessDenied("FileOS v2 evidence preparation worker required")
        ctx = principal.context
        for scope in (
            "brain.fileos.transition.prepare",
            "brain.source.ingest",
            "brain.changes.read",
        ):
            self.core.store.require(ctx, scope)
        if not all(
            isinstance(value, UUID)
            for value in (stage_id, approval_id, verification_id, preparation_id)
        ) or not isinstance(root, Path):
            raise ValueError("invalid FileOS v2 evidence preparation")
        with self.core.store.transaction(ctx) as conn:
            # _load_plan takes the source completion lock and validates the
            # current v1 receipt, packet, stage, rows and review blockers.
            plan, stage = _load_plan(ctx, conn, stage_id)
            if not plan["reviewable"]:
                raise Conflict("FileOS v2 evidence preparation requires review")
            approval = conn.execute(
                "SELECT id,stage_id,source_id,prior_run_id,packet_sha256,"
                "candidate_sha256,plan_sha256,acknowledged_counts "
                "FROM brain_fileos_v2_transition_approvals WHERE id=%s",
                (approval_id,),
            ).fetchone()
            if (
                approval is None
                or approval["stage_id"] != stage_id
                or approval["source_id"] != stage["source_id"]
                or approval["prior_run_id"] != stage["prior_run_id"]
                or approval["packet_sha256"] != stage["packet_sha256"]
                or approval["candidate_sha256"] != stage["candidate_sha256"]
                or approval["plan_sha256"] != plan["plan_sha256"]
                or approval["acknowledged_counts"] != plan["acknowledged_counts"]
            ):
                raise Conflict("FileOS v2 evidence approval requires review")
            verified = conn.execute(
                "SELECT id,approval_id,stage_id,source_id,prior_run_id,"
                "packet_sha256,candidate_sha256,plan_sha256,matched_rows_sha256,"
                "verification_sha256,fresh_observed_at "
                "FROM brain_fileos_v2_baseline_verifications WHERE id=%s",
                (verification_id,),
            ).fetchone()
            if (
                verified is None
                or verified["approval_id"] != approval_id
                or verified["stage_id"] != stage_id
                or verified["source_id"] != stage["source_id"]
                or verified["prior_run_id"] != stage["prior_run_id"]
                or verified["packet_sha256"] != stage["packet_sha256"]
                or verified["candidate_sha256"] != stage["candidate_sha256"]
                or verified["plan_sha256"] != plan["plan_sha256"]
                or verified["matched_rows_sha256"] != plan["staged_rows_sha256"]
                or verified["verification_sha256"]
                != _verification_sha(
                    verification_id,
                    approval_id,
                    stage_id,
                    stage["source_id"],
                    stage["prior_run_id"],
                    plan["plan_sha256"],
                    plan["staged_rows_sha256"],
                    verified["fresh_observed_at"],
                )
            ):
                raise Conflict("FileOS v2 evidence verification requires review")
            packet = conn.execute(
                "SELECT packet FROM brain_fileos_transition_packets WHERE id=%s",
                (stage["packet_id"],),
            ).fetchone()
            candidate = packet["packet"].get("candidate") if packet else None
            policy = candidate.get("policy") if isinstance(candidate, Mapping) else None
            if not isinstance(policy, Mapping):
                raise Conflict("FileOS v2 evidence policy requires review")
            policy_sha256 = _canonical_digest(policy)
            observed = conn.execute("SELECT clock_timestamp() AS observed_at").fetchone()
            assert observed is not None
            observed_at = observed["observed_at"]
            if observed_at <= verified["fresh_observed_at"]:
                raise Conflict("FileOS v2 evidence observation requires review")
            try:
                if fileos_root_binding_sha256(root) != stage["root_binding_sha256"]:
                    raise ValueError("wrong source root")
                fresh = build_fileos_donor_candidate(
                    root,
                    source_id=stage["source_id"],
                    observed_at=observed_at,
                    metadata_only=policy["metadata_only"],
                )
                rows = _fileos_v2_staged_rows(fresh, stage["source_id"])
            except (OSError, RuntimeError, TypeError, ValueError, KeyError):
                raise Conflict("FileOS v2 evidence source requires review") from None
            rows_sha = _canonical_digest(sorted(rows, key=lambda row: row[1]))
            if (
                fresh["root_binding"]["sha256"] != stage["root_binding_sha256"]
                or fresh["policy"] != policy
                or fresh["counts"] != stage["counts"]
                or fresh["counts"]["errors"] != 0
                or rows_sha != plan["staged_rows_sha256"]
            ):
                raise Conflict("FileOS v2 evidence source changed")
            existing = conn.execute(
                "SELECT id,actor_id,verification_id,approval_id,stage_id,source_id,"
                "prior_run_id,packet_sha256,candidate_sha256,plan_sha256,"
                "matched_rows_sha256,verification_observed_at,prepared_observed_at,"
                "hashed_count,preparation_sha256,prepared_at "
                "FROM brain_fileos_v2_evidence_preparations "
                "WHERE id=%s OR stage_id=%s OR source_id=%s",
                (preparation_id, stage_id, stage["source_id"]),
            ).fetchone()
            hashed_count = stage["counts"]["hashed"]
            if existing is not None:
                expected_sha = _preparation_sha(
                    existing["id"],
                    existing["verification_id"],
                    existing["stage_id"],
                    existing["source_id"],
                    existing["prior_run_id"],
                    existing["plan_sha256"],
                    existing["matched_rows_sha256"],
                    existing["prepared_observed_at"],
                    existing["hashed_count"],
                )
                if (
                    existing["id"] != preparation_id
                    or existing["actor_id"] != ctx.actor_id
                    or existing["verification_id"] != verification_id
                    or existing["approval_id"] != approval_id
                    or existing["stage_id"] != stage_id
                    or existing["source_id"] != stage["source_id"]
                    or existing["prior_run_id"] != stage["prior_run_id"]
                    or existing["packet_sha256"] != stage["packet_sha256"]
                    or existing["candidate_sha256"] != stage["candidate_sha256"]
                    or existing["plan_sha256"] != plan["plan_sha256"]
                    or existing["matched_rows_sha256"] != rows_sha
                    or existing["verification_observed_at"] != verified["fresh_observed_at"]
                    or existing["hashed_count"] != hashed_count
                    or existing["preparation_sha256"] != expected_sha
                ):
                    raise Conflict("FileOS v2 evidence preparation identity changed")
                self.core.store.audit(
                    conn,
                    ctx,
                    "brain.fileos_v2_evidence_preparation_replay",
                    "fileos_v2_preparation",
                    str(preparation_id),
                )
                return FileOSV2EvidencePreparation(
                    preparation_id,
                    verification_id,
                    stage_id,
                    stage["source_id"],
                    hashed_count,
                    expected_sha,
                    existing["prepared_observed_at"],
                    existing["prepared_at"],
                    False,
                )
            for kind, locator, item_id, version_id, sha256, size, media, _reason in rows:
                if kind != "hashed":
                    continue
                if (
                    item_id is None
                    or version_id is None
                    or sha256 is None
                    or size is None
                    or media is None
                ):
                    raise Conflict("FileOS v2 evidence row requires review")
                conn.execute(
                    "INSERT INTO brain_source_items(tenant_id,source_id,id,locator,"
                    "first_seen_at,last_seen_at) VALUES (%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT DO NOTHING",
                    (ctx.tenant_id, stage["source_id"], item_id, locator, observed_at, observed_at),
                )
                saved_item = conn.execute(
                    "SELECT source_id,locator FROM brain_source_items WHERE id=%s FOR UPDATE",
                    (item_id,),
                ).fetchone()
                if saved_item != {"source_id": stage["source_id"], "locator": locator}:
                    raise Conflict("FileOS v2 source item identity changed")
                prepared_version_id = stable_id("fileos_v2_version", version_id, policy_sha256)
                version_metadata = {
                    "inventory_policy_sha256": policy_sha256,
                    "candidate_version_id": version_id,
                }
                conn.execute(
                    "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,"
                    "observed_at,sha256,size_bytes,media_type,metadata) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (
                        ctx.tenant_id,
                        stage["source_id"],
                        item_id,
                        prepared_version_id,
                        observed_at,
                        sha256,
                        size,
                        media,
                        Jsonb(version_metadata),
                    ),
                )
                saved_version = conn.execute(
                    "SELECT source_id,item_id,sha256,size_bytes,media_type,metadata "
                    "FROM brain_source_versions WHERE id=%s",
                    (prepared_version_id,),
                ).fetchone()
                if saved_version != {
                    "source_id": stage["source_id"],
                    "item_id": item_id,
                    "sha256": sha256,
                    "size_bytes": size,
                    "media_type": media,
                    "metadata": version_metadata,
                }:
                    raise Conflict("FileOS v2 source version identity changed")
                evidence_id = stable_id("evidence", prepared_version_id)
                conn.execute(
                    "INSERT INTO brain_evidence(tenant_id,id,source_version_id,sha256,"
                    "storage,retained) VALUES (%s,%s,%s,%s,'source_bound',false) "
                    "ON CONFLICT DO NOTHING",
                    (ctx.tenant_id, evidence_id, prepared_version_id, sha256),
                )
                saved_evidence = conn.execute(
                    "SELECT id,source_version_id,sha256,storage,retained "
                    "FROM brain_evidence WHERE id=%s",
                    (evidence_id,),
                ).fetchone()
                if saved_evidence != {
                    "id": evidence_id,
                    "source_version_id": prepared_version_id,
                    "sha256": sha256,
                    "storage": "source_bound",
                    "retained": False,
                }:
                    raise Conflict("FileOS v2 evidence identity changed")
                conn.execute(
                    "INSERT INTO brain_fileos_v2_prepared_rows(tenant_id,stage_id,source_id,"
                    "locator,item_id,candidate_version_id,prepared_version_id,evidence_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id,
                        stage_id,
                        stage["source_id"],
                        locator,
                        item_id,
                        version_id,
                        prepared_version_id,
                        evidence_id,
                    ),
                )
            preparation_sha256 = _preparation_sha(
                preparation_id,
                verification_id,
                stage_id,
                stage["source_id"],
                stage["prior_run_id"],
                plan["plan_sha256"],
                rows_sha,
                observed_at,
                hashed_count,
            )
            inserted = conn.execute(
                "INSERT INTO brain_fileos_v2_evidence_preparations(tenant_id,id,actor_id,"
                "verification_id,approval_id,stage_id,source_id,prior_run_id,"
                "packet_sha256,candidate_sha256,plan_sha256,matched_rows_sha256,"
                "verification_observed_at,prepared_observed_at,hashed_count,"
                "preparation_sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING prepared_at",
                (
                    ctx.tenant_id,
                    preparation_id,
                    ctx.actor_id,
                    verification_id,
                    approval_id,
                    stage_id,
                    stage["source_id"],
                    stage["prior_run_id"],
                    stage["packet_sha256"],
                    stage["candidate_sha256"],
                    plan["plan_sha256"],
                    rows_sha,
                    verified["fresh_observed_at"],
                    observed_at,
                    hashed_count,
                    preparation_sha256,
                ),
            ).fetchone()
            assert inserted is not None
            self.core.store.audit(
                conn,
                ctx,
                "brain.fileos_v2_evidence_prepared",
                "fileos_v2_preparation",
                str(preparation_id),
            )
            return FileOSV2EvidencePreparation(
                preparation_id,
                verification_id,
                stage_id,
                stage["source_id"],
                hashed_count,
                preparation_sha256,
                observed_at,
                inserted["prepared_at"],
                True,
            )
