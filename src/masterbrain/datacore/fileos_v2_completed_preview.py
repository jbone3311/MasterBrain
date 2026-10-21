"""Private later-observation preview bound to one completed FileOS v2 baseline.

FOS-Master 218d5caec2f20b9047fd3eb8e027dc671acf0c15 remains unchanged.
This operation never completes a later run or authorizes absence/current reads.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from psycopg import Connection

from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.datacore.fileos_donor_candidate import build_fileos_donor_candidate
from masterbrain.datacore.fileos_transition_approval import _load_plan
from masterbrain.datacore.fileos_v2_completion import _completion_sha
from masterbrain.datacore.fileos_v2_consecutive_preview import (
    preview_fileos_v2_consecutive_observations,
)
from masterbrain.datacore.persistence import DataCoreStore, _canonical_digest


@dataclass(frozen=True, slots=True)
class FileOSV2CompletedPreview:
    completion_id: UUID
    source_id: str
    baseline_observed_at: datetime
    later_observed_at: datetime
    counts: dict[str, int]
    current_only_hashed: int
    current_only_deferred: int
    blockers: tuple[str, ...]
    preview_sha256: str
    publishable: bool = False
    absence_authorized: bool = False


def _locked_later_observation(
    ctx: TenantContext,
    conn: Connection[dict[str, Any]],
    completion_id: UUID,
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], datetime]:
    """Under one source-locked transaction, recheck and scan the exact baseline."""
    completion = conn.execute(
        "SELECT id,authorization_id,preparation_id,stage_id,source_id,"
        "prior_run_id,root_binding_sha256,plan_sha256,preparation_sha256,"
        "matched_rows_sha256,policy_sha256,counts,fresh_observed_at,"
        "completion_sha256 FROM brain_fileos_v2_baseline_completions WHERE id=%s",
        (completion_id,),
    ).fetchone()
    if completion is None:
        raise NotFound()
    plan, stage = _load_plan(ctx, conn, completion["stage_id"])
    if not plan["reviewable"]:
        raise Conflict("FileOS v2 preview basis requires review")
    try:
        expected_sha = _completion_sha(
            completion["id"], completion["authorization_id"], completion["preparation_id"],
            completion["stage_id"], completion["source_id"], completion["prior_run_id"],
            completion["plan_sha256"], completion["preparation_sha256"],
            completion["matched_rows_sha256"], completion["policy_sha256"],
            completion["root_binding_sha256"], completion["counts"],
            completion["fresh_observed_at"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise Conflict("FileOS v2 completion integrity requires review") from exc
    if (
        completion["completion_sha256"] != expected_sha
        or completion["source_id"] != stage["source_id"]
        or completion["prior_run_id"] != stage["prior_run_id"]
        or completion["root_binding_sha256"] != stage["root_binding_sha256"]
        or completion["counts"] != stage["counts"]
        or completion["plan_sha256"] != plan["plan_sha256"]
    ):
        raise Conflict("FileOS v2 completion integrity requires review")
    packet_row = conn.execute(
        "SELECT packet FROM brain_fileos_transition_packets WHERE id=%s",
        (stage["packet_id"],),
    ).fetchone()
    packet = packet_row["packet"] if packet_row else None
    prior = packet.get("candidate") if isinstance(packet, Mapping) else None
    if not isinstance(prior, Mapping):
        raise Conflict("FileOS v2 baseline candidate requires review")
    observed_row = conn.execute("SELECT clock_timestamp() AS observed_at").fetchone()
    assert observed_row is not None
    observed_at = observed_row["observed_at"]
    if observed_at <= completion["fresh_observed_at"]:
        raise Conflict("FileOS v2 preview observation requires review")
    try:
        binding = fileos_root_binding_sha256(root)
        if binding != completion["root_binding_sha256"]:
            raise ValueError("wrong source root")
        current = build_fileos_donor_candidate(
            root,
            source_id=completion["source_id"],
            observed_at=observed_at,
            metadata_only=prior["policy"]["metadata_only"],
        )
        if fileos_root_binding_sha256(root) != binding:
            raise ValueError("root changed")
        full_preview = preview_fileos_v2_consecutive_observations(prior, current)
    except (KeyError, OSError, RuntimeError, TypeError, ValueError):
        raise Conflict("FileOS v2 preview source requires review") from None
    return completion, current, full_preview, observed_at


class FileOSV2CompletedPreviewer:
    def __init__(self, core: DataCoreStore) -> None:
        self.core = core

    def preview(
        self, principal: Principal, completion_id: UUID, root: Path
    ) -> FileOSV2CompletedPreview:
        if principal.client_kind != "worker":
            raise AccessDenied("FileOS v2 preview worker required")
        ctx = principal.context
        self.core.store.require(ctx, "brain.fileos.transition.verify")
        self.core.store.require(ctx, "brain.changes.read")
        if not isinstance(completion_id, UUID) or not isinstance(root, Path):
            raise ValueError("invalid FileOS v2 preview request")
        with self.core.store.transaction(ctx) as conn:
            completion, _, full_preview, observed_at = _locked_later_observation(
                ctx, conn, completion_id, root
            )
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_preview_read",
                "fileos_v2_baseline_completion", str(completion_id),
            )
            return FileOSV2CompletedPreview(
                completion_id=completion_id,
                source_id=completion["source_id"],
                baseline_observed_at=completion["fresh_observed_at"],
                later_observed_at=observed_at,
                counts=dict(full_preview["counts"]),
                current_only_hashed=full_preview["current_only_hashed"],
                current_only_deferred=full_preview["current_only_deferred"],
                blockers=tuple(full_preview["blockers"]),
                preview_sha256=_canonical_digest(full_preview),
            )
