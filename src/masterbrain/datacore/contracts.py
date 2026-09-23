"""Immutable source, evidence, and provenance contracts for shared DataCore paths."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

_ID = re.compile(r"^[a-z][a-z0-9_-]{0,127}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class SourceKind(StrEnum):
    EMAIL = "email"
    FILEOS = "fileos"


class EvidenceStorage(StrEnum):
    INLINE = "inline"
    OBJECT = "object"
    SOURCE_BOUND = "source_bound"


def stable_id(namespace: str, *parts: str) -> str:
    """Produce a stable opaque identifier without exposing source text."""
    if not _ID.fullmatch(namespace):
        raise ValueError("invalid stable-id namespace")
    digest = hashlib.sha256("\0".join(parts).encode("utf-8", errors="strict")).hexdigest()
    return f"{namespace}_{digest[:32]}"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _metadata(value: Mapping[str, Any]) -> Mapping[str, Any]:
    clean: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or len(key) > 100 or "\x00" in key:
            raise ValueError("invalid metadata key")
        if not isinstance(item, (str, int, float, bool, type(None))):
            raise ValueError("metadata values must be scalar")
        if isinstance(item, str) and ("\x00" in item or len(item) > 4000):
            raise ValueError("invalid metadata text")
        clean[key] = item
    return MappingProxyType(clean)


@dataclass(frozen=True, slots=True)
class SourceRef:
    source_id: str
    kind: SourceKind
    display_name: str

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.source_id):
            raise ValueError("invalid source_id")
        if not self.display_name or len(self.display_name) > 200 or "\x00" in self.display_name:
            raise ValueError("invalid source display name")


@dataclass(frozen=True, slots=True)
class Digest:
    algorithm: str
    value: str

    def __post_init__(self) -> None:
        if self.algorithm != "sha256" or not _SHA256.fullmatch(self.value):
            raise ValueError("only lowercase SHA-256 digests are accepted")


@dataclass(frozen=True, slots=True)
class SourceItemVersion:
    item_id: str
    version_id: str
    source: SourceRef
    locator: str
    observed_at: datetime
    content: Digest
    size_bytes: int
    media_type: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.item_id) or not _ID.fullmatch(self.version_id):
            raise ValueError("invalid source item identity")
        if not self.locator or self.locator.startswith(('/', '\\')) or "\x00" in self.locator:
            raise ValueError("locator must be a non-empty relative path")
        if ".." in self.locator.replace("\\", "/").split("/"):
            raise ValueError("locator cannot escape its source")
        if self.size_bytes < 0:
            raise ValueError("size_bytes cannot be negative")
        if not self.media_type or len(self.media_type) > 200:
            raise ValueError("invalid media type")
        object.__setattr__(self, "observed_at", _aware(self.observed_at))
        object.__setattr__(self, "metadata", _metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    evidence_id: str
    source_version_id: str
    digest: Digest
    storage: EvidenceStorage
    retained: bool

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.evidence_id) or not _ID.fullmatch(self.source_version_id):
            raise ValueError("invalid evidence identity")
        if self.storage is EvidenceStorage.SOURCE_BOUND and self.retained:
            raise ValueError("source-bound evidence is referenced, not retained")


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    provenance_id: str
    output_id: str
    input_ids: tuple[str, ...]
    transform: str
    transform_version: str
    code_revision: str
    created_at: datetime
    configuration_digest: Digest

    def __post_init__(self) -> None:
        identities = (self.provenance_id, self.output_id, *self.input_ids)
        if not self.input_ids or any(not _ID.fullmatch(value) for value in identities):
            raise ValueError("invalid provenance identity")
        for value in (self.transform, self.transform_version, self.code_revision):
            if not value or len(value) > 200 or "\x00" in value:
                raise ValueError("invalid provenance descriptor")
        object.__setattr__(self, "created_at", _aware(self.created_at))
