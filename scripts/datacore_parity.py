#!/usr/bin/env python3
"""Compare MasterBrain DataCore dedup output with a pinned FOS-Master checkout."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

from masterbrain.datacore import dedup as masterbrain

PINNED_FOS_COMMIT = "218d5caec2f20b9047fd3eb8e027dc671acf0c15"
FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "datacore_parity" / "corpus"


def load_donor(repo: Path) -> ModuleType:
    source = repo / "_SYSTEM" / "tools" / "dedup_tool.py"
    spec = importlib.util.spec_from_file_location("fos_master_dedup_tool", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load donor module: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize(value: Any, root: Path) -> Any:
    """Remove expected machine/time differences without hiding contract differences."""
    if isinstance(value, dict):
        return {
            key: normalize(item, root)
            for key, item in value.items()
            if key != "modified"
        }
    if isinstance(value, list):
        return [normalize(item, root) for item in value]
    if isinstance(value, str):
        return value.replace(str(root), "<CORPUS>")
    return value


def git_commit(repo: Path) -> str:
    import subprocess

    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()


def build_stress_corpus(root: Path, total_files: int) -> None:
    """Create deterministic scale, name, binary, empty and exclusion cases."""
    if total_files < 200 or total_files > 10000:
        raise ValueError("stress-files must be 200..10000")
    duplicate_pairs = min(100, total_files // 20)
    for index in range(duplicate_pairs):
        payload = f"DUPLICATE-{index}-".encode() + bytes([index % 251]) * 257
        for offset, label in ((0, "original"), (7, "copy")):
            folder = root / f"batch_{(index + offset) % 20}"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{label}_{index}.bin").write_bytes(payload)
    unique_count = total_files - (duplicate_pairs * 2)
    for index in range(unique_count):
        folder = root / f"batch_{index % 20}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"unique_{index}.txt").write_text(
            f"unique payload {index} {index * 7919}\n", encoding="utf-8"
        )
    (root / "empty-a.txt").write_bytes(b"")
    (root / "empty-b.txt").write_bytes(b"")
    (root / "résumé.txt").write_text("unicode duplicate", encoding="utf-8")
    (root / "résumé_copy.txt").write_text("unicode duplicate", encoding="utf-8")
    ignored = root / "__pycache__"
    ignored.mkdir()
    (ignored / "ignored.txt").write_text("ignored", encoding="utf-8")
    (root / "metadata.db").write_text("ignored", encoding="utf-8")


def comparison_checks(donor: ModuleType, root: Path) -> dict[str, tuple[Any, Any]]:
    text_a = root / "comparison-a.txt"
    text_b = root / "comparison-b.txt"
    binary_a = root / "comparison-a.bin"
    binary_b = root / "comparison-b.bin"
    text_a.write_text("same\ntext\n", encoding="utf-8")
    text_b.write_text("same\ntext\n", encoding="utf-8")
    binary_a.write_bytes(b"\x00\x01\x02")
    binary_b.write_bytes(b"\x00\x01\x03")
    config = donor.DEFAULT_CONFIG.copy()
    return {
        "compare-identical-text": (
            donor.compare_files(text_a, text_b, config),
            masterbrain.compare_files(text_a, text_b, config),
        ),
        "compare-different-binary": (
            donor.compare_files(binary_a, binary_b, config),
            masterbrain.compare_files(binary_a, binary_b, config),
        ),
        "hash-sha256": (donor.file_hash(text_a), masterbrain.file_hash(text_a)),
        "hash-md5": (donor.file_hash(text_a, "md5"), masterbrain.file_hash(text_a, "md5")),
    }


def scan_checks(donor: ModuleType, root: Path, prefix: str) -> dict[str, tuple[Any, Any]]:
    checks = {}
    for method in ("hash", "name", "both"):
        checks[f"{prefix}-{method}"] = (
            donor.find_duplicates(root, donor.DEFAULT_CONFIG.copy(), method=method),
            masterbrain.find_duplicates(root, masterbrain.DEFAULT_CONFIG.copy(), method=method),
        )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fos-repo", type=Path, required=True)
    parser.add_argument("--allow-unpinned", action="store_true")
    parser.add_argument("--stress-files", type=int, default=2000)
    parser.add_argument("--skip-stress", action="store_true")
    args = parser.parse_args()

    commit = git_commit(args.fos_repo)
    if commit != PINNED_FOS_COMMIT and not args.allow_unpinned:
        parser.error(f"FOS-Master is {commit}; expected pinned donor {PINNED_FOS_COMMIT}")

    donor = load_donor(args.fos_repo)
    with tempfile.TemporaryDirectory(prefix="masterbrain-parity-") as directory:
        corpus = Path(directory) / "corpus"
        shutil.copytree(FIXTURE, corpus)
        for path in corpus.rglob("*"):
            if path.is_file():
                os.utime(path, (1_700_000_000, 1_700_000_000))

        checks = scan_checks(donor, corpus, "fixture")
        checks.update(comparison_checks(donor, corpus))
        if not args.skip_stress:
            stress = Path(directory) / "stress"
            stress.mkdir()
            build_stress_corpus(stress, args.stress_files)
            checks.update(scan_checks(donor, stress, "stress"))
        failures = {}
        for name, (donor_result, masterbrain_result) in checks.items():
            expected = normalize(donor_result, Path(directory))
            actual = normalize(masterbrain_result, Path(directory))
            if expected != actual:
                failures[name] = {"fos_master": expected, "masterbrain": actual}

    if failures:
        print(json.dumps(failures, indent=2, sort_keys=True))
        return 1
    stress = "disabled" if args.skip_stress else f"{args.stress_files} base files plus edges"
    print(
        f"PASS: DataCore matches FOS-Master {commit}; "
        f"fixture scans, pair comparisons, hashes, stress={stress}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
