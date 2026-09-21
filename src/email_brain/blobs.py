"""Bounded local encrypted evidence; not cloud IAM, KMS, or an authorization service.

Only ciphertext touches disk. Callers authorize the tenant/account before use and
retain manifests and keys independently. No deletion or network capability exists.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Iterator, Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAX_BLOB_BYTES = 16 * 1024 * 1024
MAX_INVENTORY_ENTRIES = 10000
_MAGIC = b"EBB1"
_OVERHEAD = len(_MAGIC) + 12 + 16
_KEY_ID = re.compile(r"[a-zA-Z0-9_-]{1,64}\Z", re.ASCII)
_SHA256 = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


class BlobError(ValueError):
    """Content-free failure; never include input, keys, filesystem paths or OS errors."""

    def __init__(self) -> None:
        super().__init__("encrypted blob operation failed")


@dataclass(frozen=True)
class BlobRef:
    object_key: str
    sha256: str
    byte_count: int
    ciphertext_sha256: str
    key_id: str


def _private(fd: int, *, directory: bool) -> None:
    info = os.fstat(fd)
    valid_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if (
        not valid_type
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)
    ):
        raise BlobError()


def _scope(tenant_id: UUID, account_id: UUID) -> None:
    if not isinstance(tenant_id, UUID) or not isinstance(account_id, UUID):
        raise BlobError()


def _object_key(tenant_id: UUID, account_id: UUID, key_id: str, digest: str) -> str:
    return f"v1/{tenant_id}/{account_id}/{key_id}/{digest}.blob"


def _aad(tenant_id: UUID, account_id: UUID, ref: BlobRef) -> bytes:
    return json.dumps(
        [
            "email-brain-blob",
            1,
            str(tenant_id),
            str(account_id),
            ref.key_id,
            ref.sha256,
            ref.byte_count,
        ],
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


class EncryptedBlobStore:
    """Local write-once AES-256-GCM store with explicit tenant-bound key injection.

    The absolute root's parent must exist. Root and all descendants must be owned
    by the current OS user and private (0700 directories / 0600 files). Symlinks
    are rejected even in root ancestors. Same-UID privileged interference remains
    outside this process boundary; integrity still requires authenticated bytes.
    """

    def __init__(
        self,
        root: Path,
        keys: Mapping[tuple[UUID, str], bytes],
        active_keys: Mapping[UUID, str],
    ) -> None:
        try:
            if (
                not isinstance(root, Path)
                or not root.is_absolute()
                or len(root.parts) < 2
                or ".." in root.parts
            ):
                raise BlobError()
            self._root = root
            self._keys = dict(keys)
            self._active_keys = dict(active_keys)
            for binding, key in self._keys.items():
                if (
                    not isinstance(binding, tuple)
                    or len(binding) != 2
                    or not isinstance(binding[0], UUID)
                    or not isinstance(binding[1], str)
                    or not _KEY_ID.fullmatch(binding[1])
                    or not isinstance(key, bytes)
                    or len(key) != 32
                ):
                    raise BlobError()
            for tenant, key_id in self._active_keys.items():
                if not isinstance(tenant, UUID) or (tenant, key_id) not in self._keys:
                    raise BlobError()
            with self._root_fd(create=True):
                pass
        except (OSError, ValueError, TypeError):
            raise BlobError() from None

    @contextmanager
    def _root_fd(self, *, create: bool) -> Iterator[int]:
        with ExitStack() as stack:
            fd = os.open("/", _DIR_FLAGS)
            stack.callback(os.close, fd)
            for index, component in enumerate(self._root.parts[1:], start=1):
                final = index == len(self._root.parts) - 1
                if final and create:
                    try:
                        os.mkdir(component, mode=0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                    os.fsync(fd)
                try:
                    fd = os.open(component, _DIR_FLAGS, dir_fd=fd)
                except OSError:
                    # An unavailable storage root is not an empty account scope.
                    raise BlobError() from None
                stack.callback(os.close, fd)
            _private(fd, directory=True)
            yield fd

    @contextmanager
    def _directory(self, object_key: str, *, create: bool) -> Iterator[tuple[int, str]]:
        # Only keys reconstructed from validated metadata ever reach this helper.
        parts = object_key.split("/")
        with self._root_fd(create=False) as root_fd, ExitStack() as stack:
            fd = root_fd
            for component in parts[:-1]:
                if create:
                    try:
                        os.mkdir(component, mode=0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                    # A concurrent creator may not have synced its parent yet.
                    os.fsync(fd)
                fd = os.open(component, _DIR_FLAGS, dir_fd=fd)
                stack.callback(os.close, fd)
                _private(fd, directory=True)
            yield fd, parts[-1]

    def _validate(self, tenant_id: UUID, account_id: UUID, ref: BlobRef) -> bytes:
        _scope(tenant_id, account_id)
        if (
            not isinstance(ref, BlobRef)
            or not isinstance(ref.key_id, str)
            or not _KEY_ID.fullmatch(ref.key_id)
            or not isinstance(ref.sha256, str)
            or not _SHA256.fullmatch(ref.sha256)
            or not isinstance(ref.ciphertext_sha256, str)
            or not _SHA256.fullmatch(ref.ciphertext_sha256)
            or type(ref.byte_count) is not int
            or not 0 <= ref.byte_count <= MAX_BLOB_BYTES
            or ref.object_key != _object_key(tenant_id, account_id, ref.key_id, ref.sha256)
        ):
            raise BlobError()
        key = self._keys.get((tenant_id, ref.key_id))
        if key is None:
            raise BlobError()
        return key

    @staticmethod
    def _read(directory: int, filename: str, byte_count: int) -> bytes:
        fd = os.open(filename, _FILE_FLAGS, dir_fd=directory)
        try:
            _private(fd, directory=False)
            expected = byte_count + _OVERHEAD
            if os.fstat(fd).st_size != expected:
                raise BlobError()
            chunks: list[bytes] = []
            remaining = expected + 1
            while remaining:
                chunk = os.read(fd, min(remaining, 1024 * 1024))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            payload = b"".join(chunks)
            if len(payload) != expected or not payload.startswith(_MAGIC):
                raise BlobError()
            return payload
        finally:
            os.close(fd)

    @staticmethod
    def _decrypt(tenant: UUID, account: UUID, ref: BlobRef, key: bytes, payload: bytes) -> bytes:
        if hashlib.sha256(payload).hexdigest() != ref.ciphertext_sha256:
            raise BlobError()
        raw = AESGCM(key).decrypt(payload[4:16], payload[16:], _aad(tenant, account, ref))
        if len(raw) != ref.byte_count or hashlib.sha256(raw).hexdigest() != ref.sha256:
            raise BlobError()
        return raw

    def get(self, tenant_id: UUID, account_id: UUID, ref: BlobRef) -> bytes:
        try:
            key = self._validate(tenant_id, account_id, ref)
            with self._directory(ref.object_key, create=False) as (directory, filename):
                payload = self._read(directory, filename, ref.byte_count)
            return self._decrypt(tenant_id, account_id, ref, key, payload)
        except (OSError, ValueError, TypeError, InvalidTag):
            raise BlobError() from None

    def object_keys(self, tenant_id: UUID, account_id: UUID) -> tuple[str, ...]:
        """Bounded read-only inventory, not a snapshot or permission to delete.

        This does not decrypt or attest content. Unpublished private temporary
        files are excluded. The scan budget includes directories and temp files.
        """
        try:
            _scope(tenant_id, account_id)
            found: list[str] = []
            visited = 0
            prefix = f"v1/{tenant_id}/{account_id}"
            try:
                with self._directory(f"{prefix}/unused", create=False) as (account_fd, _):
                    with os.scandir(account_fd) as key_dirs:
                        for entry in key_dirs:
                            visited += 1
                            if visited > MAX_INVENTORY_ENTRIES or not _KEY_ID.fullmatch(entry.name):
                                raise BlobError()
                            key_fd = os.open(entry.name, _DIR_FLAGS, dir_fd=account_fd)
                            try:
                                _private(key_fd, directory=True)
                                with os.scandir(key_fd) as objects:
                                    for obj in objects:
                                        visited += 1
                                        if visited > MAX_INVENTORY_ENTRIES:
                                            raise BlobError()
                                        file_fd = os.open(obj.name, _FILE_FLAGS, dir_fd=key_fd)
                                        try:
                                            _private(file_fd, directory=False)
                                        finally:
                                            os.close(file_fd)
                                        if re.fullmatch(r"\.tmp-[a-f0-9]{32}", obj.name):
                                            continue
                                        if not obj.name.endswith(".blob") or not _SHA256.fullmatch(
                                            obj.name[:-5]
                                        ):
                                            raise BlobError()
                                        found.append(f"{prefix}/{entry.name}/{obj.name}")
                            finally:
                                os.close(key_fd)
            except FileNotFoundError:
                # Concurrent removal/rename can also reach here: never return a
                # partial inventory falsely claiming a complete scoped listing.
                if visited:
                    raise BlobError() from None
                return ()
            return tuple(sorted(found))
        except (OSError, ValueError, TypeError):
            raise BlobError() from None

    def put(self, tenant_id: UUID, account_id: UUID, raw: bytes) -> BlobRef:
        try:
            _scope(tenant_id, account_id)
            if not isinstance(raw, bytes) or len(raw) > MAX_BLOB_BYTES:
                raise BlobError()
            key_id = self._active_keys.get(tenant_id)
            if key_id is None:
                raise BlobError()
            digest = hashlib.sha256(raw).hexdigest()
            object_key = _object_key(tenant_id, account_id, key_id, digest)
            template = BlobRef(object_key, digest, len(raw), "0" * 64, key_id)
            key = self._validate(tenant_id, account_id, template)
            with self._directory(object_key, create=True) as (directory, filename):
                try:
                    payload = self._read(directory, filename, len(raw))
                except FileNotFoundError:
                    nonce = os.urandom(12)
                    payload = (
                        _MAGIC
                        + nonce
                        + AESGCM(key).encrypt(nonce, raw, _aad(tenant_id, account_id, template))
                    )
                    self._publish(directory, filename, payload)
                    # A concurrent publisher may have won with its own nonce.
                    payload = self._read(directory, filename, len(raw))
                ref = BlobRef(
                    object_key, digest, len(raw), hashlib.sha256(payload).hexdigest(), key_id
                )
                self._decrypt(tenant_id, account_id, ref, key, payload)
                os.fsync(directory)
                return ref
        except (OSError, ValueError, TypeError, InvalidTag):
            raise BlobError() from None

    @staticmethod
    def _publish(directory: int, filename: str, payload: bytes) -> None:
        temporary = f".tmp-{uuid4().hex}"
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        try:
            _private(fd, directory=False)
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise BlobError()
                view = view[written:]
            os.fsync(fd)
            try:
                os.link(
                    temporary,
                    filename,
                    src_dir_fd=directory,
                    dst_dir_fd=directory,
                    follow_symlinks=False,
                )
            except FileExistsError:
                pass
        finally:
            try:
                owned = os.fstat(fd)
                current = os.stat(temporary, dir_fd=directory, follow_symlinks=False)
                if (owned.st_dev, owned.st_ino) == (current.st_dev, current.st_ino):
                    os.unlink(temporary, dir_fd=directory)
            finally:
                os.close(fd)
        os.fsync(directory)
