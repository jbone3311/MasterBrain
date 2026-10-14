"""Read-only JMAP protocol slice. Transport/credential enrollment is deliberately separate.

Notifications are hints. Returned state becomes a checkpoint only after ingestion commits.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

# Listing order is explicit so anchor paging is stable across servers. Ascending
# receipt time means mail arriving during a listing lands after the anchor.
LISTING_SORT: tuple[dict[str, Any], ...] = ({"property": "receivedAt", "isAscending": True},)


class ResyncRequired(Exception):
    pass


class AnchorNotFound(Exception):
    """The listing anchor no longer exists; restart the inventory generation."""


class ProtocolError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ScopedMailWindow:
    """One exact JMAP mailbox and bounded UTC receipt window for a future pilot.

    This does not scope Email/changes or authorize the existing ReadWorker. A
    caller must recheck Email/get metadata before downloading any source bytes.
    """

    mailbox_id: str
    after: datetime
    before: datetime

    def __post_init__(self) -> None:
        identifier(self.mailbox_id)
        if not self.mailbox_id.isprintable() or self.mailbox_id != self.mailbox_id.strip():
            raise ValueError("scoped mailbox ID is not printable and exact")
        for value in (self.after, self.before):
            if (
                type(value) is not datetime or value.tzinfo is None
                or value.utcoffset() != timedelta(0) or value.microsecond
            ):
                raise ValueError("scoped mail dates require whole-second UTC timestamps")
        if not self.after < self.before <= self.after + timedelta(days=31):
            raise ValueError("scoped mail window must be 1..31 days")

    def query_filter(self) -> dict[str, str]:
        return {
            "inMailbox": self.mailbox_id,
            "after": self.after.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "before": self.before.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        }

    def accepts_metadata(self, row: dict[str, Any]) -> bool:
        """Fail closed if Email/get does not confirm the provider's query scope."""
        if not isinstance(row, dict):
            raise ProtocolError("invalid scoped message metadata")
        mailboxes = row.get("mailboxIds")
        stamp = row.get("receivedAt")
        if (
            not isinstance(mailboxes, dict) or len(mailboxes) > 100
            or any(value is not True for value in mailboxes.values())
            or not isinstance(stamp, str) or len(stamp) > 40
        ):
            raise ProtocolError("invalid scoped message metadata")
        for key in mailboxes:
            identifier(key)
        try:
            received = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            raise ProtocolError("invalid scoped receive timestamp") from None
        if received.tzinfo is None or received.utcoffset() != timedelta(0):
            raise ProtocolError("scoped receive timestamp is not UTC")
        return (
            mailboxes.get(self.mailbox_id) is True
            and self.after <= received < self.before
        )


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not 0 < len(value) <= 512 or "\x00" in value:
        raise ProtocolError("invalid bounded provider identifier")
    return value


def id_list(value: Any, limit: int = 100) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > limit:
        raise ProtocolError("invalid provider identifier list")
    ids = tuple(identifier(item) for item in value)
    if len(set(ids)) != len(ids):
        raise ProtocolError("duplicate provider identifiers")
    return ids


@dataclass(frozen=True)
class QueryPage:
    ids: tuple[str, ...]
    query_state: str
    position: int
    total: int

    @property
    def has_more(self) -> bool:
        # Position and total come from one server snapshot, so together they say
        # whether anything followed this page at that instant. A server may return
        # fewer IDs than requested, so a short page alone never means the end.
        return self.position + len(self.ids) < self.total


@dataclass(frozen=True)
class ChangeIds:
    created: tuple[str, ...]
    updated: tuple[str, ...]
    destroyed: tuple[str, ...]
    next_state: str
    has_more: bool


