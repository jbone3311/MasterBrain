"""Fictional retained Email XLSX approval-to-isolated-worker result."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from io import BytesIO
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from openpyxl import Workbook
from test_email_xlsx_approvals_postgres import VERSION, _prepared
from test_sandbox_runner import IMAGE, fake_docker

from email_brain.auth import Principal
from email_brain.store import AccessDenied, Conflict, NotFound
from email_brain.synthetic_formats import SHEET_TYPE
from masterbrain.datacore.contracts import stable_id
from masterbrain.datacore.document_contract import encode_request
from masterbrain.datacore.document_processor import DockerDocumentProcessor
from masterbrain.datacore.document_worker import process_request
from masterbrain.email_xlsx_approvals import EmailXlsxApprovals
from masterbrain.email_xlsx_results import EmailXlsxResults

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant


def _worker(ctx: pg.TenantContext) -> pg.TenantContext:
    return replace(ctx, scopes=frozenset({"email.document.process", "email.evidence.read"}))


def _case(database, tenant, monkeypatch: pytest.MonkeyPatch, *, document: bytes | None = None):
    store, admin, ctx, account, attachment, raw, document = _prepared(
        database, tenant, document=document,
    )
    approval = EmailXlsxApprovals(store, VERSION).approve(
        Principal(ctx, "human"), account, attachment, uuid4(),
    )["approval_id"]
    raw_sha = hashlib.sha256(raw).hexdigest()
    part_sha = hashlib.sha256(document).hexdigest()
    version_id = stable_id("version", raw_sha, "1.2", part_sha)
    response = process_request(encode_request(
        document, version_id, "attachment.xlsx", part_sha, SHEET_TYPE,
    ))
    processor, calls, _ = fake_docker(
        monkeypatch, processor=DockerDocumentProcessor(IMAGE), output=response,
    )
    return store, admin, ctx, approval, processor, calls


def test_worker_seals_exact_text_without_publishing(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, approval, processor, calls = _case(database, tenant, monkeypatch)
    result = EmailXlsxResults(store, processor).record(_worker(ctx), approval)
    assert result["changed"] is True and result["document_published"] is False
    assert result["sheet_count"] == 1 and result["cell_count"] == 8
    assert calls
    assert EmailXlsxResults(store, processor).record(_worker(ctx), approval) == {
        **result, "changed": False,
    }
    with store.transaction(ctx) as conn:
        saved = conn.execute(
            "SELECT * FROM brain_email_xlsx_extraction_results WHERE approval_id=%s",
            (approval,),
        ).fetchone()
        assert saved is not None
        assert saved["text_sha256"] == hashlib.sha256(
            saved["extracted_text"].encode(),
        ).hexdigest()
        assert "xlsxapprovalproof" in saved["extracted_text"]
        assert conn.execute(
            "SELECT count(*) AS n FROM brain_email_document_bridge_receipts",
        ).fetchone()["n"] == 0
        for query in (
            "UPDATE brain_email_xlsx_extraction_results SET cell_count=2 "
            "WHERE approval_id=%s",
            "DELETE FROM brain_email_xlsx_extraction_results WHERE approval_id=%s",
        ):
            with pytest.raises(psycopg.Error), conn.transaction():
                conn.execute(query, (approval,))
    with psycopg.connect(admin) as conn:
        with pytest.raises(psycopg.errors.RaiseException), conn.transaction():
            conn.execute(
                "TRUNCATE brain_email_xlsx_extraction_results,"
                "brain_email_xlsx_document_bridge_receipts,"
                "brain_email_xlsx_publication_reviews",
            )


def test_wrong_processor_and_lost_authorization_leave_no_result(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, ctx, approval, processor, _ = _case(database, tenant, monkeypatch)
    wrong = DockerDocumentProcessor("sha256:" + "b" * 64)
    with pytest.raises(NotFound):
        EmailXlsxResults(store, processor).record(
            _worker(ctx), approval, expected_account_id=uuid4(),
        )
    with pytest.raises(Conflict, match="approval expired or processor changed"):
        EmailXlsxResults(store, wrong).record(_worker(ctx), approval)
    with pytest.raises(AccessDenied):
        EmailXlsxResults(store, processor).record(ctx, approval)
    with pytest.raises(AccessDenied):
        EmailXlsxResults(store, processor).record(
            _worker(ctx), approval,
            authorize=lambda: (_ for _ in ()).throw(AccessDenied("revoked")),
        )
    with store.transaction(ctx) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM brain_email_xlsx_extraction_results "
            "WHERE approval_id=%s", (approval,),
        ).fetchone()["n"] == 0


def test_unowned_worker_never_reads_raw_or_replays_result(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, approval, processor, _ = _case(database, tenant, monkeypatch)
    second_owner = uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) "
            "VALUES (%s,%s,'owner')",
            (ctx.tenant_id, second_owner),
        )
        conn.execute(
            "DELETE FROM tenant_memberships WHERE tenant_id=%s AND user_id=%s",
            (ctx.tenant_id, ctx.actor_id),
        )
    alternate_worker = replace(_worker(ctx), actor_id=second_owner)
    reads = 0
    original_load = store.load_raw

    def counted_load(*args, **kwargs):
        nonlocal reads
        reads += 1
        return original_load(*args, **kwargs)

    monkeypatch.setattr(store, "load_raw", counted_load)
    with pytest.raises(AccessDenied, match="owner authorization"):
        EmailXlsxResults(store, processor).record(alternate_worker, approval)
    assert reads == 0
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) "
            "VALUES (%s,%s,'owner')",
            (ctx.tenant_id, ctx.actor_id),
        )
    EmailXlsxResults(store, processor).record(alternate_worker, approval)
    assert reads == 1
    with psycopg.connect(admin) as conn:
        conn.execute(
            "DELETE FROM tenant_memberships WHERE tenant_id=%s AND user_id=%s",
            (ctx.tenant_id, ctx.actor_id),
        )
    with pytest.raises(AccessDenied, match="owner authorization"):
        EmailXlsxResults(store, processor).record(alternate_worker, approval)
    assert reads == 1


def test_cached_result_rechecks_caller_authorization(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, ctx, approval, processor, _ = _case(database, tenant, monkeypatch)
    EmailXlsxResults(store, processor).record(_worker(ctx), approval)
    checks = 0

    def revoked() -> None:
        nonlocal checks
        checks += 1
        raise AccessDenied("worker lease revoked")

    with pytest.raises(AccessDenied, match="worker lease revoked"):
        EmailXlsxResults(store, processor).record(
            _worker(ctx), approval, authorize=revoked,
        )
    assert checks == 1


def test_paused_source_after_approval_refuses_worker(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, ctx, approval, processor, _ = _case(database, tenant, monkeypatch)
    with store.transaction(ctx) as conn:
        source = conn.execute(
            "SELECT source_id FROM brain_email_xlsx_extraction_approvals WHERE id=%s",
            (approval,),
        ).fetchone()
        assert source is not None
        conn.execute("UPDATE brain_sources SET status='paused' WHERE id=%s", (source["source_id"],))
    with pytest.raises(Conflict, match="source changed"):
        EmailXlsxResults(store, processor).record(_worker(ctx), approval)


def test_formula_refuses_complete_result(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    book = Workbook()
    book.active.append(["Amount", "=1+2"])
    output = BytesIO()
    book.save(output)
    book.close()
    store, _, ctx, approval, processor, _ = _case(
        database, tenant, monkeypatch, document=output.getvalue(),
    )
    with pytest.raises(Conflict, match="extraction unavailable"):
        EmailXlsxResults(store, processor).record(_worker(ctx), approval)
    with store.transaction(ctx) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM brain_email_xlsx_extraction_results "
            "WHERE approval_id=%s", (approval,),
        ).fetchone()["n"] == 0


def test_database_rejects_forged_text_digest(
    database, tenant, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _, ctx, approval, processor, _ = _case(database, tenant, monkeypatch)
    EmailXlsxResults(store, processor).record(_worker(ctx), approval)
    with store.transaction(ctx) as conn:
        identity = conn.execute(
            "SELECT account_id,attachment_id FROM brain_email_xlsx_extraction_approvals "
            "WHERE id=%s", (approval,),
        ).fetchone()
    assert identity is not None
    second = EmailXlsxApprovals(store, VERSION).approve(
        Principal(ctx, "human"), identity["account_id"], identity["attachment_id"],
        uuid4(),
    )["approval_id"]
    with store.transaction(_worker(ctx)) as conn:
        row = conn.execute(
            "SELECT * FROM brain_email_xlsx_extraction_results WHERE approval_id=%s",
            (approval,),
        ).fetchone()
        assert row is not None
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute(
                "INSERT INTO brain_email_xlsx_extraction_results("
                "tenant_id,approval_id,worker_actor_id,account_id,parent_version_id,"
                "attachment_id,raw_sha256,part_path,part_sha256,processor_version,"
                "text_sha256,extracted_text,sheet_count,cell_count) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ctx.tenant_id, second, ctx.actor_id,
                    row["account_id"], row["parent_version_id"], row["attachment_id"],
                    row["raw_sha256"], row["part_path"], row["part_sha256"],
                    row["processor_version"], "0" * 64, row["extracted_text"],
                    row["sheet_count"], row["cell_count"],
                ),
            )
