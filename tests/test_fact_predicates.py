"""Code-first reviewed project-fact vocabulary contracts."""

from datetime import UTC, datetime

import pytest

from masterbrain.fact_predicates import (
    PROJECT_FACT_PREDICATES,
    registry_status,
    registry_status_with_latest,
    require_registered_fact,
)
from masterbrain.knowledge_schema import ProjectFactWrite


def _fact(predicate: str, *, value_type: str = "text", measurement: dict | None = None):
    return ProjectFactWrite.model_validate({
        "kind": "project_fact", "project_id": "project_" + "1" * 32,
        "predicate": predicate, "value": "100.25" if measurement else "Fictional note",
        "value_type": value_type, "measurement": measurement,
        "evidence_ids": ["evidence_" + "2" * 32],
        "quote_evidence_id": "evidence_" + "2" * 32,
        "source_quote": "Fictional note: 100.25 USD",
        "confidence": 1, "observed_at": datetime(2026, 10, 15, tzinfo=UTC),
        "reviewed": True,
    })


def test_canonical_registry_is_unique_and_explicit():
    assert "loi.price" in PROJECT_FACT_PREDICATES
    assert "capital_call.amount" in PROJECT_FACT_PREDICATES
    assert len(PROJECT_FACT_PREDICATES) == len(set(PROJECT_FACT_PREDICATES))
    assert all(spec.version == 1 for spec in PROJECT_FACT_PREDICATES.values())
    assert _fact("deal.note").predicate == "deal.note"
    assert _fact("loi.price", value_type="number", measurement={
        "amount": "100.25", "unit": "currency", "currency": "USD",
    }).predicate == "loi.price"


def test_unknown_or_wrong_shape_never_publishes_as_a_registered_fact():
    unknown = _fact("unlisted.note")
    assert registry_status(unknown.predicate, unknown.value_type, None) == "unknown"
    assert registry_status("capital_call.amount", "text", None) == "shape_mismatch"
    assert registry_status("loi.price", "number", "shares") == "shape_mismatch"
    assert registry_status("deal.note", "text", "currency") == "shape_mismatch"
    assert registry_status("loi.price", "number", "currency") == "active"
    for predicate, value_type, unit in (
        ("unlisted.note", "text", None),
        ("capital_call.amount", "text", None),
        ("loi.price", "number", "shares"),
        ("deal.note", "text", "currency"),
    ):
        with pytest.raises(ValueError, match="registry review"):
            require_registered_fact(predicate, value_type, unit)


def test_latest_database_revision_can_deprecate_but_not_revive_old_version():
    active = {"version": 1, "status": "active", "value_type": "number",
              "unit_code": "currency"}
    assert registry_status_with_latest("loi.price", "number", "currency", active) == "active"
    assert registry_status_with_latest(
        "loi.price", "number", "currency", {**active, "version": 2, "status": "deprecated"},
    ) == "deprecated"
    assert registry_status_with_latest(
        "loi.price", "number", "currency", {**active, "version": 2},
    ) == "version_mismatch"
    assert registry_status_with_latest("loi.price", "number", "currency", None) == "unknown"
