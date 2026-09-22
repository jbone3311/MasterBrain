"""Explicit privileged local controller; never enable Docker in the public API.

Only a caller-approved immutable image is used. Email travels through bounded
pipes after isolation inspection, never through arguments, logs or temporary files.
"""

from __future__ import annotations

import json
import os
import re
import selectors
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar
from uuid import uuid4

from email_brain.attachments import Attachment
from email_brain.mime_sandbox import (
    MAX_INPUT_BYTES,
    MAX_OUTPUT_BYTES,
    MimeUnavailable,
    decode_response,
)
from email_brain.normalize import NormalizedMessage
from email_brain.pdf_contract import MAX_OUTPUT_BYTES as PDF_OUTPUT_BYTES
from email_brain.pdf_contract import MAX_REQUEST_BYTES as PDF_REQUEST_BYTES
from masterbrain.datacore.archive_contract import MAX_OUTPUT_BYTES as ARCHIVE_OUTPUT_BYTES
from masterbrain.datacore.archive_contract import MAX_REQUEST_BYTES as ARCHIVE_REQUEST_BYTES
from masterbrain.datacore.document_contract import MAX_OUTPUT_BYTES as DOCUMENT_OUTPUT_BYTES
from masterbrain.datacore.document_contract import MAX_REQUEST_BYTES as DOCUMENT_REQUEST_BYTES

_IMAGE = re.compile(r"sha256:[a-f0-9]{64}\Z", re.ASCII)
_CONTAINER = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_LABEL = "org.cw.email-brain.mime-run"
_MEMORY = 512 * 1024 * 1024
_CONTROL_BYTES = 1024 * 1024
_ENV = {
    "PATH": "/app/.venv/bin:/usr/local/bin:/usr/bin:/bin",
    "LANG": "C.UTF-8",
    "GPG_KEY": "",
    "PYTHON_VERSION": "",
    "PYTHON_SHA256": "",
}
_COMMAND = ["-I", "-B", "-m", "email_brain.mime_sandbox"]
_T = TypeVar("_T")


@dataclass(frozen=True)
class _Profile:
    name: str
    command: tuple[str, ...]
    input_bytes: int
    output_bytes: int


_MIME_PROFILE = _Profile("mime", tuple(_COMMAND), MAX_INPUT_BYTES, MAX_OUTPUT_BYTES)
_PDF_PROFILE = _Profile(
    "pdf", ("-I", "-B", "-m", "email_brain.pdf_worker"), PDF_REQUEST_BYTES, PDF_OUTPUT_BYTES
)
_DOCUMENT_PROFILE = _Profile(
    "document",
    ("-I", "-B", "-m", "masterbrain.datacore.document_worker"),
    DOCUMENT_REQUEST_BYTES,
    DOCUMENT_OUTPUT_BYTES,
)
_ARCHIVE_PROFILE = _Profile(
    "archive",
    ("-I", "-B", "-m", "masterbrain.datacore.archive_worker"),
    ARCHIVE_REQUEST_BYTES,
    ARCHIVE_OUTPUT_BYTES,
)


def _pump(args: list[str], raw: bytes, *, limit: int, timeout: float) -> bytes:
    """Concurrently feed/drain bounded pipes; kill/reap only our CLI process."""
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={"PATH": "/usr/bin:/bin"},
            close_fds=True,
        )
        assert process.stdin is not None and process.stdout is not None
        deadline = time.monotonic() + timeout
        chunks: list[bytes] = []
        size = offset = 0
        with selectors.DefaultSelector() as selector:
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            if raw:
                os.set_blocking(process.stdin.fileno(), False)
                selector.register(process.stdin, selectors.EVENT_WRITE)
            else:
                process.stdin.close()
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise MimeUnavailable()
                for key, _ in selector.select(min(remaining, 0.1)):
                    if key.fileobj is process.stdin:
                        try:
                            written = os.write(key.fd, raw[offset : offset + 65536])
                        except BlockingIOError:
                            continue
                        if written <= 0:
                            raise MimeUnavailable()
                        offset += written
                        if offset == len(raw):
                            selector.unregister(process.stdin)
                            process.stdin.close()
                    else:
                        try:
                            chunk = os.read(key.fd, min(65536, limit - size + 1))
                        except BlockingIOError:
                            continue
                        if not chunk:
                            selector.unregister(process.stdout)
                            process.stdout.close()
                        else:
                            size += len(chunk)
                            if size > limit:
                                raise MimeUnavailable()
                            chunks.append(chunk)
            remaining = deadline - time.monotonic()
            if remaining <= 0 or process.wait(timeout=remaining) != 0 or offset != len(raw):
                raise MimeUnavailable()
        return b"".join(chunks)
    except Exception:
        raise MimeUnavailable() from None
    finally:
        if process is not None:
            try:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=1)
            except Exception:
                raise MimeUnavailable() from None
            finally:
                for stream in (process.stdin, process.stdout):
                    if stream is not None:
                        stream.close()


