"""Owner-reviewed local scope enrollment; no provider client or token discovery."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from pydantic import ConfigDict, Field, field_validator

from email_brain.auth import Credential, Principal, TokenRegistry
from email_brain.processing_controller import WorkerIdentity, _json, _path, private_bytes
from email_brain.read_controller import ReadControllerConfig
from email_brain.schemas import ClosedModel


class EnrollmentError(ValueError):
    def __init__(self) -> None:
        super().__init__("Fastmail source action unavailable")


class EnrollmentConfig(ClosedModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    version: Literal[1]
    expected_tenant_id: UUID
    expected_owner_actor_id: UUID
    address: str = Field(strict=True, min_length=3, max_length=320)
    read_config_file: Path
    owner_credentials_file: Path
    owner_token_file: Path

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value: Any) -> Any:
        if type(value) is not int or value != 1:
            raise EnrollmentError()
        return value

    @field_validator("address")
    @classmethod
    def exact_address(cls, value: str) -> str:
        if (
            not value.isprintable() or value != value.strip()
            or any(char.isspace() for char in value) or value.count("@") != 1
            or not all(value.split("@"))
        ):
            raise EnrollmentError()
        return value

    @field_validator("read_config_file", "owner_credentials_file", "owner_token_file")
    @classmethod
    def private_path(cls, value: Path) -> Path:
        return _path(value)


def _owner(config: EnrollmentConfig) -> Principal:
    data = _json(config.owner_credentials_file)
    if not isinstance(data, list) or not 1 <= len(data) <= 100:
        raise EnrollmentError()
    registry = TokenRegistry([Credential.model_validate(item) for item in data])
    token = private_bytes(config.owner_token_file, 513).decode("ascii")
    if token.endswith("\n"):
        token = token[:-1]
    if not token.isprintable() or any(char.isspace() for char in token):
        raise EnrollmentError()
    principal = registry.authenticate(token)
    if (
        principal is None or principal.client_kind != "human"
        or "email.source.manage" not in principal.context.scopes
        or principal.context.tenant_id != config.expected_tenant_id
        or principal.context.actor_id != config.expected_owner_actor_id
    ):
        raise EnrollmentError()
    return principal


def _existing(conn: psycopg.Connection[Any], tenant_id: UUID, account_id: UUID,
              address: str) -> dict[str, Any] | None:
    rows = conn.execute(
        "SELECT id,tenant_id,provider,address,secret_ref,provider_account_id,"
        "read_scope_sha256,status FROM mail_accounts WHERE id=%s OR "
        "(tenant_id=%s AND provider='fastmail' AND address=%s)",
        (account_id, tenant_id, address),
    ).fetchall()
    if len(rows) > 1:
        raise EnrollmentError()
    return rows[0] if rows else None


def _matching(row: dict[str, Any], config: EnrollmentConfig,
              read: ReadControllerConfig, fingerprint: str) -> bool:
    return (
        row["id"] == read.account_id
        and row["tenant_id"] == config.expected_tenant_id
        and row["provider"] == "fastmail"
        and row["address"] == config.address
        and row["secret_ref"] == read.provider_secret_ref
        and row["provider_account_id"] == read.provider_account_id
        and row["read_scope_sha256"] == fingerprint
        and row["status"] in ("active", "disconnected")
    )


def _binding_sha256(config: EnrollmentConfig, read: ReadControllerConfig,
                    fingerprint: str) -> str:
    fields = {
        "version": 1,
        "tenant_id": str(config.expected_tenant_id),
        "owner_actor_id": str(config.expected_owner_actor_id),
        "account_id": str(read.account_id),
        "address": config.address,
        "provider_account_id": read.provider_account_id,
        "provider_secret_ref": read.provider_secret_ref,
        "scope_sha256": fingerprint,
    }
    encoded = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def run_fastmail_enrollment(
    path: Path,
    admin_dsn: str,
    *,
    action: Literal["check", "enroll", "disconnect"],
    confirmed_account_id: UUID | None = None,
    confirmed_scope_sha256: str | None = None,
    confirmed_binding_sha256: str | None = None,
) -> dict[str, Any]:
    """One transaction; only enroll/disconnect mutate SQL. Never calls Fastmail."""
    try:
        if action not in ("check", "enroll", "disconnect") or not admin_dsn:
            raise EnrollmentError()
        config = EnrollmentConfig.model_validate(_json(path))
        read = ReadControllerConfig.model_validate(_json(config.read_config_file))
        if read.version != 2 or read.read_scope is None:
            raise EnrollmentError()
        fingerprint = read.read_scope.window().fingerprint()
        binding_sha256 = _binding_sha256(config, read, fingerprint)
        if action == "check":
            if any(value is not None for value in (
                confirmed_account_id, confirmed_scope_sha256, confirmed_binding_sha256,
            )):
                raise EnrollmentError()
        elif (
            confirmed_account_id != read.account_id
            or confirmed_scope_sha256 != fingerprint
            or confirmed_binding_sha256 != binding_sha256
        ):
            raise EnrollmentError()
        owner = _owner(config)
        worker = WorkerIdentity(read, scope="email.ingest").authenticate()
        if worker.context.tenant_id != config.expected_tenant_id:
            raise EnrollmentError()
        with psycopg.connect(admin_dsn, row_factory=dict_row) as conn, conn.transaction():
            if action == "check":
                conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL row_security = off")
            conn.execute("SET LOCAL lock_timeout = '5s'")
            conn.execute("SET LOCAL statement_timeout = '15s'")
            membership = conn.execute(
                "SELECT role FROM tenant_memberships WHERE tenant_id=%s AND user_id=%s",
                (config.expected_tenant_id, config.expected_owner_actor_id),
            ).fetchone()
            if membership is None or membership["role"] != "owner":
                raise EnrollmentError()
            if action != "check":
                conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (f"{config.expected_tenant_id}:{read.account_id}",),
                )
            row = _existing(conn, config.expected_tenant_id, read.account_id, config.address)
            if row is not None and not _matching(row, config, read, fingerprint):
                raise EnrollmentError()
            if action == "check":
                state = row["status"] if row is not None else "absent"
                return {
                    "action": action, "account_state": state,
                    "account_id": str(read.account_id), "scope_sha256": fingerprint,
                    "binding_sha256": binding_sha256,
                    "provider_requests": 0, "claims": 0,
                }
            if action == "enroll":
                if row is not None:
                    raise EnrollmentError()
                conn.execute(
                    "INSERT INTO mail_accounts"
                    "(id,tenant_id,provider,address,secret_ref,provider_account_id,"
                    "read_scope_sha256,status) "
                    "VALUES (%s,%s,'fastmail',%s,%s,%s,%s,'active')",
                    (
                        read.account_id, config.expected_tenant_id, config.address,
                        read.provider_secret_ref, read.provider_account_id, fingerprint,
                    ),
                )
                event = "fastmail.scope.enroll"
                changed = True
                state = "active"
            else:
                if row is None:
                    raise EnrollmentError()
                state = "disconnected"
                changed = row["status"] == "active"
                if changed:
                    conn.execute(
                        "UPDATE mail_accounts SET status='disconnected' "
                        "WHERE id=%s AND tenant_id=%s AND status='active'",
                        (read.account_id, config.expected_tenant_id),
                    )
                event = "fastmail.scope.disconnect"
            if changed:
                conn.execute(
                    "INSERT INTO audit_events"
                    "(tenant_id,actor_id,request_id,event_type,resource_type,resource_id,"
                    "outcome,metadata) VALUES (%s,%s,%s,%s,'mail_account',%s,'success',%s::jsonb)",
                    (
                        config.expected_tenant_id, config.expected_owner_actor_id,
                        owner.context.request_id, event, str(read.account_id),
                        json.dumps({"scope_sha256": fingerprint}),
                    ),
                )
            return {
                "action": action, "account_state": state, "changed": changed,
                "account_id": str(read.account_id), "scope_sha256": fingerprint,
                "binding_sha256": binding_sha256,
                "provider_requests": 0, "claims": 0,
            }
    except Exception:
        raise EnrollmentError() from None
