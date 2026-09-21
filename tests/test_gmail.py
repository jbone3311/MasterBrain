"""No network or real mail: transport and hostile protocol conformance tests."""

import base64
import json

import httpx
import pytest

from email_brain.connectors import gmail

TOKEN = "synthetic-gmail-token-never-valid"
ADDRESS = "owner@example.invalid"
RAW = b"From: sender@example.invalid\r\nSubject: Synthetic invoice\r\n\r\nPay nothing.\r\n"


def encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def message(**changes):
    return {
        "id": "m1",
        "threadId": "t1",
        "historyId": "15",
        "internalDate": "1234",
        "labelIds": ["INBOX"],
        "raw": encoded(RAW),
        **changes,
    }


class FakeGmail:
    def __init__(self):
        self.requests = []
        self.payload = {"historyId": "20", "history": []}
        self.status = 200
        self.headers = {}
        self.profile = {"emailAddress": ADDRESS, "historyId": "10"}

    def handle(self, request):
        self.requests.append(request)
        assert request.method == "GET"
        assert request.url.host == "gmail.googleapis.com"
        assert request.url.scheme == "https"
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        assert request.headers["accept-encoding"] == "identity"
        assert request.extensions["timeout"] == {"connect": 5, "read": 20, "write": 20, "pool": 20}
        if request.url.path.endswith("/profile"):
            return httpx.Response(200, json=self.profile)
        return httpx.Response(self.status, json=self.payload, headers=self.headers)


@pytest.fixture
def setup():
    fake = FakeGmail()
    client = gmail.GmailReadClient(TOKEN, ADDRESS, transport=httpx.MockTransport(fake.handle))
    client.discover()
    yield client, fake
    client.close()


def test_history_paging_only_terminal_checkpoint(setup):
    client, fake = setup
    fake.payload = {
        "historyId": "40",
        "nextPageToken": "opaque+/=",
        "history": [
            {"id": "15", "messagesAdded": [{"message": {"id": "m1", "threadId": "t1"}}]},
        ],
    }
    page = client.history("10")
    assert page.candidate_checkpoint is None
    assert page.changes[0].kind == "added"
    fake.payload = {
        "historyId": "47",
        "history": [{"id": "45", "messagesDeleted": [{"message": {"id": "m1", "threadId": "t1"}}]}],
    }
    final = client.history("10", page.next_page_token)
    assert final.candidate_checkpoint == "47"
    assert final.changes[0].kind == "deleted"
    assert dict(fake.requests[-1].url.params) == {
        "startHistoryId": "10",
        "maxResults": "100",
        "pageToken": "opaque+/=",
    }


def test_specific_changes_not_duplicated_by_generic_messages(setup):
    client, fake = setup
    ref = {"id": "m1", "threadId": "t1"}
    fake.payload = {
        "historyId": "20",
        "history": [
            {
                "id": "15",
                "messages": [ref],
                "labelsAdded": [{"message": ref, "labelIds": ["TRASH"]}],
                "labelsRemoved": [{"message": ref, "labelIds": ["INBOX"]}],
            }
        ],
    }
    changes = client.history("10").changes
    assert [item.kind for item in changes] == ["labels_added", "labels_removed"]
    assert all(item.kind != "deleted" for item in changes)


def test_generic_only_change_refetched_not_silently_dropped(setup):
    client, fake = setup
    fake.payload = {
        "historyId": "20",
        "history": [{"id": "15", "messages": [{"id": "m1", "threadId": "t1"}]}],
    }
    assert client.history("10").changes[0].kind == "refresh"


def test_listing_includes_trash_not_certified_by_estimate(setup):
    client, fake = setup
    fake.payload = {
        "messages": [{"id": "m1", "threadId": "t1"}],
        "resultSizeEstimate": 900,
        "nextPageToken": "other",
    }
    page = client.list_messages("first")
    assert page.messages[0].id == "m1"
    assert page.next_page_token == "other"
    assert not hasattr(page, "total")
    assert fake.requests[-1].url.params["includeSpamTrash"] == "true"


def test_raw_and_minimal_fetch(setup):
    client, fake = setup
    fake.payload = message()
    assert client.message("m1").raw == RAW
    assert fake.requests[-1].url.params["format"] == "raw"
    fake.payload.pop("raw")
    assert client.message("m1", include_raw=False).raw is None
    assert fake.requests[-1].url.params["format"] == "minimal"


def test_minimal_id_and_labels_only_is_valid_without_invented_metadata(setup):
    client, fake = setup
    fake.payload = {"id": "m1", "labelIds": ["INBOX"]}
    result = client.message("m1", include_raw=False)
    assert isinstance(result, gmail.GmailMinimalMessage)
    assert result.id == "m1"
    assert result.label_ids == ("INBOX",)
    assert result.thread_id is result.history_id is result.internal_date_ms is result.raw is None
    with pytest.raises(gmail.GmailProtocolError):
        client.message("m1", include_raw=True)


