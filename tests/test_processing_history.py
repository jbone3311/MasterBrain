"""Bounded durable history for the processing screen; synthetic data only."""

from dataclasses import replace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import test_postgres as pg
from fastapi.testclient import TestClient
from test_isolated_recovery import VERSION, FakeProcessor, make_held
from test_service import TOKEN, registry

from email_brain.api import create_app
from email_brain.auth import Principal
from email_brain.recovery_jobs import RecoveryJobs
from email_brain.store import Store

database, tenant = pg.database, pg.tenant
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


@pytest.mark.parametrize("limit", [0, 51, -1, True, "10", None])
def test_history_direct_limits_are_strict(limit):
    store = MagicMock(spec=Store)
    store.require = Store.require
    ctx = registry({"email.evidence.read"}).authenticate(TOKEN).context
    with pytest.raises(ValueError):
        RecoveryJobs(store).list(ctx, uuid4(), limit=limit)
    store.transaction.assert_not_called()


def test_history_direct_cursor_rejects_non_uuid():
    store = MagicMock(spec=Store)
    ctx = registry({"email.evidence.read"}).authenticate(TOKEN).context
    with pytest.raises(ValueError):
        RecoveryJobs(store).list(ctx, uuid4(), after="private-invalid-cursor")
    store.transaction.assert_not_called()


def test_fixed_history_route_precedes_uuid_job_route(monkeypatch):
    calls = []

    def listing(self, ctx, account, *, limit, after):
        calls.append((ctx, account, limit, after))
        return {"results": [], "next_after": None, "limit": limit, "mailbox_effects": False}

    monkeypatch.setattr(RecoveryJobs, "list", listing)
    creds = registry({"email.evidence.read"})
    client = TestClient(create_app(MagicMock(spec=Store), creds))
    account, anchor = uuid4(), uuid4()
    path = f"/v1/accounts/{account}/processing/jobs"
    assert client.get(path).status_code == 401
    result = client.get(path + f"?limit=7&after={anchor}", headers=HEADERS)
    assert result.status_code == 200 and result.json()["limit"] == 7
    ctx, passed_account, limit, after = calls.pop()
    assert (passed_account, limit, after) == (account, 7, anchor)
    assert ctx.tenant_id == creds.authenticate(TOKEN).context.tenant_id
    for query in ("?limit=0", "?limit=51", "?limit=true", "?after=invalid"):
        result = client.get(path + query, headers=HEADERS)
        assert result.status_code == 422 and result.json() == {"error": "invalid_request"}
    assert calls == []


@pytest.mark.postgres
def test_history_pages_tied_creation_times_without_duplicates(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    receipt = make_held(store, ctx, account, monkeypatch)
    with store.transaction(ctx) as conn:
        conn.execute(
            "INSERT INTO recovery_jobs(tenant_id,account_id,receipt_id,actor_id,"
            "idempotency_key,parser_version,created_at,expires_at) "
            "SELECT %s,%s,%s,%s,gen_random_uuid(),%s,statement_timestamp(),"
            "statement_timestamp()+interval '1 hour' FROM generate_series(1,73)",
            (ctx.tenant_id, account, receipt, ctx.actor_id, VERSION),
        )
        expected = [
            row["id"]
            for row in conn.execute(
                "SELECT id FROM recovery_jobs ORDER BY created_at DESC,id DESC"
            ).fetchall()
        ]
    jobs = RecoveryJobs(store)
    ids, cursor = [], None
    while True:
        page = jobs.list(ctx, account, limit=7, after=cursor)
        assert page["limit"] == 7 and page["mailbox_effects"] is False
        assert 1 <= len(page["results"]) <= 7
        ids.extend(row["id"] for row in page["results"])
        cursor = page["next_after"]
        if cursor is None:
            break
        assert cursor == page["results"][-1]["id"]
    assert ids == expected and len(set(ids)) == 73
    assert jobs.list(ctx, account, after=ids[-1])["results"] == []
    assert len(jobs.list(ctx, account)["results"]) == 50


@pytest.mark.postgres
def test_history_refresh_finds_new_jobs_and_terminal_outcomes(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    receipt = make_held(store, ctx, account, monkeypatch)
    jobs, human = RecoveryJobs(store, VERSION), Principal(ctx, "human")
    older = jobs.enqueue(human, account, receipt, VERSION, uuid4())
    newer = jobs.enqueue(human, account, receipt, VERSION, uuid4())
    first_page = jobs.list(ctx, account, limit=1)
    assert first_page["results"][0]["id"] == newer["id"]
    latest = jobs.enqueue(human, account, receipt, VERSION, uuid4())
    assert (
        jobs.list(ctx, account, after=first_page["next_after"])["results"][0]["id"] == older["id"]
    )
    jobs.cancel(human, account, latest["id"])
    jobs.run_once(
        Principal(replace(ctx, scopes=frozenset({"email.process"})), "worker"),
        account,
        FakeProcessor(),
    )
    # Recreate the service to prove nothing depends on a tab/process-local job list.
    restored = RecoveryJobs(Store(store.dsn))
    rows = restored.list(ctx, account)["results"]
    assert [row["id"] for row in rows] == [latest["id"], newer["id"], older["id"]]
    assert [row["status"] for row in rows] == ["cancelled", "queued", "completed"]
    assert rows[-1]["outcome"] == "recovered"
    for row in rows:
        assert set(row) == {
            "id",
            "account_id",
            "receipt_id",
            "parser_version",
            "status",
            "attempts",
            "created_at",
            "expires_at",
            "retry_at",
            "completed_at",
            "attempt_id",
            "outcome",
            "mailbox_effects",
        }


@pytest.mark.postgres
def test_empty_history_and_account_index(database, tenant):
    store, _ = database
    ctx, account = tenant
    assert RecoveryJobs(store).list(ctx, account) == {
        "results": [],
        "limit": 50,
        "next_after": None,
        "mailbox_effects": False,
    }
    with store.transaction(ctx) as conn:
        index = conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE schemaname='public' "
            "AND indexname='recovery_jobs_history'"
        ).fetchone()["indexdef"]
        assert "tenant_id, account_id, created_at DESC, id DESC" in index
