"""Restricted private operator for one reviewed retained-Email text replay."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict, field_validator, model_validator

from email_brain.auth import Principal
from email_brain.blobs import EncryptedBlobStore
from email_brain.processing_controller import (
    WorkerIdentity,
    _directory,
    _json,
    _Keys,
    _path,
)
from email_brain.schemas import ClosedModel
from email_brain.store import Store
from masterbrain.datacore.worker_db import worker_store
from masterbrain.source_tier_email_replay import SourceTierEmailReplayStore

_REVIEW_ID = re.compile(r"^stier_[a-f0-9]{32}$")
_SCOPES = frozenset({"brain.document.publish", "email.evidence.read"})


class EmailTierReplayControllerError(ValueError):
    def __init__(self) -> None:
        super().__init__("Email tier replay unavailable; sensitive details suppressed")


class EmailTierReplayConfig(ClosedModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    version: Literal[1]
    account_id: UUID
    credentials_file: Path
    token_file: Path
    blob_root: Path | None = None
    keys_file: Path | None = None

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value: Any) -> Any:
        if type(value) is not int or value != 1:
            raise EmailTierReplayControllerError()
        return value

    @field_validator("credentials_file", "token_file", "blob_root", "keys_file")
    @classmethod
    def private_path(cls, value: Path | None) -> Path | None:
        return _path(value) if value is not None else None

    @model_validator(mode="after")
    def paired_storage(self) -> EmailTierReplayConfig:
        if (self.blob_root is None) != (self.keys_file is None):
            raise EmailTierReplayControllerError()
        return self


def _current(identity: WorkerIdentity, initial: Principal) -> Principal:
    principal = identity.authenticate()
    if (
        principal.context.tenant_id != initial.context.tenant_id
        or principal.context.actor_id != initial.context.actor_id
    ):
        raise EmailTierReplayControllerError()
    return principal


def run_source_tier_email_controller(
    path: Path, dsn: str, review_id: str, *,
    check: bool = False, tenant_bound_db: bool = False,
) -> dict[str, Any]:
    """Check without MIME read, or execute one exact tenant-bound replay."""
    try:
        if (
            not dsn or type(review_id) is not str or _REVIEW_ID.fullmatch(review_id) is None
            or type(check) is not bool or tenant_bound_db is not True
        ):
            raise EmailTierReplayControllerError()
        config = EmailTierReplayConfig.model_validate(_json(path))
        identity = WorkerIdentity(config, scope=_SCOPES)
        initial = identity.authenticate()
        store = worker_store(Store, dsn, initial.context.tenant_id, tenant_bound_db)
        with store.transaction(initial.context) as conn:
            account = conn.execute(
                "SELECT status FROM mail_accounts WHERE id=%s", (config.account_id,),
            ).fetchone()
            if account is None or account["status"] != "active":
                raise EmailTierReplayControllerError()
        keys: _Keys | None = None
        if config.blob_root is not None and config.keys_file is not None:
            keys = _Keys.model_validate(_json(config.keys_file))
            if (
                keys.tenant_id != initial.context.tenant_id
                or len({key.key_id for key in keys.keys}) != len(keys.keys)
            ):
                raise EmailTierReplayControllerError()
            # Check mode validates the existing private root but never opens
            # an object or constructs a store that might create storage.
            with _directory(config.blob_root):
                pass
        _current(identity, initial)
        if check:
            return {
                "configuration_valid": True,
                "execution_verified": False,
                "source_effects": False,
                "data_effects": False,
            }
        if keys is not None and config.blob_root is not None:
            store = worker_store(
                Store, dsn, initial.context.tenant_id, tenant_bound_db,
                blobs=EncryptedBlobStore(
                    config.blob_root,
                    {(keys.tenant_id, key.key_id): bytes.fromhex(key.key_hex)
                     for key in keys.keys},
                    {},
                ),
            )

        def authorize() -> None:
            _current(identity, initial)

        result = SourceTierEmailReplayStore(store).record_current_text_replay(
            initial.context, review_id, expected_account_id=config.account_id,
            authorize=authorize,
        )
        _current(identity, initial)
        return result
    except Exception:
        raise EmailTierReplayControllerError() from None
