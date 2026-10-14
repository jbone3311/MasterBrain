"""Fictional goldens for six pure recipes from the pinned FOS-Master donor."""

from __future__ import annotations

import ast
import hashlib
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from masterbrain.statement_recipe_parity import (
    parse_fidelity,
    parse_jefferies,
    parse_ocr_bank,
    parse_morgan_stanley,
    parse_streetbeat,
    parse_wells_fargo_savings,
    reconcile_fidelity,
    reconcile_jefferies,
    reconcile_ocr_bank,
    reconcile_morgan_stanley,
    reconcile_streetbeat,
    reconcile_wells_fargo_savings,
)

DONOR_SHA256 = "f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe"
HEADER = "Symbol Description Quantity Market Price Market Value Cost Price Unrealized TD Cost Basis"
HOLDING = "ACME Fictional Corporation 2 $50.00 $100.00 $40.00 $20.00 $80.00"
CASES: dict[str, tuple[str, dict[str, Any], list[dict[str, Any]], tuple[float, float] | None]] = {
    "balanced": (
        "Account No: 000000\nPeriod: April - 2024\nTotal Market Value $150.00\n"
        f"Long $150.00\n{HEADER}\n{HOLDING}\n*Cash Other $ -- $ 50.00 $ --\n"
        "Transaction\n01/02/2024 Trade Entry buy ACME 2 $50.00 -$100.00",
        {"account_number": "000000", "period": "2024-04", "total_market_value": 150.0,
         "long_value": 150.0},
        [
            {"row_type": "transaction", "line_date": "01/02/2024", "symbol": "ACME",
             "quantity": 2.0, "price": 50.0, "amount": -100.0, "description": "buy ACME",
             "period": "2024-04", "extraction_method": "regex:streetbeat"},
            {"row_type": "holding", "symbol": "ACME", "description": "Fictional Corporation",
             "quantity": 2.0, "price": 50.0, "amount": 100.0,
             "category": "cost_basis=80.0;unrealized=20.0", "period": "2024-04",
             "extraction_method": "regex:streetbeat"},
            {"row_type": "holding", "symbol": "CASH", "description": "*Cash", "amount": 50.0,
             "period": "2024-04", "extraction_method": "regex:streetbeat"},
        ],
        (150.0, 150.0),
    ),
    "mismatch": (
        f"Account No: 000000\nPeriod: April - 2024\nLong $120.00\n{HEADER}\n{HOLDING}",
        {"account_number": "000000", "period": "2024-04", "total_market_value": None,
         "long_value": 120.0},
        [{"row_type": "holding", "symbol": "ACME", "description": "Fictional Corporation",
          "quantity": 2.0, "price": 50.0, "amount": 100.0,
          "category": "cost_basis=80.0;unrealized=20.0", "period": "2024-04",
          "extraction_method": "regex:streetbeat"}],
        (120.0, 100.0),
    ),
    "empty": (
        "Unrelated fictional document with no statement fields.",
        {"account_number": None, "period": None, "total_market_value": None,
         "long_value": None}, [], None,
    ),
    "unknown_month": (
        "Period: Foo - 2024\nTotal Market Value $0.00\nLong $0.00",
        {"account_number": None, "period": "2024-??", "total_market_value": 0.0,
         "long_value": 0.0}, [], (0.0, 0),
    ),
}

FIDELITY_CASES: dict[
    str, tuple[str, dict[str, Any], list[dict[str, Any]], tuple[float, float] | None]
] = {
    "balanced": (
        "Account Number: 123-456789\nApril 1, 2024 - April 30, 2024\n"
        "Ending Account Value $150.00\nTotal Holdings $150.00\n"
        "ACME Fictional Fund 100.00 67%\nCASH Fictional Reserve 50.00 33%\n"
        "04/15 Fictitious Purchase -$20.00",
        {"account_number": "123-456789", "period": "2024-04",
         "ending_account_value": 150.0, "total_holdings": 150.0},
        [
            {"row_type": "holding", "description": "ACME Fictional Fund", "amount": 100.0,
             "category": "pct_of_account=67%", "period": "2024-04",
             "extraction_method": "regex:fidelity(low_confidence_2col)", "confidence": 0.55},
            {"row_type": "holding", "description": "CASH Fictional Reserve", "amount": 50.0,
             "category": "pct_of_account=33%", "period": "2024-04",
             "extraction_method": "regex:fidelity(low_confidence_2col)", "confidence": 0.55},
            {"row_type": "transaction", "line_date": "04/15",
             "description": "Fictitious Purchase", "amount": -20.0, "period": "2024-04",
             "extraction_method": "regex:fidelity(low_confidence_2col)", "confidence": 0.4},
        ],
        (150.0, 150.0),
    ),
    "duplicate_detail": (
        "Total Holdings $100.00\nACME Fictional Fund 100.00 100%\n"
        "ACME Fictional Fund 100.00 100%",
        {"account_number": None, "ending_account_value": None, "total_holdings": 100.0},
        [{"row_type": "holding", "description": "ACME Fictional Fund", "amount": 100.0,
          "category": "pct_of_account=100%", "period": None,
          "extraction_method": "regex:fidelity(low_confidence_2col)", "confidence": 0.55}],
        (100.0, 100.0),
    ),
    "interleaved_missed_row": (
        "Total Holdings $100.00\nTransaction Costs ACME Fictional Fund 100.00 100%",
        {"account_number": None, "ending_account_value": None, "total_holdings": 100.0},
        [], (100.0, 0),
    ),
    "zero_fallback": (
        "Ending Account Value $100.00\nTotal Holdings $0.00",
        {"account_number": None, "ending_account_value": 100.0, "total_holdings": 0.0},
        [], (100.0, 0),
    ),
    "empty": (
        "Unrelated fictional text.",
        {"account_number": None, "ending_account_value": None, "total_holdings": None},
        [], None,
    ),
    "invalid_period": (
        "Foo 1, 2024 - Foo 30, 2024\nTotal Holdings $0.00",
        {"account_number": None, "period": None,
         "ending_account_value": None, "total_holdings": 0.0},
        [], None,
    ),
}

