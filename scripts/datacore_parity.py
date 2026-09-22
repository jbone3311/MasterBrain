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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fos-repo", type=Path, required=True)
    parser.add_argument("--allow-unpinned", action="store_true")
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

        checks = {
            "hash": (
                donor.find_duplicates(corpus, donor.DEFAULT_CONFIG.copy(), method="hash"),
                masterbrain.find_duplicates(
                    corpus, masterbrain.DEFAULT_CONFIG.copy(), method="hash"
                ),
            ),
            "name": (
                donor.find_duplicates(corpus, donor.DEFAULT_CONFIG.copy(), method="name"),
                masterbrain.find_duplicates(
                    corpus, masterbrain.DEFAULT_CONFIG.copy(), method="name"
                ),
            ),
            "both": (
                donor.find_duplicates(corpus, donor.DEFAULT_CONFIG.copy(), method="both"),
                masterbrain.find_duplicates(
                    corpus, masterbrain.DEFAULT_CONFIG.copy(), method="both"
                ),
            ),
        }
        failures = {}
        for name, (donor_result, masterbrain_result) in checks.items():
            expected = normalize(donor_result, corpus)
            actual = normalize(masterbrain_result, corpus)
            if expected != actual:
                failures[name] = {"fos_master": expected, "masterbrain": actual}

    if failures:
        print(json.dumps(failures, indent=2, sort_keys=True))
        return 1
    print(f"PASS: DataCore dedup matches FOS-Master {commit} for hash/name/both corpus scans")
    return 0


if __name__ == "__main__":
    sys.exit(main())
