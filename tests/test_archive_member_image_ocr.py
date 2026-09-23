from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import ANY, Mock
from uuid import uuid4

import pytest
from PIL import Image

from masterbrain.datacore import image_ocr_worker
from masterbrain.datacore.archive_contract import source_for as archive_source_for
from masterbrain.datacore.archive_member_contract import decode_result, encode_request
from masterbrain.datacore.archive_member_image_ocr import (
    extract_archive_member_image_ocr,
    publish_extracted_archive_member_image_ocr,
)
from masterbrain.datacore.archive_member_text import archive_member_version_id
from masterbrain.datacore.archive_member_worker import process_request
from masterbrain.datacore.archive_worker import inventory_archive
from masterbrain.datacore.extraction import ExtractionResult, ExtractionStatus
from masterbrain.datacore.image_ocr_contract import (
    CONTRACT,
    ImageOcrResult,
    ImageOcrUnavailable,
    ImageSource,
)
from masterbrain.datacore.image_ocr_contract import source_for as image_source_for
from masterbrain.datacore.persistence import ArchiveMemberTargetRecord


class LocalArchiveProcessor:
    def read(self, raw, *, source, target):
        return decode_result(process_request(encode_request(raw, source, target)), source, target)


class DirectImageProcessor:
    processor_version = CONTRACT + "-" + "a" * 64

    def extract(self, raw, *, suffix, sha256, format):
        return image_ocr_worker.extract_image_ocr(
            raw, image_source_for(raw, suffix=suffix, sha256=sha256, format=format)
        )


class MustNotRun:
    processor_version = "must-not-run"

    def read(self, raw, *, source, target):
        raise AssertionError("ineligible member reached archive worker")

    def extract(self, raw, *, suffix, sha256, format):
        raise AssertionError("ineligible member reached image worker")


def image_bytes(kind: str, *, size: tuple[int, int] = (40, 30)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, "white").save(output, format=kind)
    return output.getvalue()