JLB_HEADER = (
    "Account number XXXXXX0000\nLast statement: December 11, 2023\n"
    "This statement: January 11, 2024\nBeginning balance $100.00\n"
    "Total additions 30.00\nTotal subtractions 20.00\n"
    "Ending balance $110.00\nLow balance $80.00\nAverage balance $95.00\n"
)
JLB_CASES: dict[str, tuple[str, list[dict[str, Any]], tuple[float, float] | None]] = {
    "year_rollover_and_wrapped_ocr_amount": (
        JLB_HEADER + "DEBITS\n12-30 ' Online Transfer Dr\n\n20.00\nREF fictional\n"
        "CREDITS\n01-02 ACH Credit $30.00\nDAILY BALANCES\n",
        [
            {"row_type": "debit", "line_date": "2023-12-30",
             "description": "Online Transfer Dr REF fictional", "amount": 20.0,
             "category": "Online Transfer Dr", "period": "2024-01",
             "extraction_method": "regex:ocr_bank(ocr)", "confidence": 0.85},
            {"row_type": "credit", "line_date": "2024-01-02",
             "description": "ACH Credit", "amount": 30.0,
             "category": "ACH Credit", "period": "2024-01",
             "extraction_method": "regex:ocr_bank(ocr)", "confidence": 0.85},
        ],
        (110.0, 110.0),
    ),
    "mismatch": (
        JLB_HEADER + "DEBITS\n12-30 Fee 25.00\nCREDITS\n01-02 Remote Deposit 30.00\n"
        "DAILY BALANCES\n",
        [
            {"row_type": "debit", "line_date": "2023-12-30", "description": "Fee",
             "amount": 25.0, "category": "Fee", "period": "2024-01",
             "extraction_method": "regex:ocr_bank(ocr)", "confidence": 0.85},
            {"row_type": "credit", "line_date": "2024-01-02",
             "description": "Remote Deposit", "amount": 30.0,
             "category": "Remote Deposit", "period": "2024-01",
             "extraction_method": "regex:ocr_bank(ocr)", "confidence": 0.85},
        ],
        (110.0, 105.0),
    ),
    "empty": ("Unrelated fictional document.", [], None),
    "invalid_dates": (
        "Beginning balance $100.00\nEnding balance $100.00\n"
        "Last statement: Foo 1, 2024\nThis statement: Foo 30, 2024\n"
        "DEBITS\n01-02 Imaginary Debit $5.00\nCREDITS\nDAILY BALANCES\n",
        [{"row_type": "debit", "line_date": None, "description": "Imaginary Debit",
          "amount": 5.0, "category": None, "period": None,
          "extraction_method": "regex:ocr_bank(ocr)", "confidence": 0.85}],
        (100.0, 95.0),
    ),
}

