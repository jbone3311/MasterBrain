from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from masterbrain.knowledge_schema import (
    CorrectionWrite,
    EntityWrite,
    EventWrite,
    KnowledgePublishRequest,
    KnowledgeSearchRequest,
    ProjectDossierRequest,
    TimelineRequest,
)

NOW = datetime(2026, 9, 22, tzinfo=UTC)
EVIDENCE = "evidence_" + "a" * 32


def entity(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "kind": "entity",
        "entity_type": "person",
        "name": "Alex Example",
        "aliases": ["Alex E."],
        "evidence_ids": [EVIDENCE],
        "source_quote": "Alex Example agreed to the plan.",
        "confidence": 0.9,
        "observed_at": NOW,
        "reviewed": True,
    }
    value.update(updates)
    return value


def test_reviewed_entity_contract_is_closed_and_temporal() -> None:
    parsed = KnowledgePublishRequest.model_validate({"assertion": entity()})
    assert isinstance(parsed.assertion, EntityWrite)
    with pytest.raises(ValidationError):
        KnowledgePublishRequest.model_validate({"assertion": entity(reviewed=False)})
    with pytest.raises(ValidationError):
        KnowledgePublishRequest.model_validate(
            {"assertion": entity(valid_from=NOW, valid_to=NOW - timedelta(seconds=1))}
        )
    with pytest.raises(ValidationError):
        KnowledgePublishRequest.model_validate({"assertion": entity(extra="forbidden")})


def test_aliases_evidence_and_event_intervals_are_strict() -> None:
    with pytest.raises(ValidationError, match="duplicate alias"):
        EntityWrite.model_validate(entity(aliases=["Alex E", " alex   e "]))
    with pytest.raises(ValidationError, match="duplicate evidence"):
        EntityWrite.model_validate(entity(evidence_ids=[EVIDENCE, EVIDENCE]))
    with pytest.raises(ValidationError, match="event end"):
        EventWrite.model_validate(
            {
                "kind": "event",
                "event_type": "meeting",
                "title": "Review",
                "starts_at": NOW,
                "ends_at": NOW,
                "evidence_ids": [EVIDENCE],
                "source_quote": "Review meeting",
                "confidence": 0.9,
                "observed_at": NOW,
                "reviewed": True,
            }
        )


def test_correction_requires_same_kind_replacement() -> None:
    with pytest.raises(ValidationError, match="match target kind"):
        CorrectionWrite.model_validate(
            {
                "kind": "correction",
                "target_kind": "claim",
                "target_id": "claim_" + "1" * 32,
                "replacement_id": "entity_" + "2" * 32,
                "reason": "Wrong value",
                "evidence_ids": [EVIDENCE],
                "source_quote": "Corrected source",
                "observed_at": NOW,
                "reviewed": True,
            }
        )


def test_knowledge_search_visibility_is_closed_and_defaults_to_retained() -> None:
    assert KnowledgeSearchRequest(query="Atlas").visibility == "retained"
    assert KnowledgeSearchRequest(query="Atlas", visibility="unsuperseded").visibility == (
        "unsuperseded"
    )
    with pytest.raises(ValidationError):
        KnowledgeSearchRequest.model_validate({"query": "Atlas", "visibility": "current"})


def test_timeline_requires_bounded_aware_window_and_recorded_cutoff_cursor() -> None:
    request = TimelineRequest(start=NOW, end=NOW + timedelta(days=1))
    assert request.visibility == "unsuperseded" and request.limit == 25
    assert TimelineRequest(
        start=NOW, end=NOW + timedelta(days=366), visibility="retained",
        project_id="project_" + "1" * 32,
    ).project_id == "project_" + "1" * 32
    for update in (
        {"end": NOW},
        {"end": NOW + timedelta(days=367)},
        {"start": NOW.replace(tzinfo=None)},
        {"after": "event_" + "2" * 32},
        {"after": "project_" + "2" * 32, "recorded_cutoff_at": NOW},
        {"project_id": "event_" + "2" * 32},
        {"visibility": "current"},
        {"limit": 51},
        {"extra": "forbidden"},
    ):
        with pytest.raises(ValidationError):
            TimelineRequest.model_validate({
                "start": NOW, "end": NOW + timedelta(days=1), **update,
            })


def test_project_dossier_is_closed_bounded_and_cutoff_aware() -> None:
    request = ProjectDossierRequest()
    assert request.visibility == "unsuperseded"
    assert request.event_limit == request.commitment_limit == 10
    assert ProjectDossierRequest(recorded_cutoff_at=NOW, visibility="retained").visibility == (
        "retained"
    )
    for updates in (
        {"visibility": "current"}, {"event_limit": 0}, {"event_limit": 26},
        {"commitment_limit": True}, {"recorded_cutoff_at": NOW.replace(tzinfo=None)},
        {"unknown": "not allowed"},
    ):
        with pytest.raises(ValidationError):
            ProjectDossierRequest.model_validate(updates)