def fixture(name: str, content: bytes) -> tuple[bytes, ArchiveMemberTargetRecord]:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(name, content)
        archive.writestr("sibling.txt", b"sibling content must remain unread")
    raw = output.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    source = archive_source_for(
        raw, "version_" + digest[:32], "bundle.zip", digest, "application/zip"
    )
    member = next(item for item in inventory_archive(raw, source).members if item.locator == name)
    return raw, ArchiveMemberTargetRecord(
        "archive_inventory_" + "b" * 32,
        "sandbox-fileos-archive-v1-" + "a" * 64,
        "files_archive_images",
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


@pytest.mark.parametrize(
    "name,kind,expected_format,expected_mode",
    [
        ("nested/photo.jpg", "JPEG", "jpeg", "RGB"),
        ("photo.jpeg", "JPEG", "jpeg", "RGB"),
        ("photo.png", "PNG", "png", "RGB"),
        ("photo.tif", "TIFF", "tiff", "RGB"),
        ("photo.tiff", "TIFF", "tiff", "RGB"),
        ("photo.bmp", "BMP", "bmp", "RGB"),
        ("photo.gif", "GIF", "gif", "P"),
        ("photo.webp", "WEBP", "webp", "RGB"),
    ],
)
def test_exact_static_image_member_crosses_both_workers_without_sibling(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    name: str,
    kind: str,
    expected_format: str,
    expected_mode: str,
) -> None:
    archive, target = fixture(name, image_bytes(kind))
    source = tmp_path / "bundle.zip"
    source.write_bytes(archive)
    before = source.stat()
    monkeypatch.setattr(image_ocr_worker, "_ocr", lambda image: "  INVOICE 4471  ")

    result = extract_archive_member_image_ocr(
        tmp_path, target, LocalArchiveProcessor(), DirectImageProcessor()
    )

    assert result.status is ExtractionStatus.EXTRACTED
    assert result.text == "INVOICE 4471" and "sibling content" not in result.text
    assert result.error_code is None
    assert result.metadata == {
        "extractor_version": CONTRACT + "-" + "a" * 64,
        "format": expected_format,
        "image_reason": "bounded_image_ocr_v1",
        "truncated": False,
        "detected_format": expected_format,
        "width": 40,
        "height": 30,
        "mode": expected_mode,
        "frame_count": 1,
    }
    assert source.read_bytes() == archive and source.stat().st_mtime_ns == before.st_mtime_ns


def test_blank_image_is_explicit_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    archive, target = fixture("blank.png", image_bytes("PNG"))
    (tmp_path / "bundle.zip").write_bytes(archive)
    monkeypatch.setattr(image_ocr_worker, "_ocr", lambda image: "  ")
    result = extract_archive_member_image_ocr(
        tmp_path, target, LocalArchiveProcessor(), DirectImageProcessor()
    )
    assert result.status is ExtractionStatus.EMPTY
    assert result.text == "" and result.error_code is None
    assert result.metadata["image_reason"] == "empty_ocr"


def test_unsupported_and_over_limit_refuse_before_either_worker(tmp_path: Path) -> None:
    _, unsupported = fixture("note.txt", b"not an image")
    result = extract_archive_member_image_ocr(tmp_path, unsupported, MustNotRun(), MustNotRun())
    assert (result.status, result.error_code) == (
        ExtractionStatus.UNSUPPORTED,
        "unsupported_image_type",
    )

    _, image = fixture("photo.png", image_bytes("PNG"))
    result = extract_archive_member_image_ocr(
        tmp_path,
        replace(image, member_size_bytes=8 * 1024 * 1024 + 1),
        MustNotRun(),
        MustNotRun(),
    )
    assert (result.status, result.error_code) == (
        ExtractionStatus.DEFERRED,
        "image_byte_limit",
    )


def test_archive_and_image_worker_faults_fail_closed(tmp_path: Path) -> None:
    archive, target = fixture("photo.png", image_bytes("PNG"))
    (tmp_path / "bundle.zip").write_bytes(archive)
    missing = extract_archive_member_image_ocr(
        tmp_path / "missing", target, LocalArchiveProcessor(), DirectImageProcessor()
    )
    assert (missing.status, missing.error_code) == (
        ExtractionStatus.FAILED,
        "member_unavailable",
    )

    failed_processor = Mock(processor_version=CONTRACT + "-failed")
    failed_processor.extract.side_effect = ImageOcrUnavailable()
    failed = extract_archive_member_image_ocr(
        tmp_path, target, LocalArchiveProcessor(), failed_processor
    )
    assert (failed.status, failed.error_code) == (
        ExtractionStatus.FAILED,
        "image_processor_unavailable",
    )

    crashed_processor = Mock(processor_version=CONTRACT + "-crashed")
    crashed_processor.extract.side_effect = RuntimeError("worker detail must not escape")
    crashed = extract_archive_member_image_ocr(
        tmp_path, target, LocalArchiveProcessor(), crashed_processor
    )
    assert (crashed.status, crashed.error_code) == (
        ExtractionStatus.FAILED,
        "image_processor_unavailable",
    )


def test_substituted_image_result_fails_parent_revalidation(tmp_path: Path) -> None:
    archive, target = fixture("photo.png", image_bytes("PNG"))
    (tmp_path / "bundle.zip").write_bytes(archive)
    substituted = Mock(processor_version=CONTRACT + "-substituted")
    substituted.extract.return_value = ImageOcrResult(
        ImageSource("0" * 64, target.member_size_bytes, ".png", "png"),
        "extracted",
        "bounded_image_ocr_v1",
        "png",
        40,
        30,
        "RGB",
        1,
        text="substituted",
    )
    result = extract_archive_member_image_ocr(
        tmp_path, target, LocalArchiveProcessor(), substituted
    )
    assert (result.status, result.error_code, result.text) == (
        ExtractionStatus.FAILED,
        "image_processor_unavailable",
        "",
    )


def test_format_masquerade_and_bad_processor_version_fail_closed(tmp_path: Path) -> None:
    archive, target = fixture("renamed.png", image_bytes("JPEG"))
    (tmp_path / "bundle.zip").write_bytes(archive)
    masquerade = extract_archive_member_image_ocr(
        tmp_path, target, LocalArchiveProcessor(), DirectImageProcessor()
    )
    assert (masquerade.status, masquerade.error_code) == (
        ExtractionStatus.FAILED,
        "image_processor_unavailable",
    )

    archive, target = fixture("photo.png", image_bytes("PNG"))
    (tmp_path / "bundle.zip").write_bytes(archive)
    invalid_version = DirectImageProcessor()
    invalid_version.processor_version = ""
    result = extract_archive_member_image_ocr(
        tmp_path, target, LocalArchiveProcessor(), invalid_version
    )
    assert (result.status, result.error_code) == (
        ExtractionStatus.FAILED,
        "image_processor_unavailable",
    )


def test_animation_is_bounded_deferred(tmp_path: Path) -> None:
    output = io.BytesIO()
    frames = [Image.new("RGB", (20, 20), color) for color in ("red", "blue")]
    frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:])
    archive, target = fixture("animated.gif", output.getvalue())
    (tmp_path / "bundle.zip").write_bytes(archive)
    result = extract_archive_member_image_ocr(
        tmp_path, target, LocalArchiveProcessor(), DirectImageProcessor()
    )
    assert (result.status, result.error_code, result.text) == (
        ExtractionStatus.DEFERRED,
        "multiframe",
        "",
    )