MS_CASES: dict[
    str, tuple[str, dict[str, Any], list[dict[str, Any]], tuple[float, float] | None]
] = {
    "cash_detail_not_double_counted": (
        "Account Summary 123-456789-000\nPeriod April 1-30, 2024\n"
        "TOTAL ENDING VALUE $100.00\nCASH, BDP, AND MMFs 100.00% $100.00\n"
        "MORGAN STANLEY BANK N.A. # $25.00\n"
        "04/15 Dividend Fictional Fund $10.00\n"
        "04/16 Reinvestment Fictional Fund (5.00)\n",
        {"account_number": "123-456789-000", "period": "2024-04",
         "total_ending_value": 100.0, "total_value_cover": None, "is_ocr": False},
        [
            {"row_type": "holding", "description": "CASH, BDP, AND MMFs",
             "amount": 100.0, "category": "asset_class_summary",
             "account_number": "123-456789-000", "period": "2024-04",
             "extraction_method": "regex:morgan_stanley", "confidence": 0.9},
            {"row_type": "holding", "description": "MORGAN STANLEY BANK N.A.",
             "amount": 25.0, "category": "bank_deposit_detail",
             "account_number": "123-456789-000", "period": "2024-04",
             "extraction_method": "regex:morgan_stanley", "confidence": 0.9},
            {"row_type": "transaction", "line_date": "04/15",
             "description": "Dividend Fictional Fund", "amount": 10.0,
             "account_number": "123-456789-000", "period": "2024-04",
             "extraction_method": "regex:morgan_stanley", "confidence": 0.8},
            {"row_type": "transaction", "line_date": "04/16",
             "description": "Reinvestment Fictional Fund", "amount": -5.0,
             "account_number": "123-456789-000", "period": "2024-04",
             "extraction_method": "regex:morgan_stanley", "confidence": 0.8},
        ],
        (100.0, 100.0),
    ),
    "ocr_marker_and_corrupt_date": (
        "--- OCR ---\nTOTAL VALUE OF YOUR ACCOUNTS (as of 7/31/2019) $26.58\n"
        "CASH, BOP, AND MEFs 100.00% $26.58\n"
        "731 Dividend Fictional Fund 1.00\n",
        {"account_number": None, "period": None, "total_ending_value": None,
         "total_value_cover": 26.58, "is_ocr": True},
        [{"row_type": "holding", "description": "CASH, BDP, AND MMFs",
          "amount": 26.58, "category": "asset_class_summary", "account_number": None,
          "period": None, "extraction_method": "regex:morgan_stanley(ocr)",
          "confidence": 0.6}],
        (26.58, 26.58),
    ),
    "detail_only_mismatch": (
        "TOTAL ENDING VALUE $100.00\nMORGAN STANLEY BANK N.A. # $25.00\n",
        {"account_number": None, "period": None, "total_ending_value": 100.0,
         "total_value_cover": None, "is_ocr": False},
        [{"row_type": "holding", "description": "MORGAN STANLEY BANK N.A.",
          "amount": 25.0, "category": "bank_deposit_detail",
          "account_number": None, "period": None,
          "extraction_method": "regex:morgan_stanley", "confidence": 0.9}],
        (100.0, 0),
    ),
    "unknown_month_and_zero_fallback": (
        "Period Foo 1-30, 2024\nTOTAL ENDING VALUE $0.00\n"
        "TOTAL VALUE OF YOUR ACCOUNTS (as of 4/30/2024) $20.00\n",
        {"account_number": None, "period": "2024-??", "total_ending_value": 0.0,
         "total_value_cover": 20.0, "is_ocr": False},
        [], (20.0, 0),
    ),
    "empty": (
        "Unrelated fictional text.",
        {"account_number": None, "period": None, "total_ending_value": None,
         "total_value_cover": None, "is_ocr": False},
        [], None,
    ),
}

