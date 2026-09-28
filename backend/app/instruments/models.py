from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InstrumentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_key: str
    exchange: str
    segment: str
    instrument_type: str
    trading_symbol: str

    underlying_key: str | None = None
    underlying_symbol: str | None = None
    expiry_date: date | None = None
    strike: Decimal | None = None
    option_type: str | None = None
    lot_size: int | None = Field(default=None, gt=0)
    tick_size: Decimal | None = Field(default=None, gt=0)

    is_active: bool = True
    source: str
    source_updated_at: datetime | None = None

    @field_validator("option_type")
    @classmethod
    def validate_option_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.upper()
        if value not in {"CE", "PE"}:
            raise ValueError("option_type must be CE or PE")
        return value
