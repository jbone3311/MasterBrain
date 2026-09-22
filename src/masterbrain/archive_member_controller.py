"""Private one-shot operator for one archive-member text derivative."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from email_brain.auth import Principal
from email_brain.processing_controller import WorkerIdentity, _json, _path
from email_brain.schemas import ClosedModel
from email_brain.store import Store
from masterbrain.datacore.archive_member_processor import DockerArchiveMemberProcessor
from masterbrain.datacore.archive_member_text import (
    extract_archive_member_text,
    publish_extracted_archive_member_text,
)
from masterbrain.datacore.extraction import ExtractionStatus
from masterbrain.datacore.persistence import DataCoreStore

_INVENTORY = re.compile(r"archive_inventory_[a-f0-9]{32}\Z", re.ASCII)


class ArchiveMemberControllerError(ValueError):
    def __init__(self) -> None:
        super().__init__("archive member controller unavailable; sensitive details suppressed")


class ArchiveMemberControllerConfig(ClosedModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    version: Literal[1]
    root: Path
    archive_image_id: str = Field(pattern=r"^sha256:[a-f0-9]{64}\z")
    docker_binary: Path
    credentials_file: Path
    token_file: Path
    code_revision: str = Field(min_length=1, max_length=200)

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value: Any) -> Any:
        if type(value) is not int or value != 1:
            raise ArchiveMemberControllerError()
        return value

    @field_validator("docker_binary", "credentials_file", "token_file")
    @classmethod
    def private_or_binary_path(cls, value: Path) -> Path:
        return _path(value)

    @field_validator("root")
    @classmethod
    def absolute_root(cls, value: Path) -> Path:
        if not value.is_absolute() or ".." in value.parts or "\x00" in str(value):
            raise ArchiveMemberControllerError()
        return value

    @field_validator("code_revision")
    @classmethod
    def revision_is_plain(cls, value: str) -> str:
        if "\x00" in value:
            raise ArchiveMemberControllerError()
        return value


def _current(identity: WorkerIdentity, initial: Principal) -> Principal:
    principal = identity.authenticate()
    if (
        principal.context.tenant_id != initial.context.tenant_id
        or principal.context.actor_id != initial.context.actor_id
    ):
        raise ArchiveMemberControllerError()
    return principal


def _selection(inventory_id: str, member_locator: str) -> None:
    relative = PurePosixPath(member_locator)
    if (
        not _INVENTORY.fullmatch(inventory_id)
        or not 1 <= len(member_locator) <= 1024
        or relative.is_absolute()
        or ".." in relative.parts
        or "\\" in member_locator
        or "\x00" in member_locator
        or str(relative) != member_locator
        or member_locator.endswith("/")
    ):
        raise ArchiveMemberControllerError()


def run_archive_member_controller(
    path: Path,
    dsn: str,
    inventory_id: str,
    member_locator: str,
    idempotency_key: UUID,
    *,
    check: bool = False,
) -> dict[str, Any]:
    """Validate or publish exactly one selected archive-member text derivative."""
    try:
        if not dsn or not isinstance(idempotency_key, UUID):
            raise ArchiveMemberControllerError()
        _selection(inventory_id, member_locator)
        config = ArchiveMemberControllerConfig.model_validate(_json(path))
        root = config.root.resolve(strict=True)
        if not root.is_dir():
            raise ArchiveMemberControllerError()
        identity = WorkerIdentity(
            config, scope=frozenset({"brain.source.ingest", "brain.document.publish"})
        )
        initial = identity.authenticate()
        store = Store(dsn)
        with store.transaction(initial.context):
            pass
        _current(identity, initial)
        processor = DockerArchiveMemberProcessor(
            config.archive_image_id, docker_binary=config.docker_binary
        )
        if check:
            return {
                "configuration_valid": True,
                "execution_verified": False,
                "source_effects": False,
            }
        core = DataCoreStore(store)
        target = core.archive_member_target(initial.context, inventory_id, member_locator)
        _current(identity, initial)
        extraction = extract_archive_member_text(root, target, processor)
        if extraction.status is not ExtractionStatus.EXTRACTED:
            raise ArchiveMemberControllerError()
        _current(identity, initial)
        published = publish_extracted_archive_member_text(
            core,
            initial.context,
            target,
            extraction,
            code_revision=config.code_revision,
            idempotency_key=idempotency_key,
        )
        _current(identity, initial)
        return {
            "inventory_id": published.inventory_id,
            "source_id": published.source_id,
            "item_id": published.item_id,
            "version_id": published.version_id,
            "evidence_id": published.evidence_id,
            "document_id": published.document_id,
            "chunks": published.chunks,
            "changed": published.changed,
            "source_effects": False,
        }
    except Exception:
        raise ArchiveMemberControllerError() from None
