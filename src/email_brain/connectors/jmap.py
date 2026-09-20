"""Read-only JMAP protocol slice. Transport/credential enrollment is deliberately separate.

Notifications are hints. Returned state becomes a checkpoint only after ingestion commits.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class ResyncRequired(Exception):
    pass


class ProtocolError(Exception):
    pass


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
        if name != method or payload.get("accountId") != self.account_id:
            raise ProtocolError("method/account mismatch or provider error")
        return payload

    def baseline_state(self) -> str:
        # Capture BEFORE a paginated full listing; later replay changes since this
        # Email state. Email/query.queryState is not an Email/changes state.
        result = self._call("Email/get", {"ids": [], "properties": ["id"]})
        return identifier(result.get("state"))

    def changes(self, since: str) -> ChangeIds:
        data = self._call("Email/changes", {"sinceState": identifier(since), "maxChanges": 100})
        if data.get("oldState") != since or not isinstance(data.get("hasMoreChanges"), bool):
            raise ProtocolError("invalid change state")
        state = identifier(data.get("newState"))
        groups = [id_list(data.get(field)) for field in ("created", "updated", "destroyed")]
        if sum(map(len, groups)) > 100:
            raise ProtocolError("provider exceeded maxChanges")
        if any(set(groups[a]) & set(groups[b]) for a, b in ((0, 1), (0, 2), (1, 2))):
            raise ProtocolError("contradictory change lists")
        if state == since and (any(groups) or data["hasMoreChanges"]):
            raise ProtocolError("changes made no state progress")
        return ChangeIds(groups[0], groups[1], groups[2], state, data["hasMoreChanges"])

    def bootstrap_page(self, position: int = 0) -> tuple[tuple[str, ...], bool]:
        page = self.query_page(position)
        return page.ids, page.has_more

    def query_page(self, position: int = 0) -> QueryPage:
        if type(position) is not int or not 0 <= position <= 2**31 - 1:
            raise ValueError("invalid position")
        data = self._call(
            "Email/query", {"position": position, "limit": 100, "calculateTotal": True}
        )
        ids = id_list(data.get("ids"))
        total = data.get("total")
        if (
            type(data.get("position")) is not int
            or data["position"] != position
            or type(total) is not int
            or not 0 <= total <= 2**31 - 1
            or (ids and position + len(ids) > total)
        ):
            raise ProtocolError("invalid bootstrap page")
        if not ids and position < total:
            raise ProtocolError("bootstrap made no progress")
        return QueryPage(ids, identifier(data.get("queryState")), position, total)
