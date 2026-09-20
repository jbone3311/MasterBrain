from uuid import uuid4

import pytest
from pydantic import ValidationError

from email_brain.connectors.jmap import JmapReader, ProtocolError
from email_brain.sync import Checkpoint, metadata_rows, retry_delay, true_keys


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
        {"schema_version": 2},
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
