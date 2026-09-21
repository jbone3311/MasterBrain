"""Operator-injected parser contract and database fences, synthetic data only."""

from dataclasses import replace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import test_postgres as pg

from email_brain.auth import Principal
from email_brain.mime_sandbox import decode_response, process_raw
from email_brain.recovery import Recovery, RecoveryUnavailable
from email_brain.schemas import SearchRequest
from email_brain.store import Conflict, Store

database, tenant = pg.database, pg.tenant
VERSION = "sandbox-mime-v1-" + "a" * 64


class FakeProcessor:
    parser_version = VERSION
    max_raw_bytes = 16 * 1024 * 1024

    def prepare(self, raw):
        return decode_response(process_raw(raw), raw)


@pytest.mark.parametrize(
    "version,limit",
    [
        ("arbitrary", 1),
        (VERSION, True),
        (VERSION, 0),
        (VERSION, 16 * 1024 * 1024 + 1),
    ],
)
def test_processor_contract_rejects_unversioned_or_unbounded_injection(version, limit):
    processor = FakeProcessor()
    processor.parser_version, processor.max_raw_bytes = version, limit
    store = MagicMock(spec=Store)
    with pytest.raises(ValueError):
        Recovery(store, processor=processor)
    store.transaction.assert_not_called()


def make_held(store, ctx, account, monkeypatch):
    from email_brain import store as persistence

    with monkeypatch.context() as patch:
        patch.setattr(persistence, "prepare_mime", lambda raw: (None, [], True))
        store.ingest_page(ctx, account, None, "held", [pg.item()])
    return store.quarantines(ctx, account)["results"][0]["id"]


@pytest.mark.postgres
def test_injected_parser_publishes_image_bound_evidence(database, tenant, monkeypatch):
    store, _ = database
    ctx, account = tenant
    receipt = make_held(store, ctx, account, monkeypatch)
    recovery = Recovery(store, processor=FakeProcessor())
    result = recovery.retry(Principal(ctx, "human"), account, receipt, VERSION)
    assert result["outcome"] == "recovered"
    assert store.evidence(ctx, result["evidence_id"])["parser_version"] == VERSION
    assert (
        store.search(ctx, SearchRequest(query="Melron"))[0]["evidence_id"] == result["evidence_id"]
    )
    monkeypatch.setattr(recovery.processor, "prepare", lambda raw: pytest.fail("cached rerun"))
    assert recovery.retry(Principal(ctx, "human"), account, receipt, VERSION) == result


@pytest.mark.postgres
@pytest.mark.parametrize(
    "failure", ["timeout", "changed_version", "changed_budget", "changed_during"]
)
def test_processor_unavailable_does_not_cache_attempt(database, tenant, monkeypatch, failure):
    store, _ = database
    ctx, account = tenant
    receipt = make_held(store, ctx, account, monkeypatch)
    processor = FakeProcessor()
    recovery = Recovery(store, processor=processor)
    if failure == "changed_version":
        processor.parser_version = "sandbox-mime-v1-" + "b" * 64
    elif failure == "changed_budget":
        processor.max_raw_bytes = 10
    elif failure == "changed_during":
        prepare = processor.prepare

        def changing(raw):
            result = prepare(raw)
            processor.parser_version = "sandbox-mime-v1-" + "b" * 64
            return result

        monkeypatch.setattr(processor, "prepare", changing)
    else:
        monkeypatch.setattr(
            processor, "prepare", lambda raw: (_ for _ in ()).throw(TimeoutError("private"))
        )
    with pytest.raises(RecoveryUnavailable) as raised:
        recovery.retry(Principal(ctx, "human"), account, receipt, VERSION)
    assert "private" not in str(raised.value)
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM recovery_attempts").fetchone()["n"] == 0
    assert len(store.quarantines(ctx, account)["results"]) == 1


@pytest.mark.postgres
def test_provider_change_while_isolated_processing_prevents_publication(
    database, tenant, monkeypatch
):
    store, _ = database
    ctx, account = tenant
    receipt = make_held(store, ctx, account, monkeypatch)
    processor = FakeProcessor()
    prepare = processor.prepare

    def process_then_delete(raw):
        result = prepare(raw)
        store.ingest_page(ctx, account, "held", "gone", [replace(pg.item("delete"), raw=None)])
        return result

    monkeypatch.setattr(processor, "prepare", process_then_delete)
    with pytest.raises(Conflict):
        Recovery(store, processor=processor).retry(
            Principal(ctx, "human"), account, receipt, VERSION
        )
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM recovery_attempts").fetchone()["n"] == 0
        assert (
            conn.execute("SELECT opaque_cursor FROM sync_cursors").fetchone()["opaque_cursor"]
            == "gone"
        )
    assert store.search(ctx, SearchRequest(query="Melron")) == []


def test_default_recovery_does_not_admit_sandbox_version_or_construct_worker():
    store = MagicMock(spec=Store)
    ctx = pg.TenantContext(
        uuid4(), uuid4(), frozenset({"email.review", "email.evidence.read"}), uuid4()
    )
    store.require = Store.require
    with pytest.raises(Conflict):
        Recovery(store).retry(Principal(ctx, "human"), uuid4(), uuid4(), VERSION)
    store.transaction.assert_not_called()


@pytest.mark.postgres
@pytest.mark.parametrize("case", ["null_success", "contradictory", "wrong_type", "oversized_list"])
def test_malformed_adapter_result_is_not_cached_as_rejected(database, tenant, monkeypatch, case):
    store, _ = database
    ctx, account = tenant
    receipt = make_held(store, ctx, account, monkeypatch)
    processor = FakeProcessor()
    normalized, _, _ = processor.prepare(pg.item().raw)
    values = {
        "null_success": (None, [], False),
        "contradictory": (normalized, [], True),
        "wrong_type": {"unexpected": "private"},
        "oversized_list": (normalized, [None] * 65, False),
    }
    monkeypatch.setattr(processor, "prepare", lambda raw: values[case])
    with pytest.raises(RecoveryUnavailable):
        Recovery(store, processor=processor).retry(
            Principal(ctx, "human"), account, receipt, VERSION
        )
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM recovery_attempts").fetchone()["n"] == 0
    assert len(store.quarantines(ctx, account)["results"]) == 1
