"""Complete a later FileOS v2 processing run as historical evidence only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.datacore.fileos_v2_later_coverage import FileOSV2LaterCoverageStore
from masterbrain.datacore.fileos_v2_later_document_publication import (
    FileOSV2LaterDocumentPublisher,
)
from masterbrain.datacore.persistence import DataCoreStore, _canonical_digest

RUN_VERSION = "masterbrain-fileos-v2-later-run-completion-v1"


def _review_flags(packet: dict[str, Any]) -> dict[str, bool]:
    preview = packet["preview"]
    return {
        "possible_absence": preview["counts"]["absence_candidate"] > 0,
        "mass_loss": "mass_loss_requires_review" in preview["blockers"],
        "prior_coverage": "prior_coverage_requires_review" in preview["blockers"],
    }


def _run_sha(
    run_id: UUID, attempt_id: UUID, preparation_id: UUID, closure_id: UUID,
    packet_id: UUID, baseline_completion_id: UUID, source_id: str,
    root_binding_sha256: str, attempt_sha256: str, preparation_sha256: str,
    closure_sha256: str, packet_sha256: str, processed_counts: dict[str, int],
    classification_counts: dict[str, int], review_flags: dict[str, bool],
    observed_at: datetime,
) -> str:
    return _canonical_digest({
        "version": RUN_VERSION,
        "run_id": str(run_id),
        "attempt_id": str(attempt_id),
        "preparation_id": str(preparation_id),
        "closure_id": str(closure_id),
        "packet_id": str(packet_id),
        "baseline_completion_id": str(baseline_completion_id),
        "source_id": source_id,
        "root_binding_sha256": root_binding_sha256,
        "attempt_sha256": attempt_sha256,
        "preparation_sha256": preparation_sha256,
        "closure_sha256": closure_sha256,
        "packet_sha256": packet_sha256,
        "processed_counts": processed_counts,
        "classification_counts": classification_counts,
        "review_flags": review_flags,
        "observed_at": observed_at.astimezone(UTC).isoformat(),
    })


@dataclass(frozen=True, slots=True)
class FileOSV2LaterRunCompletion:
    run_id: UUID
    attempt_id: UUID
    source_id: str
    processed_counts: dict[str, int]
    classification_counts: dict[str, int]
    review_flags: dict[str, bool]
    run_sha256: str
    observed_at: datetime
    completed_at: datetime
    recorded: bool
    publishable: bool = False
    current_read_active: bool = False
    absence_authorized: bool = False
    requires_review: bool = True


class FileOSV2LaterRunCompleter:
    def __init__(self, core: DataCoreStore) -> None:
        self.core = core
        self.publisher = FileOSV2LaterDocumentPublisher(core)
        self.coverage = FileOSV2LaterCoverageStore(core)

    def _basis(
        self, conn: Connection[dict[str, Any]], attempt_id: UUID,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        attempt = conn.execute(
            "SELECT id,preparation_id,closure_id,packet_id,completion_id,"
            "source_id,root_binding_sha256,preparation_sha256,attempt_sha256,"
            "counts,ready,observed_at FROM brain_fileos_v2_later_document_attempts "
            "WHERE id=%s", (attempt_id,),
        ).fetchone()
        if attempt is None:
            raise NotFound()
        self.publisher._saved_attempt(
            conn, attempt_id, attempt["preparation_id"], None, None, None, None
        )
        prep, packet_row, _rows, _mapping = self.publisher._load_basis(
            conn, attempt["preparation_id"]
        )
        coverage = self.coverage._inspect_locked(conn, attempt["closure_id"])
        if (
            not attempt["ready"]
            or prep["closure_id"] != attempt["closure_id"]
            or prep["packet_id"] != attempt["packet_id"]
            or prep["completion_id"] != attempt["completion_id"]
            or prep["source_id"] != attempt["source_id"]
            or prep["root_binding_sha256"] != attempt["root_binding_sha256"]
            or prep["preparation_sha256"] != attempt["preparation_sha256"]
            or packet_row["id"] != attempt["packet_id"]
            or coverage.packet_id != packet_row["id"]
            or coverage.source_id != prep["source_id"]
        ):
            raise Conflict("FileOS v2 later run basis requires review")
        if packet_row["packet"]["candidate"]["counts"]["errors"] != 0:
            raise Conflict("FileOS v2 later run scan errors require review")
        return attempt, prep, packet_row

    def _saved(
        self, conn: Connection[dict[str, Any]], run_id: UUID,
        attempt_id: UUID | None, actor_id: UUID | None,
        root: Path | None,
    ) -> FileOSV2LaterRunCompletion | None:
        row = conn.execute(
            "SELECT id,actor_id,attempt_id,preparation_id,closure_id,packet_id,"
            "baseline_completion_id,source_id,root_binding_sha256,"
            "attempt_sha256,preparation_sha256,closure_sha256,packet_sha256,"
            "processed_counts,classification_counts,review_flags,observed_at,"
            "run_sha256,completed_at,publishable,current_read_active,"
            "absence_authorized,requires_review FROM "
            "brain_fileos_v2_later_run_completions WHERE id=%s", (run_id,),
        ).fetchone()
        if row is None:
            return None
        attempt, prep, packet_row = self._basis(conn, row["attempt_id"])
        coverage = self.coverage._inspect_locked(conn, row["closure_id"])
        try:
            preview = packet_row["packet"]["preview"]
            flags = _review_flags(packet_row["packet"])
            digest = _run_sha(
                row["id"], row["attempt_id"], row["preparation_id"],
                row["closure_id"], row["packet_id"], row["baseline_completion_id"],
                row["source_id"], row["root_binding_sha256"], row["attempt_sha256"],
                row["preparation_sha256"], row["closure_sha256"], row["packet_sha256"],
                row["processed_counts"], row["classification_counts"],
                row["review_flags"], row["observed_at"],
            )
            if (
                (attempt_id is not None and row["attempt_id"] != attempt_id)
                or (actor_id is not None and row["actor_id"] != actor_id)
                or row["preparation_id"] != prep["id"]
                or row["closure_id"] != prep["closure_id"]
                or row["packet_id"] != packet_row["id"]
                or row["baseline_completion_id"] != prep["completion_id"]
                or row["source_id"] != prep["source_id"]
                or row["root_binding_sha256"] != prep["root_binding_sha256"]
                or row["attempt_sha256"] != attempt["attempt_sha256"]
                or row["preparation_sha256"] != prep["preparation_sha256"]
                or row["closure_sha256"] != coverage.closure_sha256
                or row["packet_sha256"] != packet_row["packet_sha256"]
                or row["processed_counts"] != attempt["counts"]
                or row["classification_counts"] != preview["counts"]
                or row["review_flags"] != flags
                or row["observed_at"] <= attempt["observed_at"]
                or row["run_sha256"] != digest
                or row["publishable"] is not False
                or row["current_read_active"] is not False
                or row["absence_authorized"] is not False
                or row["requires_review"] is not True
                or (root is not None and fileos_root_binding_sha256(root)
                    != row["root_binding_sha256"])
            ):
                raise ValueError("run identity")
        except (KeyError, TypeError, ValueError) as exc:
            raise Conflict("FileOS v2 later run integrity requires review") from exc
        return FileOSV2LaterRunCompletion(
            run_id=row["id"], attempt_id=row["attempt_id"],
            source_id=row["source_id"], processed_counts=dict(row["processed_counts"]),
            classification_counts=dict(row["classification_counts"]),
            review_flags=dict(row["review_flags"]), run_sha256=row["run_sha256"],
            observed_at=row["observed_at"], completed_at=row["completed_at"],
            recorded=False,
        )

    def inspect(
        self, ctx: TenantContext, run_id: UUID
    ) -> FileOSV2LaterRunCompletion:
        self.core.store.require(ctx, "brain.changes.read")
        if not isinstance(run_id, UUID):
            raise ValueError("invalid FileOS v2 later run identity")
        with self.core.store.transaction(ctx) as conn:
            saved = self._saved(conn, run_id, None, None, None)
            if saved is None:
                raise NotFound()
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_run_read",
                "fileos_v2_later_run_completion", str(run_id),
            )
            return saved

    def complete(
        self, principal: Principal, attempt_id: UUID, run_id: UUID, root: Path,
    ) -> FileOSV2LaterRunCompletion:
        if principal.client_kind != "worker":
            raise AccessDenied("FileOS v2 later run worker required")
        ctx = principal.context
        for scope in ("brain.fileos.transition.complete", "brain.changes.read"):
            self.core.store.require(ctx, scope)
        if (
            not isinstance(attempt_id, UUID)
            or not isinstance(run_id, UUID)
            or not isinstance(root, Path)
        ):
            raise ValueError("invalid FileOS v2 later run completion")
        with self.core.store.transaction(ctx) as conn:
            saved = self._saved(conn, run_id, attempt_id, ctx.actor_id, root)
            if saved is not None:
                return saved
            attempt, prep, packet_row = self._basis(conn, attempt_id)
            existing = conn.execute(
                "SELECT 1 FROM brain_fileos_v2_later_run_completions WHERE packet_id=%s",
                (prep["packet_id"],),
            ).fetchone()
            if existing:
                raise Conflict("FileOS v2 later packet already completed")
            rows = sorted(
                self.publisher._load_basis(conn, prep["id"])[2], key=lambda row: row[1]
            )
            observed_at = self.publisher._match_source(
                ctx, conn, prep, packet_row, rows, root
            )
            if observed_at <= attempt["observed_at"]:
                raise Conflict("FileOS v2 later run observation requires review")
            coverage = self.coverage._inspect_locked(conn, prep["closure_id"])
            preview = packet_row["packet"]["preview"]
            flags = _review_flags(packet_row["packet"])
            digest = _run_sha(
                run_id, attempt_id, prep["id"], prep["closure_id"], prep["packet_id"],
                prep["completion_id"], prep["source_id"], prep["root_binding_sha256"],
                attempt["attempt_sha256"], prep["preparation_sha256"],
                coverage.closure_sha256, packet_row["packet_sha256"],
                attempt["counts"], preview["counts"], flags, observed_at,
            )
            row = conn.execute(
                "INSERT INTO brain_fileos_v2_later_run_completions(tenant_id,id,"
                "actor_id,attempt_id,preparation_id,closure_id,packet_id,"
                "baseline_completion_id,source_id,root_binding_sha256,"
                "attempt_sha256,preparation_sha256,closure_sha256,packet_sha256,"
                "processed_counts,classification_counts,review_flags,"
                "observed_at,run_sha256) VALUES ("
                "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING completed_at",
                (
                    ctx.tenant_id, run_id, ctx.actor_id, attempt_id, prep["id"],
                    prep["closure_id"], prep["packet_id"], prep["completion_id"],
                    prep["source_id"], prep["root_binding_sha256"],
                    attempt["attempt_sha256"], prep["preparation_sha256"],
                    coverage.closure_sha256, packet_row["packet_sha256"],
                    Jsonb(attempt["counts"]), Jsonb(preview["counts"]),
                    Jsonb(flags), observed_at, digest,
                ),
            ).fetchone()
            assert row is not None
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_run_completed",
                "fileos_v2_later_run_completion", str(run_id),
            )
            return FileOSV2LaterRunCompletion(
                run_id=run_id, attempt_id=attempt_id, source_id=prep["source_id"],
                processed_counts=dict(attempt["counts"]),
                classification_counts=dict(preview["counts"]), review_flags=flags,
                run_sha256=digest, observed_at=observed_at,
                completed_at=row["completed_at"], recorded=True,
            )
