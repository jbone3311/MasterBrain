"""Explicit isolated archive-member caller; never used by the public API."""

from pathlib import Path

from email_brain.sandbox_runner import _ARCHIVE_MEMBER_PROFILE, _DockerPipe
from masterbrain.datacore.archive_contract import ArchiveSource, ArchiveUnavailable, source_for
from masterbrain.datacore.archive_member_contract import (
    CONTRACT,
    ArchiveMemberResult,
    ArchiveMemberTarget,
    decode_result,
    encode_request,
)


class DockerArchiveMemberProcessor(_DockerPipe):
    def __init__(self, image_id: str, *, docker_binary: Path = Path("/usr/bin/docker")) -> None:
        try:
            super().__init__(image_id, docker_binary=docker_binary, profile=_ARCHIVE_MEMBER_PROFILE)
        except Exception:
            raise ArchiveUnavailable() from None

    @property
    def processor_version(self) -> str:
        return CONTRACT + "-" + self._image_id.removeprefix("sha256:")

    def read(
        self, raw: bytes, *, source: ArchiveSource, target: ArchiveMemberTarget
    ) -> ArchiveMemberResult:
        try:
            if source_for(
                raw, source.version_id, source.locator, source.sha256, source.media_type
            ) != source:
                raise ArchiveUnavailable()
            request = encode_request(raw, source, target)
            return self._run(request, lambda output: decode_result(output, source, target))
        except Exception:
            raise ArchiveUnavailable() from None
