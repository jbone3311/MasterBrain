"""Fictional exact-row coverage is historical, never absence authority."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from masterbrain.datacore.fileos_donor_candidate import build_fileos_donor_candidate
from masterbrain.datacore.fileos_v2_consecutive_preview import (
    preview_fileos_v2_consecutive_observations,
)
from masterbrain.datacore.fileos_v2_later_coverage import _coverage

FIRST = datetime(2026, 10, 15, tzinfo=UTC)


def _candidate(root: Path, *, later: bool) -> dict:
    return build_fileos_donor_candidate(
        root,
        source_id="fictional_files",
        observed_at=FIRST + timedelta(days=int(later)),
    )


def _packet(previous: dict, current: dict) -> dict:
    return {
        "candidate": current,
        "preview": preview_fileos_v2_consecutive_observations(previous, current),
        "source_id": "fictional_files",
        "root_binding_sha256": current["root_binding"]["sha256"],
    }


def test_later_coverage_projects_changed_new_and_missing_without_authority(
    tmp_path: Path,
) -> None:
    (tmp_path / "missing.txt").write_text("fictional old", encoding="utf-8")
    (tmp_path / "changed.txt").write_text("fictional old", encoding="utf-8")
    previous = _candidate(tmp_path, later=False)
    (tmp_path / "missing.txt").unlink()
    (tmp_path / "changed.txt").write_text("fictional new", encoding="utf-8")
    (tmp_path / "new.txt").write_text("fictional new", encoding="utf-8")
    current = _candidate(tmp_path, later=True)

    closure = _coverage(_packet(previous, current), "a" * 64)

    assert closure["publishable"] is False
    assert closure["absence_authorized"] is False
    assert closure["requires_review"] is True
    assert closure["current_counts"]["hashed"] == 2
    assert closure["prior_classification_counts"]["changed"] == 1
    assert closure["prior_classification_counts"]["absence_candidate"] == 1
    assert [row["locator"] for row in closure["current_rows"]] == [
        "changed.txt", "new.txt",
    ]
    assert [row["locator"] for row in closure["prior_rows"]] == [
        "changed.txt", "missing.txt",
    ]
    assert all(row["sha256"] is not None for row in closure["current_rows"])


def test_three_thousand_row_later_coverage_is_exact(tmp_path: Path) -> None:
    for index in range(3000):
        (tmp_path / f"row_{index:04d}.txt").write_text(
            f"fictional row {index}", encoding="utf-8"
        )
    previous = _candidate(tmp_path, later=False)
    current = _candidate(tmp_path, later=True)

    closure = _coverage(_packet(previous, current), "b" * 64)

    assert len(closure["current_rows"]) == 3000
    assert len(closure["prior_rows"]) == 3000
    assert closure["prior_classification_counts"]["unchanged"] == 3000
    assert len({row["locator"] for row in closure["current_rows"]}) == 3000
    assert closure["absence_authorized"] is False
