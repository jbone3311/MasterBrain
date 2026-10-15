"""Fictional supplied-text goldens against the exact pinned Schwab recipe."""

from __future__ import annotations

import ast
import hashlib
import os
import re
from pathlib import Path
from typing import Any

import pytest

from masterbrain.statement_recipe_parity import (
    parse_charles_schwab,
    reconcile_charles_schwab,
)

DONOR_SHA256 = "f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe"
HEADER = (
    "Account Number Statement Period\n0000-1111 April 01-30, 2024\n"
    "Total Investment Detail $150.00\n"
    "Account Value as of 04/30/2024:$ 151.00\n"
)
SWEEP = "Investment Detail - Bank Sweep\nBank Sweep 10.00 50.00\n"
SECURITY = "ACME FICTIONAL FUND 2.0000 25.00000 50.00\nSYMBOL: ACME\n"
INLINE = "FICTIONAL TREASURY MO:FTMO 5.0000 10.00000 50.00\n"


CASES = {
    "old_template_two_symbols": (
        HEADER + SWEEP + SECURITY + INLINE + "Transaction Detail - Deposits & Withdrawals\n",
        3, (150.0, 150.0),
    ),
    "cash_and_bank_sweep_variant": (
        HEADER.replace("$150.00", "$100.00")
        + "Investment Detail - Cash and Bank Sweep\n"
        + "Cash 0.00 25.00\nBank Sweep 10.00 75.00\n"
        + "Transaction Detail - Deposits & Withdrawals\n",
        2, (100.0, 100.0),
    ),
    "missing_symbol_lowers_all_holding_confidence": (
        HEADER.replace("$150.00", "$50.00")
        + "Investment Detail - Bank Sweep\n" + SECURITY.replace("SYMBOL: ACME\n", "")
        + "Transaction Detail - Deposits & Withdrawals\n",
        1, (50.0, 50.0),
    ),
    "transactions_and_accounting_parens": (
        HEADER + SWEEP + SECURITY + INLINE
        + "Transaction Detail - Deposits & Withdrawals\n"
        + "04/01/24 04/02/24 Fictional transfer (20.00)\n"
        + "04/03/24 04/04/24 Total Credit/(Debit) 100.00\n"
        + "Transaction Detail - Dividends & Interest\n"
        + "04/05/24 04/06/24 Fictional dividend 3.00\n"
        + "Total Dividends & Interest\n"
        + "Transaction Detail - Purchases & Sales\n"
        + "04/07/24 04/08/24 Reinvested Shares ACME 1.0000 3.00 (3.00)\n"
        + "Total Purchases & Sales\n",
        6, (150.0, 150.0),
    ),
    "cid_marker_and_symbol_continuation_not_double_counted": (
        HEADER.replace("$150.00", "$50.00")
        + "Investment Detail - Bank Sweep\n"
        + "ACME FICTIONAL (cid:224) FUND 2.0000 25.00000 50.00\n"
        + "SYMBOL: ACME 2.0000 25.00000 50.00 10/15/15 (1.00) 1173 Long-Term\n",
        1, (50.0, 50.0),
    ),
    "zero_total_falls_back_to_account_value": (
        HEADER.replace("$150.00", "$0.00").replace("$ 151.00", "$ 50.00")
        + SWEEP,
        1, (50.0, 50.0),
    ),
    "redesigned_spacing_not_silently_counted": (
        "AccountNumber StatementPeriod\n0000-1111 April01-30,2024\n"
        "TotalInvestmentDetail$150.00\nInvestmentDetail-BankSweep\n"
        "ACMEFICTIONALFUND2.000025.0000050.00\n",
        0, None,
    ),
    "scanned_no_text": ("", 0, None),
    "unknown_month": (
        "Account Number Statement Period\n0000-1111 Foo 01-30, 2024\n"
        "Total Investment Detail $0.00\n",
        0, None,  # Donor treats a zero total with no fallback as absent.
    ),
}


