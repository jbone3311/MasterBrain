"""The offline donor comparison must not certify an edited FOS checkout."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest


def _parity_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "datacore_parity.py"
    spec = importlib.util.spec_from_file_location("datacore_parity_provenance", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pinned_parity_attests_both_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    parity = _parity_module()
    tools = tmp_path / "_SYSTEM" / "tools"
    tools.mkdir(parents=True)
    dedup = tools / "dedup_tool.py"
    extract = tools / "doc_extract.py"
    dedup.write_bytes(b"fictional dedupe module")
    extract.write_bytes(b"fictional extractor module")
    monkeypatch.setattr(
        parity, "PINNED_DEDUP_SHA256", hashlib.sha256(dedup.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(
        parity, "PINNED_EXTRACT_SHA256", hashlib.sha256(extract.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(
        parity,
        "_git",
        lambda _repo, *args: parity.PINNED_FOS_COMMIT if args == ("rev-parse", "HEAD") else "",
    )

    assert parity.verify_donor(tmp_path) == parity.PINNED_FOS_COMMIT
    extract.write_bytes(b"edited extractor module")
    with pytest.raises(ValueError, match="source hash changed: doc_extract.py"):
        parity.verify_donor(tmp_path)


def test_dirty_donor_is_refused_even_with_unpinned_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    parity = _parity_module()
    monkeypatch.setattr(
        parity,
        "_git",
        lambda _repo, *args: "alternate-commit" if args == ("rev-parse", "HEAD") else " M file",
    )
    with pytest.raises(ValueError, match="checkout is dirty"):
        parity.verify_donor(tmp_path, allow_unpinned=True)


def test_unpinned_donor_requires_explicit_exploratory_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    parity = _parity_module()
    monkeypatch.setattr(
        parity,
        "_git",
        lambda _repo, *args: "alternate-commit" if args == ("rev-parse", "HEAD") else "",
    )
    with pytest.raises(ValueError, match="expected pinned donor"):
        parity.verify_donor(tmp_path)
    assert parity.verify_donor(tmp_path, allow_unpinned=True) == "alternate-commit"
