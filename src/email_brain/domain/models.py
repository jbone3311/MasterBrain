"""Dependency-light domain contracts.

These types intentionally contain no provider SDK or model SDK imports.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class Provider(StrEnum):
    FASTMAIL = "fastmail"
    GMAIL = "gmail"
    MICROSOFT = "microsoft"
    ICLOUD = "icloud"


class ProviderEventKind(StrEnum):
    UPSERT_MESSAGE = "upsert_message"
    DELETE_MESSAGE = "delete_message"
    UPDATE_MAILBOX = "update_mailbox"
    UPDATE_FLAGS = "update_flags"


class ActionKind(StrEnum):
    APPLY_LABEL = "apply_label"
    MOVE = "move"
    ARCHIVE = "archive"
    FLAG = "flag"
    CREATE_DRAFT = "create_draft"
    SEND = "send"
    DELETE_PERMANENTLY = "delete_permanently"


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: UUID
    actor_id: UUID
    scopes: frozenset[str]
    request_id: UUID


@dataclass(frozen=True, slots=True)
class ProviderEvent:
    tenant_id: UUID
    account_id: UUID
    event_key: str
    kind: ProviderEventKind
    provider_object_id: str
    provider_version: str | None
    observed_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChangePage:
    events: tuple[ProviderEvent, ...]
    next_cursor: str
    has_more: bool


@dataclass(frozen=True, slots=True)
class ActionCommand:
    tenant_id: UUID
    account_id: UUID
    kind: ActionKind
    target_ids: tuple[str, ...]
    parameters: Mapping[str, Any]
    idempotency_key: UUID
    expected_versions: Mapping[str, str] = field(default_factory=dict)

    @property
    def intrinsically_high_risk(self) -> bool:
        return self.kind in {ActionKind.SEND, ActionKind.DELETE_PERMANENTLY}
