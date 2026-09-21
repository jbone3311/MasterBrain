import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from email_brain.blobs import BlobError
from email_brain.connectors.fastmail import MAIL, FastmailReadClient
from email_brain.connectors.jmap import JmapReader, ProtocolError
from email_brain.domain.models import TenantContext
from email_brain.normalize import MAX_RAW_BYTES
from email_brain.sync import (
    MAX_PAGE_BYTES,
    Checkpoint,
    ReadWorker,
    metadata_rows,
    retry_delay,
    true_keys,
)
from email_brain.sync_store import Lease


def query(**changes):
    data = dict(accountId="a", position=0, total=2, ids=["a", "b"], queryState="q")
    data.update(changes)
    return JmapReader("a", lambda request: {"methodResponses": [["Email/query", data, "r0"]]})


def test_query_checkpoint_contract():
    page = query(total=3).query_page()
    assert page.has_more and page.query_state == "q" and page.ids == ("a", "b")
    cp = Checkpoint(
        generation=uuid4(),
        phase="listing",
        email_state="EMAIL",
        query_state="q",
        total=3,
        position=2,
    )
    assert Checkpoint.model_validate_json(cp.encode()) == cp
    assert cp.email_state != cp.query_state


@pytest.mark.parametrize(
    "changes",
    [
        {"ids": ["a", "a"]},
        {"ids": ["a", 2]},
        {"ids": [""]},
        {"ids": ["\x00"]},
        {"queryState": None},
        {"total": True},
        {"total": -1},
        {"total": 1},
        {"position": False},
        {"position": 1},
        {"ids": [], "total": 2},
        {"queryState": "x" * 513},
    ],
)
def test_query_malformed_is_not_an_empty_mailbox(changes):
    with pytest.raises(ProtocolError):
        query(**changes).query_page()


@pytest.mark.parametrize(
    "fields",
    [
        {"phase": "changes", "position": 1},
        {"position": 1},
        {"position": True},
        {"schema_version": 3},
        {"send": True},
        {"email_state": ""},
    ],
)
def test_checkpoint_fails_closed(fields):
    values = dict(generation=uuid4(), phase="listing", email_state="s")
    values.update(fields)
    with pytest.raises((ValidationError, ProtocolError)):
        Checkpoint(**values)


@pytest.mark.parametrize(
    "list_,missing",
    [
        ([{"id": "a"}, {"id": "a"}], []),
        ([{"id": "other"}], []),
        ([{"id": "a"}], ["a"]),
        ([], []),
        ([], ["a", "a"]),
    ],
)
def test_metadata_must_account_for_every_id(list_, missing):
    with pytest.raises(ProtocolError):
        metadata_rows(dict(accountId="a", state="s", list=list_, notFound=missing), ("a",), "a")


def test_metadata_accepts_explicit_not_found():
    rows, missing = metadata_rows(
        dict(accountId="a", state="s", list=[], notFound=["a"]), ("a",), "a"
    )
    assert rows == {} and missing == ("a",)


@pytest.mark.parametrize("value", [None, [], {"x": False}, {"x": 1}, {"\x00": True}])
def test_membership_maps_are_strict(value):
    with pytest.raises(ProtocolError):
        true_keys(value)


def test_retry_pressure_bounds():
    for failures in range(1001):
        for retry in (None, 0, 3, 600, 100000):
            for jitter in (0.0, 0.5, 1.0):
                delay = retry_delay(failures, retry, jitter)
                assert 5 <= delay <= 3600
                assert delay >= min(retry or 0, 3600)


def test_changes_without_progress_rejected():
    reader = JmapReader(
        "a",
        lambda request: {
            "methodResponses": [
                [
                    "Email/changes",
                    {
                        "accountId": "a",
                        "oldState": "s",
                        "newState": "s",
                        "hasMoreChanges": True,
                        "created": [],
                        "updated": [],
                        "destroyed": [],
                    },
                    "r0",
                ]
            ]
        },
    )
    with pytest.raises(ProtocolError, match="progress"):
        reader.changes("s")


def test_account_override_is_denied_before_transport():
    reader = JmapReader("a", lambda request: pytest.fail("must not call transport"))
    with pytest.raises(ProtocolError):
        reader._call("Email/get", {"accountId": "other"})


