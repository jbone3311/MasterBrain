"""Read-only file hashing and duplicate discovery extracted from FOS-Master.

Provenance:
  repository: https://github.com/jbone3311/FOS-Master
  source: _SYSTEM/tools/dedup_tool.py
  commit: 218d5caec2f20b9047fd3eb8e027dc671acf0c15

This first DataCore tranche intentionally preserves the donor's observable return
shapes and defaults. It excludes the donor CLI, local configuration discovery,
and all delete/move behavior. File effects remain outside this module.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "hash_algorithm": "sha256",
    "min_file_size": 0,
    "max_file_size_mb": 100,
    "exclude_patterns": [
        ".git",
        "__pycache__",
        "node_modules",
        "_INDEX",
        ".db",
        ".DS_Store",
        "Thumbs.db",
        "desktop.ini",
        "._*",
        "__MACOSX",
    ],
    "include_extensions": None,
}


def file_hash(filepath: str | Path, algorithm: str = "sha256") -> str:
    """Compute a content hash using the donor's 8 KiB streaming chunks."""
    digest = hashlib.new(algorithm)
    with open(filepath, "rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pattern_matches_component(pattern: str, component: str) -> bool:
    if pattern.endswith("*"):
        return component.startswith(pattern[:-1])
    if pattern.startswith("."):
        return component == pattern or Path(component).suffix == pattern
    return component == pattern or Path(component).stem == pattern


def should_include(filepath: Path, config: dict[str, Any]) -> bool:
    """Apply the donor's component-aware exclusions and size/type bounds."""
    components = Path(filepath).parts
    for pattern in config.get("exclude_patterns", []):
        if any(_pattern_matches_component(pattern, part) for part in components):
            return False

    size = filepath.stat().st_size
    if size < config.get("min_file_size", 0):
        return False
    max_size = config.get("max_file_size_mb", 100) * 1024 * 1024
    if size > max_size:
        return False

    include_ext = config.get("include_extensions")
    return not include_ext or filepath.suffix.lower() in include_ext


def _walk_files(directory: Path, config: dict[str, Any]) -> tuple[list[Path], list[dict[str, str]]]:
    files: list[Path] = []
    inaccessible_dirs: list[dict[str, str]] = []

    def onerror(exc: OSError) -> None:
        path = getattr(exc, "filename", None) or str(exc)
        inaccessible_dirs.append({"path": str(path), "error": str(exc)})

    for root, _dirnames, filenames in os.walk(directory, onerror=onerror):
        root_path = Path(root)
        for name in filenames:
            candidate = root_path / name
            if candidate.is_file() and should_include(candidate, config):
                files.append(candidate)
    return files, inaccessible_dirs


def find_duplicates(
    directory: str | Path, config: dict[str, Any], method: str = "hash"
) -> dict[str, Any]:
    """Find content-identical or similarly named files without changing them."""
    root = Path(directory)
    if not root.is_dir():
        return {"error": f"Not a directory: {root}"}

    files, inaccessible_dirs = _walk_files(root, config)
    files.sort()
    if method == "hash":
        result = _find_hash_duplicates(files, config)
        result["inaccessible_dirs"] = inaccessible_dirs
        return result
    if method == "name":
        result = _find_name_duplicates(files)
        result["inaccessible_dirs"] = inaccessible_dirs
        return result
    if method == "both":
        return {
            "hash_duplicates": _find_hash_duplicates(files, config),
            "name_duplicates": _find_name_duplicates(files),
            "total_files": len(files),
            "inaccessible_dirs": inaccessible_dirs,
        }
    return {"error": f"Unknown method: {method}"}


def _find_hash_duplicates(files: list[Path], config: dict[str, Any]) -> dict[str, Any]:
    algorithm = config.get("hash_algorithm", "sha256")
    hash_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    errors: list[dict[str, str]] = []

    for filepath in files:
        try:
            pre_stat = filepath.stat()
            content_hash = file_hash(filepath, algorithm)
            post_stat = filepath.stat()
            entry: dict[str, Any] = {
                "path": str(filepath),
                "size": post_stat.st_size,
                "modified": datetime.fromtimestamp(post_stat.st_mtime).isoformat(),
            }
            if pre_stat.st_size != post_stat.st_size:
                entry["size_changed_during_hash"] = True
                entry["size_before_hash"] = pre_stat.st_size
            hash_map[content_hash].append(entry)
        except Exception as exc:  # parity: donor records per-file failures
            errors.append({"path": str(filepath), "error": str(exc)})

    duplicates: list[dict[str, Any]] = []
    wasted_bytes = 0
    for content_hash, group in hash_map.items():
        if len(group) < 2:
            continue
        size = group[0]["size"]
        waste = size * (len(group) - 1)
        sizes = {item["size"] for item in group}
        duplicate_entry: dict[str, Any] = {
            "hash": content_hash[:16],
            "count": len(group),
            "size_each": size,
            "wasted_bytes": waste,
            "files": group,
        }
        if len(sizes) > 1:
            duplicate_entry["size_mismatch"] = True
            duplicate_entry["sizes_seen"] = sorted(sizes)
        else:
            wasted_bytes += waste
        duplicates.append(duplicate_entry)

    duplicates.sort(key=lambda item: int(item["wasted_bytes"]), reverse=True)
    return {
        "total_files": len(files),
        "unique_files": len(hash_map),
        "duplicate_groups": len(duplicates),
        "duplicate_files": sum(item["count"] - 1 for item in duplicates),
        "wasted_bytes": wasted_bytes,
        "wasted_kb": round(wasted_bytes / 1024, 1),
        "duplicates": duplicates,
        "errors": errors,
    }


def _find_name_duplicates(files: list[Path]) -> dict[str, Any]:
    name_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for filepath in files:
        clean = filepath.stem.lower()
        for pattern in [r"_v\d+", r"_copy", r"\s*\(\d+\)", r"_\d{8}", r"_old", r"_backup", r"_bak"]:
            clean = re.sub(pattern, "", clean)
        name_groups[clean].append(
            {"path": str(filepath), "name": filepath.name, "size": filepath.stat().st_size}
        )

    similar: list[dict[str, Any]] = [
        {"base_name": base_name, "count": len(group), "files": group}
        for base_name, group in name_groups.items()
        if len(group) > 1
    ]
    similar.sort(key=lambda item: int(item["count"]), reverse=True)
    return {
        "total_files": len(files),
        "similar_groups": len(similar),
        "similar_files": sum(item["count"] for item in similar),
        "groups": similar,
    }


def compare_files(file1: str | Path, file2: str | Path, config: dict[str, Any]) -> dict[str, Any]:
    """Return the donor-compatible comparison record for two files."""
    first = Path(file1)
    second = Path(file2)
    if not first.exists():
        return {"error": f"File not found: {first}"}
    if not second.exists():
        return {"error": f"File not found: {second}"}

    algorithm = config.get("hash_algorithm", "sha256")
    first_hash = file_hash(first, algorithm)
    second_hash = file_hash(second, algorithm)
    result: dict[str, Any] = {
        "file1": {
            "path": str(first),
            "size": first.stat().st_size,
            "hash": first_hash[:16],
            "modified": datetime.fromtimestamp(first.stat().st_mtime).isoformat(),
        },
        "file2": {
            "path": str(second),
            "size": second.stat().st_size,
            "hash": second_hash[:16],
            "modified": datetime.fromtimestamp(second.stat().st_mtime).isoformat(),
        },
        "identical": first_hash == second_hash,
        "same_size": first.stat().st_size == second.stat().st_size,
        "same_extension": first.suffix == second.suffix,
        "name_similarity": round(SequenceMatcher(None, first.name, second.name).ratio(), 3),
    }
    text_exts = {
        ".md",
        ".txt",
        ".py",
        ".js",
        ".json",
        ".html",
        ".css",
        ".csv",
        ".xml",
        ".yaml",
        ".yml",
    }
    if first.suffix.lower() in text_exts and second.suffix.lower() in text_exts:
        first_text = first.read_text(encoding="utf-8", errors="replace")
        second_text = second.read_text(encoding="utf-8", errors="replace")
        result["content_similarity"] = round(
            SequenceMatcher(None, first_text, second_text).ratio(), 3
        )
        result["line_count_diff"] = abs(
            len(first_text.splitlines()) - len(second_text.splitlines())
        )
    return result