JEF_CASES: dict[
    str, tuple[str, dict[str, Any], list[dict[str, Any]], tuple[float, float] | None]
] = {
    "negative_cash_multilot_and_transactions": (
        "Account Number: SYN-000001\n"
        "April 1, 2024 - April 30, 2024\n"
        "ENDING ACCOUNT VALUE $80.00\n"
        "Total Portfolio Holdings $80.00 $80.00\n"
        "TOTAL EQUITIES $100.00 $100.00\n"
        "TOTAL CASH, MONEY FUNDS AND BANK DEPOSITS -$20.00 -$20.00\n"
        "EQUITIES 100.00% of Portfolio\n"
        "ALPHA FICTIONAL CORP Security Identifier: ALFA\n"
        "01/02/24 1.0000 40.0000 40.00 50.0000 $50.00 10.00\n"
        "Total Covered 1.0000 40.00 50.00 10.00\n"
        "01/03/24 1.0000 40.0000 40.00 50.0000 $50.00 10.00\n"
        "Total 2.0000 $80.00 $100.00 $20.00\n"
        "04/15/24 04/16/24 PURCHASED ALPHA FICTIONAL 2.0000 50.00 -100.00 USD\n"
        "04/20/24 FDIC INSURED CASH SWEEP -20.00 USD\n"
        "CONTINUATION FICTIONAL IDENTIFIER\n",
        {"account_number": "SYN-000001", "period": "2024-04",
         "ending_account_value": 80.0, "total_portfolio_cost_basis": 80.0,
         "total_portfolio_market_value": 80.0},
        [
            {"row_type": "holding", "description": "EQUITIES", "category": "EQUITIES",
             "amount": 100.0, "account_number": "SYN-000001", "period": "2024-04",
             "extraction_method": "regex:jefferies_category", "confidence": 1.0},
            {"row_type": "holding", "description": "CASH, MONEY FUNDS AND BANK DEPOSITS",
             "category": "CASH, MONEY FUNDS AND BANK DEPOSITS", "amount": -20.0,
             "account_number": "SYN-000001", "period": "2024-04",
             "extraction_method": "regex:jefferies_category", "confidence": 1.0},
            {"row_type": "holding_detail", "description": "ALPHA FICTIONAL CORP",
             "symbol": "ALFA", "amount": 100.0, "category": "EQUITIES",
             "account_number": "SYN-000001", "period": "2024-04",
             "extraction_method": "regex:jefferies_security_detail", "confidence": 0.6},
            {"row_type": "transaction", "line_date": "04/15/24",
             "description": "PURCHASED ALPHA FICTIONAL", "quantity": 2.0,
             "price": 50.0, "amount": -100.0, "currency": "USD",
             "account_number": "SYN-000001", "period": "2024-04",
             "extraction_method": "regex:jefferies", "confidence": 0.85},
            {"row_type": "transaction", "line_date": "04/20/24",
             "description": "FDIC INSURED CASH SWEEP", "quantity": None,
             "price": None, "amount": -20.0, "currency": "USD",
             "account_number": "SYN-000001", "period": "2024-04",
             "extraction_method": "regex:jefferies", "confidence": 0.85},
        ],
        (80.0, 80.0),
    ),
    "single_lot_and_unpriced_position": (
        "ENDING ACCOUNT VALUE $30.00\n"
        "TOTAL ALTERNATIVE INVESTMENTS $20.00 $30.00\n"
        "ALTERNATIVE INVESTMENTS 100.00% of Portfolio\n"
        "GAMMA FICTIONAL FUND Security Identifier: GAMA\n"
        "Please Provide*,1 9,878.000 N/A Pending Receipt N/A N/A N/A\n"
        "BETA FICTIONAL FUND Security Identifier: BETA\n"
        "02/02/24 1.0000 20.0000 20.00 30.0000 $30.00 10.00\n"
        "Total Alternative Investments\n",
        {"account_number": None, "period": None, "ending_account_value": 30.0,
         "total_portfolio_cost_basis": None, "total_portfolio_market_value": None},
        [
            {"row_type": "holding", "description": "ALTERNATIVE INVESTMENTS",
             "category": "ALTERNATIVE INVESTMENTS", "amount": 30.0,
             "account_number": None, "period": None,
             "extraction_method": "regex:jefferies_category", "confidence": 1.0},
            {"row_type": "holding_detail", "description": "BETA FICTIONAL FUND",
             "symbol": "BETA", "amount": 30.0, "category": "ALTERNATIVE INVESTMENTS",
             "account_number": None, "period": None,
             "extraction_method": "regex:jefferies_security_detail", "confidence": 0.6},
        ],
        (30.0, 30.0),
    ),
    "zero_fallback": (
        "ENDING ACCOUNT VALUE $5.00\nTotal Portfolio Holdings $0.00 $0.00\n",
        {"account_number": None, "period": None, "ending_account_value": 5.0,
         "total_portfolio_cost_basis": 0.0, "total_portfolio_market_value": 0.0},
        [], (5.0, 0),
    ),
    "invalid_period": (
        "Foo 1, 2024 - Foo 30, 2024\nENDING ACCOUNT VALUE $0.00\n",
        {"account_number": None, "period": None, "ending_account_value": 0.0,
         "total_portfolio_cost_basis": None, "total_portfolio_market_value": None},
        [], (0.0, 0),
    ),
    "empty": (
        "Unrelated fictional document.",
        {"account_number": None, "period": None, "ending_account_value": None,
         "total_portfolio_cost_basis": None, "total_portfolio_market_value": None},
        [], None,
    ),
}


def _wfs_document(
    rows: str, *, ending: str, beginning: str | None = "100.00",
    fee_period: bool = True,
) -> str:
    """Only fictional text in the donor's flattened savings-statement shape."""
    header = "Account number: 000000\n"
    if fee_period:
        header += "Fee period 07/01/2024 - 07/31/2024\n"
    if beginning is not None:
        header += f"Beginning balance on 7/1 ${beginning}\n"
    return (
        header + f"Ending balance on 7/31 ${ending}\n"
        "Deposits/Credits 30.00\nWithdrawals/Debits - 25.00\n"
        "Interest paid this statement $0.00\nTransaction history\n"
        + rows + "\nThe Ending Daily Balance\n"
    )


