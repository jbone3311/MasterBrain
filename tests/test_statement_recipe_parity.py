"""Fictional golden corpus for the pinned FOS-Master Streetbeat recipe."""

from __future__ import annotations

import ast
import hashlib
import os
import re
from pathlib import Path
from typing import Any

import pytest

from masterbrain.statement_recipe_parity import parse_streetbeat, reconcile_streetbeat

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


@pytest.mark.parametrize("name", CASES)
def test_pinned_golden(name: str) -> None:
    content, expected_summary, expected_items, expected_reconciliation = CASES[name]
    summary, items = parse_streetbeat(content)
    assert (summary, items, reconcile_streetbeat(summary, items)) == (
        expected_summary, expected_items, expected_reconciliation,
    )


def _donor_functions(path: Path) -> tuple[Any, Any]:
    """Run only pure pinned recipe AST nodes, never donor module imports or DB code."""
    source = path.read_bytes()
    assert hashlib.sha256(source).hexdigest() == DONOR_SHA256
    functions = {"num", "_parse_streetbeat", "_reconcile_streetbeat"}
    constants = {"_MONTHS", "_SB_TXN", "_SB_HOLDING_ROW", "_SB_CASH_ROW"}
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
    return namespace["_parse_streetbeat"], namespace["_reconcile_streetbeat"]


def test_local_pinned_donor_parity() -> None:
    donor = os.environ.get("FOS_MASTER_STATEMENT_EXTRACT")
    if donor is None:
        pytest.skip("Set FOS_MASTER_STATEMENT_EXTRACT for optional pinned donor replay")
    donor_parse, donor_reconcile = _donor_functions(Path(donor))
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


def test_many_fictional_rows_are_repeatable() -> None:
    content = (
        "Period: April - 2024\nLong $100000.00\n" + HEADER + "\n"
        + (HOLDING + "\n") * 1000
    )
    first = parse_streetbeat(content)
    assert len(first[1]) == 1000
    assert first == parse_streetbeat(content)
    assert reconcile_streetbeat(*first) == (100000.0, 100000.0)
