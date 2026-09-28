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
from email_brain.store import Conflict, IngestItem
from email_brain.sync import (
    LISTING_LIMIT,
    MAX_PAGE_BYTES,
    Checkpoint,
    ReadWorker,
    message_size,
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
    legacy = Checkpoint(
        schema_version=2,
        generation=uuid4(),
        phase="listing",
        email_state="EMAIL",
        query_state="q",
        total=3,
        position=2,
    )
    assert Checkpoint.model_validate_json(legacy.encode()) == legacy
    assert legacy.email_state != legacy.query_state
    anchored = Checkpoint(
        generation=uuid4(), phase="listing", email_state="EMAIL", anchor="b", listed=2
    )
    assert Checkpoint.model_validate_json(anchored.encode()) == anchored
    assert anchored.schema_version == 3


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
        {"phase": "changes", "anchor": "a", "listed": 1},
        {"position": 1},
        {"position": True},
        {"query_state": "q", "total": 2},
        {"anchor": "a"},
        {"listed": 1},
        {"schema_version": 2, "anchor": "a", "listed": 1},
        {"schema_version": 4},
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


def worker_harness(
    monkeypatch,
    *,
    store_limit=None,
    raw=b"Subject: Synthetic\r\n\r\nHello",
    page_size=8,
    mails=("first", "second"),
    sizes=None,
    monotonic=None,
):
    """Only synthetic provider and durable-store doubles; no network/database access."""
    store = SimpleNamespace(cursor=None, commits=[], outcomes=[], retained={}, raws={})
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
        retained_blobs=lambda ctx, account, ids: {
            k: store.retained[k] for k in ids if k in store.retained
        },
        retained_raw=lambda ctx, account, sha: store.raws[sha],
    )
    monkeypatch.setattr("email_brain.sync.SyncStore", lambda store: jobs)
    calls = []
    mailbox = list(mails)

    def provider(payload):
        method, arguments, call_id = payload["methodCalls"][0]
        calls.append((method, arguments))
        if method == "Email/get":
            result = dict(accountId="a", state="s0")
        elif method == "Email/query":
            if "anchor" in arguments:
                if arguments["anchor"] not in mailbox:
                    return {"methodResponses": [["error", {"type": "anchorNotFound"}, call_id]]}
                position = mailbox.index(arguments["anchor"]) + arguments["anchorOffset"]
            else:
                position = arguments["position"]
            result = dict(
                accountId="a",
                position=position,
                total=len(mailbox),
                ids=mailbox[position : position + min(page_size, arguments["limit"])],
                queryState="q",
            )
        else:
            since = arguments["sinceState"]
            if since == "expired":
                return {"methodResponses": [["error", {"type": "cannotCalculateChanges"}, call_id]]}
            start = int(since[1:])
            ids = mailbox[start : start + arguments["maxChanges"]]
            end = start + len(ids)
            result = dict(
                accountId="a",
                oldState=since,
                newState=f"s{end}",
                hasMoreChanges=end < len(mailbox),
                created=ids,
                updated=[],
                destroyed=[],
            )
        return {"methodResponses": [[method, result, call_id]]}

    def metadata(ids):
        rows = []
        for identifier in ids:
            row = dict(
                id=identifier,
                blobId=f"blob-{identifier}",
                threadId="thread",
                mailboxIds={"inbox": True},
                keywords={},
                receivedAt="2026-09-20T00:00:00Z",
            )
            if sizes and identifier in sizes:
                row["size"] = sizes[identifier]
            rows.append(row)
        return dict(accountId="a", state="s2", notFound=[], list=rows)

    downloads = []

    def download(blob):
        downloads.append(blob)
        key = blob.removeprefix("blob-")
        if sizes and key in sizes and type(sizes[key]) is int and sizes[key] >= 0:
            return b"x" * sizes[key]
        return raw

    client = SimpleNamespace(
        discover=lambda: "a",
        reader=lambda: JmapReader("a", provider),
        metadata=metadata,
        download_blob=download,
    )
    ctx = TenantContext(uuid4(), uuid4(), frozenset({"email.ingest"}), uuid4())
    kwargs = {"monotonic": monotonic} if monotonic is not None else {}
    worker = ReadWorker(store, client, **kwargs)
    store.mailbox, store.downloads, store.jobs = mailbox, downloads, jobs
    return worker, store, calls, ctx, uuid4()


def cursor(store):
    return Checkpoint.model_validate_json(store.cursor)


