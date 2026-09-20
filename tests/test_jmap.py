from __future__ import annotations

from typing import Any

import pytest

from email_brain.connectors.jmap import JmapReader, ProtocolError, ResyncRequired


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
