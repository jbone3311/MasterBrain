"""Disposable SQL and fictional Fastmail proof of the scoped lease boundary."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import psycopg
import pytest
import test_postgres as pg

from email_brain.connectors.fastmail import FastmailReadClient
from email_brain.connectors.jmap import ScopedMailWindow
from email_brain.store import InventoryError, NotFound
from email_brain.sync import Checkpoint, ReadWorker
from email_brain.sync_store import SyncStore

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant


def window() -> ScopedMailWindow:
    return ScopedMailWindow(
        "inbox", datetime(2026, 9, 18, tzinfo=UTC), datetime(2026, 9, 21, tzinfo=UTC)
    )


def pin(database, tenant) -> None:
    _, admin = database
    _, account = tenant
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE mail_accounts SET provider_account_id='provider-a',"
            "read_scope_sha256=%s WHERE id=%s", (window().fingerprint(), account)
        )


def test_scoped_account_refuses_old_worker_insert_and_unscoped_acquire(database, tenant):
    store, admin = database
    ctx, account = tenant
    pin(database, tenant)
    with pytest.raises(psycopg.Error), psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO sync_workers(tenant_id,account_id) VALUES (%s,%s)",
            (ctx.tenant_id, account),
        )
    with pytest.raises(InventoryError):
        SyncStore(store).acquire(ctx, account)
    different = ScopedMailWindow(
        "other", datetime(2026, 9, 18, tzinfo=UTC), datetime(2026, 9, 21, tzinfo=UTC)
    )
    with pytest.raises(InventoryError):
        SyncStore(store).acquire(ctx, account, scope=different)
    with store.transaction(ctx) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM sync_workers WHERE account_id=%s", (account,)
        ).fetchone()["n"] == 0


def test_scope_enrollment_refuses_prior_unscoped_worker_and_cursor(database, tenant):
    store, admin = database
    ctx, account = tenant
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE mail_accounts SET provider_account_id='provider-a' WHERE id=%s",
            (account,),
        )
    lease = SyncStore(store).acquire(ctx, account)
    assert lease is not None
    with pytest.raises(psycopg.Error), psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE mail_accounts SET read_scope_sha256=%s WHERE id=%s",
            (window().fingerprint(), account),
        )
    with pytest.raises(psycopg.Error), psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO sync_cursors(tenant_id,account_id,scope,cursor_kind,opaque_cursor) "
            "VALUES (%s,%s,'email','provider',%s)",
            (
                ctx.tenant_id, account,
                Checkpoint(
                    schema_version=4, generation=uuid4(), phase="listing",
                    email_state="scoped-inventory",
                    scope_sha256=window().fingerprint(),
                ).encode(),
            ),
        )


def test_scoped_lease_refuses_foreign_tenant(database, tenant):
    store, _ = database
    _, account = tenant
    pin(database, tenant)
    foreign_ctx, _ = pg.tenant.__wrapped__(database)
    with pytest.raises(NotFound):
        SyncStore(store).acquire(foreign_ctx, account, scope=window())


def test_scoped_lease_cursor_and_crash_takeover_fence(database, tenant):
    store, admin = database
    ctx, account = tenant
    pin(database, tenant)
    jobs = SyncStore(store)
    lease = jobs.acquire(ctx, account, scope=window())
    assert lease is not None and lease.cursor is None
    checkpoint = Checkpoint(
        schema_version=4, generation=uuid4(), phase="listing",
        email_state="scoped-inventory", scope_sha256=window().fingerprint(),
    )
    assert store.ingest_page(
        ctx, account, None, checkpoint.encode(), [], lease_token=lease.token
    ) == 0
    with store.transaction(ctx) as conn:
        row = conn.execute(
            "SELECT read_scope_sha256,scope_claim_token,lease_token "
            "FROM sync_workers WHERE account_id=%s", (account,)
        ).fetchone()
        assert row == {
            "read_scope_sha256": window().fingerprint(),
            "scope_claim_token": lease.token, "lease_token": lease.token,
        }
    with pytest.raises(psycopg.Error), psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE sync_workers SET lease_token=%s,lease_until=clock_timestamp() "
            "WHERE account_id=%s", (uuid4(), account)
        )
    wrong = checkpoint.model_copy(update={"scope_sha256": "0" * 64}).encode()
    with pytest.raises(psycopg.Error), psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE sync_cursors SET opaque_cursor=%s WHERE account_id=%s AND scope='email'",
            (wrong, account),
        )
    with pytest.raises(psycopg.Error), psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE mail_accounts SET read_scope_sha256=%s WHERE id=%s",
            ("1" * 64, account),
        )
    jobs.finish(ctx, account, lease.token, "progress")
    with store.transaction(ctx) as conn:
        row = conn.execute(
            "SELECT lease_token,scope_claim_token FROM sync_workers WHERE account_id=%s",
            (account,),
        ).fetchone()
        assert row == {"lease_token": None, "scope_claim_token": None}


def test_scoped_http_worker_restarts_without_wide_change_request(database, tenant):
    store, _ = database
    ctx, account = tenant
    pin(database, tenant)
    mailbox = pg.SyntheticMailbox()
    methods = []

    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            method, args, _ = json.loads(request.content)["methodCalls"][0]
            methods.append(method)
            if method == "Email/query":
                assert args["filter"] == window().query_filter()
            assert method != "Email/changes"
        return mailbox.handle(request)

    for expected in ("progress", "progress", "caught_up"):
        client = FastmailReadClient(
            "synthetic-transport-token", transport=httpx.MockTransport(respond)
        )
        try:
            assert ReadWorker(store, client, scope=window()).step(ctx, account) == expected
        finally:
            client.close()
    assert methods == ["Email/query", "Email/get"]
    assert mailbox.downloads == ["m1"]
    with store.transaction(ctx) as conn:
        cursor = conn.execute(
            "SELECT opaque_cursor FROM sync_cursors WHERE account_id=%s AND scope='email'",
            (account,),
        ).fetchone()["opaque_cursor"]
        saved = Checkpoint.model_validate_json(cursor)
        assert saved.schema_version == 4 and saved.phase == "listing"
        assert saved.scope_sha256 == window().fingerprint()
