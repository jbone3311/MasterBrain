"""Real disposable PostgreSQL coverage of evidence-backed travel/bill memory."""

import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import psycopg
import pytest
import test_postgres as pg
from fastapi.testclient import TestClient
from test_memory import FLIGHT

from email_brain.api import create_app
from email_brain.auth import Credential, Principal, TokenRegistry
from email_brain.memory import Memory
from email_brain.memory_schema import MemoryWrite
from email_brain.schemas import SearchRequest
from email_brain.store import AccessDenied, Conflict, NotFound

database, tenant = pg.database, pg.tenant
pytestmark = pytest.mark.postgres


def setup(store, ctx, account):
    store.ingest_page(ctx, account, None, "memory1", [pg.item(body=FLIGHT)])
    evidence = store.search(ctx, SearchRequest(query="Fictional"))[0]["evidence_id"]
    memory = Memory(store)
    human = Principal(ctx, "human")
    candidate = memory.candidate(human, account, evidence)
    request = MemoryWrite(
        expected_revision=0,
        evidence_id=evidence,
        source_quote=candidate["source_quote"],
        payload=candidate["candidate"],
        reviewed=True,
    )
    return memory, human, request


def publish(memory, human, account, request, record=None, key=None):
    return memory.publish(human, account, record or uuid4(), request, key or uuid4())


def test_trip_reservation_bill_history_and_independent_feed(database, tenant):
    store, _ = database
    ctx, account = tenant
    memory, human, request = setup(store, ctx, account)
    trip = publish(memory, human, account, request)  # Separate booking; no automatic fuzzy merge.
    first = publish(memory, human, account, request)
    row = first["record"]
    assert row["revision"] == 2 and not row["live_verified"]
    changes = memory.changes(ctx, account, limit=1)
    assert changes["has_more"] and changes["changes"][0]["record_id"] == trip["record"]["record_id"]
    second = memory.changes(ctx, account, after=changes["next_cursor"], limit=1)
    assert second["changes"][0]["record_id"] == row["record_id"]
    assert memory.changes(ctx, account, limit=1) == changes  # Another client is unaffected.
    assert not memory.changes(ctx, account, after=second["next_cursor"])["changes"]
    updated = request.model_copy(
        update={
            "expected_revision": row["revision"],
            "payload": request.payload.model_copy(update={"status": "cancelled"}),
        }
    )
    result = publish(memory, human, account, updated, row["record_id"])
    assert result["record"]["revision"] == 3
    assert memory.get(ctx, account, row["record_id"])["payload"]["status"] == "cancelled"
    historical = memory.get(ctx, account, row["record_id"], at=row["cursor"])
    assert historical["payload"]["status"] == "confirmed"
    assert memory.summary(ctx, account)["buckets"][0]["revision"] == 3
    assert memory.summary(ctx, account)["needs_refresh"]
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM memory_revisions").fetchone()["n"] == 3


def test_idempotency_noop_conflict_and_optimistic_update(database, tenant):
    store, _ = database
    ctx, account = tenant
    memory, human, request = setup(store, ctx, account)
    record, key = uuid4(), uuid4()
    first = publish(memory, human, account, request, record, key)
    assert publish(memory, human, account, request, record, key) == first
    updated = request.model_copy(update={"expected_revision": 1})
    noop_key = uuid4()
    assert not publish(memory, human, account, updated, record, noop_key)["changed"]
    assert not publish(memory, human, account, updated, record, noop_key)["changed"]
    assert len(memory.changes(ctx, account)["changes"]) == 1
    with pytest.raises(Conflict):
        publish(memory, human, account, updated, record, key)
    with pytest.raises(Conflict):
        publish(memory, human, account, request, record)


@pytest.mark.parametrize(
    "mode", ["quote", "evidence", "parent", "scope", "assistant", "inactive", "revoked", "foreign"]
)
def test_denials(database, tenant, mode):
    store, admin = database
    ctx, account = tenant
    memory, human, request = setup(store, ctx, account)
    expected = NotFound
    if mode == "quote":
        request = request.model_copy(update={"source_quote": "not in the original"})
        expected = Conflict
    elif mode == "evidence":
        request = request.model_copy(update={"evidence_id": uuid4()})
    elif mode == "parent":
        request = request.model_copy(update={"parent_trip_id": uuid4()})
    elif mode == "scope":
        human = replace(human, context=replace(ctx, scopes=frozenset({"email.evidence.read"})))
        expected = AccessDenied
    elif mode == "assistant":
        human = replace(human, client_kind="assistant")
        expected = AccessDenied
    elif mode == "foreign":
        account = uuid4()
    else:
        with psycopg.connect(admin) as conn:
            if mode == "inactive":
                conn.execute("UPDATE mail_accounts SET status='paused' WHERE id=%s", (account,))
            else:
                conn.execute(
                    "UPDATE tenant_memberships SET role='member' WHERE tenant_id=%s",
                    (ctx.tenant_id,),
                )
                expected = AccessDenied
    with pytest.raises(expected):
        publish(memory, human, account, request)


