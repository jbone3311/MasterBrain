"""Explicit private FileOS index generation and rollback operation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from email_brain.auth import Principal
from email_brain.processing_controller import WorkerIdentity, _json, _path
from email_brain.schemas import ClosedModel
from email_brain.store import Store
from masterbrain.datacore.persistence import DataCoreStore
from masterbrain.datacore.worker_db import worker_store

_SOURCE_ID = re.compile(r"^[a-z][a-z0-9_-]{0,127}\Z", re.ASCII)


class FileOSIndexControllerError(ValueError):
    def __init__(self) -> None:
        super().__init__("FileOS index controller unavailable; sensitive details suppressed")


class FileOSIndexControllerConfig(ClosedModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    version: Literal[1]
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,127}\z")
    credentials_file: Path
    token_file: Path
    code_revision: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value: Any) -> Any:
        if type(value) is not int or value != 1:
            raise FileOSIndexControllerError()
        return value

    @field_validator("credentials_file", "token_file")
    @classmethod
    def private_path(cls, value: Path) -> Path:
        return _path(value)

    @field_validator("code_revision")
    @classmethod
    def safe_revision(cls, value: str | None) -> str | None:
        if value is not None and "\x00" in value:
            raise FileOSIndexControllerError()
        return value


def _current(identity: WorkerIdentity, initial: Principal) -> Principal:
    principal = identity.authenticate()
    if (
        principal.context.tenant_id != initial.context.tenant_id
        or principal.context.actor_id != initial.context.actor_id
    ):
        raise FileOSIndexControllerError()
    return principal


def run_fileos_index_controller(
    path: Path,
    dsn: str,
    idempotency_key: UUID,
    *,
    run_id: UUID | None = None,
    generation_id: str | None = None,
    check: bool = False,
    tenant_bound_db: bool = False,
) -> dict[str, Any]:
    """Build/activate an exact run, or activate an existing generation as rollback."""
    try:
        if (
            not dsn
            or not isinstance(idempotency_key, UUID)
            or (run_id is None) == (generation_id is None)
            or (run_id is not None and not isinstance(run_id, UUID))
            or (generation_id is not None and not _SOURCE_ID.fullmatch(generation_id))
            or type(tenant_bound_db) is not bool
        ):
            raise FileOSIndexControllerError()
        config = FileOSIndexControllerConfig.model_validate(_json(path))
        if run_id is not None and config.code_revision is None:
            raise FileOSIndexControllerError()
        scopes = (
            frozenset({"brain.document.publish", "brain.index.activate"})
            if run_id is not None
            else frozenset({"brain.index.activate"})
        )
        identity = WorkerIdentity(config, scope=scopes)
        initial = identity.authenticate()
        store = worker_store(Store, dsn, initial.context.tenant_id, tenant_bound_db)
        with store.transaction(initial.context):
            pass
        _current(identity, initial)
        mode = "build_and_activate" if run_id is not None else "activate_existing"
        if check:
            return {
                "configuration_valid": True,
                "execution_verified": False,
                "operation": mode,
                "source_effects": False,
                "data_effects": False,
            }
        core = DataCoreStore(store)
        generation = None
        selected_generation_id = generation_id
        if run_id is not None:
            assert config.code_revision is not None
            generation = core.build_fileos_index_generation(
                initial.context,
                config.source_id,
                run_id,
                code_revision=config.code_revision,
            )
            selected_generation_id = generation.generation_id
            _current(identity, initial)
        assert selected_generation_id is not None
        activation = core.activate_fileos_index_generation(
            initial.context,
            config.source_id,
            selected_generation_id,
            idempotency_key,
        )
        _current(identity, initial)
        payload: dict[str, Any] = {
            "source_id": config.source_id,
            "operation": mode,
            "generation_id": selected_generation_id,
            "activation": {
                "previous_generation_id": activation.previous_generation_id,
                "activated_at": activation.activated_at.isoformat(),
                "recorded": activation.recorded,
            },
            "source_effects": False,
        }
        if generation is not None:
            payload["generation"] = {
                "run_id": str(generation.run_id),
                "item_count": generation.item_count,
                "document_count": generation.document_count,
                "chunk_count": generation.chunk_count,
                "plan_sha256": generation.plan_sha256,
                "ready_at": generation.ready_at.isoformat(),
                "recorded": generation.recorded,
            }
        return payload
    except Exception:
        raise FileOSIndexControllerError() from None
