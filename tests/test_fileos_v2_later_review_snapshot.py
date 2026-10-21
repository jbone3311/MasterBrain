"""Synthetic, source-content-free tests for ADR-262 review summaries."""

from __future__ import annotations

from copy import deepcopy

import pytest

from email_brain.store import Conflict
from masterbrain.datacore.fileos_v2_later_review_snapshot import (
    historical_review_snapshot,
)

FLAGS = {"possible_absence": False, "mass_loss": False, "prior_coverage": False}


def snapshot(
    rows: list[dict[str, str]], decisions: list[dict[str, str]],
    flags: dict[str, bool] | None = None,
) -> dict[str, object]:
    return historical_review_snapshot(
        source_id="fictional_files",
        generation_id="fictional_generation",
        run_id="00000000-0000-4000-8000-000000000001",
        run_sha256="a" * 64,
        closure_id="00000000-0000-4000-8000-000000000002",
        closure_sha256="b" * 64,
        review_flags=FLAGS if flags is None else flags,
        prior_rows=rows,
        latest_decisions=decisions,
    )


def decision(locator: str, state: str, disposition: str, key: str) -> dict[str, str]:
    return {
        "locator": locator,
        "state": state,
        "prior_version_id": "prior-1",
        "disposition": disposition,
        "reviewer_id": "00000000-0000-4000-8000-000000000003",
        "idempotency_key": key,
        "recorded_at": "2026-10-16T00:00:00+00:00",
    }


def test_clean_historical_snapshot_is_stable_but_never_signoff() -> None:
    rows = [
        {"locator": "b.txt", "state": "changed", "prior_version_id": "prior-1"},
        {"locator": "a.txt", "state": "unchanged", "prior_version_id": "prior-1"},
    ]
    result = snapshot(rows, [])
    assert result["total_prior_rows"] == 2
    assert result["required_row_decisions"] == 0
    assert result["row_decisions_complete"] is True
    assert result["flag_acknowledgements_required"] == []
    reordered = snapshot(list(reversed(rows)), [])
    assert result["decision_snapshot_sha256"] == reordered["decision_snapshot_sha256"]
    assert result["run_signoff_recorded"] is False
    assert result["absence_authorized"] is False
    assert result["current_read_active"] is False
    assert result["source_effect_authorized"] is False


def test_mixed_coverage_and_mass_loss_hold_until_latest_rows_are_acknowledged() -> None:
    states = (
        "absence_candidate", "deferred_prior", "excluded_prior",
        "error_covered_prior", "unobserved_prior", "unobserved_hashless_prior",
    )
    rows = [
        {"locator": f"prior-{i}.txt", "state": state,
         "prior_version_id": "prior-1"}
        for i, state in enumerate(states)
    ]
    flags = {"possible_absence": True, "mass_loss": True, "prior_coverage": True}
    initial = snapshot(rows, [], flags)
    assert initial["required_row_decisions"] == 6
    assert initial["missing_required_rows"] == 6
    assert initial["row_decisions_complete"] is False
    assert initial["flag_acknowledgements_required"] == [
        "possible_absence", "mass_loss", "prior_coverage",
    ]
    decisions = [
        decision(row["locator"], row["state"],
                 "acknowledge_historical_observation", str(i))
        for i, row in enumerate(rows)
    ]
    decisions[0]["disposition"] = "investigate"
    decisions[1]["disposition"] = "dispute_classification"
    held = snapshot(rows, decisions, flags)
    assert held["acknowledged_required_rows"] == 4
    assert held["held_required_rows"] == 2
    assert held["missing_required_rows"] == 0
    assert held["row_decisions_complete"] is False
    corrected = deepcopy(decisions)
    corrected[0]["disposition"] = "acknowledge_historical_observation"
    corrected[0]["idempotency_key"] = "correction-0"
    corrected[1]["disposition"] = "acknowledge_historical_observation"
    corrected[1]["idempotency_key"] = "correction-1"
    complete = snapshot(rows, corrected, flags)
    assert complete["acknowledged_required_rows"] == 6
    assert complete["row_decisions_complete"] is True
    assert complete["decision_snapshot_sha256"] != held["decision_snapshot_sha256"]
    assert complete["flag_acknowledgements_required"] == [
        "possible_absence", "mass_loss", "prior_coverage",
    ]
    assert complete["run_signoff_recorded"] is False
    assert complete["absence_authorized"] is False


@pytest.mark.parametrize("defect", ["extra", "wrong_state", "duplicate"])
def test_forged_or_ambiguous_decision_snapshot_refuses(defect: str) -> None:
    rows = [{"locator": "prior.txt", "state": "absence_candidate",
             "prior_version_id": "prior-1"}]
    decisions = [decision("prior.txt", "absence_candidate", "investigate", "key-1")]
    if defect == "extra":
        decisions[0]["locator"] = "not-in-closure.txt"
    elif defect == "wrong_state":
        decisions[0]["state"] = "unchanged"
    else:
        decisions.append(deepcopy(decisions[0]))
    with pytest.raises(Conflict, match="requires review"):
        snapshot(rows, decisions)
