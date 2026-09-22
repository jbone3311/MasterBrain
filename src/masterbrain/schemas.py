"""Closed, bounded request contracts for the source-neutral Brain API."""

from pydantic import Field, field_validator

from email_brain.schemas import ClosedModel
from masterbrain.knowledge_schema import KnowledgeKind


class BrainSearchRequest(ClosedModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50, strict=True)


class EvidenceContentRequest(ClosedModel):
    max_chars: int = Field(default=4000, ge=1, le=16000, strict=True)


class UnifiedSearchRequest(ClosedModel):
    query: str = Field(min_length=1, max_length=500)
    evidence_limit: int = Field(default=10, ge=1, le=25, strict=True)
    knowledge_limit: int = Field(default=10, ge=1, le=25, strict=True)
    knowledge_kinds: list[KnowledgeKind] = Field(default_factory=list, max_length=7)

    @field_validator("knowledge_kinds")
    @classmethod
    def unique_knowledge_kinds(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("duplicate knowledge kinds")
        return values
