"""Historical later FileOS v2 documents; never current or absence authority."""

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
from masterbrain.datacore.fileos_v2_completed_preview import _locked_later_observation
from masterbrain.datacore.fileos_v2_later_evidence import FileOSV2LaterEvidencePreparer
from masterbrain.datacore.fileos_v2_later_packets import _load_packet
from masterbrain.datacore.persistence import (
    DataCoreStore,
    _canonical_digest,
    _fileos_v2_staged_rows,
)

ATTEMPT_VERSION = "masterbrain-fileos-v2-later-document-attempt-v1"
HASHED_OUTCOMES = (
    "extracted", "empty", "unsupported", "deferred", "changed", "failed",
)
SOURCE_OUTCOMES = {
    "deferred": "deferred_source",
    "excluded": "excluded_source",
    "error": "scan_error",
}
OUTCOMES = (*HASHED_OUTCOMES, *SOURCE_OUTCOMES.values())


@dataclass(frozen=True, slots=True)
class FileOSV2LaterDocumentAttempt:
    attempt_id: UUID
    preparation_id: UUID
    source_id: str
    counts: dict[str, int]
    ready: bool
    attempt_sha256: str
    observed_at: datetime
    completed_at: datetime
    recorded: bool
    publishable: bool = False
    absence_authorized: bool = False


def _attempt_sha(
    attempt_id: UUID,
    preparation_id: UUID,
    source_id: str,
    preparation_sha256: str,
    root_binding_sha256: str,
    code_revision: str,
    text_extractor_version: str,
    document_processor_version: str | None,
    counts: Mapping[str, int],
    ready: bool,
    observed_at: datetime,
    items: list[dict[str, str | None]],
) -> str:
    return _canonical_digest({
        "version": ATTEMPT_VERSION,
        "attempt_id": str(attempt_id),
        "preparation_id": str(preparation_id),
        "source_id": source_id,
        "preparation_sha256": preparation_sha256,
        "root_binding_sha256": root_binding_sha256,
        "code_revision": code_revision,
        "text_extractor_version": text_extractor_version,
        "document_processor_version": document_processor_version,
        "counts": dict(counts),
        "ready": ready,
        "observed_at": observed_at.astimezone(UTC).isoformat(),
        "items": items,
    })


