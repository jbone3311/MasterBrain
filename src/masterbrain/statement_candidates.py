"""Private, source-neutral statement candidates; no publication or financial authority.

Streetbeat syntax follows the pinned FOS-Master recipe in ADR-170. Exact decimals,
text spans and fail-closed coverage are intentional ADR-171 divergences.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from masterbrain.datacore.contracts import Digest, EvidenceRef, SourceKind
from masterbrain.statement_recipe_parity import _SB_CASH_ROW, _SB_HOLDING_ROW, _SB_TXN

MAX_TEXT_BYTES = 1_048_576
MAX_ROWS = 2_000
DONOR_COMMIT = "218d5caec2f20b9047fd3eb8e027dc671acf0c15"
TRANSFORM_VERSION = "streetbeat-candidate-1"
_PERIOD = re.compile(r"Period:\s*([A-Za-z]+)\s*-\s*(\d{4})")
_ACCOUNT = re.compile(r"Account No:\s*(\d+)")
_LONG = re.compile(r"Long\s*\$([\d,.]+)")
_TOTAL = re.compile(r"Total Market Value\s*\$([\d,.]+)")
_HOLDINGS = re.compile(
    r"Symbol\s+Description\s+Quantity.*?TD Cost Basis\n(.*?)"
    r"(?:\nTransaction\b|\nTrade Date\b|\Z)", re.S,
)
_MONTHS = {month: number for number, month in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"),
    1,
)}


class CandidateStatus(StrEnum):
    RECONCILED = "reconciled"
    MISMATCH = "mismatch"
    UNRECONCILED = "unreconciled"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class StatementRow:
    row_type: str
    description: str
    symbol: str | None
    line_date: date | None
    quantity: Decimal | None
    price: Decimal | None
    amount: Decimal
    cost_basis: Decimal | None
    unrealized: Decimal | None
    currency: str
    text_start: int
    text_end: int


@dataclass(frozen=True, slots=True)
class StatementCandidate:
    recipe: str
    donor_commit: str
    transform_version: str
    source_kind: SourceKind
    evidence: EvidenceRef
    text_digest: Digest
    account_number: str | None
    period: str | None
    rows: tuple[StatementRow, ...]
    expected: Decimal | None
    actual: Decimal | None
    delta: Decimal | None
    status: CandidateStatus
    coverage_errors: tuple[str, ...]


def _decimal(value: str) -> Decimal:
    try:
        number = Decimal(value.replace(",", "").replace("$", ""))
    except InvalidOperation as exc:
        raise ValueError("invalid_statement_number") from exc
    if not number.is_finite():
        raise ValueError("invalid_statement_number")
    return number


def _period(text: str, errors: set[str]) -> str | None:
    match = _PERIOD.search(text)
    if match is None:
        errors.add("missing_period")
        return None
    month = _MONTHS.get(match.group(1).upper()[:3])
    if month is None:
        errors.add("invalid_period")
        return None
    return f"{match.group(2)}-{month:02d}"


def _transaction_date(value: str, errors: set[str]) -> date | None:
    try:
        month, day, year = (int(part) for part in value.split("/"))
        return date(year, month, day)
    except ValueError:
        errors.add("invalid_date")
        return None


def _statement_rows(text: str, errors: set[str]) -> tuple[StatementRow, ...]:
    rows: list[StatementRow] = []
    for line in text.splitlines():
        if "Trade Entry" in line and _SB_TXN.fullmatch(line.strip()) is None:
            errors.add("unparsed_transaction_line")
    for match in _SB_TXN.finditer(text):
        transaction_date, side, symbol, quantity, price, sign, amount = match.groups()
        rows.append(StatementRow(
            row_type="transaction", description=f"{side} {symbol}", symbol=symbol,
            line_date=_transaction_date(transaction_date, errors), quantity=_decimal(quantity),
            price=_decimal(price), amount=(_decimal(amount) * (-1 if sign == "-" else 1)),
            cost_basis=None, unrealized=None, currency="USD",
            text_start=match.start(), text_end=match.end(),
        ))
    section = _HOLDINGS.search(text)
    if section is not None:
        block = section.group(1)
        offset = section.start(1)
        for line in block.splitlines(keepends=True):
            line_text = line.rstrip("\r\n")
            line_offset = offset
            offset += len(line)
            if not line_text.strip():
                continue
            holding = _SB_HOLDING_ROW.fullmatch(line_text)
            if holding is not None:
                (symbol, description, quantity, price, amount,
                 _cost_price, unrealized, cost_basis) = holding.groups()
                rows.append(StatementRow(
                    row_type="holding", description=description.strip(), symbol=symbol,
                    line_date=None, quantity=_decimal(quantity), price=_decimal(price),
                    amount=_decimal(amount), cost_basis=_decimal(cost_basis),
                    unrealized=_decimal(unrealized), currency="USD",
                    text_start=line_offset, text_end=line_offset + len(line_text),
                ))
                continue
            cash = _SB_CASH_ROW.fullmatch(line_text)
            if cash is not None and cash.group(2):
                rows.append(StatementRow(
                    row_type="holding", description="*Cash", symbol="CASH", line_date=None,
                    quantity=None, price=None, amount=_decimal(cash.group(2)),
                    cost_basis=None, unrealized=None, currency="USD",
                    text_start=line_offset, text_end=line_offset + len(line_text),
                ))
                continue
            errors.add("unparsed_holding_line")
    if not rows:
        errors.add("no_rows")
    if len(rows) > MAX_ROWS:
        raise ValueError("statement_row_limit")
    return tuple(rows)


def project_streetbeat_candidate(
    text: str, *, source_kind: SourceKind, evidence: EvidenceRef, text_digest: Digest,
) -> StatementCandidate:
    """Build a nonpublishing proposal from bounded, hash-bound extracted text."""
    if not isinstance(source_kind, SourceKind) or not isinstance(evidence, EvidenceRef):
        raise ValueError("invalid_statement_source")
    if not isinstance(text_digest, Digest):
        raise ValueError("invalid_statement_text_digest")
    try:
        raw = text.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError("invalid_statement_text") from exc
    if len(raw) > MAX_TEXT_BYTES:
        raise ValueError("statement_text_limit")
    if hashlib.sha256(raw).hexdigest() != text_digest.value:
        raise ValueError("statement_text_digest_mismatch")

    errors: set[str] = set()
    period = _period(text, errors)
    account = _ACCOUNT.search(text)
    if account is None:
        errors.add("missing_account")
    rows = _statement_rows(text, errors)
    expected_match = _LONG.search(text) or _TOTAL.search(text)
    expected = _decimal(expected_match.group(1)) if expected_match else None
    holdings = [row.amount for row in rows if row.row_type == "holding"]
    actual = sum(holdings, Decimal("0")) if holdings else None
    delta = abs(expected - actual) if expected is not None and actual is not None else None

    if errors:
        status = CandidateStatus.INCOMPLETE
    elif expected is None or actual is None:
        status = CandidateStatus.UNRECONCILED
    else:
        tolerance = max(abs(expected) * Decimal("0.02"), Decimal("1.00"))
        status = (
            CandidateStatus.RECONCILED
            if delta is not None and delta <= tolerance else CandidateStatus.MISMATCH
        )
    return StatementCandidate(
        recipe="streetbeat", donor_commit=DONOR_COMMIT,
        transform_version=TRANSFORM_VERSION, source_kind=source_kind, evidence=evidence,
        text_digest=text_digest, account_number=account.group(1) if account else None,
        period=period, rows=rows, expected=expected, actual=actual, delta=delta,
        status=status, coverage_errors=tuple(sorted(errors)),
    )
