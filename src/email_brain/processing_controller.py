"""Opt-in trusted controller. No enrollment, approval, provider or model calls."""

from __future__ import annotations

import json
import os
import signal
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from email_brain.attachments import Attachment
from email_brain.auth import Credential, Principal, TokenRegistry
from email_brain.blobs import EncryptedBlobStore
from email_brain.normalize import NormalizedMessage
from email_brain.recovery import MimeProcessor
from email_brain.recovery_jobs import RecoveryJobs
from email_brain.sandbox_runner import DockerMimeProcessor
from email_brain.schemas import ClosedModel
from email_brain.store import Store


class ControllerError(ValueError):
    def __init__(self) -> None:
        super().__init__("processing controller unavailable; sensitive details suppressed")


def _path(value: Path) -> Path:
    if (
        not value.is_absolute()
        or len(value.parts) < 2
        or ".." in value.parts
        or "\x00" in str(value)
        or any("dropbox" in part.casefold() for part in value.parts)
    ):
        raise ControllerError()
    # Source checkout state must not become credentials or runtime storage.
    for parent in Path(__file__).resolve().parents:
        if (parent / "PRODUCT.md").is_file() and (parent / "AGENTS.md").is_file():
            if value.is_relative_to(parent):
                raise ControllerError()
            break
    return value


def _private(fd: int, *, directory: bool) -> None:
    info = os.fstat(fd)
    kind = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if (
        not kind
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)
        or (not directory and info.st_nlink != 1)
    ):
        raise ControllerError()


@contextmanager
def _directory(path: Path) -> Iterator[int]:
    _path(path)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        _private(fd, directory=True)
        yield fd
    finally:
        os.close(fd)


def private_bytes(path: Path, limit: int = 65536) -> bytes:
    """Bounded same-descriptor validation/read; no symlink or FIFO traversal."""
    _path(path)
    with _directory(path.parent) as parent:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            _private(fd, directory=False)
            if os.fstat(fd).st_size > limit:
                raise ControllerError()
            chunks: list[bytes] = []
            size = 0
            while chunk := os.read(fd, min(8192, limit - size + 1)):
                size += len(chunk)
                if size > limit:
                    raise ControllerError()
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(fd)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ControllerError()
        result[key] = value
    return result


def _constant(_: str) -> None:
    raise ControllerError()


def _json(path: Path) -> Any:
    return json.loads(
        private_bytes(path).decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
    )


