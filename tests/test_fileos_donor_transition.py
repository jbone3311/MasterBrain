"""Synthetic v1-to-donor comparison; never infer deletion from policy drift."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from masterbrain.datacore import fileos_donor_candidate as candidate_module
from masterbrain.datacore import fileos_donor_shadow as shadow_module
from masterbrain.datacore.fileos import snapshot_tree
from masterbrain.datacore.fileos_donor_transition import preview_fileos_donor_transition

OBSERVED = datetime(2026, 9, 30, tzinfo=UTC)
POLICY = {
    "min_file_size": 0,
    "max_file_size_mb": 100,
    "include_extensions": None,
    "exclude_patterns": [],
}


def _v1(root: Path) -> dict:
    return snapshot_tree(root, source_id="files_transition", observed_at=OBSERVED, config=POLICY)


def _preview(root: Path, prior: dict, *, metadata_only: bool = False) -> dict:
    return preview_fileos_donor_transition(
        prior,
        root,
        source_id="files_transition",
        observed_at=OBSERVED + timedelta(days=1),
        metadata_only=metadata_only,
    )


def test_transition_classifies_every_prior_without_absence(tmp_path: Path) -> None:
    (tmp_path / "proof.txt").write_bytes(b"fictional stable proof")
    (tmp_path / "changed.txt").write_bytes(b"fictional old proof")
    (tmp_path / "missing.txt").write_bytes(b"fictional missing proof")
    (tmp_path / "_status.html").write_bytes(b"fictional generated status")
    prior = _v1(tmp_path)
    assert {row["locator"] for row in prior["items"]} == {
        "proof.txt", "changed.txt", "missing.txt", "_status.html"
    }
    (tmp_path / "changed.txt").write_bytes(b"fictional changed proof")
    (tmp_path / "missing.txt").unlink()
    (tmp_path / "new.txt").write_bytes(b"fictional new proof")
    preview = _preview(tmp_path, prior)
    assert preview["publishable"] is False
    assert preview["requires_review"] is True
    assert preview["counts"] == {
        "unchanged": 1,
        "changed": 1,
        "deferred_prior": 0,
        "excluded_prior": 1,
        "error_covered_prior": 0,
        "unobserved_prior": 1,
        "donor_only_hashed": 1,
    }
    assert {row["locator"]: row["state"] for row in preview["prior_items"]} == {
        "_status.html": "excluded_prior",
        "changed.txt": "changed",
        "missing.txt": "unobserved_prior",
        "proof.txt": "unchanged",
    }
    assert preview["donor_only_hashed"][0]["locator"] == "new.txt"
    assert preview["blockers"] == ["prior_item_not_hashed_under_donor_policy"]
    assert "absence" not in repr(preview)
    assert (tmp_path / "proof.txt").read_bytes() == b"fictional stable proof"


def test_metadata_only_does_not_gain_versions(tmp_path: Path) -> None:
    (tmp_path / "proof.txt").write_bytes(b"fictional proof")
    prior = _v1(tmp_path)
    preview = _preview(tmp_path, prior, metadata_only=True)
    assert preview["counts"]["deferred_prior"] == 1
    assert preview["counts"]["unchanged"] == 0
    assert preview["prior_items"][0]["reason"] == "no_hash"
    assert "donor_version_id" not in preview["prior_items"][0]
    assert preview["blockers"] == ["prior_item_not_hashed_under_donor_policy"]


def test_prior_and_donor_scan_errors_are_blockers(tmp_path: Path) -> None:
    (tmp_path / "proof.txt").write_bytes(b"fictional proof")
    (tmp_path / "link.txt").symlink_to(tmp_path / "proof.txt")
    prior = _v1(tmp_path)
    preview = _preview(tmp_path, prior)
    assert preview["counts"]["unchanged"] == 1
    assert preview["donor_errors"] == [{"locator": "link.txt", "code": "symlink_skipped"}]
    assert preview["blockers"] == ["prior_snapshot_errors", "donor_scan_errors"]


def test_directory_scan_error_covers_prior_descendant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "proof.txt").write_bytes(b"fictional proof")
    prior = _v1(tmp_path)
    original_scan = shadow_module.scan_donor_policy_shadow

    def unreadable_scan(root: Path, *, metadata_only: bool = False) -> dict:
        result = original_scan(root, metadata_only=metadata_only)
        result["rows"] = []
        result["errors"] = [{"locator": "nested", "code": "directory_unreadable"}]
        return result

    monkeypatch.setattr(candidate_module, "scan_donor_policy_shadow", unreadable_scan)
    preview = _preview(tmp_path, prior)
    assert preview["counts"]["error_covered_prior"] == 1
    assert preview["prior_items"][0]["reason"] == "directory_unreadable"
    assert preview["blockers"] == ["donor_scan_errors"]


@pytest.mark.parametrize("bad_time", [OBSERVED, OBSERVED - timedelta(seconds=1)])
def test_observation_must_be_newer_before_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_time: datetime
) -> None:
    (tmp_path / "proof.txt").write_bytes(b"fictional proof")
    prior = _v1(tmp_path)
    monkeypatch.setattr(
        "masterbrain.datacore.fileos_donor_transition.build_fileos_donor_candidate",
        lambda *_args, **_kwargs: pytest.fail("candidate scan started"),
    )
    with pytest.raises(ValueError, match="newer"):
        preview_fileos_donor_transition(
            prior, tmp_path, source_id="files_transition", observed_at=bad_time
        )


def test_source_and_root_mismatch_refuse_before_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "proof.txt").write_bytes(b"fictional proof")
    prior = _v1(first)
    monkeypatch.setattr(
        "masterbrain.datacore.fileos_donor_transition.build_fileos_donor_candidate",
        lambda *_args, **_kwargs: pytest.fail("candidate scan started"),
    )
    with pytest.raises(ValueError, match="source mismatch"):
        preview_fileos_donor_transition(
            prior, first, source_id="other", observed_at=OBSERVED + timedelta(days=1)
        )
    with pytest.raises(ValueError, match="root mismatch"):
        _preview(second, prior)
