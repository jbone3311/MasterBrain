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
    stat_confined_leaf,
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


def _open_shadow_directory(
    root: Path, relative: str, root_identity: tuple[int, int]
) -> int:
    """Open one directory through no-follow descriptors, never through a walked path."""
    directory_flag = getattr(os, "O_DIRECTORY", None)
    nofollow_flag = getattr(os, "O_NOFOLLOW", None)
    if directory_flag is None or nofollow_flag is None:
        raise ConfinedFileUnavailable()
    flags = os.O_RDONLY | directory_flag | nofollow_flag
    opened: list[int] = []
    try:
        directory = os.open(root.anchor, flags)
        opened.append(directory)
        for part in root.parts[1:]:
            directory = os.open(part, flags, dir_fd=directory)
            opened.append(directory)
        root_info = os.fstat(directory)
        if (root_info.st_dev, root_info.st_ino) != root_identity:
            raise ConfinedFileChanged()
        if relative != ".":
            for part in relative.split("/"):
                directory = os.open(part, flags, dir_fd=directory)
                opened.append(directory)
        opened.pop()
        return directory
    except OSError as exc:
        raise ConfinedFileUnavailable() from exc
    finally:
        for descriptor in reversed(opened):
            os.close(descriptor)


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

    pending = ["."]
    while pending:
        directory = pending.pop()
        try:
            current_root = root.lstat()
            if not stat.S_ISDIR(current_root.st_mode) or (
                current_root.st_dev, current_root.st_ino
            ) != root_identity:
                raise ConfinedFileChanged()
        except (OSError, ConfinedFileChanged):
            record(errors, {"locator": ".", "code": "root_changed_during_scan"})
            break
        try:
            directory_fd = _open_shadow_directory(root, directory, root_identity)
        except ConfinedFileChanged:
            record(errors, {"locator": ".", "code": "root_changed_during_scan"})
            break
        except ConfinedFileUnavailable:
            record(
                errors,
                {
                    "locator": directory,
                    "code": (
                        "root_changed_during_scan"
                        if directory == "."
                        else "directory_unreadable"
                    ),
                },
            )
            if directory == ".":
                break
            continue
        try:
            with os.scandir(directory_fd) as listing:
                entries = sorted(list(listing), key=lambda entry: entry.name)
            dirnames: list[str] = []
            filenames: list[str] = []
            for entry in entries:
                (dirnames if entry.is_dir() else filenames).append(entry.name)
        except OSError:
            record(errors, {"locator": directory, "code": "directory_unreadable"})
            continue
        finally:
            os.close(directory_fd)
        current = root if directory == "." else root / directory
        kept_dirs: list[str] = []
        for name in dirnames:
            path = current / name
            kind = classify_dir(name)
            if kind != "content":
                record(exclusions, {"locator": locator(path), "reason": f"donor_{kind}_dir"})
            elif path.is_symlink():
                record(exclusions, {"locator": locator(path), "reason": "symlink_directory"})
            else:
                kept_dirs.append(name)
        pending.extend(reversed([locator(current / name) for name in kept_dirs]))

        for name in filenames:
            path = current / name
            relative = locator(path)
            if is_junk_file(name):
                record(exclusions, {"locator": relative, "reason": "donor_junk_file"})
                continue
            if path.is_symlink():
                record(errors, {"locator": relative, "code": "symlink_skipped"})
                continue
            try:
                before = stat_confined_leaf(root, relative, root_identity=root_identity)
                if not stat.S_ISREG(before.st_mode):
                    if stat.S_ISLNK(before.st_mode):
                        record(errors, {"locator": relative, "code": "symlink_skipped"})
                    else:
                        record(exclusions, {"locator": relative, "reason": "not_regular"})
                    continue
                if metadata_only or _is_dataless(before) or before.st_size > DONOR_HASH_LIMIT:
                    state = (
                        "no_hash"
                        if metadata_only
                        else "dataless"
                        if _is_dataless(before)
                        else "oversize"
                    )
                    # Metadata-only records must still have a stable locator/size.
                    after = stat_confined_leaf(root, relative, root_identity=root_identity)
                    if not stat.S_ISREG(after.st_mode) or _identity(after) != _identity(before):
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
                after = stat_confined_leaf(root, relative, root_identity=root_identity)
                if (
                    not stat.S_ISREG(after.st_mode)
                    or _identity(before) != _identity(after)
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
