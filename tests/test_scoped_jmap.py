"""Synthetic protocol boundary for a future bounded Fastmail read pilot."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from email_brain.connectors.jmap import JmapReader, ProtocolError, ScopedMailWindow


def window() -> ScopedMailWindow:
    return ScopedMailWindow(
        "mailbox-fixture", datetime(2026, 9, 1, tzinfo=UTC),
        datetime(2026, 9, 8, tzinfo=UTC),
    )


def test_scoped_query_is_exact_and_anchor_keeps_filter() -> None:
    calls = []

    def transport(request):
        calls.append(request)
        return {"methodResponses": [["Email/query", {
            "accountId": "account-fixture", "position": 1 if len(calls) == 2 else 0,
            "total": 2, "ids": ["second" if len(calls) == 2 else "first"],
            "queryState": "query-fixture",
        }, "r0"]]}

    reader = JmapReader("account-fixture", transport)
    first = reader.query_page(limit=1, scope=window())
    second = reader.query_page(anchor="first", limit=1, scope=window())
    assert first.ids == ("first",) and first.has_more
    assert second.ids == ("second",) and not second.has_more
    for request in calls:
        method, args, _ = request["methodCalls"][0]
        assert method == "Email/query"
        assert args["filter"] == {
            "inMailbox": "mailbox-fixture", "after": "2026-09-01T00:00:00Z",
            "before": "2026-09-08T00:00:00Z",
        }
        assert args["sort"] == [{"property": "receivedAt", "isAscending": True}]
    assert calls[0]["methodCalls"][0][1]["position"] == 0
    assert calls[1]["methodCalls"][0][1]["anchor"] == "first"
    assert calls[1]["methodCalls"][0][1]["anchorOffset"] == 1


def test_existing_unscoped_query_does_not_acquire_an_implicit_filter() -> None:
    calls = []

    def transport(request):
        calls.append(request)
        return {"methodResponses": [["Email/query", {
            "accountId": "account-fixture", "position": 0, "total": 0,
            "ids": [], "queryState": "query-fixture",
        }, "r0"]]}

    JmapReader("account-fixture", transport).query_page()
    assert "filter" not in calls[0]["methodCalls"][0][1]


@pytest.mark.parametrize("after,before", [
    (datetime(2026, 9, 1), datetime(2026, 9, 2, tzinfo=UTC)),
    (datetime(2026, 9, 1, tzinfo=timezone(timedelta(hours=1))),
     datetime(2026, 9, 2, tzinfo=UTC)),
    (datetime(2026, 9, 1, 0, 0, 0, 1, tzinfo=UTC), datetime(2026, 9, 2, tzinfo=UTC)),
    (datetime(2026, 9, 2, tzinfo=UTC), datetime(2026, 9, 1, tzinfo=UTC)),
    (datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 10, 3, tzinfo=UTC)),
])
def test_window_refuses_unbounded_or_ambiguous_dates(after, before) -> None:
    with pytest.raises(ValueError):
        ScopedMailWindow("mailbox-fixture", after, before)


def test_window_refuses_invalid_mailbox_and_query_scope_type() -> None:
    with pytest.raises(ProtocolError):
        ScopedMailWindow("", datetime(2026, 9, 1, tzinfo=UTC),
                         datetime(2026, 9, 2, tzinfo=UTC))
    with pytest.raises(ValueError):
        ScopedMailWindow("mailbox\nfixture", datetime(2026, 9, 1, tzinfo=UTC),
                         datetime(2026, 9, 2, tzinfo=UTC))
    reader = JmapReader("account-fixture", lambda _: pytest.fail("no provider request"))
    with pytest.raises(ValueError):
        reader.query_page(scope={"after": "2026-09-01"})  # type: ignore[arg-type]


@pytest.mark.parametrize("mailboxes,stamp,allowed", [
    ({"mailbox-fixture": True}, "2026-09-01T00:00:00Z", True),
    ({"mailbox-fixture": True}, "2026-09-07T23:59:59Z", True),
    ({"mailbox-fixture": True}, "2026-09-08T00:00:00Z", False),
    ({"mailbox-fixture": True}, "2026-08-31T23:59:59Z", False),
    ({"another": True}, "2026-09-02T00:00:00Z", False),
])
def test_metadata_must_confirm_mailbox_and_time(mailboxes, stamp, allowed) -> None:
    assert window().accepts_metadata({"mailboxIds": mailboxes, "receivedAt": stamp}) is allowed


@pytest.mark.parametrize("row", [
    None,
    {"receivedAt": "2026-09-02T00:00:00Z"},
    {"mailboxIds": {"mailbox-fixture": False}, "receivedAt": "2026-09-02T00:00:00Z"},
    {"mailboxIds": {"mailbox-fixture": True}, "receivedAt": "2026-09-02T00:00:00"},
    {"mailboxIds": {"mailbox-fixture": True}, "receivedAt": "not-a-date"},
    {"mailboxIds": {"\x00": True}, "receivedAt": "2026-09-02T00:00:00Z"},
])
def test_malformed_metadata_cannot_justify_download(row) -> None:
    with pytest.raises(ProtocolError):
        window().accepts_metadata(row)


def test_exact_exclusion_policy_is_fingerprinted_but_query_stays_bounded() -> None:
    base = window()
    private = ScopedMailWindow(
        base.mailbox_id, base.after, base.before, ("Private-Example",)
    )
    row = {"mailboxIds": {"mailbox-fixture": True, "Private-Example": True},
           "receivedAt": "2026-09-02T00:00:00Z"}
    assert private.query_filter() == base.query_filter()
    assert private.fingerprint() != base.fingerprint()
    assert private.accepts_metadata(row)
    assert private.excludes_metadata(row)
    assert not private.excludes_metadata({"mailboxIds": {"mailbox-fixture": True}})


@pytest.mark.parametrize("ids", [
    ("mailbox-fixture",), ("z", "a"), ("a", "a"), ("bad\nmailbox",),
    tuple(f"m{i}" for i in range(101)),
])
def test_exclusion_policy_refuses_ambiguous_or_unbounded_ids(ids) -> None:
    base = window()
    with pytest.raises(ValueError):
        ScopedMailWindow(base.mailbox_id, base.after, base.before, ids)
