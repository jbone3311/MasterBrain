"""Bounded, descriptor-relative reads of regular FileOS source files."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path


class ConfinedFileUnavailable(Exception):
    """The locator cannot be opened as a regular file within its root."""


class ConfinedFileChanged(Exception):
    """The opened file or its locator changed while it was read."""


class ConfinedFileTooLarge(Exception):
    """The opened file exceeds the caller's read budget."""


@dataclass(frozen=True, slots=True)
class ConfinedRead:
    sha256: str
    size_bytes: int
    mtime_ns: int
    device: int
    inode: int
    raw: bytes | None


def _parts(locator: str) -> tuple[str, ...]:
    if (
        not isinstance(locator, str)
        or not 1 <= len(locator) <= 4000
        or "\\" in locator
        or "\x00" in locator
        or any(part in {"", ".", ".."} for part in locator.split("/"))
    ):
        raise ConfinedFileUnavailable()
    return tuple(locator.split("/"))


def _open_confined_descriptor(root: Path, locator: str) -> int:
    """Open only regular bytes below root; never follow an ancestor or leaf link."""
    parts = _parts(locator)
    if not root.is_absolute() or any(part in {"", ".", ".."} for part in root.parts[1:]):
        raise ConfinedFileUnavailable()
    directory_flag = getattr(os, "O_DIRECTORY", None)
    nofollow_flag = getattr(os, "O_NOFOLLOW", None)
    if directory_flag is None or nofollow_flag is None:
        raise ConfinedFileUnavailable()
    opened: list[int] = []
    try:
        directory = os.open(root.anchor, os.O_RDONLY | directory_flag | nofollow_flag)
        opened.append(directory)
        for part in (*root.parts[1:], *parts[:-1]):
            directory = os.open(
                part, os.O_RDONLY | directory_flag | nofollow_flag, dir_fd=directory
            )
            opened.append(directory)
        leaf = os.open(parts[-1], os.O_RDONLY | nofollow_flag | os.O_NONBLOCK, dir_fd=directory)
        try:
            regular = stat.S_ISREG(os.fstat(leaf).st_mode)
        except OSError:
            os.close(leaf)
            raise
        if not regular:
            os.close(leaf)
            raise ConfinedFileUnavailable()
        return leaf
    except (OSError, ValueError) as exc:
        raise ConfinedFileUnavailable() from exc
    finally:
        for descriptor in reversed(opened):
            os.close(descriptor)


def stat_confined_file(
    root: Path, locator: str, *, root_identity: tuple[int, int]
) -> os.stat_result:
    """Stat a regular leaf through no-follow directories without opening its bytes.

    This is for metadata-only inventory, including cloud placeholders that must not
    be materialized by opening the file. The root identity is bound to the scan's
    initial observation, and a second traversal rejects locator replacement.
    """
    parts = _parts(locator)
    if not root.is_absolute() or any(part in {"", ".", ".."} for part in root.parts[1:]):
        raise ConfinedFileUnavailable()
    directory_flag = getattr(os, "O_DIRECTORY", None)
    nofollow_flag = getattr(os, "O_NOFOLLOW", None)
    if directory_flag is None or nofollow_flag is None:
        raise ConfinedFileUnavailable()

    def observe() -> os.stat_result:
        opened: list[int] = []
        try:
            directory = os.open(root.anchor, os.O_RDONLY | directory_flag | nofollow_flag)
            opened.append(directory)
            for part in root.parts[1:]:
                directory = os.open(
                    part, os.O_RDONLY | directory_flag | nofollow_flag, dir_fd=directory
                )
                opened.append(directory)
            root_info = os.fstat(directory)
            if (root_info.st_dev, root_info.st_ino) != root_identity:
                raise ConfinedFileChanged()
            for part in parts[:-1]:
                directory = os.open(
                    part, os.O_RDONLY | directory_flag | nofollow_flag, dir_fd=directory
                )
                opened.append(directory)
            info = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                raise ConfinedFileUnavailable()
            return info
        except (OSError, ValueError) as exc:
            raise ConfinedFileUnavailable() from exc
        finally:
            for descriptor in reversed(opened):
                os.close(descriptor)

    before = observe()
    try:
        after = observe()
    except ConfinedFileUnavailable as exc:
        raise ConfinedFileChanged() from exc
    if _identity(before) != _identity(after):
        raise ConfinedFileChanged()
    return after


def _identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def read_confined_file(
    root: Path, locator: str, *, max_bytes: int, capture_bytes: bool
) -> ConfinedRead:
    """Hash or read a stable, bounded regular file and recheck its locator."""
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 0:
        raise ValueError("invalid confined read budget")
    try:
        authorized_root = root.resolve(strict=True)
        if authorized_root != root or not authorized_root.is_dir():
            raise ConfinedFileUnavailable()
        file_fd = _open_confined_descriptor(authorized_root, locator)
        try:
            before = os.fstat(file_fd)
            if before.st_size > max_bytes:
                raise ConfinedFileTooLarge()
            digest = hashlib.sha256()
            chunks: list[bytes] | None = [] if capture_bytes else None
            total = 0
            while True:
                chunk = os.read(file_fd, min(8192, max_bytes + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ConfinedFileTooLarge()
                digest.update(chunk)
                if chunks is not None:
                    chunks.append(chunk)
            after = os.fstat(file_fd)
            if total != before.st_size or _identity(before) != _identity(after):
                raise ConfinedFileChanged()
        finally:
            os.close(file_fd)
        try:
            check_fd = _open_confined_descriptor(authorized_root, locator)
        except ConfinedFileUnavailable as exc:
            raise ConfinedFileChanged() from exc
        try:
            if _identity(os.fstat(check_fd)) != _identity(after):
                raise ConfinedFileChanged()
        finally:
            os.close(check_fd)
        return ConfinedRead(
            digest.hexdigest(),
            total,
            after.st_mtime_ns,
            after.st_dev,
            after.st_ino,
            b"".join(chunks) if chunks is not None else None,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        raise ConfinedFileUnavailable() from exc
