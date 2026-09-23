"""Private operators for selected archive-member derivatives."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from email_brain.auth import Principal
from email_brain.processing_controller import WorkerIdentity, _json, _path
from email_brain.schemas import ClosedModel
from email_brain.store import Conflict, NotFound, Store
from masterbrain.datacore.archive_member_document import (
    extract_archive_member_document,
    publish_extracted_archive_member_document,
)
from masterbrain.datacore.archive_member_image_ocr import (
    extract_archive_member_image_ocr,
    publish_extracted_archive_member_image_ocr,
)
from masterbrain.datacore.archive_member_processor import DockerArchiveMemberProcessor
from masterbrain.datacore.archive_member_text import (
    extract_archive_member_text,
    publish_extracted_archive_member_text,
)
from masterbrain.datacore.document_processor import DockerDocumentProcessor
from masterbrain.datacore.extraction import ExtractionStatus
from masterbrain.datacore.image_ocr_processor import DockerImageOcrProcessor
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
    document_image_id: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}\z")
    image_ocr_image_id: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}\z")
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

    @model_validator(mode="after")
    def separate_ocr_image(self) -> ArchiveMemberControllerConfig:
        if self.image_ocr_image_id is not None and self.image_ocr_image_id in {
            self.archive_image_id,
            self.document_image_id,
        }:
            raise ArchiveMemberControllerError()
        return self


class ArchiveMemberBatchItem(ClosedModel):
    member_locator: str = Field(min_length=1, max_length=1024)
    idempotency_key: UUID

    @field_validator("member_locator")
    @classmethod
    def safe_member_locator(cls, value: str) -> str:
        _member_locator(value)
        return value


def archive_member_batch_sha256(
    version: int,
    inventory_id: str,
    code_revision: str,
    items: list[ArchiveMemberBatchItem],
) -> str:
    payload = {
        "version": version,
        "inventory_id": inventory_id,
        "code_revision": code_revision,
        "items": [
            {
                "member_locator": item.member_locator,
                "idempotency_key": str(item.idempotency_key),
            }
            for item in items
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class ArchiveMemberBatchPlan(ClosedModel):
    version: Literal[1]
    inventory_id: str = Field(pattern=r"^archive_inventory_[a-f0-9]{32}\z")
    code_revision: str = Field(min_length=1, max_length=200)
    items: list[ArchiveMemberBatchItem] = Field(min_length=1, max_length=100)
    plan_sha256: str = Field(pattern=r"^[a-f0-9]{64}\z")

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value: Any) -> Any:
        if type(value) is not int or value != 1:
            raise ArchiveMemberControllerError()
        return value

    @field_validator("code_revision")
    @classmethod
    def revision_is_plain(cls, value: str) -> str:
        if "\x00" in value:
            raise ArchiveMemberControllerError()
        return value

    @model_validator(mode="after")
    def sealed_and_unique(self) -> ArchiveMemberBatchPlan:
        locators = [item.member_locator for item in self.items]
        keys = [item.idempotency_key for item in self.items]
        if len(set(locators)) != len(locators) or len(set(keys)) != len(keys):
            raise ArchiveMemberControllerError()
        expected = archive_member_batch_sha256(
            self.version, self.inventory_id, self.code_revision, self.items
        )
        if self.plan_sha256 != expected:
            raise ArchiveMemberControllerError()
        return self


class ArchiveDocumentBatchItem(ClosedModel):
    member_locator: str = Field(min_length=1, max_length=1024)
    document_format: Literal["pdf", "docx", "xlsx"]
    idempotency_key: UUID

    @model_validator(mode="after")
    def safe_format_selection(self) -> ArchiveDocumentBatchItem:
        _member_locator(self.member_locator)
        expected = {".pdf": "pdf", ".docx": "docx", ".xlsx": "xlsx"}.get(
            PurePosixPath(self.member_locator).suffix.lower()
        )
        if expected != self.document_format:
            raise ArchiveMemberControllerError()
        return self


def archive_document_batch_sha256(
    version: int,
    inventory_id: str,
    code_revision: str,
    items: list[ArchiveDocumentBatchItem],
) -> str:
    payload = {
        "version": version,
        "inventory_id": inventory_id,
        "code_revision": code_revision,
        "items": [
            {
                "member_locator": item.member_locator,
                "document_format": item.document_format,
                "idempotency_key": str(item.idempotency_key),
            }
            for item in items
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class ArchiveDocumentBatchPlan(ClosedModel):
    version: Literal[1]
    inventory_id: str = Field(pattern=r"^archive_inventory_[a-f0-9]{32}\z")
    code_revision: str = Field(min_length=1, max_length=200)
    items: list[ArchiveDocumentBatchItem] = Field(min_length=1, max_length=100)
    plan_sha256: str = Field(pattern=r"^[a-f0-9]{64}\z")

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value: Any) -> Any:
        if type(value) is not int or value != 1:
            raise ArchiveMemberControllerError()
        return value

    @field_validator("code_revision")
    @classmethod
    def revision_is_plain(cls, value: str) -> str:
        if "\x00" in value:
            raise ArchiveMemberControllerError()
        return value

    @model_validator(mode="after")
    def sealed_and_unique(self) -> ArchiveDocumentBatchPlan:
        locators = [item.member_locator for item in self.items]
        keys = [item.idempotency_key for item in self.items]
        if len(set(locators)) != len(locators) or len(set(keys)) != len(keys):
            raise ArchiveMemberControllerError()
        expected = archive_document_batch_sha256(
            self.version, self.inventory_id, self.code_revision, self.items
        )
        if self.plan_sha256 != expected:
            raise ArchiveMemberControllerError()
        return self


def _current(identity: WorkerIdentity, initial: Principal) -> Principal:
    principal = identity.authenticate()
    if (
        principal.context.tenant_id != initial.context.tenant_id
        or principal.context.actor_id != initial.context.actor_id
    ):
        raise ArchiveMemberControllerError()
    return principal


def _member_locator(member_locator: str) -> None:
    relative = PurePosixPath(member_locator)
    if (
        not 1 <= len(member_locator) <= 1024
        or relative.is_absolute()
        or ".." in relative.parts
        or "\\" in member_locator
        or "\x00" in member_locator
        or str(relative) != member_locator
        or member_locator.endswith("/")
    ):
        raise ArchiveMemberControllerError()


def _selection(inventory_id: str, member_locator: str) -> None:
    if not _INVENTORY.fullmatch(inventory_id):
        raise ArchiveMemberControllerError()
    _member_locator(member_locator)


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


def run_archive_member_plan_controller(
    path: Path,
    dsn: str,
    inventory_id: str,
    *,
    after: int | None = None,
    limit: int = 25,
    check: bool = False,
) -> dict[str, Any]:
    """Validate or preview eligible text members in one current archive inventory."""
    try:
        if (
            not dsn
            or not _INVENTORY.fullmatch(inventory_id)
            or (after is not None and (type(after) is not int or not 0 <= after <= 1999))
            or type(limit) is not int
            or not 1 <= limit <= 100
        ):
            raise ArchiveMemberControllerError()
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
        if check:
            return {
                "configuration_valid": True,
                "execution_verified": False,
                "operation": "archive_member_text_plan",
                "source_effects": False,
                "data_effects": False,
            }
        _current(identity, initial)
        result = DataCoreStore(store).archive_member_text_plan(
            initial.context, inventory_id, after=after, limit=limit
        )
        _current(identity, initial)
        return {"operation": "archive_member_text_plan", **result}
    except Exception:
        raise ArchiveMemberControllerError() from None


def run_archive_document_plan_controller(
    path: Path,
    dsn: str,
    inventory_id: str,
    *,
    after: int | None = None,
    limit: int = 25,
    check: bool = False,
) -> dict[str, Any]:
    """Validate or preview eligible documents in one current archive inventory."""
    try:
        if (
            not dsn
            or not _INVENTORY.fullmatch(inventory_id)
            or (after is not None and (type(after) is not int or not 0 <= after <= 1999))
            or type(limit) is not int
            or not 1 <= limit <= 100
        ):
            raise ArchiveMemberControllerError()
        config = ArchiveMemberControllerConfig.model_validate(_json(path))
        if config.document_image_id is None:
            raise ArchiveMemberControllerError()
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
        if check:
            return {
                "configuration_valid": True,
                "execution_verified": False,
                "operation": "archive_member_document_plan",
                "source_effects": False,
                "worker_effects": False,
                "data_effects": False,
            }
        _current(identity, initial)
        result = DataCoreStore(store).archive_member_document_plan(
            initial.context, inventory_id, after=after, limit=limit
        )
        _current(identity, initial)
        return {"operation": "archive_member_document_plan", **result}
    except Exception:
        raise ArchiveMemberControllerError() from None


def run_archive_member_document_controller(
    path: Path,
    dsn: str,
    inventory_id: str,
    member_locator: str,
    idempotency_key: UUID,
    *,
    check: bool = False,
) -> dict[str, Any]:
    """Validate or publish one selected archive-member PDF/Office derivative."""
    try:
        if not dsn or not isinstance(idempotency_key, UUID):
            raise ArchiveMemberControllerError()
        _selection(inventory_id, member_locator)
        config = ArchiveMemberControllerConfig.model_validate(_json(path))
        if config.document_image_id is None:
            raise ArchiveMemberControllerError()
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
        if check:
            return {
                "configuration_valid": True,
                "execution_verified": False,
                "operation": "archive_member_document",
                "source_effects": False,
                "data_effects": False,
            }
        core = DataCoreStore(store)
        target = core.archive_document_member_target(initial.context, inventory_id, member_locator)
        _current(identity, initial)
        archive_processor = DockerArchiveMemberProcessor(
            config.archive_image_id, docker_binary=config.docker_binary
        )
        document_processor = DockerDocumentProcessor(
            config.document_image_id, docker_binary=config.docker_binary
        )
        _current(identity, initial)
        extraction = extract_archive_member_document(
            root, target, archive_processor, document_processor
        )
        if extraction.status is not ExtractionStatus.EXTRACTED:
            raise ArchiveMemberControllerError()
        _current(identity, initial)
        published = publish_extracted_archive_member_document(
            core,
            initial.context,
            target,
            extraction,
            code_revision=config.code_revision,
            idempotency_key=idempotency_key,
        )
        _current(identity, initial)
        counts = {
            key: value
            for key, value in extraction.metadata.items()
            if key.endswith("_count") and isinstance(value, int) and not isinstance(value, bool)
        }
        return {
            "operation": "archive_member_document",
            "inventory_id": published.inventory_id,
            "source_id": published.source_id,
            "item_id": published.item_id,
            "version_id": published.version_id,
            "evidence_id": published.evidence_id,
            "document_id": published.document_id,
            "format": extraction.metadata["format"],
            "metadata_counts": counts,
            "chunks": published.chunks,
            "changed": published.changed,
            "source_effects": False,
        }
    except Exception:
        raise ArchiveMemberControllerError() from None


def run_archive_member_image_ocr_controller(
    path: Path,
    dsn: str,
    inventory_id: str,
    member_locator: str,
    idempotency_key: UUID,
    *,
    check: bool = False,
) -> dict[str, Any]:
    """Validate or publish one explicitly selected archive image OCR derivative."""
    try:
        if not dsn or not isinstance(idempotency_key, UUID):
            raise ArchiveMemberControllerError()
        _selection(inventory_id, member_locator)
        config = ArchiveMemberControllerConfig.model_validate(_json(path))
        if config.image_ocr_image_id is None:
            raise ArchiveMemberControllerError()
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
        if check:
            return {
                "configuration_valid": True,
                "execution_verified": False,
                "operation": "archive_member_image_ocr",
                "source_effects": False,
                "data_effects": False,
            }
        core = DataCoreStore(store)
        target = core.archive_member_target(initial.context, inventory_id, member_locator)
        _current(identity, initial)
        archive_processor = DockerArchiveMemberProcessor(
            config.archive_image_id, docker_binary=config.docker_binary
        )
        image_processor = DockerImageOcrProcessor(
            config.image_ocr_image_id, docker_binary=config.docker_binary
        )
        _current(identity, initial)
        extraction = extract_archive_member_image_ocr(
            root, target, archive_processor, image_processor
        )
        if extraction.status is not ExtractionStatus.EXTRACTED:
            raise ArchiveMemberControllerError()
        _current(identity, initial)
        published = publish_extracted_archive_member_image_ocr(
            core,
            initial.context,
            target,
            extraction,
            code_revision=config.code_revision,
            idempotency_key=idempotency_key,
        )
        _current(identity, initial)
        return {
            "operation": "archive_member_image_ocr",
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


def run_archive_member_batch_controller(
    path: Path,
    plan_path: Path,
    dsn: str,
    *,
    check: bool = False,
) -> dict[str, Any]:
    """Validate or execute one sealed archive-member text publication plan."""
    try:
        if not dsn:
            raise ArchiveMemberControllerError()
        config = ArchiveMemberControllerConfig.model_validate(_json(path))
        plan = ArchiveMemberBatchPlan.model_validate(_json(plan_path))
        if plan.code_revision != config.code_revision:
            raise ArchiveMemberControllerError()
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
        if check:
            return {
                "configuration_valid": True,
                "execution_verified": False,
                "operation": "archive_member_text_batch",
                "plan_sha256": plan.plan_sha256,
                "requested": len(plan.items),
                "source_effects": False,
                "data_effects": False,
            }
        processor = DockerArchiveMemberProcessor(
            config.archive_image_id, docker_binary=config.docker_binary
        )
        core = DataCoreStore(store)
        results: list[dict[str, Any]] = []
        recorded = 0
        replayed = 0

        def refused(index: int) -> dict[str, Any]:
            return {
                "operation": "archive_member_text_batch",
                "plan_sha256": plan.plan_sha256,
                "requested": len(plan.items),
                "completed": len(results),
                "recorded": recorded,
                "replayed": replayed,
                "results": results,
                "complete": False,
                "failed_item_index": index,
                "error_code": "member_refused",
                "source_effects": False,
            }

        for index, item in enumerate(plan.items):
            _current(identity, initial)
            try:
                target = core.archive_member_target(
                    initial.context, plan.inventory_id, item.member_locator
                )
            except (NotFound, ValueError):
                return refused(index)
            _current(identity, initial)
            extraction = extract_archive_member_text(root, target, processor)
            if extraction.status is not ExtractionStatus.EXTRACTED:
                return refused(index)
            _current(identity, initial)
            try:
                published = publish_extracted_archive_member_text(
                    core,
                    initial.context,
                    target,
                    extraction,
                    code_revision=config.code_revision,
                    idempotency_key=item.idempotency_key,
                )
            except (Conflict, NotFound, ValueError):
                return refused(index)
            _current(identity, initial)
            recorded += int(published.changed)
            replayed += int(not published.changed)
            results.append({"item_index": index, "recorded": published.changed})
        return {
            "operation": "archive_member_text_batch",
            "plan_sha256": plan.plan_sha256,
            "requested": len(plan.items),
            "completed": len(results),
            "recorded": recorded,
            "replayed": replayed,
            "results": results,
            "complete": True,
            "failed_item_index": None,
            "error_code": None,
            "source_effects": False,
        }
    except Exception:
        raise ArchiveMemberControllerError() from None


def run_archive_document_batch_controller(
    path: Path,
    plan_path: Path,
    dsn: str,
    *,
    check: bool = False,
) -> dict[str, Any]:
    """Validate or execute one sealed archive-member document publication plan."""
    try:
        if not dsn:
            raise ArchiveMemberControllerError()
        config = ArchiveMemberControllerConfig.model_validate(_json(path))
        plan = ArchiveDocumentBatchPlan.model_validate(_json(plan_path))
        if config.document_image_id is None or plan.code_revision != config.code_revision:
            raise ArchiveMemberControllerError()
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
        if check:
            return {
                "configuration_valid": True,
                "execution_verified": False,
                "operation": "archive_member_document_batch",
                "plan_sha256": plan.plan_sha256,
                "requested": len(plan.items),
                "source_effects": False,
                "data_effects": False,
            }
        archive_processor = DockerArchiveMemberProcessor(
            config.archive_image_id, docker_binary=config.docker_binary
        )
        document_processor = DockerDocumentProcessor(
            config.document_image_id, docker_binary=config.docker_binary
        )
        core = DataCoreStore(store)
        results: list[dict[str, Any]] = []
        recorded = 0
        replayed = 0

        def refused(index: int) -> dict[str, Any]:
            return {
                "operation": "archive_member_document_batch",
                "plan_sha256": plan.plan_sha256,
                "requested": len(plan.items),
                "completed": len(results),
                "recorded": recorded,
                "replayed": replayed,
                "results": results,
                "complete": False,
                "failed_item_index": index,
                "error_code": "document_refused",
                "source_effects": False,
            }

        for index, item in enumerate(plan.items):
            _current(identity, initial)
            try:
                target = core.archive_document_member_target(
                    initial.context, plan.inventory_id, item.member_locator
                )
            except (NotFound, ValueError):
                return refused(index)
            _current(identity, initial)
            extraction = extract_archive_member_document(
                root, target, archive_processor, document_processor
            )
            if (
                extraction.status is not ExtractionStatus.EXTRACTED
                or extraction.metadata.get("format") != item.document_format
            ):
                return refused(index)
            _current(identity, initial)
            try:
                published = publish_extracted_archive_member_document(
                    core,
                    initial.context,
                    target,
                    extraction,
                    code_revision=config.code_revision,
                    idempotency_key=item.idempotency_key,
                )
            except (Conflict, NotFound, ValueError):
                return refused(index)
            _current(identity, initial)
            recorded += int(published.changed)
            replayed += int(not published.changed)
            results.append({"item_index": index, "recorded": published.changed})
        return {
            "operation": "archive_member_document_batch",
            "plan_sha256": plan.plan_sha256,
            "requested": len(plan.items),
            "completed": len(results),
            "recorded": recorded,
            "replayed": replayed,
            "results": results,
            "complete": True,
            "failed_item_index": None,
            "error_code": None,
            "source_effects": False,
        }
    except Exception:
        raise ArchiveMemberControllerError() from None
