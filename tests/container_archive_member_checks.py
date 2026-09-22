"""Explicit real restricted-image archive-member checks; not ordinary discovery."""

from __future__ import annotations

import hashlib
import io
import os
import zipfile

import pytest

from masterbrain.datacore.archive_contract import ArchiveUnavailable, source_for
from masterbrain.datacore.archive_member_contract import ArchiveMemberTarget
from masterbrain.datacore.archive_member_processor import DockerArchiveMemberProcessor


@pytest.fixture
def processor() -> DockerArchiveMemberProcessor:
    image = os.environ.get("MASTERBRAIN_ARCHIVE_IMAGE_ID")
    if not image:
        pytest.fail("explicit archive-member checks require an approved prebuilt image")
    return DockerArchiveMemberProcessor(image)


def fixture():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("unrelated.txt", b"unrelated secret")
        archive.writestr("folder/proof.txt", b"actual restricted member proof")
    raw = output.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    source = source_for(raw, "version_" + digest[:32], "proof.zip", digest, "application/zip")
    target = ArchiveMemberTarget(
        "archive_inventory_" + "b" * 32,
        "sandbox-fileos-archive-v1-" + "a" * 64,
        "folder/proof.txt",
        hashlib.sha256(b"actual restricted member proof").hexdigest(),
        len(b"actual restricted member proof"),
        0,
        None,
    )
    return raw, source, target


def test_actual_hash_bound_member_profile(processor: DockerArchiveMemberProcessor) -> None:
    raw, source, target = fixture()
    result = processor.read(raw, source=source, target=target)
    assert result.raw == b"actual restricted member proof"
    assert b"unrelated secret" not in result.raw
    assert result.scanner_status == "unscanned"


def test_actual_child_refuses_member_hash_mismatch(
    processor: DockerArchiveMemberProcessor,
) -> None:
    raw, source, target = fixture()
    wrong = ArchiveMemberTarget(
        target.inventory_id,
        target.inventory_processor_version,
        target.locator,
        "0" * 64,
        target.size_bytes,
        target.depth,
        target.parent_locator,
    )
    with pytest.raises(ArchiveUnavailable, match="^archive_processing_unavailable$"):
        processor.read(raw, source=source, target=wrong)
