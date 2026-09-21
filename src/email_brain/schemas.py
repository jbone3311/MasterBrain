"""Closed, bounded request schemas. Proposals are data, never executable instructions."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*")
    @classmethod
    def safe_text(cls, value: object) -> object:
        if isinstance(value, str):
            if "\x00" in value:
                raise ValueError("NUL is not valid persisted text")
            try:
                value.encode("utf-8", errors="strict")
            except UnicodeError:
                raise ValueError("text must be valid Unicode") from None
        return value


class SearchRequest(ClosedModel):
    query: str = Field(min_length=1, max_length=500)
    account_id: UUID | None = None
    limit: int = Field(default=10, ge=1, le=50)
    include_attachments: bool = True
    include_documents: bool = False


class DocumentRequest(ClosedModel):
    expected_processor_version: str = Field(pattern=r"^sandbox-pdf-v1-[a-f0-9]{64}$")
    policy_version: Literal["synthetic-unscanned-pdf-v1"]


class RecoveryRequest(ClosedModel):
    expected_parser_version: str = Field(min_length=1, max_length=100)


class RulePayload(ClosedModel):
    kind: Literal["rule"]
    sender_domain: str = Field(min_length=1, max_length=253, pattern=r"^[a-z0-9.-]+$")
    category: str = Field(min_length=1, max_length=80)
    canonical_mailbox: Literal["review", "review_delete", "needs_reply"] = "review"

    @field_validator("sender_domain")
    @classmethod
    def valid_domain(cls, value: str) -> str:
        labels = value.split(".")
        if any(
            not 1 <= len(label) <= 63 or label.startswith("-") or label.endswith("-")
            for label in labels
        ):
            raise ValueError("exact DNS domain required")
        return value


class RuleSimulationRequest(ClosedModel):
    expected_version: int = Field(ge=1, strict=True)


class RuleActivationRequest(ClosedModel):
    simulation_id: UUID


class RuleRollbackRequest(ClosedModel):
    expected_revision: int = Field(ge=1, strict=True)
    target_revision: int = Field(ge=0, strict=True)


class ProjectPayload(ClosedModel):
    kind: Literal["project"]
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


class FactPayload(ClosedModel):
    kind: Literal["fact"]
    subject: str = Field(min_length=1, max_length=200)
    predicate: Literal["affiliated_with", "invested_in", "waiting_on", "deadline", "other"]
    value: str = Field(min_length=1, max_length=2000)


class FeaturePayload(ClosedModel):
    kind: Literal["feature"]
    title: str = Field(min_length=1, max_length=200)
    desired_outcome: str = Field(min_length=1, max_length=4000)


class CorrectionPayload(ClosedModel):
    kind: Literal["correction"]
    message_id: UUID
    desired_category: str = Field(min_length=1, max_length=80)


ProposalPayload = Annotated[
    RulePayload | ProjectPayload | FactPayload | FeaturePayload | CorrectionPayload,
    Field(discriminator="kind"),
]


class ProposalRequest(ClosedModel):
    payload: ProposalPayload
    reason: str = Field(min_length=1, max_length=2000)
    source: str = Field(min_length=1, max_length=80)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=20)


class ReviewRequest(ClosedModel):
    decision: Literal["approved", "rejected"]
    expected_version: int = Field(ge=1)


class Classification(ClosedModel):
    category: Literal["personal", "business", "investment", "receipt", "promotion", "unknown"]
    needs_reply: bool
    confidence: float = Field(ge=0, le=1)
    evidence_excerpt: str = Field(max_length=500)
