"""Restricted pipe-only in-memory ZIP/TAR inventory worker."""

from __future__ import annotations

import hashlib
import logging
import stat
import sys
import tarfile
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import PurePosixPath

from email_brain.mime_sandbox import _resource_limits
from masterbrain.datacore.archive_contract import (
    MAX_COMPRESSION_RATIO,
    MAX_DEPTH,
    MAX_FILE_COUNT,
    MAX_MEMBER_UNCOMPRESSED_BYTES,
    MAX_OUTPUT_BYTES,
    MAX_REQUEST_BYTES,
    MAX_TOTAL_UNCOMPRESSED_BYTES,
    ArchiveMember,
    ArchiveResult,
    ArchiveSkip,
    ArchiveSource,
    ArchiveUnavailable,
    decode_request,
    decode_result,
    encode_result,
)

_MEDIA = {
    ".csv": "text/csv",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".eml": "message/rfc822",
    ".html": "text/html",
    ".ics": "text/calendar",
    ".json": "application/json",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xml": "application/xml",
    ".zip": "application/zip",
    ".tar": "application/x-tar",
    ".gz": "application/gzip",
    ".bz2": "application/x-bzip2",
    ".xz": "application/x-xz",
}


class _Bomb(Exception):
    pass


class _Duplicate(Exception):
    pass


class _Invalid(Exception):
    pass


@dataclass(slots=True)
class _State:
    source: ArchiveSource
    members: list[ArchiveMember] = field(default_factory=list)
    skipped: list[ArchiveSkip] = field(default_factory=list)
    locators: set[str] = field(default_factory=set)
    file_count: int = 0
    total_bytes: int = 0

    def skip(self, locator: str, reason: str, depth: int, parent: str | None) -> None:
        self.skipped.append(ArchiveSkip(locator, reason, depth, parent))

    def check(self, size: int, locator: str, depth: int, parent: str | None) -> None:
        if (
            self.file_count + 1 > MAX_FILE_COUNT
            or size > MAX_MEMBER_UNCOMPRESSED_BYTES
            or self.total_bytes + size > MAX_TOTAL_UNCOMPRESSED_BYTES
        ):
            self.skip(locator, "bomb_limit", depth, parent)
            raise _Bomb()

    def commit(self, size: int) -> None:
        self.file_count += 1
        self.total_bytes += size


def _safe_name(name: str) -> str | None:
    if (
        not name
        or len(name) > 1024
        or "\\" in name
        or "\x00" in name
        or any(ord(character) < 32 or ord(character) == 127 for character in name)
    ):
        return None
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or str(path) != name or name.endswith("/"):
        return None
    try:
        name.encode("utf-8", errors="strict")
    except UnicodeError:
        return None
    return name


def _dotfile(name: str) -> bool:
    return "__MACOSX" in name or PurePosixPath(name).name.startswith(".")


def _join(prefix: str, name: str) -> str:
    return f"{prefix}/{name}" if prefix else name


def _nested_prefix(locator: str) -> str:
    path = PurePosixPath(locator)
    return str(path.parent / f"{path.stem}_unpacked")


def _media_hint(locator: str) -> str:
    return _MEDIA.get(PurePosixPath(locator).suffix.casefold(), "application/octet-stream")


def _kind(raw: bytes) -> str | None:
    stream = BytesIO(raw)
    if zipfile.is_zipfile(stream):
        return "zip"
    stream.seek(0)
    try:
        with tarfile.open(fileobj=stream, mode="r:*"):
            return "tar"
    except (tarfile.TarError, OSError, EOFError):
        return None


def _looks_corrupt_archive(raw: bytes) -> bool:
    signatures = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08", b"\x1f\x8b", b"BZh", b"\xfd7zXZ")
    return raw.startswith(signatures)


def _read_exact(stream: object, size: int) -> bytes:
    reader = getattr(stream, "read", None)
    if not callable(reader):
        raise _Invalid()
    raw = reader(size + 1)
    if type(raw) is not bytes or len(raw) != size:
        raise _Invalid()
    return raw


def _record(
    state: _State,
    raw: bytes,
    locator: str,
    declared: int,
    depth: int,
    parent: str | None,
    *,
    is_container: bool,
) -> None:
    if locator in state.locators:
        raise _Duplicate()
    state.locators.add(locator)
    state.members.append(
        ArchiveMember(
            locator,
            hashlib.sha256(raw).hexdigest(),
            declared,
            len(raw),
            _media_hint(locator),
            depth,
            parent,
            is_container,
        )
    )


def _handle_member(
    state: _State,
    raw: bytes,
    locator: str,
    declared: int,
    depth: int,
    parent: str | None,
) -> None:
    nested_kind = _kind(raw)
    if nested_kind is not None and depth < MAX_DEPTH:
        _record(state, raw, locator, declared, depth, parent, is_container=True)
        _inventory(state, raw, nested_kind, depth + 1, _nested_prefix(locator), locator)
    else:
        _record(state, raw, locator, declared, depth, parent, is_container=False)
        if nested_kind is not None:
            state.skip(locator, "depth_limit", depth, parent)


