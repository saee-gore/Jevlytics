"""Strict request, tool-argument and response schemas.

Every model forbids unknown fields. A tool-argument payload that contains merchant_id, tenant,
role, SQL, or any other unexpected key fails validation before any analytics code runs.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

CardType = Literal["CREDIT", "DEBIT"]
CardNetwork = Literal["VISA", "MASTERCARD", "AMEX", "DISCOVER"]
TransactionStatus = Literal["APPROVED", "DECLINED", "PENDING", "REVERSED", "REFUNDED"]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
Region = Annotated[str, StringConstraints(pattern=r"^[A-Z0-9-]{2,32}$")]

ResponseStatus = Literal[
    "answered",
    "clarification_required",
    "unsupported",
    "blocked",
    "temporarily_unavailable",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class DateRange(StrictModel):
    start: date
    end: date

    @model_validator(mode="after")
    def _ordered(self) -> DateRange:
        if self.end < self.start:
            raise ValueError("end must be on or after start")
        return self


# --- Tool argument models (one per registered tool) ------------------------------------------------


class VolumeArgs(StrictModel):
    date_range: DateRange
    card_type: CardType | None = None
    card_network: CardNetwork | None = None
    currency: Currency | None = None


class CountArgs(StrictModel):
    date_range: DateRange
    card_type: CardType | None = None
    card_network: CardNetwork | None = None
    status: TransactionStatus | None = None


class DeclineReasonsArgs(StrictModel):
    date_range: DateRange
    card_type: CardType | None = None
    card_network: CardNetwork | None = None


class DeclineRateArgs(StrictModel):
    date_range: DateRange
    card_type: CardType | None = None
    card_network: CardNetwork | None = None


class SettlementVolumeArgs(StrictModel):
    date_range: DateRange
    currency: Currency | None = None


class ChargebackRateArgs(StrictModel):
    date_range: DateRange
    card_type: CardType | None = None
    region: Region | None = None


class CardTypePerformanceArgs(StrictModel):
    date_range: DateRange
    currency: Currency | None = None


class RegionVolumeArgs(StrictModel):
    date_range: DateRange
    card_type: CardType | None = None


class FraudIndicatorsArgs(StrictModel):
    date_range: DateRange
    card_type: CardType | None = None


# --- API request / response -------------------------------------------------------------------------


class ChatRequest(StrictModel):
    """The only client-controlled input. There is deliberately no merchant_id or role field."""

    message: str = Field(min_length=1, max_length=4000)


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ResponseStatus
    answer: str | None
    tool_used: str | None = None
    filters: dict[str, Any] | None = None
    data: dict[str, Any] | None = None
    chart: dict[str, Any] | None = None
    request_id: str


class CapabilityItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str
    min_role: str


class CapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    capabilities: list[CapabilityItem]
    request_id: str
