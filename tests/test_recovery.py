"""Synthetic PostgreSQL recovery, races, immutable history and API boundaries."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from email.message import EmailMessage
from threading import Barrier
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo
from test_service import TOKEN, registry

from email_brain import store as persistence
from email_brain.api import create_app
from email_brain.auth import Principal
from email_brain.migrate import migrate
from email_brain.recovery import Recovery, RecoveryUnavailable
from email_brain.schemas import SearchRequest
from email_brain.store import AccessDenied, Conflict, NotFound, Store

database, tenant = pg.database, pg.tenant


def held(store, ctx, account, monkeypatch, *, raw=None, cursor=None, key="held"):
    message = replace(
        pg.item(key),
        raw=pg.item().raw if raw is None else raw,
        thread_id="thread-1",
        mailbox_ids=("inbox",),
        keywords=("$seen",),
    )
    with monkeypatch.context() as patch:
        patch.setattr(persistence, "prepare_mime", lambda raw: (None, [], True))
        store.ingest_page(ctx, account, cursor, key, [message])
    return store.quarantines(ctx, account)["results"][0]["id"]


def retry(store, ctx, account, receipt):
    return Recovery(store).retry(
        Principal(ctx, "human"), account, receipt, persistence.PARSER_VERSION
    )


def test_library_requires_human_and_both_scopes_before_sql():
    store = MagicMock(spec=Store)
    # Real scope guard, not a permissive mock.
    store.require = Store.require
    ctx = pg.TenantContext(uuid4(), uuid4(), frozenset({"email.review"}), uuid4())
    for kind, scopes in (
        ("assistant", {"email.review", "email.evidence.read"}),
        ("human", {"email.review"}),
        ("human", {"email.evidence.read"}),
    ):
        with pytest.raises(AccessDenied):
            Recovery(store).retry(
                Principal(replace(ctx, scopes=frozenset(scopes)), kind),
                uuid4(),
                uuid4(),
                persistence.PARSER_VERSION,
            )
    store.transaction.assert_not_called()


def test_api_denies_missing_scope_and_rejects_untrusted_parameters(monkeypatch):
    store = MagicMock(spec=Store)
    path = f"/v1/accounts/{uuid4()}/quarantine/{uuid4()}/retry"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    body = {"expected_parser_version": persistence.PARSER_VERSION}
    client = TestClient(create_app(store, registry({"email.review", "email.evidence.read"})))
    assert client.post(path, json=body).status_code == 401
    assert client.post(path, json={**body, "raw": "private"}, headers=headers).status_code == 422
    assert client.post(path, json={}, headers=headers).status_code == 422
    for scopes, kind in (({"email.evidence.read"}, "assistant"), ({"email.review"}, "human")):
        denied = TestClient(create_app(store, registry(scopes, kind)))
        # Mock must not bypass the library's scope guard.
        store.require = Store.require
        assert denied.post(path, json=body, headers=headers).status_code == 403
    monkeypatch.setattr(
        Recovery,
        "retry",
        lambda *args: (_ for _ in ()).throw(RecoveryUnavailable("private parser output")),
    )
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == 503 and "private" not in response.text


@pytest.mark.postgres
def test_recovery_preserves_source_cursor_metadata_and_is_idempotent(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    with store.transaction(ctx) as conn:
        raw_before = conn.execute("SELECT * FROM raw_objects").fetchall()
        events_before = conn.execute("SELECT * FROM provider_events").fetchall()
        cursor_before = conn.execute("SELECT * FROM sync_cursors").fetchall()
    result = retry(store, ctx, account, receipt)
    assert result["outcome"] == "recovered"
    assert result["historical_outcome"] is True and result["mailbox_effects"] is False
    assert retry(store, ctx, account, receipt) == result
    hits = store.search(ctx, SearchRequest(query="Melron"))
    assert len(hits) == 1 and hits[0]["evidence_id"] == result["evidence_id"]
    assert store.quarantines(ctx, account)["results"] == []
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT * FROM raw_objects").fetchall() == raw_before
        assert conn.execute("SELECT * FROM provider_events").fetchall() == events_before
        assert conn.execute("SELECT * FROM sync_cursors").fetchall() == cursor_before
        assert conn.execute("SELECT count(*) AS n FROM quarantine_receipts").fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM recovery_attempts").fetchone()["n"] == 1
        projection = conn.execute("SELECT * FROM messages").fetchone()
        assert projection["provider_thread_id"] == "thread-1"
        assert projection["provider_metadata"] == {"mailbox_ids": ["inbox"], "keywords": ["$seen"]}
    with psycopg.connect(admin) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM audit_events WHERE tenant_id=%s "
                "AND event_type='recovery.recovered'",
                (ctx.tenant_id,),
            ).fetchone()[0]
            == 1
        )
    # Cached successful receipt cannot resurrect a later deletion.
    store.ingest_page(ctx, account, "held", "deleted", [replace(pg.item("gone"), raw=None)])
    assert retry(store, ctx, account, receipt) == result
    assert store.search(ctx, SearchRequest(query="Melron")) == []


@pytest.mark.postgres
def test_failure_is_cached_per_parser_and_new_version_can_retry(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    with monkeypatch.context() as patch:
        patch.setattr(persistence, "prepare_mime", lambda raw: (None, [], True))
        result = retry(store, ctx, account, receipt)
    assert result["outcome"] == "mime_rejected" and result["evidence_id"] is None
    assert retry(store, ctx, account, receipt) == result
    assert len(store.quarantines(ctx, account)["results"]) == 1
    monkeypatch.setattr(persistence, "PARSER_VERSION", "synthetic-fixed-v5")
    assert retry(store, ctx, account, receipt)["outcome"] == "recovered"


@pytest.mark.postgres
@pytest.mark.parametrize("change", ["deleted", "ready", "quarantined"])
def test_new_provider_event_during_parse_prevents_recovery(database, tenant, monkeypatch, change):
    store, _ = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    real_prepare = persistence.prepare_mime

    def racing_parse(raw):
        with monkeypatch.context() as patch:
            patch.setattr(persistence, "prepare_mime", real_prepare)
            newer = replace(
                pg.item("newer"),
                raw=None
                if change == "deleted"
                else b""
                if change == "quarantined"
                else pg.item().raw,
            )
            store.ingest_page(ctx, account, "held", "newer", [newer])
        return real_prepare(raw)

    monkeypatch.setattr(persistence, "prepare_mime", racing_parse)
    with pytest.raises(Conflict):
        retry(store, ctx, account, receipt)
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT status FROM message_sync_state").fetchone()["status"] == change
        assert conn.execute("SELECT count(*) AS n FROM recovery_attempts").fetchone()["n"] == 0


@pytest.mark.postgres
def test_concurrent_retry_has_exactly_one_attempt(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    barrier = Barrier(2)
    real_prepare = persistence.prepare_mime

    def simultaneous(raw):
        barrier.wait(timeout=10)
        return real_prepare(raw)

    monkeypatch.setattr(persistence, "prepare_mime", simultaneous)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: retry(store, ctx, account, receipt), range(2)))
    assert results[0] == results[1]
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM recovery_attempts").fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM message_versions").fetchone()["n"] == 1


@pytest.mark.postgres
def test_parser_exception_and_publish_failure_leave_no_partial_writes(
    database, tenant, monkeypatch
):
    store, _ = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    with monkeypatch.context() as patch:
        patch.setattr(
            persistence,
            "prepare_mime",
            lambda raw: (_ for _ in ()).throw(RuntimeError("private mail contents")),
        )
        with pytest.raises(RecoveryUnavailable) as exc:
            retry(store, ctx, account, receipt)
        assert "private" not in str(exc.value)
    with monkeypatch.context() as patch:
        patch.setattr(
            store,
            "record_attachments",
            lambda *args: (_ for _ in ()).throw(RuntimeError("synthetic crash")),
        )
        with pytest.raises(RuntimeError):
            retry(store, ctx, account, receipt)
    with store.transaction(ctx) as conn:
        for table in ("recovery_attempts", "messages", "message_versions", "attachment_receipts"):
            assert conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == 0
        assert (
            conn.execute("SELECT status FROM message_sync_state").fetchone()["status"]
            == "quarantined"
        )
    assert retry(store, ctx, account, receipt)["outcome"] == "recovered"


@pytest.mark.postgres
def test_wrong_account_tenant_membership_and_parser_cannot_retry(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    with pytest.raises(NotFound):
        retry(store, ctx, uuid4(), receipt)
    with pytest.raises(NotFound):
        retry(store, ctx, account, uuid4())
    other_ctx, other_account = pg.tenant.__wrapped__(database)
    with pytest.raises(NotFound):
        retry(store, other_ctx, account, receipt)
    with pytest.raises(NotFound):
        retry(store, other_ctx, other_account, receipt)
    with pytest.raises(AccessDenied):
        retry(store, replace(ctx, actor_id=uuid4()), account, receipt)
    with pytest.raises(Conflict):
        Recovery(store).retry(Principal(ctx, "human"), account, receipt, "arbitrary-parser")


@pytest.mark.postgres
def test_current_search_excludes_old_parser_attachments_and_old_citations_survive(
    database, tenant, monkeypatch
):
    store, _ = database
    ctx, account = tenant
    mail = EmailMessage()
    mail["Subject"] = "Melron"
    mail.set_content("Synthetic body")
    mail.add_attachment("historicalattachmenttoken", filename="proof.txt")
    raw = mail.as_bytes()
    with monkeypatch.context() as patch:
        patch.setattr(persistence, "PARSER_VERSION", "synthetic-old-parser")
        store.ingest_page(ctx, account, None, "old", [replace(pg.item("old"), raw=raw)])
    old_hit = store.search(ctx, SearchRequest(query="historicalattachmenttoken"))[0]
    old_evidence = store.evidence(ctx, old_hit["evidence_id"])
    receipt = held(store, ctx, account, monkeypatch, raw=raw, cursor="old")
    real_prepare = persistence.prepare_mime

    def updated_parser(raw):
        normalized, attachments, rejected = real_prepare(raw)
        return (
            normalized,
            [replace(a, text="currentattachmenttoken") for a in attachments],
            rejected,
        )

    monkeypatch.setattr(persistence, "prepare_mime", updated_parser)
    result = retry(store, ctx, account, receipt)
    assert result["evidence_id"] != old_hit["evidence_id"]
    assert store.evidence(ctx, old_hit["evidence_id"]) == old_evidence
    assert store.search(ctx, SearchRequest(query="historicalattachmenttoken")) == []
    assert len(store.search(ctx, SearchRequest(query="currentattachmenttoken"))) == 1
    assert len(store.search(ctx, SearchRequest(query="Melron"))) == 1


@pytest.mark.postgres
def test_recovery_attempts_are_rls_isolated_and_immutable(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch, raw=b"")
    result = retry(store, ctx, account, receipt)
    other_ctx, _ = pg.tenant.__wrapped__(database)
    with store.transaction(other_ctx) as conn:
        assert (
            conn.execute("SELECT * FROM recovery_attempts WHERE id=%s", (result["id"],)).fetchall()
            == []
        )
    for verb in (
        "UPDATE recovery_attempts SET outcome='integrity_failed'",
        "DELETE FROM recovery_attempts",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), store.transaction(ctx) as conn:
            conn.execute(verb)
        with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(admin) as conn:
            conn.execute(verb + " WHERE id=%s", (result["id"],))


@pytest.mark.postgres
def test_hash_mismatch_never_parses_or_changes_quarantine(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    # Deliberate at-rest corruption in this disposable synthetic tenant only.
    with psycopg.connect(admin) as conn:
        conn.execute("ALTER TABLE raw_objects DISABLE TRIGGER raw_append_only")
        conn.execute(
            "UPDATE raw_objects SET raw_mime=%s WHERE tenant_id=%s", (b"corrupt", ctx.tenant_id)
        )
        conn.execute("ALTER TABLE raw_objects ENABLE TRIGGER raw_append_only")

    def forbidden(raw):
        pytest.fail("corrupt bytes must not reach the parser")

    monkeypatch.setattr(persistence, "prepare_mime", forbidden)
    result = retry(store, ctx, account, receipt)
    assert result["outcome"] == "integrity_failed"
    assert result["evidence_id"] is None
    assert len(store.quarantines(ctx, account)["results"]) == 1


@pytest.mark.postgres
def test_legacy_receipt_does_not_reuse_stale_mailbox_metadata(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    store.ingest_page(ctx, account, None, "old", [replace(pg.item("old"), thread_id="stale")])
    receipt = held(store, ctx, account, monkeypatch, cursor="old")
    with psycopg.connect(admin) as conn:
        conn.execute("ALTER TABLE quarantine_receipts DISABLE TRIGGER quarantine_immutable")
        conn.execute("UPDATE quarantine_receipts SET source_metadata=NULL WHERE id=%s", (receipt,))
        conn.execute("ALTER TABLE quarantine_receipts ENABLE TRIGGER quarantine_immutable")
    assert retry(store, ctx, account, receipt)["outcome"] == "recovered"
    with store.transaction(ctx) as conn:
        row = conn.execute("SELECT provider_thread_id,provider_metadata FROM messages").fetchone()
        assert row == {
            "provider_thread_id": None,
            "provider_metadata": {"source_metadata": "unknown"},
        }


@pytest.mark.postgres
@pytest.mark.parametrize("revoke", ["account", "membership"])
def test_authorization_revoked_during_parse_cannot_publish(database, tenant, monkeypatch, revoke):
    store, admin = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    real_prepare = persistence.prepare_mime

    def revoke_during_parse(raw):
        with psycopg.connect(admin) as conn:
            if revoke == "account":
                conn.execute("UPDATE mail_accounts SET status='disabled' WHERE id=%s", (account,))
            else:
                conn.execute("DELETE FROM tenant_memberships WHERE tenant_id=%s", (ctx.tenant_id,))
        return real_prepare(raw)

    monkeypatch.setattr(persistence, "prepare_mime", revoke_during_parse)
    with pytest.raises(NotFound if revoke == "account" else AccessDenied):
        retry(store, ctx, account, receipt)
    with psycopg.connect(admin) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM recovery_attempts WHERE tenant_id=%s", (ctx.tenant_id,)
            ).fetchone()[0]
            == 0
        )


@pytest.mark.postgres
def test_populated_upgrade_preserves_immutable_evidence(database, tmp_path):
    from pathlib import Path

    from psycopg.types.json import Jsonb

    _, admin = database
    name = "email_brain_test_upgrade_" + uuid4().hex
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(admin, dbname=name)
    try:
        directory = Path(__file__).resolve().parents[1] / "migrations"
        for path in sorted(directory.glob("000[1-7]_*.sql")):
            (tmp_path / path.name).write_bytes(path.read_bytes())
        migrate(dsn, tmp_path)
        tenant_id, account_id, message_id, version_id = (uuid4() for _ in range(4))
        snapshot = {"parser_version": "synthetic-old", "text": "unchanged"}
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO tenants(id,name) VALUES (%s,'Synthetic upgrade')", (tenant_id,)
            )
            conn.execute(
                "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
                "VALUES (%s,%s,'fastmail','test@example.invalid','synthetic:none')",
                (account_id, tenant_id),
            )
            conn.execute(
                "INSERT INTO raw_objects(tenant_id,account_id,sha256,raw_mime) "
                "VALUES (%s,%s,%s,%s)",
                (tenant_id, account_id, "a" * 64, b"synthetic"),
            )
            conn.execute(
                "INSERT INTO messages(id,tenant_id,account_id,provider_message_id,provider_version,"
                "subject,sender,recipients,clean_text,raw_sha256,parser_version,received_at) "
                "VALUES (%s,%s,%s,'p1','v1','subject','test@example.invalid',"
                "'[]','unchanged',%s,'synthetic-old',now())",
                (message_id, tenant_id, account_id, "a" * 64),
            )
            conn.execute(
                "INSERT INTO message_versions(id,tenant_id,account_id,message_id,raw_sha256,"
                "provider_version,snapshot) "
                "VALUES (%s,%s,%s,%s,%s,'v1',%s)",
                (version_id, tenant_id, account_id, message_id, "a" * 64, Jsonb(snapshot)),
            )
        with psycopg.connect(dsn) as conn:
            conn.execute("UPDATE messages SET parser_version='mismatched-legacy'")
        with pytest.raises(psycopg.errors.RaiseException, match="parser provenance mismatch"):
            migrate(dsn, directory)
        with psycopg.connect(dsn) as conn:
            assert (
                conn.execute(
                    "SELECT count(*) FROM schema_migrations "
                    "WHERE name='0008_quarantine_recovery.sql'"
                ).fetchone()[0]
                == 0
            )
            conn.execute("UPDATE messages SET parser_version='synthetic-old'")
        assert migrate(dsn, directory) == [
            "0008_quarantine_recovery.sql",
            "0009_external_raw_evidence.sql",
            "0010_recovery_jobs.sql",
        ]
        with psycopg.connect(dsn) as conn:
            assert conn.execute(
                "SELECT id,snapshot,parser_version FROM message_versions"
            ).fetchone() == (version_id, snapshot, "synthetic-old")
        with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(dsn) as conn:
            conn.execute("UPDATE message_versions SET snapshot='{}'")
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
