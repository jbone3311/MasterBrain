"""Gmail GET-only library. No OAuth enrollment, worker, webhook, or mailbox effects."""

from __future__ import annotations

import base64
import binascii
import json
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Literal, overload

import httpx

from email_brain.normalize import MAX_RAW_BYTES

BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
MAX_JSON_BYTES = 2 * 1024 * 1024
PAGE_SIZE = 100


class GmailProtocolError(Exception):
    pass


class GmailUnavailable(Exception):
    pass


class GmailAuthRequired(Exception):
    pass


class GmailHistoryExpired(Exception):
    """Requires full reconciliation; never checkpoint a notification instead."""


class GmailMessageGone(Exception):
    """Only the requested message was not found; this is not history expiry."""


class GmailThrottled(Exception):
    def __init__(self, retry_after_seconds: int | None) -> None:
        super().__init__("provider throttled")
        self.retry_after_seconds = retry_after_seconds


def _text(value: object, limit: int = 128) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= limit:
        raise GmailProtocolError("invalid bounded provider text")
    if any(ord(char) < 33 or ord(char) > 126 for char in value):
        raise GmailProtocolError("invalid bounded provider text")
    return value


def _id(value: object) -> str:
    result = _text(value)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", result):
        raise GmailProtocolError("invalid provider identifier")
    return result


def _history_id(value: object) -> str:
    result = _text(value, 32)
    if not re.fullmatch(r"[0-9]+", result):
        raise GmailProtocolError("invalid history identifier")
    return result


def _date(value: object) -> int:
    date = int(_history_id(value))
    if date > 253402300799999:
        raise GmailProtocolError("invalid message timestamp")
    return date


def _address(value: object) -> str:
    result = _text(value, 320)
    if result.count("@") != 1 or not all(result.split("@")):
        raise GmailProtocolError("invalid account binding")
    return result.casefold()


def _object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GmailProtocolError("provider JSON is not an object")
    return value


def _json(raw: bytes) -> dict[str, Any]:
    try:
        return _object(
            json.loads(
                raw,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
                parse_float=_finite_float,
            )
        )
    except (ValueError, UnicodeError, RecursionError):
        raise GmailProtocolError("invalid provider JSON") from None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("nonfinite JSON constant")


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite JSON number")
    return result


def _response_json(response: httpx.Response, started: float) -> dict[str, Any]:
    if response.headers.get("Content-Encoding", "identity").lower() != "identity":
        raise GmailProtocolError("compressed responses are not supported")
    body = bytearray()
    count = 0
    for chunk in response.iter_bytes():
        if time.monotonic() - started > 30:
            raise GmailUnavailable("provider response deadline exceeded")
        count += len(chunk)
        if count > MAX_JSON_BYTES:
            raise GmailProtocolError("provider response exceeds prototype byte limit")
        body.extend(chunk)
    if time.monotonic() - started > 30:
        raise GmailUnavailable("provider response deadline exceeded")
    return _json(bytes(body))


def _retry_after(response: httpx.Response) -> int | None:
    retry = response.headers.get("Retry-After", "")
    if retry.isascii() and retry.isdigit() and len(retry) <= 8:
        return min(int(retry), 3600)
    return None


def _quota_only(data: dict[str, Any]) -> bool:
    error = data.get("error")
    if not isinstance(error, dict):
        return False
    reasons = error.get("errors")
    if not isinstance(reasons, list) or not 1 <= len(reasons) <= 100:
        return False
    return all(
        isinstance(reason, dict)
        and reason.get("reason") in ("rateLimitExceeded", "userRateLimitExceeded")
        for reason in reasons
    )


def _array(value: object, maximum: int = PAGE_SIZE) -> list[Any]:
    if not isinstance(value, list) or len(value) > maximum:
        raise GmailProtocolError("invalid bounded provider list")
    return value


def _labels(value: object) -> tuple[str, ...]:
    result = tuple(_id(item) for item in _array(value))
    if len(set(result)) != len(result):
        raise GmailProtocolError("duplicate labels")
    return result


def _next_token(data: dict[str, Any], previous: str | None) -> str | None:
    if "nextPageToken" not in data:
        return None
    token = _text(data["nextPageToken"], 2048)
    if token == previous:
        raise GmailProtocolError("pagination made no progress")
    return token


