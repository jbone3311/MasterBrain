"""Isolated donor statement recipe candidates; not runtime or financial-truth APIs.

Extracted from FOS-Master at 218d5caec2f20b9047fd3eb8e027dc671acf0c15,
_SYSTEM/tools/statement_extract.py
(SHA-256 f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe).
The parsing and reconciliation semantics are intentionally unchanged. See
ADR-170 and ADR-174.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any


def _num(value: object) -> float | None:
    if value is None:
        return None
    value = str(value).replace(",", "").replace("$", "").strip()
    if value in ("", "--", "-", "N/A"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


_MONTHS = {month: f"{i:02d}" for i, month in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1
)}
_SB_TXN = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s+Trade Entry\s+(buy|sell)\s+([A-Z][A-Z0-9.]*)\s+"
    r"(-?[\d.]+)\s+\$([\d,.]+)\s+(-?)\$([\d,.]+)"
)
_SB_HOLDING_ROW = re.compile(
    r"^([A-Z][A-Z.]{0,5})\s+(.+?)\s+([\d.]+)\s+\$([\d,.]+)\s+\$([\d,.]+)\s+"
    r"\$([\d,.]+)\s+(-?\$[\d,.]+)\s+\$([\d,.]+)\s*$", re.MULTILINE
)
_SB_CASH_ROW = re.compile(
    r"^\*Cash\s+\w+\s+\$\s*(?:--|([\d,.]+))\s+\$\s*(?:--|([\d,.]+))\s+\$\s*(?:--|([\d,.]+))",
    re.MULTILINE,
)


def parse_streetbeat(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return the donor's raw summary and rows, without publication or effects."""
    summary: dict[str, Any] = {}
    match = re.search(r"Account No:\s*(\d+)", text)
    summary["account_number"] = match.group(1) if match else None
    match = re.search(r"Period:\s*([A-Za-z]+)\s*-\s*(\d{4})", text)
    summary["period"] = (
        f"{match.group(2)}-{_MONTHS.get(match.group(1).upper()[:3], '??')}"
        if match else None
    )
    match = re.search(r"Total Market Value\s*\$([\d,.]+)", text)
    summary["total_market_value"] = _num(match.group(1)) if match else None
    match = re.search(r"Long\s*\$([\d,.]+)", text)
    summary["long_value"] = _num(match.group(1)) if match else None

    items: list[dict[str, Any]] = []
    for date, side, symbol, quantity, price, sign, amount in _SB_TXN.findall(text):
        parsed_amount = _num(amount)
        assert parsed_amount is not None  # The pinned regex captures only numeric amounts.
        items.append({
            "row_type": "transaction", "line_date": date, "symbol": symbol,
            "quantity": float(quantity), "price": _num(price),
            "amount": (-1 if sign == "-" else 1) * parsed_amount,
            "description": f"{side} {symbol}", "period": summary["period"],
            "extraction_method": "regex:streetbeat",
        })

    holding_section = re.search(
        r"Symbol\s+Description\s+Quantity.*?TD Cost Basis\n(.*?)"
        r"(?:\nTransaction\b|\nTrade Date\b|\Z)", text, re.S,
    )
    if holding_section:
        block = holding_section.group(1)
        for row in _SB_HOLDING_ROW.findall(block):
            (symbol, description, quantity, market_price, market_value,
             _cost_price, unrealized, cost_basis) = row
            items.append({
                "row_type": "holding", "symbol": symbol, "description": description.strip(),
                "quantity": _num(quantity), "price": _num(market_price),
                "amount": _num(market_value),
                "category": f"cost_basis={_num(cost_basis)};unrealized={_num(unrealized)}",
                "period": summary["period"], "extraction_method": "regex:streetbeat",
            })
        cash = _SB_CASH_ROW.search(block)
        if cash and cash.group(2):
            items.append({
                "row_type": "holding", "symbol": "CASH", "description": "*Cash",
                "amount": _num(cash.group(2)), "period": summary["period"],
                "extraction_method": "regex:streetbeat",
            })
    return summary, items


