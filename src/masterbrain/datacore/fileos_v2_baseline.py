"""Private, nonpublishing verification of one approved FileOS v2 stage.

FOS-Master 218d5caec2f20b9047fd3eb8e027dc671acf0c15 is unchanged.
The receipt is historical evidence, not current FileOS or deletion authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from email_brain.auth import Principal
from email_brain.store import AccessDenied, Conflict
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.datacore.fileos_donor_candidate import build_fileos_donor_candidate
from masterbrain.datacore.fileos_transition_approval import _load_plan
from masterbrain.datacore.persistence import (
    DataCoreStore,
    _canonical_digest,
    _fileos_v2_staged_rows,
)

VERIFICATION_VERSION = "masterbrain-fileos-v2-baseline-verification-v1"


@dataclass(frozen=True, slots=True)
class FileOSV2BaselineVerification:
    verification_id: UUID
    approval_id: UUID
    stage_id: UUID
    source_id: str
    verification_sha256: str
    fresh_observed_at: datetime
    verified_at: datetime
    recorded: bool


def _verification_sha(
    verification_id: UUID,
    approval_id: UUID,
    stage_id: UUID,
    source_id: str,
    prior_run_id: UUID,
    plan_sha256: str,
    matched_rows_sha256: str,
    fresh_observed_at: datetime,
) -> str:
    return _canonical_digest(
        {
            "version": VERIFICATION_VERSION,
            "verification_id": str(verification_id),
            "approval_id": str(approval_id),
            "stage_id": str(stage_id),
            "source_id": source_id,
            "prior_run_id": str(prior_run_id),
            "plan_sha256": plan_sha256,
            "matched_rows_sha256": matched_rows_sha256,
            "fresh_observed_at": fresh_observed_at.astimezone(UTC).isoformat(),
        }
    )


class FileOSV2BaselineVerifier:
    def __init__(self, core: DataCoreStore) -> None:
        self.core = core

    def verify(
        self,
        principal: Principal,
        stage_id: UUID,
        approval_id: UUID,
        verification_id: UUID,
        root: Path,
    ) -> FileOSV2BaselineVerification:
        if principal.client_kind != "worker":
            raise AccessDenied("FileOS baseline verification worker required")
        ctx = principal.context
        self.core.store.require(ctx, "brain.fileos.transition.verify")
        self.core.store.require(ctx, "brain.changes.read")
        if (
            not isinstance(stage_id, UUID)
            or not isinstance(approval_id, UUID)
            or not isinstance(verification_id, UUID)
            or not isinstance(root, Path)
        ):
            raise ValueError("invalid FileOS v2 baseline verification")
        with self.core.store.transaction(ctx) as conn:
            # _load_plan serializes with v1 completion and rechecks every
            # persisted stage/packet/row and current-v1 binding before scanning.
            plan, stage = _load_plan(ctx, conn, stage_id)
            if not plan["reviewable"]:
                raise Conflict("FileOS v2 baseline requires review")
            approval = conn.execute(
                "SELECT id,stage_id,packet_id,source_id,prior_run_id,packet_sha256,"
                "candidate_sha256,plan_sha256,acknowledged_counts "
                "FROM brain_fileos_v2_transition_approvals WHERE id=%s",
                (approval_id,),
            ).fetchone()
            if (
                approval is None
                or approval["stage_id"] != stage_id
                or approval["packet_id"] != stage["packet_id"]
                or approval["source_id"] != stage["source_id"]
                or approval["prior_run_id"] != stage["prior_run_id"]
                or approval["packet_sha256"] != stage["packet_sha256"]
                or approval["candidate_sha256"] != stage["candidate_sha256"]
                or approval["plan_sha256"] != plan["plan_sha256"]
                or approval["acknowledged_counts"] != plan["acknowledged_counts"]
            ):
                raise Conflict("FileOS v2 baseline approval requires review")
            packet = conn.execute(
                "SELECT packet FROM brain_fileos_transition_packets WHERE id=%s",
                (stage["packet_id"],),
            ).fetchone()
            if packet is None or not isinstance(packet["packet"], Mapping):
                raise Conflict("FileOS v2 baseline packet requires review")
            candidate = packet["packet"].get("candidate")
            if not isinstance(candidate, Mapping):
                raise Conflict("FileOS v2 baseline packet requires review")
            policy = candidate.get("policy")
            if not isinstance(policy, Mapping):
                raise Conflict("FileOS v2 baseline policy requires review")
            fresh_observed = conn.execute("SELECT clock_timestamp() AS observed_at").fetchone()
            assert fresh_observed is not None
            observed_at = fresh_observed["observed_at"]
            if observed_at <= stage["donor_observed_at"]:
                raise Conflict("FileOS v2 baseline observation requires review")
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
                raise Conflict("FileOS v2 baseline source requires review") from None
            matched_rows_sha256 = _canonical_digest(sorted(rows, key=lambda row: row[1]))
            if (
                fresh["root_binding"]["sha256"] != stage["root_binding_sha256"]
                or fresh["policy"] != policy
                or fresh["counts"] != stage["counts"]
                or fresh["counts"]["errors"] != 0
                or matched_rows_sha256 != plan["staged_rows_sha256"]
            ):
                raise Conflict("FileOS v2 baseline source changed")
            existing = conn.execute(
                "SELECT id,actor_id,approval_id,stage_id,packet_id,source_id,prior_run_id,"
                "stage_donor_observed_at,fresh_observed_at,packet_sha256,candidate_sha256,"
                "plan_sha256,matched_rows_sha256,verification_sha256,verified_at "
                "FROM brain_fileos_v2_baseline_verifications "
                "WHERE id=%s OR stage_id=%s OR source_id=%s",
                (verification_id, stage_id, stage["source_id"]),
            ).fetchone()
            if existing:
                expected_sha = _verification_sha(
                    existing["id"],
                    existing["approval_id"],
                    existing["stage_id"],
                    existing["source_id"],
                    existing["prior_run_id"],
                    existing["plan_sha256"],
                    existing["matched_rows_sha256"],
                    existing["fresh_observed_at"],
                )
                if (
                    existing["id"] != verification_id
                    or existing["actor_id"] != ctx.actor_id
                    or existing["approval_id"] != approval_id
                    or existing["stage_id"] != stage_id
                    or existing["packet_id"] != stage["packet_id"]
                    or existing["source_id"] != stage["source_id"]
                    or existing["prior_run_id"] != stage["prior_run_id"]
                    or existing["stage_donor_observed_at"] != stage["donor_observed_at"]
                    or existing["packet_sha256"] != stage["packet_sha256"]
                    or existing["candidate_sha256"] != stage["candidate_sha256"]
                    or existing["plan_sha256"] != plan["plan_sha256"]
                    or existing["matched_rows_sha256"] != matched_rows_sha256
                    or existing["verification_sha256"] != expected_sha
                ):
                    raise Conflict("FileOS v2 baseline verification identity changed")
                self.core.store.audit(
                    conn,
                    ctx,
                    "brain.fileos_v2_baseline_verification_replay",
                    "fileos_v2_baseline_verification",
                    str(verification_id),
                )
                return FileOSV2BaselineVerification(
                    verification_id,
                    approval_id,
                    stage_id,
                    stage["source_id"],
                    expected_sha,
                    existing["fresh_observed_at"],
                    existing["verified_at"],
                    False,
                )
            verification_sha256 = _verification_sha(
                verification_id,
                approval_id,
                stage_id,
                stage["source_id"],
                stage["prior_run_id"],
                plan["plan_sha256"],
                matched_rows_sha256,
                observed_at,
            )
            inserted = conn.execute(
                "INSERT INTO brain_fileos_v2_baseline_verifications(tenant_id,id,actor_id,"
                "approval_id,stage_id,packet_id,source_id,prior_run_id,"
                "stage_donor_observed_at,fresh_observed_at,packet_sha256,candidate_sha256,"
                "plan_sha256,matched_rows_sha256,verification_sha256) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING verified_at",
                (
                    ctx.tenant_id,
                    verification_id,
                    ctx.actor_id,
                    approval_id,
                    stage_id,
                    stage["packet_id"],
                    stage["source_id"],
                    stage["prior_run_id"],
                    stage["donor_observed_at"],
                    observed_at,
                    stage["packet_sha256"],
                    stage["candidate_sha256"],
                    plan["plan_sha256"],
                    matched_rows_sha256,
                    verification_sha256,
                ),
            ).fetchone()
            assert inserted is not None
            self.core.store.audit(
                conn,
                ctx,
                "brain.fileos_v2_baseline_verified",
                "fileos_v2_baseline_verification",
                str(verification_id),
            )
            return FileOSV2BaselineVerification(
                verification_id,
                approval_id,
                stage_id,
                stage["source_id"],
                verification_sha256,
                observed_at,
                inserted["verified_at"],
                True,
            )