def _decode(raw: object, maximum: int) -> bytes:
    if not isinstance(raw, str) or len(raw) > ((maximum + 2) // 3) * 4:
        raise GmailProtocolError("invalid bounded base64url data")
    if not re.fullmatch(r"[A-Za-z0-9_-]*={0,2}", raw):
        raise GmailProtocolError("invalid base64url data")
    try:
        result = base64.b64decode(raw + "=" * (-len(raw) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error):
        raise GmailProtocolError("invalid base64url data") from None
    if len(result) > maximum:
        raise GmailProtocolError("decoded data exceeds prototype byte limit")
    return result


@dataclass(frozen=True)
class GmailProfile:
    email_address: str
    history_id: str


@dataclass(frozen=True)
class GmailMessageRef:
    id: str
    thread_id: str


def _ref(value: object) -> GmailMessageRef:
    data = _object(value)
    return GmailMessageRef(_id(data.get("id")), _id(data.get("threadId")))


@dataclass(frozen=True)
class GmailListing:
    messages: tuple[GmailMessageRef, ...]
    next_page_token: str | None
    # resultSizeEstimate is intentionally not an inventory certificate.


@dataclass(frozen=True)
class GmailChange:
    history_id: str
    kind: Literal["added", "deleted", "labels_added", "labels_removed", "refresh"]
    message: GmailMessageRef
    label_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class GmailHistoryPage:
    changes: tuple[GmailChange, ...]
    next_page_token: str | None
    history_id: str

    @property
    def candidate_checkpoint(self) -> str | None:
        """Candidate only: caller must durably process every page before committing."""
        return self.history_id if self.next_page_token is None else None


@dataclass(frozen=True)
class GmailMessage:
    id: str
    thread_id: str
    history_id: str
    label_ids: tuple[str, ...]
    internal_date_ms: int
    raw: bytes


@dataclass(frozen=True)
class GmailMinimalMessage:
    """Label refresh only; missing evidence metadata is not invented."""

    id: str
    thread_id: str | None
    history_id: str | None
    label_ids: tuple[str, ...]
    internal_date_ms: int | None
    raw: None = None


@dataclass(frozen=True)
class UntrustedGmailHint:
    email_address: str
    history_id: str


def decode_untrusted_hint(
    envelope: object, *, expected_email: str, expected_subscription: str
) -> UntrustedGmailHint:
    """Structural checks only. This is NOT JWT authentication or enqueue authorization."""
    data = _object(envelope)
    if data.get("subscription") != _text(expected_subscription, 512):
        raise GmailProtocolError("notification subscription mismatch")
    message = _object(data.get("message"))
    _text(message.get("messageId"), 128)
    content = _json(_decode(message.get("data"), 4096))
    address = _address(content.get("emailAddress"))
    if address != _address(expected_email):
        raise GmailProtocolError("notification account mismatch")
    return UntrustedGmailHint(address, _history_id(content.get("historyId")))


class GmailReadClient:
    def __init__(
        self, token: str, expected_email: str, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        if not isinstance(token, str) or not 16 <= len(token) <= 4096:
            raise ValueError("invalid provider token")
        if any(ord(char) < 33 or ord(char) > 126 for char in token):
            raise ValueError("invalid provider token")
        self._expected_email = _address(expected_email)
        self._verified = False
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {token}", "Accept-Encoding": "identity"},
            timeout=httpx.Timeout(20, connect=5),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def close(self) -> None:
        self._verified = False
        self._client.close()

    def _get(self, resource: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        # Validate even internal routing: credentials cannot accompany arbitrary URLs.
        if resource not in {"profile", "messages", "history"} and not re.fullmatch(
            r"messages/[A-Za-z0-9_-]{1,128}", resource
        ):
            raise GmailProtocolError("provider route denied")
        if resource != "profile" and not self._verified:
            raise GmailProtocolError("verify account profile first")
        started = time.monotonic()
        try:
            with self._client.stream("GET", f"{BASE}/{resource}", params=params) as response:
                if response.status_code == 401:
                    self._verified = False
                    raise GmailAuthRequired("provider authorization required")
                if response.status_code == 403:
                    was_verified = self._verified
                    self._verified = False
                    try:
                        data = _response_json(response, started)
                    except GmailProtocolError:
                        raise GmailAuthRequired("provider authorization required") from None
                    if _quota_only(data):
                        self._verified = was_verified
                        raise GmailThrottled(_retry_after(response))
                    raise GmailAuthRequired("provider authorization required")
                if response.status_code == 429:
                    raise GmailThrottled(_retry_after(response))
                if response.status_code == 404 and resource == "history":
                    raise GmailHistoryExpired("full resync required")
                if response.status_code == 404 and resource.startswith("messages/"):
                    raise GmailMessageGone("message not found")
                if response.status_code != 200:
                    raise GmailUnavailable("provider returned non-success status")
                return _response_json(response, started)
        except httpx.HTTPError:
            raise GmailUnavailable("provider network failure") from None

    def discover(self) -> GmailProfile:
        self._verified = False
        data = self._get("profile")
        address = _address(data.get("emailAddress"))
        history_id = _history_id(data.get("historyId"))
        if address != self._expected_email:
            raise GmailProtocolError("provider account binding mismatch")
        self._verified = True
        return GmailProfile(address, history_id)

    def list_messages(self, page_token: str | None = None) -> GmailListing:
        params = {"maxResults": str(PAGE_SIZE), "includeSpamTrash": "true"}
        if page_token is not None:
            params["pageToken"] = _text(page_token, 2048)
        data = self._get("messages", params)
        messages = tuple(_ref(item) for item in _array(data.get("messages", [])))
        if len({message.id for message in messages}) != len(messages):
            raise GmailProtocolError("duplicate listed message")
        return GmailListing(messages, _next_token(data, page_token))

    def history(self, start_history_id: str, page_token: str | None = None) -> GmailHistoryPage:
        start = _history_id(start_history_id)
        params = {"startHistoryId": start, "maxResults": str(PAGE_SIZE)}
        if page_token is not None:
            params["pageToken"] = _text(page_token, 2048)
        data = self._get("history", params)
        current = _history_id(data.get("historyId"))
        if int(current) < int(start):
            raise GmailProtocolError("history moved backwards")
        changes: list[GmailChange] = []
        previous = int(start)
        kinds: tuple[
            tuple[str, Literal["added", "deleted", "labels_added", "labels_removed"]], ...
        ] = (
            ("messagesAdded", "added"),
            ("messagesDeleted", "deleted"),
            ("labelsAdded", "labels_added"),
            ("labelsRemoved", "labels_removed"),
        )
        for value in _array(data.get("history", [])):
            record = _object(value)
            record_id = _history_id(record.get("id"))
            if not previous < int(record_id) <= int(current):
                raise GmailProtocolError("invalid history ordering")
            previous = int(record_id)
            covered: set[str] = set()
            for field, kind in kinds:
                for item in _array(record.get(field, []), 1000):
                    entry = _object(item)
                    message = _ref(entry.get("message"))
                    labels = _labels(entry.get("labelIds")) if field.startswith("labels") else ()
                    changes.append(GmailChange(record_id, kind, message, labels))
                    covered.add(message.id)
            for item in _array(record.get("messages", []), 1000):
                message = _ref(item)
                if message.id not in covered:
                    changes.append(GmailChange(record_id, "refresh", message))
                    covered.add(message.id)
            if len(changes) > 1000:
                raise GmailProtocolError("history change budget exceeded")
        return GmailHistoryPage(tuple(changes), _next_token(data, page_token), current)

    @overload
    def message(self, message_id: str, *, include_raw: Literal[True] = True) -> GmailMessage: ...

    @overload
    def message(self, message_id: str, *, include_raw: Literal[False]) -> GmailMinimalMessage: ...

    @overload
    def message(
        self, message_id: str, *, include_raw: bool
    ) -> GmailMessage | GmailMinimalMessage: ...

    def message(
        self, message_id: str, *, include_raw: bool = True
    ) -> GmailMessage | GmailMinimalMessage:
        expected = _id(message_id)
        data = self._get(f"messages/{expected}", {"format": "raw" if include_raw else "minimal"})
        received = _id(data.get("id"))
        if received != expected:
            raise GmailProtocolError("provider message binding mismatch")
        labels = _labels(data.get("labelIds", []))
        if not include_raw:
            return GmailMinimalMessage(
                received,
                _id(data["threadId"]) if "threadId" in data else None,
                _history_id(data["historyId"]) if "historyId" in data else None,
                labels,
                _date(data["internalDate"]) if "internalDate" in data else None,
            )
        return GmailMessage(
            received,
            _id(data.get("threadId")),
            _history_id(data.get("historyId")),
            labels,
            _date(data.get("internalDate")),
            _decode(data.get("raw"), MAX_RAW_BYTES),
        )
