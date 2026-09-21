"""Offline IMAPClient-compatible fakes; no sockets, passwords, writes or real mail."""

import imaplib
from dataclasses import replace

import pytest

from email_brain.connectors.imap import (
    ImapMessageUnavailable,
    ImapProtocolError,
    ImapReadClient,
    ImapUidValidityChanged,
    ImapUnavailable,
    UidReference,
)
from email_brain.normalize import MAX_RAW_BYTES


class FakeImap:
    use_uid = True

    def __init__(self):
        self.validity = 42
        self.uidnext = 2002
        self.messages = {1: b"From: fake@example.invalid\r\n\r\nhello", 2001: b"second"}
        self.calls = []
        self.search_override = None
        self.fetch_override = None
        self.select_override = None
        self.fail = None
        self.reset_on_search = False

    def select_folder(self, folder, readonly=False):
        self.calls.append(("select", folder, readonly))
        if self.fail:
            raise self.fail
        return (
            self.select_override
            if self.select_override is not None
            else {
                b"UIDVALIDITY": self.validity,
                b"UIDNEXT": self.uidnext,
                b"READ-WRITE": False,
            }
        )

    def folder_status(self, folder, what):
        self.calls.append(("status", folder, what))
        if self.fail:
            raise self.fail
        return {b"UIDVALIDITY": self.validity, b"UIDNEXT": self.uidnext}

    def search(self, criteria):
        self.calls.append(("search", criteria))
        if self.fail:
            raise self.fail
        if self.reset_on_search:
            self.validity += 1
        if self.search_override is not None:
            return self.search_override
        assert criteria[0] == "UID"
        low, high = map(int, criteria[1].split(":"))
        return sorted(uid for uid in self.messages if low <= uid <= high)

    def fetch(self, messages, data):
        self.calls.append(("fetch", messages, data))
        if self.fail:
            raise self.fail
        if self.fetch_override is not None:
            return self.fetch_override(messages, data)
        uid = messages[0]
        if uid not in self.messages:
            return {}
        if "RFC822.SIZE" in data:
            return {uid: {b"RFC822.SIZE": len(self.messages[uid]), b"SEQ": 99}}
        assert data == ["UID", "FLAGS", f"BODY.PEEK[]<0.{MAX_RAW_BYTES + 1}>"]
        return {uid: {b"SEQ": 99, b"BODY[]<0>": self.messages[uid], b"FLAGS": (b"\\Seen",)}}


def finish(client, cursor):
    while True:
        page = client.inventory_page(cursor)
        if page.complete:
            return page.complete
        cursor = page.next_cursor


def test_imap_readonly_selection_uid_windows_complete_absence_only():
    fake = FakeImap()
    client = ImapReadClient(fake)
    cursor = client.select("INBOX")
    assert fake.calls[0] == ("select", "INBOX", True)
    page = client.inventory_page(cursor)
    assert page.uids == (1,) and page.complete is None
    assert page.next_cursor.next_uid == 1001
    complete = finish(client, page.next_cursor)
    assert complete.uids == (1, 2001)
    known = [UidReference("INBOX", 42, uid) for uid in [1, 2, 2001, 3000]]
    assert client.absent_uids(known, complete) == (UidReference("INBOX", 42, 2),)
    assert [call[1] for call in fake.calls if call[0] == "search"] == [
        ["UID", "1:1000"],
        ["UID", "1001:2000"],
        ["UID", "2001:2001"],
    ]


def test_imap_arrivals_after_selection_do_not_become_false_absences():
    fake = FakeImap()
    client = ImapReadClient(fake)
    cursor = client.select("INBOX")
    fake.messages[2002] = b"new arrival"
    fake.uidnext = 2003
    complete = finish(client, cursor)
    assert 2002 not in complete.uids
    assert client.absent_uids([UidReference("INBOX", 42, 2002)], complete) == ()


def test_imap_empty_folder_never_searches_reversed_uid_range():
    fake = FakeImap()
    fake.uidnext = 1
    fake.messages = {}
    client = ImapReadClient(fake)
    complete = finish(client, client.select("INBOX"))
    assert complete.uids == () and complete.high_water_uid == 0
    assert not any(call[0] == "search" for call in fake.calls)


@pytest.mark.parametrize("reason", ["disconnect", "reselect", "validity", "forged"])
def test_imap_certificate_cannot_survive_scope_reset(reason):
    fake = FakeImap()
    client = ImapReadClient(fake)
    complete = finish(client, client.select("INBOX"))
    if reason == "disconnect":
        client.reset()
    elif reason == "reselect":
        client.select("INBOX")
    elif reason == "validity":
        fake.validity += 1
    else:
        complete = replace(complete, uids=())
    with pytest.raises((ImapProtocolError, ImapUidValidityChanged)):
        client.absent_uids([UidReference("INBOX", 42, 1)], complete)