@pytest.mark.parametrize("tombstone", [True, False])
def test_source_change_does_not_erase_history_or_silently_cancel(database, tenant, tombstone):
    store, _ = database
    ctx, account = tenant
    memory, human, request = setup(store, ctx, account)
    saved = publish(memory, human, account, request)["record"]
    item = pg.item("memory2", "replacement")
    store.ingest_page(
        ctx, account, "memory1", "memory2", [replace(item, raw=None) if tombstone else item]
    )
    row = memory.get(ctx, account, saved["record_id"])
    assert not row["source_current"] and row["payload"]["status"] == "confirmed"
    with pytest.raises(NotFound):
        publish(memory, human, account, request)


def test_parallel_updates_have_one_winner_and_ordered_feed(database, tenant):
    store, _ = database
    ctx, account = tenant
    memory, human, request = setup(store, ctx, account)
    saved = publish(memory, human, account, request)["record"]

    def update(status):
        edit = request.model_copy(
            update={
                "expected_revision": 1,
                "payload": request.payload.model_copy(update={"status": status}),
            }
        )
        try:
            return publish(memory, human, account, edit, saved["record_id"])["record"]["revision"]
        except Conflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ["changed", "cancelled"]))
    assert set(results) == {2, "conflict"}
    assert [r["revision"] for r in memory.changes(ctx, account)["changes"]] == [1, 2]


def test_rls_immutability_and_cross_account_cursor(database, tenant):
    store, admin = database
    ctx, account = tenant
    memory, human, request = setup(store, ctx, account)
    row = publish(memory, human, account, request)["record"]
    other_account, other_tenant, other_actor = uuid4(), uuid4(), uuid4()
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO mail_accounts(id,tenant_id,provider,address,secret_ref) "
            "VALUES (%s,%s,'gmail','other@example.invalid','synthetic:none')",
            (other_account, ctx.tenant_id),
        )
        conn.execute("INSERT INTO tenants(id,name) VALUES (%s,'Other')", (other_tenant,))
        conn.execute(
            "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner')",
            (other_tenant, other_actor),
        )
    with pytest.raises(NotFound):
        memory.changes(ctx, other_account, after=row["cursor"])
    foreign = replace(ctx, tenant_id=other_tenant, actor_id=other_actor)
    with pytest.raises(NotFound):
        memory.get(foreign, account, row["record_id"])
    with store.transaction(foreign) as conn:
        assert conn.execute("SELECT count(*) AS n FROM memory_revisions").fetchone()["n"] == 0
    for table in ["memory_records", "memory_revisions", "memory_receipts"]:
        with pytest.raises(psycopg.errors.InsufficientPrivilege), store.transaction(ctx) as conn:
            conn.execute(f"DELETE FROM {table}")
        with pytest.raises(psycopg.errors.RaiseException), psycopg.connect(admin) as conn:
            conn.execute(f"DELETE FROM {table} WHERE tenant_id=%s", (ctx.tenant_id,))


def test_trip_link_bill_decimal_and_paging(database, tenant):
    store, _ = database
    ctx, account = tenant
    memory, human, request = setup(store, ctx, account)

    def request_for(payload, **kwargs):
        return MemoryWrite.model_validate(
            {**request.model_dump(mode="json"), "payload": payload, **kwargs}
        )

    trip = publish(memory, human, account, request_for({"kind": "trip", "title": "Autumn"}))[
        "record"
    ]
    flight = publish(
        memory, human, account, request.model_copy(update={"parent_trip_id": trip["record_id"]})
    )["record"]
    bill = publish(
        memory,
        human,
        account,
        request_for(
            {"kind": "bill", "title": "Reviewed expense", "amount": "100.25", "currency": "USD"}
        ),
    )["record"]
    assert flight["parent_trip_id"] == trip["record_id"] and bill["payload"]["amount"] == "100.25"
    page = memory.records(ctx, account, limit=2)
    assert len(page["results"]) == 2 and page["next_after"]
    assert len(memory.records(ctx, account, after=page["next_after"], limit=2)["results"]) == 1
    assert [b["revision"] for b in memory.summary(ctx, account)["buckets"]] == [2, 3]


