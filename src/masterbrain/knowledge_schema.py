"""Reviewed, evidence-linked KnowledgeCore publication contracts."""

from __future__ import annotations

import unicodedata
from datetime import timedelta
from typing import Annotated, Any, Literal, Self

from pydantic import AwareDatetime, Field, field_validator, model_validator

from email_brain.schemas import ClosedModel

Identity = Annotated[str, Field(pattern=r"^[a-z]+_[a-f0-9]{32}$")]
EvidenceIdentity = Annotated[str, Field(pattern=r"^evidence_[a-f0-9]{32}$")]
EventIdentity = Annotated[str, Field(pattern=r"^event_[a-f0-9]{32}$")]
CommitmentIdentity = Annotated[str, Field(pattern=r"^commitment_[a-f0-9]{32}$")]
ProjectIdentity = Annotated[str, Field(pattern=r"^project_[a-f0-9]{32}$")]
ProjectArtifactIdentity = Annotated[str, Field(pattern=r"^partifact_[a-f0-9]{32}$")]
ProjectFactIdentity = Annotated[str, Field(pattern=r"^pfact_[a-f0-9]{32}$")]
EntityIdentity = Annotated[str, Field(pattern=r"^entity_[a-f0-9]{32}$")]
Predicate = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{0,99}$")]
KnowledgeKind = Literal[
    "entity", "relationship", "claim", "event", "project", "commitment", "member", "correction"
]
KnowledgeVisibility = Literal["retained", "unsuperseded"]


class AssertionBase(ClosedModel):
    evidence_ids: list[EvidenceIdentity] = Field(min_length=1, max_length=20)
    source_quote: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    observed_at: AwareDatetime
    valid_from: AwareDatetime | None = None
    valid_to: AwareDatetime | None = None
    supersedes_id: Identity | None = None
    reviewed: Literal[True]

    @field_validator("evidence_ids")
    @classmethod
    def unique_evidence(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("duplicate evidence")
        return values

    @model_validator(mode="after")
    def interval(self) -> Self:
        if self.valid_to is not None and (
            self.valid_from is None or self.valid_to <= self.valid_from
        ):
            raise ValueError("valid_to must follow valid_from")
        return self


class EntityWrite(AssertionBase):
    kind: Literal["entity"]
    entity_type: Literal["person", "organization", "place", "account", "artifact", "other"]
    name: str = Field(min_length=1, max_length=300)
    aliases: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("aliases")
    @classmethod
    def safe_aliases(cls, values: list[str]) -> list[str]:
        normalized: set[str] = set()
        for value in values:
            if not value or len(value) > 300 or "\x00" in value:
                raise ValueError("invalid alias")
            clean = " ".join(value.casefold().split())
            if clean in normalized:
                raise ValueError("duplicate alias")
            normalized.add(clean)
        return values


class RelationshipWrite(AssertionBase):
    kind: Literal["relationship"]
    subject_entity_id: Identity
    predicate: Predicate
    object_entity_id: Identity
    assertion_status: Literal["asserted", "disputed", "retracted"] = "asserted"

    @model_validator(mode="after")
    def endpoints(self) -> Self:
        if self.subject_entity_id == self.object_entity_id:
            raise ValueError("relationship endpoints must differ")
        return self


class ClaimWrite(AssertionBase):
    kind: Literal["claim"]
    subject_entity_id: Identity
    predicate: Predicate
    value: str = Field(min_length=1, max_length=4000)
    value_type: Literal["text", "number", "date", "boolean", "reference"] = "text"
    assertion_status: Literal["asserted", "disputed", "retracted"] = "asserted"


def normalize_project_alias(value: str) -> str:
    """Casefold and separate Unicode punctuation; never infer semantic equivalence."""
    folded = unicodedata.normalize("NFKC", value).casefold()
    separated = "".join(
        " " if char.isspace() or unicodedata.category(char).startswith("P") else char
        for char in folded
    )
    return " ".join(separated.split())


class ProjectAliasWrite(ClosedModel):
    alias: str = Field(min_length=1, max_length=300)
    alias_kind: Literal["name", "address", "legal_entity", "folder", "other"]
    evidence_id: EvidenceIdentity
    source_quote: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def meaningful(self) -> Self:
        if ("\x00" in self.alias or "\x00" in self.source_quote
                or not 1 <= len(normalize_project_alias(self.alias)) <= 300):
            raise ValueError("invalid project alias")
        return self


class ProjectWrite(AssertionBase):
    kind: Literal["project"]
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=4000)
    state: Literal["proposed", "active", "blocked", "completed", "cancelled", "unknown"]
    aliases: list[ProjectAliasWrite] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def alias_evidence(self) -> Self:
        normalized_title = normalize_project_alias(self.title)
        if not 1 <= len(normalized_title) <= 300:
            raise ValueError("invalid project title for lookup")
        seen = {normalized_title}
        for item in self.aliases:
            if item.evidence_id not in self.evidence_ids:
                raise ValueError("project alias evidence must belong to the assertion")
            normalized = normalize_project_alias(item.alias)
            if normalized in seen:
                raise ValueError("duplicate project alias")
            seen.add(normalized)
        return self