def test_imap_partial_scan_has_no_certificate_and_stale_cursor_fails():
    fake = FakeImap()
    client = ImapReadClient(fake)
    cursor = client.select("INBOX")
    assert client.inventory_page(cursor).complete is None
    with pytest.raises(ImapProtocolError, match="cursor"):
        client.inventory_page(cursor)
    with pytest.raises(ImapProtocolError, match="select"):
        client.fetch_mime(UidReference("INBOX", 42, 1))


@pytest.mark.parametrize(
    "values", [[0], [-1], [True], [2**32], ["1"], [1, 1], [1001], list(range(1, 1002)), {}]
)
def test_imap_malformed_search_never_seals_inventory(values):
    fake = FakeImap()
    fake.search_override = values
    client = ImapReadClient(fake)
    cursor = client.select("INBOX")
    with pytest.raises(ImapProtocolError):
        client.inventory_page(cursor)
    with pytest.raises(ImapProtocolError):
        client.inventory_page(cursor)


def test_imap_uidvalidity_changes_during_search_invalidate_result():
    fake = FakeImap()
    fake.reset_on_search = True
    client = ImapReadClient(fake)
    with pytest.raises(ImapUidValidityChanged):
        client.inventory_page(client.select("INBOX"))


@pytest.mark.parametrize(
    "data",
    [
        {},
        {b"UIDVALIDITY": True, b"UIDNEXT": 1},
        {b"UIDVALIDITY": 42, b"UIDNEXT": 0},
        {b"UIDVALIDITY": 42, b"UIDNEXT": 1, b"READ-WRITE": True},
    ],
)
def test_imap_bad_selection_is_not_usable(data):
    fake = FakeImap()
    fake.select_override = data
    client = ImapReadClient(fake)
    with pytest.raises(ImapProtocolError):
        client.select("INBOX")


@pytest.mark.parametrize("folder", ["", "INBOX\r\nSTORE", "a\x00b", "x" * 1025])
def test_imap_folder_validation_precedes_command(folder):
    fake = FakeImap()
    client = ImapReadClient(fake)
    with pytest.raises(ImapProtocolError):
        client.select(folder)
    assert fake.calls == []


def test_imap_sequence_mode_never_sends_commands():
    fake = FakeImap()
    fake.use_uid = False
    client = ImapReadClient(fake)
    with pytest.raises(ImapProtocolError, match="UID-mode"):
        client.select("INBOX")
    assert fake.calls == []


def test_imap_fetch_is_peek_only_ignores_mutable_sequence_number():
    fake = FakeImap()
    client = ImapReadClient(fake)
    client.select("INBOX")
    evidence = client.fetch_mime(UidReference("INBOX", 42, 1))
    assert evidence.raw == fake.messages[1] and evidence.reference.uid == 1
    assert evidence.flags == (b"\\Seen",)
    assert "hello" not in repr(evidence)
    assert all(call[0] in {"select", "status", "fetch"} for call in fake.calls)
    assert not hasattr(client, "send") and not hasattr(client, "expunge")


@pytest.mark.parametrize(
    "reference",
    [
        UidReference("Other", 42, 1),
        UidReference("INBOX", 43, 1),
        UidReference("INBOX", 42, 0),
        UidReference("INBOX", 42, True),
    ],
)
def test_imap_foreign_or_invalid_fetch_reference_denied(reference):
    fake = FakeImap()
    client = ImapReadClient(fake)
    client.select("INBOX")
    with pytest.raises(ImapProtocolError):
        client.fetch_mime(reference)
    assert not any(call[0] == "fetch" for call in fake.calls)


def test_imap_fetch_missing_after_search_does_not_mark_deleted():
    fake = FakeImap()
    client = ImapReadClient(fake)
    client.select("INBOX")
    del fake.messages[1]
    with pytest.raises(ImapMessageUnavailable):
        client.fetch_mime(UidReference("INBOX", 42, 1))