def test_minimal_wrong_id_still_rejected(setup):
    client, fake = setup
    fake.payload = {"id": "m2", "labelIds": ["INBOX"]}
    with pytest.raises(gmail.GmailProtocolError, match="binding"):
        client.message("m1", include_raw=False)


@pytest.mark.parametrize("field", ["threadId", "historyId", "internalDate"])
def test_minimal_present_but_malformed_metadata_is_not_treated_as_missing(setup, field):
    client, fake = setup
    fake.payload = {"id": "m1", "labelIds": ["INBOX"], field: None}
    with pytest.raises(gmail.GmailProtocolError):
        client.message("m1", include_raw=False)


@pytest.mark.parametrize("raw", [b"", b"\x00\xff\r\n", b"a" * gmail.MAX_RAW_BYTES])
def test_raw_preserved_exactly_even_if_mime_rejected_later(setup, raw):
    client, fake = setup
    fake.payload = message(raw=encoded(raw))
    assert client.message("m1").raw == raw


def test_decoded_raw_limit(setup):
    client, fake = setup
    fake.payload = message(raw=encoded(b"a" * (gmail.MAX_RAW_BYTES + 1)))
    with pytest.raises(gmail.GmailProtocolError):
        client.message("m1")


@pytest.mark.parametrize(
    "changes",
    [
        {"id": "m2"},
        {"threadId": None},
        {"historyId": "not-history"},
        {"raw": "$"},
        {"raw": "a"},
        {"raw": "YQ=== "},
        {"raw": None},
        {"internalDate": "-2"},
        {"internalDate": "253402300800000"},
        {"labelIds": ["INBOX", "INBOX"]},
        {"labelIds": "INBOX"},
    ],
)
def test_rejects_bad_message_fields(setup, changes):
    client, fake = setup
    fake.payload = message(**changes)
    with pytest.raises(gmail.GmailProtocolError):
        client.message("m1")


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"historyId": 20},
        {"historyId": "9"},
        {"historyId": "２０"},
        {"historyId": "20", "history": None},
        {"historyId": "20", "history": [{"id": "10"}]},
        {"historyId": "20", "history": [{"id": "21"}]},
        {"historyId": "20", "history": [{"id": "19"}, {"id": "15"}]},
        {"historyId": "20", "history": [{"id": "15", "messagesAdded": [{}]}]},
        {
            "historyId": "20",
            "history": [{"id": "15", "labelsAdded": [{"message": {"id": "m1", "threadId": "t1"}}]}],
        },
        {"historyId": "20", "nextPageToken": "same"},
        {"historyId": "20", "nextPageToken": ""},
    ],
)
def test_bad_history_never_yields_checkpoint(setup, payload):
    client, fake = setup
    fake.payload = payload
    with pytest.raises(gmail.GmailProtocolError):
        client.history("10", "same")


@pytest.mark.parametrize(
    "payload",
    [
        {"messages": [None]},
        {"messages": [{"id": "m1"}]},
        {"messages": [{"id": "m1", "threadId": "t1"}] * 2},
        {"messages": [{"id": f"m{i}", "threadId": "t1"} for i in range(101)]},
        {"nextPageToken": "same"},
    ],
)
def test_bad_list_pages(setup, payload):
    client, fake = setup
    fake.payload = payload
    with pytest.raises(gmail.GmailProtocolError):
        client.list_messages("same")


def test_history_change_budget(setup):
    client, fake = setup
    fake.payload = {
        "historyId": "20",
        "history": [
            {"id": str(i), "messages": [{"id": f"m{j}", "threadId": "t1"} for j in range(600)]}
            for i in (15, 16)
        ],
    }
    with pytest.raises(gmail.GmailProtocolError, match="budget"):
        client.history("10")


def test_404_has_resource_specific_meaning(setup):
    client, fake = setup
    fake.status = 404
    with pytest.raises(gmail.GmailHistoryExpired):
        client.history("10")
    with pytest.raises(gmail.GmailMessageGone):
        client.message("m1")
    with pytest.raises(gmail.GmailUnavailable):
        client.list_messages()


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, gmail.GmailAuthRequired),
        (403, gmail.GmailAuthRequired),
        (429, gmail.GmailThrottled),
        (500, gmail.GmailUnavailable),
        (302, gmail.GmailUnavailable),
        (204, gmail.GmailUnavailable),
    ],
)
def test_error_status_scrubbed_no_redirect(setup, status, expected):
    client, fake = setup
    fake.status = status
    fake.headers = {"Location": "https://evil.invalid/steal", "Retry-After": "999999"}
    fake.payload = {"private": "do not leak this mail"}
    with pytest.raises(expected) as error:
        client.history("10")
    assert "private" not in str(error.value)
    assert "do not leak" not in str(error.value)
    assert len(fake.requests) == 2
    if status == 429:
        assert error.value.retry_after_seconds == 3600
    if status in {401, 403}:
        with pytest.raises(gmail.GmailProtocolError, match="profile"):
            client.list_messages()


