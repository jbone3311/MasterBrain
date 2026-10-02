"""The three legacy Email worker commands under real single-tenant SQL logins."""

import secrets
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
import test_postgres as pg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from test_document_controller_postgres import setup_controller as setup_document
from test_document_jobs import snapshot as document_snapshot
from test_processing_controller import private_write
from test_processing_controller_postgres import setup_job
from test_read_controller_postgres import setup as setup_read

from email_brain.document_controller import run_document_controller
from email_brain.migrate import grant_tenant_runtime
from email_brain.processing_controller import ControllerError, run_controller
from email_brain.read_controller import run_read_controller
from email_brain.schemas import SearchRequest

database, tenant = pg.database, pg.tenant
pytestmark = pytest.mark.postgres


@pytest.fixture
def bound_logins(
    database: tuple[object, str], tenant: tuple[object, UUID]
) -> tuple[str, str, UUID]:
    _, admin = database
    ctx, _ = tenant
    foreign_tenant = uuid4()
    own_role = "test_legacy_bound_" + uuid4().hex[:12]
    foreign_role = "test_legacy_bound_" + uuid4().hex[:12]
    own_password, foreign_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenants(id,name) VALUES (%s,'Other fictional Email worker tenant')",
            (foreign_tenant,),
        )
        for role, password, tenant_id in (
            (own_role, own_password, ctx.tenant_id),
            (foreign_role, foreign_password, foreign_tenant),
        ):
            conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
            grant_tenant_runtime(conn, role, tenant_id)
    return (
        make_conninfo(admin, user=own_role, password=own_password),
        make_conninfo(admin, user=foreign_role, password=foreign_password),
        foreign_tenant,
    )


@pytest.mark.parametrize("kind", ("mime", "document", "read"))
def test_bound_preflight_refuses_shared_foreign_and_owner_login(
    kind: str,
    database: tuple[object, str],
    tenant: tuple[object, UUID],
    bound_logins: tuple[str, str, UUID],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    shared, admin = database
    own_dsn, foreign_dsn, _ = bound_logins
    if kind == "mime":
        path, _, _, _, job, _, factory = setup_job(database, tenant, monkeypatch, tmp_path)

        def check(dsn: str) -> dict:
            return run_controller(path, dsn, check=True, tenant_bound_db=True)

        job_table = "recovery_jobs"
    elif kind == "document":
        path, _, _, _, _, job, _, factory = setup_document(
            database, tenant, monkeypatch, tmp_path
        )

        def check(dsn: str) -> dict:
            return run_document_controller(path, dsn, check=True, tenant_bound_db=True)

        job_table = "document_jobs"
    else:
        path, _, _, mail, transports, _ = setup_read(database, tenant, tmp_path)

        def check(dsn: str) -> dict:
            return run_read_controller(path, dsn, check=True, tenant_bound_db=True)

        job_table = None

    assert check(own_dsn)["configuration_valid"] is True
    for refused_dsn in (shared.dsn, foreign_dsn, admin):
        with pytest.raises(ControllerError):
            check(refused_dsn)
    if job_table is not None:
        factory.assert_not_called()
        with psycopg.connect(admin) as conn:
            assert conn.execute(
                sql.SQL("SELECT status,attempts FROM {} WHERE id=%s").format(
                    sql.Identifier(job_table)
                ),
                (job["id"],),
            ).fetchone() == ("queued", 0)
    else:
        assert not mail.calls and not transports
    private_write(path.parent / "credentials.json", [])
    with pytest.raises(ControllerError):
        check(own_dsn)


@pytest.mark.parametrize("kind", ("mime", "document", "read"))
def test_bound_worker_executes_with_fictional_inputs_only(
    kind: str,
    database: tuple[object, str],
    tenant: tuple[object, UUID],
    bound_logins: tuple[str, str, UUID],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store, _ = database
    ctx, account = tenant
    own_dsn, _, foreign_tenant = bound_logins
    if kind == "mime":
        path, _, _, jobs, job, processor, _ = setup_job(
            database, tenant, monkeypatch, tmp_path
        )
        assert run_controller(path, own_dsn, tenant_bound_db=True)["results"]["completed"] == 1
        assert run_controller(path, own_dsn, tenant_bound_db=True)["results"]["no_result"] == 1
        assert jobs.get(ctx, account, job["id"])["attempts"] == 1
        assert jobs.get(ctx, account, job["id"])["status"] == "completed"
    elif kind == "document":
        path, _, _, _, jobs, job, processor, _ = setup_document(
            database, tenant, monkeypatch, tmp_path
        )
        before = document_snapshot(store, ctx)
        assert run_document_controller(path, own_dsn, tenant_bound_db=True)["results"][
            "completed"
        ] == 1
        assert run_document_controller(path, own_dsn, tenant_bound_db=True)["results"][
            "no_result"
        ] == 1
        assert jobs.get(ctx, account, job["id"])["attempts"] == 1
        assert document_snapshot(store, ctx) == before
        assert processor.extract.call_count == 1
    else:
        path, _, _, mail, _, _ = setup_read(database, tenant, tmp_path)
        def transport() -> httpx.MockTransport:
            return httpx.MockTransport(mail.handle)

        outcomes = [
            run_read_controller(
                path, own_dsn, allow_provider_read=True,
                transport_factory=transport, tenant_bound_db=True,
            )["results"]
            for _ in range(4)
        ]
        assert sum(result["progress"] for result in outcomes) >= 1
        assert len(store.search(ctx, SearchRequest(query="Melron"))) == 1
    with psycopg.connect(own_dsn) as conn:
        conn.execute("SELECT set_config('email_brain.tenant_id', %s, true)",
                     (str(foreign_tenant),))
        assert conn.execute(
            "SELECT id FROM tenants WHERE id=%s", (foreign_tenant,)
        ).fetchall() == []
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute(
                "INSERT INTO brain_sources(tenant_id,id,kind,display_name) "
                "VALUES (%s,'forged_legacy_worker','email','Forged source')",
                (foreign_tenant,),
            )
