"""Isolated donor statement recipe candidates; not runtime or financial-truth APIs.

Extracted from FOS-Master at 218d5caec2f20b9047fd3eb8e027dc671acf0c15,
_SYSTEM/tools/statement_extract.py
(SHA-256 f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe).
The parsing and reconciliation semantics are intentionally unchanged. See
ADR-170, ADR-174, ADR-180, ADR-181 and ADR-187.
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


# OCR-only OCR bank statement recipe. Keep donor row grouping and year
# assignment exactly: an amount may be on a separate OCR line, and December
# rows in a January statement belong to the preceding year.
_JLB_BOILERPLATE = re.compile(
    r"JBL TRUST\s*Page\s*\d+\s*of\s*\d+|"
    r"[A-Za-z]+ \d{1,2},\s*\d{4}\s*X+\d+|"
    r"Date\s+Description\s+(?:Additions|Subtractions)"
)
_JLB_TXN_TYPE = re.compile(
    r"^(Online Transfer Dr|Online Transfer Cr|ACH Credit|ACH Debit|"
    r"Remote Deposit|Mobile Deposit|Check|Fee)\b", re.IGNORECASE
)


def _jlb_section(text: str, start_kw: str, end_kw: str) -> str:
    match = re.search(re.escape(start_kw) + r"\s*(.*?)" + re.escape(end_kw), text, re.S)
    return match.group(1) if match else ""


def _jlb_rows(block: str) -> list[tuple[str, str]]:
    parts = re.split(r"^(\d{2}-\d{2})[ \t]*['\"]?[ \t]*", block, flags=re.MULTILINE)
    return list(zip(parts[1::2], parts[2::2], strict=True))


def _jlb_row_date(mm_dd: str, last_dt: datetime | None, this_dt: datetime | None) -> str | None:
    mm, dd = mm_dd.split("-")
    mm_i = int(mm)
    if last_dt and mm_i == last_dt.month:
        yr = last_dt.year
    elif this_dt and mm_i == this_dt.month:
        yr = this_dt.year
    elif this_dt:
        yr = this_dt.year
    else:
        return None
    return f"{yr:04d}-{mm}-{dd}"


def parse_ocr_bank(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return the pinned donor's OCR-text bank summary and raw debit/credit rows."""
    summary: dict[str, Any] = {}
    match = re.search(r"Account number\s*(X+\d+)", text)
    summary["account_number"] = match.group(1) if match else None
    for field, pattern in (
        ("beginning_balance", r"Beginning balance\s*\$([\d,.]+)"),
        ("total_additions", r"Total additions\s*\$?([\d,.]+)"),
        ("total_subtractions", r"Total subtractions\s*\$?([\d,.]+)"),
        ("ending_balance", r"Ending balance\s*\$([\d,.]+)"),
        ("low_balance", r"Low balance\s*\$([\d,.]+)"),
        ("average_balance", r"Average balance\s*\$([\d,.]+)"),
    ):
        match = re.search(pattern, text)
        summary[field] = _num(match.group(1)) if match else None

    last_dt = this_dt = None
    match = re.search(r"Last statement:\s*([A-Za-z]+ \d{1,2},\s*\d{4})", text)
    if match:
        try:
            last_dt = datetime.strptime(match.group(1), "%B %d, %Y")
        except ValueError:
            pass
    match = re.search(r"This statement:\s*([A-Za-z]+ \d{1,2},\s*\d{4})", text)
    if match:
        try:
            this_dt = datetime.strptime(match.group(1), "%B %d, %Y")
        except ValueError:
            pass
    summary["period"] = this_dt.strftime("%Y-%m") if this_dt else None

    items: list[dict[str, Any]] = []
    debits_block = _jlb_section(text, "DEBITS", "CREDITS")
    credits_block = _jlb_section(text, "CREDITS", "DAILY BALANCES")
    for row_type, block in (("debit", debits_block), ("credit", credits_block)):
        for mm_dd, chunk in _jlb_rows(block):
            amount_match = re.search(r"\$?([\d,]+\.\d{2})", chunk)
            if not amount_match:
                continue
            desc_raw = chunk[:amount_match.start()] + chunk[amount_match.end():]
            desc_raw = _JLB_BOILERPLATE.sub(" ", desc_raw)
            desc = re.sub(r"\s+", " ", desc_raw).strip(" '\"\n\t")
            type_match = _JLB_TXN_TYPE.match(desc)
            items.append({
                "row_type": row_type,
                "line_date": _jlb_row_date(mm_dd, last_dt, this_dt),
                "description": desc[:200],
                "amount": _num(amount_match.group(1)),
                "category": type_match.group(1) if type_match else None,
                "period": summary["period"],
                "extraction_method": "regex:ocr_bank(ocr)",
                "confidence": 0.85,
            })
    return summary, items


