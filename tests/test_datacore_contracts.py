from __future__ import annotations

from datetime import UTC, datetime

import pytest

from masterbrain.datacore.contracts import (
    Digest,
    EvidenceRef,
    EvidenceStorage,
    ProvenanceRecord,
    SourceItemVersion,
    SourceKind,
    SourceRef,
    stable_id,
)

SHA = "a" * 64


def test_stable_id_is_deterministic_and_opaque() -> None:
    first = stable_id("item", "files_main", "private/contract.pdf")
    assert first == stable_id("item", "files_main", "private/contract.pdf")
    assert first != stable_id("item", "files_main", "private/other.pdf")
    assert "contract" not in first


@pytest.mark.parametrize("namespace", ["", "UPPER", "space bad", "a" * 129])
def test_stable_id_rejects_invalid_namespace(namespace: str) -> None:
    with pytest.raises(ValueError):
        stable_id(namespace, "x")


def test_source_item_is_immutable_and_normalizes_time() -> None:
    source = SourceRef("files_main", SourceKind.FILEOS, "Main files")
    item = SourceItemVersion(
        stable_id("item", "files_main", "folder/report.txt"),
        stable_id("version", "one"),
        source,
        "folder/report.txt",
        datetime(2026, 9, 22, 1, tzinfo=UTC),
        Digest("sha256", SHA),
        12,
        "text/plain",
        {"mtime_ns": 1, "reviewed": False},
    )
    assert item.observed_at.tzinfo is UTC
    with pytest.raises(TypeError):
        item.metadata["mtime_ns"] = 2  # type: ignore[index]


@pytest.mark.parametrize("locator", ["", "/absolute", "../escape", "a/../../escape", "bad\x00x"])
def test_source_item_rejects_unsafe_locator(locator: str) -> None:
    with pytest.raises(ValueError):
        SourceItemVersion(
            stable_id("item", "x"),
            stable_id("version", "x"),
            SourceRef("files_main", SourceKind.FILEOS, "Main"),
            locator,
            datetime.now(UTC),
            Digest("sha256", SHA),
            0,
            "text/plain",
        )


def test_contracts_reject_bad_digest_time_metadata_and_evidence_state() -> None:
    with pytest.raises(ValueError):
        Digest("md5", "a" * 32)
    with pytest.raises(ValueError):
        SourceItemVersion(
            stable_id("item", "x"),
            stable_id("version", "x"),
            SourceRef("files_main", SourceKind.FILEOS, "Main"),
            "ok.txt",
            datetime(2026, 9, 22),
            Digest("sha256", SHA),
            0,
            "text/plain",
        )
    with pytest.raises(ValueError):
        SourceItemVersion(
            stable_id("item", "x"),
            stable_id("version", "x"),
            SourceRef("files_main", SourceKind.FILEOS, "Main"),
            "ok.txt",
            datetime.now(UTC),
            Digest("sha256", SHA),
            0,
            "text/plain",
            {"nested": []},
        )
    with pytest.raises(ValueError):
        EvidenceRef(
            stable_id("evidence", "x"),
            stable_id("version", "x"),
            Digest("sha256", SHA),
            EvidenceStorage.SOURCE_BOUND,
            True,
        )


def test_provenance_requires_inputs_and_aware_time() -> None:
    digest = Digest("sha256", SHA)
    with pytest.raises(ValueError):
        ProvenanceRecord(
            stable_id("provenance", "x"),
            stable_id("chunk", "x"),
            (),
            "normalize",
            "v1",
            "abc123",
            datetime.now(UTC),
            digest,
        )
    record = ProvenanceRecord(
        stable_id("provenance", "x"),
        stable_id("chunk", "x"),
        (stable_id("evidence", "x"),),
        "normalize",
        "v1",
        "abc123",
        datetime.now(UTC),
        digest,
    )
    assert record.input_ids
