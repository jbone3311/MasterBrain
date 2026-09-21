"""Same harmless MIME bytes through four independently shaped provider read boundaries.

No provider account, SMTP server, uploaded corpus or real correspondence is used.
These exercise current transports, not live account conformance or delta workers.
"""

import base64

import httpx
import pytest
from attachment_samples import attachment_cases
from test_imap import FakeImap

from email_brain.connectors.fastmail import MAIL, FastmailReadClient
from email_brain.connectors.gmail import GmailReadClient
from email_brain.connectors.graph import GraphReadClient
from email_brain.connectors.imap import ImapReadClient, UidReference

TOKEN = "synthetic-format-test-token-not-real"


@pytest.mark.parametrize("case", attachment_cases(), ids=lambda case: case.name)
def test_realistic_attachment_bytes_survive_gmail_raw_wrapper(case):
    def handle(request):
        assert request.method == "GET" and request.url.host == "gmail.googleapis.com"
        if request.url.path.endswith("/profile"):
            return httpx.Response(
                200, json={"emailAddress": "owner@example.invalid", "historyId": "10"}
            )
        assert request.url.params["format"] == "raw"
        return httpx.Response(
            200,
            json={
                "id": "m1",
                "threadId": "t1",
                "historyId": "11",
                "internalDate": "1234",
                "labelIds": ["INBOX"],
                "raw": base64.urlsafe_b64encode(case.raw).decode().rstrip("="),
            },
        )

    client = GmailReadClient(TOKEN, "owner@example.invalid", transport=httpx.MockTransport(handle))
    try:
        client.discover()
        assert client.message("m1").raw == case.raw
    finally:
        client.close()


@pytest.mark.parametrize("case", attachment_cases(), ids=lambda case: case.name)
def test_realistic_attachment_bytes_survive_graph_mime_endpoint(case):
    def handle(request):
        assert request.method == "GET" and request.url.host == "graph.microsoft.com"
        assert request.url.path == "/v1.0/users/synthetic-user/messages/m1/$value"
        assert 'IdType="ImmutableId"' in request.headers["Prefer"]
        return httpx.Response(200, content=case.raw)

    client = GraphReadClient("synthetic-user", TOKEN, transport=httpx.MockTransport(handle))
    try:
        assert client.download_mime("m1") == case.raw
    finally:
        client.close()


@pytest.mark.parametrize("case", attachment_cases(), ids=lambda case: case.name)
def test_realistic_attachment_bytes_survive_jmap_blob_download(case):
    def handle(request):
        assert request.method == "GET" and request.url.host == "api.fastmail.com"
        if request.url.path == "/jmap/session":
            return httpx.Response(
                200,
                json={
                    "primaryAccounts": {MAIL: "synthetic-account"},
                    "accounts": {"synthetic-account": {"accountCapabilities": {MAIL: {}}}},
                    "apiUrl": "https://api.fastmail.com/jmap/api/",
                    "downloadUrl": "https://api.fastmail.com/jmap/download/{accountId}/{blobId}/{name}?type={type}",
                },
            )
        assert "/synthetic-account/blob-1/" in request.url.path
        return httpx.Response(200, content=case.raw)

    client = FastmailReadClient(TOKEN, transport=httpx.MockTransport(handle))
    try:
        client.discover()
        assert client.download_blob("blob-1") == case.raw
    finally:
        client.close()


@pytest.mark.parametrize("case", attachment_cases(), ids=lambda case: case.name)
def test_realistic_attachment_bytes_survive_imap_literal(case):
    session = FakeImap()
    session.messages = {1: case.raw}
    session.uidnext = 2
    client = ImapReadClient(session)
    client.select("INBOX")
    assert client.fetch_mime(UidReference("INBOX", 42, 1)).raw == case.raw
    assert all(call[2] is True for call in session.calls if call[0] == "select")
