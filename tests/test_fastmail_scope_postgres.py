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
from email_brain.schemas import SearchRequest
from email_brain.store import Conflict, IngestItem, InventoryError, NotFound
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


def test_scoped_mailbox_exclusion_hides_old_projection_without_new_content(database, tenant):
    store, admin = database
    ctx, account = tenant
    base = window()
    scope = ScopedMailWindow(base.mailbox_id, base.after, base.before, ("private",))
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE mail_accounts SET provider_account_id='provider-a',"
            "read_scope_sha256=%s WHERE id=%s", (scope.fingerprint(), account)
        )
    mailbox = pg.SyntheticMailbox()
    private = False

    def respond(request: httpx.Request) -> httpx.Response:
        response = mailbox.handle(request)
        if request.method == "POST" and b'"Email/get"' in request.content and private:
            payload = response.json()
            for row in payload["methodResponses"][0][1]["list"]:
                row["mailboxIds"] = {"inbox": True, "private": True}
            return httpx.Response(200, json=payload)
        return response

    def step(expected: str) -> None:
        client = FastmailReadClient(
            "synthetic-transport-token", transport=httpx.MockTransport(respond)
        )
        try:
            assert ReadWorker(store, client, scope=scope).step(ctx, account) == expected
        finally:
            client.close()

    step("progress")  # scope-bound baseline
    step("progress")  # included first inventory
    step("caught_up")
    hits = store.search(ctx, SearchRequest(query="Melron"))
    assert len(hits) == 1
    bridge_ctx = pg.datacore_context(ctx)
    core = pg.DataCoreStore(store)
    core.bridge_current_email_version(
        bridge_ctx, hits[0]["evidence_id"], uuid4(), code_revision="exclusion-test-v1"
    )
    assert len(core.search_current_email(bridge_ctx, "Melron")) == 1
    assert mailbox.downloads == ["m1"]

    private = True
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE sync_workers SET next_attempt_at=now() WHERE account_id=%s", (account,)
        )
    step("progress")  # mixed mailbox membership is excluded before byte lookup
    assert store.search(ctx, SearchRequest(query="Melron")) == []
    assert core.search_current_email(bridge_ctx, "Melron") == []
    assert core.search_current_email_family(bridge_ctx, "Melron").messages == ()
    assert mailbox.downloads == ["m1"]
    assert store.sync_status(ctx, account)["message_counts"] == {
        "ready": 0, "quarantined": 0, "deleted": 0, "excluded": 1,
    }
    with store.transaction(ctx) as conn:
        state = conn.execute(
            "SELECT status FROM message_sync_state WHERE account_id=%s", (account,)
        ).fetchone()
        assert state == {"status": "excluded"}
        assert conn.execute(
            "SELECT count(*) AS n FROM raw_objects WHERE account_id=%s", (account,)
        ).fetchone()["n"] == 1
        assert conn.execute(
            "SELECT count(*) AS n FROM provider_events WHERE account_id=%s "
            "AND kind='exclude_message'", (account,)
        ).fetchone()["n"] == 1
    step("caught_up")

    private = False
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE sync_workers SET next_attempt_at=now() WHERE account_id=%s", (account,)
        )
    step("progress")
    assert len(store.search(ctx, SearchRequest(query="Melron"))) == 1
    assert len(core.search_current_email(bridge_ctx, "Melron")) == 1
    assert store.sync_status(ctx, account)["message_counts"]["ready"] == 1


def test_newly_excluded_message_never_downloads_or_publishes(database, tenant):
    store, admin = database
    ctx, account = tenant
    base = window()
    scope = ScopedMailWindow(base.mailbox_id, base.after, base.before, ("private",))
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE mail_accounts SET provider_account_id='provider-a',"
            "read_scope_sha256=%s WHERE id=%s", (scope.fingerprint(), account)
        )
    mailbox = pg.SyntheticMailbox()

    def respond(request: httpx.Request) -> httpx.Response:
        response = mailbox.handle(request)
        if request.method == "POST" and b'"Email/get"' in request.content:
            payload = response.json()
            for row in payload["methodResponses"][0][1]["list"]:
                row["mailboxIds"] = {"inbox": True, "private": True}
            return httpx.Response(200, json=payload)
        return response

    client = FastmailReadClient(
        "synthetic-transport-token", transport=httpx.MockTransport(respond)
    )
    try:
        for expected in ("progress", "progress", "caught_up"):
            assert ReadWorker(store, client, scope=scope).step(ctx, account) == expected
    finally:
        client.close()
    assert mailbox.downloads == []
    assert store.search(ctx, SearchRequest(query="Melron")) == []
    assert store.sync_status(ctx, account)["message_counts"]["excluded"] == 1
    with store.transaction(ctx) as conn:
        for table in ("raw_objects", "messages", "message_versions", "quarantine_receipts"):
            count = conn.execute(
                f"SELECT count(*) AS n FROM {table} WHERE account_id=%s", (account,)
            ).fetchone()["n"]
            assert count == 0


def test_exclusion_event_requires_pinned_live_scoped_worker(database, tenant):
    store, _ = database
    ctx, account = tenant
    item = IngestItem(
        "synthetic-event", "synthetic-id", "synthetic-version",
        datetime(1970, 1, 1, tzinfo=UTC), exclusion_policy="a" * 64,
    )
    with pytest.raises(Conflict, match="matching scoped worker"):
        store.ingest_page(ctx, account, None, "synthetic-cursor", [item], synthetic_only=True)