@pytest.mark.parametrize(
    "route",
    [
        "https://evil.invalid",
        "//evil.invalid",
        "../messages",
        "messages/../profile",
        "messages/a?token=steal",
        "messages/a%2Fb",
        "watch",
        "messages/send",
        "messages/delete",
    ],
)
def test_route_boundary(setup, route):
    client, fake = setup
    # send/delete are possible opaque message IDs under GET, never write verbs.
    if route in {"messages/send", "messages/delete"}:
        client._get(route)
        assert fake.requests[-1].method == "GET"
    else:
        with pytest.raises(gmail.GmailProtocolError):
            client._get(route)
        assert len(fake.requests) == 1


@pytest.mark.parametrize(
    "identifier", ["../../x", "https://evil.invalid", "a/b", "m1?x=y", "x" * 129]
)
def test_message_path_injection_rejected_before_request(setup, identifier):
    client, fake = setup
    with pytest.raises(gmail.GmailProtocolError):
        client.message(identifier)
    assert len(fake.requests) == 1


def test_profile_mismatch_and_failed_refresh_revokes_binding(setup):
    client, fake = setup
    fake.profile["emailAddress"] = "other@example.invalid"
    with pytest.raises(gmail.GmailProtocolError, match="binding"):
        client.discover()
    with pytest.raises(gmail.GmailProtocolError, match="profile"):
        client.history("10")


def test_must_discover_before_mail():
    fake = FakeGmail()
    client = gmail.GmailReadClient(TOKEN, ADDRESS, transport=httpx.MockTransport(fake.handle))
    with pytest.raises(gmail.GmailProtocolError, match="profile"):
        client.message("m1")
    assert not fake.requests
    client.close()


@pytest.mark.parametrize(
    "token", ["short", "x" * 4097, "x" * 16 + "\n", "x" * 16 + "\x00", "é" * 20]
)
def test_invalid_token_rejected(token):
    with pytest.raises(ValueError):
        gmail.GmailReadClient(token, ADDRESS)


def test_json_byte_limit_and_compression(setup):
    client, fake = setup
    fake.payload = {"data": "a" * gmail.MAX_JSON_BYTES}
    with pytest.raises(gmail.GmailProtocolError, match="byte limit"):
        client.history("10")
    fake.payload = {}
    fake.headers = {"Content-Encoding": "unsupported"}
    with pytest.raises(gmail.GmailProtocolError, match="compressed"):
        client.history("10")


def test_elapsed_deadline(setup, monkeypatch):
    client, _ = setup
    times = iter([0, 31])
    monkeypatch.setattr(gmail.time, "monotonic", lambda: next(times))
    with pytest.raises(gmail.GmailUnavailable, match="deadline"):
        client.history("10")


def test_network_error_does_not_leak_credentials():
    def handler(request):
        raise httpx.ReadTimeout(f"private {TOKEN}", request=request)

    client = gmail.GmailReadClient(TOKEN, ADDRESS, transport=httpx.MockTransport(handler))
    with pytest.raises(gmail.GmailUnavailable) as error:
        client.discover()
    assert TOKEN not in str(error.value)
    client.close()


@pytest.mark.parametrize("body", [b"not-json", b"\xff", b"[" * 2000, b"null"])
def test_invalid_json_is_scrubbed(body):
    client = gmail.GmailReadClient(
        TOKEN, ADDRESS, transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body))
    )
    with pytest.raises(gmail.GmailProtocolError):
        client.discover()
    client.close()


@pytest.mark.parametrize("retry", ["-1", "Wed, 21 Oct 2015 07:28:00 GMT", "9" * 100, ""])
def test_invalid_retry_after_does_not_create_unbounded_sleep(setup, retry):
    client, fake = setup
    fake.status = 429
    fake.headers = {"Retry-After": retry}
    with pytest.raises(gmail.GmailThrottled) as error:
        client.history("10")
    assert error.value.retry_after_seconds is None


