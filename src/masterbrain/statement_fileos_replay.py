"""Private FileOS-byte replay for one historical statement proposal.

No source effect, claim publication, API route, or reviewed investment is made.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from email_brain.domain.models import TenantContext
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from masterbrain.datacore.current_fileos_text_replay import (
    CurrentFileOSFileUnavailable,
    replay_current_fileos_text,
)
from masterbrain.datacore.extraction import EXTRACTOR_VERSION, MAX_SOURCE_BYTES
from masterbrain.datacore.fileos import fileos_root_binding_sha256

_PROPOSAL_ID = re.compile(r"^statement_[a-f0-9]{32}$")

_BASIS_SQL = (
    "SELECT p.id,p.document_id,p.evidence_id,p.source_version_id,p.source_id,"
    "p.source_kind,p.source_sha256,p.text_sha256,d.body,d.body_sha256,"
    "d.normalizer,e.source_version_id AS evidence_version_id,"
    "e.sha256 AS evidence_sha,v.sha256 AS version_sha,v.size_bytes,"
    "i.locator,i.current_version_id,s.kind AS actual_source_kind,"
    "s.status AS source_status,s.root_binding_sha256 "
    "FROM knowledge_statement_proposals p "
    "JOIN brain_normalized_documents d ON d.tenant_id=p.tenant_id "
    "AND d.id=p.document_id "
    "JOIN brain_evidence e ON e.tenant_id=d.tenant_id AND e.id=d.evidence_id "
    "JOIN brain_source_versions v ON v.tenant_id=e.tenant_id "
    "AND v.id=e.source_version_id "
    "JOIN brain_source_items i ON i.tenant_id=v.tenant_id "
    "AND i.id=v.item_id AND i.source_id=v.source_id "
    "JOIN brain_sources s ON s.tenant_id=i.tenant_id AND s.id=i.source_id "
    "WHERE p.id=%s"
)


def _checked_basis(
    row: dict[str, Any] | None, ctx: TenantContext, root_sha256: str,
) -> dict[str, Any]:
    if row is None or (ctx.source_ids is not None and row["source_id"] not in ctx.source_ids):
        raise NotFound()
    if (
        row["source_kind"] != "fileos"
        or row["actual_source_kind"] != "fileos"
        or row["source_status"] != "active"
        or row["source_version_id"] != row["evidence_version_id"]
        or row["source_version_id"] != row["current_version_id"]
        or row["source_sha256"] != row["evidence_sha"]
        or row["source_sha256"] != row["version_sha"]
        or row["text_sha256"] != row["body_sha256"]
        or row["normalizer"] != EXTRACTOR_VERSION
        or row["root_binding_sha256"] != root_sha256
        or type(row["size_bytes"]) is not int
        or not 0 < row["size_bytes"] <= MAX_SOURCE_BYTES
        or hashlib.sha256(row["body"].encode("utf-8")).hexdigest() != row["text_sha256"]
    ):
        raise Conflict("statement FileOS replay basis changed")
    return row


@dataclass(slots=True)
class StatementFileOSReplayStore:
    store: Store

    def record_current_text_replay(
        self, ctx: TenantContext, proposal_id: str, root: Path,
    ) -> dict[str, Any]:
        """Reacquire one current confined source and seal its exact text replay."""
        self.store.require(ctx, "brain.document.publish")
        if ctx.identity is not None and ctx.identity.client_kind != "worker":
            raise AccessDenied("worker identity required")
        if type(proposal_id) is not str or _PROPOSAL_ID.fullmatch(proposal_id) is None:
            raise NotFound()
        if not isinstance(root, Path):
            raise ValueError("invalid_fileos_root")
        try:
            root_sha256 = fileos_root_binding_sha256(root)
        except (OSError, RuntimeError, ValueError):
            raise Conflict("statement FileOS root unavailable") from None

        with self.store.transaction(ctx) as conn:
            before = _checked_basis(
                conn.execute(_BASIS_SQL, (proposal_id,)).fetchone(), ctx, root_sha256
            )
        try:
            proof = replay_current_fileos_text(
                root,
                locator=before["locator"],
                root_binding_sha256=root_sha256,
                source_sha256=before["source_sha256"],
                source_size_bytes=before["size_bytes"],
                text=before["body"],
                text_sha256=before["text_sha256"],
                normalizer=before["normalizer"],
            )
        except CurrentFileOSFileUnavailable:
            raise Conflict("statement FileOS source unavailable or changed") from None
        except (OSError, RuntimeError, ValueError):
            raise Conflict("statement FileOS text replay failed") from None

        with self.store.transaction(ctx) as conn:
            after = _checked_basis(
                conn.execute(_BASIS_SQL + " FOR SHARE OF i,s", (proposal_id,)).fetchone(),
                ctx, root_sha256,
            )
            if after != before:
                raise Conflict("statement FileOS replay basis changed")
            conn.execute(
                "INSERT INTO knowledge_statement_fileos_replays(tenant_id,proposal_id,"
                "document_id,evidence_id,source_version_id,source_id,actor_id,"
                "source_sha256,source_size_bytes,text_sha256,normalizer,"
                "root_binding_sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tenant_id,proposal_id) DO NOTHING",
                (
                    ctx.tenant_id, proposal_id, after["document_id"], after["evidence_id"],
                    after["source_version_id"], after["source_id"], ctx.actor_id,
                    proof.source_sha256, proof.source_size_bytes, proof.text_sha256,
                    proof.normalizer, root_sha256,
                ),
            )
            saved = conn.execute(
                "SELECT document_id,evidence_id,source_version_id,source_id,source_sha256,"
                "source_size_bytes,text_sha256,normalizer,root_binding_sha256 "
                "FROM knowledge_statement_fileos_replays WHERE proposal_id=%s",
                (proposal_id,),
            ).fetchone()
            fields = (
                "document_id", "evidence_id", "source_version_id", "source_id",
                "source_sha256", "source_size_bytes", "text_sha256", "normalizer",
                "root_binding_sha256",
            )
            if saved is None or tuple(saved[field] for field in fields) != (
                after["document_id"], after["evidence_id"], after["source_version_id"],
                after["source_id"], proof.source_sha256, proof.source_size_bytes,
                proof.text_sha256, proof.normalizer, root_sha256,
            ):
                raise Conflict("statement FileOS replay receipt differs")
            self.store.audit(
                conn, ctx, "knowledge.statement_fileos_replay", "statement_proposal",
                proposal_id,
            )
        return {
            "proposal_id": proposal_id,
            "worker_observed_text_replay": True,
            "reviewed": False,
            "source_effects": False,
        }
