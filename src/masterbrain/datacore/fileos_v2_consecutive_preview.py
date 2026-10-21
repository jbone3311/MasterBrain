"""Nonpublishing comparison of two donor-policy FileOS observations.

FOS-Master 218d5caec2f20b9047fd3eb8e027dc671acf0c15 is unchanged.
Neither input is presumed to be a completed database run or absence authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from masterbrain.datacore.contracts import SourceKind, SourceRef
from masterbrain.datacore.persistence import (
    _fileos_v2_staged_rows,
    fileos_mass_loss_requires_review,
)

PREVIEW_VERSION = "masterbrain-fileos-v2-consecutive-preview-v1"
_DIRECTORY_EXCLUSIONS = frozenset({"donor_junk_dir", "donor_operational_dir"})
_DIRECTORY_ERRORS = frozenset(
    {"directory_unreadable", "root_changed_during_scan", "symlink_skipped"}
)
_STATES = (
    "unchanged", "changed", "deferred_prior", "excluded_prior",
    "error_covered_prior", "unobserved_prior", "absence_candidate",
    "newly_hashed_prior", "unobserved_hashless_prior",
)


def _time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("invalid FileOS v2 observation time")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid FileOS v2 observation time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("invalid FileOS v2 observation time")
    return parsed.astimezone(UTC)


def _covering_reason(
    locator: str, entries: Mapping[str, str], *, directory_reasons: frozenset[str]
) -> str | None:
    exact = entries.get(locator)
    if exact is not None:
        return exact
    parent = locator.rpartition("/")[0]
    while parent:
        reason = entries.get(parent)
        if reason in directory_reasons:
            return reason
        parent = parent.rpartition("/")[0]
    root_reason = entries.get(".")
    if root_reason in directory_reasons:
        return root_reason
    return None


def preview_fileos_v2_consecutive_observations(
    previous: Mapping[str, Any], current: Mapping[str, Any]
) -> dict[str, Any]:
    """Classify a later donor observation without writing or inferring absence.

    The caller must separately prove that a prior database baseline completed;
    this pure preview intentionally does not claim that authority.
    """
    if not isinstance(previous, Mapping) or not isinstance(current, Mapping):
        raise ValueError("invalid FileOS v2 observations")
    source = previous.get("source")
    if not isinstance(source, Mapping) or not isinstance(source.get("source_id"), str):
        raise ValueError("invalid FileOS v2 source")
    source_id = source["source_id"]
    SourceRef(source_id, SourceKind.FILEOS, source_id)
    prior_rows = _fileos_v2_staged_rows(previous, source_id)
    next_rows = _fileos_v2_staged_rows(current, source_id)
    if (
        previous["source"] != current["source"]
        or previous["root_binding"] != current["root_binding"]
        or previous["policy"] != current["policy"]
        or previous["counts"]["errors"] != 0
    ):
        raise ValueError("FileOS v2 consecutive observation boundary requires review")
    prior_time = _time(previous["observed_at"])
    next_time = _time(current["observed_at"])
    if next_time <= prior_time:
        raise ValueError("FileOS v2 observations are not consecutive in time")

    prior_present = {
        row[1]: row for row in prior_rows if row[0] in {"hashed", "deferred"}
    }
    next_present = {
        row[1]: row for row in next_rows if row[0] in {"hashed", "deferred"}
    }
    excluded: dict[str, str] = {}
    errors: dict[str, str] = {}
    for coverage_row in next_rows:
        if coverage_row[0] in {"excluded", "error"}:
            assert isinstance(coverage_row[7], str)
            (excluded if coverage_row[0] == "excluded" else errors)[
                coverage_row[1]
            ] = coverage_row[7]
    counts = {state: 0 for state in _STATES}
    classified: list[dict[str, str]] = []
    for locator, prior in sorted(prior_present.items()):
        row: dict[str, str] = {"locator": locator, "prior_kind": prior[0]}
        if prior[3] is not None:
            row["prior_version_id"] = prior[3]
        matching = next_present.get(locator)
        reason = _covering_reason(locator, errors, directory_reasons=_DIRECTORY_ERRORS)
        exclusion = _covering_reason(
            locator, excluded, directory_reasons=_DIRECTORY_EXCLUSIONS
        )
        if reason is not None:
            state = "error_covered_prior"
            row["reason"] = reason
        elif exclusion is not None:
            state = "excluded_prior"
            row["reason"] = exclusion
        elif matching is not None and matching[0] == "deferred":
            state = "deferred_prior"
            assert isinstance(matching[7], str)
            row["reason"] = matching[7]
        elif matching is not None and prior[0] == "hashed":
            state = "unchanged" if matching[3] == prior[3] else "changed"
            assert matching[3] is not None
            row["next_version_id"] = matching[3]
        elif matching is not None:
            state = "newly_hashed_prior"
            assert matching[3] is not None
            row["next_version_id"] = matching[3]
        elif prior[0] == "deferred":
            state = "unobserved_hashless_prior"
        elif errors:
            state = "unobserved_prior"
        else:
            state = "absence_candidate"
        row["state"] = state
        counts[state] += 1
        classified.append(row)

    previous_hashed = sum(row[0] == "hashed" for row in prior_present.values())
    current_only_hashed = sum(
        row[0] == "hashed" and locator not in prior_present
        for locator, row in next_present.items()
    )
    current_only_deferred = sum(
        row[0] == "deferred" and locator not in prior_present
        for locator, row in next_present.items()
    )
    blockers = []
    if errors:
        blockers.append("current_scan_errors")
    if any(counts[state] for state in (
        "deferred_prior", "excluded_prior", "error_covered_prior",
        "unobserved_prior", "unobserved_hashless_prior",
    )):
        blockers.append("prior_coverage_requires_review")
    if fileos_mass_loss_requires_review(previous_hashed, counts["absence_candidate"]):
        blockers.append("mass_loss_requires_review")
    return {
        "preview_version": PREVIEW_VERSION,
        "publishable": False,
        "absence_authorized": False,
        "requires_review": True,
        "source_id": source_id,
        "root_binding_sha256": previous["root_binding"]["sha256"],
        "prior_observed_at": prior_time.isoformat(),
        "current_observed_at": next_time.isoformat(),
        "counts": counts,
        "current_only_hashed": current_only_hashed,
        "current_only_deferred": current_only_deferred,
        "prior_rows": classified,
        "blockers": blockers,
    }
