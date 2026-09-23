"""Explicit real two-image archive-image OCR checks; not ordinary discovery."""

from __future__ import annotations

import hashlib
import io
import os
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from masterbrain.datacore.archive_contract import CONTRACT as ARCHIVE_CONTRACT
from masterbrain.datacore.archive_contract import source_for
from masterbrain.datacore.archive_member_image_ocr import extract_archive_member_image_ocr
from masterbrain.datacore.archive_member_processor import DockerArchiveMemberProcessor
from masterbrain.datacore.archive_worker import inventory_archive
from masterbrain.datacore.extraction import ExtractionStatus
from masterbrain.datacore.image_ocr_contract import CONTRACT as IMAGE_CONTRACT
from masterbrain.datacore.image_ocr_processor import DockerImageOcrProcessor
from masterbrain.datacore.persistence import ArchiveMemberTargetRecord


@pytest.fixture
def processors() -> tuple[DockerArchiveMemberProcessor, DockerImageOcrProcessor, str, str]:
    archive_image = os.environ.get("MASTERBRAIN_ARCHIVE_IMAGE_ID")
    image_ocr_image = os.environ.get("MASTERBRAIN_IMAGE_OCR_IMAGE_ID")
    if not archive_image or not image_ocr_image:
        pytest.fail("explicit archive-image checks require both approved prebuilt images")
    return (
        DockerArchiveMemberProcessor(archive_image),
        DockerImageOcrProcessor(image_ocr_image),
        archive_image,
        image_ocr_image,
    )


def png_with_text(text: str) -> bytes:
    image = Image.new("RGB", (1200, 260), "white")
    draw = ImageDraw.Draw(image)
    draw.text((35, 70), text, fill="black", font=ImageFont.load_default(size=54))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def blank_png() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (80, 60), "white").save(output, format="PNG")
    return output.getvalue()


def animated_gif() -> bytes:
    output = io.BytesIO()
    frames = [Image.new("RGB", (30, 30), color) for color in ("red", "blue")]
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=20,
    )
    return output.getvalue()


def fixture(
    root: Path, name: str, content: bytes, archive_image: str
) -> tuple[bytes, ArchiveMemberTargetRecord]:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, content)
        for index in range(64):
            archive.writestr(
                f"unrelated/sibling-{index:02d}.txt",
                f"sibling-secret-{index:02d}".encode(),
            )
    raw = output.getvalue()
    (root / "bundle.zip").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    source = source_for(
        raw,
        "version_" + digest[:32],
        "bundle.zip",
        digest,
        "application/zip",
    )
    member = next(item for item in inventory_archive(raw, source).members if item.locator == name)
    return raw, ArchiveMemberTargetRecord(
        "archive_inventory_" + digest[:32],
        ARCHIVE_CONTRACT + "-" + archive_image.removeprefix("sha256:"),
        "files_archive_image_container",
        "item_parent",
        source.version_id,
        source.locator,
        source.sha256,
        source.size_bytes,
        source.media_type,
        member.locator,
        member.sha256,
        member.observed_size,
        member.media_hint,
        member.depth,
        member.parent_locator,
    )


def test_actual_archive_image_chain_is_exact_and_source_preserving(
    processors: tuple[DockerArchiveMemberProcessor, DockerImageOcrProcessor, str, str],
    tmp_path: Path,
) -> None:
    archive_processor, image_processor, archive_image, image_image = processors
    raw, target = fixture(
        tmp_path,
        "nested/invoice.png",
        png_with_text("ARCHIVE INVOICE 4471"),
        archive_image,
    )
    source = tmp_path / "bundle.zip"
    before = source.stat()

    result = extract_archive_member_image_ocr(
        tmp_path, target, archive_processor, image_processor
    )

    assert result.status is ExtractionStatus.EXTRACTED
    assert result.error_code is None and result.metadata["format"] == "png"
    assert "ARCHIVE" in result.text and "4471" in result.text
    assert "sibling-secret" not in result.text
    assert result.metadata["extractor_version"] == (
        IMAGE_CONTRACT + "-" + image_image.removeprefix("sha256:")
    )
    assert source.read_bytes() == raw
    assert source.stat().st_mtime_ns == before.st_mtime_ns


@pytest.mark.parametrize(
    "name,content,expected_status,expected_reason",
    [
        ("blank.png", blank_png(), ExtractionStatus.EMPTY, "empty_ocr"),
        ("animated.gif", animated_gif(), ExtractionStatus.DEFERRED, "multiframe"),
    ],
)
def test_actual_chain_preserves_empty_and_policy_outcomes(
    processors: tuple[DockerArchiveMemberProcessor, DockerImageOcrProcessor, str, str],
    tmp_path: Path,
    name: str,
    content: bytes,
    expected_status: ExtractionStatus,
    expected_reason: str,
) -> None:
    archive_processor, image_processor, archive_image, _ = processors
    raw, target = fixture(tmp_path, name, content, archive_image)
    source = tmp_path / "bundle.zip"
    before = source.stat()
    result = extract_archive_member_image_ocr(
        tmp_path, target, archive_processor, image_processor
    )
    assert result.status is expected_status
    assert result.metadata["image_reason"] == expected_reason and not result.text
    assert source.read_bytes() == raw and source.stat().st_mtime_ns == before.st_mtime_ns


def test_actual_chain_rejects_member_identity_substitution(
    processors: tuple[DockerArchiveMemberProcessor, DockerImageOcrProcessor, str, str],
    tmp_path: Path,
) -> None:
    archive_processor, image_processor, archive_image, _ = processors
    raw, target = fixture(tmp_path, "invoice.png", png_with_text("BOUND 9182"), archive_image)
    result = extract_archive_member_image_ocr(
        tmp_path,
        replace(target, member_sha256="0" * 64),
        archive_processor,
        image_processor,
    )
    assert (result.status, result.error_code, result.text) == (
        ExtractionStatus.FAILED,
        "member_unavailable",
        "",
    )
    assert (tmp_path / "bundle.zip").read_bytes() == raw
