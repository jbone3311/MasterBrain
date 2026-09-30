"""Read-only, nonpublishing inventory under the pinned FOS scanner policy.

The classifier is extracted from FOS-Master 218d5caec2f20b9047fd3eb8e027dc671acf0c15.
This is a comparison instrument, not a DataCore source manifest or cutover path.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

from masterbrain.datacore.confined_files import (
    ConfinedFileChanged,
    ConfinedFileTooLarge,
    ConfinedFileUnavailable,
    read_confined_file,
    stat_confined_file,
)
from masterbrain.datacore.fileos_junk_filter import classify_dir, is_junk_file

DONOR_HASH_LIMIT = 2 * 1024**3
SF_DATALESS = 0x40000000
MAX_SHADOW_RECORDS = 20_000
SHADOW_PROFILE = "pinned-fos-scanner-shadow-v1"


def _is_dataless(info: os.stat_result) -> bool:
    """Use the donor's macOS flag without trying to materialize cloud placeholders."""
    return bool(getattr(info, "st_flags", 0) & SF_DATALESS)


def _identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def scan_donor_policy_shadow(root: Path, *, metadata_only: bool = False) -> dict[str, Any]:
    """Compare pinned donor membership safely; the result is never publishable.

    This function accepts only an explicit local root. It does not consult donor
    configuration or a database, and never writes to the source tree.
    """
    if type(metadata_only) is not bool:
        raise ValueError("metadata_only must be boolean")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("FileOS shadow root must be a directory")
    root_stat = root.lstat()
    root_identity = (root_stat.st_dev, root_stat.st_ino)
    rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    def locator(path: Path) -> str:
        return path.relative_to(root).as_posix()

    def record(collection: list[dict[str, Any]], entry: dict[str, Any]) -> None:
        if len(rows) + len(exclusions) + len(errors) >= MAX_SHADOW_RECORDS:
            raise ValueError("FileOS shadow record limit exceeded")
        collection.append(entry)

    def onerror(exc: OSError) -> None:
        path = Path(exc.filename) if exc.filename else root
        try:
            relative = locator(path)
        except ValueError:
            relative = "."
        record(errors, {"locator": relative, "code": "directory_unreadable"})

    for directory, dirnames, filenames in os.walk(root, topdown=True, onerror=onerror):
        try:
            current_root = root.lstat()
            if not stat.S_ISDIR(current_root.st_mode) or (
                current_root.st_dev, current_root.st_ino
            ) != root_identity:
                raise ConfinedFileChanged()
        except (OSError, ConfinedFileChanged):
            record(errors, {"locator": ".", "code": "root_changed_during_scan"})
            break
        current = Path(directory)
        kept_dirs: list[str] = []
        for name in sorted(dirnames):
            path = current / name
            kind = classify_dir(name)
            if kind != "content":
                record(exclusions, {"locator": locator(path), "reason": f"donor_{kind}_dir"})
            elif path.is_symlink():
                record(exclusions, {"locator": locator(path), "reason": "symlink_directory"})
            else:
                kept_dirs.append(name)
        dirnames[:] = kept_dirs

        for name in sorted(filenames):
            path = current / name
            relative = locator(path)
            if is_junk_file(name):
                record(exclusions, {"locator": relative, "reason": "donor_junk_file"})
                continue
            if path.is_symlink():
                record(errors, {"locator": relative, "code": "symlink_skipped"})
                continue
            try:
                before = stat_confined_file(root, relative, root_identity=root_identity)
                if metadata_only or _is_dataless(before) or before.st_size > DONOR_HASH_LIMIT:
                    state = (
                        "no_hash"
                        if metadata_only
                        else "dataless"
                        if _is_dataless(before)
                        else "oversize"
                    )
                    # Metadata-only records must still have a stable locator/size.
                    after = stat_confined_file(root, relative, root_identity=root_identity)
                    if _identity(after) != _identity(before):
                        raise ConfinedFileChanged()
                    record(
                        rows,
                        {
                            "locator": relative,
                            "size_bytes": before.st_size,
                            "sha256": None,
                            "state": state,
                        },
                    )
                    continue
                read = read_confined_file(
                    root, relative, max_bytes=DONOR_HASH_LIMIT, capture_bytes=False
                )
                after = stat_confined_file(root, relative, root_identity=root_identity)
                if (
                    _identity(before) != _identity(after)
                    or _identity(before)
                    != (read.device, read.inode, read.size_bytes, read.mtime_ns)
                ):
                    raise ConfinedFileChanged()
                record(
                    rows,
                    {
                        "locator": relative,
                        "size_bytes": read.size_bytes,
                        "sha256": read.sha256,
                        "state": "hashed",
                    },
                )
            except (ConfinedFileChanged, ConfinedFileTooLarge):
                record(errors, {"locator": relative, "code": "changed_during_scan"})
            except (ConfinedFileUnavailable, OSError):
                record(errors, {"locator": relative, "code": "file_unreadable"})

    try:
        after_root = root.lstat()
        if not stat.S_ISDIR(after_root.st_mode) or root_identity != (
            after_root.st_dev, after_root.st_ino
        ):
            if not any(error["code"] == "root_changed_during_scan" for error in errors):
                record(errors, {"locator": ".", "code": "root_changed_during_scan"})
    except OSError:
        if not any(error["code"] == "root_changed_during_scan" for error in errors):
            record(errors, {"locator": ".", "code": "root_changed_during_scan"})
    rows.sort(key=lambda row: row["locator"])
    exclusions.sort(key=lambda row: (row["locator"], row["reason"]))
    errors.sort(key=lambda row: (row["locator"], row["code"]))
    return {
        "shadow_profile": SHADOW_PROFILE,
        "publishable": False,
        "rows": rows,
        "exclusions": exclusions,
        "errors": errors,
    }
