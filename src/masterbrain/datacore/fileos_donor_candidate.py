"""Source-bound, nonpublishing candidate ledger for the pinned FOS policy.

FOS-Master 218d5caec2f20b9047fd3eb8e027dc671acf0c15 remains unchanged.
Metadata-only donor rows are observations, never invented source versions.
"""

from __future__ import annotations

import mimetypes
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from masterbrain.datacore.contracts import Digest, SourceKind, SourceRef, stable_id
from masterbrain.datacore.fileos import ROOT_BINDING_VERSION, fileos_root_binding_sha256
from masterbrain.datacore.fileos_donor_shadow import (
    DONOR_HASH_LIMIT,
    MAX_SHADOW_RECORDS,
    SHADOW_PROFILE,
    scan_donor_policy_shadow,
)

CANDIDATE_VERSION = "masterbrain-fileos-donor-candidate-v2"
DONOR_COMMIT = "218d5caec2f20b9047fd3eb8e027dc671acf0c15"
_HEX_SHA = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_DEFERRED_STATES = frozenset({"no_hash", "dataless", "oversize"})


def _locator(value: object) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 4000
        or value.startswith(("/", "\\"))
        or "\\" in value
        or "\x00" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError("invalid donor candidate locator")
    return value


def build_fileos_donor_candidate(
    root: Path,
    *,
    source_id: str,
    observed_at: datetime,
    metadata_only: bool = False,
) -> dict[str, Any]:
    """Separate hashed evidence candidates from hashless donor observations.

    The result is deliberately not a snapshot manifest; v1 intake must reject it.
    """
    source = SourceRef(source_id, SourceKind.FILEOS, source_id)
    if not isinstance(observed_at, datetime) or observed_at.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware")
    if observed_at.utcoffset() is None or type(metadata_only) is not bool:
        raise ValueError("invalid donor candidate observation")
    observed = observed_at.astimezone(UTC).isoformat()
    root = root.resolve(strict=True)
    binding = fileos_root_binding_sha256(root)
    shadow = scan_donor_policy_shadow(root, metadata_only=metadata_only)
    if shadow.get("shadow_profile") != SHADOW_PROFILE or shadow.get("publishable") is not False:
        raise ValueError("invalid donor shadow profile")
    rows = shadow.get("rows")
    raw_exclusions = shadow.get("exclusions")
    raw_errors = shadow.get("errors")
    if (
        not isinstance(rows, list)
        or not isinstance(raw_exclusions, list)
        or not isinstance(raw_errors, list)
        or len(rows) + len(raw_exclusions) + len(raw_errors) > MAX_SHADOW_RECORDS
    ):
        raise ValueError("invalid donor shadow ledgers")
    if any(
        isinstance(entry, dict) and entry.get("code") == "invalid_locator_encoding"
        for entry in raw_errors
    ):
        raise ValueError("FileOS transition refused: unencodable filename in source root")
    hashed: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    exclusions: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    occupied: set[str] = set()

    def unique(value: object, *, root_error: bool = False) -> str:
        locator = "." if root_error and value == "." else _locator(value)
        if locator in occupied:
            raise ValueError("overlapping donor candidate ledgers")
        occupied.add(locator)
        return locator

    for row in rows:
        if not isinstance(row, dict) or set(row) != {"locator", "size_bytes", "sha256", "state"}:
            raise ValueError("invalid donor candidate row")
        locator = unique(row["locator"])
        size = row["size_bytes"]
        state = row["state"]
        digest = row["sha256"]
        if type(size) is not int or size < 0:
            raise ValueError("invalid donor candidate size")
        item_id = stable_id("item", source.source_id, locator)
        if state == "hashed":
            if (
                size > DONOR_HASH_LIMIT
                or not isinstance(digest, str)
                or _HEX_SHA.fullmatch(digest) is None
            ):
                raise ValueError("invalid donor candidate digest")
            verified = Digest("sha256", digest)
            hashed.append(
                {
                    "item_id": item_id,
                    "version_id": stable_id("version", item_id, verified.value, str(size)),
                    "locator": locator,
                    "observed_at": observed,
                    "digest": {"algorithm": "sha256", "value": verified.value},
                    "size_bytes": size,
                    "media_type": mimetypes.guess_type(locator)[0] or "application/octet-stream",
                }
            )
        elif isinstance(state, str) and state in _DEFERRED_STATES and digest is None:
            if state == "oversize" and size <= DONOR_HASH_LIMIT:
                raise ValueError("invalid donor candidate oversize state")
            deferred.append(
                {"item_id": item_id, "locator": locator, "size_bytes": size, "reason": state}
            )
        else:
            raise ValueError("invalid donor candidate state")

    for raw in raw_exclusions:
        if not isinstance(raw, dict) or set(raw) != {"locator", "reason"}:
            raise ValueError("invalid donor candidate exclusion")
        locator = unique(raw["locator"])
        reason = raw["reason"]
        if not isinstance(reason, str) or reason not in {
            "donor_junk_dir",
            "donor_operational_dir",
            "donor_junk_file",
            "not_regular",
        }:
            raise ValueError("invalid donor candidate exclusion")
        exclusions.append({"locator": locator, "reason": reason})

    for raw in raw_errors:
        if not isinstance(raw, dict) or set(raw) != {"locator", "code"}:
            raise ValueError("invalid donor candidate error")
        locator = unique(raw["locator"], root_error=True)
        code = raw["code"]
        if not isinstance(code, str) or code not in {
            "directory_unreadable",
            "root_changed_during_scan",
            "symlink_skipped",
            "changed_during_scan",
            "file_unreadable",
        }:
            raise ValueError("invalid donor candidate error")
        errors.append({"locator": locator, "code": code})

    excluded_directories = {
        entry["locator"]
        for entry in exclusions
        if entry["reason"] in {"donor_junk_dir", "donor_operational_dir"}
    }
    for locator in occupied:
        parts = locator.split("/")
        if any("/".join(parts[:index]) in excluded_directories for index in range(1, len(parts))):
            raise ValueError("overlapping donor candidate directory exclusion")

    try:
        if fileos_root_binding_sha256(root) != binding:
            raise ValueError("root drift")
    except (OSError, RuntimeError, ValueError):
        if "." not in occupied:
            if len(rows) + len(raw_exclusions) + len(raw_errors) >= MAX_SHADOW_RECORDS:
                raise ValueError("donor candidate record bound exceeded") from None
            errors.append({"locator": ".", "code": "root_changed_during_scan"})
    hashed.sort(key=lambda row: row["locator"])
    deferred.sort(key=lambda row: row["locator"])
    exclusions.sort(key=lambda row: (row["locator"], row["reason"]))
    errors.sort(key=lambda row: (row["locator"], row["code"]))
    return {
        "candidate_version": CANDIDATE_VERSION,
        "publishable": False,
        "source": {"source_id": source.source_id, "kind": source.kind.value},
        "observed_at": observed,
        "root_binding": {"version": ROOT_BINDING_VERSION, "sha256": binding},
        "policy": {
            "shadow_profile": SHADOW_PROFILE,
            "donor_commit": DONOR_COMMIT,
            "hash_limit_bytes": DONOR_HASH_LIMIT,
            "follow_file_symlinks": False,
            "metadata_only": metadata_only,
        },
        "counts": {
            "hashed": len(hashed),
            "deferred": len(deferred),
            "excluded": len(exclusions),
            "errors": len(errors),
        },
        "hashed": hashed,
        "deferred": deferred,
        "exclusions": exclusions,
        "errors": errors,
    }