WFS_CASES = {
    "single_row_deltas": (
        _wfs_document(
            "7/2 Credit Fictional 10.00 110.00\n"
            "7/3 Debit Fictional 20.00 90.00\n"
            "7/4 Fee Fictional 5.00 85.00", ending="85.00",
        ),
        [("7/2", "Credit Fictional", 10.0, 0.9),
         ("7/3", "Debit Fictional", -20.0, 0.9),
         ("7/4", "Fee Fictional", -5.0, 0.9)],
        (-15.0, -15.0), "2024-07", 100.0,
    ),
    "same_direction_days": (
        _wfs_document(
            "7/2 Neutral A 10.00\n7/2 Neutral B 20.00 130.00\n"
            "7/3 Neutral C 5.00\n7/3 Neutral D 5.00 120.00", ending="120.00",
        ),
        [("7/2", "Neutral A", 10.0, 0.8),
         ("7/2", "Neutral B", 20.0, 0.8),
         ("7/3", "Neutral C", -5.0, 0.8),
         ("7/3", "Neutral D", -5.0, 0.8)],
        (20.0, 20.0), "2024-07", 100.0,
    ),
    "mixed_keyword_and_residual": (
        _wfs_document(
            "7/2 Debit Fictional 20.00\n7/2 Neutral Fictional 10.00 90.00",
            ending="90.00",
        ),
        [("7/2", "Debit Fictional", -20.0, 0.85),
         ("7/2", "Neutral Fictional", 10.0, 0.65)],
        (-10.0, -10.0), "2024-07", 100.0,
    ),
    "misleading_transfer_from_into": (
        _wfs_document(
            "7/2 Transfer From Fictional Into Vault 10.00\n"
            "7/2 Neutral Fictional 20.00 110.00", ending="110.00",
        ),
        [("7/2", "Transfer From Fictional Into Vault", -10.0, 0.85),
         ("7/2", "Neutral Fictional", 20.0, 0.65)],
        (10.0, 10.0), "2024-07", 100.0,
    ),
    "wire_originator_and_beneficiary": (
        _wfs_document(
            "7/2 WT /Org=Fictional 10.00\n"
            "7/2 WT /Bnf=Fictional 20.00 90.00", ending="90.00",
        ),
        [("7/2", "WT /Org=Fictional", 10.0, 0.85),
         ("7/2", "WT /Bnf=Fictional", -20.0, 0.85)],
        (-10.0, -10.0), "2024-07", 100.0,
    ),
    "unique_subset_solution": (
        _wfs_document(
            "7/2 Neutral A 5.00\n7/2 Neutral B 10.00\n"
            "7/2 Neutral C 20.00 105.00", ending="105.00",
        ),
        [("7/2", "Neutral A", -5.0, 0.5),
         ("7/2", "Neutral B", -10.0, 0.5),
         ("7/2", "Neutral C", 20.0, 0.5)],
        (5.0, 5.0), "2024-07", 100.0,
    ),
    "ambiguous_equal_amounts": (
        _wfs_document(
            "7/2 Neutral A 10.00\n7/2 Neutral B 10.00 100.00", ending="100.00",
        ),
        [("7/2", "Neutral A", 10.0, 0.3),
         ("7/2", "Neutral B", 10.0, 0.3)],
        (0.0, 20.0), "2024-07", 100.0,
    ),
    "no_subset_solution": (
        _wfs_document(
            "7/2 Neutral A 10.00\n7/2 Neutral B 10.00 105.00", ending="105.00",
        ),
        [("7/2", "Neutral A", 10.0, 0.2),
         ("7/2", "Neutral B", 10.0, 0.2)],
        (5.0, 20.0), "2024-07", 100.0,
    ),
    "twelve_unknown_bound": (
        _wfs_document(
            "\n".join(f"7/2 Neutral {index:02d} 1.00" for index in range(11))
            + "\n7/2 Neutral 11 1.00 100.00", ending="100.00",
        ),
        [("7/2", f"Neutral {index:02d}", 1.0, 0.3) for index in range(12)],
        (0.0, 12.0), "2024-07", 100.0,
    ),
    "thirteen_unknown_cap": (
        _wfs_document(
            "\n".join(f"7/2 Neutral {index:02d} 1.00" for index in range(12))
            + "\n7/2 Neutral 12 1.00 101.00", ending="101.00",
        ),
        [("7/2", f"Neutral {index:02d}", 1.0, 0.15) for index in range(13)],
        (1.0, 13.0), "2024-07", 100.0,
    ),
    "missing_daily_balance": (
        _wfs_document("7/2 Neutral A 5.00", ending="100.00"),
        [("7/2", "Neutral A", 5.0, 0.2)],
        (0.0, 5.0), "2024-07", 100.0,
    ),
    "missing_beginning_balance": (
        _wfs_document("7/2 Neutral A 5.00 105.00", ending="105.00", beginning=None),
        [], None, "2024-07", None,
    ),
    "missing_fee_period": (
        _wfs_document("7/2 Neutral A 5.00 105.00", ending="105.00", fee_period=False),
        [("7/2", "Neutral A", 5.0, 0.9)],
        (5.0, 5.0), None, 100.0,
    ),
}
WFS_ENDINGS = {
    "single_row_deltas": 85.0,
    "same_direction_days": 120.0,
    "mixed_keyword_and_residual": 90.0,
    "misleading_transfer_from_into": 110.0,
    "wire_originator_and_beneficiary": 90.0,
    "unique_subset_solution": 105.0,
    "ambiguous_equal_amounts": 100.0,
    "no_subset_solution": 105.0,
    "twelve_unknown_bound": 100.0,
    "thirteen_unknown_cap": 101.0,
    "missing_daily_balance": 100.0,
    "missing_beginning_balance": 105.0,
    "missing_fee_period": 105.0,
}


