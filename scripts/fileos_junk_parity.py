#!/usr/bin/env python3
"""Compare the copied FileOS inventory classifier with the pinned FOS donor.

This harness classifies synthetic names only. It never scans donor roots or opens
the donor database, and it refuses an unpinned or edited donor module.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

from masterbrain.datacore import fileos_junk_filter as shared

PINNED_FOS_COMMIT = "218d5caec2f20b9047fd3eb8e027dc671acf0c15"
PINNED_SOURCE_SHA256 = "12110b1b5404c31172d65878a9327bf8f415f8d343b668aa5982948c840da437"


def corpus(total: int = 3000) -> list[str]:
    """Deterministic synthetic paths spanning exact, case and nested boundaries."""
    if not 100 <= total <= 100000:
        raise ValueError("total must be 100..100000")
    seeds = [
        ".DS_Store", "Thumbs.db", "~$draft.docx", ".~lock.foo.odt#",
        "._resource", "_status.html", "metadata.db", "notes.tmp",
        ".Investor Letters/2026/Q1.pdf", ".trashes/old.pdf",
        "_SYSTEM/state.json", "_DocsToAdd/queued.pdf", "__MACOSX/fork",
        ".git/config", ".db/child.txt", "ordinary/report.txt",
        "résumé/été.txt", ".hidden content/real.pdf", "folder/.DS_STORE",
        "folder/DESKTOP.INI", "folder/.~temp.txt", "folder/genuine.stackdump",
    ]
    result = list(seeds)
    for i in range(total - len(result)):
        name = f"record_{i:05d}.txt"
        parent = (
            "ordinary", ".Investor Letters", ".spotlight-v100", "_SYSTEM",
            "._fork", "project", "node_modules", "Résumé",
        )[i % 8]
        result.append(f"{parent}/{i % 17:02d}/{name}")
    return result


def load_donor(repo: Path) -> ModuleType:
    repo = repo.resolve(strict=True)
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != PINNED_FOS_COMMIT:
        raise ValueError(f"donor commit is not pinned: {commit}")
    source = repo / "_SYSTEM" / "tools" / "junk_filter.py"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != PINNED_SOURCE_SHA256:
        raise ValueError(f"donor classifier digest is not pinned: {digest}")
    spec = importlib.util.spec_from_file_location("pinned_fos_junk_filter", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load pinned donor classifier")
    donor = importlib.util.module_from_spec(spec)
    old_bytecode_policy = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(donor)
    finally:
        sys.dont_write_bytecode = old_bytecode_policy
    return donor


def compare(donor: ModuleType, paths: list[str]) -> list[dict[str, object]]:
    mismatches: list[dict[str, object]] = []
    for path in paths:
        parts = path.split("/")
        leaf = parts[-1]
        for label, expected, actual in (
            ("file", donor.is_junk_file(leaf), shared.is_junk_file(leaf)),
            ("reason", donor.path_skip_reason(path), shared.path_skip_reason(path)),
        ):
            if expected != actual:
                mismatches.append(
                    {"path": path, "contract": label, "donor": expected, "shared": actual}
                )
        for name in parts[:-1]:
            for label, expected, actual in (
                ("dir", donor.is_junk_dir(name), shared.is_junk_dir(name)),
                ("operational", donor.is_operational_dir(name), shared.is_operational_dir(name)),
                ("class", donor.classify_dir(name), shared.classify_dir(name)),
            ):
                if expected != actual:
                    mismatches.append(
                        {"path": path, "contract": label, "donor": expected, "shared": actual}
                    )
        donor_dirs = parts[:-1].copy()
        shared_dirs = parts[:-1].copy()
        donor.prune_dirs(donor_dirs)
        shared.prune_dirs(shared_dirs)
        if donor_dirs != shared_dirs:
            mismatches.append(
                {"path": path, "contract": "prune", "donor": donor_dirs, "shared": shared_dirs}
            )
    return mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fos-repo", type=Path, required=True)
    parser.add_argument("--cases", type=int, default=3000)
    args = parser.parse_args()
    donor = load_donor(args.fos_repo)
    paths = corpus(args.cases)
    mismatches = compare(donor, paths)
    print(json.dumps({"cases": len(paths), "mismatches": mismatches[:20]}, sort_keys=True))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
