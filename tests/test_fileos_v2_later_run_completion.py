"""Fictional review-flag projection for historical later FileOS v2 runs."""

from masterbrain.datacore.fileos_v2_later_run_completion import _review_flags


def test_later_run_review_flags_keep_absence_and_coverage_distinct() -> None:
    packet = {
        "preview": {
            "counts": {"absence_candidate": 12},
            "blockers": [
                "mass_loss_requires_review",
                "prior_coverage_requires_review",
            ],
        }
    }
    assert _review_flags(packet) == {
        "possible_absence": True,
        "mass_loss": True,
        "prior_coverage": True,
    }
    packet["preview"]["counts"]["absence_candidate"] = 0
    packet["preview"]["blockers"] = ["prior_coverage_requires_review"]
    assert _review_flags(packet) == {
        "possible_absence": False,
        "mass_loss": False,
        "prior_coverage": True,
    }
