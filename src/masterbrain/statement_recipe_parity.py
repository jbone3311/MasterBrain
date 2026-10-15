"""Isolated donor statement recipe candidates; not runtime or financial-truth APIs.

Extracted from FOS-Master at 218d5caec2f20b9047fd3eb8e027dc671acf0c15,
_SYSTEM/tools/statement_extract.py
(SHA-256 f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe).
The parsing and reconciliation semantics are intentionally unchanged. See
ADR-170, ADR-174, ADR-180, ADR-181, ADR-187, ADR-191, ADR-198 and ADR-199.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, cast


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


# Wells Fargo savings is a deposit-account recipe, not a securities holding
# parser. Preserve donor balance-delta direction and low-confidence fallbacks.
_WFS_TXN_SECTION = re.compile(
    r"Transaction\s+(?:history|hi\s*story).*?\n(.*?)(?:\nThe Ending Daily Balance|\Z)", re.S
)
_WFS_TXN_ROW = re.compile(
    r"^(\d{1,2}/\d{1,2})\s+(.+?)\s+([\d,]+\.\d{2})(?:\s+([\d,]+\.\d{2}))?\s*$",
    re.MULTILINE,
)


def _wf_sign_keyword(desc: str) -> int | None:
    """Donor tie-breaker only; wording alone never establishes direction."""
    if re.search(r"\bCredit\b", desc, re.I):
        return 1
    if re.search(r"\bDebit\b", desc, re.I):
        return -1
    if "/Org=" in desc:
        return 1
    if "/Bnf=" in desc:
        return -1
    if re.search(r"Reversal of.*Charge", desc, re.I):
        return 1
    if re.search(r"Wire Trans.*Svc Charge|Service Charge", desc, re.I):
        return -1
    if re.search(r"Interest Rebate", desc, re.I):
        return 1
    if re.search(r"Interest Payment", desc, re.I) and not re.search(
        r"Obligation#|Customer#", desc
    ):
        return 1
    if re.search(r"(Interest|Principal) Payment.*(Obligation#|Customer#)", desc, re.I):
        return -1
    if re.search(r"Transfer to\b", desc, re.I):
        return -1
    if re.search(r"Transfer From\b", desc, re.I) and "Into" not in desc:
        return 1
    if "Into" in desc:
        return -1
    return None


def _wf_resolve_group(
    group: list[tuple[str, str, str, str]], running_balance: float,
) -> tuple[list[tuple[str, str, float, float]], float]:
    amounts = [cast(float, _num(a)) for (_, _, a, _) in group]
    bal_str = group[-1][3]
    if not bal_str:
        return (
            [
                (d, desc, (_wf_sign_keyword(desc) or 1) * a, 0.2)
                for (d, desc, _, _), a in zip(group, amounts, strict=True)
            ],
            running_balance,
        )

    new_balance = cast(float, _num(bal_str))
    delta = round(new_balance - running_balance, 2)
    if len(group) == 1:
        sign = 1 if delta >= 0 else -1
        conf = 0.9 if abs(abs(delta) - amounts[0]) < 0.01 else 0.5
        return ([(group[0][0], group[0][1], sign * amounts[0], conf)], new_balance)

    total = round(sum(amounts), 2)
    if abs(total - delta) < 0.01:
        return (
            [(d, desc, a, 0.8) for (d, desc, _, _), a in zip(group, amounts, strict=True)],
            new_balance,
        )
    if abs(-total - delta) < 0.01:
        return (
            [(d, desc, -a, 0.8) for (d, desc, _, _), a in zip(group, amounts, strict=True)],
            new_balance,
        )

    signs = [_wf_sign_keyword(desc) for (_, desc, _, _) in group]
    known_sum = sum(s * a for s, a in zip(signs, amounts, strict=True) if s is not None)
    unresolved = [k for k, s in enumerate(signs) if s is None]
    if len(unresolved) == 1:
        residual = round(delta - known_sum, 2)
        signs[unresolved[0]] = 1 if residual >= 0 else -1
        fallback_conf = {unresolved[0]: 0.65}
    elif 2 <= len(unresolved) <= 12:
        target = round(delta - known_sum, 2)
        solutions = []
        for bits in range(1 << len(unresolved)):
            trial = [1 if (bits >> b) & 1 else -1 for b in range(len(unresolved))]
            trial_sum = sum(t * amounts[k] for t, k in zip(trial, unresolved, strict=True))
            if abs(trial_sum - target) < 0.01:
                solutions.append(trial)
        fallback_conf = {}
        if len(solutions) == 1:
            for k, t in zip(unresolved, solutions[0], strict=True):
                signs[k] = t
                fallback_conf[k] = 0.5
        else:
            for k in unresolved:
                signs[k] = 1
                fallback_conf[k] = 0.2 if not solutions else 0.3
    else:
        fallback_conf = {}
        for k in unresolved:
            signs[k] = 1
            fallback_conf[k] = 0.15
    out = [
        (
            d, desc, cast(int, s) * a,
            0.85 if _wf_sign_keyword(desc) is not None else fallback_conf.get(k, 0.65),
        )
        for k, ((d, desc, _, _), s, a) in enumerate(zip(group, signs, amounts, strict=True))
    ]
    return out, new_balance


def parse_wells_fargo_savings(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return pinned donor savings summary and unsigned-row resolution."""
    summary: dict[str, Any] = {}
    match = re.search(r"Account number:\s*(\d+)", text)
    summary["account_number"] = match.group(1) if match else None
    match = re.search(
        r"Fee period\s+(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{2})/(\d{2})/(\d{4})",
        text,
    )
    summary["period"] = f"{match.group(6)}-{match.group(4)}" if match else None
    for field, pattern in (
        ("beginning_balance", r"Beginning balance on \d{1,2}/\d{1,2}\s+\$([\d,.]+)"),
        ("ending_balance", r"Ending balance on \d{1,2}/\d{1,2}\s+\$([\d,.]+)"),
        ("deposits_total", r"Deposits/Credits\s+([\d,.]+)"),
        ("withdrawals_total", r"Withdrawals/Debits\s*-?\s*([\d,.]+)"),
        ("interest_paid", r"Interest paid this statement\s*\$([\d,.]+)"),
    ):
        match = re.search(pattern, text)
        summary[field] = _num(match.group(1)) if match else None

    items: list[dict[str, Any]] = []
    section = _WFS_TXN_SECTION.search(text)
    if section and summary["beginning_balance"] is not None:
        rows = _WFS_TXN_ROW.findall(section.group(1))
        running = summary["beginning_balance"]
        i = 0
        while i < len(rows):
            j = i
            while j < len(rows) and rows[j][0] == rows[i][0]:
                j += 1
            group = rows[i:j]
            resolved, running = _wf_resolve_group(group, running)
            for line_date, desc, signed_amt, confidence in resolved:
                items.append({
                    "row_type": "transaction", "line_date": line_date,
                    "description": desc.strip()[:200], "amount": signed_amt,
                    "category": "deposit" if signed_amt >= 0 else "withdrawal",
                    "account_number": summary["account_number"], "period": summary["period"],
                    "currency": "USD", "confidence": confidence,
                    "extraction_method": "regex:wells_fargo_savings",
                })
            i = j
    return summary, items