def _environment(value: Any) -> dict[str, str]:
    if not isinstance(value, list) or len(value) > len(_ENV):
        raise MimeUnavailable()
    parsed: dict[str, str] = {}
    for entry in value:
        if not isinstance(entry, str) or "=" not in entry:
            raise MimeUnavailable()
        name, content = entry.split("=", 1)
        if name not in _ENV or name in parsed:
            raise MimeUnavailable()
        parsed[name] = content
    return parsed


class _DockerPipe:
    def __init__(self, image_id: str, *, docker_binary: Path, profile: _Profile) -> None:
        if (
            profile not in (_MIME_PROFILE, _PDF_PROFILE, _DOCUMENT_PROFILE, _ARCHIVE_PROFILE)
            or not isinstance(image_id, str)
            or not _IMAGE.fullmatch(image_id)
            or not isinstance(docker_binary, Path)
            or not docker_binary.is_absolute()
            or ".." in docker_binary.parts
        ):
            raise MimeUnavailable()
        self._image_id = image_id
        self._docker_binary = docker_binary
        self._profile = profile
        self._label = f"org.cw.email-brain.{profile.name}-run"

    def _invoke(
        self,
        args: list[str],
        raw: bytes = b"",
        *,
        limit: int = _CONTROL_BYTES,
        timeout: float = 10,
    ) -> bytes:
        return _pump(
            [
                str(self._docker_binary),
                "--host=unix:///var/run/docker.sock",
                "--config=/nonexistent",
                *args,
            ],
            raw,
            limit=limit,
            timeout=timeout,
        )

    def _inspect(self, kind: str, target: str) -> dict[str, Any]:
        value = json.loads(self._invoke([kind, "inspect", target]))
        if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
            raise MimeUnavailable()
        return value[0]

    def _image(self) -> None:
        security = json.loads(self._invoke(["info", "--format", "{{json .SecurityOptions}}"]))
        if not isinstance(security, list) or not any(
            option in {"name=seccomp,profile=builtin", "name=seccomp,profile=default"}
            for option in security
            if isinstance(option, str)
        ):
            raise MimeUnavailable()
        image = self._inspect("image", self._image_id)
        config = image["Config"]
        if image["Id"] != self._image_id or config.get("Volumes"):
            raise MimeUnavailable()
        # Refuse hidden inherited variables, including credentials/PYTHONPATH.
        # Known Python-image metadata is explicitly overwritten before execution.
        _environment(config.get("Env", []))

    def _owned(self, state: dict[str, Any], name: str, expected: str | None) -> str:
        identifier = state["Id"]
        if (
            not isinstance(identifier, str)
            or not _CONTAINER.fullmatch(identifier)
            or (expected is not None and identifier != expected)
            or state["Name"] != "/" + name
            or state["Image"] != self._image_id
            or state["Config"].get("Labels", {}).get(self._label) != name
        ):
            raise MimeUnavailable()
        return identifier

    def _isolated(self, state: dict[str, Any]) -> None:
        config, host = state["Config"], state["HostConfig"]
        if (
            state["State"]["Status"] != "created"
            or state.get("Mounts") != []
            or config.get("Volumes")
            or config.get("User") != "10001:10001"
            or config.get("WorkingDir") != "/app"
            or config.get("Entrypoint") != ["/app/.venv/bin/python"]
            or config.get("Cmd") != list(self._profile.command)
            or config.get("Healthcheck", {}).get("Test") != ["NONE"]
            or not config.get("OpenStdin")
            or config.get("Tty")
            or _environment(config.get("Env")) != _ENV
            or host.get("NetworkMode") != "none"
            or host.get("ReadonlyRootfs") is not True
            or host.get("Privileged") is not False
            or host.get("CapDrop") != ["ALL"]
            or host.get("CapAdd")
            or host.get("SecurityOpt") != ["no-new-privileges:true"]
            or host.get("Memory") != _MEMORY
            or host.get("MemorySwap") != _MEMORY
            or host.get("NanoCpus") != 1_000_000_000
            or host.get("PidsLimit") != 32
            or host.get("LogConfig", {}).get("Type") != "none"
            or host.get("Binds")
            or host.get("Mounts")
            or host.get("Tmpfs")
            or host.get("Devices")
            or host.get("DeviceRequests")
            or host.get("VolumesFrom")
            or host.get("PidMode")
            or host.get("UTSMode")
            or host.get("IpcMode") != "private"
            or host.get("PublishAllPorts")
            or host.get("PortBindings")
            or host.get("RestartPolicy", {}).get("Name") != "no"
        ):
            raise MimeUnavailable()

    def _cleanup(self, name: str, expected: str | None) -> None:
        state = self._inspect("container", name)
        identifier = self._owned(state, name, expected)
        if self._invoke(["container", "rm", "--force", identifier]).strip() != identifier.encode():
            raise MimeUnavailable()

    def _run(self, raw: bytes, decode: Callable[[bytes], _T]) -> _T:
        try:
            if not isinstance(raw, bytes) or len(raw) > self._profile.input_bytes:
                raise MimeUnavailable()
            self._image()
            name = f"eb-{self._profile.name}-" + uuid4().hex
            identifier = None
            try:
                args = [
                    "container",
                    "create",
                    "--pull=never",
                    "--name",
                    name,
                    "--label",
                    f"{self._label}={name}",
                    "--network=none",
                    "--read-only",
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges:true",
                    "--memory=512m",
                    "--memory-swap=512m",
                    "--cpus=1",
                    "--pids-limit=32",
                    "--user=10001:10001",
                    "--log-driver=none",
                    "--restart=no",
                    "--ipc=private",
                    "--no-healthcheck",
                    "--workdir=/app",
                    "--interactive",
                    "--entrypoint=/app/.venv/bin/python",
                ]
                for key, value in _ENV.items():
                    args.extend(["--env", f"{key}={value}"])
                result = (
                    self._invoke([*args, self._image_id, *self._profile.command])
                    .decode("ascii")
                    .strip()
                )
                if not _CONTAINER.fullmatch(result):
                    raise MimeUnavailable()
                identifier = result
                state = self._inspect("container", identifier)
                self._owned(state, name, identifier)
                self._isolated(state)
                output = self._invoke(
                    ["container", "start", "--attach", "--interactive", identifier],
                    raw,
                    limit=self._profile.output_bytes,
                    timeout=30,
                )
                completed = self._inspect("container", identifier)
                self._owned(completed, name, identifier)
                status = completed["State"]
                if (
                    status.get("Status") != "exited"
                    or type(status.get("ExitCode")) is not int
                    or status["ExitCode"] != 0
                    or status.get("OOMKilled") is not False
                ):
                    raise MimeUnavailable()
                return decode(output)
            finally:
                self._cleanup(name, identifier)
        except Exception:
            raise MimeUnavailable() from None


class DockerMimeProcessor(_DockerPipe):
    max_raw_bytes = MAX_INPUT_BYTES

    def __init__(self, image_id: str, *, docker_binary: Path = Path("/usr/bin/docker")) -> None:
        super().__init__(image_id, docker_binary=docker_binary, profile=_MIME_PROFILE)

    @property
    def parser_version(self) -> str:
        return "sandbox-mime-v1-" + self._image_id.removeprefix("sha256:")

    def prepare(self, raw: bytes) -> tuple[NormalizedMessage | None, list[Attachment], bool]:
        return self._run(raw, lambda output: decode_response(output, raw))
