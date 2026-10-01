#!/usr/bin/env python3
"""Compare nonpublishing DataCore donor-policy rows with pinned FOS synthetic rows."""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fileos_inventory_shadow import (
    donor_rows,
    donor_scan,
    load_pinned_scanner,
    make_synthetic_tree,
)

from masterbrain.datacore.fileos import snapshot_tree
from masterbrain.datacore.fileos_donor_candidate import build_fileos_donor_candidate
from masterbrain.datacore.fileos_donor_shadow import scan_donor_policy_shadow
from masterbrain.datacore.fileos_donor_transition import preview_fileos_donor_transition
from masterbrain.datacore.persistence import MAX_MANIFEST_ITEMS

OBSERVED_AT = datetime(2026, 9, 30, tzinfo=UTC)
# The pinned synthetic fixture has six fixed items under snapshot v1 policy.
FIXED_V1_ITEMS = 6


def compare_candidate(
    donor: dict[str, dict[str, Any]], candidate: dict[str, Any], *, metadata_only: bool = False
) -> None:
    """Require exact donor path/size/SHA without treating hashless rows as evidence."""
    if candidate["publishable"] is not False or candidate["errors"]:
        raise AssertionError("donor candidate is not a clean nonpublishing observation")
    if metadata_only:
        if candidate["hashed"] or set(donor) != {row["locator"] for row in candidate["deferred"]}:
            raise AssertionError("donor candidate metadata membership diverged")
        for row in candidate["deferred"]:
            if (
                row["reason"] != "no_hash"
                or set(row) != {"item_id", "locator", "size_bytes", "reason"}
                or donor[row["locator"]]["sha256"] is not None
                or donor[row["locator"]]["size_bytes"] != row["size_bytes"]
            ):
                raise AssertionError("donor candidate metadata row diverged")
    else:
        if candidate["deferred"] or set(donor) != {row["locator"] for row in candidate["hashed"]}:
            raise AssertionError("donor candidate hashed membership diverged")
        for row in candidate["hashed"]:
            if (
                donor[row["locator"]]["size_bytes"] != row["size_bytes"]
                or donor[row["locator"]]["sha256"] != row["digest"]["value"]
            ):
                raise AssertionError("donor candidate hashed row diverged")


def compare_rows(
    donor: dict[str, dict[str, Any]],
    shadow: dict[str, Any],
    *,
    metadata_only: bool = False,
    allow_deferred: bool = False,
) -> list[dict[str, str]]:
    """Require matching membership/size/hash and explicit metadata-only state."""
    shared = {row["locator"]: row for row in shadow["rows"]}
    differences: list[dict[str, str]] = [
        {"locator": error["locator"], "code": f"shadow_{error['code']}"}
        for error in shadow["errors"]
    ]
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
    if not 100 <= stress_files <= MAX_MANIFEST_ITEMS - FIXED_V1_ITEMS:
        raise ValueError("stress_files exceeds v1 manifest capacity (100..9994)")
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
            candidate = build_fileos_donor_candidate(
                root, source_id="synthetic_fos", observed_at=OBSERVED_AT
            )
            compare_candidate(donor_rows(conn), candidate)
            v1 = snapshot_tree(
                root,
                source_id="synthetic_fos",
                observed_at=OBSERVED_AT - timedelta(days=1),
            )
            transition = preview_fileos_donor_transition(
                v1, root, source_id="synthetic_fos", observed_at=OBSERVED_AT
            )
            if transition["publishable"] is not False or transition["counts"] != {
                "unchanged": stress_files + 2,
                "changed": 0,
                "deferred_prior": 0,
                "excluded_prior": 4,
                "error_covered_prior": 0,
                "unobserved_prior": 0,
                "donor_only_hashed": 2,
            }:
                raise AssertionError("v1-to-donor policy transition classification diverged")
            if transition["blockers"] != ["prior_item_not_hashed_under_donor_policy"]:
                raise AssertionError("v1-to-donor policy gaps were not blocked")
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
            compare_candidate(
                donor_rows(conn),
                build_fileos_donor_candidate(
                    root, source_id="synthetic_fos", observed_at=OBSERVED_AT
                ),
            )
            with sqlite3.connect(":memory:") as no_hash_conn:
                scanner.ensure_schema(no_hash_conn)
                donor_scan(scanner, root, no_hash_conn, no_hash=True)
                deferred = scan_donor_policy_shadow(root, metadata_only=True)
                if compare_rows(donor_rows(no_hash_conn), deferred, metadata_only=True):
                    raise AssertionError("pinned donor-policy metadata-only rows diverged")
                compare_candidate(
                    donor_rows(no_hash_conn),
                    build_fileos_donor_candidate(
                        root,
                        source_id="synthetic_fos",
                        observed_at=OBSERVED_AT,
                        metadata_only=True,
                    ),
                    metadata_only=True,
                )
            return {
                "ordinary_matches": expected,
                "known_membership_differences": 0,
                "replay_matches": expected,
                "changed_matches": expected,
                "metadata_only_matches": expected,
                "candidate_hashed_matches": expected,
                "candidate_metadata_only_matches": expected,
                "transition_prior_matches": stress_files + 6,
                "transition_policy_gaps": 6,
                "excluded_locators": len(shared["exclusions"]),
            }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fos-repo", required=True, type=Path)
    parser.add_argument("--stress-files", type=int, default=3000)
    args = parser.parse_args()
    if not 100 <= args.stress_files <= MAX_MANIFEST_ITEMS - FIXED_V1_ITEMS:
        parser.error("--stress-files must be 100..9994 for the v1 transition corpus")
    print(json.dumps(run_shadow(args.fos_repo, args.stress_files), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