@pytest.mark.parametrize("expired", [False, True])
def test_large_store_splits_listing_pages_by_bytes_and_changes_by_count(monkeypatch, expired):
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
    # Without a reported size a second message could be 16 MiB: commit the first alone.
    assert cursor(store).anchor == "first" and cursor(store).listed == 1
    assert worker.step(ctx, account) == "progress"
    assert cursor(store).phase == "reconcile"
    assert store.commits[-1][1]["inventory_total"] == 2
    assert worker.step(ctx, account) == "progress"
    assert worker.step(ctx, account) == "progress"
    assert worker.step(ctx, account) == "caught_up"
    assert cursor(store).email_state == "s2"
    assert all(args["limit"] == LISTING_LIMIT for method, args in calls if method == "Email/query")
    assert all(args["maxChanges"] == 1 for method, args in calls if method == "Email/changes")
    assert [len(items) for items, _ in store.commits] == [0, 1, 1, 0, 1, 1]
    assert all(item.raw == raw for items, _ in store.commits for item in items)


def test_default_store_lists_whole_pages_and_bounds_change_pages(monkeypatch):
    worker, store, calls, ctx, account = worker_harness(monkeypatch)
    for _ in range(3):
        assert worker.step(ctx, account) == "progress"
    assert worker.step(ctx, account) == "caught_up"
    assert all(args["limit"] == LISTING_LIMIT for method, args in calls if method == "Email/query")
    assert all(args["maxChanges"] == 16 for method, args in calls if method == "Email/changes")
    assert [len(items) for items, _ in store.commits] == [0, 2, 0, 2]
    assert all(
        item.blob_id == f"blob-{item.provider_id}" for items, _ in store.commits for item in items
    )


def test_reported_sizes_pack_listing_pages_within_budget(monkeypatch):
    sizes = {"first": 9 * MAX_RAW_BYTES, "second": 9 * MAX_RAW_BYTES, "third": 1}
    worker, store, _, ctx, account = worker_harness(
        monkeypatch,
        store_limit=MAX_PAGE_BYTES,
        raw=b"x",
        mails=("first", "second", "third"),
        sizes=sizes,
    )
    assert worker.step(ctx, account) == "progress"
    assert worker.step(ctx, account) == "progress"
    assert [i.provider_id for i in store.commits[-1][0]] == ["first"]
    assert worker.step(ctx, account) == "progress"
    assert [i.provider_id for i in store.commits[-1][0]] == ["second", "third"]
    assert cursor(store).phase == "reconcile"


def test_listing_uses_anchor_of_last_committed_id(monkeypatch):
    worker, store, calls, ctx, account = worker_harness(monkeypatch, page_size=1)
    assert worker.step(ctx, account) == "progress"
    assert worker.step(ctx, account) == "progress"
    assert cursor(store) == Checkpoint(
        generation=cursor(store).generation,
        phase="listing",
        email_state="s0",
        anchor="first",
        listed=1,
    )
    assert worker.step(ctx, account) == "progress"
    queries = [args for method, args in calls if method == "Email/query"]
    assert queries[0]["position"] == 0 and "anchor" not in queries[0]
    assert queries[1]["anchor"] == "first" and queries[1]["anchorOffset"] == 1
    assert "position" not in queries[1]
    assert all(q["sort"] == [{"property": "receivedAt", "isAscending": True}] for q in queries)
    assert cursor(store).phase == "reconcile" and store.commits[-1][1]["inventory_total"] == 2


def test_missing_anchor_restarts_generation_and_keeps_baseline(monkeypatch):
    worker, store, _, ctx, account = worker_harness(monkeypatch, page_size=1)
    assert worker.step(ctx, account) == "progress"
    assert worker.step(ctx, account) == "progress"
    first = cursor(store)
    store.mailbox.remove("first")
    assert worker.step(ctx, account) == "progress"
    restarted = cursor(store)
    assert restarted.phase == "listing" and restarted.anchor is None and restarted.listed == 0
    assert restarted.generation != first.generation and restarted.email_state == "s0"
    assert store.commits[-1][0] == [] and store.commits[-1][1]["inventory_generation"] is None
    assert worker.step(ctx, account) == "progress"
    assert cursor(store).phase == "reconcile" and store.commits[-1][1]["inventory_total"] == 1


def test_positional_listing_checkpoint_relists_with_anchors(monkeypatch):
    worker, store, calls, ctx, account = worker_harness(monkeypatch)
    legacy = Checkpoint(
        schema_version=2,
        generation=uuid4(),
        phase="listing",
        email_state="s0",
        query_state="q",
        position=1,
        total=2,
    )
    store.cursor = legacy.encode()
    assert worker.step(ctx, account) == "progress"
    fresh = cursor(store)
    assert fresh.schema_version == 3 and fresh.phase == "listing" and fresh.anchor is None
    assert fresh.generation != legacy.generation and fresh.email_state == "s0"
    assert not [m for m, _ in calls if m == "Email/query"] and store.commits[-1][0] == []


