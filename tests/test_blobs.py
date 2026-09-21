"""Synthetic encrypted-object pressure tests; no real mail or persistent keys."""

from __future__ import annotations

import hashlib
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from email_brain import blobs
from email_brain.blobs import MAX_BLOB_BYTES, BlobError, BlobRef, EncryptedBlobStore

TENANT = UUID("11111111-1111-4111-8111-111111111111")
ACCOUNT = UUID("22222222-2222-4222-8222-222222222222")
KEY = bytes(range(32))
RAW = b"From: synthetic@example.invalid\r\n\r\nPrivate synthetic attachment bytes.\x00\xff"


@pytest.fixture
def backend(tmp_path: Path) -> EncryptedBlobStore:
    return EncryptedBlobStore(tmp_path / "objects", {(TENANT, "key-1"): KEY}, {TENANT: "key-1"})


def location(tmp_path: Path, ref: BlobRef) -> Path:
    return tmp_path / "objects" / ref.object_key


def test_round_trip_only_ciphertext_touches_disk(
    backend: EncryptedBlobStore, tmp_path: Path
) -> None:
    ref = backend.put(TENANT, ACCOUNT, RAW)
    assert backend.get(TENANT, ACCOUNT, ref) == RAW
    assert ref.sha256 == hashlib.sha256(RAW).hexdigest()
    payload = location(tmp_path, ref).read_bytes()
    assert RAW not in payload
    assert payload.startswith(b"EBB1")
    assert len(payload) == len(RAW) + 32
    assert hashlib.sha256(payload).hexdigest() == ref.ciphertext_sha256
    assert stat.S_IMODE(location(tmp_path, ref).stat().st_mode) == 0o600
    assert not list((tmp_path / "objects").rglob(".tmp-*"))
    for path in (tmp_path / "objects").rglob("*"):
        if path.is_dir():
            assert stat.S_IMODE(path.stat().st_mode) == 0o700
    assert repr(KEY) not in repr(backend)
    with pytest.raises(FrozenInstanceError):
        ref.key_id = "other"  # type: ignore[misc]


def test_idempotent_no_overwrite(backend: EncryptedBlobStore, tmp_path: Path) -> None:
    first = backend.put(TENANT, ACCOUNT, RAW)
    before = location(tmp_path, first).stat()
    assert backend.put(TENANT, ACCOUNT, RAW) == first
    after = location(tmp_path, first).stat()
    assert (before.st_ino, before.st_mtime_ns) == (after.st_ino, after.st_mtime_ns)


def test_concurrent_same_content(backend: EncryptedBlobStore, tmp_path: Path) -> None:
    with ThreadPoolExecutor(max_workers=12) as executor:
        refs = list(executor.map(lambda _: backend.put(TENANT, ACCOUNT, RAW), range(40)))
    assert len(set(refs)) == 1
    assert backend.get(TENANT, ACCOUNT, refs[0]) == RAW
    assert not list((tmp_path / "objects").rglob(".tmp-*"))


def test_distinct_random_nonce_between_stores(tmp_path: Path) -> None:
    first = EncryptedBlobStore(tmp_path / "one", {(TENANT, "k"): KEY}, {TENANT: "k"})
    second = EncryptedBlobStore(tmp_path / "two", {(TENANT, "k"): KEY}, {TENANT: "k"})
    one = first.put(TENANT, ACCOUNT, RAW)
    two = second.put(TENANT, ACCOUNT, RAW)
    assert one.sha256 == two.sha256
    assert one.ciphertext_sha256 != two.ciphertext_sha256
    assert (tmp_path / "one" / one.object_key).read_bytes()[4:16] != (
        tmp_path / "two" / two.object_key
    ).read_bytes()[4:16]