def test_legacy_memory_assistant_denied_and_human_write_preserved(database, tenant):
    store, _ = database
    ctx, account = tenant
    memory, human, request = setup(store, ctx, account)
    token = "synthetic-memory-read-token-not-a-secret"

    def api(kind):
        if kind == "assistant":
            authenticator = Mock()
            authenticator.authenticate.return_value = Principal(
                replace(ctx, scopes=frozenset({"email.evidence.read"})), "assistant"
            )
            return TestClient(
                create_app(store, authenticator),
                headers={"Authorization": f"Bearer {token}"},
            )
        return TestClient(
            create_app(
                store,
                TokenRegistry(
                    [
                        Credential(
                            token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                            tenant_id=ctx.tenant_id,
                            actor_id=ctx.actor_id,
                            scopes={"email.evidence.read"}
                            | ({"email.review"} if kind == "human" else set()),
                            expires_at=datetime.now(UTC) + timedelta(minutes=10),
                            client_kind=kind,
                        )
                    ]
                ),
            ),
            headers={"Authorization": f"Bearer {token}"},
        )

    path = f"/v1/accounts/{account}/memory"
    record = uuid4()
    result = api("human").put(
        f"{path}/records/{record}",
        json=request.model_dump(mode="json"),
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert result.status_code == 200
    assistant = api("assistant")
    assert assistant.get(f"{path}/records/{record}").status_code == 403
    assert assistant.get(f"{path}/summary").status_code == 403
    assert assistant.get(f"{path}/changes").status_code == 403
    assert (
        assistant.put(
            f"{path}/records/{record}",
            json=request.model_dump(mode="json"),
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 403
    )


def test_uncommitted_publication_cannot_be_skipped_by_feed(database, tenant):
    store, _ = database
    ctx, account = tenant
    memory, human, request = setup(store, ctx, account)
    entered, release = threading.Event(), threading.Event()
    original = store.audit
    first_record = uuid4()

    def paused_audit(conn, actor, event, resource, identifier=None):
        original(conn, actor, event, resource, identifier)
        if event == "memory.publish" and identifier == str(first_record):
            entered.set()
            assert release.wait(10), "test publication release timed out"

    store.audit = paused_audit
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(publish, memory, human, account, request, first_record)
            assert entered.wait(5)
            second = pool.submit(publish, memory, human, account, request)
            try:
                assert memory.changes(ctx, account)["changes"] == []
            finally:
                release.set()
            assert first.result(timeout=10)["record"]["revision"] == 1
            assert second.result(timeout=10)["record"]["revision"] == 2
    finally:
        release.set()
        store.audit = original
    assert [r["revision"] for r in memory.changes(ctx, account)["changes"]] == [1, 2]


def test_sync_freshness_never_claims_interpretation_complete(database, tenant):
    store, admin = database
    ctx, account = tenant
    memory, _, _ = setup(store, ctx, account)
    summary = memory.summary(ctx, account)
    assert summary["last_checked_at"] is None and summary["needs_refresh"]
    with psycopg.connect(admin) as conn:
        conn.execute(
            "INSERT INTO sync_runs(tenant_id,account_id,request_id,outcome,event_count) "
            "VALUES (%s,%s,%s,'caught_up',0)",
            (ctx.tenant_id, account, uuid4()),
        )
        conn.execute(
            "INSERT INTO sync_workers(tenant_id,account_id,last_outcome) "
            "VALUES (%s,%s,'caught_up')",
            (ctx.tenant_id, account),
        )
    summary = memory.summary(ctx, account)
    assert summary["checked_recently"] and not summary["needs_refresh"]
    assert not summary["all_mail_interpreted"] and summary["latest_cursor"] is None
    with psycopg.connect(admin) as conn:
        conn.execute(
            "UPDATE sync_workers SET paused=true,last_outcome='auth_required' WHERE account_id=%s",
            (account,),
        )
    summary = memory.summary(ctx, account)
    assert summary["checked_recently"] and summary["needs_refresh"]