def test_time_budget_commits_a_partial_listing_page(monkeypatch):
    clock = [0.0]
    worker, store, _, ctx, account = worker_harness(monkeypatch, monotonic=lambda: clock[0])
    assert worker.step(ctx, account) == "progress"
    original = worker.client.download_blob

    def slow(blob):
        clock[0] += 45
        return original(blob)

    worker.client.download_blob = slow
    assert worker.step(ctx, account) == "progress"
    assert [i.provider_id for i in store.commits[-1][0]] == ["first"]
    assert cursor(store).anchor == "first" and cursor(store).listed == 1


def test_oversized_source_is_held_not_paused(monkeypatch):
    worker, store, _, ctx, account = worker_harness(
        monkeypatch, raw=b"x" * (MAX_RAW_BYTES + 1), sizes={"second": MAX_RAW_BYTES + 5}
    )
    assert worker.step(ctx, account) == "progress"
    assert worker.step(ctx, account) == "progress"
    held = store.commits[-1][0]
    assert [i.provider_id for i in held] == ["first", "second"]
    assert all(i.held and i.raw is None and i.held_reason == "source_too_large" for i in held)
    assert held[0].source_size is None and held[1].source_size == MAX_RAW_BYTES + 5
    assert store.downloads == ["blob-first"], "a reported oversize is never downloaded"
    assert held[0].blob_id == "blob-first" and held[0].version != held[1].version
    assert store.outcomes[-1] == "progress" and cursor(store).phase == "reconcile"


def test_held_version_depends_on_the_storage_budget(monkeypatch):
    versions = []
    for limit in (MAX_RAW_BYTES, 2 * MAX_RAW_BYTES):
        worker, store, _, ctx, account = worker_harness(
            monkeypatch, store_limit=limit, sizes={"first": 4 * MAX_RAW_BYTES}, mails=("first",)
        )
        worker.step(ctx, account)
        worker.step(ctx, account)
        versions.append(store.commits[-1][0][0].version)
    assert versions[0] != versions[1]


@pytest.mark.parametrize("value", ["big", -1, True, 2**31])
def test_invalid_reported_size_is_a_protocol_error(monkeypatch, value):
    worker, store, _, ctx, account = worker_harness(monkeypatch, sizes={"first": value})
    assert worker.step(ctx, account) == "progress"
    previous = store.cursor
    assert worker.step(ctx, account) == "protocol_error"
    assert store.cursor == previous


def test_message_size_contract():
    assert message_size(None) is None and message_size(0) == 0
    with pytest.raises(ProtocolError):
        message_size(1.5)


def test_flag_only_update_reuses_retained_bytes(monkeypatch):
    worker, store, _, ctx, account = worker_harness(monkeypatch)
    retained_raw = b"Subject: Retained\r\n\r\nAlready stored"
    sha = __import__("hashlib").sha256(retained_raw).hexdigest()
    store.retained["first"] = ("blob-first", sha)
    store.raws[sha] = retained_raw
    store.cursor = Checkpoint(generation=uuid4(), phase="changes", email_state="s0").encode()
    assert worker.step(ctx, account) == "caught_up"
    items = store.commits[-1][0]
    assert [i.provider_id for i in items] == ["first", "second"]
    assert items[0].raw == retained_raw and items[1].raw == b"Subject: Synthetic\r\n\r\nHello"
    assert store.downloads == ["blob-second"]


def test_changed_or_unreadable_retained_blob_falls_back_to_download(monkeypatch):
    worker, store, _, ctx, account = worker_harness(monkeypatch)
    store.retained["first"] = ("blob-first-old", "a" * 64)
    store.retained["second"] = ("blob-second", "b" * 64)  # Not readable locally.

    def unreadable(ctx, account, sha):
        raise BlobError()

    store.jobs.retained_raw = unreadable
    store.cursor = Checkpoint(generation=uuid4(), phase="changes", email_state="s0").encode()
    assert worker.step(ctx, account) == "caught_up"
    assert store.downloads == ["blob-first", "blob-second"]