def reconcile_wells_fargo_savings(
    summary: dict[str, Any], items: list[dict[str, Any]],
) -> tuple[float, float] | None:
    """Preserve donor ending-minus-beginning and transaction-sum comparison."""
    beginning, ending = summary.get("beginning_balance"), summary.get("ending_balance")
    if beginning is None or ending is None:
        return None
    expected = round(ending - beginning, 2)
    actual = round(sum(
        item["amount"] for item in items
        if item["row_type"] == "transaction" and item["amount"] is not None
    ), 2)
    return expected, actual


# Pinned donor Wells Fargo brokerage recipe, retained as a pure comparison
# baseline. Do not route its raw float rows into reviewed investment claims.
_WFB_MONTHS = {month: f"{i:02d}" for i, month in enumerate(
    ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
     "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"], 1,
)}
_WFB_ACCOUNT_NO = re.compile(r"ACCOUNT\s*NUMBER:\s*(\d{4}-\d{4})")
_WFB_PERIOD_CLEAN = re.compile(
    r"Current period ending\s+([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})"
)
_WFB_PERIOD_HEADER = re.compile(
    r"([A-Z]{3,9})\s*(\d{1,2}),\s*(\d{4})\s*-\s*[A-Z]{3,9}\s*\d{1,2},\s*(\d{4})"
)
_WFB_CLOSING_VALUE = re.compile(r"Closing\s*value\s*\$([\d,.]+)")
_WFB_ASSET_VALUE = re.compile(r"Asset\s*value\s*\$[\d,.]+\s*100%\s*\$([\d,.]+)")
_WFB_CASH_ROW = re.compile(
    r"Total\s*Cash\s*and\s*Sweep\s*Balances\s*\$([\d,.]+)", re.IGNORECASE,
)
_WFB_HOLDING_TOTAL_ROW = re.compile(
    r"^Total[ \t]+([\d,]+\.?\d*)[ \t]+\$?([\d,.]+)[ \t]*\$([\d,.]+)"
    r"[ \t]+([\d,.]+)[ \t]*\$([\d,.]+)[ \t]*"
    r"(-?\$[\d,.]+)[ \t]*(?:\$?([\d,]+)|N/A)[ \t]+(?:([\d.]+)|N/A)[ \t]*$",
    re.MULTILINE,
)
_WFB_ACQUIRED_SINGLE_LOT_ROW = re.compile(
    r"^Acquired\d{2}/\d{2}/\d{2}(?:nc)?[ \t]+([\d,]+\.?\d*)"
    r"[ \t]+([\d,.]+)[ \t]+([\d,.]+)[ \t]+([\d,.]+)[ \t]+"
    r"\$?([\d,.]+)[ \t]+(-?[\d,.]+)[^\n]*\n(?!Reinvestments)", re.MULTILINE,
)
_WFB_HOLDING_SINGLELINE_ROW = re.compile(
    r"^([A-Z][A-Z0-9&,./\- ]{2,40}?)[ \t]+([\d,]+\.?\d*)"
    r"[ \t]+([\d.]+)\*\*[ \t]+([\d,.]+)[ \t]+([\d,.]+)[ \t]+"
    r"\$?([\d,.]+)[ \t]+(-?[\d,.]+)[ \t]+(?:\$?([\d,]+)|N/A)[ \t]+(?:([\d.]+)|N/A)[ \t]*$",
    re.MULTILINE,
)
_WFB_TICKER_LINE = re.compile(r"^([A-Z][A-Z0-9\-]{0,9})\s*$", re.MULTILINE)
_WFB_NAME_LINE = re.compile(r"^([A-Z][A-Z0-9&,./\- ]{2,40})\s*$", re.MULTILINE)
_WFB_LOT_LINE = re.compile(r"^(?:Acquired\d|Reinvestments)")
_WFB_TXN_ROW = re.compile(
    r"^(\d{2}/\d{2})[ \t]+Cash[ \t]+([A-Z][A-Z/]*)[ \t]+(.+?)[ \t]+"
    r"(-?[\d,]+\.\d{2})(?:[ \t]+[\d,]+\.\d{2})?[ \t]*$",
    re.MULTILINE,
)


