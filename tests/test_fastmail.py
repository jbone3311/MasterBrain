import httpx
import pytest

from email_brain.connectors.fastmail import (
    MAIL,
    FastmailReadClient,
    ProviderAuthRequired,
    ProviderThrottled,
    ProviderUnavailable,
)
from email_brain.connectors.jmap import ProtocolError

TOKEN = "synthetic-provider-token-not-real"


def session(**changes):
    return {
        "primaryAccounts": {MAIL: "a"},
        "accounts": {"a": {"accountCapabilities": {MAIL: {}}}},
        "apiUrl": "https://api.fastmail.com/jmap/api/",
        "downloadUrl": "https://api.fastmail.com/jmap/download/{accountId}/{blobId}/{name}?type={type}",
        **changes,
    }


def test_discovery_and_blob_download_are_bounded_and_read_only() -> None:
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("session"):
            return httpx.Response(200, json=session())
        return httpx.Response(200, content=b"Subject: Synthetic\r\n\r\nHello")

    client = FastmailReadClient(TOKEN, transport=httpx.MockTransport(handler))
    try:
        assert client.discover() == "a"
        assert client.download_blob("blob") == b"Subject: Synthetic\r\n\r\nHello"
        assert all(call.method == "GET" for call in calls)
        with pytest.raises(ProtocolError):
            client._call({"methodCalls": [["Email/set", {"accountId": "a"}, "r0"]]})
        assert len(calls) == 2
    finally:
        client.close()


@pytest.mark.parametrize(
    "url",
    [
        "http://api.fastmail.com/jmap/api",
        "https://evil.invalid/jmap/api",
        "https://api.fastmail.com.evil.invalid/jmap/api",
        "https://api.fastmail.com:444/jmap/api",
        "https://user:pass@api.fastmail.com/jmap/api",
        "https://api.fastmail.com:bad/jmap/api",
        "https://api.fastmail.com/jmap/\\evil",
        "https://api.fastmail.com/jmap/\napi",
    ],
)
def test_session_cannot_redirect_credentials(url: str) -> None:
    client = FastmailReadClient(
        TOKEN,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=session(apiUrl=url))
        ),
    )
    try:
        with pytest.raises(ProtocolError):
            client.discover()
    finally:
        client.close()


@pytest.mark.parametrize(
    "status,error",
    [
        (401, ProviderAuthRequired),
        (403, ProviderAuthRequired),
        (429, ProviderThrottled),
        (302, ProviderUnavailable),
        (500, ProviderUnavailable),
    ],
)
def test_provider_errors_are_explicit(status, error) -> None:
    client = FastmailReadClient(
        TOKEN,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, headers={"Retry-After": "120"})
        ),
    )
    try:
        with pytest.raises(error):
            client.discover()
    finally:
        client.close()


def test_oversized_response_refused() -> None:
    client = FastmailReadClient(
        TOKEN,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 1048577)),
    )
    try:
        with pytest.raises(ProtocolError, match="byte limit"):
            client.discover()
    finally:
        client.close()


def test_invalid_session_capabilities_scrubbed():
    client = FastmailReadClient(
        TOKEN,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json=session(accounts={"a": {"accountCapabilities": None}})
            )
        ),
    )
    try:
        with pytest.raises(ProtocolError):
            client.discover()
        assert client.account_id is None
    finally:
        client.close()
