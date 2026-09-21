"""Explicit bounded Fastmail reads, never enrollment or provider writes."""

from __future__ import annotations

import hmac
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import Any, Literal
from uuid import UUID

import httpx
from pydantic import ConfigDict, Field, field_validator, model_validator

from email_brain.auth import Principal
from email_brain.blobs import EncryptedBlobStore
from email_brain.connectors.fastmail import MAX_BLOB_BYTES, FastmailReadClient
from email_brain.connectors.jmap import identifier
from email_brain.normalize import MAX_RAW_BYTES
from email_brain.processing_controller import (
    ControllerError,
    WorkerIdentity,
    _directory,
    _json,
    _Keys,
    _path,
    private_bytes,
    validate_run_options,
)
from email_brain.schemas import ClosedModel
from email_brain.store import Store
from email_brain.sync import ReadWorker


class ReadControllerConfig(ClosedModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    version: Literal[1]
    job_kind: Literal["fastmail-read"]
    account_id: UUID
    provider_account_id: str
    provider_secret_ref: str = Field(min_length=1, max_length=512)
    credentials_file: Path
    token_file: Path
    provider_token_file: Path
    max_raw_bytes: int = Field(
        default=MAX_RAW_BYTES, strict=True, ge=MAX_RAW_BYTES, le=MAX_BLOB_BYTES
    )
    blob_root: Path | None = None
    keys_file: Path | None = None
    active_key_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{1,64}\z")

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value: Any) -> Any:
        if type(value) is not int or value != 1:
            raise ControllerError()
        return value

    @field_validator("provider_account_id")
    @classmethod
    def provider_identifier(cls, value: str) -> str:
        if not value.isprintable() or value != value.strip():
            raise ControllerError()
        value.encode("utf-8", errors="strict")
        return identifier(value)

    @field_validator("provider_secret_ref")
    @classmethod
    def secret_reference(cls, value: str) -> str:
        if not value.isprintable() or value != value.strip():
            raise ControllerError()
        value.encode("utf-8", errors="strict")
        return value

    @field_validator(
        "credentials_file", "token_file", "provider_token_file", "blob_root", "keys_file"
    )
    @classmethod
    def private_path(cls, value: Path | None) -> Path | None:
        return _path(value) if value is not None else None

    @model_validator(mode="after")
    def storage_fields(self) -> ReadControllerConfig:
        selected = (
            self.blob_root is not None,
            self.keys_file is not None,
            self.active_key_id is not None,
        )
        if (any(selected) and not all(selected)) or (
            self.max_raw_bytes > MAX_RAW_BYTES and not all(selected)
        ):
            raise ControllerError()
        if self.token_file == self.provider_token_file:
            raise ControllerError()
        return self


def _provider_token(config: ReadControllerConfig) -> str:
    token = private_bytes(config.provider_token_file, 4097).decode("ascii")
    if token.endswith("\n"):
        token = token[:-1]
    if not 16 <= len(token) <= 4096 or not token.isprintable() or any(c.isspace() for c in token):
        raise ControllerError()
    return token


def _binding(store: Store, principal: Principal, config: ReadControllerConfig) -> bool:
    """Read-only preflight/guard: no enrollment, lease acquisition or pause reset."""
    with store.transaction(principal.context) as conn:
        row = conn.execute(
            "SELECT a.provider_account_id,a.secret_ref,coalesce(w.paused,false) AS paused "
            "FROM mail_accounts a LEFT JOIN sync_workers w ON w.account_id=a.id "
            "AND w.tenant_id=a.tenant_id WHERE a.id=%s AND a.provider='fastmail' "
            "AND a.status='active'",
            (config.account_id,),
        ).fetchone()
        if (
            row is None
            or row["provider_account_id"] != config.provider_account_id
            or row["secret_ref"] != config.provider_secret_ref
            or type(row["paused"]) is not bool
        ):
            raise ControllerError()
        return row["paused"]


