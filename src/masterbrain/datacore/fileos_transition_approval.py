"""Private, nonpublishing human review of one sealed FileOS v2 stage."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound
from masterbrain.datacore.persistence import (
    DataCoreStore,
    _canonical_digest,
    _fileos_v2_staged_rows,
)

PLAN_VERSION = "masterbrain-fileos-v2-transition-plan-v1"
_PRIOR_STATES = frozenset(
    {
        "unchanged",
        "changed",
        "deferred_prior",
        "excluded_prior",
        "error_covered_prior",
        "unobserved_prior",
    }
)
_BLOCKERS = frozenset(
    {
        "prior_snapshot_errors",
        "donor_scan_errors",
        "prior_item_not_hashed_under_donor_policy",
    }
)
_ROW_FIELDS = (
    "kind",
    "locator",
    "item_id",
    "version_id",
    "sha256",
    "size_bytes",
    "media_type",
    "reason",
)


@dataclass(frozen=True, slots=True)
class FileOSV2ApprovalRecord:
    approval_id: UUID
    stage_id: UUID
    source_id: str
    plan_sha256: str
    approved_at: datetime
    recorded: bool


def _load_plan(
    ctx: TenantContext, conn: Connection[dict[str, Any]], stage_id: UUID
) -> tuple[dict[str, Any], dict[str, Any]]:
    stage = conn.execute(
        "SELECT id,packet_id,source_id,prior_actor_id,prior_run_id,prior_observed_at,"
        "donor_observed_at,root_binding_sha256,packet_sha256,candidate_sha256,counts "
        "FROM brain_fileos_v2_staged_inventories WHERE id=%s",
        (stage_id,),
    ).fetchone()
    if stage is None:
        raise NotFound()
    source_id = stage["source_id"]
    conn.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"{ctx.tenant_id}:fileos-source:{source_id}",),
    )
    packet_row = conn.execute(
        "SELECT id,source_id,prior_actor_id,prior_run_id,prior_observed_at,"
        "donor_observed_at,root_binding_sha256,packet_sha256,packet "
        "FROM brain_fileos_transition_packets WHERE id=%s",
        (stage["packet_id"],),
    ).fetchone()
    if packet_row is None:
        raise Conflict("FileOS v2 transition stage requires review")
    packet = packet_row["packet"]
    if (
        not isinstance(packet, Mapping)
        or _canonical_digest(packet) != stage["packet_sha256"]
        or packet_row["packet_sha256"] != stage["packet_sha256"]
        or any(
            packet_row[key] != stage[key]
            for key in (
                "source_id",
                "prior_actor_id",
                "prior_run_id",
                "prior_observed_at",
                "donor_observed_at",
                "root_binding_sha256",
            )
        )
        or packet.get("packet_version") != "masterbrain-fileos-transition-review-packet-v1"
        or packet.get("publishable") is not False
        or packet.get("requires_review") is not True
    ):
        raise Conflict("FileOS v2 transition packet integrity requires review")
    candidate = packet.get("candidate")
    preview = packet.get("preview")
    if not isinstance(candidate, Mapping) or not isinstance(preview, Mapping):
        raise Conflict("FileOS v2 transition packet integrity requires review")
    try:
        expected_rows = _fileos_v2_staged_rows(candidate, source_id)
        actual_rows = conn.execute(
            "SELECT kind,locator,item_id,version_id,sha256,size_bytes,media_type,reason "
            "FROM brain_fileos_v2_staged_rows WHERE stage_id=%s ORDER BY locator",
            (stage_id,),
        ).fetchall()
        actual_tuples = [tuple(row[field] for field in _ROW_FIELDS) for row in actual_rows]
        if (
            _canonical_digest(candidate) != stage["candidate_sha256"]
            or candidate.get("counts") != stage["counts"]
            or sorted(expected_rows, key=lambda row: row[1]) != actual_tuples
            or preview.get("candidate_counts") != candidate["counts"]
            or preview.get("source_id") != source_id
            or preview.get("prior_observed_at")
            != stage["prior_observed_at"].astimezone(UTC).isoformat()
            or preview.get("donor_observed_at")
            != stage["donor_observed_at"].astimezone(UTC).isoformat()
            or preview.get("root_binding") != candidate.get("root_binding")
        ):
            raise ValueError("staged row mismatch")
        counts = preview.get("counts")
        prior_rows = preview.get("prior_items")
        donor_only = preview.get("donor_only_hashed")
        blockers = preview.get("blockers")
        if (
            not isinstance(counts, Mapping)
            or set(counts) != _PRIOR_STATES | {"donor_only_hashed"}
            or any(type(value) is not int or value < 0 for value in counts.values())
            or not isinstance(prior_rows, list)
            or not isinstance(donor_only, list)
            or not isinstance(blockers, list)
            or any(value not in _BLOCKERS for value in blockers)
            or len(blockers) != len(set(blockers))
            or counts["donor_only_hashed"] != len(donor_only)
        ):
            raise ValueError("invalid transition classification")
        prior_db = conn.execute(
            "SELECT i.item_id,i.version_id,s.locator FROM brain_fileos_run_items i "
            "JOIN brain_source_items s ON s.tenant_id=i.tenant_id "
            "AND s.source_id=i.source_id AND s.id=i.item_id "
            "WHERE i.actor_id=%s AND i.run_id=%s AND i.source_id=%s ORDER BY s.locator",
            (stage["prior_actor_id"], stage["prior_run_id"], source_id),
        ).fetchall()
        if len(prior_rows) != len(prior_db):
            raise ValueError("prior ledger mismatch")
        observed_states: Counter[str] = Counter()
        for saved, current in zip(prior_rows, prior_db, strict=True):
            if (
                not isinstance(saved, Mapping)
                or saved.get("locator") != current["locator"]
                or saved.get("item_id") != current["item_id"]
                or saved.get("prior_version_id") != current["version_id"]
                or saved.get("state") not in _PRIOR_STATES
            ):
                raise ValueError("prior classification mismatch")
            observed_states[saved["state"]] += 1
        if any(counts[state] != observed_states[state] for state in _PRIOR_STATES):
            raise ValueError("prior classification count mismatch")
    except (TypeError, ValueError, KeyError) as exc:
        raise Conflict("FileOS v2 transition stage integrity requires review") from exc
    latest = conn.execute(
        "SELECT actor_id,run_id,observed_at,root_binding_sha256 "
        "FROM brain_fileos_run_receipts WHERE source_id=%s "
        "ORDER BY observed_at DESC,completed_at DESC,run_id DESC LIMIT 1",
        (source_id,),
    ).fetchone()
    source = conn.execute(
        "SELECT root_binding_sha256 FROM brain_sources WHERE id=%s AND kind='fileos'",
        (source_id,),
    ).fetchone()
    latest_matches = bool(
        latest
        and source
        and latest["actor_id"] == stage["prior_actor_id"]
        and latest["run_id"] == stage["prior_run_id"]
        and latest["observed_at"] == stage["prior_observed_at"]
        and latest["root_binding_sha256"] == stage["root_binding_sha256"]
        and source["root_binding_sha256"] == stage["root_binding_sha256"]
    )
    hard_blockers = sorted(
        {
            *(value for value in blockers if value != "prior_item_not_hashed_under_donor_policy"),
            *(("unobserved_prior",) if counts["unobserved_prior"] else ()),
            *(("error_covered_prior",) if counts["error_covered_prior"] else ()),
            *(("donor_scan_errors",) if candidate["counts"]["errors"] else ()),
        }
    )
    acknowledged_counts = {
        "candidate_counts": dict(candidate["counts"]),
        "classification_counts": dict(counts),
    }
    static_plan = {
        "plan_version": PLAN_VERSION,
        "stage_id": str(stage_id),
        "packet_id": str(stage["packet_id"]),
        "source_id": source_id,
        "prior_run_id": str(stage["prior_run_id"]),
        "packet_sha256": stage["packet_sha256"],
        "candidate_sha256": stage["candidate_sha256"],
        "staged_rows_sha256": _canonical_digest(actual_tuples),
        "acknowledged_counts": acknowledged_counts,
        "hard_blockers": hard_blockers,
    }
    result = {
        **static_plan,
        "plan_sha256": _canonical_digest(static_plan),
        "latest_receipt_matches_stage": latest_matches,
        "reviewable": latest_matches and not hard_blockers,
        "publishable": False,
        "requires_review": True,
    }
    return result, stage


class FileOSV2TransitionReview:
    def __init__(self, core: DataCoreStore) -> None:
        self.core = core

    def plan(self, ctx: TenantContext, stage_id: UUID) -> dict[str, Any]:
        self.core.store.require(ctx, "brain.changes.read")
        if not isinstance(stage_id, UUID):
            raise ValueError("invalid FileOS v2 stage identity")
        with self.core.store.transaction(ctx) as conn:
            result, _ = _load_plan(ctx, conn, stage_id)
            self.core.store.audit(
                conn,
                ctx,
                "brain.fileos_v2_transition_plan_read",
                "fileos_v2_stage",
                str(stage_id),
            )
            return result

    def approve(
        self,
        principal: Principal,
        stage_id: UUID,
        approval_id: UUID,
        *,
        expected_plan_sha256: str,
        acknowledged_counts: Mapping[str, Any],
    ) -> FileOSV2ApprovalRecord:
        if principal.client_kind != "human":
            raise AccessDenied("human FileOS transition review required")
        ctx = principal.context
        self.core.store.require(ctx, "brain.fileos.transition.review")
        self.core.store.require(ctx, "brain.evidence.read")
        if (
            not isinstance(stage_id, UUID)
            or not isinstance(approval_id, UUID)
            or not isinstance(expected_plan_sha256, str)
            or len(expected_plan_sha256) != 64
            or any(character not in "0123456789abcdef" for character in expected_plan_sha256)
            or not isinstance(acknowledged_counts, Mapping)
        ):
            raise ValueError("invalid FileOS v2 transition approval")
        with self.core.store.transaction(ctx) as conn:
            plan, stage = _load_plan(ctx, conn, stage_id)
            if (
                not plan["reviewable"]
                or plan["plan_sha256"] != expected_plan_sha256
                or dict(acknowledged_counts) != plan["acknowledged_counts"]
            ):
                raise Conflict("FileOS v2 transition approval requires review")
            existing = conn.execute(
                "SELECT id,actor_id,stage_id,source_id,plan_sha256,acknowledged_counts,"
                "approved_at FROM brain_fileos_v2_transition_approvals "
                "WHERE id=%s OR stage_id=%s",
                (approval_id, stage_id),
            ).fetchone()
            if existing:
                if (
                    existing["id"] != approval_id
                    or existing["actor_id"] != ctx.actor_id
                    or existing["stage_id"] != stage_id
                    or existing["source_id"] != stage["source_id"]
                    or existing["plan_sha256"] != expected_plan_sha256
                    or existing["acknowledged_counts"] != dict(acknowledged_counts)
                ):
                    raise Conflict("FileOS v2 transition approval identity changed")
                self.core.store.audit(
                    conn,
                    ctx,
                    "brain.fileos_v2_transition_approval_replay",
                    "fileos_v2_transition_approval",
                    str(approval_id),
                )
                return FileOSV2ApprovalRecord(
                    approval_id,
                    stage_id,
                    stage["source_id"],
                    expected_plan_sha256,
                    existing["approved_at"],
                    False,
                )
            inserted = conn.execute(
                "INSERT INTO brain_fileos_v2_transition_approvals(tenant_id,id,actor_id,"
                "stage_id,packet_id,source_id,prior_run_id,packet_sha256,candidate_sha256,"
                "plan_sha256,acknowledged_counts) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING approved_at",
                (
                    ctx.tenant_id,
                    approval_id,
                    ctx.actor_id,
                    stage_id,
                    stage["packet_id"],
                    stage["source_id"],
                    stage["prior_run_id"],
                    stage["packet_sha256"],
                    stage["candidate_sha256"],
                    expected_plan_sha256,
                    Jsonb(dict(acknowledged_counts)),
                ),
            ).fetchone()
            assert inserted is not None
            self.core.store.audit(
                conn,
                ctx,
                "brain.fileos_v2_transition_approved",
                "fileos_v2_transition_approval",
                str(approval_id),
            )
            return FileOSV2ApprovalRecord(
                approval_id,
                stage_id,
                stage["source_id"],
                expected_plan_sha256,
                inserted["approved_at"],
                True,
            )
