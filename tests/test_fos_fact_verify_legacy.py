"""Fictional-only parity against the pinned, unmodified FOS verifier."""

from __future__ import annotations

import ast
import hashlib
import json
import random
import re
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from masterbrain.datacore.fos_fact_verify_legacy import (
    classify_tier,
    confirmation_status,
    value_variants,
)

DONOR_SHA256 = "c2f4c38c8a6bd783e726cebde1f555586d5675639aab2beb45c50128898feb8b"
DONOR_PATH = Path(__file__).resolve().parents[2] / "FOS-Master/_SYSTEM/tools/fact_verify.py"


def _donor() -> dict[str, Any]:
    if not DONOR_PATH.is_file():
        pytest.skip("pinned private FOS-Master checkout is unavailable")
    source = DONOR_PATH.read_bytes()
    assert hashlib.sha256(source).hexdigest() == DONOR_SHA256
    names = {"classify_tier", "_value_variants", "confirm"}
    tree = ast.parse(source, filename=str(DONOR_PATH))
    selected = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    assert {node.name for node in selected} == names
    ns: dict[str, Any] = {
        "re": re, "json": json, "hashlib": hashlib,
        "T1": "T1", "T2": "T2", "T3": "T3",
    }
    ns["T1_PATTERNS"] = re.compile(
        r"subscription agmt|subscription agreement|joinder|lpagreement|lp agreement|"
        r"executed|signed|k-?1\b|424b4|form s-1|prospectus|amended and restated", re.I,
    )
    ns["T2_PATTERNS"] = re.compile(
        r"portfolio summary|custodian report|investor statement|capitalcall|capital call|"
        r"period report|quarterly|pcap|financial-statement|financial statement|"
        r"stockdistribution|invoice|management fee", re.I,
    )
    ns["ADMIN_EMAIL_DOMAINS"] = re.compile(
        r"getquid\.com|troycapitalpartners|dblpartners|tcp-", re.I,
    )
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(DONOR_PATH), "exec"), ns)
    return ns


@pytest.mark.parametrize("source_type,kind,filename,sender", [
    ("regulatory", "pdf", "ordinary.pdf", ""),
    ("primary_document", "pdf", "signed subscription agreement.pdf", ""),
    ("primary_document", "pdf", "ordinary.pdf", ""),
    ("email", "eml", "signed subscription agreement.eml", "unknown@example.test"),
    ("email", "eml", "ordinary.eml", "contact@getquid.com.evil.test"),
    ("email", "eml", "ordinary.eml", "unknown@example.test"),
    ("internal_correction", "txt", "note.txt", ""),
    ("internal_correction", "txt", "signed note.txt", ""),
    (None, None, None, ""),
])
def test_tier_exact_donor_parity(source_type, kind, filename, sender):
    donor = _donor()
    assert classify_tier(source_type, kind, filename, sender) == donor["classify_tier"](
        source_type, kind, filename, sender,
    )


def test_numeric_variant_donor_parity_stress_and_unsafe_substrings():
    donor = _donor()["_value_variants"]
    rng = random.Random(216)
    cases: list[object] = [
        "1", "0.5", "10", "$1,000", "1e6", "not a number", "-1000", "NaN",
        "Infinity", 27_000_000_000.0,
    ]
    cases += [str(rng.randint(-10**11, 10**11) / 100) for _ in range(500)]
    for case in cases:
        if case == "Infinity":
            with pytest.raises((ValueError, OverflowError)) as donor_error:
                donor(case)
            with pytest.raises(type(donor_error.value)):
                value_variants(case)
        else:
            assert value_variants(case) == donor(case)
    # This is *why* numeric substring matching cannot attest to a financial claim.
    assert "1" in "1000" and "1" in value_variants("1")


def test_confirmation_status_parity_against_original_confirm(tmp_path: Path):
    donor = _donor()
    db = tmp_path / "fictional.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE sources (source_id INTEGER PRIMARY KEY, source_tier TEXT, "
                "source_type TEXT, kind TEXT, filename TEXT, from_party TEXT, "
                "sha256 TEXT, rel_path TEXT)")
    con.executemany("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?)", [
        (1, "T1", "primary_document", "pdf", "signed.pdf", "", "a" * 64, None),
        (2, "T2", "primary_document", "pdf", "quarterly.pdf", "", "b" * 64, None),
        (3, "T3", "email", "eml", "ordinary.eml", "", "c" * 64, None),
    ])
    con.commit()
    con.close()

    texts: dict[int, str | None] = {}

    def connect():
        cx = sqlite3.connect(db)
        cx.row_factory = sqlite3.Row
        return cx

    donor.update({
        "_connect": connect, "_ensure_schema": lambda _: None,
        "_source_text": lambda row: texts.get(row["source_id"]),
        "_resolve_source_path": lambda _: None,
    })
    cases = [
        ({1: "value 25", 2: "value 25"}, [1, 2], [True, True]),
        ({1: "value 25", 2: None}, [1, 2], [True, None]),
        ({1: "value 25", 2: "value 50"}, [1, 2], [True, False]),
        ({1: None, 2: None}, [1, 2], [None, None]),
        ({1: "value 25"}, [1, 999], [True, None]),
        ({1: "value 125"}, [1], [True]),  # donor substring false-positive
    ]
    for source_texts, ids, expected_matches in cases:
        texts.clear()
        texts.update(source_texts)
        result = donor["confirm"](1, "fictional.amount", "25", ids, apply=False)
        assert result["matches"] == expected_matches
        assert result["status"] == confirmation_status(expected_matches)
        assert result["hashes"][0] == "a" * 64
    # No donor database, files, or live path were touched.