def worker_harness(monkeypatch, *, store_limit=None, raw=b"Subject: Synthetic\r\n\r\nHello"):
    """Only synthetic provider and durable-store doubles; no network/database access."""
    store = SimpleNamespace(cursor=None, commits=[], outcomes=[])
    if store_limit is not None:
        store.max_raw_bytes = store_limit

    def ingest(ctx, account_id, previous, following, items, **kwargs):
        assert previous == store.cursor
        store.commits.append((items, kwargs))
        store.cursor = following
        return len(items)

    store.ingest_page = ingest
    lease_token = uuid4()
    jobs = SimpleNamespace(
        acquire=lambda ctx, account: Lease(lease_token, "a", store.cursor, 0),
        renew=lambda *args: None,
        reconciliation_candidates=lambda *args: (),
        finish=lambda ctx, account, token, outcome, *args, **kwargs: store.outcomes.append(outcome),
    )
    monkeypatch.setattr("email_brain.sync.SyncStore", lambda store: jobs)
    calls = []

    def provider(payload):
        method, arguments, call_id = payload["methodCalls"][0]
        calls.append((method, arguments))
        if method == "Email/get":
            result = dict(accountId="a", state="s0")
        elif method == "Email/query":
            position = arguments["position"]
            result = dict(
                accountId="a", position=position, total=2,
                ids=["first", "second"][position:position + arguments["limit"]],
                queryState="q",
            )
        else:
            since = arguments["sinceState"]
            if since == "expired":
                return {"methodResponses": [["error", {"type": "cannotCalculateChanges"}, call_id]]}
            start = int(since[1:])
            ids = ["first", "second"][start:start + arguments["maxChanges"]]
            end = start + len(ids)
            result = dict(
                accountId="a", oldState=since, newState=f"s{end}",
                hasMoreChanges=end < 2, created=ids, updated=[], destroyed=[],
            )
        return {"methodResponses": [[method, result, call_id]]}

    def metadata(ids):
        return dict(
            accountId="a", state="s2", notFound=[],
            list=[dict(
                id=identifier, blobId=f"blob-{identifier}", threadId="thread",
                mailboxIds={"inbox": True}, keywords={}, receivedAt="2026-09-20T00:00:00Z",
            ) for identifier in ids],
        )

    client = SimpleNamespace(
        discover=lambda: "a", reader=lambda: JmapReader("a", provider),
        metadata=metadata, download_blob=lambda blob: raw,
    )
    ctx = TenantContext(uuid4(), uuid4(), frozenset({"email.ingest"}), uuid4())
    return ReadWorker(store, client), store, calls, ctx, uuid4()


@pytest.mark.parametrize("expired", [False, True])
def test_large_store_uses_one_message_pages_through_listing_and_changes(monkeypatch, expired):
    raw = b"x" * (MAX_RAW_BYTES + 1)
    worker, store, calls, ctx, account = worker_harness(
        monkeypatch, store_limit=MAX_PAGE_BYTES, raw=raw
    )
    if expired:
        store.cursor = Checkpoint(
            generation=uuid4(), phase="changes", email_state="expired"
        ).encode()
    assert worker.step(ctx, account) == "progress"  # Baseline, including expired cursor.
    assert worker.step(ctx, account) == "progress"
    assert Checkpoint.model_validate_json(store.cursor).position == 1
    assert worker.step(ctx, account) == "progress"
    assert Checkpoint.model_validate_json(store.cursor).phase == "reconcile"
    assert worker.step(ctx, account) == "progress"
    assert worker.step(ctx, account) == "progress"
    assert worker.step(ctx, account) == "caught_up"
    assert Checkpoint.model_validate_json(store.cursor).email_state == "s2"
    assert all(args["limit"] == 1 for method, args in calls if method == "Email/query")
    assert all(args["maxChanges"] == 1 for method, args in calls if method == "Email/changes")
    assert [len(items) for items, _ in store.commits] == [0, 1, 1, 0, 1, 1]
    assert all(item.raw == raw for items, _ in store.commits for item in items)