def test_worker_preserves_cumulative_page_budget(monkeypatch):
    worker, store, _, ctx, account = worker_harness(
        monkeypatch, store_limit=MAX_PAGE_BYTES, raw=b"x" * (9 * MAX_RAW_BYTES)
    )
    checkpoint = Checkpoint(generation=uuid4(), phase="listing", email_state="s0")
    with pytest.raises(ProtocolError, match="page byte budget"):
        worker._fetch(ctx, account, checkpoint, ("first", "second"), (), "a", lambda: None)
    assert not store.commits and store.cursor is None


def test_partial_fetch_keeps_tombstones_and_prefix_order(monkeypatch):
    worker, store, _, ctx, account = worker_harness(
        monkeypatch, store_limit=MAX_PAGE_BYTES, raw=b"x" * (9 * MAX_RAW_BYTES)
    )
    checkpoint = Checkpoint(generation=uuid4(), phase="listing", email_state="s0")
    items, consumed = worker._fetch(
        ctx,
        account,
        checkpoint,
        ("first", "second"),
        ("gone",),
        "a",
        lambda: None,
        partial=lambda: False,
    )
    assert consumed == 1 and [i.provider_id for i in items] == ["first", "gone"]
    assert items[1].raw is None and not items[1].held


@pytest.mark.parametrize("limit", [True, "16777216", MAX_RAW_BYTES - 1, MAX_PAGE_BYTES + 1])
def test_worker_rejects_invalid_store_budget(monkeypatch, limit):
    with pytest.raises(ValueError, match="store raw byte limit"):
        worker_harness(monkeypatch, store_limit=limit)


def test_large_store_does_not_silently_expand_fastmail_transport(monkeypatch):
    worker, store, _, ctx, account = worker_harness(monkeypatch, store_limit=MAX_PAGE_BYTES)
    fake_client = worker.client

    def handler(request):
        if request.url.path.endswith("session"):
            return httpx.Response(
                200,
                json={
                    "primaryAccounts": {MAIL: "a"},
                    "accounts": {"a": {"accountCapabilities": {MAIL: {}}}},
                    "apiUrl": "https://api.fastmail.com/jmap/api/",
                    "downloadUrl": "https://api.fastmail.com/jmap/download/{accountId}/{blobId}",
                },
            )
        if request.method == "POST":
            payload = json.loads(request.content)
            method, args, call_id = payload["methodCalls"][0]
            if method == "Email/get" and args["ids"]:
                return httpx.Response(
                    200,
                    json={
                        "methodResponses": [[method, fake_client.metadata(args["ids"]), call_id]]
                    },
                )
            return httpx.Response(200, json=fake_client.reader().transport(payload))
        return httpx.Response(200, content=b"x" * (MAX_RAW_BYTES + 1))

    client = FastmailReadClient(
        "synthetic-provider-token-not-real", transport=httpx.MockTransport(handler)
    )
    worker.client = client
    try:
        assert worker.step(ctx, account) == "progress"
        # The transport keeps its own 1 MiB budget; the message is held, not fetched.
        assert worker.step(ctx, account) == "progress"
        held = store.commits[-1][0]
        assert len(held) == 2 and all(i.held and i.raw is None for i in held)
        assert cursor(store).phase == "reconcile"
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


def test_lost_lease_returns_without_recording_an_outcome(monkeypatch):
    worker, store, _, ctx, account = worker_harness(monkeypatch)

    def lost(*args, **kwargs):
        raise Conflict("worker lease expired or replaced")

    worker.jobs.renew = lost
    worker.jobs.finish = lost
    assert worker.step(ctx, account) == "lease_lost"
    assert store.cursor is None and not store.commits and not store.outcomes


def test_non_lease_conflict_is_a_durable_protocol_pause(monkeypatch):
    worker, store, _, ctx, account = worker_harness(monkeypatch)

    def reused(*args, **kwargs):
        raise Conflict("event key reused with different content")

    store.ingest_page = reused
    assert worker.step(ctx, account) == "protocol_error"
    assert store.outcomes == ["protocol_error"] and store.cursor is None


def test_ingest_item_held_contract():
    base = dict(
        event_key="e",
        provider_id="p",
        version="v",
        received_at=__import__("datetime").datetime(2026, 9, 20, tzinfo=__import__("datetime").UTC),
    )
    assert IngestItem(**base, held_reason="source_too_large", source_size=5).held
    with pytest.raises(ValueError, match="held"):
        IngestItem(**base, raw=b"x", held_reason="source_too_large")
    with pytest.raises(ValueError, match="held"):
        IngestItem(**base, held_reason="other")
    with pytest.raises(ValueError, match="source size"):
        IngestItem(**base, source_size=-1)
    with pytest.raises(ValueError, match="blob"):
        IngestItem(**base, raw=b"x", blob_id="")
