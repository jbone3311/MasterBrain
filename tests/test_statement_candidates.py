"""Fictional, nonpublishing statement candidate and evidence-span checks."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from decimal import Decimal

import pytest

from masterbrain.datacore.contracts import Digest, EvidenceRef, EvidenceStorage, SourceKind
from masterbrain.statement_candidates import (
    DONOR_COMMIT,
    MAX_TEXT_BYTES,
    TRANSFORM_VERSION,
    CandidateStatus,
    project_streetbeat_candidate,
)
from masterbrain.statement_recipe_parity import parse_streetbeat

HEADER = "Symbol Description Quantity Market Price Market Value Cost Price Unrealized TD Cost Basis"
HOLDING = "ACME Fictional Corporation 2 $50.00 $100.00 $40.00 $20.00 $80.00"
BASE = (
    "Account No: 000000\nPeriod: April - 2024\nTotal Market Value $150.00\n"
    f"Long $150.00\n{HEADER}\n{HOLDING}\n*Cash Other $ -- $ 50.00 $ --\n"
    "Transaction\n01/02/2024 Trade Entry buy ACME 2 $50.00 -$100.00"
)
EVIDENCE = EvidenceRef(
    evidence_id="ev_fictional", source_version_id="ver_fictional",
    digest=Digest("sha256", hashlib.sha256(b"fictional source bytes").hexdigest()),
    storage=EvidenceStorage.INLINE, retained=True,
)


def candidate(text: str = BASE, kind: SourceKind = SourceKind.FILEOS):
    return project_streetbeat_candidate(
        text, source_kind=kind, evidence=EVIDENCE,
        text_digest=Digest("sha256", hashlib.sha256(text.encode()).hexdigest()),
    )


def test_exact_rows_spans_and_source_neutrality() -> None:
    file_candidate = candidate()
    mail_candidate = candidate(kind=SourceKind.EMAIL)
    assert file_candidate.status is CandidateStatus.RECONCILED
    assert file_candidate.coverage_errors == ()
    assert (file_candidate.expected, file_candidate.actual, file_candidate.delta) == (
        Decimal("150.00"), Decimal("150.00"), Decimal("0.00"),
    )
    assert file_candidate.account_number == "000000"
    assert file_candidate.period == "2024-04"
    assert file_candidate.donor_commit == DONOR_COMMIT
    assert file_candidate.transform_version == TRANSFORM_VERSION
    assert file_candidate.evidence == EVIDENCE
    assert mail_candidate.source_kind is SourceKind.EMAIL
    assert mail_candidate.rows == file_candidate.rows
    assert [row.row_type for row in file_candidate.rows] == [
        row["row_type"] for row in parse_streetbeat(BASE)[1]
    ]
    assert [row.symbol for row in file_candidate.rows] == [
        row["symbol"] for row in parse_streetbeat(BASE)[1]
    ]
    for row in file_candidate.rows:
        quote = BASE[row.text_start:row.text_end]
        assert quote and ("Fictional" in quote or "Trade Entry" in quote or "*Cash" in quote)
        assert row.currency == "USD"
    holding = file_candidate.rows[1]
    assert (holding.quantity, holding.price, holding.amount, holding.cost_basis,
            holding.unrealized) == tuple(map(Decimal, ("2", "50.00", "100.00", "80.00", "20.00")))
    assert file_candidate.rows[0].amount == Decimal("-100.00")


def test_exact_decimal_sum_and_duplicate_occurrences() -> None:
    line = "ACME Fictional Corporation 1 $0.10 $0.10 $0.10 $0.00 $0.10"
    other = "BETA Imaginary Company 1 $0.20 $0.20 $0.20 $0.00 $0.20"
    text = (
        "Account No: 000000\nPeriod: April - 2024\nLong $0.40\n"
        f"{HEADER}\n{line}\n{line}\n{other}"
    )
    result = candidate(text)
    assert result.status is CandidateStatus.RECONCILED
    assert result.actual == Decimal("0.40")
    assert result.rows[0] != result.rows[1]  # Same values, distinct source positions.
    assert result.rows[0].amount == result.rows[1].amount == Decimal("0.10")


def test_mismatch_and_stated_zero_do_not_fall_back() -> None:
    mismatch = candidate(BASE.replace("Long $150.00", "Long $120.00"))
    assert mismatch.status is CandidateStatus.MISMATCH
    zero = candidate(BASE.replace("Long $150.00", "Long $0.00"))
    assert zero.expected == Decimal("0.00")
    assert zero.status is CandidateStatus.MISMATCH


@pytest.mark.parametrize(
    ("text", "error"),
    [
        (BASE.replace("Account No: 000000\n", ""), "missing_account"),
        (BASE.replace("Period: April", "Period: Foo"), "invalid_period"),
        (BASE.replace("01/02/2024", "13/02/2024"), "invalid_date"),
        (BASE + " note", "unparsed_transaction_line"),
        (BASE.replace(HOLDING, HOLDING + "\nUNKNOWN $500.00"), "unparsed_holding_line"),
        ("Account No: 000000\nPeriod: April - 2024", "no_rows"),
    ],
)
def test_incomplete_coverage_cannot_look_reconciled(text: str, error: str) -> None:
    result = candidate(text)
    assert result.status is CandidateStatus.INCOMPLETE
    assert error in result.coverage_errors


def test_unreconciled_if_no_statement_total() -> None:
    text = BASE.replace("Total Market Value $150.00\n", "").replace("Long $150.00\n", "")
    result = candidate(text)
    assert result.status is CandidateStatus.UNRECONCILED
    assert result.expected is None
    assert result.actual == Decimal("150.00")


def test_refuse_changed_text_and_invalid_source_without_leaking_content() -> None:
    with pytest.raises(ValueError, match="^statement_text_digest_mismatch$"):
        project_streetbeat_candidate(
            BASE + " private", source_kind=SourceKind.FILEOS, evidence=EVIDENCE,
            text_digest=Digest("sha256", hashlib.sha256(BASE.encode()).hexdigest()),
        )
    with pytest.raises(ValueError, match="^invalid_statement_source$"):
        project_streetbeat_candidate(
            BASE, source_kind="fileos", evidence=EVIDENCE,  # type: ignore[arg-type]
            text_digest=Digest("sha256", hashlib.sha256(BASE.encode()).hexdigest()),
        )
    with pytest.raises(ValueError, match="^invalid_statement_text$"):
        project_streetbeat_candidate(
            BASE + "\udcff", source_kind=SourceKind.FILEOS, evidence=EVIDENCE,
            text_digest=Digest("sha256", hashlib.sha256(BASE.encode()).hexdigest()),
        )
    with pytest.raises(ValueError, match="^statement_text_limit$"):
        candidate(BASE + "x" * MAX_TEXT_BYTES)


def test_bounded_thousand_row_repeat_and_row_limit() -> None:
    text = f"Account No: 000000\nPeriod: April - 2024\nLong $100000.00\n{HEADER}\n"
    text += (HOLDING + "\n") * 1000
    first = candidate(text)
    assert first.status is CandidateStatus.RECONCILED
    assert len(first.rows) == 1000
    assert first == candidate(text)
    with pytest.raises(ValueError, match="^statement_row_limit$"):
        candidate(text + (HOLDING + "\n") * 1001)


def test_candidate_is_immutable() -> None:
    result = candidate()
    with pytest.raises(AttributeError):
        result.rows = ()  # type: ignore[misc]
    assert replace(result, status=CandidateStatus.INCOMPLETE).status is CandidateStatus.INCOMPLETE
