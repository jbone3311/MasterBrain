"""Fictional Wells Fargo credit-line text goldens against pinned FOS-Master."""

from __future__ import annotations

import ast
import hashlib
import os
import re
from pathlib import Path
from typing import Any

import pytest

from masterbrain.statement_recipe_parity import (
    parse_wells_fargo_loc,
    reconcile_wells_fargo_loc,
)

DONOR_SHA256 = "f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe"
HEADER = "ACCOUNTNUMBER: 0000-1111\nAUGUST1,2024-AUGUST31,2024\n"
STANDARD = (
    HEADER
    + "Beginningloanbalance 100.00\nEndingloanbalance 80.00\n"
    + "Availablecredit* 500.00\nPlusadditionalborrowing 10.00\n"
    + "Plusfinancecharges 5.00\nLessrepayments -35.00\n"
    + "Activity detail\nDATE TRANSACTION QUANTITY DESCRIPTION PRICE AMOUNT BALANCES\n"
    + "08/01 BEGINNINGBALANCE -100.00\n"
    + "08/05 AUTOACTIVITY ACHDIRECTWITHDRAWAL 35.00\n"
    + "08/06 WIRETRANSFER WIRETOFICTIONAL -10.00 -75.00\n"
    + "08/07 INTCHARGED INTEREST08/01THRU08/07 -5.00 -80.00\n"
    + "Bank Deposits Through Teller\n"
    + "08/09 WIRETRANSFER LINKEDBANKONLY -999.00\n"
)
FALLBACK = (
    HEADER
    + "Beginning loan balance\n100.00\nPlus additional borrowing 10.00\n"
    + "Plus finance charges 5.00\nLess repayments -35.00\n"
    + "Available credit *\n500.00\nYour Priority Credit Line\n"
    + "CASH AND SWEEP\nBEGINNING BALANCE\n08/01\n-100.00\n"
    + "AUTO ACTIVITY\n08/05\n35.00\n"
    + "WIRE TRANSFER\n08/06\n-10.00\n"
    + "INT CHARGED\ninterest 08/01THRU08/07\n08/07\n-5.00\n"
    + "Bank Deposits Through Teller\nWIRE TRANSFER\n08/09\n-999.00\n"
)
CASES = {
    "standard_payment_draw_interest": (STANDARD, 3, (20.0, 20.0)),
    "standard_page_break": (
        STANDARD.replace("08/06 WIRETRANSFER", "PAGE 2 OF 3\n08/06 WIRETRANSFER"),
        3, (20.0, 20.0),
    ),
    "standard_optional_missing": (
        STANDARD.replace("Availablecredit* 500.00\n", "")
        .replace("Plusadditionalborrowing 10.00\n", ""),
        3, (20.0, 20.0),
    ),
    "overpayment_sign": (
        HEADER + "Endingloanbalance -11.47\nActivity detail\n"
        "DATE TRANSACTION QUANTITY DESCRIPTION PRICE AMOUNT BALANCES\n"
        "08/01 BEGINNINGBALANCE -10.00\n"
        "08/05 AUTOACTIVITY FICTIONALPAYMENT 21.47\n",
        1, (21.47, 21.47),
    ),
    "pymupdf_fallback": (FALLBACK, 3, (20.0, 20.0)),
    "fallback_unknown_transaction_label": (
        FALLBACK.replace("WIRE TRANSFER\n08/06", "MISCELLANEOUS ADJUSTMENT\n08/06"),
        3, (20.0, 20.0),
    ),
    "fallback_page_header_noise": (
        FALLBACK.replace("WIRE TRANSFER\n08/06", "A PARTNERSHIP\nWIRE TRANSFER\n08/06"),
        3, (20.0, 20.0),
    ),
    "fallback_missing_beginning": (
        FALLBACK.replace("BEGINNING BALANCE\n08/01\n-100.00\n", ""),
        3, None,
    ),
    "incomplete_text": (HEADER + "Boilerplate only\n", 0, None),
}
COMPLETE_SUMMARY = {
    "account_number": "0000-1111", "period": "2024-08",
    "beginning_balance": -100.0, "ending_balance": -80.0,
    "ending_loan_balance_unsigned": 80.0,
    "beginning_loan_balance_unsigned": 100.0,
    "available_credit": 500.0, "additional_borrowing_period": 10.0,
    "finance_charges_period": 5.0,
}
STANDARD_ROWS = [
    {
        "row_type": "transaction", "line_date": "08/05",
        "description": "AUTOACTIVITY ACHDIRECTWITHDRAWAL", "amount": 35.0,
        "category": "payment", "period": "2024-08",
        "extraction_method": "regex:wells_fargo_loc",
    },
    {
        "row_type": "transaction", "line_date": "08/06",
        "description": "WIRETRANSFER WIRETOFICTIONAL", "amount": -10.0,
        "category": "draw", "period": "2024-08",
        "extraction_method": "regex:wells_fargo_loc",
    },
    {
        "row_type": "transaction", "line_date": "08/07",
        "description": "INTCHARGED INTEREST08/01THRU08/07", "amount": -5.0,
        "category": "interest", "period": "2024-08",
        "extraction_method": "regex:wells_fargo_loc",
    },
]


