"""Tenant-bound private worker command for one approved synthetic Email XLSX."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from email_brain.auth import Principal
from email_brain.blobs import EncryptedBlobStore
from email_brain.processing_controller import WorkerIdentity, _directory, _json, _Keys, _path
from email_brain.store import Store
from masterbrain.datacore.document_processor import DockerDocumentProcessor
from masterbrain.datacore.worker_db import worker_store
from masterbrain.email_xlsx_results import EmailXlsxResults
from masterbrain.source_tier_email_controller import EmailTierReplayConfig

_APPROVAL_ID = re.compile(r"^xapp_[a-f0-9]{32}$")
_SCOPES = frozenset({"email.document.process", "email.evidence.read"})


class EmailXlsxExtractionControllerError(ValueError):
    def __init__(self) -> None:
        super().__init__("Email XLSX extraction unavailable; sensitive details suppressed")


class EmailXlsxExtractionConfig(EmailTierReplayConfig):
    document_image_id: str = Field(pattern=r"^sha256:[a-f0-9]{64}\z")
    docker_binary: Path

    @field_validator("docker_binary")
    @classmethod
    def absolute_docker_binary(cls, value: Path) -> Path:
        return _path(value)


def _current(identity: WorkerIdentity, initial: Principal) -> None:
    principal = identity.authenticate()
    if (
        principal.context.tenant_id != initial.context.tenant_id
        or principal.context.actor_id != initial.context.actor_id
    ):
        raise EmailXlsxExtractionControllerError()


def run_email_xlsx_extraction_controller(
    path: Path, dsn: str, approval_id: str, *,
    check: bool = False, tenant_bound_db: bool = False,
) -> dict[str, Any]:
    """Check without selected MIME read, or seal one exact approved result."""
    try:
        if (
            not dsn or type(approval_id) is not str or _APPROVAL_ID.fullmatch(approval_id) is None
            or type(check) is not bool or tenant_bound_db is not True
        ):
            raise EmailXlsxExtractionControllerError()
        config = EmailXlsxExtractionConfig.model_validate(_json(path))
        identity = WorkerIdentity(config, scope=_SCOPES)
        initial = identity.authenticate()
        store = worker_store(Store, dsn, initial.context.tenant_id, tenant_bound_db)
        with store.transaction(initial.context) as conn:
            account = conn.execute(
                "SELECT provider_account_id,secret_ref FROM mail_accounts "
                "WHERE id=%s AND status='active'", (config.account_id,),
            ).fetchone()
            if (
                account is None or account["provider_account_id"] is not None
                or not account["secret_ref"].startswith("synthetic:")
            ):
                raise EmailXlsxExtractionControllerError()
        keys: _Keys | None = None
        if config.blob_root is not None and config.keys_file is not None:
            keys = _Keys.model_validate(_json(config.keys_file))
            if (
                keys.tenant_id != initial.context.tenant_id
                or len({key.key_id for key in keys.keys}) != len(keys.keys)
            ):
                raise EmailXlsxExtractionControllerError()
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
        processor = DockerDocumentProcessor(
            config.document_image_id, docker_binary=config.docker_binary,
        )

        def authorize() -> None:
            _current(identity, initial)

        result = EmailXlsxResults(store, processor).record(
            initial.context, approval_id, expected_account_id=config.account_id,
            authorize=authorize,
        )
        _current(identity, initial)
        return result
    except Exception:
        raise EmailXlsxExtractionControllerError() from None