@pytest.mark.parametrize("size", [-1, True, "12", MAX_RAW_BYTES + 1])
def test_imap_size_preflight_rejects_before_body_request(size):
    fake = FakeImap()
    fake.fetch_override = lambda messages, data: {1: {b"UID": 1, b"RFC822.SIZE": size}}
    client = ImapReadClient(fake)
    client.select("INBOX")
    with pytest.raises(ImapProtocolError):
        client.fetch_mime(UidReference("INBOX", 42, 1))
    assert len([call for call in fake.calls if call[0] == "fetch"]) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {2: {b"UID": 2}},
        {True: {b"UID": 1}},
        {1: {b"UID": 2}},
        {1: {b"UID": 1, b"BODY[]<0>": b"wrong size", b"FLAGS": ()}},
        {1: {b"UID": 1, b"BODY[]<0>": b"a", b"FLAGS": ["\\Seen"]}},
        {1: {b"UID": 1, b"BODY[]<0>": b"a", b"FLAGS": [b"bad\nflag"]}},
        {1: {b"UID": 1, b"BODY[]<0>": b"a", b"FLAGS": [b"flag"] * 65}},
        {1: {b"UID": 1, b"BODY[]<0>": "a", b"FLAGS": ()}},
    ],
)
def test_imap_fetch_validates_complete_bytes_uid_and_flags(payload):
    fake = FakeImap()
    fake.fetch_override = lambda messages, data: (
        {1: {b"UID": 1, b"RFC822.SIZE": 1}} if "RFC822.SIZE" in data else payload
    )
    client = ImapReadClient(fake)
    client.select("INBOX")
    with pytest.raises(ImapProtocolError):
        client.fetch_mime(UidReference("INBOX", 42, 1))


@pytest.mark.parametrize(
    "error", [OSError("secret server details"), EOFError("secret"), imaplib.IMAP4.abort("secret")]
)
def test_imap_disconnect_scrubs_errors_and_resets_selection(error):
    fake = FakeImap()
    client = ImapReadClient(fake)
    cursor = client.select("INBOX")
    fake.fail = error
    with pytest.raises(ImapUnavailable) as caught:
        client.inventory_page(cursor)
    assert "secret" not in str(caught.value)
    fake.fail = None
    with pytest.raises(ImapProtocolError, match="select"):
        client.inventory_page(cursor)


def test_imap_known_ids_must_match_same_folder_validity_and_no_duplicates():
    for known in [
        [UidReference("INBOX", 43, 1)],
        [UidReference("Other", 42, 1)],
        [UidReference("INBOX", 42, 1)] * 2,
    ]:
        client = ImapReadClient(FakeImap())
        complete = finish(client, client.select("INBOX"))
        with pytest.raises(ImapProtocolError):
            client.absent_uids(known, complete)


def test_imap_scan_window_and_inventory_budgets_fail_closed(monkeypatch):
    monkeypatch.setattr("email_brain.connectors.imap.MAX_SCAN_WINDOWS", 1)
    client = ImapReadClient(FakeImap())
    page = client.inventory_page(client.select("INBOX"))
    with pytest.raises(ImapProtocolError, match="window budget"):
        client.inventory_page(page.next_cursor)
    monkeypatch.setattr("email_brain.connectors.imap.MAX_INVENTORY_UIDS", 0)
    client = ImapReadClient(FakeImap())
    with pytest.raises(ImapProtocolError, match="inventory budget"):
        client.inventory_page(client.select("INBOX"))


def test_imap_uidnext_regression_requires_reselection():
    fake = FakeImap()
    client = ImapReadClient(fake)
    cursor = client.select("INBOX")
    fake.uidnext -= 1
    with pytest.raises(ImapProtocolError, match="backwards"):
        client.inventory_page(cursor)


def test_imap_uidvalidity_reset_between_size_and_body_prevents_mixed_evidence():
    fake = FakeImap()

    def fetch(messages, data):
        fake.validity += 1
        return {1: {b"UID": 1, b"RFC822.SIZE": 1}}

    fake.fetch_override = fetch
    client = ImapReadClient(fake)
    client.select("INBOX")
    with pytest.raises(ImapUidValidityChanged):
        client.fetch_mime(UidReference("INBOX", 42, 1))
    assert len([call for call in fake.calls if call[0] == "fetch"]) == 1


@pytest.mark.parametrize("size", [0, MAX_RAW_BYTES])
def test_imap_raw_bytes_at_limits_are_preserved(size):
    fake = FakeImap()
    fake.messages[1] = b"a" * size
    client = ImapReadClient(fake)
    client.select("INBOX")
    assert client.fetch_mime(UidReference("INBOX", 42, 1)).raw == fake.messages[1]


def test_imap_boolean_uidvalidity_cannot_alias_integer_one():
    fake = FakeImap()
    fake.validity = 1
    client = ImapReadClient(fake)
    client.select("INBOX")
    with pytest.raises(ImapProtocolError):
        client.fetch_mime(UidReference("INBOX", True, 1))