@pytest.mark.parametrize("name", WFS_CASES)
def test_wells_fargo_savings_pinned_golden(name: str) -> None:
    content, expected_rows, expected_reconciliation, period, beginning = WFS_CASES[name]
    summary, items = parse_wells_fargo_savings(content)
    assert summary == {
        "account_number": "000000", "period": period,
        "beginning_balance": beginning,
        "ending_balance": WFS_ENDINGS[name],
        "deposits_total": 30.0, "withdrawals_total": 25.0, "interest_paid": 0.0,
    }
    assert items == [
        {
            "row_type": "transaction", "line_date": line_date,
            "description": description, "amount": amount,
            "category": "deposit" if amount >= 0 else "withdrawal",
            "account_number": "000000", "period": period,
            "currency": "USD", "confidence": confidence,
            "extraction_method": "regex:wells_fargo_savings",
        }
        for line_date, description, amount, confidence in expected_rows
    ]
    assert reconcile_wells_fargo_savings(summary, items) == expected_reconciliation


@pytest.mark.parametrize("name", CASES)
def test_pinned_golden(name: str) -> None:
    content, expected_summary, expected_items, expected_reconciliation = CASES[name]
    summary, items = parse_streetbeat(content)
    assert (summary, items, reconcile_streetbeat(summary, items)) == (
        expected_summary, expected_items, expected_reconciliation,
    )


@pytest.mark.parametrize("name", FIDELITY_CASES)
def test_fidelity_pinned_golden(name: str) -> None:
    content, expected_summary, expected_items, expected_reconciliation = FIDELITY_CASES[name]
    summary, items = parse_fidelity(content)
    assert (summary, items, reconcile_fidelity(summary, items)) == (
        expected_summary, expected_items, expected_reconciliation,
    )


@pytest.mark.parametrize("name", JLB_CASES)
def test_ocr_bank_pinned_golden(name: str) -> None:
    content, expected_items, expected_reconciliation = JLB_CASES[name]
    summary, items = parse_ocr_bank(content)
    assert items == expected_items
    assert reconcile_ocr_bank(summary, items) == expected_reconciliation
    assert summary["period"] == ("2024-01" if name in (
        "year_rollover_and_wrapped_ocr_amount", "mismatch") else None)


@pytest.mark.parametrize("name", MS_CASES)
def test_morgan_stanley_pinned_golden(name: str) -> None:
    content, expected_summary, expected_items, expected_reconciliation = MS_CASES[name]
    summary, items = parse_morgan_stanley(content)
    assert (summary, items, reconcile_morgan_stanley(summary, items)) == (
        expected_summary, expected_items, expected_reconciliation,
    )


@pytest.mark.parametrize("name", JEF_CASES)
def test_jefferies_pinned_golden(name: str) -> None:
    content, expected_summary, expected_items, expected_reconciliation = JEF_CASES[name]
    summary, items = parse_jefferies(content)
    assert (summary, items, reconcile_jefferies(summary, items)) == (
        expected_summary, expected_items, expected_reconciliation,
    )


