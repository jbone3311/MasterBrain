#!/usr/bin/env python3
"""Compare nonpublishing DataCore donor-policy rows with pinned FOS synthetic rows."""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from fileos_inventory_shadow import (
    donor_rows,
    donor_scan,
    load_pinned_scanner,
    make_synthetic_tree,
)

from masterbrain.datacore.fileos_donor_shadow import scan_donor_policy_shadow


def compare_rows(
    donor: dict[str, dict[str, Any]],
    shadow: dict[str, Any],
    *,
    metadata_only: bool = False,
    allow_deferred: bool = False,
) -> list[dict[str, str]]:
    """Require matching membership/size/hash and explicit metadata-only state."""
    shared = {row["locator"]: row for row in shadow["rows"]}
    differences: list[dict[str, str]] = []
    for locator in sorted(donor.keys() | shared.keys()):
        original = donor.get(locator)
        candidate = shared.get(locator)
        if original is None:
            code = "shared_only"
        elif candidate is None:
            code = "donor_only"
        elif original["size_bytes"] != candidate["size_bytes"]:
            code = "size_mismatch"
        elif original["sha256"] is None and candidate["sha256"] is None:
            if metadata_only and candidate["state"] == "no_hash":
                continue
            if allow_deferred and candidate["state"] in {"oversize", "dataless"}:
                continue
            code = "unverified_hashless"
        elif original["sha256"] != candidate["sha256"]:
            code = "sha256_mismatch"
        elif candidate["state"] != "hashed":
            code = "unexpected_shared_state"
        else:
            continue
        differences.append({"locator": locator, "code": code})
    return differences


def run_shadow(repo: Path, stress_files: int = 3000) -> dict[str, int]:
    scanner = load_pinned_scanner(repo)
    with tempfile.TemporaryDirectory(prefix="masterbrain-donor-policy-shadow-") as tmp:
        root = Path(tmp) / "synthetic_root"
        root.mkdir()
        make_synthetic_tree(root, stress_files)
        with sqlite3.connect(":memory:") as conn:
            scanner.ensure_schema(conn)
            first = donor_scan(scanner, root, conn)
            shared = scan_donor_policy_shadow(root)
            differences = compare_rows(donor_rows(conn), shared)
            if differences or shared["errors"]:
                raise AssertionError("pinned donor-policy baseline diverged")
            expected = stress_files + 4
            if len(shared["rows"]) != expected or first["scanned"] != expected:
                raise AssertionError("pinned donor-policy membership count changed")
            replay = donor_scan(scanner, root, conn)
            if replay["unchanged"] != expected or compare_rows(
                donor_rows(conn), scan_donor_policy_shadow(root)
            ):
                raise AssertionError("pinned donor-policy replay diverged")
            changed = root / "ordinary" / "report.txt"
            changed.write_bytes(b"fictional changed report with longer content\n")
            update = donor_scan(scanner, root, conn)
            if update["updated"] != 1 or compare_rows(
                donor_rows(conn), scan_donor_policy_shadow(root)
            ):
                raise AssertionError("pinned donor-policy changed file diverged")
            with sqlite3.connect(":memory:") as no_hash_conn:
                scanner.ensure_schema(no_hash_conn)
                donor_scan(scanner, root, no_hash_conn, no_hash=True)
                deferred = scan_donor_policy_shadow(root, metadata_only=True)
                if compare_rows(donor_rows(no_hash_conn), deferred, metadata_only=True):
                    raise AssertionError("pinned donor-policy metadata-only rows diverged")
            return {
                "ordinary_matches": expected,
                "known_membership_differences": 0,
                "replay_matches": expected,
                "changed_matches": expected,
                "metadata_only_matches": expected,
                "excluded_locators": len(shared["exclusions"]),
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
