"""Fictional consecutive donor observations never become absence authority."""

from __future__ import annotations

import os
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from masterbrain.datacore import fileos_donor_shadow as shadow
from masterbrain.datacore.fileos_donor_candidate import build_fileos_donor_candidate
from masterbrain.datacore.fileos_v2_consecutive_preview import (
    preview_fileos_v2_consecutive_observations,
)

FIRST = datetime(2026, 10, 15, tzinfo=UTC)


def _candidate(root: Path, later: bool = False) -> dict:
    return build_fileos_donor_candidate(
        root, source_id="fictional_files", observed_at=FIRST + timedelta(days=later)
    )


def test_changed_missing_and_new_rows_are_only_preview_candidates(tmp_path: Path):
    (tmp_path / "missing.txt").write_text("fictional old", encoding="utf-8")
    (tmp_path / "changed.txt").write_text("fictional first", encoding="utf-8")
    previous = _candidate(tmp_path)
    (tmp_path / "missing.txt").unlink()
    (tmp_path / "changed.txt").write_text("fictional second", encoding="utf-8")
    (tmp_path / "new.txt").write_text("fictional new", encoding="utf-8")
    current = _candidate(tmp_path, later=True)
    original_previous, original_current = deepcopy(previous), deepcopy(current)

    preview = preview_fileos_v2_consecutive_observations(previous, current)

    assert previous == original_previous and current == original_current
    assert preview["publishable"] is False
    assert preview["absence_authorized"] is False
    assert preview["requires_review"] is True
    assert preview["counts"]["changed"] == 1
    assert preview["counts"]["absence_candidate"] == 1
    assert preview["current_only_hashed"] == 1
    assert preview["blockers"] == []
    assert {row["locator"]: row["state"] for row in preview["prior_rows"]} == {
        "changed.txt": "changed", "missing.txt": "absence_candidate",
    }


def test_symlink_directory_covers_old_child_and_any_error_suppresses_absence(tmp_path: Path):
    inside = tmp_path / "inside"
    inside.mkdir()
    (inside / "child.txt").write_text("fictional child", encoding="utf-8")
    (tmp_path / "other.txt").write_text("fictional other", encoding="utf-8")
    previous = _candidate(tmp_path)
    (inside / "child.txt").unlink()
    inside.rmdir()
    inside.symlink_to(tmp_path.parent, target_is_directory=True)
    (tmp_path / "other.txt").unlink()
    current = _candidate(tmp_path, later=True)

    preview = preview_fileos_v2_consecutive_observations(previous, current)

    assert preview["counts"]["error_covered_prior"] == 1
    assert preview["counts"]["unobserved_prior"] == 1
    assert preview["counts"]["absence_candidate"] == 0
    assert preview["blockers"] == ["current_scan_errors", "prior_coverage_requires_review"]


def test_hashless_prior_can_become_hashed_but_never_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = tmp_path / "cloud.txt"
    path.write_text("fictional cloud", encoding="utf-8")
    with monkeypatch.context() as patched:
        patched.setattr(shadow, "_is_dataless", lambda _info: True)
        previous = _candidate(tmp_path)
    current = _candidate(tmp_path, later=True)
    preview = preview_fileos_v2_consecutive_observations(previous, current)
    assert preview["counts"]["newly_hashed_prior"] == 1
    assert preview["counts"]["absence_candidate"] == 0

    path.unlink()
    missing = _candidate(tmp_path, later=True)
    preview = preview_fileos_v2_consecutive_observations(previous, missing)
    assert preview["counts"]["unobserved_hashless_prior"] == 1
    assert preview["counts"]["absence_candidate"] == 0


def test_hashed_prior_can_become_deferred_or_excluded_without_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = tmp_path / "record.txt"
    path.write_text("fictional evidence", encoding="utf-8")
    previous = _candidate(tmp_path)
    with monkeypatch.context() as patched:
        patched.setattr(shadow, "_is_dataless", lambda _info: True)
        deferred = _candidate(tmp_path, later=True)
    preview = preview_fileos_v2_consecutive_observations(previous, deferred)
    assert preview["counts"]["deferred_prior"] == 1
    assert preview["counts"]["absence_candidate"] == 0
    assert preview["blockers"] == ["prior_coverage_requires_review"]

    path.unlink()
    os.mkfifo(path)
    excluded = _candidate(tmp_path, later=True)
    preview = preview_fileos_v2_consecutive_observations(previous, excluded)
    assert preview["counts"]["excluded_prior"] == 1
    assert preview["counts"]["absence_candidate"] == 0
    assert preview["blockers"] == ["prior_coverage_requires_review"]


def test_donor_mass_loss_is_a_blocker_not_an_absence_event(tmp_path: Path):
    for index in range(20):
        (tmp_path / f"record_{index:02d}.txt").write_text(
            f"fictional {index}", encoding="utf-8"
        )
    previous = _candidate(tmp_path)
    for index in range(10):
        (tmp_path / f"record_{index:02d}.txt").unlink()
    current = _candidate(tmp_path, later=True)
    preview = preview_fileos_v2_consecutive_observations(previous, current)
    assert preview["counts"]["absence_candidate"] == 10
    assert preview["blockers"] == ["mass_loss_requires_review"]
    assert preview["absence_authorized"] is False


def test_incomplete_previous_observation_cannot_be_a_baseline(tmp_path: Path):
    (tmp_path / "outside").symlink_to(tmp_path.parent, target_is_directory=True)
    previous = _candidate(tmp_path)
    (tmp_path / "outside").unlink()
    current = _candidate(tmp_path, later=True)
    with pytest.raises(ValueError, match="boundary requires review"):
        preview_fileos_v2_consecutive_observations(previous, current)


def test_three_thousand_row_preview_has_exact_unchanged_coverage(tmp_path: Path):
    for index in range(3000):
        (tmp_path / f"record_{index:04d}.txt").write_text(
            f"fictional row {index}", encoding="utf-8"
        )
    previous, current = _candidate(tmp_path), _candidate(tmp_path, later=True)
    preview = preview_fileos_v2_consecutive_observations(previous, current)
    assert preview["counts"]["unchanged"] == 3000
    assert sum(preview["counts"].values()) == 3000
    assert preview["current_only_hashed"] == 0
    assert preview["blockers"] == []
    assert preview["absence_authorized"] is False


@pytest.mark.parametrize("change", ["source", "root_binding", "policy", "time", "row"])
def test_mismatched_or_malformed_candidate_is_refused(tmp_path: Path, change: str):
    (tmp_path / "record.txt").write_text("fictional", encoding="utf-8")
    previous, current = _candidate(tmp_path), _candidate(tmp_path, later=True)
    if change == "source":
        current["source"]["source_id"] = "another_source"
    elif change == "root_binding":
        current["root_binding"]["sha256"] = "0" * 64
    elif change == "policy":
        current["policy"]["metadata_only"] = True
    elif change == "time":
        current["observed_at"] = previous["observed_at"]
        current["hashed"][0]["observed_at"] = previous["observed_at"]
    else:
        current["hashed"][0]["version_id"] = "version_forged"
    with pytest.raises(ValueError):
        preview_fileos_v2_consecutive_observations(previous, current)