def test_environment_proxy_not_inherited(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://credential-stealer.invalid:1234")
    fake = FakeGmail()
    client = gmail.GmailReadClient(TOKEN, ADDRESS, transport=httpx.MockTransport(fake.handle))
    assert client.discover().email_address == ADDRESS
    assert len(fake.requests) == 1
    client.close()


def hint(email=ADDRESS, subscription="projects/synthetic/subscriptions/email"):
    return {
        "subscription": subscription,
        "message": {
            "messageId": "123",
            "data": encoded(json.dumps({"emailAddress": email, "historyId": "999"}).encode()),
        },
    }


def test_notification_is_only_untrusted_data(setup):
    client, fake = setup
    result = gmail.decode_untrusted_hint(
        hint(),
        expected_email=ADDRESS,
        expected_subscription="projects/synthetic/subscriptions/email",
    )
    assert isinstance(result, gmail.UntrustedGmailHint)
    assert result.history_id == "999"
    assert not hasattr(result, "candidate_checkpoint")
    assert len(fake.requests) == 1
    assert client.history("10").candidate_checkpoint == "20"


@pytest.mark.parametrize(
    "payload",
    [
        hint(email="attacker@example.invalid"),
        hint(subscription="projects/attacker/subscriptions/email"),
        {},
        {"subscription": "projects/synthetic/subscriptions/email", "message": {"data": "bad!"}},
    ],
)
def test_spoofed_or_malformed_hints_rejected(payload):
    with pytest.raises(gmail.GmailProtocolError):
        gmail.decode_untrusted_hint(
            payload,
            expected_email=ADDRESS,
            expected_subscription="projects/synthetic/subscriptions/email",
        )


@pytest.mark.parametrize(
    "body",
    [
        b'{"emailAddress":"attacker@example.invalid","emailAddress":"owner@example.invalid",'
        b'"historyId":"10"}',
        b'{"emailAddress":"owner@example.invalid","historyId":"10","historyId":"20"}',
        b'{"emailAddress":"owner@example.invalid","historyId":"10",'
        b'"extra":{"nested":1,"nested":2}}',
    ],
)
def test_duplicate_json_keys_cannot_establish_account_binding(body):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, content=body)

    client = gmail.GmailReadClient(TOKEN, ADDRESS, transport=httpx.MockTransport(handler))
    with pytest.raises(gmail.GmailProtocolError, match="invalid provider JSON"):
        client.discover()
    with pytest.raises(gmail.GmailProtocolError, match="profile"):
        client.list_messages()
    assert len(requests) == 1
    client.close()


@pytest.mark.parametrize(
    "body",
    [
        b'{"emailAddress":"attacker@example.invalid","emailAddress":"owner@example.invalid",'
        b'"historyId":"10"}',
        b'{"emailAddress":"owner@example.invalid","historyId":"10","historyId":"20"}',
        b'{"emailAddress":"owner@example.invalid","historyId":"10",'
        b'"extra":{"nested":1,"nested":2}}',
    ],
)
def test_notification_inner_json_duplicate_keys_rejected(body):
    envelope = hint()
    envelope["message"]["data"] = encoded(body)
    with pytest.raises(gmail.GmailProtocolError, match="invalid provider JSON"):
        gmail.decode_untrusted_hint(
            envelope,
            expected_email=ADDRESS,
            expected_subscription="projects/synthetic/subscriptions/email",
        )


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
def test_nonfinite_json_rejected_even_in_unknown_nested_fields(number):
    raw = (
        '{"emailAddress":"owner@example.invalid","historyId":"10",'
        '"extra":{"number":' + number + "}}"
    ).encode()
    with pytest.raises(gmail.GmailProtocolError, match="invalid provider JSON"):
        gmail._json(raw)
    envelope = hint()
    envelope["message"]["data"] = encoded(raw)
    with pytest.raises(gmail.GmailProtocolError, match="invalid provider JSON"):
        gmail.decode_untrusted_hint(
            envelope,
            expected_email=ADDRESS,
            expected_subscription="projects/synthetic/subscriptions/email",
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"error": {"errors": [{"reason": "rateLimitExceeded"}, {"reason": "forbidden"}]}},
        {"error": {"errors": [{"reason": ["rateLimitExceeded"]}]}},
        {"error": {"errors": [{"reason": "rateLimitExceeded"}] * 101}},
        {
            "error": {"errors": [{"reason": "rateLimitExceeded"}]},
            "huge": "a" * gmail.MAX_JSON_BYTES,
        },
    ],
)
def test_403_mixed_malformed_or_oversize_quota_body_invalidates_binding(setup, payload):
    client, fake = setup
    fake.status = 403
    fake.payload = payload
    with pytest.raises(gmail.GmailAuthRequired):
        client.history("10")
    with pytest.raises(gmail.GmailProtocolError, match="profile"):
        client.history("10")


def test_403_response_deadline_still_enforced(setup, monkeypatch):
    client, fake = setup
    fake.status = 403
    fake.payload = {"error": {"errors": [{"reason": "rateLimitExceeded"}]}}
    times = iter([0, 31])
    monkeypatch.setattr(gmail.time, "monotonic", lambda: next(times))
    with pytest.raises(gmail.GmailUnavailable, match="deadline"):
        client.history("10")
