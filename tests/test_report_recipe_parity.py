"""Fictional FOS coverage/timeline goldens and exact-hash donor replay."""

from __future__ import annotations

import ast
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from masterbrain.report_recipe_parity import (
    CoverageDocument,
    TimelineFact,
    report_coverage,
    report_timeline,
)

DONOR_SHA256 = "e52ee7672121a609171a827eab086080dcea159ef987e21f0793e32528521cc9"
DONOR_PATH = (
    Path(__file__).resolve().parents[2] / "FOS-Master/_SYSTEM/tools/reporting.py"
)


def _coverage_rows() -> list[CoverageDocument]:
    return [
        CoverageDocument("finance", value) for value in (1, 1, 2, 99, None)
    ] + [CoverageDocument("legal", value) for value in (1, None, 0)]


def _timeline_rows() -> list[TimelineFact]:
    return [
        TimelineFact("finance", "date", "2024-01-01"),
        TimelineFact("finance", "date", "2024-02-01"),
        TimelineFact("legal", "date", "2023-01-01"),
        TimelineFact("finance", "date", "xx"),
        TimelineFact("finance", "date", ""),
        TimelineFact("finance", "date", None),
        TimelineFact("finance", "money", "2025-01-01"),
    ]


def test_coverage_golden_keeps_failed_skipped_and_success_denominators_distinct():
    assert report_coverage(_coverage_rows()) == {
        "report": "coverage", "filter_domain": None, "total_docs": 8,
        "total_extracted_ok": 3, "overall_pct": 37.5,
        "rows": [
            {"domain": "finance", "total_docs": 5, "extracted_ok": 2,
             "extracted_failed": 1, "skipped": 1, "pending": 1,
             "coverage_pct": 80.0},
            {"domain": "legal", "total_docs": 3, "extracted_ok": 1,
             "extracted_failed": 0, "skipped": 0, "pending": 1,
             "coverage_pct": 33.3},
        ],
    }
    assert report_coverage(_coverage_rows(), "finance")["overall_pct"] == 40.0
    assert report_coverage([], "finance")["rows"] == []
    assert report_coverage([], "finance")["overall_pct"] == 0.0
    assert report_coverage(_coverage_rows(), "")["total_docs"] == 8


def test_timeline_golden_keeps_donor_prefix_year_and_empty_behavior():
    assert report_timeline(_timeline_rows()) == {
        "report": "timeline", "filter_domain": None,
        "rows": [
            {"year": "xx", "domain": "finance", "fact_count": 1},
            {"year": "2024", "domain": "finance", "fact_count": 2},
            {"year": "2023", "domain": "legal", "fact_count": 1},
        ],
        "empty_hint": None,
    }
    assert [row["year"] for row in report_timeline(
        _timeline_rows(), "finance",
    )["rows"]] == ["xx", "2024"]
    assert report_timeline([], "finance")["empty_hint"] == (
        "No dated facts yet — run extract_facts.py to populate."
    )


def test_parity_inputs_are_bounded():
    with pytest.raises(ValueError, match="exceeds bound"):
        report_coverage([CoverageDocument("finance", 1)] * 10_001)
    with pytest.raises(ValueError, match="exceeds bound"):
        report_timeline([TimelineFact("finance", "date", "2024")] * 10_001)


def _donor_functions(db_path: Path) -> dict[str, Any]:
    if not DONOR_PATH.is_file():
        pytest.skip("pinned private FOS-Master checkout is unavailable")
    source = DONOR_PATH.read_bytes()
    assert hashlib.sha256(source).hexdigest() == DONOR_SHA256
    names = {"_sqlite", "_rows_to_dicts", "report_coverage", "report_timeline"}
    selected = [
        node for node in ast.parse(source, filename=str(DONOR_PATH)).body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    assert {node.name for node in selected} == names
    module = ast.Module(body=selected, type_ignores=[])
    namespace: dict[str, Any] = {
        "sqlite3": sqlite3, "DB_PATH": db_path, "datetime": datetime,
    }
    exec(compile(module, str(DONOR_PATH), "exec"), namespace)
    return namespace


def _donor_db(
    path: Path, documents: list[CoverageDocument], facts: list[TimelineFact],
) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE unified_index(domain text,facts_extracted integer)")
        conn.execute(
            "CREATE TABLE document_facts(domain text,fact_type text,fact_value_date text)"
        )
        conn.executemany(
            "INSERT INTO unified_index(domain,facts_extracted) VALUES (?,?)",
            [(row.domain, row.facts_extracted) for row in documents],
        )
        conn.executemany(
            "INSERT INTO document_facts(domain,fact_type,fact_value_date) VALUES (?,?,?)",
            [(row.domain, row.fact_type, row.fact_value_date) for row in facts],
        )


@pytest.mark.parametrize("domain", [None, "finance", "missing", ""])
def test_exact_pinned_donor_coverage_and_timeline_replay(tmp_path: Path, domain: str | None):
    documents, facts = _coverage_rows(), _timeline_rows()
    path = tmp_path / "fictional-donor.sqlite"
    _donor_db(path, documents, facts)
    donor = _donor_functions(path)
    donor_coverage = donor["report_coverage"](domain)
    donor_timeline = donor["report_timeline"](domain)
    donor_coverage.pop("generated_at")
    donor_timeline.pop("generated_at")
    assert report_coverage(documents, domain) == donor_coverage
    assert report_timeline(facts, domain) == donor_timeline


def test_exact_pinned_donor_thousand_row_repeat(tmp_path: Path):
    distribution = (("finance", 500, 2024), ("legal", 300, 2023), ("other", 200, 2022))
    documents = [
        CoverageDocument(domain, (1, 2, 99, None, 0)[index % 5])
        for domain, count, _ in distribution for index in range(count)
    ]
    facts = [
        TimelineFact(domain, "date", f"{year}-01-01")
        for domain, count, year in distribution for _ in range(count)
    ]
    path = tmp_path / "fictional-donor.sqlite"
    _donor_db(path, documents, facts)
    donor = _donor_functions(path)
    for _ in range(2):
        baseline_coverage = donor["report_coverage"]()
        baseline_timeline = donor["report_timeline"]()
        baseline_coverage.pop("generated_at")
        baseline_timeline.pop("generated_at")
        assert report_coverage(documents) == baseline_coverage
        assert report_timeline(facts) == baseline_timeline
