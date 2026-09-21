"""SQL locking must not become membership-management authority."""

import psycopg
import pytest
import test_postgres as pg
from psycopg import sql
from test_isolated_recovery import FakeProcessor
from test_recovery_jobs import no_publication, queued

database, tenant = pg.database, pg.tenant
pytestmark = pytest.mark.postgres


def test_lock_helper_privilege_and_search_path_are_narrow(database, tenant):
    store, _ = database
    ctx, account = tenant
    with store.transaction(ctx) as conn:
        helper = conn.execute(
            "SELECT prosecdef,proconfig, EXISTS(SELECT 1 FROM "
            "aclexplode(coalesce(proacl,acldefault('f',proowner))) x "
            "WHERE grantee=0 AND privilege_type='EXECUTE') AS public_execute "
            "FROM pg_proc WHERE oid='public.lock_recovery_owners(uuid,uuid,uuid)'::regprocedure"
        ).fetchone()
        assert helper == {
            "prosecdef": True,
            "proconfig": ["search_path=pg_catalog"],
            "public_execute": False,
        }
        assert conn.execute(
            "SELECT public.lock_recovery_owners(%s,%s,%s) AS allowed",
            (account, ctx.actor_id, ctx.actor_id),
        ).fetchone()["allowed"]
    for table in ("mail_accounts", "tenant_memberships"):
        with store.transaction(ctx) as conn:
            assert not conn.execute(
                "SELECT has_table_privilege(current_user,%s,'UPDATE') AS allowed", (table,)
            ).fetchone()["allowed"]
        column = "status" if table == "mail_accounts" else "role"
        with pytest.raises(psycopg.errors.InsufficientPrivilege), store.transaction(ctx) as conn:
            conn.execute(
                sql.SQL("UPDATE {} SET {}={} WHERE false").format(
                    sql.Identifier(table), sql.Identifier(column), sql.Identifier(column)
                )
            )


def test_lock_helper_cannot_lock_foreign_tenant_authority(database, tenant):
    store, _ = database
    ctx, account = tenant
    other, foreign_account = pg.tenant.__wrapped__(database)
    with store.transaction(ctx) as conn:
        for acct, requester, worker in (
            (foreign_account, other.actor_id, other.actor_id),
            (account, ctx.actor_id, other.actor_id),
            (account, other.actor_id, ctx.actor_id),
        ):
            assert not conn.execute(
                "SELECT public.lock_recovery_owners(%s,%s,%s) AS allowed",
                (acct, requester, worker),
            ).fetchone()["allowed"]


def test_account_disabled_during_processing_blocks_publication(database, tenant, monkeypatch):
    _, admin = database
    ctx, account = tenant
    jobs, _, worker, _, job = queued(database, tenant, monkeypatch)
    processor = FakeProcessor()
    prepare = processor.prepare

    def disabled(raw):
        result = prepare(raw)
        with psycopg.connect(admin) as conn:
            conn.execute("UPDATE mail_accounts SET status='disabled' WHERE id=%s", (account,))
        return result

    monkeypatch.setattr(processor, "prepare", disabled)
    jobs.run_once(worker, account, processor)
    no_publication(admin, ctx)
    assert jobs.get(ctx, account, job["id"])["status"] == "revoked"


def test_terminal_job_cannot_be_reopened_by_runtime(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    jobs, human, _, _, job = queued(database, tenant, monkeypatch)
    jobs.cancel(human, account, job["id"])
    with pytest.raises(psycopg.errors.RaiseException), store.transaction(ctx) as conn:
        conn.execute(
            "UPDATE recovery_jobs SET status='queued',outcome=NULL,completed_at=NULL WHERE id=%s",
            (job["id"],),
        )
    assert jobs.get(ctx, account, job["id"])["status"] == "cancelled"