class JmapReader:
    """Capability-neutral parser; injected transport must enforce TLS/host/time/byte limits."""

    def __init__(
        self, account_id: str, transport: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> None:
        self.account_id = identifier(account_id)
        self.transport = transport

    def _call(self, method: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if method not in {"Email/get", "Email/changes", "Email/query"}:
            raise ProtocolError("write or unknown method denied")
        if "accountId" in arguments:
            raise ProtocolError("account override denied")
        response = self.transport(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [[method, {"accountId": self.account_id, **arguments}, "r0"]],
            }
        )
        calls = response.get("methodResponses")
        if not isinstance(calls, list) or len(calls) != 1:
            raise ProtocolError("unexpected method responses")
        result = calls[0]
        if not isinstance(result, list) or len(result) != 3 or result[2] != "r0":
            raise ProtocolError("method call mismatch")
        name, payload, _ = result
        if not isinstance(payload, dict):
            raise ProtocolError("invalid payload")
        if name == "error" and payload.get("type") == "cannotCalculateChanges":
            raise ResyncRequired()
        if name == "error" and payload.get("type") == "anchorNotFound":
            raise AnchorNotFound()
        if name != method or payload.get("accountId") != self.account_id:
            raise ProtocolError("method/account mismatch or provider error")
        return payload

    def baseline_state(self) -> str:
        # Capture BEFORE a paginated full listing; later replay changes since this
        # Email state. Email/query.queryState is not an Email/changes state.
        result = self._call("Email/get", {"ids": [], "properties": ["id"]})
        return identifier(result.get("state"))

    def changes(self, since: str, limit: int = 100) -> ChangeIds:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("invalid batch limit")
        data = self._call("Email/changes", {"sinceState": identifier(since), "maxChanges": limit})
        if data.get("oldState") != since or not isinstance(data.get("hasMoreChanges"), bool):
            raise ProtocolError("invalid change state")
        state = identifier(data.get("newState"))
        groups = [id_list(data.get(field)) for field in ("created", "updated", "destroyed")]
        if sum(map(len, groups)) > limit:
            raise ProtocolError("provider exceeded maxChanges")
        if any(set(groups[a]) & set(groups[b]) for a, b in ((0, 1), (0, 2), (1, 2))):
            raise ProtocolError("contradictory change lists")
        if state == since and (any(groups) or data["hasMoreChanges"]):
            raise ProtocolError("changes made no state progress")
        return ChangeIds(groups[0], groups[1], groups[2], state, data["hasMoreChanges"])

    def query_page(
        self, anchor: str | None = None, limit: int = 100,
        *, scope: ScopedMailWindow | None = None,
    ) -> QueryPage:
        """List the page after ``anchor`` in explicit receipt order.

        Anchor paging keeps its place when mail is created or destroyed elsewhere in
        the mailbox, which positional paging cannot (RFC 8620 section 5.5). A missing
        anchor raises ``AnchorNotFound`` so the caller restarts the inventory.
        """
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("invalid batch limit")
        if scope is not None and not isinstance(scope, ScopedMailWindow):
            raise ValueError("invalid scoped mail window")
        arguments: dict[str, Any] = {
            "sort": [dict(entry) for entry in LISTING_SORT],
            "limit": limit,
            "calculateTotal": True,
        }
        if scope is not None:
            arguments["filter"] = scope.query_filter()
        if anchor is None:
            arguments["position"] = 0
        else:
            arguments["anchor"] = identifier(anchor)
            arguments["anchorOffset"] = 1
        data = self._call("Email/query", arguments)
        ids = id_list(data.get("ids"), limit)
        total = data.get("total")
        position = data.get("position")
        if (
            type(position) is not int
            or not 0 <= position <= 2**31 - 1
            or (anchor is None and position != 0)
            or type(total) is not int
            or not 0 <= total <= 2**31 - 1
            or (ids and position + len(ids) > total)
            or (anchor is not None and anchor in ids)
        ):
            raise ProtocolError("invalid listing page")
        if not ids and position < total:
            raise ProtocolError("listing made no progress")
        return QueryPage(ids, identifier(data.get("queryState")), position, total)