def _inventory_zip(
    state: _State, raw: bytes, depth: int, prefix: str, parent: str | None
) -> None:
    try:
        with zipfile.ZipFile(BytesIO(raw), "r") as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                locator = _join(prefix, name)
                safe = _safe_name(name)
                if safe is None:
                    state.skip(_join(prefix, "unsafe-member"), "traversal", depth, parent)
                    continue
                if _dotfile(name):
                    state.skip(locator, "dotfile", depth, parent)
                    continue
                locator = _join(prefix, safe)
                if info.flag_bits & 1:
                    state.skip(locator, "encrypted", depth, parent)
                    continue
                mode = info.external_attr >> 16
                if mode and stat.S_ISLNK(mode):
                    state.skip(locator, "link", depth, parent)
                    continue
                if (
                    info.compress_size > 0
                    and info.file_size > info.compress_size * MAX_COMPRESSION_RATIO
                ):
                    state.skip(locator, "bomb_limit", depth, parent)
                    raise _Bomb()
                if locator in state.locators:
                    raise _Duplicate()
                state.check(info.file_size, locator, depth, parent)
                try:
                    with archive.open(info, "r") as stream:
                        member_raw = _read_exact(stream, info.file_size)
                except (OSError, RuntimeError, ValueError, zipfile.BadZipFile, _Invalid):
                    state.skip(locator, "unreadable", depth, parent)
                    continue
                state.commit(info.file_size)
                _handle_member(state, member_raw, locator, info.file_size, depth, parent)
    except (_Bomb, _Duplicate):
        raise
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        raise _Invalid() from exc


def _inventory_tar(
    state: _State, raw: bytes, depth: int, prefix: str, parent: str | None
) -> None:
    try:
        with tarfile.open(fileobj=BytesIO(raw), mode="r:*") as archive:
            for info in archive:
                if info.isdir():
                    continue
                name = info.name
                locator = _join(prefix, name)
                safe = _safe_name(name)
                if safe is None:
                    state.skip(_join(prefix, "unsafe-member"), "traversal", depth, parent)
                    continue
                if _dotfile(name):
                    state.skip(locator, "dotfile", depth, parent)
                    continue
                locator = _join(prefix, safe)
                if info.issym() or info.islnk():
                    state.skip(locator, "link", depth, parent)
                    continue
                if not info.isfile():
                    state.skip(locator, "non_regular", depth, parent)
                    continue
                if locator in state.locators:
                    raise _Duplicate()
                state.check(info.size, locator, depth, parent)
                try:
                    stream = archive.extractfile(info)
                    if stream is None:
                        raise _Invalid()
                    with stream:
                        member_raw = _read_exact(stream, info.size)
                except (OSError, tarfile.TarError, _Invalid):
                    state.skip(locator, "unreadable", depth, parent)
                    continue
                state.commit(info.size)
                _handle_member(state, member_raw, locator, info.size, depth, parent)
    except (_Bomb, _Duplicate):
        raise
    except (OSError, tarfile.TarError, EOFError) as exc:
        raise _Invalid() from exc


def _inventory(
    state: _State,
    raw: bytes,
    kind: str,
    depth: int,
    prefix: str = "",
    parent: str | None = None,
) -> None:
    if kind == "zip":
        _inventory_zip(state, raw, depth, prefix, parent)
    else:
        _inventory_tar(state, raw, depth, prefix, parent)


def inventory_archive(raw: bytes, source: ArchiveSource) -> ArchiveResult:
    kind = _kind(raw)
    if kind is None:
        reason = "invalid_archive" if _looks_corrupt_archive(raw) else "unsupported_format"
        status = "failed" if reason == "invalid_archive" else "refused"
        return ArchiveResult(source, status, reason, None)
    state = _State(source)
    try:
        _inventory(state, raw, kind, 0)
    except _Bomb:
        return ArchiveResult(
            source,
            "refused",
            "bomb_suspected",
            kind,
            skipped=tuple(state.skipped),
            file_count=state.file_count,
            total_uncompressed_bytes=state.total_bytes,
            bomb_suspected=True,
        )
    except _Duplicate:
        return ArchiveResult(
            source,
            "refused",
            "duplicate_member",
            kind,
            file_count=state.file_count,
            total_uncompressed_bytes=state.total_bytes,
        )
    except _Invalid:
        if not state.members:
            return ArchiveResult(source, "failed", "invalid_archive", kind)
        state.skip(source.locator, "unreadable", 0, None)
    reason = "bounded_archive_partial_v1" if state.skipped else "bounded_archive_v1"
    status = "partial" if state.skipped else "complete"
    return ArchiveResult(
        source,
        status,
        reason,
        kind,
        tuple(state.members),
        tuple(state.skipped),
        state.file_count,
        state.total_bytes,
    )


def process_request(payload: bytes) -> bytes:
    try:
        raw, source = decode_request(payload)
        response = encode_result(inventory_archive(raw, source))
        if len(response) > MAX_OUTPUT_BYTES:
            raise ArchiveUnavailable()
        decode_result(response, source)
        return response
    except Exception:
        raise ArchiveUnavailable() from None


def main() -> int:
    try:
        _resource_limits()
        logging.disable(sys.maxsize)
        payload = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        response = process_request(payload)
        if len(response) > MAX_OUTPUT_BYTES:
            raise ArchiveUnavailable()
        sys.stdout.buffer.write(response)
        sys.stdout.buffer.flush()
        return 0
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
