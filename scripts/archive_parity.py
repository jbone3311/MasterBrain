#!/usr/bin/env python3
"""Live golden comparison between pinned FOS-Master and DataCore archive inventory."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

from masterbrain.datacore.archive_contract import ArchiveResult, source_for
from masterbrain.datacore.archive_worker import inventory_archive

DONOR_COMMIT = "218d5caec2f20b9047fd3eb8e027dc671acf0c15"
DONOR_SOURCE_SHA256 = "a1d20a266313d7b2c36af3ffc78311ee1999824cfe933883a3ed4f87223d21ba"
DONOR_TEST_SHA256 = "a5b177791a3045661b42c1aa4692b54546c8ce18711f00d7ca74fd08c055dfbc"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True, timeout=10
    )
    return result.stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_donor(root: Path) -> ModuleType:
    source = root / "_SYSTEM/tools/archive_unpack.py"
    tests = root / "_SYSTEM/tests/test_archive_unpack.py"
    if (
        _git(root, "rev-parse", "HEAD") != DONOR_COMMIT
        or _git(root, "status", "--porcelain")
        or _sha256(source) != DONOR_SOURCE_SHA256
        or _sha256(tests) != DONOR_TEST_SHA256
    ):
        raise RuntimeError("donor provenance or cleanliness mismatch")
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("pinned_fos_archive_unpack", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load pinned donor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _zip(members: list[tuple[str, bytes]], *, compression: int = zipfile.ZIP_STORED) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        for name, raw in members:
            archive.writestr(name, raw)
    return output.getvalue()


def _tar(members: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, raw in members:
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
    return output.getvalue()


def _master(raw: bytes, name: str) -> ArchiveResult:
    digest = hashlib.sha256(raw).hexdigest()
    media = "application/zip" if name.endswith(".zip") else "application/gzip"
    source = source_for(raw, "version_" + digest[:32], name, digest, media)
    return inventory_archive(raw, source)


def _donor_leaves(result: dict[str, Any], destination: Path) -> dict[str, str]:
    leaves: dict[str, str] = {}
    destination = destination.resolve()
    for value in result["extracted"]:
        path = Path(value).resolve()
        relative = path.relative_to(destination).as_posix()
        leaves[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return leaves


def _master_leaves(result: ArchiveResult) -> dict[str, str]:
    return {item.locator: item.sha256 for item in result.members if not item.is_container}


def _skip_class(reason: str) -> str:
    lowered = reason.casefold()
    for name in ("traversal", "dotfile", "encrypted", "link", "bomb", "depth", "unreadable"):
        if name in lowered or (name == "depth" and "max_depth" in lowered):
            return name
    return "other"


def run(donor_root: Path) -> dict[str, Any]:
    donor = _load_donor(donor_root)
    nested = _tar([("nested/proof.txt", b"nested proof")])
    cases = {
        "flat_zip": ("flat.zip", _zip([("a.txt", b"alpha"), ("sub/b.txt", b"bravo")])),
        "flat_tar": ("flat.tar.gz", _tar([("a.txt", b"alpha"), ("sub/b.txt", b"bravo")])),
        "nested": ("nested.zip", _zip([("before.txt", b"before"), ("inner.tar.gz", nested)])),
        "filtered": (
            "filtered.zip",
            _zip([("../escape.txt", b"no"), (".hidden", b"no"), ("good.txt", b"yes")]),
        ),
    }
    checked: list[str] = []
    with tempfile.TemporaryDirectory(prefix="masterbrain-archive-parity-") as temporary:
        root = Path(temporary)
        for case, (name, raw) in cases.items():
            archive = root / case / name
            destination = root / case / "out"
            archive.parent.mkdir(parents=True)
            archive.write_bytes(raw)
            donor_result = donor.unpack(
                archive,
                destination,
                max_depth=donor.DEFAULT_CONFIG["max_depth"],
                config=donor.DEFAULT_CONFIG.copy(),
            )
            master_result = _master(raw, name)
            if _donor_leaves(donor_result, destination) != _master_leaves(master_result):
                raise AssertionError(f"{case}: leaf identity mismatch")
            donor_skips = sorted(_skip_class(reason) for _, reason in donor_result["skipped"])
            master_skips = sorted(item.reason for item in master_result.skipped)
            expected_master = sorted(
                "depth_limit" if item == "depth" else item for item in donor_skips
            )
            if master_skips != expected_master:
                raise AssertionError(f"{case}: skip class mismatch")
            if donor_result["bomb_suspected"] != master_result.bomb_suspected:
                raise AssertionError(f"{case}: bomb state mismatch")
            checked.append(case)

        bomb_raw = _zip(
            [("before.txt", b"safe"), ("bomb.bin", b"0" * (1024 * 1024))],
            compression=zipfile.ZIP_DEFLATED,
        )
        bomb_path = root / "bomb.zip"
        bomb_path.write_bytes(bomb_raw)
        bomb_destination = root / "bomb-out"
        donor_bomb = donor.unpack(
            bomb_path, bomb_destination, config=donor.DEFAULT_CONFIG.copy()
        )
        master_bomb = _master(bomb_raw, "bomb.zip")
        if not donor_bomb["bomb_suspected"] or master_bomb.reason != "bomb_suspected":
            raise AssertionError("bomb classification mismatch")
        if not (bomb_destination / "before.txt").exists() or master_bomb.members:
            raise AssertionError("named bomb publication policy difference was not preserved")
        checked.append("bomb_expected_publication_difference")

        with __import__("warnings").catch_warnings():
            __import__("warnings").simplefilter("ignore", UserWarning)
            duplicate_raw = _zip([("same.txt", b"first"), ("same.txt", b"second")])
        duplicate_path = root / "duplicate.zip"
        duplicate_path.write_bytes(duplicate_raw)
        duplicate_destination = root / "duplicate-out"
        donor_duplicate = donor.unpack(
            duplicate_path, duplicate_destination, config=donor.DEFAULT_CONFIG.copy()
        )
        master_duplicate = _master(duplicate_raw, "duplicate.zip")
        donor_hash = hashlib.sha256((duplicate_destination / "same.txt").read_bytes()).hexdigest()
        if (
            master_duplicate.reason != "duplicate_member"
            or master_duplicate.members
            or len(donor_duplicate["extracted"]) != 1
            or donor_hash != hashlib.sha256(b"second").hexdigest()
        ):
            raise AssertionError("named duplicate policy difference was not preserved")
        checked.append("duplicate_expected_refusal_difference")
    if _git(donor_root, "status", "--porcelain"):
        raise RuntimeError("donor checkout changed during parity run")
    return {"donor_commit": DONOR_COMMIT, "checked": checked, "status": "passed"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--donor", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.donor.resolve()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
