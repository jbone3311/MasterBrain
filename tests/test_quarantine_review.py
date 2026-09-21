from dataclasses import replace
from uuid import uuid4

import pytest
import test_postgres as pg

from email_brain.store import AccessDenied, NotFound

pytestmark = pytest.mark.postgres
database, tenant, item = pg.database, pg.tenant, pg.item


def test_current_quarantine_pagination_is_bounded_and_has_no_raw_access(database, tenant):
    store, _ = database
    ctx, account = tenant
    bad = [replace(item(f"bad-{i}"), provider_id=f"p{i}", raw=b"") for i in range(60)]
    store.ingest_page(ctx, account, None, "c1", bad)
    resolved = [replace(item(f"fixed-{i}"), provider_id=f"p{i}") for i in range(3)]
    resolved.append(replace(item("deleted"), provider_id="p3", raw=None))
    store.ingest_page(ctx, account, "c1", "c2", resolved)
    seen, after = set(), None
    while True:
        page = store.quarantines(ctx, account, limit=10, after=after)
        assert page["raw_access"] is False and page["reprocessing"] is False
        assert len(page["results"]) <= 10
        for row in page["results"]:
            assert row["id"] not in seen
            seen.add(row["id"])
            assert row["provider_id"] not in {"p0", "p1", "p2", "p3"}
            assert set(row) == {
                "id",
                "provider_id",
                "raw_sha256",
                "reason",
                "parser_version",
                "recorded_at",
            }
        after = page["next_after"]
        if after is None:
            break
    assert len(seen) == 56


def test_quarantine_requires_evidence_scope_and_known_owned_account(database, tenant):
    store, _ = database
    ctx, account = tenant
    with pytest.raises(AccessDenied):
        store.quarantines(replace(ctx, scopes=frozenset({"email.search"})), account)
    with pytest.raises(NotFound):
        store.quarantines(ctx, uuid4())
    for limit in (0, 51, True, -1):
        with pytest.raises(ValueError):
            store.quarantines(ctx, account, limit=limit)


def test_only_latest_rejected_version_is_in_current_review_queue(database, tenant):
    store, _ = database
    ctx, account = tenant
    store.ingest_page(ctx, account, None, "c1", [replace(item("bad-v1"), raw=b"")])
    store.ingest_page(ctx, account, "c1", "c2", [replace(item("bad-v2"), raw=b"")])
    page = store.quarantines(ctx, account)
    assert len(page["results"]) == 1
    with store.transaction(ctx) as conn:
        assert conn.execute("SELECT count(*) AS n FROM quarantine_receipts").fetchone()["n"] == 2
