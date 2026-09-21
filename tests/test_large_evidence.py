"""Encrypted raw evidence through actual PostgreSQL, synthetic data only."""

import hashlib
import secrets
from dataclasses import asdict, replace
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from test_service import TOKEN, registry

from email_brain.api import create_app
from email_brain.auth import Principal
from email_brain.blobs import MAX_BLOB_BYTES, BlobError, EncryptedBlobStore
from email_brain.connectors.fastmail import FastmailReadClient
from email_brain.domain.models import TenantContext
from email_brain.normalize import MAX_RAW_BYTES, PARSER_VERSION
from email_brain.recovery import Recovery
from email_brain.schemas import SearchRequest
from email_brain.store import AccessDenied, Conflict, NotFound, Store
from email_brain.sync import ReadWorker

database, tenant = pg.database, pg.tenant


@pytest.fixture
def external(database, tenant, tmp_path):
    runtime, _ = database
    ctx, _ = tenant
    blobs = EncryptedBlobStore(
        tmp_path.resolve() / "objects",
        {(ctx.tenant_id, "test-key"): secrets.token_bytes(32)},
        {ctx.tenant_id: "test-key"},
    )
    return Store(runtime.dsn, blobs=blobs)


def large():
    return b"Subject: Synthetic attachment-heavy message\r\n\r\n" + b"x" * MAX_RAW_BYTES


