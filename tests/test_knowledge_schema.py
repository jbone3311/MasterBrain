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
    MemberWrite,
    ProjectAliasLookupRequest,
    ProjectArtifactLinkWrite,
    ProjectArtifactPageRequest,
    ProjectDossierRequest,
    ProjectWrite,
    TimelineRequest,
    normalize_project_alias,
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


def test_reviewed_project_aliases_require_cited_distinct_names() -> None:
    base = {
        "kind": "project", "title": "Deal Example", "state": "active",
        "evidence_ids": [EVIDENCE], "source_quote": "Deal Example at 123 Main St.",
        "confidence": 0.9, "observed_at": NOW, "reviewed": True,
    }
    alias = {
        "alias": "123 Main St.", "alias_kind": "address",
        "evidence_id": EVIDENCE, "source_quote": "123 Main St.",
    }
    assert normalize_project_alias(" 123-MAIN, St. ") == "123 main st"
    assert ProjectWrite.model_validate({**base, "aliases": [alias]}).aliases[0].alias_kind == (
        "address"
    )
    for bad in (
        {**base, "aliases": [alias], "reviewed": False},
        {**base, "aliases": [alias, {**alias, "alias": "123-Main St"}]},
        {**base, "aliases": [{**alias, "evidence_id": "evidence_" + "b" * 32}]},
        {**base, "aliases": [{**alias, "alias": "!!!"}]},
        {**base, "aliases": [{**alias, "source_quote": ""}]},
    ):
        with pytest.raises(ValidationError):
            ProjectWrite.model_validate(bad)
    with pytest.raises(ValidationError):
        ProjectAliasLookupRequest(name="!!!")


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


def test_reviewed_project_member_is_closed_evidence_linked_and_temporal() -> None:
    base = {
        "kind": "member", "project_id": "project_" + "1" * 32,
        "entity_id": "entity_" + "2" * 32, "role": "broker",
        "evidence_ids": [EVIDENCE], "source_quote": "Alex brokers this deal.",
        "confidence": 0.9, "observed_at": NOW, "reviewed": True,
    }
    assertion = KnowledgePublishRequest.model_validate({"assertion": base}).assertion
    assert isinstance(assertion, MemberWrite)
    assert assertion.assertion_status == "asserted"
    assert MemberWrite.model_validate({**base, "role": "escrow_agent"}).role == (
        "escrow_agent"
    )  # Advisory vocabulary until the separate registry is implemented.
    assert KnowledgeSearchRequest(query="broker", kinds=["member"]).kinds == ["member"]
    for update in (
        {"reviewed": False}, {"evidence_ids": []},
        {"project_id": "entity_" + "1" * 32},
        {"entity_id": "project_" + "2" * 32},
        {"role": "Broker / Counsel"},
        {"valid_from": NOW, "valid_to": NOW},
        {"unexpected": "field"},
    ):
        with pytest.raises(ValidationError):
            MemberWrite.model_validate({**base, **update})


def test_project_artifact_contract_is_closed_and_quote_is_sql_safe() -> None:
    base = {
        "artifact_evidence_id": EVIDENCE,
        "basis_evidence_id": EVIDENCE,
        "source_quote": "Fictional evidence line",
        "relation": "related",
        "observed_at": NOW,
    }
    assert ProjectArtifactLinkWrite.model_validate(base).assertion_status == "asserted"
    for update in (
        {"source_quote": "bad\x00quote"},
        {"source_quote": "bad\ud800quote"},
        {"relation": "move / delete"},
        {"artifact_evidence_id": "evidence_bad"},
        {"extra": "unexpected"},
    ):
        with pytest.raises(ValidationError):
            ProjectArtifactLinkWrite.model_validate({**base, **update})
    with pytest.raises(ValidationError):
        ProjectArtifactPageRequest(limit=True)
    with pytest.raises(ValidationError):
        ProjectArtifactPageRequest(after="partifact_" + "1" * 32)


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
    assert (
        request.event_limit == request.commitment_limit
        == request.member_limit == request.artifact_limit == 10
    )
    assert ProjectDossierRequest(recorded_cutoff_at=NOW, visibility="retained").visibility == (
        "retained"
    )
    for updates in (
        {"visibility": "current"}, {"event_limit": 0}, {"event_limit": 26},
        {"commitment_limit": True}, {"recorded_cutoff_at": NOW.replace(tzinfo=None)},
        {"member_limit": 0}, {"member_limit": True},
        {"artifact_limit": 0}, {"artifact_limit": 26}, {"artifact_limit": True},
        {"unknown": "not allowed"},
    ):
        with pytest.raises(ValidationError):
            ProjectDossierRequest.model_validate(updates)
