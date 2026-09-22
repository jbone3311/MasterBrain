from __future__ import annotations

import hashlib
import io
import zipfile

import pytest
from test_sandbox_runner import CID, IMAGE, fake_docker

from masterbrain.datacore import archive_member_processor as parent
from masterbrain.datacore.archive_contract import ArchiveUnavailable, source_for
from masterbrain.datacore.archive_member_contract import (
    MAX_OUTPUT_BYTES,
    ArchiveMemberTarget,
    encode_request,
)
from masterbrain.datacore.archive_member_worker import process_request


def fixture():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("proof.txt", b"isolated member proof")
    raw = output.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    source = source_for(raw, "version_" + digest[:32], "proof.zip", digest, "application/zip")
    target = ArchiveMemberTarget(
        "archive_inventory_" + "b" * 32,
        "sandbox-fileos-archive-v1-" + "a" * 64,
        "proof.txt",
        hashlib.sha256(b"isolated member proof").hexdigest(),
        len(b"isolated member proof"),
        0,
        None,
    )
    return raw, source, target


def test_member_profile_is_fixed_and_pipe_only(monkeypatch) -> None:
    raw, source, target = fixture()
    request = encode_request(raw, source, target)
    processor, calls, _ = fake_docker(
        monkeypatch,
        processor=parent.DockerArchiveMemberProcessor(IMAGE),
        output=process_request(request),
    )
    result = processor.read(raw, source=source, target=target)
    assert result.raw == b"isolated member proof"
    create = next(args for args, _, _ in calls if args[:2] == ["container", "create"])
    assert create[-5:] == [
        IMAGE,
        "-I",
        "-B",
        "-m",
        "masterbrain.datacore.archive_member_worker",
    ]
    assert create[create.index("--name") + 1].startswith("eb-archive-member-")
    assert [(value, bounds) for _, value, bounds in calls if value] == [
        (request, {"limit": MAX_OUTPUT_BYTES, "timeout": 30})
    ]
    assert calls[-1][0] == ["container", "rm", "--force", CID]


def test_isolation_or_output_failure_is_content_free(monkeypatch) -> None:
    raw, source, target = fixture()
    request = encode_request(raw, source, target)
    processor, calls, _ = fake_docker(
        monkeypatch,
        processor=parent.DockerArchiveMemberProcessor(IMAGE),
        output=process_request(request),
        mutate=lambda state: state["HostConfig"].update(NetworkMode="host"),
    )
    with pytest.raises(ArchiveUnavailable, match="^archive_processing_unavailable$"):
        processor.read(raw, source=source, target=target)
    assert not any(data for _, data, _ in calls)

    processor, calls, _ = fake_docker(
        monkeypatch,
        processor=parent.DockerArchiveMemberProcessor(IMAGE),
        output=b"x" * (MAX_OUTPUT_BYTES + 1),
    )
    with pytest.raises(ArchiveUnavailable, match="^archive_processing_unavailable$"):
        processor.read(raw, source=source, target=target)
    assert calls[-1][0] == ["container", "rm", "--force", CID]
