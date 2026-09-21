"""Read-only Graph library; no enrollment, subscriptions, worker or mailbox writes."""

from __future__ import annotations

import hmac
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import quote, urlsplit
from uuid import UUID

import httpx

from email_brain.connectors.fastmail import (
    ProviderAuthRequired,
    ProviderThrottled,
    ProviderUnavailable,
)
from email_brain.connectors.jmap import ProtocolError, ResyncRequired
from email_brain.normalize import MAX_RAW_BYTES

ORIGIN = "https://graph.microsoft.com"
MAX_PAGE_ITEMS = 100


class GraphResourceMissing(Exception):
    """A missing resource is not evidence of global message deletion."""


def _identifier(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 1024
        or any(ord(char) < 33 or ord(char) > 126 for char in value)
        or value in {".", ".."}
    ):
        raise ProtocolError("invalid Graph identifier")
    return value


def _url(value: Any, path: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 16384:
        raise ProtocolError("invalid Graph URL")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise ProtocolError("invalid Graph URL") from None
    if (
        parts.scheme != "https"
        or parts.netloc != "graph.microsoft.com"
        or port is not None
        or parts.path != path
        or parts.fragment
        or "\\" in value
        or any(ord(char) < 33 or ord(char) > 126 for char in value)
    ):
        raise ProtocolError("Graph URL outside bound endpoint")
    return value


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_RAW_BYTES:
        raise ProtocolError("Graph payload exceeds byte limit")
    try:
        data = json.loads(raw, object_pairs_hook=_object)
    except (ValueError, UnicodeError, RecursionError):
        raise ProtocolError("invalid Graph JSON") from None
    if not isinstance(data, dict):
        raise ProtocolError("Graph payload must be an object")
    return data


@dataclass(frozen=True)
class FolderChange:
    message_id: str
    folder_id: str
    kind: Literal["changed", "membership_removed"]
    # Delta order is not an authoritative last-write order. Fetch current evidence.
    requires_fetch: bool


@dataclass(frozen=True)
class DeltaPage:
    changes: tuple[FolderChange, ...]
    continuation: str = field(repr=False)
    complete: bool


class GraphReadClient:
    """Explicit account binding; opaque links cannot change account or folder."""

    def __init__(
        self, user_id: str, token: str, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._account_path = "/v1.0/users/" + quote(_identifier(user_id), safe="")
        if not 16 <= len(token) <= 4096 or any(ord(char) < 33 or ord(char) > 126 for char in token):
            raise ValueError("invalid provider token")
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Prefer": 'IdType="ImmutableId", odata.maxpagesize=100',
                "Accept-Encoding": "identity",
            },
            timeout=httpx.Timeout(20, connect=5),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _get(self, url: str, path: str) -> bytes:
        safe = _url(url, path)
        started = time.monotonic()
        try:
            with self._client.stream("GET", safe) as response:
                if response.status_code in {401, 403}:
                    raise ProviderAuthRequired("provider authorization required")
                if response.status_code == 404:
                    raise GraphResourceMissing("Graph resource unavailable")
                if response.status_code == 410:
                    raise ResyncRequired("Graph state expired; full folder resync required")
                if response.status_code == 429:
                    retry = response.headers.get("Retry-After", "")
                    delay = (
                        min(int(retry), 3600)
                        if retry.isascii() and retry.isdigit() and len(retry) <= 8
                        else None
                    )
                    raise ProviderThrottled(delay)
                if response.status_code != 200:
                    raise ProviderUnavailable("provider returned non-success status")
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise ProtocolError("compressed Graph responses are not supported")
                body = bytearray()
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_RAW_BYTES:
                        raise ProtocolError("Graph response exceeds byte limit")
                    if time.monotonic() - started > 30:
                        raise ProviderUnavailable("provider response deadline exceeded")
                    body.extend(chunk)
                if time.monotonic() - started > 30:
                    raise ProviderUnavailable("provider response deadline exceeded")
                return bytes(body)
        except httpx.HTTPError:
            raise ProviderUnavailable("provider network failure") from None

    def delta(self, folder_id: str, cursor: str | None = None) -> DeltaPage:
        folder_id = _identifier(folder_id)
        path = self._account_path + "/mailFolders/" + quote(folder_id, safe="") + "/messages/delta"
        # No property filter: changes to an unselected property must not be lost.
        url = cursor if cursor is not None else ORIGIN + path
        data = _json(self._get(url, path))
        values = data.get("value")
        if not isinstance(values, list) or len(values) > MAX_PAGE_ITEMS:
            raise ProtocolError("invalid Graph delta item list")
        next_link, delta_link = data.get("@odata.nextLink"), data.get("@odata.deltaLink")
        if (next_link is None) == (delta_link is None):
            raise ProtocolError("exactly one Graph continuation required")
        continuation = _url(next_link if next_link is not None else delta_link, path)
        if not urlsplit(continuation).query:
            raise ProtocolError("Graph continuation requires an opaque query")
        if next_link is not None and continuation == url:
            raise ProtocolError("Graph pagination made no progress")
        changes: list[FolderChange] = []
        for item in values:
            if not isinstance(item, dict):
                raise ProtocolError("invalid Graph delta item")
            message_id = _identifier(item.get("id"))
            if "@removed" in item:
                removed = item["@removed"]
                if not isinstance(removed, dict) or removed.get("reason") != "deleted":
                    raise ProtocolError("unsupported Graph removal")
                changes.append(FolderChange(message_id, folder_id, "membership_removed", True))
            else:
                changes.append(FolderChange(message_id, folder_id, "changed", True))
        return DeltaPage(tuple(changes), continuation, delta_link is not None)

    def download_mime(self, message_id: str) -> bytes:
        path = (
            self._account_path + "/messages/" + quote(_identifier(message_id), safe="") + "/$value"
        )
        return self._get(ORIGIN + path, path)


@dataclass(frozen=True)
class SubscriptionBinding:
    """Trusted server configuration, never constructed from a webhook payload."""

    account_id: UUID
    folder_id: str
    graph_tenant_id: str
    resource_prefix: str
    expires_at: datetime
    client_state: str = field(repr=False)

    def __post_init__(self) -> None:
        _identifier(self.folder_id)
        _identifier(self.graph_tenant_id)
        if (
            self.expires_at.tzinfo is None
            or not 16 <= len(self.client_state) <= 128
            or not self.client_state.isascii()
            or not self.resource_prefix
            or self.resource_prefix.endswith("/")
            or len(self.resource_prefix) > 2048
        ):
            raise ValueError("invalid subscription binding")


@dataclass(frozen=True)
class SyncHint:
    account_id: UUID
    folder_id: str


def notification_hints(
    raw: bytes, bindings: Mapping[str, SubscriptionBinding], *, now: datetime | None = None
) -> tuple[SyncHint, ...]:
    """Basic notifications only. Returns no provider URLs, content or mutation claims."""
    data = _json(raw)
    if "validationTokens" in data:
        raise ProtocolError("rich Graph notifications are unsupported")
    values = data.get("value")
    if not isinstance(values, list) or not 1 <= len(values) <= 100:
        raise ProtocolError("invalid notification batch")
    current = now if now is not None else datetime.now(UTC)
    if current.tzinfo is None:
        raise ValueError("timezone-aware clock required")
    hints: list[SyncHint] = []
    for item in values:
        if not isinstance(item, dict) or "encryptedContent" in item or "lifecycleEvent" in item:
            raise ProtocolError("unsupported Graph notification")
        subscription_id = _identifier(item.get("subscriptionId"))
        binding = bindings.get(subscription_id)
        state = item.get("clientState")
        resource = item.get("resource")
        if (
            binding is None
            or binding.expires_at <= current
            or not isinstance(state, str)
            or not state.isascii()
            or not hmac.compare_digest(state, binding.client_state)
            or item.get("tenantId") != binding.graph_tenant_id
            or not isinstance(item.get("changeType"), str)
            or item.get("changeType") not in {"created", "updated", "deleted"}
            or not isinstance(resource, str)
            or not resource.startswith(binding.resource_prefix + "/")
        ):
            raise ProtocolError("Graph notification validation failed")
        suffix = resource[len(binding.resource_prefix) + 1 :]
        _identifier(suffix)
        if "/" in suffix or "?" in suffix or "#" in suffix:
            raise ProtocolError("Graph notification resource mismatch")
        hint = SyncHint(binding.account_id, binding.folder_id)
        if hint not in hints:
            hints.append(hint)
    return tuple(hints)


def validation_response(decoded_token: str, *, registration_pending: bool) -> tuple[int, str, str]:
    """Framework must decode the query once; return plain text, never HTML or a grant."""
    if (
        not registration_pending
        or not isinstance(decoded_token, str)
        or not 1 <= len(decoded_token) <= 2048
        or any(ord(char) < 32 or ord(char) == 127 for char in decoded_token)
    ):
        raise ProtocolError("invalid Graph endpoint validation")
    return 200, "text/plain; charset=utf-8", decoded_token
