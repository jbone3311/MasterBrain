"""Tenant-bound private worker command for one reviewed synthetic Email XLSX."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict, field_validator

from email_brain.auth import Principal
from email_brain.processing_controller import WorkerIdentity, _json, _path
from email_brain.schemas import ClosedModel
from email_brain.store import Store
from masterbrain.datacore.worker_db import worker_store
from masterbrain.email_xlsx_document_bridge import EmailXlsxDocumentBridge

_REVIEW_ID = re.compile(r"^xrev_[a-f0-9]{32}$")
_SCOPES = frozenset({
    "brain.source.ingest", "brain.document.publish", "email.evidence.read",
})


class EmailXlsxPublicationControllerError(ValueError):
    def __init__(self) -> None:
        super().__init__("Email XLSX publication unavailable; sensitive details suppressed")


class EmailXlsxPublicationConfig(ClosedModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    version: Literal[1]
    account_id: UUID
    credentials_file: Path
    token_file: Path

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value: Any) -> Any:
        if type(value) is not int or value != 1:
            raise EmailXlsxPublicationControllerError()
        return value

    @field_validator("credentials_file", "token_file")
    @classmethod
    def private_path(cls, value: Path) -> Path:
        return _path(value)


def _current(identity: WorkerIdentity, initial: Principal) -> None:
    principal = identity.authenticate()
    if (
        principal.context.tenant_id != initial.context.tenant_id
        or principal.context.actor_id != initial.context.actor_id
    ):
        raise EmailXlsxPublicationControllerError()


def run_email_xlsx_publication_controller(
    path: Path, dsn: str, review_id: str, idempotency_key: UUID, *,
    check: bool = False, tenant_bound_db: bool = False,
) -> dict[str, Any]:
    """Check without selected-result read; execute only one reviewed derivative."""
    try:
        if (
            not dsn or type(review_id) is not str or _REVIEW_ID.fullmatch(review_id) is None
            or not isinstance(idempotency_key, UUID)
            or type(check) is not bool or tenant_bound_db is not True
        ):
            raise EmailXlsxPublicationControllerError()
        config = EmailXlsxPublicationConfig.model_validate(_json(path))
        identity = WorkerIdentity(config, scope=_SCOPES)
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
                "data_effects": False,
            }

        def authorize() -> None:
            _current(identity, initial)

        result = EmailXlsxDocumentBridge(store).publish(
            initial.context, review_id, idempotency_key,
            expected_account_id=config.account_id, authorize=authorize,
        )
        _current(identity, initial)
        return result
    except Exception:
        raise EmailXlsxPublicationControllerError() from None