class ControllerConfig(ClosedModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    version: Literal[1]
    account_id: UUID
    image_id: str = Field(pattern=r"^sha256:[a-f0-9]{64}\z")
    docker_binary: Path
    credentials_file: Path
    token_file: Path
    blob_root: Path | None = None
    keys_file: Path | None = None

    @field_validator("version", mode="before")
    @classmethod
    def exact_version(cls, value: Any) -> Any:
        if type(value) is not int or value != 1:
            raise ControllerError()
        return value

    @field_validator("docker_binary", "credentials_file", "token_file", "blob_root", "keys_file")
    @classmethod
    def absolute_path(cls, value: Path | None) -> Path | None:
        return _path(value) if value is not None else None

    @model_validator(mode="after")
    def paired_storage(self) -> ControllerConfig:
        if (self.blob_root is None) != (self.keys_file is None):
            raise ControllerError()
        return self


class _Key(ClosedModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    key_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}\z")
    key_hex: str = Field(pattern=r"^[a-f0-9]{64}\z", repr=False)


class _Keys(ClosedModel):
    tenant_id: UUID
    keys: list[_Key] = Field(min_length=1, max_length=100, repr=False)


class WorkerIdentity:
    def __init__(self, config: ControllerConfig) -> None:
        self.config = config
        self.initial: Principal | None = None

    def authenticate(self) -> Principal:
        data = _json(self.config.credentials_file)
        if not isinstance(data, list) or not 1 <= len(data) <= 100:
            raise ControllerError()
        registry = TokenRegistry([Credential.model_validate(item) for item in data])
        token = private_bytes(self.config.token_file, 513).decode("ascii")
        if token.endswith("\n"):
            token = token[:-1]
        if not token.isprintable() or any(c.isspace() for c in token):
            raise ControllerError()
        principal = registry.authenticate(token)
        if (
            principal is None
            or principal.client_kind != "worker"
            or principal.context.scopes != frozenset({"email.process"})
        ):
            raise ControllerError()
        if self.initial is not None and (
            principal.context.tenant_id != self.initial.context.tenant_id
            or principal.context.actor_id != self.initial.context.actor_id
        ):
            raise ControllerError()
        self.initial = principal
        return principal


class _AuthenticatedProcessor:
    def __init__(self, processor: MimeProcessor, identity: WorkerIdentity) -> None:
        self.processor, self.identity = processor, identity

    @property
    def parser_version(self) -> str:
        return self.processor.parser_version

    @property
    def max_raw_bytes(self) -> int:
        return self.processor.max_raw_bytes

    def prepare(self, raw: bytes) -> tuple[NormalizedMessage | None, list[Attachment], bool]:
        self.identity.authenticate()
        result = self.processor.prepare(raw)
        self.identity.authenticate()
        return result


@contextmanager
def shutdown_signals(stop: Event) -> Iterator[None]:
    previous = {}
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, lambda _sig, _frame: stop.set())
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def run_controller(
    path: Path,
    dsn: str,
    *,
    check: bool = False,
    max_iterations: int = 1,
    idle_seconds: int = 5,
    stop: Event | None = None,
) -> dict[str, Any]:
    """Run explicit bounded work. CLI owns signal handling; tests may inject stop."""
    try:
        if (
            type(max_iterations) is not int
            or not 1 <= max_iterations <= 1000
            or type(idle_seconds) is not int
            or not 1 <= idle_seconds <= 60
            or not dsn
        ):
            raise ControllerError()
        config = ControllerConfig.model_validate(_json(path))
        identity = WorkerIdentity(config)
        principal = identity.authenticate()
        store = Store(dsn)
        with store.transaction(principal.context) as conn:
            if not conn.execute(
                "SELECT 1 FROM mail_accounts WHERE id=%s AND status='active'",
                (config.account_id,),
            ).fetchone():
                raise ControllerError()
        if config.blob_root is not None and config.keys_file is not None:
            keys = _Keys.model_validate(_json(config.keys_file))
            if keys.tenant_id != principal.context.tenant_id or len(
                {key.key_id for key in keys.keys}
            ) != len(keys.keys):
                raise ControllerError()
            # Check mode must not create an empty object root or alter storage.
            with _directory(config.blob_root):
                pass
            store = Store(
                dsn,
                blobs=EncryptedBlobStore(
                    config.blob_root,
                    {(keys.tenant_id, k.key_id): bytes.fromhex(k.key_hex) for k in keys.keys},
                    {},
                ),
            )
        identity.authenticate()
        if check:
            return {"configuration_valid": True, "execution_verified": False, "claims": 0}
        processor = _AuthenticatedProcessor(
            DockerMimeProcessor(config.image_id, docker_binary=config.docker_binary), identity
        )
        jobs = RecoveryJobs(store, processor.parser_version)
        stop = stop if stop is not None else Event()
        counts = dict.fromkeys(
            (
                "completed",
                "cancelled",
                "expired",
                "failed",
                "stale",
                "revoked",
                "retry_wait",
                "running",
                "queued",
                "no_result",
            ),
            0,
        )
        polls = 0
        for _ in range(max_iterations):
            if stop.is_set():
                break
            principal = identity.authenticate()
            if stop.is_set():
                break
            result = jobs.run_once(principal, config.account_id, processor)
            polls += 1
            identity.authenticate()
            status = result["status"] if result is not None else "no_result"
            if status not in counts:
                raise ControllerError()
            counts[status] += 1
            if polls < max_iterations and stop.wait(idle_seconds):
                break
        return {
            "polls": polls,
            "results": counts,
            "stopped": stop.is_set(),
            "mailbox_effects": False,
        }
    except Exception:
        # Parsing/configuration/SQL/OS exceptions may include secrets or mail.
        raise ControllerError() from None
