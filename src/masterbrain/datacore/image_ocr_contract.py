"""Closed byte-bound pipe contract for isolated raster OCR."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from email_brain.mime_sandbox import _invalid_constant, _json_budget, _unique_object

CONTRACT = "sandbox-fileos-image-ocr-v1"
OCR_ENGINE = "tesseract-5.5.0-eng"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_REQUEST_BYTES = 12 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
MAX_PIXELS = 25_000_000
MAX_TEXT_CHARS = 5_000
MAX_TEXT_BYTES = 20_000
OCR_TIMEOUT_SECONDS = 20

_HASH = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_SUFFIX_FORMAT = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".tif": "tiff",
    ".tiff": "tiff",
    ".bmp": "bmp",
    ".gif": "gif",
    ".webp": "webp",
}
_SIGNATURES: dict[str, Callable[[bytes], bool]] = {
    "jpeg": lambda raw: raw.startswith(b"\xff\xd8\xff"),
    "png": lambda raw: raw.startswith(b"\x89PNG\r\n\x1a\n"),
    "tiff": lambda raw: raw.startswith((b"II*\x00", b"MM\x00*")),
    "bmp": lambda raw: raw.startswith(b"BM"),
    "gif": lambda raw: raw.startswith((b"GIF87a", b"GIF89a")),
    "webp": lambda raw: len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP",
}
_OUTCOMES = {
    "bounded_image_ocr_v1": "extracted",
    "empty_ocr": "extracted",
    "pixel_limit": "deferred",
    "multiframe": "deferred",
    "ocr_timeout": "deferred",
    "invalid_image": "failed",
}
_WARNINGS = {"ocr_text_truncated"}


class ImageOcrUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("image_ocr_processing_unavailable")


@dataclass(frozen=True, slots=True)
class ImageSource:
    sha256: str
    size_bytes: int
    suffix: str
    format: str

    def __post_init__(self) -> None:
        if (
            type(self.sha256) is not str
            or not _HASH.fullmatch(self.sha256)
            or type(self.size_bytes) is not int
            or not 0 < self.size_bytes <= MAX_IMAGE_BYTES
            or type(self.suffix) is not str
            or _SUFFIX_FORMAT.get(self.suffix) != self.format
        ):
            raise ImageOcrUnavailable()


@dataclass(frozen=True, slots=True)
class ImageOcrResult:
    source: ImageSource
    status: str
    reason: str
    detected_format: str | None = None
    width: int | None = None
    height: int | None = None
    mode: str | None = None
    frame_count: int | None = None
    engine: str = OCR_ENGINE
    text: str = ""
    truncated: bool = False
    warnings: tuple[str, ...] = ()
    scanner_status: str = "unscanned"


def source_for(raw: bytes, *, suffix: str, sha256: str, format: str) -> ImageSource:
    try:
        if type(raw) is not bytes:
            raise ImageOcrUnavailable()
        source = ImageSource(sha256, len(raw), suffix, format)
        if hashlib.sha256(raw).hexdigest() != sha256 or not _SIGNATURES[format](raw):
            raise ImageOcrUnavailable()
        return source
    except Exception:
        raise ImageOcrUnavailable() from None


def _fields(value: Any, expected: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise ImageOcrUnavailable()
    return value


def _load(payload: bytes, limit: int) -> dict[str, Any]:
    try:
        if type(payload) is not bytes or not 0 < len(payload) <= limit:
            raise ImageOcrUnavailable()
        text = payload.decode("utf-8", errors="strict")
        _json_budget(text)
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        if type(value) is not dict:
            raise ImageOcrUnavailable()
        return value
    except Exception:
        raise ImageOcrUnavailable() from None


def _dump(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode()


def encode_request(raw: bytes, *, suffix: str, sha256: str, format: str) -> bytes:
    source = source_for(raw, suffix=suffix, sha256=sha256, format=format)
    return _dump(
        {
            "contract_version": CONTRACT,
            "source": asdict(source),
            "ocr": True,
            "raw_base64": base64.b64encode(raw).decode("ascii"),
        }
    )


def decode_request(payload: bytes) -> tuple[bytes, ImageSource]:
    try:
        value = _fields(
            _load(payload, MAX_REQUEST_BYTES),
            {"contract_version", "source", "ocr", "raw_base64"},
        )
        if (
            value["contract_version"] != CONTRACT
            or value["ocr"] is not True
            or type(value["raw_base64"]) is not str
        ):
            raise ImageOcrUnavailable()
        encoded = value["raw_base64"]
        if len(encoded) > 4 * ((MAX_IMAGE_BYTES + 2) // 3):
            raise ImageOcrUnavailable()
        raw = base64.b64decode(encoded, validate=True)
        if base64.b64encode(raw).decode("ascii") != encoded:
            raise ImageOcrUnavailable()
        data = _fields(value["source"], {"sha256", "size_bytes", "suffix", "format"})
        source = source_for(
            raw,
            suffix=data["suffix"],
            sha256=data["sha256"],
            format=data["format"],
        )
        if asdict(source) != data:
            raise ImageOcrUnavailable()
        return raw, source
    except Exception:
        raise ImageOcrUnavailable() from None


def encode_result(result: ImageOcrResult) -> bytes:
    return _dump({"contract_version": CONTRACT, **asdict(result)})


def _optional_int(value: object, maximum: int) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 1 <= value <= maximum:
        raise ImageOcrUnavailable()
    return value


def decode_result(payload: bytes, source: ImageSource) -> ImageOcrResult:
    """Validate every field returned by the untrusted worker."""
    try:
        value = _fields(
            _load(payload, MAX_OUTPUT_BYTES),
            {
                "contract_version", "source", "status", "reason", "detected_format",
                "width", "height", "mode", "frame_count", "engine", "text",
                "truncated", "warnings", "scanner_status",
            },
        )
        source_data = _fields(value["source"], {"sha256", "size_bytes", "suffix", "format"})
        reason = value["reason"]
        if (
            type(source) is not ImageSource
            or source_data != asdict(source)
            or value["contract_version"] != CONTRACT
            or type(reason) is not str
            or reason not in _OUTCOMES
            or value["status"] != _OUTCOMES[reason]
            or value["engine"] != OCR_ENGINE
            or value["scanner_status"] != "unscanned"
            or type(value["text"]) is not str
            or type(value["truncated"]) is not bool
            or type(value["warnings"]) is not list
        ):
            raise ImageOcrUnavailable()
        text = value["text"]
        text_bytes = text.encode("utf-8", errors="strict")
        warnings = tuple(value["warnings"])
        if (
            len(text) > MAX_TEXT_CHARS
            or len(text_bytes) > MAX_TEXT_BYTES
            or "\x00" in text
            or text != text.strip()
            or len(warnings) != len(set(warnings))
            or any(type(item) is not str or item not in _WARNINGS for item in warnings)
            or value["truncated"] != ("ocr_text_truncated" in warnings)
        ):
            raise ImageOcrUnavailable()
        detected = value["detected_format"]
        mode = value["mode"]
        width = _optional_int(value["width"], MAX_PIXELS)
        height = _optional_int(value["height"], MAX_PIXELS)
        frames = _optional_int(value["frame_count"], 1)
        has_metadata = all(item is not None for item in (detected, width, height, mode, frames))
        if (
            (detected is not None and detected != source.format)
            or (mode is not None and (type(mode) is not str or not 1 <= len(mode) <= 16))
            or (width is not None and height is not None and width * height > MAX_PIXELS)
            or (reason in {"bounded_image_ocr_v1", "empty_ocr"} and not has_metadata)
            or (reason == "bounded_image_ocr_v1" and not text)
            or (reason == "empty_ocr" and text)
            or (value["status"] != "extracted" and (text or value["truncated"] or warnings))
        ):
            raise ImageOcrUnavailable()
        return ImageOcrResult(
            source=source, status=value["status"], reason=reason,
            detected_format=detected, width=width, height=height, mode=mode,
            frame_count=frames, engine=value["engine"], text=text,
            truncated=value["truncated"], warnings=warnings,
        )
    except Exception:
        raise ImageOcrUnavailable() from None