def test_rotation_keeps_prior_objects_readable(tmp_path: Path) -> None:
    keys = {(TENANT, "old"): KEY, (TENANT, "new"): bytes(reversed(KEY))}
    root = tmp_path / "objects"
    first = EncryptedBlobStore(root, keys, {TENANT: "old"})
    old = first.put(TENANT, ACCOUNT, RAW)
    second = EncryptedBlobStore(root, keys, {TENANT: "new"})
    new = second.put(TENANT, ACCOUNT, RAW)
    assert second.get(TENANT, ACCOUNT, old) == second.get(TENANT, ACCOUNT, new) == RAW
    assert old.object_key != new.object_key
    lost = EncryptedBlobStore(root, {(TENANT, "new"): keys[(TENANT, "new")]}, {TENANT: "new"})
    with pytest.raises(BlobError):
        lost.get(TENANT, ACCOUNT, old)


@pytest.mark.parametrize("size", [0, 1, MAX_BLOB_BYTES])
def test_byte_bounds(backend: EncryptedBlobStore, size: int) -> None:
    raw = b"x" * size
    assert backend.get(TENANT, ACCOUNT, backend.put(TENANT, ACCOUNT, raw)) == raw


@pytest.mark.parametrize("raw", [b"x" * (MAX_BLOB_BYTES + 1), "not bytes", bytearray(b"a"), None])
def test_invalid_bytes_rejected(backend: EncryptedBlobStore, raw: object) -> None:
    with pytest.raises(BlobError):
        backend.put(TENANT, ACCOUNT, raw)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    [
        {"object_key": "../../private"},
        {"object_key": "/absolute"},
        {"sha256": "F" * 64},
        {"sha256": "0" * 64},
        {"sha256": "../a"},
        {"ciphertext_sha256": "0" * 64},
        {"ciphertext_sha256": "g" * 64},
        {"key_id": "../key-1"},
        {"key_id": "unknown"},
        {"key_id": "é"},
        {"byte_count": -1},
        {"byte_count": True},
        {"byte_count": MAX_BLOB_BYTES + 1},
        {"byte_count": 1},
    ],
)
def test_manifest_tampering(backend: EncryptedBlobStore, changes: dict[str, object]) -> None:
    ref = backend.put(TENANT, ACCOUNT, RAW)
    with pytest.raises(BlobError):
        backend.get(TENANT, ACCOUNT, replace(ref, **changes))  # type: ignore[arg-type]


@pytest.mark.parametrize("mutation", ["truncate", "append", "flip", "magic"])
def test_corruption_rejected_even_with_updated_cipherhash(
    backend: EncryptedBlobStore,
    tmp_path: Path,
    mutation: str,
) -> None:
    ref = backend.put(TENANT, ACCOUNT, RAW)
    path = location(tmp_path, ref)
    original = path.read_bytes()
    payload = {
        "truncate": original[:-1],
        "append": original + b"x",
        "flip": original[:20] + bytes([original[20] ^ 1]) + original[21:],
        "magic": b"EBB2" + original[4:],
    }[mutation]
    path.write_bytes(payload)
    forged = replace(ref, ciphertext_sha256=hashlib.sha256(payload).hexdigest())
    with pytest.raises(BlobError):
        backend.get(TENANT, ACCOUNT, forged)
    with pytest.raises(BlobError):
        backend.put(TENANT, ACCOUNT, RAW)
    assert path.read_bytes() == payload


def test_scope_binding_prevents_ciphertext_substitution(tmp_path: Path) -> None:
    other_tenant, other_account = uuid4(), uuid4()
    backend = EncryptedBlobStore(
        tmp_path / "objects",
        {(TENANT, "k"): KEY, (other_tenant, "k"): KEY},
        {TENANT: "k", other_tenant: "k"},
    )
    original = backend.put(TENANT, ACCOUNT, RAW)
    for tenant, account in [(other_tenant, ACCOUNT), (TENANT, other_account)]:
        with pytest.raises(BlobError):
            backend.get(tenant, account, original)
        target = backend.put(tenant, account, RAW)
        location(tmp_path, target).write_bytes(location(tmp_path, original).read_bytes())
        forged = replace(target, ciphertext_sha256=original.ciphertext_sha256)
        with pytest.raises(BlobError):
            backend.get(tenant, account, forged)


