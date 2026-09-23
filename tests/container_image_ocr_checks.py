"""Explicit real restricted-image OCR tests; not ordinary discovery."""

from __future__ import annotations

import hashlib
import os
from io import BytesIO

import pytest
from PIL import Image, ImageDraw, ImageFont

from masterbrain.datacore.image_ocr_contract import ImageOcrUnavailable
from masterbrain.datacore.image_ocr_processor import DockerImageOcrProcessor


@pytest.fixture
def processor() -> DockerImageOcrProcessor:
    image = os.environ.get("MASTERBRAIN_IMAGE_OCR_IMAGE_ID")
    if not image:
        pytest.fail("explicit image OCR checks require an approved prebuilt image")
    return DockerImageOcrProcessor(image)


def png_with_text(text: str) -> bytes:
    image = Image.new("RGB", (1200, 260), "white")
    draw = ImageDraw.Draw(image)
    draw.text((35, 70), text, fill="black", font=ImageFont.load_default(size=54))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_actual_restricted_ocr_and_empty_image(processor: DockerImageOcrProcessor) -> None:
    raw = png_with_text("INVOICE NUMBER 4471")
    digest = hashlib.sha256(raw).hexdigest()
    result = processor.extract(raw, suffix=".png", sha256=digest, format="png")
    assert (result.status, result.reason, result.detected_format) == (
        "extracted",
        "bounded_image_ocr_v1",
        "png",
    )
    assert "INVOICE" in result.text and "4471" in result.text
    assert (result.width, result.height, result.frame_count) == (1200, 260, 1)
    assert result.engine == "tesseract-5.3.0-eng" and result.scanner_status == "unscanned"

    output = BytesIO()
    Image.new("RGB", (80, 60), "white").save(output, format="PNG")
    blank = output.getvalue()
    result = processor.extract(
        blank,
        suffix=".png",
        sha256=hashlib.sha256(blank).hexdigest(),
        format="png",
    )
    assert (result.status, result.reason, result.text) == ("extracted", "empty_ocr", "")


def test_actual_worker_refuses_animation_and_parent_refuses_mismatch(
    processor: DockerImageOcrProcessor,
) -> None:
    output = BytesIO()
    frames = [Image.new("RGB", (30, 30), color) for color in ("red", "blue")]
    frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:], duration=20)
    raw = output.getvalue()
    result = processor.extract(
        raw,
        suffix=".gif",
        sha256=hashlib.sha256(raw).hexdigest(),
        format="gif",
    )
    assert (result.status, result.reason, result.text) == ("deferred", "multiframe", "")
    with pytest.raises(ImageOcrUnavailable):
        processor.extract(
            raw,
            suffix=".png",
            sha256=hashlib.sha256(raw).hexdigest(),
            format="png",
        )
