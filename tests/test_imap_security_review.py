"""Independent late-race and certificate tests using exclusively fictional IMAP mail."""

from dataclasses import replace

import pytest
from test_imap import FakeImap, finish

from email_brain.connectors.imap import (
    CompleteInventory,
    ImapProtocolError,
    ImapReadClient,
    ImapUidValidityChanged,
    UidReference,
)
from email_brain.normalize import MAX_RAW_BYTES


def test_uidvalidity_change_after_body_fetch_never_returns_mixed_evidence():
    fake = FakeImap()

    def change_after_body(messages, fields):
        if "RFC822.SIZE" in fields:
            return {1: {b"RFC822.SIZE": 3}}
        fake.validity += 1
        return {1: {b"BODY[]<0>": b"new", b"FLAGS": ()}}

    fake.fetch_override = change_after_body
    client = ImapReadClient(fake)
    client.select("INBOX")
    with pytest.raises(ImapUidValidityChanged):
        client.fetch_mime(UidReference("INBOX", 42, 1))
    assert len([call for call in fake.calls if call[0] == "fetch"]) == 2
    with pytest.raises(ImapProtocolError, match="select"):
        client.fetch_mime(UidReference("INBOX", fake.validity, 1))


@pytest.mark.parametrize("actual_size", [2, MAX_RAW_BYTES + 1])
def test_size_changed_after_preflight_discards_entire_body_and_selection(actual_size):
    fake = FakeImap()
    fake.fetch_override = lambda messages, fields: (
        {1: {b"RFC822.SIZE": 1}}
        if "RFC822.SIZE" in fields
        else {1: {b"BODY[]<0>": b"x" * actual_size, b"FLAGS": ()}}
    )
    client = ImapReadClient(fake)
    client.select("INBOX")
    with pytest.raises(ImapProtocolError, match="incomplete or oversized"):
        client.fetch_mime(UidReference("INBOX", 42, 1))
    with pytest.raises(ImapProtocolError, match="select"):
        client.fetch_mime(UidReference("INBOX", 42, 1))


def test_expunge_after_earlier_window_favors_stale_presence_not_false_absence():
    fake = FakeImap()
    client = ImapReadClient(fake)
    first = client.inventory_page(client.select("INBOX"))
    assert first.uids == (1,) and first.complete is None
    del fake.messages[1]
    complete = finish(client, first.next_cursor)
    assert 1 in complete.uids
    # No claim that one non-atomic scan detects every expunge. Next scan catches this.
    assert client.absent_uids([UidReference("INBOX", 42, 1)], complete) == ()
    refreshed = finish(client, client.select("INBOX"))
    assert client.absent_uids([UidReference("INBOX", 42, 1)], refreshed) == (
        UidReference("INBOX", 42, 1),
    )


def test_equal_but_copied_certificate_has_no_absence_authority():
    client = ImapReadClient(FakeImap())
    complete = finish(client, client.select("INBOX"))
    copied = replace(complete)
    assert copied == complete and copied is not complete
    with pytest.raises(ImapProtocolError, match="certificate"):
        client.absent_uids([UidReference("INBOX", 42, 2)], copied)


def test_partial_inventory_cannot_be_promoted_by_constructing_certificate():
    client = ImapReadClient(FakeImap())
    cursor = client.select("INBOX")
    partial = client.inventory_page(cursor)
    assert partial.complete is None
    forged = CompleteInventory(
        cursor.folder,
        cursor.uidvalidity,
        cursor.high_water_uid,
        cursor.generation,
        partial.uids,
    )
    with pytest.raises(ImapProtocolError, match="certificate"):
        client.absent_uids([UidReference("INBOX", 42, 2001)], forged)
