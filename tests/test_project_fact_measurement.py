"""Closed exact-decimal measurement validation, not a balance calculator."""

from datetime import UTC, datetime

import pytest

from masterbrain.knowledge_schema import ProjectFactMeasurement, ProjectFactWrite


def _fact(measurement: dict, value: str = "100.25", value_type: str = "number",
          quote: str = "The fictional figure was 100.25 USD shares percent count."):
    return ProjectFactWrite(
        kind="project_fact", project_id="project_" + "1" * 32,
        predicate="capital.amount", value=value, value_type=value_type,
        evidence_ids=["evidence_" + "2" * 32],
        quote_evidence_id="evidence_" + "2" * 32,
        source_quote=quote,
        confidence=1.0, observed_at=datetime(2026, 10, 15, tzinfo=UTC),
        reviewed=True, measurement=measurement,
    )


def test_exact_decimal_currency_and_noncurrency_contract():
    fact = _fact({"amount": "100.25", "unit": "currency", "currency": "USD"})
    assert fact.measurement == ProjectFactMeasurement(
        amount="100.25", unit="currency", currency="USD",
    )
    assert ProjectFactMeasurement(amount="100.25", unit="shares").currency is None
    assert ProjectFactMeasurement(amount="100.25", unit="count").unit == "count"


def test_registered_financial_predicate_requires_its_declared_type_and_unit():
    from masterbrain.fact_predicates import require_registered_fact

    unregistered_unit = _fact({"amount": "100.25", "unit": "shares"})
    with pytest.raises(ValueError, match="registry review"):
        require_registered_fact(unregistered_unit.predicate, unregistered_unit.value_type,
                                unregistered_unit.measurement.unit)


@pytest.mark.parametrize("amount", ["1e3", "+1", "01", "1.123456789", "NaN", "Infinity", 1.0])
def test_noncanonical_or_float_amount_rejected(amount):
    with pytest.raises(ValueError):
        _fact({"amount": amount, "unit": "currency", "currency": "USD"})


def test_mismatched_value_and_currency_shape_rejected():
    with pytest.raises(ValueError):
        _fact({"amount": "100.25", "unit": "currency", "currency": "USD"}, value="100")
    with pytest.raises(ValueError):
        _fact({"amount": "100.25", "unit": "currency", "currency": "USD"},
              value_type="text")
    with pytest.raises(ValueError):
        _fact({"amount": "100.25", "unit": "currency"})
    with pytest.raises(ValueError):
        _fact({"amount": "100.25", "unit": "shares", "currency": "USD"})
    with pytest.raises(ValueError):
        _fact({"amount": "100.25", "unit": "currency", "currency": "usd"})
    with pytest.raises(ValueError):
        _fact({"amount": "100.25", "unit": "currency", "currency": "USD"},
              quote="The source says 100.25 EUR.")
    with pytest.raises(ValueError):
        _fact({"amount": "100.25", "unit": "currency", "currency": "USD"},
              quote="The source says 200.00 USD.")


@pytest.mark.parametrize("quote", [
    "The source says 1100.25 USD.",
    "The source says -100.25 USD.",
    "The source says 100.25 USDA.",
    "The source says 100.25 preUSD.",
    "The source says 100.25USD without a unit boundary.",
    "The source says 100.25 US dollars.",
])
def test_measurement_requires_complete_amount_and_unit_tokens(quote):
    with pytest.raises(ValueError):
        _fact({"amount": "100.25", "unit": "currency", "currency": "USD"},
              quote=quote)


def test_quote_allows_punctuation_around_complete_tokens():
    assert _fact({"amount": "100.25", "unit": "currency", "currency": "USD"},
                 quote="The amount ($100.25), in USD; was fictional.").measurement
