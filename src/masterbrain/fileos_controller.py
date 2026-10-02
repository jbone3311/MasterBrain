"""Explicit authenticated FileOS snapshot publication; source effects are absent."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from email_brain.auth import Principal
from email_brain.processing_controller import WorkerIdentity, _json, _path
from email_brain.schemas import ClosedModel
from email_brain.store import Store
from masterbrain.datacore.document_processor import DockerDocumentProcessor
from masterbrain.datacore.extraction import FileOSAdapter
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.datacore.persistence import (
    DataCoreStore,
    fileos_manifest_root_binding_sha256,
    validate_fileos_completion_coverage,
)
from masterbrain.datacore.worker_db import worker_store

MAX_MANIFEST_BYTES = 16 * 1024 * 1024
_SOURCE_ID = re.compile(r"^[a-z][a-z0-9_-]{0,127}\Z", re.ASCII)


class FileOSControllerError(ValueError):
    def __init__(self) -> None:
        super().__init__("FileOS controller unavailable; sensitive details suppressed")


class FileOSControllerConfig(ClosedModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    version: Literal[1]
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,127}\z")
    root: Path
    manifest_file: Path
    credentials_file: Path
    token_file: Path
    code_revision: str = Field(min_length=1, max_length=200)
    document_image_id: str | None = Field(default=None, pattern=r"^sha256:[a-f0-9]{64}\z")
    docker_binary: Path | None = None

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value: Any) -> Any:
        if type(value) is not int or value != 1:
            raise FileOSControllerError()
        return value

    @field_validator("manifest_file", "credentials_file", "token_file", "docker_binary")
    @classmethod
    def private_or_binary_path(cls, value: Path | None) -> Path | None:
        return _path(value) if value is not None else None

    @field_validator("root")
    @classmethod
    def absolute_root(cls, value: Path) -> Path:
        if not value.is_absolute() or ".." in value.parts or "\x00" in str(value):
            raise FileOSControllerError()
        return value

    @model_validator(mode="after")
    def paired_document_worker(self) -> FileOSControllerConfig:
        if (self.document_image_id is None) != (self.docker_binary is None):
            raise FileOSControllerError()
        return self


def _manifest(config: FileOSControllerConfig) -> dict[str, Any]:
    value = _json(config.manifest_file, MAX_MANIFEST_BYTES)
    if not isinstance(value, dict):
        raise FileOSControllerError()
    source, _, _ = validate_fileos_completion_coverage(value)
    if source.source_id != config.source_id or not _SOURCE_ID.fullmatch(config.source_id):
        raise FileOSControllerError()
    return value


def _current(identity: WorkerIdentity, initial: Principal) -> Principal:
    principal = identity.authenticate()
    if (
        principal.context.tenant_id != initial.context.tenant_id
        or principal.context.actor_id != initial.context.actor_id
    ):
        raise FileOSControllerError()
    return principal


def run_fileos_controller(
    path: Path,
    dsn: str,
    idempotency_key: UUID,
    *,
    check: bool = False,
    tenant_bound_db: bool = False,
) -> dict[str, Any]:
    """Validate or publish one immutable snapshot with bounded, replayable authority."""
    try:
        if not dsn or not isinstance(idempotency_key, UUID) or type(tenant_bound_db) is not bool:
            raise FileOSControllerError()
        config = FileOSControllerConfig.model_validate(_json(path))
        manifest = _manifest(config)
        root = config.root.resolve(strict=True)
        if not root.is_dir():
            raise FileOSControllerError()
        if fileos_root_binding_sha256(root) != fileos_manifest_root_binding_sha256(manifest):
            raise FileOSControllerError()
        identity = WorkerIdentity(
            config, scope=frozenset({"brain.source.ingest", "brain.document.publish"})
        )
        initial = identity.authenticate()
        store = worker_store(Store, dsn, initial.context.tenant_id, tenant_bound_db)
        with store.transaction(initial.context):
            pass
        _current(identity, initial)
        if check:
            return {
                "configuration_valid": True,
                "execution_verified": False,
                "source_effects": False,
            }
        processor = (
            DockerDocumentProcessor(config.document_image_id, docker_binary=config.docker_binary)
            if config.document_image_id is not None and config.docker_binary is not None
            else None
        )

        def authorize() -> None:
            _current(identity, initial)

        core = DataCoreStore(store)
        result = FileOSAdapter(core, processor).publish_snapshot(
            initial.context,
            root,
            manifest,
            idempotency_key,
            code_revision=config.code_revision,
            authorize=authorize,
        )
        published = sum(item.publication is not None for item in result.results)
        changed = sum(
            item.publication is not None and item.publication.changed for item in result.results
        )
        manifest_items = manifest["items"]
        item_id_by_version = {item["version_id"]: item["item_id"] for item in manifest_items}
        item_outcomes = {
            item_id_by_version[item.extraction.version_id]: item.extraction.status.value
            for item in result.results
        }
        authorize()
        receipt = core.complete_fileos_run(
            initial.context,
            manifest,
            idempotency_key,
            outcomes=result.counts,
            item_outcomes=item_outcomes,
            published_documents=published,
            code_revision=config.code_revision,
            document_processor_version=(processor.processor_version if processor else None),
        )
        _current(identity, initial)
        return {
            "source_id": result.imported.source_id,
            "observed_items": result.imported.observed_items,
            "new_versions": result.imported.new_versions,
            "unchanged_versions": result.imported.unchanged_versions,
            "outcomes": result.counts,
            "published": published,
            "changed_publications": changed,
            "completion": {
                "run_id": str(receipt.run_id),
                "completed_at": receipt.completed_at.isoformat(),
                "recorded": receipt.recorded,
            },
            "source_effects": False,
        }
    except Exception:
        raise FileOSControllerError() from None