def _wfb_lookback_symbol(text: str, match_start: int, window: int = 220) -> str | None:
    chunk = text[max(0, match_start - window):match_start]
    symbols = _WFB_TICKER_LINE.findall(chunk)
    return symbols[-1] if symbols else None


def _wfb_lookback_name(
    text: str, match_start: int, window: int = 260, max_lines: int = 5,
) -> str | None:
    """Preserve donor's bounded, best-effort wrapped security-name lookback."""
    chunk = text[max(0, match_start - window):match_start]
    lines = [line.strip() for line in chunk.splitlines() if line.strip()]
    while lines and _WFB_LOT_LINE.match(lines[-1]):
        lines.pop()
    name_lines: list[str] = []
    for line in reversed(lines):
        if _WFB_NAME_LINE.match(line):
            name_lines.insert(0, line)
            if len(name_lines) >= max_lines:
                break
        else:
            break
    return " ".join(name_lines) if name_lines else None


def parse_wells_fargo_brokerage(
    text: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return ordered pinned-donor brokerage rows without publication."""
    summary: dict[str, Any] = {}
    match = _WFB_ACCOUNT_NO.search(text)
    summary["account_number"] = match.group(1) if match else None

    match = _WFB_PERIOD_CLEAN.search(text)
    if match:
        month = match.group(1).upper()
        summary["period"] = (
            f"{match.group(3)}-{_WFB_MONTHS.get(month, month[:3])}"
            if month in _WFB_MONTHS else None
        )
    else:
        match = _WFB_PERIOD_HEADER.search(text)
        summary["period"] = (
            f"{match.group(4)}-{_WFB_MONTHS[match.group(1)]}"
            if match and match.group(1) in _WFB_MONTHS else None
        )

    match = _WFB_CLOSING_VALUE.search(text)
    summary["closing_value"] = _num(match.group(1)) if match else None
    match = _WFB_ASSET_VALUE.search(text)
    summary["asset_value"] = _num(match.group(1)) if match else None
    items: list[dict[str, Any]] = []

    match = _WFB_CASH_ROW.search(text)
    if match:
        items.append({
            "row_type": "holding", "symbol": "CASH",
            "description": "Cash and Sweep Balances", "amount": _num(match.group(1)),
            "account_number": summary["account_number"], "period": summary["period"],
            "extraction_method": "regex:wells_fargo_brokerage",
        })

    total_matches = list(_WFB_HOLDING_TOTAL_ROW.finditer(text))
    for row in total_matches:
        qty, origprice, origcost, curprice, mktval, gain, income, yld = row.groups()
        symbol = _wfb_lookback_symbol(text, row.start())
        items.append({
            "row_type": "holding", "symbol": symbol,
            "description": _wfb_lookback_name(text, row.start()) or symbol,
            "quantity": _num(qty), "price": _num(curprice), "amount": _num(mktval),
            "category": f"orig_cost={_num(origcost)};gain_loss={_num(gain)};yield_pct={_num(yld)}",
            "account_number": summary["account_number"], "period": summary["period"],
            "extraction_method": "regex:wells_fargo_brokerage", "confidence": 0.75,
        })

    acquired_matches = list(_WFB_ACQUIRED_SINGLE_LOT_ROW.finditer(text))
    acquired_starts = [
        row.start() for row in re.finditer(r"^Acquired\d{2}/\d{2}/\d{2}", text, re.MULTILINE)
    ]
    for row in acquired_matches:
        window_end = row.end() + 600
        next_acquired = next((position for position in acquired_starts
                              if position > row.end()), None)
        boundary = min(window_end, next_acquired) if next_acquired else window_end
        if any(row.end() < total.start() < boundary for total in total_matches):
            continue
        qty, origprice, origcost, curprice, mktval, gain = row.groups()
        symbol = _wfb_lookback_symbol(text, row.start())
        items.append({
            "row_type": "holding", "symbol": symbol,
            "description": _wfb_lookback_name(text, row.start()) or symbol,
            "quantity": _num(qty), "price": _num(curprice), "amount": _num(mktval),
            "category": f"orig_cost={_num(origcost)};gain_loss={_num(gain)}",
            "account_number": summary["account_number"], "period": summary["period"],
            "extraction_method": "regex:wells_fargo_brokerage", "confidence": 0.65,
        })

    for row in _WFB_HOLDING_SINGLELINE_ROW.finditer(text):
        name, qty, avgprice, origcost, curprice, mktval, gain, income, yld = row.groups()
        ticker = _WFB_TICKER_LINE.search(text[row.end():row.end() + 30])
        symbol = ticker.group(1) if ticker else None
        items.append({
            "row_type": "holding", "symbol": symbol or name.strip(),
            "description": name.strip(), "quantity": _num(qty),
            "price": _num(curprice), "amount": _num(mktval),
            "category": (
                f"orig_cost={_num(origcost)};gain_loss={_num(gain)};"
                "avg_cost_gt_6_lots=true"
            ),
            "account_number": summary["account_number"], "period": summary["period"],
            "extraction_method": "regex:wells_fargo_brokerage", "confidence": 0.7,
        })

    for date, txn_type, desc, amt in _WFB_TXN_ROW.findall(text):
        desc = desc.strip()
        if len(desc) < 2:
            continue
        items.append({
            "row_type": "transaction", "line_date": date,
            "description": f"{txn_type} {desc}"[:120], "amount": _num(amt),
            "account_number": summary["account_number"], "period": summary["period"],
            "extraction_method": "regex:wells_fargo_brokerage", "confidence": 0.6,
        })
    return summary, items


def reconcile_wells_fargo_brokerage(
    summary: dict[str, Any], items: list[dict[str, Any]],
) -> tuple[float, float] | None:
    """Preserve donor's closing-or-asset fallback and holding sum."""
    expected = summary.get("closing_value") or summary.get("asset_value")
    if expected is None:
        return None
    actual = round(sum(item["amount"] for item in items
                       if item["row_type"] == "holding" and item["amount"]), 2)
    return expected, actual


# ADR-199: exact donor Wells Fargo Priority Credit Line text-recipe comparison.
# This is supplied-text parity, not source-PDF derivation or a verified debt.
_WFLOC_MONTHS = {month: f"{i:02d}" for i, month in enumerate(
    ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
     "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"], 1,
)}
_WFLOC_ACCOUNT = re.compile(r"ACCOUNT\s*NUMBER:?\s*(\d{4}-\d{4})", re.IGNORECASE)
_WFLOC_PERIOD = re.compile(
    r"([A-Za-z]+)\s*\d{1,2},\s*\d{4}\s*-\s*([A-Za-z]+)\s*(\d{1,2}),\s*(\d{4})"
)
_WFLOC_ACT_BEGIN_BAL = re.compile(
    r"\d{2}/\d{2}\s*BEGINNING\s*BALANCE\s*(-?[\d,]+\.\d{2})", re.IGNORECASE
)
_WFLOC_BEGIN_LOAN_BAL = re.compile(
    r"Beginning\s*loan\s*balance\s*(-?[\d,]+\.\d{2})", re.IGNORECASE
)
_WFLOC_END_LOAN_BAL = re.compile(
    r"Ending\s*loan\s*balance\s*(-?[\d,]+\.\d{2})", re.IGNORECASE
)
_WFLOC_AVAIL_CREDIT = re.compile(
    r"Available\s*credit\s*\*?\s*([\d,]+\.\d{2})", re.IGNORECASE
)
_WFLOC_ADDL_BORROW = re.compile(
    r"Plus\s*additional\s*borrowing\s*([\d,]+\.\d{2})", re.IGNORECASE
)
_WFLOC_FINANCE_CHG = re.compile(
    r"Plus\s*finance\s*charges\s*([\d,]+\.\d{2})", re.IGNORECASE
)
_WFLOC_REPAYMENTS = re.compile(
    r"Less\s*repayments\s*(-?[\d,]+\.\d{2})", re.IGNORECASE
)
_WFLOC_ACTIVITY_SECTION = re.compile(
    r"Activity\s*detail.*?"
    r"DATE\s*TRANSACTION\s*QUANTITY\s*DESCRIPTION\s*PRICE\s*AMOUNT\s*BALANCES\s*"
    r"(.*?)"
    r"(?:Bank\s*Deposits\s*Through\s*Teller|Statement\s*of\s*interest\s*charged|"
    r"Specific\s*instructions\s*and\s*disclosures|\Z)",
    re.S | re.IGNORECASE,
)
_WFLOC_TXN_ROW = re.compile(
    r"^(\d{2}/\d{2})\s+([A-Z]+)\s+(.+?)\s+(-?[\d,]+\.\d{2})"
    r"\s*(?:-?[\d,]+\.\d{2})?\s*$",
    re.MULTILINE,
)
_WFLOC2_BEGIN_LOAN = re.compile(r"Beginning loan balance\s*\n?\s*([\d,]+\.\d{2})")
_WFLOC2_AVAIL_SCOPE = re.compile(
    r"Available credit\s*\*?(.*?)(?:Your Priority Credit Line|Loan history|\Z)", re.S
)
_WFLOC2_FIRST_AMOUNT = re.compile(r"(-?[\d,]+\.\d{2})")
_WFLOC2_ROW_ANCHOR = re.compile(r"^([A-Z][A-Z ]{2,30}[A-Z])\s*$", re.MULTILINE)
_WFLOC2_ROW_DATE = re.compile(r"^(\d{2}/\d{2})\s*$", re.MULTILINE)


