"""Private, nonpublishing preview of a v1-to-donor FileOS policy transition.

FOS-Master 218d5caec2f20b9047fd3eb8e027dc671acf0c15 is unchanged.
This comparison never turns an unobserved locator into deletion evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from email_brain.domain.models import TenantContext
from masterbrain.datacore.fileos import fileos_root_binding_sha256
from masterbrain.datacore.fileos_donor_candidate import build_fileos_donor_candidate
from masterbrain.datacore.persistence import (
    DataCoreStore,
    fileos_inventory_policy_sha256,
    fileos_manifest_root_binding_sha256,
    fileos_manifest_sha256,
    validate_fileos_completion_coverage,
)

TRANSITION_PREVIEW_VERSION = "masterbrain-fileos-donor-transition-preview-v1"
_DIRECTORY_EXCLUSIONS = frozenset(
    {"donor_junk_dir", "donor_operational_dir", "symlink_directory"}
)


def _covering_entry(
    locator: str, entries: list[dict[str, str]], *, directory_reasons: frozenset[str]
) -> dict[str, str] | None:
    for entry in entries:
        parent = entry["locator"]
        reason = entry.get("reason", entry.get("code", ""))
        if (
            parent == locator
            or (parent == "." and "." in directory_reasons)
            or (reason in directory_reasons and locator.startswith(parent + "/"))
        ):
            return entry
    return None


def preview_fileos_donor_transition(
    prior_manifest: Mapping[str, Any],
    root: Path,
    *,
    source_id: str,
    observed_at: datetime,
    metadata_only: bool = False,
) -> dict[str, Any]:
    """Compare a completed-shape v1 snapshot with one fresh donor-policy scan.

    The preview is a review aid, not a v2 manifest or a completion authorization.
    """
    source, prior_observed, prior_items = validate_fileos_completion_coverage(prior_manifest)
    if source.source_id != source_id:
        raise ValueError("FileOS transition source mismatch")
    if not isinstance(observed_at, datetime) or observed_at.tzinfo is None:
        raise ValueError("invalid FileOS transition observation")
    if observed_at.utcoffset() is None or observed_at.astimezone(UTC) <= prior_observed:
        raise ValueError("FileOS transition observation must be newer")
    prior_binding = fileos_manifest_root_binding_sha256(prior_manifest)
    if fileos_root_binding_sha256(root) != prior_binding:
        raise ValueError("FileOS transition root mismatch")
    candidate = build_fileos_donor_candidate(
        root, source_id=source_id, observed_at=observed_at, metadata_only=metadata_only
    )
    if candidate["root_binding"]["sha256"] != prior_binding:
        raise ValueError("FileOS transition root changed")

    hashed = {row["locator"]: row for row in candidate["hashed"]}
    deferred = {row["locator"]: row for row in candidate["deferred"]}
    exclusions = candidate["exclusions"]
    errors = candidate["errors"]
    classified: list[dict[str, str]] = []
    counts = {
        "unchanged": 0,
        "changed": 0,
        "deferred_prior": 0,
        "excluded_prior": 0,
        "error_covered_prior": 0,
        "unobserved_prior": 0,
        "donor_only_hashed": 0,
    }
    for item in sorted(prior_items, key=lambda item: item.locator):
        row = {
            "locator": item.locator,
            "item_id": item.item_id,
            "prior_version_id": item.version_id,
        }
        error = _covering_entry(
            item.locator,
            errors,
            directory_reasons=frozenset({".", "directory_unreadable"}),
        )
        exclusion = _covering_entry(
            item.locator, exclusions, directory_reasons=_DIRECTORY_EXCLUSIONS
        )
        if error is not None:
            state = "error_covered_prior"
            row["reason"] = error["code"]
        elif exclusion is not None:
            state = "excluded_prior"
            row["reason"] = exclusion["reason"]
        elif item.locator in deferred:
            state = "deferred_prior"
            row["reason"] = deferred[item.locator]["reason"]
        elif item.locator in hashed:
            current = hashed[item.locator]
            row["donor_version_id"] = current["version_id"]
            state = "unchanged" if current["version_id"] == item.version_id else "changed"
        else:
            state = "unobserved_prior"
        row["state"] = state
        counts[state] += 1
        classified.append(row)

    prior_locators = {item.locator for item in prior_items}
    donor_only = [
        {
            "locator": row["locator"],
            "item_id": row["item_id"],
            "version_id": row["version_id"],
        }
        for row in candidate["hashed"]
        if row["locator"] not in prior_locators
    ]
    counts["donor_only_hashed"] = len(donor_only)
    blockers = []
    if prior_manifest["errors"]:
        blockers.append("prior_snapshot_errors")
    if errors:
        blockers.append("donor_scan_errors")
    if any(counts[key] for key in ("deferred_prior", "excluded_prior", "unobserved_prior")):
        blockers.append("prior_item_not_hashed_under_donor_policy")
    return {
        "preview_version": TRANSITION_PREVIEW_VERSION,
        "publishable": False,
        "requires_review": True,
        "source_id": source_id,
        "prior_observed_at": prior_observed.isoformat(),
        "donor_observed_at": candidate["observed_at"],
        "prior_policy_sha256": fileos_inventory_policy_sha256(prior_manifest),
        "root_binding": dict(candidate["root_binding"]),
        "donor_policy": dict(candidate["policy"]),
        "candidate_counts": dict(candidate["counts"]),
        "counts": counts,
        "prior_items": classified,
        "donor_only_hashed": donor_only,
        "donor_errors": list(errors),
        "blockers": blockers,
    }


def preview_fileos_completed_donor_transition(
    core: DataCoreStore,
    ctx: TenantContext,
    prior_manifest: Mapping[str, Any],
    prior_run_id: UUID,
    root: Path,
    *,
    source_id: str,
    observed_at: datetime,
    metadata_only: bool = False,
) -> dict[str, Any]:
    """Preview only against the latest exact, completed v1 database baseline.

    A second verification rejects a newer completed run during the donor scan.
    No v2 state is persisted or made publishable by this function.
    """
    prior_hash = fileos_manifest_sha256(prior_manifest)
    completed_at = core.verify_fileos_completed_baseline(ctx, prior_manifest, prior_run_id)
    preview = preview_fileos_donor_transition(
        prior_manifest,
        root,
        source_id=source_id,
        observed_at=observed_at,
        metadata_only=metadata_only,
    )
    if (
        core.verify_fileos_completed_baseline(ctx, prior_manifest, prior_run_id) != completed_at
        or fileos_manifest_sha256(prior_manifest) != prior_hash
    ):
        raise ValueError("FileOS completed baseline changed during transition preview")
    preview["completed_baseline"] = {
        "run_id": str(prior_run_id),
        "completed_at": completed_at.isoformat(),
        "manifest_sha256": prior_hash,
    }
    return preview
