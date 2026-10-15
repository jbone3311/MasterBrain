"""Synthetic review-to-DataCore bridge for one exact Email XLSX occurrence."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from test_email_xlsx_results_postgres import _case, _worker

from email_brain.auth import Principal
from email_brain.store import AccessDenied, Conflict, NotFound
from masterbrain.datacore.persistence import DataCoreStore
from masterbrain.email_xlsx_document_bridge import EmailXlsxDocumentBridge
from masterbrain.email_xlsx_results import EmailXlsxResults

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant


def _published(database, tenant, monkeypatch: pytest.MonkeyPatch):
    store, admin, ctx, approval, processor, _ = _case(database, tenant, monkeypatch)
    sealed = EmailXlsxResults(store, processor).record(_worker(ctx), approval)
    shared = pg.datacore_context(ctx)
    reviewer = Principal(
        replace(shared, scopes=shared.scopes | {"brain.content.read"}), "human",
    )
    return store, admin, reviewer, approval, sealed


def _publish(bridge, reviewer, approval, sealed, key, *, revision="xlsx-bridge-test-v1"):
    return bridge.publish(
        reviewer, approval, key, expected_text_sha256=sealed["text_sha256"],
        expected_sheet_count=sealed["sheet_count"],
        expected_cell_count=sealed["cell_count"], code_revision=revision,
    )


def test_reviewed_xlsx_publishes_exact_cited_document_and_replays(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, reviewer, approval, sealed = _published(database, tenant, monkeypatch)
    core = DataCoreStore(store)
    bridge = EmailXlsxDocumentBridge(store)
    key = uuid4()
    published = _publish(bridge, reviewer, approval, sealed, key)
    assert published["changed"] is True and published["mailbox_effects"] is False
    assert published["chunk_count"] > 0
    hit = core.search(reviewer.context, "xlsxapprovalproof")
    assert any(row.document_id == published["document_id"] for row in hit)
    family = core.search_current_email_family(reviewer.context, "xlsxapprovalproof")
    assert any(row.document_id == published["document_id"] for row in family.documents)
    content = core.evidence_content(reviewer.context, published["evidence_id"])
    assert "xlsxapprovalproof" in content["content"]
    assert _publish(bridge, reviewer, approval, sealed, key) == {
        **published, "changed": False,
    }
    with pytest.raises(Conflict, match="different provenance"):
        _publish(bridge, reviewer, approval, sealed, uuid4(), revision="different")
    with pytest.raises(Conflict, match="reviewed result identity changed"):
        bridge.publish(
            reviewer, approval, uuid4(), expected_text_sha256="0" * 64,
            expected_sheet_count=sealed["sheet_count"],
            expected_cell_count=sealed["cell_count"],
            code_revision="xlsx-bridge-test-v1",
        )
    with store.transaction(reviewer.context) as conn:
        receipt = conn.execute(
            "SELECT * FROM brain_email_xlsx_document_bridge_receipts "
            "WHERE approval_id=%s", (approval,),
        ).fetchone()
        assert receipt is not None
        assert receipt["evidence_id"] == published["evidence_id"]
        assert conn.execute(
            "SELECT count(*) AS n FROM brain_provenance WHERE output_id=%s",
            (published["document_id"],),
        ).fetchone()["n"] == 1
        with pytest.raises(
            psycopg.errors.RaiseException,
            match="invalid Email XLSX document bridge basis",
        ), conn.transaction():
            conn.execute(
                "INSERT INTO brain_email_xlsx_document_bridge_receipts("
                "tenant_id,actor_id,idempotency_key,approval_id,account_id,"
                "attachment_id,source_id,item_id,version_id,evidence_id,"
                "document_id,normalizer,text_sha256,chunk_count,code_revision,"
                "request_hash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    reviewer.context.tenant_id, reviewer.context.actor_id, uuid4(),
                    receipt["approval_id"], receipt["account_id"],
                    receipt["attachment_id"], receipt["source_id"],
                    receipt["item_id"], receipt["version_id"],
                    receipt["evidence_id"], receipt["document_id"],
                    receipt["normalizer"], receipt["text_sha256"],
                    receipt["chunk_count"] + 1, receipt["code_revision"],
                    receipt["request_hash"],
                ),
            )
        with pytest.raises(psycopg.Error), conn.transaction():
            conn.execute(
                "DELETE FROM brain_email_xlsx_document_bridge_receipts "
                "WHERE approval_id=%s", (approval,),
            )
    with psycopg.connect(admin) as conn:
        with pytest.raises(psycopg.errors.RaiseException), conn.transaction():
            conn.execute("TRUNCATE brain_email_xlsx_document_bridge_receipts")


def test_source_scoped_reader_cannot_see_xlsx_derivative(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, reviewer, approval, sealed = _published(database, tenant, monkeypatch)
    publication = _publish(
        EmailXlsxDocumentBridge(store), reviewer, approval, sealed, uuid4(),
    )
    scoped = replace(reviewer.context, source_ids=frozenset({"unrelated_source"}))
    core = DataCoreStore(store)
    assert core.search(scoped, "xlsxapprovalproof") == []
    assert core.search_current_email_family(scoped, "xlsxapprovalproof").documents == ()
    with pytest.raises(NotFound):
        core.evidence_content(scoped, publication["evidence_id"])


def test_paused_source_hides_published_xlsx_from_generic_brain_reads(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, reviewer, approval, sealed = _published(database, tenant, monkeypatch)
    core = DataCoreStore(store)
    publication = _publish(
        EmailXlsxDocumentBridge(store), reviewer, approval, sealed, uuid4(),
    )
    assert core.search(reviewer.context, "xlsxapprovalproof")
    with store.transaction(reviewer.context) as conn:
        conn.execute(
            "UPDATE brain_sources SET status='paused' WHERE id=%s",
            (publication["source_id"],),
        )
    assert not any(
        row.document_id == publication["document_id"]
        for row in core.search(reviewer.context, "xlsxapprovalproof")
    )
    assert not any(
        row.document_id == publication["document_id"]
        for row in core.search_current_email_family(reviewer.context, "xlsxapprovalproof").documents
    )
    with pytest.raises(NotFound):
        core.evidence_content(reviewer.context, publication["evidence_id"])


def test_no_result_or_nonhuman_cannot_publish(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, ctx, approval, _, _ = _case(database, tenant, monkeypatch)
    reviewer = Principal(pg.datacore_context(ctx), "human")
    bridge = EmailXlsxDocumentBridge(store)
    with pytest.raises(Conflict, match="not complete"):
        bridge.publish(
            reviewer, approval, uuid4(), expected_text_sha256="0" * 64,
            expected_sheet_count=1, expected_cell_count=1,
            code_revision="xlsx-bridge-test-v1",
        )
    with pytest.raises(AccessDenied, match="human document review required"):
        bridge.publish(
            Principal(pg.datacore_context(ctx), "assistant"),
            approval, uuid4(), expected_text_sha256="0" * 64,
            expected_sheet_count=1, expected_cell_count=1,
            code_revision="xlsx-bridge-test-v1",
        )
