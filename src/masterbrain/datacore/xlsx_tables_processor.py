"""Restricted XLSX table caller; no public API or publishing path."""

from __future__ import annotations

from pathlib import Path

from email_brain.sandbox_runner import _XLSX_TABLE_PROFILE, _DockerPipe
from masterbrain.datacore.document_contract import DocumentUnavailable, encode_request, source_for
from masterbrain.datacore.xlsx_tables import (
    CONTRACT,
    XlsxTableProjection,
    decode_projection,
)


class DockerXlsxTableProcessor(_DockerPipe):
    def __init__(self, image_id: str, *, docker_binary: Path = Path("/usr/bin/docker")) -> None:
        try:
            super().__init__(image_id, docker_binary=docker_binary, profile=_XLSX_TABLE_PROFILE)
        except Exception:
            raise DocumentUnavailable() from None

    @property
    def processor_version(self) -> str:
        return CONTRACT + "-" + self._image_id.removeprefix("sha256:")

    def extract(
        self, raw: bytes, *, version_id: str, locator: str, sha256: str, media_type: str,
    ) -> XlsxTableProjection:
        try:
            source = source_for(raw, version_id, locator, sha256, media_type)
            if source.format != "xlsx":
                raise DocumentUnavailable()
            request = encode_request(raw, version_id, locator, sha256, media_type)
            return self._run(request, lambda output: decode_projection(output, source))
        except Exception:
            raise DocumentUnavailable() from None
