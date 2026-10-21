"""One synthetic reviewed XLSX reaches search through the real worker command."""

from __future__ import annotations

import secrets
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from test_email_xlsx_document_bridge_postgres import _published, _review
from test_email_xlsx_publication_controller import _operator, _private

from email_brain.migrate import grant_tenant_runtime
from masterbrain.datacore.persistence import DataCoreStore
from masterbrain.email_xlsx_document_bridge import EmailXlsxDocumentBridge
from masterbrain.email_xlsx_publication_controller import (
    EmailXlsxPublicationControllerError,
    run_email_xlsx_publication_controller,
)

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant


def test_command_check_then_publish_with_distinct_worker_and_tenant_login(
    database, tenant, tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, admin, reviewer, approval, sealed = _published(database, tenant, monkeypatch)
    reviewed = _review(
        EmailXlsxDocumentBridge(store), reviewer, approval, sealed, uuid4(),
    )
    path, config, credentials = _operator(tmp_path)
    worker_id = uuid4()
    with store.transaction(reviewer.context) as conn:
        row = conn.execute(
            "SELECT account_id FROM brain_email_xlsx_extraction_approvals WHERE id=%s",
            (approval,),
        ).fetchone()
        assert row is not None
        account_id = row["account_id"]
    config["account_id"] = str(account_id)
    credentials[0]["tenant_id"] = str(reviewer.context.tenant_id)
    credentials[0]["actor_id"] = str(worker_id)
    _private(path, config)
    _private(path.parent / "credentials.json", credentials)
    role = "test_email_xlsx_command_" + uuid4().hex[:12]
    password = secrets.token_urlsafe(32)
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) "
            "VALUES (%s,%s,'owner')",
            (reviewer.context.tenant_id, worker_id),
        )
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password),
            ),
        )
        grant_tenant_runtime(conn, role, reviewer.context.tenant_id)
    tenant_dsn = make_conninfo(admin, user=role, password=password)
    key = uuid4()
    checked = run_email_xlsx_publication_controller(
        path, tenant_dsn, reviewed["review_id"], key,
        check=True, tenant_bound_db=True,
    )
    assert checked["execution_verified"] is False
    with store.transaction(reviewer.context) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM brain_email_xlsx_document_bridge_receipts "
            "WHERE approval_id=%s", (approval,),
        ).fetchone()["n"] == 0
    wrong = uuid4()
    config["account_id"] = str(wrong)
    _private(path, config)
    with pytest.raises(EmailXlsxPublicationControllerError):
        run_email_xlsx_publication_controller(
            path, tenant_dsn, reviewed["review_id"], key,
            tenant_bound_db=True,
        )
    config["account_id"] = str(account_id)
    _private(path, config)
    published = run_email_xlsx_publication_controller(
        path, tenant_dsn, reviewed["review_id"], key,
        tenant_bound_db=True,
    )
    assert published["changed"] is True and published["mailbox_effects"] is False
    assert run_email_xlsx_publication_controller(
        path, tenant_dsn, reviewed["review_id"], key,
        tenant_bound_db=True,
    ) == {**published, "changed": False}
    assert any(
        row.document_id == published["document_id"]
        for row in DataCoreStore(store).search_current_email_family(
            reviewer.context, "xlsxapprovalproof",
        ).documents
    )
    with pytest.raises(EmailXlsxPublicationControllerError):
        run_email_xlsx_publication_controller(
            path, admin, reviewed["review_id"], uuid4(),
            check=True, tenant_bound_db=True,
        )
