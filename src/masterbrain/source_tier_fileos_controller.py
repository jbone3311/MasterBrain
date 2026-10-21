"""Explicit authenticated FileOS tier-text replay; no source file effects."""

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
from masterbrain.source_tier_fileos_replay import SourceTierFileOSReplayStore

_REVIEW_ID = re.compile(r"^stier_[a-f0-9]{32}$")


class FileOSTierReplayControllerError(ValueError):
    def __init__(self) -> None:
        super().__init__("FileOS tier replay unavailable; sensitive details suppressed")


class FileOSTierReplayConfig(ClosedModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    version: Literal[1]
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,127}\z")
    root: Path
    credentials_file: Path
    token_file: Path

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value: Any) -> Any:
        if type(value) is not int or value != 1:
            raise FileOSTierReplayControllerError()
        return value

    @field_validator("credentials_file", "token_file")
    @classmethod
    def private_path(cls, value: Path) -> Path:
        return _path(value)

    @field_validator("root")
    @classmethod
    def absolute_root(cls, value: Path) -> Path:
        if not value.is_absolute() or ".." in value.parts or "\x00" in str(value):
            raise FileOSTierReplayControllerError()
        return value


def _current(identity: WorkerIdentity, initial: Principal) -> Principal:
    principal = identity.authenticate()
    if (
        principal.context.tenant_id != initial.context.tenant_id
        or principal.context.actor_id != initial.context.actor_id
    ):
        raise FileOSTierReplayControllerError()
    return principal


def run_source_tier_fileos_controller(
    path: Path, dsn: str, review_id: str, *,
    check: bool = False, tenant_bound_db: bool = False,
) -> dict[str, Any]:
    """Validate or replay one selected review with a document-only worker."""
    try:
        if (
            not dsn or type(review_id) is not str or _REVIEW_ID.fullmatch(review_id) is None
            or type(check) is not bool or tenant_bound_db is not True
        ):
            raise FileOSTierReplayControllerError()
        config = FileOSTierReplayConfig.model_validate(_json(path))
        identity = WorkerIdentity(config, scope="brain.document.publish")
        initial = identity.authenticate()
        store = worker_store(Store, dsn, initial.context.tenant_id, tenant_bound_db)
        with store.transaction(initial.context):
            pass
        root = config.root.resolve(strict=True)
        if not root.is_dir():
            raise FileOSTierReplayControllerError()
        # Check only the physical root identity. No selected source file is read
        # and no review or replay row is touched by --check.
        fileos_root_binding_sha256(root)
        _current(identity, initial)
        if check:
            return {
                "configuration_valid": True,
                "execution_verified": False,
                "source_effects": False,
                "data_effects": False,
            }

        def authorize() -> None:
            _current(identity, initial)

        result = SourceTierFileOSReplayStore(store).record_current_text_replay(
            initial.context, review_id, root,
            expected_source_id=config.source_id,
            authorize=authorize,
        )
        _current(identity, initial)
        return result
    except Exception:
        raise FileOSTierReplayControllerError() from None
