"""The private XLSX extraction command reaches one exact synthetic approval."""

from __future__ import annotations

import secrets
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from test_email_xlsx_extraction_controller import IMAGE, _config
from test_email_xlsx_publication_controller import _private
from test_email_xlsx_results_postgres import _case

from email_brain.migrate import grant_tenant_runtime
from masterbrain import email_xlsx_extraction_controller as control
from masterbrain.email_xlsx_extraction_controller import (
    EmailXlsxExtractionControllerError,
    run_email_xlsx_extraction_controller,
)

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant


def test_command_check_then_extracts_with_distinct_worker_and_tenant_login(
    database, tenant, tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, ctx, approval, processor, calls = _case(database, tenant, monkeypatch)
    monkeypatch.setattr(control, "DockerDocumentProcessor", lambda *_args, **_kw: processor)
    path, config, credentials = _config(tmp_path)
    worker_id = uuid4()
    with store.transaction(ctx) as conn:
        row = conn.execute(
            "SELECT account_id FROM brain_email_xlsx_extraction_approvals WHERE id=%s",
            (approval,),
        ).fetchone()
        assert row is not None
        account_id = row["account_id"]
    config["account_id"] = str(account_id)
    config["document_image_id"] = IMAGE
    credentials[0]["tenant_id"] = str(ctx.tenant_id)
    credentials[0]["actor_id"] = str(worker_id)
    _private(path, config)
    _private(path.parent / "credentials.json", credentials)
    role = "test_email_xlsx_extract_" + uuid4().hex[:12]
    password = secrets.token_urlsafe(32)
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) "
            "VALUES (%s,%s,'owner')", (ctx.tenant_id, worker_id),
        )
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password),
            ),
        )
        grant_tenant_runtime(conn, role, ctx.tenant_id)
    tenant_dsn = make_conninfo(admin, user=role, password=password)
    checked = run_email_xlsx_extraction_controller(
        path, tenant_dsn, approval, check=True, tenant_bound_db=True,
    )
    assert checked == {
        "configuration_valid": True, "execution_verified": False,
        "source_effects": False, "data_effects": False,
    }
    with store.transaction(ctx) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM brain_email_xlsx_extraction_results "
            "WHERE approval_id=%s", (approval,),
        ).fetchone()["n"] == 0
    assert not calls
    other_account = uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
            "VALUES (%s,%s,'fastmail','other@example.invalid','synthetic:none')",
            (other_account, ctx.tenant_id),
        )
    config["account_id"] = str(other_account)
    _private(path, config)
    assert run_email_xlsx_extraction_controller(
        path, tenant_dsn, approval, check=True, tenant_bound_db=True,
    )["configuration_valid"] is True
    with pytest.raises(EmailXlsxExtractionControllerError):
        run_email_xlsx_extraction_controller(
            path, tenant_dsn, approval, tenant_bound_db=True,
        )
    assert not calls
    config["account_id"] = str(account_id)
    _private(path, config)
    sealed = run_email_xlsx_extraction_controller(
        path, tenant_dsn, approval, tenant_bound_db=True,
    )
    assert sealed["changed"] is True and sealed["document_published"] is False
    assert sealed["mailbox_effects"] is False and calls
    assert run_email_xlsx_extraction_controller(
        path, tenant_dsn, approval, tenant_bound_db=True,
    ) == {**sealed, "changed": False}
    with store.transaction(ctx) as conn:
        result = conn.execute(
            "SELECT text_sha256,sheet_count,cell_count FROM "
            "brain_email_xlsx_extraction_results WHERE approval_id=%s", (approval,),
        ).fetchone()
        assert result is not None
        assert result["text_sha256"] == sealed["text_sha256"]
        assert result["sheet_count"] == sealed["sheet_count"]
        assert result["cell_count"] == sealed["cell_count"]
    with pytest.raises(EmailXlsxExtractionControllerError):
        run_email_xlsx_extraction_controller(
            path, admin, approval, check=True, tenant_bound_db=True,
        )