def _donor_functions(path: Path) -> tuple[Any, ...]:
    """Run only pure pinned recipe AST nodes, never donor module imports or DB code."""
    source = path.read_bytes()
    assert hashlib.sha256(source).hexdigest() == DONOR_SHA256
    functions = {"num", "_parse_streetbeat", "_reconcile_streetbeat",
                 "_parse_fidelity", "_reconcile_fidelity", "_jlb_section",
                 "_jlb_rows", "_jlb_row_date", "_parse_ocr_bank",
                 "_reconcile_ocr_bank", "_ms_num", "_parse_morgan_stanley",
                 "_reconcile_morgan_stanley", "_parse_jefferies",
                 "_reconcile_jefferies", "_wf_sign_keyword", "_wf_resolve_group",
                 "_parse_wells_fargo_savings", "_reconcile_wells_fargo_savings"}
    constants = {"_MONTHS", "_SB_TXN", "_SB_HOLDING_ROW", "_SB_CASH_ROW",
                 "_FID_HOLDING_ROW", "_FID_ACTIVITY_ROW", "_FID_NON_HOLDING_LABELS",
                 "_JLB_BOILERPLATE", "_JLB_TXN_TYPE", "_MS_MONTHS", "_MS_ACCOUNT",
                 "_MS_PERIOD", "_MS_TOTAL_ENDING", "_MS_TOTAL_COVER", "_MS_CASH_BUCKET",
                 "_MS_BANK_DEPOSIT", "_MS_ACTIVITY_ROW"}
    constants.update({
        "_JEF_CATEGORY_TOTAL", "_JEF_SECTION_HEADER", "_JEF_SECURITY_HEADER",
        "_JEF_SKIP_SUBTOTAL", "_JEF_LOT_LINE", "_JEF_SECURITY_TOTAL",
        "_JEF_TXN", "_JEF_TXN_QTY_PRICE",
        "_WFS_TXN_SECTION", "_WFS_TXN_ROW",
    })
    nodes = []
    for node in ast.parse(source, filename=str(path)).body:
        if isinstance(node, ast.FunctionDef) and node.name in functions:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in constants for target in node.targets
        ):
            nodes.append(node)
    assert len(nodes) == len(functions) + len(constants)
    namespace: dict[str, Any] = {"re": re, "datetime": datetime}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return (namespace["_parse_streetbeat"], namespace["_reconcile_streetbeat"],
            namespace["_parse_fidelity"], namespace["_reconcile_fidelity"],
            namespace["_parse_ocr_bank"], namespace["_reconcile_ocr_bank"],
            namespace["_parse_morgan_stanley"], namespace["_reconcile_morgan_stanley"],
            namespace["_parse_jefferies"], namespace["_reconcile_jefferies"],
            namespace["_parse_wells_fargo_savings"],
            namespace["_reconcile_wells_fargo_savings"])


def test_local_pinned_donor_parity() -> None:
    donor = os.environ.get("FOS_MASTER_STATEMENT_EXTRACT")
    if donor is None:
        pytest.skip("Set FOS_MASTER_STATEMENT_EXTRACT for optional pinned donor replay")
    (donor_parse, donor_reconcile, donor_fidelity, donor_fidelity_reconcile,
     donor_jlb, donor_jlb_reconcile, donor_ms, donor_ms_reconcile,
     donor_jef, donor_jef_reconcile, donor_wfs, donor_wfs_reconcile) = _donor_functions(
        Path(donor)
    )
    stress_content = (
        "Period: April - 2024\nLong $100000.00\n" + HEADER + "\n"
        + (HOLDING + "\n") * 1000
    )
    for content in [*(case[0] for case in CASES.values()), stress_content]:
        donor_summary, donor_items = donor_parse(content)
        summary, items = parse_streetbeat(content)
        assert (summary, items, reconcile_streetbeat(summary, items)) == (
            donor_summary, donor_items, donor_reconcile(donor_summary, donor_items),
        )
    fidelity_stress = "Total Holdings $1000.00\n" + "".join(
        f"ACME Fictional Fund {index:04d} 1.00 1%\n" for index in range(1000)
    )
    for content in [*(case[0] for case in FIDELITY_CASES.values()), fidelity_stress]:
        donor_summary, donor_items = donor_fidelity(content)
        summary, items = parse_fidelity(content)
        assert (summary, items, reconcile_fidelity(summary, items)) == (
            donor_summary, donor_items, donor_fidelity_reconcile(donor_summary, donor_items),
        )
        if content == fidelity_stress:
            assert len(items) == 1000
    jlb_stress = JLB_HEADER + "DEBITS\n" + "".join(
        f"12-30 Fictional Debit {index}.00\n" for index in range(1, 1001)
    ) + "CREDITS\nDAILY BALANCES\n"
    for content in [*(case[0] for case in JLB_CASES.values()), jlb_stress]:
        donor_summary, donor_items = donor_jlb(content)
        summary, items = parse_ocr_bank(content)
        assert (summary, items, reconcile_ocr_bank(summary, items)) == (
            donor_summary, donor_items, donor_jlb_reconcile(donor_summary, donor_items),
        )
        if content == jlb_stress:
            assert len(items) == 1000
    ms_stress = "TOTAL ENDING VALUE $0.00\n" + "".join(
        f"01/02 Dividend Fictional Fund {index}.00\n" for index in range(1, 1001)
    )
    for content in [*(case[0] for case in MS_CASES.values()), ms_stress]:
        donor_summary, donor_items = donor_ms(content)
        summary, items = parse_morgan_stanley(content)
        assert (summary, items, reconcile_morgan_stanley(summary, items)) == (
            donor_summary, donor_items, donor_ms_reconcile(donor_summary, donor_items),
        )
        if content == ms_stress:
            assert len(items) == 1000
    jefferies_stress = (
        "ENDING ACCOUNT VALUE $1000.00\nTOTAL EQUITIES $1000.00 $1000.00\n"
        "EQUITIES 100.00% of Portfolio\n"
        + "".join(
            f"FICTIONAL SECURITY {index:04d} Security Identifier: SYM{index:04d}\n"
            "02/02/24 1.0000 1.0000 1.00 1.0000 $1.00 0.00\n"
            for index in range(1000)
        )
    )
    for content in [*(case[0] for case in JEF_CASES.values()), jefferies_stress]:
        donor_summary, donor_items = donor_jef(content)
        summary, items = parse_jefferies(content)
        assert (summary, items, reconcile_jefferies(summary, items)) == (
            donor_summary, donor_items, donor_jef_reconcile(donor_summary, donor_items),
        )
        if content == jefferies_stress:
            assert len(items) == 1001
    wfs_stress = _wfs_document(
        "\n".join(f"7/2 Fictional Credit {index:04d} 1.00" for index in range(999))
        + "\n7/2 Fictional Credit 0999 1.00 1100.00",
        ending="1100.00",
    )
    for content in [*(case[0] for case in WFS_CASES.values()), wfs_stress]:
        donor_summary, donor_items = donor_wfs(content)
        summary, items = parse_wells_fargo_savings(content)
        assert (summary, items, reconcile_wells_fargo_savings(summary, items)) == (
            donor_summary, donor_items, donor_wfs_reconcile(donor_summary, donor_items),
        )
        if content == wfs_stress:
            assert len(items) == 1000


