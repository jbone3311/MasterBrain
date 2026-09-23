from __future__ import annotations

import hashlib
import io
import json
import tarfile
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from masterbrain.datacore.archive_contract import ArchiveUnavailable, source_for
from masterbrain.datacore.archive_member import read_persisted_archive_member
from masterbrain.datacore.archive_member_contract import (
    ArchiveMemberTarget,
    decode_request,
    decode_result,
    encode_request,
)
from masterbrain.datacore.archive_member_worker import process_request
from masterbrain.datacore.archive_worker import inventory_archive
from masterbrain.datacore.persistence import ArchiveMemberTargetRecord

PROCESSOR = "sandbox-fileos-archive-v1-" + "a" * 64
INVENTORY = "archive_inventory_" + "b" * 32


def zip_bytes(members: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, raw in members:
            archive.writestr(name, raw)
    return output.getvalue()


def tar_bytes(members: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, raw in members:
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
    return output.getvalue()


def prepared(raw: bytes, locator: str):
    digest = hashlib.sha256(raw).hexdigest()
    source = source_for(raw, "version_" + digest[:32], "bundle.zip", digest, "application/zip")
    inventory = inventory_archive(raw, source)
    member = next(item for item in inventory.members if item.locator == locator)
    target = ArchiveMemberTarget(
        INVENTORY,
        PROCESSOR,
        member.locator,
        member.sha256,
        member.observed_size,
        member.depth,
        member.parent_locator,
    )
    return source, target


@pytest.mark.parametrize("nested_kind", ["zip", "tar"])
def test_flat_and_nested_member_reads_return_only_exact_bytes(nested_kind: str) -> None:
    proof = b"one exact nested proof"
    inner = (
        zip_bytes([("proof.txt", proof)])
        if nested_kind == "zip"
        else tar_bytes([("proof.txt", proof)])
    )
    suffix = "zip" if nested_kind == "zip" else "tar.gz"
    raw = zip_bytes([("unrelated.txt", b"must never return"), (f"inner.{suffix}", inner)])
    locator = "inner_unpacked/proof.txt" if nested_kind == "zip" else "inner.tar_unpacked/proof.txt"
    source, target = prepared(raw, locator)
    request = encode_request(raw, source, target)
    assert decode_request(request) == (raw, source, target)
    result = decode_result(process_request(request), source, target)
    assert result.status == "read" and result.raw == proof
    assert b"must never return" not in result.raw


def test_empty_member_is_hash_bound_and_allowed() -> None:
    raw = zip_bytes([("empty.txt", b"")])
    source, target = prepared(raw, "empty.txt")
    result = decode_result(process_request(encode_request(raw, source, target)), source, target)
    assert result.status == "read" and result.raw == b""


def test_member_over_output_cap_is_explicitly_deferred() -> None:
    proof = b"x" * (8 * 1024 * 1024 + 1)
    raw = zip_bytes([("proof.txt", proof)])
    source, target = prepared(raw, "proof.txt")
    result = decode_result(process_request(encode_request(raw, source, target)), source, target)
    assert (result.status, result.reason, result.raw) == (
        "deferred",
        "member_output_limit",
        b"",
    )


def test_closed_contract_rejects_substitution_and_unknown_fields() -> None:
    raw = zip_bytes([("proof.txt", b"proof")])
    source, target = prepared(raw, "proof.txt")
    request = json.loads(encode_request(raw, source, target))
    request["ambient"] = True
    with pytest.raises(ArchiveUnavailable):
        decode_request(json.dumps(request).encode())

    request.pop("ambient")
    request["target"]["sha256"] = "c" * 64
    with pytest.raises(ArchiveUnavailable):
        process_request(json.dumps(request).encode())


@pytest.mark.parametrize("change", ["sha256", "size_bytes", "depth", "parent_locator"])
def test_wrong_persisted_identity_cannot_release_bytes(change: str) -> None:
    raw = zip_bytes([("proof.txt", b"proof")])
    source, target = prepared(raw, "proof.txt")
    values = {
        "sha256": "c" * 64,
        "size_bytes": target.size_bytes + 1,
        "depth": 1,
        "parent_locator": "other.zip",
    }
    with pytest.raises(ArchiveUnavailable):
        process_request(encode_request(raw, source, replace(target, **{change: values[change]})))


def test_container_and_depth_limited_container_bytes_are_never_returned() -> None:
    inner = zip_bytes([("proof.txt", b"proof")])
    raw = zip_bytes([("inner.zip", inner)])
    source, target = prepared(raw, "inner.zip")
    with pytest.raises(ArchiveUnavailable):
        process_request(encode_request(raw, source, target))

    nested = inner
    for level in range(4, -1, -1):
        nested = zip_bytes([(f"level-{level}.zip", nested)])
    inventory_source, depth_target = prepared(
        nested,
        "level-0_unpacked/level-1_unpacked/level-2_unpacked/level-3.zip",
    )
    with pytest.raises(ArchiveUnavailable):
        process_request(encode_request(nested, inventory_source, depth_target))


def test_bomb_or_duplicate_inventory_never_releases_prior_member() -> None:
    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("proof.txt", b"proof")
        archive.writestr("bomb.bin", b"0" * (1024 * 1024))
    raw = bomb.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    source = source_for(raw, "version_" + digest[:32], "bundle.zip", digest, "application/zip")
    target = ArchiveMemberTarget(
        INVENTORY, PROCESSOR, "proof.txt", hashlib.sha256(b"proof").hexdigest(), 5, 0, None
    )
    with pytest.raises(ArchiveUnavailable):
        process_request(encode_request(raw, source, target))


class LocalProcessor:
    def read(self, raw, *, source, target):
        return decode_result(process_request(encode_request(raw, source, target)), source, target)


def persisted(raw: bytes) -> ArchiveMemberTargetRecord:
    source, target = prepared(raw, "proof.txt")
    return ArchiveMemberTargetRecord(
        target.inventory_id,
        target.inventory_processor_version,
        "files_archive",
        "item_archive",
        source.version_id,
        source.locator,
        source.sha256,
        source.size_bytes,
        source.media_type,
        target.locator,
        target.sha256,
        target.size_bytes,
        "text/plain",
        target.depth,
        target.parent_locator,
    )


def test_root_confined_source_revalidation_reads_exact_current_archive(tmp_path: Path) -> None:
    raw = zip_bytes([("proof.txt", b"proof")])
    (tmp_path / "bundle.zip").write_bytes(raw)
    result = read_persisted_archive_member(tmp_path, persisted(raw), LocalProcessor())
    assert result.raw == b"proof"


def test_root_confined_source_revalidation_refuses_mutation_and_symlink(tmp_path: Path) -> None:
    raw = zip_bytes([("proof.txt", b"proof")])
    record = persisted(raw)
    path = tmp_path / "bundle.zip"
    path.write_bytes(raw + b"changed")
    with pytest.raises(ArchiveUnavailable):
        read_persisted_archive_member(tmp_path, record, LocalProcessor())

    path.unlink()
    outside = tmp_path / "outside.zip"
    outside.write_bytes(raw)
    path.symlink_to(outside)
    with pytest.raises(ArchiveUnavailable):
        read_persisted_archive_member(tmp_path, record, LocalProcessor())