def test_legacy_store_without_limit_preserves_eight_message_pages(monkeypatch):
    worker, store, calls, ctx, account = worker_harness(monkeypatch)
    for _ in range(3):
        assert worker.step(ctx, account) == "progress"
    assert worker.step(ctx, account) == "caught_up"
    assert all(args["limit"] == 8 for method, args in calls if method == "Email/query")
    assert all(args["maxChanges"] == 8 for method, args in calls if method == "Email/changes")
    assert [len(items) for items, _ in store.commits] == [0, 2, 0, 2]


@pytest.mark.parametrize("limit", [MAX_RAW_BYTES, 2 * MAX_RAW_BYTES, MAX_PAGE_BYTES])
def test_worker_rejects_bytes_above_store_budget_without_checkpoint(monkeypatch, limit):
    worker, store, _, ctx, account = worker_harness(
        monkeypatch, store_limit=limit, raw=b"x" * (limit + 1)
    )
    assert worker.step(ctx, account) == "progress"
    previous = store.cursor
    assert worker.step(ctx, account) == "protocol_error"
    assert store.cursor == previous
    assert len(store.commits) == 1


def test_worker_preserves_cumulative_page_budget(monkeypatch):
    worker, store, _, _, _ = worker_harness(
        monkeypatch, store_limit=MAX_PAGE_BYTES, raw=b"x" * (9 * MAX_RAW_BYTES)
    )
    checkpoint = Checkpoint(generation=uuid4(), phase="listing", email_state="s0")
    with pytest.raises(ProtocolError, match="page byte budget"):
        worker._fetch(checkpoint, ("first", "second"), (), "a", lambda: None)
    assert not store.commits and store.cursor is None


@pytest.mark.parametrize("limit", [True, "16777216", MAX_RAW_BYTES - 1, MAX_PAGE_BYTES + 1])
def test_worker_rejects_invalid_store_budget(monkeypatch, limit):
    with pytest.raises(ValueError, match="store raw byte limit"):
        worker_harness(monkeypatch, store_limit=limit)


def test_large_store_does_not_silently_expand_fastmail_transport(monkeypatch):
    worker, store, _, ctx, account = worker_harness(monkeypatch, store_limit=MAX_PAGE_BYTES)
    fake_client = worker.client

    def handler(request):
        if request.url.path.endswith("session"):
            return httpx.Response(200, json={
                "primaryAccounts": {MAIL: "a"},
                "accounts": {"a": {"accountCapabilities": {MAIL: {}}}},
                "apiUrl": "https://api.fastmail.com/jmap/api/",
                "downloadUrl": "https://api.fastmail.com/jmap/download/{accountId}/{blobId}",
            })
        if request.method == "POST":
            payload = json.loads(request.content)
            method, args, call_id = payload["methodCalls"][0]
            if method == "Email/get" and args["ids"]:
                return httpx.Response(200, json={
                    "methodResponses": [[method, fake_client.metadata(args["ids"]), call_id]]
                })
            return httpx.Response(200, json=fake_client.reader().transport(payload))
        return httpx.Response(200, content=b"x" * (MAX_RAW_BYTES + 1))

    client = FastmailReadClient(
        "synthetic-provider-token-not-real", transport=httpx.MockTransport(handler)
    )
    worker.client = client
    try:
        assert worker.step(ctx, account) == "progress"
        previous = store.cursor
        assert worker.step(ctx, account) == "protocol_error"
        assert store.cursor == previous and len(store.commits) == 1
    finally:
        client.close()


def test_evidence_storage_failure_retries_without_checkpoint_or_parse_pause(monkeypatch):
    worker, store, _, ctx, account = worker_harness(monkeypatch, store_limit=MAX_PAGE_BYTES)
    assert worker.step(ctx, account) == "progress"
    previous = store.cursor
    ingest = store.ingest_page
    delays = []

    def fail_storage(*args, **kwargs):
        raise BlobError()

    def finish(ctx, account, token, outcome, *args, **kwargs):
        store.outcomes.append(outcome)
        delays.append(kwargs.get("delay"))

    store.ingest_page = fail_storage
    worker.jobs.finish = finish
    assert worker.step(ctx, account) == "retry"
    assert store.cursor == previous and len(store.commits) == 1
    assert store.outcomes[-1] == "retry" and 5 <= delays[-1] <= 3600
    store.ingest_page = ingest
    assert worker.step(ctx, account) == "progress"
    assert store.cursor != previous
