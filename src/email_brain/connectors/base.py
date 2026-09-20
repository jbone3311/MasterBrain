"""Provider-neutral connector protocol.

Implementations must keep provider cursors opaque and must never advance a
checkpoint before every event it covers is durable.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from email_brain.domain.models import ActionCommand, ChangePage, Provider


class Connector(Protocol):
    provider: Provider

    def capabilities(self, account_id: UUID) -> frozenset[str]: ...

    def bootstrap(self, tenant_id: UUID, account_id: UUID) -> ChangePage: ...

    def changes(self, tenant_id: UUID, account_id: UUID, cursor: str) -> ChangePage: ...

    def fetch_raw(self, tenant_id: UUID, account_id: UUID, provider_object_id: str) -> bytes: ...

    def reconcile(
        self, tenant_id: UUID, account_id: UUID, watermark: str | None
    ) -> Mapping[str, str]: ...


class ActionConnector(Connector, Protocol):
    def preview(self, command: ActionCommand) -> Mapping[str, object]: ...

    def execute(self, command: ActionCommand) -> Mapping[str, object]: ...