def _wfloc2_row_amount(chunk: str, after_idx: int) -> float | None:
    match = _WFLOC2_FIRST_AMOUNT.search(chunk, after_idx)
    return _num(match.group(1)) if match else None


def _wfloc_summary_ending_balance(text: str) -> float | None:
    match = _WFLOC2_BEGIN_LOAN.search(text)
    if not match:
        return None
    total = _num(match.group(1))
    assert total is not None
    for pattern in (_WFLOC_ADDL_BORROW, _WFLOC_FINANCE_CHG, _WFLOC_REPAYMENTS):
        part_match = pattern.search(text)
        if part_match:
            part = _num(part_match.group(1))
            assert part is not None
            total += part
    return round(total, 2)


def _parse_wells_fargo_loc_pymupdf(
    text: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary: dict[str, Any] = {"beginning_balance": None}
    ending_unsigned = _wfloc_summary_ending_balance(text)
    summary["ending_loan_balance_unsigned"] = ending_unsigned
    summary["ending_balance"] = -ending_unsigned if ending_unsigned is not None else None

    match = _WFLOC2_AVAIL_SCOPE.search(text)
    if match:
        amount_match = _WFLOC2_FIRST_AMOUNT.search(match.group(1))
        summary["available_credit"] = _num(amount_match.group(1)) if amount_match else None
    else:
        summary["available_credit"] = None

    items: list[dict[str, Any]] = []
    section = re.search(
        r"CASH AND SWEEP(.*?)(?:Bank Deposits Through Teller|"
        r"Statement of interest charged|\Z)", text, re.S,
    )
    block = section.group(1) if section else ""
    anchors = list(_WFLOC2_ROW_ANCHOR.finditer(block))
    for index, anchor in enumerate(anchors):
        row_type = anchor.group(1).strip()
        chunk_end = anchors[index + 1].start() if index + 1 < len(anchors) else len(block)
        chunk = block[anchor.end():chunk_end]
        date_match = _WFLOC2_ROW_DATE.search(chunk)
        if not date_match:
            continue
        amount = _wfloc2_row_amount(chunk, date_match.end())
        if amount is None:
            continue
        if row_type == "BEGINNING BALANCE":
            if summary["beginning_balance"] is None:
                summary["beginning_balance"] = amount
            continue
        description = chunk[:date_match.start()].strip().replace("\n", " ")
        category = "interest" if ("INT" in row_type and "CHARG" in row_type) else (
            "draw" if amount < 0 else "payment" if amount > 0 else "other"
        )
        items.append({
            "row_type": "transaction", "line_date": date_match.group(1),
            "description": f"{row_type} {description}"[:120] if description else row_type,
            "amount": amount, "category": category,
            "extraction_method": "regex:wells_fargo_loc(pymupdf_fallback)", "confidence": 0.7,
        })
    return summary, items


def parse_wells_fargo_loc(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return donor loan summary and ordered rows for supplied fictional text only."""
    summary: dict[str, Any] = {}
    match = _WFLOC_ACCOUNT.search(text)
    summary["account_number"] = match.group(1) if match else None

    match = _WFLOC_PERIOD.search(text)
    if match:
        ending_month, ending_year = match.group(2).upper(), match.group(4)
        summary["period"] = f"{ending_year}-{_WFLOC_MONTHS.get(ending_month, '??')}"
    else:
        summary["period"] = None

    match = _WFLOC_ACT_BEGIN_BAL.search(text)
    summary["beginning_balance"] = _num(match.group(1)) if match else None

    match = _WFLOC_END_LOAN_BAL.search(text)
    ending_unsigned = _num(match.group(1)) if match else None
    summary["ending_balance"] = -ending_unsigned if ending_unsigned is not None else None
    summary["ending_loan_balance_unsigned"] = ending_unsigned

    match = _WFLOC_BEGIN_LOAN_BAL.search(text)
    summary["beginning_loan_balance_unsigned"] = _num(match.group(1)) if match else None

    match = _WFLOC_AVAIL_CREDIT.search(text)
    summary["available_credit"] = _num(match.group(1)) if match else None

    match = _WFLOC_ADDL_BORROW.search(text)
    summary["additional_borrowing_period"] = _num(match.group(1)) if match else None

    match = _WFLOC_FINANCE_CHG.search(text)
    summary["finance_charges_period"] = _num(match.group(1)) if match else None

    items: list[dict[str, Any]] = []
    section = _WFLOC_ACTIVITY_SECTION.search(text)
    block = section.group(1) if section else text
    for date, code, description, raw_amount in _WFLOC_TXN_ROW.findall(block):
        amount = _num(raw_amount)
        combined = f"{code} {description.strip()}".strip()
        if "INT" in code and "CHARG" in combined.upper():
            category = "interest"
        elif amount is not None and amount < 0:
            category = "draw"
        elif amount is not None and amount > 0:
            category = "payment"
        else:
            category = "other"
        items.append({
            "row_type": "transaction", "line_date": date, "description": combined[:120],
            "amount": amount, "category": category, "period": summary.get("period"),
            "extraction_method": "regex:wells_fargo_loc",
        })

    if summary["beginning_balance"] is None:
        fallback_summary, fallback_items = _parse_wells_fargo_loc_pymupdf(text)
        for key, value in fallback_summary.items():
            if summary.get(key) is None and value is not None:
                summary[key] = value
        if not items:
            for item in fallback_items:
                item["period"] = summary.get("period")
            items = fallback_items

    return summary, items


def reconcile_wells_fargo_loc(
    summary: dict[str, Any], items: list[dict[str, Any]],
) -> tuple[float, float] | None:
    """Preserve the donor's debt-negative activity reconciliation."""
    beginning, ending = summary.get("beginning_balance"), summary.get("ending_balance")
    if beginning is None or ending is None:
        return None
    expected = round(ending - beginning, 2)
    actual = round(sum(item["amount"] for item in items if item["amount"] is not None), 2)
    return expected, actual