def reconcile_ocr_bank(
    summary: dict[str, Any], items: list[dict[str, Any]],
) -> tuple[float, float] | None:
    """Preserve the donor's opening balance plus credits minus debits check."""
    expected = summary.get("ending_balance")
    if expected is None or summary.get("beginning_balance") is None:
        return None
    credits = sum(it["amount"] for it in items if it["row_type"] == "credit" and it["amount"])
    debits = sum(it["amount"] for it in items if it["row_type"] == "debit" and it["amount"])
    actual = round(summary["beginning_balance"] + credits - debits, 2)
    return expected, actual


# Morgan Stanley's bank-deposit detail is a component of its cash bucket, not
# another holding to add. Preserve the donor's OCR marker, weak OCR confidence,
# date-loss limitation and reconciliation exclusion in this comparison only.
_MS_MONTHS = {month: f"{i:02d}" for i, month in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], 1
)}
_MS_ACCOUNT = re.compile(r"Account\s+(?:Summary|Detail)\s+(\d{3})\s*-\s*(\d{6})\s*-\s*(\d{3})\b")
_MS_PERIOD = re.compile(r"Period\s+([A-Za-z]+)\s+\d{1,2}\s*-\s*\d{1,2}\s*,\s*(\d{4})")
_MS_TOTAL_ENDING = re.compile(r"TOTAL ENDING VALUE\s+\$?([\d,]+\.\d{2})")
_MS_TOTAL_COVER = re.compile(
    r"TOTAL VALUE OF YOUR ACCOUNTS\s*[\{\(]as of \d{1,2}/\d{1,2}/\d{2,4}[\)\}]\s*\$?([\d,]+\.\d{2})"
)
_MS_CASH_BUCKET = re.compile(
    r"CASH,?\s*B[DO]P,?\s*AND\s*M[MZE]Fs?\s+[\d.]+%\.?\s+\$?([\d,]+\.\d{2})"
)
_MS_BANK_DEPOSIT = re.compile(r"MORGAN STANLEY BANK N\.?A\.?\s*#+\s*\$?([\d,]+\.\d{2})")
_MS_ACTIVITY_ROW = re.compile(
    r"^(\d{1,2}/\d{1,2})(?:\s+\d{1,2}/\d{1,2})?\s+(.+?)\s+(\(?-?\$?[\d,]+\.\d{2}\)?)\s*$",
    re.MULTILINE,
)


def _ms_num(value: object) -> float | None:
    if value is None:
        return None
    value = str(value).strip()
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1]
    parsed = _num(value)
    return None if parsed is None else (-parsed if negative else parsed)


