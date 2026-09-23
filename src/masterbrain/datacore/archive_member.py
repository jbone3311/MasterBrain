"""Root-confined revalidation and isolated read of one persisted archive member."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path, PurePosixPath
from typing import Protocol

from masterbrain.datacore.archive_contract import (
    MAX_ARCHIVE_BYTES,
    ArchiveSource,
    ArchiveUnavailable,
)
from masterbrain.datacore.archive_member_contract import (
    ArchiveMemberResult,
    ArchiveMemberTarget,
)
from masterbrain.datacore.persistence import ArchiveMemberTargetRecord


class ArchiveMemberProcessor(Protocol):
    def read(
        self, raw: bytes, *, source: ArchiveSource, target: ArchiveMemberTarget
    ) -> ArchiveMemberResult: ...


def _read_confined(root: Path, locator: str) -> tuple[bytes, os.stat_result, os.stat_result]:
    relative = PurePosixPath(locator)
    if not locator or relative.is_absolute() or ".." in relative.parts or "\\" in locator:
        raise ArchiveUnavailable()
    authorized_root = root.resolve(strict=True)
    if not authorized_root.is_dir():
        raise ArchiveUnavailable()
    directory = os.open(authorized_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    opened: list[int] = [directory]
    try:
        for part in relative.parts[:-1]:
            directory = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
            )
            opened.append(directory)
        file_fd = os.open(
            relative.parts[-1],
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=directory,
        )
        opened.append(file_fd)
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode):
            raise ArchiveUnavailable()
        chunks: list[bytes] = []
        remaining = MAX_ARCHIVE_BYTES + 1
        while remaining:
            chunk = os.read(file_fd, min(remaining, 1024 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(file_fd)
        return b"".join(chunks), before, after
    except Exception:
        raise ArchiveUnavailable() from None
    finally:
        for descriptor in reversed(opened):
            try:
                os.close(descriptor)
            except OSError:
                pass


def read_persisted_archive_member(
    root: Path,
    record: ArchiveMemberTargetRecord,
    processor: ArchiveMemberProcessor,
) -> ArchiveMemberResult:
    """Reopen the exact source and release at most one independently verified member."""
    try:
        if not isinstance(record, ArchiveMemberTargetRecord):
            raise ArchiveUnavailable()
        source = ArchiveSource(
            record.source_version_id,
            record.source_locator,
            record.source_sha256,
            record.source_size_bytes,
            record.source_media_type,
        )
        target = ArchiveMemberTarget(
            record.inventory_id,
            record.inventory_processor_version,
            record.member_locator,
            record.member_sha256,
            record.member_size_bytes,
            record.member_depth,
            record.member_parent_locator,
        )
        raw, before, after = _read_confined(root, source.locator)
        if (
            len(raw) > MAX_ARCHIVE_BYTES
            or len(raw) != source.size_bytes
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or hashlib.sha256(raw).hexdigest() != source.sha256
        ):
            raise ArchiveUnavailable()
        result = processor.read(raw, source=source, target=target)
        if result.source != source or result.target != target:
            raise ArchiveUnavailable()
        return result
    except Exception:
        raise ArchiveUnavailable() from None
