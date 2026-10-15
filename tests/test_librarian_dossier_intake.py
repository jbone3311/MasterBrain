"""Fictional, side-effect-free intake of the current MasterBrain export format."""

from __future__ import annotations

import pytest

from masterbrain.librarian_dossier_intake import inspect_project_dossier_markdown
from masterbrain.project_dossier_markdown import _HEADER
from masterbrain.project_facts import _markdown_json_text

PROJECT = "project_" + "a" * 32
EVIDENCE = "evidence_" + "b" * 32
OTHER_EVIDENCE = "evidence_" + "c" * 32


def _dossier(*, event: str = "", fact: str = "") -> str:
    return (
        _HEADER
        + f"Project ID: `{PROJECT}`. Recorded cutoff: `2026-10-14T00:00:00+00:00`. "
        "Visibility: `unsuperseded`.\n\n"
        "## Project\n\n"
        f"- project `{PROJECT}`: reviewed title \"Fictional Deal\"; "
        f"derivation unspecified; exact quote \"fictional\"; citation `{EVIDENCE}`.\n"
        "\n## Events\n\n" + event
        + "\n## Commitments\n\n"
        "\n## People and roles\n\n"
        "\n## Related artifacts\n\n"
        "\n## Source-stated project facts\n\n" + fact
    )


def test_empty_sections_are_untrusted_inventory_only():
    result = inspect_project_dossier_markdown(_dossier())
    assert result["claimed_project_id"] == PROJECT
    assert result["section_counts"]["Project"] == 1
    assert result["section_counts"]["Events"] == 0
    assert result["untrusted_content"] is True
    assert result["proposal_ready"] is False
    assert result["staged"] is False
    assert result["candidates"][0]["claimed_citation_ids"] == [EVIDENCE]


def test_fictional_event_and_fact_remain_unreviewed_candidates():
    event = (
        f"- event `event_{'d' * 32}` (review, undated): reviewed title \"Review\"; "
        f"derivation unspecified; exact quote \"fictional\"; citation `{EVIDENCE}`.\n"
    )
    fact = (
        f"- fact `pfact_{'e' * 32}`: `deal.price` = \"100\" "
        f"(asserted; source-stated); exact quote \"fictional\"; "
        f"citation `{OTHER_EVIDENCE}`.\n"
    )
    result = inspect_project_dossier_markdown(_dossier(event=event, fact=fact))
    assert result["section_counts"]["Events"] == 1
    assert result["section_counts"]["Source-stated project facts"] == 1
    assert all(not row["proposal_ready"] for row in result["candidates"])
    assert result == inspect_project_dossier_markdown(_dossier(event=event, fact=fact))


@pytest.mark.parametrize("change", [
    lambda value: value.replace("## Events", "## Infiltrated\n\n- fake\n\n## Events"),
    lambda value: value.replace(f"citation `{EVIDENCE}`", "citation `evidence_wrong`"),
    lambda value: value.replace(f"project `{PROJECT}`", "project `project_" + "f" * 32 + "`"),
    lambda value: value.replace("2026-10-14T00:00:00+00:00", "2026-10-14"),
    lambda value: value + "\n## Injected\n",
    lambda value: value.replace("## Events", "## Source-stated project facts"),
])
def test_malformed_layout_or_claim_refused(change):
    with pytest.raises(ValueError):
        inspect_project_dossier_markdown(change(_dossier()))


def test_size_and_surrogate_refused():
    with pytest.raises(ValueError):
        inspect_project_dossier_markdown(_dossier() + "x" * 66_000)
    with pytest.raises(ValueError):
        inspect_project_dossier_markdown(_dossier() + "\ud800")


def test_duplicate_and_overfull_rows_refused():
    event = (
        f"- event `event_{'d' * 32}` (review, undated): exact quote \"fictional\"; "
        f"citation `{EVIDENCE}`.\n"
    )
    with pytest.raises(ValueError):
        inspect_project_dossier_markdown(_dossier(event=event * 2))
    unique = "".join(
        f"- event `event_{i:032x}`: exact quote \"fictional\"; "
        f"citation `{EVIDENCE}`.\n"
        for i in range(26)
    )
    with pytest.raises(ValueError):
        inspect_project_dossier_markdown(_dossier(event=unique))


def test_escaped_source_text_cannot_add_quote_label_or_citation():
    hostile = 'quoted exact quote; citation `evidence_' + 'f' * 32 + '` <script>'
    markdown = _dossier().replace('"Fictional Deal"', _markdown_json_text(hostile))
    markdown = markdown.replace(
        'exact quote "fictional"', 'exact quote ' + _markdown_json_text(hostile),
    )
    result = inspect_project_dossier_markdown(markdown)
    assert result["candidates"][0]["claimed_quote_previews"] == [hostile]
    assert result["candidates"][0]["claimed_citation_ids"] == [EVIDENCE]


def test_missing_or_noncanonical_quote_preview_refused():
    with pytest.raises(ValueError):
        inspect_project_dossier_markdown(
            _dossier().replace('exact quote "fictional"', 'exact quote ""'),
        )
    with pytest.raises(ValueError):
        inspect_project_dossier_markdown(
            _dossier().replace('exact quote "fictional"', 'exact quote "\\u0066ictional"'),
        )
