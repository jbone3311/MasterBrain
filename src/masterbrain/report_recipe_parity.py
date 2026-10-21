"""Isolated FOS report row semantics; never a current or financial-truth API.

Pinned FOS-Master 218d5caec2f20b9047fd3eb8e027dc671acf0c15,
_SYSTEM/tools/reporting.py, SHA-256
e52ee7672121a609171a827eab086080dcea159ef987e21f0793e32528521cc9.
The five report row shapes are compared here (ADR-209/210). No database, source
grant, verified fact, or user-facing report is read or published by this module.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from math import isfinite
from typing import Any, cast

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


@dataclass(frozen=True, slots=True)
class EntityMention:
    canonical_name: str
    entity_type: str
    domain: str | None


@dataclass(frozen=True, slots=True)
class MoneyFact:
    domain: str | None
    fact_type: str
    fact_value_num: float | None


def _bound(rows: Sequence[object]) -> None:
    if len(rows) > _MAX_ROWS:
        raise ValueError("report parity input exceeds bound")


def _donor_round(value: float) -> float:
    """DuckDB ROUND uses half-away rather than Python's ties-to-even."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def report_coverage(
    documents: Sequence[CoverageDocument], domain: str | None = None,
) -> dict[str, Any]:
    """Replicate the donor's status counts and two different percentages."""
    _bound(documents)
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
    _bound(facts)
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


def report_top_entities(
    mentions: Sequence[EntityMention], limit: int = 20, domain: str | None = None,
) -> dict[str, Any]:
    """Compare donor grouping by name/type, not by individual entity ID."""
    _bound(mentions)
    if not 0 <= limit <= _MAX_ROWS:
        raise ValueError("report parity limit exceeds bound")
    grouped: dict[tuple[str, str], list[str | None]] = defaultdict(list)
    for mention in mentions:
        if domain and mention.domain != domain:
            continue
        grouped[(mention.canonical_name, mention.entity_type)].append(mention.domain)
    rows = [
        {
            "canonical_name": name, "entity_type": kind,
            "mention_count": len(domains),
            "domain_count": len(set(domains) - {None}),
            "sample_domain": min((d for d in domains if d is not None), default=None),
        }
        for (name, kind), domains in grouped.items()
    ]
    # SQL only orders by count; equal-count ties have no donor order contract.
    rows.sort(key=lambda row: (
        -cast(int, row["mention_count"]), cast(str, row["canonical_name"]),
        cast(str, row["entity_type"]),
    ))
    rows = rows[:limit]
    return {
        "report": "top_entities", "filter_domain": domain, "limit": limit,
        "rows": rows,
        "empty_hint": None if rows else "No entities yet — run extract_facts.py to populate.",
    }


def report_entity_crossdomain(
    mentions: Sequence[EntityMention], min_domains: int = 2, limit: int = 50,
) -> dict[str, Any]:
    """Compare distinct non-NULL domains and mention multiplicity."""
    _bound(mentions)
    if not 0 <= limit <= _MAX_ROWS or not 0 <= min_domains <= _MAX_ROWS:
        raise ValueError("report parity limit exceeds bound")
    grouped: dict[tuple[str, str], list[str | None]] = defaultdict(list)
    for mention in mentions:
        grouped[(mention.canonical_name, mention.entity_type)].append(mention.domain)
    rows = []
    for (name, kind), domains in grouped.items():
        distinct = sorted(d for d in set(domains) if d is not None)
        if len(distinct) < min_domains:
            continue
        rows.append({
            "canonical_name": name, "entity_type": kind,
            "domain_count": len(distinct), "domains": ", ".join(distinct) or None,
            "total_mentions": len(domains),
        })
    # Donor STRING_AGG(DISTINCT) has no specified internal order; normalize its
    # domain list before direct comparison rather than claiming byte parity.
    rows.sort(key=lambda row: (
        -cast(int, row["domain_count"]), -cast(int, row["total_mentions"]),
        cast(str, row["canonical_name"]), cast(str, row["entity_type"]),
    ))
    rows = rows[:limit]
    return {
        "report": "entity_crossdomain", "min_domains": min_domains,
        "rows": rows,
        "empty_hint": None if rows else (
            "No cross-domain entities yet — run extract_facts.py across multiple domains."
        ),
    }


def report_dollars_by_domain(
    facts: Sequence[MoneyFact], domain: str | None = None,
) -> dict[str, Any]:
    """Compare raw numeric fact aggregation; never interpret as a balance."""
    _bound(facts)
    grouped: dict[str | None, list[float]] = defaultdict(list)
    for fact in facts:
        if fact.fact_type != "money" or fact.fact_value_num is None:
            continue
        if domain and fact.domain != domain:
            continue
        if not isfinite(fact.fact_value_num):
            raise ValueError("non-finite report parity amount")
        grouped[fact.domain].append(fact.fact_value_num)
    rows = []
    for name, values in grouped.items():
        rows.append({
            "domain": name, "fact_count": len(values),
            "total_amount": _donor_round(sum(values)),
            "avg_amount": _donor_round(sum(values) / len(values)),
            "max_amount": _donor_round(max(values)),
        })
    # SQL only orders by total; equal-total ties have no donor order contract.
    rows.sort(key=lambda row: (-cast(float, row["total_amount"]), row["domain"] or ""))
    return {
        "report": "dollars_by_domain", "filter_domain": domain,
        "grand_total": round(sum(cast(float, row["total_amount"]) for row in rows), 2),
        "rows": rows,
        "empty_hint": None if rows else "No money facts yet — run extract_facts.py to populate.",
    }
