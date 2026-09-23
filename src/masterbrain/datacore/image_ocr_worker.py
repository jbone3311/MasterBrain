"""Restricted pipe-only raster OCR worker."""

from __future__ import annotations

import logging
import os
import sys
from io import BytesIO

from email_brain.mime_sandbox import _resource_limits
from masterbrain.datacore.image_ocr_contract import (
    MAX_OUTPUT_BYTES,
    MAX_PIXELS,
    MAX_REQUEST_BYTES,
    MAX_TEXT_CHARS,
    OCR_ENGINE,
    OCR_TIMEOUT_SECONDS,
    ImageOcrResult,
    ImageOcrUnavailable,
    ImageSource,
    decode_request,
    decode_result,
    encode_result,
)

_PILLOW_VERSION = "11.3.0"
_PYTESSERACT_VERSION = "0.3.13"
_PILLOW_FORMATS = {
    "JPEG": "jpeg", "PNG": "png", "TIFF": "tiff", "BMP": "bmp",
    "GIF": "gif", "WEBP": "webp",
}


class _OcrTimeout(Exception):
    pass


def _outcome(
    source: ImageSource, status: str, reason: str, *, detected_format: str | None = None,
    width: int | None = None, height: int | None = None, mode: str | None = None,
    frame_count: int | None = None, text: str = "", truncated: bool = False,
) -> ImageOcrResult:
    warnings = ("ocr_text_truncated",) if truncated else ()
    return ImageOcrResult(
        source, status, reason, detected_format, width, height, mode, frame_count,
        OCR_ENGINE, text, truncated, warnings,
    )


def _ocr(image: object) -> str:
    import pytesseract  # type: ignore[import-untyped]

    if pytesseract.__version__ != _PYTESSERACT_VERSION:
        raise ImageOcrUnavailable()
    if str(pytesseract.get_tesseract_version()).split()[0] != "5.5.0":
        raise ImageOcrUnavailable()
    try:
        value = pytesseract.image_to_string(
            image, lang="eng", config="--psm 3", timeout=OCR_TIMEOUT_SECONDS
        )
    except RuntimeError:
        raise _OcrTimeout() from None
    if type(value) is not str:
        raise ImageOcrUnavailable()
    return value


def extract_image_ocr(raw: bytes, source: ImageSource) -> ImageOcrResult:
    try:
        import PIL
        from PIL import Image, UnidentifiedImageError

        if PIL.__version__ != _PILLOW_VERSION:
            raise ImageOcrUnavailable()
        try:
            with Image.open(BytesIO(raw)) as opened:
                detected = _PILLOW_FORMATS.get(opened.format or "")
                if detected != source.format:
                    return _outcome(source, "failed", "invalid_image")
                width, height = int(opened.width), int(opened.height)
                if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
                    return _outcome(source, "deferred", "pixel_limit")
                frames = int(getattr(opened, "n_frames", 1))
                if frames != 1 or bool(getattr(opened, "is_animated", False)):
                    return _outcome(source, "deferred", "multiframe")
                mode = str(opened.mode)
                if not 1 <= len(mode) <= 16:
                    return _outcome(source, "failed", "invalid_image")
                opened.load()
                image = opened.convert("RGB")
            try:
                raw_text = _ocr(image).replace("\x00", "").strip()
            finally:
                image.close()
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            return _outcome(source, "deferred", "pixel_limit")
        except UnidentifiedImageError:
            return _outcome(source, "failed", "invalid_image")
        except _OcrTimeout:
            return _outcome(
                source, "deferred", "ocr_timeout", detected_format=detected,
                width=width, height=height, mode=mode, frame_count=frames,
            )
        except (OSError, SyntaxError, ValueError):
            return _outcome(source, "failed", "invalid_image")
        truncated = len(raw_text) > MAX_TEXT_CHARS
        text = raw_text[:MAX_TEXT_CHARS].strip()
        return _outcome(
            source, "extracted", "bounded_image_ocr_v1" if text else "empty_ocr",
            detected_format=detected, width=width, height=height, mode=mode,
            frame_count=frames, text=text, truncated=truncated,
        )
    except ImageOcrUnavailable:
        raise
    except Exception:
        raise ImageOcrUnavailable() from None


def process_request(payload: bytes) -> bytes:
    try:
        raw, source = decode_request(payload)
        response = encode_result(extract_image_ocr(raw, source))
        decode_result(response, source)
        if len(response) > MAX_OUTPUT_BYTES:
            raise ImageOcrUnavailable()
        return response
    except Exception:
        raise ImageOcrUnavailable() from None


def main() -> int:
    try:
        _resource_limits()
        logging.disable(sys.maxsize)
        os.environ["TMPDIR"] = "/dev/shm"
        payload = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        response = process_request(payload)
        sys.stdout.buffer.write(response)
        sys.stdout.buffer.flush()
        return 0
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