def test_many_fictional_rows_are_repeatable() -> None:
    content = (
        "Period: April - 2024\nLong $100000.00\n" + HEADER + "\n"
        + (HOLDING + "\n") * 1000
    )
    first = parse_streetbeat(content)
    assert len(first[1]) == 1000
    assert first == parse_streetbeat(content)
    assert reconcile_streetbeat(*first) == (100000.0, 100000.0)


def test_fidelity_many_distinct_fictional_rows_are_repeatable() -> None:
    content = "Total Holdings $1000.00\n" + "".join(
        f"ACME Fictional Fund {index:04d} 1.00 1%\n" for index in range(1000)
    )
    first = parse_fidelity(content)
    assert len(first[1]) == 1000
    assert first == parse_fidelity(content)
    assert reconcile_fidelity(*first) == (1000.0, 1000.0)


def test_ocr_bank_many_fictional_rows_are_repeatable() -> None:
    content = JLB_HEADER + "DEBITS\n" + "".join(
        f"12-30 Fictional Debit {index}.00\n" for index in range(1, 1001)
    ) + "CREDITS\nDAILY BALANCES\n"
    first = parse_ocr_bank(content)
    assert len(first[1]) == 1000
    assert first == parse_ocr_bank(content)
    assert reconcile_ocr_bank(*first) == (110.0, -500400.0)


def test_morgan_stanley_many_fictional_rows_are_repeatable() -> None:
    content = "TOTAL ENDING VALUE $0.00\n" + "".join(
        f"01/02 Dividend Fictional Fund {index}.00\n" for index in range(1, 1001)
    )
    first = parse_morgan_stanley(content)
    assert len(first[1]) == 1000
    assert first == parse_morgan_stanley(content)
    assert reconcile_morgan_stanley(*first) is None  # Donor treats a zero total as absent.


def test_jefferies_many_fictional_details_are_repeatable() -> None:
    content = (
        "ENDING ACCOUNT VALUE $1000.00\nTOTAL EQUITIES $1000.00 $1000.00\n"
        "EQUITIES 100.00% of Portfolio\n"
        + "".join(
            f"FICTIONAL SECURITY {index:04d} Security Identifier: SYM{index:04d}\n"
            "02/02/24 1.0000 1.0000 1.00 1.0000 $1.00 0.00\n"
            for index in range(1000)
        )
    )
    first = parse_jefferies(content)
    assert len(first[1]) == 1001
    assert first == parse_jefferies(content)
    assert reconcile_jefferies(*first) == (1000.0, 1000.0)


def test_wells_fargo_savings_many_fictional_rows_are_repeatable() -> None:
    content = _wfs_document(
        "\n".join(f"7/2 Fictional Credit {index:04d} 1.00" for index in range(999))
        + "\n7/2 Fictional Credit 0999 1.00 1100.00",
        ending="1100.00",
    )
    first = parse_wells_fargo_savings(content)
    assert len(first[1]) == 1000
    assert first == parse_wells_fargo_savings(content)
    assert all(row["confidence"] == 0.8 for row in first[1])
    assert reconcile_wells_fargo_savings(*first) == (1000.0, 1000.0)
