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
        self.account_id = account_id
        self.transport = transport

    def _call(self, method: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if method not in {"Email/get", "Email/changes", "Email/query"}:
            raise ProtocolError("write or unknown method denied")
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
        state = result.get("state")
        if not isinstance(state, str) or not state:
            raise ProtocolError("missing Email state")
        return state

    def changes(self, since: str) -> ChangeIds:
        data = self._call("Email/changes", {"sinceState": since, "maxChanges": 100})
        if data.get("oldState") != since or not isinstance(data.get("hasMoreChanges"), bool):
            raise ProtocolError("invalid change state")
        state = data.get("newState")
        if not isinstance(state, str) or not state:
            raise ProtocolError("missing next state")
        groups: list[tuple[str, ...]] = []
        for field in ("created", "updated", "destroyed"):
            ids = data.get(field)
            if not isinstance(ids, list) or len(ids) > 100:
                raise ProtocolError("invalid id list")
            if any(not isinstance(value, str) or not 0 < len(value) <= 1000 for value in ids):
                raise ProtocolError("invalid provider id")
            if len(ids) != len(set(ids)):
                raise ProtocolError("duplicate ids")
            groups.append(tuple(ids))
        if sum(map(len, groups)) > 100:
            raise ProtocolError("provider exceeded maxChanges")
        if any(set(groups[a]) & set(groups[b]) for a, b in ((0, 1), (0, 2), (1, 2))):
            raise ProtocolError("contradictory change lists")
        return ChangeIds(groups[0], groups[1], groups[2], state, data["hasMoreChanges"])

    def bootstrap_page(self, position: int = 0) -> tuple[tuple[str, ...], bool]:
        if position < 0:
            raise ValueError("invalid position")
        data = self._call(
            "Email/query", {"position": position, "limit": 100, "calculateTotal": True}
        )
        ids = data.get("ids")
        total = data.get("total")
        if (
            not isinstance(ids, list)
            or len(ids) > 100
            or any(not isinstance(value, str) or not value for value in ids)
            or data.get("position") != position
            or not isinstance(total, int)
        ):
            raise ProtocolError("invalid bootstrap page")
        if not ids and position < total:
            raise ProtocolError("bootstrap made no progress")
        return tuple(ids), position + len(ids) < total
