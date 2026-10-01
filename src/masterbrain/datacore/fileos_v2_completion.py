"""Seal an authorized FileOS v2 inventory without switching current reads.

The pinned FOS-Master donor at 218d5caec2f20b9047fd3eb8e027dc671acf0c15
is unchanged. A completed private baseline is historical evidence, not cutover.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from psycopg.types.json import Jsonb

from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.datacore.fileos_donor_candidate import build_fileos_donor_candidate
from masterbrain.datacore.fileos_transition_approval import _load_plan
from masterbrain.datacore.fileos_v2_preparation import _preparation_sha
from masterbrain.datacore.persistence import (
    _IDENTITY,
    DataCoreStore,
    _canonical_digest,
    _fileos_v2_staged_rows,
)

COMPLETION_VERSION = "masterbrain-fileos-v2-baseline-completion-v1"


@dataclass(frozen=True, slots=True)
class FileOSV2BaselineCompletion:
    completion_id: UUID
    authorization_id: UUID
    stage_id: UUID
    source_id: str
    counts: dict[str, int]
    completion_sha256: str
    fresh_observed_at: datetime
    completed_at: datetime
    recorded: bool


def _completion_sha(
    completion_id: UUID,
    authorization_id: UUID,
    preparation_id: UUID,
    stage_id: UUID,
    source_id: str,
    prior_run_id: UUID,
    plan_sha256: str,
    preparation_sha256: str,
    matched_rows_sha256: str,
    policy_sha256: str,
    root_binding_sha256: str,
    counts: Mapping[str, int],
    fresh_observed_at: datetime,
) -> str:
    return _canonical_digest(
        {
            "version": COMPLETION_VERSION,
            "completion_id": str(completion_id),
            "authorization_id": str(authorization_id),
            "preparation_id": str(preparation_id),
            "stage_id": str(stage_id),
            "source_id": source_id,
            "prior_run_id": str(prior_run_id),
            "plan_sha256": plan_sha256,
            "preparation_sha256": preparation_sha256,
            "matched_rows_sha256": matched_rows_sha256,
            "policy_sha256": policy_sha256,
            "root_binding_sha256": root_binding_sha256,
            "counts": dict(counts),
            "fresh_observed_at": fresh_observed_at.astimezone(UTC).isoformat(),
        }
    )


class FileOSV2BaselineCompleter:
    def __init__(self, core: DataCoreStore) -> None:
        self.core = core

    def inspect(self, ctx: TenantContext, source_id: str) -> dict[str, object]:
        """Read a compact private receipt; never treat it as current FileOS state."""
        self.core.store.require(ctx, "brain.changes.read")
        if not isinstance(source_id, str) or not _IDENTITY.fullmatch(source_id):
            raise NotFound()
        with self.core.store.transaction(ctx) as conn:
            row = conn.execute(
                "SELECT id,authorization_id,preparation_id,stage_id,source_id,"
                "prior_run_id,root_binding_sha256,plan_sha256,preparation_sha256,"
                "matched_rows_sha256,policy_sha256,counts,fresh_observed_at,"
                "completion_sha256,completed_at "
                "FROM brain_fileos_v2_baseline_completions WHERE source_id=%s",
                (source_id,),
            ).fetchone()
            if row is None:
                raise NotFound()
            expected_sha = _completion_sha(
                row["id"],
                row["authorization_id"],
                row["preparation_id"],
                row["stage_id"],
                row["source_id"],
                row["prior_run_id"],
                row["plan_sha256"],
                row["preparation_sha256"],
                row["matched_rows_sha256"],
                row["policy_sha256"],
                row["root_binding_sha256"],
                row["counts"],
                row["fresh_observed_at"],
            )
            if row["completion_sha256"] != expected_sha:
                raise Conflict("FileOS v2 baseline receipt integrity requires review")
            latest = conn.execute(
                "SELECT run_id,root_binding_sha256 FROM brain_fileos_run_receipts "
                "WHERE source_id=%s "
                "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
                (source_id,),
            ).fetchone()
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_baseline_read", "fileos_v2_baseline_completion",
                str(row["id"]),
            )
            return {
                "completion_id": row["id"],
                "stage_id": row["stage_id"],
                "source_id": source_id,
                "counts": dict(row["counts"]),
                "observed_at": row["fresh_observed_at"],
                "completed_at": row["completed_at"],
                "latest_v1_matches": bool(
                    latest
                    and latest["run_id"] == row["prior_run_id"]
                    and latest["root_binding_sha256"] == row["root_binding_sha256"]
                ),
                "current_read_active": False,
                "absence_authorized": False,
            }

    def complete(
        self,
        principal: Principal,
        stage_id: UUID,
        approval_id: UUID,
        preparation_id: UUID,
        authorization_id: UUID,
        completion_id: UUID,
        root: Path,
    ) -> FileOSV2BaselineCompletion:
        if principal.client_kind != "worker":
            raise AccessDenied("FileOS v2 baseline completion worker required")
        ctx = principal.context
        for scope in (
            "brain.fileos.transition.complete",
            "brain.source.ingest",
            "brain.changes.read",
        ):
            self.core.store.require(ctx, scope)
        if not all(
            isinstance(value, UUID)
            for value in (stage_id, approval_id, preparation_id, authorization_id, completion_id)
        ) or not isinstance(root, Path):
            raise ValueError("invalid FileOS v2 baseline completion")
        with self.core.store.transaction(ctx) as conn:
            plan, stage = _load_plan(ctx, conn, stage_id)
            if not plan["reviewable"]:
                raise Conflict("FileOS v2 baseline completion requires review")
            authorization = conn.execute(
                "SELECT id,preparation_id,approval_id,stage_id,source_id,prior_run_id,"
                "plan_sha256,preparation_sha256,acknowledged_counts "
                "FROM brain_fileos_v2_baseline_authorizations WHERE id=%s",
                (authorization_id,),
            ).fetchone()
            if (
                authorization is None
                or authorization["preparation_id"] != preparation_id
                or authorization["approval_id"] != approval_id
                or authorization["stage_id"] != stage_id
                or authorization["source_id"] != stage["source_id"]
                or authorization["prior_run_id"] != stage["prior_run_id"]
                or authorization["plan_sha256"] != plan["plan_sha256"]
                or authorization["acknowledged_counts"] != plan["acknowledged_counts"]
            ):
                raise Conflict("FileOS v2 baseline authorization requires review")
            preparation = conn.execute(
                "SELECT id,approval_id,verification_id,stage_id,source_id,prior_run_id,"
                "packet_sha256,candidate_sha256,plan_sha256,matched_rows_sha256,"
                "prepared_observed_at,hashed_count,preparation_sha256 "
                "FROM brain_fileos_v2_evidence_preparations WHERE id=%s",
                (preparation_id,),
            ).fetchone()
            if (
                preparation is None
                or preparation["approval_id"] != approval_id
                or preparation["stage_id"] != stage_id
                or preparation["source_id"] != stage["source_id"]
                or preparation["prior_run_id"] != stage["prior_run_id"]
                or preparation["packet_sha256"] != stage["packet_sha256"]
                or preparation["candidate_sha256"] != stage["candidate_sha256"]
                or preparation["plan_sha256"] != plan["plan_sha256"]
                or preparation["matched_rows_sha256"] != plan["staged_rows_sha256"]
                or preparation["hashed_count"] != stage["counts"]["hashed"]
                or preparation["preparation_sha256"] != authorization["preparation_sha256"]
                or preparation["preparation_sha256"]
                != _preparation_sha(
                    preparation_id,
                    preparation["verification_id"],
                    stage_id,
                    stage["source_id"],
                    stage["prior_run_id"],
                    plan["plan_sha256"],
                    plan["staged_rows_sha256"],
                    preparation["prepared_observed_at"],
                    preparation["hashed_count"],
                )
            ):
                raise Conflict("FileOS v2 baseline preparation requires review")
            packet = conn.execute(
                "SELECT packet FROM brain_fileos_transition_packets WHERE id=%s",
                (stage["packet_id"],),
            ).fetchone()
            candidate = packet["packet"].get("candidate") if packet else None
            policy = candidate.get("policy") if isinstance(candidate, Mapping) else None
            if not isinstance(policy, Mapping):
                raise Conflict("FileOS v2 baseline policy requires review")
            policy_sha256 = _canonical_digest(policy)
            observed = conn.execute("SELECT clock_timestamp() AS observed_at").fetchone()
            assert observed is not None
            observed_at = observed["observed_at"]
            if observed_at <= preparation["prepared_observed_at"]:
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
            rows_sha256 = _canonical_digest(sorted(rows, key=lambda row: row[1]))
            if (
                fresh["root_binding"]["sha256"] != stage["root_binding_sha256"]
                or fresh["policy"] != policy
                or fresh["counts"] != stage["counts"]
                or fresh["counts"]["errors"] != 0
                or rows_sha256 != plan["staged_rows_sha256"]
            ):
                raise Conflict("FileOS v2 baseline source changed")
            existing = conn.execute(
                "SELECT id,actor_id,authorization_id,preparation_id,approval_id,"
                "stage_id,source_id,prior_run_id,root_binding_sha256,plan_sha256,"
                "preparation_sha256,matched_rows_sha256,policy_sha256,counts,"
                "acknowledged_counts,hashed_count,prepared_observed_at,"
                "fresh_observed_at,completion_sha256,completed_at "
                "FROM brain_fileos_v2_baseline_completions "
                "WHERE id=%s OR stage_id=%s OR source_id=%s",
                (completion_id, stage_id, stage["source_id"]),
            ).fetchone()
            if existing is not None:
                expected_sha = _completion_sha(
                    existing["id"],
                    existing["authorization_id"],
                    existing["preparation_id"],
                    existing["stage_id"],
                    existing["source_id"],
                    existing["prior_run_id"],
                    existing["plan_sha256"],
                    existing["preparation_sha256"],
                    existing["matched_rows_sha256"],
                    existing["policy_sha256"],
                    existing["root_binding_sha256"],
                    existing["counts"],
                    existing["fresh_observed_at"],
                )
                if (
                    existing["id"] != completion_id
                    or existing["actor_id"] != ctx.actor_id
                    or existing["authorization_id"] != authorization_id
                    or existing["preparation_id"] != preparation_id
                    or existing["approval_id"] != approval_id
                    or existing["stage_id"] != stage_id
                    or existing["source_id"] != stage["source_id"]
                    or existing["prior_run_id"] != stage["prior_run_id"]
                    or existing["root_binding_sha256"] != stage["root_binding_sha256"]
                    or existing["plan_sha256"] != plan["plan_sha256"]
                    or existing["preparation_sha256"] != preparation["preparation_sha256"]
                    or existing["matched_rows_sha256"] != rows_sha256
                    or existing["policy_sha256"] != policy_sha256
                    or existing["counts"] != stage["counts"]
                    or existing["acknowledged_counts"] != plan["acknowledged_counts"]
                    or existing["hashed_count"] != stage["counts"]["hashed"]
                    or existing["prepared_observed_at"] != preparation["prepared_observed_at"]
                    or existing["completion_sha256"] != expected_sha
                ):
                    raise Conflict("FileOS v2 baseline completion identity changed")
                self.core.store.audit(
                    conn,
                    ctx,
                    "brain.fileos_v2_baseline_completion_replay",
                    "fileos_v2_baseline_completion",
                    str(completion_id),
                )
                return FileOSV2BaselineCompletion(
                    completion_id,
                    authorization_id,
                    stage_id,
                    stage["source_id"],
                    dict(existing["counts"]),
                    expected_sha,
                    existing["fresh_observed_at"],
                    existing["completed_at"],
                    False,
                )
            completion_sha256 = _completion_sha(
                completion_id,
                authorization_id,
                preparation_id,
                stage_id,
                stage["source_id"],
                stage["prior_run_id"],
                plan["plan_sha256"],
                preparation["preparation_sha256"],
                rows_sha256,
                policy_sha256,
                stage["root_binding_sha256"],
                stage["counts"],
                observed_at,
            )
            inserted = conn.execute(
                "INSERT INTO brain_fileos_v2_baseline_completions(tenant_id,id,actor_id,"
                "authorization_id,preparation_id,approval_id,stage_id,source_id,prior_run_id,"
                "root_binding_sha256,plan_sha256,preparation_sha256,matched_rows_sha256,"
                "policy_sha256,counts,acknowledged_counts,hashed_count,prepared_observed_at,"
                "fresh_observed_at,completion_sha256) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING completed_at",
                (
                    ctx.tenant_id,
                    completion_id,
                    ctx.actor_id,
                    authorization_id,
                    preparation_id,
                    approval_id,
                    stage_id,
                    stage["source_id"],
                    stage["prior_run_id"],
                    stage["root_binding_sha256"],
                    plan["plan_sha256"],
                    preparation["preparation_sha256"],
                    rows_sha256,
                    policy_sha256,
                    Jsonb(stage["counts"]),
                    Jsonb(plan["acknowledged_counts"]),
                    stage["counts"]["hashed"],
                    preparation["prepared_observed_at"],
                    observed_at,
                    completion_sha256,
                ),
            ).fetchone()
            assert inserted is not None
            self.core.store.audit(
                conn,
                ctx,
                "brain.fileos_v2_baseline_completed",
                "fileos_v2_baseline_completion",
                str(completion_id),
            )
            return FileOSV2BaselineCompletion(
                completion_id,
                authorization_id,
                stage_id,
                stage["source_id"],
                dict(stage["counts"]),
                completion_sha256,
                observed_at,
                inserted["completed_at"],
                True,
            )