class EventWrite(AssertionBase):
    kind: Literal["event"]
    event_type: Predicate
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=4000)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    project_id: Identity | None = None

    @model_validator(mode="after")
    def event_interval(self) -> Self:
        if self.ends_at is not None and (self.starts_at is None or self.ends_at <= self.starts_at):
            raise ValueError("event end must follow start")
        return self


class CommitmentWrite(AssertionBase):
    kind: Literal["commitment"]
    description: str = Field(min_length=1, max_length=4000)
    state: Literal["proposed", "open", "completed", "cancelled", "overdue", "unknown"]
    owner_entity_id: Identity | None = None
    counterparty_entity_id: Identity | None = None
    project_id: Identity | None = None
    due_at: AwareDatetime | None = None


class MemberWrite(AssertionBase):
    kind: Literal["member"]
    project_id: ProjectIdentity
    entity_id: EntityIdentity
    role: Predicate
    assertion_status: Literal["asserted", "disputed", "retracted"] = "asserted"


class CorrectionWrite(ClosedModel):
    kind: Literal["correction"]
    target_kind: Literal[
        "entity", "relationship", "claim", "event", "project", "commitment", "member"
    ]
    target_id: Identity
    replacement_id: Identity
    reason: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[EvidenceIdentity] = Field(min_length=1, max_length=20)
    source_quote: str = Field(min_length=1, max_length=2000)
    observed_at: AwareDatetime
    reviewed: Literal[True]

    @model_validator(mode="after")
    def targets(self) -> Self:
        if self.target_id == self.replacement_id:
            raise ValueError("correction requires a replacement")
        prefix = self.target_kind + "_"
        if not self.target_id.startswith(prefix) or not self.replacement_id.startswith(prefix):
            raise ValueError("correction identities must match target kind")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("duplicate evidence")
        return self


KnowledgeAssertion = Annotated[
    EntityWrite
    | RelationshipWrite
    | ClaimWrite
    | ProjectWrite
    | EventWrite
    | CommitmentWrite
    | MemberWrite
    | CorrectionWrite,
    Field(discriminator="kind"),
]


class KnowledgePublishRequest(ClosedModel):
    assertion: KnowledgeAssertion


