from __future__ import annotations

from typing import Any

import pytest

from email_brain.connectors.jmap import AnchorNotFound, JmapReader, ProtocolError, ResyncRequired


def reply(method: str, **kwargs: Any) -> dict[str, Any]:
    return {"methodResponses": [[method, {"accountId": "a", **kwargs}, "r0"]]}


def test_changes_preserves_opaque_state() -> None:
    reader = JmapReader(
        "a",
        lambda request: reply(
            "Email/changes",
            oldState="old",
            newState="opaque-next",
            created=["c"],
            updated=["u"],
            destroyed=["d"],
            hasMoreChanges=True,
        ),
    )
    result = reader.changes("old")
    assert result.next_state == "opaque-next"
    assert result.destroyed == ("d",) and result.has_more


def test_cursor_expiry_is_not_empty_success() -> None:
    reader = JmapReader(
        "a",
        lambda request: {"methodResponses": [["error", {"type": "cannotCalculateChanges"}, "r0"]]},
    )
    with pytest.raises(ResyncRequired):
        reader.changes("expired")


@pytest.mark.parametrize(
    "change",
    [
        {"accountId": "other"},
        {"oldState": "wrong"},
        {"created": ["x"], "destroyed": ["x"]},
        {"hasMoreChanges": "yes"},
    ],
)
def test_malformed_or_wrong_account(change: dict[str, Any]) -> None:
    payload = dict(
        oldState="old", newState="new", created=[], updated=[], destroyed=[], hasMoreChanges=False
    )
    payload.update(change)
    reader = JmapReader("a", lambda request: reply("Email/changes", **payload))
    with pytest.raises(ProtocolError):
        reader.changes("old")


def test_baseline_is_email_state_not_query_state() -> None:
    reader = JmapReader("a", lambda request: reply("Email/get", state="email-state", list=[]))
    assert reader.baseline_state() == "email-state"


def test_write_methods_have_no_surface() -> None:
    reader = JmapReader("a", lambda request: pytest.fail("transport must not be called"))
    with pytest.raises(ProtocolError):
        reader._call("Email/set", {})


def test_query_page_sends_stable_sort_and_anchor() -> None:
    requests: list[dict[str, Any]] = []

    def transport(request: dict[str, Any]) -> dict[str, Any]:
        arguments = request["methodCalls"][0][1]
        requests.append(arguments)
        if "anchor" in arguments:
            return reply("Email/query", ids=["c", "d"], position=2, total=5, queryState="q")
        return reply("Email/query", ids=["a", "b"], position=0, total=5, queryState="q")

    reader = JmapReader("a", transport)
    page = reader.query_page("b", limit=2)
    assert page.ids == ("c", "d") and page.has_more
    assert requests[0]["anchor"] == "b" and requests[0]["anchorOffset"] == 1
    assert "position" not in requests[0]
    assert requests[0]["sort"] == [{"property": "receivedAt", "isAscending": True}]
    reader.query_page(None, limit=2)
    assert requests[1]["position"] == 0 and "anchor" not in requests[1]


def test_missing_anchor_is_explicit_not_an_empty_mailbox() -> None:
    reader = JmapReader(
        "a", lambda request: {"methodResponses": [["error", {"type": "anchorNotFound"}, "r0"]]}
    )
    with pytest.raises(AnchorNotFound):
        reader.query_page("gone")


@pytest.mark.parametrize(
    "page",
    [
        dict(ids=["b", "c"], position=1, total=3),  # anchor echoed back
        dict(ids=[], position=1, total=3),  # no progress
        dict(ids=["c"], position=-1, total=3),
        dict(ids=["c"], position=5, total=3),
    ],
)
def test_anchored_page_contract(page: dict[str, Any]) -> None:
    reader = JmapReader("a", lambda request: reply("Email/query", queryState="q", **page))
    with pytest.raises(ProtocolError):
        reader.query_page("b")


def test_short_page_is_not_the_end_when_total_says_more() -> None:
    reader = JmapReader(
        "a",
        lambda request: reply("Email/query", ids=["a", "b"], position=0, total=9, queryState="q"),
    )
    page = reader.query_page(limit=50)
    assert page.has_more
    last = JmapReader(
        "a",
        lambda request: reply("Email/query", ids=["i"], position=8, total=9, queryState="q"),
    ).query_page("h", limit=50)
    assert not last.has_more