def _store(config: ReadControllerConfig, dsn: str, principal: Principal) -> Store:
    store = Store(dsn)
    _binding(store, principal, config)
    if config.blob_root is not None and config.keys_file is not None:
        keys = _Keys.model_validate(_json(config.keys_file))
        ids = {key.key_id for key in keys.keys}
        if (
            keys.tenant_id != principal.context.tenant_id
            or len(ids) != len(keys.keys)
            or config.active_key_id not in ids
        ):
            raise ControllerError()
        with _directory(config.blob_root):
            pass
        store = Store(
            dsn,
            blobs=EncryptedBlobStore(
                config.blob_root,
                {(keys.tenant_id, key.key_id): bytes.fromhex(key.key_hex) for key in keys.keys},
                {keys.tenant_id: config.active_key_id},
            ),
        )
    return store


class _ReadGuardDenied(RuntimeError):
    """Authorization failure must not be misclassified as malformed MIME."""


class _GuardedFastmail(FastmailReadClient):
    def __init__(
        self,
        token: str,
        guard: Callable[[], None],
        *,
        transport: httpx.BaseTransport | None,
        max_raw_bytes: int,
    ) -> None:
        self.guard = guard
        super().__init__(token, transport=transport, max_raw_bytes=max_raw_bytes)

    def _request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        *,
        byte_limit: int = MAX_RAW_BYTES,
    ) -> bytes:
        self.guard()
        result = super()._request(method, url, payload, byte_limit=byte_limit)
        self.guard()
        return result


def run_read_controller(
    path: Path,
    dsn: str,
    *,
    check: bool = False,
    allow_provider_read: bool = False,
    max_iterations: int = 1,
    idle_seconds: int = 5,
    stop: Event | None = None,
    transport_factory: Callable[[], httpx.BaseTransport] | None = None,
) -> dict[str, Any]:
    """Transport injection is test/library-only, never a config URL or CLI option."""
    try:
        validate_run_options(dsn, max_iterations, idle_seconds)
        if (
            type(check) is not bool
            or type(allow_provider_read) is not bool
            or (not check and not allow_provider_read)
        ):
            raise ControllerError()
        config = ReadControllerConfig.model_validate(_json(path))
        identity = WorkerIdentity(config, scope="email.ingest")
        principal = identity.authenticate()
        store = _store(config, dsn, principal)
        _provider_token(config)
        identity.authenticate()
        if check:
            return {
                "configuration_valid": True,
                "execution_verified": False,
                "claims": 0,
                "provider_requests": 0,
            }
        stop = stop if stop is not None else Event()
        counts = dict.fromkeys(
            (
                "progress",
                "caught_up",
                "retry",
                "not_due",
                "paused",
                "auth_required",
                "protocol_error",
                "parse_error",
                "resync_required",
            ),
            0,
        )
        attention = False
        polls = 0
        for _ in range(max_iterations):
            if stop.is_set():
                break
            principal = identity.authenticate()
            # Reopen the keyring between steps, including deliberate key rotation.
            store = _store(config, dsn, principal)
            if _binding(store, principal, config):
                counts["paused"] += 1
                attention = True
                break
            token = _provider_token(config)

            def guard(step_store: Store = store, step_token: str = token) -> None:
                try:
                    current = identity.authenticate()
                    if _binding(step_store, current, config) or not hmac.compare_digest(
                        step_token, _provider_token(config)
                    ):
                        raise ControllerError()
                except Exception:
                    raise _ReadGuardDenied("read authorization unavailable") from None

            if stop.is_set():
                break
            client = _GuardedFastmail(
                token,
                guard,
                transport=transport_factory() if transport_factory is not None else None,
                max_raw_bytes=config.max_raw_bytes,
            )
            try:
                outcome = ReadWorker(store, client, authorize=guard).step(
                    principal.context, config.account_id
                )
            finally:
                client.close()
            polls += 1
            identity.authenticate()
            if outcome not in counts or outcome == "paused":
                raise ControllerError()
            counts[outcome] += 1
            if outcome in {"auth_required", "protocol_error", "parse_error", "resync_required"}:
                attention = True
                break
            if polls < max_iterations and stop.wait(idle_seconds):
                break
        return {
            "polls": polls,
            "results": counts,
            "stopped": stop.is_set(),
            "attention_required": attention,
            "mailbox_effects": False,
        }
    except Exception:
        raise ControllerError() from None
