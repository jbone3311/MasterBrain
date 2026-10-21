"""Restricted operator command for one reviewed retained-Email PDF replay."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from email_brain.auth import Principal
from email_brain.blobs import EncryptedBlobStore
from email_brain.pdf_processor import DockerPdfProcessor
from email_brain.processing_controller import WorkerIdentity, _directory, _json, _Keys, _path
from email_brain.store import Store
from masterbrain.datacore.worker_db import worker_store
from masterbrain.source_tier_email_controller import EmailTierReplayConfig
from masterbrain.source_tier_email_pdf_replay import SourceTierEmailPdfReplayStore

_REVIEW_ID = re.compile(r"^stier_[a-f0-9]{32}$")
_SCOPES = frozenset({"brain.document.publish", "email.evidence.read"})


class EmailTierPdfControllerError(ValueError):
    def __init__(self) -> None:
        super().__init__("Email PDF tier replay unavailable; sensitive details suppressed")


class EmailTierPdfConfig(EmailTierReplayConfig):
    pdf_image_id: str = Field(pattern=r"^sha256:[a-f0-9]{64}\z")
    docker_binary: Path

    @field_validator("docker_binary")
    @classmethod
    def absolute_docker_binary(cls, value: Path) -> Path:
        return _path(value)


def _current(identity: WorkerIdentity, initial: Principal) -> Principal:
    principal = identity.authenticate()
    if (
        principal.context.tenant_id != initial.context.tenant_id
        or principal.context.actor_id != initial.context.actor_id
    ):
        raise EmailTierPdfControllerError()
    return principal


def run_source_tier_email_pdf_controller(
    path: Path, dsn: str, review_id: str, *,
    check: bool = False, tenant_bound_db: bool = False,
) -> dict[str, Any]:
    """Check without MIME/PDF read, or seal one exact tenant-bound replay."""
    try:
        if (
            not dsn or type(review_id) is not str or _REVIEW_ID.fullmatch(review_id) is None
            or type(check) is not bool or tenant_bound_db is not True
        ):
            raise EmailTierPdfControllerError()
        config = EmailTierPdfConfig.model_validate(_json(path))
        identity = WorkerIdentity(config, scope=_SCOPES)
        initial = identity.authenticate()
        store = worker_store(Store, dsn, initial.context.tenant_id, tenant_bound_db)
        with store.transaction(initial.context) as conn:
            account = conn.execute(
                "SELECT status FROM mail_accounts WHERE id=%s", (config.account_id,),
            ).fetchone()
            if account is None or account["status"] != "active":
                raise EmailTierPdfControllerError()
        keys: _Keys | None = None
        if config.blob_root is not None and config.keys_file is not None:
            keys = _Keys.model_validate(_json(config.keys_file))
            if (
                keys.tenant_id != initial.context.tenant_id
                or len({key.key_id for key in keys.keys}) != len(keys.keys)
            ):
                raise EmailTierPdfControllerError()
            # Check mode validates a private directory without opening any
            # selected MIME/PDF, review row or blob object.
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
        processor = DockerPdfProcessor(
            config.pdf_image_id, docker_binary=config.docker_binary,
        )

        def authorize() -> None:
            _current(identity, initial)

        result = SourceTierEmailPdfReplayStore(store, processor).record_current_pdf_replay(
            initial.context, review_id, expected_account_id=config.account_id,
            authorize=authorize,
        )
        _current(identity, initial)
        return result
    except Exception:
        raise EmailTierPdfControllerError() from None
