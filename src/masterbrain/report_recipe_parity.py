"""Isolated FOS report row semantics; never a current or financial-truth API.

Pinned FOS-Master 218d5caec2f20b9047fd3eb8e027dc671acf0c15,
_SYSTEM/tools/reporting.py, SHA-256
e52ee7672121a609171a827eab086080dcea159ef987e21f0793e32528521cc9.
Only coverage and timeline are compared here (ADR-209). No database, source
grant, verified fact, or user-facing report is read or published by this module.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

_MAX_ROWS = 10_000


@dataclass(frozen=True, slots=True)
class CoverageDocument:
    domain: str | None
    facts_extracted: int | None


@dataclass(frozen=True, slots=True)
class TimelineFact:
    domain: str | None
    fact_type: str
    fact_value_date: str | None


def report_coverage(
    documents: Sequence[CoverageDocument], domain: str | None = None,
) -> dict[str, Any]:
    """Replicate the donor's status counts and two different percentages."""
    if len(documents) > _MAX_ROWS:
        raise ValueError("report parity input exceeds bound")
    grouped: dict[str | None, list[CoverageDocument]] = defaultdict(list)
    for document in documents:
        if domain and document.domain != domain:
            continue
        grouped[document.domain].append(document)
    rows: list[dict[str, Any]] = []
    for name, group in grouped.items():
        total = len(group)
        ok = sum(row.facts_extracted == 1 for row in group)
        failed = sum(row.facts_extracted == 2 for row in group)
        skipped = sum(row.facts_extracted == 99 for row in group)
        pending = sum(row.facts_extracted is None for row in group)
        rows.append({
            "domain": name, "total_docs": total, "extracted_ok": ok,
            "extracted_failed": failed, "skipped": skipped, "pending": pending,
            "coverage_pct": round(100.0 * (ok + failed + skipped) / total, 1),
        })
    # Donor SQL orders by total_docs only; tied domains have no contractual order.
    rows.sort(key=lambda row: (-row["total_docs"], row["domain"] or ""))
    total_docs = sum(row["total_docs"] for row in rows)
    total_ok = sum(row["extracted_ok"] for row in rows)
    return {
        "report": "coverage", "filter_domain": domain, "total_docs": total_docs,
        "total_extracted_ok": total_ok,
        "overall_pct": round(100.0 * total_ok / total_docs, 1) if total_docs else 0.0,
        "rows": rows,
    }


def report_timeline(
    facts: Sequence[TimelineFact], domain: str | None = None,
) -> dict[str, Any]:
    """Replicate donor year-prefix grouping, including malformed nonempty dates."""
    if len(facts) > _MAX_ROWS:
        raise ValueError("report parity input exceeds bound")
    counts: dict[tuple[str, str | None], int] = defaultdict(int)
    for fact in facts:
        if (fact.fact_type != "date" or not fact.fact_value_date
                or (domain and fact.domain != domain)):
            continue
        counts[(fact.fact_value_date[:4], fact.domain)] += 1
    # Donor SQL orders by year DESC, fact_count DESC; domain ties are undefined.
    rows = [
        {"year": year, "domain": name, "fact_count": count}
        for (year, name), count in counts.items()
    ]
    rows.sort(key=lambda row: (row["year"], row["fact_count"]), reverse=True)
    return {
        "report": "timeline", "filter_domain": domain, "rows": rows,
        "empty_hint": None if rows else "No dated facts yet — run extract_facts.py to populate.",
    }
