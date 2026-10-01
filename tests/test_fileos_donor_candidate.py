"""Synthetic candidate ledger: hashless donor rows are never evidence versions."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from masterbrain.datacore import fileos_donor_candidate as candidate
from masterbrain.datacore import fileos_donor_shadow as shadow
from masterbrain.datacore.fileos import INVENTORY_POLICY_VERSION
from masterbrain.datacore.persistence import _fileos_v2_staged_rows, validate_fileos_manifest

OBSERVED = datetime(2026, 9, 30, tzinfo=UTC)


def test_hashed_and_deferred_are_separate_and_not_publishable(tmp_path: Path) -> None:
    (tmp_path / "metadata.db").write_bytes(b"fictional database")
    (tmp_path / "_status.html").write_bytes(b"generated status")
    (tmp_path / ".Investor Letters").mkdir()
    (tmp_path / ".Investor Letters" / "proof.txt").write_bytes(b"fictional proof")
    oversized = tmp_path / "oversized.bin"
    with oversized.open("wb") as handle:
        handle.truncate(shadow.DONOR_HASH_LIMIT + 1)
    result = candidate.build_fileos_donor_candidate(
        tmp_path, source_id="files_candidate", observed_at=OBSERVED
    )
    assert result["candidate_version"] == candidate.CANDIDATE_VERSION
    assert result["publishable"] is False
    assert result["policy"]["donor_commit"] == candidate.DONOR_COMMIT
    assert result["counts"] == {"hashed": 2, "deferred": 1, "excluded": 1, "errors": 0}
    assert [row["locator"] for row in result["hashed"]] == [
        ".Investor Letters/proof.txt",
        "metadata.db",
    ]
    assert result["deferred"] == [
        {
            "item_id": result["deferred"][0]["item_id"],
            "locator": "oversized.bin",
            "size_bytes": shadow.DONOR_HASH_LIMIT + 1,
            "reason": "oversize",
        }
    ]
    assert "version_id" not in result["deferred"][0]
    assert "digest" not in result["deferred"][0]
    assert result["exclusions"] == [
        {"locator": "_status.html", "reason": "donor_junk_file"}
    ]
    with pytest.raises(ValueError, match="snapshot manifest"):
        validate_fileos_manifest(result)
    assert INVENTORY_POLICY_VERSION == "fileos-inventory-policy-v1"


def test_candidate_identity_replays_without_misdating_versions(tmp_path: Path) -> None:
    (tmp_path / "proof.txt").write_bytes(b"fictional")
    first = candidate.build_fileos_donor_candidate(
        tmp_path, source_id="files_candidate", observed_at=OBSERVED
    )
    later = candidate.build_fileos_donor_candidate(
        tmp_path, source_id="files_candidate", observed_at=OBSERVED + timedelta(days=1)
    )
    assert first["hashed"][0]["item_id"] == later["hashed"][0]["item_id"]
    assert first["hashed"][0]["version_id"] == later["hashed"][0]["version_id"]
    assert first["hashed"][0]["observed_at"] != later["hashed"][0]["observed_at"]
    (tmp_path / "proof.txt").write_bytes(b"changed fictional content")
    changed = candidate.build_fileos_donor_candidate(
        tmp_path, source_id="files_candidate", observed_at=OBSERVED + timedelta(days=2)
    )
    assert first["hashed"][0]["item_id"] == changed["hashed"][0]["item_id"]
    assert first["hashed"][0]["version_id"] != changed["hashed"][0]["version_id"]


def test_no_hash_and_dataless_never_gain_a_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "proof.txt").write_bytes(b"fictional")
    monkeypatch.setattr(
        shadow, "read_confined_file", lambda *args, **kwargs: pytest.fail("hashless read")
    )
    no_hash = candidate.build_fileos_donor_candidate(
        tmp_path, source_id="files_candidate", observed_at=OBSERVED, metadata_only=True
    )
    assert no_hash["counts"]["hashed"] == 0
    assert no_hash["deferred"][0]["reason"] == "no_hash"
    monkeypatch.setattr(shadow, "_is_dataless", lambda _info: True)
    monkeypatch.setattr(
        shadow, "read_confined_file", lambda *args, **kwargs: pytest.fail("dataless read")
    )
    dataless = candidate.build_fileos_donor_candidate(
        tmp_path, source_id="files_candidate", observed_at=OBSERVED
    )
    assert dataless["counts"]["hashed"] == 0
    assert dataless["deferred"][0]["reason"] == "dataless"
    for entry in (no_hash["deferred"][0], dataless["deferred"][0]):
        assert set(entry) == {"item_id", "locator", "size_bytes", "reason"}


def test_symlink_and_coverage_errors_remain_explicit(tmp_path: Path) -> None:
    (tmp_path / "proof.txt").write_bytes(b"fictional")
    (tmp_path / "link.txt").symlink_to(tmp_path / "proof.txt")
    result = candidate.build_fileos_donor_candidate(
        tmp_path, source_id="files_candidate", observed_at=OBSERVED
    )
    assert result["counts"]["errors"] == 1
    assert result["errors"] == [{"locator": "link.txt", "code": "symlink_skipped"}]
    assert [row["locator"] for row in result["hashed"]] == ["proof.txt"]


def test_v2_stage_projection_keeps_all_donor_ledger_kinds(tmp_path: Path) -> None:
    (tmp_path / "proof.txt").write_bytes(b"fictional")
    (tmp_path / "_status.html").write_bytes(b"generated")
    (tmp_path / "link.txt").symlink_to(tmp_path / "proof.txt")
    oversized = tmp_path / "oversized.bin"
    with oversized.open("wb") as handle:
        handle.truncate(shadow.DONOR_HASH_LIMIT + 1)
    result = candidate.build_fileos_donor_candidate(
        tmp_path, source_id="files_candidate", observed_at=OBSERVED
    )
    rows = _fileos_v2_staged_rows(result, "files_candidate")
    assert {row[0] for row in rows} == {"hashed", "deferred", "excluded", "error"}
    deferred = next(row for row in rows if row[0] == "deferred")
    assert deferred[3:5] == (None, None)
    assert deferred[7] == "oversize"
    forged = deepcopy(result)
    forged["deferred"][0]["version_id"] = "invented"
    with pytest.raises(ValueError, match="deferred row"):
        _fileos_v2_staged_rows(forged, "files_candidate")
    forged = deepcopy(result)
    forged["hashed"][0]["version_id"] = "invented"
    with pytest.raises(ValueError, match="hashed identity"):
        _fileos_v2_staged_rows(forged, "files_candidate")
    forged = deepcopy(result)
    forged["policy"]["donor_commit"] = "unreviewed"
    with pytest.raises(ValueError, match="candidate ledger"):
        _fileos_v2_staged_rows(forged, "files_candidate")
    forged = deepcopy(result)
    forged["errors"][0]["locator"] = "proof.txt"
    with pytest.raises(ValueError, match="candidate locator"):
        _fileos_v2_staged_rows(forged, "files_candidate")


def test_root_drift_keeps_candidate_nonpublishing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "proof.txt").write_bytes(b"fictional")
    real_binding = candidate.fileos_root_binding_sha256
    calls = 0

    def drifted_binding(root: Path) -> str:
        nonlocal calls
        calls += 1
        return real_binding(root) if calls == 1 else "0" * 64

    monkeypatch.setattr(candidate, "fileos_root_binding_sha256", drifted_binding)
    result = candidate.build_fileos_donor_candidate(
        tmp_path, source_id="files_candidate", observed_at=OBSERVED
    )
    assert result["publishable"] is False
    assert result["errors"] == [{"locator": ".", "code": "root_changed_during_scan"}]


@pytest.mark.parametrize(
    "observation",
    [datetime(2026, 9, 30), "2026-09-30", None],
)
def test_invalid_time_fails_before_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, observation: object
) -> None:
    monkeypatch.setattr(
        candidate, "scan_donor_policy_shadow", lambda *args, **kwargs: pytest.fail("scan started")
    )
    with pytest.raises(ValueError):
        candidate.build_fileos_donor_candidate(  # type: ignore[arg-type]
            tmp_path, source_id="files_candidate", observed_at=observation
        )


@pytest.mark.parametrize(
    "defect", ["duplicate", "hashless", "overlap", "unknown_error", "directory_overlap", "oversize"]
)
def test_corrupt_shadow_ledger_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    (tmp_path / "proof.txt").write_bytes(b"fictional")
    result = shadow.scan_donor_policy_shadow(tmp_path)
    if defect == "duplicate":
        result["rows"].append(result["rows"][0].copy())
    elif defect == "hashless":
        result["rows"][0]["sha256"] = None
    elif defect == "overlap":
        result["exclusions"].append(
            {"locator": "proof.txt", "reason": "donor_junk_file"}
        )
    elif defect == "directory_overlap":
        result["exclusions"].append(
            {"locator": "nested", "reason": "donor_junk_dir"}
        )
        result["rows"][0]["locator"] = "nested/proof.txt"
    elif defect == "oversize":
        result["rows"][0]["state"] = "oversize"
        result["rows"][0]["sha256"] = None
    else:
        result["errors"].append({"locator": "missing.txt", "code": "unknown"})
    monkeypatch.setattr(candidate, "scan_donor_policy_shadow", lambda *_args, **_kwargs: result)
    with pytest.raises(ValueError):
        candidate.build_fileos_donor_candidate(
            tmp_path, source_id="files_candidate", observed_at=OBSERVED
        )