def reconcile_streetbeat(
    summary: dict[str, Any], items: list[dict[str, Any]],
) -> tuple[float, float] | None:
    """Preserve the donor's reported-long-value versus summed-holdings check."""
    expected = summary.get("long_value") or summary.get("total_market_value")
    if expected is None:
        return None
    actual = round(sum(item["amount"] for item in items
                       if item["row_type"] == "holding" and item["amount"]), 2)
    return expected, actual


# Preserve the donor's intentionally low-confidence, flattened two-column
# Fidelity parse. This is a comparison baseline, not a complete holdings parser.
_FID_HOLDING_ROW = re.compile(
    r"^([A-Z][A-Za-z0-9&.,'/\- ]{2,60}?)\s+\$?([\d,]+\.\d{2})\s+(\d{1,3})%?\s*$",
    re.MULTILINE,
)
_FID_ACTIVITY_ROW = re.compile(
    r"^(\d{2}/\d{2})\s+(.+?)\s+(-?\$?[\d,]+\.\d{2})\s*(?:-|\$?[\d,]*\.?\d*)?\s*$",
    re.MULTILINE,
)
_FID_NON_HOLDING_LABELS = re.compile(
    r"^(Total|Beginning|Ending|Change|Subtractions|Withdrawals|Exchanges|Transaction|"
    r"Net|Return|Realized|Accrued|Taxable|Dividends|Income)\b",
    re.IGNORECASE,
)


def parse_fidelity(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return the pinned donor's best-effort Fidelity summary and raw rows."""
    summary: dict[str, Any] = {}
    match = re.search(r"Account\s*(?:Number)?:?\s*#?\s*(\d{3}-\d{6})", text)
    summary["account_number"] = match.group(1) if match else None
    match = re.search(r"([A-Za-z]+ \d{1,2}, \d{4})\s*-\s*([A-Za-z]+ \d{1,2}, \d{4})", text)
    if match:
        try:
            end = datetime.strptime(match.group(2), "%B %d, %Y")
            summary["period"] = end.strftime("%Y-%m")
        except ValueError:
            summary["period"] = None
    match = re.search(r"Ending Account Value\s+\$([\d,.]+)(?!\s*Incl)", text)
    summary["ending_account_value"] = _num(match.group(1)) if match else None
    match = re.search(r"Total Holdings\s+\$([\d,.]+)", text)
    summary["total_holdings"] = _num(match.group(1)) if match else None

    items: list[dict[str, Any]] = []
    seen_desc: set[tuple[str, str]] = set()
    for description, value, percent in _FID_HOLDING_ROW.findall(text):
        description = description.strip()
        if _FID_NON_HOLDING_LABELS.match(description) or description.lower() in (
            "percent of", "description"
        ):
            continue
        key = (description, value)
        if key in seen_desc:
            continue
        seen_desc.add(key)
        items.append({
            "row_type": "holding", "description": description, "amount": _num(value),
            "category": f"pct_of_account={percent}%", "period": summary.get("period"),
            "extraction_method": "regex:fidelity(low_confidence_2col)", "confidence": 0.55,
        })

    for line_date, description, amount in _FID_ACTIVITY_ROW.findall(text):
        description = description.strip()
        if len(description) < 4 or amount.strip() in ("-", ""):
            continue
        items.append({
            "row_type": "transaction", "line_date": line_date,
            "description": description[:120], "amount": _num(amount),
            "period": summary.get("period"),
            "extraction_method": "regex:fidelity(low_confidence_2col)", "confidence": 0.4,
        })
    return summary, items


def reconcile_fidelity(
    summary: dict[str, Any], items: list[dict[str, Any]],
) -> tuple[float, float] | None:
    """Preserve donor fallback and holdings-sum arithmetic, including zero behavior."""
    expected = summary.get("total_holdings") or summary.get("ending_account_value")
    if expected is None:
        return None
    actual = round(sum(item["amount"] for item in items
                       if item["row_type"] == "holding" and item["amount"]), 2)
    return expected, actual
