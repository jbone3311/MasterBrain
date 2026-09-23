"""Explicit restricted FileOS archive caller; never used by the public API."""

from pathlib import Path

from email_brain.sandbox_runner import _ARCHIVE_PROFILE, _DockerPipe
from masterbrain.datacore.archive_contract import (
    CONTRACT,
    ArchiveResult,
    ArchiveUnavailable,
    decode_result,
    encode_request,
    source_for,
)


class DockerArchiveProcessor(_DockerPipe):
    def __init__(self, image_id: str, *, docker_binary: Path = Path("/usr/bin/docker")) -> None:
        try:
            super().__init__(image_id, docker_binary=docker_binary, profile=_ARCHIVE_PROFILE)
        except Exception:
            raise ArchiveUnavailable() from None

    @property
    def processor_version(self) -> str:
        return CONTRACT + "-" + self._image_id.removeprefix("sha256:")

    def inventory(
        self,
        raw: bytes,
        *,
        version_id: str,
        locator: str,
        sha256: str,
        media_type: str,
    ) -> ArchiveResult:
        try:
            source = source_for(raw, version_id, locator, sha256, media_type)
            request = encode_request(raw, version_id, locator, sha256, media_type)
            return self._run(request, lambda output: decode_result(output, source))
        except Exception:
            raise ArchiveUnavailable() from None
