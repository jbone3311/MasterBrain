"""Reviewed, evidence-linked KnowledgeCore publication contracts."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, field_validator, model_validator

from email_brain.schemas import ClosedModel

Identity = Annotated[str, Field(pattern=r"^[a-z]+_[a-f0-9]{32}$")]
EvidenceIdentity = Annotated[str, Field(pattern=r"^evidence_[a-f0-9]{32}$")]
Predicate = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{0,99}$")]
KnowledgeKind = Literal[
    "entity", "relationship", "claim", "event", "project", "commitment", "correction"
]


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


class ProjectWrite(AssertionBase):
    kind: Literal["project"]
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=4000)
    state: Literal["proposed", "active", "blocked", "completed", "cancelled", "unknown"]


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


class CorrectionWrite(ClosedModel):
    kind: Literal["correction"]
    target_kind: Literal["entity", "relationship", "claim", "event", "project", "commitment"]
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
    | CorrectionWrite,
    Field(discriminator="kind"),
]


class KnowledgePublishRequest(ClosedModel):
    assertion: KnowledgeAssertion


class KnowledgeSearchRequest(ClosedModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50, strict=True)
    kinds: list[KnowledgeKind] = Field(default_factory=list, max_length=7)

    @field_validator("kinds")
    @classmethod
    def unique_kinds(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("duplicate kinds")
        return values
