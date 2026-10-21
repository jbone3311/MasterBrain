"""Compact, nonauthoritative snapshot of historical FileOS row review."""

from __future__ import annotations

from typing import Any

from email_brain.store import Conflict
from masterbrain.datacore.fileos_v2_consecutive_preview import _STATES
from masterbrain.datacore.persistence import _canonical_digest

SNAPSHOT_VERSION = "masterbrain-fileos-v2-later-review-snapshot-v1"
REQUIRED_ROW_STATES = frozenset({
    "absence_candidate", "deferred_prior", "excluded_prior",
    "error_covered_prior", "unobserved_prior", "unobserved_hashless_prior",
})
REVIEW_FLAGS = ("possible_absence", "mass_loss", "prior_coverage")
DISPOSITIONS = frozenset({
    "investigate", "dispute_classification",
    "acknowledge_historical_observation",
})


def historical_review_snapshot(
    *, source_id: str, generation_id: str, run_id: str, run_sha256: str,
    closure_id: str, closure_sha256: str, review_flags: dict[str, bool],
    prior_rows: list[dict[str, Any]], latest_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate exact membership and summarize without granting run authority."""
    if set(review_flags) != set(REVIEW_FLAGS) or any(
        type(value) is not bool for value in review_flags.values()
    ):
        raise Conflict("FileOS later review flags require review")
    latest: dict[str, dict[str, Any]] = {}
    for decision in latest_decisions:
        locator = decision.get("locator")
        if not isinstance(locator, str) or locator in latest:
            raise Conflict("FileOS later decision snapshot requires review")
        if decision.get("disposition") not in DISPOSITIONS:
            raise Conflict("FileOS later decision snapshot requires review")
        latest[locator] = decision
    projection: list[dict[str, Any]] = []
    seen: set[str] = set()
    required = acknowledged = held = missing = 0
    for row in prior_rows:
        locator = row.get("locator")
        state = row.get("state")
        if (
            not isinstance(locator, str) or not locator or locator in seen
            or state not in _STATES
        ):
            raise Conflict("FileOS later review closure requires review")
        seen.add(locator)
        latest_decision = latest.get(locator)
        if latest_decision is not None:
            del latest[locator]
        prior_version_id = row.get("prior_version_id")
        if latest_decision is not None and (
            latest_decision.get("state") != state
            or latest_decision.get("prior_version_id") != prior_version_id
            or not isinstance(latest_decision.get("reviewer_id"), str)
            or not isinstance(latest_decision.get("idempotency_key"), str)
            or not isinstance(latest_decision.get("recorded_at"), str)
        ):
            raise Conflict("FileOS later decision snapshot requires review")
        if state in REQUIRED_ROW_STATES:
            required += 1
            if latest_decision is None:
                missing += 1
            elif latest_decision["disposition"] == "acknowledge_historical_observation":
                acknowledged += 1
            else:
                held += 1
        projection.append({
            "locator": locator,
            "state": state,
            "prior_version_id": prior_version_id,
            "decision": None if latest_decision is None else {
                "disposition": latest_decision["disposition"],
                "reviewer_id": latest_decision["reviewer_id"],
                "idempotency_key": latest_decision["idempotency_key"],
                "recorded_at": latest_decision["recorded_at"],
            },
        })
    if latest:
        raise Conflict("FileOS later decision snapshot requires review")
    projection.sort(key=lambda row: row["locator"])
    flags_required = [name for name in REVIEW_FLAGS if review_flags[name]]
    digest = _canonical_digest({
        "version": SNAPSHOT_VERSION,
        "source_id": source_id,
        "generation_id": generation_id,
        "run_id": run_id,
        "run_sha256": run_sha256,
        "closure_id": closure_id,
        "closure_sha256": closure_sha256,
        "review_flags": review_flags,
        "prior_rows": projection,
    })
    return {
        "source_id": source_id,
        "generation_id": generation_id,
        "run_id": run_id,
        "snapshot_version": SNAPSHOT_VERSION,
        "decision_snapshot_sha256": digest,
        "total_prior_rows": len(projection),
        "required_row_decisions": required,
        "acknowledged_required_rows": acknowledged,
        "held_required_rows": held,
        "missing_required_rows": missing,
        "row_decisions_complete": required == acknowledged,
        "review_flags": dict(review_flags),
        "flag_acknowledgements_required": flags_required,
        "run_signoff_recorded": False,
        "absence_authorized": False,
        "current_read_active": False,
        "source_effect_authorized": False,
        "untrusted_content": True,
    }