def test_same_tenant_key_id_is_authenticated(tmp_path: Path) -> None:
    backend = EncryptedBlobStore(
        tmp_path / "objects",
        {(TENANT, "one"): KEY, (TENANT, "two"): KEY},
        {TENANT: "one"},
    )
    first = backend.put(TENANT, ACCOUNT, RAW)
    rotated = EncryptedBlobStore(
        tmp_path / "objects",
        {(TENANT, "one"): KEY, (TENANT, "two"): KEY},
        {TENANT: "two"},
    )
    second = rotated.put(TENANT, ACCOUNT, RAW)
    location(tmp_path, second).write_bytes(location(tmp_path, first).read_bytes())
    with pytest.raises(BlobError):
        rotated.get(TENANT, ACCOUNT, replace(second, ciphertext_sha256=first.ciphertext_sha256))


def test_wrong_key_no_fallback(backend: EncryptedBlobStore, tmp_path: Path) -> None:
    ref = backend.put(TENANT, ACCOUNT, RAW)
    wrong = EncryptedBlobStore(tmp_path / "objects", {(TENANT, "key-1"): b"z" * 32}, {})
    with pytest.raises(BlobError):
        wrong.get(TENANT, ACCOUNT, ref)
    with pytest.raises(BlobError):
        backend.put(uuid4(), ACCOUNT, RAW)


@pytest.mark.parametrize("key_id", ["", "a" * 65, "..", "a/b", "a\x00b", "café"])
def test_invalid_key_id(tmp_path: Path, key_id: str) -> None:
    with pytest.raises(BlobError):
        EncryptedBlobStore(tmp_path / "objects", {(TENANT, key_id): KEY}, {TENANT: key_id})


@pytest.mark.parametrize("key", [b"a" * 16, b"a" * 31, b"a" * 33, "secret", None])
def test_invalid_key_length_or_type(tmp_path: Path, key: object) -> None:
    with pytest.raises(BlobError):
        EncryptedBlobStore(tmp_path / "objects", {(TENANT, "k"): key}, {})  # type: ignore[dict-item]


@pytest.mark.parametrize("mode", [0o755, 0o770, 0o777])
def test_unsafe_root_permissions_rejected(tmp_path: Path, mode: int) -> None:
    root = tmp_path / "objects"
    root.mkdir(mode=mode)
    root.chmod(mode)
    with pytest.raises(BlobError):
        EncryptedBlobStore(root, {(TENANT, "k"): KEY}, {TENANT: "k"})


@pytest.mark.parametrize("component", ["root", "ancestor", "scope", "file"])
def test_symlinks_rejected(backend: EncryptedBlobStore, tmp_path: Path, component: str) -> None:
    ref = backend.put(TENANT, ACCOUNT, RAW)
    if component == "ancestor":
        alias = tmp_path / "alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        with pytest.raises(BlobError):
            EncryptedBlobStore(alias / "objects", {(TENANT, "key-1"): KEY}, {})
        return
    path = {
        "root": tmp_path / "objects",
        "scope": tmp_path / "objects" / "v1",
        "file": location(tmp_path, ref),
    }[component]
    moved = path.with_name(path.name + ".original")
    path.rename(moved)
    path.symlink_to(moved, target_is_directory=moved.is_dir())
    with pytest.raises(BlobError):
        backend.get(TENANT, ACCOUNT, ref)
    with pytest.raises(BlobError):
        backend.put(TENANT, ACCOUNT, RAW)


@pytest.mark.parametrize("target", ["file", "directory"])
def test_permission_changes_fail_closed(
    backend: EncryptedBlobStore,
    tmp_path: Path,
    target: str,
) -> None:
    ref = backend.put(TENANT, ACCOUNT, RAW)
    path = location(tmp_path, ref)
    (path if target == "file" else path.parent).chmod(0o644 if target == "file" else 0o755)
    with pytest.raises(BlobError):
        backend.get(TENANT, ACCOUNT, ref)
    with pytest.raises(BlobError):
        backend.put(TENANT, ACCOUNT, RAW)


