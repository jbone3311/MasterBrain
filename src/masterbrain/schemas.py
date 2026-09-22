"""Closed, bounded request contracts for the source-neutral Brain API."""

from pydantic import Field

from email_brain.schemas import ClosedModel


class BrainSearchRequest(ClosedModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50, strict=True)


class EvidenceContentRequest(ClosedModel):
    max_chars: int = Field(default=4000, ge=1, le=16000, strict=True)
