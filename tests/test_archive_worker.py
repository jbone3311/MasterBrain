from __future__ import annotations

import hashlib
import io
import stat
import struct
import tarfile
import zipfile

import pytest

from masterbrain.datacore.archive_contract import (
    ArchiveUnavailable,
    decode_result,
    encode_request,
    source_for,
)
from masterbrain.datacore.archive_worker import inventory_archive, process_request


def zip_bytes(members: list[tuple[str, bytes]], *, compression: int = zipfile.ZIP_STORED) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
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


def source(raw: bytes, name: str = "fixture.zip"):
    digest = hashlib.sha256(raw).hexdigest()
    media_type = "application/zip" if name.endswith(".zip") else "application/gzip"
    return source_for(raw, "version_" + digest[:32], name, digest, media_type)


@pytest.mark.parametrize(
    "raw,name,kind",
    [
        (zip_bytes([("b.txt", b"bravo"), ("folder/a.txt", b"alpha")]), "fixture.zip", "zip"),
        (tar_bytes([("b.txt", b"bravo"), ("folder/a.txt", b"alpha")]), "fixture.tar.gz", "tar"),
    ],
)
def test_zip_and_tar_inventory_preserve_order_hashes_and_no_member_bytes(
    raw: bytes, name: str, kind: str
) -> None:
    result = inventory_archive(raw, source(raw, name))
    assert (result.status, result.reason, result.format) == (
        "complete",
        "bounded_archive_v1",
        kind,
    )
    assert [item.locator for item in result.members] == ["b.txt", "folder/a.txt"]
    assert [item.sha256 for item in result.members] == [
        hashlib.sha256(b"bravo").hexdigest(),
        hashlib.sha256(b"alpha").hexdigest(),
    ]
    assert result.file_count == 2 and result.total_uncompressed_bytes == 10
    encoded = process_request(
        encode_request(
            raw,
            result.source.version_id,
            name,
            result.source.sha256,
            result.source.media_type,
        )
    )
    assert b"bravo" not in encoded and b"alpha" not in encoded
    assert decode_result(encoded, result.source) == result


def test_nested_archives_share_identity_depth_and_parent_provenance() -> None:
    inner = tar_bytes([("proof.txt", b"nested proof")])
    outer = zip_bytes([("before.txt", b"before"), ("inner.tar.gz", inner)])
    result = inventory_archive(outer, source(outer))
    assert [item.locator for item in result.members] == [
        "before.txt",
        "inner.tar.gz",
        "inner.tar_unpacked/proof.txt",
    ]
    container = result.members[1]
    child = result.members[2]
    assert container.is_container is True and container.depth == 0
    assert child.parent_locator == "inner.tar.gz" and child.depth == 1
    assert result.file_count == 3
    assert result.total_uncompressed_bytes == len(b"before") + len(inner) + len(b"nested proof")


def test_traversal_dotfiles_and_links_are_explicit_and_never_manifested() -> None:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, raw in [("../escape.txt", b"no"), (".hidden", b"no"), ("good.txt", b"yes")]:
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
        link = tarfile.TarInfo("outside-link")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        archive.addfile(link)
    raw = output.getvalue()
    result = inventory_archive(raw, source(raw, "fixture.tar.gz"))
    assert result.status == "partial"
    assert [item.locator for item in result.members] == ["good.txt"]
    assert {item.reason for item in result.skipped} == {"traversal", "dotfile", "link"}
    assert all(
        not item.locator.startswith("/") and ".." not in item.locator
        for item in result.skipped
    )


