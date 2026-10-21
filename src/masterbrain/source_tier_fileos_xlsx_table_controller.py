"""Restricted operator command for one reviewed FileOS XLSX table replay."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator

from email_brain.auth import Principal
from email_brain.processing_controller import WorkerIdentity, _json, _path
from email_brain.schemas import ClosedModel
from email_brain.store import Store
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.datacore.worker_db import worker_store
from masterbrain.datacore.xlsx_tables_processor import DockerXlsxTableProcessor
from masterbrain.source_tier_fileos_xlsx_table_replay import (
    SourceTierFileOSXlsxTableReplayStore,
)

_REVIEW_ID = re.compile(r"^stier_[a-f0-9]{32}$")


class FileOSTierXlsxTableControllerError(ValueError):
    def __init__(self) -> None:
        super().__init__("FileOS XLSX table replay unavailable; sensitive details suppressed")


class FileOSTierXlsxTableConfig(ClosedModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    version: Literal[1]
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,127}\z")
    root: Path
    document_image_id: str = Field(pattern=r"^sha256:[a-f0-9]{64}\z")
    docker_binary: Path
    credentials_file: Path
    token_file: Path

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value: Any) -> Any:
        if type(value) is not int or value != 1:
            raise FileOSTierXlsxTableControllerError()
        return value

    @field_validator("docker_binary", "credentials_file", "token_file")
    @classmethod
    def private_or_binary_path(cls, value: Path) -> Path:
        return _path(value)

    @field_validator("root")
    @classmethod
    def absolute_root(cls, value: Path) -> Path:
        if not value.is_absolute() or ".." in value.parts or "\x00" in str(value):
            raise FileOSTierXlsxTableControllerError()
        return value


def _current(identity: WorkerIdentity, initial: Principal) -> Principal:
    principal = identity.authenticate()
    if (
        principal.context.tenant_id != initial.context.tenant_id
        or principal.context.actor_id != initial.context.actor_id
    ):
        raise FileOSTierXlsxTableControllerError()
    return principal


def run_source_tier_fileos_xlsx_table_controller(
    path: Path, dsn: str, review_id: str, *,
    check: bool = False, tenant_bound_db: bool = False,
) -> dict[str, Any]:
    """Check without XLSX read, or replay exactly one reviewed source."""
    try:
        if (
            not dsn or type(review_id) is not str or _REVIEW_ID.fullmatch(review_id) is None
            or type(check) is not bool or tenant_bound_db is not True
        ):
            raise FileOSTierXlsxTableControllerError()
        config = FileOSTierXlsxTableConfig.model_validate(_json(path))
        identity = WorkerIdentity(config, scope="brain.document.publish")
        initial = identity.authenticate()
        store = worker_store(Store, dsn, initial.context.tenant_id, tenant_bound_db)
        with store.transaction(initial.context):
            pass
        root = config.root.resolve(strict=True)
        if not root.is_dir():
            raise FileOSTierXlsxTableControllerError()
        fileos_root_binding_sha256(root)
        _current(identity, initial)
        if check:
            return {
                "configuration_valid": True,
                "execution_verified": False,
                "source_effects": False,
                "data_effects": False,
            }
        processor = DockerXlsxTableProcessor(
            config.document_image_id, docker_binary=config.docker_binary,
        )

        def authorize() -> None:
            _current(identity, initial)

        result = SourceTierFileOSXlsxTableReplayStore(
            store, processor,
        ).record_current_xlsx_table_replay(
            initial.context, review_id, root,
            expected_source_id=config.source_id, authorize=authorize,
        )
        _current(identity, initial)
        return result
    except Exception:
        raise FileOSTierXlsxTableControllerError() from None
