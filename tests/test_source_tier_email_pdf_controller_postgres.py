"""Fictional private Email PDF command through a tenant-bound PostgreSQL login."""

from __future__ import annotations

import secrets
from unittest.mock import Mock
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from test_sandbox_runner import fake_docker
from test_source_tier_email_pdf_controller import _operator, _private
from test_source_tier_email_pdf_replay_postgres import _prepared, _worker

from email_brain.migrate import grant_tenant_runtime
from email_brain.pdf_contract import encode_request
from email_brain.pdf_worker import process_request
from masterbrain import source_tier_email_pdf_controller as control

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant


def test_check_then_execute_exact_review_with_tenant_bound_login(
    database, tenant, tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, account, raw, processor, review_id, receipt_id = _prepared(
        database, tenant, monkeypatch,
    )
    path, config, credentials = _operator(tmp_path)
    config["account_id"] = str(account)
    credentials[0]["tenant_id"] = str(ctx.tenant_id)
    credentials[0]["actor_id"] = str(ctx.actor_id)
    _private(path, config)
    _private(path.parent / "credentials.json", credentials)
    role = "test_email_pdf_command_" + uuid4().hex[:12]
    password = secrets.token_urlsafe(32)
    with psycopg.connect(admin) as conn:
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password),
            ),
        )
        grant_tenant_runtime(conn, role, ctx.tenant_id)
    tenant_dsn = make_conninfo(admin, user=role, password=password)
    no_processor = Mock(side_effect=AssertionError("check constructed PDF processor"))
    monkeypatch.setattr(control, "DockerPdfProcessor", no_processor)
    assert control.run_source_tier_email_pdf_controller(
        path, tenant_dsn, review_id, check=True, tenant_bound_db=True,
    )["execution_verified"] is False
    no_processor.assert_not_called()
    with store.transaction(_worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_email_pdf_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 0
        part_sha = conn.execute(
            "SELECT sha256 FROM attachment_receipts WHERE id=%s", (receipt_id,),
        ).fetchone()["sha256"]
    fake_docker(
        monkeypatch, processor=processor,
        output=process_request(encode_request(raw, "1.2", part_sha)),
    )
    monkeypatch.setattr(control, "DockerPdfProcessor", Mock(return_value=processor))
    result = control.run_source_tier_email_pdf_controller(
        path, tenant_dsn, review_id, tenant_bound_db=True,
    )
    assert result["worker_observed_pdf_text_replay"] is True
    assert result["financial_claim_approved"] is False
    with store.transaction(_worker(ctx)) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM knowledge_source_tier_email_pdf_replays "
            "WHERE review_id=%s", (review_id,),
        ).fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM knowledge_claims").fetchone()["n"] == 0
    with pytest.raises(control.EmailTierPdfControllerError):
        control.run_source_tier_email_pdf_controller(
            path, database[0].dsn, review_id, check=True, tenant_bound_db=True,
        )
    with pytest.raises(control.EmailTierPdfControllerError):
        control.run_source_tier_email_pdf_controller(
            path, admin, review_id, check=True, tenant_bound_db=True,
        )
