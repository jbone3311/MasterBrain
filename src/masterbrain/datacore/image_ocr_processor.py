"""Explicit restricted image OCR caller; never used by the public API."""

from pathlib import Path

from email_brain.sandbox_runner import _IMAGE_OCR_PROFILE, _DockerPipe
from masterbrain.datacore.image_ocr_contract import (
    CONTRACT,
    ImageOcrResult,
    ImageOcrUnavailable,
    decode_result,
    encode_request,
    source_for,
)


class DockerImageOcrProcessor(_DockerPipe):
    def __init__(self, image_id: str, *, docker_binary: Path = Path("/usr/bin/docker")) -> None:
        try:
            super().__init__(image_id, docker_binary=docker_binary, profile=_IMAGE_OCR_PROFILE)
        except Exception:
            raise ImageOcrUnavailable() from None

    @property
    def processor_version(self) -> str:
        return CONTRACT + "-" + self._image_id.removeprefix("sha256:")

    def extract(self, raw: bytes, *, suffix: str, sha256: str, format: str) -> ImageOcrResult:
        try:
            source = source_for(raw, suffix=suffix, sha256=sha256, format=format)
            request = encode_request(raw, suffix=suffix, sha256=sha256, format=format)
            return self._run(request, lambda output: decode_result(output, source))
        except Exception:
            raise ImageOcrUnavailable() from None
