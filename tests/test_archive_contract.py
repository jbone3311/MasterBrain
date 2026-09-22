from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from masterbrain.datacore.archive_contract import (
    ArchiveMember,
    ArchiveResult,
    ArchiveSkip,
    ArchiveSource,
    ArchiveUnavailable,
    decode_request,
    decode_result,
    encode_request,
    encode_result,
    source_for,
)


def fixture() -> tuple[bytes, ArchiveSource]:
    raw = b"PK\x03\x04synthetic-archive-contract"
    digest = hashlib.sha256(raw).hexdigest()
    source = source_for(raw, "version_" + digest[:32], "proof.zip", digest, "application/zip")
    return raw, source


def test_request_is_exact_source_bound_and_closed() -> None:
    raw, source = fixture()
    request = encode_request(
        raw, source.version_id, source.locator, source.sha256, source.media_type
    )
    assert decode_request(request) == (raw, source)

    value = json.loads(request)
    value["source"]["sha256"] = "0" * 64
    with pytest.raises(ArchiveUnavailable):
        decode_request(json.dumps(value).encode())
    value["source"]["sha256"] = source.sha256
    value["ambient_config"] = True
    with pytest.raises(ArchiveUnavailable):
        decode_request(json.dumps(value).encode())


def test_result_is_closed_bounded_and_rejects_host_paths() -> None:
    _, source = fixture()
    member = ArchiveMember("folder/a.txt", "a" * 64, 5, 5, "text/plain", 0, None, False)
    skip = ArchiveSkip(".hidden", "dotfile", 0, None)
    result = ArchiveResult(
        source,
        "complete",
        "bounded_archive_v1",
        "zip",
        (member,),
        (skip,),
        1,
        5,
    )
    assert decode_result(encode_result(result), source) == result

    value = json.loads(encode_result(result))
    value["members"][0]["locator"] = "/tmp/leaked.txt"
    with pytest.raises(ArchiveUnavailable):
        decode_result(json.dumps(value).encode(), source)

    value = json.loads(encode_result(result))
    value["source"]["locator"] = "substituted.zip"
    with pytest.raises(ArchiveUnavailable):
        decode_result(json.dumps(value).encode(), source)


@pytest.mark.parametrize(
    "result",
    [
        ("refused", "bomb_suspected", True),
        ("refused", "duplicate_member", False),
        ("refused", "unsupported_format", False),
        ("failed", "invalid_archive", False),
    ],
)
def test_terminal_outcomes_cannot_publish_members(result: tuple[str, str, bool]) -> None:
    _, source = fixture()
    status, reason, bomb = result
    format_name = None if reason == "unsupported_format" else "zip"
    terminal = ArchiveResult(source, status, reason, format_name, bomb_suspected=bomb)
    assert decode_result(encode_result(terminal), source) == terminal

    member = ArchiveMember("a.txt", "a" * 64, 1, 1, "text/plain", 0, None, False)
    with pytest.raises(ArchiveUnavailable):
        decode_result(encode_result(replace(terminal, members=(member,), file_count=1)), source)


@pytest.mark.parametrize(
    "locator",
    ["../escape.zip", "/absolute.zip", "windows\\path.zip", "double//slash.zip", "nul\x00.zip"],
)
def test_source_locator_is_portable_relative_identity(locator: str) -> None:
    raw, source = fixture()
    with pytest.raises(ArchiveUnavailable):
        source_for(raw, source.version_id, locator, source.sha256, source.media_type)
