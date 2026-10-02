"""Closed, bounded request contracts for the source-neutral Brain API."""

from typing import Literal

from pydantic import Field, field_validator

from email_brain.schemas import ClosedModel
from masterbrain.knowledge_schema import KnowledgeKind


class BrainSearchRequest(ClosedModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50, strict=True)


class FileOSV2SearchPreviewRequest(ClosedModel):
    generation_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,127}$")
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50, strict=True)

    @field_validator("query")
    @classmethod
    def nonempty_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query is empty")
        return value


class EmailFamilySearchRequest(ClosedModel):
    query: str = Field(min_length=1, max_length=500)
    message_limit: int = Field(default=10, ge=1, le=25, strict=True)
    attachment_limit: int = Field(default=10, ge=1, le=25, strict=True)
    document_limit: int = Field(default=10, ge=1, le=25, strict=True)


class EvidenceContentRequest(ClosedModel):
    max_chars: int = Field(default=4000, ge=1, le=16000, strict=True)


class GroundedAnswerRequest(ClosedModel):
    question: str = Field(min_length=1, max_length=500)

    @field_validator("question")
    @classmethod
    def meaningful_question(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("invalid question")
        return value.strip()


class UnifiedSearchRequest(ClosedModel):
    query: str = Field(min_length=1, max_length=500)
    evidence_limit: int = Field(default=10, ge=1, le=25, strict=True)
    knowledge_limit: int = Field(default=10, ge=1, le=25, strict=True)
    knowledge_kinds: list[KnowledgeKind] = Field(default_factory=list, max_length=7)
    evidence_visibility: Literal["retained", "current_fileos"] = "retained"

    @field_validator("knowledge_kinds")
    @classmethod
    def unique_knowledge_kinds(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("duplicate knowledge kinds")
        return values


class CurrentGroupedSearchRequest(ClosedModel):
    query: str = Field(min_length=1, max_length=500)
    fileos_limit: int = Field(default=10, ge=1, le=20, strict=True)
    archive_member_limit: int = Field(default=10, ge=1, le=20, strict=True)
    archive_document_limit: int = Field(default=10, ge=1, le=20, strict=True)
    archive_image_limit: int = Field(default=10, ge=1, le=20, strict=True)
    email_message_limit: int = Field(default=10, ge=1, le=20, strict=True)
    email_attachment_limit: int = Field(default=10, ge=1, le=20, strict=True)
    email_document_limit: int = Field(default=10, ge=1, le=20, strict=True)
    knowledge_limit: int = Field(default=10, ge=1, le=20, strict=True)
    knowledge_kinds: list[KnowledgeKind] = Field(default_factory=list, max_length=7)

    @field_validator("knowledge_kinds")
    @classmethod
    def unique_knowledge_kinds(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("duplicate knowledge kinds")
        return values
