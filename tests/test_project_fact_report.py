"""Page-local, nonfinancial grouping of already authorized fictional facts."""

from datetime import UTC, datetime

from masterbrain.project_facts import _report_from_fact_page


def _row(predicate: str, value: str, status: str = "asserted", *, short: bool = False):
    return {
        "predicate": predicate, "value_preview": value,
        "value_truncated": short, "assertion_status": status,
        "evidence_ids": ["evidence_" + "1" * 32],
        "quote_evidence_id": "evidence_" + "1" * 32,
    }


def test_report_groups_without_amounts_or_certifying_conflicts():
    page = {
        "project_id": "project_" + "2" * 32,
        "results": [
            _row("capital.amount", "100 fictional units"),
            _row("capital.amount", "200 fictional units"),
            _row("capital.amount", "100 fictional units", "disputed"),
            _row("deal.note", "fictional note"),
        ],
        "next_cursor": None,
        "recorded_cutoff_at": datetime(2026, 10, 15, tzinfo=UTC),
        "limit": 25, "visibility": "unsuperseded",
    }
    report = _report_from_fact_page(page, after=None)
    assert [group["predicate"] for group in report["groups"]] == [
        "capital.amount", "deal.note",
    ]
    money = report["groups"][0]
    assert money["different_asserted_previews_on_page"] is True
    assert money["has_disputed_or_retracted_on_page"] is True
    assert money["comparison_incomplete"] is False
    assert len(money["facts"]) == 3
    assert report["numeric_aggregation"] == "none_units_currency_ownership_unverified"
    assert "total" not in report


def test_report_marks_page_and_truncated_value_comparison_incomplete():
    page = {
        "project_id": "project_" + "2" * 32,
        "results": [_row("capital.amount", "100", short=True)],
        "next_cursor": "pfact_" + "3" * 32,
        "recorded_cutoff_at": datetime(2026, 10, 15, tzinfo=UTC),
        "limit": 1, "visibility": "retained",
    }
    report = _report_from_fact_page(page, after=None)
    assert report["groups"][0]["comparison_incomplete"] is True
    assert report["next_cursor"] == page["next_cursor"]
    assert _report_from_fact_page({**page, "next_cursor": None}, after="pfact_" + "4" * 32)[
        "groups"
    ][0]["comparison_incomplete"] is True