@pytest.mark.parametrize("name", CASES)
def test_fictional_schwab_golden(name: str) -> None:
    content, count, expected_reconciliation = CASES[name]
    summary, rows = parse_charles_schwab(content)
    assert len(rows) == count
    assert reconcile_charles_schwab(summary, rows) == expected_reconciliation
    if name == "old_template_two_symbols":
        assert summary == {
            "account_number": "0000-1111", "period": "2024-04",
            "total_investment_detail": 150.0, "account_value": 151.0,
        }
        assert [row["symbol"] for row in rows] == ["CASH", "ACME", "FTMO"]
        assert [row["amount"] for row in rows] == [50.0, 50.0, 50.0]
        assert rows[1]["confidence"] == rows[2]["confidence"] == 0.85
    if name == "cash_and_bank_sweep_variant":
        assert [row["description"] for row in rows] == ["Cash", "Bank Sweep"]
    if name == "missing_symbol_lowers_all_holding_confidence":
        assert rows[0]["symbol"] is None
        assert rows[0]["confidence"] == 0.65
    if name == "transactions_and_accounting_parens":
        assert [row["category"] for row in rows[3:]] == [
            "deposit_withdrawal", "dividend_interest", "purchase_sale",
        ]
        assert [row["amount"] for row in rows[3:]] == [-20.0, 3.0, -3.0]
        assert rows[-1]["confidence"] == 0.5
    if name == "cid_marker_and_symbol_continuation_not_double_counted":
        assert rows[0]["symbol"] == "ACME"


def _pinned_donor(path: Path) -> tuple[Any, Any]:
    source = path.read_bytes()
    assert hashlib.sha256(source).hexdigest() == DONOR_SHA256
    functions = {
        "num", "_schw_signed", "_parse_charles_schwab", "_reconcile_charles_schwab",
    }
    constants = {
        "_MONTHS", "_NAME", "_SCHW_ACCT_PERIOD", "_SCHW_TOTAL_INV_DETAIL",
        "_SCHW_ACCT_VALUE_ASOF", "_SCHW_INLINE_SYMBOL", "_SCHW_BANK_SWEEP_ROW",
        "_SCHW_HOLDING_ROW", "_SCHW_SYMBOL", "_SCHW_DW_ROW", "_SCHW_PS_ROW",
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
    return namespace["_parse_charles_schwab"], namespace["_reconcile_charles_schwab"]


def test_exact_hash_local_donor_replay() -> None:
    donor = os.environ.get("FOS_MASTER_STATEMENT_EXTRACT")
    if donor is None:
        pytest.skip("Set FOS_MASTER_STATEMENT_EXTRACT for pinned donor replay")
    donor_parse, donor_reconcile = _pinned_donor(Path(donor))
    stress = (
        "Account Number Statement Period\n0000-1111 April 01-30, 2024\n"
        "Total Investment Detail $1000.00\nInvestment Detail - Bank Sweep\n"
        + "".join(
            f"FICTIONAL SECURITY {index:04d} 1.0000 1.00000 1.00\n"
            f"SYMBOL: S{index:04d}\n" for index in range(1000)
        )
    )
    for content in [*(case[0] for case in CASES.values()), stress]:
        donor_summary, donor_rows = donor_parse(content)
        summary, rows = parse_charles_schwab(content)
        assert (summary, rows, reconcile_charles_schwab(summary, rows)) == (
            donor_summary, donor_rows, donor_reconcile(donor_summary, donor_rows),
        )
        if content == stress:
            assert len(rows) == 1000


def test_thousand_fictional_holdings_repeatable() -> None:
    content = (
        "Total Investment Detail $1000.00\nInvestment Detail - Bank Sweep\n"
        + "".join(
            f"FICTIONAL SECURITY {index:04d} 1.0000 1.00000 1.00\n"
            f"SYMBOL: S{index:04d}\n" for index in range(1000)
        )
    )
    first = parse_charles_schwab(content)
    assert first == parse_charles_schwab(content)
    assert len(first[1]) == 1000
    assert reconcile_charles_schwab(*first) == (1000.0, 1000.0)
