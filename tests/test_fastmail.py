import json

import httpx
import pytest

from email_brain.connectors.fastmail import (
    MAIL,
    MAX_BLOB_BYTES,
    BlobTooLarge,
    ControlTooLarge,
    FastmailReadClient,
    ProviderAuthRequired,
    ProviderThrottled,
    ProviderUnavailable,
    retry_after_seconds,
)
from email_brain.connectors.jmap import ProtocolError
from email_brain.normalize import MAX_RAW_BYTES

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


def test_control_response_overflow_has_a_splitable_error_type() -> None:
    def handler(request):
        if request.url.path.endswith("session"):
            return httpx.Response(200, json=session())
        return httpx.Response(200, content=b" " * (MAX_RAW_BYTES + 1))

    client = FastmailReadClient(TOKEN, transport=httpx.MockTransport(handler))
    try:
        client.discover()
        with pytest.raises(ControlTooLarge, match="byte limit"):
            client.metadata(["message"])
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


@pytest.mark.parametrize(
    "limit", [None, True, False, "2097152", 2097152.0, MAX_RAW_BYTES - 1, MAX_BLOB_BYTES + 1]
)
def test_blob_budget_requires_explicit_bounded_integer(limit):
    with pytest.raises(ValueError, match="raw byte limit"):
        FastmailReadClient(TOKEN, max_raw_bytes=limit)


@pytest.mark.parametrize(
    "limit,size,accepted",
    [
        (MAX_RAW_BYTES, MAX_RAW_BYTES, True),
        (MAX_RAW_BYTES, MAX_RAW_BYTES + 1, False),
        (2 * MAX_RAW_BYTES, MAX_RAW_BYTES + 1, True),
        (2 * MAX_RAW_BYTES, 2 * MAX_RAW_BYTES, True),
        (2 * MAX_RAW_BYTES, 2 * MAX_RAW_BYTES + 1, False),
        (MAX_BLOB_BYTES, MAX_BLOB_BYTES, True),
        (MAX_BLOB_BYTES, MAX_BLOB_BYTES + 1, False),
    ],
)
def test_configured_blob_download_budget(limit, size, accepted):
    raw = b"x" * size

    def handler(request):
        if request.url.path.endswith("session"):
            return httpx.Response(200, json=session())
        return httpx.Response(200, content=raw)

    client = FastmailReadClient(TOKEN, max_raw_bytes=limit, transport=httpx.MockTransport(handler))
    try:
        client.discover()
        if accepted:
            assert client.download_blob("blob") == raw
        else:
            with pytest.raises(ProtocolError, match="byte limit"):
                client.download_blob("blob")
    finally:
        client.close()


@pytest.mark.parametrize("control", ["session", "metadata"])
def test_larger_blob_budget_does_not_expand_control_responses(control):
    def handler(request):
        if control == "metadata" and request.url.path.endswith("session"):
            return httpx.Response(200, json=session())
        return httpx.Response(200, content=b" " * (MAX_RAW_BYTES + 1))

    client = FastmailReadClient(
        TOKEN, max_raw_bytes=MAX_BLOB_BYTES, transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(ProtocolError, match="byte limit"):
            client.discover()
            client.metadata(["message"])
    finally:
        client.close()


def test_default_blob_download_stays_small():
    def handler(request):
        if request.url.path.endswith("session"):
            return httpx.Response(200, json=session())
        return httpx.Response(200, content=b"x" * (MAX_RAW_BYTES + 1))

    client = FastmailReadClient(TOKEN, transport=httpx.MockTransport(handler))
    try:
        client.discover()
        with pytest.raises(ProtocolError, match="byte limit"):
            client.download_blob("blob")
    finally:
        client.close()


@pytest.mark.parametrize(
    "value,expected",
    [
        ("120", 120),
        ("0", 0),
        ("99999", 3600),
        ("999999999", None),
        ("", None),
        ("²", None),  # Unicode digits are not delay-seconds.
        ("٣٠", None),
        ("Wed, 21 Oct 2026 07:28:00 GMT", None),
        ("12 ", None),
    ],
)
def test_retry_after_only_accepts_ascii_delay_seconds(value, expected):
    assert retry_after_seconds(value) == expected


def test_unicode_retry_after_throttles_instead_of_failing():
    client = FastmailReadClient(
        TOKEN,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(429, headers=[(b"Retry-After", "²".encode())])
        ),
    )
    try:
        with pytest.raises(ProviderThrottled) as raised:
            client.discover()
        assert raised.value.retry_after_seconds is None
    finally:
        client.close()


def test_oversized_blob_is_distinct_from_control_response_overflow():
    def handler(request):
        if request.url.path.endswith("session"):
            return httpx.Response(200, json=session())
        return httpx.Response(200, content=b"x" * (MAX_RAW_BYTES + 1))

    client = FastmailReadClient(TOKEN, transport=httpx.MockTransport(handler))
    try:
        client.discover()
        with pytest.raises(BlobTooLarge):
            client.download_blob("blob")
        assert issubclass(BlobTooLarge, ProtocolError)
    finally:
        client.close()
    oversized = FastmailReadClient(
        TOKEN,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b" " * (MAX_RAW_BYTES + 1))
        ),
    )
    try:
        with pytest.raises(ProtocolError) as raised:
            oversized.discover()
        assert not isinstance(raised.value, BlobTooLarge)
    finally:
        oversized.close()


def test_metadata_requests_the_message_size():
    seen = []

    def handler(request):
        if request.url.path.endswith("session"):
            return httpx.Response(200, json=session())
        seen.append(json.loads(request.content)["methodCalls"][0])
        return httpx.Response(
            200,
            json={
                "methodResponses": [
                    [
                        "Email/get",
                        {"accountId": "a", "list": [], "state": "s", "notFound": ["m"]},
                        "r0",
                    ]
                ]
            },
        )

    client = FastmailReadClient(TOKEN, transport=httpx.MockTransport(handler))
    try:
        client.discover()
        client.metadata(["m"])
        assert "size" in seen[0][1]["properties"]
    finally:
        client.close()
