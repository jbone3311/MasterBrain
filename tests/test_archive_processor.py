"""Parent archive boundary and fixed-profile regression, without local Docker."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from unittest.mock import Mock

import pytest
from test_sandbox_runner import CID, IMAGE, fake_docker

from masterbrain.datacore import archive_processor as parent
from masterbrain.datacore.archive_contract import (
    MAX_OUTPUT_BYTES,
    ArchiveUnavailable,
    encode_request,
)
from masterbrain.datacore.archive_worker import process_request


def fixture() -> tuple[bytes, str, str]:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("proof.txt", b"isolated archive parent proof")
    raw = output.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    return raw, "version_" + digest[:32], digest


def prepared(monkeypatch, **kwargs):
    raw, version_id, digest = fixture()
    request = encode_request(raw, version_id, "proof.zip", digest, "application/zip")
    processor, calls, _ = fake_docker(
        monkeypatch,
        processor=parent.DockerArchiveProcessor(IMAGE),
        output=process_request(request),
        **kwargs,
    )
    return processor, raw, version_id, digest, request, calls


def test_archive_profile_uses_only_bounded_pipes_and_fixed_child(monkeypatch) -> None:
    processor, raw, version_id, digest, request, calls = prepared(monkeypatch)
    result = processor.inventory(
        raw,
        version_id=version_id,
        locator="proof.zip",
        sha256=digest,
        media_type="application/zip",
    )
    assert result.reason == "bounded_archive_v1"
    assert [item.locator for item in result.members] == ["proof.txt"]
    assert processor.processor_version == "sandbox-fileos-archive-v1-" + "a" * 64
    create = next(args for args, _, _ in calls if args[:2] == ["container", "create"])
    assert create[-5:] == [IMAGE, "-I", "-B", "-m", "masterbrain.datacore.archive_worker"]
    assert create[create.index("--name") + 1].startswith("eb-archive-")
    assert all("parent proof" not in arg and digest not in arg for arg in create)
    assert [(args, value, bounds) for args, value, bounds in calls if value] == [
        (
            ["container", "start", "--attach", "--interactive", CID],
            request,
            {"limit": MAX_OUTPUT_BYTES, "timeout": 30},
        )
    ]
    assert calls[-1][0] == ["container", "rm", "--force", CID]


def test_archive_isolation_failure_prevents_source_disclosure(monkeypatch) -> None:
    processor, raw, version_id, digest, _, calls = prepared(
        monkeypatch, mutate=lambda state: state["HostConfig"].update(NetworkMode="host")
    )
    with pytest.raises(ArchiveUnavailable):
        processor.inventory(
            raw,
            version_id=version_id,
            locator="proof.zip",
            sha256=digest,
            media_type="application/zip",
        )
    assert not any(data for _, data, _ in calls)
    assert calls[-1][0] == ["container", "rm", "--force", CID]


def test_substituted_archive_source_is_rejected_and_cleaned(monkeypatch) -> None:
    raw, version_id, digest = fixture()
    request = encode_request(raw, version_id, "proof.zip", digest, "application/zip")
    output = json.loads(process_request(request))
    output["source"]["sha256"] = "c" * 64
    processor, calls, _ = fake_docker(
        monkeypatch,
        processor=parent.DockerArchiveProcessor(IMAGE),
        output=json.dumps(output).encode(),
    )
    with pytest.raises(ArchiveUnavailable):
        processor.inventory(
            raw,
            version_id=version_id,
            locator="proof.zip",
            sha256=digest,
            media_type="application/zip",
        )
    assert calls[-1][0] == ["container", "rm", "--force", CID]


def test_invalid_input_never_invokes_docker(monkeypatch) -> None:
    processor = parent.DockerArchiveProcessor(IMAGE)
    invoke = Mock(side_effect=AssertionError("must not invoke"))
    monkeypatch.setattr(processor, "_invoke", invoke)
    raw, version_id, _ = fixture()
    with pytest.raises(ArchiveUnavailable):
        processor.inventory(
            raw,
            version_id=version_id,
            locator="../proof.zip",
            sha256="a" * 64,
            media_type="application/zip",
        )
    invoke.assert_not_called()


def test_worker_failure_and_oversized_output_are_one_closed_error(monkeypatch) -> None:
    processor, raw, version_id, digest, _, calls = prepared(monkeypatch, started_error=True)
    with pytest.raises(ArchiveUnavailable, match="^archive_processing_unavailable$"):
        processor.inventory(
            raw,
            version_id=version_id,
            locator="proof.zip",
            sha256=digest,
            media_type="application/zip",
        )
    assert calls[-1][0] == ["container", "rm", "--force", CID]

    processor, calls, _ = fake_docker(
        monkeypatch,
        processor=parent.DockerArchiveProcessor(IMAGE),
        output=b"x" * (MAX_OUTPUT_BYTES + 1),
    )
    with pytest.raises(ArchiveUnavailable, match="^archive_processing_unavailable$"):
        processor.inventory(
            raw,
            version_id=version_id,
            locator="proof.zip",
            sha256=digest,
            media_type="application/zip",
        )
    assert calls[-1][0] == ["container", "rm", "--force", CID]