class FileOSV2LaterDocumentPublisher:
    def __init__(
        self, core: DataCoreStore, document_processor: DocumentProcessor | None = None
    ) -> None:
        self.core = core
        self.document_processor = document_processor
        self.evidence = FileOSV2LaterEvidencePreparer(core)

    def _load_basis(
        self, conn: Connection[dict[str, Any]], preparation_id: UUID
    ) -> tuple[dict[str, Any], dict[str, Any], list[tuple[Any, ...]], dict[str, dict[str, Any]]]:
        self.evidence._inspect_locked(conn, preparation_id)
        prep = conn.execute(
            "SELECT id,closure_id,packet_id,completion_id,source_id,"
            "root_binding_sha256,preparation_sha256,policy_sha256,"
            "matched_rows_sha256,prepared_observed_at "
            "FROM brain_fileos_v2_later_evidence_preparations WHERE id=%s",
            (preparation_id,),
        ).fetchone()
        assert prep is not None
        packet_row, _ = _load_packet(conn, prep["packet_id"])
        candidate = packet_row["packet"]["candidate"]
        rows = sorted(
            _fileos_v2_staged_rows(candidate, prep["source_id"]),
            key=lambda row: row[1],
        )
        prepared_rows = conn.execute(
            "SELECT locator,item_id,candidate_version_id,prepared_version_id,"
            "evidence_id,sha256,size_bytes,media_type "
            "FROM brain_fileos_v2_later_prepared_rows "
            "WHERE preparation_id=%s ORDER BY locator COLLATE \"C\"",
            (preparation_id,),
        ).fetchall()
        mapping = {row["locator"]: row for row in prepared_rows}
        if len(mapping) != candidate["counts"]["hashed"]:
            raise Conflict("FileOS v2 later document evidence requires review")
        return prep, packet_row, rows, mapping

    @staticmethod
    def _match_source(
        ctx: TenantContext,
        conn: Connection[dict[str, Any]],
        prep: Mapping[str, Any],
        packet_row: Mapping[str, Any],
        rows: list[tuple[Any, ...]],
        root: Path,
    ) -> datetime:
        _completion, fresh, _preview, observed_at = _locked_later_observation(
            ctx, conn, prep["completion_id"], root
        )
        candidate = packet_row["packet"]["candidate"]
        try:
            fresh_rows = sorted(
                _fileos_v2_staged_rows(fresh, prep["source_id"]),
                key=lambda row: row[1],
            )
            if (
                fresh["root_binding"] != candidate["root_binding"]
                or fresh["policy"] != candidate["policy"]
                or fresh_rows != rows
                or fresh["counts"]["errors"] != 0
                or observed_at <= prep["prepared_observed_at"]
            ):
                raise ValueError("source changed")
        except (KeyError, TypeError, ValueError) as exc:
            raise Conflict("FileOS v2 later document source changed") from exc
        return observed_at

    def _saved_attempt(
        self,
        conn: Connection[dict[str, Any]],
        attempt_id: UUID,
        preparation_id: UUID | None,
        actor_id: UUID | None,
        code_revision: str | None,
        processor_version: str | None,
        root: Path | None,
    ) -> FileOSV2LaterDocumentAttempt | None:
        saved = conn.execute(
            "SELECT id,actor_id,preparation_id,source_id,root_binding_sha256,"
            "preparation_sha256,code_revision,text_extractor_version,"
            "document_processor_version,counts,ready,observed_at,attempt_sha256,"
            "completed_at,publishable,absence_authorized "
            "FROM brain_fileos_v2_later_document_attempts WHERE id=%s",
            (attempt_id,),
        ).fetchone()
        if saved is None:
            return None
        prep, _packet, rows, mapping = self._load_basis(conn, saved["preparation_id"])
        items = conn.execute(
            "SELECT locator,kind,item_id,candidate_version_id,"
            "prepared_version_id,evidence_id,outcome,document_id "
            "FROM brain_fileos_v2_later_document_attempt_items "
            "WHERE attempt_id=%s ORDER BY locator COLLATE \"C\"",
            (attempt_id,),
        ).fetchall()
        try:
            if len(items) != len(rows):
                raise ValueError("incomplete items")
            counts = Counter(item["outcome"] for item in items)
            for expected, item in zip(rows, items, strict=True):
                kind, locator, item_id, version_id, *_ = expected
                if item["kind"] != kind or item["locator"] != locator:
                    raise ValueError("item coverage")
                if kind == "hashed":
                    prepared = mapping[locator]
                    if (
                        item["item_id"] != item_id
                        or item["candidate_version_id"] != version_id
                        or item["prepared_version_id"] != prepared["prepared_version_id"]
                        or item["evidence_id"] != prepared["evidence_id"]
                        or item["outcome"] not in HASHED_OUTCOMES
                    ):
                        raise ValueError("hashed item identity")
                elif (
                    item["item_id"] is not None
                    or item["candidate_version_id"] is not None
                    or item["prepared_version_id"] is not None
                    or item["evidence_id"] is not None
                    or item["outcome"] != SOURCE_OUTCOMES[kind]
                ):
                    raise ValueError("nonhashed item identity")
            expected_counts = {outcome: counts[outcome] for outcome in OUTCOMES}
            expected_sha = _attempt_sha(
                saved["id"], saved["preparation_id"], saved["source_id"],
                saved["preparation_sha256"], saved["root_binding_sha256"],
                saved["code_revision"], saved["text_extractor_version"],
                saved["document_processor_version"], expected_counts,
                saved["ready"], saved["observed_at"], items,
            )
            if (
                (preparation_id is not None
                 and saved["preparation_id"] != preparation_id)
                or saved["source_id"] != prep["source_id"]
                or saved["preparation_sha256"] != prep["preparation_sha256"]
                or saved["text_extractor_version"] != EXTRACTOR_VERSION
                or saved["counts"] != expected_counts
                or saved["ready"] is not (
                    not expected_counts["changed"]
                    and not expected_counts["failed"]
                    and not expected_counts["scan_error"]
                )
                or saved["attempt_sha256"] != expected_sha
                or saved["publishable"] is not False
                or saved["absence_authorized"] is not False
                or (actor_id is not None and saved["actor_id"] != actor_id)
                or (code_revision is not None and saved["code_revision"] != code_revision)
                or (actor_id is not None
                    and saved["document_processor_version"] != processor_version)
                or (root is not None and fileos_root_binding_sha256(root)
                    != saved["root_binding_sha256"])
            ):
                raise ValueError("attempt identity")
        except (KeyError, TypeError, ValueError) as exc:
            raise Conflict("FileOS v2 later document integrity requires review") from exc
        return FileOSV2LaterDocumentAttempt(
            attempt_id=saved["id"],
            preparation_id=saved["preparation_id"],
            source_id=saved["source_id"],
            counts=dict(saved["counts"]),
            ready=saved["ready"],
            attempt_sha256=saved["attempt_sha256"],
            observed_at=saved["observed_at"],
            completed_at=saved["completed_at"],
            recorded=False,
        )

    def inspect(
        self, ctx: TenantContext, attempt_id: UUID
    ) -> FileOSV2LaterDocumentAttempt:
        self.core.store.require(ctx, "brain.changes.read")
        if not isinstance(attempt_id, UUID):
            raise ValueError("invalid FileOS v2 later document attempt identity")
        with self.core.store.transaction(ctx) as conn:
            saved = self._saved_attempt(
                conn, attempt_id, None, None, None, None, None
            )
            if saved is None:
                raise NotFound()
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_document_attempt_read",
                "fileos_v2_later_document_attempt", str(attempt_id),
            )
            return saved

    def publish(
        self,
        principal: Principal,
        preparation_id: UUID,
        attempt_id: UUID,
        root: Path,
        *,
        code_revision: str,
        authorize: Callable[[], None] | None = None,
    ) -> FileOSV2LaterDocumentAttempt:
        if principal.client_kind != "worker":
            raise AccessDenied("FileOS v2 later document worker required")
        ctx = principal.context
        for scope in (
            "brain.fileos.transition.publish", "brain.document.publish", "brain.changes.read"
        ):
            self.core.store.require(ctx, scope)
        processor_version = (
            self.document_processor.processor_version
            if self.document_processor is not None else None
        )
        if (
            not isinstance(preparation_id, UUID)
            or not isinstance(attempt_id, UUID)
            or not isinstance(root, Path)
            or not isinstance(code_revision, str)
            or not code_revision
            or len(code_revision) > 200
            or "\x00" in code_revision
            or (processor_version is not None and (
                not processor_version or len(processor_version) > 200
                or "\x00" in processor_version
            ))
        ):
            raise ValueError("invalid FileOS v2 later document publication")
        if authorize is not None:
            authorize()
        with self.core.store.transaction(ctx) as conn:
            saved = self._saved_attempt(
                conn, attempt_id, preparation_id, ctx.actor_id,
                code_revision, processor_version, root,
            )
            if saved is not None:
                return saved
            prep, packet_row, rows, mapping = self._load_basis(conn, preparation_id)
            if conn.execute(
                "SELECT 1 FROM brain_fileos_v2_later_document_attempts "
                "WHERE preparation_id=%s AND ready", (preparation_id,),
            ).fetchone():
                raise Conflict("FileOS v2 later documents are already ready")
            self._match_source(ctx, conn, prep, packet_row, rows, root)

        results: list[dict[str, str | None]] = []
        counts: Counter[str] = Counter()
        for kind, locator, item_id, version_id, sha, size, media, _reason in rows:
            if authorize is not None:
                authorize()
            prepared_version_id = None
            evidence_id = None
            document_id = None
            if kind == "hashed":
                prepared = mapping[locator]
                prepared_version_id = prepared["prepared_version_id"]
                evidence_id = prepared["evidence_id"]
                item = {
                    "locator": locator,
                    "version_id": prepared_version_id,
                    "digest": {"algorithm": "sha256", "value": sha},
                    "size_bytes": size,
                    "media_type": media,
                }
                suffix = PurePosixPath(locator).suffix.lower()
                extraction = (
                    extract_document_source_version(root, item, self.document_processor)
                    if self.document_processor is not None and suffix in DOCUMENT_SUFFIXES
                    else extract_source_version(root, item)
                )
                if authorize is not None:
                    authorize()
                outcome = extraction.status.value
                if extraction.status is ExtractionStatus.EXTRACTED:
                    published = self.core.publish_text(
                        ctx, prepared_version_id, extraction.text,
                        code_revision=code_revision,
                        normalizer=(
                            processor_version or EXTRACTOR_VERSION
                            if self.document_processor is not None
                            and suffix in DOCUMENT_SUFFIXES
                            else EXTRACTOR_VERSION
                        ),
                    )
                    document_id = published.document_id
            else:
                outcome = SOURCE_OUTCOMES[kind]
            counts[outcome] += 1
            results.append({
                "locator": locator,
                "kind": kind,
                "item_id": item_id if kind == "hashed" else None,
                "candidate_version_id": version_id if kind == "hashed" else None,
                "prepared_version_id": prepared_version_id,
                "evidence_id": evidence_id,
                "outcome": outcome,
                "document_id": document_id,
            })
        final_counts = {outcome: counts[outcome] for outcome in OUTCOMES}
        ready = not (
            final_counts["changed"] or final_counts["failed"]
            or final_counts["scan_error"]
        )
        if authorize is not None:
            authorize()
        with self.core.store.transaction(ctx) as conn:
            saved = self._saved_attempt(
                conn, attempt_id, preparation_id, ctx.actor_id,
                code_revision, processor_version, root,
            )
            if saved is not None:
                return saved
            current, packet_now, current_rows, current_mapping = self._load_basis(
                conn, preparation_id
            )
            saved = self._saved_attempt(
                conn, attempt_id, preparation_id, ctx.actor_id,
                code_revision, processor_version, root,
            )
            if saved is not None:
                return saved
            if conn.execute(
                "SELECT 1 FROM brain_fileos_v2_later_document_attempts "
                "WHERE preparation_id=%s AND ready", (preparation_id,),
            ).fetchone():
                raise Conflict("FileOS v2 later documents are already ready")
            if (
                current["preparation_sha256"] != prep["preparation_sha256"]
                or packet_now["packet_sha256"] != packet_row["packet_sha256"]
                or current_rows != rows
                or current_mapping != mapping
            ):
                raise Conflict("FileOS v2 later document basis changed")
            observed_at = self._match_source(
                ctx, conn, current, packet_now, current_rows, root
            )
            for result in results:
                conn.execute(
                    "INSERT INTO brain_fileos_v2_later_document_attempt_items("
                    "tenant_id,attempt_id,preparation_id,source_id,locator,kind,"
                    "item_id,candidate_version_id,prepared_version_id,evidence_id,"
                    "outcome,document_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        ctx.tenant_id, attempt_id, preparation_id,
                        current["source_id"], result["locator"], result["kind"],
                        result["item_id"], result["candidate_version_id"],
                        result["prepared_version_id"], result["evidence_id"],
                        result["outcome"], result["document_id"],
                    ),
                )
            digest = _attempt_sha(
                attempt_id, preparation_id, current["source_id"],
                current["preparation_sha256"], current["root_binding_sha256"],
                code_revision, EXTRACTOR_VERSION, processor_version,
                final_counts, ready, observed_at, results,
            )
            inserted = conn.execute(
                "INSERT INTO brain_fileos_v2_later_document_attempts(tenant_id,id,"
                "actor_id,preparation_id,closure_id,packet_id,completion_id,"
                "source_id,root_binding_sha256,preparation_sha256,code_revision,"
                "text_extractor_version,document_processor_version,counts,"
                "ready,observed_at,attempt_sha256) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING completed_at",
                (
                    ctx.tenant_id, attempt_id, ctx.actor_id, preparation_id,
                    current["closure_id"], current["packet_id"],
                    current["completion_id"], current["source_id"],
                    current["root_binding_sha256"], current["preparation_sha256"],
                    code_revision, EXTRACTOR_VERSION, processor_version,
                    Jsonb(final_counts), ready, observed_at, digest,
                ),
            ).fetchone()
            assert inserted is not None
            self.core.store.audit(
                conn, ctx, "brain.fileos_v2_later_documents_attempted",
                "fileos_v2_later_document_attempt", str(attempt_id),
            )
            return FileOSV2LaterDocumentAttempt(
                attempt_id=attempt_id,
                preparation_id=preparation_id,
                source_id=current["source_id"],
                counts=final_counts,
                ready=ready,
                attempt_sha256=digest,
                observed_at=observed_at,
                completed_at=inserted["completed_at"],
                recorded=True,
            )
