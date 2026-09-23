"""Closed source-bound pipe contract for isolated FileOS archive inventory."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any

from email_brain.mime_sandbox import _invalid_constant, _json_budget, _unique_object

CONTRACT = "sandbox-fileos-archive-v1"
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_REQUEST_BYTES = 44 * 1024 * 1024
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_MEMBER_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_FILE_COUNT = 2_000
MAX_COMPRESSION_RATIO = 100
MAX_DEPTH = 3

_HASH = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_VERSION = re.compile(r"version_[a-f0-9]{32}\Z", re.ASCII)
_MEDIA_TYPES = {
    "application/zip",
    "application/x-tar",
    "application/gzip",
    "application/x-bzip2",
    "application/x-xz",
    "application/octet-stream",
}
_FORMATS = {"zip", "tar"}
_STATUSES = {"complete", "partial", "refused", "failed"}
_REASONS = {
    "bounded_archive_v1",
    "bounded_archive_partial_v1",
    "bomb_suspected",
    "duplicate_member",
    "unsupported_format",
    "invalid_archive",
}
_SKIP_REASONS = {
    "dotfile",
    "traversal",
    "encrypted",
    "link",
    "non_regular",
    "depth_limit",
    "unreadable",
    "bomb_limit",
}


class ArchiveUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("archive_processing_unavailable")


def _locator(value: object) -> str:
    if type(value) is not str or not 1 <= len(value) <= 1024 or "\x00" in value or "\\" in value:
        raise ArchiveUnavailable()
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) != value or value.endswith("/"):
        raise ArchiveUnavailable()
    value.encode("utf-8", errors="strict")
    return value


@dataclass(frozen=True, slots=True)
class ArchiveSource:
    version_id: str
    locator: str
    sha256: str
    size_bytes: int
    media_type: str

    def __post_init__(self) -> None:
        _locator(self.locator)
        if (
            type(self.version_id) is not str
            or not _VERSION.fullmatch(self.version_id)
            or type(self.sha256) is not str
            or not _HASH.fullmatch(self.sha256)
            or type(self.size_bytes) is not int
            or not 0 < self.size_bytes <= MAX_ARCHIVE_BYTES
            or type(self.media_type) is not str
            or self.media_type not in _MEDIA_TYPES
        ):
            raise ArchiveUnavailable()


@dataclass(frozen=True, slots=True)
class ArchiveMember:
    locator: str
    sha256: str
    declared_size: int
    observed_size: int
    media_hint: str
    depth: int
    parent_locator: str | None
    is_container: bool


@dataclass(frozen=True, slots=True)
class ArchiveSkip:
    locator: str
    reason: str
    depth: int
    parent_locator: str | None


@dataclass(frozen=True, slots=True)
class ArchiveResult:
    source: ArchiveSource
    status: str
    reason: str
    format: str | None
    members: tuple[ArchiveMember, ...] = ()
    skipped: tuple[ArchiveSkip, ...] = ()
    file_count: int = 0
    total_uncompressed_bytes: int = 0
    bomb_suspected: bool = False
    scanner_status: str = "unscanned"


def source_for(
    raw: bytes, version_id: str, locator: str, sha256: str, media_type: str
) -> ArchiveSource:
    try:
        source = ArchiveSource(version_id, locator, sha256, len(raw), media_type)
        if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != sha256:
            raise ArchiveUnavailable()
        return source
    except Exception:
        raise ArchiveUnavailable() from None


def _fields(value: Any, expected: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise ArchiveUnavailable()
    return value


def _load(payload: bytes, limit: int) -> dict[str, Any]:
    try:
        if type(payload) is not bytes or not 0 < len(payload) <= limit:
            raise ArchiveUnavailable()
        text = payload.decode("utf-8", errors="strict")
        _json_budget(text)
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        if type(value) is not dict:
            raise ArchiveUnavailable()
        return value
    except Exception:
        raise ArchiveUnavailable() from None


def _dump(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode()


def encode_request(
    raw: bytes, version_id: str, locator: str, sha256: str, media_type: str
) -> bytes:
    source = source_for(raw, version_id, locator, sha256, media_type)
    return _dump(
        {
            "contract_version": CONTRACT,
            "source": asdict(source),
            "raw_base64": base64.b64encode(raw).decode("ascii"),
        }
    )


def decode_request(payload: bytes) -> tuple[bytes, ArchiveSource]:
    try:
        value = _fields(
            _load(payload, MAX_REQUEST_BYTES), {"contract_version", "source", "raw_base64"}
        )
        if value["contract_version"] != CONTRACT or type(value["raw_base64"]) is not str:
            raise ArchiveUnavailable()
        encoded = value["raw_base64"]
        if len(encoded) > 4 * ((MAX_ARCHIVE_BYTES + 2) // 3):
            raise ArchiveUnavailable()
        raw = base64.b64decode(encoded, validate=True)
        if base64.b64encode(raw).decode("ascii") != encoded:
            raise ArchiveUnavailable()
        source_data = _fields(
            value["source"], {"version_id", "locator", "sha256", "size_bytes", "media_type"}
        )
        source = source_for(
            raw,
            source_data["version_id"],
            source_data["locator"],
            source_data["sha256"],
            source_data["media_type"],
        )
        if asdict(source) != source_data:
            raise ArchiveUnavailable()
        return raw, source
    except Exception:
        raise ArchiveUnavailable() from None


def encode_result(result: ArchiveResult) -> bytes:
    return _dump({"contract_version": CONTRACT, **asdict(result)})


def _parent(value: object) -> str | None:
    if value is None:
        return None
    return _locator(value)


def _member(value: object) -> ArchiveMember:
    data = _fields(
        value,
        {
            "locator",
            "sha256",
            "declared_size",
            "observed_size",
            "media_hint",
            "depth",
            "parent_locator",
            "is_container",
        },
    )
    if (
        type(data["sha256"]) is not str
        or not _HASH.fullmatch(data["sha256"])
        or type(data["declared_size"]) is not int
        or type(data["observed_size"]) is not int
        or not 0 <= data["declared_size"] <= MAX_MEMBER_UNCOMPRESSED_BYTES
        or data["observed_size"] != data["declared_size"]
        or type(data["media_hint"]) is not str
        or not 1 <= len(data["media_hint"]) <= 100
        or type(data["depth"]) is not int
        or not 0 <= data["depth"] <= MAX_DEPTH
        or type(data["is_container"]) is not bool
    ):
        raise ArchiveUnavailable()
    return ArchiveMember(
        _locator(data["locator"]),
        data["sha256"],
        data["declared_size"],
        data["observed_size"],
        data["media_hint"],
        data["depth"],
        _parent(data["parent_locator"]),
        data["is_container"],
    )


def _skip(value: object) -> ArchiveSkip:
    data = _fields(value, {"locator", "reason", "depth", "parent_locator"})
    if (
        type(data["reason"]) is not str
        or data["reason"] not in _SKIP_REASONS
        or type(data["depth"]) is not int
        or not 0 <= data["depth"] <= MAX_DEPTH
    ):
        raise ArchiveUnavailable()
    return ArchiveSkip(
        _locator(data["locator"]),
        data["reason"],
        data["depth"],
        _parent(data["parent_locator"]),
    )


def decode_result(payload: bytes, source: ArchiveSource) -> ArchiveResult:
    """Treat the entire isolated-child response as untrusted."""
    try:
        value = _fields(
            _load(payload, MAX_OUTPUT_BYTES),
            {
                "contract_version",
                "source",
                "status",
                "reason",
                "format",
                "members",
                "skipped",
                "file_count",
                "total_uncompressed_bytes",
                "bomb_suspected",
                "scanner_status",
            },
        )
        source_data = _fields(
            value["source"], {"version_id", "locator", "sha256", "size_bytes", "media_type"}
        )
        if (
            type(source) is not ArchiveSource
            or source_data != asdict(source)
            or value["contract_version"] != CONTRACT
            or value["scanner_status"] != "unscanned"
            or value["status"] not in _STATUSES
            or value["reason"] not in _REASONS
            or value["format"] not in _FORMATS | {None}
            or type(value["members"]) is not list
            or type(value["skipped"]) is not list
            or len(value["members"]) > MAX_FILE_COUNT
            or len(value["skipped"]) > MAX_FILE_COUNT + 1
            or type(value["file_count"]) is not int
            or not 0 <= value["file_count"] <= MAX_FILE_COUNT
            or type(value["total_uncompressed_bytes"]) is not int
            or not 0 <= value["total_uncompressed_bytes"] <= MAX_TOTAL_UNCOMPRESSED_BYTES
            or type(value["bomb_suspected"]) is not bool
        ):
            raise ArchiveUnavailable()
        members = tuple(_member(item) for item in value["members"])
        skipped = tuple(_skip(item) for item in value["skipped"])
        locators = [item.locator for item in members]
        if len(set(locators)) != len(locators) or value["file_count"] < len(members):
            raise ArchiveUnavailable()
        if sum(item.declared_size for item in members) > value["total_uncompressed_bytes"]:
            raise ArchiveUnavailable()
        expected = {
            "bounded_archive_v1": ("complete", False),
            "bounded_archive_partial_v1": ("partial", False),
            "bomb_suspected": ("refused", True),
            "duplicate_member": ("refused", False),
            "unsupported_format": ("refused", False),
            "invalid_archive": ("failed", False),
        }[value["reason"]]
        if (value["status"], value["bomb_suspected"]) != expected:
            raise ArchiveUnavailable()
        if value["status"] in {"refused", "failed"} and members:
            raise ArchiveUnavailable()
        if value["reason"] == "unsupported_format" and value["format"] is not None:
            raise ArchiveUnavailable()
        return ArchiveResult(
            source,
            value["status"],
            value["reason"],
            value["format"],
            members,
            skipped,
            value["file_count"],
            value["total_uncompressed_bytes"],
            value["bomb_suspected"],
        )
    except Exception:
        raise ArchiveUnavailable() from None
