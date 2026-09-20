"""Closed, bounded request schemas. Proposals are data, never executable instructions."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchRequest(ClosedModel):
    query: str = Field(min_length=1, max_length=500)
    account_id: UUID | None = None
    limit: int = Field(default=10, ge=1, le=50)
    include_attachments: bool = True


class RulePayload(ClosedModel):
    kind: Literal["rule"]
    sender_domain: str = Field(min_length=1, max_length=253, pattern=r"^[a-z0-9.-]+$")
    category: str = Field(min_length=1, max_length=80)
    canonical_mailbox: Literal["review", "review_delete", "needs_reply"] = "review"


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
