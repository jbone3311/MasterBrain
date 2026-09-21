"""Deterministic labelled-format candidates. Unknown formats abstain, never infer."""

from typing import Any

from pydantic import ValidationError

from email_brain.memory_schema import PAYLOAD

VERSION = "labelled-memory-v1"
FIELDS = {
    "trip": {"Start date": "start_date", "End date": "end_date"},
    "flight": {"Airline": "airline", "Confirmation": "confirmation"},
    "hotel": {
        "Hotel": "hotel",
        "Confirmation": "confirmation",
        "Location": "location",
        "Check in": "check_in",
        "Check out": "check_out",
        "Time zone": "timezone",
    },
    "bill": {
        "Vendor": "vendor",
        "Invoice": "invoice_number",
        "Due date": "due_date",
        "Amount": "amount",
        "Currency": "currency",
    },
}
SEGMENT = {
    "Flight": "flight_number",
    "From airport": "origin",
    "To airport": "destination",
    "Departure": "departure",
    "Arrival": "arrival",
}


def extract(text: str) -> dict[str, Any]:
    """Parse one entire short labelled body, not quoted history or arbitrary prose."""
    empty = {
        "extractor_version": VERSION,
        "status": "abstained",
        "candidate": None,
        "reason": "unsupported_or_ambiguous_format",
        "requires_review": True,
    }
    if not isinstance(text, str) or not 0 < len(text) <= 2000:
        return empty
    values: dict[str, str] = {}
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator or key in values or not value.strip():
            return empty
        values[key] = value.strip()
    kind = values.get("Record type", "")
    if kind not in FIELDS or "Title" not in values:
        return empty
    allowed = {"Record type", "Title", "Status"} | set(FIELDS[kind])
    if kind == "flight":
        allowed |= set(SEGMENT) | {"Traveler"}
    if set(values) - allowed:
        return empty
    payload: dict[str, Any] = {"kind": kind, "title": values["Title"]}
    if "Status" in values:
        payload["status"] = values["Status"]
    for label, field in FIELDS[kind].items():
        if label in values:
            payload[field] = values[label]
    if kind == "flight":
        segment = {field: values[label] for label, field in SEGMENT.items() if label in values}
        if segment:
            payload["segments"] = [segment]
        if "Traveler" in values:
            payload["travelers"] = [values["Traveler"]]
    try:
        validated = PAYLOAD.validate_python(payload)
    except (ValidationError, ValueError):
        return empty
    return {
        "extractor_version": VERSION,
        "status": "candidate",
        "reason": "labelled_format",
        "candidate": validated.model_dump(mode="json"),
        "source_quote": text.strip(),
        "requires_review": True,
    }
