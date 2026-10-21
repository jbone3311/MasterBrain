"""Versioned vocabulary for newly reviewed project facts.

Legacy rows are never reclassified. Additions require an explicit code/SQL
migration and tests; aliases must not silently change a fact's meaning.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class FactPredicate:
    version: int
    value_type: Literal["text", "number", "date", "boolean", "reference"]
    unit: Literal["currency", "shares", "percent", "count"] | None
    description: str


PROJECT_FACT_PREDICATES: dict[str, FactPredicate] = {
    "deal.note": FactPredicate(1, "text", None, "Source-stated project note; not a summary."),
    "loan.proposed_amount": FactPredicate(
        1, "text", None, "Raw proposed loan amount before canonical numeric extraction."
    ),
    "capital.amount": FactPredicate(
        1, "number", "currency", "Source-stated capital amount; not a balance."
    ),
    "loi.price": FactPredicate(
        1, "number", "currency", "Source-stated letter-of-intent price; not a sale."
    ),
    "capital_call.amount": FactPredicate(
        1, "number", "currency", "Source-stated capital-call amount; not paid capital."
    ),
}


def registry_status(predicate: str, value_type: str, unit: str | None) -> str:
    """Describe a proposed row without approving an unknown name or shape."""
    spec = PROJECT_FACT_PREDICATES.get(predicate)
    if spec is None:
        return "unknown"
    if spec.value_type != value_type or spec.unit != unit:
        return "shape_mismatch"
    return "active"


def registry_status_with_latest(
    predicate: str, value_type: str, unit: str | None,
    latest: Mapping[str, object] | None,
) -> str:
    """Combine checked-in shape with the database's authoritative revision."""
    code_status = registry_status(predicate, value_type, unit)
    if code_status != "active":
        return code_status
    if latest is None:
        return "unknown"
    if latest.get("status") == "deprecated":
        return "deprecated"
    expected = PROJECT_FACT_PREDICATES[predicate]
    if (latest.get("status") != "active"
            or latest.get("version") != expected.version
            or latest.get("value_type") != expected.value_type
            or latest.get("unit_code") != expected.unit):
        return "version_mismatch"
    return "active"


def require_registered_fact(
    predicate: str, value_type: str, unit: str | None,
) -> FactPredicate:
    """Gate NEW publication; exact older idempotent receipts are checked first."""
    status = registry_status(predicate, value_type, unit)
    if status != "active":
        raise ValueError("project fact predicate requires registry review: " + status)
    return PROJECT_FACT_PREDICATES[predicate]
