"""Publish bounded historical documents for one completed FileOS v2 baseline.

This prepares evidence for a future v2 index. It never activates current reads,
infers absence, writes source files, or changes the pinned FOS-Master donor.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from email_brain.auth import Principal
from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound
from masterbrain.datacore.extraction import (
    DOCUMENT_SUFFIXES,
    EXTRACTOR_VERSION,
    DocumentProcessor,
    ExtractionStatus,
    extract_document_source_version,
    extract_source_version,
)
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.datacore.fileos_donor_candidate import build_fileos_donor_candidate
from masterbrain.datacore.fileos_transition_approval import _load_plan
from masterbrain.datacore.fileos_v2_completion import _completion_sha
from masterbrain.datacore.persistence import (
    DataCoreStore,
    _canonical_digest,
    _fileos_v2_staged_rows,
)

PUBLICATION_VERSION = "masterbrain-fileos-v2-document-attempt-v1"
OUTCOMES = ("extracted", "empty", "unsupported", "deferred", "changed", "failed")


@dataclass(frozen=True, slots=True)
class FileOSV2DocumentAttempt:
    attempt_id: UUID
    completion_id: UUID
    source_id: str
    counts: dict[str, int]
    ready: bool
    attempt_sha256: str
    observed_at: datetime
    completed_at: datetime
    recorded: bool


def _attempt_sha(
    attempt_id: UUID,
    completion_id: UUID,
    source_id: str,
    completion_sha256: str,
    root_binding_sha256: str,
    code_revision: str,
    text_extractor_version: str,
    document_processor_version: str | None,
    counts: Mapping[str, int],
    ready: bool,
    observed_at: datetime,
    items: list[dict[str, str | None]],
) -> str:
    return _canonical_digest(
        {
            "version": PUBLICATION_VERSION,
            "attempt_id": str(attempt_id),
            "completion_id": str(completion_id),
            "source_id": source_id,
            "completion_sha256": completion_sha256,
            "root_binding_sha256": root_binding_sha256,
            "code_revision": code_revision,
            "text_extractor_version": text_extractor_version,
            "document_processor_version": document_processor_version,
            "counts": dict(counts),
            "ready": ready,
            "observed_at": observed_at.astimezone(UTC).isoformat(),
            "items": items,
        }
    )


class FileOSV2DocumentPublisher:
    def __init__(self, core: DataCoreStore, document_processor: DocumentProcessor | None = None):
        self.core = core
        self.document_processor = document_processor

    def _load_baseline(
        self, ctx: TenantContext, conn: Connection[dict[str, Any]], completion_id: UUID
    ) -> tuple[dict[str, Any], Mapping[str, Any], list[dict[str, Any]]]:
        # The caller owns the transaction. _load_plan acquires the same source
        # advisory lock as completion and rechecks latest-v1 and review blockers.
        completion = conn.execute(
            "SELECT id,stage_id,source_id,prior_run_id,root_binding_sha256,"
            "authorization_id,preparation_id,plan_sha256,preparation_sha256,"
            "matched_rows_sha256,policy_sha256,counts,hashed_count,"
            "fresh_observed_at,completion_sha256 "
            "FROM brain_fileos_v2_baseline_completions WHERE id=%s",
            (completion_id,),
        ).fetchone()
        if completion is None:
            raise NotFound()
        plan, stage = _load_plan(ctx, conn, completion["stage_id"])
        if not plan["reviewable"] or completion["source_id"] != stage["source_id"]:
            raise Conflict("FileOS v2 document baseline requires review")
        expected = _completion_sha(
            completion["id"],
            completion["authorization_id"],
            completion["preparation_id"],
            completion["stage_id"],
            completion["source_id"],
            completion["prior_run_id"],
            completion["plan_sha256"],
            completion["preparation_sha256"],
            completion["matched_rows_sha256"],
            completion["policy_sha256"],
            completion["root_binding_sha256"],
            completion["counts"],
            completion["fresh_observed_at"],
        )
        if (
            completion["completion_sha256"] != expected
            or completion["prior_run_id"] != stage["prior_run_id"]
            or completion["root_binding_sha256"] != stage["root_binding_sha256"]
            or completion["counts"] != stage["counts"]
            or completion["matched_rows_sha256"] != plan["staged_rows_sha256"]
            or completion["hashed_count"] != stage["counts"]["hashed"]
        ):
            raise Conflict("FileOS v2 document baseline integrity requires review")
        packet = conn.execute(
            "SELECT packet FROM brain_fileos_transition_packets WHERE id=%s",
            (stage["packet_id"],),
        ).fetchone()
        candidate = packet["packet"].get("candidate") if packet else None
        policy = candidate.get("policy") if isinstance(candidate, Mapping) else None
        if (
            not isinstance(policy, Mapping)
            or _canonical_digest(policy) != completion["policy_sha256"]
        ):
            raise Conflict("FileOS v2 document policy requires review")
        staged_rows = conn.execute(
            "SELECT locator,source_id,item_id,version_id AS candidate_version_id,"
            "sha256,size_bytes,media_type FROM brain_fileos_v2_staged_rows "
            "WHERE tenant_id=%s AND stage_id=%s AND kind='hashed' ORDER BY locator",
            (ctx.tenant_id, completion["stage_id"]),
        ).fetchall()
        prepared_rows = conn.execute(
            "SELECT locator,source_id,item_id,candidate_version_id,"
            "prepared_version_id,evidence_id FROM brain_fileos_v2_prepared_rows "
            "WHERE tenant_id=%s AND stage_id=%s ORDER BY locator",
            (ctx.tenant_id, completion["stage_id"]),
        ).fetchall()
        if (
            len(staged_rows) != completion["hashed_count"]
            or len(prepared_rows) != completion["hashed_count"]
        ):
            raise Conflict("FileOS v2 document evidence requires review")
        rows: list[dict[str, Any]] = []
        for staged, prepared in zip(staged_rows, prepared_rows, strict=True):
            if (
                staged["locator"] != prepared["locator"]
                or staged["source_id"] != prepared["source_id"]
                or staged["item_id"] != prepared["item_id"]
                or staged["candidate_version_id"] != prepared["candidate_version_id"]
            ):
                raise Conflict("FileOS v2 document evidence requires review")
            rows.append({
                **staged,
                "prepared_version_id": prepared["prepared_version_id"],
                "evidence_id": prepared["evidence_id"],
            })
        return completion, policy, rows

    @staticmethod
    def _match_source(
        root: Path,
        completion: Mapping[str, Any],
        policy: Mapping[str, Any],
        observed_at: datetime,
    ) -> None:
        try:
            if fileos_root_binding_sha256(root) != completion["root_binding_sha256"]:
                raise ValueError("wrong source root")
            fresh = build_fileos_donor_candidate(
                root,
                source_id=completion["source_id"],
                observed_at=observed_at,
                metadata_only=policy["metadata_only"],
            )
            rows = _fileos_v2_staged_rows(fresh, completion["source_id"])
        except (OSError, RuntimeError, TypeError, ValueError, KeyError):
            raise Conflict("FileOS v2 document source requires review") from None
        if (
            fresh["root_binding"]["sha256"] != completion["root_binding_sha256"]
            or fresh["policy"] != policy
            or fresh["counts"] != completion["counts"]
            or fresh["counts"]["errors"] != 0
            or _canonical_digest(sorted(rows, key=lambda row: row[1]))
            != completion["matched_rows_sha256"]
        ):
            raise Conflict("FileOS v2 document source changed")

    def _saved_attempt(
        self,
        ctx: TenantContext,
        conn: Connection[dict[str, Any]],
        completion_id: UUID,
        attempt_id: UUID,
        root: Path,
        code_revision: str,
        processor_version: str | None,
    ) -> FileOSV2DocumentAttempt | None:
        existing = conn.execute(
            "SELECT id,actor_id,completion_id,source_id,root_binding_sha256,"
            "completion_sha256,code_revision,text_extractor_version,"
            "document_processor_version,counts,ready,observed_at,attempt_sha256,"
            "completed_at FROM brain_fileos_v2_document_attempts WHERE id=%s",
            (attempt_id,),
        ).fetchone()
        if existing is None:
            return None
        items = conn.execute(
            "SELECT locator,item_id,candidate_version_id,prepared_version_id,"
            "evidence_id,outcome,document_id "
            "FROM brain_fileos_v2_document_attempt_items WHERE attempt_id=%s "
            "ORDER BY locator",
            (attempt_id,),
        ).fetchall()
        expected_sha = _attempt_sha(
            attempt_id, existing["completion_id"], existing["source_id"],
            existing["completion_sha256"], existing["root_binding_sha256"],
            existing["code_revision"], existing["text_extractor_version"],
            existing["document_processor_version"], existing["counts"],
            existing["ready"], existing["observed_at"], items,
        )
        if (
            existing["actor_id"] != ctx.actor_id
            or existing["completion_id"] != completion_id
            or existing["code_revision"] != code_revision
            or existing["text_extractor_version"] != EXTRACTOR_VERSION
            or existing["document_processor_version"] != processor_version
            or existing["attempt_sha256"] != expected_sha
            or fileos_root_binding_sha256(root) != existing["root_binding_sha256"]
        ):
            raise Conflict("FileOS v2 document attempt identity changed")
        self.core.store.audit(
            conn, ctx, "brain.fileos_v2_document_attempt_replay",
            "fileos_v2_document_attempt", str(attempt_id),
        )
        return FileOSV2DocumentAttempt(
            attempt_id, completion_id, existing["source_id"], dict(existing["counts"]),
            existing["ready"], expected_sha, existing["observed_at"],
            existing["completed_at"], False,
        )

    def publish(
        self,
        principal: Principal,
        completion_id: UUID,
        attempt_id: UUID,
        root: Path,
        *,
        code_revision: str,
        authorize: Callable[[], None] | None = None,
    ) -> FileOSV2DocumentAttempt:
        if principal.client_kind != "worker":
            raise AccessDenied("FileOS v2 document publication worker required")
        ctx = principal.context
        for scope in (
            "brain.fileos.transition.publish",
            "brain.document.publish",
            "brain.changes.read",
        ):
            self.core.store.require(ctx, scope)
        processor_version = (
            self.document_processor.processor_version
            if self.document_processor is not None
            else None
        )
        if (
            not isinstance(completion_id, UUID)
            or not isinstance(attempt_id, UUID)
            or not isinstance(root, Path)
            or not isinstance(code_revision, str)
            or not code_revision
            or len(code_revision) > 200
            or "\x00" in code_revision
            or (processor_version is not None and (
                not processor_version or len(processor_version) > 200 or "\x00" in processor_version
            ))
        ):
            raise ValueError("invalid FileOS v2 document publication")
        if authorize is not None:
            authorize()
        with self.core.store.transaction(ctx) as conn:
            saved = self._saved_attempt(
                ctx, conn, completion_id, attempt_id, root, code_revision, processor_version,
            )
            if saved is not None:
                return saved
            completion, policy, rows = self._load_baseline(ctx, conn, completion_id)
            if conn.execute(
                "SELECT 1 FROM brain_fileos_v2_document_attempts "
                "WHERE completion_id=%s AND ready", (completion_id,),
            ).fetchone():
                raise Conflict("FileOS v2 documents are already ready")
            stamp = conn.execute("SELECT clock_timestamp() AS observed_at").fetchone()
            assert stamp is not None
            self._match_source(root, completion, policy, stamp["observed_at"])

        results: list[dict[str, str | None]] = []
        counts: Counter[str] = Counter()
        for row in rows:
            if authorize is not None:
                authorize()
            item = {
                "locator": row["locator"],
                "version_id": row["prepared_version_id"],
                "digest": {"algorithm": "sha256", "value": row["sha256"]},
                "size_bytes": row["size_bytes"],
                "media_type": row["media_type"],
            }
            suffix = PurePosixPath(row["locator"]).suffix.lower()
            extraction = (
                extract_document_source_version(root, item, self.document_processor)
                if self.document_processor is not None and suffix in DOCUMENT_SUFFIXES
                else extract_source_version(root, item)
            )
            if authorize is not None:
                authorize()
            document_id = None
            if extraction.status is ExtractionStatus.EXTRACTED:
                published = self.core.publish_text(
                    ctx,
                    row["prepared_version_id"],
                    extraction.text,
                    code_revision=code_revision,
                    normalizer=(
                        processor_version or EXTRACTOR_VERSION
                        if self.document_processor is not None and suffix in DOCUMENT_SUFFIXES
                        else EXTRACTOR_VERSION
                    ),
                )
                document_id = published.document_id
            counts[extraction.status.value] += 1
            results.append(
                {
                    "locator": row["locator"],
                    "item_id": row["item_id"],
                    "candidate_version_id": row["candidate_version_id"],
                    "prepared_version_id": row["prepared_version_id"],
                    "evidence_id": row["evidence_id"],
                    "outcome": extraction.status.value,
                    "document_id": document_id,
                }
            )
        final_counts = {outcome: counts[outcome] for outcome in OUTCOMES}
        ready = not final_counts["changed"] and not final_counts["failed"]
        if authorize is not None:
            authorize()
        with self.core.store.transaction(ctx) as conn:
            saved = self._saved_attempt(
                ctx, conn, completion_id, attempt_id, root, code_revision, processor_version,
            )
            if saved is not None:
                return saved
            current, final_policy, final_rows = self._load_baseline(ctx, conn, completion_id)
            # A competing identical writer may have committed while this
            # transaction waited for the source lock inside _load_baseline.
            saved = self._saved_attempt(
                ctx, conn, completion_id, attempt_id, root, code_revision, processor_version,
            )
            if saved is not None:
                return saved
            if (
                current["completion_sha256"] != completion["completion_sha256"]
                or final_policy != policy
                or final_rows != rows
            ):
                raise Conflict("FileOS v2 document baseline changed")
            if conn.execute(
                "SELECT 1 FROM brain_fileos_v2_document_attempts "
                "WHERE completion_id=%s AND ready", (completion_id,),
            ).fetchone():
                raise Conflict("FileOS v2 documents are already ready")
            stamp = conn.execute("SELECT clock_timestamp() AS observed_at").fetchone()
            assert stamp is not None
            observed_at = stamp["observed_at"]
            self._match_source(root, current, final_policy, observed_at)
            for item in results:
                conn.execute(
                    "INSERT INTO brain_fileos_v2_document_attempt_items(tenant_id,attempt_id,"
                    "completion_id,stage_id,source_id,locator,item_id,candidate_version_id,"
                    "prepared_version_id,evidence_id,outcome,document_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id, attempt_id, completion_id, current["stage_id"],
                        current["source_id"], item["locator"], item["item_id"],
                        item["candidate_version_id"], item["prepared_version_id"],
                        item["evidence_id"], item["outcome"], item["document_id"],
                    ),
                )
            attempt_sha = _attempt_sha(
                attempt_id, completion_id, current["source_id"],
                current["completion_sha256"], current["root_binding_sha256"],
                code_revision, EXTRACTOR_VERSION, processor_version, final_counts,
                ready, observed_at, results,
            )
            inserted = conn.execute(
                "INSERT INTO brain_fileos_v2_document_attempts(tenant_id,id,actor_id,"
                "completion_id,stage_id,source_id,prior_run_id,root_binding_sha256,"
                "completion_sha256,hashed_count,code_revision,text_extractor_version,"
                "document_processor_version,counts,ready,observed_at,attempt_sha256) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING completed_at",
                (
                    ctx.tenant_id, attempt_id, ctx.actor_id, completion_id,
                    current["stage_id"], current["source_id"], current["prior_run_id"],
                    current["root_binding_sha256"], current["completion_sha256"],
                    current["hashed_count"], code_revision, EXTRACTOR_VERSION,
                    processor_version, Jsonb(final_counts), ready, observed_at, attempt_sha,
                ),
            ).fetchone()
            assert inserted is not None
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_documents_ready" if ready else
                "brain.fileos_v2_documents_blocked", "fileos_v2_document_attempt",
                str(attempt_id),
            )
            return FileOSV2DocumentAttempt(
                attempt_id, completion_id, current["source_id"], final_counts, ready,
                attempt_sha, observed_at, inserted["completed_at"], True,
            )
