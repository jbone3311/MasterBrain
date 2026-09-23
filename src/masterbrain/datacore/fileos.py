"""Read-only FileOS source inventory built on shared DataCore contracts."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from masterbrain.datacore.confined_files import (
    ConfinedFileChanged,
    ConfinedFileTooLarge,
    ConfinedFileUnavailable,
    read_confined_file,
)
from masterbrain.datacore.contracts import (
    Digest,
    SourceItemVersion,
    SourceKind,
    SourceRef,
    stable_id,
)
from masterbrain.datacore.dedup import DEFAULT_CONFIG, is_excluded_path, should_include

SNAPSHOT_VERSION = "masterbrain-fileos-snapshot-v1"
INVENTORY_POLICY_VERSION = "fileos-inventory-policy-v1"
ROOT_BINDING_VERSION = "fileos-root-binding-v1"
MAX_SNAPSHOT_EXCLUSIONS = 10_000


@dataclass(frozen=True, slots=True)
class SnapshotError:
    locator: str
    code: str


@dataclass(frozen=True, slots=True)
class SnapshotExclusion:
    locator: str
    kind: str
    reason: str


def fileos_inventory_policy(
    config: dict[str, Any] | None = None, *, follow_file_symlinks: bool = False
) -> dict[str, Any]:
    """Describe the exact v1 membership rules used by a FileOS snapshot."""
    policy = DEFAULT_CONFIG if config is None else config
    return {
        "policy_version": INVENTORY_POLICY_VERSION,
        "hash_algorithm": "sha256",
        "follow_file_symlinks": follow_file_symlinks,
        "min_file_size": policy.get("min_file_size", 0),
        "max_file_size_mb": policy.get("max_file_size_mb", 100),
        "include_extensions": policy.get("include_extensions"),
        "exclude_patterns": policy.get("exclude_patterns", []),
    }


def fileos_root_binding_sha256(root: Path) -> str:
    """Identify a resolved local root without persisting its path in the manifest."""
    resolved = root.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("FileOS root must be a directory")
    stat = resolved.stat()
    identity = {
        "version": ROOT_BINDING_VERSION,
        "path_bytes_hex": os.fsencode(str(resolved)).hex(),
        "device": stat.st_dev,
        "inode": stat.st_ino,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _item_dict(item: SourceItemVersion, *, is_symlink: bool) -> dict[str, Any]:
    return {
        "item_id": item.item_id,
        "version_id": item.version_id,
        "locator": item.locator,
        "observed_at": item.observed_at.isoformat(),
        "digest": {"algorithm": item.content.algorithm, "value": item.content.value},
        "size_bytes": item.size_bytes,
        "media_type": item.media_type,
        "metadata": dict(item.metadata),
        "is_symlink": is_symlink,
    }


def snapshot_tree(
    root: Path,
    *,
    source_id: str,
    observed_at: datetime,
    config: dict[str, Any] | None = None,
    follow_file_symlinks: bool = False,
) -> dict[str, Any]:
    """Hash an authorized root without modifying it and return a portable manifest."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("FileOS root must be a directory")
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    root_binding = fileos_root_binding_sha256(root)
    policy = dict(DEFAULT_CONFIG if config is None else config)
    source = SourceRef(source_id, SourceKind.FILEOS, source_id)
    observed_at = observed_at.astimezone(UTC)
    items: list[dict[str, Any]] = []
    errors: list[SnapshotError] = []
    exclusions: list[SnapshotExclusion] = []
    excluded = 0

    def record_exclusion(path: Path, kind: str, reason: str) -> None:
        nonlocal excluded
        excluded += 1
        if len(exclusions) < MAX_SNAPSHOT_EXCLUSIONS:
            exclusions.append(SnapshotExclusion(_relative(path, root), kind, reason))
        elif not any(error.code == "exclusion_ledger_overflow" for error in errors):
            errors.append(SnapshotError(".", "exclusion_ledger_overflow"))

    def onerror(exc: OSError) -> None:
        filename = Path(exc.filename) if exc.filename else root
        try:
            locator = _relative(filename, root)
        except ValueError:
            locator = "."
        errors.append(SnapshotError(locator, "directory_unreadable"))

    for directory, dirnames, filenames in os.walk(root, topdown=True, onerror=onerror):
        current = Path(directory)
        kept_dirs = []
        for name in sorted(dirnames):
            candidate = current / name
            if candidate.is_symlink():
                record_exclusion(candidate, "directory", "symlink_directory")
            elif is_excluded_path(candidate, policy):
                record_exclusion(candidate, "directory", "policy_path")
            else:
                kept_dirs.append(name)
        dirnames[:] = kept_dirs

        for name in sorted(filenames):
            path = current / name
            locator = _relative(path, root)
            is_symlink = path.is_symlink()
            if is_excluded_path(path, policy):
                record_exclusion(path, "file", "policy_path")
                continue
            if is_symlink:
                if not follow_file_symlinks:
                    errors.append(SnapshotError(locator, "symlink_skipped"))
                    continue
                try:
                    target = path.resolve(strict=True)
                    target_locator = _relative(target, root)
                except (FileNotFoundError, RuntimeError, ValueError):
                    errors.append(SnapshotError(locator, "symlink_outside_root"))
                    continue
            try:
                if not path.is_file():
                    record_exclusion(path, "file", "not_regular")
                    continue
                if not should_include(path, policy):
                    size = path.stat().st_size
                    if size < policy.get("min_file_size", 0):
                        reason = "below_min_size"
                    elif size > policy.get("max_file_size_mb", 100) * 1024 * 1024:
                        reason = "above_max_size"
                    else:
                        reason = "extension_filtered"
                    record_exclusion(path, "file", reason)
                    continue
                before = path.stat()
                read_locator = target_locator if is_symlink else locator
                read = read_confined_file(
                    root,
                    read_locator,
                    max_bytes=policy.get("max_file_size_mb", 100) * 1024 * 1024,
                    capture_bytes=False,
                )
                after = path.stat()
                if (
                    before.st_dev != read.device
                    or before.st_ino != read.inode
                    or before.st_size != read.size_bytes
                    or before.st_mtime_ns != read.mtime_ns
                    or after.st_dev != read.device
                    or after.st_ino != read.inode
                    or after.st_size != read.size_bytes
                    or after.st_mtime_ns != read.mtime_ns
                    or (is_symlink and path.resolve(strict=True) != target)
                ):
                    raise ConfinedFileChanged()
            except (ConfinedFileChanged, ConfinedFileTooLarge):
                errors.append(SnapshotError(locator, "changed_during_scan"))
                continue
            except ConfinedFileUnavailable:
                errors.append(SnapshotError(locator, "file_unreadable"))
                continue
            except OSError:
                errors.append(SnapshotError(locator, "file_unreadable"))
                continue
            digest = Digest("sha256", read.sha256)
            item_id = stable_id("item", source_id, locator)
            version_id = stable_id("version", item_id, read.sha256, str(read.size_bytes))
            media_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
            item = SourceItemVersion(
                item_id,
                version_id,
                source,
                locator,
                observed_at,
                digest,
                read.size_bytes,
                media_type,
                {"mtime_ns": read.mtime_ns},
            )
            items.append(_item_dict(item, is_symlink=is_symlink))

    try:
        if fileos_root_binding_sha256(root) != root_binding:
            errors.append(SnapshotError(".", "root_changed_during_scan"))
    except (OSError, RuntimeError, ValueError):
        errors.append(SnapshotError(".", "root_changed_during_scan"))
    items.sort(key=lambda item: item["locator"])
    errors.sort(key=lambda item: (item.locator, item.code))
    exclusions.sort(key=lambda item: (item.locator, item.kind, item.reason))
    return {
        "manifest_version": SNAPSHOT_VERSION,
        "source": {"source_id": source.source_id, "kind": source.kind.value},
        "observed_at": observed_at.isoformat(),
        "policy": fileos_inventory_policy(policy, follow_file_symlinks=follow_file_symlinks),
        "root_binding": {"version": ROOT_BINDING_VERSION, "sha256": root_binding},
        "counts": {"items": len(items), "excluded": excluded, "errors": len(errors)},
        "items": items,
        "errors": [asdict(item) for item in errors],
        "exclusions": [asdict(item) for item in exclusions],
    }
