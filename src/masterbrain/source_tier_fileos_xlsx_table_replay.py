"""Worker-only, nonpublishing replay receipt for one reviewed FileOS XLSX."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.datacore.current_fileos_xlsx_table_replay import (
    CurrentFileOSXlsxTableUnavailable,
    replay_current_fileos_xlsx_tables,
)
from masterbrain.datacore.document_contract import MAX_DOCUMENT_BYTES, SHEET_TYPE
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.datacore.xlsx_tables_processor import DockerXlsxTableProcessor

_REVIEW_ID = re.compile(r"^stier_[a-f0-9]{32}$")
_SOURCE_ID = re.compile(r"^[a-z][a-z0-9_-]{0,127}$")
_NORMALIZER = re.compile(r"^sandbox-fileos-document-v1-([a-f0-9]{64})$")
_BASIS_SQL = (
    "SELECT r.id,r.evidence_id,r.document_id,r.source_version_id,"
    "r.source_sha256,r.document_sha256,r.source_quote,"
    "d.body,d.body_sha256,d.normalizer,"
    "e.source_version_id AS evidence_version_id,e.sha256 AS evidence_sha,"
    "e.storage AS evidence_storage,e.retained AS evidence_retained,"
    "v.sha256 AS version_sha,v.size_bytes,v.media_type,"
    "i.locator,i.current_version_id,s.id AS source_id,s.kind AS source_kind,"
    "s.status AS source_status,s.root_binding_sha256,"
    "public.brain_email_evidence_is_excluded(e.tenant_id,e.id) AS excluded "
    "FROM knowledge_source_tier_reviews r "
    "JOIN brain_normalized_documents d ON d.tenant_id=r.tenant_id "
    "AND d.id=r.document_id "
    "JOIN brain_evidence e ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id "
    "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
    "AND v.id=e.source_version_id "
    "JOIN brain_source_items i ON i.tenant_id=v.tenant_id "
    "AND i.id=v.item_id AND i.source_id=v.source_id "
    "JOIN brain_sources s ON s.tenant_id=i.tenant_id AND s.id=i.source_id "
    "WHERE r.id=%s"
)


def _checked_basis(
    row: dict[str, Any] | None, ctx: TenantContext, root_sha256: str,
    expected_source_id: str | None, processor_version: str,
) -> dict[str, Any]:
    if row is None or (ctx.source_ids is not None and row["source_id"] not in ctx.source_ids):
        raise NotFound()
    if expected_source_id is not None and row["source_id"] != expected_source_id:
        raise NotFound()
    image = _NORMALIZER.fullmatch(row["normalizer"])
    if (
        image is None
        or processor_version != "sandbox-xlsx-tables-v1-" + image.group(1)
        or row["source_kind"] != "fileos"
        or row["source_status"] != "active"
        or row["excluded"] is not False
        or row["evidence_storage"] != "source_bound"
        or row["evidence_retained"] is not False
        or row["source_version_id"] != row["evidence_version_id"]
        or row["source_version_id"] != row["current_version_id"]
        or row["source_sha256"] != row["evidence_sha"]
        or row["source_sha256"] != row["version_sha"]
        or row["document_sha256"] != row["body_sha256"]
        or row["root_binding_sha256"] != root_sha256
        or row["media_type"] != SHEET_TYPE
        or type(row["locator"]) is not str
        or not row["locator"].lower().endswith(".xlsx")
        or type(row["size_bytes"]) is not int
        or not 0 < row["size_bytes"] <= MAX_DOCUMENT_BYTES
        or row["source_quote"] not in row["body"]
        or hashlib.sha256(row["body"].encode("utf-8")).hexdigest()
        != row["document_sha256"]
    ):
        raise Conflict("source tier FileOS XLSX replay basis changed")
    return row


@dataclass(slots=True)
class SourceTierFileOSXlsxTableReplayStore:
    store: Store
    processor: DockerXlsxTableProcessor

    def record_current_xlsx_table_replay(
        self, ctx: TenantContext, review_id: str, root: Path,
        *, expected_source_id: str | None = None,
        authorize: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        """Reacquire a reviewed XLSX and seal only its observed row-layout digest."""
        self.store.require(ctx, "brain.document.publish")
        if ctx.identity is not None and ctx.identity.client_kind != "worker":
            raise AccessDenied("worker identity required")
        if type(review_id) is not str or _REVIEW_ID.fullmatch(review_id) is None:
            raise NotFound()
        if not isinstance(root, Path) or type(self.processor) is not DockerXlsxTableProcessor:
            raise ValueError("invalid_fileos_xlsx_table_replay")
        if expected_source_id is not None and (
            type(expected_source_id) is not str
            or _SOURCE_ID.fullmatch(expected_source_id) is None
        ):
            raise ValueError("invalid_expected_source")
        processor_version = self.processor.processor_version
        if not processor_version.startswith("sandbox-xlsx-tables-v1-"):
            raise ValueError("invalid_xlsx_table_processor_version")
        try:
            root_sha256 = fileos_root_binding_sha256(root)
        except (OSError, RuntimeError, ValueError):
            raise Conflict("source tier FileOS XLSX root unavailable") from None
        with self.store.transaction(ctx) as conn:
            before = _checked_basis(
                conn.execute(_BASIS_SQL, (review_id,)).fetchone(), ctx,
                root_sha256, expected_source_id, processor_version,
            )
        try:
            proof = replay_current_fileos_xlsx_tables(
                root, locator=before["locator"], version_id=before["source_version_id"],
                root_binding_sha256=root_sha256,
                source_sha256=before["source_sha256"],
                source_size_bytes=before["size_bytes"],
                text_sha256=before["document_sha256"],
                normalizer=before["normalizer"], processor=self.processor,
            )
        except CurrentFileOSXlsxTableUnavailable:
            raise Conflict("source tier FileOS XLSX unavailable or changed") from None
        with self.store.transaction(ctx) as conn:
            after = _checked_basis(
                conn.execute(_BASIS_SQL + " FOR SHARE OF i,s", (review_id,)).fetchone(),
                ctx, root_sha256, expected_source_id, processor_version,
            )
            if after != before:
                raise Conflict("source tier FileOS XLSX replay basis changed")
            if authorize is not None:
                authorize()
            conn.execute(
                "INSERT INTO knowledge_source_tier_fileos_xlsx_table_replays("
                "tenant_id,review_id,evidence_id,document_id,source_version_id,source_id,"
                "actor_id,source_sha256,source_size_bytes,text_sha256,normalizer,"
                "table_processor_version,row_layout_sha256,sheet_count,row_count,"
                "cell_count,root_binding_sha256) VALUES ("
                "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,review_id) DO NOTHING",
                (ctx.tenant_id, review_id, after["evidence_id"], after["document_id"],
                 after["source_version_id"], after["source_id"], ctx.actor_id,
                 proof.source_sha256, proof.source_size_bytes, proof.text_sha256,
                 after["normalizer"], proof.table_processor_version,
                 proof.row_layout_sha256, proof.sheet_count, proof.row_count,
                 proof.cell_count, root_sha256),
            )
            fields = (
                "evidence_id", "document_id", "source_version_id", "source_id",
                "source_sha256", "source_size_bytes", "text_sha256", "normalizer",
                "table_processor_version", "row_layout_sha256", "sheet_count",
                "row_count", "cell_count", "root_binding_sha256",
            )
            saved = conn.execute(
                "SELECT " + ",".join(fields)
                + " FROM knowledge_source_tier_fileos_xlsx_table_replays WHERE review_id=%s",
                (review_id,),
            ).fetchone()
            expected = (
                after["evidence_id"], after["document_id"], after["source_version_id"],
                after["source_id"], proof.source_sha256, proof.source_size_bytes,
                proof.text_sha256, after["normalizer"], proof.table_processor_version,
                proof.row_layout_sha256, proof.sheet_count, proof.row_count,
                proof.cell_count, root_sha256,
            )
            if saved is None or tuple(saved[field] for field in fields) != expected:
                raise Conflict("source tier FileOS XLSX replay receipt differs")
            self.store.audit(
                conn, ctx, "knowledge.source_tier_fileos_xlsx_table_replayed", "stier",
                review_id,
            )
        return {
            "review_id": review_id,
            "worker_observed_xlsx_table_replay": True,
            "source_effects": False,
            "financial_claim_approved": False,
        }
