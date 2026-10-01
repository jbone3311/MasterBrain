"""Expiring, server-bound bootstrap credentials. Replace with OIDC before hosted use."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from email_brain.domain.models import TenantContext
from email_brain.schemas import ClosedModel

SCOPES = frozenset(
    {
        "email.search",
        "email.evidence.read",
        "email.proposal.create",
        "email.proposal.read",
        "email.review",
        "email.ingest",
        "email.process",
        "email.document.process",
        "brain.search",
        "brain.evidence.read",
        "brain.content.read",
        "brain.changes.read",
        "brain.source.ingest",
        "brain.document.publish",
        "brain.index.activate",
        "brain.fileos.transition.review",
        "brain.fileos.transition.verify",
        "brain.fileos.transition.prepare",
        "brain.fileos.transition.authorize",
        "brain.fileos.transition.complete",
        "brain.fileos.transition.publish",
        "brain.fileos.transition.index",
        "knowledge.search",
        "knowledge.read",
        "knowledge.changes.read",
        "knowledge.review",
    }
)


class Credential(ClosedModel):
    token_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    tenant_id: UUID
    actor_id: UUID
    scopes: set[str]
    expires_at: datetime
    client_kind: str = Field(pattern=r"^(human|assistant|worker)$")

    @field_validator("expires_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("expiry requires a timezone")
        return value

    @field_validator("scopes")
    @classmethod
    def known_scopes(cls, value: set[str]) -> set[str]:
        if not value or not value <= SCOPES:
            raise ValueError("unknown or empty scopes")
        return value


@dataclass(frozen=True)
class Principal:
    context: TenantContext
    client_kind: str


class AuthenticationUnavailable(Exception):
    """Authentication infrastructure failed; never include sensitive diagnostics."""


class Authenticator(Protocol):
    def authenticate(self, token: str) -> Principal | None: ...


class TokenRegistry:
    def __init__(self, credentials: list[Credential]) -> None:
        if not credentials or len(credentials) > 100:
            raise ValueError("1..100 credentials required")
        if len({c.token_sha256 for c in credentials}) != len(credentials):
            raise ValueError("duplicate credential digest")
        if any(
            c.client_kind != "human"
            and {
                "email.review",
                "knowledge.review",
                "brain.fileos.transition.review",
                "brain.fileos.transition.authorize",
            }
            & c.scopes
            for c in credentials
        ):
            raise ValueError("review is human-only")
        if any(
            c.client_kind != "worker"
            and {
                "email.process",
                "email.document.process",
                "brain.source.ingest",
                "brain.document.publish",
                "brain.index.activate",
                "brain.fileos.transition.verify",
                "brain.fileos.transition.prepare",
                "brain.fileos.transition.complete",
                "brain.fileos.transition.publish",
                "brain.fileos.transition.index",
            }
            & c.scopes
            for c in credentials
        ):
            raise ValueError("processing is worker-only")
        self.credentials = credentials

    @classmethod
    def from_file(cls, path: Path) -> TokenRegistry:
        if path.stat().st_mode & 0o077:
            raise ValueError("credential file must be readable only by its owner (0600)")
        if path.stat().st_size > 65536:
            raise ValueError("credential file is too large")
        data = json.loads(path.read_text())
        return cls([Credential.model_validate(item) for item in data])

    def authenticate(self, token: str) -> Principal | None:
        if not 32 <= len(token) <= 512:
            return None
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        for credential in self.credentials:
            if hmac.compare_digest(token_hash, credential.token_sha256):
                if credential.expires_at <= datetime.now(UTC):
                    return None
                return Principal(
                    TenantContext(
                        credential.tenant_id,
                        credential.actor_id,
                        frozenset(credential.scopes),
                        uuid4(),
                    ),
                    credential.client_kind,
                )
        return None
