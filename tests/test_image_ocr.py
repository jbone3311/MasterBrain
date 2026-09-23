from __future__ import annotations

import hashlib
import json
import struct
import zlib
from io import BytesIO

import pytest
from PIL import Image

from masterbrain.datacore import image_ocr_worker as worker
from masterbrain.datacore.image_ocr_contract import (
    MAX_TEXT_CHARS,
    ImageOcrResult,
    ImageOcrUnavailable,
    decode_request,
    decode_result,
    encode_request,
    encode_result,
    source_for,
)


def image_bytes(kind: str, *, size: tuple[int, int] = (40, 30)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, "white").save(output, format=kind)
    return output.getvalue()


def identity(raw: bytes, suffix: str, kind: str):
    digest = hashlib.sha256(raw).hexdigest()
    return source_for(raw, suffix=suffix, sha256=digest, format=kind), digest


@pytest.mark.parametrize(
    "pillow_kind,suffix,kind",
    [
        ("JPEG", ".jpg", "jpeg"),
        ("PNG", ".png", "png"),
        ("TIFF", ".tif", "tiff"),
        ("BMP", ".bmp", "bmp"),
        ("GIF", ".gif", "gif"),
        ("WEBP", ".webp", "webp"),
    ],
)
def test_closed_contract_and_full_decode_for_six_static_formats(
    monkeypatch: pytest.MonkeyPatch, pillow_kind: str, suffix: str, kind: str
) -> None:
    raw = image_bytes(pillow_kind)
    source, digest = identity(raw, suffix, kind)
    request = encode_request(raw, suffix=suffix, sha256=digest, format=kind)
    assert decode_request(request) == (raw, source)
    monkeypatch.setattr(worker, "_ocr", lambda image: "  INVOICE NUMBER 4471  ")
    result = decode_result(worker.process_request(request), source)
    assert (result.status, result.reason, result.detected_format) == (
        "extracted",
        "bounded_image_ocr_v1",
        kind,
    )
    assert result.text == "INVOICE NUMBER 4471"
    assert (result.width, result.height, result.frame_count) == (40, 30, 1)


def test_request_rejects_hash_suffix_format_signature_and_unknown_fields() -> None:
    raw = image_bytes("PNG")
    _, digest = identity(raw, ".png", "png")
    for suffix, kind, sha in [
        (".jpg", "jpeg", digest),
        (".png", "jpeg", digest),
        (".png", "png", "0" * 64),
        (".heic", "heic", digest),
    ]:
        with pytest.raises(ImageOcrUnavailable):
            encode_request(raw, suffix=suffix, sha256=sha, format=kind)
    value = json.loads(encode_request(raw, suffix=".png", sha256=digest, format="png"))
    value["extra"] = True
    with pytest.raises(ImageOcrUnavailable):
        decode_request(json.dumps(value).encode())
    value.pop("extra")
    value["ocr"] = 1
    with pytest.raises(ImageOcrUnavailable):
        decode_request(json.dumps(value).encode())


def test_result_rejects_substitution_unbounded_text_and_fake_scanner_status() -> None:
    raw = image_bytes("PNG")
    source, _ = identity(raw, ".png", "png")
    good = ImageOcrResult(
        source, "extracted", "bounded_image_ocr_v1", "png", 40, 30, "RGB", 1,
        text="proof",
    )
    for field, value in [
        ("engine", "ambient-tesseract"),
        ("scanner_status", "safe"),
        ("text", "x" * (MAX_TEXT_CHARS + 1)),
        ("frame_count", 2),
    ]:
        payload = json.loads(encode_result(good))
        payload[field] = value
        with pytest.raises(ImageOcrUnavailable):
            decode_result(json.dumps(payload).encode(), source)


def test_truncation_empty_and_timeout_are_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = image_bytes("PNG")
    source, digest = identity(raw, ".png", "png")
    request = encode_request(raw, suffix=".png", sha256=digest, format="png")
    monkeypatch.setattr(worker, "_ocr", lambda image: "x" * (MAX_TEXT_CHARS + 10))
    truncated = decode_result(worker.process_request(request), source)
    assert len(truncated.text) == MAX_TEXT_CHARS
    assert truncated.truncated and truncated.warnings == ("ocr_text_truncated",)
    monkeypatch.setattr(worker, "_ocr", lambda image: "  ")
    empty = decode_result(worker.process_request(request), source)
    assert (empty.status, empty.reason, empty.text) == ("extracted", "empty_ocr", "")

    def timeout(image: object) -> str:
        raise worker._OcrTimeout()

    monkeypatch.setattr(worker, "_ocr", timeout)
    delayed = decode_result(worker.process_request(request), source)
    assert (delayed.status, delayed.reason, delayed.text) == ("deferred", "ocr_timeout", "")


def test_animated_image_corrupt_body_and_header_bomb_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = BytesIO()
    frames = [Image.new("RGB", (20, 20), color) for color in ("red", "blue")]
    frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:], duration=10)
    animated = output.getvalue()
    source, _ = identity(animated, ".gif", "gif")
    monkeypatch.setattr(worker, "_ocr", lambda image: pytest.fail("must not OCR animation"))
    result = worker.extract_image_ocr(animated, source)
    assert (result.status, result.reason) == ("deferred", "multiframe")

    corrupt = b"\x89PNG\r\n\x1a\n" + b"broken"
    source, _ = identity(corrupt, ".png", "png")
    assert worker.extract_image_ocr(corrupt, source).reason == "invalid_image"

    data = struct.pack(">IIBBBBB", 50_000, 50_000, 8, 2, 0, 0, 0)
    def png_chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    bomb = b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", data)
    bomb += png_chunk(b"IDAT", zlib.compress(b"\x00" * 3)) + png_chunk(b"IEND", b"")
    source, _ = identity(bomb, ".png", "png")
    assert worker.extract_image_ocr(bomb, source).reason == "pixel_limit"
