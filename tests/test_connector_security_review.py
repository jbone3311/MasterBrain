"""Independent provider boundary regressions; all HTTP responses are synthetic."""

import httpx
import pytest

from email_brain.connectors import gmail, graph
from email_brain.connectors.fastmail import (
    ProviderThrottled,
    ProviderUnavailable,
)
from email_brain.connectors.jmap import ProtocolError

TOKEN = "synthetic-review-token-never-valid"
ADDRESS = "owner@example.invalid"
GRAPH_ROOT = "https://graph.microsoft.com/v1.0/users/test-user/mailFolders/inbox/messages/delta"


@pytest.mark.parametrize("reason", ["rateLimitExceeded", "userRateLimitExceeded"])
def test_gmail_documented_403_rate_limits_are_retryable_and_keep_binding(reason):
    # https://developers.google.com/workspace/gmail/api/guides/handle-errors
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path.endswith("/profile"):
            return httpx.Response(200, json={"emailAddress": ADDRESS, "historyId": "10"})
        if len(calls) == 2:
            return httpx.Response(
                403,
                json={
                    "error": {
                        "errors": [{"reason": reason, "message": "synthetic-private-canary"}],
                        "code": 403,
                    }
                },
                headers={"Retry-After": "37"},
            )
        return httpx.Response(200, json={"historyId": "11", "history": []})

    client = gmail.GmailReadClient(TOKEN, ADDRESS, transport=httpx.MockTransport(handle))
    try:
        client.discover()
        with pytest.raises(gmail.GmailThrottled) as failure:
            client.history("10")
        assert failure.value.retry_after_seconds == 37
        assert "private-canary" not in str(failure.value)
        # Rate limiting is not credential revocation; no profile rediscovery is required.
        assert client.history("10").candidate_checkpoint == "11"
        assert len(calls) == 3
    finally:
        client.close()


@pytest.mark.parametrize(
    "reasons", [["domainPolicy"], ["rateLimitExceeded", "domainPolicy"], [], [None]]
)
def test_gmail_rate_word_cannot_override_permission_denial(reasons):
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path.endswith("/profile"):
            return httpx.Response(200, json={"emailAddress": ADDRESS, "historyId": "10"})
        return httpx.Response(
            403,
            json={"error": {"errors": [{"reason": reason} for reason in reasons], "code": 403}},
        )

    client = gmail.GmailReadClient(TOKEN, ADDRESS, transport=httpx.MockTransport(handle))
    try:
        client.discover()
        with pytest.raises(gmail.GmailAuthRequired):
            client.history("10")
        with pytest.raises(gmail.GmailProtocolError):
            client.history("10")
        assert len(calls) == 2
    finally:
        client.close()


@pytest.mark.parametrize("retry", [b"\xb2", b"\xb3", b"\xb9"])
def test_graph_nonnumeric_ascii_retry_header_does_not_escape_typed_errors(retry):
    client = graph.GraphReadClient(
        "test-user",
        TOKEN,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(429, headers=[(b"Retry-After", retry)])
        ),
    )
    try:
        with pytest.raises(ProviderThrottled) as failure:
            client.download_mime("fictional-message")
        assert failure.value.retry_after_seconds is None
    finally:
        client.close()


def test_graph_empty_success_still_checks_elapsed_deadline(monkeypatch):
    ticks = iter([0, 31])
    monkeypatch.setattr(graph.time, "monotonic", lambda: next(ticks))
    client = graph.GraphReadClient(
        "test-user",
        TOKEN,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=httpx.ByteStream(b""))),
    )
    try:
        with pytest.raises(ProviderUnavailable, match="deadline"):
            client.download_mime("fictional-message")
    finally:
        client.close()


def test_graph_identifier_slashes_remain_encoded_single_path_segments():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, content=b"Subject: Synthetic\r\n\r\nNo real mail")

    client = graph.GraphReadClient(
        "user/../other%2Fuser", TOKEN, transport=httpx.MockTransport(handle)
    )
    try:
        assert client.download_mime("mail/../other%2Fmail")
        assert len(calls) == 1
        assert calls[0].url.host == "graph.microsoft.com"
        assert calls[0].url.raw_path == (
            b"/v1.0/users/user%2F..%2Fother%252Fuser/messages/mail%2F..%2Fother%252Fmail/$value"
        )
    finally:
        client.close()


@pytest.mark.parametrize("link_kind", ["@odata.nextLink", "@odata.deltaLink"])
@pytest.mark.parametrize("foreign_part", ["account", "folder"])
def test_graph_returned_continuation_cannot_rebind_account_or_folder(link_kind, foreign_part):
    foreign = (
        GRAPH_ROOT.replace("test-user", "other-user")
        if foreign_part == "account"
        else (GRAPH_ROOT.replace("inbox", "other-folder"))
    )
    client = graph.GraphReadClient(
        "test-user",
        TOKEN,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"value": [], link_kind: foreign + "?opaque=1"})
        ),
    )
    try:
        with pytest.raises(ProtocolError):
            client.delta("inbox")
    finally:
        client.close()


def test_graph_repeated_removed_ids_do_not_become_global_delete_commands():
    payload = {
        "value": [
            {"id": "same-id", "@removed": {"reason": "deleted"}},
            {"id": "same-id"},
        ],
        "@odata.nextLink": GRAPH_ROOT + "?$skiptoken=continuation",
    }
    client = graph.GraphReadClient(
        "test-user",
        TOKEN,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    )
    try:
        page = client.delta("inbox")
        assert not page.complete
        assert [change.kind for change in page.changes] == ["membership_removed", "changed"]
        assert all(change.requires_fetch for change in page.changes)
        assert all(change.folder_id == "inbox" for change in page.changes)
    finally:
        client.close()
