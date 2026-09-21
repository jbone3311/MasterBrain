"""Explicit restricted PDF caller, not a MIME Recovery processor or public API."""

from pathlib import Path

from email_brain.pdf_contract import (
    CONTRACT,
    PdfResult,
    PdfUnavailable,
    decode_result,
    encode_request,
    source_for,
)
from email_brain.sandbox_runner import _PDF_PROFILE, _DockerPipe


class DockerPdfProcessor(_DockerPipe):
    def __init__(self, image_id: str, *, docker_binary: Path = Path("/usr/bin/docker")) -> None:
        try:
            super().__init__(image_id, docker_binary=docker_binary, profile=_PDF_PROFILE)
        except Exception:
            raise PdfUnavailable() from None

    @property
    def processor_version(self) -> str:
        return CONTRACT + "-" + self._image_id.removeprefix("sha256:")

    def extract(self, raw: bytes, *, part_path: str, part_sha256: str) -> PdfResult:
        try:
            source = source_for(raw, part_path, part_sha256)
            request = encode_request(raw, part_path, part_sha256)
            return self._run(request, lambda output: decode_result(output, source))
        except Exception:
            raise PdfUnavailable() from None
