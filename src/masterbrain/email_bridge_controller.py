"""Explicit private operator for one current Email-to-DataCore bridge."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from email_brain.auth import Principal
from email_brain.processing_controller import WorkerIdentity, _json, _path
from email_brain.schemas import ClosedModel
from email_brain.store import Store
from masterbrain.datacore.persistence import DataCoreStore


class EmailBridgeControllerError(ValueError):
    def __init__(self) -> None:
        super().__init__("Email bridge controller unavailable; sensitive details suppressed")


class EmailBridgeControllerConfig(ClosedModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    version: Literal[1]
    credentials_file: Path
    token_file: Path
    code_revision: str = Field(min_length=1, max_length=200)

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value: Any) -> Any:
        if type(value) is not int or value != 1:
            raise EmailBridgeControllerError()
        return value

    @field_validator("credentials_file", "token_file")
    @classmethod
    def private_path(cls, value: Path) -> Path:
        return _path(value)

    @field_validator("code_revision")
    @classmethod
    def safe_revision(cls, value: str) -> str:
        if "\x00" in value:
            raise EmailBridgeControllerError()
        return value


def _current(identity: WorkerIdentity, initial: Principal) -> Principal:
    principal = identity.authenticate()
    if (
        principal.context.tenant_id != initial.context.tenant_id
        or principal.context.actor_id != initial.context.actor_id
    ):
        raise EmailBridgeControllerError()
    return principal


def run_email_bridge_controller(
    path: Path,
    dsn: str,
    legacy_version_id: UUID,
    idempotency_key: UUID,
    *,
    check: bool = False,
) -> dict[str, Any]:
    """Validate or bridge one explicitly selected current Email evidence version."""
    return _run_email_bridge_controller(
        path,
        dsn,
        legacy_version_id,
        idempotency_key,
        operation="bridge_current_email_version",
        check=check,
    )


def run_email_attachment_bridge_controller(
    path: Path,
    dsn: str,
    legacy_attachment_id: UUID,
    idempotency_key: UUID,
    *,
    check: bool = False,
) -> dict[str, Any]:
    """Validate or bridge one explicitly selected Email attachment occurrence."""
    return _run_email_bridge_controller(
        path,
        dsn,
        legacy_attachment_id,
        idempotency_key,
        operation="bridge_email_attachment",
        check=check,
    )


def run_email_document_bridge_controller(
    path: Path,
    dsn: str,
    legacy_extraction_id: UUID,
    idempotency_key: UUID,
    *,
    check: bool = False,
) -> dict[str, Any]:
    """Validate or bridge one explicitly selected approved Email PDF extraction."""
    return _run_email_bridge_controller(
        path,
        dsn,
        legacy_extraction_id,
        idempotency_key,
        operation="bridge_email_document_extraction",
        check=check,
    )


def _run_email_bridge_controller(
    path: Path,
    dsn: str,
    legacy_id: UUID,
    idempotency_key: UUID,
    *,
    operation: Literal[
        "bridge_current_email_version",
        "bridge_email_attachment",
        "bridge_email_document_extraction",
    ],
    check: bool,
) -> dict[str, Any]:
    try:
        if not dsn or not isinstance(legacy_id, UUID) or not isinstance(idempotency_key, UUID):
            raise EmailBridgeControllerError()
        config = EmailBridgeControllerConfig.model_validate(_json(path))
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
                "operation": operation,
                "source_effects": False,
                "data_effects": False,
            }
        _current(identity, initial)
        core = DataCoreStore(store)
        bridge = getattr(core, operation)
        result = bridge(
            initial.context,
            legacy_id,
            idempotency_key,
            code_revision=config.code_revision,
        )
        _current(identity, initial)
        output = {
            "operation": operation,
            "source_id": result.source_id,
            "item_id": result.item_id,
            "version_id": result.version_id,
            "evidence_id": result.evidence_id,
            "document_id": result.document_id,
            "chunks": result.chunks,
            "recorded": result.changed,
            "source_effects": False,
        }
        if operation == "bridge_email_attachment":
            output.update({"part_id": result.part_id, "outcome": result.outcome})
        elif operation == "bridge_email_document_extraction":
            output["extraction_status"] = result.extraction_status
        return output
    except Exception:
        raise EmailBridgeControllerError() from None
