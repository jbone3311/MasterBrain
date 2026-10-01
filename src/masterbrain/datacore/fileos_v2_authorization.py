"""Private owner authorization for a future FileOS v2 baseline attempt.

This does not attest current filesystem bytes or publish v2 state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from email_brain.auth import Principal
from email_brain.store import AccessDenied, Conflict
from masterbrain.datacore.fileos_transition_approval import _load_plan
from masterbrain.datacore.fileos_v2_preparation import _preparation_sha
from masterbrain.datacore.persistence import DataCoreStore


@dataclass(frozen=True, slots=True)
class FileOSV2BaselineAuthorization:
    authorization_id: UUID
    preparation_id: UUID
    stage_id: UUID
    source_id: str
    authorized_at: datetime
    recorded: bool


class FileOSV2BaselineAuthorizer:
    def __init__(self, core: DataCoreStore) -> None:
        self.core = core

    def authorize(
        self,
        principal: Principal,
        stage_id: UUID,
        approval_id: UUID,
        preparation_id: UUID,
        authorization_id: UUID,
        *,
        expected_plan_sha256: str,
        expected_preparation_sha256: str,
        acknowledged_counts: Mapping[str, Any],
    ) -> FileOSV2BaselineAuthorization:
        if principal.client_kind != "human":
            raise AccessDenied("human FileOS v2 baseline authorization required")
        ctx = principal.context
        self.core.store.require(ctx, "brain.fileos.transition.authorize")
        self.core.store.require(ctx, "brain.evidence.read")
        if (
            not all(
                isinstance(value, UUID)
                for value in (stage_id, approval_id, preparation_id, authorization_id)
            )
            or not isinstance(acknowledged_counts, Mapping)
            or any(
                not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
                for value in (expected_plan_sha256, expected_preparation_sha256)
            )
        ):
            raise ValueError("invalid FileOS v2 baseline authorization")
        with self.core.store.transaction(ctx) as conn:
            plan, stage = _load_plan(ctx, conn, stage_id)
            if (
                not plan["reviewable"]
                or plan["plan_sha256"] != expected_plan_sha256
                or plan["acknowledged_counts"] != dict(acknowledged_counts)
            ):
                raise Conflict("FileOS v2 baseline authorization requires review")
            approval = conn.execute(
                "SELECT id,actor_id,stage_id,source_id,prior_run_id,packet_sha256,"
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
                or approval["plan_sha256"] != expected_plan_sha256
                or approval["acknowledged_counts"] != dict(acknowledged_counts)
            ):
                raise Conflict("FileOS v2 baseline review approval changed")
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
                or preparation["plan_sha256"] != expected_plan_sha256
                or preparation["matched_rows_sha256"] != plan["staged_rows_sha256"]
                or preparation["hashed_count"] != stage["counts"]["hashed"]
                or preparation["preparation_sha256"] != expected_preparation_sha256
                or preparation["preparation_sha256"]
                != _preparation_sha(
                    preparation_id,
                    preparation["verification_id"],
                    stage_id,
                    stage["source_id"],
                    stage["prior_run_id"],
                    expected_plan_sha256,
                    plan["staged_rows_sha256"],
                    preparation["prepared_observed_at"],
                    preparation["hashed_count"],
                )
            ):
                raise Conflict("FileOS v2 baseline preparation changed")
            existing = conn.execute(
                "SELECT id,actor_id,preparation_id,approval_id,stage_id,source_id,"
                "prior_run_id,plan_sha256,preparation_sha256,acknowledged_counts,"
                "authorized_at FROM brain_fileos_v2_baseline_authorizations "
                "WHERE id=%s OR stage_id=%s OR source_id=%s",
                (authorization_id, stage_id, stage["source_id"]),
            ).fetchone()
            if existing is not None:
                if (
                    existing["id"] != authorization_id
                    or existing["actor_id"] != ctx.actor_id
                    or existing["preparation_id"] != preparation_id
                    or existing["approval_id"] != approval_id
                    or existing["stage_id"] != stage_id
                    or existing["source_id"] != stage["source_id"]
                    or existing["prior_run_id"] != stage["prior_run_id"]
                    or existing["plan_sha256"] != expected_plan_sha256
                    or existing["preparation_sha256"] != expected_preparation_sha256
                    or existing["acknowledged_counts"] != dict(acknowledged_counts)
                ):
                    raise Conflict("FileOS v2 baseline authorization identity changed")
                self.core.store.audit(
                    conn,
                    ctx,
                    "brain.fileos_v2_baseline_authorization_replay",
                    "fileos_v2_baseline_authorization",
                    str(authorization_id),
                )
                return FileOSV2BaselineAuthorization(
                    authorization_id,
                    preparation_id,
                    stage_id,
                    stage["source_id"],
                    existing["authorized_at"],
                    False,
                )
            inserted = conn.execute(
                "INSERT INTO brain_fileos_v2_baseline_authorizations(tenant_id,id,"
                "actor_id,preparation_id,approval_id,stage_id,source_id,prior_run_id,"
                "plan_sha256,preparation_sha256,acknowledged_counts) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING authorized_at",
                (
                    ctx.tenant_id,
                    authorization_id,
                    ctx.actor_id,
                    preparation_id,
                    approval_id,
                    stage_id,
                    stage["source_id"],
                    stage["prior_run_id"],
                    expected_plan_sha256,
                    expected_preparation_sha256,
                    Jsonb(dict(acknowledged_counts)),
                ),
            ).fetchone()
            assert inserted is not None
            self.core.store.audit(
                conn,
                ctx,
                "brain.fileos_v2_baseline_authorized",
                "fileos_v2_baseline_authorization",
                str(authorization_id),
            )
            return FileOSV2BaselineAuthorization(
                authorization_id,
                preparation_id,
                stage_id,
                stage["source_id"],
                inserted["authorized_at"],
                True,
            )
