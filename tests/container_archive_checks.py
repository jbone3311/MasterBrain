"""Explicit real restricted-image FileOS archive tests; not ordinary discovery."""

from __future__ import annotations

import hashlib
import io
import os
import zipfile

import pytest

from masterbrain.datacore.archive_contract import ArchiveUnavailable
from masterbrain.datacore.archive_processor import DockerArchiveProcessor


@pytest.fixture
def processor() -> DockerArchiveProcessor:
    image = os.environ.get("MASTERBRAIN_ARCHIVE_IMAGE_ID")
    if not image:
        pytest.fail("explicit archive container checks require an approved prebuilt image")
    return DockerArchiveProcessor(image)


def archive_bytes() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("folder/proof.txt", b"actual restricted archive proof")
    return output.getvalue()


def test_actual_source_bound_archive_profile(processor: DockerArchiveProcessor) -> None:
    raw = archive_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    result = processor.inventory(
        raw,
        version_id="version_" + digest[:32],
        locator="proof.zip",
        sha256=digest,
        media_type="application/zip",
    )
    assert (result.status, result.reason, result.format) == (
        "complete",
        "bounded_archive_v1",
        "zip",
    )
    assert [item.locator for item in result.members] == ["folder/proof.txt"]
    expected_hash = hashlib.sha256(b"actual restricted archive proof").hexdigest()
    assert result.members[0].sha256 == expected_hash


def test_actual_child_refuses_source_mismatch(processor: DockerArchiveProcessor) -> None:
    raw = archive_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ArchiveUnavailable, match="^archive_processing_unavailable$"):
        processor.inventory(
            raw,
            version_id="version_" + digest[:32],
            locator="proof.zip",
            sha256="0" * 64,
            media_type="application/zip",
        )
