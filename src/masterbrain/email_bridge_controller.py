"""Explicit private operator for one current Email-to-DataCore bridge."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from email_brain.auth import Principal
from email_brain.processing_controller import WorkerIdentity, _json, _path
from email_brain.schemas import ClosedModel
from email_brain.store import Conflict, NotFound, Store
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


class EmailBridgeBatchItem(ClosedModel):
    legacy_version_id: UUID
    idempotency_key: UUID


def email_bridge_batch_sha256(
    version: int,
    account_id: UUID,
    code_revision: str,
    items: list[EmailBridgeBatchItem],
) -> str:
    payload = {
        "version": version,
        "account_id": str(account_id),
        "code_revision": code_revision,
        "items": [
            {
                "legacy_version_id": str(item.legacy_version_id),
                "idempotency_key": str(item.idempotency_key),
            }
            for item in items
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class EmailBridgeBatchPlan(ClosedModel):
    version: Literal[1]
    account_id: UUID
    code_revision: str = Field(min_length=1, max_length=200)
    items: list[EmailBridgeBatchItem] = Field(min_length=1, max_length=100)
    plan_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("code_revision")
    @classmethod
    def safe_revision(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("invalid code revision")
        return value

    @model_validator(mode="after")
    def sealed_and_unique(self) -> EmailBridgeBatchPlan:
        version_ids = [item.legacy_version_id for item in self.items]
        keys = [item.idempotency_key for item in self.items]
        if len(set(version_ids)) != len(version_ids) or len(set(keys)) != len(keys):
            raise ValueError("duplicate batch identity")
        expected = email_bridge_batch_sha256(
            self.version, self.account_id, self.code_revision, self.items
        )
        if self.plan_sha256 != expected:
            raise ValueError("invalid batch digest")
        return self

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


def run_email_bridge_plan_controller(
    path: Path,
    dsn: str,
    account_id: UUID,
    *,
    after: UUID | None = None,
    limit: int = 25,
    check: bool = False,
) -> dict[str, Any]:
    """Validate or preview current Email versions for explicit bridge operation."""
    try:
        if (
            not dsn
            or not isinstance(account_id, UUID)
            or (after is not None and not isinstance(after, UUID))
            or not 1 <= limit <= 100
        ):
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
                "operation": "email_bridge_plan",
                "source_effects": False,
                "data_effects": False,
            }
        _current(identity, initial)
        result = DataCoreStore(store).email_bridge_plan(
            initial.context, account_id, after=after, limit=limit
        )
        _current(identity, initial)
        return {"operation": "email_bridge_plan", **result}
    except Exception:
        raise EmailBridgeControllerError() from None


def run_email_part_bridge_plan_controller(
    path: Path,
    dsn: str,
    account_id: UUID,
    kind: Literal["attachment", "document"],
    *,
    after: UUID | None = None,
    limit: int = 25,
    check: bool = False,
) -> dict[str, Any]:
    """Validate or preview current Email attachment/document bridge candidates."""
    try:
        if (
            not dsn
            or not isinstance(account_id, UUID)
            or kind not in {"attachment", "document"}
            or (after is not None and not isinstance(after, UUID))
            or not 1 <= limit <= 100
        ):
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
                "operation": "email_part_bridge_plan",
                "kind": kind,
                "source_effects": False,
                "data_effects": False,
            }
        _current(identity, initial)
        result = DataCoreStore(store).email_part_bridge_plan(
            initial.context, account_id, kind, after=after, limit=limit
        )
        _current(identity, initial)
        return {"operation": "email_part_bridge_plan", **result}
    except Exception:
        raise EmailBridgeControllerError() from None


def run_email_bridge_batch_controller(
    path: Path,
    plan_path: Path,
    dsn: str,
    *,
    check: bool = False,
) -> dict[str, Any]:
    """Validate or execute one sealed, explicit Email message bridge batch."""
    try:
        if not dsn:
            raise EmailBridgeControllerError()
        config = EmailBridgeControllerConfig.model_validate(_json(path))
        plan = EmailBridgeBatchPlan.model_validate(_json(plan_path))
        if plan.code_revision != config.code_revision:
            raise EmailBridgeControllerError()
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
                "operation": "email_bridge_batch",
                "plan_sha256": plan.plan_sha256,
                "requested": len(plan.items),
                "source_effects": False,
                "data_effects": False,
            }
        core = DataCoreStore(store)
        results: list[dict[str, Any]] = []
        recorded = 0
        replayed = 0
        for item in plan.items:
            _current(identity, initial)
            try:
                result = core.bridge_current_email_version(
                    initial.context,
                    item.legacy_version_id,
                    item.idempotency_key,
                    code_revision=config.code_revision,
                    expected_account_id=plan.account_id,
                )
            except (Conflict, NotFound, ValueError):
                return {
                    "operation": "email_bridge_batch",
                    "plan_sha256": plan.plan_sha256,
                    "requested": len(plan.items),
                    "completed": len(results),
                    "recorded": recorded,
                    "replayed": replayed,
                    "results": results,
                    "complete": False,
                    "failed_version_id": str(item.legacy_version_id),
                    "error_code": "bridge_refused",
                    "source_effects": False,
                }
            _current(identity, initial)
            recorded += int(result.changed)
            replayed += int(not result.changed)
            results.append(
                {
                    "legacy_version_id": str(item.legacy_version_id),
                    "recorded": result.changed,
                }
            )
        return {
            "operation": "email_bridge_batch",
            "plan_sha256": plan.plan_sha256,
            "requested": len(plan.items),
            "completed": len(results),
            "recorded": recorded,
            "replayed": replayed,
            "results": results,
            "complete": True,
            "failed_version_id": None,
            "error_code": None,
            "source_effects": False,
        }
    except Exception:
        raise EmailBridgeControllerError() from None


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
