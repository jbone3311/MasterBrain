"""Fictional ordered-row goldens against the pinned FOS brokerage recipe."""

from __future__ import annotations

import ast
import hashlib
import os
import re
from pathlib import Path
from typing import Any

import pytest

from masterbrain.statement_recipe_parity import (
    parse_wells_fargo_brokerage,
    reconcile_wells_fargo_brokerage,
)

DONOR_SHA256 = "f5b0c8bc5c0c9f01fa8decdecba36a27b81ccfd212894409472bac8526b577fe"
HEADER = "ACCOUNT NUMBER: 0000-1111\nCurrent period ending July 31, 2024\n"
TOTAL = "Total 2 $40.00 $80.00 50.00 $100.00 $20.00 N/A N/A"
LOT = "Acquired01/02/24 2 40.00 80.00 50.00 $100.00 20.00 N/A\n"
SINGLELINE = (
    "APPLEINC 8,758 72.53** 635,228.89 196.4500 1,720,509.10 "
    "1,085,280.21 8,408 0.48\nAAPL\n"
)
CASES = {
    "cash_and_total": (
        HEADER + "Closing value $150.00\nTotal Cash and Sweep Balances $50.00\n"
        "ACME FICTIONAL FUND\nACME\n" + TOTAL + "\n"
        "07/03 Cash DIVIDEND ACME FICTIONAL FUND 2.00\n",
        3, (150.0, 150.0),
    ),
    "single_acquired_lot": (
        HEADER + "Closing value $100.00\nACME FICTIONAL FUND\nACME\n"
        + LOT + "END OF FICTIONAL SECTION\n",
        1, (100.0, 100.0),
    ),
    "page_break_lot_dedup": (
        HEADER + "Closing value $100.00\nACME FICTIONAL FUND\nACME\n"
        + LOT + "PAGE 2 OF 3\n" + TOTAL + "\n",
        1, (100.0, 100.0),
    ),
    "more_than_six_lots": (
        HEADER + "Closing value $1,720,509.10\n" + SINGLELINE,
        1, (1_720_509.10, 1_720_509.10),
    ),
    "zero_closing_uses_asset": (
        HEADER + "Closing value $0.00\nAsset value $100.00 100% $100.00\n"
        "Total Cash and Sweep Balances $100.00\n",
        1, (100.0, 100.0),
    ),
    "incomplete_tail_mismatch": (
        "JULY1,2024-JULY31,2024\nClosing value $100.00\n"
        "This fictional tail has no holdings section.\n",
        0, (100.0, 0),
    ),
    "empty": ("Fictional unrelated text", 0, None),
}


@pytest.mark.parametrize("name", CASES)
def test_fictional_brokerage_golden(name: str) -> None:
    content, row_count, expected_reconciliation = CASES[name]
    summary, rows = parse_wells_fargo_brokerage(content)
    assert len(rows) == row_count
    assert reconcile_wells_fargo_brokerage(summary, rows) == expected_reconciliation
    assert all(row["extraction_method"] == "regex:wells_fargo_brokerage" for row in rows)
    if name == "cash_and_total":
        assert [row["row_type"] for row in rows] == [
            "holding", "holding", "transaction",
        ]
        assert rows[1]["symbol"] == "ACME"
        assert rows[1]["amount"] == 100.0
    if name == "page_break_lot_dedup":
        assert rows[0]["confidence"] == 0.75
    if name == "more_than_six_lots":
        assert rows[0]["symbol"] == "AAPL"
        assert "avg_cost_gt_6_lots=true" in rows[0]["category"]


def _pinned_donor(path: Path) -> tuple[Any, Any]:
    source = path.read_bytes()
    assert hashlib.sha256(source).hexdigest() == DONOR_SHA256
    functions = {
        "num", "_wfb_lookback_symbol", "_wfb_lookback_name",
        "_parse_wells_fargo_brokerage", "_reconcile_wells_fargo_brokerage",
    }
    constants = {
        "_WFB_MONTHS", "_WFB_ACCOUNT_NO", "_WFB_PERIOD_CLEAN",
        "_WFB_PERIOD_HEADER", "_WFB_CLOSING_VALUE", "_WFB_ASSET_VALUE",
        "_WFB_CASH_ROW", "_WFB_HOLDING_TOTAL_ROW",
        "_WFB_ACQUIRED_SINGLE_LOT_ROW", "_WFB_HOLDING_SINGLELINE_ROW",
        "_WFB_TICKER_LINE", "_WFB_NAME_LINE", "_WFB_LOT_LINE", "_WFB_TXN_ROW",
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
    return namespace["_parse_wells_fargo_brokerage"], namespace[
        "_reconcile_wells_fargo_brokerage"
    ]


def test_exact_hash_local_donor_replay() -> None:
    donor_path = os.environ.get("FOS_MASTER_STATEMENT_EXTRACT")
    if donor_path is None:
        pytest.skip("Set FOS_MASTER_STATEMENT_EXTRACT for pinned donor replay")
    donor_parse, donor_reconcile = _pinned_donor(Path(donor_path))
    stress = HEADER + "Closing value $1000.00\n" + "".join(
        f"FICTIONAL SECURITY {index:04d} 1 1.00** 1.00 1.00 1.00 0.00 N/A N/A\n"
        f"SYM{index:04d}\n"
        for index in range(1000)
    )
    for content in [*(case[0] for case in CASES.values()), stress]:
        donor_summary, donor_rows = donor_parse(content)
        summary, rows = parse_wells_fargo_brokerage(content)
        assert (summary, rows, reconcile_wells_fargo_brokerage(summary, rows)) == (
            donor_summary, donor_rows, donor_reconcile(donor_summary, donor_rows),
        )
        if content == stress:
            assert len(rows) == 1000


def test_thousand_fictional_holdings_repeatable() -> None:
    text = HEADER + "Closing value $1000.00\n" + "".join(
        f"FICTIONAL SECURITY {index:04d} 1 1.00** 1.00 1.00 1.00 0.00 N/A N/A\n"
        f"SYM{index:04d}\n"
        for index in range(1000)
    )
    first = parse_wells_fargo_brokerage(text)
    assert first == parse_wells_fargo_brokerage(text)
    assert len(first[1]) == 1000
    assert reconcile_wells_fargo_brokerage(*first) == (1000.0, 1000.0)
