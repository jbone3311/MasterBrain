#!/usr/bin/env python3
"""Synthetic, isolated FOS scanner versus MasterBrain snapshot shadow comparison."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import sqlite3
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from masterbrain.datacore import fileos_junk_filter
from masterbrain.datacore.dedup import DEFAULT_CONFIG, is_excluded_path
from masterbrain.datacore.fileos import snapshot_tree

PINNED_FOS_COMMIT = "218d5caec2f20b9047fd3eb8e027dc671acf0c15"
PINNED_SCANNER_SHA256 = "bf4a9bb46275bb3d9ae429335520b333541dfbbddbd0c2ec4ddef2d9873d1073"
PINNED_FILTER_SHA256 = "12110b1b5404c31172d65878a9327bf8f415f8d343b668aa5982948c840da437"
PINNED_SNAPSHOT_ROOT = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "pinned_fos_master"
)
OBSERVED_AT = datetime(2026, 9, 23, tzinfo=UTC)
DOMAIN = "shadow"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pinned_scanner(repo: Path) -> ModuleType:
    """Import checked donor source or its exact test-only snapshot.

    Never call the donor CLI or path resolver. The snapshot is allowed only at
    the one checked-in test path, never from a caller-chosen lookalike root.
    """
    repo = repo.resolve(strict=True)
    if repo != PINNED_SNAPSHOT_ROOT.resolve(strict=False):
        commit = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
        ).strip()
        if commit != PINNED_FOS_COMMIT:
            raise ValueError(f"donor commit is not pinned: {commit}")
    tools = repo / "_SYSTEM" / "tools"
    scanner = tools / "scan_domains.py"
    classifier = tools / "junk_filter.py"
    if _sha256(scanner) != PINNED_SCANNER_SHA256:
        raise ValueError("donor scanner source hash changed")
    if _sha256(classifier) != PINNED_FILTER_SHA256:
        raise ValueError("donor classifier source hash changed")
    spec = importlib.util.spec_from_file_location("pinned_fos_scan_domains", scanner)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load pinned donor scanner")
    module = importlib.util.module_from_spec(spec)
    old_bytecode_policy = sys.dont_write_bytecode
    old_import_path = sys.path[:]
    old_classifier = sys.modules.pop("junk_filter", None)
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
        if Path(module.junk_filter.__file__).resolve() != classifier.resolve():
            raise RuntimeError("donor scanner imported a different classifier")
    finally:
        sys.dont_write_bytecode = old_bytecode_policy
        sys.path[:] = old_import_path
        sys.modules.pop("junk_filter", None)
        if old_classifier is not None:
            sys.modules["junk_filter"] = old_classifier
    return module


def make_synthetic_tree(root: Path, stress_files: int) -> None:
    """Create only small fictional files beneath a caller-owned temporary root."""
    if not 100 <= stress_files <= 10000:
        raise ValueError("stress_files must be 100..10000")
    fixed = {
        "ordinary/report.txt": b"fictional report\n",
        ".Investor Letters/2026/letter.txt": b"fictional hidden content\n",
        "metadata.db": b"fictional data file\n",
        ".db/child.txt": b"fictional dot directory\n",
        "~$draft.docx": b"fictional office lock\n",
        "_status.html": b"fictional status\n",
        "_SYSTEM/state.json": b"{}\n",
        ".trashes/old.txt": b"fictional system trash\n",
        ".DS_Store": b"fictional finder file\n",
        "__MACOSX/fork.txt": b"fictional sidecar\n",
    }
    for locator, data in fixed.items():
        path = root / locator
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for index in range(stress_files):
        path = root / f"batch_{index % 20:02d}" / f"record_{index:05d}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"fictional-{index}-{index * 7919}\n".encode())


def donor_scan(scanner: ModuleType, root: Path, conn: sqlite3.Connection, **kwargs: Any) -> dict:
    """Use only the explicit synthetic root and caller-owned in-memory database."""
    if any(database_file for _, _, database_file in conn.execute("PRAGMA database_list")):
        raise ValueError("donor shadow scan requires an in-memory SQLite database")
    scanner.domain_abs_path = lambda _domain, _folder: root
    with contextlib.redirect_stdout(io.StringIO()):
        result = scanner.scan_domain("SYNTHETIC", DOMAIN, conn, **kwargs)
    if result.get("error"):
        raise RuntimeError("donor synthetic scanner failed")
    return result


def donor_rows(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT full_path, size_bytes, sha256, crc32, doc_type "
        "FROM unified_index WHERE domain = ? ORDER BY full_path",
        (DOMAIN,),
    ).fetchall()
    prefix = f"{DOMAIN}/"
    return {
        full_path[len(prefix) :]: {
            "size_bytes": size,
            "sha256": sha256,
            "crc32": crc32,
            "doc_type": doc_type,
        }
        for full_path, size, sha256, crc32, doc_type in rows
        if full_path.startswith(prefix)
    }


def compare_inventory(
    root: Path,
    donor: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
    *,
    allow_hashless: bool = False,
) -> dict[str, Any]:
    """Return exact common checks plus reason-coded differences; never publish."""
    shared = {item["locator"]: item for item in manifest["items"]}
    errors = {item["locator"]: item["code"] for item in manifest["errors"]}
    differences: list[dict[str, str]] = []
    common = 0
    for locator in sorted(donor.keys() | shared.keys()):
        fos = donor.get(locator)
        item = shared.get(locator)
        if fos is None:
            reason = fileos_junk_filter.path_skip_reason(locator)
            code = f"donor_{reason}" if reason else "unexplained_shared_only"
        elif item is None:
            path = root / locator
            if locator in errors:
                code = f"shared_{errors[locator]}"
            elif is_excluded_path(path, DEFAULT_CONFIG):
                code = "shared_dedupe_exclusion"
            elif fos["size_bytes"] > DEFAULT_CONFIG["max_file_size_mb"] * 1024 * 1024:
                code = "shared_size_limit"
            else:
                code = "unexplained_donor_only"
        elif fos["sha256"] is None:
            code = "donor_hash_deferred" if allow_hashless else "unexpected_donor_hashless"
        elif fos["size_bytes"] != item["size_bytes"]:
            code = "common_size_mismatch"
        elif fos["sha256"] != item["digest"]["value"]:
            code = "common_sha256_mismatch"
        else:
            common += 1
            continue
        differences.append({"locator": locator, "code": code})
    if manifest["errors"]:
        for error in manifest["errors"]:
            if error["locator"] not in donor:
                differences.append({"locator": error["locator"], "code": f"shared_{error['code']}"})
    return {
        "common": common,
        "differences": sorted(differences, key=lambda d: (d["locator"], d["code"])),
    }


def baseline_expected() -> list[dict[str, str]]:
    return sorted(
        [
            {"locator": ".db/child.txt", "code": "shared_dedupe_exclusion"},
            {"locator": "metadata.db", "code": "shared_dedupe_exclusion"},
            {"locator": ".trashes/old.txt", "code": "donor_junk_dir"},
            {"locator": "_SYSTEM/state.json", "code": "donor_operational"},
            {"locator": "_status.html", "code": "donor_junk_file"},
            {"locator": "~$draft.docx", "code": "donor_junk_file"},
        ],
        key=lambda d: (d["locator"], d["code"]),
    )


def run_shadow(repo: Path, stress_files: int = 3000) -> dict[str, Any]:
    scanner = load_pinned_scanner(repo)
    with tempfile.TemporaryDirectory(prefix="masterbrain-fileos-shadow-") as tmp:
        root = Path(tmp) / "synthetic_root"
        root.mkdir()
        if is_excluded_path(root, DEFAULT_CONFIG):
            raise RuntimeError("synthetic root itself matches the shared dedupe exclusion policy")
        make_synthetic_tree(root, stress_files)
        with sqlite3.connect(":memory:") as conn:
            scanner.ensure_schema(conn)
            first = donor_scan(scanner, root, conn)
            manifest = snapshot_tree(root, source_id="shadow_source", observed_at=OBSERVED_AT)
            baseline = compare_inventory(root, donor_rows(conn), manifest)
            if (
                baseline["differences"] != baseline_expected()
                or baseline["common"] != stress_files + 2
            ):
                raise AssertionError(f"unexplained baseline inventory difference: {baseline}")

            replay = donor_scan(scanner, root, conn)
            if (replay["added"], replay["updated"], replay["removed"], replay["unchanged"]) != (
                0,
                0,
                0,
                first["scanned"],
            ):
                raise AssertionError(f"donor replay changed inventory: {replay}")
            if (
                compare_inventory(
                    root,
                    donor_rows(conn),
                    snapshot_tree(root, source_id="shadow_source", observed_at=OBSERVED_AT),
                )
                != baseline
            ):
                raise AssertionError("shared snapshot replay changed inventory")

            changed = root / "ordinary" / "report.txt"
            changed.write_bytes(b"fictional changed report with longer content\n")
            changed_result = donor_scan(scanner, root, conn)
            if changed_result["updated"] != 1:
                raise AssertionError(f"donor did not detect changed content: {changed_result}")
            after_change = compare_inventory(
                root,
                donor_rows(conn),
                snapshot_tree(root, source_id="shadow_source", observed_at=OBSERVED_AT),
            )
            if after_change != baseline:
                raise AssertionError("changed file diverged between scanners")

            with sqlite3.connect(":memory:") as no_hash_conn:
                scanner.ensure_schema(no_hash_conn)
                no_hash = donor_scan(scanner, root, no_hash_conn, no_hash=True)
                deferred = compare_inventory(
                    root,
                    donor_rows(no_hash_conn),
                    snapshot_tree(root, source_id="shadow_source", observed_at=OBSERVED_AT),
                    allow_hashless=True,
                )
                if (
                    no_hash["added"] != first["scanned"]
                    or sum(
                        diff["code"] == "donor_hash_deferred" for diff in deferred["differences"]
                    )
                    != stress_files + 2
                ):
                    raise AssertionError("no-hash donor rows were treated as publishable parity")
                if [
                    diff
                    for diff in deferred["differences"]
                    if diff["code"] != "donor_hash_deferred"
                ] != baseline_expected():
                    raise AssertionError("unexpected no-hash policy difference")
                rehashed = donor_scan(scanner, root, no_hash_conn, rehash=True)
                if rehashed["rehashed"] != first["scanned"]:
                    raise AssertionError(f"donor rehash did not backfill all rows: {rehashed}")
                if (
                    compare_inventory(
                        root,
                        donor_rows(no_hash_conn),
                        snapshot_tree(root, source_id="shadow_source", observed_at=OBSERVED_AT),
                    )
                    != baseline
                ):
                    raise AssertionError("donor rehash diverged from shared snapshot")

            removed = root / "batch_00" / "record_00000.txt"
            removed.unlink()
            single_loss = donor_scan(scanner, root, conn)
            if single_loss["removed"] != 1:
                raise AssertionError(f"donor single removal mismatch: {single_loss}")
            single_compare = compare_inventory(
                root,
                donor_rows(conn),
                snapshot_tree(root, source_id="shadow_source", observed_at=OBSERVED_AT),
            )
            if (
                single_compare["differences"] != baseline_expected()
                or single_compare["common"] != stress_files + 1
            ):
                raise AssertionError("single removal diverged between scanners")
            for index in range(1, stress_files // 2 + 3):
                (root / f"batch_{index % 20:02d}" / f"record_{index:05d}.txt").unlink()
            mass_loss = donor_scan(scanner, root, conn)
            if mass_loss["prune_refused"] < 10 or mass_loss["removed"] != 0:
                raise AssertionError(f"donor mass-prune guard failed: {mass_loss}")
            mass_compare = compare_inventory(
                root,
                donor_rows(conn),
                snapshot_tree(root, source_id="shadow_source", observed_at=OBSERVED_AT),
            )
            mass_retained = sum(
                diff["code"] == "unexplained_donor_only" for diff in mass_compare["differences"]
            )
            if mass_retained != mass_loss["prune_refused"]:
                raise AssertionError("mass-loss retention did not match donor refusal")

            symlink_root = Path(tmp) / "symlink_root"
            symlink_root.mkdir()
            (symlink_root / "source.txt").write_bytes(b"fictional in-root bytes\n")
            outside = Path(tmp) / "outside.txt"
            outside.write_bytes(b"fictional outside-root bytes\n")
            (symlink_root / "internal_link.txt").symlink_to(symlink_root / "source.txt")
            (symlink_root / "external_link.txt").symlink_to(outside)
            with sqlite3.connect(":memory:") as symlink_conn:
                scanner.ensure_schema(symlink_conn)
                donor_scan(scanner, symlink_root, symlink_conn)
                symlink_compare = compare_inventory(
                    symlink_root,
                    donor_rows(symlink_conn),
                    snapshot_tree(symlink_root, source_id="shadow_source", observed_at=OBSERVED_AT),
                )
                expected_links = [
                    {"locator": "external_link.txt", "code": "shared_symlink_skipped"},
                    {"locator": "internal_link.txt", "code": "shared_symlink_skipped"},
                ]
                if symlink_compare != {"common": 1, "differences": expected_links}:
                    raise AssertionError(f"symlink policy divergence changed: {symlink_compare}")
            return {
                "stress_files": stress_files,
                "baseline_common": baseline["common"],
                "expected_policy_differences": baseline["differences"],
                "replay_unchanged": replay["unchanged"],
                "changed_updated": changed_result["updated"],
                "no_hash_deferred": stress_files + 2,
                "rehash_backfilled": rehashed["rehashed"],
                "single_removed": single_loss["removed"],
                "mass_prune_refused": mass_loss["prune_refused"],
                "mass_retained_vs_snapshot": mass_retained,
                "symlink_policy_differences": 2,
            }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fos-repo", required=True, type=Path)
    parser.add_argument("--stress-files", type=int, default=3000)
    args = parser.parse_args()
    print(json.dumps(run_shadow(args.fos_repo, args.stress_files), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
