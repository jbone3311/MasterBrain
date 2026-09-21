"""Typed, bounded owner-reviewed claims; never payment or airline verification."""

from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, Field, TypeAdapter, field_validator, model_validator

from email_brain.schemas import ClosedModel

Text = Annotated[str, Field(min_length=1, max_length=200)]
Code = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
Amount = Annotated[str, Field(pattern=r"^(0|[1-9][0-9]{0,11})(\.[0-9]{1,4})?$")]


class MemoryBase(ClosedModel):
    title: Text


class Trip(MemoryBase):
    kind: Literal["trip"]
    status: Literal["planned", "cancelled", "completed", "unknown"] = "unknown"
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def dates(self) -> Self:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("trip end precedes start")
        return self


class FlightSegment(ClosedModel):
    flight_number: Text | None = None
    origin: Code | None = None
    destination: Code | None = None
    departure: AwareDatetime | None = None
    arrival: AwareDatetime | None = None

    @model_validator(mode="after")
    def chronology(self) -> Self:
        if self.departure and self.arrival and self.arrival <= self.departure:
            raise ValueError("arrival must follow departure")
        return self


class Flight(MemoryBase):
    kind: Literal["flight"]
    status: Literal["confirmed", "changed", "cancelled", "unknown"] = "unknown"
    airline: Text | None = None
    confirmation: Text | None = None
    travelers: list[Text] = Field(default_factory=list, max_length=10)
    segments: list[FlightSegment] = Field(default_factory=list, max_length=8)

    @field_validator("travelers")
    @classmethod
    def safe_travelers(cls, values: list[str]) -> list[str]:
        for value in values:
            cls.safe_text(value)
        if len(set(values)) != len(values):
            raise ValueError("duplicate traveler")
        return values


class Hotel(MemoryBase):
    kind: Literal["hotel"]
    status: Literal["confirmed", "changed", "cancelled", "unknown"] = "unknown"
    hotel: Text | None = None
    confirmation: Text | None = None
    location: Text | None = None
    check_in: date | None = None
    check_out: date | None = None
    timezone: Text | None = None

    @field_validator("timezone")
    @classmethod
    def known_zone(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                ZoneInfo(value)
            except (ValueError, ZoneInfoNotFoundError):
                raise ValueError("IANA time zone required") from None
        return value

    @model_validator(mode="after")
    def dates(self) -> Self:
        if self.check_in and self.check_out and self.check_out <= self.check_in:
            raise ValueError("checkout must follow checkin")
        return self


class Bill(MemoryBase):
    kind: Literal["bill"]
    status: Literal["due", "paid", "disputed", "cancelled", "unknown"] = "unknown"
    vendor: Text | None = None
    invoice_number: Text | None = None
    due_date: date | None = None
    amount: Amount | None = None
    currency: Code | None = None

    @model_validator(mode="after")
    def money(self) -> Self:
        if (self.amount is None) != (self.currency is None):
            raise ValueError("amount and currency must be supplied together")
        return self


MemoryPayload = Annotated[Trip | Flight | Hotel | Bill, Field(discriminator="kind")]
PAYLOAD: TypeAdapter[Trip | Flight | Hotel | Bill] = TypeAdapter(MemoryPayload)


class MemoryWrite(ClosedModel):
    expected_revision: int = Field(ge=0, strict=True)
    evidence_id: UUID
    source_quote: str = Field(min_length=1, max_length=2000)
    parent_trip_id: UUID | None = None
    payload: MemoryPayload
    reviewed: bool = Field(strict=True)

    @field_validator("reviewed")
    @classmethod
    def explicit_review(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("explicit review required")
        return value

    @model_validator(mode="after")
    def parent(self) -> Self:
        if self.parent_trip_id and self.payload.kind not in {"flight", "hotel"}:
            raise ValueError("only reservations can link to a trip")
        return self
