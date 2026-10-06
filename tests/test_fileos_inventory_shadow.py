"""Synthetic-only contracts for the FileOS scanner shadow comparator."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sqlite3
from pathlib import Path

import pytest

from masterbrain.datacore import fileos as shared_fileos
from masterbrain.datacore import fileos_donor_shadow as donor_profile
from masterbrain.datacore.fileos_donor_candidate import build_fileos_donor_candidate
from masterbrain.datacore.persistence import validate_fileos_completion_coverage

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fileos_inventory_shadow.py"
SPEC = importlib.util.spec_from_file_location("fileos_inventory_shadow", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
shadow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shadow)


def _manifest(*items: tuple[str, int, str], errors: list[dict[str, str]] | None = None) -> dict:
    return {
        "items": [
            {"locator": locator, "size_bytes": size, "digest": {"value": sha}}
            for locator, size, sha in items
        ],
        "errors": [] if errors is None else errors,
    }


def test_common_digest_and_size_must_match(tmp_path: Path) -> None:
    rows = {"report.txt": {"size_bytes": 3, "sha256": "abc"}}
    assert shadow.compare_inventory(tmp_path, rows, _manifest(("report.txt", 3, "abc"))) == {
        "common": 1,
        "differences": [],
    }
    mismatch = shadow.compare_inventory(tmp_path, rows, _manifest(("report.txt", 3, "other")))
    assert mismatch["differences"] == [{"locator": "report.txt", "code": "common_sha256_mismatch"}]
    mismatch = shadow.compare_inventory(tmp_path, rows, _manifest(("report.txt", 4, "abc")))
    assert mismatch["differences"] == [{"locator": "report.txt", "code": "common_size_mismatch"}]


def test_known_policy_difference_is_reason_coded(tmp_path: Path) -> None:
    rows = {
        ".db/child.txt": {"size_bytes": 1, "sha256": "a"},
        "metadata.db": {"size_bytes": 1, "sha256": "b"},
    }
    actual = shadow.compare_inventory(
        tmp_path, rows, _manifest(("~$draft.docx", 1, "c"), ("_SYSTEM/state.json", 1, "d"))
    )
    assert actual["differences"] == [
        {"locator": ".db/child.txt", "code": "shared_dedupe_exclusion"},
        {"locator": "_SYSTEM/state.json", "code": "donor_operational"},
        {"locator": "metadata.db", "code": "shared_dedupe_exclusion"},
        {"locator": "~$draft.docx", "code": "donor_junk_file"},
    ]


def test_unexplained_and_hashless_are_not_equivalent(tmp_path: Path) -> None:
    rows = {
        "lost.txt": {"size_bytes": 1, "sha256": "a"},
        "nohash.txt": {"size_bytes": 1, "sha256": None},
    }
    manifest = _manifest(("nohash.txt", 1, "b"), ("unexpected.txt", 1, "c"))
    actual = shadow.compare_inventory(tmp_path, rows, manifest)
    assert actual["differences"] == [
        {"locator": "lost.txt", "code": "unexplained_donor_only"},
        {"locator": "nohash.txt", "code": "unexpected_donor_hashless"},
        {"locator": "unexpected.txt", "code": "unexplained_shared_only"},
    ]
    deferred = shadow.compare_inventory(tmp_path, rows, manifest, allow_hashless=True)
    assert {difference["code"] for difference in deferred["differences"]} == {
        "unexplained_donor_only",
        "donor_hash_deferred",
        "unexplained_shared_only",
    }


def test_snapshot_errors_remain_visible(tmp_path: Path) -> None:
    actual = shadow.compare_inventory(
        tmp_path,
        {},
        _manifest(errors=[{"locator": "inaccessible", "code": "directory_unreadable"}]),
    )
    assert actual["differences"] == [
        {"locator": "inaccessible", "code": "shared_directory_unreadable"}
    ]


def test_fixture_is_fictional_and_bound_to_requested_size(tmp_path: Path) -> None:
    root = tmp_path / "synthetic"
    root.mkdir()
    shadow.make_synthetic_tree(root, 100)
    assert len(list(root.rglob("record_*.txt"))) == 100
    assert (root / ".Investor Letters" / "2026" / "letter.txt").is_file()
    assert shadow.baseline_expected() == sorted(
        shadow.baseline_expected(), key=lambda diff: (diff["locator"], diff["code"])
    )
    with pytest.raises(ValueError):
        shadow.make_synthetic_tree(tmp_path, 99)


def test_shadow_refuses_file_backed_donor_database(tmp_path: Path) -> None:
    class Scanner:
        pass

    with sqlite3.connect(tmp_path / "synthetic.sqlite") as conn:
        with pytest.raises(ValueError, match="in-memory"):
            shadow.donor_scan(Scanner(), tmp_path, conn)


def test_live_pinned_donor_full_inventory_shadow() -> None:
    result = shadow.run_shadow(_pinned_scanner_root(), 100)
    assert result["baseline_common"] == 102
    assert result["changed_updated"] == 1
    assert result["single_removed"] == 1
    assert result["mass_prune_refused"] == result["mass_retained_vs_snapshot"]
    assert result["symlink_policy_differences"] == 2


def _pinned_scanner_root() -> Path:
    if os.environ.get("MASTERBRAIN_TEST_PINNED_SNAPSHOT") == "1":
        return shadow.PINNED_SNAPSHOT_ROOT
    repo = Path(__file__).resolve().parents[2] / "FOS-Master"
    return repo if repo.is_dir() else shadow.PINNED_SNAPSHOT_ROOT


def _pinned_scanner():
    return shadow.load_pinned_scanner(_pinned_scanner_root())


def test_pinned_snapshot_exact_source_and_local_equivalence() -> None:
    copied_tools = shadow.PINNED_SNAPSHOT_ROOT / "_SYSTEM" / "tools"
    expected = {
        "scan_domains.py": shadow.PINNED_SCANNER_SHA256,
        "junk_filter.py": shadow.PINNED_FILTER_SHA256,
    }
    for name, digest in expected.items():
        copied = (copied_tools / name).read_bytes()
        assert hashlib.sha256(copied).hexdigest() == digest
        local_repo = Path(__file__).resolve().parents[2] / "FOS-Master"
        if local_repo.is_dir():
            assert copied == (local_repo / "_SYSTEM" / "tools" / name).read_bytes()


def test_pinned_snapshot_refuses_source_hash_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(shadow, "PINNED_SCANNER_SHA256", "0" * 64)
        with pytest.raises(ValueError, match="scanner source hash changed"):
            shadow.load_pinned_scanner(shadow.PINNED_SNAPSHOT_ROOT)
    with monkeypatch.context() as patch:
        patch.setattr(shadow, "PINNED_FILTER_SHA256", "0" * 64)
        with pytest.raises(ValueError, match="classifier source hash changed"):
            shadow.load_pinned_scanner(shadow.PINNED_SNAPSHOT_ROOT)


def test_pinned_snapshot_scanner_matches_local_donor(tmp_path: Path) -> None:
    local_repo = Path(__file__).resolve().parents[2] / "FOS-Master"
    if not local_repo.is_dir():
        pytest.skip("local donor checkout is not present for source-to-snapshot comparison")
    root = tmp_path / "fictional_source_comparison"
    root.mkdir()
    shadow.make_synthetic_tree(root, 100)
    observed = []
    for source in (local_repo, shadow.PINNED_SNAPSHOT_ROOT):
        scanner = shadow.load_pinned_scanner(source)
        with sqlite3.connect(":memory:") as conn:
            scanner.ensure_schema(conn)
            observed.append((shadow.donor_scan(scanner, root, conn), shadow.donor_rows(conn)))
    assert observed[0] == observed[1]


def _assert_live_name_parity(scanner, root: Path, payloads: dict[str, bytes]) -> None:
    with sqlite3.connect(":memory:") as conn:
        scanner.ensure_schema(conn)
        assert shadow.donor_scan(scanner, root, conn)["added"] == len(payloads)
        rows = shadow.donor_rows(conn)
    manifest = shadow.snapshot_tree(root, source_id="shadow_source", observed_at=shadow.OBSERVED_AT)
    profile = donor_profile.scan_donor_policy_shadow(root)
    assert set(rows) == set(payloads)
    assert {item["locator"] for item in manifest["items"]} == set(payloads)
    assert {item["locator"] for item in profile["rows"]} == set(payloads)
    assert profile["errors"] == []
    assert shadow.compare_inventory(root, rows, manifest) == {
        "common": len(payloads), "differences": [],
    }
    for locator, payload in payloads.items():
        expected_sha = hashlib.sha256(payload).hexdigest()
        assert rows[locator]["sha256"] == expected_sha
        assert next(item for item in profile["rows"] if item["locator"] == locator)[
            "sha256"
        ] == expected_sha
    assert {item["locator"] for item in json.loads(json.dumps(profile))["rows"]} == set(
        payloads
    )


def test_live_pinned_donor_sparse_size_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scanner = _pinned_scanner()
    root = tmp_path / "synthetic_size_boundaries"
    root.mkdir()
    shared_limit = shared_fileos.DEFAULT_CONFIG["max_file_size_mb"] * 1024 * 1024
    donor_limit = scanner.MAX_HASH_BYTES
    shared_oversize = root / "shared_oversize.bin"
    donor_oversize = root / "donor_oversize.bin"
    with shared_oversize.open("wb") as handle:
        handle.truncate(shared_limit + 1)
    with donor_oversize.open("wb") as handle:
        handle.truncate(donor_limit + 1)
    if getattr(donor_oversize.stat(), "st_blocks", 0) * 512 > 1024 * 1024:
        pytest.skip("sparse-file allocation is unavailable on this filesystem")

    original_hash = scanner._hash_streaming

    def bounded_hash(path: Path):
        assert path != donor_oversize, "donor must not read files above its hash limit"
        return original_hash(path)

    monkeypatch.setattr(scanner, "_hash_streaming", bounded_hash)
    with sqlite3.connect(":memory:") as conn:
        scanner.ensure_schema(conn)
        result = shadow.donor_scan(scanner, root, conn)
        rows = shadow.donor_rows(conn)
    assert result["added"] == 2
    assert rows["shared_oversize.bin"]["sha256"] == shadow._sha256(shared_oversize)
    assert rows["donor_oversize.bin"]["sha256"] is None
    assert shadow.compare_inventory(
        root,
        rows,
        shadow.snapshot_tree(root, source_id="shadow_source", observed_at=shadow.OBSERVED_AT),
    ) == {
        "common": 0,
        "differences": [
            {"locator": "donor_oversize.bin", "code": "shared_size_limit"},
            {"locator": "shared_oversize.bin", "code": "shared_size_limit"},
        ],
    }


def test_live_pinned_donor_read_failure_retains_old_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scanner = _pinned_scanner()
    root = tmp_path / "synthetic_read_failure"
    root.mkdir()
    path = root / "readfail.txt"
    path.write_bytes(b"old fictional bytes")
    with sqlite3.connect(":memory:") as conn:
        scanner.ensure_schema(conn)
        assert shadow.donor_scan(scanner, root, conn)["added"] == 1
        old_row = shadow.donor_rows(conn)["readfail.txt"]
        path.write_bytes(b"new and longer fictional bytes")
        os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1_000_000_000))

        def unreadable(_path: Path):
            raise OSError("synthetic donor read refusal")

        monkeypatch.setattr(scanner, "_hash_streaming", unreadable)
        result = shadow.donor_scan(scanner, root, conn)
        assert (result["scanned"], result["updated"], result["removed"]) == (1, 0, 0)
        rows = shadow.donor_rows(conn)
        assert rows["readfail.txt"] == old_row

        def shared_unreadable(_root: Path, _locator: str, *, max_bytes: int, capture_bytes: bool):
            raise shared_fileos.ConfinedFileUnavailable()

        monkeypatch.setattr(shared_fileos, "read_confined_file", shared_unreadable)
        manifest = shadow.snapshot_tree(
            root, source_id="shadow_source", observed_at=shadow.OBSERVED_AT
        )
        assert manifest["errors"] == [{"locator": "readfail.txt", "code": "file_unreadable"}]
        assert shadow.compare_inventory(root, rows, manifest) == {
            "common": 0,
            "differences": [{"locator": "readfail.txt", "code": "shared_file_unreadable"}],
        }


def test_live_pinned_donor_snapshot_race_and_broken_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scanner = _pinned_scanner()
    root = tmp_path / "synthetic_race"
    root.mkdir()
    path = root / "changing.txt"
    path.write_bytes(b"old fictional bytes")
    (root / "broken.txt").symlink_to(root / "missing.txt")
    (root / "directory_link").symlink_to(root, target_is_directory=True)
    with sqlite3.connect(":memory:") as conn:
        scanner.ensure_schema(conn)
        donor_result = shadow.donor_scan(scanner, root, conn)
        rows = shadow.donor_rows(conn)
    assert donor_result["scanned"] == 2
    assert set(rows) == {"changing.txt"}

    original_read = shared_fileos.read_confined_file

    def changing_read(root: Path, locator: str, *, max_bytes: int, capture_bytes: bool):
        result = original_read(root, locator, max_bytes=max_bytes, capture_bytes=capture_bytes)
        (root / locator).write_bytes(b"new and longer fictional bytes")
        return result

    monkeypatch.setattr(shared_fileos, "read_confined_file", changing_read)
    manifest = shadow.snapshot_tree(root, source_id="shadow_source", observed_at=shadow.OBSERVED_AT)
    assert manifest["items"] == []
    assert manifest["errors"] == [
        {"locator": "broken.txt", "code": "symlink_skipped"},
        {"locator": "changing.txt", "code": "changed_during_scan"},
    ]
    assert shadow.compare_inventory(root, rows, manifest) == {
        "common": 0,
        "differences": [
            {"locator": "broken.txt", "code": "shared_symlink_skipped"},
            {"locator": "changing.txt", "code": "shared_changed_during_scan"},
        ],
    }


def test_live_pinned_donor_dataless_placeholder_simulation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scanner = _pinned_scanner()
    root = tmp_path / "synthetic_placeholder"
    root.mkdir()
    path = root / "placeholder.txt"
    path.write_bytes(b"fictional local bytes standing in for cloud metadata")
    monkeypatch.setattr(scanner, "_is_dataless", lambda candidate: candidate == path)

    def forbidden_hash(_path: Path):
        raise AssertionError("simulated dataless donor file must not be read")

    monkeypatch.setattr(scanner, "_hash_streaming", forbidden_hash)
    with sqlite3.connect(":memory:") as conn:
        scanner.ensure_schema(conn)
        assert shadow.donor_scan(scanner, root, conn)["added"] == 1
        rows = shadow.donor_rows(conn)
    assert rows["placeholder.txt"]["sha256"] is None
    manifest = shadow.snapshot_tree(root, source_id="shadow_source", observed_at=shadow.OBSERVED_AT)
    assert shadow.compare_inventory(root, rows, manifest) == {
        "common": 0,
        "differences": [{"locator": "placeholder.txt", "code": "unexpected_donor_hashless"}],
    }


def test_live_pinned_donor_unreadable_directory_is_not_a_complete_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scanner = _pinned_scanner()
    root = tmp_path / "synthetic_unreadable_directory"
    hidden = root / "inaccessible"
    hidden.mkdir(parents=True)
    (hidden / "old.txt").write_bytes(b"fictional prior content")
    with sqlite3.connect(":memory:") as conn:
        scanner.ensure_schema(conn)
        assert shadow.donor_scan(scanner, root, conn)["added"] == 1
        original_walk = os.walk

        def donor_walk(_root: Path):
            yield str(root), [], []

        with monkeypatch.context() as patcher:
            patcher.setattr(os, "walk", donor_walk)
            result = shadow.donor_scan(scanner, root, conn)
        assert (result["scanned"], result["removed"]) == (0, 1)
        assert shadow.donor_rows(conn) == {}

        def shared_walk(_root: Path, *, topdown: bool, onerror):
            assert topdown
            onerror(PermissionError(13, "synthetic access denial", str(hidden)))
            yield str(root), [], []

        with monkeypatch.context() as patcher:
            patcher.setattr(os, "walk", shared_walk)
            manifest = shadow.snapshot_tree(
                root, source_id="shadow_source", observed_at=shadow.OBSERVED_AT
            )
        assert os.walk is original_walk
    assert manifest["items"] == []
    assert manifest["errors"] == [{"locator": "inaccessible", "code": "directory_unreadable"}]


def test_live_pinned_donor_hash_time_mutation_can_record_stale_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scanner = _pinned_scanner()
    root = tmp_path / "synthetic_donor_race"
    root.mkdir()
    path = root / "changing.txt"
    path.write_bytes(b"short")
    original_hash = scanner._hash_streaming

    def mutate_then_hash(candidate: Path):
        candidate.write_bytes(b"new and longer fictional content")
        return original_hash(candidate)

    monkeypatch.setattr(scanner, "_hash_streaming", mutate_then_hash)
    with sqlite3.connect(":memory:") as conn:
        scanner.ensure_schema(conn)
        assert shadow.donor_scan(scanner, root, conn)["added"] == 1
        rows = shadow.donor_rows(conn)
    donor_row = rows["changing.txt"]
    assert donor_row["size_bytes"] == len(b"short")
    assert donor_row["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = shadow.snapshot_tree(root, source_id="shadow_source", observed_at=shadow.OBSERVED_AT)
    assert shadow.compare_inventory(root, rows, manifest) == {
        "common": 0,
        "differences": [{"locator": "changing.txt", "code": "common_size_mismatch"}],
    }


def test_live_pinned_donor_unusual_valid_filenames_round_trip(tmp_path: Path) -> None:
    scanner = _pinned_scanner()
    root = tmp_path / "synthetic_filenames"
    root.mkdir()
    locators = {" leading space.txt", "emoji-🧪.txt", "café.txt", "line\nbreak.txt"}
    for locator in locators:
        (root / locator).write_bytes(b"fictional name fixture")
    with sqlite3.connect(":memory:") as conn:
        scanner.ensure_schema(conn)
        assert shadow.donor_scan(scanner, root, conn)["added"] == len(locators)
        rows = shadow.donor_rows(conn)
    manifest = shadow.snapshot_tree(root, source_id="shadow_source", observed_at=shadow.OBSERVED_AT)
    assert set(rows) == locators
    assert {item["locator"] for item in manifest["items"]} == locators
    assert shadow.compare_inventory(root, rows, manifest) == {
        "common": len(locators),
        "differences": [],
    }
    assert {item["locator"] for item in json.loads(json.dumps(manifest))["items"]} == locators


def test_snapshot_refuses_unencodable_names_without_opening_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "valid.txt").write_bytes(b"fictional valid sibling")

    def names_with_surrogates(_root: Path, *, topdown: bool, onerror):
        assert topdown and onerror is not None
        directories = ["invalid-\udcff"]
        yield str(tmp_path), directories, ["invalid-\udcfe.txt", "valid.txt"]
        assert directories == []

    with monkeypatch.context() as patcher:
        patcher.setattr(shared_fileos.os, "walk", names_with_surrogates)
        manifest = shared_fileos.snapshot_tree(
            tmp_path, source_id="shadow_source", observed_at=shadow.OBSERVED_AT
        )
    assert [item["locator"] for item in manifest["items"]] == ["valid.txt"]
    assert manifest["errors"] == [{"locator": ".", "code": "invalid_locator_encoding"}]
    with pytest.raises(ValueError, match="incomplete FileOS snapshot coverage"):
        validate_fileos_completion_coverage(manifest)


def test_snapshot_sanitizes_unencodable_walk_error_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def walk_error(root: Path, *, topdown: bool, onerror):
        assert topdown
        onerror(PermissionError(13, "synthetic denial", str(root / "bad-\udcff")))
        yield str(root), [], []

    with monkeypatch.context() as patcher:
        patcher.setattr(shared_fileos.os, "walk", walk_error)
        manifest = shared_fileos.snapshot_tree(
            tmp_path, source_id="shadow_source", observed_at=shadow.OBSERVED_AT
        )
    assert manifest["errors"] == [{"locator": ".", "code": "invalid_locator_encoding"}]


def test_live_pinned_donor_invalid_byte_names_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "synthetic_invalid_byte_names"
    root.mkdir()
    (root / "valid.txt").write_bytes(b"fictional valid sibling")
    raw_root = os.fsencode(root)
    try:
        os.mkdir(raw_root + b"/invalid-\xfe")
        descriptor = os.open(
            raw_root + b"/invalid-\xff.txt", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
    except OSError:
        reason = "this filesystem refuses invalid-byte filenames"
        if os.environ.get("MASTERBRAIN_REQUIRE_INVALID_BYTE_FILENAMES") == "1":
            pytest.fail(reason)
        pytest.skip(reason)
    try:
        os.write(descriptor, b"fictional invalid-name sibling")
    finally:
        os.close(descriptor)

    scanner = _pinned_scanner()
    with sqlite3.connect(":memory:") as conn:
        scanner.ensure_schema(conn)
        with pytest.raises((UnicodeEncodeError, sqlite3.ProgrammingError)):
            shadow.donor_scan(scanner, root, conn)

    manifest = shadow.snapshot_tree(root, source_id="shadow_source", observed_at=shadow.OBSERVED_AT)
    profile = donor_profile.scan_donor_policy_shadow(root)
    assert [item["locator"] for item in manifest["items"]] == ["valid.txt"]
    assert manifest["errors"] == [{"locator": ".", "code": "invalid_locator_encoding"}]
    assert [row["locator"] for row in profile["rows"]] == ["valid.txt"]
    assert profile["errors"] == [{"locator": ".", "code": "invalid_locator_encoding"}]
    with pytest.raises(ValueError, match="unencodable filename"):
        build_fileos_donor_candidate(
            root, source_id="shadow_source", observed_at=shadow.OBSERVED_AT
        )


def test_live_pinned_donor_distinct_case_and_normalization_names(
    tmp_path: Path,
) -> None:
    scanner = _pinned_scanner()
    root = tmp_path / "synthetic_distinct_names"
    root.mkdir()
    payloads = {
        "Ledger.txt": b"fictional uppercase record",
        "ledger.txt": b"fictional lowercase record",
        "caf\u00e9.txt": b"fictional composed record",
        "cafe\u0301.txt": b"fictional decomposed record",
    }
    for locator, payload in payloads.items():
        (root / locator).write_bytes(payload)
    if (
        {entry.name for entry in root.iterdir()} != set(payloads)
        or any((root / locator).read_bytes() != payload for locator, payload in payloads.items())
    ):
        reason = "this filesystem cannot represent the distinct filename pairs"
        if os.environ.get("MASTERBRAIN_REQUIRE_DISTINCT_FILENAMES") == "1":
            pytest.fail(reason)
        pytest.skip(reason)

    _assert_live_name_parity(scanner, root, payloads)


def test_live_pinned_donor_same_directory_case_variants(tmp_path: Path) -> None:
    scanner = _pinned_scanner()
    root = tmp_path / "synthetic_case_variants"
    root.mkdir()
    payloads = {
        "Ledger.txt": b"fictional uppercase ledger",
        "ledger.txt": b"fictional lowercase ledger",
        "Report.PDF": b"fictional uppercase extension",
        "report.pdf": b"fictional lowercase extension",
    }
    for index in range(128):
        payloads[f"Record{index:04d}.txt"] = f"fictional uppercase {index}".encode()
        payloads[f"record{index:04d}.txt"] = f"fictional lowercase {index}".encode()
    for locator, payload in payloads.items():
        (root / locator).write_bytes(payload)
    if (
        {entry.name for entry in root.iterdir()} != set(payloads)
        or any((root / locator).read_bytes() != payload for locator, payload in payloads.items())
    ):
        reason = "this filesystem cannot represent distinct case-variant siblings"
        if os.environ.get("MASTERBRAIN_REQUIRE_DISTINCT_FILENAMES") == "1":
            pytest.fail(reason)
        pytest.skip(reason)

    _assert_live_name_parity(scanner, root, payloads)


def test_live_pinned_donor_case_and_normalization_across_directories(
    tmp_path: Path,
) -> None:
    scanner = _pinned_scanner()
    root = tmp_path / "synthetic_spelling_variants"
    payloads = {
        "upper/Ledger.txt": b"fictional uppercase record",
        "lower/ledger.txt": b"fictional lowercase record",
        "composed/caf\u00e9.txt": b"fictional composed record",
        "decomposed/cafe\u0301.txt": b"fictional decomposed record",
    }
    for locator, payload in payloads.items():
        path = root / locator
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    # Compare the actual names returned by this platform, not an assumed
    # Unicode storage form. Every file is in a separate directory, so this
    # corpus still runs when same-directory collisions cannot be represented.
    observed = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*.txt")
    }
    assert len(observed) == len(payloads)
    _assert_live_name_parity(scanner, root, observed)