@pytest.mark.parametrize("name", CASES)
def test_fictional_credit_line_golden(name: str) -> None:
    content, row_count, expected_reconciliation = CASES[name]
    summary, rows = parse_wells_fargo_loc(content)
    assert len(rows) == row_count
    assert reconcile_wells_fargo_loc(summary, rows) == expected_reconciliation
    assert all(row["row_type"] == "transaction" for row in rows)
    assert all("LINKEDBANKONLY" not in row["description"] for row in rows)
    assert summary["account_number"] == "0000-1111"
    assert summary["period"] == "2024-08"
    if name == "standard_payment_draw_interest":
        assert summary == COMPLETE_SUMMARY
        assert rows == STANDARD_ROWS
        assert [row["category"] for row in rows] == ["payment", "draw", "interest"]
        assert [row["amount"] for row in rows] == [35.0, -10.0, -5.0]
        assert summary["ending_loan_balance_unsigned"] == 80.0
        assert summary["available_credit"] == 500.0
    if name == "standard_optional_missing":
        assert summary["available_credit"] is None
        assert summary["additional_borrowing_period"] is None
    if name == "overpayment_sign":
        assert summary["ending_loan_balance_unsigned"] == -11.47
        assert summary["ending_balance"] == 11.47
    if name == "pymupdf_fallback":
        assert summary == COMPLETE_SUMMARY
        assert all(
            row["extraction_method"] == "regex:wells_fargo_loc(pymupdf_fallback)"
            for row in rows
        )
        assert [row["category"] for row in rows] == ["payment", "draw", "interest"]
        assert [row["line_date"] for row in rows] == ["08/05", "08/06", "08/07"]
        assert [row["amount"] for row in rows] == [35.0, -10.0, -5.0]
        assert [row["confidence"] for row in rows] == [0.7, 0.7, 0.7]
    if name == "fallback_unknown_transaction_label":
        assert rows[1]["description"] == "MISCELLANEOUS ADJUSTMENT"
        assert rows[1]["category"] == "draw"


def _pinned_donor(path: Path) -> tuple[Any, Any]:
    source = path.read_bytes()
    assert hashlib.sha256(source).hexdigest() == DONOR_SHA256
    functions = {
        "num", "_wfloc2_row_amount", "_wfloc_summary_ending_balance",
        "_parse_wells_fargo_loc_pymupdf", "_parse_wells_fargo_loc",
        "_reconcile_wells_fargo_loc",
    }
    constants = {
        "_WFLOC_MONTHS", "_WFLOC_ACCOUNT", "_WFLOC_PERIOD", "_WFLOC_ACT_BEGIN_BAL",
        "_WFLOC_BEGIN_LOAN_BAL", "_WFLOC_END_LOAN_BAL", "_WFLOC_AVAIL_CREDIT",
        "_WFLOC_ADDL_BORROW", "_WFLOC_FINANCE_CHG", "_WFLOC_REPAYMENTS",
        "_WFLOC_ACTIVITY_SECTION", "_WFLOC_TXN_ROW", "_WFLOC2_BEGIN_LOAN",
        "_WFLOC2_AVAIL_SCOPE", "_WFLOC2_FIRST_AMOUNT", "_WFLOC2_ROW_ANCHOR",
        "_WFLOC2_ROW_DATE",
    }
    nodes = []
    for node in ast.parse(source, filename=str(path)).body:
        if isinstance(node, ast.FunctionDef) and node.name in functions:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in constants for target in node.targets
        ):
            nodes.append(node)
    assert len(nodes) == len(functions) + len(constants)
    namespace: dict[str, Any] = {"re": re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["_parse_wells_fargo_loc"], namespace["_reconcile_wells_fargo_loc"]


def _stress_text() -> str:
    return (
        HEADER + "Endingloanbalance 0.00\nActivity detail\n"
        "DATE TRANSACTION QUANTITY DESCRIPTION PRICE AMOUNT BALANCES\n"
        "08/01 BEGINNINGBALANCE -1,000.00\n"
        + "".join(
            f"08/05 AUTOACTIVITY FICTIONALPAYMENT{index:04d} 1.00\n"
            for index in range(1000)
        )
        + "Bank Deposits Through Teller\n"
    )


def test_exact_hash_local_donor_replay() -> None:
    donor_path = os.environ.get("FOS_MASTER_STATEMENT_EXTRACT")
    if donor_path is None:
        pytest.skip("Set FOS_MASTER_STATEMENT_EXTRACT for pinned donor replay")
    donor_parse, donor_reconcile = _pinned_donor(Path(donor_path))
    for content in [*(case[0] for case in CASES.values()), _stress_text()]:
        donor_summary, donor_rows = donor_parse(content)
        summary, rows = parse_wells_fargo_loc(content)
        assert (summary, rows, reconcile_wells_fargo_loc(summary, rows)) == (
            donor_summary, donor_rows, donor_reconcile(donor_summary, donor_rows),
        )


def test_thousand_fictional_payments_repeatable() -> None:
    text = _stress_text()
    first = parse_wells_fargo_loc(text)
    assert first == parse_wells_fargo_loc(text)
    assert len(first[1]) == 1000
    assert reconcile_wells_fargo_loc(*first) == (1000.0, 1000.0)
