"""Bounded, read-only Fastmail JMAP transport. No SMTP, Email/set or submission path."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from email_brain.connectors.jmap import JmapReader, ProtocolError, id_list, identifier
from email_brain.normalize import MAX_RAW_BYTES

MAIL = "urn:ietf:params:jmap:mail"
SESSION = "https://api.fastmail.com/jmap/session"
# Explicit opt-in for encrypted object-backed ingestion; control JSON stays bounded.
MAX_BLOB_BYTES = 16 * 1024 * 1024


class ProviderUnavailable(Exception):
    pass


class ProviderAuthRequired(Exception):
    pass


class ProviderThrottled(Exception):
    def __init__(self, retry_after_seconds: int | None) -> None:
        super().__init__("provider throttled")
        self.retry_after_seconds = retry_after_seconds


class BlobTooLarge(ProtocolError):
    """A message blob exceeds the configured download budget; hold it, do not pause."""


def retry_after_seconds(value: str) -> int | None:
    """Delay-seconds only; HTTP-date forms and non-ASCII digits are ignored, never errors."""
    if not 1 <= len(value) <= 8 or not value.isascii() or not value.isdigit():
        return None
    return min(int(value), 3600)


def _safe_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise ProtocolError("invalid provider URL") from None
    if (
        parts.scheme != "https"
        or parts.hostname != "api.fastmail.com"
        or port not in {None, 443}
        or parts.username
        or parts.password
        or parts.fragment
        or not parts.path.startswith("/jmap/")
        or any(ord(char) < 33 or ord(char) > 126 for char in url)
        or "\\" in url
    ):
        raise ProtocolError("provider URL is outside the Fastmail boundary")
    return url


class FastmailReadClient:
    def __init__(
        self,
        token: str,
        *,
        transport: httpx.BaseTransport | None = None,
        max_raw_bytes: int = MAX_RAW_BYTES,
    ) -> None:
        if not 16 <= len(token) <= 4096 or "\n" in token or "\r" in token:
            raise ValueError("invalid provider token")
        if type(max_raw_bytes) is not int or not MAX_RAW_BYTES <= max_raw_bytes <= MAX_BLOB_BYTES:
            raise ValueError("raw byte limit must be an integer between 1 and 16 MiB")
        self._max_raw_bytes = max_raw_bytes
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {token}", "Accept-Encoding": "identity"},
            timeout=httpx.Timeout(20, connect=5),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )
        self.account_id: str | None = None
        self._api_url: str | None = None
        self._download_template: str | None = None

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        *,
        byte_limit: int = MAX_RAW_BYTES,
        too_large: type[ProtocolError] = ProtocolError,
    ) -> bytes:
        safe = _safe_url(url)
        started = time.monotonic()
        try:
            with self._client.stream(method, safe, json=payload) as response:
                if response.status_code in {401, 403}:
                    raise ProviderAuthRequired("provider authorization required")
                if response.status_code == 429:
                    raise ProviderThrottled(
                        retry_after_seconds(response.headers.get("Retry-After", ""))
                    )
                if response.status_code != 200:
                    raise ProviderUnavailable("provider returned non-success status")
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise ProtocolError("compressed provider responses are not supported")
                body = bytearray()
                count = 0
                for chunk in response.iter_bytes():
                    if time.monotonic() - started > 30:
                        raise ProviderUnavailable("provider response deadline exceeded")
                    count += len(chunk)
                    if count > byte_limit:
                        raise too_large("provider response exceeds prototype byte limit")
                    body.extend(chunk)
                if time.monotonic() - started > 30:
                    raise ProviderUnavailable("provider response deadline exceeded")
                return bytes(body)
        except httpx.HTTPError:
            # HTTP exceptions can carry sensitive URLs/request headers.
            raise ProviderUnavailable("provider network failure") from None

    def _json(self, raw: bytes) -> dict[str, Any]:
        try:
            parsed = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            raise ProtocolError("invalid provider JSON") from None
        if not isinstance(parsed, dict):
            raise ProtocolError("provider JSON is not an object")
        return parsed

    def discover(self) -> str:
        # A failed refresh must not leave a previously discovered identity usable.
        self.account_id = self._api_url = self._download_template = None
        data = self._json(self._request("GET", SESSION))
        primary = data.get("primaryAccounts", {})
        accounts = data.get("accounts", {})
        if not isinstance(primary, dict) or not isinstance(accounts, dict):
            raise ProtocolError("invalid account inventory")
        account_id = primary.get(MAIL)
        account = accounts.get(account_id, {}) if isinstance(account_id, str) else {}
        if (
            not isinstance(account_id, str)
            or not account_id
            or not isinstance(account, dict)
            or not isinstance(account.get("accountCapabilities"), dict)
            or MAIL not in account["accountCapabilities"]
        ):
            raise ProtocolError("no primary mail account")
        api_url = data.get("apiUrl")
        download = data.get("downloadUrl")
        if not isinstance(api_url, str) or not isinstance(download, str):
            raise ProtocolError("missing endpoint URLs")
        _safe_url(api_url)
        _safe_url(download)
        self.account_id = identifier(account_id)
        self._api_url = api_url
        self._download_template = download
        return account_id

    def _call(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._api_url is None or self.account_id is None:
            raise ProtocolError("discover session first")
        calls = payload.get("methodCalls")
        if not isinstance(calls, list) or len(calls) != 1:
            raise ProtocolError("one read method per request required")
        call = calls[0]
        if (
            not isinstance(call, list)
            or len(call) != 3
            or call[0] not in {"Email/get", "Email/query", "Email/changes"}
            or not isinstance(call[1], dict)
            or call[1].get("accountId") != self.account_id
        ):
            raise ProtocolError("method/account denied")
        return self._json(self._request("POST", self._api_url, payload))

    def reader(self) -> JmapReader:
        if self.account_id is None:
            raise ProtocolError("discover session first")
        return JmapReader(self.account_id, self._call)

    def metadata(self, ids: list[str]) -> dict[str, Any]:
        if not id_list(ids):
            raise ValueError("1..100 bounded provider IDs required")
        # Keep notFound in the result: callers must reconcile, not silently drop it.
        return self.reader()._call(
            "Email/get",
            {
                "ids": ids,
                "properties": [
                    "id",
                    "blobId",
                    "threadId",
                    "receivedAt",
                    "size",
                    "mailboxIds",
                    "keywords",
                ],
            },
        )

    def download_blob(self, blob_id: str) -> bytes:
        if not self._download_template or not self.account_id:
            raise ProtocolError("discover session first")
        identifier(blob_id)
        url = self._download_template
        for key, value in {
            "accountId": self.account_id,
            "blobId": blob_id,
            "name": "source.eml",
            "type": "message/rfc822",
        }.items():
            url = url.replace("{" + key + "}", quote(value, safe=""))
        if "{" in url or "}" in url:
            raise ProtocolError("unsupported download template")
        return self._request("GET", url, byte_limit=self._max_raw_bytes, too_large=BlobTooLarge)