def accepted_publication_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[ArchiveMemberTargetRecord, ExtractionResult]:
    archive, target = fixture("nested/photo.png", image_bytes("PNG"))
    (tmp_path / "bundle.zip").write_bytes(archive)
    monkeypatch.setattr(image_ocr_worker, "_ocr", lambda image: "  IMAGE PROOF  ")
    extraction = extract_archive_member_image_ocr(
        tmp_path, target, LocalArchiveProcessor(), DirectImageProcessor()
    )
    assert extraction.status is ExtractionStatus.EXTRACTED
    return target, extraction


def test_publication_wrapper_accepts_only_complete_bound_image_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target, extraction = accepted_publication_fixture(monkeypatch, tmp_path)
    core = Mock()
    key = uuid4()
    published = object()
    core.publish_archive_member_image_ocr.return_value = published

    assert (
        publish_extracted_archive_member_image_ocr(
            core,
            object(),
            target,
            extraction,
            code_revision="unit-v1",
            idempotency_key=key,
        )
        is published
    )
    core.publish_archive_member_image_ocr.assert_called_once_with(
        ANY,
        target,
        "IMAGE PROOF",
        CONTRACT + "-" + "a" * 64,
        "png",
        "png",
        40,
        30,
        "RGB",
        1,
        False,
        "unit-v1",
        key,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("extractor_version", ""),
        ("extractor_version", "worker\x00version"),
        ("extractor_version", CONTRACT + "-synthetic-unit"),
        ("format", "jpeg"),
        ("detected_format", "jpeg"),
        ("image_reason", "empty_ocr"),
        ("width", 0),
        ("width", True),
        ("height", 25_000_001),
        ("height", 625_001),
        ("mode", ""),
        ("mode", "RGB\x00"),
        ("frame_count", 2),
        ("frame_count", True),
        ("truncated", 0),
    ],
)
def test_publication_wrapper_rejects_malformed_image_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    target, extraction = accepted_publication_fixture(monkeypatch, tmp_path)
    core = Mock()
    malformed = replace(extraction, metadata={**extraction.metadata, field: value})
    with pytest.raises(ValueError, match="not an accepted extraction"):
        publish_extracted_archive_member_image_ocr(
            core,
            object(),
            target,
            malformed,
            code_revision="unit-v1",
            idempotency_key=uuid4(),
        )
    core.publish_archive_member_image_ocr.assert_not_called()


def test_publication_wrapper_rejects_incomplete_or_unbound_results(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target, extraction = accepted_publication_fixture(monkeypatch, tmp_path)
    variants = [
        replace(extraction, version_id="version_stale"),
        replace(extraction, locator="other.png"),
        replace(extraction, status=ExtractionStatus.EMPTY),
        replace(extraction, text=""),
        replace(extraction, text="bad\x00text"),
        replace(extraction, text=" untrimmed"),
        replace(extraction, text="x" * 5_001),
        replace(extraction, error_code="unexpected"),
        replace(extraction, metadata={**extraction.metadata, "extra": "not admitted"}),
        replace(
            extraction,
            metadata={
                key: value
                for key, value in extraction.metadata.items()
                if key != "detected_format"
            },
        ),
    ]
    for invalid in variants:
        core = Mock()
        with pytest.raises(ValueError, match="not an accepted extraction"):
            publish_extracted_archive_member_image_ocr(
                core,
                object(),
                target,
                invalid,
                code_revision="unit-v1",
                idempotency_key=uuid4(),
            )
        core.publish_archive_member_image_ocr.assert_not_called()

    core = Mock()
    oversized = replace(target, member_size_bytes=8 * 1024 * 1024 + 1)
    oversized_extraction = replace(
        extraction,
        version_id=archive_member_version_id(oversized),
    )
    with pytest.raises(ValueError, match="not an accepted extraction"):
        publish_extracted_archive_member_image_ocr(
            core,
            object(),
            oversized,
            oversized_extraction,
            code_revision="unit-v1",
            idempotency_key=uuid4(),
        )
    core.publish_archive_member_image_ocr.assert_not_called()