class KnowledgeProposalStageRequest(ClosedModel):
    """Unreviewed source-stated rows; `reviewed` is forbidden in every payload."""

    proposals: list[dict[str, Any]] = Field(min_length=1, max_length=50)

    @field_validator("proposals")
    @classmethod
    def no_review_marker(cls, values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if any("reviewed" in value for value in values):
            raise ValueError("proposal payload cannot claim review")
        return values


class KnowledgeProposalDecision(ClosedModel):
    proposal_id: Annotated[str, Field(pattern=r"^kproposal_[a-f0-9]{32}$")]
    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def reason_contract(self) -> Self:
        if self.decision == "approved" and self.reason is not None:
            raise ValueError("approval does not take a reason")
        if self.decision == "rejected" and (
            self.reason is None or not self.reason.strip()
        ):
            raise ValueError("rejection requires a reason")
        return self


class KnowledgeProposalReviewRequest(ClosedModel):
    batch_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    decisions: list[KnowledgeProposalDecision] = Field(min_length=1, max_length=50)

    @field_validator("decisions")
    @classmethod
    def unique_rows(
        cls, values: list[KnowledgeProposalDecision]
    ) -> list[KnowledgeProposalDecision]:
        if len({item.proposal_id for item in values}) != len(values):
            raise ValueError("duplicate proposal decision")
        return values


class FactProposalDecision(ClosedModel):
    proposal_id: Annotated[str, Field(pattern=r"^kfproposal_[a-f0-9]{32}$")]
    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def reason_contract(self) -> Self:
        if self.decision == "approved" and self.reason is not None:
            raise ValueError("approval does not take a reason")
        if self.decision == "rejected" and (
            self.reason is None or not self.reason.strip()
        ):
            raise ValueError("rejection requires a reason")
        return self


class FactProposalReviewRequest(ClosedModel):
    batch_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    decisions: list[FactProposalDecision] = Field(min_length=1, max_length=50)

    @field_validator("decisions")
    @classmethod
    def unique_rows(cls, values: list[FactProposalDecision]) -> list[FactProposalDecision]:
        if len({item.proposal_id for item in values}) != len(values):
            raise ValueError("duplicate fact proposal decision")
        return values


class ArtifactProposalDecision(ClosedModel):
    proposal_id: Annotated[str, Field(pattern=r"^kaproposal_[a-f0-9]{32}$")]
    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def reason_contract(self) -> Self:
        if self.decision == "approved" and self.reason is not None:
            raise ValueError("approval does not take a reason")
        if self.decision == "rejected" and (
            self.reason is None or not self.reason.strip()
        ):
            raise ValueError("rejection requires a reason")
        return self


class ArtifactProposalReviewRequest(ClosedModel):
    batch_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    decisions: list[ArtifactProposalDecision] = Field(min_length=1, max_length=50)

    @field_validator("decisions")
    @classmethod
    def unique_rows(
        cls, values: list[ArtifactProposalDecision],
    ) -> list[ArtifactProposalDecision]:
        if len({item.proposal_id for item in values}) != len(values):
            raise ValueError("duplicate artifact proposal decision")
        return values


class KnowledgeSearchRequest(ClosedModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50, strict=True)
    kinds: list[KnowledgeKind] = Field(default_factory=list, max_length=8)
    visibility: KnowledgeVisibility = "retained"

    @field_validator("kinds")
    @classmethod
    def unique_kinds(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("duplicate kinds")
        return values


class TimelineRequest(ClosedModel):
    start: AwareDatetime
    end: AwareDatetime
    project_id: ProjectIdentity | None = None
    visibility: KnowledgeVisibility = "unsuperseded"
    limit: int = Field(default=25, ge=1, le=50)
    recorded_cutoff_at: AwareDatetime | None = None
    after: EventIdentity | None = None

    @model_validator(mode="after")
    def window_and_cursor(self) -> Self:
        if self.end <= self.start or self.end - self.start > timedelta(days=366):
            raise ValueError("timeline window must be positive and at most 366 days")
        if self.after is not None and self.recorded_cutoff_at is None:
            raise ValueError("timeline cursor requires recorded_cutoff_at")
        return self


class DueCommitmentsRequest(ClosedModel):
    start: AwareDatetime
    end: AwareDatetime
    project_id: ProjectIdentity | None = None
    state: Literal["proposed", "open", "completed", "cancelled", "overdue", "unknown"] | None = None
    visibility: KnowledgeVisibility = "unsuperseded"
    limit: int = Field(default=25, ge=1, le=50)
    recorded_cutoff_at: AwareDatetime | None = None
    after: CommitmentIdentity | None = None

    @model_validator(mode="after")
    def window_and_cursor(self) -> Self:
        if self.end <= self.start or self.end - self.start > timedelta(days=366):
            raise ValueError("due window must be positive and at most 366 days")
        if self.after is not None and self.recorded_cutoff_at is None:
            raise ValueError("due cursor requires recorded_cutoff_at")
        return self


class ProjectDossierRequest(ClosedModel):
    visibility: KnowledgeVisibility = "unsuperseded"
    event_limit: int = Field(default=10, ge=1, le=25)
    commitment_limit: int = Field(default=10, ge=1, le=25)
    member_limit: int = Field(default=10, ge=1, le=25)
    artifact_limit: int = Field(default=10, ge=1, le=25)
    fact_limit: int = Field(default=10, ge=1, le=25)
    recorded_cutoff_at: AwareDatetime | None = None

    @field_validator(
        "event_limit", "commitment_limit", "member_limit", "artifact_limit",
        "fact_limit", mode="before"
    )
    @classmethod
    def integer_limit(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean limit is invalid")
        return value


class ProjectFactWrite(AssertionBase):
    kind: Literal["project_fact"]
    project_id: ProjectIdentity
    predicate: Predicate
    value: str = Field(min_length=1, max_length=4000)
    value_type: Literal["text", "number", "date", "boolean", "reference"] = "text"
    assertion_status: Literal["asserted", "disputed", "retracted"] = "asserted"
    derivation: Literal["source_stated"] = "source_stated"
    quote_evidence_id: EvidenceIdentity

    @model_validator(mode="after")
    def quote_basis(self) -> Self:
        if self.quote_evidence_id not in self.evidence_ids:
            raise ValueError("quote evidence must belong to the fact evidence set")
        if "\x00" in self.source_quote or "\x00" in self.value:
            raise ValueError("project fact text contains NUL")
        self.source_quote.encode("utf-8", errors="strict")
        self.value.encode("utf-8", errors="strict")
        return self


class ProjectFactPageRequest(ClosedModel):
    visibility: KnowledgeVisibility = "unsuperseded"
    limit: int = Field(default=25, ge=1, le=25)
    recorded_cutoff_at: AwareDatetime | None = None
    after: ProjectFactIdentity | None = None

    @field_validator("limit", mode="before")
    @classmethod
    def integer_limit(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean limit is invalid")
        return value

    @model_validator(mode="after")
    def page_anchor(self) -> Self:
        if self.after is not None and self.recorded_cutoff_at is None:
            raise ValueError("fact cursor requires recorded_cutoff_at")
        return self


class ProjectArtifactLinkWrite(ClosedModel):
    artifact_evidence_id: EvidenceIdentity
    basis_evidence_id: EvidenceIdentity
    source_quote: str = Field(min_length=1, max_length=2000)
    relation: Predicate
    assertion_status: Literal["asserted", "retracted"] = "asserted"
    observed_at: AwareDatetime

    @field_validator("source_quote")
    @classmethod
    def valid_quote(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("source quote contains NUL")
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
            raise ValueError("source quote is not valid UTF-8") from None
        return value


class ProjectArtifactPageRequest(ClosedModel):
    limit: int = Field(default=10, ge=1, le=25)
    recorded_cutoff_at: AwareDatetime | None = None
    after: ProjectArtifactIdentity | None = None

    @field_validator("limit", mode="before")
    @classmethod
    def integer_limit(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean limit is invalid")
        return value

    @model_validator(mode="after")
    def cursor_needs_cutoff(self) -> Self:
        if self.after is not None and self.recorded_cutoff_at is None:
            raise ValueError("artifact cursor requires recorded_cutoff_at")
        return self


class ProjectAliasLookupRequest(ClosedModel):
    name: str = Field(min_length=1, max_length=300)
    limit: int = Field(default=25, ge=1, le=25)

    @field_validator("limit", mode="before")
    @classmethod
    def integer_limit(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean limit is invalid")
        return value

    @field_validator("name")
    @classmethod
    def meaningful_name(cls, value: str) -> str:
        if "\x00" in value or not 1 <= len(normalize_project_alias(value)) <= 300:
            raise ValueError("invalid project alias query")
        return value