@pytest.mark.parametrize("case", ["count", "individual", "aggregate", "inline"])
def test_direct_staging_is_bounded_before_database_or_disk(case, monkeypatch):
    store = Store("unused", blobs=MagicMock(spec=EncryptedBlobStore))
    ctx = TenantContext(uuid4(), uuid4(), frozenset({"email.ingest"}), uuid4())
    monkeypatch.setattr(store, "transaction", lambda *args: pytest.fail("overbudget SQL"))
    if case == "count":
        items = [pg.item()] * 101
    elif case == "individual":
        items = [replace(pg.item(), raw=b"x" * (MAX_BLOB_BYTES + 1))]
    elif case == "aggregate":
        items = [replace(pg.item(), raw=b"x" * (MAX_BLOB_BYTES // 2 + 1))] * 2
    else:
        store.blobs = None
        items = [replace(pg.item(), raw=large())]
    with pytest.raises(ValueError):
        store.stage_raw(ctx, uuid4(), items)


def test_storage_api_failure_is_scrubbed(monkeypatch):
    monkeypatch.setattr(Recovery, "retry", lambda *args: (_ for _ in ()).throw(BlobError()))
    app = create_app(MagicMock(spec=Store), registry({"email.review", "email.evidence.read"}))
    result = TestClient(app).post(
        f"/v1/accounts/{uuid4()}/quarantine/{uuid4()}/retry",
        json={"expected_parser_version": PARSER_VERSION},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert result.status_code == 503
    assert result.json() == {"error": "evidence_storage_unavailable"}


@pytest.mark.postgres
def test_large_mail_is_encrypted_held_and_healthy_mail_progresses(external, tenant):
    ctx, account = tenant
    raw = large()
    items = [replace(pg.item("large"), raw=raw), replace(pg.item("good"), provider_id="healthy")]
    assert external.ingest_page(ctx, account, None, "done", items) == 2
    assert external.ingest_page(ctx, account, None, "done", items) == 0
    status = external.sync_status(ctx, account)
    assert status["message_counts"] == {"ready": 1, "quarantined": 1, "deleted": 0}
    held = external.quarantines(ctx, account)["results"]
    assert len(held) == 1 and held[0]["reason"] == "mime_too_large"
    assert len(external.search(ctx, SearchRequest(query="Melron"))) == 1
    sha = hashlib.sha256(raw).hexdigest()
    assert external.load_raw(ctx, account, sha) == raw
    with external.transaction(ctx) as conn:
        rows = conn.execute("SELECT raw_mime,blob_ref,raw_size FROM raw_objects").fetchall()
        assert len(rows) == 2 and all(row["raw_mime"] is None for row in rows)
        assert {row["raw_size"] for row in rows} == {len(i.raw) for i in items}
        assert all(
            row["blob_ref"]["object_key"].startswith(f"v1/{ctx.tenant_id}/{account}/")
            for row in rows
        )
    report = external.object_inventory(ctx, account)
    assert report["referenced"] == report["present"] == 2
    assert report["missing"] == report["unreferenced"] == []
    assert report["deletion_authorized"] is False and report["snapshot_consistent"] is False
    with pytest.raises(Conflict, match="parser budget"):
        Recovery(external).retry(Principal(ctx, "human"), account, held[0]["id"], PARSER_VERSION)
    with external.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM recovery_attempts").fetchone()["n"] == 0


@pytest.mark.postgres
def test_sql_rollback_leaves_reportable_encrypted_orphan_then_reuses_it(
    external, tenant, monkeypatch
):
    ctx, account = tenant
    with monkeypatch.context() as patch:
        patch.setattr(
            external,
            "record_attachments",
            lambda *args: (_ for _ in ()).throw(RuntimeError("synthetic rollback")),
        )
        with pytest.raises(RuntimeError):
            external.ingest_page(ctx, account, None, "done", [pg.item()])
    report = external.object_inventory(ctx, account)
    assert report["referenced"] == 0 and report["present"] == 1
    assert len(report["unreferenced"]) == 1 and report["missing"] == []
    with external.transaction(ctx) as conn:
        for table in ("raw_objects", "messages", "provider_events", "sync_cursors"):
            assert conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == 0
    external.ingest_page(ctx, account, None, "done", [pg.item()])
    assert external.object_inventory(ctx, account)["unreferenced"] == []


@pytest.mark.postgres
def test_storage_failure_cannot_advance_cursor(external, tenant, monkeypatch):
    ctx, account = tenant
    monkeypatch.setattr(external.blobs, "put", lambda *args: (_ for _ in ()).throw(BlobError()))
    with pytest.raises(BlobError):
        external.ingest_page(ctx, account, None, "done", [pg.item()])
    with external.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM sync_cursors").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM raw_objects").fetchone()["n"] == 0


@pytest.mark.postgres
def test_authorization_precedes_object_write_or_read(external, database, tenant, monkeypatch):
    ctx, account = tenant
    monkeypatch.setattr(external.blobs, "put", lambda *args: pytest.fail("unauthorized disk write"))
    with pytest.raises(AccessDenied):
        external.ingest_page(replace(ctx, actor_id=uuid4()), account, None, "x", [pg.item()])
    foreign, _ = pg.tenant.__wrapped__(database)
    with pytest.raises(NotFound):
        external.ingest_page(foreign, account, None, "x", [pg.item()])
    monkeypatch.setattr(external.blobs, "get", lambda *args: pytest.fail("unauthorized disk read"))
    with pytest.raises(NotFound):
        external.load_raw(foreign, account, "a" * 64)
    with pytest.raises(AccessDenied):
        external.object_inventory(replace(ctx, scopes=frozenset()), account)


@pytest.mark.postgres
def test_enrolled_account_cannot_be_seeded_into_external_storage(
    external, database, tenant, monkeypatch
):
    ctx, account = tenant
    with psycopg.connect(database[1]) as conn:
        conn.execute(
            "UPDATE mail_accounts SET provider_account_id='enrolled' WHERE id=%s", (account,)
        )
    monkeypatch.setattr(external.blobs, "put", lambda *args: pytest.fail("seed wrote objects"))
    with pytest.raises(ValueError, match="unenrolled"):
        external.ingest_page(ctx, account, None, "x", [pg.item()], synthetic_only=True)


@pytest.mark.postgres
@pytest.mark.parametrize("change", ["membership", "inactive", "enrollment"])
def test_authority_changed_during_staging_cannot_publish(
    external, database, tenant, monkeypatch, change
):
    ctx, account = tenant
    put = external.blobs.put

    def stage_then_revoke(*args):
        ref = put(*args)
        with psycopg.connect(database[1]) as conn:
            if change == "membership":
                conn.execute(
                    "UPDATE tenant_memberships SET role='member' WHERE tenant_id=%s AND user_id=%s",
                    (ctx.tenant_id, ctx.actor_id),
                )
            elif change == "inactive":
                conn.execute("UPDATE mail_accounts SET status='paused' WHERE id=%s", (account,))
            else:
                conn.execute(
                    "UPDATE mail_accounts SET provider_account_id='enrolled' WHERE id=%s",
                    (account,),
                )
        return ref

    monkeypatch.setattr(external.blobs, "put", stage_then_revoke)
    expected = {"membership": AccessDenied, "inactive": NotFound, "enrollment": ValueError}
    with pytest.raises(expected[change]):
        external.ingest_page(ctx, account, None, "x", [pg.item()], synthetic_only=True)
    # Owner access may now be revoked. Inspect only this synthetic tenant as test admin.
    with psycopg.connect(database[1]) as conn:
        for table in ("raw_objects", "provider_events", "messages", "sync_cursors"):
            assert (
                conn.execute(
                    f"SELECT count(*) FROM {table} WHERE tenant_id=%s", (ctx.tenant_id,)
                ).fetchone()[0]
                == 0
            )
    assert len(external.blobs.object_keys(ctx.tenant_id, account)) == 1


@pytest.mark.postgres
def test_persisted_manifest_survives_rotation_and_missing_old_key_blocks_replay(
    database, tenant, tmp_path
):
    ctx, account = tenant
    keys = {
        (ctx.tenant_id, "old"): secrets.token_bytes(32),
        (ctx.tenant_id, "new"): secrets.token_bytes(32),
    }
    root = tmp_path.resolve() / "rotation"
    store = Store(database[0].dsn, blobs=EncryptedBlobStore(root, keys, {ctx.tenant_id: "old"}))
    store.ingest_page(ctx, account, None, "one", [pg.item()])
    with store.transaction(ctx) as conn:
        original = conn.execute("SELECT * FROM raw_objects").fetchone()
    store.blobs = EncryptedBlobStore(root, keys, {ctx.tenant_id: "new"})
    assert store.ingest_page(ctx, account, "one", "two", [pg.item("second")]) == 1
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT * FROM raw_objects").fetchone() == original
    assert store.load_raw(ctx, account, original["sha256"]) == pg.item().raw
    assert len(store.blobs.object_keys(ctx.tenant_id, account)) == 1
    store.blobs = EncryptedBlobStore(
        root, {(ctx.tenant_id, "new"): keys[(ctx.tenant_id, "new")]}, {ctx.tenant_id: "new"}
    )
    with pytest.raises(BlobError):
        store.ingest_page(ctx, account, "two", "three", [pg.item("third")])
    with store.transaction(ctx) as conn:
        assert (
            conn.execute("SELECT opaque_cursor FROM sync_cursors").fetchone()["opaque_cursor"]
            == "two"
        )
        assert conn.execute("SELECT * FROM raw_objects").fetchone() == original


@pytest.mark.postgres
def test_missing_backend_or_object_refuses_recovery_without_cached_failure(
    external, tenant, monkeypatch
):
    ctx, account = tenant
    external.ingest_page(ctx, account, None, "held", [replace(pg.item(), raw=b"")])
    receipt = external.quarantines(ctx, account)["results"][0]["id"]
    for store in (Store(external.dsn), external):
        with monkeypatch.context() as patch:
            if store.blobs:
                patch.setattr(store.blobs, "get", lambda *args: (_ for _ in ()).throw(BlobError()))
            with pytest.raises(BlobError):
                Recovery(store).retry(Principal(ctx, "human"), account, receipt, PARSER_VERSION)
    with external.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM recovery_attempts").fetchone()["n"] == 0
    assert (
        Recovery(external).retry(Principal(ctx, "human"), account, receipt, PARSER_VERSION)[
            "outcome"
        ]
        == "mime_rejected"
    )


@pytest.mark.postgres
def test_inline_history_is_not_silently_moved_when_backend_is_enabled(external, database, tenant):
    ctx, account = tenant
    inline = database[0]
    raw = pg.item().raw
    inline.ingest_page(ctx, account, None, "old", [pg.item()])
    with inline.transaction(ctx) as conn:
        before = conn.execute("SELECT * FROM raw_objects").fetchall()
    external.ingest_page(ctx, account, "old", "new", [pg.item("new")])
    with external.transaction(ctx) as conn:
        assert conn.execute("SELECT * FROM raw_objects").fetchall() == before
    assert external.load_raw(ctx, account, hashlib.sha256(raw).hexdigest()) == raw
    assert external.object_inventory(ctx, account)["present"] == 0


@pytest.mark.postgres
def test_default_and_aggregate_limits_fail_before_any_storage(
    database, external, tenant, monkeypatch
):
    ctx, account = tenant
    with pytest.raises(ValueError):
        database[0].ingest_page(ctx, account, None, "large", [replace(pg.item(), raw=large())])
    monkeypatch.setattr(external.blobs, "put", lambda *args: pytest.fail("overbudget disk write"))
    with pytest.raises(ValueError):
        external.ingest_page(
            ctx, account, None, "large", [replace(pg.item(), raw=b"x" * (MAX_BLOB_BYTES + 1))]
        )
    half = b"x" * (MAX_BLOB_BYTES // 2 + 1)
    with pytest.raises(ValueError):
        external.ingest_page(
            ctx,
            account,
            None,
            "large",
            [replace(pg.item("a"), raw=half), replace(pg.item("b"), raw=half)],
        )


@pytest.mark.postgres
@pytest.mark.parametrize(
    "mutation", ["null_key", "foreign_path", "null_hash", "extra", "both", "nonhex_hash"]
)
def test_manifest_database_constraints_reject_forgery(external, tenant, mutation):
    ctx, account = tenant
    ref = external.blobs.put(ctx.tenant_id, account, b"synthetic uncommitted")
    data = asdict(ref)
    raw = None
    sha = ref.sha256
    if mutation == "null_key":
        data["key_id"] = None
    elif mutation == "foreign_path":
        data["object_key"] = ref.object_key.replace(str(account), str(uuid4()))
    elif mutation == "null_hash":
        data["ciphertext_sha256"] = None
    elif mutation == "extra":
        data["arbitrary_url"] = "https://invalid.example"
    elif mutation == "nonhex_hash":
        sha = "z" * 64
        data["sha256"] = sha
        data["object_key"] = ref.object_key.replace(ref.sha256, sha)
    else:
        raw = b"synthetic uncommitted"
    with pytest.raises(psycopg.Error), external.transaction(ctx) as conn:
        conn.execute(
            "INSERT INTO raw_objects(tenant_id,account_id,sha256,raw_mime,blob_ref) "
            "VALUES (%s,%s,%s,%s,%s)",
            (ctx.tenant_id, account, sha, raw, Jsonb(data)),
        )


@pytest.mark.postgres
def test_fastmail_large_mail_restarts_through_durable_worker(database, external, tenant):
    ctx, account = tenant
    mail = pg.SyntheticMailbox()
    mail.mail = {"a-large": large(), "z-healthy": pg.item().raw}
    mail.page_size = 1
    with psycopg.connect(database[1]) as conn:
        conn.execute(
            "UPDATE mail_accounts SET provider_account_id=%s WHERE id=%s", (mail.account, account)
        )
    client = FastmailReadClient(
        "synthetic-test-token-only",
        transport=httpx.MockTransport(mail.handle),
        max_raw_bytes=MAX_BLOB_BYTES,
    )
    try:
        for _ in range(10):
            result = ReadWorker(external, client, jitter=lambda: 0).step(ctx, account)
            if result == "caught_up":
                break
            assert result == "progress"
        assert result == "caught_up"
        assert external.sync_status(ctx, account)["message_counts"] == {
            "ready": 1,
            "quarantined": 1,
            "deleted": 0,
        }
        assert external.object_inventory(ctx, account)["referenced"] == 2
    finally:
        client.close()
