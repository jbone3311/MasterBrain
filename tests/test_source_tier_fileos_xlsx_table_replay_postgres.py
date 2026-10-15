"""Fictional reviewed XLSX receipt, tenant fence, and stale-source refusal."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from test_sandbox_runner import IMAGE, fake_docker
from test_statement_persistence_postgres import worker

import masterbrain.datacore.current_fileos_xlsx_table_replay as replay_core
from email_brain.store import AccessDenied, Conflict, NotFound
from email_brain.synthetic_formats import SHEET_TYPE, xlsx_bytes
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.document_contract import encode_request, source_for
from masterbrain.datacore.document_worker import extract_document
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.datacore.xlsx_tables_processor import DockerXlsxTableProcessor
from masterbrain.datacore.xlsx_tables_worker import process_request
from masterbrain.knowledge_schema import SourceTierReviewWrite
from masterbrain.source_tier_fileos_xlsx_table_replay import (
    SourceTierFileOSXlsxTableReplayStore,
)
from masterbrain.source_tier_reviews import SourceTierReviews

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant
QUOTE = "Fictional Atlas"


def _prepared(database, tenant, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store, admin = database
    ctx = tenant[0]
    root = tmp_path / "fictional-xlsx"
    root.mkdir()
    raw = xlsx_bytes(QUOTE, 2450, 3, "tableproof")
    (root / "statement.xlsx").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    source_id = stable_id("source", str(uuid4()))
    item_id = stable_id("item", source_id)
    version_id = stable_id("version", item_id)
    evidence_id = stable_id("evidence", version_id)
    source = source_for(raw, version_id, "statement.xlsx", digest, SHEET_TYPE)
    document = extract_document(raw, source)
    assert document.status == "extracted" and QUOTE in document.text
    document_id = stable_id("document", evidence_id, document.text)
    now = datetime(2026, 10, 15, tzinfo=UTC)
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO brain_sources(tenant_id,id,kind,display_name,root_binding_sha256) "
            "VALUES (%s,%s,'fileos','Fictional XLSX replay',%s)",
            (ctx.tenant_id, source_id, fileos_root_binding_sha256(root)),
        )
        conn.execute(
            "INSERT INTO brain_source_items(tenant_id,source_id,id,locator,first_seen_at,"
            "last_seen_at) VALUES (%s,%s,%s,'statement.xlsx',%s,%s)",
            (ctx.tenant_id, source_id, item_id, now, now),
        )
        conn.execute(
            "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,observed_at,"
            "sha256,size_bytes,media_type,metadata) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'{}'::jsonb)",
            (ctx.tenant_id, source_id, item_id, version_id, now, digest,
             len(raw), SHEET_TYPE),
        )
        conn.execute(
            "UPDATE brain_source_items SET current_version_id=%s "
            "WHERE tenant_id=%s AND id=%s", (version_id, ctx.tenant_id, item_id),
        )
        conn.execute(
            "INSERT INTO brain_evidence(tenant_id,id,source_version_id,sha256,storage,"
            "retained) VALUES (%s,%s,%s,%s,'source_bound',false)",
            (ctx.tenant_id, evidence_id, version_id, digest),
        )
        conn.execute(
            "INSERT INTO brain_normalized_documents(tenant_id,id,evidence_id,normalizer,"
            "body_sha256,body) VALUES (%s,%s,%s,%s,%s,%s)",
            (ctx.tenant_id, document_id, evidence_id,
             "sandbox-fileos-document-v1-" + IMAGE.removeprefix("sha256:"),
             hashlib.sha256(document.text.encode()).hexdigest(), document.text),
        )
    reviewer = replace(
        ctx, scopes=ctx.scopes | frozenset({"knowledge.review", "brain.content.read"}),
    )
    body = SourceTierReviewWrite(
        evidence_id=evidence_id, document_id=document_id,
        document_sha256=hashlib.sha256(document.text.encode()).hexdigest(),
        source_version_id=version_id, source_sha256=digest, source_tier="T3",
        authority_kind="internal_record", source_quote=QUOTE,
    )
    review_id = SourceTierReviews(store).publish(
        reviewer, evidence_id, body, uuid4(),
    )["object_id"]
    request = encode_request(raw, version_id, "statement.xlsx", digest, SHEET_TYPE)
    processor, _, _ = fake_docker(
        monkeypatch, processor=DockerXlsxTableProcessor(IMAGE),
        output=process_request(request),
    )
    return store, admin, ctx, root, processor, review_id, item_id, version_id, raw


def test_reviewed_receipt_is_idempotent_content_free_and_immutable(
    database, tenant, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, root, processor, review_id, _, version_id, raw = _prepared(
        database, tenant, tmp_path, monkeypatch,
    )
    replay = SourceTierFileOSXlsxTableReplayStore(store, processor)
    first = replay.record_current_xlsx_table_replay(worker(ctx), review_id, root)
    request = encode_request(
        raw, version_id, "statement.xlsx", hashlib.sha256(raw).hexdigest(), SHEET_TYPE,
    )
    fake_docker(monkeypatch, processor=processor, output=process_request(request))
    assert replay.record_current_xlsx_table_replay(worker(ctx), review_id, root) == first
    assert first == {
        "review_id": review_id, "worker_observed_xlsx_table_replay": True,
        "source_effects": False, "financial_claim_approved": False,
    }
    assert (root / "statement.xlsx").read_bytes() == raw
    with store.transaction(worker(ctx)) as conn:
        saved = conn.execute(
            "SELECT sheet_count,row_count,cell_count,row_layout_sha256,normalizer,"
            "table_processor_version FROM knowledge_source_tier_fileos_xlsx_table_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()
        assert saved is not None
        assert saved["sheet_count"] == 1 and saved["row_count"] == 2
        assert saved["cell_count"] == 8 and len(saved["row_layout_sha256"]) == 64
        assert saved["normalizer"].split("-v1-")[1] == (
            saved["table_processor_version"].split("-v1-")[1]
        )
        for query in (
            "UPDATE knowledge_source_tier_fileos_xlsx_table_replays "
            "SET row_count=3 WHERE review_id=%s",
            "DELETE FROM knowledge_source_tier_fileos_xlsx_table_replays WHERE review_id=%s",
        ):
            with pytest.raises(psycopg.Error), conn.transaction():
                conn.execute(query, (review_id,))
    with psycopg.connect(admin) as conn:
        with pytest.raises(psycopg.errors.RaiseException), conn.transaction():
            conn.execute("TRUNCATE knowledge_source_tier_fileos_xlsx_table_replays")


def test_scope_revocation_and_changed_bytes_leave_no_receipt(
    database, tenant, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, ctx, root, processor, review_id, _, _, _ = _prepared(
        database, tenant, tmp_path, monkeypatch,
    )
    replay = SourceTierFileOSXlsxTableReplayStore(store, processor)
    with pytest.raises(AccessDenied):
        replay.record_current_xlsx_table_replay(ctx, review_id, root)
    with pytest.raises(NotFound):
        replay.record_current_xlsx_table_replay(
            replace(worker(ctx), source_ids=frozenset()), review_id, root,
        )
    with pytest.raises(AccessDenied):
        replay.record_current_xlsx_table_replay(
            worker(ctx), review_id, root,
            authorize=lambda: (_ for _ in ()).throw(AccessDenied("revoked")),
        )
    (root / "statement.xlsx").write_bytes(xlsx_bytes("Changed", 2450, 3, "tableproof"))
    with pytest.raises(Conflict, match="unavailable or changed"):
        replay.record_current_xlsx_table_replay(worker(ctx), review_id, root)
    with store.transaction(worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_fileos_xlsx_table_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0


def test_current_version_race_refuses_receipt(
    database, tenant, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, root, processor, review_id, item_id, version_id, _ = _prepared(
        database, tenant, tmp_path, monkeypatch,
    )
    original = replay_core.read_confined_file

    def race(*args: object, **kwargs: object):
        opened = original(*args, **kwargs)  # type: ignore[arg-type]
        next_version = "version_" + uuid4().hex
        with psycopg.connect(admin) as conn:
            conn.execute(
                "INSERT INTO brain_source_versions(tenant_id,source_id,item_id,id,"
                "observed_at,sha256,size_bytes,media_type,metadata) "
                "SELECT tenant_id,source_id,item_id,%s,observed_at,sha256,"
                "size_bytes,media_type,metadata FROM brain_source_versions "
                "WHERE tenant_id=%s AND id=%s",
                (next_version, ctx.tenant_id, version_id),
            )
            conn.execute(
                "UPDATE brain_source_items SET current_version_id=%s "
                "WHERE tenant_id=%s AND id=%s",
                (next_version, ctx.tenant_id, item_id),
            )
        return opened

    monkeypatch.setattr(replay_core, "read_confined_file", race)
    with pytest.raises(Conflict, match="basis changed"):
        SourceTierFileOSXlsxTableReplayStore(store, processor).record_current_xlsx_table_replay(
            worker(ctx), review_id, root,
        )
    with store.transaction(worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_fileos_xlsx_table_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0