def parse_morgan_stanley(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return the pinned donor's OCR-sensitive summary and raw rows."""
    is_ocr = "--- OCR ---" in text
    method = "regex:morgan_stanley(ocr)" if is_ocr else "regex:morgan_stanley"

    summary: dict[str, Any] = {}
    match = _MS_ACCOUNT.search(text)
    summary["account_number"] = (
        f"{match.group(1)}-{match.group(2)}-{match.group(3)}" if match else None
    )
    match = _MS_PERIOD.search(text)
    summary["period"] = (
        f"{match.group(2)}-{_MS_MONTHS.get(match.group(1), '??')}" if match else None
    )
    match = _MS_TOTAL_ENDING.search(text)
    summary["total_ending_value"] = _num(match.group(1)) if match else None
    match = _MS_TOTAL_COVER.search(text)
    summary["total_value_cover"] = _num(match.group(1)) if match else None
    summary["is_ocr"] = is_ocr

    items: list[dict[str, Any]] = []
    match = _MS_CASH_BUCKET.search(text)
    if match:
        items.append({
            "row_type": "holding", "description": "CASH, BDP, AND MMFs",
            "amount": _num(match.group(1)), "category": "asset_class_summary",
            "account_number": summary["account_number"], "period": summary["period"],
            "extraction_method": method, "confidence": 0.6 if is_ocr else 0.9,
        })
    match = _MS_BANK_DEPOSIT.search(text)
    if match:
        items.append({
            "row_type": "holding", "description": "MORGAN STANLEY BANK N.A.",
            "amount": _num(match.group(1)), "category": "bank_deposit_detail",
            "account_number": summary["account_number"], "period": summary["period"],
            "extraction_method": method, "confidence": 0.6 if is_ocr else 0.9,
        })
    for line_date, description, amount in _MS_ACTIVITY_ROW.findall(text):
        description = description.strip()
        if len(description) < 4:
            continue
        items.append({
            "row_type": "transaction", "line_date": line_date,
            "description": description[:200], "amount": _ms_num(amount),
            "account_number": summary["account_number"], "period": summary["period"],
            "extraction_method": method, "confidence": 0.5 if is_ocr else 0.8,
        })
    return summary, items


def reconcile_morgan_stanley(
    summary: dict[str, Any], items: list[dict[str, Any]],
) -> tuple[float, float] | None:
    """Exclude the deposit detail from its parent cash bucket, as donor does."""
    expected = summary.get("total_ending_value") or summary.get("total_value_cover")
    if expected is None:
        return None
    actual = round(sum(
        item["amount"] for item in items
        if item["row_type"] == "holding" and item["amount"] is not None
        and item.get("category") != "bank_deposit_detail"
    ), 2)
    return expected, actual


# Jefferies category rows reconcile the statement; lower-confidence security
# details are supplemental and must never be summed with their parent category.
# Keep the pinned donor's subtotal and unavailable-value behavior unchanged.
_JEF_CATEGORY_TOTAL = re.compile(
    r"^TOTAL ([A-Z][A-Z,\- ]+?)\s+(-?\$?[\d,]+\.\d{2})\s+(-?\$?[\d,]+\.\d{2})",
    re.MULTILINE,
)
_JEF_SECTION_HEADER = re.compile(
    r"^([A-Z][A-Z,\- ]+?)\s+[\d.]+% of Portfolio\s*$"
)
_JEF_SECURITY_HEADER = re.compile(
    r"^\d*([A-Z][A-Za-z0-9&.,'/#\-\* ]{2,80}?)\s+Security Identifier:\s*(.+?)\s*$"
)
_JEF_SKIP_SUBTOTAL = re.compile(r"^Total (?:Covered|Noncovered|Unallocated)\b")
_JEF_LOT_LINE = re.compile(
    r"^(?:\d{2}/\d{2}/\d{2}\*?(?:,\d)?|Please Provide\*(?:,\d)?|Average\d?)\s+"
    r"[\d,]+\.\d+\s+(?:N/A|Please Provide|[\d,]+\.\d+)\s+"
    r"(?:N/A|Please Provide|Pending Receipt|[\d,]+\.\d+)\s+"
    r"(?:N/A|[\d,]+\.\d+)\s+\$?([\d,]+\.\d+)\s+"
)
_JEF_SECURITY_TOTAL = re.compile(
    r"^Total\s+[\d,]+\.\d+\s+(?:N/A|\$?[\d,]+\.\d+)\s+\$?([\d,]+\.\d+)"
)
_JEF_TXN = re.compile(
    r"^(\d{2}/\d{2}/\d{2})(?:\s+\d{2}/\d{2}/\d{2})?\s+(.+?)\s+(-?[\d,]+\.\d{2})\s+USD\s*$",
    re.MULTILINE,
)
_JEF_TXN_QTY_PRICE = re.compile(
    r"^(.*?)\s+(-?[\d,]+\.\d{3,4})\s+([\d,]+\.\d{2,4})$"
)


def parse_jefferies(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return pinned donor category, detail and transaction rows without publication."""
    summary: dict[str, Any] = {}
    match = re.search(r"Account Number:\s*([A-Za-z0-9\-]+)", text)
    summary["account_number"] = match.group(1) if match else None
    match = re.search(r"([A-Za-z]+ \d{1,2}, \d{4})\s*-\s*([A-Za-z]+ \d{1,2}, \d{4})", text)
    if match:
        try:
            end = datetime.strptime(match.group(2), "%B %d, %Y")
            summary["period"] = end.strftime("%Y-%m")
        except ValueError:
            summary["period"] = None
    else:
        summary["period"] = None
    match = re.search(r"ENDING ACCOUNT VALUE\s+\$([\d,.]+)", text)
    summary["ending_account_value"] = _num(match.group(1)) if match else None
    match = re.search(r"Total Portfolio Holdings\s+(-?\$?[\d,.]+)\s+(-?\$?[\d,.]+)", text)
    summary["total_portfolio_cost_basis"] = _num(match.group(1)) if match else None
    summary["total_portfolio_market_value"] = _num(match.group(2)) if match else None

    items: list[dict[str, Any]] = []
    for category, _cost_basis, market_value in _JEF_CATEGORY_TOTAL.findall(text):
        items.append({
            "row_type": "holding", "description": category.strip(),
            "category": category.strip(), "amount": _num(market_value),
            "account_number": summary["account_number"], "period": summary["period"],
            "extraction_method": "regex:jefferies_category", "confidence": 1.0,
        })

    current_name = current_symbol = current_category = None
    pending_value = None

    def _flush() -> None:
        nonlocal current_name, current_symbol, pending_value
        if current_name and pending_value is not None:
            items.append({
                "row_type": "holding_detail", "description": current_name,
                "symbol": current_symbol, "amount": pending_value,
                "category": current_category, "account_number": summary["account_number"],
                "period": summary["period"],
                "extraction_method": "regex:jefferies_security_detail",
                "confidence": 0.6,
            })
        current_name = current_symbol = None
        pending_value = None

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        section = _JEF_SECTION_HEADER.match(line)
        if section:
            current_category = section.group(1).strip()
            continue
        if _JEF_SKIP_SUBTOTAL.match(line):
            continue
        header = _JEF_SECURITY_HEADER.match(line)
        if header:
            _flush()
            current_name, current_symbol = header.group(1).strip(), header.group(2).strip()
            continue
        total = _JEF_SECURITY_TOTAL.match(line)
        if total and current_name:
            pending_value = _num(total.group(1))
            _flush()
            continue
        if line.startswith("Total ") or line.startswith("TOTAL "):
            _flush()
            continue
        lot = _JEF_LOT_LINE.match(line)
        if lot and current_name:
            pending_value = _num(lot.group(1))
    _flush()

    for line_date, description, amount in _JEF_TXN.findall(text):
        description = description.strip()
        quantity = price = None
        qty_price = _JEF_TXN_QTY_PRICE.match(description)
        if qty_price:
            description, quantity, price = (
                qty_price.group(1).strip(), _num(qty_price.group(2)),
                _num(qty_price.group(3)),
            )
        items.append({
            "row_type": "transaction", "line_date": line_date,
            "description": description[:120], "quantity": quantity, "price": price,
            "amount": _num(amount), "currency": "USD",
            "account_number": summary["account_number"], "period": summary["period"],
            "extraction_method": "regex:jefferies", "confidence": 0.85,
        })
    return summary, items


def reconcile_jefferies(
    summary: dict[str, Any], items: list[dict[str, Any]],
) -> tuple[float, float] | None:
    """Reconcile category totals only; preserve the donor's zero-value fallback."""
    expected = summary.get("total_portfolio_market_value") or summary.get(
        "ending_account_value"
    )
    if expected is None:
        return None
    actual = round(sum(
        item["amount"] for item in items
        if item["row_type"] == "holding" and item["amount"] is not None
    ), 2)
    return expected, actual
