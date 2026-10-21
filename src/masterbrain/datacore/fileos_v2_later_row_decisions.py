"""Append-only human decisions about historical FileOS classifications.

These decisions are observations for review, never absence or file authority.
"""

from __future__ import annotations

from typing import Any

from email_brain.auth import Principal
from email_brain.store import AccessDenied, Conflict, NotFound
from masterbrain.datacore.fileos_v2_later_index_generation import (
    FileOSV2LaterSearchReviewer,
)
from masterbrain.datacore.fileos_v2_later_review_snapshot import historical_review_snapshot
from masterbrain.datacore.persistence import _IDENTITY, DataCoreStore
from masterbrain.schemas import (
    FileOSV2LaterReviewSummaryRequest,
    FileOSV2LaterRowDecisionHistoryRequest,
    FileOSV2LaterRowDecisionsRequest,
)


class FileOSV2LaterRowDecisions:
    def __init__(self, core: DataCoreStore) -> None:
        self.core = core
        self.reviewer = FileOSV2LaterSearchReviewer(core)

    def summary(
        self, principal: Principal, source_id: str,
        body: FileOSV2LaterReviewSummaryRequest,
    ) -> dict[str, Any]:
        if principal.client_kind != "human":
            raise AccessDenied("human FileOS later review required")
        ctx = principal.context
        for scope in (
            "brain.fileos.transition.review", "brain.search", "brain.evidence.read"
        ):
            self.core.store.require(ctx, scope)
        if (
            not isinstance(source_id, str) or not _IDENTITY.fullmatch(source_id)
            or not isinstance(body, FileOSV2LaterReviewSummaryRequest)
        ):
            raise ValueError("invalid FileOS later review summary request")
        if ctx.source_ids is not None and source_id not in ctx.source_ids:
            raise NotFound()
        with self.core.store.transaction(ctx) as conn:
            run, _active_id, closure_id = self.reviewer._candidate_locked(
                conn, ctx, source_id, body.generation_id
            )
            closure = self.reviewer.coverage._inspect_locked(conn, closure_id)
            closure_row = conn.execute(
                "SELECT closure FROM brain_fileos_v2_later_coverage_closures "
                "WHERE tenant_id=%s AND id=%s", (ctx.tenant_id, closure_id),
            ).fetchone()
            if closure_row is None:
                raise Conflict("FileOS later review closure requires review")
            rows = conn.execute(
                "SELECT DISTINCT ON (locator) locator,state,prior_version_id,"
                "disposition,reviewer_id,idempotency_key,recorded_at "
                "FROM brain_fileos_v2_later_row_decisions "
                "WHERE tenant_id=%s AND source_id=%s AND generation_id=%s "
                "ORDER BY locator,recorded_at DESC,idempotency_key DESC",
                (ctx.tenant_id, source_id, body.generation_id),
            ).fetchall()
            result = historical_review_snapshot(
                source_id=source_id,
                generation_id=body.generation_id,
                run_id=str(run.run_id),
                run_sha256=run.run_sha256,
                closure_id=str(closure_id),
                closure_sha256=closure.closure_sha256,
                review_flags=dict(run.review_flags),
                prior_rows=closure_row["closure"]["prior_rows"],
                latest_decisions=[{
                    **row,
                    "reviewer_id": str(row["reviewer_id"]),
                    "idempotency_key": str(row["idempotency_key"]),
                    "recorded_at": row["recorded_at"].isoformat(),
                } for row in rows],
            )
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_review_summary",
                "index_generation", body.generation_id,
            )
            return result

    def record(
        self, principal: Principal, source_id: str,
        body: FileOSV2LaterRowDecisionsRequest,
    ) -> dict[str, Any]:
        if principal.client_kind != "human":
            raise AccessDenied("human FileOS later decision required")
        ctx = principal.context
        for scope in (
            "brain.fileos.transition.review", "brain.search", "brain.evidence.read"
        ):
            self.core.store.require(ctx, scope)
        if (
            not isinstance(source_id, str) or not _IDENTITY.fullmatch(source_id)
            or not isinstance(body, FileOSV2LaterRowDecisionsRequest)
        ):
            raise ValueError("invalid FileOS later row decision request")
        if ctx.source_ids is not None and source_id not in ctx.source_ids:
            raise NotFound()
        keys = [item.idempotency_key for item in body.decisions]
        locators = [item.locator for item in body.decisions]
        if len(set(keys)) != len(keys) or len(set(locators)) != len(locators):
            raise ValueError("duplicate FileOS later decision key or locator")
        with self.core.store.transaction(ctx) as conn:
            for key in sorted(keys):
                conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (f"{ctx.tenant_id}:fileos-row-decision:{ctx.actor_id}:{key}",),
                )
            run, _active_id, closure_id = self.reviewer._candidate_locked(
                conn, ctx, source_id, body.generation_id
            )
            closure = self.reviewer.coverage._inspect_locked(conn, closure_id)
            closure_row = conn.execute(
                "SELECT closure FROM brain_fileos_v2_later_coverage_closures "
                "WHERE tenant_id=%s AND id=%s", (ctx.tenant_id, closure_id),
            ).fetchone()
            if closure_row is None:
                raise Conflict("FileOS later decision closure requires review")
            exact_rows = {
                row["locator"]: row for row in closure_row["closure"]["prior_rows"]
            }
            for item in body.decisions:
                row = exact_rows.get(item.locator)
                if (
                    row is None or row["state"] != item.state
                    or row.get("prior_version_id") != item.prior_version_id
                ):
                    raise Conflict("FileOS later decision row requires review")
            recorded = 0
            replayed = 0
            for item in body.decisions:
                values = (
                    source_id, body.generation_id, run.run_id, run.run_sha256,
                    closure_id, closure.closure_sha256, item.locator,
                    item.state, item.prior_version_id, item.disposition,
                )
                prior = conn.execute(
                    "SELECT source_id,generation_id,run_id,run_sha256,closure_id,"
                    "closure_sha256,locator,state,prior_version_id,disposition "
                    "FROM brain_fileos_v2_later_row_decisions "
                    "WHERE tenant_id=%s AND reviewer_id=%s AND idempotency_key=%s",
                    (ctx.tenant_id, ctx.actor_id, item.idempotency_key),
                ).fetchone()
                if prior is not None:
                    if (
                        prior["source_id"], prior["generation_id"], prior["run_id"],
                        prior["run_sha256"], prior["closure_id"],
                        prior["closure_sha256"], prior["locator"], prior["state"],
                        prior["prior_version_id"], prior["disposition"],
                    ) != values:
                        raise Conflict("FileOS later decision idempotency key reused")
                    replayed += 1
                    continue
                conn.execute(
                    "INSERT INTO brain_fileos_v2_later_row_decisions(tenant_id,"
                    "reviewer_id,idempotency_key,source_id,generation_id,run_id,"
                    "run_sha256,closure_id,closure_sha256,locator,state,"
                    "prior_version_id,disposition) VALUES "
                    "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (ctx.tenant_id, ctx.actor_id, item.idempotency_key, *values),
                )
                recorded += 1
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_rows_decided",
                "index_generation", body.generation_id,
            )
            return {
                "source_id": source_id,
                "generation_id": body.generation_id,
                "run_id": str(run.run_id),
                "recorded_count": recorded,
                "replayed_count": replayed,
                "decision_kind": "historical_classification_not_absence_approval",
                "absence_authorized": False,
                "current_read_active": False,
                "source_effect_authorized": False,
            }

    def history(
        self, principal: Principal, source_id: str,
        body: FileOSV2LaterRowDecisionHistoryRequest,
    ) -> dict[str, Any]:
        if principal.client_kind != "human":
            raise AccessDenied("human FileOS later decision review required")
        ctx = principal.context
        for scope in (
            "brain.fileos.transition.review", "brain.search", "brain.evidence.read"
        ):
            self.core.store.require(ctx, scope)
        if (
            not isinstance(source_id, str) or not _IDENTITY.fullmatch(source_id)
            or not isinstance(body, FileOSV2LaterRowDecisionHistoryRequest)
        ):
            raise ValueError("invalid FileOS later decision history request")
        if ctx.source_ids is not None and source_id not in ctx.source_ids:
            raise NotFound()
        with self.core.store.transaction(ctx) as conn:
            run, _active_id, closure_id = self.reviewer._candidate_locked(
                conn, ctx, source_id, body.generation_id
            )
            self.reviewer.coverage._inspect_locked(conn, closure_id)
            closure_row = conn.execute(
                "SELECT closure FROM brain_fileos_v2_later_coverage_closures "
                "WHERE tenant_id=%s AND id=%s", (ctx.tenant_id, closure_id),
            ).fetchone()
            if closure_row is None or not any(
                row["locator"] == body.locator
                for row in closure_row["closure"]["prior_rows"]
            ):
                raise NotFound()
            count_row = conn.execute(
                "SELECT count(*) AS n FROM brain_fileos_v2_later_row_decisions "
                "WHERE tenant_id=%s AND generation_id=%s AND locator=%s",
                (ctx.tenant_id, body.generation_id, body.locator),
            ).fetchone()
            if count_row is None:
                raise Conflict("FileOS later decision history count unavailable")
            count = count_row["n"]
            rows = conn.execute(
                "SELECT disposition,state,prior_version_id,reviewer_id,"
                "idempotency_key,recorded_at "
                "FROM brain_fileos_v2_later_row_decisions "
                "WHERE tenant_id=%s AND generation_id=%s AND locator=%s "
                "ORDER BY recorded_at DESC,idempotency_key DESC LIMIT %s OFFSET %s",
                (ctx.tenant_id, body.generation_id, body.locator,
                 body.limit, body.offset),
            ).fetchall()
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_row_decision_history",
                "index_generation", body.generation_id,
            )
            next_offset = body.offset + len(rows)
            return {
                "source_id": source_id,
                "generation_id": body.generation_id,
                "run_id": str(run.run_id),
                "locator": body.locator,
                "offset": body.offset,
                "total_decisions": count,
                "decisions": [
                    {
                        "disposition": row["disposition"],
                        "state": row["state"],
                        "prior_version_id": row["prior_version_id"],
                        "reviewer_id": str(row["reviewer_id"]),
                        "idempotency_key": str(row["idempotency_key"]),
                        "recorded_at": row["recorded_at"].isoformat(),
                    }
                    for row in rows
                ],
                "next_offset": next_offset if next_offset < count else None,
                "decision_kind": "historical_classification_not_absence_approval",
                "absence_authorized": False,
                "current_read_active": False,
                "source_effect_authorized": False,
                "untrusted_content": True,
            }
