"""Closed hash-bound contract for reading one accepted archive member."""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import asdict, dataclass

from masterbrain.datacore.archive_contract import (
    MAX_ARCHIVE_BYTES,
    ArchiveSource,
    ArchiveUnavailable,
    _dump,
    _fields,
    _load,
    _locator,
    source_for,
)

CONTRACT = "sandbox-fileos-archive-member-v1"
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_REQUEST_BYTES = 44 * 1024 * 1024
MAX_OUTPUT_BYTES = 12 * 1024 * 1024

_HASH = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_INVENTORY = re.compile(r"archive_inventory_[a-f0-9]{32}\Z", re.ASCII)
_PROCESSOR = re.compile(r"sandbox-fileos-archive-v1-[a-f0-9]{64}\Z", re.ASCII)


@dataclass(frozen=True, slots=True)
class ArchiveMemberTarget:
    inventory_id: str
    inventory_processor_version: str
    locator: str
    sha256: str
    size_bytes: int
    depth: int
    parent_locator: str | None

    def __post_init__(self) -> None:
        if (
            type(self.inventory_id) is not str
            or not _INVENTORY.fullmatch(self.inventory_id)
            or type(self.inventory_processor_version) is not str
            or not _PROCESSOR.fullmatch(self.inventory_processor_version)
            or type(self.sha256) is not str
            or not _HASH.fullmatch(self.sha256)
            or type(self.size_bytes) is not int
            or not 0 <= self.size_bytes <= 64 * 1024 * 1024
            or type(self.depth) is not int
            or not 0 <= self.depth <= 3
        ):
            raise ArchiveUnavailable()
        _locator(self.locator)
        if self.parent_locator is not None:
            _locator(self.parent_locator)


@dataclass(frozen=True, slots=True)
class ArchiveMemberResult:
    source: ArchiveSource
    target: ArchiveMemberTarget
    status: str
    reason: str
    raw: bytes
    scanner_status: str = "unscanned"


def _target(value: object) -> ArchiveMemberTarget:
    data = _fields(
        value,
        {
            "inventory_id",
            "inventory_processor_version",
            "locator",
            "sha256",
            "size_bytes",
            "depth",
            "parent_locator",
        },
    )
    try:
        return ArchiveMemberTarget(**data)
    except Exception:
        raise ArchiveUnavailable() from None


def encode_request(raw: bytes, source: ArchiveSource, target: ArchiveMemberTarget) -> bytes:
    verified = source_for(
        raw, source.version_id, source.locator, source.sha256, source.media_type
    )
    if verified != source:
        raise ArchiveUnavailable()
    return _dump(
        {
            "contract_version": CONTRACT,
            "source": asdict(source),
            "target": asdict(target),
            "raw_base64": base64.b64encode(raw).decode("ascii"),
        }
    )


def decode_request(payload: bytes) -> tuple[bytes, ArchiveSource, ArchiveMemberTarget]:
    try:
        value = _fields(
            _load(payload, MAX_REQUEST_BYTES),
            {"contract_version", "source", "target", "raw_base64"},
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
        return raw, source, _target(value["target"])
    except Exception:
        raise ArchiveUnavailable() from None


def encode_result(result: ArchiveMemberResult) -> bytes:
    value = asdict(result)
    value["raw_base64"] = base64.b64encode(value.pop("raw")).decode("ascii")
    return _dump({"contract_version": CONTRACT, **value})


def decode_result(
    payload: bytes, source: ArchiveSource, target: ArchiveMemberTarget
) -> ArchiveMemberResult:
    try:
        value = _fields(
            _load(payload, MAX_OUTPUT_BYTES),
            {
                "contract_version",
                "source",
                "target",
                "status",
                "reason",
                "raw_base64",
                "scanner_status",
            },
        )
        if value["contract_version"] != CONTRACT:
            raise ArchiveUnavailable()
        source_data = _fields(
            value["source"], {"version_id", "locator", "sha256", "size_bytes", "media_type"}
        )
        decoded_source = ArchiveSource(**source_data)
        decoded_target = _target(value["target"])
        if decoded_source != source or decoded_target != target:
            raise ArchiveUnavailable()
        if type(value["raw_base64"]) is not str:
            raise ArchiveUnavailable()
        encoded = value["raw_base64"]
        if len(encoded) > 4 * ((MAX_MEMBER_BYTES + 2) // 3):
            raise ArchiveUnavailable()
        raw = base64.b64decode(encoded, validate=True)
        if base64.b64encode(raw).decode("ascii") != encoded:
            raise ArchiveUnavailable()
        status, reason = value["status"], value["reason"]
        if value["scanner_status"] != "unscanned":
            raise ArchiveUnavailable()
        if status == "read" and reason == "hash_bound_archive_member_v1":
            if len(raw) != target.size_bytes or hashlib.sha256(raw).hexdigest() != target.sha256:
                raise ArchiveUnavailable()
        elif status == "deferred" and reason == "member_output_limit" and not raw:
            if target.size_bytes <= MAX_MEMBER_BYTES:
                raise ArchiveUnavailable()
        else:
            raise ArchiveUnavailable()
        return ArchiveMemberResult(source, target, status, reason, raw)
    except Exception:
        raise ArchiveUnavailable() from None