def test_fifo_rejected_without_blocking(backend: EncryptedBlobStore, tmp_path: Path) -> None:
    ref = backend.put(TENANT, ACCOUNT, RAW)
    path = location(tmp_path, ref)
    path.unlink()
    os.mkfifo(path, mode=0o600)
    with pytest.raises(BlobError):
        backend.get(TENANT, ACCOUNT, ref)


@pytest.mark.parametrize("stage", ["write", "link", "fsync"])
def test_failure_never_publishes_partial_plaintext(
    backend: EncryptedBlobStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    backend.put(TENANT, ACCOUNT, b"first")  # Create scope before fault injection.
    original_fsync = os.fsync

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("private exception marker must not escape")

    def fail_file_fsync(fd: int) -> None:
        if stat.S_ISREG(os.fstat(fd).st_mode):
            fail()
        original_fsync(fd)

    monkeypatch.setattr(blobs.os, stage, fail_file_fsync if stage == "fsync" else fail)
    with pytest.raises(BlobError, match="^encrypted blob operation failed$") as caught:
        backend.put(TENANT, ACCOUNT, RAW)
    assert "private exception" not in str(caught.value)
    assert not list((tmp_path / "objects").rglob(".tmp-*"))
    assert len(list((tmp_path / "objects").rglob("*.blob"))) == 1


def test_partial_writes_are_completed(
    backend: EncryptedBlobStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write = os.write
    monkeypatch.setattr(blobs.os, "write", lambda fd, data: write(fd, data[:7]))
    ref = backend.put(TENANT, ACCOUNT, RAW)
    assert backend.get(TENANT, ACCOUNT, ref) == RAW


def test_missing_object_no_implicit_write(backend: EncryptedBlobStore, tmp_path: Path) -> None:
    ref = backend.put(TENANT, ACCOUNT, RAW)
    location(tmp_path, ref).unlink()
    with pytest.raises(BlobError):
        backend.get(TENANT, ACCOUNT, ref)
    assert not location(tmp_path, ref).exists()


def test_inventory_scoped_read_only(backend: EncryptedBlobStore, tmp_path: Path) -> None:
    assert backend.object_keys(TENANT, ACCOUNT) == ()
    first = backend.put(TENANT, ACCOUNT, RAW)
    second = backend.put(TENANT, ACCOUNT, b"another")
    backend.put(TENANT, uuid4(), b"other account")
    temp = location(tmp_path, first).parent / (".tmp-" + "f" * 32)
    temp.touch(mode=0o600)
    assert backend.object_keys(TENANT, ACCOUNT) == tuple(
        sorted([first.object_key, second.object_key])
    )
    assert temp.exists()
    assert backend.object_keys(uuid4(), ACCOUNT) == ()


def test_inventory_budget(backend: EncryptedBlobStore, monkeypatch: pytest.MonkeyPatch) -> None:
    backend.put(TENANT, ACCOUNT, RAW)
    monkeypatch.setattr(blobs, "MAX_INVENTORY_ENTRIES", 1)
    with pytest.raises(BlobError):
        backend.object_keys(TENANT, ACCOUNT)


def test_inventory_symlink_rejected(backend: EncryptedBlobStore, tmp_path: Path) -> None:
    ref = backend.put(TENANT, ACCOUNT, RAW)
    path = location(tmp_path, ref)
    path.with_name("0" * 64 + ".blob").symlink_to(path)
    with pytest.raises(BlobError):
        backend.object_keys(TENANT, ACCOUNT)


def test_published_object_survives_post_link_failure_for_retry(
    backend: EncryptedBlobStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend.put(TENANT, ACCOUNT, b"initialize scope")
    fsync = os.fsync
    link = os.link
    linked = False

    def record_link(*args: object, **kwargs: object) -> None:
        nonlocal linked
        link(*args, **kwargs)  # type: ignore[arg-type]
        linked = True

    def fail_directory_sync(fd: int) -> None:
        if linked and stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("synthetic disk failure")
        fsync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(blobs.os, "link", record_link)
        patch.setattr(blobs.os, "fsync", fail_directory_sync)
        with pytest.raises(BlobError):
            backend.put(TENANT, ACCOUNT, RAW)
    assert len(list((tmp_path / "objects").rglob("*.blob"))) == 2
    assert not list((tmp_path / "objects").rglob(".tmp-*"))
    ref = backend.put(TENANT, ACCOUNT, RAW)
    assert backend.get(TENANT, ACCOUNT, ref) == RAW


def test_zero_length_write_is_error_and_cleans_only_temp(
    backend: EncryptedBlobStore,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = backend.put(TENANT, ACCOUNT, b"preserved")
    monkeypatch.setattr(blobs.os, "write", lambda fd, data: 0)
    with pytest.raises(BlobError):
        backend.put(TENANT, ACCOUNT, RAW)
    assert backend.get(TENANT, ACCOUNT, first) == b"preserved"
    assert not list((tmp_path / "objects").rglob(".tmp-*"))


def test_root_ownership_guard(
    backend: EncryptedBlobStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ref = backend.put(TENANT, ACCOUNT, RAW)
    own_uid = os.getuid()
    monkeypatch.setattr(blobs.os, "getuid", lambda: own_uid + 1)
    with pytest.raises(BlobError):
        backend.get(TENANT, ACCOUNT, ref)
    with pytest.raises(BlobError):
        backend.put(TENANT, ACCOUNT, RAW)
    with pytest.raises(BlobError):
        backend.object_keys(TENANT, ACCOUNT)


def test_missing_root_is_failure_not_empty_inventory(
    backend: EncryptedBlobStore,
    tmp_path: Path,
) -> None:
    (tmp_path / "objects").rmdir()
    with pytest.raises(BlobError):
        backend.object_keys(TENANT, ACCOUNT)


def test_key_configuration_is_copied(tmp_path: Path) -> None:
    keys = {(TENANT, "k"): KEY}
    active = {TENANT: "k"}
    backend = EncryptedBlobStore(tmp_path / "objects", keys, active)
    keys.clear()
    active.clear()
    ref = backend.put(TENANT, ACCOUNT, RAW)
    assert backend.get(TENANT, ACCOUNT, ref) == RAW


@pytest.mark.parametrize("kind", ["relative", "parent_escape", "filesystem_root"])
def test_root_path_validation(tmp_path: Path, kind: str) -> None:
    root = {
        "relative": Path("relative"),
        "parent_escape": tmp_path / ".." / "objects",
        "filesystem_root": Path("/"),
    }[kind]
    with pytest.raises(BlobError):
        EncryptedBlobStore(root, {}, {})


def test_invalid_uuid_scope_rejected(backend: EncryptedBlobStore) -> None:
    ref = backend.put(TENANT, ACCOUNT, RAW)
    with pytest.raises(BlobError):
        backend.get(str(TENANT), ACCOUNT, ref)  # type: ignore[arg-type]
    with pytest.raises(BlobError):
        backend.put(TENANT, "../account", RAW)  # type: ignore[arg-type]
    with pytest.raises(BlobError):
        backend.object_keys(TENANT, "../account")  # type: ignore[arg-type]


def test_read_error_exception_is_scrubbed(
    backend: EncryptedBlobStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ref = backend.put(TENANT, ACCOUNT, RAW)

    def fail_read(*args: object) -> bytes:
        raise OSError("SYNTHETIC_PRIVATE_DATA /private/operator-location")

    monkeypatch.setattr(blobs.os, "read", fail_read)
    with pytest.raises(BlobError) as caught:
        backend.get(TENANT, ACCOUNT, ref)
    assert str(caught.value) == "encrypted blob operation failed"
    assert caught.value.__suppress_context__ is True