def test_zip_symlink_is_refused() -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        link = zipfile.ZipInfo("link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, "/etc/passwd")
        archive.writestr("good.txt", b"yes")
    raw = output.getvalue()
    result = inventory_archive(raw, source(raw))
    assert [item.locator for item in result.members] == ["good.txt"]
    assert [(item.locator, item.reason) for item in result.skipped] == [("link", "link")]


def test_encrypted_flag_is_refused_without_opening_member() -> None:
    raw = bytearray(zip_bytes([("secret.txt", b"ciphertext marker")]))
    local = raw.find(b"PK\x03\x04")
    central = raw.find(b"PK\x01\x02")
    assert local >= 0 and central >= 0
    struct.pack_into("<H", raw, local + 6, struct.unpack_from("<H", raw, local + 6)[0] | 1)
    struct.pack_into("<H", raw, central + 8, struct.unpack_from("<H", raw, central + 8)[0] | 1)
    encrypted = bytes(raw)
    result = inventory_archive(encrypted, source(encrypted))
    assert result.status == "partial" and result.members == ()
    assert [(item.locator, item.reason) for item in result.skipped] == [
        ("secret.txt", "encrypted")
    ]


def test_ratio_bomb_refuses_all_prior_members() -> None:
    raw = zip_bytes(
        [("before.txt", b"safe"), ("bomb.bin", b"0" * (1024 * 1024))],
        compression=zipfile.ZIP_DEFLATED,
    )
    result = inventory_archive(raw, source(raw))
    assert (result.status, result.reason, result.bomb_suspected) == (
        "refused",
        "bomb_suspected",
        True,
    )
    assert result.members == ()
    assert result.file_count == 1 and result.total_uncompressed_bytes == 4


def test_cumulative_limits_are_global_across_nested_archives(monkeypatch) -> None:
    import masterbrain.datacore.archive_worker as worker

    inner = zip_bytes([("inside.txt", b"5678")])
    outer = zip_bytes([("first.txt", b"1234"), ("inner.zip", inner)])
    monkeypatch.setattr(worker, "MAX_TOTAL_UNCOMPRESSED_BYTES", len(b"1234") + len(inner) + 3)
    result = inventory_archive(outer, source(outer))
    assert result.reason == "bomb_suspected" and result.members == ()
    assert any(item.locator == "inner_unpacked/inside.txt" for item in result.skipped)


def test_member_and_file_count_limits_publish_nothing(monkeypatch) -> None:
    import masterbrain.datacore.archive_worker as worker

    raw = zip_bytes([("one.txt", b"1"), ("two.txt", b"22")])
    monkeypatch.setattr(worker, "MAX_MEMBER_UNCOMPRESSED_BYTES", 1)
    member_limited = inventory_archive(raw, source(raw))
    assert member_limited.reason == "bomb_suspected" and member_limited.members == ()

    monkeypatch.setattr(worker, "MAX_MEMBER_UNCOMPRESSED_BYTES", 64 * 1024 * 1024)
    monkeypatch.setattr(worker, "MAX_FILE_COUNT", 1)
    count_limited = inventory_archive(raw, source(raw))
    assert count_limited.reason == "bomb_suspected" and count_limited.members == ()


def test_duplicate_safe_locator_refuses_whole_manifest() -> None:
    with pytest.warns(UserWarning, match="Duplicate name"):
        raw = zip_bytes([("same.txt", b"first"), ("same.txt", b"second")])
    result = inventory_archive(raw, source(raw))
    assert (result.status, result.reason, result.members) == ("refused", "duplicate_member", ())


def test_depth_limit_keeps_hash_bound_container_without_expanding() -> None:
    nested = zip_bytes([("leaf.txt", b"leaf")])
    for level in range(4, -1, -1):
        nested = zip_bytes([(f"level-{level}.zip", nested)])
    result = inventory_archive(nested, source(nested))
    assert result.status == "partial"
    depth_skip = next(item for item in result.skipped if item.reason == "depth_limit")
    assert depth_skip.depth == 3
    retained = next(item for item in result.members if item.locator == depth_skip.locator)
    assert retained.is_container is False and retained.depth == 3


def test_crc_failure_is_partial_and_does_not_publish_corrupt_member() -> None:
    raw = bytearray(zip_bytes([("bad.txt", b"targetpayload"), ("good.txt", b"good")]))
    offset = raw.find(b"targetpayload")
    assert offset >= 0
    raw[offset : offset + len(b"targetpayload")] = b"corruptbytes!"
    corrupt = bytes(raw)
    result = inventory_archive(corrupt, source(corrupt))
    assert result.status == "partial"
    assert [item.locator for item in result.members] == ["good.txt"]
    assert [(item.locator, item.reason) for item in result.skipped] == [
        ("bad.txt", "unreadable")
    ]


@pytest.mark.parametrize(
    "name",
    [
        "..\\..\\evil.txt",
        "/absolute.txt",
        "folder/../../escape.txt",
        "control-\x01.txt",
        "double//slash.txt",
    ],
)
def test_hostile_names_never_become_manifest_locators(name: str) -> None:
    raw = zip_bytes([(name, b"hostile"), ("good.txt", b"good")])
    result = inventory_archive(raw, source(raw))
    assert [item.locator for item in result.members] == ["good.txt"]
    assert [item.reason for item in result.skipped] == ["traversal"]


@pytest.mark.parametrize(
    "raw,expected",
    [
        (b"plain text", ("refused", "unsupported_format")),
        (b"PK\x03\x04truncated", ("failed", "invalid_archive")),
    ],
)
def test_unsupported_and_corrupt_roots_are_closed(raw: bytes, expected: tuple[str, str]) -> None:
    result = inventory_archive(raw, source(raw))
    assert (result.status, result.reason) == expected
    assert result.members == ()


def test_contract_failure_is_one_non_content_error() -> None:
    with pytest.raises(ArchiveUnavailable, match="^archive_processing_unavailable$"):
        process_request(b'{"not":"the contract"}')
