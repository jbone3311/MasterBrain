"""Coherent fixture feed through actual transactions/RLS, never provider writes."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg

from email_brain.schemas import SearchRequest
from email_brain.synthetic_mailbox import (
    MailboxSpec,
    mailbox_manifest,
    project_events,
    seed_mailbox,
)

database, tenant = pg.database, pg.tenant
pytestmark = pytest.mark.postgres


def snapshot(store, ctx):
    with store.transaction(ctx) as conn:
        return {
            table: conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            for table in (
                "provider_events",
                "raw_objects",
                "message_versions",
                "quarantine_receipts",
            )
        }


def test_coherent_feed_resume_search_evidence_and_final_oracle(database, tenant):
    store, _ = database
    ctx, account = tenant
    spec = MailboxSpec(42, 2)
    first = seed_mailbox(store, ctx, account, spec, max_events=7)
    assert first["position"] == 7 and not first["complete"] and first["new_events"] == 7
    second = seed_mailbox(store, ctx, account, spec)
    assert second["position"] == 30 and second["complete"] and second["new_events"] == 21
    before = snapshot(store, ctx)
    assert before["provider_events"] == 28 and before["message_versions"] == 22
    assert before["quarantine_receipts"] == 2
    assert seed_mailbox(store, ctx, account, spec)["scheduled_this_run"] == 0
    assert snapshot(store, ctx) == before
    with store.transaction(ctx) as conn:
        counts = {
            row["status"]: row["n"]
            for row in conn.execute(
                "SELECT status,count(*) AS n FROM message_sync_state GROUP BY status"
            ).fetchall()
        }
        assert counts == {"ready": 20, "quarantined": 2, "deleted": 2}
        assert conn.execute(
            "SELECT provider_metadata FROM messages WHERE provider_message_id=%s",
            ("s42p0000-mail00",),
        ).fetchone()["provider_metadata"]["keywords"] == ["$seen"]
    for project in range(2):
        events = project_events(42, project)
        for event in events:
            if event.kind != "created":
                continue
            assert store.load_raw(ctx, account, event.manifest()["raw_sha256"]) == event.item.raw
            if event.marker:
                hits = store.search(ctx, SearchRequest(query=event.marker))
                assert len(hits) == (0 if event.item.provider_id.endswith("mail10") else 1)
                if hits:
                    evidence = store.evidence(ctx, hits[0]["evidence_id"])
                    assert evidence["raw_sha256"] == event.manifest()["raw_sha256"]
        tag = f"s42p{project:04d}"
        assert len(store.search(ctx, SearchRequest(query=f"rentproof{tag}"))) == 2
        assert len(store.search(ctx, SearchRequest(query=f"invoiceproof{tag}"))) == 1
        assert store.search(ctx, SearchRequest(query=f"pdfproof{tag}")) == []
    # No quoted instruction or source content becomes a control-plane request.
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM proposals").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM recovery_jobs").fetchone()["n"] == 0


def test_lost_commit_response_resumes_from_sql_not_report(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    original = store.ingest_page

    def ambiguous(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic response loss after durable commit")

    monkeypatch.setattr(store, "ingest_page", ambiguous)
    with pytest.raises(ValueError):
        seed_mailbox(store, ctx, account, MailboxSpec(42, 1))
    assert snapshot(store, ctx)["provider_events"] == 1
    monkeypatch.setattr(store, "ingest_page", original)
    result = seed_mailbox(store, ctx, account, MailboxSpec(42, 1))
    assert result["position"] == 15 and result["new_events"] == 13
    assert snapshot(store, ctx)["provider_events"] == 14


def test_stop_after_commit_then_resume(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    stop = Event()
    original = store.ingest_page

    def stopping(*args, **kwargs):
        value = original(*args, **kwargs)
        stop.set()
        return value

    monkeypatch.setattr(store, "ingest_page", stopping)
    result = seed_mailbox(store, ctx, account, MailboxSpec(42, 1), interval_seconds=60, stop=stop)
    assert result["position"] == 1 and result["stopped"] and not result["complete"]
    monkeypatch.setattr(store, "ingest_page", original)
    assert seed_mailbox(store, ctx, account, MailboxSpec(42, 1))["complete"]


@pytest.mark.parametrize(
    "denial",
    ["foreign", "nonowner", "scope", "enrolled", "real_secret", "inactive", "other_cursor"],
)
def test_synthetic_boundary_denial_cannot_add_events(database, tenant, denial):
    store, admin = database
    ctx, account = tenant
    request_ctx, request_account = ctx, account
    if denial == "foreign":
        _, request_account = pg.tenant.__wrapped__(database)
    elif denial == "nonowner":
        request_ctx = replace(ctx, actor_id=uuid4())
    elif denial == "scope":
        request_ctx = replace(ctx, scopes=frozenset({"email.search"}))
    elif denial == "other_cursor":
        store.ingest_page(ctx, account, None, "another-corpus", [pg.item()], synthetic_only=True)
    else:
        with psycopg.connect(admin) as conn:
            if denial == "enrolled":
                conn.execute(
                    "UPDATE mail_accounts SET provider_account_id='fixture-enrolled' WHERE id=%s",
                    (account,),
                )
            elif denial == "real_secret":
                conn.execute(
                    "UPDATE mail_accounts SET secret_ref='vault:fixture-not-real' WHERE id=%s",
                    (account,),
                )
            else:
                conn.execute(
                    "UPDATE mail_accounts SET status='disconnected' WHERE id=%s", (account,)
                )
    before = snapshot(store, ctx)
    with pytest.raises(ValueError):
        seed_mailbox(store, request_ctx, request_account, MailboxSpec(42, 1))
    assert snapshot(store, ctx) == before


def test_enrollment_race_is_rechecked_by_ingestion(database, tenant, monkeypatch):
    store, admin = database
    ctx, account = tenant
    original = store.ingest_page

    def enrollment(*args, **kwargs):
        with psycopg.connect(admin) as conn:
            conn.execute(
                "UPDATE mail_accounts SET provider_account_id='fixture-enrolled' WHERE id=%s",
                (account,),
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(store, "ingest_page", enrollment)
    with pytest.raises(ValueError):
        seed_mailbox(store, ctx, account, MailboxSpec(42, 1))
    assert snapshot(store, ctx)["provider_events"] == 0


def test_changed_spec_and_corrupt_checkpoint_refused(database, tenant):
    store, admin = database
    ctx, account = tenant
    spec = MailboxSpec(42, 1)
    seed_mailbox(store, ctx, account, spec, max_events=1)
    before = snapshot(store, ctx)
    for changed in (MailboxSpec(43, 1), MailboxSpec(42, 2)):
        with pytest.raises(ValueError):
            seed_mailbox(store, ctx, account, changed)
    prefix = f"synthetic-mailbox-v1:{mailbox_manifest(spec)['manifest_sha256']}:"
    for invalid in ("01", "-1", "16", "1:2", "١", ""):
        with psycopg.connect(admin) as conn:
            conn.execute(
                "UPDATE sync_cursors SET opaque_cursor=%s WHERE account_id=%s",
                (prefix + invalid, account),
            )
        with pytest.raises(ValueError):
            seed_mailbox(store, ctx, account, spec)
        assert snapshot(store, ctx) == before


def test_competing_feeders_conflict_without_duplicates(database, tenant):
    store, _ = database
    ctx, account = tenant
    spec = MailboxSpec(42, 1)

    def run():
        try:
            return seed_mailbox(store, ctx, account, spec)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert any(result is not None for result in results)
    assert seed_mailbox(store, ctx, account, spec)["complete"]
    assert snapshot(store, ctx)["provider_events"] == 14


def test_real_cli_two_processes_resume_same_account(database, tenant, tmp_path):
    store, _ = database
    ctx, account = tenant
    root = tmp_path.resolve()
    root.chmod(0o700)
    state = root / "demo.json"
    state.write_text(
        json.dumps(
            {
                "tenant_id": str(ctx.tenant_id),
                "actor_id": str(ctx.actor_id),
                "account_id": str(account),
            }
        )
    )
    state.chmod(0o600)

    def invoke(limit):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "email_brain.cli",
                "seed-test-mailbox",
                "--state-dir",
                str(root),
                "--projects",
                "1",
                "--max-events",
                str(limit),
            ],
            env={"PATH": "/usr/bin:/bin", "EMAIL_BRAIN_DSN": store.dsn},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert (
            result.stderr == ""
            and store.dsn not in result.stdout
            and str(account) not in result.stdout
        )
        return json.loads(result.stdout)

    assert invoke(3)["position"] == 3
    assert invoke(15)["complete"]
    assert snapshot(store, ctx)["provider_events"] == 14
