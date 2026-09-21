"""Synthetic recovery invariants for parser drift, competing owners and worker leases."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from email.message import EmailMessage
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from psycopg import sql
from test_recovery import held, retry

from email_brain import store as persistence
from email_brain.schemas import SearchRequest
from email_brain.store import Conflict
from email_brain.sync_store import SyncStore

pytestmark = pytest.mark.postgres
database, tenant = pg.database, pg.tenant


def attachment_mail():
    mail = EmailMessage()
    mail["From"] = "synthetic@example.invalid"
    mail["Subject"] = "Melron recovery pressure test"
    mail.set_content("Original synthetic body")
    mail.add_attachment("originalattachmenttoken", filename="proof.txt")
    return mail.as_bytes()


def rows(store, ctx, tables):
    with store.transaction(ctx) as conn:
        return {
            table: conn.execute(
                sql.SQL("SELECT * FROM {} ORDER BY 1,2").format(sql.Identifier(table))
            ).fetchall()
            for table in tables
        }


def test_concurrent_owner_retries_audit_both_requests(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    second_actor = uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (ctx.tenant_id, second_actor),
        )
    callers = [
        replace(ctx, request_id=uuid4()),
        replace(ctx, actor_id=second_actor, request_id=uuid4()),
    ]
    barrier = Barrier(2)
    real_prepare = persistence.prepare_mime

    def simultaneous(raw):
        barrier.wait(timeout=10)
        return real_prepare(raw)

    monkeypatch.setattr(persistence, "prepare_mime", simultaneous)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda caller: retry(store, caller, account, receipt), callers))
    assert results[0] == results[1]
    with psycopg.connect(admin) as conn:
        audit = conn.execute(
            "SELECT actor_id,request_id,event_type,resource_id FROM audit_events "
            "WHERE tenant_id=%s AND event_type LIKE 'recovery.%%'",
            (ctx.tenant_id,),
        ).fetchall()
    assert len(audit) == 2
    assert {(row[0], row[1]) for row in audit} == {(c.actor_id, c.request_id) for c in callers}
    assert {row[2] for row in audit} == {"recovery.recovered", "recovery.read"}
    assert {row[3] for row in audit} == {str(results[0]["id"])}
    state = rows(store, ctx, ("recovery_attempts", "message_versions"))
    assert len(state["recovery_attempts"]) == len(state["message_versions"]) == 1


def test_same_parser_recovery_reuses_evidence_without_changing_history(
    database, tenant, monkeypatch
):
    store, _ = database
    ctx, account = tenant
    raw = attachment_mail()
    store.ingest_page(ctx, account, None, "old", [replace(pg.item("old"), raw=raw)])
    old_id = store.search(ctx, SearchRequest(query="originalattachmenttoken"))[0]["evidence_id"]
    old_evidence = store.evidence(ctx, old_id)
    tables = ("message_versions", "attachment_receipts", "intake_events")
    before = rows(store, ctx, tables)
    assert len(before["attachment_receipts"]) == 1
    receipt = held(store, ctx, account, monkeypatch, raw=raw, cursor="old")
    result = retry(store, ctx, account, receipt)
    assert result["outcome"] == "recovered" and result["evidence_id"] == old_id
    assert rows(store, ctx, tables) == before
    assert store.evidence(ctx, old_id) == old_evidence
    assert len(store.search(ctx, SearchRequest(query="originalattachmenttoken"))) == 1
    assert store.quarantines(ctx, account)["results"] == []


def test_recovery_preserves_active_worker_lease_and_worker_can_continue(
    database, tenant, monkeypatch
):
    store, admin = database
    ctx, account = tenant
    receipt = held(store, ctx, account, monkeypatch)
    # Synthetic enrollment only: no provider token, transport or mailbox is used.
    with psycopg.connect(admin) as conn:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"{ctx.tenant_id}:{account}",),
        )
        conn.execute(
            "UPDATE mail_accounts SET provider_account_id='synthetic-provider' WHERE id=%s",
            (account,),
        )
    jobs = SyncStore(store)
    lease = jobs.acquire(ctx, account)
    assert lease is not None and lease.cursor == "held"
    tables = ("sync_workers", "sync_cursors", "sync_runs")
    before = rows(store, ctx, tables)
    reviewer = replace(ctx, scopes=frozenset({"email.review", "email.evidence.read"}))
    assert retry(store, reviewer, account, receipt)["outcome"] == "recovered"
    assert rows(store, ctx, tables) == before
    assert (
        store.ingest_page(
            ctx, account, lease.cursor, "continued", [pg.item("continued")], lease_token=lease.token
        )
        == 1
    )
    jobs.finish(ctx, account, lease.token, "progress", 1)
    after = rows(store, ctx, tables)
    assert after["sync_cursors"][0]["opaque_cursor"] == "continued"
    assert after["sync_workers"][0]["lease_token"] is None
    assert after["sync_workers"][0]["last_outcome"] == "progress"
    assert len(after["sync_runs"]) == 1


@pytest.mark.parametrize("drift", ["normalized_text", "attachment_text"])
def test_same_parser_output_drift_conflicts_and_rolls_back_every_projection(
    database, tenant, monkeypatch, drift
):
    store, admin = database
    ctx, account = tenant
    raw = attachment_mail()
    store.ingest_page(ctx, account, None, "old", [replace(pg.item("old"), raw=raw)])
    old_id = store.search(ctx, SearchRequest(query="originalattachmenttoken"))[0]["evidence_id"]
    old_evidence = store.evidence(ctx, old_id)
    receipt = held(store, ctx, account, monkeypatch, raw=raw, cursor="old")
    tables = (
        "messages",
        "message_versions",
        "attachment_receipts",
        "intake_events",
        "recovery_attempts",
        "message_sync_state",
        "quarantine_receipts",
        "raw_objects",
        "provider_events",
        "sync_cursors",
    )
    before = rows(store, ctx, tables)
    real_prepare = persistence.prepare_mime

    def changed_parser(raw):
        normalized, attachments, rejected = real_prepare(raw)
        assert normalized is not None and len(attachments) == 1 and not rejected
        if drift == "normalized_text":
            normalized = replace(normalized, text="UNVERSIONED_PRIVATE_DRIFT")
        else:
            attachments = [replace(a, text="UNVERSIONED_PRIVATE_DRIFT") for a in attachments]
        return normalized, attachments, rejected

    with monkeypatch.context() as patch:
        patch.setattr(persistence, "prepare_mime", changed_parser)
        with pytest.raises(Conflict) as failure:
            retry(store, ctx, account, receipt)
    assert "PRIVATE" not in str(failure.value)
    assert rows(store, ctx, tables) == before
    assert store.evidence(ctx, old_id) == old_evidence
    assert store.search(ctx, SearchRequest(query="UNVERSIONED_PRIVATE_DRIFT")) == []
    assert len(store.quarantines(ctx, account)["results"]) == 1
    with psycopg.connect(admin) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM audit_events WHERE tenant_id=%s "
                "AND event_type LIKE 'recovery.%%'",
                (ctx.tenant_id,),
            ).fetchone()[0]
            == 0
        )
    # The failed publication was not cached as success or failure, so unchanged
    # deterministic output can still complete the original receipt safely.
    assert retry(store, ctx, account, receipt)["evidence_id"] == old_id
