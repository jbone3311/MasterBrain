"""Synthetic-only, exact-occurrence XLSX extraction approval boundary."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient

from email_brain.api import create_app
from email_brain.auth import Credential, Principal, TokenRegistry
from email_brain.store import AccessDenied, NotFound
from email_brain.synthetic_formats import SHEET_TYPE, xlsx_bytes
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.persistence import DataCoreStore
from masterbrain.email_xlsx_approvals import POLICY, EmailXlsxApprovals

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant
VERSION = "sandbox-fileos-document-v1-" + "a" * 64


def _mail(document: bytes) -> bytes:
    message = EmailMessage()
    message["From"] = "sender@example.invalid"
    message["To"] = "owner@example.invalid"
    message["Subject"] = "Fictional workbook"
    message.set_content("Synthetic message")
    message.add_attachment(
        document, maintype="application",
        subtype=SHEET_TYPE.removeprefix("application/"), filename="rent.xlsx",
    )
    message.set_boundary("synthetic-xlsx-approval-boundary")
    return message.as_bytes()


def _prepared(database, tenant, *, document: bytes | None = None):
    store, admin = database
    ctx, account = tenant
    document = document if document is not None else xlsx_bytes(
        "Fictional Atlas", 2450, 3, "xlsxapprovalproof",
    )
    raw = _mail(document)
    store.ingest_page(
        ctx, account, None, "xlsx-approval-ready", [replace(pg.item(), raw=raw)],
    )
    with store.transaction(ctx) as conn:
        receipt = conn.execute(
            "SELECT id,evidence_id FROM attachment_receipts WHERE account_id=%s",
            (account,),
        ).fetchone()
    assert receipt is not None
    core = DataCoreStore(store)
    bridge_ctx = pg.datacore_context(ctx)
    core.bridge_current_email_version(
        bridge_ctx, receipt["evidence_id"], uuid4(), code_revision="xlsx-approval-test-v1",
    )
    core.bridge_email_attachment(
        bridge_ctx, receipt["id"], uuid4(), code_revision="xlsx-approval-test-v1",
    )
    return store, admin, ctx, account, receipt["id"], raw, document


def test_owner_api_approves_only_one_current_synthetic_xlsx(database, tenant) -> None:
    store, _, ctx, account, receipt, _, _ = _prepared(database, tenant)
    token = "fictional-xlsx-approval-" + uuid4().hex
    owner = Credential(
        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
        scopes={"email.review", "email.evidence.read"},
        expires_at=datetime.now(UTC) + timedelta(hours=1), client_kind="human",
    )
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid4())}
    path = f"/v1/accounts/{account}/attachments/{receipt}/xlsx-approvals"
    with TestClient(create_app(store, TokenRegistry([owner]),
                               xlsx_document_processor_version=VERSION)) as api:
        first = api.post(path, headers=headers)
        assert first.status_code == 201
        assert first.json()["approval_id"].startswith("xapp_")
        assert first.json()["changed"] is True
        assert first.json()["mailbox_effects"] is False
        assert first.json()["document_published"] is False
        again = api.post(path, headers=headers)
        assert again.status_code == 201
        assert again.json() == {**first.json(), "changed": False}
        assert api.post(path, headers={"Authorization": f"Bearer {token}"}).status_code == 422
        missing = path.replace(str(receipt), str(uuid4()))
        assert api.post(missing, headers=headers).status_code == 404
    with TestClient(create_app(store, TokenRegistry([owner]))) as api:
        assert api.post(path, headers=headers).status_code == 503
    assistant = owner.model_copy(update={
        "client_kind": "assistant", "scopes": {"brain.search"},
    })
    with TestClient(create_app(store, TokenRegistry([assistant]),
                               xlsx_document_processor_version=VERSION)) as api:
        assert api.post(path, headers=headers).status_code == 403


def test_exact_human_approval_is_immutable_and_does_not_publish(database, tenant) -> None:
    store, admin, ctx, account, receipt, raw, document = _prepared(database, tenant)
    approvals = EmailXlsxApprovals(store, VERSION)
    key = uuid4()
    first = approvals.approve(Principal(ctx, "human"), account, receipt, key)
    assert first["changed"] is True and first["document_published"] is False
    assert approvals.approve(Principal(ctx, "human"), account, receipt, key) == {
        **first, "changed": False,
    }
    with store.transaction(ctx) as conn:
        row = conn.execute(
            "SELECT * FROM brain_email_xlsx_extraction_approvals WHERE id=%s",
            (first["approval_id"],),
        ).fetchone()
        assert row is not None
        assert row["raw_sha256"] == hashlib.sha256(raw).hexdigest()
        assert row["part_sha256"] == hashlib.sha256(document).hexdigest()
        assert row["part_path"] == "1.2" and row["policy_version"] == POLICY
        assert row["expires_at"] == row["created_at"] + pg.timedelta(hours=1)
        assert conn.execute(
            "SELECT count(*) AS n FROM brain_email_document_bridge_receipts",
        ).fetchone()["n"] == 0
        for query in (
            "UPDATE brain_email_xlsx_extraction_approvals SET part_path='1.3' WHERE id=%s",
            "DELETE FROM brain_email_xlsx_extraction_approvals WHERE id=%s",
        ):
            with pytest.raises(psycopg.Error), conn.transaction():
                conn.execute(query, (first["approval_id"],))
    with psycopg.connect(admin) as conn:
        with pytest.raises(psycopg.errors.RaiseException), conn.transaction():
            conn.execute(
                "TRUNCATE brain_email_xlsx_extraction_approvals,"
                "brain_email_xlsx_extraction_results,"
                "brain_email_xlsx_document_bridge_receipts,"
                "brain_email_xlsx_publication_reviews",
            )


def test_nonhuman_and_wrong_account_refuse(database, tenant) -> None:
    store, _, ctx, account, receipt, _, _ = _prepared(database, tenant)
    approvals = EmailXlsxApprovals(store, VERSION)
    for kind in ("assistant", "worker"):
        with pytest.raises(AccessDenied):
            approvals.approve(Principal(ctx, kind), account, receipt, uuid4())
    with pytest.raises(NotFound):
        approvals.approve(Principal(ctx, "human"), account, uuid4(), uuid4())
    with pytest.raises(AccessDenied):
        approvals.approve(Principal(ctx, "human"), uuid4(), receipt, uuid4())


def test_paused_source_refuses_new_approval(database, tenant) -> None:
    store, _, ctx, account, receipt, _, _ = _prepared(database, tenant)
    with store.transaction(ctx) as conn:
        row = conn.execute(
            "SELECT source_id FROM brain_email_attachment_bridge_receipts "
            "WHERE legacy_attachment_id=%s", (receipt,),
        ).fetchone()
        assert row is not None
        conn.execute("UPDATE brain_sources SET status='paused' WHERE id=%s", (row["source_id"],))
    with pytest.raises(NotFound):
        EmailXlsxApprovals(store, VERSION).approve(
            Principal(ctx, "human"), account, receipt, uuid4(),
        )


def test_sql_guard_refuses_forged_parent_hash(database, tenant) -> None:
    store, _, ctx, account, receipt, _, _ = _prepared(database, tenant)
    approved = EmailXlsxApprovals(store, VERSION).approve(
        Principal(ctx, "human"), account, receipt, uuid4(),
    )
    forged_key = uuid4()
    forged_id = stable_id(
        "xapp", str(ctx.tenant_id), str(ctx.actor_id), str(forged_key),
    )
    with store.transaction(ctx) as conn:
        with pytest.raises(psycopg.errors.RaiseException), conn.transaction():
            conn.execute(
                "INSERT INTO brain_email_xlsx_extraction_approvals("
                "tenant_id,id,actor_id,idempotency_key,account_id,parent_version_id,"
                "attachment_id,source_id,source_event_key,raw_sha256,raw_size_bytes,"
                "part_path,part_sha256,part_size_bytes,processor_version,policy_version,"
                "request_sha256) SELECT tenant_id,%s,actor_id,%s,account_id,"
                "parent_version_id,attachment_id,source_id,source_event_key,%s,"
                "raw_size_bytes,part_path,part_sha256,part_size_bytes,"
                "processor_version,policy_version,request_sha256 "
                "FROM brain_email_xlsx_extraction_approvals WHERE id=%s",
                (forged_id, forged_key, "0" * 64, approved["approval_id"]),
            )
        assert conn.execute(
            "SELECT count(*) AS n FROM brain_email_xlsx_extraction_approvals "
            "WHERE id=%s", (forged_id,),
        ).fetchone()["n"] == 0
